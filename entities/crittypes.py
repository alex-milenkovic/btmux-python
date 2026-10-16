# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.utils.c
#   btech/src/btech/mech.h
# Historical Aerospace sources:
#   btech/mech.utils.c
#   src/hcode/btech/mech.h

"""
Critical-slot type namespace for BTMux Python reimplementation.

A critical slot's `type` byte is not an enum: the C partitions the 0-511 byte
range into segments and the segment tells you what kind of thing the slot holds
(weapon / ammo / bomb / special equipment / cargo).  The sub-index inside a
segment is recovered with subtraction.  This module is that namespace, copied
arithmetic-for-arithmetic from the header.

    EMPTY               0
    weapons             [1, 193)      index = type - WEAPON_BASE_INDEX
    ammo                [193, 385)    weapon index = type - AMMO_BASE_INDEX
    bombs               [385, 394)
    specials            [394, 512)    Special sub-index = type - SPECIAL_BASE_INDEX
    cargo               [512, ...)

Note that ammo shares the weapon numbering: the ammo type for weapon i is
`i2ammo(i)`, and `ammo2weapon_i()` gets you straight back to the weapon.

Reference:
- BTMux btech/src/btech/mech.h lines 104-113 - segment base indices
- BTMux btech/src/btech/mech.h lines 123-128 - IsAmmo/IsBomb/IsSpecial/IsCargo/
                                               IsActuator/IsWeapon predicates
- BTMux btech/src/btech/mech.h lines 148-161 - the *2I / I2* converters
- BTMux btech/src/btech/mech.h lines 163-215 - Special sub-indices
- BTMux btech/src/btech/mech.utils.c lines 151-166 - CritsInLoc
"""

from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities.mech import Mech


# =============================================================================
# Segment Base Indices (from mech.h)
# =============================================================================

# Reference: mech.h lines 104-105
NUM_WEAPONS = 192
NUM_BOMBS = 9

# Reference: mech.h lines 107-113
EMPTY = 0
WEAPON_BASE_INDEX = 1
AMMO_BASE_INDEX = WEAPON_BASE_INDEX + NUM_WEAPONS    # 193
BOMB_BASE_INDEX = AMMO_BASE_INDEX + NUM_WEAPONS      # 385
SPECIAL_BASE_INDEX = BOMB_BASE_INDEX + NUM_BOMBS     # 394
OSPECIAL_BASE_INDEX = 220                            # Legacy (pre-renumber) base
CARGO_BASE_INDEX = 512


# =============================================================================
# Special Equipment Sub-Indices (from mech.h)
# =============================================================================

class Special(IntEnum):
    """
    Special-equipment sub-indices.

    These are NOT crit-slot types: a slot holding a gyro stores
    `i2special(Special.GYRO)`, i.e. 394 + 8.  The C comment says it outright:
    "To define one of these-> x=SPECIAL_BASE_INDEX+SHOULDER_OR_HIP".

    Reference: mech.h lines 163-215
    """
    SHOULDER_OR_HIP = 0
    UPPER_ACTUATOR = 1
    LOWER_ACTUATOR = 2
    HAND_OR_FOOT_ACTUATOR = 3
    LIFE_SUPPORT = 4
    SENSORS = 5
    COCKPIT = 6
    ENGINE = 7
    GYRO = 8
    HEAT_SINK = 9
    JUMP_JET = 10
    CASE = 11
    FERRO_FIBROUS = 12
    ENDO_STEEL = 13
    TRIPLE_STRENGTH_MYOMER = 14
    TARGETING_COMPUTER = 15
    MASC = 16
    C3_MASTER = 17
    C3_SLAVE = 18
    BEAGLE_PROBE = 19
    ARTEMIS_IV = 20
    ECM = 21
    AXE = 22
    SWORD = 23
    MACE = 24
    CLAW = 25
    DS_AERODOOR = 26
    DS_MECHDOOR = 27
    FUELTANK = 28
    TAG = 29
    DS_TANKDOOR = 30
    DS_CARGODOOR = 31
    LAMEQUIP = 32
    CASE_II = 33
    STEALTH_ARMOR = 34
    NULL_SIGNATURE_SYSTEM = 35
    C3I = 36
    ANGELECM = 37
    HVY_FERRO_FIBROUS = 38
    LT_FERRO_FIBROUS = 39
    BLOODHOUND_PROBE = 40
    PURIFIER_ARMOR = 41
    KAGE_STEALTH_UNIT = 42
    ACHILEUS_STEALTH_UNIT = 43
    INFILTRATOR_STEALTH_UNIT = 44
    INFILTRATORII_STEALTH_UNIT = 45
    SUPERCHARGER = 46
    DUAL_SAW = 47
    LIGHT_BAP = 48
    SPLIT_CRIT_LEFT = 49
    SPLIT_CRIT_RIGHT = 50
    HARDPOINT = 51


