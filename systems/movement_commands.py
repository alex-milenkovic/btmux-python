# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.bth.c
#   btech/mech.events.c
#   btech/mech.move.c
#   btech/mech.notify.c
#   btech/mech.update.c
# Historical Aerospace sources:
#   btech/ds.turret.c
#   btech/mech.bth.c

"""Movement commands, eligibility, modes, posture and maneuvers."""
from entities.mech import (
    MechStatus as S, MechStatus2 as S2, MoveType, Location, UnitType, CritStatus, Specials,
)
from entities.map import WATER, ICE, BRIDGE, HIGHWATER
import re
from core.events import EventType
from physics.cargo import cargo_max_speed
from core.randomness import draw, float32
import math


MP1 = 10.75


def in_water(unit):
    from physics.collision import mech_rterrain
    return mech_rterrain(unit) in (WATER, ICE, BRIDGE) and unit.z < 0


def grounded_watercraft(unit):
    # mech.move.c speed/heading use WaterBeast && NotInWater. OnWater includes
    # the surface; the strict InWater predicate above remains for submerged rules.
    from physics.collision import mech_rterrain
    return (unit.move_type in (MoveType.HULL, MoveType.FOIL) and
            not (mech_rterrain(unit) in (WATER, ICE, BRIDGE) and unit.z <= 0))


def water_beast(unit):
    return unit.move_type in (MoveType.HULL, MoveType.FOIL)


def pending(unit, name):
    # Source posture/mode macros query queued events, including events restored
    # without the optional Python callback handle.
    event_type = {'_mode_event': EventType.MOVEMODE,
                  '_hulldown_event': EventType.HULLDOWN,
                  '_stand_event': EventType.STAND,
                  '_standfail_event': EventType.STANDFAIL,
                  '_stabil_event': EventType.JUMPSTABIL}.get(name)
    engine = getattr(unit, '_engine', None)
    if engine is not None and event_type is not None:
        return engine.has_event(event_type, unit)
    event = getattr(unit, name, None)
    return event is not None and not event.zombie


def posture_guard(unit):
    if unit.has_status(S.HULLDOWN):
        return 'You can not move while hulldown'
    if pending(unit, '_hulldown_event'):
        return 'You are busy changing your hulldown mode'
    return None


def limb_busy(unit, locations=None, weapons=True):
    if locations is None:
        locations = (tuple(unit.sections) if isinstance(unit.sections, dict)
                     else range(len(unit.sections)))
    return (any(unit.sections[loc].recycle > 0 for loc in locations) or
            (weapons and any(w.recycle > 0 and w.section in locations for w in unit.weapons)))


def stand_time(unit):
    return int(30 / min(30, max(1, unit.max_speed / (2 * MP1))))


def legs(unit):
    return (Location.LLEG, Location.RLEG) + ((Location.LARM, Location.RARM) if unit.move_type == MoveType.QUAD else ())


def mode_locked(unit):
    return bool(unit.status2 & S2.MOVE_MODES_LOCK or
                (pending(unit, '_mode_event') and not unit.has_status2(S2.DODGING)))


def mode_delay(unit):
    return 15 if unit.unit_type in (UnitType.MW, UnitType.BSUIT) else 30


def target_mode_bth(unit):
    """Weapon BTH mode modifiers (mech.bth.c), independent of target speed."""
    value = getattr(unit, 'btech_sprint_bth', -4) if unit.has_status2(S2.SPRINTING) else 0
    if unit.has_status2(S2.EVADING) and not unit.is_fallen:
        value += 1
    return value




def notify(unit, text, audience=2):
    from physics.movement import _notify
    if not hasattr(unit, 'movement_messages'):
        unit.movement_messages = []
    unit.movement_messages.append(text)
    _notify(unit, text, audience=None)
    if audience is not None:
        from systems.notifications import deliver
        deliver(unit, audience, text)
    return text


def printf_notice(unit, template, *args, audience=2):
    from systems.notifications import mech_printf
    message = template % args
    mech_printf(unit, audience, '%s', message)
    return message


def caller_notice(unit, caller, message):
    from core.effects import notify_actor
    from systems.combat_commands import NotifiedError
    if unit is not None: notify_actor(unit, unit.pilot if caller is None else caller, message)
    return NotifiedError(message)


def historical_aircraft(unit):
    return unit.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)


def actor_is_pilot(unit, caller=None):
    actor = unit.pilot if caller is None else caller
    if actor is unit.pilot: return True
    aid = actor if isinstance(actor, int) else getattr(actor, '_id', -1)
    pid = unit.pilot if isinstance(unit.pilot, int) else getattr(unit.pilot, '_id', -1)
    return aid >= 0 and aid == pid


