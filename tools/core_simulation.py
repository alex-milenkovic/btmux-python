"""Run core simulation JSON workflows. Schema: docs/core-simulation-cli.md."""
import argparse
from copy import deepcopy
from dataclasses import asdict, is_dataclass, replace
import json
import sys
from types import SimpleNamespace

from tools.combat_resolution import CombatSession, unique_fields, reject_constant
from tools.damage_criticals import SECTION_FIELDS, SLOT_FIELDS
from tools.movement_inputs import fields, number, boolean, array, string
from entities.mech import MechStatus, UnitType
from entities.pilot import Pilot
from entities.weapon import get_weapon
from core.events import EventType, SOURCE_EVENT_IDS, SOURCE_EVENT_NAMES
from core.randomness import RandomState
from systems.economy import CostTables

CORE_INTS = ('engine_rating','bv','bv_last','original_sinks','real_num_sinks','pilot_status','repair_remaining',
    'fuel','fuel_orig','fuel_max','carried_cargo','last_startup','last_use','turn_damage','stagger_damage',
    'stagger_level','last_stagger_notify','last_comm','comm_last','lateral','last_heat_tick','jump_heading',
    'disabled_sinks','engine_hits','gyro_hits','sensor_hits','pilot_skill_base','base_to_hit','unusable_arcs',
    'rnd','last_rnd_update','vis_mod','comm','per','last_stagger_check','stagger_stamp',
    'last_weapon_recycle','going_x','going_y','last_fall_levels','mapflag','x','y','mapindex','facing','hs_engine_override','stall')
CORE_FLOATS = ('jump_length','start_fx','start_fy','start_fz','end_fx','end_fy','jump_pos','jump_top',
    'engine_heat','plus_heat','minus_heat','weap_heat','jump_speed','max_speed','speed','desired_speed')
CORE_BOOLS = ('quiet','valid_object','free_fuel','dug_in','digging','out_of_control')
CORE_TEXT = ('mechskills','template_ref','preferred_contact_id','contact_id')
ACTOR_BOOLS = ('valid','alive','robot','hardcode','is_player','connected','ansimap','wizard','security','royalty','inherit','maneuvering_ace','melee_specialist','sixth_sense','dodge_maneuver')
ACTOR_TEXT = ('name','mapcolor','tacsize','lrsheight','heatchars','contact_options')
ACTOR_INTS = ('id','owner','location','gunnery','piloting','spotting','artillery','perception','technician')


