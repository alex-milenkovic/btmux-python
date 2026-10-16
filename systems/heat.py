# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/crit.c
#   btech/mech.startup.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   btech/src/btech/weapons.h
#   btech/src/include/btconfig.h
#   src/conf.c
# Historical Aerospace sources:
#   btech/crit.c
#   btech/mech.update.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.h
#   src/hcode/btech/mech.startup.c
#   src/hcode/btech/weapons.h
#   src/hcode/include/btconfig.h

"""
Heat system for BTMux Python reimplementation.

This module handles mech heat including:
- Heat generation from movement, weapons, and environment
- Heat dissipation from heat sinks
- Overheat effects: shutdown, ammo explosion, pilot damage

Reference:
- BTMux btech/src/btech/mech.update.c - UpdateHeat(), HandleOverheat()
- BTMux btech/src/include/btconfig.h - HEAT_TICK, TURN, etc.
- BTMux btech/src/btech/mech.h - Heat-related constants

Key mechanics:
- Heat updates every HEAT_TICK (2 seconds)
- Overheat checks happen every TURN (30 seconds)
- Current heat is assigned from plus-minus; weapon heat retains history
- Heat sinks dissipate (plus_heat - minus_heat) each HEAT_TICK
"""

from __future__ import annotations
from core.randomness import roll as source_roll
import random
import math
from core.randomness import draw, float32
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Optional, Callable, List, Tuple

if TYPE_CHECKING:
    from entities.mech import Mech
    from core.game_loop import GameEngine


# =============================================================================
# Heat Constants (from BTMux btconfig.h and mech.h)
# =============================================================================

# Timing
HEAT_TICK = 2               # Heat updates every 2 ticks
TURN = 30                   # A "turn" is 30 seconds (used for overheat checks)
WEAPON_RECYCLE_TIME = 30    # Weapon heat decay rate divisor

# Movement heat values
HEAT_WALKING = 1.0          # Heat from walking
HEAT_RUNNING = 2.0          # Heat from running
HEAT_SPRINTING = 3.0        # Heat from sprinting/evading (optional mode)
HEAT_JUMP_MINIMUM = 3.0     # Minimum heat from jumping

# Environment heat
HEAT_FIRE_HEX = 5.0         # Heat from standing in fire
HEAT_STEALTH_ARMOR = 10.0   # Heat from stealth armor active
HEAT_NULL_SIG = 10.0        # Heat from null signature system

# Map temperature constants (reference: mech.update.c)
# Temperature in Celsius - modifies heat dissipation
TEMP_STANDARD = 25          # Standard/neutral temperature
TEMP_COLD_THRESHOLD = 10    # Below this, +2 dissipation bonus
TEMP_EXTREME_COLD = -30     # Below this, +4 dissipation bonus
TEMP_HOT_THRESHOLD = 40     # Above this, -2 dissipation
TEMP_EXTREME_HOT = 55       # Above this, additional heat generation

# Heat dissipation modifiers from temperature
TEMP_COLD_BONUS = 2.0       # Extra dissipation in cold
TEMP_EXTREME_COLD_BONUS = 4.0  # Extra dissipation in extreme cold
TEMP_HOT_PENALTY = 2.0      # Reduced dissipation in hot temps
TEMP_EXTREME_HOT_HEAT = 2.0 # Extra heat generation in extreme heat

# Heat sink constants
DEFAULT_HEAT_SINKS = 10     # Default number of heat sinks
MAX_LEG_SINKS_BONUS = 4     # Maximum bonus from leg sinks in water
INFERNO_SINK_PENALTY = 6    # Heat sink effectiveness penalty when jellied

# Overheat thresholds (2d6 target number to avoid shutdown)
# If roll >= target, avoid shutdown
SHUTDOWN_THRESHOLDS = {
    14: 4,   # 14+ heat: avoid on 4+
    18: 6,   # 18+ heat: avoid on 6+
    22: 8,   # 22+ heat: avoid on 8+
    26: 10,  # 26+ heat: avoid on 10+
    30: 99,  # 30+ heat: automatic shutdown (can't avoid)
}

# Ammo explosion thresholds (2d6 target number to avoid explosion)
# Without inferno ammo
# mudconf.btech_inferno_penalty (conf.c:144, default 0) — gates both the
# inferno cook-off risk table and inferno-bin precedence
BTECH_INFERNO_PENALTY = 0

AMMO_EXPLOSION_THRESHOLDS = {
    19: 4,   # 19+ heat: avoid on 4+
    23: 6,   # 23+ heat: avoid on 6+
    28: 8,   # 28+ heat: avoid on 8+
}

# Ammo explosion with inferno ammo (harder to avoid)
AMMO_EXPLOSION_INFERNO_THRESHOLDS = {
    10: 4,   # 10+ heat: avoid on 4+
    14: 6,   # 14+ heat: avoid on 6+
    19: 8,   # 19+ heat: avoid on 8+
    23: 10,  # 23+ heat: avoid on 10+
    28: 12,  # 28+ heat: avoid on 12+ (nearly impossible)
}