def wizard_actor(actor):
    return actor == 1 or getattr(actor, '_id', -1) == 1 or getattr(actor, 'wizard', False) or getattr(actor, 'god', False)


def guard(unit, caller=None, pilot_only=False):
    from systems.combat_commands import command_guard
    return command_guard(unit, caller=caller, pilot_only=pilot_only, wizard=wizard_actor(caller))


def attributes(argument, count):
    from data.templates import parse_attributes
    return parse_attributes('' if argument is None else str(argument), count)


def removing_pods(unit):
    return unit._engine is not None and unit._engine.has_event(EventType.REMOVE_PODS, unit)


def swarm_target_id(unit):
    from systems.combat_firing import swarm_id
    return swarm_id(unit)


def moving_guard(unit):
    if unit.has_status2(S2.FORTIFIED):
        return 'Your fortified state prevents you from moving.'
    if unit.move_type == MoveType.NONE:
        return 'This piece of equipment is stationary!'
    if pending(unit, '_stand_event'):
        return 'You are currently standing up and cannot move.'
    if unit.is_fallen:
        return 'You are currently prone and cannot move.'
    if grounded_watercraft(unit):
        return 'You are regrettably unable to move at this time.'
    return None


def c_number(value, integer=False):
    pattern = r'\s*([+-]?\d+)' if integer else r'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
    match = re.match(pattern, str(value))
    return (int if integer else float)(match[1]) if match else 0


def maybe_move(engine, unit):
    from physics.movement import start_move_event
    unit._engine = engine
    if unit.is_started and (not unit.is_fallen or unit.unit_type == UnitType.MECH):
        start_move_event(engine, unit)



MODES = {'sprint': S2.SPRINTING, 'evade': S2.EVADING, 'dodge': S2.DODGING}


def _mode_complete(event):
    unit = event.data
    encoded = event.data2 if isinstance(event.data2,int) else None
    if encoded is None:
        flag, entering = event.data2
        used = False
    else:
        flag = S2.EVADING if encoded & 1 else S2.SPRINTING if encoded & 2 else S2.DODGING if encoded & 16 else None
        entering, used = bool(encoded & 4), bool(encoded & 32)
    unit._mode_event = None
    if not unit.is_started or unit.is_destroyed:
        unit.clear_status2(S2.MOVE_MODES)
        return
    from systems.sensors import los_broadcast
    if entering:
        if flag == S2.DODGING and limb_busy(unit, weapons=False):
            notify(unit, 'You cannot enter DODGE mode due to physical useage.')
            return
        if flag is not None: unit.set_status2(flag)
        if flag == S2.EVADING:
            notify(unit,'You bounce chaotically as you maximize your movement mode to evade!')
            los_broadcast(unit,'suddenly begins to move erratically performing evasive maneuvers!')
        elif flag == S2.SPRINTING:
            notify(unit,'You shimmy side to side as you get more speed from your movement mode.')
            los_broadcast(unit,'breaks out into a full blown stride as it sprints over the terrain!' if unit.unit_type in (UnitType.MECH,UnitType.BSUIT) else 'shifts into high gear as it gains more speed!')
            if unit.speed < 0:
                notify(unit,'You stop your backward momemtum while sprinting and come to a stop!')
                unit.desired_speed = 0
        elif flag == S2.DODGING:
            notify(unit,'You brace yourself for any oncoming physicals.')
    else:
        if flag is not None: unit.clear_status2(flag)
        if flag == S2.EVADING:
            notify(unit,'Cockpit movement normalizes as you cease your evasive maneuvers.')
            los_broadcast(unit,'ceases its evasive behavior and calms down.')
        elif flag == S2.SPRINTING:
            notify(unit,'You feel less seasick as you leave your sprint mode and resume normal movement.')
            los_broadcast(unit,'slows down and enters a normal movement mode.')
        elif flag == S2.DODGING:
            notify(unit,'Your dodge maneuver has been used and you are no longer braced for physicals.' if used else 'You loosen up your stance and no longer dodge physicals.')
    maximum = cargo_max_speed(unit)
    if unit.speed > maximum or unit.desired_speed > maximum:
        unit.desired_speed = maximum


def schedule_mode(engine, unit, flag, entering, delay=None):
    unit._engine = engine
    unit._mode_event = engine.schedule_event(mode_delay(unit) if delay is None else delay,
                                             EventType.MOVEMODE, _mode_complete,
                                             data=unit, data2=(flag, entering))


