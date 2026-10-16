# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.move.c
#   btech/mech.startup.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/src/include/btconfig.h

"""Jump trajectories, landing, falls and standing with movement event integration."""

from __future__ import annotations
from core.randomness import draw, float32
from dataclasses import dataclass
import math
import random
from typing import TYPE_CHECKING, Optional, Callable

from physics.hexmath import (
    hex_to_float, float_to_hex, hex_distance, hex_bearing,
    find_components, SCALEMAP, ZSCALE
)

if TYPE_CHECKING:
    from entities.mech import Mech
    from core.events import Event, EventQueue
    from core.game_loop import GameEngine


# =============================================================================
# Jump Constants
# =============================================================================

# Timing
JUMP_TICK = 1                    # Jump updates every 1 second
JUMPSTABIL_TIME = 12             # Seconds of stabilization after landing

# Jump trajectory
JUMP_SPEED_MULT = 10.75          # KPH per jump MP
MOVE_MOD = 0.5                   # Position scale per tick

# Heat
JUMP_HEAT_PER_MP = 1.0           # Heat generated per jump MP used
MIN_JUMP_HEAT = 3.0              # Minimum heat from any jump

# Piloting modifiers
PILOTING_BASE = 0                # Base piloting target for landing
PILOTING_DAMAGED_LEG = 1         # +1 per damaged leg actuator
PILOTING_GYRO_DAMAGED = 3        # +3 for damaged gyro
PILOTING_GYRO_DESTROYED = 6      # +6 for destroyed gyro (auto-fail)

# Fall damage
FALL_DAMAGE_BASE = 1             # Legacy exported constant; fall totals use tonnage
FALL_CLUSTER_SIZE = 5            # Damage applied in 5-point clusters

# Preserve the historical piloting helper and fallback-skill import.
from systems.piloting import DEFAULT_PILOTING, find_spilot_piloting


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class JumpResult:
    """Result of a jump attempt."""
    success: bool = False
    message: str = ""
    distance: int = 0
    heat_generated: float = 0.0


# =============================================================================
# Jump Validation
# =============================================================================

def jump_eligibility(mech):
    """Ordered mech_jump guards after MECH_USUALO, before target parsing."""
    from entities.mech import MechStatus as S, MechStatus2 as S2, UnitType
    from systems.movement_commands import mode_locked, pending, removing_pods, swarm_target_id
    from physics.cargo import cargo_max_speed
    if mech.has_status2(S2.FORTIFIED): return 'Your fortified state prevents you from moving.'
    if mode_locked(mech): return 'Movement modes disallow jumping.'
    if mech.unit_type not in (UnitType.MECH, UnitType.MW, UnitType.BSUIT, UnitType.VEH_GROUND): return 'This unit cannot jump.'
    if mech.carrying > 0: return "You can't jump while towing someone!"
    if float32(mech.max_speed - cargo_max_speed(mech)) > 10.75: return "No, with this cargo you won't!"
    if mech.is_fallen: return "You can't Jump from a FALLEN position"
    if mech.has_status(S.HULLDOWN): return "You can't Jump while hulldown"
    if pending(mech, '_hulldown_event'): return 'You are busy changing your hulldown mode'
    if mech.is_jumping: return "You're already jumping!"
    if pending(mech, '_stabil_event'): return "You haven't stabilized from your last jump yet."
    if pending(mech, '_stand_event'): return "You haven't finished standing up yet."
    if abs(mech.jump_speed) <= 0: return "This mech doesn't have jump jets!"
    if mech.dumping: return 'You can not jump while dumping ammo!'
    if mech.unjamming: return 'You can not jump while unjamming your weapon!'
    if removing_pods(mech): return 'You are too busy removing iNARC pods!'
    if mech.map is not None and mech.map.flags & 16: return 'Realize the ceiling in this grotto is a bit to low for that!'
    if mech.cocoon: return "You can't jump while orbital dropping!"
    if swarm_target_id(mech) > 0: return 'Perhaps you should dismount your ride first!'
    return None