# Pilot damage thresholds (with life support destroyed)
PILOT_DAMAGE_THRESHOLD_1 = 15.0  # +1 damage to pilot
PILOT_DAMAGE_THRESHOLD_2 = 25.0  # +2 damage to pilot

# Startup restrictions (reference: mech.startup.c)
STARTUP_HEAT_PILOTING_THRESHOLD = 9.0   # At or above this, need piloting check to startup
STARTUP_HEAT_IMPOSSIBLE_THRESHOLD = 14.0  # Cannot restart if heat > this
STARTUP_PILOTING_MODIFIER = 3           # +3 to piloting difficulty for hot startup

# Heat level indicators
HEAT_LEVEL_GREEN = 14.0     # Below this, indicator is green
HEAT_LEVEL_YELLOW = 19.0    # Below this (above green), indicator is yellow
# 19+ is red

# Movement point conversion
KPH_PER_MP = 10.75
MP_PER_KPH = 0.0930233


# =============================================================================
# Heat Result Data Structure
# =============================================================================

@dataclass
class HeatResult:
    """Results of a heat update."""
    plus_heat: float = 0.0          # Heat generated this tick
    minus_heat: float = 0.0         # Heat dissipated this tick
    delta_heat: float = 0.0         # Net heat change
    new_heat: float = 0.0           # New heat level
    shutdown: bool = False          # Did the mech shut down?
    shutdown_avoided: bool = False  # Did the mech avoid shutdown?
    ammo_explosion: bool = False    # Did ammo explode?
    ammo_explosion_damage: int = 0  # Damage from ammo explosion
    ammo_explosion_location: int = -1  # Location of explosion
    mech_destroyed: bool = False    # Was mech destroyed by explosion?
    pilot_damage: int = 0           # Damage dealt to pilot
    heat_level_changed: bool = False  # Did heat indicator change?
    old_heat_level: str = "green"   # Previous indicator
    new_heat_level: str = "green"   # New indicator
    messages: List[str] = field(default_factory=list)  # Status messages


@dataclass
class StartupResult:
    """Result of a startup attempt."""
    success: bool = False           # Did startup succeed?
    heat_blocked: bool = False      # Was startup blocked due to high heat?
    piloting_required: bool = False # Was a piloting check required?
    piloting_roll: int = 0          # What was rolled (if applicable)
    piloting_target: int = 0        # What was needed (if applicable)
    message: str = ""               # Status message


# =============================================================================
# Utility Functions
# =============================================================================

def roll_2d6() -> int:
    """Roll 2d6 and return the sum."""
    return source_roll()


def get_heat_indicator(heat: float) -> str:
    """Get the heat indicator color based on heat level."""
    if heat >= HEAT_LEVEL_YELLOW:
        return "red"
    elif heat >= HEAT_LEVEL_GREEN:
        return "yellow"
    else:
        return "green"


def is_running(speed: float, max_speed: float) -> bool:
    """
    Check if a speed is considered "running".

    Running = speed > 2/3 of max speed (+ small buffer)
    Reference: btmacros.h MWalkingSpeed and IsRunning macros
    """
    walk_speed = float32(2.0 * float32(max_speed)) / 3.0 + 0.1
    return speed > walk_speed


def calculate_temperature_dissipation_modifier(temperature: int) -> float:
    """C special-map dissipation: one capacity per begun ten-degree interval."""
    if temperature < -30:
        return math.ceil((-30 - temperature) / 10)
    if temperature > 50:
        return -math.ceil((temperature - 50) / 10)
    return 0.0


def calculate_temperature_heat_generation(temperature: int) -> float:
    """Temperature affects dissipation only in the C heat update."""
    return 0.0


def calculate_movement_heat(mech, max_speed=None):
    """Movement and jump heat are additive; use the previous heat for TSM."""
    from entities.mech import Specials, MechStatus2
    from physics.cargo import cargo_max_speed
    if max_speed is None:
        max_speed = cargo_max_speed(mech)
        if mech.specials & Specials.TRIPLE_MYOMER_TECH and mech.heat >= 9:
            max_speed = math.ceil((round(max_speed / 1.5 / KPH_PER_MP) + 1) * 1.5) * KPH_PER_MP
    heat = 0.0
    if abs(mech.speed) > 0:
        if mech.has_status2(MechStatus2.SPRINTING | MechStatus2.EVADING):
            heat = 3.0
        else:
            heat = 2.0 if is_running(mech.desired_speed, max_speed) else 1.0
    if mech.is_jumping:
        heat += max(3.0, mech.jump_speed * MP_PER_KPH)
    return heat