def set_mode(engine, unit, mode, caller=None):
    from systems.characters import actor_advantage
    from systems.physical import mech_full_no_recycle
    from systems.combat import part_is_nonfunctional
    mode = mode.lower()
    flag = MODES[mode]
    if unit is not None: unit._engine = engine
    error = guard(unit, caller, True)
    if error: return False, error
    entering = not unit.has_status2(flag)
    checks = [(not historical_aircraft(unit) and unit.has_status2(S2.FORTIFIED), 'Your fortified state prevents you from moving.'),
              (not historical_aircraft(unit) and unit.cocoon, 'While falling out of the sky?'),
              (unit.move_type == MoveType.NONE, 'This piece of equipment is stationary!')]
    if flag == S2.SPRINTING: checks.append((unit.carrying > 0, 'You cannot sprint while towing!'))
    checks.append((pending(unit, '_stand_event'), 'You are currently standing up and cannot move.'))
    if flag != S2.DODGING: checks.append((unit.is_jumping, 'You cannot do this while jumping.'))
    checks.append((unit.is_fallen and unit.unit_type not in (UnitType.MECH, UnitType.MW), "Your vehicle's movement system is destroyed."))
    if flag == S2.EVADING: checks.append((unit.carrying > 0, "You can't do that while towing"))
    checks.append((unit.is_fallen, 'You are currently prone and cannot move.'))
    if flag == S2.SPRINTING:
        checks.append((not historical_aircraft(unit) and entering and in_water(unit) and not water_beast(unit), 'You cannot start sprinting while in water!'))
    if flag == S2.EVADING:
        checks.append((entering and unit.unit_type == UnitType.MECH and any(part_is_nonfunctional(unit, loc, 0) for loc in (Location.LLEG, Location.RLEG)), 'You need both hips functional to evade.'))
    checks.extend([(grounded_watercraft(unit), 'You are regrettably unable to move at this time. We apologize for the inconvenience.'),
                   (pending(unit, '_mode_event'), 'You are already changing movement modes!'),
                   (unit.status2 & (S2.MOVE_MODES ^ flag), 'You cannot perform multiple movement modes!')])
    limping = unit.unit_type == UnitType.MECH and any(unit.is_section_destroyed(loc) for loc in (Location.RLEG, Location.LLEG))
    if flag != S2.DODGING:
        checks.append((swarm_target_id(unit) > 0, f'You cannot {mode} while mounted!'))
        if flag == S2.SPRINTING: checks.append((limping, "That's kind of hard while limping."))
    else:
        actor = unit.pilot if caller is None else caller
        checks.append((not actor_advantage(actor, 'Dodge_Maneuver') or not actor_is_pilot(unit, caller), 'You either are not the pilot of this mech, have no Dodge Maneuver adavantage, or both.'))
    checks.append((not historical_aircraft(unit) and unit.charge_target > 0, 'You are currently charging a target and unable to start sprinting!' if flag == S2.SPRINTING else f'You cannot {mode} while charging!'))
    if flag == S2.EVADING: checks.append((limping, "That's kind of hard while limping."))
    for condition, text in checks:
        if condition: return False, text
    if entering:
        busy = mech_full_no_recycle(unit, 2 if flag == S2.DODGING else 3)
        if busy:
            return False, printf_notice(unit, "You have %s recycling!", "weapons" if busy == 1 else "limbs" if busy == 2 else "error")
    activity = {'sprint': 'sprinting', 'evade': 'evading', 'dodge': 'dodging'}[mode]
    message = notify(unit, ('You begin the process of ' + activity + ('.....' if historical_aircraft(unit) else '...')) if entering else f'You begin the process of ceasing to {mode}.')
    delay = (1 if entering else 30) if flag == S2.DODGING else mode_delay(unit)
    schedule_mode(engine, unit, flag, entering, delay)
    return True, message


def damage_interrupt(unit):
    engine = getattr(unit, '_engine', None)
    if unit.has_status2(S2.SPRINTING):
        unit.clear_status2(S2.SPRINTING)
        from systems.sensors import los_broadcast
        los_broadcast(unit, 'breaks out of its sprint as it takes damage!')
        notify(unit, 'You lose your sprinting momentum as you take damage!')
        if engine is not None and not pending(unit, '_mode_event'):
            schedule_mode(engine, unit, S2.SPRINTING, False, 30)



def _hulldown_complete(event):
    unit = event.data
    if not pending(unit, '_hulldown_event'):
        return
    unit._hulldown_event = None
    if not unit.is_started:
        return
    if event.data2:
        unit.set_status(S.HULLDOWN)
    else:
        unit.clear_status(S.HULLDOWN)
    notify(unit, 'You finish lowering yourself to the ground.' if event.data2 else 'You finish lifting yourself up.')
    from systems.sensors import los_broadcast
    los_broadcast(unit, 'finishes lowering itself to the ground.' if event.data2 else 'finishes lifting itself up')