def jump_preparation(mech):
    from systems.movement_commands import notify, printf_notice
    from systems.sensors import los_broadcast
    from systems.piloting import make_piloting_roll
    from systems.stagger import legacy_modifier
    from systems.swarm import jettison_checks
    if int(mech.stagger_damage / 20) > 0:
        notify(mech, 'The damage inhibits your coordination...')
        if not make_piloting_roll(mech, legacy_modifier(mech)).success:
            message = notify(mech, "... something you apparently can't handle!")
            los_broadcast(mech, 'engages jumpjets, rolls to the side and slams into the ground!')
            mech_falls(mech, 1, notify_fall=False)
            return message
    error = jettison_checks(mech)
    if error: return printf_notice(mech, '%s', error)
    return None


def get_jump_mp(mech):
    from physics.collision import jump_speed_mp
    return jump_speed_mp(mech, mech.map)


def _jump_destination_error(mech, target_x, target_y, distance):
    if mech.map is not None and not mech.map.valid(target_x, target_y): return 'That would take you off the map!'
    if (mech.x, mech.y) == (target_x, target_y): return "You're already in the target hex."
    if distance > get_jump_mp(mech): return 'That target is out of range!'
    return None


def can_jump(mech, target_x, target_y):
    """Read-only convenience validation for an explicit destination hex."""
    if not mech.is_started: return False, 'Mech is not started'
    if mech.is_destroyed: return False, 'Mech is destroyed'
    from physics.hexmath import find_range
    fx, fy = hex_to_float(target_x, target_y)
    error = jump_eligibility(mech) or _jump_destination_error(mech, target_x, target_y, find_range(mech.fx, mech.fy, fx, fy))
    return not bool(error), error or ''


def begin_jump(mech, target_x, target_y, distance, event_queue=None, *, dfa=False):
    """Complete source target validation and preserve its partial-write order."""
    from entities.mech import MechStatus as S, UnitType
    from entities.map import ICE
    from core.events import EventType
    from physics.hexmath import find_bearing
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    result = JumpResult()
    distance = float32(distance)
    error = _jump_destination_error(mech, target_x, target_y, distance)
    if error:
        result.message = error
        return result
    target_height = (0 if mech.map.rterrain(target_x, target_y) == ICE else mech.map.base_elevation(target_x, target_y)) if mech.map else mech.z
    jps = get_jump_mp(mech)
    if dfa and mech.unit_type != UnitType.BSUIT: mech.set_status(S.DFA_ATTACK)
    top = min(float32(jps + 1 - float32(distance / 3)), float32(float32(2 * distance) + 2))
    mech.jump_top = (int(top) + 128) % 256 - 128
    error = ("That target's high for you to reach with a single jump!" if target_height - mech.z > jps
             else "That target's low for you to reach with a single jump!" if mech.z - target_height > jps
             else 'Glub glub glub.' if mech.z < -1 else None)
    if error:
        result.message = error
        return result
    fx, fy = hex_to_float(target_x, target_y)
    bearing = find_bearing(mech.fx, mech.fy, fx, fy)
    mech.cocoon = 0
    mech.jump_heading = bearing
    mech.set_status(S.JUMPING)
    mech.start_fx, mech.start_fy, mech.start_fz = mech.fx, mech.fy, mech.fz
    length = int(math.hypot(float32(fx - mech.start_fx), float32(fy - mech.start_fy)))
    mech.jump_length = (length + 32768) % 65536 - 32768
    mech.going_x, mech.going_y = target_x, target_y
    mech.end_fz = float32(ZSCALE * target_height)
    mech.speed = 0
    message = notify(mech, 'You engage your jump jets for a Death From Above attack!' if mech.has_status(S.DFA_ATTACK) else 'You engage your jump jets.')
    mech.swarm_target = -1
    mech.swarming = -1
    los_broadcast(mech, 'engages jumpjets!')
    if event_queue is not None:
        mech._jump_queue = event_queue
        event_queue.schedule(JUMP_TICK, EventType.JUMP, _jump_event_callback, data=mech)
    result.success, result.message = True, message
    result.distance = int(round(distance))
    result.heat_generated = max(MIN_JUMP_HEAT, result.distance * JUMP_HEAT_PER_MP)
    return result