def calculate_environment_heat(mech, map_temperature=TEMP_STANDARD):
    from entities.mech import UnitType, MechStatus2
    from entities.map import FIRE
    heat = 5.0 if mech.terrain == FIRE and mech.unit_type == UnitType.MECH else 0.0
    if mech.has_status2(MechStatus2.STH_ARMOR_ON):
        heat += 10
    if mech.has_status2(MechStatus2.NULLSIGSYS_ON):
        heat += 10
    return heat


def calculate_engine_heat(mech: 'Mech') -> float:
    """
    Calculate heat from engine damage.

    Each engine critical hit adds +5 heat when started.

    Reference: UpdateHeat() in mech.update.c line 1421

    Args:
        mech: The mech to calculate for

    Returns:
        Engine damage heat
    """
    if mech.is_started:
        return float(mech.engine_heat)
    return 0.0


def calculate_internal_heat(mech):
    """UpdateHeat's pre-weapon sum, retaining each source float assignment."""
    from entities.mech import UnitType, Specials, MechStatus2
    from entities.map import FIRE
    from physics.cargo import cargo_max_speed
    maximum = float32(cargo_max_speed(mech))
    if mech.specials & Specials.TRIPLE_MYOMER_TECH and mech.heat >= 9:
        maximum = float32(math.ceil((round(cargo_max_speed(mech) / 1.5 / KPH_PER_MP) + 1) * 1.5) * KPH_PER_MP)
    heat = 5.0 if mech.terrain == FIRE and mech.unit_type == UnitType.MECH else 0.0
    if abs(mech.speed) > 0:
        movement = 3.0 if mech.has_status2(MechStatus2.SPRINTING | MechStatus2.EVADING) else 2.0 if is_running(mech.desired_speed, maximum) else 1.0
        heat = float32(heat + movement)
    if mech.is_jumping:
        heat = float32(heat + max(3.0, float32(mech.jump_speed) * MP_PER_KPH))
    if mech.is_started:
        heat = float32(heat + float32(mech.engine_heat))
    if mech.has_status2(MechStatus2.STH_ARMOR_ON):
        heat = float32(heat + 10)
    if mech.has_status2(MechStatus2.NULLSIGSYS_ON):
        heat = float32(heat + 10)
    return heat


def calculate_plus_heat(mech, map_temperature=TEMP_STANDARD):
    return float32(calculate_internal_heat(mech) + float32(mech.weap_heat))


# =============================================================================
# Heat Dissipation
# =============================================================================

def calculate_minus_heat(mech, in_water=False, water_depth=0, map_temperature=TEMP_STANDARD):
    from entities.mech import CritStatus
    from systems.heat_control import active_capacity, leg_heat_sinks
    capacity = active_capacity(mech)
    minus = float(capacity)
    if in_water and water_depth <= -1:
        bonus = min(4, leg_heat_sinks(mech)) if water_depth == -1 and not mech.is_fallen else 6
        minus = min(2 * capacity, capacity + bonus)
    if mech.has_crit_status(CritStatus.JELLIED):
        minus = max(0, minus - 6)
    from physics.environment import heat_modifier
    from entities.mech import UnitType
    minus = float32(minus + calculate_temperature_dissipation_modifier(map_temperature))
    # The Maps-approved weather adapter remains on the general profile; the
    # recovered fighter UpdateHeat has no weather dissipation consumer.
    return float32(minus + (heat_modifier(mech) if mech.unit_type == UnitType.MECH else 0))


def decay_weapon_heat(mech: 'Mech', minus_heat: float, internal_heat: float) -> None:
    """
    Decay the accumulated weapon heat.

    Weapon heat decays based on heat sink capacity beyond internal heat.

    Reference: UpdateHeat() in mech.update.c lines 1485-1489

    Args:
        mech: The mech to update
        minus_heat: Current heat dissipation
        internal_heat: Heat from non-weapon sources (movement, env, etc.)
    """
    # Decay rate based on excess dissipation capacity
    decay = float32(float32(minus_heat - internal_heat) / WEAPON_RECYCLE_TIME)
    mech.weap_heat = max(0.0, float32(mech.weap_heat - decay))


