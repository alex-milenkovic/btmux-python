# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/bsuit.c
#   btech/crit.c
#   btech/mech.c3.c
#   btech/mech.damage.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   src/conf.c
# Historical Aerospace sources:
#   btech/bsuit.c
#   btech/crit.c
#   btech/mech.damage.c
#   btech/mech.update.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.h

"""
Critical hit effects system for BTMux Python reimplementation.

This module implements critical hit effects for all equipment types:
- ENGINE: +5 heat per hit, 3rd hit = destruction
- GYRO: +3 pilot skill, immediate fall check; 2nd = destroyed
- SENSORS: 1st: half range, +2 BTH; 2nd: blind (+75 BTH)
- LIFE_SUPPORT: Heat damage to pilot doubled
- COCKPIT: Instant pilot death
- SHOULDER/HIP: +4 BTH with limb, speed/2 for hip
- ACTUATORS: +1 BTH per, -1 MP per leg actuator

Also handles ammo explosions with CASE support.

Weapon and ammo crits are dispatched by crit-slot namespace range rather than by
enum member - see entities/crittypes.py.

Reference:
- BTMux btech/src/btech/crit.c - HandleMechCrit() (lines 1670-2344)
- BTMux btech/src/btech/crit.c - handleWeaponCrit() (lines 338-484)
- BTMux btech/src/btech/mech.damage.c - DestroyWeapon() (lines 809-847)
- BTMux btech/src/btech/mech.update.c - ammo_explosion() (lines 1142-1186)
"""

from __future__ import annotations
import random
from entities.mech import CritStatus, FireMode, MoveType, Location, UnitType, MechStatus, Specials
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Callable, List

from entities.crittypes import (
    EMPTY,
    Special,
    ammo2weapon_i,
    crits_in_loc,
    is_ammo,
    i2special,
    is_special,
    is_weapon,
    special2i,
    weapon2i,
)

if TYPE_CHECKING:
    from entities.mech import Mech, Location


# =============================================================================
# Equipment Type Constants (from mech.h)
# =============================================================================

# The C has no "equipment type" enum: a crit slot's type byte is a segmented
# namespace (see entities/crittypes.py) and the handlers below are keyed off the
# Special *sub*-index, i.e. Special2I(type).  EquipmentType is kept as the
# port's historical name for that sub-index enum.
#
# Weapons and ammo are deliberately absent: they are namespace RANGES
# (mech.h:123,128), not members, and are dispatched by is_weapon()/is_ammo().
#
# Reference: mech.h lines 163-215 (the Special sub-index list)
EquipmentType = Special


# =============================================================================
# Critical Hit Constants
# =============================================================================

# Engine critical effects
ENGINE_HEAT_PER_HIT = 5       # +5 heat per engine critical
ENGINE_HITS_TO_DESTROY = 3    # 3rd hit destroys engine

# Gyro critical effects
GYRO_PILOTING_MODIFIER = 3    # +3 to piloting skill per gyro hit
GYRO_HITS_TO_DESTROY = 2      # 2nd hit destroys gyro

# Sensor critical effects
SENSORS_BTH_MODIFIER_1 = 2    # +2 BTH on first sensor hit
SENSORS_BTH_MODIFIER_2 = 75   # +75 BTH (blind) on second sensor hit

# Actuator critical effects
SHOULDER_ARM_BTH_MODIFIER = 4      # +4 BTH for weapons in arm with shoulder crit
HIP_PILOTING_MODIFIER = 2          # +2 to piloting with hip crit
HIP_DESTROYED_PILOTING_MODIFIER = 4  # +4 when hip destroyed (second hit)
ACTUATOR_BTH_MODIFIER = 1          # +1 BTH per actuator crit
ACTUATOR_PILOTING_MODIFIER = 1     # +1 piloting per leg actuator crit

# Ammo explosion
AMMO_EXPLOSION_PILOT_DAMAGE = 2    # Pilot takes 2 damage from ammo explosion

# mudconf.btech_inferno_penalty (conf.c:144, default 0): +30 weapon heat
# when your own inferno ammo cooks off
BTECH_INFERNO_PENALTY = 0

# Ammo mode bit for SRMs loaded with Inferno rounds - lives in the crit slot's
# ammomode byte, not on the weapon.
# Reference: mech.h line 643 (INFERNO_MODE 0x00000040)
AMMO_INFERNO_MODE = 0x00000040

# Specials that occupy crit slots but can never take a critical hit: armour and
# structure fillers plus the myomer/MASC/supercharger group.
# Reference: crit.c lines 2402-2410 (the critList exclusion chain)
UNCRITTABLE_SPECIALS = frozenset({
    Special.CASE,
    Special.FERRO_FIBROUS,
    Special.STEALTH_ARMOR,
    Special.HVY_FERRO_FIBROUS,
    Special.LT_FERRO_FIBROUS,
    Special.ENDO_STEEL,
    Special.TRIPLE_STRENGTH_MYOMER,
    Special.SUPERCHARGER,
    Special.MASC,
})


# =============================================================================
# Data Structures
# =============================================================================

NO_EQUIPMENT_TYPE = -1
"""
Sentinel for "this result is not about a Special sub-index".

It cannot be confused with a real one: the C's Special list starts at
SHOULDER_OR_HIP 0 (mech.h:164), so 0 is a legitimate value and cannot double as
"nothing".  The C never needs a sentinel because it only ever computes
Special2I(critType) *after* IsSpecial(critType) has passed (crit.c:1859-1861) -
a crit type and a Special sub-index never share a variable there.  Empty-slot,
weapon and ammo results leave the field at this value.
"""


@dataclass
class CriticalResult:
    """Result of applying a critical hit."""
    # A Special sub-index (mech.h:163-215) for equipment crits, else
    # NO_EQUIPMENT_TYPE.  Typed int, not EquipmentType, because the sentinel is
    # deliberately outside the enum.
    equipment_type: int = NO_EQUIPMENT_TYPE
    equipment_name: str = ""
    effect_applied: bool = False
    mech_destroyed: bool = False
    pilot_killed: bool = False
    pilot_damage: int = 0
    piloting_check_required: bool = False
    piloting_modifier: int = 0
    fell: bool = False
    message: str = ""
    messages: List[str] = field(default_factory=list)


@dataclass
class AmmoExplosionResult:
    """Result of an ammo explosion."""
    damage: int = 0
    heat_added: float = 0.0
    pilot_damage: int = 0
    was_inferno: bool = False
    contained_by_case: bool = False
    mech_destroyed: bool = False
    message: str = ""


# =============================================================================
# Equipment Name Lookup
# =============================================================================

EQUIPMENT_NAMES = {
    EquipmentType.LIFE_SUPPORT: "Life Support",
    EquipmentType.COCKPIT: "Cockpit",
    EquipmentType.SENSORS: "Sensors",
    EquipmentType.HEAT_SINK: "Heat Sink",
    EquipmentType.JUMP_JET: "Jump Jet",
    EquipmentType.ENGINE: "Engine",
    EquipmentType.GYRO: "Gyro",
    EquipmentType.SHOULDER_OR_HIP: "Shoulder/Hip",
    EquipmentType.UPPER_ACTUATOR: "Upper Actuator",
    EquipmentType.LOWER_ACTUATOR: "Lower Actuator",
    EquipmentType.HAND_OR_FOOT_ACTUATOR: "Hand/Foot Actuator",
    EquipmentType.TARGETING_COMPUTER: "Targeting Computer",
    EquipmentType.C3_MASTER: "C3 Master",
    EquipmentType.C3_SLAVE: "C3 Slave",
    EquipmentType.C3I: "C3i",
    EquipmentType.TAG: "TAG",
    EquipmentType.ECM: "ECM",
    EquipmentType.ANGELECM: "Angel ECM",
    EquipmentType.BEAGLE_PROBE: "Beagle Active Probe",
    EquipmentType.BLOODHOUND_PROBE: "Bloodhound Probe",
    EquipmentType.LIGHT_BAP: "Light Beagle Probe",
    EquipmentType.AXE: "Axe",
    EquipmentType.SWORD: "Sword",
    EquipmentType.MACE: "Mace",
}


def get_equipment_name(equip_type: EquipmentType, location: 'Location') -> str:
    """Get human-readable name for equipment, considering location context."""
    from entities.mech import Location

    if equip_type == EquipmentType.SHOULDER_OR_HIP:
        if location in (Location.LARM, Location.RARM):
            return "Shoulder"
        return "Hip"

    if equip_type == EquipmentType.HAND_OR_FOOT_ACTUATOR:
        if location in (Location.LARM, Location.RARM):
            return "Hand Actuator"
        return "Foot Actuator"

    if equip_type in (EquipmentType.UPPER_ACTUATOR, EquipmentType.LOWER_ACTUATOR):
        if location in (Location.LARM, Location.RARM):
            prefix = "Upper" if equip_type == EquipmentType.UPPER_ACTUATOR else "Lower"
            return f"{prefix} Arm Actuator"
        else:
            prefix = "Upper" if equip_type == EquipmentType.UPPER_ACTUATOR else "Lower"
            return f"{prefix} Leg Actuator"

    return EQUIPMENT_NAMES.get(equip_type, "Unknown Equipment")