def mech_jump(mech, target_x, target_y, event_queue=None):
    """Explicit-hex API using the same command eligibility and launch owner."""
    from entities.mech import MechStatus as S
    from physics.hexmath import find_range
    if not mech.is_started: return JumpResult(message='Mech is not started')
    if mech.is_destroyed: return JumpResult(message='Mech is destroyed')
    error = jump_eligibility(mech) or jump_preparation(mech)
    if error: return JumpResult(message=error)
    mech.clear_status(S.DFA_ATTACK)
    fx, fy = hex_to_float(target_x, target_y)
    return begin_jump(mech, target_x, target_y, find_range(mech.fx, mech.fy, fx, fy), event_queue)


def _jump_event_callback(event: 'Event') -> None:
    """Source rearm-before-move ordering preserves live queue visibility."""
    from core.events import EventType
    mech = event.data
    queue = mech._engine.events if mech._engine is not None else mech._jump_queue
    queue.schedule(JUMP_TICK, EventType.JUMP, _jump_event_callback, data=mech)
    from physics.movement import move_mech
    move_mech(mech)
    if not mech.is_jumping:
        queue.cancel_by_type_and_data(EventType.JUMP, mech)


# =============================================================================
# Jump Trajectory Update
# =============================================================================

def calculate_jump_altitude(
    progress: float,
    jump_length: float,
    start_fz: float,
    end_fz: float,
    jump_top: int,
) -> float:
    """
    Calculate altitude during jump (parabolic arc).

    Reference: BTMux mech.update.c jump calculations

    The formula creates a parabola:
    fz = (4 * JumpTop / JumpLength^2) * pos * (JumpLength - pos) + base_elevation

    Args:
        progress: Current position along jump path (0 to jump_length)
        jump_length: Total jump distance in position units
        start_fz: Starting elevation
        end_fz: Ending elevation
        jump_top: Maximum height in ZSCALE units

    Returns:
        Current fz (elevation in position units)
    """
    if jump_length <= 0:
        return start_fz

    # Calculate base elevation (linear interpolation between start and end)
    fraction = progress / jump_length
    base_elev = start_fz + (end_fz - start_fz) * fraction

    # Calculate parabolic arc height
    # Peak at progress = jump_length / 2
    arc_height = (4.0 * jump_top / (jump_length * jump_length)) * progress * (jump_length - progress)

    return base_elev + arc_height


def calculate_odd_jump_altitude(progress, length, start, end, top, capability):
    """ODDJUMP trajectory enabled in the supplied include/btconfig.h."""
    if length <= 0:
        return start
    position = progress / length
    centered = (position - .5) * 2
    power = 2 if top / ZSCALE >= 1 + capability else 4
    return (max(0, length - progress) * start + progress * end) / length + (1 - centered ** power) * top


def update_jump(mech, event=None):
    if not mech.is_jumping:
        return False
    from physics.movement import move_mech
    move_mech(mech)
    return mech.is_jumping


def update_jump_periodic(mech: 'Mech') -> bool:
    """
    Update jump for periodic system (no event).

    This is called from the game loop's movement periodic.

    Returns:
        True if still jumping, False if landed
    """
    return update_jump(mech, None)


# =============================================================================
# Landing
# =============================================================================