def update_heat(
    mech: 'Mech',
    in_water: bool = False,
    water_depth: int = 0,
    map_temperature: int = TEMP_STANDARD
) -> HeatResult:
    """
    Update the mech's heat level.

    This is the main heat update function called every HEAT_TICK.
    It calculates plus/minus heat and updates the mech's heat level.

    Reference: UpdateHeat() in mech.update.c

    Args:
        mech: The mech to update
        in_water: Whether in water
        water_depth: Water depth
        map_temperature: Map temperature in Celsius (default 25)

    Returns:
        HeatResult with the update results
    """
    from entities.mech import UnitType

    result = HeatResult()

    # MechHasHeat includes mechs and aerospace/dropship heat-bearing classes.
    if mech.unit_type not in (UnitType.MECH, UnitType.AERO):
        result.new_heat = mech.heat
        return result

    # Store old heat for comparison
    old_heat = mech.heat
    result.old_heat_level = get_heat_indicator(old_heat)

    # Calculate heat generation (includes extreme temperature effects)
    internal_heat = calculate_internal_heat(mech)
    result.plus_heat = float32(internal_heat + float32(mech.weap_heat))

    # Calculate heat dissipation (includes temperature modifiers)
    result.minus_heat = calculate_minus_heat(mech, in_water, water_depth, map_temperature)

    # Store values on mech for reference
    mech.plus_heat = result.plus_heat
    mech.minus_heat = result.minus_heat

    from entities.mech import CritStatus
    from systems.heat_control import enable_some_sinks, disable_some_sinks
    if mech.has_crit_status(CritStatus.HEATCUTOFF):
        net = float32(mech.plus_heat - mech.minus_heat)
        if net >= 10:
            enable_some_sinks(mech, math.floor(net - 10) + 1)
        elif net < 9:
            disable_some_sinks(mech, math.floor(9 - net) + 1)
    else:
        enable_some_sinks(mech, 100)
    result.minus_heat = mech.minus_heat
    # C assigns the new balance; retained weapon heat carries the history.
    result.delta_heat = float32(result.plus_heat - result.minus_heat)
    mech.heat = max(0.0, result.delta_heat)
    result.new_heat = mech.heat

    # Decay weapon heat
    decay_weapon_heat(mech, result.minus_heat, internal_heat)

    # Check for heat indicator change
    result.new_heat_level = get_heat_indicator(mech.heat)
    result.heat_level_changed = (result.old_heat_level != result.new_heat_level)

    return result


# =============================================================================
# Overheat Effects
# =============================================================================

def check_ammo_explosion(mech: 'Mech', has_inferno: bool = False) -> bool:
    """
    Check if ammo explodes due to heat.

    At certain heat levels, there's a chance of ammo cooking off.
    Inferno ammo makes this more likely.

    Reference: HandleOverheat() in mech.update.c lines 1201-1256

    Args:
        mech: The mech to check
        has_inferno: Whether the mech has inferno ammo

    Returns:
        True if ammo explodes, False otherwise
    """
    heat = mech.heat

    # Select threshold table
    if has_inferno:
        thresholds = AMMO_EXPLOSION_INFERNO_THRESHOLDS
    else:
        thresholds = AMMO_EXPLOSION_THRESHOLDS

    # Find applicable threshold (highest that applies)
    target_number = None
    for threshold, target in sorted(thresholds.items(), reverse=True):
        if heat >= threshold:
            target_number = target
            break

    # No explosion risk
    if target_number is None:
        return True  # Avoided (no risk)

    # Roll to avoid
    roll = source_roll('ammo_avoidance', roll_2d6)
    return roll >= target_number


def check_shutdown(mech: 'Mech') -> tuple[bool, bool]:
    """
    Check if mech shuts down due to heat.

    At certain heat levels, the pilot must roll to avoid shutdown.

    Reference: HandleOverheat() in mech.update.c lines 1262-1322

    Args:
        mech: The mech to check

    Returns:
        Tuple of (shutdown, avoided):
        - shutdown: True if mech shuts down
        - avoided: True if shutdown was successfully avoided
    """
    heat = mech.heat

    # Find applicable threshold
    target_number = None
    for threshold, target in sorted(SHUTDOWN_THRESHOLDS.items(), reverse=True):
        if heat >= threshold:
            target_number = target
            break

    # Below 14 there is no shutdown risk, even when ammunition checks are due.
    if target_number is None:
        return (False, False)

    # 30+ heat is automatic shutdown
    if target_number >= 99:
        return (True, False)

    # Roll to avoid
    roll = source_roll('shutdown_rolls', roll_2d6)
    avoided = roll >= target_number

    return (not avoided, avoided)


def check_pilot_damage(mech: 'Mech', life_support_destroyed: bool = False) -> int:
    """
    Check for pilot damage from heat.

    Pilots take damage at high heat levels, especially with life support destroyed.

    Reference: UpdateHeat() in mech.update.c lines 1494-1512

    Args:
        mech: The mech to check
        life_support_destroyed: Whether life support is destroyed

    Returns:
        Amount of pilot damage to apply
    """
    from entities.mech import CritStatus

    heat = mech.heat

    # Check if life support is destroyed (from crit status)
    if not life_support_destroyed:
        life_support_destroyed = mech.has_crit_status(CritStatus.LIFE_SUPPORT_DESTROYED)

    # Pilot damage only with life support destroyed or extreme heat
    if not life_support_destroyed and heat <= 30.0:
        return 0

    # Additional check: at heat > 30, 50% chance of damage even with life support
    if not life_support_destroyed and heat > 30.0:
        if draw('heat_injury', 0, 1, lambda: random.randint(0, 1)) == 1:
            return 0

    # Apply damage based on heat level
    if heat > 25.0:
        return 2 if life_support_destroyed else 1
    elif heat >= 15.0:
        return 1

    return 0


