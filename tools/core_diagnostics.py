# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.utils.c

"""Documented source diagnostics and ordinary core command adapters."""
from dataclasses import asdict
from types import SimpleNamespace
from tools.movement_inputs import number, boolean, array, string
from core.events import EventType as E, very_fake_func
from core.randomness import roll
from systems import parts, repairs, economy, battle_value, piloting, weapon_inventory as inventory
from systems import combat_ammunition as ammunition, targeting, stagger
from physics import hexmath
from systems.criticals import find_first_weapon_crit
from systems.enhanced_crits import find_split_crits, get_split_data
from systems.weapon_modes import find_artemis_for_weapon
from systems.physical import sect_has_busy_weap
from systems.combat import is_in_weapon_arc


def integer(value): return number(value,-2**31,2**32-1,True)
def signed32(value):
    if type(value) is not int or not -2**31 <= value < 2**31:
        raise ValueError('Unsupported signed C int input or result')
    return value


def coord(value): return number(value,-32768,32767,True)
def real(value): return number(value,-1e12,1e12)
def section(value): return number(value,0,7,True)
def critical(value): return number(value,0,11,True)
def part(value): return number(value,0,1023,True)
def catalog(value):
    from entities.weapon import get_weapon_by_index
    index = number(value,0,1000,True)
    if get_weapon_by_index(index) is None: raise ValueError('unknown weapon catalog index')
    return index


def skill_weapon(value):
    index = integer(value)
    return index if index < 0 else catalog(index)