def land_mech(mech, event=None, event_queue=None):
    from entities.mech import MechStatus as S, CritStatus, Location as L, UnitType
    from core.events import EventType
    from systems.piloting import make_piloting_roll
    from systems.movement_commands import notify, maybe_move
    from systems.sensors import los_broadcast
    from systems.parts import count_destroyed_legs
    from physics.movement import drop_set_elevation
    from physics.flooding import flood_unit, extinguish_in_water
    from physics.collision import domino_space
    from systems.swarm import swarmers, detach_all
    queue = event_queue or (mech._engine.events if mech._engine is not None else getattr(mech, '_jump_queue', None))
    dfa = done = False
    if mech.is_unconscious:
        notify(mech, 'Your lack of conciousness makes you fall to the ground. Not like you can read this anyway.')
        mech_falls(mech, 1, notify_fall=False)
        dfa = done = True
    else:
        if mech.has_status(S.DFA_ATTACK):
            from systems.targeting import resolve_unit
            target = resolve_unit(mech, mech.dfa_target)
            if target is None:
                notify(mech, 'Your target has become invalid.', 0)
            elif (target.x, target.y) != (mech.x, mech.y):
                notify(mech, 'Your DFA target has moved!', 0)
            else:
                from systems.physical import dfa_attack
                outcome = dfa_attack(mech, target, notify_attacker=True)
                mech.last_dfa_result = outcome
                dfa = outcome.success
        if not dfa:
            notify(mech, 'You finish your jump.')
        if mech.map is not None:
            mech.elev = mech.map.elevation(mech.x, mech.y)
            mech.z = mech.elev - 1
            mech.fz = float32(mech.z * ZSCALE)
            drop_set_elevation(mech, 1)
        if int(mech.stagger_damage / 20) > 0:
            from systems.stagger import legacy_modifier
            notify(mech, "The damage you've taken makes the landing a bit harder...")
            if not make_piloting_roll(mech, legacy_modifier(mech)).success:
                notify(mech, "... something you apparently can't handle!")
                los_broadcast(mech, 'lands, staggers, and falls down!')
                mech_falls(mech, 1, notify_fall=False)
                return False
        if mech.unit_type == UnitType.MECH:
            reason = None
            if count_destroyed_legs(mech):
                reason = ('Your missing leg makes it harder to land', 'Your missing leg has caused you to fall upon landing!', 'lands, unbalanced, and falls down!')
            elif mech.sections[L.RLEG].basetohit or mech.sections[L.LLEG].basetohit:
                reason = ('Your damaged leg actuators make it harder to land', 'Your damaged leg actuators have caused you to fall upon landing!', 'lands, stumbles, and falls down!')
            elif mech.has_crit_status(CritStatus.GYRO_DAMAGED | CritStatus.GYRO_DESTROYED):
                reason = ('Your damaged gyro makes it harder to land', 'Your damaged gyro has caused you to fall upon landing!', 'lands, twists awkwardly, and falls down!')
            if reason:
                notify(mech, reason[0], 0)
                if not make_piloting_roll(mech, 0).success:
                    notify(mech, reason[1])
                    los_broadcast(mech, reason[2])
                    dfa = done = True
                    mech_falls(mech, 1, notify_fall=False)
    if mech.unit_type == UnitType.MECH and swarmers(mech):
        notify(mech, 'The suits hanging off you make landing harder!')
        if make_piloting_roll(mech, 4).success:
            detach_all(mech)
        else:
            notify(mech, 'You fail to properly control your unbalanced landing!')
            los_broadcast(mech, 'lands and crashes to the ground from the weight of the battlesuits!')
            mech_falls(mech, 1, notify_fall=False)
    if not dfa and not mech.is_fallen and not domino_space(mech, 1):
        los_broadcast(mech, 'returns to the ground where it belongs.' if mech.unit_type == UnitType.VEH_GROUND else 'lands gracefully.')
    if mech.is_jumping:
        _schedule_stabilization(mech, queue)
    mech.clear_status(S.JUMPING | S.DFA_ATTACK)
    mech.dfa_target = -1
    mech.going_x = mech.going_y = 0
    mech.speed = 0
    if queue is not None:
        queue.cancel_by_type_and_data(EventType.JUMP, mech)
    if mech._engine is not None:
        maybe_move(mech._engine, mech)
    if not done:
        from systems.mines import possible_mine_poof
        possible_mine_poof(mech, 'land')
    flood_unit(mech)
    extinguish_in_water(mech)
    if not getattr(mech._engine, 'new_stagger', 1):
        from systems.stagger import stop_stagger_check
        stop_stagger_check(mech)
    return not mech.is_fallen


