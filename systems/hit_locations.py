# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.hitloc.c
# Historical Aerospace sources:
#   btech/aero.move.c
#   btech/mech.hitloc.c

"""Class-aware hit tables, physical selection, critical eligibility and transfer."""
from core.randomness import roll as source_roll
import random
from core.randomness import draw
from entities.mech import Location as L, VehicleLocation as V, UnitType as U, MoveType as M, MechStatus as S, CritStatus as C, Specials
from core.events import EventType


def number(name, low, high):
    return draw(name, low, high, lambda: random.randint(low, high))


def roll_total(name='hit_location_rolls'):
    return source_roll(name, lambda: random.randint(1,6)+random.randint(1,6))


def config(unit, name, default=0):
    return getattr(unit._engine, name, default)


def live_suit_hit_location(unit):
    members = [i for i, section in enumerate(unit.sections) if section.internal != 0]
    return members[number('suit_choice', 0, len(members)-1)] if members else -1


def transfer_target(unit, location):
    if unit.unit_type == U.BSUIT:
        return live_suit_hit_location(unit)
    if unit.unit_type == U.AERO:
        return 3 if location in (0,1,2,4,5) else -1
    if unit.unit_type in (U.MECH, U.MW):
        return {L.RARM:L.RTORSO,L.RLEG:L.RTORSO,L.LARM:L.LTORSO,L.LLEG:L.LTORSO,L.RTORSO:L.CTORSO,L.LTORSO:L.CTORSO}.get(location,-1)
    return -1


def crittable(unit, location, threshold):
    if unit.specials & Specials.CRITPROOF_TECH or unit.move_type == M.NONE:
        return False
    section = unit.sections[location]
    if not section.armor_orig:
        return True
    if unit.unit_type != U.MECH and config(unit,'vcrit',2) <= 1:
        return False
    percent = 100 * section.armor // section.armor_orig
    if unit.unit_type in (U.AERO, U.DS, U.SPHEROID_DS):
        if percent < threshold: return True
        if percent == 100: return number('crittable_chance',1,71) == 23
        return percent < 100-(100-threshold)//2 and number('crittable_chance',1,11) == 6
    from core.effects import emit_channel
    if percent < threshold:
        emit_channel(unit, 'TACInfo', f'{unit._id} was below thresh (d: {percent}, tres: {threshold})')
        if number('crittable_chance',1,12) == 6:
            emit_channel(unit, 'TACInfo', f"{unit._id} is pretty unlucky. Needed 6. Rolled: 6. You're getting tac'd!")
            return True
    if percent == 100 and number('crittable_chance',1,71) == 23:
        emit_channel(unit, 'TACInfo', f'{unit._id} has full armor, but you suck. 1-71 and you got a 23? Who the eff are you, MJ?')
        return True
    return False


def physical_location(unit, group, kind, roll=None):
    from systems.combat import HitGroup as H
    roll = number('physical_location',1,6) if roll is None else roll
    if not 1 <= roll <= 6:
        raise ValueError('physical roll must be 1..6')
    if group not in (H.FRONT, H.BACK, H.LEFTSIDE, H.RIGHTSIDE):
        return -1
    quad = unit.move_type == M.QUAD
    if kind == 'kick':
        if group == H.LEFTSIDE:
            pair = (L.LARM,L.LLEG) if quad else (L.LLEG,L.LLEG)
        elif group == H.RIGHTSIDE:
            pair = (L.RARM,L.RLEG) if quad else (L.RLEG,L.RLEG)
        else:
            pair = (L.RARM,L.LARM) if quad and group == H.FRONT else (L.RLEG,L.LLEG)
        return pair[int(roll > 3)]
    if group in (H.LEFTSIDE,H.RIGHTSIDE):
        torso, arm, leg = (L.LTORSO,L.LARM,L.LLEG) if group == H.LEFTSIDE else (L.RTORSO,L.RARM,L.RLEG)
        table = (torso,torso,L.CTORSO,arm,leg if quad else arm,L.HEAD)
    else:
        table = (L.LLEG if quad and group == H.BACK else L.LARM,L.LTORSO,L.CTORSO,L.RTORSO,L.RLEG if quad and group == H.BACK else L.RARM,L.HEAD)
    return table[roll-1]