def hulldown(engine, unit, arg='', caller=None):
    from systems.sensors import los_broadcast
    if unit is not None: unit._engine = engine
    error = guard(unit, caller, True)
    if error: return False, error
    for condition, text in (
        (not historical_aircraft(unit) and unit.has_status2(S2.FORTIFIED), 'Your fortified state prevents you from moving.'),
        (unit.cocoon, 'While falling out of the sky?'),
        (unit.move_type != MoveType.QUAD, 'Only QUADs can hulldown.'),
        (unit.is_fallen, "You can't hulldown from a FALLEN position"),
        (unit.is_jumping, "You can't hulldown while jumping!"),
        (unit.speed > .5, "You can't hulldown while moving!"),
        (pending(unit, '_stabil_event'), 'You are still stabilizing from your last jump.'),
        (pending(unit, '_stand_event'), "You haven't finished standing up yet.")):
        if condition: return False, text
    args = attributes(arg, 1)
    if args:
        if args[0] == '-':
            if not unit.has_status(S.HULLDOWN): return False, notify(unit, 'You are not hulldown.')
            if pending(unit, '_hulldown_event'): return False, notify(unit, 'You are busy changing your hulldown mode.')
            message = notify(unit, 'You start to lift yourself up.')
            los_broadcast(unit, 'begins to raise up on its legs.')
            lowering = False
        elif args[0].lower() == 'stop':
            if not pending(unit, '_hulldown_event'): return False, notify(unit, 'You are not currently changing your hulldown mode.')
            engine.cancel_events_of_type(EventType.HULLDOWN, unit)
            unit._hulldown_event = None
            return True, notify(unit, 'You stop changing your hulldown mode.')
        else: return False, notify(unit, "Invalid argument for 'hulldown'.")
    else:
        if unit.has_status(S.HULLDOWN): return False, 'You are already hulldown.'
        if pending(unit, '_hulldown_event'): return False, 'You are busy changing your hulldown mode.'
        message = notify(unit, 'You start to lower yourself to the ground.')
        los_broadcast(unit, 'begins to lower itself to the ground.')
        unit.desired_speed = 0
        lowering = True
    unit._hulldown_event = engine.schedule_event(stand_time(unit), EventType.HULLDOWN, _hulldown_complete, data=unit, data2=lowering)
    return True, message


def prone(engine, unit, caller=None):
    from systems.piloting import make_piloting_roll
    from physics.jump import mech_falls, make_mech_fall
    from physics.flooding import flood_unit, extinguish_in_water
    from systems.sensors import los_broadcast
    from systems.swarm import swarmers, detach_all
    if unit is not None: unit._engine = engine
    error = guard(unit, caller)
    if error: return False, error
    for condition, text in (
        (unit.unit_type == UnitType.BSUIT, 'No crawling!'),
        (unit.unit_type not in (UnitType.MECH, UnitType.MW), "You can't prone in this!"),
        (unit.is_fallen, 'You are already prone.'),
        (unit.is_jumping or unit.cocoon, "You can't prone in the air!"),
        (pending(unit, '_stand_event'), "You can't drop while trying to stand up!")):
        if condition: return False, text
    threshold = float32(cargo_max_speed(unit) / 3)
    levels = modifier = 0
    swarmed = unit.unit_type == UnitType.MECH and bool(swarmers(unit))
    if unit.unit_type != UnitType.MW and abs(unit.speed) > threshold * 2:
        notify(unit, 'You attempt a controlled drop while running.')
        levels = modifier = 2
    elif abs(unit.speed) > threshold:
        notify(unit, 'You attempt a controlled drop from your fast walk.')
        levels = 1
    stagger = int(unit.stagger_damage / 20)
    if stagger > 0:
        notify(unit, 'Still staggering, you try not to fall on your face.')
        levels, modifier = max(1, levels), modifier + stagger
    if swarmed: notify(unit, 'The suits hanging off you make a controlled drop harder!')
    if levels or swarmed:
        if make_piloting_roll(unit, modifier).success:
            message = notify(unit, 'You hit the ground with minimal damage')
            los_broadcast(unit, 'drops to the ground!')
            if swarmed: detach_all(unit)
        else:
            message = notify(unit, 'You fall to the ground hard')
            los_broadcast(unit, 'falls hard to the ground!')
            if swarmed: detach_all(unit)
            mech_falls(unit, max(1, levels), notify_fall=True)
    else:
        message = notify(unit, 'You drop to the ground prone!')
        los_broadcast(unit, 'drops to the ground!')
    make_mech_fall(unit)
    unit.speed = unit.desired_speed = 0
    flood_unit(unit)
    extinguish_in_water(unit)
    if getattr(engine, 'new_stagger', 1):
        from systems.stagger import clear_all
        clear_all(unit)
    from systems.mines import possible_mine_poof
    possible_mine_poof(unit, 'step')
    return True, message