def _jumpstabil_callback(event):
    from systems.movement_commands import notify
    event.data._stabil_event = None
    notify(event.data, '%cgYou have finally stabilized after your jump.%c', 1)


# =============================================================================
# Piloting Check Helpers
# =============================================================================

def make_piloting_check(
    mech: 'Mech',
    modifier: int = 0,
    piloting_skill: Optional[int] = None,
) -> tuple[bool, int, int]:
    """
    Make a piloting skill check.

    The base skill comes off the machine the way MechPilotSkillRoll_BTH does it
    (mech.utils.c:668: `mods += FindSPilotPiloting(mech) + ...`), i.e.
    find_spilot_piloting(mech) - the pilot's skill, or DEFAULT_PILOTING with no
    pilot, plus the quad's -2 (mech.utils.c:592-595).  `piloting_skill` is a
    None-sentinel override kept for callers that supply a skill directly (the C
    has no such parameter; nothing in the engine passes one).

    Args:
        mech: The mech making the check
        modifier: Additional modifier to the check
        piloting_skill: Override base piloting skill (default: the mech's pilot)

    Returns:
        Tuple of (success, roll, target)
    """
    from entities.mech import CritStatus

    if piloting_skill is None:
        piloting_skill = find_spilot_piloting(mech)

    # Calculate total modifier
    total_mod = modifier

    # Gyro damage
    if mech.has_crit_status(CritStatus.GYRO_DESTROYED):
        # Auto-fail with destroyed gyro
        return (False, 0, 99)
    elif mech.has_crit_status(CritStatus.GYRO_DAMAGED):
        total_mod += PILOTING_GYRO_DAMAGED

    # Hip damage
    if mech.has_crit_status(CritStatus.HIP_DAMAGED):
        total_mod += 2
    if mech.has_crit_status(CritStatus.HIP_DESTROYED):
        total_mod += 4

    target = piloting_skill + total_mod
    from core.randomness import roll as source_roll
    roll = source_roll('fall_pilot_rolls')

    return (roll >= target, roll, target)


# =============================================================================
# Game Loop Integration
# =============================================================================

def jump_periodic(engine: 'GameEngine') -> None:
    """
    Periodic jump update for all jumping mechs.

    This is registered with the game engine to run every JUMP_TICK.
    """
    from entities.mech import Mech

    for entity in engine.get_entities():
        if isinstance(entity, Mech) and entity.is_jumping:
            update_jump_periodic(entity)


def register_jump_system(engine: 'GameEngine') -> None:
    """
    Register the jump system with the game engine.
    """
    engine.register_periodic("jump", JUMP_TICK, jump_periodic)


@dataclass
class FallResult:
    """Result of a fall."""
    levels_fallen: int = 0
    damage_taken: int = 0
    pilot_damage: int = 0
    direction: int = 0            # New facing after fall
    message: str = ""


def make_mech_fall(mech, *, set_fallen=True):
    """Expanded MakeMechFall macro; the unbraced tail runs for every class."""
    from entities.mech import MechStatus as S
    from systems.ecm import mark_for_los_update
    from physics.flooding import flood_unit
    from core.events import EventType
    if set_fallen:
        mech.set_status(S.FALLEN)
    mech.clear_status(S.TORSO_LEFT | S.TORSO_RIGHT | S.FLIPPED_ARMS)
    mark_for_los_update(mech)
    flood_unit(mech)
    engine = getattr(mech, '_engine', None)
    if engine is not None:
        for kind in (EventType.STAND, EventType.HULLDOWN):
            engine.cancel_events_of_type(kind, mech)
    mech._stand_event = mech._hulldown_event = None
    mech.clear_status(S.HULLDOWN)
    from systems.movement_commands import historical_aircraft
    if not historical_aircraft(mech) and getattr(engine, 'new_stagger', 1):
        from systems.stagger import clear_all
        clear_all(mech)


