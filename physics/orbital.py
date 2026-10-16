# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.ood.c

"""Orbital drop, cocoon interception and accelerating free-fall events."""
from core.randomness import roll as source_roll
from core.randomness import draw, float32
from core.events import EventType
from entities.mech import UnitType, MoveType, MechStatus as S, MechStatus2 as S2
from entities.map import GRASSLAND, ROAD, WATER, HIGHWATER, BRIDGE
from physics.hexmath import ZSCALE
from physics.collision import mech_elevation, mech_upper_elevation, bridge_w_elevation, mech_rterrain
from systems.movement_commands import notify, maybe_move
from systems.movement_commands import in_water, grounded_watercraft, printf_notice


def height_above_ground(unit):
    upper = mech_upper_elevation(unit)
    if upper <= unit.z:
        ground = upper
    elif mech_rterrain(unit) == BRIDGE:
        ground = bridge_w_elevation(unit)
    else:
        ground = mech_elevation(unit)
    return unit.z - ground


def initiate_ood(engine, unit, argument, *, actor=None):
    from systems.map_management import arguments, readnum
    from systems.map_transitions import set_xy, flying_type
    from core.effects import notify_actor
    actor = actor if actor is not None else getattr(unit, 'command_actor', None) or unit.pilot or 1
    unit._engine = engine
    def reply(ok, message):
        notify_actor(unit, actor, message)
        return ok, message
    args = arguments(str(argument), 3)
    if len(args) < 2:
        return reply(False, 'Invalid attributes!')
    coordinates = []
    for label, value in zip(('x', 'y', 'z'), args):
        try: coordinates.append(readnum(value))
        except ValueError: return reply(False, f'Invalid number! ({label})')
    x, y = coordinates[:2]
    z = coordinates[2] if len(coordinates) == 3 else 300
    if unit.cocoon:
        return reply(False, 'OOD already in progress!')
    set_xy(unit, x, y, actor=1)
    if (unit.x, unit.y) != (x, y):
        return reply(False, 'Invalid co-ordinates!')
    if unit.is_fallen:
        return reply(False, "You'll have to get up first.")
    if unit.digging:
        return reply(False, "You're too busy digging in.")
    unit.z, unit.fz = z, z * ZSCALE
    from systems.ecm import mark_for_los_update
    mark_for_los_update(unit)
    notify_actor(unit, actor, 'OOD initiated.')
    aerospace = unit.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)
    if not aerospace:  # Recovered Aerospace predates these mode mutations.
        unit.clear_status2(S2.EVADING | S2.SPRINTING)
    if flying_type(unit):
        unit.clear_status(S.LANDED)
        unit.desired_speed = unit.max_speed / 2
        if aerospace: unit.desired_angle = 0
        maybe_move(engine, unit)
    else:
        from systems.construction_weight import get_weight
        # Explicit measured fixture mass enters the same source weight cache.
        supplied = getattr(unit, 'measured_mass', None)
        compute = (lambda: supplied) if supplied is not None and not getattr(unit, 'construction_managed', False) else None
        mass = get_weight(unit, compute=compute)
        unit.cocoon = mass // 5 // 1024 + 1
        engine.cancel_events_of_type(EventType.MOVE, unit)
        engine.schedule_event(1, EventType.OOD, ood_event, data=unit)
    return True, 'OOD initiated.'


def _touchdown_target(unit):
    from systems.piloting import find_pilot_piloting, find_spilot_piloting
    target = (find_pilot_piloting(unit) - 1 if unit.unit_type in (UnitType.MW, UnitType.BSUIT)
              else find_spilot_piloting(unit) + getattr(unit, 'pilot_skill_base', 0))
    if not unit.is_started:
        target += 10
    if unit.cocoon < 0:
        target += 4
    elif unit.cocoon == 0:
        target += 10
    terrain = mech_rterrain(unit)
    if terrain not in (GRASSLAND, ROAD):
        target += 2 if terrain in (WATER, HIGHWATER) else 3
    return target


def _touchdown_margin(unit):
    from systems.combat import roll_2d6
    margin = -10 if unit.is_fallen else 0
    if unit.is_unconscious or not unit.is_started or unit.has_status(S.BLINDED):
        margin = -20
    roll = source_roll('pilot_rolls', roll_2d6)
    target = _touchdown_target(unit)
    unit._ood_parachute = unit.cocoon == 1
    unit.cocoon = 0
    if unit.in_character and (unit.pilot is None or (isinstance(unit.pilot, int) and unit.pilot < 0)
                              or getattr(unit.pilot, 'location', unit._id) != unit._id):
        target += 99
    notify(unit, 'You make a piloting skill roll!', 0)
    notify(unit, f'Modified Pilot Skill: BTH {target}\tRoll: {roll}', 0)
    unit.last_ood_target = target
    margin += roll - target
    if roll >= target and target > 2:
        amount = min(20, max(1, (abs(margin) + 1) * 2))
        unit.orbital_pilot_xp = getattr(unit, 'orbital_pilot_xp', 0) + amount
        from systems.experience import piloting
        piloting(unit.pilot, unit, amount, True)
    # C applies the roll margin twice, awarding XP between the additions.
    return margin + roll - target


def _crash_battlesuit(unit, margin):
    import random
    from systems.combat import apply_damage_with_transfer
    from physics.flooding import flood_unit
    from physics.jump import mech_falls
    for loc, section in enumerate(unit.sections):
        if section.internal_orig > 0:
            damage = sum(draw('suit_d4', 1, 4, lambda: random.randint(1, 4)) for _ in range(abs(margin)))
            apply_damage_with_transfer(unit, loc, damage, attacker=unit, engine=unit._engine,
                                       transfer=True, _entry_processed=True, attack_pilot=-1, los=0)
            flood_unit(unit)
    mech_falls(unit, 0)