# =============================================================================
# Location Helpers
# =============================================================================

def is_arm_location(location: 'Location') -> bool:
    """Check if location is an arm (for biped mechs)."""
    from entities.mech import Location
    return location in (Location.LARM, Location.RARM)


def is_leg_location(location: 'Location') -> bool:
    """Check if location is a leg."""
    from entities.mech import Location
    return location in (Location.LLEG, Location.RLEG)


def is_torso_location(location: 'Location') -> bool:
    """Check if location is a torso."""
    from entities.mech import Location
    return location in (Location.LTORSO, Location.RTORSO, Location.CTORSO)


# =============================================================================
# Critical Effect Handlers
# =============================================================================

def handle_engine_critical(mech, location, attacker=None, engine=None):
    from systems.damage import destroy_mech, KILL_TYPE_ENGINE, KILL_TYPE_NORMAL, unit_is_fixable
    from systems.parts import armor_string
    from systems.sensors import los_broadcast
    result = CriticalResult(equipment_type=Special.ENGINE, equipment_name='Engine', effect_applied=True)
    historic = _historical_aero(mech)
    if not mech.is_destroyed and mech.is_started:
        los_broadcast(mech, f"'s {armor_string(mech, location)} spews black smoke!")
    mech.engine_hits = getattr(mech, 'engine_hits', 0) + 1
    if mech.engine_heat < 10:
        mech.engine_heat += 5
        _critical_notice(mech, result, "Your engine shielding takes a hit!  It's getting hotter in here!!" if historic else "Your engine shielding takes a hit! It's getting hotter in here!")
    elif mech.engine_heat < 15:
        mech.engine_heat = 15
        _critical_notice(mech, result, 'Your engine is destroyed!!' if historic else 'Your engine is destroyed!')
        if attacker is not None and attacker is not mech and not mech.is_destroyed:
            from systems.damage import _notify
            _notify(attacker, 'You destroy the engine!!' if historic else 'You destroy the engine!')
        destroy_mech(mech, attacker, True, KILL_TYPE_NORMAL if historic or not unit_is_fixable(mech) else KILL_TYPE_ENGINE, engine)
        result.mech_destroyed = True
    return result


def handle_gyro_critical(mech: 'Mech', location: 'Location') -> CriticalResult:
    """
    Handle gyro critical hit.

    Effects:
    - 1st hit: +3 to piloting skill, immediate piloting check
    - 2nd hit: Gyro destroyed, automatic fall, cannot stand

    Reference: crit.c lines 1985-2048
    """
    from entities.mech import CritStatus, MechStatus

    result = CriticalResult(
        equipment_type=EquipmentType.GYRO,
        equipment_name="Gyro"
    )

    # Check current gyro state
    gyro_damaged = mech.has_crit_status(CritStatus.GYRO_DAMAGED)
    gyro_destroyed = mech.has_crit_status(CritStatus.GYRO_DESTROYED)

    if gyro_destroyed:
        # Already destroyed, just more damage to non-functional gyro
        result.message = "Already-destroyed gyro takes another hit!"
        result.messages.append("Gyro is already destroyed")
        return result

    if not gyro_damaged:
        # First gyro hit
        mech.set_crit_status(CritStatus.GYRO_DAMAGED)
        mech.pilot_skill_base = getattr(mech, 'pilot_skill_base', 0) + GYRO_PILOTING_MODIFIER
        result.effect_applied = True
        result.piloting_check_required = True
        result.piloting_modifier = 0  # Standard check
        result.message = f"Gyro damaged! (+{GYRO_PILOTING_MODIFIER} to piloting checks)"
        result.messages.append("Gyro damaged - piloting check required!")
    else:
        # Second gyro hit - destroyed
        mech.set_crit_status(CritStatus.GYRO_DESTROYED)
        result.effect_applied = True
        result.piloting_check_required = True  # Will auto-fail
        result.message = "Gyro destroyed! Mech cannot balance!"
        result.messages.append("Gyro destroyed - mech will fall and cannot stand!")

        # Force fall if not already fallen
        if not mech.has_status(MechStatus.FALLEN):
            result.fell = True

    return result


def handle_sensors_critical(mech, location):
    result = CriticalResult(equipment_type=Special.SENSORS, equipment_name='Sensors', effect_applied=True)
    if not mech.has_crit_status(CritStatus.SENSORS_DAMAGED):
        mech.lrs_range //= 2
        mech.tac_range //= 2
        mech.scan_range //= 2
        mech.base_to_hit += 2
        mech.set_crit_status(CritStatus.SENSORS_DAMAGED)
        message = 'Your sensors have been damaged!'
    else:
        mech.lrs_range = mech.tac_range = mech.scan_range = 0
        mech.base_to_hit = 75
        message = 'Your sensors have been destroyed!'
    _critical_notice(mech, result, message + ('!' if _historical_aero(mech) else ''))
    return result


def handle_cockpit_critical(mech, location, attacker=None, engine=None, *, los=1):
    from systems.damage import destroy_mech, destroy_state, channel_emit_kill, _kill_mech_contents, _notify, KILL_TYPE_COCKPIT
    from systems.occupants import ensure_personnel
    from systems.sensors import los_broadcast
    historic = _historical_aero(mech)
    result = CriticalResult(equipment_type=Special.COCKPIT, equipment_name='Cockpit', effect_applied=True, pilot_killed=True, mech_destroyed=True)
    _critical_notice(mech, result, "Your cockpit is destroyed!!  Your body is fried!!!" if historic else "Your cockpit is destroyed, your blood boils, and your body is fried! %cyYou're dead!%cn")
    ensure_personnel(mech)
    if not mech.is_destroyed:
        if historic:
            destroy_state(mech, engine or mech._engine, historical=True)
            channel_emit_kill(mech, attacker)
        else:
            destroy_mech(mech, attacker, False, KILL_TYPE_COCKPIT, engine or mech._engine)
    if los and attacker is not None:
        _notify(attacker, "You destroy the cockpit!!  The pilot's blood splatters down the sides!!!" if historic else "You destroy the cockpit! The pilot's blood splatters down the sides!")
    los_broadcast(mech, 'spasms for a second then remains oddly still.')
    mech.pilot = None
    _kill_mech_contents(mech)
    return result


def handle_life_support_critical(mech, location):
    mech.set_crit_status(CritStatus.LIFE_SUPPORT_DESTROYED)
    result = CriticalResult(equipment_type=Special.LIFE_SUPPORT, equipment_name='Life Support', effect_applied=True)
    _critical_notice(mech, result, 'Your life support has been destroyed!!' if _historical_aero(mech) else 'Your life support has been destroyed!')
    return result


def handle_shoulder_hip_critical(
    mech: 'Mech',
    location: 'Location'
) -> CriticalResult:
    """
    Handle shoulder or hip critical hit.

    Effects:
    - Shoulder (arm): +4 BTH for weapons in that arm
    - Hip (leg): Speed halved, +2 piloting, piloting check required
                 2nd hip hit on biped = HIP_DESTROYED flag

    Reference: crit.c lines 2049-2083
    """
    from entities.mech import CritStatus, MoveType

    result = CriticalResult(
        equipment_type=EquipmentType.SHOULDER_OR_HIP
    )

    is_arm = is_arm_location(location)

    if is_arm:
        # Shoulder critical
        result.equipment_name = "Shoulder"

        # Add +4 BTH to weapons in this arm
        mech.sections[location].basetohit = SHOULDER_ARM_BTH_MODIFIER

        result.effect_applied = True
        result.message = f"Shoulder joint frozen! +{SHOULDER_ARM_BTH_MODIFIER} BTH for arm weapons"
        result.messages.append("Shoulder destroyed - arm weapons impaired")
    else:
        # Hip critical
        result.equipment_name = "Hip"

        hip_damaged = mech.has_crit_status(CritStatus.HIP_DAMAGED)

        if not hip_damaged:
            # First hip hit
            mech.set_crit_status(CritStatus.HIP_DAMAGED)

            # Halve max speed
            mech.max_speed = mech.max_speed / 2.0
            mech.clear_crit_status(CritStatus.SPEED_OK)

            # Add piloting modifier
            mech.pilot_skill_base = getattr(mech, 'pilot_skill_base', 0) + HIP_PILOTING_MODIFIER

            result.effect_applied = True
            result.piloting_check_required = True
            result.message = f"Hip damaged! Speed halved, +{HIP_PILOTING_MODIFIER} piloting"
            result.messages.append("Hip critical - piloting check required")
        else:
            # Second hip hit (only matters for bipeds)
            if mech.move_type != MoveType.QUAD:
                mech.set_crit_status(CritStatus.HIP_DESTROYED)
                result.effect_applied = True
                result.piloting_check_required = True
                result.message = "Hip destroyed!"
                result.messages.append("Hip destroyed - severe mobility impairment")
            else:
                # Quads can take multiple hip hits without HIP_DESTROYED
                result.effect_applied = True
                result.piloting_check_required = True
                result.message = "Another hip takes damage!"

    return result