def _schedule_stabilization(mech, queue=None):
    from core.events import EventType
    queue = queue or (mech._engine.events if mech._engine is not None else getattr(mech, '_jump_queue', None))
    if queue is not None:
        from entities.mech import UnitType
        delay = 3 if mech.unit_type == UnitType.BSUIT else 12
        mech._stabil_event = queue.schedule(delay, EventType.JUMPSTABIL, _jumpstabil_callback, data=mech)


def mech_falls(mech, levels=1, attacker=None, *, notify_fall=True):
    """MechFalls self-attribution, ordered macro effects and source damage context."""
    from entities.mech import MechStatus as S, UnitType
    from systems.combat import HitGroup, roll_1d6
    from systems.piloting import make_piloting_roll, head_hit_mw_damage
    from systems.movement_commands import notify
    from physics.movement import drop_set_elevation
    from systems.ecm import mark_for_los_update
    from systems.sensors import los_broadcast
    from systems.swarm import detach_all
    from systems.movement_commands import historical_aircraft
    historical = historical_aircraft(mech)
    detach_all(mech,historical=historical)
    if not historical and getattr(mech._engine, 'new_stagger', 1):
        from systems.stagger import clear_all
        clear_all(mech)
    result = FallResult(levels_fallen=levels)
    mech.last_fall_levels = levels
    mech.cocoon = 0
    if historical or not mech.has_status(S.COMBAT_SAFE):
        falling = mech.unit_type in (UnitType.MECH, UnitType.MW) or notify_fall
        prefix = 'You try to avoid taking ' + ('' if historical else 'personal ')
        notify(mech, prefix + ('damage in the fall.' if falling else 'damage.'), 0)
        if not make_piloting_roll(mech, levels).success:
            notify(mech, 'You take personal injury from the fall!' if falling else 'You take personal injury!', 0)
            result.pilot_damage = 1
            head_hit_mw_damage(mech, mech, 1)
    _interrupt_movement(mech)
    make_mech_fall(mech, set_fallen=mech.unit_type in (UnitType.MECH, UnitType.MW))
    if notify_fall:
        los_broadcast(mech, 'falls down!')
    drop_set_elevation(mech, 1)
    mech.fz = float32(mech.z * ZSCALE)
    die = draw('fall_directions', 1, 6, roll_1d6)
    from physics.hexmath import acceptable_degree
    mech.facing = mech.desired_facing = acceptable_degree(mech.facing + (die - 1) * 60)
    result.direction = mech.facing
    group = (HitGroup.FRONT, HitGroup.RIGHTSIDE, HitGroup.RIGHTSIDE, HitGroup.BACK, HitGroup.LEFTSIDE, HitGroup.LEFTSIDE)[die - 1]
    total = _fall_damage(mech, levels)
    if historical or not mech.has_status(S.COMBAT_SAFE):
        result.damage_taken = _apply_damage(mech, mech, group, total)
    from systems.mines import possible_mine_poof
    possible_mine_poof(mech, 'fall')
    mark_for_los_update(mech)
    result.message = f'Mech fell {levels} level(s), taking {result.damage_taken} damage'
    return result


