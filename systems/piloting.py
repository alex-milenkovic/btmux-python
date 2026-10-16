# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btechstats.c
#   btech/mech.bth.c
#   btech/mech.events.c
#   btech/mech.fire.c
#   btech/mech.sensor.c
#   btech/mech.startup.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/src/btech/mech.h
#   btech/src/include/btconfig.h

"""
Piloting skill system for BTMux Python reimplementation.

This module implements:
- Pilot skill resolution (the FindPilot* chain)
- Piloting skill checks (2d6 vs target)
- Stagger damage tracking
- Fall triggers from damage, criticals, etc.
- Pilot injury mechanics

Reference:
- BTMux btech/src/btech/mech.utils.c lines 580-629 - FindPilot* skill chain
- BTMux btech/src/btech/mech.bth.c - Piloting modifiers
- BTMux btech/src/btech/mech.update.c - Fall triggers
- BTMux btech/src/btech/btechstats.c - Pilot stats

Key mechanics:
- Piloting skill (default 5) is target for 2d6 roll
- Modifiers added for damage, gyro hits, leg damage
- Stagger damage accumulates and affects checks
- Certain events trigger immediate piloting checks
- Failed checks typically result in falls
"""

from __future__ import annotations
from core.randomness import roll as source_roll
from core.randomness import draw
import random
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from entities.mech import Mech
    from entities.weapon import Weapon


# =============================================================================
# Piloting Constants
# =============================================================================

# Default skill values - the single definition for the whole port.
# systems/combat.py and physics/jump.py re-export these names for compatibility.
#
# The C fallbacks are DEFAULT_PILOTING 6 / DEFAULT_GUNNERY 6
# (btconfig.h:179-180, "Skills used if pilot's not valid and no default mech
# skills"). Explicit Pilot values remain 5/4; these values apply only when
# no eligible pilot or machine override provides a skill.
DEFAULT_PILOTING = 6
DEFAULT_GUNNERY = 6

# Damage threshold for stagger (20+ damage in single hit triggers check)
STAGGER_DAMAGE_THRESHOLD = 20

# Piloting modifiers
PILOTING_GYRO_DAMAGED = 3        # +3 per damaged gyro hit
PILOTING_GYRO_DESTROYED = 99     # Auto-fail (can't balance)
PILOTING_HIP_DAMAGED = 2         # +2 for damaged hip
PILOTING_HIP_DESTROYED = 4       # +4 for destroyed hip
PILOTING_LEG_DESTROYED = 5       # +5 for destroyed leg
PILOTING_ACTUATOR_DAMAGED = 1    # +1 per damaged leg actuator

# Pilot injury thresholds
MAX_PILOT_HITS = 6               # Pilot death threshold
CONSCIOUSNESS_CHECK_TARGET = 5   # Base target for consciousness rolls


# =============================================================================
# Piloting Check Types
# =============================================================================

class PilotingCheckReason(IntEnum):
    """Reasons for making piloting checks."""
    DAMAGE_TAKEN = auto()         # Heavy damage received
    LEG_DESTROYED = auto()        # Lost a leg
    HIP_DAMAGED = auto()          # Hip critical
    GYRO_DAMAGED = auto()         # Gyro critical hit
    CHARGE_IMPACT = auto()        # Hit by charge attack
    DFA_IMPACT = auto()           # Hit by DFA
    KICK_HIT = auto()            # Hit by kick to leg
    JUMP_LANDING = auto()         # Landing from jump
    STAND_ATTEMPT = auto()        # Trying to stand up
    TERRAIN = auto()              # Difficult terrain
    PHYSICAL_ATTACK = auto()      # Making physical attack (kick miss)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class PilotingResult:
    """Result of a piloting check."""
    success: bool = False
    roll: int = 0
    target: int = 0
    reason: Optional[PilotingCheckReason] = None
    fell: bool = False
    message: str = ""


@dataclass
class PilotStats:
    """
    Pilot statistics for a mech.

    Legacy shim: superseded by entities.pilot.Pilot (skills) plus the Mech's own
    pilot_hits/unconscious state (the C keeps injuries on the machine as
    MechPilotStatus, mech.h:922).  Nothing constructs this; get_piloting_skill()
    still honours a mech.pilot_stats attribute if some caller sets one.
    """
    gunnery: int = DEFAULT_GUNNERY
    piloting: int = DEFAULT_PILOTING
    hits: int = 0                 # Damage taken (6 = death)
    unconscious: bool = False
    killed: bool = False


