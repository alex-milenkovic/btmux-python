# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.los.c
#   btech/mech.scan.c
#   btech/mech.sensor.c
#   btech/mech.utils.c

"""Sensors simulation CLI: --input FILE, or one JSON document on stdin."""
import argparse
from contextlib import redirect_stdout
from dataclasses import asdict,is_dataclass
from io import StringIO
import json
import random
import sys
from core.events import EventType
from core.game_loop import GameEngine,wire_standard_systems
from core.randomness import use_source, use_simulation
from entities.map import GameMap,FIRE,SMOKE
from entities.mech import Mech,MechStatus as S,MechStatus2 as S2,CritStatus as C,Specials,UnitType,MoveType,WeaponState
from entities.pilot import Pilot
from entities.crittypes import Special,i2special,i2weapon,i2ammo,is_ammo,ammo2weapon_i
from entities.weapon import get_weapon
from physics.hexmath import float_to_hex,ZSCALE
from systems import sensors,targeting,ecm,observation
from systems.los import calculate_los_map,in_line_of_sight,in_line_of_sight_nb,actual_elevation,add_terrain_mod
from systems.movement_commands import notify
from tools.movement_inputs import fields,number,boolean,string,array
from tools.path_cost_inputs import terrain_value

LETTERS='VLIESRBAH'
EQUIPMENT={'TAG':('specials2',0x8000,Special.TAG),'Guardian':('specials',int(Specials.ECM_TECH),Special.ECM),
 'Angel':('specials2',0x1000,Special.ANGELECM),'Beagle':('specials',int(Specials.BEAGLE_PROBE_TECH),Special.BEAGLE_PROBE),
 'LightBeagle':('specials',int(Specials.LIGHT_BAP_TECH),Special.LIGHT_BAP),'Bloodhound':('specials2',0x800,Special.BLOODHOUND_PROBE),
 'searchlight':('specials',int(Specials.SLITE_TECH),None),'Radar':('specials',int(Specials.AA_TECH),None),
 'C3master':('specials',int(Specials.C3_MASTER_TECH),Special.C3_MASTER),'Personal':('infantry_specials',0x80,None)}


def set_flag(unit,word,flag,value):
    boolean(value)
    setattr(unit,word,getattr(unit,word)|flag if value else getattr(unit,word)&~flag)