def _interrupt_movement(mech):
    from entities.mech import MechStatus as S, MechStatus2 as S2, MoveType
    from core.events import EventType
    from systems.movement_commands import schedule_mode, maybe_move, notify
    engine = getattr(mech, '_engine', None)
    mech.speed = mech.desired_speed = 0
    if mech.is_jumping:
        mech.clear_status(S.JUMPING | S.DFA_ATTACK)
        queue = engine.events if engine is not None else getattr(mech, '_jump_queue', None)
        if queue is not None:
            queue.cancel_by_type_and_data(EventType.JUMP, mech)
        _schedule_stabilization(mech, queue)
    if engine is not None:
        engine.cancel_events_of_type(EventType.MOVEMODE, mech)
        mech._mode_event = None
        for flag in (S2.SPRINTING, S2.EVADING):
            if mech.has_status2(flag):
                schedule_mode(engine, mech, flag, False)
    if mech.move_type in (MoveType.VTOL, MoveType.FLY):
        mech.vertical_speed = mech.going_y = 0
        mech.start_fx = mech.start_fy = mech.start_fz = 0
        mech.set_status(S.LANDED)
        from systems.movement_commands import historical_aircraft
        if historical_aircraft(mech) or not mech.has_status(S.COMBAT_SAFE):
            if not historical_aircraft(mech) and mech.move_type == MoveType.VTOL:
                notify(mech, 'Your rotor has been destroyed!')
            mech.set_status(S.FALLEN)
        if engine is not None:
            engine.cancel_events_of_type(EventType.MOVE, mech)
            engine.cancel_events_of_type(EventType.AERO_MOVE, mech)
    elif engine is not None:
        maybe_move(engine, mech)


def _fall_damage(mech, levels):
    from entities.mech import MechStatus as S, UnitType
    from entities.map import HIGHWATER
    from systems.movement_commands import in_water
    from physics.collision import mech_rterrain
    divisor = 20 if in_water(mech) or mech_rterrain(mech) == HIGHWATER else 10
    total = int(levels * (mech.tonnage + 5) / divisor)
    if mech.has_status(S.UNDERSPECIAL) and mech.map is not None and mech.map.flags & 2:
        total = int(total * min(100, mech.map.grav) / 100)
    return total * 40 if mech.unit_type == UnitType.MW else total


def _apply_damage(mech, attacker, group, total):
    from systems.combat import HitGroup, get_hit_location, apply_damage_with_transfer
    from physics.flooding import flood_unit, extinguish_in_water
    from physics.hexmath import signed_remainder
    damage_taken, critical = 0, False
    clusters = [5] * max(0, int(total / 5))
    remainder = signed_remainder(total, 5)
    if remainder:
        clusters.append(remainder)
    for cluster in clusters:
        location, critical = get_hit_location(mech, group, critical=critical)
        damage_taken += apply_damage_with_transfer(mech, location, cluster,
            group == HitGroup.BACK, attacker=mech, is_critical=critical, engine=mech._engine,
            transfer=True, _entry_processed=True, attack_pilot=-1, los=0)
        flood_unit(mech)
        extinguish_in_water(mech)
    return damage_taken


def can_stand(mech: 'Mech') -> tuple[bool, str]:
    """
    Check if a mech can attempt to stand.

    Args:
        mech: The fallen mech

    Returns:
        Tuple of (can_stand, reason)
    """
    from entities.mech import MechStatus, CritStatus

    # Must be fallen to stand
    if not mech.is_fallen:
        return (False, "Mech is not fallen")

    # Must be started
    if not mech.is_started:
        return (False, "Mech is not started")

    # Can't be destroyed
    if mech.is_destroyed:
        return (False, "Mech is destroyed")

    # Can't stand with destroyed gyro
    if mech.has_crit_status(CritStatus.GYRO_DESTROYED):
        return (False, "Gyro is destroyed - cannot stand")

    # Need at least one working leg
    from entities.mech import MoveType
    from systems.parts import count_destroyed_legs
    dead = count_destroyed_legs(mech)
    if dead > (2 if mech.move_type == MoveType.QUAD else 1):
        return False, 'You have no legs to stand on!'

    return (True, "")