def stand(engine, unit, argument='', caller=None):
    """Pilot-facing stand command; stand_up remains an internal callable."""
    from physics.jump import stand_up
    if unit is not None: unit._engine = engine
    error = guard(unit, caller)
    if error:
        return False, error
    unit._engine = engine
    return stand_up(unit, engine.events, argument)


def bootlegger(engine, unit, argument, caller=None):
    from systems.piloting import make_piloting_roll
    from systems.physical import set_recycle_limb, sect_has_busy_weap
    from systems.parts import count_destroyed_legs, armor_string
    from physics.hexmath import acceptable_degree
    from physics.jump import mech_falls
    from systems.sensors import los_broadcast
    from systems.notifications import mech_printf
    from core.effects import send_debug
    if unit is not None: unit._engine = engine
    error = guard(unit, caller, True)
    if error: return False, error
    args = attributes(argument, 1)
    if not args: return False, 'Invalid number of arguments!'
    if count_destroyed_legs(unit): return False, "You can't perform a bootlegger with destroyed legs!"
    if unit.speed < 4 * MP1: return False, f'You are going too slow to perform a bootlegger! The required minimum speed is {4 * MP1:4.1f} KPH.'
    direction = args[0][0].upper()
    if direction not in ('L', 'R'): return False, 'Invalid turn direction!'
    participating = sorted(legs(unit))
    modifier = 0
    for loc in participating:
        name = armor_string(unit, loc)
        message = ('You have weapons recycling in your %s.' if sect_has_busy_weap(unit, loc) else
                   'Your %s is still recovering from its last action.' if unit.sections[loc].recycle else None)
        if message:
            mech_printf(unit, 2, message, name)
            return False, message % name
        modifier += unit.sections[loc].basetohit
    modifier += sum(unit.speed > band * MP1 for band in (4, 8, 12))
    modifier += sum(unit.tonnage > band for band in (35, 55, 75))
    modifier = max(1, modifier + (2 if in_water(unit) else 0))
    unit.last_piloting_modifier = modifier
    send_debug(unit, f'#{unit._id} attempts to do a bootlegger (mech). Tonnage: {unit.tonnage}, Speed: {unit.speed:4.1f}, BTHMod: {modifier}')
    if make_piloting_roll(unit, modifier).success:
        unit.facing = unit.desired_facing = acceptable_degree(unit.facing + (90 if direction == 'R' else -90))
        unit.speed = float32(unit.speed / 2)
        message = f'You plant a foot and swivel, changing your heading to {unit.facing}.'
        mech_printf(unit, 2, '%s', message)
        for loc in participating: set_recycle_limb(unit, loc, 30)
    else:
        notify(unit, 'You plant a foot and try to swivel...')
        message = notify(unit, '... but realize a little late that this is harder than it looks!')
        los_broadcast(unit, 'attempts to fight the forces of inertia but looses the battle miserably!')
        if modifier > 2: los_broadcast(unit, 'tumbles over and over and over!')
        mech_falls(unit, modifier, notify_fall=True)
    return True, message