def handle_actuator_critical(
    mech: 'Mech',
    location: 'Location',
    actuator_type: EquipmentType
) -> CriticalResult:
    """
    Handle actuator critical hit (upper, lower, hand/foot).

    Effects:
    - Arm actuators: +1 BTH for weapons in that arm
    - Leg actuators: -1 MP, +1 piloting, piloting check required

    Reference: crit.c lines 2084-2133
    """
    from entities.mech import CritStatus

    result = CriticalResult(
        equipment_type=actuator_type,
        equipment_name=get_equipment_name(actuator_type, location)
    )

    is_arm = is_arm_location(location)

    if is_arm:
        # Arm actuator - just BTH penalty
        mech.sections[location].basetohit = getattr(mech.sections[location], 'basetohit', 0) + ACTUATOR_BTH_MODIFIER

        result.effect_applied = True
        result.message = f"{result.equipment_name} destroyed! +{ACTUATOR_BTH_MODIFIER} BTH"
        result.messages.append("Arm actuator destroyed - reduced accuracy")
    else:
        # Leg actuator - MP loss, piloting penalty, check required
        # Only apply if hip isn't already destroyed (hip crit overrides)
        if not mech.has_crit_status(CritStatus.HIP_DAMAGED):
            # Reduce MP (approximately -10.75 KPH per MP)
            mp_loss = 10.75
            mech.max_speed = max(0, mech.max_speed - mp_loss)
            mech.clear_crit_status(CritStatus.SPEED_OK)

            # BTH penalty for leg weapons (if any)
            mech.sections[location].basetohit = getattr(mech.sections[location], 'basetohit', 0) + ACTUATOR_BTH_MODIFIER

            # Piloting penalty
            mech.pilot_skill_base = getattr(mech, 'pilot_skill_base', 0) + ACTUATOR_PILOTING_MODIFIER

            result.effect_applied = True
            result.piloting_check_required = True
            result.message = f"{result.equipment_name} destroyed! -1 MP, +{ACTUATOR_PILOTING_MODIFIER} piloting"
            result.messages.append("Leg actuator destroyed - piloting check required")
        else:
            # Hip crit overrides actuator crits
            result.effect_applied = True
            result.message = f"{result.equipment_name} destroyed! (hip already damaged)"

    return result


def handle_heat_sink_critical(mech, location, slot=-1):
    from systems.damage import heat_sink_size
    from systems.parts import armor_string
    from systems.sensors import los_broadcast
    result = CriticalResult(equipment_type=Special.HEAT_SINK, equipment_name='Heat Sink', effect_applied=True)
    double = bool(mech.specials & (Specials.DOUBLE_HEAT_TECH | Specials.CLAN_TECH))
    mech.real_num_sinks -= 2 if double else 1
    if double and slot >= 0:
        part_type = mech.sections[location].criticals[slot].type
        size = heat_sink_size(mech)
        first = slot if _historical_aero(mech) else find_first_weapon_crit(mech, location, slot, 0, part_type, size)
        destroy_weapon(mech, location, part_type, first, 1, size)
    _critical_notice(mech, result, 'You lost a heat sink!')
    if not mech.is_destroyed:
        los_broadcast(mech, f"'s {armor_string(mech, location)} is covered in a green mist!")
    return result


def handle_jump_jet_critical(mech: 'Mech', location: 'Location') -> CriticalResult:
    """
    Handle jump jet critical hit.

    Effects:
    - Lose 1 jump MP
    - If last jump jet destroyed while jumping, fall

    Reference: crit.c lines 1930-1955
    """
    from entities.mech import MechStatus

    result = CriticalResult(
        equipment_type=EquipmentType.JUMP_JET,
        equipment_name="Jump Jet"
    )

    # Reduce jump MP
    mech.jump_mp = max(0, getattr(mech, 'jump_mp', 0) - 1)

    result.effect_applied = True
    result.message = f"Jump jet destroyed! ({mech.jump_mp} MP remaining)"
    result.messages.append("Jump jet destroyed")

    # Check if jumping with no jets left
    if mech.jump_mp <= 0 and mech.has_status(MechStatus.JUMPING):
        result.fell = True
        result.messages.append("Lost last jump jet while jumping - falling!")

    return result


def handle_targeting_computer_critical(mech, location):
    result = CriticalResult(equipment_type=Special.TARGETING_COMPUTER, equipment_name='Targeting Computer')
    # The recovered Aerospace expression (!status & TC_DESTROYED) is always false.
    if not _historical_aero(mech) and not mech.has_crit_status(CritStatus.TC_DESTROYED):
        _critical_notice(mech, result, 'Your targeting computer is destroyed!')
        mech.set_crit_status(CritStatus.TC_DESTROYED)
        result.effect_applied = True
    return result


def calculate_ammo_damage(
    ammo_rounds: int,
    weapon_damage: int,
    missiles_per_shot: int = 1
) -> int:
    """
    Calculate damage from ammo explosion.

    Damage = rounds * weapon_damage * missiles_per_shot

    Reference: crit.c lines 1695-1704
    """
    return ammo_rounds * weapon_damage * missiles_per_shot


def apply_internal_damage_with_transfer(
    mech: 'Mech',
    location: 'Location',
    damage: int,
    attacker: Optional['Mech'] = None,
    engine=None,
) -> int:
    """
    Apply damage straight to internal structure, transferring inwards.

    This is the C's `intDamage` argument to DamageMech (arg 9 of the signature
    at mech.damage.c:334-343).  When `damage` is 0 (the gauss weapon-crit
    explosion, crit.c:383-385) or -1 (the ammo explosion,
    mech.update.c:1167-1170) the armour branch at mech.damage.c:702 is skipped
    entirely and the whole amount goes through cause_internaldamage
    (mech.damage.c:749-757) — crit rolls, the roll-12 limb blow-off and the
    stackpole-window trigger included.  Overflow transfers inwards as
    `damage=-2, intDamage=rest` (mech.damage.c:766-772), i.e. it stays
    internals-only all the way down — UNLESS the section has CASE or the
    unit is clan tech, which contain the blast (mech.damage.c:763-764).
    Running out of transfer targets destroys the unit
    (mech.damage.c:778-781).

    Returns total internal damage dealt.
    """
    from systems.combat import apply_damage_with_transfer
    return apply_damage_with_transfer(mech, location, damage, attacker=attacker,
                                      engine=engine, internal=True, transfer=True)


