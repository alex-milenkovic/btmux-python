# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.move.c
#   btech/mech.update.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h

"""
Maneuver commands for BTMux Python reimplementation.

This module handles the maneuvering commands and state:
- Torso twist (rotate_torso)
- Vehicle turret control (set_turret) and autoturn snap
- Lateral movement mode (set_lateral + the delayed change event)
- Tight turn mode (set_turnmode)

Reference:
- BTMux btech/src/btech/mech.move.c - mech_rotorso, mech_turret,
  mech_lateral, mech_turnmode
- BTMux btech/src/btech/mech.events.c - the lateral change event
- BTMux btech/src/btech/mech.update.c - autoturn turret snap
- BTMux btech/src/include/btmacros.h - turret facing storage

Command functions follow the repo convention of returning a
``(success, message)`` tuple; event callbacks return their notification
string (the event queue discards it, tests assert it).
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

from entities.mech import MechStatus, MoveType, UnitType, Location, VehicleLocation
from physics.hexmath import normalize_heading, find_bearing, hex_to_float
from core.events import EventType
from core.game_loop import LATERAL_TICK

if TYPE_CHECKING:
    from entities.mech import Mech
    from core.game_loop import GameEngine
    from core.events import Event


def acceptable_degree(degree: float) -> int:
    """AcceptableDegree's signed integer convention, including -360 -> 360."""
    from physics.hexmath import acceptable_degree as source_degree
    return source_degree(int(degree))


def has_maneuvering_ace(mech: Any) -> bool:
    """
    Does the unit's pilot have the Maneuvering Ace advantage?

    C: HasBoolAdvantage(MechPilot(mech), "maneuvering_ace"). Attached
    characters use their durable source record; legacy actors retain flags.
    """
    from systems.characters import actor_advantage
    return actor_advantage(getattr(mech, 'pilot', None), 'Maneuvering_Ace')


# =============================================================================
# Torso twist (mech.move.c:749-796)
# =============================================================================

def rotate_torso(engine, mech, arg, caller=None):
    from systems.movement_commands import guard, attributes, notify, caller_notice
    from systems.ecm import mark_for_los_update
    if mech is not None: mech._engine = engine
    error = guard(mech, caller, True)
    if error: return False, error
    if mech.unit_type == UnitType.BSUIT: return False, 'Huh?'
    if mech.unit_type not in (UnitType.MECH, UnitType.MW): return False, "You don't have a torso."
    if mech.is_fallen: return False, "You're lying flat on your face, you can't rotate your torso."
    if mech.unit_type == UnitType.MECH and mech.move_type == MoveType.QUAD:
        return False, "Quads can't rotate their torsos."
    args = attributes(arg, 2)
    success = False
    if len(args) != 1:
        message = caller_notice(mech, caller, 'Invalid number of arguments!')
    else:
        direction = args[0][0].lower()
        if direction in ('l', 'r'):
            wanted, opposite = ((MechStatus.TORSO_LEFT, MechStatus.TORSO_RIGHT)
                                if direction == 'l' else (MechStatus.TORSO_RIGHT, MechStatus.TORSO_LEFT))
            if mech.has_status(wanted): return False, 'You cannot rotate torso beyond 60 degrees!'
            if mech.has_status(opposite): mech.clear_status(opposite)
            else: mech.set_status(wanted)
            message = notify(mech, 'You rotate your torso %s.' % ('left' if direction == 'l' else 'right'))
            success = True
        elif direction == 'c':
            mech.clear_status(MechStatus.TORSO_LEFT | MechStatus.TORSO_RIGHT)
            message = notify(mech, 'You center your torso.')
            success = True
        else: message = caller_notice(mech, caller, 'Rotate must have LEFT RIGHT or CENTER.')
    mark_for_los_update(mech)
    return success, message


# =============================================================================
# Vehicle turret (mech.move.c:720-747)
# =============================================================================

# Aerospace unit classes the C's turret command refuses alongside
# mechs/MW/bsuits (mech.move.c:727-729).
_AERO_UNIT_TYPES = (UnitType.AERO, UnitType.SPHEROID_DS, UnitType.DS)