def thrash(engine, unit, caller=None):
    from entities.map import GRASSLAND, ROAD
    from systems.targeting import fa_mech_range
    from systems.combat import apply_damage_with_transfer
    from systems.physical import set_recycle_limb, sect_has_busy_weap
    from systems.piloting import make_piloting_roll
    from physics.jump import mech_falls
    from systems.parts import armor_string
    from systems.notifications import identity, mech_printf
    from systems.sensors import los_broadcast
    from core.randomness import number
    if unit is not None: unit._engine = engine
    error = guard(unit, caller, True)
    if error: return False, error
    if not unit.is_fallen: return False, 'You need to be prone to thrash!'
    if unit.map is None: return False, 'Invalid map! Contact a wizard!'
    if unit.map.rterrain(unit.x, unit.y) not in (GRASSLAND, ROAD, BRIDGE):
        return False, 'Thrashing only works in clear terrain or on roads or bridges.'
    limbs = []
    for loc in (Location.RARM, Location.LARM, Location.LLEG, Location.RLEG):
        if unit.is_section_destroyed(loc): continue
        limbs.append(loc)
        name = armor_string(unit, loc)
        if sect_has_busy_weap(unit, loc): return False, f'You have weapons recycling on your {name}.'
        if unit.sections[loc].recycle: return False, f'Your {name} is still recovering from your last attack.'
    if not limbs: return False, notify(unit, "You can't thrash if you have no limbs!")
    message = notify(unit, 'You start to flail your arms and legs like a wild man!')
    los_broadcast(unit, 'starts to flail its arms and legs like a wild beast!')
    for target in list(unit.map.mechs_on_map):
        if target is None or target.unit_type != UnitType.BSUIT or target.team == unit.team or target.is_jumping or target.cocoon:
            continue
        if fa_mech_range(unit, target) > 1: continue
        mech_printf(unit, 2, 'You manage to hit %s!', identity(unit, target))
        mech_printf(target, 2, "You get hit by %s's thrashing limbs!", identity(target, unit))
        remaining = int(unit.tonnage / 3)
        while remaining > 0:
            cluster = min(5, remaining)
            apply_damage_with_transfer(target, draw('suit_members', 0, 7, lambda: number(0, 7)), cluster, attacker=unit, engine=engine,
                                       ignore_swarmers=True, los=1, attack_pilot=unit.pilot)
            remaining -= cluster
    if not make_piloting_roll(unit, 0, succeed_when_fallen=False).success:
        mech_falls(unit, 1)
    for loc in limbs:
        if not unit.is_section_destroyed(loc): set_recycle_limb(unit, loc, 60)
    return True, message


def heading(engine, unit, arg=None, caller=None):
    from physics.hexmath import acceptable_degree
    from physics.heights import AERO_TYPES
    if unit is not None: unit._engine = engine
    error = guard(unit, caller)
    if error: return False, error
    args = attributes(arg, 1)
    if not args: return True, caller_notice(unit, caller, f'Your current heading is {unit.facing}.')
    for condition, text in (
        (unit.move_type == MoveType.NONE, 'This piece of equipment is stationary!'),
        (not historical_aircraft(unit) and unit.has_status2(S2.FORTIFIED), 'Your fortified state prevents you from moving.'),
        (grounded_watercraft(unit), 'You are regrettably unable to move at this time. We apologize for the inconvenience.'),
        (unit.unit_type in AERO_TYPES and unit.has_crit_status(CritStatus.SPINNING) and not unit.has_status(S.LANDED), 'You are unable to control your craft at the moment.'),
        (unit.has_status(S.PERFORMING_ACTION), 'You are too busy at the moment to turn.'),
        (unit.dug_in or getattr(unit, 'tank_crit_status', 0) & 4, 'You are in a hole you dug, unable to move [use speed cmd to get out].'),
        (unit.has_status(S.HULLDOWN), 'You can not turn while hulldown'),
        (pending(unit, '_hulldown_event'), 'You are busy changing your hulldown mode')):
        if condition: return False, text
    if unit.digging or getattr(unit, 'tank_crit_status', 0) & 8:
        notify(unit, 'You cease your attempts at digging in.')
        from systems.combat_equipment import stop_digging
        stop_digging(unit)
    unit.desired_facing = acceptable_degree(c_number(args[0], True))
    message = printf_notice(unit, 'Heading changed to %d.', unit.desired_facing)
    maybe_move(engine, unit)
    return True, message