def swarm_hit_location(roll=None):
    roll = roll_total('swarm_location') if roll is None else roll
    return ((L.HEAD,L.CTORSO,L.RTORSO,L.RTORSO,L.RARM,L.CTORSO,L.LARM,L.LTORSO,L.LTORSO,L.CTORSO,L.HEAD)[roll-2], roll in (3,4,10,11), True)


def crewstun_recovery(event):
    unit = event.data
    if unit is None:
        return
    if unit.is_started and not unit.is_destroyed:
        from systems.movement_commands import notify
        notify(unit, '%ch%cgYou recover from your stunning experience!%cn' if unit.unit_type == U.MECH
               else '%ch%cgThe crew recovers from their bewilderment!%cn')
    if unit.has_crit_status(C.MECH_STUNNED):
        unit.clear_crit_status(C.MECH_STUNNED)


def modify_head_hit(unit, group):
    location = physical_location(unit,group,'punch')
    if unit.unit_type == U.MECH and location != L.HEAD and config(unit,'exile_stun_code') == 1:
        if unit._engine is None:
            raise ValueError('head stun requires owning event engine')
        from systems.notifications import mech_notify, MECHALL
        from systems.sensors import los_broadcast
        mech_notify(unit, MECHALL, '%ch%cyCRITICAL HIT!%c')
        mech_notify(unit, MECHALL, 'The cockpit violently shakes from a grazing blow! You are momentarily stunned!')
        unit._engine.cancel_events_of_type(EventType.CREWSTUN,unit)
        los_broadcast(unit, 'significantly slows down and starts wobbling!')
        unit.set_crit_status(C.MECH_STUNNED)
        if unit.speed > unit.max_speed*2/3:
            unit.desired_speed = unit.max_speed*2/3
        unit._engine.events.schedule(10,EventType.CREWSTUN,crewstun_recovery,unit)
    return location


def find_hit_location(unit, group, roll=None, *, profile=None, critical=False):
    """Public selector draws before delegating; direct profile diagnostics draw once."""
    from systems.combat import HitGroup as H, MECH_HIT_LOCATIONS
    roll = roll_total() if roll is None else roll
    if not 2 <= roll <= 12:
        raise ValueError('hit-location roll must be 2..12')
    if profile is None:
        advanced = unit.unit_type == U.VEH_GROUND and config(unit,'fasaadvvhlcrit') or unit.unit_type == U.VTOL and config(unit,'fasaadvvtolcrit')
        delegated = 'advanced' if advanced else 'critproof' if unit.specials & Specials.CRITPROOF_TECH else 'FASA' if config(unit,'fasacrit') else None
        if delegated:
            return find_hit_location(unit,group,profile=delegated,critical=critical)
        profile = 'legacy'
    if profile not in ('legacy','FASA','advanced','critproof'):
        raise ValueError('unknown hit table profile')
    if profile != 'legacy':
        critical = False
    if unit.has_status(S.COMBAT_SAFE):
        return 0,critical
    turret = unit.sections[V.TURRET]
    if getattr(unit,'dug_in',False) or getattr(unit,'tank_crit_status',0) & 0x04:
        intact = turret.internal if profile == 'advanced' else turret.internal_orig
        if intact and number('dug_in',1,100) >= 42:
            return V.TURRET,critical
    from core.randomness import record_hit_roll
    record_hit_roll(roll, unit)
    if profile == 'advanced':
        return advanced_location(unit,group,roll)
    if unit.unit_type == U.BSUIT:
        if live_suit_hit_location(unit) < 0:
            return number('empty_suit_location',0,7),critical
        # Deliberate C fallthrough into the MECH table.
    if group not in (H.FRONT, H.BACK, H.LEFTSIDE, H.RIGHTSIDE):
        return 0,critical
    if unit.unit_type in (U.MECH,U.MW,U.BSUIT):
        value = MECH_HIT_LOCATIONS.get(group,{}).get(roll,0)
        location = value[0] if isinstance(value,tuple) else value
        if roll == 2:
            success = profile == 'FASA' or profile == 'legacy' and crittable(unit,location,60)
            if success:
                from core.effects import emit_channel
                name = 'FindFasaHitLocation' if profile == 'FASA' else 'FindHitLocation'
                emit_channel(unit, 'TACInfo', f"{unit._id}'s luck sucks. It got TACed. We're in {name}()")
                critical = True
        if location == L.HEAD and config(unit,'exile_stun_code'):
            location = modify_head_hit(unit,group)
        return location,critical
    side = {H.FRONT:V.FSIDE,H.BACK:V.BSIDE,H.LEFTSIDE:V.LSIDE,H.RIGHTSIDE:V.RSIDE}.get(group,0)
    if unit.unit_type == U.VEH_GROUND:
        return ground_location(unit,group,side,roll,profile,critical)
    if unit.unit_type == U.VTOL:
        return vtol_location(unit,group,side,roll,profile,critical)
    if unit.unit_type == U.VEH_NAVAL:
        return naval_location(unit,group,side,roll,profile,critical)
    if unit.unit_type == U.AERO:
        return aero_location(unit,group,roll,profile,critical)
    if unit.unit_type in (U.DS,U.SPHEROID_DS):
        return dropship_location(unit,group,roll,profile,critical)
    return 0,critical