def set_turret(engine, unit, bearing=None, caller=None):
    from systems.movement_commands import guard, attributes, c_number, printf_notice, caller_notice
    from systems.ecm import mark_for_los_update
    if unit is not None: unit._engine = engine
    error = guard(unit, caller, True)
    if error: return False, error
    if (unit.unit_type in (UnitType.MECH, UnitType.MW, UnitType.BSUIT) + _AERO_UNIT_TYPES
            or not unit.sections[VehicleLocation.TURRET].internal):
        return False, "You don't have a turret."
    if getattr(unit, 'tank_crit_status', 0) & 2: return False, 'Your turret is jammed in position.'
    if getattr(unit, 'tank_crit_status', 0) & 1: return False, 'Your turret is locked in position.'
    args = attributes(bearing, 1)
    if args:
        unit.turret_facing = acceptable_degree(c_number(args[0], True) - unit.facing)
        message = printf_notice(unit, 'Turret facing changed to %d.', acceptable_degree(unit.turret_facing + unit.facing))
    else:
        message = caller_notice(unit, caller, 'Your turret is currently facing %d.' % acceptable_degree(unit.turret_facing + unit.facing))
    mark_for_los_update(unit)
    return True, message


def update_autoturn_turret(unit: Any, gamemap: Any) -> bool:
    """
    Snap an autoturning turret onto the unit's aim point.

    Port of the AUTOTURN_TURRET turret update (mech.update.c:2932-2965;
    C AUTOTURN_TURRET status2 bit, mech.h:1042).  Runs once per second
    from the movement periodic - no rotation rate, no messages.  Bails
    on: flag off, not started, unconscious pilot, blinded, turret
    jammed/locked, no turret, or no lock.

    Args:
        unit: The vehicle to update
        gamemap: The map the unit is on (used to resolve a locked target)

    Returns:
        True if the turret snapped, False if any gate bailed
    """
    from entities.mech import MechStatus2, VehicleLocation
    if not unit.is_started:
        return False
    if unit.has_status(MechStatus.UNCONSCIOUS):
        return False
    if unit.has_status(MechStatus.BLINDED):
        return False
    if getattr(unit, 'tank_crit_status', 0) & 2:
        return False
    if getattr(unit, 'tank_crit_status', 0) & 1:
        return False
    if not unit.sections[VehicleLocation.TURRET].internal:
        return False

    # Resolve the aim point: locked unit first, else locked hex.
    aim = None
    target_id = getattr(unit, 'target', -1)
    if target_id != -1:
        from systems.targeting import resolve_unit
        other = resolve_unit(unit, target_id)
        if other is not None:
            aim = (other.fx, other.fy)
    if aim is None and target_id == -1:
        targ_x = getattr(unit, 'targ_x', -1)
        targ_y = getattr(unit, 'targ_y', -1)
        if targ_x != -1 and targ_y != -1:
            aim = hex_to_float(targ_x, targ_y)
    if aim is None:
        return False        # no lock

    unit.turret_facing = acceptable_degree(
        find_bearing(unit.fx, unit.fy, aim[0], aim[1]) - unit.facing)
    from systems.ecm import mark_for_los_update
    mark_for_los_update(unit)
    return True


# =============================================================================
# Lateral movement (mech.move.c:39-103 + mech.events.c:298-317)
# =============================================================================

# Source table accepts these nine names, case insensitively.
_LATERAL_ALIASES = {'nw': 300, 'fl': 300, 'ne': 60, 'fr': 60, 'sw': 240, 'rl': 240, 'se': 120, 'rr': 120, '-': 0}

# Canonical display names per offset (lateral_modes[].full,
# mech.move.c:39-55).
LATERAL_NAMES = {
    300: 'Front/Left',
    60: 'Front/Right',
    240: 'Rear/Left',
    120: 'Rear/Right',
    0: 'None',
}


def _parse_lateral_mode(mode_name):
    # skipws consumes only the leading whitespace; strcasecmp uses the remainder.
    return _LATERAL_ALIASES.get(('' if mode_name is None else str(mode_name)).split('\0', 1)[0].lstrip().lower())


def can_move_laterally(mech, caller=None):
    from systems.parts import count_destroyed_legs
    from systems.movement_commands import actor_is_pilot
    from systems.characters import actor_advantage
    if mech.move_type == MoveType.QUAD and count_destroyed_legs(mech) == 0: return True
    if mech.unit_type == UnitType.VTOL or int(mech.unit_type) == int(MoveType.HOVER): return True
    actor = mech.pilot if caller is None else caller
    return actor_is_pilot(mech, caller) and actor_advantage(actor, 'Maneuvering_Ace')