def serialized(value):
    if is_dataclass(value): return serialized(asdict(value))
    if isinstance(value,dict): return {str(k):serialized(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [serialized(item) for item in value]
    if isinstance(value,set): return sorted(serialized(item) for item in value)
    if value is None or isinstance(value,(str,int,float,bool)): return value
    raise ValueError('result contains an unsupported object: '+type(value).__name__)


def actor_from(record, unit):
    fields(record,ACTOR_BOOLS+ACTOR_INTS+ACTOR_TEXT+('skills','health'))
    actor = Pilot(name=record.get('name','MechWarrior'),gunnery=4,piloting=5)
    actor._id, actor.location = 10000 + unit._id, unit._id
    for key,value in record.items():
        if key in ACTOR_BOOLS: value = boolean(value)
        elif key in ACTOR_INTS: value = number(value,integer=True)
        elif key in ACTOR_TEXT: value = string(value)
        elif key == 'skills':
            if not isinstance(value,dict): raise ValueError('skills must be an object')
            value = {string(k):number(v,-100,100,True) for k,v in value.items()}
        elif key == 'health':
            fields(value,('build','bruise','lethal'))
            value = {k:number(v,0,100000,True) for k,v in value.items()}
        setattr(actor,'_id' if key=='id' else key,value)
    return actor


class CoreSession(CombatSession):
    def __init__(self, document):
        document = deepcopy(fields(document,('map','maps','units','objects','templates','costs','config','random','actions','pending_events','diagnostic_cache'),('actions',)))
        maps = array(document.pop('maps',[]))
        if maps and 'map' in document: raise ValueError('supply map or maps, not both')
        if maps: document['map'] = deepcopy(maps[0])
        objects, templates, costs = (document.pop(key,[]) for key in ('objects','templates','costs'))
        self.costs = CostTables()
        self.event_trace = []
        self.heartbeat_trace = []
        random_spec = fields(document.get('random',{}),('seed','array_seed','raw32','streams'))
        if sum(key in random_spec for key in ('seed','array_seed','raw32')) > 1: raise ValueError('choose one MT initialization')
        self.strict_streams = 'streams' in random_spec
        # Configure MT before the parent's ordinary contact acquisition.
        self.random_spec = deepcopy(random_spec)
        document['random'] = {key:value for key,value in random_spec.items() if key in ('seed','streams')}
        if 'seed' in random_spec: number(random_spec['seed'],integer=True)
        self.core_map_spec = self.map_fields(document.setdefault('map',{}))
        config = document.setdefault('config',{})
        initial_global_tick = number(config.pop('initial_global_tick',0),0,2**32-1,True)
        explode_reactor = number(config.pop('explode_reactor',1),0,2**31-1,True)
        extra_config = {key:config.pop(key) for key in ('extended_gunnery','extended_piloting','complexrepair','cost_debug','nofusion_vtol_fuel','random_state') if key in config}
        document.setdefault('units',[{'name':'u'}])
        for record in array(document['units']): record.setdefault('target',-1)
        config.setdefault('lock_tick',8)
        super().__init__(document)
        self.engine.global_tick = initial_global_tick
        self.engine.explode_reactor = explode_reactor
        for key,value in extra_config.items(): setattr(self.engine,key,boolean(value))
        self.maps = {}
        self.apply_map_fields(self.map,self.core_map_spec,'main')
        for index,record in enumerate(maps[1:],1):
            specification = deepcopy(record)
            extra = self.map_fields(specification)
            # Use the existing map fixture validator without creating gameplay units.
            other = CombatSession({'map':specification,'units':[],'config':{'periodic_updates':False},'actions':[]}).map
            self.apply_map_fields(other,extra,'map'+str(index))
            self.engine.register_entity(other)
        for record in document['units']:
            unit = self.units[record['name']]
            wanted = record.get('map',self.map.name)
            board = self.maps[wanted]
            if board is not unit.map:
                unit.map.remove_mech(unit)
                board.add_mech(unit)
            unit.mapindex = board._id
            if not board.valid(unit.x,unit.y): raise ValueError('off-map unit')
        self.acquire_contacts_ready = True
        self.acquire_contacts()
        self.objects = {}
        ids = {u._id for u in self.units.values()} | {m._id for m in self.maps.values()}
        if len(ids) != len(self.units) + len(self.maps): raise ValueError('duplicate object ID')
        for record in array(objects):
            fields(record,('name','id','type','mymech','weaplist'),('name','id','type'))
            name, ident = string(record['name']), number(record['id'],0,integer=True)
            if ident in ids or name in self.objects: raise ValueError('duplicate object')
            if record['type'] not in ('AUTO','OTHER'): raise ValueError('unsupported object type')
            ids.add(ident)
            obj = SimpleNamespace(_id=ident,xcode_type=record['type'],mymech=self.units[record['mymech']] if record.get('mymech') else None,
                                  weaplist=deepcopy(record.get('weaplist')),external_effects=[])
            self.objects[name] = obj
            self.engine.register_entity(obj)
        self.engine.templates = {}
        self.template_inputs = {}
        for record in array(templates):
            fields(record,('name','unit'),('name','unit'))
            name = string(record['name'])
            if name in self.engine.templates: raise ValueError('duplicate template')
            fixture = deepcopy(record['unit'])
            fixture.setdefault('name','template')
            session = CoreSession({'units':[fixture],'config':{'periodic_updates':False},'actions':[]})
            self.engine.templates[name] = session.units[fixture['name']]
            self.template_inputs[name] = deepcopy(fixture)
            for index,weapon in session.weapon_overrides.items():
                if index in self.weapon_overrides and self.weapon_overrides[index] != weapon: raise ValueError('inconsistent template catalog metadata')
                self.weapon_overrides[index] = weapon
        for record in array(costs):
            fields(record,('part','value'),('part','value'))
            self.costs.set(number(record['part'],1,1023,True),number(record['value'],0,2**64-1,True))
        self.engine.events.observe_execution = self.observe_event
        self.engine.observe_heartbeat_dispatch = self.observe_heartbeat

    def observe_heartbeat(self, entity):
        self.heartbeat_trace.append(dict(id=entity._id,type=self.engine._object_type_of(entity),
            wall=self.engine.sim_now,event=self.engine.muxevent_tick,
            global_tick=self.engine.global_tick,deadline=self.engine.heartbeat_deadline))

    def acquire_contacts(self):
        if not getattr(self,'acquire_contacts_ready',False): return
        self.initialize_random()
        from systems import sensors, targeting
        for board in self.maps.values(): self.invoke(sensors.update_los_info,board)
        for unit in self.units.values():
            self.engine.events.cancel_by_type_and_data(EventType.PLOS,unit)
            self.invoke(targeting.plos_event,SimpleNamespace(data=unit,data2=self.engine))

    def initialize_random(self):
        if getattr(self,'random_initialized',False): return
        self.engine.randomness = RandomState()
        spec, mt = self.random_spec, self.engine.randomness.mt
        if 'seed' in spec: mt.seed(number(spec['seed'],integer=True))
        if 'array_seed' in spec: mt.init_by_array([number(v,integer=True) for v in array(spec['array_seed'])])
        if 'raw32' in spec: mt.use_words([number(v,0,2**32-1,True) for v in array(spec['raw32'])])
        self.random_initialized = True

    @staticmethod
    def map_fields(record):
        return {key:record.pop(key) for key in ('name','id','linked','cf','onmap','leave_target','entrances','current_tick') if key in record}

    def apply_map_fields(self,board,extra,default_name):
        board.name = string(extra.get('name',default_name))
        board.object_name = board.name
        board._id = number(extra.get('id',1000+len(self.maps)),0,integer=True)
        if board.name in self.maps: raise ValueError('duplicate map name')
        board.linked = boolean(extra.get('linked',False))
        board.cf = number(extra.get('cf',0),0,integer=True)
        board.onmap = number(extra.get('onmap',0),0,integer=True)
        board.current_tick = number(extra.get('current_tick',0),0,2**32-1,True)
        board.leave_target = number(extra['leave_target'],0,integer=True) if 'leave_target' in extra else None
        board.entrances = {}
        for entrance in array(extra.get('entrances',[])):
            fields(entrance,('target','x','y','name'),('target','x','y'))
            target = number(entrance['target'],0,integer=True)
            value = dict(x=number(entrance['x'],0,board.map_width-1,True),y=number(entrance['y'],0,board.map_height-1,True))
            if 'name' in entrance: value['name'] = string(entrance['name'])
            if target in board.entrances: raise ValueError('duplicate entrance target')
            board.entrances[target] = value
        self.maps[board.name] = board

    def add_unit(self,record):
        record = deepcopy(record)
        extras = {key:record.pop(key) for key in ('core','actor','pilot_details','gunner','pilot_owner','id','map','profile') if key in record}
        prices = {}
        for mount in record.get('weapons',[]):
            if isinstance(mount,dict) and 'metadata' in mount:
                metadata = mount['metadata']
                prices[mount['name']] = {key:metadata.pop(key) for key in ('cost','ammo_cost','ammo_bv','bv') if key in metadata}
        if 'id' in extras:
            record['id'] = extras['id']
        record.setdefault('gunnery',4) if record.get('pilot',True) else None
        record.setdefault('piloting',5) if record.get('pilot',True) else None
        unit = super().add_unit(record)
        unit._id = number(extras.get('id',len(self.units)),1,integer=True)
        if unit.map is not None:
            unit.map.roster_ids[unit.mapnumber]=unit._id
            from systems.map_membership import publish_los
            publish_los(unit.map)
        profile = extras.get('profile','normal')
        if profile not in ('normal','sparse'): raise ValueError('unknown unit profile')
        if profile == 'sparse':
            from entities.crittypes import i2special
            for section in unit.sections:
                for key in ('armor','armor_orig','rear','rear_orig','internal','internal_orig'): setattr(section,key,0)
                for slot in section.criticals:
                    if slot.type in [i2special(i) for i in range(4)]: slot.type = 0
            for section in record.get('sections',[]): self.configure_section(unit,section)
        if unit.pilot is not None:
            details = {key:getattr(unit.pilot,key) for key in ACTOR_BOOLS+ACTOR_INTS+('name','skills','health')
                       if getattr(unit.pilot,key,None) is not None}
            details.update(extras.get('pilot_details',{}))
            unit.pilot = actor_from(details,unit)
        elif 'pilot_details' in extras: raise ValueError('pilot_details requires an assigned pilot')
        unit.command_actor = actor_from(extras['actor'],unit) if 'actor' in extras else unit.pilot or actor_from({},unit)
        if 'gunner' in extras: unit.gun_pilot = actor_from(extras['gunner'],unit)
        if 'pilot_owner' in extras:
            if extras['pilot_owner'] not in ('actor','pilot'): raise ValueError('pilot_owner must reference actor or pilot')
            unit.pilot_owner = unit.command_actor if extras['pilot_owner']=='actor' else unit.pilot
        self.configure_core(unit,extras.get('core',{}))
        for name,values in prices.items():
            weapon = get_weapon(name)
            weapon = self.weapon_overrides.get(weapon.index,weapon)
            self.weapon_overrides[weapon.index] = replace(weapon,**{k:number(v,0,2**32-1,True) for k,v in values.items()})
        from systems.weapon_inventory import sync_weapon_states
        self.invoke(sync_weapon_states,unit)
        return unit

    def configure_section(self,unit,record):
        # Reject values outside the source struct instead of silently wrapping them.
        for key in ('armor','armor_orig','rear','rear_orig','internal','internal_orig','config'):
            if key in record: number(record[key],0,255,True)
        if 'specials' in record: number(record['specials'],0,65535,True)
        for key in ('basetohit','recycle'):
            if key in record: number(record[key],0,127,True)
        for slot in array(record.get('slots',[])):
            for key in ('data','brand'):
                if key in slot: number(slot[key],0,255,True)
        return super().configure_section(unit,record)

    def configure_core(self,unit,values):
        fields(values,CORE_INTS+CORE_FLOATS+CORE_BOOLS+CORE_TEXT+('cargo_inventory','stagger_damage_list'))
        for key,value in values.items():
            if key in ('x','y'): value = number(value,-32768,32767,True)
            elif key == 'facing': value = number(value,0,359,True)
            elif key in CORE_INTS: value = number(value,-2**31,2**32-1,True)
            elif key in CORE_FLOATS: value = number(value,-1000000,1000000)
            elif key in CORE_BOOLS: value = boolean(value)
            elif key in CORE_TEXT:
                if not isinstance(value,str): raise ValueError(key+' requires text')
                if key == 'contact_id':
                    from systems.parts import source_text
                    if len(value) != 2: raise ValueError('contact_id requires two bytes')
                    value = source_text(value)
            elif key == 'cargo_inventory':
                value = [[number(p,1,1023,True),number(b,0,255,True),number(c,0,2**31-1,True)] for p,b,c in [array(row,3) for row in array(value)]]
            else:
                value = deepcopy(array(value))
                for node in value:
                    fields(node,('amount','occurred_at','counted'),('amount','occurred_at','counted'))
                    node['amount'] = number(node['amount'],0,100000,True)
                    node['occurred_at'] = number(node['occurred_at'],integer=True)
                    node['counted'] = boolean(node['counted'])
            setattr(unit,key,value)

    def random_source(self,name,low,high,fallback):
        if self.strict_streams and name not in self.streams: raise ValueError('missing finite draw stream: '+name)
        before = self.engine.randomness.mt.words_consumed
        value = super().random_source(name,low,high,fallback)
        self.draws[-1].update(raw_words=self.engine.randomness.mt.words_consumed-before)
        return value

    def observe_event(self,phase,event):
        self.event_trace.append(dict(phase=phase,id=event.event_id,type=SOURCE_EVENT_IDS.get(event.event_type),
                                    kind=event.event_type.name,deadline=event.tick,
                                    pending_same_type=self.engine.events.count_type(event.event_type)))

    def command(self,unit,name,args):
        from tools.core_diagnostics import command
        name = string(name).lower()
        reply = command(self,unit,name,args)
        if reply is not NotImplemented: return reply
        previous = getattr(unit,'caller_is_pilot',True),getattr(unit,'caller_wizard',False)
        unit.caller_is_pilot = unit.command_actor is unit.pilot
        unit.caller_wizard = getattr(unit.command_actor,'wizard',False)
        try: return super().command(unit,name,args)
        finally: unit.caller_is_pilot,unit.caller_wizard = previous

    def action(self,action):
        self.initialize_random()
        if not isinstance(action,dict): raise ValueError('action must be an object')
        op = action.get('op')
        if op == 'diagnose' and ('args' in action or action.get('kind') in self.source_operations()):
            fields(action,('op','unit','kind','args'),('op','kind'))
            from tools.core_diagnostics import diagnose
            unit = self.units[action.get('unit','u')]
            return serialized(self.invoke(diagnose,self,unit,string(action['kind']),array(action.get('args',[]))))
        if op == 'clock':
            fields(action,('op','name','seconds'),('op','name'))
            name = action['name']
            if name not in ('dispatch','heartbeat','skip_seconds','heartbeat_init','heartbeat_stop'): raise ValueError('unknown clock operation')
            args = [number(action['seconds'],0,1000000,True)] if 'seconds' in action else []
            if name == 'skip_seconds' and not args: raise ValueError('skip_seconds requires seconds')
            if name not in ('dispatch','skip_seconds') and args: raise ValueError('clock operation takes no seconds')
            return serialized(self.invoke(getattr(self.engine,name),*args))
        if op == 'schedule':
            fields(action,('op','unit','callback','delay','data','cancelled'),('op','callback','delay'))
            from tools.core_diagnostics import schedule
            event = schedule(self,self.units[action.get('unit','u')],action['callback'],action['delay'],action.get('data',0))
            if boolean(action.get('cancelled',False)): event.cancel()
            return dict(id=event.event_id,deadline=event.tick)
        if op == 'core':
            fields(action,('op','unit','values'),('op','values'))
            self.configure_core(self.units[action.get('unit','u')],action['values'])
            return None
        if op == 'command' and 'actor' in action:
            action = deepcopy(action)
            unit = self.units[action.get('unit','u')]
            reference = action.pop('actor')
            actor = actor_from(reference,unit) if isinstance(reference,dict) else (
                unit.pilot if reference=='pilot' else unit.command_actor if reference=='caller' else None)
            if actor is None: raise ValueError('unknown or unavailable command actor')
            previous = unit.command_actor
            unit.command_actor = actor
            try: return serialized(super().action(action))
            finally: unit.command_actor = previous
        return serialized(super().action(action))

    @staticmethod
    def source_operations():
        from tools.core_diagnostics import OPERATIONS
        return OPERATIONS

    def snapshot(self):
        self.initialize_random()
        return self.invoke(self._snapshot)

    def _snapshot(self):
        # Parent reads actual slot, armor and movement state without invoking calculations.
        result = super()._snapshot()
        engine = self.engine
        result['clocks'] = dict(wall=engine.sim_now,event=engine.muxevent_tick,global_tick=engine.global_tick)
        result['heartbeat_timer'] = dict(count=engine.heartbeat_timer_count,deadline=engine.heartbeat_deadline)
        result['random'] = dict(words_consumed=engine.randomness.mt.words_consumed,total_rolls=engine.randomness.total_rolls,
                                histogram=list(engine.randomness.rolls),rows=engine.randomness.stat_rows(),
                                hit_histogram=list(engine.randomness.hit_rolls),total_hit_rolls=engine.randomness.total_hit_rolls)
        if getattr(engine,'random_state',False):
            result['random']['generator'] = dict(index=engine.randomness.mt.index,state=list(engine.randomness.mt.state))
        result['event_history'] = list(engine.events.history)
        result['event_trace'] = deepcopy(self.event_trace)
        result['heartbeat_trace'] = deepcopy(self.heartbeat_trace)
        result['events'] = [dict(id=e.event_id,kind=e.event_type.name,type=SOURCE_EVENT_IDS.get(e.event_type),
            source_name=(SOURCE_EVENT_NAMES[SOURCE_EVENT_IDS[e.event_type]] if SOURCE_EVENT_IDS[e.event_type]<len(SOURCE_EVENT_NAMES) else e.event_type.name) if e.event_type in SOURCE_EVENT_IDS else None,
            unit=next((n for n,u in self.units.items() if u is e.data),None),data2=serialized(e.data2) if isinstance(e.data2,(int,str,list,tuple,type(None))) else None,
            deadline=e.tick) for e in engine.events.pending_events()]
        for name,unit in self.units.items():
            row = result['units'][name]
            for key in CORE_INTS+CORE_FLOATS+CORE_BOOLS+CORE_TEXT:
                row[key] = getattr(unit,key,False if key in CORE_BOOLS else '' if key in CORE_TEXT else 0)
            row.update(id=unit._id,contact_id=unit.contact_id,mapindex=unit.mapindex,
                map=unit.map.name if unit.map else None,boot_messages=list(unit.boot_messages),units_killed=unit.units_killed,
                skills=self.skill_snapshot(unit),pilot=self.actor_snapshot(unit.pilot),caller=self.actor_snapshot(unit.command_actor),
                cargo_inventory=deepcopy(getattr(unit,'cargo_inventory',None)),
                stagger_damage_list=[dict(amount=node['amount'],occurred_at=node['occurred_at'],counted=node['counted'],
                    attacker=getattr(node.get('attacker'),'_id',node.get('attacker'))) for node in unit.stagger_damage_list],
                xp_requests=deepcopy(getattr(unit,'xp_requests',[])),
                debug_messages=list(getattr(unit,'debug_messages',[])),
                channel_requests=deepcopy(getattr(unit,'channel_requests',[])),
                hook_requests=deepcopy(getattr(unit,'hook_requests',[])),
                events=[deepcopy(e) for e in result['events'] if e['unit']==name])
        result['objects'] = {name:dict(id=obj._id,type=obj.xcode_type,external_effects=deepcopy(obj.external_effects)) for name,obj in self.objects.items()}
        result['maps'] = {name:dict(id=board._id,size=[board.map_width,board.map_height],moves=getattr(board,'moves',0),current_tick=board.current_tick,
            roster=[u._id if u is not None else None for u in board.mechs_on_map],
            los=[dict(viewer=a,target=b,flags=flags) for (a,b),flags in sorted((board.losinfo or {}).items())]) for name,board in self.maps.items()}
        result['costs'] = {str(index):value for index,value in enumerate(self.costs.values) if value}
        result['templates'] = {name:self.template_snapshot(unit) for name,unit in self.engine.templates.items()}
        return serialized(result)

    @staticmethod
    def template_snapshot(unit):
        row = {key:value for key,value in vars(unit).items() if not key.startswith('_')
               and (value is None or isinstance(value,(int,float,str,bool)))}
        row['sections'] = [asdict(section) for section in unit.sections]
        row['weapons'] = [asdict(weapon) for weapon in unit.weapons]
        row['pilot'] = CoreSession.actor_snapshot(unit.pilot)
        return row

    @staticmethod
    def actor_snapshot(actor):
        if actor is None: return None
        return {key:getattr(actor,'_id' if key=='id' else key,None) for key in ACTOR_BOOLS+ACTOR_INTS+('name','skills','health')}

    @staticmethod
    def skill_snapshot(unit):
        from systems import piloting as p
        return dict(piloting=p.find_pilot_piloting(unit),gunnery=p.find_pilot_gunnery(unit),
                    spotting=p.find_pilot_spotting(unit),artillery=p.find_pilot_arty_gun(unit),
                    piloting_name=p.find_piloting_skill_name(unit),gunnery_name=p.find_gunnery_skill_name(unit))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',help='JSON input file; defaults to stdin')
    args = parser.parse_args(argv)
    try:
        if args.input:
            with open(args.input) as source: document = json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        else: document = json.load(sys.stdin,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session = CoreSession(document)
        results = [session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,KeyError,TypeError,IndexError,OSError,OverflowError) as error:
        print(str(error),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