# =============================================================================
# Piloting Check Calculation
# =============================================================================

def calculate_piloting_modifier(mech: 'Mech') -> int:
    """
    Calculate total piloting modifier from mech damage.

    Args:
        mech: The mech to check

    Returns:
        Total modifier to add to piloting target
    """
    from entities.mech import CritStatus, Location, SectionConfig

    modifier = 0

    # Gyro damage
    if mech.has_crit_status(CritStatus.GYRO_DESTROYED):
        return PILOTING_GYRO_DESTROYED  # Auto-fail
    elif mech.has_crit_status(CritStatus.GYRO_DAMAGED):
        modifier += PILOTING_GYRO_DAMAGED

    # Hip damage
    if mech.has_crit_status(CritStatus.HIP_DESTROYED):
        modifier += PILOTING_HIP_DESTROYED
    elif mech.has_crit_status(CritStatus.HIP_DAMAGED):
        modifier += PILOTING_HIP_DAMAGED

    # Leg destruction
    if mech.sections[Location.LLEG].config & SectionConfig.SECTION_DESTROYED:
        modifier += PILOTING_LEG_DESTROYED
    if mech.sections[Location.RLEG].config & SectionConfig.SECTION_DESTROYED:
        modifier += PILOTING_LEG_DESTROYED

    # Stagger damage (if tracked)
    stagger = getattr(mech, 'stagger_damage', 0)
    if stagger > 0:
        modifier += calculate_stagger_modifier(stagger)

    return modifier


def calculate_stagger_modifier(stagger_damage: int) -> int:
    """
    Calculate piloting modifier from accumulated stagger damage.

    In BTMux, stagger damage accumulates during a turn and affects
    piloting checks until cleared.

    Args:
        stagger_damage: Total stagger damage accumulated

    Returns:
        Modifier to piloting target
    """
    if stagger_damage <= 0:
        return 0

    # Each 20 damage adds +1 to piloting
    return stagger_damage // STAGGER_DAMAGE_THRESHOLD


def _extended(mech, name):
    return bool(getattr(mech._engine, name, False))


def find_piloting_skill_name(mech):
    from entities.mech import UnitType as U, MoveType as M
    from physics.collision import mech_rterrain
    from entities.map import WATER
    if not _extended(mech, 'extended_piloting'):
        return {U.MW: 'Running', U.BSUIT: 'Piloting-BSuit', U.MECH: 'Piloting-Battlemech',
                U.VEH_GROUND: 'Drive', U.VEH_NAVAL: 'Drive', U.VTOL: 'Piloting-Aerospace',
                U.AERO: 'Piloting-Aerospace', U.DS: 'Piloting-Spacecraft', U.SPHEROID_DS: 'Piloting-Spacecraft'}.get(mech.unit_type)
    if mech.unit_type == U.MW and mech_rterrain(mech) == WATER:
        return 'Swimming'
    selected = {U.MW: 'Running', U.BSUIT: 'Piloting-Bsuit', U.VEH_NAVAL: 'Piloting-Naval',
                U.DS: 'Piloting-Spacecraft', U.SPHEROID_DS: 'Piloting-Spacecraft',
                U.VTOL: 'Piloting-Aerospace', U.AERO: 'Piloting-Aerospace'}.get(mech.unit_type)
    return selected or {M.BIPED: 'Piloting-Biped', M.QUAD: 'Piloting-Quad', M.TRACK: 'Piloting-Tracked',
                       M.HOVER: 'Piloting-Hover', M.WHEEL: 'Piloting-Wheeled'}.get(mech.move_type)