def ammo_explosion(
    mech: 'Mech',
    location: 'Location',
    ammo_rounds: int,
    weapon_damage: int,
    missiles_per_shot: int = 1,
    is_inferno: bool = False,
    is_gauss: bool = False,
    attacker: Optional['Mech'] = None,
    engine=None,
    slot=None,
) -> AmmoExplosionResult:
    """
    Handle ammunition explosion.

    Effects:
    - Gauss ammo: No explosion (just destroyed)
    - Normal ammo: Full damage to location internals
    - Inferno ammo: +30 heat, half damage
    - CASE: Contains explosion to that location
    - Pilot takes 2 damage

    With no attacker the C destroys the bin and returns immediately - no
    inferno heat, no location damage and no pilot injury
    (mech.update.c:1156-1158).  Destroying the bin is the caller's job here
    (apply_ammo_critical / trigger_heat_ammo_explosion), so this function only
    has the early return.  Both C callers do pass one: HandleMechCrit forwards
    the attacker (crit.c:1711) and the heat cook-off passes the mech itself
    (mech.update.c:1245, `ammo_explosion(mech, mech, ...)`).

    Reference: mech.update.c lines 1142-1186
    """
    from entities.mech import SectionConfig, MechStatus

    result = AmmoExplosionResult()

    # Gauss ammo doesn't explode
    if is_gauss:
        result.message = "Gauss ammo feed destroyed (no explosion)"
        return result

    # Calculate base damage
    result.damage = calculate_ammo_damage(ammo_rounds, weapon_damage, missiles_per_shot)

    if result.damage <= 0:
        result.message = "No ammunition to explode"
        return result

    from entities.mech import UnitType
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    if mech.unit_type == UnitType.MW:
        notify(mech, "Your weapon's ammo explodes!")
        los_broadcast(mech, "'s weapon's ammo explodes!")
    else:
        notify(mech, 'Ammunition explosion!')
        los_broadcast(mech, 'is suddenly enveloped by a brilliant fireball!' if is_inferno else 'has an internal ammo explosion!')
    if slot is not None:
        _destroy_part(mech.sections[location].criticals[slot])

    # if(!attacker) return; - mech.update.c:1157-1158.  The bin is already gone
    # by this point in the C (DestroyPart at 1156); nothing else happens.
    if attacker is None:
        result.message = (
            f"Ammunition explosion! {result.damage} damage "
            "(unattributed - no damage applied)"
        )
        return result

    # Handle inferno ammo (mech.update.c:1159-1164): the mech jellies
    # itself for damage/4 "missiles" worth of burn, weapon heat +30 only
    # under btech_inferno_penalty (conf.c:144, default 0), and the blast
    # halves.
    if is_inferno:
        result.was_inferno = True
        from systems.missile import inferno_hit
        inferno_hit(engine, mech, mech, result.damage // 4, 0)
        if getattr(engine or mech._engine, 'inferno_penalty', BTECH_INFERNO_PENALTY):
            mech.weap_heat += 30.0
            result.heat_added = 30.0
        result.damage = result.damage // 2
        result.message = f"Inferno ammo explodes! {result.damage} damage"
    else:
        result.message = f"Ammunition explosion! {result.damage} damage"

    # Internal damage with transfer.  The C passes damage = -1 and
    # intDamage = damage with isrear 0 (mech.update.c:1167-1170 against the
    # signature at mech.damage.c:334-343), so armour is never touched.
    # CASE is NOT special-cased here: the ammo section always takes the
    # full internal hit (crit rolls included); CASE/clan tech only stop
    # the inward transfer hop (mech.damage.c:763-764, handled inside
    # apply_internal_damage_with_transfer).  The CLASS_BSUIT armor-path
    # arm (mech.update.c:1166-1167) lands with bsuit.c.
    from entities.mech import Specials
    section = mech.sections[location]
    result.contained_by_case = bool(
        (section.config & SectionConfig.CASE_TECH) or
        (mech.specials & Specials.CLAN_TECH))
    from entities.mech import UnitType
    if mech.unit_type == UnitType.BSUIT:
        from systems.combat import apply_damage_with_transfer
        apply_damage_with_transfer(mech, location, result.damage, attacker=attacker, engine=engine)
    else:
        apply_internal_damage_with_transfer(mech, location, result.damage,
                                            attacker=attacker, engine=engine or mech._engine)

    # Pilot injury (mech.update.c:1175-1185): 2 bruise via headhitmwdamage,
    # 1 with pain_resistance; BSuits exempt
    from entities.mech import UnitType
    from systems.piloting import head_hit_mw_damage
    if mech.unit_type != UnitType.BSUIT:
        pilot = getattr(mech, 'pilot', None)
        from systems.characters import actor_advantage
        pain_resistance = actor_advantage(pilot, 'Pain_Resistance')
        result.pilot_damage = 1 if pain_resistance else 2
        notify(mech, "You take personal injury from the ammunition explosion!", 0)
        head_hit_mw_damage(mech, mech, result.pilot_damage)

    result.mech_destroyed = mech.is_destroyed

    return result


# =============================================================================
# Main Critical Hit Handler
# =============================================================================

# Equipment type to handler mapping
CRITICAL_HANDLERS = {
    EquipmentType.ENGINE: handle_engine_critical,
    EquipmentType.GYRO: handle_gyro_critical,
    EquipmentType.SENSORS: handle_sensors_critical,
    EquipmentType.COCKPIT: handle_cockpit_critical,
    EquipmentType.LIFE_SUPPORT: handle_life_support_critical,
    EquipmentType.SHOULDER_OR_HIP: handle_shoulder_hip_critical,
    EquipmentType.HEAT_SINK: handle_heat_sink_critical,
    EquipmentType.JUMP_JET: handle_jump_jet_critical,
    EquipmentType.TARGETING_COMPUTER: handle_targeting_computer_critical,
}


def handle_critical_hit(mech, location, equipment_type, critical_slot=-1, attacker=None, engine=None, *, los=1):
    if equipment_type in (Special.GYRO, Special.SHOULDER_OR_HIP, Special.UPPER_ACTUATOR,
                          Special.LOWER_ACTUATOR, Special.HAND_OR_FOOT_ACTUATOR, Special.JUMP_JET):
        return live_mobility_critical(mech, location, equipment_type, attacker, critical_slot)
    if equipment_type in (Special.C3_MASTER, Special.C3_SLAVE, Special.C3I, Special.ARTEMIS_IV,
                          Special.NULL_SIGNATURE_SYSTEM, Special.DS_MECHDOOR, Special.DS_AERODOOR,
                          Special.AXE, Special.SWORD, Special.MACE, Special.DUAL_SAW):
        return linked_equipment_critical(mech, location, critical_slot, equipment_type)
    if equipment_type in (Special.TAG, Special.ECM, Special.ANGELECM, Special.BEAGLE_PROBE,
                          Special.BLOODHOUND_PROBE, Special.LIGHT_BAP):
        return handle_sensor_equipment_critical(mech, equipment_type, attacker)
    if equipment_type == Special.COCKPIT:
        return handle_cockpit_critical(mech, location, attacker, engine, los=los)
    if equipment_type == Special.ENGINE:
        return handle_engine_critical(mech, location, attacker, engine)
    if equipment_type == Special.HEAT_SINK:
        return handle_heat_sink_critical(mech, location, critical_slot)
    handler = CRITICAL_HANDLERS.get(equipment_type)
    return handler(mech, location) if handler else CriticalResult(equipment_type=equipment_type)


def find_first_weapon_crit(
    mech: 'Mech',
    location: 'Location',
    slot: int,
    start_slot: int,
    crit_type: int,
    max_crits: int,
) -> int:
    """
    Find the first slot of the weapon run that `slot` belongs to.

    A weapon occupies `Weapon.crits` slots all carrying the same type byte, so
    "which weapon does slot N belong to" is the first matching slot at or after
    start_slot - unless the location holds more slots of that type than one
    weapon needs, i.e. two copies of the same weapon, in which case the C skips
    a full run's worth and recurses until `slot` falls inside the run.

    Pass slot == -1 to mean "the first run, whichever it is".

    Argument order and semantics follow the C exactly.

    Reference: mech.utils.c lines 2401-2445 (FindFirstWeaponCrit)
    """
    section = mech.sections[location]
    crits_here = 0
    first_crit = -1

    # This helper deliberately scans all twelve source slots, including
    # slots beyond the normal head/leg allocation (mech.utils.c:2414).
    for i in range(start_slot, 12):
        if section.criticals[i].type == crit_type:
            crits_here += 1
            if first_crit == -1:
                first_crit = i

    if first_crit > -1 and slot == -1:
        return first_crit

    # More slots of this type than one weapon uses: two of the same weapon in
    # this location. Walk past this run if `slot` isn't in it.
    # (mech.utils.c:2431-2442)
    if crits_here > max_crits:
        if (first_crit + max_crits) <= slot:
            first_crit = find_first_weapon_crit(
                mech, location, slot, first_crit + max_crits, crit_type,
                max_crits)

    return first_crit


def destroy_weapon(
    mech: 'Mech',
    location: 'Location',
    crit_type: int,
    start_crit: int,
    numcrits: int,
    totalcrits: int,
) -> int:
    """
    Set every slot of a weapon to destroyed/broken, walking forward by type.

    Faithful to the C's odd accounting: the first `numcrits` *undamaged* slots
    are destroyed outright, any already-damaged slot is destroyed, and the
    remainder are merely BROKEN (still nonfunctional - btmacros.h:324).  The
    walk stops once `totalcrits` matching slots have been seen.

    Returns the number of slots touched.

    Reference: mech.damage.c lines 809-847 (DestroyWeapon)
    """
    from entities.mech import FireMode, UnitType

    section = mech.sections[location]
    sum_left = totalcrits
    destroyed = numcrits
    touched = 0

    # Destruction includes populated padding slots, as does source enumeration.
    from entities.mech import NUM_CRITICALS
    for i in range(start_crit, NUM_CRITICALS):
        crit = section.criticals[i]
        if crit.type != crit_type:
            continue

        if crit.firemode & FireMode.DAMAGED_MODE:
            _destroy_part(crit)
        elif destroyed:
            _destroy_part(crit)
            destroyed -= 1
        else:
            crit.firemode |= FireMode.BROKEN_MODE

        touched += 1
        sum_left -= 1
        if not sum_left:
            return touched

    # Ran out of matching slots here with sum unspent: split-crit weapon —
    # tail-recurse into the other half (mech.damage.c:840-847).  The C
    # recurses with the split MARKER type and the marker's slot index.
    if mech.unit_type != UnitType.MECH:
        return touched
    from systems.enhanced_crits import get_split_data
    split = get_split_data(mech, location, start_crit)
    if split is not None:
        checkloc, newcrit, stype = split
        touched += destroy_weapon(mech, checkloc, stype, newcrit,
                                  destroyed, sum_left)
    return touched


def _destroy_part(crit) -> None:
    """
    Mark a crit slot destroyed, clearing the lesser damage states.

    The C also zeroes the temp-nuke (jam) nibble it keeps in the brand byte;
    clear that nibble while retaining the component brand.

    Reference: btmacros.h line 335 (DestroyPart)
    """
    from entities.mech import FireMode

    crit.firemode = (int(crit.firemode) | int(FireMode.DESTROYED_MODE)) & ~int(
        FireMode.BROKEN_MODE | FireMode.DISABLED_MODE | FireMode.DAMAGED_MODE)
    crit.weap_damage_flags = 0
    from systems.enhanced_crits import set_part_temp_nuke
    set_part_temp_nuke(crit, 0)


def _mark_weapon_state_destroyed(
    mech: 'Mech',
    location: 'Location',
    first_crit: int,
) -> None:
    """
    Flag the WeaponState that owns a crit run as unusable.

    The C has no WeaponState: the crit slots *are* the weapon, and every
    "can this fire" test walks them (PartIsNonfunctional, btmacros.h:324;
    WpnIsRecycling, btmacros.h:338-341).  The port keeps a parallel list on the
    mech, so it has to be kept in step.
    """
    for ws in mech.weapons:
        if ws.section == location and ws.critical == first_crit:
            ws.destroyed = True


def apply_weapon_critical(mech, location, slot, attacker=None, engine=None, *, los=1, special_only=False):
    """HandleMechCrit weapon branches and handleWeaponCrit's special chain.

    Vehicle destruction asks for only the special chain, then applies its own
    first-copy fallback without the enhanced critical table.
    """
    from entities.weapon import WeaponFlags, WeaponType, get_weapon_by_index
    from entities.mech import AmmoMode
    from systems.damage import _notify
    from systems.notifications import mech_notify, MECHPILOT
    from systems.sensors import los_broadcast
    from systems.parts import armor_string
    from systems.enhanced_crits import FAIL_DESTROYED, part_temp_nuke
    from systems.combat import apply_damage_with_transfer
    section = mech.sections[location]
    part = section.criticals[slot]
    weapon = get_weapon_by_index(weapon2i(part.type))
    result = CriticalResult(equipment_name=weapon.name if weapon else 'Weapon')
    if weapon is None:
        _destroy_part(part)
        return result
    name = weapon.name[3:]
    broken = FireMode.DESTROYED_MODE | FireMode.BROKEN_MODE
    nonfunctional = broken | FireMode.DISABLED_MODE
    if not special_only and part.firemode & broken and not part.firemode & FireMode.DISABLED_MODE:
        i = slot - 1
        while i > 0 and section.criticals[i].type == part.type:
            if section.criticals[i].firemode & FireMode.DESTROYED_MODE: break
            i -= 1
        result.message = f'Your destroyed {name} is damaged some more!'
        _notify(mech, result.message)
        _destroy_part(section.criticals[i+1])
        return result
    if not special_only and part.firemode & nonfunctional:
        result.message = f'Part of your non-working {name} has been hit!'
        _notify(mech, result.message)
        _destroy_part(part)
        return result
    size = weapon.crits if mech.unit_type == UnitType.MECH else 1
    first = find_first_weapon_crit(mech, location, slot, 0, part.type, size)
    if first < 0: first = slot
    first_slot = section.criticals[first]
    dead = first_slot.firemode & nonfunctional or part_temp_nuke(first_slot) == FAIL_DESTROYED
    historical = mech.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)
    destruction = f'Your {name} has been destroyed' + ('!!' if historical else '!')

    def explode(amount):
        destroy_weapon(mech, location, part.type, first, size, size)
        _mark_weapon_state_destroyed(mech, location, first)
        result.effect_applied = True
        result.message = destruction
        if attacker is not None:
            apply_damage_with_transfer(mech, location, 0, attacker=attacker,
                internal_damage=amount, cause=-1, bth=7, attack_pilot=-1,
                los=0, ignore_swarmers=True, engine=engine)
        result.mech_destroyed = mech.is_destroyed

    if weapon.special & WeaponFlags.GAUSS and not dead:
        _notify(mech, destruction)
        _notify(mech, f'It explodes for {weapon.explosive_damage} points damage' + ('' if historical else '.'))
        if historical:
            if los and attacker is not None and mech is not attacker:
                _notify(attacker, 'Your target is covered with a large electrical discharge')
        elif not mech.is_destroyed:
            los_broadcast(mech, f"'s {armor_string(mech, location)} is covered in a large electrical discharge!")
        explode(weapon.explosive_damage)
        if not historical and mech.unit_type != UnitType.BSUIT:
            from systems.piloting import head_hit_mw_damage
            from systems.characters import actor_advantage
            result.pilot_damage = 1 if actor_advantage(mech.pilot, 'Pain_Resistance') else 2
            mech_notify(mech, MECHPILOT, "You take personal injury from the weapon's explosion!")
            head_hit_mw_damage(mech, mech, result.pilot_damage)
            _check_pilot_death(mech, result)
        return result
    elif weapon.special & WeaponFlags.AMS:
        _notify(mech, destruction)
        mech.clear_status(MechStatus.AMS_ENABLED)
        mech.specials = int(mech.specials) & ~int(Specials.IS_ANTI_MISSILE_TECH | Specials.CL_ANTI_MISSILE_TECH)
    elif first_slot.firemode & FireMode.HOTLOAD_MODE and weapon.special & WeaponFlags.IDF and not dead:
        from systems.combat_ammunition import find_normal_ammo_for_weapon
        if find_normal_ammo_for_weapon(mech, weapon.index, 0) is not None:
            from systems.ammo_dump import find_max_ammo_damage
            damage = find_max_ammo_damage(weapon) if weapon.weapon_type in (WeaponType.TMISSILE, WeaponType.TARTILLERY) else weapon.damage
            _notify(mech, destruction)
            _notify(mech, f'%ch%crYour hotloaded launcher explodes for {damage} points of damage!%cn')
            if (los and attacker is not None and mech is not attacker) if historical else not mech.is_destroyed:
                los_broadcast(mech, 'looses a launcher in a brilliant explosion!' if historical else ' loses a launcher in a brilliant explosion!')
            explode(damage)
            return result
    elif first_slot.ammomode & AmmoMode.AC_INCENDIARY_MODE and not dead and first_slot.data > 0 and not mech.is_section_destroyed(location):
        from systems.combat import find_ammo_for_weapon
        if find_ammo_for_weapon(mech, weapon.index, -1, gof=AmmoMode.AC_INCENDIARY_MODE, critical=-1, start=0) is not None:
            _notify(mech, destruction)
            _notify(mech, f'%ch%crThe incendiary ammunition in your launcher ignites for {weapon.damage} points of damage!%cn')
            if (los and attacker is not None and mech is not attacker) if historical else not mech.is_destroyed:
                los_broadcast(mech, f"'s {armor_string(mech, location)} is engulfed {'by' if historical else 'in'} a brilliant blue flame!")
            explode(weapon.damage)
            if attacker is not None:
                return result
    if special_only:
        return None
    from systems.enhanced_crits import score_enhanced_weapon_critical_hit
    message = score_enhanced_weapon_critical_hit(mech, attacker, location, slot)
    result.effect_applied = True
    result.message = message or f'{name} critical hit'
    if message: result.messages.append(message)
    return result


