"""Public source diagnostics, separate from ordinary personnel commands."""
from tools.movement_inputs import fields,number,boolean
from tools.construction_templates import text


def diagnose(session,a):
    fields(a,('op','kind','unit','target','amount','gunnery','piloting','speed',
              'source_id','no_map','intentional','difficulty','leg','weapon',
              'section','physical','bth'),('op','kind'))
    from systems import swarm,experience,piloting
    kind=text(a['kind'])
    if kind=='definitions':
        from data.character_values import VALUES
        return [dict(code=i,name=v.name,type=v.type,flags=v.flags,
                     threshold=v.threshold,short=v.short) for i,v in enumerate(VALUES)]
    if kind=='pilot-bv':
        return experience.pilot_bv_factor(number(a['gunnery'],integer=True),number(a['piloting'],integer=True))
    if kind=='movement-value':return experience.movement_value(number(a['speed']))
    if kind=='old-probability':return experience.old_probability(number(a['difficulty']))
    unit=session.unit(a)
    if kind=='visibility':
        from systems.los import in_line_of_sight, calculate_los_flag
        from systems.targeting import fa_mech_range
        target=session.units[text(a['target'])]
        distance=fa_mech_range(unit,target)
        return dict(distance=distance,visible=bool(in_line_of_sight(unit,target,target.x,target.y,distance)),
                    cached=unit.map.losinfo.get((unit._id,target._id),0),
                    flags=calculate_los_flag(unit,target,unit.map,target.x,target.y,0,distance),
                    pnum_seen=unit.pnum_seen,sensors=list(unit.sensor))
    if kind=='damage-entry':
        from systems.combat import apply_damage_with_transfer
        from entities.weapon import get_weapon
        weapon=get_weapon(text(a['weapon']))
        if weapon is None:raise ValueError('Unknown weapon')
        return apply_damage_with_transfer(session.units[text(a['target'])],
            number(a.get('section',4),0,7,True),number(a['amount'],0,100000,True),
            attacker=unit,weapon=weapon,engine=session.engine,
            physical=number(a.get('physical',0),0,2,True),bth=number(a.get('bth',6),integer=True))
    original_id,original_map=unit._id,unit.map
    try:
        # Deliberately invalid source objects are diagnostic fixtures only. The
        # registered identity/map is restored before any ordinary action follows.
        if 'source_id' in a:unit._id=number(a['source_id'],-2147483648,2147483647,True)
        if boolean(a.get('no_map',False)):unit.map=None
        if kind=='swarm-query':
            queried=session.units[text(a['target'])] if 'target' in a else unit
            first=swarm.first_swarmer(queried)
            return dict(members=swarm.members(queried),swarmed=swarm.is_swarmed(queried),
                        mounted=swarm.is_mounted(queried),count=swarm.count_swarmers(queried),
                        first=first._id if first else None,name=swarm.suit_name(unit),
                        lower_name=swarm.suit_name(unit,True))
        if kind=='modifier':return swarm.modifier(unit,session.units[text(a['target'])],boolean(a.get('leg',False)))
        if kind=='recycle':swarm.start_recycle(unit,number(a['amount'],0,2147483647,True));return True
        if kind=='common-checks':return swarm.common_checks(unit)
        if kind=='detach':swarm.detach(unit,boolean(a.get('intentional',False)));return True
        if kind=='mirror':swarm.mirror(session.units[text(a['target'])],unit);return dict(x=unit.x,y=unit.y,z=unit.z,elev=unit.elev,fz=unit.fz)
        if kind in ('head','lethal'):
            fn=piloting.head_hit_mw_damage if kind=='head' else piloting.mw_lethal_damage
            fn(unit,None,number(a['amount'],integer=True));return unit.pilot_hits
        raise ValueError('Unknown pilot diagnostic')
    finally:
        unit._id,unit.map=original_id,original_map