# Exact source names, production functions, whether to prepend the selected unit,
# and positional input validators. Optional arguments are handled below.
PURE = {
    'SectHasBusyWeap':(sect_has_busy_weap,True,(section,)),
    'FindArtemisForWeapon':(find_artemis_for_weapon,True,(section,critical)),
    'FindSplitCrits':(find_split_crits,True,(section,part,critical)),
    'GetSplitData':(get_split_data,True,(section,critical)),
    'FindFirstWeaponCrit':(find_first_weapon_crit,True,(section,lambda v:number(v,-1,11,True),critical,part,lambda v:number(v,1,12,True))),
    'mechtypename':(parts.mechtypename,True,()),
    'mech_armorpoints':(parts.armorpoints,True,()),'mech_intpoints':(parts.intpoints,True,()),
    'round_to_halfton':(parts.round_to_halfton,False,(signed32,)),
    'round_to_quarterton':(parts.round_to_quarterton,False,(signed32,)),
    'MyToUpper':(parts.my_to_upper,False,(parts.source_text,)),
    'ProperSectionStringFromType':(parts.section_strings,True,()),
    'ArmorStringFromIndex':(parts.armor_string,True,(integer,)),
    'listmatch':(parts.listmatch,False,(lambda xs:[string(x) for x in array(xs)],string)),
    'CountDestroyedLegs':(parts.count_destroyed_legs,True,()),
    'IsMechLegLess':(parts.is_mech_legless,True,()),
    'IsLegDestroyed':(parts.is_leg_destroyed,True,(section,)),
    'ReverseSplitCritLoc':(parts.reverse_split_crit_loc,True,(section,critical)),
    'checkSectionForSpecial':(parts.check_section_for_special,True,(integer,section)),
    'checkAllSections':(parts.check_all_sections,True,(integer,)),
    'FindObj':(parts.find_obj,True,(section,part)),
    'getRemainingInternalPercent':(parts.remaining_internal_percent,True,()),
    'getRemainingArmorPercent':(parts.remaining_armor_percent,True,()),
    'GetPartMod':(parts.part_mod,True,(part,)),
    'ProperArmor':(parts.proper_armor,True,()),'ProperInternal':(parts.proper_internal,True,()),
    'ProperMyomer':(parts.proper_myomer,True,()),'alias_part':(parts.alias_part,True,(part,section)),
    'payloadlist':(parts.payloadlist,True,()),'partlist':(parts.partlist,True,()),
    'unit_parts_list':(parts.unit_parts_list,True,(integer,)),'heat_factor':(parts.heat_factor,True,()),
    'SetCargoWeight':(parts.set_cargo_weight,True,()),'update_specials':(parts.update_specials,True,()),
    'part_weight':(parts.part_weight,False,(part,boolean)),
    'mech_RepairPart':(repairs.repair_part,True,(section,critical)),
    'mech_FillPartAmmo':(repairs.fill_part_ammo,True,(section,critical)),
    'no_locations_destroyed':(repairs.no_locations_destroyed,True,()),
    'mech_ReAttach':(repairs.reattach,True,(section,)),
    'mech_ReplaceSuit':(repairs.replace_suit,True,(section,)),
    'mech_ReSeal':(repairs.reseal,True,(section,)), 'mech_Detach':(repairs.detach,True,(section,)),
    'do_fixextra':(repairs.fixextra,True,()), 'do_magic':(repairs.magic,True,()),
    'CalcFasaCost':(economy.fasa_cost,True,()), 'Calculate_Defensive_BV':(battle_value.defensive_bv,True,()),
    'Calculate_Offensive_BV':(battle_value.offensive_bv,True,()),
    'FindWeaponIndex':(inventory.find_weapon_index,True,(integer,)),
    'FindWeaponFromIndex':(inventory.find_weapon_from_index,True,(catalog,)),
    'GetWeaponCrits':(inventory.weapon_crits,True,(catalog,)),
    'FullAmmo':(ammunition.full_ammo,True,(section,critical)),
    'FindRoundsForWeapon':(ammunition.find_rounds_for_weapon,True,(catalog,)),
    'CountAmmoForWeapon':(ammunition.count_ammo,True,(catalog,)),
    'FindAmmoForWeapon':(ammunition.find_normal_ammo_for_weapon,True,(catalog,section)),
    'FindPilotingSkillName':(piloting.find_piloting_skill_name,True,()),
    'FindGunnerySkillName':(piloting.find_gunnery_skill_name,True,(integer,)),
    'FindTechSkillName':(piloting.find_tech_skill_name,True,()),
    'FindPilotPiloting':(piloting.find_pilot_piloting,True,()),
    'FindSPilotPiloting':(piloting.find_spilot_piloting,True,()),
    'FindPilotGunnery':(piloting.find_pilot_gunnery,True,(integer,)),
    'FindPilotSpotting':(piloting.find_pilot_spotting,True,()),
    'FindPilotArtyGun':(piloting.find_pilot_arty_gun,True,()),
    'FindAverageGunnery':(lambda unit:piloting.find_pilot_gunnery(unit,0),True,()),
    'MechPilotSkillRoll_BTH':(piloting.piloting_bth,True,(integer,)),
    'prolong_uncon':(piloting.prolong_uncon,True,(integer,)),
    'FindComponents':(hexmath.find_components,False,(real,integer)),
    'FindBearing':(hexmath.find_bearing,False,(real,)*4),
    'FindZBearing':(hexmath.find_z_bearing,False,(real,)*6),
    'FindRange':(hexmath.find_range3d,False,(real,)*6),
    'FindXYRange':(hexmath.find_range,False,(real,)*4),
    'FindHexRange':(hexmath.find_range,False,(real,)*4),
    'FindXY':(hexmath.find_xy,False,(real,real,integer,real)),
    'MapCoordToRealCoord':(hexmath.hex_to_float,False,(coord,coord)),
    'RealCoordToMapCoord':(hexmath.float_to_hex,False,(real,real)),
    'MyHexDist':(hexmath.my_hex_dist,False,(coord,coord,coord,coord,integer)),
    'AcceptableDegree':(hexmath.acceptable_degree,False,(integer,)),
    'InWeaponArc':(hexmath.in_weapon_arc,True,(real,real)),
    'IsInWeaponArc':(is_in_weapon_arc,True,(real,real,section,critical)),
}
SPECIAL = {'Number','Roll','MNumber','init_stat','do_show_stat','init_genrand','init_by_array',
    'genrand_int32','genrand_int31','genrand_real1','genrand_real2','genrand_real3','genrand_res53',
    'debug_event_types','initialize_part_costs','SetPartCost','GetPartCost','MechIDS',
    'CalculateBV','CalcFasaCost_AddPrice','CalcFasaCost_DoArmMath','CalcFasaCost_DoLegMath',
    'Calc_AddOffBV','Calc_AddDefBV','Calc_SubDefBV','MechNumHeatsinksInEngine',
    'FindAmmunition','ammo_capacity','FindObjWithDest','do_sub_magic','FindWeaponNumberOnMech','FindWeapons_Advanced',
    'FindWeaponNumberOnMech_Advanced','WeaponIsNonfunctional','CritsInLoc','MechFullNoRecycle',
    'FindLegHeatSinks','FindDestructiveAmmo','FindInfernoAmmo','FindTechSkill',
    'MadePilotSkillRoll','MadePilotSkillRoll_NoXP','MadePilotSkillRoll_Advanced',
    'find_mech_in_hex','ValidMap','FindMechOnMap','FindTargetDBREFFromMapNumber','FindTargetXY','navigate_sketch_mechs',
    'CheckEdgeOfMap','Leave_Hangar','ChannelEmitKill','FuelCheck','MarkForLOSUpdate','visit_neighbor_hexes',
    'mech_heartbeat','heartbeat_dispatch','run_by_type','history_input','muxevent_count_initialize','cancel_events','callback','queue_event','multi_weap_sel',
    'calcStaggerBTHMod','calcNewStaggerBTHMod','accumulate_stagger_damage','get_stagger_damage','mark_stagger_damage',
    'clear_stagger_damage','clear_all_stagger_damage','clear_old_stagger_damage'}