def apply_ammo_critical(
    mech: 'Mech',
    location: 'Location',
    slot: int,
    attacker: Optional['Mech'] = None,
    engine=None,
) -> CriticalResult:
    """
    Handle a critical hit on an ammo bin: BOOM (usually).

    damage = rounds in the bin x the weapon's per-shot damage, x the full
    salvo size for missiles/artillery.  Gauss and NOBOOM ammo just dies, and an
    empty bin just dies ("lucky you").

    Reference: crit.c lines 1695-1718 (HandleMechCrit ammo branch)
    """
    from entities.weapon import (
        WeaponFlags,
        WeaponType,
        get_missiles_hit,
        get_weapon_by_index,
    )

    crit = mech.sections[location].criticals[slot]
    weapindx = ammo2weapon_i(crit.type)
    weapon = get_weapon_by_index(weapindx)

    result = CriticalResult(equipment_name=f"{weapon.name} Ammo" if weapon else "Ammunition")

    if weapon is None:
        _destroy_part(crit)
        result.message = "Unknown ammunition critical hit"
        return result

    # damage = critData * MechWeapons[weapindx].damage (crit.c:1699)
    damage = crit.data * weapon.damage

    # ...times the full salvo for missiles/artillery (crit.c:1700-1704).
    # num_missiles[10] is the roll-12 column, i.e. every missile hits.
    missiles_per_shot = 1
    if weapon.weapon_type in (WeaponType.TMISSILE, WeaponType.TARTILLERY):
        missiles_per_shot = get_missiles_hit(12, weapon.missiles)
        damage *= missiles_per_shot

    if weapon.special & (WeaponFlags.GAUSS | WeaponFlags.NOBOOM):
        # Gauss/NOBOOM ammo is inert: the feed just dies (crit.c:1705-1709)
        if weapon.special & WeaponFlags.GAUSS:
            ammo = 'Ammo' if _historical_aero(mech) else 'ammo'
            result.message = f"One of your Gauss Rifle {ammo} feeds is destroyed"
            from systems.damage import _notify
            _notify(mech, result.message)
        else:
            result.message = f"{weapon.name} ammo feed destroyed (does not explode)"
        _destroy_part(crit)
        result.effect_applied = True
        return result

    if damage:
        # ammo_explosion destroys the slot itself (mech.update.c:1156)
        rounds = crit.data
        is_inferno = bool(crit.ammomode & AMMO_INFERNO_MODE)

        explosion = ammo_explosion(
            mech=mech,
            location=location,
            ammo_rounds=rounds,
            weapon_damage=weapon.damage,
            missiles_per_shot=missiles_per_shot,
            is_inferno=is_inferno,
            is_gauss=False,
            engine=engine,
            slot=slot,
            # ammo_explosion(attacker, wounded, ...) - crit.c:1711 forwards the
            # attacker, and with none the C stops after destroying the bin
            # (mech.update.c:1157-1158).
            attacker=attacker,
        )
        result.effect_applied = True
        result.pilot_damage = explosion.pilot_damage
        result.mech_destroyed = explosion.mech_destroyed
        result.message = explosion.message
        result.messages.append(f"{weapon.name} ammo exploded for {explosion.damage} damage")
        return result

    # Empty bin (crit.c:1712-1716): notify before DestroyPart.
    result.message = "You have no ammunition left in that location, lucky you!"
    from systems.damage import _notify
    _notify(mech, result.message)
    _destroy_part(crit)
    result.effect_applied = True
    return result