def find_gunnery_skill_name(mech, weapon=0):
    from entities.mech import UnitType as U
    from entities.weapon import get_weapon_by_index, WeaponType as W
    extended = _extended(mech, 'extended_gunnery')
    if not extended and mech.unit_type != U.MW:
        return {U.BSUIT: 'Gunnery-BSuit', U.MECH: 'Gunnery-Battlemech',
                U.VEH_GROUND: 'Gunnery-Conventional', U.VEH_NAVAL: 'Gunnery-Conventional',
                U.VTOL: 'Gunnery-Aerospace', U.AERO: 'Gunnery-Aerospace',
                U.DS: 'Gunnery-Spacecraft', U.SPHEROID_DS: 'Gunnery-Spacecraft'}.get(mech.unit_type)
    if weapon is None:
        weapon = 0
    if isinstance(weapon, int):
        if weapon < 0:
            if extended:
                return None
            weapon = None
        else:
            weapon = get_weapon_by_index(weapon)
            if weapon is None:
                raise ValueError('unsupported gunnery weapon index')
    name = getattr(weapon, 'name', '')
    if not extended:
        if mech.unit_type == U.MW:
            return 'Blade' if name in ('PC.Sword', 'PC.Vibroblade') else 'Small_Arms'
        return {U.BSUIT: 'Gunnery-BSuit', U.MECH: 'Gunnery-Battlemech',
                U.VEH_GROUND: 'Gunnery-Conventional', U.VEH_NAVAL: 'Gunnery-Conventional',
                U.VTOL: 'Gunnery-Aerospace', U.AERO: 'Gunnery-Aerospace',
                U.DS: 'Gunnery-Spacecraft', U.SPHEROID_DS: 'Gunnery-Spacecraft'}.get(mech.unit_type)
    if mech.unit_type == U.MW:
        if name in ('PC.Blade', 'PC.Vibroblade'):
            return 'Blade'
        return 'Support_Weapons' if name in ('PC.Blazer', 'PC.HeavyGyrojetGun') else 'Small_Arms'
    selected = {W.TARTILLERY: 'Gunnery-Artillery', W.TMISSILE: 'Gunnery-Missile',
                W.TAMMO: 'Gunnery-Ballistic', W.TBEAM: 'Gunnery-Laser'}.get(weapon.weapon_type)
    return selected or ('Gunnery-Flamer' if 'Flamer' in name else None)


def find_tech_skill_name(mech):
    from entities.mech import UnitType as U
    return {U.MECH: 'Technician-Battlemech', U.BSUIT: 'Technician-Battlemech',
            U.VEH_GROUND: 'Technician-Mechanic', U.VEH_NAVAL: 'Technician-Mechanic',
            U.AERO: 'Technician-Aerospace', U.VTOL: 'Technician-Aerospace',
            U.DS: 'Technician-Aerospace', U.SPHEROID_DS: 'Technician-Aerospace'}.get(mech.unit_type)


def skill_target(actor, name, scalar, default):
    if actor is None or name is None:
        return default
    from systems.characters import attached, skill_target as character_target
    if attached(actor):
        return character_target(actor._character_store,actor._character_id,name)
    target = getattr(actor, 'skills', {}).get(name, getattr(actor, scalar, default))
    store = getattr(actor, '_xp_store', None)
    if store is not None:
        from data.character_values import code, XP_MAX
        from data.characters import SKILLS, divide
        index = code(name)
        ident = getattr(actor, '_xp_id', getattr(actor, '_id', 1))
        if index >= 0 and ident in store.records:
            target -= divide(store.retrieve(ident, SKILLS).xp[index], XP_MAX)
    return target


def valid_pilot(mech, gun=False):
    override = getattr(mech, 'gun_pilot', None) if gun else None
    actor = override if override is not None else mech.pilot
    if actor is None or not getattr(actor, 'valid', True) or getattr(actor, '_id', 1) <= 0:
        return None
    if override is None and getattr(actor, 'location', mech._id) != mech._id:
        return None
    if getattr(actor, 'is_player', True) and not getattr(actor, 'connected', True):
        return None
    return actor


def machine_skill(mech, column):
    """sscanf's sequential signed %d parsing, including adjacent signed values."""
    import re
    if not getattr(mech, 'quiet', False):
        return None
    text = getattr(mech, 'mechskills', '')
    position = 0
    for index in range(column + 1):
        match = re.match(r'\s*([+-]?\d+)', text[position:])
        if match is None:
            return None
        value = int(match[1])
        if not -(1 << 31) <= value < 1 << 31:
            raise ValueError('unsupported MECHSKILLS signed integer overflow')
        position += match.end()
    return value


def find_pilot_piloting(mech):
    override = machine_skill(mech, 0)
    if override is not None:
        return override
    return skill_target(valid_pilot(mech), find_piloting_skill_name(mech), 'piloting', DEFAULT_PILOTING)


def find_spilot_piloting(mech):
    from entities.mech import MoveType
    return find_pilot_piloting(mech) - (2 if mech.move_type == MoveType.QUAD else 0)