# =============================================================================
# Converters (from mech.h)
# =============================================================================

def i2weapon(index: int) -> int:
    """Weapon index -> crit type. Reference: mech.h line 156 (I2Weapon)."""
    return index + WEAPON_BASE_INDEX


def weapon2i(crit_type: int) -> int:
    """Crit type -> weapon index. Reference: mech.h line 154 (Weapon2I)."""
    return crit_type - WEAPON_BASE_INDEX


def i2ammo(index: int) -> int:
    """Weapon index -> ammo crit type. Reference: mech.h line 157 (I2Ammo)."""
    return index + AMMO_BASE_INDEX


def ammo2weapon_i(crit_type: int) -> int:
    """Ammo crit type -> weapon index. Reference: mech.h line 148 (Ammo2WeaponI)."""
    return crit_type - AMMO_BASE_INDEX


def i2special(index: int) -> int:
    """Special sub-index -> crit type. Reference: mech.h line 158 (I2Special)."""
    return index + SPECIAL_BASE_INDEX


def special2i(crit_type: int) -> int:
    """Crit type -> Special sub-index. Reference: mech.h line 152 (Special2I)."""
    return crit_type - SPECIAL_BASE_INDEX


def i2bomb(index: int) -> int:
    """Bomb index -> crit type. Reference: mech.h line 155 (I2Bomb)."""
    return index + BOMB_BASE_INDEX


def bomb2i(crit_type: int) -> int:
    """Crit type -> bomb index. Reference: mech.h line 151 (Bomb2I)."""
    return crit_type - BOMB_BASE_INDEX


def i2cargo(index: int) -> int:
    """Cargo index -> crit type. Reference: mech.h line 159 (I2Cargo)."""
    return index + CARGO_BASE_INDEX


def cargo2i(crit_type: int) -> int:
    """Crit type -> cargo index. Reference: mech.h line 153 (Cargo2I)."""
    return crit_type - CARGO_BASE_INDEX


# =============================================================================
# Predicates (from mech.h)
# =============================================================================

def is_weapon(crit_type: int) -> bool:
    """Reference: mech.h line 128 (IsWeapon)."""
    return WEAPON_BASE_INDEX <= crit_type < AMMO_BASE_INDEX


def is_ammo(crit_type: int) -> bool:
    """Reference: mech.h line 123 (IsAmmo)."""
    return AMMO_BASE_INDEX <= crit_type < BOMB_BASE_INDEX


def is_bomb(crit_type: int) -> bool:
    """Reference: mech.h line 124 (IsBomb)."""
    return BOMB_BASE_INDEX <= crit_type < SPECIAL_BASE_INDEX


def is_special(crit_type: int) -> bool:
    """Reference: mech.h line 125 (IsSpecial)."""
    return SPECIAL_BASE_INDEX <= crit_type < CARGO_BASE_INDEX


def is_cargo(crit_type: int) -> bool:
    """Reference: mech.h line 126 (IsCargo)."""
    return crit_type >= CARGO_BASE_INDEX


def is_actuator(crit_type: int) -> bool:
    """
    Shoulder/hip and the three actuators, i.e. the first four Special slots.

    Reference: mech.h line 127 (IsActuator) - IsSpecial(a) && a <=
    I2Special(HAND_OR_FOOT_ACTUATOR)
    """
    return is_special(crit_type) and crit_type <= i2special(Special.HAND_OR_FOOT_ACTUATOR)


# =============================================================================
# Slots Per Location
# =============================================================================

def crits_in_loc(mech: 'Mech', loc: int) -> int:
    """
    Number of critical slots that actually exist in a location.

    Head and legs only ever have 6; a quad's "arms" are legs, so they get 6 too.
    Ejected MechWarriors have 2.  Everything else has the full NUM_CRITICALS.
    The `criticals` array itself stays NUM_CRITICALS wide in both codebases -
    this is the loop bound, not the allocation.

    Reference: mech.utils.c lines 151-166 (CritsInLoc)
    """
    from entities.mech import Location, MoveType, NUM_CRITICALS, UnitType

    if mech.unit_type == UnitType.MECH:
        if loc in (Location.HEAD, Location.RLEG, Location.LLEG):
            return 6
        if loc in (Location.RARM, Location.LARM):
            if mech.move_type == MoveType.QUAD:
                return 6
    elif mech.unit_type == UnitType.MW:
        return 2
    elif mech.unit_type == UnitType.AERO and loc == 4:
        return 5
    return NUM_CRITICALS