def _check_pilot_death(mech: 'Mech', result: CriticalResult) -> None:
    """Roll pilot hits up into mech destruction, as ammo_explosion() does."""
    from entities.mech import MechStatus

    if mech.pilot_hits >= 6:
        result.mech_destroyed = True
        result.pilot_killed = True
        mech.set_status(MechStatus.DESTROYED)


def apply_critical_to_slot(mech, location, slot, attacker=None, engine=None, *, los=1):
    """HandleMechCrit: retain dispatch order and each case's mutation point."""
    from systems.damage import _notify
    from systems.combat import part_is_nonfunctional
    _notify(mech, '%ch%cyCRITICAL HIT!!!%c' if _historical_aero(mech) else '%ch%cyCRITICAL HIT!!%c')
    part = mech.sections[location].criticals[slot]
    if is_ammo(part.type):
        return apply_ammo_critical(mech, location, slot, attacker, engine=engine)
    if is_weapon(part.type):
        return apply_weapon_critical(mech, location, slot, attacker, engine=engine, los=los)
    if not is_special(part.type):
        return CriticalResult()
    kind = special2i(part.type)
    if part_is_nonfunctional(mech, location, slot):
        is_arm = location in (Location.LARM, Location.RARM) and mech.move_type != MoveType.QUAD
        names = {Special.LIFE_SUPPORT:'life support', Special.COCKPIT:'cockpit', Special.SENSORS:'sensors',
            Special.HEAT_SINK:'heatsink', Special.JUMP_JET:'jump jet', Special.ENGINE:'engine',
            Special.TARGETING_COMPUTER:'targeting computer', Special.GYRO:'gyro',
            Special.SHOULDER_OR_HIP:'shoulder' if is_arm else 'hip',
            Special.UPPER_ACTUATOR:'arm actuator', Special.LOWER_ACTUATOR:'arm actuator',
            Special.HAND_OR_FOOT_ACTUATOR:'hand actuator' if is_arm else 'foot actuator',
            Special.C3_MASTER:'C3 system', Special.C3_SLAVE:'C3 system', Special.C3I:'C3i system',
            Special.TAG:'TAG system', Special.ECM:'ECM system', Special.ANGELECM:'Angel ECM system',
            Special.BEAGLE_PROBE:'Beagle Active Probe', Special.BLOODHOUND_PROBE:'Bloodhound Active Probe',
            Special.LIGHT_BAP:'Light Beagle Active Probe', Special.ARTEMIS_IV:'ArtemisIV system',
            Special.AXE:'axe', Special.SWORD:'sword', Special.MACE:'mace', Special.DUAL_SAW:'dual saw',
            Special.DS_AERODOOR:'aero doors', Special.DS_MECHDOOR:'mech doors', Special.NULL_SIGNATURE_SYSTEM:'Null Signature System'}
        result = CriticalResult()
        _critical_notice(mech, result, f"Part of your non-working {names.get(kind, 'equipment')} has been hit!")
        _destroy_part(part)
        return result
    if kind in (Special.SPLIT_CRIT_LEFT, Special.SPLIT_CRIT_RIGHT):
        parent = {0:2,5:2,1:3,6:3,3:1,2:0,4:3 if kind == Special.SPLIT_CRIT_RIGHT else 2}.get(location,-1) if mech.unit_type == UnitType.MECH else -1
        if parent >= 0 and 0 <= part.data < 12 and is_weapon(mech.sections[parent].criticals[part.data].type):
            result = apply_weapon_critical(mech, parent, part.data, attacker, engine, los=los, special_only=True)
            if result is not None:return result
            from systems.enhanced_crits import score_enhanced_weapon_critical_hit
            scored = score_enhanced_weapon_critical_hit(mech, attacker, parent, part.data)
            return CriticalResult(effect_applied=True, message=scored or '')
        result = CriticalResult()
        _critical_notice(mech, result, f'ERROR: Could not find split weapon parent location. Loc:{int(location)} Crit:{slot} temp:{parent} fCrit:{part.data}')
        _destroy_part(part)
        return result
    before = kind in (Special.SHOULDER_OR_HIP, Special.UPPER_ACTUATOR, Special.LOWER_ACTUATOR, Special.HAND_OR_FOOT_ACTUATOR, Special.C3_MASTER)
    if kind == Special.C3_MASTER and not hasattr(mech,'working_c3_masters'):
        mech.working_c3_masters = count_working_c3_masters(mech)
    if before:_destroy_part(part)
    grouped = (kind == Special.HEAT_SINK and bool(mech.specials & (Specials.DOUBLE_HEAT_TECH | Specials.CLAN_TECH)) or
               kind == Special.JUMP_JET and not _historical_aero(mech) and bool(mech.specials2 & 0x80))
    result = handle_critical_hit(mech, location, kind, slot, attacker, engine, los=los)
    if not before and not grouped:_destroy_part(part)
    return result