def find_pilot_gunnery(mech, weapon=0):
    override = machine_skill(mech, 1)
    if override is not None:
        return override
    actor = valid_pilot(mech, True)
    if actor is None: return DEFAULT_GUNNERY
    return skill_target(actor, find_gunnery_skill_name(mech, weapon), 'gunnery', DEFAULT_GUNNERY)


DEFAULT_SPOTTING = 8


def find_pilot_spotting(mech):
    override = machine_skill(mech, 2)
    if override is not None:
        return override
    return skill_target(valid_pilot(mech), 'Gunnery-Spotting', 'spotting', DEFAULT_SPOTTING)


def find_pilot_arty_gun(mech):
    override = machine_skill(mech, 3)
    if override is not None:
        return override
    return skill_target(valid_pilot(mech, True), 'Gunnery-Artillery', 'artillery', 8)


def find_tech_skill(actor, mech):
    return skill_target(actor, find_tech_skill_name(mech), 'technician', 18)


def get_piloting_skill(mech: 'Mech') -> int:
    """
    Get the pilot's base piloting skill (legacy entry point).

    Kept for the pre-A9 callers that duck-typed skills onto the Mech.  A real
    Pilot wins over those attributes; after it the historical `pilot_skill` /
    `pilot_stats` lookups still apply, then DEFAULT_PILOTING.

    New code should not call this: find_pilot_piloting() is the faithful
    C-ordered chain (mech.utils.c:580-590) and find_spilot_piloting() is what
    every pilot-skill roll uses (mech.utils.c:668).  make_piloting_roll() was
    moved onto find_spilot_piloting; nothing in the engine calls this anymore.

    Args:
        mech: The mech to check

    Returns:
        Base piloting skill (default 5)
    """
    # Pilot entity (A9) takes precedence
    pilot = getattr(mech, 'pilot', None)
    if pilot is not None:
        return pilot.piloting

    # Check for pilot_skill attribute
    if hasattr(mech, 'pilot_skill') and mech.pilot_skill > 0:
        return mech.pilot_skill

    # Check for pilot_stats
    if hasattr(mech, 'pilot_stats') and mech.pilot_stats:
        return mech.pilot_stats.piloting

    return DEFAULT_PILOTING


# =============================================================================
# Piloting Checks
# =============================================================================

def piloting_bth(mech, modifier=0, piloting_skill=None):
    base = find_spilot_piloting(mech) if piloting_skill is None else piloting_skill
    target = base + mech.pilot_skill_base + modifier
    if mech.specials2 & 0x2000000:
        target += 1
    if mech.in_character and (mech.pilot is None or getattr(mech.pilot, 'location', mech._id) != mech._id):
        target += 5
    from physics.environment import pilot_modifier
    return target + pilot_modifier(mech)


def make_piloting_roll(mech, modifier=0, reason=None, piloting_skill=None, *,
                       succeed_when_fallen=True, award_xp=True):
    """MadePilotSkillRoll_Advanced/NoXP guard order, target and actual Roll."""
    from entities.mech import MechStatus
    from systems.movement_commands import notify
    result = PilotingResult(reason=reason)
    if mech.is_fallen and succeed_when_fallen:
        result.success = True
        result.message = 'Already fallen.'
        return result
    if mech.is_unconscious or not mech.is_started or mech.has_status(MechStatus.BLINDED):
        result.message = 'Pilot cannot make a skill roll.'
        return result
    result.roll = source_roll('pilot_rolls', lambda: random.randint(1, 6) + random.randint(1, 6))
    result.target = piloting_bth(mech, modifier, piloting_skill)
    result.success = result.roll >= result.target
    from core.effects import send_debug
    variant = ' (noxp)' if award_xp else ''  # Source labels are intentionally reversed.
    send_debug(mech, f'Attempting to make pilot{variant} skill roll. '
               f'SPilot: {find_spilot_piloting(mech)}, mods: {modifier}, '
               f'MechPilot: {mech.pilot_skill_base}, BTH: {result.target}')
    notify(mech, 'You make a piloting skill roll!', audience=0)
    notify(mech, f'Modified Pilot Skill: BTH {result.target}\tRoll: {result.roll}', audience=0)
    result.message = f"Piloting check {'passed' if result.success else 'failed'} ({result.roll} vs {result.target})"
    if result.success and result.target > 2 and award_xp:
        amount = max(1, min(result.target - 7, max(2, 1 + modifier)))
        adapter = getattr(mech._engine, 'piloting_xp_service', None)
        applied = False
        from systems.characters import attached
        if attached(mech.pilot):
            from systems.experience import piloting
            piloting(mech.pilot,mech,amount,True)
        else:
            if adapter is not None:
                applied = bool(adapter(mech.pilot, mech, amount, 1))
                name = find_piloting_skill_name(mech)
                if applied and mech.pilot is not None and name is not None:
                    from core.effects import emit_channel
                    emit_channel(mech, 'MechPilotXP', f'{mech.pilot.name} gained {amount} {name} XP')
            else:
                from systems.experience import piloting
                before = len(getattr(mech, 'xp_requests', []))
                applied = piloting(mech.pilot, mech, amount, True)
                if len(getattr(mech, 'xp_requests', [])) > before:
                    return result
            if not hasattr(mech, 'xp_requests'):mech.xp_requests=[]
            mech.xp_requests.append(dict(skill='piloting',amount=amount,applied=applied))
    return result