def _stand_done(event):
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    from systems.ecm import mark_for_los_update
    from entities.mech import MechStatus
    event.data._stand_event = None
    los_broadcast(event.data, 'stands up!')
    notify(event.data, 'You have finally finished standing up.')
    event.data.clear_status(MechStatus.FALLEN)
    mark_for_los_update(event.data)


def _stand_recovered(event):
    from systems.movement_commands import notify
    event.data._standfail_event = None
    notify(event.data, '%cgYou have finally recovered from your attempt to stand.%c')


def stand_up(mech, event_queue=None, argument=''):
    from entities.mech import MechStatus as S, UnitType, MoveType, CritStatus
    from systems.movement_commands import notify, pending, stand_time
    from systems.piloting import make_piloting_roll, piloting_bth
    from systems.parts import count_destroyed_legs
    from systems.ecm import mark_for_los_update
    from systems.sensors import los_broadcast
    from physics.collision import mech_rterrain
    from physics.movement import break_thru_ice, btech_config
    from core.events import EventType
    from entities.map import ICE
    if mech.unit_type == UnitType.BSUIT: return False, "You're standing already!"
    if mech.unit_type not in (UnitType.MECH, UnitType.MW): return False, "This vehicle cannot stand like a 'Mech."
    if mech.is_jumping: return False, "You're standing while jumping!"
    if mech.cocoon: return False, "You're standing while flying!"
    dead = count_destroyed_legs(mech)
    if dead > (3 if mech.move_type == MoveType.QUAD else 1): return False, 'You have no legs to stand on!'
    if dead > 2: return False, "You'd be far too unstable!"
    if mech.has_crit_status(CritStatus.GYRO_DESTROYED): return False, 'You cannot stand with a destroyed gyro!'
    if not mech.is_fallen: return False, "You're already standing!"
    if pending(mech, '_standfail_event'): return False, "You're still recovering from your last attempt!"
    if mech.has_status(S.HULLDOWN): return False, 'You can not stand while hulldown'
    if pending(mech, '_hulldown_event'): return False, 'You are busy changing your hulldown mode'
    target = piloting_bth(mech)
    # proper_explodearguments retains an empty first field for leading whitespace.
    import re
    keyword = re.split('[ \t]', str(argument).split('\0', 1)[0], maxsplit=1)[0]
    configured = btech_config(mech, 'btech_standcareful', 1)
    if argument:
        if keyword == 'check': return True, f'Your BTH to stand would be: {target}'
        if keyword != 'anyway' and not (keyword == 'careful' and configured):
            return False, "Unknown argument! use 'stand check'" + (", 'stand careful' or 'stand anyway'" if configured else " or 'stand anyway'")
    if keyword != 'anyway' and target > 12:
        return False, "You would fail; use 'stand anyway' if you really want to stand."
    careful = keyword == 'careful'
    mech.clear_status(S.FALLEN)
    mark_for_los_update(mech)
    auto = (mech.move_type == MoveType.QUAD and dead == 0) or mech.unit_type == UnitType.MW
    los_broadcast(mech, 'attempts to stand up.')
    if mech_rterrain(mech) == ICE and mech.z == -1: break_thru_ice(mech)
    if not auto and not make_piloting_roll(mech, -2 if careful else 0, succeed_when_fallen=False, award_xp=False).success:
        message = notify(mech, 'You fail your attempt to stand and fall back on the ground')
        mech_falls(mech, 1)
        delay = 4 if mech.unit_type == UnitType.MW else stand_time(mech)
        if careful: delay = max(30, delay * 2)
        if event_queue is not None:
            mech._standfail_event = event_queue.schedule(delay, EventType.STANDFAIL, _stand_recovered, data=mech)
        return False, message
    message = notify(mech, 'You begin to stand up.')
    delay = (4 if mech.unit_type == UnitType.MW else stand_time(mech)) * (2 if careful else 1)
    if event_queue is not None:
        mech._stand_event = event_queue.schedule(delay, EventType.STAND, _stand_done, data=mech)
    return True, message