def check_and_apply_criticals(
    mech: 'Mech',
    location: 'Location',
    num_crits: int,
    attacker: Optional['Mech'] = None,
    engine=None,
    *, los=1,
) -> List[CriticalResult]:
    """
    Roll for and apply multiple critical hits to a location.

    This is called by the combat system when criticals are rolled.

    Args:
        mech: The mech taking criticals
        location: Body section
        num_crits: Number of critical slots to hit
        attacker: Who caused the damage

    Returns:
        List of CriticalResult for each critical applied

    Reference: crit.c lines 2395-2429 (the critList / Number(0, count-1) roll)
    """
    from entities.mech import FireMode

    from entities.mech import UnitType, Specials, MechStatus
    from core.randomness import draw
    from systems.vehicle_combat import resolve_vehicle_critical, legacy_vehicle_critical
    engine = engine or mech._engine
    if mech.has_status(MechStatus.COMBAT_SAFE) or mech.specials & Specials.CRITPROOF_TECH:
        return []
    if mech.unit_type == UnitType.MW and draw('critical_mw_gate', 1, 2, lambda: random.randint(1, 2)) == 1:
        return []
    if mech.unit_type != UnitType.MECH and not getattr(engine, 'vcrit', 2):
        return []
    if mech.unit_type in (UnitType.DS, UnitType.SPHEROID_DS):
        return []
    if mech.unit_type in (UnitType.VEH_GROUND, UnitType.VEH_NAVAL, UnitType.VTOL):
        vtol = mech.unit_type == UnitType.VTOL
        advanced = getattr(engine, 'fasaadvvtolcrit' if vtol else 'fasaadvvhlcrit', 0)
        results = []
        for _ in range(num_crits):
            effect = (resolve_vehicle_critical(mech, location, attacker=attacker, los=los) if advanced else
                legacy_vehicle_critical(mech, location, attacker, fasa=bool(getattr(engine, 'fasacrit', 0)), vtol=vtol, los=los))
            results.append(CriticalResult(effect_applied=effect.effect_applied,
                mech_destroyed=effect.vehicle_destroyed, pilot_killed=effect.crew_killed,
                message=effect.message, messages=effect.messages))
        return results
    results = []
    section = mech.sections[location]

    # The C REBUILDS critList from scratch for every one of `num` criticals: the
    # scan loop at crit.c:2397-2415 is nested inside the `while (num > 0)` at
    # 2395.  So a crit that lands on a slot an earlier crit in the same batch
    # destroyed is impossible - it was dropped from the list before the roll.
    # (HandleMechCrit always returns 1, so `num` decrements every pass.)
    for _ in range(num_crits):
        # crit.c:2398-2414 skips empty, already-destroyed and already-damaged
        # slots plus the armour/structure fillers that cannot be critted at all.
        # It bounds the walk with NUM_CRITICALS; slots past CritsInLoc are always
        # EMPTY so this bound (mech.utils.c:151-166) gives the same answer for
        # real mechs.
        undamaged_slots = []
        for i in range(12):
            crit = section.criticals[i]
            if crit.type == EMPTY:
                continue
            if crit.firemode & (FireMode.DESTROYED_MODE | FireMode.DAMAGED_MODE):
                continue
            if is_special(crit.type) and special2i(crit.type) in UNCRITTABLE_SPECIALS:
                continue
            undamaged_slots.append(i)

        # if(!count) return; - nothing critworthy left (crit.c:2416-2417)
        if not undamaged_slots:
            break

        # index = Number(0, count - 1) (crit.c:2419-2420)
        slot = undamaged_slots[draw('critical_slot', 0, len(undamaged_slots)-1, lambda: undamaged_slots.index(random.choice(undamaged_slots)))]

        # Apply the critical
        result = apply_critical_to_slot(mech, location, slot, attacker,
                                        engine=engine, los=los)
        results.append(result)


    return results


def recalculate_mech_stats(mech):
    """Restore template speed and rebuild source actuator/gyro penalties."""
    from systems.vehicle_combat import correct_speed, make_vehicle_fall, set_max_speed
    mech.pilot_skill_base = 0
    if not hasattr(mech, 'template_max_speed'):
        mech.template_max_speed = mech.max_speed
    set_max_speed(mech, mech.template_max_speed)
    if mech.specials2 & 0x400000:
        if getattr(mech, 'crit_status2', 0) & 1:
            mech.pilot_skill_base += 3 if mech.has_crit_status(CritStatus.GYRO_DAMAGED) else 2
    elif mech.has_crit_status(CritStatus.GYRO_DAMAGED):
        mech.pilot_skill_base += 3
    quad = mech.move_type == MoveType.QUAD
    limbs = (Location.LARM, Location.RARM, Location.LLEG, Location.RLEG)
    from systems.parts import is_leg_destroyed, count_destroyed_legs
    lost = count_destroyed_legs(mech)
    if lost:
        mech.pilot_skill_base += 2 if quad else (5 if lost == 1 else 10)
        if quad and lost == 1:
            set_max_speed(mech, mech.max_speed - 10.75)
        elif lost == 1 or quad and lost == 2:
            set_max_speed(mech, 10.75)
            if quad:
                mech.pilot_skill_base += 5
        else:
            set_max_speed(mech, 0)
            make_vehicle_fall(mech)
    for loc in limbs:
        if not is_leg_destroyed(mech, loc):
            normalize_location_actuators(mech, loc)
    if mech.has_crit_status(CritStatus.HIP_DESTROYED):
        set_max_speed(mech, 0)
        make_vehicle_fall(mech)
    correct_speed(mech)


def normalize_arm_actuator(mech, location, kind):
    if kind == Special.SHOULDER_OR_HIP:
        mech.sections[location].basetohit = 4
    elif kind in (Special.UPPER_ACTUATOR, Special.LOWER_ACTUATOR):
        mech.sections[location].basetohit += 1


def normalize_leg_actuator(mech, location, kind):
    from systems.vehicle_combat import set_max_speed
    if kind == Special.SHOULDER_OR_HIP:
        set_max_speed(mech, mech.max_speed / 2)
        mech.pilot_skill_base += 2
    elif kind in (Special.UPPER_ACTUATOR, Special.LOWER_ACTUATOR, Special.HAND_OR_FOOT_ACTUATOR):
        set_max_speed(mech, mech.max_speed - 10.75)
        mech.pilot_skill_base += 1
        mech.sections[location].basetohit += 1


def normalize_location_actuators(mech, location):
    from systems.vehicle_combat import correct_speed
    section = mech.sections[location]
    section.basetohit = 0
    kinds = [special2i(slot.type) for slot in section.criticals
             if is_special(slot.type) and slot.firemode & FireMode.DESTROYED_MODE]
    normalize = (normalize_arm_actuator if mech.move_type != MoveType.QUAD
                 and location in (Location.LARM, Location.RARM) else normalize_leg_actuator)
    if Special.SHOULDER_OR_HIP in kinds:
        normalize(mech, location, Special.SHOULDER_OR_HIP)
    else:
        for kind in kinds:
            normalize(mech, location, kind)
    correct_speed(mech)

    # Apply engine heat
    # Engine heat is applied during heat phase, not as base modifier


# =============================================================================
# Game Loop Integration
# =============================================================================

def criticals_periodic(engine: 'GameEngine') -> None:
    """
    Periodic critical system update.

    Currently a no-op, but could be used for gradual effects.
    """
    pass


def register_criticals_system(engine: 'GameEngine') -> None:
    """
    Register the criticals system with the game engine.
    """
    # Currently no periodic updates needed
    pass


def handle_sensor_equipment_critical(mech, equipment_type, attacker=None):
    """Preserve the destruction notice before shutdown and sensor resets."""
    from systems.sensors import sensors
    from systems.ecm import mark_for_los_update
    result = CriticalResult(equipment_type=equipment_type, effect_applied=True)
    probes = {Special.BEAGLE_PROBE:(Specials.BEAGLE_PROBE_TECH,1,CritStatus.BEAGLE_DESTROYED,'Beagle Active Probe'),
              Special.BLOODHOUND_PROBE:(0x800,2,CritStatus.BLOODHOUND_DESTROYED,'Bloodhound Probe'),
              Special.LIGHT_BAP:(Specials.LIGHT_BAP_TECH,1,0,'Light Beagle Active Probe')}
    if equipment_type == Special.TAG:
        mech.crit_status |= CritStatus.TAG_DESTROYED
        _critical_notice(mech, result, 'Your TAG system has been destroyed!')
        from systems.targeting import check_tag
        check_tag(mech)
    elif equipment_type == Special.ECM:
        mech.crit_status |= CritStatus.ECM_DESTROYED
        _critical_notice(mech, result, 'Your ECM system has been destroyed!')
        mech.status2 &= ~(1|2)
        if mech.status2 & 0x40:
            _critical_notice(mech, result, 'Your stealth armor system shuts down!')
            mech.status2 &= ~0x40
    elif equipment_type == Special.ANGELECM:
        mech.crit_status |= CritStatus.ANGEL_ECM_DESTROYED
        _critical_notice(mech, result, 'Your Angel ECM system has been destroyed!')
        mech.status2 &= ~(0x100|0x200)
    else:
        special, word, crit, name = probes[equipment_type]
        mech.crit_status |= crit
        if equipment_type == Special.LIGHT_BAP:
            mech.crit_status2 = getattr(mech,'crit_status2',0) | 2
        field = 'specials' if word == 1 else 'specials2'
        setattr(mech, field, getattr(mech, field) & ~special)
        _critical_notice(mech, result, f'Your {name} has been destroyed!')
        changed = False
        for index, sn in enumerate(mech.sensor):
            if sensors[sn].required_special == special and sensors[sn].specials_set == 1:
                mech.sensor[index] = 0
                changed = True
        if changed:mark_for_los_update(mech)
    return result