def check_overheat(mech: 'Mech', tick: int, has_inferno: Optional[bool] = None) -> HeatResult:
    """
    Check all overheat effects.

    This is called to check for shutdown, ammo explosion, and pilot damage.
    Overheat checks only happen once per TURN (30 seconds).

    When ammo explosion occurs, this now actually triggers the explosion
    using the criticals system.

    Reference: HandleOverheat() in mech.update.c

    Args:
        mech: The mech to check
        tick: Current game tick (for TURN timing)
        has_inferno: Whether mech has inferno ammo (auto-detected if None)

    Returns:
        HeatResult with overheat effects
    """
    result = HeatResult()
    result.new_heat = mech.heat

    # Heat must be >= 10 for any overheat effects
    if mech.heat < 10.0:
        return result

    # Overheat checks happen once per TURN
    # Check if it's been a full TURN since last check
    last_check = getattr(mech, '_last_overheat_tick', 0)
    if (tick - last_check) < TURN:
        return result

    # Update last check time
    mech._last_overheat_tick = tick

    # Auto-detect inferno ammo if not specified.  The C only looks for
    # inferno ammo at all under btech_inferno_penalty (HandleOverheat,
    # mech.update.c:1203-1204; conf.c:144 default 0) — without it,
    # inferno bins neither raise the cook-off risk nor take precedence.
    if has_inferno is None:
        has_inferno = (bool(getattr(mech._engine, 'inferno_penalty', BTECH_INFERNO_PENALTY)) and
                       has_inferno_ammo(mech))

    # Check for ammo explosion first (can cause shutdown)
    ammo_avoided = check_ammo_explosion(mech, has_inferno)
    if not ammo_avoided:
        result.ammo_explosion = True

        # Actually trigger the explosion!
        explosion_result = trigger_heat_ammo_explosion(mech)
        if explosion_result is not None:
            result.ammo_explosion_damage = explosion_result.damage
            result.ammo_explosion_location = -1  # Location handled by explosion
            result.mech_destroyed = explosion_result.mech_destroyed
            result.pilot_damage += explosion_result.pilot_damage
            result.messages.append(explosion_result.message)
        else:
            result.ammo_explosion = False
            message = 'You have no ammunition, lucky you!'
            from systems.movement_commands import notify
            notify(mech, message)
            result.messages.append(message)

    # The source still consumes the shutdown roll after an ammunition death.
    result.shutdown, result.shutdown_avoided = check_shutdown(mech)
    if result.shutdown and mech.is_started:
        apply_shutdown(mech)

    return result


def apply_shutdown(mech):
    """Overheat's ordered notices, falling, and shared Shutdown/StopMoving tail."""
    from entities.mech import MechStatus as S, MechStatus2 as S2, CritStatus
    from physics.heights import AERO_TYPES
    from systems.piloting import make_piloting_roll
    from physics.jump import mech_falls
    from physics.collision import jump_speed_mp
    from physics.collision import domino_space
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    if not mech.is_started:
        return
    notify(mech, '%ci%crReactor shutting down...%c')
    if mech.has_status2(S2.SLITE_ON):
        notify(mech, 'Your searchlight shuts off.')
        mech.clear_status2(S2.SLITE_ON)
        mech.clear_crit_status(CritStatus.SLITE_LIT)
    if mech.is_jumping or mech.cocoon or (mech.unit_type in AERO_TYPES and not mech.has_status(S.LANDED)):
        notify(mech, '%chYou fall from the sky!!!!!%c' if mech.unit_type in AERO_TYPES else '%chYou fall from the sky!%c')
        los_broadcast(mech, 'falls from the sky!')
        mech_falls(mech, jump_speed_mp(mech, mech.map), notify_fall=False)
        if mech.map is not None:
            domino_space(mech, 2)
    else:
        los_broadcast(mech, 'stops in mid-motion!')
        # Recovered Aerospace source applies fabs to the comparison itself.
        moving = mech.speed > KPH_PER_MP if mech.unit_type in AERO_TYPES else abs(mech.speed) > KPH_PER_MP
        if moving and not mech.is_fallen and not make_piloting_roll(mech, 3).success:
            mech_falls(mech, 0)
    from systems.startup import shutdown_state
    shutdown_state(mech._engine, mech)


