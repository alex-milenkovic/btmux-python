"""Explicit, validated diagnostic inputs into production combat functions."""
from dataclasses import asdict
from types import SimpleNamespace
from tools.movement_inputs import fields,number,boolean
from systems import combat,combat_ranges as ranges,physical,combat_equipment as equipment
from entities.weapon import get_weapon_by_index
from systems.damage_commands import section_index

SCHEMAS={
    'map-unregister':(),
    'combat-range':('weapon','target','distance','network_range','ordinary'),
    'combat-bth':('weapon','target','distance','indirect_fire','spotter'),
    'artillery-bth':('weapon','distance','indirect'),
    'artillery-launch':('weapon','x','y','hit'),
    'ammunition-check':('weapon','offset'),
    'combat-attack':('weapon','target','distance','roll','cluster_roll','location_roll','aim_roll','tc_roll','x','y'),
    'missile-hit':('weapon','target','bth','roll','incoming','player_roll','cluster_roll','ams_roll'),
    'missile-index':('weapon','target','glancing'),
    'swarm-next':('target','visited','enemy_only'),
    'swarm-hit':('weapon','target','bth','roll','incoming','enemy_only','player_roll'),
    'physical-damage':('target','attack','section','weight','glancing'),
    'impact-damage':('weapon','target','distance','failure_type','failure_modifier','temporary'),
    'physical-attack':('target','attack','section','weight','bth','roll'),
    'dfa':('target','roll'), 'charge':('target','roll','target_roll'),
    'blast':('damage','cluster','heat','x','y','source_real','table','safeup','safedown','underwater','neighbors',
             'target_message','observer_message','neighbor_target_message','neighbor_observer_message'),
    'combat-callback':('name','data'),
    'terrain-hit':('weapon','x','y','damage','hit','operation'),
}


def callback(name):
    from core.events import EventType as E
    table={'explode':(E.EXPLODE,equipment.explode_event),
        'unjam-ammo':(E.UNJAM_AMMO,equipment.unjam_ammo_event),
        'dig':(E.DIG,equipment.dig_event),'unjam-turret':(E.UNJAM_TURRET,equipment.unjam_turret_event),
        'remove-pods':(E.REMOVE_PODS,equipment.remove_pods_event),
        'signature':(E.STEALTH_ARMOR,equipment.signature_event),
        'booster':(E.MASC_FAIL,equipment.booster_event),'booster-regen':(E.MASC_REGEN,equipment.booster_regen)}
    if name=='jump-stabil':
        from physics.jump import _jumpstabil_callback
        return E.JUMPSTABIL,_jumpstabil_callback
    if name=='sixth-sense':
        from systems.targeting import sixth_sense_event
        return E.SIXTH_SENSE,sixth_sense_event
    if name not in table:raise ValueError('unknown combat callback')
    return table[name]


def callback_data(name,value):
    if name=='sixth-sense':return number(value,-100000,100000,True)
    if name=='signature':
        from tools.movement_inputs import array
        system,enabled=array(value,2)
        if system not in ('stealtharmor','nullsig'):raise ValueError('unknown signature system')
        return system,boolean(enabled)
    if name.startswith('booster'):
        if value not in ('masc','scharge'):raise ValueError('unknown booster')
        return value
    return number(value,0,100000,True)


def mounted(unit,ordinal):
    ordinal=number(ordinal,0,len(unit.weapons)-1,True)
    ws=unit.weapons[ordinal]
    slot=unit.sections[ws.section].criticals[ws.critical]
    return ws,get_weapon_by_index(ws.weapon_idx),slot