def check_for_fall(
    mech: 'Mech',
    modifier: int = 0,
    reason: Optional[PilotingCheckReason] = None,
) -> PilotingResult:
    """
    Make a piloting check that causes fall on failure.

    This is a convenience function that combines the piloting roll
    with fall execution.

    Args:
        mech: The mech making the check
        modifier: Additional situational modifier
        reason: Why this check is being made

    Returns:
        PilotingResult with fall status
    """
    result = make_piloting_roll(mech, modifier, reason)

    if not result.success:
        from physics.jump import mech_falls
        mech_falls(mech, levels=1)
        result.fell = True
        result.message += " - mech fell!"

    return result


# =============================================================================
# Stagger System
# =============================================================================

def add_stagger_damage(mech: 'Mech', damage: int) -> bool:
    """
    Add stagger damage to a mech.

    When a mech takes 20+ damage in a single hit, it accumulates
    "stagger" that affects piloting checks.

    Args:
        mech: The mech taking damage
        damage: Amount of damage in this hit

    Returns:
        True if piloting check is required
    """
    # Ensure stagger_damage attribute exists
    if not hasattr(mech, 'stagger_damage'):
        mech.stagger_damage = 0

    # Add damage if over threshold
    if damage >= STAGGER_DAMAGE_THRESHOLD:
        mech.stagger_damage += damage
        return True

    return False


def clear_stagger(mech: 'Mech') -> None:
    """
    Clear accumulated stagger damage.

    Called at end of turn or after successful piloting check.

    Args:
        mech: The mech to clear
    """
    if hasattr(mech, 'stagger_damage'):
        mech.stagger_damage = 0


def check_stagger(mech: 'Mech') -> Optional[PilotingResult]:
    """
    Check if mech needs to make piloting roll for stagger.

    Args:
        mech: The mech to check

    Returns:
        PilotingResult if check was needed, None otherwise
    """
    stagger = getattr(mech, 'stagger_damage', 0)
    if stagger <= 0:
        return None

    return check_for_fall(mech, reason=PilotingCheckReason.DAMAGE_TAKEN)


# =============================================================================
# Fall Triggers
# =============================================================================

def check_damage_fall_trigger(
    mech: 'Mech',
    damage: int,
    location: 'Location',
) -> Optional[PilotingResult]:
    """
    Check if damage triggers a piloting check.

    Triggers:
    - 20+ damage in single hit
    - Leg destruction
    - Hip critical

    Args:
        mech: The mech taking damage
        damage: Amount of damage
        location: Where damage was applied

    Returns:
        PilotingResult if check was triggered, None otherwise
    """
    from entities.mech import Location

    result = None

    # Heavy damage check
    if damage >= STAGGER_DAMAGE_THRESHOLD:
        add_stagger_damage(mech, damage)
        result = check_for_fall(mech, reason=PilotingCheckReason.DAMAGE_TAKEN)

    # Leg destruction check
    if location in (Location.LLEG, Location.RLEG):
        from entities.mech import SectionConfig
        if mech.sections[location].config & SectionConfig.SECTION_DESTROYED:
            result = check_for_fall(mech, modifier=2, reason=PilotingCheckReason.LEG_DESTROYED)

    return result


def trigger_fall_from_critical(
    mech: 'Mech',
    critical_type: str,
) -> Optional[PilotingResult]:
    """
    Trigger piloting check from critical hit.

    Args:
        mech: The mech taking the critical
        critical_type: Type of critical hit

    Returns:
        PilotingResult if check was triggered
    """
    if critical_type == "GYRO":
        return check_for_fall(mech, reason=PilotingCheckReason.GYRO_DAMAGED)
    elif critical_type == "HIP":
        return check_for_fall(mech, reason=PilotingCheckReason.HIP_DAMAGED)

    return None