def can_startup(mech: 'Mech') -> Tuple[bool, str]:
    """
    Check if a mech can attempt startup.

    Startup is blocked if:
    - Mech is already started
    - Mech is destroyed
    - Heat is above STARTUP_HEAT_IMPOSSIBLE_THRESHOLD (14)

    Reference: mech.startup.c

    Args:
        mech: The mech to check

    Returns:
        Tuple of (can_start, reason_message)
    """
    from entities.mech import MechStatus

    # Already started
    if mech.has_status(MechStatus.STARTED):
        return (False, "Mech is already running")

    # Destroyed
    if mech.has_status(MechStatus.DESTROYED):
        return (False, "Mech is destroyed")

    # Heat too high
    if mech.heat > STARTUP_HEAT_IMPOSSIBLE_THRESHOLD:
        return (False, f"Heat too high to restart (>{STARTUP_HEAT_IMPOSSIBLE_THRESHOLD})")

    return (True, "")


def attempt_startup(mech: 'Mech') -> StartupResult:
    """
    Attempt to start a mech.

    If heat is >= STARTUP_HEAT_PILOTING_THRESHOLD (9), a piloting check
    is required with a +3 modifier to difficulty.

    If heat is > STARTUP_HEAT_IMPOSSIBLE_THRESHOLD (14), startup fails
    automatically.

    Reference: mech.startup.c HandleStartup()

    Args:
        mech: The mech to start

    Returns:
        StartupResult with the outcome
    """
    from entities.mech import MechStatus
    from systems.piloting import find_pilot_piloting

    result = StartupResult()

    # Check if startup is possible
    can_start, reason = can_startup(mech)
    if not can_start:
        if mech.heat > STARTUP_HEAT_IMPOSSIBLE_THRESHOLD:
            result.heat_blocked = True
        result.message = reason
        return result

    # Check if piloting check is required (hot startup)
    if mech.heat >= STARTUP_HEAT_PILOTING_THRESHOLD:
        result.piloting_required = True

        # Calculate piloting target
        # Base skill (typically 5) + modifier (3) + any damage mods.
        # Skill comes from the FindPilotPiloting chain (mech.utils.c:580-590);
        # damage_mod is the C MechPilotSkillBase (mech.h:814).
        base_skill = find_pilot_piloting(mech)
        damage_mod = getattr(mech, 'pilot_skill_base', 0)
        result.piloting_target = base_skill + STARTUP_PILOTING_MODIFIER + damage_mod

        # Roll 2d6
        result.piloting_roll = roll_2d6()

        if result.piloting_roll < result.piloting_target:
            result.success = False
            result.message = (
                f"Hot startup failed! Rolled {result.piloting_roll} vs "
                f"{result.piloting_target} (skill {base_skill} + {STARTUP_PILOTING_MODIFIER} heat mod)"
            )
            return result
        else:
            result.message = (
                f"Hot startup successful! Rolled {result.piloting_roll} vs "
                f"{result.piloting_target}"
            )
    else:
        result.message = "Startup sequence complete"

    # Startup succeeds
    result.success = True
    mech.set_status(MechStatus.STARTED)
    mech.per = getattr(mech.pilot, 'perception', 6)
    if mech._engine is not None and mech.map is not None:
        from systems.targeting import start_plos_event
        start_plos_event(mech._engine, mech)

    return result


# =============================================================================
# Heat-Triggered Ammo Explosion System
# =============================================================================

@dataclass
class AmmoBin:
    """Represents an ammo bin location on a mech."""
    location: int                    # Section location
    slot: int                        # Critical slot index
    ammo_count: int                  # Rounds remaining
    weapon_damage: int = 1           # Damage per round
    missiles_per_shot: int = 1       # For missile weapons
    is_inferno: bool = False         # Inferno ammo?
    is_gauss: bool = False           # Gauss ammo (doesn't explode)