def speed(engine, unit, arg=None, caller=None):
    from physics.heights import aero_free_fuel
    from physics.aerospace import flying
    from physics.collision import mech_rterrain
    from systems.heat import is_running
    if unit is not None: unit._engine = engine
    error = guard(unit, caller)
    if error: return False, error
    if not historical_aircraft(unit) and unit.has_status2(S2.FORTIFIED): return False, 'Your fortified state prevents you from moving.'
    rolling = unit.unit_type in (UnitType.AERO, UnitType.DS)
    if rolling:
        if not unit.has_status(S.LANDED): return False, 'Use thrust command instead!'
    elif flying(unit) and unit.unit_type != UnitType.VTOL: return False, 'Use thrust command instead!'
    for condition, text in (
        (unit.move_type == MoveType.NONE, 'This piece of equipment is stationary!'),
        (unit.has_status(S.PERFORMING_ACTION), 'You are too busy at the moment to turn.'),
        (pending(unit, '_stand_event'), 'You are currently standing up and cannot move.'),
        (unit.is_fallen and unit.unit_type not in (UnitType.MECH, UnitType.MW), "Your vehicle's movement system is destroyed."),
        (unit.is_fallen, 'You are currently prone and cannot move.'),
        (grounded_watercraft(unit), 'You are regrettably unable to move at this time. We apologize for the inconvenience.'),
        (unit.unit_type != UnitType.MECH and removing_pods(unit), 'You are too busy removing iNARC pods!')):
        if condition: return False, text
    error = posture_guard(unit)
    if error: return False, error
    args = attributes(arg, 1)
    if not args: return True, caller_notice(unit, caller, f'Your current speed is {unit.speed:.2f}.')
    if flying(unit) and unit.fuel <= 0 and not aero_free_fuel(unit): return False, "You're out of fuel!"
    maximum = float32(cargo_max_speed(unit))
    if unit.move_type == MoveType.VTOL:
        square = float32(float32(maximum * maximum) - float32(unit.vertical_speed * unit.vertical_speed))
        maximum = float32(math.sqrt(square)) if square >= 0 else float('nan')
    maximum = maximum if maximum > 0 else 0.0
    if historical_aircraft(unit) and unit.heat >= 9 and unit.specials & Specials.TRIPLE_MYOMER_TECH:
        maximum = float32(math.ceil((round(maximum / 1.5 / MP1) + 1) * 1.5) * MP1)
    walk = float32(float32(2.0 * maximum) / 3.0)
    value = float32(c_number(args[0]))
    if value < .1:
        value = {'walk': walk, 'cruise': walk, 'run': maximum, 'flank': maximum, 'back': -walk, 'stop': 0}.get(args[0].lower(), value)
    value = min(maximum, max(-walk, value))
    if value < 0 and unit.carrying > 0 and not unit.specials & Specials.SALVAGE_TECH: return False, 'You can not backup while towing!'
    if value < 0 and unit.has_status2(S2.SPRINTING): return False, 'You can not backup while sprinting!'
    if is_running(value, maximum):
        if unit.dumping: return False, 'You can not run while dumping ammo!'
        if unit.unjamming: return False, 'You can not run while unjamming your weapon!'
        if unit.has_crit_status(CritStatus.MECH_STUNNED):
            from systems.combat_commands import NotifiedError
            return False, NotifiedError(notify(unit, 'You cannot move faster than cruise speed while stunned!'))
        if unit.crew_stunned or engine.has_event(EventType.UNSTUN_CREW, unit):
            return False, 'Your cannot possibly control a vehicle going this fast in your current mental state!'
        if getattr(unit, 'tank_crit_status', 0) & 0x20:
            return False, 'Your cannot possibly control a VTOL going this fast with a destroyed tail rotor!'
        if unit.unit_type == UnitType.MECH and (in_water(unit) or mech_rterrain(unit) == HIGHWATER): return False, "You can't run through water!"
    if not wizard_actor(caller) and unit.in_character and not actor_is_pilot(unit, caller):
        if value < 0: return False, 'Not being the Pilot of this beast, you cannot move it backwards.'
        if value > walk: return False, 'Not being the Pilot of this beast, you cannot go faster than walking speed.'
    unit.desired_speed = value
    maybe_move(engine, unit)
    if abs(value) > .1:
        if swarm_target_id(unit) > 0:
            from systems.swarm import detach
            detach(unit, intentional=True)
            unit.clear_crit_status(CritStatus.HIDDEN)
        if unit.digging or getattr(unit, 'tank_crit_status', 0) & 8:
            notify(unit, 'You cease your attempts at digging in.')
            from systems.combat_equipment import stop_digging
            stop_digging(unit)
        unit.dug_in = False
        unit.tank_crit_status = getattr(unit, 'tank_crit_status', 0) & ~0x04
    return True, printf_notice(unit, 'Desired speed changed to %d KPH' + ('' if historical_aircraft(unit) else '.'), int(value))


def vertical(engine, unit, arg=None, caller=None):
    from physics.heights import aero_free_fuel
    if unit is not None: unit._engine = engine
    error = guard(unit, caller)
    if error: return False, error
    if unit.unit_type != UnitType.VTOL and unit.move_type != MoveType.SUB: return False, 'This command is for VTOLs only.'
    if unit.unit_type == UnitType.VTOL and unit.fuel <= 0 and not aero_free_fuel(unit): return False, "You're out of fuel!"
    if grounded_watercraft(unit): return False, 'You are regrettably unable to move at this time. We apologize for the inconvenience.'
    args = attributes(arg, 1)
    if not args: return False, caller_notice(unit, caller, f'Current vertical speed is {unit.vertical_speed:.2f} KPH.')
    value = float32(c_number(args[0]))
    maximum = float32(cargo_max_speed(unit))
    square = float32(float32(maximum * maximum) - float32(unit.desired_speed * unit.desired_speed))
    maximum = float32(math.sqrt(square)) if square >= 0 else float('nan')
    if value > maximum or value < -maximum:
        return False, f'Max vertical speed is + {int(maximum)} KPH and - {int(maximum)} KPH'
    if unit.is_fallen: return False, "Your vehicle's movement system is destroyed."
    if unit.unit_type == UnitType.VTOL and unit.has_status(S.LANDED): return False, 'You need to take off first.'
    unit.vertical_speed = value
    message = printf_notice(unit, 'Vertical speed changed to %d KPH', int(value))
    maybe_move(engine, unit)
    return True, message