def advanced_location(unit,group,roll):
    from systems.combat import HitGroup as H
    from systems.vehicle_combat import motive_system_hit
    side = {H.FRONT:V.FSIDE,H.BACK:V.BSIDE,H.LEFTSIDE:V.LSIDE,H.RIGHTSIDE:V.RSIDE}.get(group,0)
    supported = unit.unit_type in (U.VEH_GROUND,U.VTOL) and group in (H.FRONT,H.BACK,H.LEFTSIDE,H.RIGHTSIDE)
    if not supported:
        location = 0
    else:
        lateral = group in (H.LEFTSIDE,H.RIGHTSIDE)
        five = V.FSIDE if lateral else V.RSIDE if group == H.FRONT else V.LSIDE
        nine = V.BSIDE if lateral else V.LSIDE if group == H.FRONT else V.RSIDE
        high = V.ROTOR if unit.unit_type == U.VTOL else V.TURRET if unit.sections[V.TURRET].internal > 0 else side if lateral else nine
        location = five if roll == 5 else nine if roll == 9 else high if roll >= 10 else side
        if unit.unit_type == U.VEH_GROUND and roll == 3 and crittable(unit,location,config(unit,'critlevel',100)):
            motive_system_hit(unit,0)
    eligible = crittable(unit,location,config(unit,'critlevel',100))
    return location, bool(supported and roll in (2,12) and eligible)


def ground_location(unit,group,side,roll,profile,critical):
    from systems.combat import HitGroup as H
    from systems.vehicle_combat import set_max_speed,make_vehicle_fall,tank_flag,TankCritStatus
    turret = unit.sections[V.TURRET].internal != 0
    location = V.TURRET if turret and roll in (10,11) else side
    lateral = group in (H.LEFTSIDE,H.RIGHTSIDE)
    if profile == 'legacy':
        if roll in (2,12):
            critical = crittable(unit,side if lateral else V.FSIDE,40) or critical
        elif roll == 11 and turret:
            critical = crittable(unit,V.TURRET,50) or critical
    elif profile == 'FASA':
        if roll in (2,12) and lateral or roll == 2 or roll == 11 and not lateral:
            critical = True
        if roll == 12 and not lateral:
            location = V.TURRET if turret else side
            critical = crittable(unit,location,config(unit,'critlevel',100)) or critical
        if roll == 11 and turret and not getattr(unit,'tank_crit_status',0) & TankCritStatus.TURRET_LOCKED:
            from systems.notifications import mech_notify, MECHALL
            mech_notify(unit, MECHALL, '%ch%cyCRITICAL HIT!%c')
            tank_flag(unit,TankCritStatus.TURRET_LOCKED,True)
            mech_notify(unit, MECHALL, 'Your turret takes a direct hit and locks up!')
        severe = roll == 3 and (lateral or config(unit,'tankshield'))
        slow = roll in (4,5) if lateral else roll == 4 and config(unit,'tankshield')
        hover = unit.move_type == M.HOVER and ((group == H.RIGHTSIDE and roll == 9) or (not lateral and roll == 5))
        if not unit.is_fallen and (severe or slow or hover):
            destroyed = severe and not config(unit,'tankfriendly')
            fasa_motive_notice(unit, 'destroyed' if destroyed else 'serious' if severe else 'minor')
            set_max_speed(unit, 0 if destroyed else unit.max_speed - (21.5 if severe else 10.75))
            if destroyed:
                make_vehicle_fall(unit)
    return location,critical