def find_ammo_bins(mech: 'Mech', *, inferno_only=False) -> List[AmmoBin]:
    """
    Find all ammo bins on a mech that could explode.

    Searches the source critical-slot array, skipping destroyed bins and,
    when requested, non-inferno modes before catalog access. Empty eligible
    bins still resolve their catalog entries; positive damage is selected below.
    Each bin's explosion characteristics come from the weapon the ammo belongs
    to: the ammo type byte IS the weapon index, offset by AMMO_BASE_INDEX.

    This is the heat cook-off's bin search, so the C analogues are
    FindDestructiveAmmo / FindInfernoAmmo - the two functions HandleOverheat
    actually calls (mech.update.c:1204, 1245).  They filter on
    `IsAmmo(type) && !PartIsDestroyed(...)` (not PartIsNonfunctional, and no
    ammo-mode masks - that is findAmmoInSection, mech.utils.c:1301-1321, which is
    the *firing* path's per-section lookup), take damage from the owning weapon
    and skip GAUSS only.

    Selection of the bin that actually cooks off is
    find_destructive_ammo() below — the single MAX-damage bin, as the C's
    functions return (mech.utils.c:1556-1560, 1594-1598).

    Reference:
    - mech.utils.c lines 1530-1562 (FindDestructiveAmmo)
    - mech.utils.c lines 1564-1600 (FindInfernoAmmo)
    - crit.c lines 1698-1704 (weapindx / damage / missile salvo)

    Args:
        mech: The mech to search

    Returns:
        List of AmmoBin objects representing exploitable ammo
    """
    from entities.crittypes import ammo2weapon_i, crits_in_loc, is_ammo
    from entities.mech import FireMode, NUM_SECTIONS, NUM_CRITICALS
    from entities.weapon import (
        WeaponFlags,
        WeaponType,
        get_weapon_by_index,
    )
    from systems.criticals import AMMO_INFERNO_MODE

    ammo_bins = []

    for loc_idx in range(NUM_SECTIONS):
        section = mech.sections[loc_idx]

        for slot_idx in range(NUM_CRITICALS):
            crit = section.criticals[slot_idx]

            # Empty eligible bins still resolve their source catalog entry.
            if not is_ammo(crit.type):
                continue
            if crit.firemode & FireMode.DESTROYED_MODE:
                continue
            if inferno_only and not crit.ammomode & AMMO_INFERNO_MODE:
                continue

            weapon = get_weapon_by_index(ammo2weapon_i(crit.type))
            if weapon is None:
                raise ValueError(f'Unsupported ammunition catalog index: {ammo2weapon_i(crit.type)}')

            # Missiles and artillery multiply by the full salvo (crit.c:1700-
            # 1704 uses num_missiles[10], the roll-12 column).
            from systems.ammo_dump import ammo_full_salvo
            missiles_per_shot = ammo_full_salvo(weapon)

            # Only GAUSS suppresses a heat cook-off: FindDestructiveAmmo
            # `continue`s on `special & GAUSS` alone (mech.utils.c:1547-1548), so
            # NOBOOM ammo (e.g. IS.PlasmaRifle, weapons.h:342-343) DOES cook off
            # from heat.  GAUSS|NOBOOM is the *crit* path's test (crit.c:1705),
            # which lives in systems.criticals.apply_ammo_critical.
            # Inferno is a per-bin ammo mode, not a weapon property (mech.h:643;
            # FindInfernoAmmo tests it at mech.utils.c:1581-1583).
            ammo_bins.append(AmmoBin(
                location=loc_idx,
                slot=slot_idx,
                ammo_count=crit.data,
                weapon_damage=weapon.damage,
                missiles_per_shot=missiles_per_shot,
                is_inferno=bool(crit.ammomode & AMMO_INFERNO_MODE),
                is_gauss=bool(weapon.special & WeaponFlags.GAUSS),
            ))

    return ammo_bins


def find_destructive_ammo(mech: 'Mech',
                          inferno_only: bool = False) -> Optional[AmmoBin]:
    """
    The single most destructive live ammo bin — the one a heat cook-off
    detonates.

    Port of FindDestructiveAmmo (mech.utils.c:1530-1562) and, with
    inferno_only, FindInfernoAmmo (:1564-1600): rounds x weapon damage
    (x roll-12 salvo for missiles/artillery), GAUSS skipped, MAX wins.
    Ties keep the first-found bin, as the C's strict > does.
    """
    best = None
    best_damage = 0
    for b in find_ammo_bins(mech, inferno_only=inferno_only):
        if b.is_gauss:
            continue
        if inferno_only and not b.is_inferno:
            continue
        damage = b.ammo_count * b.weapon_damage * b.missiles_per_shot
        if damage > best_damage:
            best = b
            best_damage = damage
    return best


def trigger_heat_ammo_explosion(mech: 'Mech') -> Optional['AmmoExplosionResult']:
    """
    Trigger an ammo explosion due to heat.

    Finds a random ammo bin and detonates it using the criticals
    system's ammo_explosion() function.

    Reference: mech.update.c HandleOverheat() ammo explosion code

    Args:
        mech: The mech experiencing the explosion

    Returns:
        AmmoExplosionResult or None if no ammo to explode
    """
    from entities.mech import Location, FireMode
    from systems.criticals import ammo_explosion, AmmoExplosionResult

    # The MAX-damage bin cooks off; with btech_inferno_penalty on, a
    # live inferno bin takes precedence (HandleOverheat,
    # mech.update.c:1243-1247)
    ammo_bin = None
    if getattr(mech._engine, 'inferno_penalty', BTECH_INFERNO_PENALTY):
        ammo_bin = find_destructive_ammo(mech, inferno_only=True)
    if ammo_bin is None:
        ammo_bin = find_destructive_ammo(mech)

    if ammo_bin is None:
        return None

    # Trigger the explosion through criticals system
    result = ammo_explosion(
        mech=mech,
        location=Location(ammo_bin.location),
        ammo_rounds=ammo_bin.ammo_count,
        weapon_damage=ammo_bin.weapon_damage,
        missiles_per_shot=ammo_bin.missiles_per_shot,
        is_inferno=ammo_bin.is_inferno,
        is_gauss=ammo_bin.is_gauss,
        # The heat cook-off is self-inflicted: the C passes the mech as its own
        # attacker, `ammo_explosion(mech, mech, ...)` (mech.update.c:1245), so
        # the !attacker early-out at mech.update.c:1157-1158 does not apply.
        attacker=mech,
        slot=ammo_bin.slot,
    )

    return result