ALIASES = {'GetPartWeight':'part_weight','UnitPartsList':'unit_parts_list','HeatFactor':'heat_factor',
           'ProlongUncon':'prolong_uncon','debug_EventTypes':'debug_event_types',
           'mech_stabilizing_event':'mech_jumpstabil_event'}
OPERATIONS = set(PURE) | SPECIAL | (set(ALIASES) - {'mech_stabilizing_event'})


def arguments(args, validators, minimum=None):
    if not (len(validators) if minimum is None else minimum) <= len(args) <= len(validators):
        raise ValueError('wrong number of diagnostic arguments')
    return [validate(value) for value,validate in zip(args,validators)]


def event_type(name):
    if name not in E.__members__: raise ValueError('unknown event type')
    return E[name]


def callback(name):
    name = ALIASES.get(name,name)
    from systems import startup, maneuver, vehicle_combat, hit_locations, combat_equipment, movement_commands, vehicle_fire
    from physics import jump, movement, orbital
    callbacks = {
        'vehicle_burn_event':(E.VEHICLE_BURN,vehicle_fire.burn_event),
        'vehicle_extinguish_event':(E.VEHICLE_EXTINGUISH,vehicle_fire.extinguish_event),
        'very_fake_func':(E.CUSTOM,very_fake_func),
        'mech_startup_event':(E.STARTUP,startup.startup_event),
        'mech_recovery_event':(E.RECOVERY,piloting.recovery_event),
        'mech_stand_event':(E.STAND,jump._stand_done),
        'mech_standfail_event':(E.STANDFAIL,jump._stand_recovered),
        'mech_jump_event':(E.JUMP,jump._jump_event_callback),
        'mech_jumpstabil_event':(E.JUMPSTABIL,jump._jumpstabil_callback),
        'mech_fall_event':(E.FALL,orbital.fall_event),
        'mech_move_event':(E.MOVE,movement.mech_move_event),
        'aero_move_event':(E.AERO_MOVE,movement.aero_move_event),
        'mech_crewstun_event':(E.CREWSTUN,hit_locations.crewstun_recovery),
        'unstun_crew_event':(E.UNSTUN_CREW,vehicle_combat.unstun_crew),
        'check_stagger_event':(E.CHECK_STAGGER,stagger.check_stagger_event),
        'mech_sideslip_event':(E.SIDESLIP,maneuver.sideslip_event),
        'mech_lateral_event':(E.LATERAL,lambda event:maneuver.lateral_event(SimpleNamespace(data=event.data,data2=(300,300,60,60,240,240,120,120,0)[event.data2]))),
        'mech_movemode_event':(E.MOVEMODE,movement_commands._mode_complete),
        'mech_unjam_ammo_event':(E.UNJAM_AMMO,combat_equipment.unjam_ammo_event),
        'mech_lock_event':(E.LOCK,targeting.lock_event),
        'mech_plos_event':(E.PLOS,targeting.plos_event),
    }
    if name not in callbacks: raise ValueError('unknown source callback')
    return callbacks[name]