def live_mobility_critical(unit, location, kind, attacker, slot=-1):
    from systems.piloting import make_piloting_roll
    from physics.jump import mech_falls
    from physics.collision import domino_space, jump_speed_mp
    from systems.parts import armor_string
    from systems.sensors import los_broadcast
    from systems.combat import part_is_nonfunctional
    result = CriticalResult(equipment_type=kind, effect_applied=True)
    def notice(message):_critical_notice(unit, result, message)
    def fall(message, broadcast, levels=1, domino=False):
        notice(message)
        los_broadcast(unit, broadcast)
        mech_falls(unit, levels, notify_fall=False)
        result.fell = True
        if domino:domino_space(unit, 2)
    def leg_fall():
        if attacker is not None and not unit.is_jumping and not unit.cocoon:
            result.piloting_check_required = True
            if not make_piloting_roll(unit, 0).success:
                fall('You lose your balance and fall down!', 'stumbles and falls down!')
    alive_started = not unit.is_destroyed and unit.is_started
    if kind == Special.GYRO:
        secondary = getattr(unit,'crit_status2',0)
        hardened = not secondary if _historical_aero(unit) else not secondary & 1
        if unit.specials2 & 0x400000 and hardened:
            los_broadcast(unit, 'emits a screech as its hardened gyro buckles slightly!')
            unit.crit_status2 = secondary | 1
            notice('Your hardened gyro takes a hit!')
            return result
        first = not unit.has_crit_status(CritStatus.GYRO_DAMAGED)
        force = False
        if first:
            if alive_started:los_broadcast(unit, 'emits a loud screech as its gyro buckles under the impact!')
            unit.set_crit_status(CritStatus.GYRO_DAMAGED)
            unit.pilot_skill_base += 3
            notice('Your Gyro has been damaged!')
            if attacker is not None:
                result.piloting_check_required = True
                force = not make_piloting_roll(unit, 0).success
        elif not unit.has_crit_status(CritStatus.GYRO_DESTROYED):
            unit.set_crit_status(CritStatus.GYRO_DESTROYED)
            notice('Your Gyro has been destroyed!')
            force = attacker is not None
        else:notice('Your destroyed gyro takes another hit!')
        if force and not unit.is_fallen:
            if unit.is_jumping or unit.cocoon:
                fall('You fall from the sky!', 'falls from the sky!', jump_speed_mp(unit,unit.map), True)
            elif first:fall('You lose your balance and fall down!', 'stumbles and falls down.')
            else:fall("You fall and you can't get up!", 'is knocked over!')
    elif kind == Special.JUMP_JET:
        if alive_started:los_broadcast(unit, f"'s {armor_string(unit, location)} flares as superheated plasma spews out!")
        if not _historical_aero(unit) and unit.specials2 & 0x80 and slot >= 0:
            part_type = unit.sections[location].criticals[slot].type
            first = find_first_weapon_crit(unit,location,slot,0,part_type,2)
            destroy_weapon(unit,location,part_type,first,1,2)
        unit.jump_mp = max(0,unit.jump_mp-1)
        unit.jump_speed = max(0,unit.jump_speed-10.75)
        notice('One of your jump jet engines has shut down!')
        if attacker is not None and unit.jump_speed < 10.75 and unit.is_jumping:
            fall('Losing your last Jump Jet you fall from the sky!!!!!' if _historical_aero(unit) else 'Losing your last jump jet, you fall from the sky!', 'falls from the sky!',1,True)
    else:
        arm = location in (Location.LARM,Location.RARM) and unit.move_type != MoveType.QUAD
        leg = location in (Location.LLEG,Location.RLEG) or location in (Location.LARM,Location.RARM) and unit.move_type == MoveType.QUAD
        if kind == Special.SHOULDER_OR_HIP:
            if arm:
                notice('Your shoulder joint takes a hit and is frozen!')
                normalize_location_actuators(unit,location)
            elif leg:
                if alive_started:los_broadcast(unit,"'s hip locks into place!")
                notice('Your hip takes a direct hit and freezes up!')
                if not unit.has_crit_status(CritStatus.HIP_DAMAGED):unit.set_crit_status(CritStatus.HIP_DAMAGED)
                elif unit.move_type != MoveType.QUAD:unit.set_crit_status(CritStatus.HIP_DESTROYED)
                recalculate_mech_stats(unit)
                leg_fall()
        elif arm:
            side = 'left' if location == Location.LARM else 'right'
            name = 'hand' if kind == Special.HAND_OR_FOOT_ACTUATOR else ('lower arm' if kind == Special.LOWER_ACTUATOR else 'upper arm')
            notice(f'Your {side} {name} actuator is destroyed!')
            if kind == Special.HAND_OR_FOOT_ACTUATOR and unit.sections[location].specials & 0x20:
                from systems.physical import drop_club
                messages = drop_club(unit)
                if messages:
                    notice(messages[0]);los_broadcast(unit,messages[1])
            if unit.carrying > 0:
                from systems.damage import release_tow
                notice('The hit causes your tow line to let go!')
                los_broadcast(unit,"'s tow lines release and flap freely behind it!")
                release_tow(unit)
            normalize_location_actuators(unit,location)
        elif leg:
            notice('One of your leg actuators is destroyed!')
            hip = unit.sections[location].criticals[0]
            if hip.type == i2special(Special.SHOULDER_OR_HIP) and not part_is_nonfunctional(unit,location,0):
                if alive_started:los_broadcast(unit,f"'s {armor_string(unit,location)} twists in an odd way!")
                recalculate_mech_stats(unit)
                leg_fall()
    return result


def linked_equipment_critical(unit, location, slot, kind):
    from entities.mech import MechStatus2, AmmoMode
    from systems.targeting import check_tag
    from systems.movement_commands import notify
    if kind == EquipmentType.C3_MASTER:
        working = count_working_c3_masters(unit)
        previous = getattr(unit, 'working_c3_masters', working + 1)
        unit.working_c3_masters = working
        unit.total_c3_masters = getattr(unit, 'total_c3_masters', count_total_c3_masters(unit))
        from systems.movement_commands import notify
        if previous == working:
            notify(unit, 'Your destroyed C3 system takes another hit!')
        else:
            if working == 0:
                unit.set_crit_status(CritStatus.C3_DESTROYED)
                check_tag(unit)
            notify(unit, 'One of your C3 systems has been destroyed!' if unit.total_c3_masters else 'Your C3 system has been destroyed!')
    elif kind == EquipmentType.C3_SLAVE:
        unit.set_crit_status(CritStatus.C3_DESTROYED)
        notify(unit,'Your C3 system has been destroyed!')
    elif kind == EquipmentType.C3I:
        unit.set_crit_status(CritStatus.C3I_DESTROYED)
        notify(unit,'Your C3i system has been destroyed!')
        from systems.c3 import clear
        clear(unit, ordinary=False)
    elif kind == EquipmentType.ARTEMIS_IV:
        linked = unit.sections[location].criticals[slot].data
        if linked > 12:
            from core.effects import send_error
            send_error(unit,f'Artemis IV error on mech {unit._id}')
        elif 0 <= linked < 12:
            unit.sections[location].criticals[linked].ammomode &= ~AmmoMode.ARTEMIS_MODE
            notify(unit,'Your Artemis IV system has been destroyed!')
        # Index 12 is an undefined C dereference, not a Python slot.
    elif kind == Special.DS_AERODOOR:
        notify(unit,'One of the aero doors has been rendered useless!')
    elif kind in (Special.AXE,Special.SWORD,Special.MACE,Special.DUAL_SAW):
        name={Special.AXE:'axe',Special.SWORD:'sword',Special.MACE:'mace',Special.DUAL_SAW:'dual saw'}[kind]
        notify(unit,f'Your {name} has been destroyed!')
    elif kind in (Special.DS_MECHDOOR,Special.NULL_SIGNATURE_SYSTEM):
        if kind == Special.DS_MECHDOOR:notify(unit,"One of the 'mech doors has been rendered useless!")
        notify(unit,'Your Null Signature System has been destroyed!')
        if unit.status2 & MechStatus2.NULLSIGSYS_ON:
            notify(unit,'Your Null Signature System shuts down!')
            unit.status2 &= ~MechStatus2.NULLSIGSYS_ON
        unit.set_crit_status(CritStatus.NSS_DESTROYED)
    return CriticalResult(equipment_type=kind, effect_applied=True)


def count_working_c3_masters(unit):
    from systems.combat import part_is_nonfunctional
    size = 5 if unit.unit_type == UnitType.MECH else 1
    count = 0
    for loc, section in enumerate(unit.sections):
        slots = working = 0
        for index, crit in enumerate(section.criticals[:crits_in_loc(unit, loc)]):
            if is_special(crit.type) and special2i(crit.type) == Special.C3_MASTER:
                slots += 1
                working += not part_is_nonfunctional(unit, loc, index)
            if slots == size:
                slots = 0
                count += working == size
                # C retains cumulative working count within each section.
    return count


def count_total_c3_masters(unit):
    """Count complete source slot groups, including nonfunctional masters."""
    size = 5 if unit.unit_type == UnitType.MECH else 1
    return sum(sum(crit.type == i2special(Special.C3_MASTER)
                   for crit in section.criticals[:crits_in_loc(unit, loc)]) // size
               for loc, section in enumerate(unit.sections))


def _historical_aero(unit):
    return unit.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)


def _critical_notice(unit, result, message):
    from systems.damage import _notify
    _notify(unit, message)
    result.message = message
    result.messages.append(message)