def _resolve_touchdown(unit):
    from physics.jump import mech_falls
    from systems.sensors import los_broadcast
    margin = _touchdown_margin(unit)
    parachute = unit._ood_parachute
    if margin >= 0:
        los_broadcast(unit, 'touches down and rolls on the ground!' if parachute else 'touches down!')
    elif unit.unit_type == UnitType.MECH:
        notify(unit, 'You are unable to control your momentum and fall on your face!')
        los_broadcast(unit, 'touches down on the ground, twists, and falls down!')
        mech_falls(unit, abs(margin) * (1 if parachute else 2))
    elif unit.unit_type == UnitType.BSUIT:
        notify(unit, 'You are unable to control your momentum and crash!')
        los_broadcast(unit, 'crashes to the ground!')
        _crash_battlesuit(unit, margin)
    else:
        notify(unit, 'You are unable to control your momentum and crash!')
        los_broadcast(unit, 'crashes at the ground!')
        mech_falls(unit, abs(margin) * (1 if parachute else 3))


def _settle_touchdown(unit):
    from physics.movement import drop_set_elevation
    from physics.collision import domino_space
    from systems.damage import destroy_mech, KILL_TYPE_FLOOD
    drop_set_elevation(unit, 1)
    if not unit.is_fallen:
        domino_space(unit, 2)
    if grounded_watercraft(unit):
        unit.desired_speed = 0
    maybe_move(unit._engine, unit)
    if (in_water(unit) and unit.unit_type in (UnitType.VEH_GROUND, UnitType.VTOL,
            UnitType.BSUIT, UnitType.AERO, UnitType.DS) and not unit.specials2 & 0x100000):
        from systems.sensors import los_broadcast
        notify(unit, 'Water floods your engine and your unit becomes unoperable.')
        los_broadcast(unit, 'emits some bubbles and flails their arms around as they sink to the bottom!' if unit.unit_type == UnitType.BSUIT else 'emits some bubbles as its engines are flooded.')
        destroy_mech(unit, unit, showboom=False, reason=KILL_TYPE_FLOOD)


def ood_event(event):
    from systems.ecm import mark_for_los_update
    from physics.movement import drop_get_elevation, drop_set_elevation
    unit = event.data
    engine = unit._engine
    if not unit.cocoon:
        return
    mark_for_los_update(unit)
    if height_above_ground(unit) - drop_get_elevation(unit) > 2:
        unit.z -= 2
        unit.fz = float32(unit.z * ZSCALE)
        engine.schedule_event(1, EventType.OOD, ood_event, data=unit)
        return
    notify(unit, 'Your unit touches down!')
    from core.effects import did_it
    from systems.movement_commands import historical_aircraft
    if not historical_aircraft(unit): did_it(unit, unit, unit, awhat='A_AOODLAND')
    if unit.has_status(S.COMBAT_SAFE):
        unit.cocoon = 0
        from systems.sensors import los_broadcast
        los_broadcast(unit, 'touches down safely!')
        drop_set_elevation(unit, 1)
        maybe_move(engine, unit)
        return
    _resolve_touchdown(unit)
    _settle_touchdown(unit)


def cocoon_damage(unit, attacker, damage):
    engine = unit._engine
    printf_notice(attacker, '%%cgYou hit the cocoon for %d points of damage!%%cn', damage)
    printf_notice(unit, '%%ch%%cyYour cocoon has been hit for %d points of damage!%%cn', damage)
    unit.cocoon = max(0, unit.cocoon - damage)
    if unit.cocoon or unit.z <= mech_elevation(unit):
        return
    if unit.jump_speed >= 10.75:
        notify(unit, 'You initiate your jumpjets to compensate for the breached cocoon!')
        unit.cocoon = -1
        return
    if engine is None:
        raise ValueError('Orbital damage requires the owning event engine')
    notify(unit, 'Your cocoon has been destroyed - have a nice fall!')
    from systems.sensors import los_broadcast
    los_broadcast(unit, 'starts plummeting down, as the final blast blows the cocoon apart!')
    engine.cancel_events_of_type(EventType.OOD, unit)
    engine.schedule_event(3, EventType.FALL, fall_event, data=unit, data2=-1)


def fall_event(event):
    from physics.jump import mech_falls
    from systems.ecm import mark_for_los_update
    unit, speed = event.data, event.data2
    if unit.is_started and speed >= 0:
        return
    from physics.heights import AERO_TYPES, aero_free_fuel
    powerless = (not unit.is_started or not (unit.unit_type in AERO_TYPES or unit.move_type == MoveType.VTOL)
                 or (unit.fuel <= 0 and not aero_free_fuel(unit))
                 or (unit.unit_type == UnitType.VTOL and unit.is_section_destroyed(5)))
    speed += -1 if speed <= 0 and powerless else 1
    mark_for_los_update(unit)
    if height_above_ground(unit) > abs(speed):
        unit.z -= abs(speed)
        unit.fz = float32(unit.z * ZSCALE)
        unit._engine.schedule_event(3, EventType.FALL, fall_event, data=unit, data2=speed)
    else:
        from systems.sensors import los_broadcast
        notify(unit, 'You hit the ground!')
        los_broadcast(unit, 'hits the ground!')
        mech_falls(unit, abs(speed) * (abs(speed) + 1) // 2, notify_fall=False)
        unit.clear_status(S.JUMPING)