def lateral_event(event: 'Event') -> Optional[str]:
    """
    Delayed lateral mode change completion.

    Port of the lateral change event (mech.events.c:298-317): bails if
    the mech is not started, else applies the wanted offset.

    Event convention: data = the mech, data2 = the target offset.

    Returns:
        The completion message (the event queue discards it; tests
        assert it), or None if the event bailed.
    """
    mech = event.data
    if mech is None: return None
    ofs = event.data2
    mech._lateral_event = None
    if not mech.is_started:
        return None
    from systems.movement_commands import printf_notice
    message = printf_notice(mech, 'Lateral movement mode change to %s (%d offset) completed.', LATERAL_NAMES[ofs], ofs)
    mech.lateral = ofs
    from core.events import EventType
    if mech.move_type != MoveType.QUAD and mech._engine is not None:
        if ofs == 0:
            mech._engine.cancel_events_of_type(EventType.SIDESLIP, mech)
        elif not mech._engine.has_event(EventType.SIDESLIP, mech):
            mech._engine.schedule_event(1, EventType.SIDESLIP, sideslip_event, data=mech)
    return message


def sideslip_event(event):
    from core.events import EventType
    from core.randomness import draw, number
    from systems.piloting import make_piloting_roll
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    unit = event.data
    if unit is None or not unit.is_started:
        return
    notify(unit, 'You make a skill roll while sideslipping!')
    if not make_piloting_roll(unit, -1 if has_maneuvering_ace(unit) else 0).success:
        notify(unit, 'You fail and spin out!')
        los_broadcast(unit, 'spins out while sideslipping!')
        unit.speed = unit.desired_speed = 0
        rotation = draw('sideslip_rotation', 0, 5, lambda: number(0, 5))
        from physics.hexmath import acceptable_degree
        unit.facing = unit.desired_facing = acceptable_degree(unit.facing + rotation * 60)
        unit.lateral = 0
        return
    unit._engine.schedule_event(30, EventType.SIDESLIP, sideslip_event, data=unit)


def set_lateral(engine, mech, mode_name, caller=None):
    from systems.movement_commands import guard, notify, printf_notice
    if mech is not None: mech._engine = engine
    error = guard(mech, caller, True)
    if error: return False, error
    if not can_move_laterally(mech, caller): return False, 'You cannot alter your lateral movement!'
    ofs = _parse_lateral_mode(mode_name)
    if ofs is None: return False, 'Invalid mode!'
    if ofs == mech.lateral:
        if not engine.has_event(EventType.LATERAL, mech): return False, 'You are going that way already!'
        message = notify(mech, 'Lateral mode change aborted.')
        engine.cancel_events_of_type(EventType.LATERAL, mech)
        mech._lateral_event = None
        return True, message
    message = printf_notice(mech, 'Wanted lateral movement mode changed to %s (%d offset).', LATERAL_NAMES[ofs], ofs)
    engine.cancel_events_of_type(EventType.LATERAL, mech)
    mech._lateral_event = engine.schedule_event(LATERAL_TICK, EventType.LATERAL, lateral_event, data=mech, data2=ofs)
    return True, message


# =============================================================================
# Turn mode (mech.move.c:105-131)
# =============================================================================

def set_turnmode(engine, mech, arg=None, caller=None):
    from systems.movement_commands import actor_is_pilot, notify, printf_notice
    pilot = mech.pilot
    # Plain Pilot objects model the attached cockpit actor; explicit dbrefs and
    # locations use the same positive-ID/location checks as GotPilot.
    if (pilot is None or (pilot if isinstance(pilot, int) else getattr(pilot, '_id', 1)) <= 0
            or getattr(pilot, 'location', mech._id) != mech._id or not actor_is_pilot(mech, caller)):
        return False, "You're not the pilot!"
    if not has_maneuvering_ace(mech):
        return False, notify(mech, "You're not skilled enough to do that.", 0)
    value = '' if arg is None else str(arg).split('\0', 1)[0].lower()
    if value == 'tight':
        mech.turn_mode = True
        return True, notify(mech, 'You brace for tighter turns.')
    if value == 'normal':
        mech.turn_mode = False
        return True, notify(mech, 'You assume a normal turn mode.')
    return True, printf_notice(mech, 'Your turning type is : %s', 'TIGHT' if mech.turn_mode else 'NORMAL')