def schedule(session,unit,name,delay,data):
    kind, fn = callback(string(name))
    data = integer(data)
    if kind == E.STARTUP: number(data,0,5,True)
    if kind == E.VEHICLE_BURN:
        number(data,0,len(unit.sections)-1,True)
        if not hasattr(unit,'_side_burns'): unit._side_burns={}
        old = unit._side_burns.get(data)
        if old is not None and not old.zombie: raise ValueError('duplicate side burn')
    if kind == E.LATERAL: number(data,0,8,True)
    if kind in (E.PLOS,E.LOCK): data = session.engine
    def observed_callback(event):
        session.observe_event('callback',event)
        return fn(event)
    event = session.engine.schedule_event(number(delay,1,100000,True),kind,observed_callback,unit,data)
    if kind == E.VEHICLE_BURN: unit._side_burns[data]=event
    if kind == E.VEHICLE_EXTINGUISH: unit._extinguish_event=event
    return event


def diagnose(session,unit,kind,args):
    kind = ALIASES.get(kind,kind)
    if kind in PURE:
        fn, with_unit, validators = PURE[kind]
        values = arguments(args,validators,{'unit_parts_list':0,'part_weight':1}.get(kind))
        result = fn(*([unit] if with_unit else []),*values)
        return signed32(result) if kind in ('round_to_halfton','round_to_quarterton') else result
    if kind not in SPECIAL: raise ValueError('unknown source operation: '+kind)
    engine, state = session.engine, session.engine.randomness
    if kind == 'FindWeapons_Advanced':
        values = arguments(args,(section,boolean,boolean),1)
        return inventory.find_weapons(unit,values[0],whine=values[1] if len(values)>1 else True,
                                      silence=values[2] if len(values)>2 else False)
    if kind == 'multi_weap_sel':
        from systems.tic import multi_weap_sel
        values = arguments(args,(string,lambda v:number(v,0,3,True),lambda v:number(v,0,96,True)),2)
        text,mode = values[:2]
        stop_after = values[2] if len(values)>2 else 0
        calls,messages = [],[]
        def record_selection(mech,low,high):
            calls.append([low,high])
            return bool(stop_after and len(calls)>=stop_after)
        multi_weap_sel(unit,text,mode,record_selection,messages)
        return dict(calls=calls,messages=messages)
    if kind == 'queue_event':
        event_kind, delay = arguments(args,(event_type,lambda v:number(v,1,100000,True)))
        event = engine.schedule_event(delay,event_kind,very_fake_func,unit)
        return dict(id=event.event_id,deadline=event.tick)
    if kind.startswith('genrand_'):
        arguments(args,())
        return getattr(state.mt,kind[8:])()
    if kind == 'Number': return state.number(*arguments(args,(integer,integer)))
    if kind == 'Roll': arguments(args,()); return roll()
    if kind == 'MNumber':
        from systems.sensors import m_number
        low,high = arguments(args,(integer,integer))
        if high < low: raise ValueError('MNumber requires ordered bounds')
        return m_number(unit,low,high)
    if kind in ('init_stat','init_genrand'):
        value, = arguments(args,(integer,))
        return state.init_stat(value) if kind=='init_stat' else state.mt.seed(value)
    if kind == 'init_by_array':
        values, = arguments(args,(lambda x:[integer(v) for v in array(x)],))
        return state.mt.init_by_array(values)
    if kind == 'do_show_stat': arguments(args,()); return state.show_stat()
    if kind == 'debug_event_types':
        arguments(args,(lambda text:text if isinstance(text,str) else string(text),),0)
        return engine.events.debug_event_types(*args)
    if kind == 'initialize_part_costs': arguments(args,()); session.costs = economy.CostTables(); return None
    if kind in ('GetPartCost','SetPartCost'):
        values = arguments(args,(part,) if kind=='GetPartCost' else (part,lambda v:number(v,0,2**64-1,True)))
        return session.costs.get(*values) if kind=='GetPartCost' else session.costs.set(*values)
    if kind == 'MechIDS': return parts.mech_ids(unit,*arguments(args,(boolean,),0))
    if kind == 'CalculateBV':
        arguments(args,(integer,integer,integer),0)
        if len(args)==1: raise ValueError('CalculateBV takes zero, two or three arguments')
        gun,pilot = args[:2] if args else (100,100)
        tick = args[2] if len(args)==3 else engine.muxevent_tick
        return battle_value.calculate_bv(unit,gun,pilot,tick=tick)
    if kind in ('CalcFasaCost_DoArmMath','CalcFasaCost_DoLegMath'):
        return economy.actuator_cost(unit,*arguments(args,(section,)),leg=kind=='CalcFasaCost_DoLegMath')
    if kind == 'MechNumHeatsinksInEngine': arguments(args,()); return parts.heatsinks_in_engine(unit)
    if kind in ('CalcFasaCost_AddPrice','Calc_AddOffBV','Calc_AddDefBV','Calc_SubDefBV'):
        total,label,value = arguments(args,(real,string,real))
        prefix = 'Addprice -' if kind=='CalcFasaCost_AddPrice' else 'AddOffBV' if kind=='Calc_AddOffBV' else 'AddDefBV'
        result = economy.calculation(unit,prefix,total)
        result.add(label,value,subtract=kind=='Calc_SubDefBV')
        return result
    if kind == 'FindAmmunition': return ammunition.find_ammunition(unit,*arguments(args,(boolean,),0))
    if kind == 'ammo_capacity': return ammunition.ammo_capacity(*arguments(args,(lambda v:number(v,0,65535,True),integer,integer)))
    if kind == 'FindObjWithDest': return parts.find_obj(unit,*arguments(args,(section,part)),with_destroyed=True)
    if kind == 'do_sub_magic': return repairs.sub_magic(unit,*arguments(args,(boolean,),0))
    if kind in ('FindWeaponNumberOnMech','FindWeaponNumberOnMech_Advanced'):
        from systems.weapon_modes import find_weapon_number_on_mech
        values = arguments(args,(integer,boolean),1)
        return find_weapon_number_on_mech(unit,values[0],sight=values[1] if len(values)>1 else False)
    if kind == 'WeaponIsNonfunctional': return inventory.weapon_is_nonfunctional(unit,*arguments(args,(section,critical,integer),2))
    if kind == 'CritsInLoc':
        from entities.crittypes import crits_in_loc
        return crits_in_loc(unit,*arguments(args,(section,)))
    if kind == 'MechFullNoRecycle':
        from systems.physical import mech_full_no_recycle
        return mech_full_no_recycle(unit,*arguments(args,(integer,)))
    if kind == 'FindLegHeatSinks':
        from systems.heat_control import leg_heat_sinks
        arguments(args,()); return leg_heat_sinks(unit)
    if kind in ('FindDestructiveAmmo','FindInfernoAmmo'):
        from systems.heat import find_destructive_ammo
        arguments(args,())
        return find_destructive_ammo(unit,inferno_only=kind=='FindInfernoAmmo')
    if kind == 'FindTechSkill': arguments(args,()); return piloting.find_tech_skill(unit.command_actor,unit)
    if kind.startswith('MadePilotSkillRoll'):
        values = arguments(args,(integer,boolean,boolean),0)
        return piloting.make_piloting_roll(unit,values[0] if values else 0,
            succeed_when_fallen=values[1] if len(values)>1 else True,
            award_xp=values[2] if len(values)>2 else kind != 'MadePilotSkillRoll_NoXP')
    if kind == 'find_mech_in_hex':
        found = targeting.find_mech_in_hex(unit,unit.map,*arguments(args,(coord,coord,lambda v:number(v,0,3,True))))
        return getattr(found,'_id',found)
    if kind == 'ValidMap':
        values = arguments(args,(string,boolean,lambda v:v if isinstance(v,str) else string(v),boolean),1)
        reference = values[0]
        board = session.maps.get(reference)
        valid,xtype,allocated = (values[1:] + [True,'MAP',True][len(values)-1:]) if len(values)>1 else (board is not None,'MAP',True)
        found,error = targeting.valid_map(dict(valid=valid,xtype=xtype,object=board if allocated else None), getattr(unit,'command_actor',None))
        return dict(id=found._id if found is not None else None,error=error)
    if kind in ('FindMechOnMap','FindTargetDBREFFromMapNumber'):
        token, = arguments(args,(string,))
        found = (targeting.find_mech_on_map(unit.map,token) if kind == 'FindMechOnMap'
                 else targeting.contact_target(unit,token))
        return found._id if found is not None else -1
    if kind == 'FindTargetXY':
        from systems.combat import find_target_xy
        arguments(args,()); return find_target_xy(unit)
    if kind == 'navigate_sketch_mechs':
        x,y = arguments(args,(coord,coord))
        return targeting.navigate_sketch_mechs(unit,unit.map,x,y,[' '*27 for _ in range(13)])
    if kind in ('CheckEdgeOfMap','Leave_Hangar'):
        from systems import map_transitions
        arguments(args,())
        return map_transitions.check_edge_of_map(unit) if kind=='CheckEdgeOfMap' else map_transitions.leave_hangar(unit.map,unit)
    if kind == 'ChannelEmitKill':
        from systems.damage import channel_emit_kill
        arguments(args,(string,lambda value:value if value is None or isinstance(value,str) else string(value)),0)
        return channel_emit_kill(unit,session.units[args[0]] if args else None,args[1] if len(args)>1 else None)
    if kind == 'FuelCheck':
        from physics.heights import fuel_check
        arguments(args,()); return fuel_check(unit)
    if kind == 'MarkForLOSUpdate':
        from systems.ecm import mark_for_los_update
        arguments(args,()); return mark_for_los_update(unit)
    if kind == 'visit_neighbor_hexes':
        from entities.map import neighbors
        return list(neighbors(unit.map,*arguments(args,(coord,coord))))
    if kind == 'mech_heartbeat':
        from core.game_loop import mech_heartbeat
        arguments(args,()); return mech_heartbeat(engine,unit)
    if kind == 'heartbeat_dispatch':
        name, = arguments(args,(string,))
        return engine.heartbeat_dispatch(session.objects[name] if name in session.objects else session.units[name])
    if kind == 'run_by_type': return engine.events.run_by_type(*arguments(args,(event_type,)))
    if kind == 'history_input':
        counts, = arguments(args,(lambda xs:[number(v,0,2**31-1,True) for v in array(xs)],))
        if len(counts)>100: raise ValueError('history has 100 source slots')
        if sum(counts)>2**31-1: raise ValueError('history total exceeds source signed integer')
        engine.events.history[:] = counts + [0]*(100-len(counts))
        return None
    if kind == 'muxevent_count_initialize':
        arguments(args,()); return engine.events.initialize_history()
    if kind == 'cancel_events': return engine.cancel_events_of_type(*arguments(args,(event_type,)),unit)
    if kind == 'callback':
        name,data = (args+[0])[:2]
        arguments(args,(string,integer,boolean),1)
        if len(args)>2 and args[2]:
            if name != 'mech_crewstun_event': raise ValueError('null callback unit is supported only for mech_crewstun_event')
            unit = None
        event = schedule(session,unit,name,1,data)
        try:
            engine.events._execute(event)
            return None
        finally: event.cancel()
    if kind == 'calcStaggerBTHMod': arguments(args,()); return stagger.legacy_modifier(unit)
    if kind == 'calcNewStaggerBTHMod':
        values = arguments(args,(integer,boolean),1)
        return stagger.stagger_modifier(unit,values[0],values[1] if len(values)>1 else getattr(engine,'stagger_tonnage',True))
    if kind == 'accumulate_stagger_damage': return stagger.record_damage(unit,*arguments(args,(integer,)),engine=engine)
    if kind == 'get_stagger_damage': return stagger.current_damage(unit,*arguments(args,(integer,boolean),1))
    if kind == 'mark_stagger_damage': return stagger.mark_damage(unit,*arguments(args,(integer,)))
    if kind == 'clear_stagger_damage': return stagger.remove_damage(unit,*arguments(args,(integer,)))
    if kind == 'clear_old_stagger_damage': return stagger.clear_expired(unit,*arguments(args,(integer,)))
    if kind == 'clear_all_stagger_damage': arguments(args,()); return stagger.clear_all(unit)
    raise ValueError('unsupported source operation: '+kind)