class SensorSession:
    def __init__(self,document):
        fields(document,('map','units','config','random','actions','diagnostic_cache'),('actions',))
        array(document['actions'])
        config=fields(document.get('config',{}),('periodic_updates','lock_tick','infrared_profile','seismic_see_stopped','movement_modes'))
        board=fields(document.get('map',{}),('size','default','hexes','mapvis','maxvis','light','cloudbase','sensorflags','weather','dark'))
        width,height=[number(v,1,200,True) for v in array(board.get('size',[8,8]),2)]
        self.map=GameMap(width,height)
        self.map._id=0  # Scenario map key; all unit object keys are positive.
        self.map.grav=100
        self.map.mapvis=number(board.get('mapvis',30),0,60,True)
        self.map.maxvis=number(board.get('maxvis',60),0,180,True)
        self.map.maplight=number(board.get('light',2),0,2,True)
        self.map.cloudbase=number(board.get('cloudbase',0),integer=True)
        self.map.sensorflags=number(board.get('sensorflags',0),0,2**32-1,True)
        self.map.dark=boolean(board.get('dark',False))
        self.map.visibility_config=board.get('weather',f'{self.map.mapvis} {self.map.maplight} 0 0 {self.map.cloudbase}')
        if not isinstance(self.map.visibility_config,str): raise ValueError('weather must be a string')
        self.map.infrared_profile=config.get('infrared_profile','unscaled')
        if self.map.infrared_profile not in ('unscaled','scaled'): raise ValueError('invalid infrared profile')
        self.map.seismic_see_stopped=boolean(config.get('seismic_see_stopped',False))
        self.map.losinfo={}
        self.engine=GameEngine()
        if 'default' in board:
            terrain,floor=array(board['default'],2)
            for y in range(height):
                for x in range(width): self.hexagon(dict(at=[x,y],terrain=terrain,elevation=floor))
        for hexagon in array(board.get('hexes',[])): self.hexagon(hexagon)
        self.engine.lock_tick=number(config.get('lock_tick',0),0,100,True)
        self.engine.movement_modes=boolean(config.get('movement_modes',True))
        if boolean(config.get('periodic_updates',True)): wire_standard_systems(self.engine)
        self.engine.register_entity(self.map)
        self.units={}
        for value in array(document.get('units',[{'name':'u'}])): self.add_unit(value)
        for record in array(document.get('diagnostic_cache',[])):
            fields(record,('viewer','target','flags'),('viewer','target','flags'))
            self.map.losinfo[self.units[record['viewer']]._id,self.units[record['target']]._id]=number(record['flags'],0,65535,True)
        self.diagnostic_cache=bool(document.get('diagnostic_cache'))
        random_config=fields(document.get('random',{}),('seed','streams'))
        random.seed(number(random_config.get('seed',0),integer=True))
        if 'seed' in random_config:
            self.engine.randomness.mt.seed(number(random_config['seed'], integer=True))
        self.streams=random_config.get('streams',{})
        if not isinstance(self.streams,dict): raise ValueError('streams must be an object')
        for key,values in self.streams.items():
            string(key)
            for value in array(values): number(value,integer=True)
        self.draws=[]

    def hexagon(self,value):
        fields(value,('at','terrain','elevation','overlay','duration'),('at','terrain','elevation'))
        x,y=[number(v,integer=True) for v in array(value['at'],2)]
        if not self.map.valid(x,y): raise ValueError('off-map hex')
        terrain=terrain_value('GRASSLAND' if value['terrain']=='CLEAR' else value['terrain'])
        self.map.set_terrain(x,y,terrain)
        self.map.set_elevation(x,y,abs(number(value['elevation'],-9,9,True)))
        if value.get('overlay'):
            overlay=terrain_value(value['overlay'])
            if overlay not in (FIRE,SMOKE): raise ValueError('invalid overlay')
            from physics.decorations import add_decoration
            add_decoration(self.engine,self.map,x,y,overlay,number(value.get('duration',100),0,32767,True))

    def add_unit(self,value):
        allowed=('name','contact_id','team','at','real','sensors','class','movement','pilot','perception','equipment','weapons','started','destroyed','conscious','blinded','fallen','hulldown','hidden','observer','clairvoyant','heat','plus_heat','minus_heat','speed','desired_speed','facing','turret_facing','tonnage','radio_range','scan_range','brief','sl_warn','autocon_shutdown','markings','status','status2','crit_status','specials','specials2','sections','target','spotter','fire_adjustment','tag_target','tagged_by','in_character','recycle','sensor_hits')
        fields(value,allowed+('ammo','real_mass','id'),('name',))
        name=string(value['name'])
        if name in self.units: raise ValueError('duplicate unit name')
        unit=Mech.create_test_mech(name)
        if 'id' in value:
            unit._id=number(value['id'],1,integer=True)
        unit.contact_id=value.get('contact_id',f'{len(self.units):02d}')
        if not isinstance(unit.contact_id,str) or len(unit.contact_id)!=2 or any(u.contact_id.lower()==unit.contact_id.lower() for u in self.units.values()): raise ValueError('contact IDs must be unique two-character strings')
        unit.unit_type=UnitType[value.get('class','MECH')]
        unit.move_type=MoveType[value.get('movement','BIPED')]
        unit.pilot=Pilot(perception=number(value.get('perception',6),0,20,True)) if boolean(value.get('pilot',True)) else None
        unit.command_actor = unit.pilot
        for key,word,flag,default in [('started','status',S.STARTED,True),('destroyed','status',S.DESTROYED,False),('conscious','status',S.UNCONSCIOUS,True),('blinded','status',S.BLINDED,False),('fallen','status',S.FALLEN,False),('hulldown','status',S.HULLDOWN,False),('hidden','crit_status',C.HIDDEN,False),('observer','crit_status',C.OBSERVATORIC,False),('clairvoyant','crit_status',C.CLAIRVOYANT,False)]:
            v=boolean(value.get(key,default));set_flag(unit,word,flag,not v if key=='conscious' else v)
        for key in ('team','heat','plus_heat','minus_heat','speed','desired_speed','facing','turret_facing','tonnage','radio_range','scan_range','brief','status','status2','crit_status','specials','specials2','fire_adjustment','sensor_hits'):
            if key in value: setattr(unit,key,number(value[key],integer=key not in ('heat','plus_heat','minus_heat','speed','desired_speed')))
        from data.templates import update_oweight
        update_oweight(unit, int(number(value.get('real_mass',unit.tonnage),0) * 1024))
        for key in ('sl_warn','autocon_shutdown','in_character'):
            if key in value: setattr(unit,key,boolean(value[key]))
        if 'markings' in value:
            if not isinstance(value['markings'],str): raise ValueError('markings must be text')
            unit.markings=value['markings']
        pair=array(value.get('sensors',['V','V']),2)
        if any(v not in LETTERS or len(v)!=1 for v in pair): raise ValueError('unknown sensor')
        unit.sensor=[LETTERS.index(v) for v in pair]
        for index,name in enumerate(array(value.get('equipment',[]))):
            if name not in EQUIPMENT: raise ValueError('unknown equipment '+str(name))
            word,bit,special=EQUIPMENT[name]
            setattr(unit,word,getattr(unit,word,0)|bit)
            if special is not None:
                if index>=12: raise ValueError('too many equipment slots')
                unit.sections[0].criticals[index].type=i2special(special)
        next_critical={}
        for entry in array(value.get('weapons',[])):
            specification={'name':entry} if isinstance(entry,str) else entry
            fields(specification,('name','section','critical','ammo_mode','fire_mode'),('name',))
            weapon=get_weapon(string(specification['name']))
            if weapon is None: raise ValueError('unknown weapon '+str(specification['name']))
            from entities.weapon import WEAPON_INDEX
            wi=next(i for i,w in enumerate(WEAPON_INDEX) if w is weapon)
            section=number(specification.get('section',4),0,7,True)
            index=number(specification.get('critical',next_critical.get(section,0)),0,11,True)
            if index+weapon.crits>len(unit.sections[section].criticals): raise ValueError('weapon does not fit in section')
            slots=unit.sections[section].criticals[index:index+weapon.crits]
            if any(slot.type for slot in slots): raise ValueError('overlapping weapon/equipment slots')
            unit.weapons.append(WeaponState(section=section,critical=index,weapon_idx=wi))
            for slot in slots:
                slot.type=i2weapon(wi)
                slot.ammomode=number(specification.get('ammo_mode',0),0,2**32-1,True)
                slot.firemode=number(specification.get('fire_mode',0),0,2**32-1,True)
            next_critical[section]=index+weapon.crits
        for index,bin_spec in enumerate(array(value.get('ammo',[]))):
            fields(bin_spec,('weapon','rounds','section','critical','ammo_mode'),('weapon','rounds'))
            weapon=get_weapon(string(bin_spec['weapon']))
            if weapon is None or not weapon.uses_ammo: raise ValueError('invalid ammunition weapon')
            section=number(bin_spec.get('section',2),0,7,True)
            critical=number(bin_spec.get('critical',index),0,len(unit.sections[section].criticals)-1,True)
            slot=unit.sections[section].criticals[critical]
            if slot.type: raise ValueError('overlapping ammunition/equipment slots')
            slot.type=i2ammo(weapon.index)
            slot.data=number(bin_spec['rounds'],0,255,True)
            slot.ammomode=number(bin_spec.get('ammo_mode',0),0,2**32-1,True)
        if 'recycle' in value:
            for ws in unit.weapons:
                ws.recycle=number(value['recycle'],0,1000,True)
                unit.sections[ws.section].criticals[ws.critical].data=ws.recycle
        for section in array(value.get('sections',[])):
            fields(section,('index','armor','internal','specials','config'),('index',))
            target=unit.sections[number(section['index'],0,7,True)]
            for key in section.keys()-{'index'}: setattr(target,key,number(section[key],0,integer=True))
        self.units[value['name']]=unit
        self.place(unit,value.get('at',[2,2,0]),value.get('real'))
        self.map.add_mech(unit)
        self.engine.register_entity(unit)
        for key in ('target','spotter','tag_target','tagged_by'):
            if key in value:
                ref=value[key]
                setattr(unit,key,self.units[ref]._id if isinstance(ref,str) else number(ref,integer=True))
        return unit

    def place(self,unit,at,real=None):
        x,y,z=[number(v,integer=True) for v in array(at,3)]
        if not self.map.valid(x,y): raise ValueError('off-map unit')
        unit.set_hex_position(x,y,z)
        if real is not None:
            fx,fy,fz=[number(v) for v in array(real,3)]
            x,y=float_to_hex(fx,fy)
            if not self.map.valid(x,y): raise ValueError('off-map real coordinates')
            unit.set_position(x,y,fx,fy,int(fz/ZSCALE),fz)
        unit.terrain=self.map.terrain(unit.x,unit.y)
        unit.elev=self.map.elevation(unit.x,unit.y)
        ecm.mark_for_los_update(unit)

    def random_source(self,name,low,high,fallback):
        if name in self.streams:
            if not self.streams[name]: raise ValueError('exhausted dice: '+name)
            value=self.streams[name].pop(0)
            if not low<=value<=high: raise ValueError('dice outside range: '+name)
        else: value=fallback()
        self.draws.append(dict(name=name,value=value,low=low,high=high))
        return value

    def invoke(self,fn,*args,**kwargs):
        output=StringIO()
        with use_simulation(self.engine.randomness),use_source(self.random_source),redirect_stdout(output): result=fn(*args,**kwargs)
        if output.getvalue(): raise ValueError(output.getvalue().strip())
        return result

    def command(self,unit,name,args):
        args=array(args)
        if any(not isinstance(v,(str,int,float)) or isinstance(v,bool) for v in args): raise ValueError('invalid command argument')
        text=' '.join(str(v) for v in args)
        if name=='sensor':
            if unit is None:
                return observation.response(True, '')
            ok,message=targeting.set_sensors(self.engine,unit,text)
            return observation.response(ok,targeting.show_sensor(self.engine,unit,len(args)==1) if ok else message)
        if name=='enterbase':
            from systems.hangar import enter_base
            return enter_base(unit,text,unit.command_actor)
        if name in ('brief','contacts','view'): return getattr(observation,name)(unit,text)
        if name in ('scan','report'): return observation.scan(unit,text,report=name=='report')
        if name in ('bearing','range','vector'): return observation.navigation(unit,name,text)
        if name=='tag': result=targeting.tag(self.engine,unit,text,caller=getattr(unit,'command_actor',None))
        elif name=='slite': result=sensors.slite(self.engine,unit,caller=getattr(unit,'command_actor',None),wizard=getattr(unit,'caller_wizard',False))
        elif name=='spot':
            from systems.spot import mech_spot
            result=mech_spot(self.engine,unit,text,caller=getattr(unit,'command_actor',None))
        elif name=='target':
            if text=='-': result=targeting.clear_target(unit,self.engine)
            elif len(args)==1: result=targeting.set_target(self.engine,unit,targeting.contact_target(unit,text))
            elif len(args) in (2,3): result=targeting.set_target_hex(self.engine,unit,int(args[0]),int(args[1]),str(args[2]) if len(args)==3 else None)
            else: result=False,'Invalid target arguments.'
        elif name in ('speed','heading'):
            from systems import movement_commands
            result=getattr(movement_commands,name)(self.engine,unit,text)
        elif name in ('ecm','eccm','angelecm','angeleccm','perecm','pereccm'):
            messages=getattr(ecm,'mech_'+name)(unit,caller=getattr(unit,'command_actor',None),wizard=getattr(unit,'caller_wizard',False))
            return observation.response(messages[0].startswith('You turn'),'\n'.join(messages))
        elif name=='losemit':
            result=sensors.mech_losemit(unit,text,caller=getattr(unit,'command_actor',None))
        elif name=='startup':
            from systems.startup import startup
            result=startup(self.engine,unit,text,caller=unit.command_actor,
                           wizard=getattr(unit,'caller_wizard',False))
        elif name=='shutdown':
            from systems.startup import shutdown
            result=shutdown(self.engine,unit,text,caller=unit.command_actor,
                            wizard=getattr(unit,'caller_wizard',False))
        elif name in ('sight','fire'):
            from systems.combat_firing import fire_command
            from systems.combat_commands import parse_attributes
            attack=fire_command(self.engine,unit,parse_attributes(text,5),sight=name=='sight',caller=getattr(unit,'command_actor',None))
            return observation.response(attack.bth_breakdown is not None and not attack.roll_impossible and not attack.shot_aborted,'\n'.join(attack.messages),attack=asdict(attack))
        else: raise ValueError('unsupported command: '+name)
        return observation.response(*result)

    def configure(self,unit,values):
        """Explicit diagnostic state inputs, never computed answers or callbacks."""
        flags={'started':('status',S.STARTED),'conscious':('status',S.UNCONSCIOUS),
               'blinded':('status',S.BLINDED),'destroyed':('status',S.DESTROYED)}
        integers=('tank_crit_status','targ_x','targ_y','targ_z','brief','status','status2',
                  'crit_status','specials','specials2','radio_range','scan_range','team',
                  'targcomp','cocoon','carrying','stagger_level','fire_adjustment')
        numbers=('speed','desired_speed','heat','plus_heat','minus_heat','vertical_speed')
        refs=('spotter','target','tag_target','tagged_by','swarm_target')
        fields(values,tuple(flags)+integers+numbers+refs+('contact_options','sl_warn','autocon_shutdown'))
        for key,value in values.items():
            if key in flags:
                word,flag=flags[key];set_flag(unit,word,flag,not boolean(value) if key=='conscious' else value)
            elif key in refs: setattr(unit,key,self.units[value]._id if isinstance(value,str) else number(value,integer=True))
            elif key in integers+numbers: setattr(unit,key,number(value,integer=key in integers))
            elif key=='contact_options':
                if not isinstance(value,str): raise ValueError('contact_options must be text')
                setattr(unit,key,value)
            else: setattr(unit,key,boolean(value))
        ecm.mark_for_los_update(unit)

    def diagnose(self,unit,kind,target=None,options=None):
        options={} if options is None else options
        fields(options,{'random-window':('low','high'),'flags':('value',),
                        'sensor-description':('index',),'notice':('los','seeanew','gain'),
                        'sensor-chance':()}.get(kind,()))
        other=self.units[target] if target else None
        distance=targeting.fa_mech_range(unit,other) if other else 0
        if kind=='map-maintenance': sensors.update_los_info(self.map);return {}
        if kind=='reactor-explosion':
            from systems.damage import reactor_explosion
            reactor_explosion(unit,None,engine=self.engine);return {}
        if kind=='plos':
            event=next((e for e in self.engine.events._events.values() if e.data is unit and e.event_type==EventType.PLOS and not e.zombie),None)
            if event: event.cancel();targeting.plos_event(event)
            return {}
        if kind=='ecm': ecm.check_ecm(unit);return {}
        if kind=='tag': targeting.check_tag(unit);return {}
        if kind=='end-light': sensors.end_lite_check(unit);return {}
        if kind=='illumination': return dict(qualifies=sensors.mech_lites_target(unit,other))
        if kind=='height': return dict(height=actual_elevation(self.map,unit.x,unit.y,unit))
        if kind=='terrain-modifier': return dict(modifier=add_terrain_mod(unit,other,self.map,distance,0))
        if kind=='status': return dict(status=observation.status_chars(unit,other),full=observation.status_string(other))
        if kind=='legacy-sensor-info': return dict(legacy=targeting.sensor_info(self.engine,unit))
        if kind=='random-window':
            low=number(options.get('low',0),integer=True);high=number(options.get('high',2),integer=True)
            if high<low: raise ValueError('random interval is reversed')
            return dict(value=sensors.m_number(unit,low,high))
        if kind=='flags': return dict(flags=sensors.dump_flag(number(options['value'],0,2**32-1,True)))
        if kind=='sensor-description': return dict(description=targeting.sensor_mode_name(unit,number(options['index'],integer=True)))
        if kind=='trace':
            from systems.los import trace_los,calculate_los_flag
            return dict(trace=trace_los(self.map,unit.x,unit.y,other.x,other.y),flags=calculate_los_flag(unit,other,self.map,other.x,other.y,0,distance))
        if kind=='sensor-chance':
            from physics.hexmath import in_weapon_arc
            arc=in_weapon_arc(unit,other.fx,other.fy)
            return dict(driver=sensors.sensor_driver_base_chance(unit),arc=sensors.sensor_arc_base_chance(unit.unit_type,arc))
        if kind=='notice':
            sensors.contact_notice(unit,other,number(options['los'],integer=True),number(options['seeanew'],0,3,True),1,boolean(options['gain']))
            return {}
        if kind=='los': return dict(detected=bool(in_line_of_sight(unit,other,other.x,other.y,distance)),identified=bool(in_line_of_sight_nb(unit,other,other.x,other.y,distance)))
        if kind=='eligibility':
            flag=self.map.losinfo.get((unit._id,other._id),8)
            return dict(eligible=sensors.sensor_can_see(unit,other,flag,__import__('physics.hexmath',fromlist=['in_weapon_arc']).in_weapon_arc(unit,other.fx,other.fy),distance,self.map.mapvis,self.map.maplight,self.map.cloudbase))
        raise ValueError('unsupported diagnosis: '+kind)

    def action(self,action):
        if not isinstance(action,dict): raise ValueError('action must be an object')
        op=action.get('op')
        schemas={'command':('name','args'),'advance':('seconds',),'inspect':(),
                 'map':('origin','size'),'conditions':('weather','sensorflags'),'place':('at','real'),
                 'remove':(),'flash':('source','duration','chance'),
                 'diagnose':('kind','target','options'),'equipment_hit':('equipment','attacker'),
                 'configure':('values',),'register':(),'cache':('target','flags'),
                 'hex':('value',),'roster-hole':(),'pending-hide':('seconds',)}
        if op not in schemas: raise ValueError('unsupported operation: '+str(op))
        global_action=op in ('advance','inspect','conditions','flash','hex','roster-hole')
        fields(action,('op',)+(() if global_action else ('unit',))+schemas[op],('op',))
        unit=None if global_action else self.units[action.get('unit','u')]
        if op=='command': return self.invoke(self.engine.inject_command,unit,lambda:self.command(unit,action['name'],action.get('args',[])),action['name'])
        if op=='advance': self.invoke(self.engine.run_ticks,number(action['seconds'],0,100000,True));return {}
        if op=='inspect': return self.snapshot()
        if op=='map':
            origin=[number(v,0,integer=True) for v in array(action['origin'],2)]
            size=[number(v,1,integer=True) for v in array(action['size'],2)]
            result=calculate_los_map(self.map,unit,*origin,*size)
            return dict(cells=result.render(self.map),flags=result.cells)
        if op=='conditions':
            if 'weather' in action:
                if not isinstance(action['weather'],str): raise ValueError('weather must be text')
                self.map.visibility_config=action['weather']
            if 'sensorflags' in action: self.map.sensorflags=number(action['sensorflags'],0,2**32-1,True)
            return {}
        if op=='configure': self.configure(unit,action['values']);return {}
        if op=='register': self.engine.register_entity(unit);return {}
        if op=='cache':
            self.map.losinfo[unit._id,self.units[action['target']]._id]=number(action['flags'],0,65535,True)
            self.diagnostic_cache=True;return {}
        if op=='hex': self.hexagon(action['value']);return {}
        if op=='roster-hole': self.map.mechs_on_map.append(None);return {}
        if op=='pending-hide':
            # An explicit pending-operation fixture, not a replacement hide
            # implementation. It is useful only before the sentinel deadline.
            def unhandled_hide(event):
                raise ValueError('diagnostic pending hide reached its deadline')
            self.engine.schedule_event(number(action['seconds'],1,100000,True),
                EventType.HIDE,unhandled_hide,data=unit)
            return {}
        if op=='place': self.place(unit,action.get('at',[unit.x,unit.y,unit.z]),action.get('real'));return {}
        if op=='remove':
            if unit.map is not None: unit.map.remove_mech(unit)
            self.engine.unregister_entity(unit);return {}
        if op=='flash':
            self.invoke(sensors.scramble_infra_and_liteamp,self.units[action['source']],number(action['duration'],1,10000,True),number(action.get('chance',0),0,100,True),'Infrared flash!','Light-amplifier flash!');return {}
        if op=='diagnose':
            options=action.get('options',{})
            if not isinstance(options,dict): raise ValueError('diagnostic options must be an object')
            return self.invoke(self.diagnose,unit,action['kind'],action.get('target'),options)
        if op=='equipment_hit':
            from systems.criticals import apply_critical_to_slot
            special=EQUIPMENT[action['equipment']][2]
            for i,section in enumerate(unit.sections):
                for j,slot in enumerate(section.criticals):
                    if special is not None and slot.type==i2special(special):
                        return asdict(apply_critical_to_slot(unit,i,j,self.units.get(action.get('attacker')),engine=self.engine))
            raise ValueError('equipment is not installed in critical slots')
        raise ValueError('unsupported operation: '+str(op))

    def snapshot(self):
        units={}
        for name,u in self.units.items():
            wanted=targeting.sensor_check(self.engine,u)
            events=[dict(kind=e.event_type.name,deadline=e.tick) for e in self.engine.events._events.values() if not e.zombie and e.data is u]
            units[name]=dict(id=u._id,contact_id=u.contact_id,at=[u.x,u.y,u.z],real=[u.fx,u.fy,u.fz],
                sensors=''.join(LETTERS[i] for i in u.sensor),wanted=''.join(LETTERS[i] for i in wanted) if wanted else None,
                target=u.target,hex_target=[u.targ_x,u.targ_y],lock_modes=int(u.status & S.LOCK_MODES),
                perception=u.per,real_mass=u.rtons/1024,num_seen=u.num_seen,pnum_seen=u.pnum_seen,started=u.is_started,brief=u.brief,
                blinded=u.has_status(S.BLINDED),status=int(u.status),status2=int(u.status2),crit_status=int(u.crit_status),
                tag_target=u.tag_target,tagged_by=u.tagged_by,spotter=u.spotter,fire_adjustment=u.fire_adjustment,
                lit=bool(u.crit_status & C.SLITE_LIT),searchlight=bool(u.status2 & 0x20),
                disturbed=ecm.any_ecm_disturbed(u),countered=bool(ecm.ecm_countered(u)),events=sorted(events,key=lambda e:e['deadline']),
                messages=list(u.movement_messages),armor=[s.armor for s in u.sections],
                rear_armor=[s.rear for s in u.sections],internal=[s.internal for s in u.sections],
                contacts={n:self.map.losinfo.get((u._id,t._id),0) for n,t in self.units.items() if t is not u},
                mapped=u.map is self.map,specials=int(u.specials),specials2=int(u.specials2))
            units[name]['weapons']=[dict(section=w.section,critical=w.critical,weapon_index=w.weapon_idx,
                recycle=u.sections[w.section].criticals[w.critical].data,
                ammo_mode=int(u.sections[w.section].criticals[w.critical].ammomode)) for w in u.weapons]
            units[name]['ammo']=[dict(section=i,critical=j,weapon_index=ammo2weapon_i(slot.type),rounds=slot.data,
                ammo_mode=int(slot.ammomode)) for i,section in enumerate(u.sections)
                for j,slot in enumerate(section.criticals) if is_ammo(slot.type)]
        return dict(time=self.engine.muxevent_tick,units=units,map=dict(mapvis=self.map.mapvis,maxvis=self.map.maxvis,light=self.map.maplight,sensorflags=self.map.sensorflags),diagnostic_cache=self.diagnostic_cache)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',help='JSON workflow file (default: stdin)')
    args=parser.parse_args(argv)
    try:
        if args.input:
            with open(args.input) as source: document=json.load(source)
        else: document=json.load(sys.stdin)
        session=SensorSession(document)
        results=[session.action(a) for a in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws)))
    except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
        print(str(error),file=sys.stderr);return 1
    return 0


if __name__=='__main__': raise SystemExit(main())
