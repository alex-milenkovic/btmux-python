"""Run damage and component-failure workflows supplied as JSON."""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
import sys
from tools.sensors_los import SensorSession
from tools.movement_inputs import fields, number, boolean, array
from entities.mech import UnitType, MoveType, FireMode, MechStatus, Location, WeaponState
from entities.crittypes import Special, i2special, i2weapon, i2ammo
from entities.weapon import get_weapon, get_weapon_by_index
from systems import damage, criticals, damage_commands, hit_locations, enhanced_crits, failures, vehicle_combat

CLASSES = {'GROUND':'VEH_GROUND', 'NAVAL':'VEH_NAVAL', 'BA':'BSUIT'}
CONFIG = dict(parts=1, vcrit=2, fasacrit=0, fasaadvvhlcrit=0, fasaadvvtolcrit=0,
              tankfriendly=0, tankshield=0, divrotordamage=0, critlevel=100,
              exile_stun_code=0, hit_arcs=0, stackpole=1, inferno_penalty=0, transported_unit_death=1, erange=1)
NUMERIC = ('max_speed','template_max_speed','jump_speed','jump_mp','engine_heat','num_sinks',
           'disabled_sinks','lrs_range','tac_range','scan_range','radio_range','base_to_hit',
           'pilot_skill_base','pilot_hits','crit_status2','tank_crit_status','computer_brand',
           'radio_brand','working_c3_masters','total_c3_masters','computer','radio','fuel','si','vertical_speed','cocoon','carrying','boom_start','measured_mass','aim','aim_type')
FLAGS = ('armor_warnings',)
SECTION_FIELDS = ('armor','armor_orig','rear','rear_orig','internal','internal_orig','config','specials','basetohit','recycle')
SLOT_FIELDS = ('type','data','brand','firemode','ammomode','weap_damage_flags','desired_ammo_loc')