COMMANDS = {'repair':'mech_RepairPart','refill':'mech_FillPartAmmo','reattach':'mech_ReAttach',
    'replacesuit':'mech_ReplaceSuit','reseal':'mech_ReSeal','detach':'mech_Detach',
    'fixextra':'do_fixextra','recalculate':'do_magic','parts':'unit_parts_list','cost':'CalcFasaCost',
    'defensivebv':'Calculate_Defensive_BV','offensivebv':'Calculate_Offensive_BV','bv':'CalculateBV',
    'rollstats':'do_show_stat','eventstats':'debug_event_types'}


def command(session,unit,name,args):
    if name in ('startup','shutdown'):
        from systems import startup
        text = args if isinstance(args,str) else ' '.join(map(str,array(args)))
        actor = unit.command_actor
        accepted,text = getattr(startup,name)(session.engine,unit,text,caller=actor,wizard=getattr(actor,'wizard',False))
        return dict(accepted=accepted,text=text)
    if name == 'skills': return dict(accepted=True,result=session.skill_snapshot(unit))
    if name not in COMMANDS: return NotImplemented
    args = args.split() if isinstance(args,str) else array(args)
    if name in ('repair','refill','reattach','replacesuit','reseal','detach','bv'):
        from systems.damage_commands import section_index
        if name != 'bv' and args:
            loc = section_index(unit,args[0])
            if loc < 0: return dict(accepted=False,text='Invalid section.')
            args = [loc]+args[1:]
        try: args = [int(value) for value in args]
        except (ValueError,TypeError): return dict(accepted=False,text='Arguments must be integers.')
    try:
        result = diagnose(session,unit,COMMANDS[name],args)
    except ValueError as error:
        if name not in ('repair','refill','reattach','replacesuit','reseal','detach','bv'): raise
        return dict(accepted=False,text=str(error))
    return dict(accepted=True,result=result)