# =============================================================================
# Pilot Injury System (btechstats.c:894-1088, mech.events.c:235-262)
# =============================================================================

# Message hook, same pattern as systems.missile.NOTIFY_HOOK — a client wires
# in a callable to receive mech_notify-style strings.
NOTIFY_HOOK: Optional[Callable[['Mech', str], None]] = None


def _notify(mech: 'Mech', message: str, audience=0) -> None:
    from systems.movement_commands import notify
    notify(mech,message,audience=audience)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


# Consciousness target by pilot-hit count (PilotStatusRollNeeded,
# btechstats.c:894).  handlemwconc indexes it with BOUNDED(0, hits, 4)
# (btechstats.c:955), so the final 11 entry is unreachable from there —
# kept anyway, as in the C.
PILOT_STATUS_ROLL_NEEDED = [0, 3, 5, 7, 10, 11]

# btconfig.h:154 (sic: "ORIGINAL authors thought it was UNCONCIOUS")
UNCONSCIOUS_TIME = 30


def roll_skilled() -> int:
    """char_rollskilled (btechstats.c:270-273): plain 2d6."""
    from systems.characters import roll_dice
    return roll_dice('skilled')


def roll_saving() -> int:
    """
    char_rollsaving (btechstats.c:218-242): roll 3d6, return the best
    pair — the "toughness" advantage's consciousness roll.
    """
    from systems.characters import roll_dice
    return roll_dice('saving')


def _pilot_has_toughness(mech: 'Mech') -> bool:
    """HasBoolAdvantage(MechPilot(mech), "toughness") — advantage flags
    live on the Pilot entity; absent pilot/flag reads False, like the C's
    MechPilot == -1."""
    pilot = getattr(mech, 'pilot', None)
    from systems.characters import actor_advantage
    return actor_advantage(pilot,'Toughness')


def prolong_uncon(mech: 'Mech', length: int) -> None:
    """
    Knock the pilot out (or extend an existing knockout).

    ProlongUncon (mech.events.c:248-262) extends the last live recovery
    deadline and replaces all old events. Detached legacy units retain
    their countdown fallback until attached to a real event engine.
    """
    from entities.mech import MechStatus

    if mech.has_status(MechStatus.DESTROYED):
        return
    engine = mech._engine
    if engine is not None:
        from core.events import EventType
        remaining = engine.events.last_time_until_type_data(EventType.RECOVERY, mech)
        if remaining is None:
            mech.set_status(MechStatus.UNCONSCIOUS)
            delay = length
        else:
            delay = remaining + length
            engine.cancel_events_of_type(EventType.RECOVERY, mech)
        engine.schedule_event(delay, EventType.RECOVERY, recovery_event, data=mech)
        return
    countdown = getattr(mech, 'uncon_recovery_countdown', 0)
    # Recovering(mech) == an EVENT_RECOVERY is pending (mech.events.c:253)
    if not (mech.has_status(MechStatus.UNCONSCIOUS) and countdown > 0):
        mech.set_status(MechStatus.UNCONSCIOUS)
        mech.uncon_recovery_countdown = length
        return
    # mech.events.c:259-261: new pending time = remaining + length
    mech.uncon_recovery_countdown = countdown + length


def recovery_event(event):
    mech_recovery(event.data)