def fasa_motive_notice(unit, severity):
    from systems.notifications import mech_notify, MECHALL
    mech_notify(unit, MECHALL, '%ch%cyCRITICAL HIT!%c')
    messages = {
        'minor': {M.TRACK:'One of your tracks is damaged!', M.WHEEL:'One of your wheels is damaged!', M.HOVER:'Your air skirt is damaged!'},
        'serious': {M.TRACK:'One of your tracks is seriously damaged!', M.WHEEL:'One of your wheels is seriously damaged!', M.HOVER:'Your air skirt is seriously damaged!'},
        'destroyed': {M.TRACK:'One of your tracks is destroyed, immobilizing your vehicle!', M.WHEEL:'One of your wheels is destroyed, immobilizing your vehicle!', M.HOVER:'Your lift fan is destroyed, immobilizing your vehicle!'},
    }
    message = messages[severity].get(unit.move_type)
    if unit.move_type in (M.HULL,M.SUB,M.FOIL):
        message = {'minor':'Your craft suddenly slows!', 'serious':'Your craft lurches and suddenly loses a lot of speed!', 'destroyed':'Your engines cut out and you drift to a halt!'}[severity]
    if message:
        mech_notify(unit, MECHALL, message)


def vtol_location(unit,group,side,roll,profile,critical=False):
    from systems.combat import HitGroup as H
    from systems.vehicle_combat import handle_rotor_damaged,handle_rotor_destroyed,destroy_main_weapon
    if profile == 'critproof':
        return (side if 5 <= roll <= 9 else V.ROTOR),False
    if profile == 'FASA':
        if group in (H.LEFTSIDE,H.RIGHTSIDE):
            if roll == 3:
                return 0,True
            if roll == 9:
                destroy_main_weapon(unit)
                return 0,False
            location = side if 6 <= roll <= 8 else V.ROTOR
        else:
            location = side if 6 <= roll <= 9 else V.ROTOR
        destroy = roll == 2 or roll == 3 and group in (H.FRONT,H.BACK)
    else:
        location = side if 5 <= roll <= 9 else V.ROTOR
        destroy = roll == 2
    if location == V.ROTOR:
        (handle_rotor_destroyed if destroy else handle_rotor_damaged)(unit)
    return location,critical or roll in (2,12)


def naval_location(unit,group,side,roll,profile,critical):
    from systems.combat import HitGroup as H
    turret = unit.sections[V.TURRET].internal != 0
    if group in (H.FRONT,H.BACK) and profile != 'FASA':
        side = V.FSIDE
    omitted = group == H.LEFTSIDE and roll in (6,7,8) or group == H.RIGHTSIDE and roll == 9
    location = 0 if omitted else V.TURRET if turret and roll in (10,11) else side
    if profile != 'critproof':
        if roll == 12 and group == H.LEFTSIDE or roll == 11 and turret and group in (H.FRONT,H.BACK):
            critical = True
        elif roll in (2,12) or roll == 11 and turret:
            critical = crittable(unit,location,40) or critical
    return location,critical