def eta(engine, unit, argument='', caller=None):
    from physics.hexmath import hex_to_float, find_range
    if unit is not None: unit._engine = engine
    error = guard(unit, caller)
    if error:
        return False, error
    args = attributes(argument, 2)
    if not args:
        if unit.targ_x < 0 or unit.target >= 0:
            return False, 'You have invalid default target for ETA!'
        x, y = unit.targ_x, unit.targ_y
    elif len(args) == 2:
        x, y = (c_number(arg, True) for arg in args)
    else:
        return False, 'Invalid number of arguments!'
    fx, fy = hex_to_float(x, y)
    distance = find_range(unit.fx, unit.fy, fx, fy)
    if abs(unit.speed) < .1:
        display = 'Never, mech not moving.'
    else:
        minutes = int(abs(distance / (unit.speed / MP1)))
        display = f'{minutes // 60:02d}:{minutes % 60:02d}.'
    return True, printf_notice(unit, 'Range to hex (%d,%d) is %.1f.  ETA: %s', x, y, distance, display)


def land(engine, unit, caller=None):
    from physics.aerospace import land as aero_land
    from systems.piloting import make_piloting_roll
    from physics.jump import land_mech, mech_falls
    from systems.sensors import los_broadcast
    if unit is not None: unit._engine = engine
    error = guard(unit, caller)
    if error: return False, error
    if unit.unit_type not in (UnitType.MECH, UnitType.MW, UnitType.BSUIT, UnitType.VEH_GROUND):
        return aero_land(engine, unit, caller)
    if not unit.is_jumping: return False, "You're not jumping!"
    notify(unit, 'You abort your full jump and attempt to land early')
    if make_piloting_roll(unit, 0).success:
        message = notify(unit, 'You are able to abort the jump.')
        land_mech(unit, event_queue=engine.events if engine else None)
    else:
        message = notify(unit, "You don't quite make it.")
        los_broadcast(unit, 'attempts a landing, but crashes to the ground!')
        mech_falls(unit, 1, notify_fall=False)
        unit.dfa_target = -1
        unit.going_x = unit.going_y = 0
        unit.speed = 0
        if engine is not None: maybe_move(engine, unit)
    return True, message


def jump_command(engine, unit, argument, caller=None):
    """Source bearing/range or DFA command through the shared launch owner."""
    from physics.jump import jump_eligibility, jump_preparation, begin_jump
    from physics.hexmath import find_xy, float_to_hex
    from systems.targeting import contact_target, resolve_unit, fa_mech_range
    from systems.los import in_line_of_sight
    if unit is not None: unit._engine = engine
    error = guard(unit, caller, True)
    if error: return False, error
    error = jump_eligibility(unit)
    if error: return False, error
    args = attributes(argument, 3)
    error = jump_preparation(unit)
    if error: return False, error
    if len(args) > 2: return False, 'Too many arguments to JUMP function!'
    unit.clear_status(S.DFA_ATTACK)
    target = None
    if len(args) < 2:
        if unit.unit_type != UnitType.MECH: return False, 'Only mechs can do Death From Above attacks!'
        target = contact_target(unit, args[0]) if args else resolve_unit(unit, unit.target)
        if target is None: return False, 'Target is not in line of sight!' if args else 'Invalid Target!'
        distance = fa_mech_range(unit, target)
        if not in_line_of_sight(unit, target, target.x, target.y, distance): return False, 'Target is not in line of sight!'
        if target.unit_type == UnitType.MW: return False, "Even you can't aim your jump well enough to squish that!"
        x, y = target.x, target.y
        unit.dfa_target = target._id if args else unit.target
    else:
        distance = float32(c_number(args[1]))
        x, y = float_to_hex(*find_xy(unit.fx, unit.fy, c_number(args[0], True), distance))
    result = begin_jump(unit, x, y, distance, engine.events, dfa=target is not None)
    return result.success, result.message