def handle_mw_conc(mech: 'Mech', initial: bool = True) -> bool:
    """
    Pilot consciousness (and pilot-death) check.

    Port of handlemwconc (btechstats.c:929-987), the engine-pilot branch —
    the C's In_Character path reads MUX character stats via mw_ic_bth
    (btechstats.c) and lands with the btechstats port; engine pilots use
    MechPilotStatus (here mech.pilot_hits) exactly as the C's non-IC arm
    does.

    Rule refs in the C: MechWarrior 2nd Ed p.22, BMR Revised p.17 /
    Total Warfare p.41-42 (>5 bruise = death).

    Returns True if the pilot is (or remains) conscious.
    """
    from entities.mech import MechStatus

    # btechstats.c:941-954: >5 pilot hits on a fresh check = death
    character_ic = _has_character_health(mech,require_location=False)
    if not character_ic and initial and mech.pilot_hits > 5:
        _notify(mech, "You are killed from personal injuries!!")
        if not mech.has_status(MechStatus.DESTROYED):
            from systems.damage import destroy_mech, KILL_TYPE_MWDAMAGE
            destroy_mech(mech, mech, showboom=False,
                         reason=KILL_TYPE_MWDAMAGE)
        mech.pilot = None            # MechPilot(mech) = -1
        mech.speed = 0.0
        mech.desired_speed = 0.0
        return False

    # btechstats.c:955 — note the index cap at 4
    target = mw_ic_bth(mech) if character_ic else PILOT_STATUS_ROLL_NEEDED[
        max(0, min(int(mech.pilot_hits), 4))]

    # btechstats.c:957-958
    if initial and mech.has_status(MechStatus.UNCONSCIOUS):
        return False

    if _pilot_has_toughness(mech):
        roll = roll_saving()
    else:
        roll = roll_skilled()

    if mech.pilot is not None and getattr(mech.pilot,'_id',-1)>=0:
        _notify(mech, "You attempt to keep consciousness!" if initial else
                "You attempt to regain consciousness!")
        _notify(mech, ("Retain Conciousness on: %d  \tRoll: %d" if initial else
                      "Regain Consciousness on: %d  \tRoll: %d") % (abs(target), roll))

    if roll < abs(target):
        if initial:
            _notify(mech, "Consciousness slips away from you as you "
                          "enter a sea of darkness...")
        prolong_uncon(mech, UNCONSCIOUS_TIME)
        return False
    return True


def mech_recovery(mech: 'Mech') -> None:
    """
    The EVENT_RECOVERY firing — an unconscious pilot's wake-up attempt.

    Port of mech_recovery_event (mech.events.c:235-246).  A failed
    attempt re-knocks via handle_mw_conc -> prolong_uncon(30), exactly
    the C's self-perpetuating loop.
    """
    from entities.mech import MechStatus

    if (mech.has_status(MechStatus.DESTROYED) or
            not mech.has_status(MechStatus.UNCONSCIOUS)):
        return
    if handle_mw_conc(mech, initial=False):
        mech.clear_status(MechStatus.UNCONSCIOUS)
        mech.uncon_recovery_countdown = 0
        _notify(mech, "The pilot regains consciousness!",audience=2)


def head_hit_mw_damage(mech: 'Mech', attacker: Optional['Mech'],
                       dam: int) -> None:
    """
    Pilot bruising from head hits / cockpit trauma.

    Port of headhitmwdamage (btechstats.c:989-1042). Attached IC pilots
    persist source bruise/lethal health before consciousness processing;
    non-IC pilots use the unit hit counter.
    """
    _character_injury(mech,attacker,dam,lethal=False)


def mw_lethal_damage(mech: 'Mech', attacker: Optional['Mech'], dam: int) -> None:
    """Source lethal injury, including health storage before consciousness."""
    _character_injury(mech,attacker,dam,lethal=True)


def _has_character_health(mech,require_location=True):
    from systems.characters import attached
    actor=mech.pilot
    return (mech.in_character and attached(actor) and actor._id>0 and
            (not require_location or actor.location==mech._id))


def mw_ic_bth(mech):
    from data.characters import HEALTH,ATTRS,ADVS
    stats=health_snapshot(mech.pilot,HEALTH|ATTRS|ADVS)
    build=stats.get('Build');remaining=10*build-stats.get('Bruise')
    modifier=-int(stats.get('Pain_Resistance')==1)
    for multiple,target in ((8,3),(6,5),(4,7),(2,10)):
        if remaining>=multiple*build:return target+modifier
    return 11+modifier if remaining>=-1 else 0


def fix_pilotdamage(mech,actor):
    from data.characters import divide,HEALTH,ATTRS
    from systems.characters import source_stats
    stats=source_stats(mech,actor,HEALTH|ATTRS)
    denominator=stats.get('Build')*2
    if not 1<=denominator<=100:denominator=10
    mech.pilot_hits=mech.pilot_status=divide(stats.get('Bruise')+stats.get('Lethal'),denominator)


def health_snapshot(actor,mask):
    from systems.characters import attached,actor_value
    from data.characters import Stats
    if attached(actor):return actor._character_store.retrieve(actor._character_id,mask)
    stats=Stats()
    for name in ('Build','Bruise','Lethal','Pain_Resistance'):stats.set(name,actor_value(actor,name))
    return stats