def aero_location(unit,group,roll,profile,critical):
    from systems.combat import HitGroup as H
    from systems.damage_commands import lose_weapon
    from systems.damage import destroy_heat_sink
    side = 1 if group == H.LEFTSIDE else 2
    tables = {H.FRONT:(4,0,3,2,0,0,0,1,3,0,4),H.BACK:(5,3,3,2,5,3,5,1,3,3,5),H.LEFTSIDE:(4,1,5,3,1,3,1,0,5,1,5),H.RIGHTSIDE:(4,2,5,3,2,3,2,0,5,2,5)}
    location = tables[group][roll-2]
    if profile != 'critproof':
        if group == H.FRONT and roll in (3,11) and crittable(unit,0,90):
            lose_weapon(unit,0)
        elif group == H.FRONT and roll == 10 or group in (H.LEFTSIDE,H.RIGHTSIDE) and roll == 5:
            from systems.bombing import destroy_bomb
            destroy_bomb(unit,3)
        elif group in (H.LEFTSIDE,H.RIGHTSIDE):
            if roll == 12:
                critical = crittable(unit,5,99) or critical
            elif roll in (3,11) and crittable(unit,side,99):
                lose_weapon(unit,side)
            elif roll in (4,10) and crittable(unit,5,90):
                destroy_heat_sink(unit,5)
        elif group == H.BACK and roll in (2,12):
            critical = crittable(unit,5,90) or critical
        elif group == H.BACK and roll in (3,11):
            from physics.aerospace import control_effect
            control_effect(unit)
        elif group == H.BACK and roll in (4,7,10) and crittable(unit,3,90):
            destroy_heat_sink(unit,3)
    return location,critical


def dropship_location(unit,group,roll,profile,critical):
    from systems.combat import HitGroup as H
    from systems.damage_commands import lose_weapon
    from systems.damage import destroy_heat_sink
    active = profile != 'critproof'
    if group == H.FRONT:
        location = 0 if roll == 5 else 1 if roll == 9 else (1 if number('dropship_wing',1,2)==1 else 0) if roll in (4,10) else 5
        if active and roll in (2,12) and crittable(unit,5,30):
            bridge_hit(unit)
        elif active and roll in (3,11) and crittable(unit,5,50):
            lose_weapon(unit,5)
    elif group in (H.LEFTSIDE,H.RIGHTSIDE):
        side = 1 if group == H.LEFTSIDE else 0
        if number('dropship_wing',1,2) == 2 and unit.unit_type == U.SPHEROID_DS:
            side = 2 if side == 1 else 3
        location = 5 if roll in (2,9) else side
        if active and roll == 2 and crittable(unit,5,30):
            bridge_hit(unit)
        elif active and roll in (3,11) and crittable(unit,side,60):
            lose_weapon(unit,side)
        elif active and roll == 12:
            critical = crittable(unit,side,60) or critical
    else:
        location = (3 if unit.unit_type == U.SPHEROID_DS else 0) if roll == 5 else (2 if unit.unit_type == U.SPHEROID_DS else 1) if roll == 9 else 4
        if active and roll in (2,12):
            critical = crittable(unit,4,60) or critical
        elif active and roll in (4,7,10) and crittable(unit,4,60):
            destroy_heat_sink(unit,4)
    return location,critical


def bridge_hit(unit):
    from systems.damage import _kill_mech_contents, _notify
    if unit.is_destroyed: return
    if unit.in_character:
        _notify(unit, 'SHIT! The shot seems to be coming straight for the bridge!')
        _kill_mech_contents(unit)


def target_hit_location(attacker,target,group=None,roll=None,*,rear=False):
    from systems.combat import determine_hit_group,HitGroup as H
    group = determine_hit_group(attacker,target) if group is None else group
    rear = rear or group == H.BACK
    if target.unit_type == U.MECH:
        if target.has_status(S.PARTIAL_COVER):
            return physical_location(target,group,'punch'),rear,False
        if attacker.unit_type == U.MW and attacker.z <= target.z:
            return physical_location(target,group,'kick'),rear,False
        from systems.combat_firing import swarm_id
        if attacker.unit_type == U.BSUIT and swarm_id(attacker) == target._id:
            return swarm_hit_location(roll)
    location,critical = find_hit_location(target,group,roll)
    return location,rear,critical


def narc_hit_location(attacker,target,location=None,rear=False,roll=None):
    incoming_rear = rear
    if location is None:
        location,rear,_ = target_hit_location(attacker,target,roll=roll)
    while target.sections[location].internal <= 0:
        location = transfer_target(target,location)
        if location < 0:
            return -1,incoming_rear
    if target.unit_type != U.MECH:
        if rear and location == V.FSIDE:
            location = V.BSIDE
        rear = False
    return location,rear