def has_inferno_ammo(mech: 'Mech') -> bool:
    """
    Check for a positive-damage, non-Gauss inferno bin (FindInfernoAmmo).

    Inferno ammo is more dangerous at high heat (lower explosion
    threshold) so this is used to determine which explosion table
    to use.

    Args:
        mech: The mech to check

    Returns:
        True if mech has inferno ammo
    """
    return find_destructive_ammo(mech, inferno_only=True) is not None


# =============================================================================
# Combined Heat Update
# =============================================================================

def update_from_environment(mech: 'Mech', tick: int) -> HeatResult:
    """Update using the unit's actual water, height and special-map state.

    Shared by the standard dispatcher and explicit maintenance adapters.
    Full_heat_update remains available for callers supplying an environment.
    """
    from entities.mech import MechStatus
    from systems.movement_commands import in_water

    special = (mech.has_status(MechStatus.UNDERSPECIAL)
               and mech.map is not None and mech.map.flags & 2)
    temperature = mech.map.temp if special else TEMP_STANDARD
    return full_heat_update(mech, tick=tick, in_water=in_water(mech),
                            water_depth=mech.z, map_temperature=temperature)


def full_heat_update(
    mech: 'Mech',
    tick: int,
    in_water: bool = False,
    water_depth: int = 0,
    map_temperature: int = TEMP_STANDARD,
    has_inferno: Optional[bool] = None
) -> HeatResult:
    """
    Perform a full heat update including overheat checks.

    This is the main function called by the game loop.
    It updates heat levels and checks for overheat effects.

    Args:
        mech: The mech to update
        tick: Current game tick
        in_water: Whether in water
        water_depth: Water depth
        map_temperature: Map temperature in Celsius (default 25)
        has_inferno: Whether mech has inferno ammo (auto-detected if None)

    Returns:
        Combined HeatResult
    """
    from entities.mech import UnitType

    # Units without heat don't get updates
    if mech.unit_type not in (UnitType.MECH, UnitType.AERO):
        return HeatResult()

    # Update heat level with temperature effects
    result = update_heat(mech, in_water, water_depth, map_temperature)

    from systems.movement_commands import notify
    from systems.notifications import MECHPILOT
    injury = check_pilot_damage(mech) if tick % TURN == 0 else 0
    if injury:
        from systems.piloting import head_hit_mw_damage
        message = 'You take personal injury from heat!!' if mech.unit_type == UnitType.AERO else 'You take personal injury from heat!'
        notify(mech, message, MECHPILOT)
        result.messages.append(message)
        head_hit_mw_damage(mech, mech, injury)
    if result.heat_level_changed:
        color = result.new_heat_level
        prefix, width, label = {'red': ('%ch%cr', 37, 'RED!'), 'yellow': ('%ch%cy', 39, 'YELLOW'), 'green': ('%cg', 38, 'GREEN')}[color]
        lines = (prefix + '=' * width, 'Your Excess Heat indicator turns ' + label, '=' * width + '%c')
        # The recovered aircraft source emits three notifications; general C
        # combines the same banner into one multiline notification.
        for message in lines if mech.unit_type == UnitType.AERO else ('\n'.join(lines),):
            notify(mech, message)
            result.messages.append(message)

    # Check overheat effects (has_inferno auto-detected if None)
    overheat_result = check_overheat(mech, tick, has_inferno)

    # Merge overheat results into heat result
    result.shutdown = overheat_result.shutdown
    result.shutdown_avoided = overheat_result.shutdown_avoided
    result.ammo_explosion = overheat_result.ammo_explosion
    result.ammo_explosion_damage = overheat_result.ammo_explosion_damage
    result.ammo_explosion_location = overheat_result.ammo_explosion_location
    result.mech_destroyed = overheat_result.mech_destroyed
    result.pilot_damage = injury + overheat_result.pilot_damage
    result.messages.extend(overheat_result.messages)

    return result


# =============================================================================
# Game Loop Integration
# =============================================================================

def heat_periodic(engine: 'GameEngine') -> None:
    """
    Periodic heat update for all registered mechs.

    This is registered with the game engine to run every HEAT_TICK.

    Args:
        engine: The game engine
    """
    from entities.mech import Mech

    tick = engine.tick

    for entity in engine.get_entities():
        if isinstance(entity, Mech):
            # Simplified: not tracking water state per entity yet
            full_heat_update(entity, tick)


def register_heat_system(engine: 'GameEngine') -> None:
    """
    Register the heat system with the game engine.

    This sets up the periodic heat updates.

    Args:
        engine: The game engine to register with
    """
    engine.register_periodic("heat", HEAT_TICK, heat_periodic)