def _character_injury(mech,attacker,dam,lethal):
    if mech._id<0:return
    if not _has_character_health(mech):
        mech.pilot_hits+=dam;handle_mw_conc(mech,initial=True);return
    from data.characters import HEALTH,ATTRS,ADVS
    from systems.damage import destroy_mech,KILL_TYPE_MWDAMAGE,_kill_mech_contents
    actor=mech.pilot;store=actor._character_store
    stats=store.retrieve(actor._id,HEALTH|ATTRS|ADVS)
    build=stats.get('Build');bruise=stats.get('Bruise');deadly=stats.get('Lethal')
    fatal=False
    if lethal:
        build=build or 1
        deadly+=min(40,max(10,dam*build));fatal=deadly>=build*10
        bruise=build*10-5
    else:
        bruise+=2*build*dam
        if bruise>build*10:
            deadly+=bruise-build*10;bruise=build*10
            fatal=deadly>=build*10
    if fatal:
        stats.set('Lethal',build*10-1);stats.set('Bruise',build*10)
        store.store(actor._id,stats,HEALTH)
        if not mech.is_destroyed:destroy_mech(mech,attacker,showboom=False,reason=KILL_TYPE_MWDAMAGE)
        _kill_mech_contents(mech);return
    stats.set('Bruise',bruise);stats.set('Lethal',deadly);store.store(actor._id,stats,HEALTH)
    handle_mw_conc(mech,initial=True)
    mech.pilot_hits+=dam


# =============================================================================
# Combat Integration
# =============================================================================

def on_damage_received(
    mech: 'Mech',
    damage: int,
    location: 'Location',
    attacker: Optional['Mech'] = None,
) -> list[PilotingResult]:
    """
    Handle piloting checks triggered by receiving damage.

    This should be called by the combat system after applying damage.

    Args:
        mech: The mech that took damage
        damage: Amount of damage dealt
        location: Where damage was applied
        attacker: Who dealt the damage (optional)

    Returns:
        List of piloting check results
    """
    results = []

    # Check for damage-triggered fall
    result = check_damage_fall_trigger(mech, damage, location)
    if result:
        results.append(result)

    return results


def on_turn_end(mech: 'Mech') -> None:
    """
    Called at end of turn to clear stagger and do cleanup.

    Args:
        mech: The mech ending its turn
    """
    clear_stagger(mech)


# =============================================================================
# Game Loop Integration
# =============================================================================

def piloting_periodic(engine: 'GameEngine') -> None:
    """
    Periodic piloting system update.

    Handles pilot recovery checks for unconscious pilots.

    Args:
        engine: The game engine
    """
    from entities.mech import Mech, MechStatus

    for entity in engine.get_entities():
        if isinstance(entity, Mech):
            # EVENT_RECOVERY countdown (mech.events.c:235-262): the wake
            # attempt fires UNCONSCIOUS_TIME seconds after the knockout,
            # not every tick.
            if entity.has_status(MechStatus.UNCONSCIOUS) and entity._engine is None:
                countdown = getattr(entity, 'uncon_recovery_countdown', 0) - 1
                entity.uncon_recovery_countdown = countdown
                if countdown <= 0:
                    mech_recovery(entity)

            # EVENT_BLINDREC countdown (mech_unblind_event,
            # mech.sensor.c:870-877 / ScrambleInfraAndLiteAmp :920-921)
            if entity.has_status(MechStatus.BLINDED) and entity._engine is None:
                bcd = getattr(entity, 'blind_recovery_countdown', 0) - 1
                entity.blind_recovery_countdown = bcd
                if bcd <= 0:
                    from systems.sensors import mech_unblind
                    mech_unblind(entity)

            # Inferno-burn countdown fallback (inferno_end_event,
            # mech.fire.c:20-27) — used only when the burn was started
            # without an engine clock; the event path is primary.
            from entities.mech import CritStatus as CS
            if (entity.has_crit_status(CS.JELLIED) and
                    getattr(entity, 'burn_recovery_countdown', 0) > 0):
                from systems.missile import inferno_burn
                inferno_burn(engine, entity, 0)


def register_piloting_system(engine: 'GameEngine') -> None:
    """
    Register the piloting system with the game engine.

    Args:
        engine: The game engine to register with
    """
    # Pilot recovery check every 30 seconds
    engine.register_periodic("piloting", 30, piloting_periodic)