def diagnose(session,unit,kind,options):
    fields(options,SCHEMAS[kind],('weapon',) if 'weapon' in SCHEMAS[kind] else ())
    if kind=='map-unregister':
        session.engine.unregister_entity(session.map)
        return {}
    target=session.units[options['target']] if options.get('target') is not None else None
    if 'weapon' in options:ws,weapon,slot=mounted(unit,options['weapon'])
    distance=number(options.get('distance',combat_distance(unit,target)),0)
    def roll(name):
        return None if name not in options else number(options[name],1 if name=='tc_roll' else 2,6 if name=='tc_roll' else 12,True)
    if kind=='ammunition-check':
        from systems.combat_ammunition import expenditure_check
        return dict(severity=expenditure_check(unit,weapon.index,number(options.get('offset',0),0,1000,True)))
    if kind=='swarm-next':
        from tools.movement_inputs import array
        from systems.missile import swarm_next_target
        if target is None:raise ValueError('swarm source target is required')
        chosen=swarm_next_target(unit,target,[session.units[name] for name in array(options.get('visited',[]))],boolean(options.get('enemy_only',False)))
        return dict(target=next((name for name,u in session.units.items() if u is chosen),None))
    if kind=='swarm-hit':
        from systems.missile import swarm_hit_target
        if target is None:raise ValueError('swarm target is required')
        return asdict(swarm_hit_target(unit,target,weapon,ws.section,ws.critical,
            number(options['bth'],integer=True),number(options['roll'],2,12,True),
            number(options['incoming'],0,1000,True),boolean(options.get('enemy_only',False)),
            number(options.get('player_roll',options['roll']),2,12,True)))
    if kind=='artillery-bth':
        from systems.artillery import artillery_bth
        return dict(bth=artillery_bth(unit,ws.section,weapon,distance,boolean(options.get('indirect',False))))
    if kind=='impact-damage':
        from systems.combat_impacts import determine_damage
        failure=options.get('failure_type')
        if failure not in (None,'DAMAGE'):raise ValueError('unsupported damage failure')
        return dict(damage=determine_damage(unit,target,weapon,distance,ws.section,ws.critical,
            ammo_mode=slot.ammomode,failure_type=failure,
            failure_modifier=number(options.get('failure_modifier',0),0,1000,True),
            temporary=boolean(options.get('temporary',False))))
    if kind=='artillery-launch':
        from systems.artillery import artillery_shoot
        x,y=coordinates(session,options,None)
        artillery_shoot(session.engine,unit,x,y,weapon.index,slot.ammomode,boolean(options.get('hit',True)))
        return {}
    if kind=='combat-range':
        water=ranges.underwater(unit,ws.section)
        network,ref=ranges.find_c3_range(unit,target,distance,boolean(options.get('ordinary',True)))
        if 'network_range' in options:
            network=number(options['network_range'],0)
            bracket,modifier=ranges.by_c3_range(unit,target,ws.section,weapon,distance,network,slot.ammomode)
        else:bracket,modifier=ranges.by_range(unit,target,ws.section,weapon,distance,slot.firemode,slot.ammomode)
        return dict(bracket=bracket,modifier=modifier,long=ranges.long_range(weapon,water),extreme=ranges.extreme_range(unit,weapon,water),actual_range=distance,network_range=network,c3_ref=ref)
    if kind=='combat-bth':
        spotter=session.units[options['spotter']] if options.get('spotter') else None
        result=combat.calculate_bth(unit,target,weapon,distance,unit.pilot.gunnery,ws.section,
            w_ammo_mode=slot.ammomode,w_fire_mode=slot.firemode,indirect_fire=number(options.get('indirect_fire',1000),integer=True),spotter=spotter,critical=ws.critical)
        critical=result.critical_bth
        network,_=ranges.find_c3_range(unit,target,distance)
        return dict(asdict(result),critical_bth=critical,actual_range=distance,network_range=network)
    if kind=='combat-attack':
        x,y=coordinates(session,options,target)
        return asdict(combat.resolve_attack(unit,target,weapon,distance,unit.pilot.gunnery,
            to_hit_roll=roll('roll'),cluster_roll=roll('cluster_roll'),location_roll=roll('location_roll'),
            aim_roll=roll('aim_roll'),tc_roll=roll('tc_roll'),section=ws.section,w_section=ws.section,w_critical=ws.critical,
            w_fire_mode=slot.firemode,w_ammo_mode=slot.ammomode,mapx=x,mapy=y,ishex=target is None,engine=session.engine))
    if kind in ('missile-hit','missile-index'):
        from systems import missile
        if kind=='missile-index':return dict(index=missile.missile_hit_index(unit,weapon,ws.section,ws.critical,target,boolean(options.get('glancing',False))))
        return asdict(missile.missile_hit_target(unit,target,weapon,ws.section,ws.critical,
            number(options['bth'],integer=True),number(options['roll'],2,12,True),number(options['incoming'],0,1000,True),
            number(options.get('player_roll',options['roll']),2,12,True),cluster_roll=roll('cluster_roll'),ams_roll=roll('ams_roll')))
    if kind in ('dfa','charge'):
        if target is None:raise ValueError('target is required')
        result=physical.dfa_attack(unit,target,roll('roll')) if kind=='dfa' else physical.charge_mech(unit,target,roll('roll'),roll('target_roll'))
        return asdict(result)
    if kind.startswith('physical-'):
        if target is None:raise ValueError('target is required')
        attack=physical.PhysicalAttackType[options['attack'].upper()]
        loc=section_index(unit,options.get('section','RA'))
        if loc<0:raise ValueError('unknown physical section')
        weight=number(options.get('weight',5 if attack==physical.PhysicalAttackType.KICK else 10),1,1000,True)
        if kind=='physical-damage':result=physical.physical_damage(unit,target,weight,attack,loc,boolean(options.get('glancing',False)))
        else:result=physical.physical_attack(unit,weight,number(options['bth'],integer=True),attack,loc,target,roll=roll('roll'))
        return asdict(result)
    if kind=='combat-callback':
        _,fn=callback(options['name']);fn(SimpleNamespace(data=unit,data2=callback_data(options['name'],options.get('data',0))))
        return {}
    if kind=='blast':
        from systems.damage import blast_hit_hexes_f,TABLE_GEN,TABLE_PUNCH,TABLE_KICK
        from physics.hexmath import hex_to_float
        from tools.movement_inputs import array
        x=number(options.get('x',unit.x),-200,400,True)
        y=number(options.get('y',unit.y),-200,400,True)
        fx,fy=hex_to_float(x,y)
        source=[number(v) for v in array(options.get('source_real',[fx,fy]),2)]
        table={'normal':TABLE_GEN,'punch':TABLE_PUNCH,'kick':TABLE_KICK}[options.get('table','normal')]
        def message(key,default):
            value=options.get(key,default)
            if value is not None and not isinstance(value,str):raise ValueError('blast message must be text or null')
            return value
        blast_hit_hexes_f(session.map,number(options['damage'],-100000,100000,True),number(options.get('cluster',5),1,100000,True),
            number(options.get('heat',0),integer=True),fx,fy,*source,message('target_message','Blast hits you!'),message('observer_message','is hit by the blast!'),
            message('neighbor_target_message','Blast hits you!'),message('neighbor_observer_message','is hit by the blast!'),table,number(options.get('safeup',10),integer=True),
            number(options.get('safedown',10),integer=True),boolean(options.get('underwater',False)),
            number(options.get('neighbors',0),0,20,True),engine=session.engine)
        return {}
    if kind=='terrain-hit':
        x,y=coordinates(session,options,unit)
        amount=number(options.get('damage',weapon.damage),0,100000,True)
        operation=options.get('operation','hex')
        if operation=='hex':combat.hex_hit(unit,x,y,weapon.index,slot.ammomode,amount,number(options.get('hit',1),0,1,True))
        elif operation=='ignite-clear':combat.possibly_ignite_or_clear(unit,weapon.index,slot.ammomode,amount,x,y,number(options.get('hit',1),0,1,True))
        elif operation=='ice':combat.possibly_blow_ice(unit,weapon.index,x,y)
        elif operation=='bridge':combat.possibly_blow_bridge(unit,weapon.index,x,y)
        elif operation=='building':combat.hit_building(unit,x,y,weapon.index,amount)
        else:raise ValueError('unknown terrain operation')
        return {}


def combat_distance(unit,target):
    from systems.targeting import fa_mech_range
    return fa_mech_range(unit,target) if target is not None else 0


def coordinates(session,options,target):
    return (number(options.get('x',target.x if target else 0),0,session.map.map_width-1,True),
            number(options.get('y',target.y if target else 0),0,session.map.map_height-1,True))