class DamageSession(SensorSession):
    def __init__(self, document):
        self.weapon_overrides = {}
        document = deepcopy(document)
        config = document.setdefault('config', {})
        extra = {key: config.pop(key, default) for key, default in CONFIG.items()}
        board = document.setdefault('map', {})
        safe = boolean(board.pop('combat_safe', False))
        super().__init__(document)
        self.map.buildflag = 2 if safe else 0
        for key, value in extra.items(): setattr(self.engine, key, number(value,0,10000,True))
        for record in document.get('units', []):
            unit = self.units[record['name']]
            for key in ('swarm_target','towed_unit'):
                if key in record:
                    if record[key] not in self.units: raise ValueError('unknown related unit')
                    setattr(unit,key,self.units[record[key]])
            if 'c3i_network' in record:
                unit.c3i_network = [self.units[name] for name in array(record['c3i_network'])]

    def add_unit(self, value):
        value = deepcopy(value)
        extras = {key:value.pop(key) for key in NUMERIC+FLAGS+('swarm_target','towed_unit','c3i_network','piloting') if key in value}
        sections = value.pop('sections', [])
        weapons = value.pop('weapons', [])
        value['class'] = CLASSES.get(value.get('class'), value.get('class','MECH'))
        value.setdefault('movement', {'VEH_GROUND':'TRACK','VEH_NAVAL':'HULL','VTOL':'VTOL','AERO':'FLY','DS':'FLY','SPHEROID_DS':'FLY','MW':'BIPED','BSUIT':'BIPED'}.get(value['class'],'BIPED'))
        unit = super().add_unit(value)
        if unit.unit_type in (UnitType.VTOL, UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
            if unit.z == 0: unit.set_status(MechStatus.LANDED)
        for key,val in extras.items():
            if key == 'aim': unit.aim=number(val,0,8,True)
            elif key == 'aim_type': unit.aim_type=int(UnitType(number(val,0,integer=True)))
            elif key == 'measured_mass': unit.measured_mass=number(val,0,integer=True)
            elif key in NUMERIC: setattr(unit,{'computer_brand':'computer','radio_brand':'radio'}.get(key,key),number(val))
            elif key in FLAGS: setattr(unit,key,boolean(val))
            elif key == 'piloting':
                if unit.pilot is None: raise ValueError('piloting requires pilot')
                unit.pilot.piloting=number(val,0,20,True)
        unit.template_max_speed = extras.get('template_max_speed', unit.max_speed)
        for record in array(weapons):
            record={'name':record} if isinstance(record,str) else record
            fields(record,('name','section','critical','ammo_mode','fire_mode','brand','metadata'),('name',))
            weapon=get_weapon(record['name'])
            if weapon is None: raise ValueError('unknown weapon')
            if 'metadata' in record:
                supplied_metadata=deepcopy(record['metadata'])
                source_name=supplied_metadata.pop('source_name',None) if isinstance(supplied_metadata,dict) else None
                if source_name is not None and (not isinstance(source_name,str) or not source_name or len(source_name)>100):
                    raise ValueError('source_name must be nonempty text of at most 100 characters')
                metadata=fields(supplied_metadata,('damage','heat','vrt','crits','tonnage','range_min','range_short','range_medium','range_long','missiles','damage_per_missile','special','ammo_per_ton','explosive_damage','weapon_type','range_min_water','range_short_water','range_medium_water','range_long_water'))
                metadata={key:number(value,-1 if key in ('explosive_damage','range_min_water') else 0,integer=key!='tonnage') for key,value in metadata.items()}
                if "weapon_type" in metadata:
                    from entities.weapon import WeaponType
                    metadata["weapon_type"]=WeaponType(metadata["weapon_type"])
                weapon=replace(weapon,**metadata,**({'name':source_name} if source_name is not None else {}))
                number(weapon.crits,1,12,True)
                previous=self.weapon_overrides.get(weapon.index)
                if previous is not None and previous!=weapon: raise ValueError('inconsistent metadata for shared weapon type')
                self.weapon_overrides[weapon.index]=weapon
            else:
                weapon=self.weapon_overrides.get(weapon.index,weapon)
            loc=damage_commands.section_index(unit,record.get('section',4))
            if loc<0: raise ValueError('unknown weapon section')
            start=number(record.get('critical',0),0,11,True)
            size=weapon.crits if unit.unit_type == UnitType.MECH else 1
            if start+size>12: raise ValueError('weapon run exceeds section')
            for slot in unit.sections[loc].criticals[start:start+size]:
                if slot.type: raise ValueError('overlapping weapon')
                slot.type=i2weapon(weapon.index)
                slot.brand=number(record.get('brand',0),0,255,True)
                slot.firemode=number(record.get('fire_mode',0),0,2**32-1,True)
                slot.ammomode=number(record.get('ammo_mode',0),0,2**32-1,True)
            unit.weapons.append(WeaponState(section=loc,critical=start,weapon_idx=weapon.index))
        for section in array(sections): self.configure_section(unit,section)
        return unit

    def invoke(self, fn, *args, **kwargs):
        # The C metadata table is global; fixture overrides are scoped to this call.
        from entities.weapon import WEAPON_INDEX, WEAPON_CATALOG
        saved={index:WEAPON_INDEX[index] for index in self.weapon_overrides}
        missing=object()
        saved_names={w.name:WEAPON_CATALOG.get(w.name,missing) for w in self.weapon_overrides.values()}
        try:
            for index,weapon in self.weapon_overrides.items():
                WEAPON_INDEX[index]=weapon
                WEAPON_CATALOG[weapon.name]=weapon
            return super().invoke(fn,*args,**kwargs)
        finally:
            for index,weapon in saved.items():
                WEAPON_INDEX[index]=weapon
                WEAPON_CATALOG[weapon.name]=weapon
            for name,weapon in saved_names.items():
                if weapon is missing:WEAPON_CATALOG.pop(name,None)
                else:WEAPON_CATALOG[name]=weapon

    def configure_section(self, unit, record):
        fields(record,('index','slots')+SECTION_FIELDS,('index',))
        loc=damage_commands.section_index(unit,record['index'])
        if loc<0: raise ValueError('unknown section')
        section=unit.sections[loc]
        for key in SECTION_FIELDS:
            if key in record: setattr(section,key,number(record[key],0,integer=True))
        for entry in array(record.get('slots',[])):
            fields(entry,('index','special','weapon','ammo','temp_failure')+SLOT_FIELDS,('index',))
            slot=section.criticals[number(entry['index'],0,11,True)]
            if sum(key in entry for key in ('special','weapon','ammo','type'))>1: raise ValueError('multiple slot types')
            for key in SLOT_FIELDS:
                if key in entry: setattr(slot,key,number(entry[key],-1 if key=='desired_ammo_loc' else 0,7 if key=='desired_ammo_loc' else 2**32-1,True))
            if 'type' in entry:
                from entities.crittypes import is_weapon, is_ammo, is_special, special2i, weapon2i, ammo2weapon_i
                raw=slot.type
                if (raw > 65535 or
                    is_weapon(raw) and get_weapon_by_index(weapon2i(raw)) is None or
                    is_ammo(raw) and get_weapon_by_index(ammo2weapon_i(raw)) is None or
                    is_special(raw) and special2i(raw) not in Special._value2member_map_):
                    raise ValueError('unknown slot type')
            if 'special' in entry:
                if entry['special'] not in Special.__members__: raise ValueError('unknown special')
                slot.type=i2special(Special[entry['special']])
            for key,encode in (('weapon',i2weapon),('ammo',i2ammo)):
                if key in entry:
                    weapon=get_weapon(entry[key])
                    if weapon is None: raise ValueError('unknown weapon')
                    slot.type=encode(weapon.index)
            if 'temp_failure' in entry: enhanced_crits.set_part_temp_nuke(slot,number(entry['temp_failure'],0,15,True))

    def command(self, unit, name, args):
        args=args.split() if isinstance(args,str) else array(args)
        text=' '.join(map(str,args))
        if name in ('damage','damage-section'):
            return damage_commands.damage_command(unit,text,name=='damage-section')
        if name=='setarmorstatus':
            if len(args)!=3: return dict(accepted=False,text='Invalid arguments!')
            reply=damage_commands.set_armor_status(unit,*args)
            return dict(accepted=reply=='1',text=reply)
        if name=='dodamage':
            if len(args)!=3: return dict(accepted=False,text='Invalid arguments!')
            return damage_commands.dodamage(unit,*map(int,args))
        if name=='weaponstatus': return enhanced_crits.weapon_status_command(unit)
        if name in ('punch','kick'):
            from systems import physical, targeting
            if len(args)!=2: return dict(accepted=False,message='Expected limb and target ID.')
            target=targeting.contact_target(unit,str(args[1]))
            if target is None: return dict(accepted=False,message='Unknown target ID.')
            result=getattr(physical,'mech_'+name)(unit,target,str(args[0]))
            return dict(attacks=[asdict(r) for r in result] if isinstance(result,list) else [asdict(result)])
        if name in ('stand','prone'):
            from systems import movement_commands
            if len(args)>(1 if name=='stand' else 0): return dict(accepted=False,message='Invalid arguments!')
            result=movement_commands.stand(self.engine,unit,text) if name=='stand' else movement_commands.prone(self.engine,unit)
            return dict(accepted=result[0],message=result[1])
        if name=='aim':
            from systems.targeting import set_aim
            if len(args)!=1: return dict(accepted=False,message='Expected section or -.')
            accepted,message=set_aim(self.engine,unit,None if str(args[0])=='-' else args[0])
            return dict(accepted=accepted,message=message)
        if name=='turret':
            from systems.maneuver import set_turret
            return set_turret(self.engine,unit,text if text else None)
        if name=='ammo':
            from systems.weapon_modes import _COMMANDS, _run_command
            if len(args)!=2 or args[1] not in _COMMANDS: raise ValueError('invalid ammo mode arguments')
            return asdict(_run_command(unit,int(args[0]),args[1]))
        return super().command(unit,name,args)

    def action(self, action):
        if not isinstance(action,dict): raise ValueError('action must be an object')
        if action.get('op') == 'diagnose':
            fields(action,('op','unit','kind','options'),('op','kind'))
            unit=self.units[action.get('unit','u')]
            return self.invoke(self.diagnose_damage,unit,action['kind'],action.get('options',{}))
        if action.get('op') == 'section':
            fields(action,('op','unit','value'),('op','value'))
            self.configure_section(self.units[action.get('unit','u')],action['value'])
            return {}
        return super().action(action)

    def diagnose_damage(self, unit, kind, options):
        schemas={
          'dodamage':('total','cluster','direction','critical','message','broadcast'),
          'damage':('section','amount','rear','critical','internal','transfer','attacker','weapon','ammo_mode','ignore_swarmers'),
          'destroy-section':('section','attacker'), 'destroy-parts':('section','attacker','breach','disable'),
          'critical':('section','count','attacker'), 'slot':('section','slot','attacker'),
          'location':('side','roll','profile','critical'), 'physical-location':('side','roll','attack'),
          'target-location':('target','side','roll'),
          'hit-arc':('target',), 'aim-location':('target',), 'tc-location':('target',), 'narc-location':('target','section','rear','roll'),
          'swarm-location':('roll',), 'transfer':('section',), 'live-suit':(),
          'crittable':('section','threshold'), 'normalize':('section',),
          'effect':('name','section','attacker'), 'failure':('category','outcome','section','slot'),
          'weapon-failure':('section','slot'), 'generic-failure':('part_type',),
          'brand':('part_type','level'), 'enhanced':('section','slot','roll'),
          'weapon-detail':('section','slot'), 'weapon-count':('section',),
          'weapon-type':('section','ordinal'), 'correct-speed':(), 'bridge-hit':(),
          'destroy-heat-sink':('section',), 'main-weapon-jam':(),
          'main-weapon-destroy':('attacker',), 'motive':('modifier',),
          'brand-index':('part_type',), 'weapon-threshold':('section','slot','increment'),
          'weapon-modifiers':('section','slot','range_bracket'),
          'percentage-failure':('weapon','type','percentage','section'), 'serious':('value',),
          'explode-unit':('attacker',), 'reactor-explosion':('attacker',),
          'radio-recovery':('value',),'scanner-recovery':('value',)}
        if kind not in schemas: raise ValueError('unknown damage diagnostic')
        fields(options,schemas[kind])
        loc=damage_commands.section_index(unit,options.get('section',4))
        if loc<0: raise ValueError('unknown section')
        slot=number(options.get('slot',0),0,11,True)
        attacker=self.units[options['attacker']] if options.get('attacker') else None
        from systems.combat import apply_damage_with_transfer, HitGroup
        side=HitGroup[options.get('side','FRONT')]
        roll=options.get('roll')
        if roll is not None: number(roll,1,12,True)
        if 'weapon' in options and get_weapon(options['weapon']) is None: raise ValueError('unknown weapon')
        if kind=='dodamage':
            if any(not isinstance(options.get(key,''),str) for key in ('message','broadcast')): raise ValueError('messages must be text')
            return damage_commands.dodamage(unit,number(options['total'],1,100000,True),number(options['cluster'],1,100000,True),number(options['direction'],0,21,True),number(options.get('critical',0),integer=True),options.get('message',''),options.get('broadcast',''))
        if kind=='damage': return dict(dealt=apply_damage_with_transfer(unit,loc,number(options['amount'],0,100000,True),boolean(options.get('rear',False)),attacker,boolean(options.get('critical',False)),get_weapon(options['weapon']) if options.get('weapon') else None,number(options.get('ammo_mode',0),0,integer=True),self.engine,internal=boolean(options.get('internal',False)),transfer=boolean(options.get('transfer',False)),ignore_swarmers=boolean(options.get('ignore_swarmers',False))))
        if kind=='explode-unit': damage.explode_unit(unit,attacker);return {}
        if kind=='reactor-explosion': damage.reactor_explosion(unit,attacker,self.engine);return {}
        if kind=='destroy-section': damage.destroy_section(unit,attacker,loc,self.engine);return {}
        if kind=='destroy-parts': damage.destroy_parts(attacker,unit,loc,self.engine,breach=boolean(options.get('breach',False)),disable=boolean(options.get('disable',False)));return {}
        if kind=='critical': return [asdict(r) for r in criticals.check_and_apply_criticals(unit,loc,number(options.get('count',1),0,100,True),attacker,self.engine)]
        if kind=='slot': return asdict(criticals.apply_critical_to_slot(unit,loc,slot,attacker,self.engine))
        if kind=='location': return hit_locations.find_hit_location(unit,side,roll,profile=options.get('profile'),critical=boolean(options.get('critical',False)))
        if kind=='physical-location':
            if options['attack'] not in ('punch','kick'): raise ValueError('unknown physical attack')
            return hit_locations.physical_location(unit,side,options['attack'],roll)
        if kind=='swarm-location': return hit_locations.swarm_hit_location(roll)
        if kind in ('hit-arc','aim-location','tc-location'):
            from systems.combat import determine_hit_group, find_aim_hit_loc, find_tc_hit_loc
            target=self.units[options['target']]
            if kind=='hit-arc': return determine_hit_group(unit,target).name
            return (find_aim_hit_loc if kind=='aim-location' else find_tc_hit_loc)(unit,target)
        if kind=='target-location': return hit_locations.target_hit_location(unit,self.units[options['target']],side,roll)
        if kind=='narc-location': return hit_locations.narc_hit_location(unit,self.units[options['target']],loc if 'section' in options else None,boolean(options.get('rear',False)),roll)
        if kind=='transfer': return hit_locations.transfer_target(unit,loc)
        if kind=='live-suit': return hit_locations.live_suit_hit_location(unit)
        if kind=='crittable': return hit_locations.crittable(unit,loc,number(options['threshold'],0,100,True))
        if kind=='normalize':
            if 'section' in options: criticals.normalize_location_actuators(unit,loc)
            else: criticals.recalculate_mech_stats(unit)
            return {}
        if kind=='effect':
            names=('driver_hit','commander_hit','crew_stunned','crew_killed','sensor_hit','stabilizer_destroyed','turret_jam','turret_lock','turret_blown_off','engine_hit','fuel_tank_hit','ammo_explosion','cargo_hit','rotor_damaged','rotor_destroyed','tail_rotor_damaged','weapon_jam','weapon_destroyed')
            name=options['name']
            if name not in names: raise ValueError('unknown vehicle effect')
            import inspect
            fn=getattr(vehicle_combat,'handle_'+name)
            kwargs={key:val for key,val in [('attacker',attacker),('location',loc)] if key in inspect.signature(fn).parameters}
            return asdict(fn(unit,**kwargs))
        if kind=='failure': return asdict(failures.apply_failure(unit,number(options['category'],0,30,True),number(options['outcome'],1,6,True),loc,slot))
        if kind=='weapon-failure': return asdict(failures.check_weapon_failed(unit,loc,slot))
        if kind=='generic-failure': return asdict(failures.check_generic_fail(unit,number(options['part_type'],-2,-1,True)))
        if kind=='percentage-failure':
            weapon=get_weapon(options['weapon'])
            if weapon is None or options['type'] not in ('DAMAGE','HEAT','RANGE'): raise ValueError('invalid percentage failure')
            return asdict(failures.percentage_failure(weapon,options['type'],number(options['percentage'],0,10000,True),unit,loc))
        if kind=='serious':
            value=number(options['value'],0,integer=True)
            return dict(color=damage.serious_color(value),text=damage.serious_message(value))
        if kind=='brand': return failures.get_part_brand_name(number(options['part_type'],integer=True),number(options['level'],0,5,True))
        if kind=='enhanced':
            if roll is not None: self.streams['enhanced_rolls']=[roll]
            return enhanced_crits.score_enhanced_weapon_critical_hit(unit,attacker,loc,slot)
        if kind=='weapon-detail': return enhanced_crits.show_weapon_damage_and_info(unit,loc,slot)
        if kind=='weapon-count': return damage_commands.count_weapons_in_location(unit,loc)
        if kind=='weapon-type': return damage_commands.find_weapon_type_num_in_location(unit,loc,number(options['ordinal'],1,100,True))
        if kind=='correct-speed': vehicle_combat.correct_speed(unit);return {}
        if kind=='destroy-heat-sink': damage.destroy_heat_sink(unit,loc);return {}
        if kind=='main-weapon-jam': vehicle_combat.jam_main_weapon(unit);return {}
        if kind=='main-weapon-destroy': vehicle_combat.destroy_main_weapon(unit);return {}
        if kind=='motive': vehicle_combat.motive_system_hit(unit,number(options.get('modifier',0),integer=True));return {}
        if kind=='brand-index': return failures.get_brand_index(number(options['part_type'],integer=True))
        if kind=='weapon-threshold': return enhanced_crits.should_destroy_weapon(unit,loc,slot,boolean(options.get('increment',False)))
        if kind=='weapon-modifiers':
            bracket=number(options.get('range_bracket',0),0,2,True)
            return dict(bth=enhanced_crits.get_crit_added_bth(unit,loc,slot,bracket),
                        heat=enhanced_crits.get_crit_added_heat(unit,loc,slot),
                        damage=enhanced_crits.get_crit_sub_damage(unit,loc,slot))
        if kind=='bridge-hit': hit_locations.bridge_hit(unit);return {}
        from types import SimpleNamespace
        getattr(failures,kind.replace('-','_'))(SimpleNamespace(data=unit,data2=number(options['value'],0,10000,True)))
        return {}

    def snapshot(self):
        return self.invoke(self._snapshot)

    def _snapshot(self):
        result={}
        for name,u in self.units.items():
            scalar=('status','status2','crit_status','specials','specials2','target','speed','desired_speed','max_speed','vertical_speed','heat','plus_heat','weap_heat','engine_heat','jump_mp','jump_speed','num_sinks','pilot_hits','pilot_skill_base','base_to_hit','damage_taken','damage_inflicted','radio_range','lrs_range','tac_range','scan_range','kill_reason','si','crit_status2','tank_crit_status','working_c3_masters','total_c3_masters')
            row={key:getattr(u,key,0) for key in scalar}
            row.update(at=[u.x,u.y,u.z],started=u.is_started,destroyed=u.is_destroyed,fallen=u.is_fallen,
                       sink_capacity=u.effective_heat_sinks,pilot_present=u.pilot is not None,
                       messages=list(u.movement_messages),broadcasts=list(getattr(u,'broadcasts',[])),armor_notices=getattr(u,'armor_notices',[]),
                       weapons=enhanced_crits.weapon_status(u),stagger=sum(n['amount'] for n in u.stagger_damage_list),
                       events=[dict(kind=e.event_type.name,deadline=e.tick) for e in self.engine.events._events.values() if not e.zombie and e.data is u])
            row['sections']=[dict(**{key:int(getattr(s,key)) for key in SECTION_FIELDS}, slots=[dict(**{key:int(getattr(c,key)) for key in SLOT_FIELDS},temp_failure=enhanced_crits.part_temp_nuke(c)) for c in s.criticals]) for s in u.sections]
            row['missing_services']=sorted(getattr(u,'unavailable_updates',[]))
            row['external_effects']=deepcopy(getattr(u,'external_effects',[]))
            def related(value):
                if value is None or value == -1: return None
                return next((name for name,peer in self.units.items() if peer is value or peer._id == value),value if isinstance(value,(str,int)) else None)
            row['relationships']={key:related(getattr(u,key,None)) for key in ('swarm_target','towed_unit','carrying','spotter','tag_target','tagged_by')}
            row['relationships']['c3i_network']=[related(peer) for peer in getattr(u,'c3i_network',[])]
            result[name]=row
        return dict(time=self.engine.muxevent_tick,units=result)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',help='JSON workflow file; defaults to stdin')
    args=parser.parse_args(argv)
    try:
        if args.input:
            with open(args.input) as source: document=json.load(source)
        else: document=json.load(sys.stdin)
        session=DamageSession(document)
        results=[session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws)))
    except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
        print(str(error),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
