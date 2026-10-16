# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.bth.c
#   btech/src/btech/mech.h
#   btech/src/btech/weapons.h
#   btech/src/btech/weapons.vrt.h

"""
Weapon definitions for BTMux Python reimplementation.

This module defines weapon data structures and a catalog of standard weapons.
The weapon stats are ported directly from BTMux's weapons.h and weapons.vrt.h.

Reference:
- BTMux btech/src/btech/weapons.h - Weapon definitions (MechWeapons[])
- BTMux btech/src/btech/weapons.vrt.h - VRT (recycle time) values
- BTMux btech/src/btech/mech.h - Weapon type constants

Key concepts:
- VRT (Variable Recycle Time): Seconds until weapon can fire again
- Range brackets: Short, Medium, Long, Extreme (water ranges separate)
- Heat: Heat generated when firing
- Damage: Base damage or damage per missile
"""

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag, auto
from typing import Optional


# =============================================================================
# Weapon Type Constants (from mech.h)
# =============================================================================

class WeaponType(IntEnum):
    """
    Weapon type categories.

    Reference: mech.h lines 577-585
    """
    TBEAM = 0       # Energy weapons (lasers, PPCs)
    TMISSILE = 1    # Missile weapons (LRMs, SRMs)
    TARTILLERY = 2  # Artillery weapons
    TAMMO = 3       # Ballistic weapons requiring ammo (ACs, MGs)
    THAND = 4       # Hand weapons (swords)


class WeaponClass(IntEnum):
    """
    Weapon class for special handling.
    """
    ENERGY = 0      # Lasers, PPCs
    BALLISTIC = 1   # ACs, MGs, Gauss
    MISSILE = 2     # LRMs, SRMs
    PHYSICAL = 3    # Melee weapons


# =============================================================================
# Weapon Special Flags (from mech.h)
# =============================================================================

class WeaponFlags(IntFlag):
    """
    Special weapon flags.

    Reference: mech.h lines 639-680
    """
    NONE = 0
    PULSE = 0x00000001           # Pulse laser (-2 BTH)
    LBX = 0x00000002             # LBX autocannon (cluster mode)
    ULTRA = 0x00000004           # Ultra AC (double tap)
    STREAK = 0x00000008          # Streak missiles (all or nothing)
    IDF = 0x00000010             # Indirect fire capable
    DAR = 0x00000020             # Direct Artillery
    CLAT = 0x00000040            # Clan tech
    GAUSS = 0x00000080           # Gauss rifle (no heat, explodes)
    NARC = 0x00000100            # NARC beacon
    INARC = 0x00000200           # iNARC beacon
    AMS = 0x00000400             # Anti-Missile System
    RFAC = 0x00000800            # Rapid Fire AC capable
    RAC = 0x00001000             # Rotary AC
    GMG = 0x00002000             # Gattling MG
    NOSPA = 0x00004000           # No special ammo
    MRM = 0x00008000             # Medium Range Missiles (+1 BTH)
    ROCKET = 0x00010000          # Rocket launcher (+1 BTH, one-shot)
    A_POD = 0x00020000           # Anti-personnel pod
    CHEAT = 0x00040000           # Flamer (heat mode)
    PC_IMPA = 0x00080000         # PC impact weapon
    PC_SHAR = 0x00100000         # PC sharp weapon
    PC_HEAT = 0x00200000         # PC heat weapon
    NOBOOM = 0x00400000          # Ammo doesn't explode
    ELRM = 0x00800000            # Extended LRM
    DFM = 0x01000000             # Dead Fire Missile
    HVYW = 0x02000000            # Heavy weapon (+1 BTH)
    HYPER = 0x04000000           # Hyper AC
    CASELESS = 0x08000000        # Caseless ammo
    SNUBPPC = 0x10000000         # Snub-nosed PPC
    HVYGAUSS = 0x20000000        # Heavy Gauss
    SPLIT_CRITS = 0x40000000     # Can split across sections


# =============================================================================
# Range Bracket Constants
# =============================================================================

class RangeBracket(IntEnum):
    """Range brackets for to-hit modifiers."""
    SHORT = 0       # 0 BTH modifier
    MEDIUM = 1      # +2 BTH modifier
    LONG = 2        # +4 BTH modifier
    EXTREME = 3     # +8 BTH modifier (beyond normal range)
    OUT_OF_RANGE = 4  # Cannot fire
    MINIMUM = 5     # Inside minimum range


# BTH modifiers by range bracket
RANGE_BTH_MODIFIERS = {
    RangeBracket.SHORT: 0,
    RangeBracket.MEDIUM: 2,
    RangeBracket.LONG: 4,
    RangeBracket.EXTREME: 8,
    RangeBracket.MINIMUM: 1,  # Per hex inside minimum
}


# =============================================================================
# Weapon Data Structure
# =============================================================================

@dataclass
class Weapon:
    """
    A weapon definition with all stats.

    Reference: weapons.h weapon_struct
    Fields in weapons.h order:
    name, vrt, type, heat, damage, min, short, med, long,
    min_water, short_water, med_water, long_water,
    crits, ammo_per_ton, weight, explosive_damage, special, bv
    """

    # Identity
    name: str                    # Weapon name (e.g., "IS.MediumLaser")

    # Catalog index - the C's subscript into MechWeapons[], which is what a
    # crit slot actually stores (as I2Weapon(index) / I2Ammo(index)) and what
    # every weapon-number API passes around.  Assigned by register_weapon();
    # -1 means "not in the catalog".
    # Reference: mech.h lines 156-157 (I2Weapon / I2Ammo)
    index: int = -1

    # Type and classification
    weapon_type: WeaponType = WeaponType.TBEAM
    weapon_class: WeaponClass = WeaponClass.ENERGY

    # Core stats
    damage: int = 0              # Damage per hit (or per missile)
    heat: int = 0                # Heat generated when fired
    vrt: int = 20                # Variable Recycle Time (seconds)
    crits: int = 1               # Critical slots required
    tonnage: float = 1.0         # Weight in tons

    # Range brackets (in hexes)
    range_min: int = 0           # Minimum range (0 = no minimum)
    range_short: int = 3         # Short range
    range_medium: int = 6        # Medium range
    range_long: int = 9          # Long range

    # Underwater range brackets (optional, -1 means cannot fire underwater)
    range_min_water: int = -1
    range_short_water: int = -1
    range_medium_water: int = -1
    range_long_water: int = -1

    # Ammo
    ammo_per_ton: int = 0        # Shots per ton (0 = infinite/energy)
    uses_ammo: bool = False      # Does this weapon require ammo?

    # Missile specific
    missiles: int = 1            # Number of missiles per shot (1 for non-missiles)
    damage_per_missile: int = 0  # Damage per missile (set for missiles)

    # Special properties
    special: WeaponFlags = WeaponFlags.NONE
    explosive_damage: int = -1   # Damage if ammo explodes (-1 = standard)
    bv: int = 0                  # Battle Value
    cost: int = 0
    ammo_bv: int = 0
    ammo_cost: int = 0

    # Clan flag (convenience)
    is_clan: bool = False

    def __post_init__(self):
        """Set derived values."""
        if self.special & WeaponFlags.CLAT:
            self.is_clan = True
        if self.damage_per_missile > 0 and self.damage == 0:
            # Missiles use damage_per_missile, set damage for compatibility
            self.damage = self.damage_per_missile

    @property
    def extreme_range(self) -> int:
        """
        Calculate extreme range (1.5x long range, rounded down).

        Reference: mech.bth.c EGunRange macro
        """
        return int(self.range_long * 1.5)

    @property
    def extreme_range_water(self) -> int:
        """Extreme range underwater."""
        if self.range_long_water < 0:
            return -1
        return int(self.range_long_water * 1.5)

    def get_range_bracket(self, distance: float, underwater: bool = False) -> RangeBracket:
        """
        Determine range bracket for a given distance.

        Args:
            distance: Distance to target in hexes
            underwater: Whether shooter is underwater

        Returns:
            RangeBracket enum value
        """
        dist = int(distance + 0.95)  # Round up like BTMux

        if underwater:
            if self.range_short_water < 0:
                return RangeBracket.OUT_OF_RANGE
            if dist > self.extreme_range_water:
                return RangeBracket.OUT_OF_RANGE
            if dist > self.range_long_water:
                return RangeBracket.EXTREME
            if dist > self.range_medium_water:
                return RangeBracket.LONG
            if dist > self.range_short_water:
                return RangeBracket.MEDIUM
            if dist > self.range_min_water and self.range_min_water >= 0:
                return RangeBracket.SHORT
            if self.range_min_water > 0 and dist <= self.range_min_water:
                return RangeBracket.MINIMUM
            return RangeBracket.SHORT

        # Normal (above water)
        if dist > self.extreme_range:
            return RangeBracket.OUT_OF_RANGE
        if dist > self.range_long:
            return RangeBracket.EXTREME
        if dist > self.range_medium:
            return RangeBracket.LONG
        if dist > self.range_short:
            return RangeBracket.MEDIUM
        if dist > self.range_min:
            return RangeBracket.SHORT
        if self.range_min > 0 and dist <= self.range_min:
            return RangeBracket.MINIMUM
        return RangeBracket.SHORT

    def get_range_bth_modifier(self, distance: float, underwater: bool = False) -> int:
        """
        Get BTH modifier for range.

        Args:
            distance: Distance to target in hexes
            underwater: Whether shooter is underwater

        Returns:
            BTH modifier (add to base to-hit roll)
        """
        bracket = self.get_range_bracket(distance, underwater)

        if bracket == RangeBracket.OUT_OF_RANGE:
            return 1000  # Cannot fire

        if bracket == RangeBracket.MINIMUM:
            # Inside minimum range: +1 per hex inside
            dist = int(distance + 0.95)
            return self.range_min - dist + 1

        return RANGE_BTH_MODIFIERS.get(bracket, 0)

    def can_fire_at_range(self, distance: float, underwater: bool = False) -> bool:
        """Check if this weapon can fire at the given range."""
        return self.get_range_bracket(distance, underwater) != RangeBracket.OUT_OF_RANGE


# =============================================================================
# Weapon Catalog
# =============================================================================

# Dictionary of all weapons by name
WEAPON_CATALOG: dict[str, Weapon] = {}

# The C's MechWeapons[] array: weapons by index, in declaration order.
# Reference: mech.h line 1322 (extern struct weapon_struct MechWeapons[])
WEAPON_INDEX: list[Weapon] = []


def register_weapon(weapon: Weapon) -> Weapon:
    """
    Register a weapon in the catalog, assigning it its catalog index.

    Indices are handed out sequentially in registration order, which for this
    module is source order - the Python analogue of a weapon's position in the
    C's static MechWeapons[] table.  Crit slots then reference the weapon as
    i2weapon(index) and its ammo as i2ammo(index).
    """
    from entities.weapon_values import WEAPON_VALUES
    if weapon.name in WEAPON_VALUES:
        weapon.cost, weapon.ammo_bv, weapon.ammo_cost = WEAPON_VALUES[weapon.name]
    weapon.index = len(WEAPON_INDEX)
    WEAPON_INDEX.append(weapon)
    WEAPON_CATALOG[weapon.name] = weapon
    return weapon


def get_weapon(name: str) -> Optional[Weapon]:
    """Get a weapon by name."""
    return WEAPON_CATALOG.get(name)


def get_weapon_by_index(index: int) -> Optional[Weapon]:
    """Get a weapon by catalog index (the C's MechWeapons[index])."""
    if 0 <= index < len(WEAPON_INDEX):
        return WEAPON_INDEX[index]
    return None


# =============================================================================
# Standard Weapon Definitions
# =============================================================================

# -----------------------------------------------------------------------------
# Inner Sphere Energy Weapons
# -----------------------------------------------------------------------------

# IS Small Laser
IS_SMALL_LASER = register_weapon(Weapon(
    name="IS.SmallLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=3,
    heat=1,
    vrt=15,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=-1,  # Doesn't work deep underwater
    bv=9,
))

# IS Medium Laser
IS_MEDIUM_LASER = register_weapon(Weapon(
    name="IS.MediumLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=5,
    heat=3,
    vrt=20,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    range_min_water=0,
    range_short_water=2,
    range_medium_water=4,
    range_long_water=6,
    bv=46,
))

# IS Large Laser
IS_LARGE_LASER = register_weapon(Weapon(
    name="IS.LargeLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=8,
    heat=8,
    vrt=25,
    crits=2,
    tonnage=5.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=6,
    range_long_water=9,
    bv=124,
))

# IS PPC
IS_PPC = register_weapon(Weapon(
    name="IS.PPC",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=10,
    vrt=30,
    crits=3,
    tonnage=7.0,
    range_min=3,
    range_short=6,
    range_medium=12,
    range_long=18,
    range_min_water=3,
    range_short_water=4,
    range_medium_water=7,
    range_long_water=10,
    bv=176,
))

# IS ER PPC
IS_ERPPC = register_weapon(Weapon(
    name="IS.ERPPC",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=15,
    vrt=30,
    crits=3,
    tonnage=7.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=23,
    range_min_water=0,
    range_short_water=4,
    range_medium_water=10,
    range_long_water=16,
    bv=229,
))

# IS Medium Pulse Laser
IS_MEDIUM_PULSE_LASER = register_weapon(Weapon(
    name="IS.MediumPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=6,
    heat=4,
    vrt=20,
    crits=1,
    tonnage=2.0,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=6,
    range_min_water=0,
    range_short_water=2,
    range_medium_water=3,
    range_long_water=4,
    special=WeaponFlags.PULSE,
    bv=48,
))

# IS Large Pulse Laser
IS_LARGE_PULSE_LASER = register_weapon(Weapon(
    name="IS.LargePulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=9,
    heat=10,
    vrt=25,
    crits=2,
    tonnage=7.0,
    range_min=0,
    range_short=3,
    range_medium=7,
    range_long=10,
    range_min_water=0,
    range_short_water=2,
    range_medium_water=5,
    range_long_water=7,
    special=WeaponFlags.PULSE,
    bv=119,
))

# IS Flamer
IS_FLAMER = register_weapon(Weapon(
    name="IS.Flamer",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=2,
    heat=3,
    vrt=10,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    special=WeaponFlags.CHEAT,
    bv=6,
))

# IS ER Large Laser
IS_ER_LARGE_LASER = register_weapon(Weapon(
    name="IS.ERLargeLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=8,
    heat=12,
    vrt=25,
    crits=2,
    tonnage=5.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=19,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=5,
    range_long_water=12,
    bv=163,
))

# IS ER Medium Laser
IS_ER_MEDIUM_LASER = register_weapon(Weapon(
    name="IS.ERMediumLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=5,
    heat=5,
    vrt=20,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=5,
    range_long_water=8,
    bv=62,
))

# IS ER Small Laser
IS_ER_SMALL_LASER = register_weapon(Weapon(
    name="IS.ERSmallLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=3,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=5,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=3,
    bv=17,
))

# IS Small Pulse Laser
IS_SMALL_PULSE_LASER = register_weapon(Weapon(
    name="IS.SmallPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=3,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=-1,
    special=WeaponFlags.PULSE,
    bv=12,
))

# IS X-Large Pulse Laser
IS_X_LARGE_PULSE_LASER = register_weapon(Weapon(
    name="IS.X-LargePulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=9,
    heat=14,
    vrt=27,
    crits=2,
    tonnage=7.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=6,
    range_long_water=9,
    special=WeaponFlags.PULSE,
    bv=178,
))

# IS X-Medium Pulse Laser
IS_X_MEDIUM_PULSE_LASER = register_weapon(Weapon(
    name="IS.X-MediumPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=6,
    heat=6,
    vrt=22,
    crits=1,
    tonnage=2.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    range_min_water=0,
    range_short_water=2,
    range_medium_water=4,
    range_long_water=6,
    special=WeaponFlags.PULSE,
    bv=71,
))

# IS X-Small Pulse Laser
IS_X_SMALL_PULSE_LASER = register_weapon(Weapon(
    name="IS.X-SmallPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=3,
    heat=3,
    vrt=17,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=5,
    special=WeaponFlags.PULSE,
    bv=21,
))

# IS Snub-Nosed PPC
IS_SNUB_NOSED_PPC = register_weapon(Weapon(
    name="IS.SnubNosedPPC",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=10,
    vrt=30,
    crits=2,
    tonnage=6.0,
    range_min=0,
    range_short=9,
    range_medium=13,
    range_long=15,
    range_min_water=0,
    range_short_water=6,
    range_medium_water=8,
    range_long_water=9,
    special=WeaponFlags.SNUBPPC,
    bv=165,
))

# IS Light PPC
IS_LIGHT_PPC = register_weapon(Weapon(
    name="IS.LightPPC",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=5,
    heat=5,
    vrt=30,
    crits=2,
    tonnage=3.0,
    range_min=3,
    range_short=6,
    range_medium=12,
    range_long=18,
    range_min_water=3,
    range_short_water=4,
    range_medium_water=8,
    range_long_water=10,
    bv=88,
))

# IS Heavy PPC
IS_HEAVY_PPC = register_weapon(Weapon(
    name="IS.HeavyPPC",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=15,
    heat=15,
    vrt=30,
    crits=4,
    tonnage=10.0,
    range_min=3,
    range_short=6,
    range_medium=12,
    range_long=18,
    range_min_water=3,
    range_short_water=4,
    range_medium_water=8,
    range_long_water=10,
    bv=317,
))

# -----------------------------------------------------------------------------
# Inner Sphere Ballistic Weapons
# -----------------------------------------------------------------------------

# IS AC/2
IS_AC2 = register_weapon(Weapon(
    name="IS.AC/2",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=12,
    crits=1,
    tonnage=6.0,
    range_min=4,
    range_short=8,
    range_medium=16,
    range_long=24,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.RFAC,
    bv=37,
))

# IS AC/5
IS_AC5 = register_weapon(Weapon(
    name="IS.AC/5",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=20,
    crits=4,
    tonnage=8.0,
    range_min=3,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.RFAC,
    bv=70,
))

# IS AC/10
IS_AC10 = register_weapon(Weapon(
    name="IS.AC/10",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=3,
    vrt=25,
    crits=7,
    tonnage=12.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.RFAC,
    bv=124,
))

# IS AC/20
IS_AC20 = register_weapon(Weapon(
    name="IS.AC/20",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=20,
    heat=7,
    vrt=30,
    crits=10,
    tonnage=14.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.RFAC | WeaponFlags.SPLIT_CRITS,
    bv=178,
))

# IS Machine Gun
IS_MACHINE_GUN = register_weapon(Weapon(
    name="IS.MachineGun",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=0,
    vrt=7,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    ammo_per_ton=200,
    uses_ammo=True,
    special=WeaponFlags.GMG,
    bv=5,
))

# IS Gauss Rifle
IS_GAUSS_RIFLE = register_weapon(Weapon(
    name="IS.GaussRifle",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=15,
    heat=1,
    vrt=30,
    crits=7,
    tonnage=15.0,
    range_min=2,
    range_short=7,
    range_medium=15,
    range_long=22,
    ammo_per_ton=8,
    uses_ammo=True,
    explosive_damage=20,
    special=WeaponFlags.GAUSS,
    bv=321,
))

# IS Light Gauss Rifle
IS_LIGHT_GAUSS_RIFLE = register_weapon(Weapon(
    name="IS.LightGaussRifle",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=8,
    heat=1,
    vrt=20,
    crits=5,
    tonnage=12.0,
    range_min=3,
    range_short=8,
    range_medium=17,
    range_long=25,
    ammo_per_ton=16,
    uses_ammo=True,
    explosive_damage=16,
    special=WeaponFlags.GAUSS,
    bv=159,
))

# IS Heavy Gauss Rifle
IS_HEAVY_GAUSS_RIFLE = register_weapon(Weapon(
    name="IS.HeavyGaussRifle",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=25,
    heat=2,
    vrt=30,
    crits=11,
    tonnage=18.0,
    range_min=4,
    range_short=6,
    range_medium=13,
    range_long=20,
    ammo_per_ton=4,
    uses_ammo=True,
    explosive_damage=25,
    special=WeaponFlags.GAUSS | WeaponFlags.HVYGAUSS | WeaponFlags.SPLIT_CRITS,
    bv=346,
))

# IS LB 2-X AC
IS_LBX2 = register_weapon(Weapon(
    name="IS.LB2-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=15,
    crits=4,
    tonnage=6.0,
    range_min=4,
    range_short=9,
    range_medium=18,
    range_long=27,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.LBX,
    bv=42,
))

# IS LB 5-X AC
IS_LBX5 = register_weapon(Weapon(
    name="IS.LB5-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=20,
    crits=5,
    tonnage=8.0,
    range_min=3,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.LBX,
    bv=83,
))

# IS LB 10-X AC
IS_LBX10 = register_weapon(Weapon(
    name="IS.LB10-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=2,
    vrt=25,
    crits=6,
    tonnage=11.0,
    range_min=0,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.LBX,
    bv=148,
))

# IS LB 20-X AC
IS_LBX20 = register_weapon(Weapon(
    name="IS.LB20-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=20,
    heat=6,
    vrt=30,
    crits=11,
    tonnage=14.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.LBX | WeaponFlags.SPLIT_CRITS,
    bv=237,
))

# IS Ultra AC/2
IS_ULTRA_AC2 = register_weapon(Weapon(
    name="IS.UltraAC/2",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=12,
    crits=3,
    tonnage=7.0,
    range_min=4,
    range_short=8,
    range_medium=17,
    range_long=25,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.ULTRA,
    bv=56,
))

# IS Ultra AC/5
IS_ULTRA_AC5 = register_weapon(Weapon(
    name="IS.UltraAC/5",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=20,
    crits=5,
    tonnage=9.0,
    range_min=2,
    range_short=6,
    range_medium=13,
    range_long=20,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.ULTRA,
    bv=113,
))

# IS Ultra AC/10
IS_ULTRA_AC10 = register_weapon(Weapon(
    name="IS.UltraAC/10",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=4,
    vrt=25,
    crits=7,
    tonnage=13.0,
    range_min=0,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.ULTRA,
    bv=253,
))

# IS Ultra AC/20
IS_ULTRA_AC20 = register_weapon(Weapon(
    name="IS.UltraAC/20",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=20,
    heat=8,
    vrt=30,
    crits=10,
    tonnage=15.0,
    range_min=0,
    range_short=3,
    range_medium=7,
    range_long=10,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.ULTRA | WeaponFlags.SPLIT_CRITS,
    bv=282,
))

# IS Rotary AC/2
IS_ROTARY_AC2 = register_weapon(Weapon(
    name="IS.RotaryAC/2",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=15,
    crits=3,
    tonnage=8.0,
    range_min=0,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.RAC,
    bv=118,
))

# IS Rotary AC/5
IS_ROTARY_AC5 = register_weapon(Weapon(
    name="IS.RotaryAC/5",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=22,
    crits=6,
    tonnage=10.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.RAC,
    bv=247,
))

# IS Light AC/2
IS_LIGHT_AC2 = register_weapon(Weapon(
    name="IS.LightAC/2",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=12,
    crits=1,
    tonnage=4.0,
    range_min=0,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.RFAC,
    bv=30,
))

# IS Light AC/5
IS_LIGHT_AC5 = register_weapon(Weapon(
    name="IS.LightAC/5",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=20,
    crits=2,
    tonnage=5.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.RFAC,
    bv=62,
))

# IS Heavy Machine Gun
IS_HEAVY_MACHINE_GUN = register_weapon(Weapon(
    name="IS.HeavyMachineGun",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=0,
    vrt=7,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=6,
    ammo_per_ton=100,
    uses_ammo=True,
    special=WeaponFlags.GMG,
    bv=6,
))

# IS Vehicle Flamer
IS_VEHICLE_FLAMER = register_weapon(Weapon(
    name="IS.VehicleFlamer",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=3,
    vrt=10,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.CHEAT,
    bv=5,
))

# IS Heavy Flamer
IS_HEAVY_FLAMER = register_weapon(Weapon(
    name="IS.HeavyFlamer",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=4,
    heat=5,
    vrt=15,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=6,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.CHEAT,
    bv=20,
))

# IS Plasma Rifle
IS_PLASMA_RIFLE = register_weapon(Weapon(
    name="IS.PlasmaRifle",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=10,
    vrt=30,
    crits=2,
    tonnage=6.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.NOBOOM,
    bv=210,
))

# IS Anti-Missile System
IS_AMS = register_weapon(Weapon(
    name="IS.Anti-MissileSystem",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=10,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=1,
    range_long=1,
    ammo_per_ton=12,
    uses_ammo=True,
    special=WeaponFlags.AMS,
    bv=32,
))

# IS Laser AMS
IS_LASER_AMS = register_weapon(Weapon(
    name="IS.LaserAMS",
    ammo_per_ton=24,
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=2,
    heat=12,
    vrt=25,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=1,
    range_long=1,
    special=WeaponFlags.AMS,
    bv=105,
))

# IS Magshot Gauss Rifle
IS_MAGSHOT_GAUSS = register_weapon(Weapon(
    name="IS.MagshotGaussRifle",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=0,
    vrt=12,
    crits=2,
    tonnage=0.5,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=50,
    uses_ammo=True,
    explosive_damage=3,
    special=WeaponFlags.GAUSS,
    bv=15,
))

# -----------------------------------------------------------------------------
# Inner Sphere Missile Weapons
# -----------------------------------------------------------------------------

# IS SRM-2
IS_SRM2 = register_weapon(Weapon(
    name="IS.SRM-2",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,  # Per missile
    heat=2,
    vrt=15,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=50,
    uses_ammo=True,
    missiles=2,
    damage_per_missile=2,
    bv=21,
))

# IS SRM-4
IS_SRM4 = register_weapon(Weapon(
    name="IS.SRM-4",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=3,
    vrt=15,
    crits=1,
    tonnage=2.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=25,
    uses_ammo=True,
    missiles=4,
    damage_per_missile=2,
    bv=39,
))

# IS SRM-6
IS_SRM6 = register_weapon(Weapon(
    name="IS.SRM-6",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=4,
    vrt=15,
    crits=2,
    tonnage=3.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=15,
    uses_ammo=True,
    missiles=6,
    damage_per_missile=2,
    bv=59,
))

# IS LRM-5
IS_LRM5 = register_weapon(Weapon(
    name="IS.LRM-5",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=2.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=24,
    uses_ammo=True,
    missiles=5,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=45,
))

# IS LRM-10
IS_LRM10 = register_weapon(Weapon(
    name="IS.LRM-10",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=4,
    vrt=20,
    crits=2,
    tonnage=5.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=12,
    uses_ammo=True,
    missiles=10,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=90,
))

# IS LRM-15
IS_LRM15 = register_weapon(Weapon(
    name="IS.LRM-15",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=5,
    vrt=25,
    crits=3,
    tonnage=7.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=8,
    uses_ammo=True,
    missiles=15,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=136,
))

# IS LRM-20
IS_LRM20 = register_weapon(Weapon(
    name="IS.LRM-20",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=6,
    vrt=30,
    crits=5,
    tonnage=10.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=20,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=181,
))

# IS Streak SRM-2
IS_STREAK_SRM2 = register_weapon(Weapon(
    name="IS.StreakSRM-2",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=1.5,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=50,
    uses_ammo=True,
    missiles=2,
    damage_per_missile=2,
    special=WeaponFlags.STREAK | WeaponFlags.NOSPA,
    bv=30,
))

# IS Streak SRM-4
IS_STREAK_SRM4 = register_weapon(Weapon(
    name="IS.StreakSRM-4",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=3,
    vrt=15,
    crits=1,
    tonnage=3.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=25,
    uses_ammo=True,
    missiles=4,
    damage_per_missile=2,
    special=WeaponFlags.STREAK | WeaponFlags.NOSPA,
    bv=59,
))

# IS Streak SRM-6
IS_STREAK_SRM6 = register_weapon(Weapon(
    name="IS.StreakSRM-6",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=4,
    vrt=15,
    crits=2,
    tonnage=4.5,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=15,
    uses_ammo=True,
    missiles=6,
    damage_per_missile=2,
    special=WeaponFlags.STREAK | WeaponFlags.NOSPA,
    bv=89,
))

# IS MRM-10
IS_MRM10 = register_weapon(Weapon(
    name="IS.MRM-10",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=4,
    vrt=20,
    crits=2,
    tonnage=3.0,
    range_min=0,
    range_short=3,
    range_medium=8,
    range_long=15,
    ammo_per_ton=24,
    uses_ammo=True,
    missiles=10,
    damage_per_missile=1,
    special=WeaponFlags.MRM,
    bv=56,
))

# IS MRM-20
IS_MRM20 = register_weapon(Weapon(
    name="IS.MRM-20",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=6,
    vrt=30,
    crits=3,
    tonnage=7.0,
    range_min=0,
    range_short=3,
    range_medium=8,
    range_long=15,
    ammo_per_ton=12,
    uses_ammo=True,
    missiles=20,
    damage_per_missile=1,
    special=WeaponFlags.MRM,
    bv=112,
))

# IS MRM-30
IS_MRM30 = register_weapon(Weapon(
    name="IS.MRM-30",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=10,
    vrt=30,
    crits=5,
    tonnage=10.0,
    range_min=0,
    range_short=3,
    range_medium=8,
    range_long=15,
    ammo_per_ton=8,
    uses_ammo=True,
    missiles=30,
    damage_per_missile=1,
    special=WeaponFlags.MRM,
    bv=168,
))

# IS MRM-40
IS_MRM40 = register_weapon(Weapon(
    name="IS.MRM-40",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=12,
    vrt=30,
    crits=7,
    tonnage=12.0,
    range_min=0,
    range_short=3,
    range_medium=8,
    range_long=15,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=40,
    damage_per_missile=1,
    special=WeaponFlags.MRM,
    bv=224,
))

# IS NARC Beacon
IS_NARC = register_weapon(Weapon(
    name="IS.NarcBeacon",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=4,
    heat=1,
    vrt=30,
    crits=2,
    tonnage=3.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=1,
    damage_per_missile=4,
    special=WeaponFlags.NARC,
    bv=30,
))

# IS iNARC Beacon
IS_INARC = register_weapon(Weapon(
    name="IS.iNarcBeacon",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=6,
    heat=1,
    vrt=30,
    crits=3,
    tonnage=5.0,
    range_min=0,
    range_short=4,
    range_medium=9,
    range_long=15,
    ammo_per_ton=4,
    uses_ammo=True,
    missiles=1,
    damage_per_missile=6,
    special=WeaponFlags.INARC,
    bv=75,
))

# IS Rocket Launcher 10
IS_RL10 = register_weapon(Weapon(
    name="IS.RL-10",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=3,
    vrt=30,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=5,
    range_medium=11,
    range_long=18,
    ammo_per_ton=0,  # One-shot
    uses_ammo=False,
    missiles=10,
    damage_per_missile=1,
    special=WeaponFlags.ROCKET | WeaponFlags.IDF,
    bv=18,
))

# IS Rocket Launcher 15
IS_RL15 = register_weapon(Weapon(
    name="IS.RL-15",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=4,
    vrt=30,
    crits=2,
    tonnage=1.0,
    range_min=0,
    range_short=4,
    range_medium=9,
    range_long=15,
    ammo_per_ton=0,  # One-shot
    uses_ammo=False,
    missiles=15,
    damage_per_missile=1,
    special=WeaponFlags.ROCKET | WeaponFlags.IDF,
    bv=23,
))

# IS Rocket Launcher 20
IS_RL20 = register_weapon(Weapon(
    name="IS.RL-20",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=5,
    vrt=30,
    crits=3,
    tonnage=1.5,
    range_min=0,
    range_short=3,
    range_medium=7,
    range_long=12,
    ammo_per_ton=0,  # One-shot
    uses_ammo=False,
    missiles=20,
    damage_per_missile=1,
    special=WeaponFlags.ROCKET | WeaponFlags.IDF,
    bv=24,
))

# IS Thunderbolt-5
IS_THUNDERBOLT5 = register_weapon(Weapon(
    name="IS.Thunderbolt-5",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=5,
    heat=3,
    vrt=20,
    crits=1,
    tonnage=3.0,
    range_min=5,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=12,
    uses_ammo=True,
    missiles=1,
    damage_per_missile=5,
    special=WeaponFlags.IDF | WeaponFlags.NOSPA,
    bv=64,
))

# IS Thunderbolt-10
IS_THUNDERBOLT10 = register_weapon(Weapon(
    name="IS.Thunderbolt-10",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=10,
    heat=5,
    vrt=20,
    crits=2,
    tonnage=7.0,
    range_min=5,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=1,
    damage_per_missile=10,
    special=WeaponFlags.IDF | WeaponFlags.NOSPA,
    bv=127,
))

# IS Thunderbolt-15
IS_THUNDERBOLT15 = register_weapon(Weapon(
    name="IS.Thunderbolt-15",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=15,
    heat=7,
    vrt=30,
    crits=3,
    tonnage=11.0,
    range_min=5,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=4,
    uses_ammo=True,
    missiles=1,
    damage_per_missile=15,
    special=WeaponFlags.IDF | WeaponFlags.NOSPA,
    bv=229,
))

# IS Thunderbolt-20
IS_THUNDERBOLT20 = register_weapon(Weapon(
    name="IS.Thunderbolt-20",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=20,
    heat=8,
    vrt=30,
    crits=5,
    tonnage=15.0,
    range_min=5,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=3,
    uses_ammo=True,
    missiles=1,
    damage_per_missile=20,
    special=WeaponFlags.IDF | WeaponFlags.NOSPA,
    bv=305,
))

# IS MML-3 (Multi-Missile Launcher)
IS_MML3 = register_weapon(Weapon(
    name="IS.MML-3",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=2,
    vrt=30,
    crits=2,
    tonnage=1.5,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=33,
    uses_ammo=True,
    missiles=3,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=29,
))

# IS MML-5
IS_MML5 = register_weapon(Weapon(
    name="IS.MML-5",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=3,
    vrt=30,
    crits=3,
    tonnage=3.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=20,
    uses_ammo=True,
    missiles=5,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=45,
))

# IS MML-7
IS_MML7 = register_weapon(Weapon(
    name="IS.MML-7",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=4,
    vrt=30,
    crits=4,
    tonnage=4.5,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=14,
    uses_ammo=True,
    missiles=7,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=67,
))

# IS MML-9
IS_MML9 = register_weapon(Weapon(
    name="IS.MML-9",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=5,
    vrt=30,
    crits=5,
    tonnage=6.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=11,
    uses_ammo=True,
    missiles=9,
    damage_per_missile=1,
    special=WeaponFlags.IDF,
    bv=86,
))

# IS ELRM-5 (Extended LRM)
IS_ELRM5 = register_weapon(Weapon(
    name="IS.ELRM-5",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=3,
    vrt=30,
    crits=1,
    tonnage=6.0,
    range_min=10,
    range_short=12,
    range_medium=24,
    range_long=36,
    ammo_per_ton=18,
    uses_ammo=True,
    missiles=5,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.ELRM | WeaponFlags.NOSPA,
    bv=1000,
))

# IS ELRM-10
IS_ELRM10 = register_weapon(Weapon(
    name="IS.ELRM-10",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=6,
    vrt=30,
    crits=4,
    tonnage=8.0,
    range_min=10,
    range_short=12,
    range_medium=24,
    range_long=36,
    ammo_per_ton=9,
    uses_ammo=True,
    missiles=10,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.ELRM | WeaponFlags.NOSPA,
    bv=1000,
))

# IS ELRM-15
IS_ELRM15 = register_weapon(Weapon(
    name="IS.ELRM-15",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=8,
    vrt=30,
    crits=6,
    tonnage=12.0,
    range_min=10,
    range_short=12,
    range_medium=24,
    range_long=36,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=15,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.ELRM | WeaponFlags.NOSPA,
    bv=1000,
))

# IS ELRM-20
IS_ELRM20 = register_weapon(Weapon(
    name="IS.ELRM-20",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=10,
    vrt=30,
    crits=8,
    tonnage=18.0,
    range_min=10,
    range_short=12,
    range_medium=24,
    range_long=36,
    ammo_per_ton=4,
    uses_ammo=True,
    missiles=20,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.ELRM | WeaponFlags.NOSPA,
    bv=1000,
))

# -----------------------------------------------------------------------------
# Inner Sphere Artillery Weapons
# -----------------------------------------------------------------------------

# IS Arrow IV System
IS_ARROW_IV = register_weapon(Weapon(
    name="IS.ArrowIVSystem",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.MISSILE,
    damage=20,
    heat=10,
    vrt=60,
    crits=15,
    tonnage=15.0,
    range_min=0,
    range_short=0,
    range_medium=0,
    range_long=5,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR,
    bv=171,
))

# IS Long Tom Artillery
IS_LONG_TOM = register_weapon(Weapon(
    name="IS.LongTom",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.MISSILE,
    damage=20,
    heat=20,
    vrt=60,
    crits=30,
    tonnage=30.0,
    range_min=0,
    range_short=0,
    range_medium=0,
    range_long=20,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR,
    bv=171,
))

# IS Long Tom Cannon
IS_LONG_TOM_CANNON = register_weapon(Weapon(
    name="IS.LongTomCannon",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.BALLISTIC,
    damage=20,
    heat=20,
    vrt=30,
    crits=15,
    tonnage=20.0,
    range_min=4,
    range_short=6,
    range_medium=13,
    range_long=20,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR,
    bv=348,
))

# IS Sniper Artillery
IS_SNIPER = register_weapon(Weapon(
    name="IS.Sniper",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.MISSILE,
    damage=10,
    heat=10,
    vrt=60,
    crits=20,
    tonnage=20.0,
    range_min=0,
    range_short=0,
    range_medium=0,
    range_long=12,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR,
    bv=86,
))

# IS Sniper Cannon
IS_SNIPER_CANNON = register_weapon(Weapon(
    name="IS.SniperCannon",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=10,
    vrt=25,
    crits=10,
    tonnage=15.0,
    range_min=2,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR,
    bv=115,
))

# IS Thumper Artillery
IS_THUMPER = register_weapon(Weapon(
    name="IS.Thumper",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.MISSILE,
    damage=5,
    heat=6,
    vrt=60,
    crits=15,
    tonnage=15.0,
    range_min=0,
    range_short=0,
    range_medium=0,
    range_long=14,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR,
    bv=40,
))

# IS Thumper Cannon
IS_THUMPER_CANNON = register_weapon(Weapon(
    name="IS.ThumperCannon",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=6,
    vrt=25,
    crits=7,
    tonnage=10.0,
    range_min=3,
    range_short=4,
    range_medium=9,
    range_long=14,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR,
    bv=58,
))

# -----------------------------------------------------------------------------
# Clan Energy Weapons
# -----------------------------------------------------------------------------

# Clan ER Medium Laser
CL_ER_MEDIUM_LASER = register_weapon(Weapon(
    name="CL.ERMediumLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=7,
    heat=5,
    vrt=15,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=7,
    range_long_water=10,
    special=WeaponFlags.CLAT,
    bv=108,
))

# Clan ER Large Laser
CL_ER_LARGE_LASER = register_weapon(Weapon(
    name="CL.ERLargeLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=12,
    vrt=20,
    crits=1,
    tonnage=4.0,
    range_min=0,
    range_short=8,
    range_medium=15,
    range_long=25,
    range_min_water=0,
    range_short_water=5,
    range_medium_water=10,
    range_long_water=15,
    special=WeaponFlags.CLAT,
    bv=249,
))

# Clan ER PPC
CL_ERPPC = register_weapon(Weapon(
    name="CL.ERPPC",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=15,
    heat=15,
    vrt=25,
    crits=2,
    tonnage=6.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=23,
    range_min_water=0,
    range_short_water=4,
    range_medium_water=10,
    range_long_water=16,
    special=WeaponFlags.CLAT,
    bv=412,
))

# Clan Medium Pulse Laser
CL_MEDIUM_PULSE_LASER = register_weapon(Weapon(
    name="CL.MediumPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=7,
    heat=4,
    vrt=18,
    crits=1,
    tonnage=2.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=5,
    range_long_water=8,
    special=WeaponFlags.PULSE | WeaponFlags.CLAT,
    bv=111,
))

# Clan Large Pulse Laser
CL_LARGE_PULSE_LASER = register_weapon(Weapon(
    name="CL.LargePulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=10,
    vrt=23,
    crits=2,
    tonnage=6.0,
    range_min=0,
    range_short=6,
    range_medium=14,
    range_long=20,
    range_min_water=0,
    range_short_water=4,
    range_medium_water=10,
    range_long_water=14,
    special=WeaponFlags.PULSE | WeaponFlags.CLAT,
    bv=265,
))

# Clan ER Small Laser
CL_ER_SMALL_LASER = register_weapon(Weapon(
    name="CL.ERSmallLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=5,
    heat=2,
    vrt=10,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=6,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=4,
    special=WeaponFlags.CLAT,
    bv=31,
))

# Clan ER Micro Laser
CL_ER_MICRO_LASER = register_weapon(Weapon(
    name="CL.ERMicroLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=2,
    heat=1,
    vrt=15,
    crits=1,
    tonnage=0.25,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=4,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=2,
    special=WeaponFlags.CLAT,
    bv=7,
))

# Clan Flamer
CL_FLAMER = register_weapon(Weapon(
    name="CL.Flamer",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=2,
    heat=3,
    vrt=10,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    special=WeaponFlags.CLAT | WeaponFlags.CHEAT,
    bv=6,
))

# Clan Heavy Large Laser
CL_HEAVY_LARGE_LASER = register_weapon(Weapon(
    name="CL.HeavyLargeLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=16,
    heat=18,
    vrt=30,
    crits=3,
    tonnage=4.0,
    range_min=0,
    range_short=5,
    range_medium=10,
    range_long=15,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=6,
    range_long_water=9,
    special=WeaponFlags.CLAT | WeaponFlags.HVYW,
    bv=243,
))

# Clan Heavy Medium Laser
CL_HEAVY_MEDIUM_LASER = register_weapon(Weapon(
    name="CL.HeavyMediumLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=7,
    vrt=25,
    crits=2,
    tonnage=1.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    range_min_water=0,
    range_short_water=2,
    range_medium_water=4,
    range_long_water=6,
    special=WeaponFlags.CLAT | WeaponFlags.HVYW,
    bv=76,
))

# Clan Heavy Small Laser
CL_HEAVY_SMALL_LASER = register_weapon(Weapon(
    name="CL.HeavySmallLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=6,
    heat=3,
    vrt=20,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=-1,
    special=WeaponFlags.CLAT | WeaponFlags.HVYW,
    bv=15,
))

# Clan Small Pulse Laser
CL_SMALL_PULSE_LASER = register_weapon(Weapon(
    name="CL.SmallPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=3,
    heat=2,
    vrt=13,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=6,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=4,
    special=WeaponFlags.PULSE | WeaponFlags.CLAT,
    bv=24,
))

# Clan Micro Pulse Laser
CL_MICRO_PULSE_LASER = register_weapon(Weapon(
    name="CL.MicroPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=3,
    heat=1,
    vrt=15,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    range_min_water=0,
    range_short_water=1,
    range_medium_water=2,
    range_long_water=2,
    special=WeaponFlags.PULSE | WeaponFlags.CLAT,
    bv=12,
))

# Clan ER Large Pulse Laser
CL_ER_LARGE_PULSE_LASER = register_weapon(Weapon(
    name="CL.ERLargePulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=13,
    vrt=30,
    crits=3,
    tonnage=6.0,
    range_min=0,
    range_short=7,
    range_medium=15,
    range_long=23,
    range_min_water=0,
    range_short_water=4,
    range_medium_water=10,
    range_long_water=16,
    special=WeaponFlags.PULSE | WeaponFlags.CLAT,
    bv=271,
))

# Clan ER Medium Pulse Laser
CL_ER_MEDIUM_PULSE_LASER = register_weapon(Weapon(
    name="CL.ERMediumPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=7,
    heat=6,
    vrt=30,
    crits=2,
    tonnage=2.0,
    range_min=0,
    range_short=5,
    range_medium=9,
    range_long=14,
    range_min_water=0,
    range_short_water=3,
    range_medium_water=6,
    range_long_water=8,
    special=WeaponFlags.PULSE | WeaponFlags.CLAT,
    bv=116,
))

# Clan ER Small Pulse Laser
CL_ER_SMALL_PULSE_LASER = register_weapon(Weapon(
    name="CL.ERSmallPulseLaser",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=5,
    heat=3,
    vrt=30,
    crits=1,
    tonnage=1.5,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=6,
    range_min_water=0,
    range_short_water=2,
    range_medium_water=3,
    range_long_water=4,
    special=WeaponFlags.PULSE | WeaponFlags.CLAT,
    bv=36,
))

# Clan Plasma Rifle
CL_PLASMA_RIFLE = register_weapon(Weapon(
    name="CL.PlasmaRifle",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=10,
    heat=15,
    vrt=25,
    crits=2,
    tonnage=6.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=22,
    range_min_water=0,
    range_short_water=4,
    range_medium_water=10,
    range_long_water=16,
    special=WeaponFlags.CLAT,
    bv=400,
))

# -----------------------------------------------------------------------------
# Clan Ballistic Weapons
# -----------------------------------------------------------------------------

# Clan Ultra AC/5
CL_ULTRA_AC5 = register_weapon(Weapon(
    name="CL.UltraAC/5",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=20,
    crits=3,
    tonnage=7.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.ULTRA | WeaponFlags.CLAT,
    bv=123,
))

# Clan Ultra AC/10
CL_ULTRA_AC10 = register_weapon(Weapon(
    name="CL.UltraAC/10",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=3,
    vrt=25,
    crits=4,
    tonnage=10.0,
    range_min=0,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.ULTRA | WeaponFlags.CLAT,
    bv=211,
))

# Clan Gauss Rifle
CL_GAUSS_RIFLE = register_weapon(Weapon(
    name="CL.GaussRifle",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=15,
    heat=1,
    vrt=30,
    crits=6,
    tonnage=12.0,
    range_min=2,
    range_short=7,
    range_medium=15,
    range_long=22,
    ammo_per_ton=8,
    uses_ammo=True,
    explosive_damage=20,
    special=WeaponFlags.GAUSS | WeaponFlags.CLAT,
    bv=321,
))

# Clan LB 10-X AC
CL_LBX10 = register_weapon(Weapon(
    name="CL.LB10-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=2,
    vrt=25,
    crits=5,
    tonnage=10.0,
    range_min=0,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.LBX | WeaponFlags.CLAT,
    bv=148,
))

# Clan LB 2-X AC
CL_LBX2 = register_weapon(Weapon(
    name="CL.LB2-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=15,
    crits=3,
    tonnage=5.0,
    range_min=4,
    range_short=10,
    range_medium=20,
    range_long=30,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.LBX | WeaponFlags.CLAT,
    bv=47,
))

# Clan LB 5-X AC
CL_LBX5 = register_weapon(Weapon(
    name="CL.LB5-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=20,
    crits=4,
    tonnage=7.0,
    range_min=3,
    range_short=8,
    range_medium=15,
    range_long=24,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.LBX | WeaponFlags.CLAT,
    bv=93,
))

# Clan LB 20-X AC
CL_LBX20 = register_weapon(Weapon(
    name="CL.LB20-XAC",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=20,
    heat=6,
    vrt=30,
    crits=9,
    tonnage=12.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.LBX | WeaponFlags.CLAT,
    bv=237,
))

# Clan Ultra AC/2
CL_ULTRA_AC2 = register_weapon(Weapon(
    name="CL.UltraAC/2",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=12,
    crits=2,
    tonnage=5.0,
    range_min=2,
    range_short=9,
    range_medium=18,
    range_long=27,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.ULTRA | WeaponFlags.CLAT,
    bv=62,
))

# Clan Ultra AC/20
CL_ULTRA_AC20 = register_weapon(Weapon(
    name="CL.UltraAC/20",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=20,
    heat=7,
    vrt=30,
    crits=8,
    tonnage=12.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.ULTRA | WeaponFlags.CLAT | WeaponFlags.SPLIT_CRITS,
    bv=337,
))

# Clan Rotary AC/2
CL_ROTARY_AC2 = register_weapon(Weapon(
    name="CL.RotaryAC/2",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=10,
    crits=4,
    tonnage=7.0,
    range_min=2,
    range_short=9,
    range_medium=18,
    range_long=27,
    ammo_per_ton=45,
    uses_ammo=True,
    special=WeaponFlags.RAC | WeaponFlags.CLAT,
    bv=75,
))

# Clan Rotary AC/5
CL_ROTARY_AC5 = register_weapon(Weapon(
    name="CL.RotaryAC/5",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=5,
    heat=1,
    vrt=15,
    crits=5,
    tonnage=10.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=20,
    uses_ammo=True,
    special=WeaponFlags.RAC | WeaponFlags.CLAT,
    bv=150,
))

# Clan Rotary AC/10
CL_ROTARY_AC10 = register_weapon(Weapon(
    name="CL.RotaryAC/10",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=10,
    heat=3,
    vrt=20,
    crits=7,
    tonnage=14.0,
    range_min=0,
    range_short=6,
    range_medium=12,
    range_long=18,
    ammo_per_ton=10,
    uses_ammo=True,
    special=WeaponFlags.RAC | WeaponFlags.CLAT,
    bv=250,
))

# Clan Rotary AC/20
CL_ROTARY_AC20 = register_weapon(Weapon(
    name="CL.RotaryAC/20",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=20,
    heat=7,
    vrt=25,
    crits=10,
    tonnage=16.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.RAC | WeaponFlags.CLAT,
    bv=400,
))

# Clan Machine Gun
CL_MACHINE_GUN = register_weapon(Weapon(
    name="CL.MachineGun",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=0,
    vrt=7,
    crits=1,
    tonnage=0.25,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    ammo_per_ton=200,
    uses_ammo=True,
    special=WeaponFlags.GMG | WeaponFlags.CLAT,
    bv=5,
))

# Clan Light Machine Gun
CL_LIGHT_MACHINE_GUN = register_weapon(Weapon(
    name="CL.LightMachineGun",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=1,
    heat=0,
    vrt=7,
    crits=1,
    tonnage=0.25,
    range_min=0,
    range_short=2,
    range_medium=4,
    range_long=6,
    ammo_per_ton=200,
    uses_ammo=True,
    special=WeaponFlags.GMG | WeaponFlags.CLAT,
    bv=5,
))

# Clan Heavy Machine Gun
CL_HEAVY_MACHINE_GUN = register_weapon(Weapon(
    name="CL.HeavyMachineGun",
    weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,
    damage=3,
    heat=0,
    vrt=7,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=2,
    range_long=3,
    ammo_per_ton=100,
    uses_ammo=True,
    special=WeaponFlags.GMG | WeaponFlags.CLAT,
    bv=6,
))

# Clan Anti-Missile System
CL_AMS = register_weapon(Weapon(
    name="CL.Anti-MissileSystem",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.BALLISTIC,
    damage=2,
    heat=1,
    vrt=10,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=1,
    range_long=1,
    ammo_per_ton=24,
    uses_ammo=True,
    special=WeaponFlags.AMS | WeaponFlags.CLAT,
    bv=63,
))

# Clan Laser AMS
CL_LASER_AMS = register_weapon(Weapon(
    name="CL.LaserAMS",
    ammo_per_ton=24,
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.ENERGY,
    damage=2,
    heat=1,
    vrt=25,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=1,
    range_long=1,
    special=WeaponFlags.AMS | WeaponFlags.CLAT,
    bv=105,
))

# Clan Arrow IV System
CL_ARROW_IV = register_weapon(Weapon(
    name="CL.ArrowIVSystem",
    weapon_type=WeaponType.TARTILLERY,
    weapon_class=WeaponClass.MISSILE,
    damage=20,
    heat=10,
    vrt=60,
    crits=12,
    tonnage=12.0,
    range_min=0,
    range_short=0,
    range_medium=0,
    range_long=6,
    ammo_per_ton=5,
    uses_ammo=True,
    special=WeaponFlags.IDF | WeaponFlags.DAR | WeaponFlags.CLAT,
    bv=171,
))

# Clan A-Pod
CL_APOD = register_weapon(Weapon(
    name="CL.A-Pod",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.BALLISTIC,
    damage=0,
    heat=0,
    vrt=30,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=1,
    range_long=1,
    special=WeaponFlags.A_POD | WeaponFlags.CLAT,
    bv=1,
))

# IS A-Pod
IS_APOD = register_weapon(Weapon(
    name="IS.A-Pod",
    weapon_type=WeaponType.TBEAM,
    weapon_class=WeaponClass.BALLISTIC,
    damage=0,
    heat=0,
    vrt=30,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=1,
    range_medium=1,
    range_long=1,
    special=WeaponFlags.A_POD,
    bv=1,
))

# -----------------------------------------------------------------------------
# Clan Missile Weapons
# -----------------------------------------------------------------------------

# Clan SRM-6
CL_SRM6 = register_weapon(Weapon(
    name="CL.SRM-6",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=4,
    vrt=15,
    crits=1,
    tonnage=1.5,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=15,
    uses_ammo=True,
    missiles=6,
    damage_per_missile=2,
    special=WeaponFlags.CLAT,
    bv=59,
))

# Clan LRM-10
CL_LRM10 = register_weapon(Weapon(
    name="CL.LRM-10",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=4,
    vrt=20,
    crits=1,
    tonnage=2.5,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=12,
    uses_ammo=True,
    missiles=10,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=109,
))

# Clan LRM-20
CL_LRM20 = register_weapon(Weapon(
    name="CL.LRM-20",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=6,
    # 20, not 30: the C table entry for CL.LRM-20 uses VRT_CL_LRM10
    # (weapons.h:206), i.e. the LRM-10 recycle of 20 (weapons.vrt.h:16), while
    # VRT_CL_LRM20 30 (weapons.vrt.h:18) goes unused.  Looks like a C typo;
    # ported as-is per the prime directive.
    vrt=20,
    crits=4,
    tonnage=5.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=20,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=220,
))

# Clan Streak SRM-6
CL_STREAK_SRM6 = register_weapon(Weapon(
    name="CL.StreakSRM-6",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=4,
    vrt=15,
    crits=2,
    tonnage=3.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=15,
    uses_ammo=True,
    missiles=6,
    damage_per_missile=2,
    special=WeaponFlags.STREAK | WeaponFlags.CLAT | WeaponFlags.NOSPA,
    bv=119,
))

# Clan SRM-2
CL_SRM2 = register_weapon(Weapon(
    name="CL.SRM-2",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=0.5,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=50,
    uses_ammo=True,
    missiles=2,
    damage_per_missile=2,
    special=WeaponFlags.CLAT,
    bv=21,
))

# Clan SRM-4
CL_SRM4 = register_weapon(Weapon(
    name="CL.SRM-4",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=3,
    vrt=15,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=3,
    range_medium=6,
    range_long=9,
    ammo_per_ton=25,
    uses_ammo=True,
    missiles=4,
    damage_per_missile=2,
    special=WeaponFlags.CLAT,
    bv=39,
))

# Clan LRM-5
CL_LRM5 = register_weapon(Weapon(
    name="CL.LRM-5",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=24,
    uses_ammo=True,
    missiles=5,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=55,
))

# Clan LRM-15
CL_LRM15 = register_weapon(Weapon(
    name="CL.LRM-15",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=5,
    vrt=25,
    crits=2,
    tonnage=3.5,
    range_min=0,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=8,
    uses_ammo=True,
    missiles=15,
    damage_per_missile=1,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=164,
))

# Clan Streak SRM-2
CL_STREAK_SRM2 = register_weapon(Weapon(
    name="CL.StreakSRM-2",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=1.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=50,
    uses_ammo=True,
    missiles=2,
    damage_per_missile=2,
    special=WeaponFlags.STREAK | WeaponFlags.CLAT | WeaponFlags.NOSPA,
    bv=40,
))

# Clan Streak SRM-4
CL_STREAK_SRM4 = register_weapon(Weapon(
    name="CL.StreakSRM-4",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=3,
    vrt=15,
    crits=1,
    tonnage=2.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=25,
    uses_ammo=True,
    missiles=4,
    damage_per_missile=2,
    special=WeaponFlags.STREAK | WeaponFlags.CLAT | WeaponFlags.NOSPA,
    bv=79,
))

# Clan ATM-3
CL_ATM3 = register_weapon(Weapon(
    name="CL.ATM-3",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=2,
    vrt=15,
    crits=2,
    tonnage=1.5,
    range_min=4,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=20,
    uses_ammo=True,
    missiles=3,
    damage_per_missile=2,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=53,
))

# Clan ATM-6
CL_ATM6 = register_weapon(Weapon(
    name="CL.ATM-6",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=4,
    vrt=20,
    crits=3,
    tonnage=3.5,
    range_min=4,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=10,
    uses_ammo=True,
    missiles=6,
    damage_per_missile=2,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=105,
))

# Clan ATM-9
CL_ATM9 = register_weapon(Weapon(
    name="CL.ATM-9",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=6,
    vrt=25,
    crits=4,
    tonnage=5.0,
    range_min=4,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=7,
    uses_ammo=True,
    missiles=9,
    damage_per_missile=2,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=147,
))

# Clan ATM-12
CL_ATM12 = register_weapon(Weapon(
    name="CL.ATM-12",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=2,
    heat=8,
    vrt=30,
    crits=5,
    tonnage=7.0,
    range_min=4,
    range_short=5,
    range_medium=10,
    range_long=15,
    ammo_per_ton=5,
    uses_ammo=True,
    missiles=12,
    damage_per_missile=2,
    special=WeaponFlags.IDF | WeaponFlags.CLAT,
    bv=212,
))

# Clan NARC Beacon
CL_NARC = register_weapon(Weapon(
    name="CL.NarcBeacon",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=4,
    heat=1,
    vrt=30,
    crits=1,
    tonnage=2.0,
    range_min=0,
    range_short=4,
    range_medium=8,
    range_long=12,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=1,
    damage_per_missile=4,
    special=WeaponFlags.NARC | WeaponFlags.CLAT,
    bv=30,
))

# Clan Streak LRM-5
CL_STREAK_LRM5 = register_weapon(Weapon(
    name="CL.StreakLRM-5",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=2,
    vrt=15,
    crits=1,
    tonnage=2.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=24,
    uses_ammo=True,
    missiles=5,
    damage_per_missile=1,
    special=WeaponFlags.STREAK | WeaponFlags.CLAT | WeaponFlags.NOSPA,
    bv=87,
))

# Clan Streak LRM-10
CL_STREAK_LRM10 = register_weapon(Weapon(
    name="CL.StreakLRM-10",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=4,
    vrt=20,
    crits=2,
    tonnage=5.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=12,
    uses_ammo=True,
    missiles=10,
    damage_per_missile=1,
    special=WeaponFlags.STREAK | WeaponFlags.CLAT | WeaponFlags.NOSPA,
    bv=173,
))

# Clan Streak LRM-15
CL_STREAK_LRM15 = register_weapon(Weapon(
    name="CL.StreakLRM-15",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=5,
    vrt=25,
    crits=3,
    tonnage=7.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=8,
    uses_ammo=True,
    missiles=15,
    damage_per_missile=1,
    special=WeaponFlags.STREAK | WeaponFlags.CLAT | WeaponFlags.NOSPA,
    bv=260,
))

# Clan Streak LRM-20
CL_STREAK_LRM20 = register_weapon(Weapon(
    name="CL.StreakLRM-20",
    weapon_type=WeaponType.TMISSILE,
    weapon_class=WeaponClass.MISSILE,
    damage=1,
    heat=6,
    vrt=30,
    crits=5,
    tonnage=10.0,
    range_min=6,
    range_short=7,
    range_medium=14,
    range_long=21,
    ammo_per_ton=6,
    uses_ammo=True,
    missiles=20,
    damage_per_missile=1,
    special=WeaponFlags.STREAK | WeaponFlags.CLAT | WeaponFlags.NOSPA,
    bv=346,
))


# =============================================================================
# Missile Hit Tables (from weapons.h MissileHitTable[])
# =============================================================================

# Index by 2d6 roll (2-12), so 11 entries
# Values are number of missiles that hit
# Sizes: 2, 3, 4, 5, 6, 7, 9, 10, 12, 15, 20, 30, 40
MISSILE_HIT_TABLE = {
    2:  {2: 1, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 9: 2, 10: 3, 12: 4, 15: 5, 20: 6, 30: 10, 40: 12},
    3:  {2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 2, 9: 2, 10: 3, 12: 4, 15: 5, 20: 6, 30: 10, 40: 12},
    4:  {2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3, 9: 3, 10: 4, 12: 6, 15: 6, 20: 9, 30: 12, 40: 18},
    5:  {2: 1, 3: 1, 4: 2, 5: 3, 6: 3, 7: 4, 9: 4, 10: 6, 12: 6, 15: 9, 20: 12, 30: 18, 40: 24},
    6:  {2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 4, 9: 4, 10: 6, 12: 8, 15: 9, 20: 12, 30: 18, 40: 24},
    7:  {2: 1, 3: 2, 4: 3, 5: 3, 6: 4, 7: 5, 9: 5, 10: 6, 12: 8, 15: 9, 20: 12, 30: 18, 40: 24},
    8:  {2: 2, 3: 2, 4: 3, 5: 3, 6: 4, 7: 5, 9: 6, 10: 6, 12: 8, 15: 9, 20: 12, 30: 18, 40: 24},
    9:  {2: 2, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 9: 7, 10: 8, 12: 10, 15: 12, 20: 16, 30: 24, 40: 32},
    10: {2: 2, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 9: 8, 10: 8, 12: 10, 15: 12, 20: 16, 30: 24, 40: 32},
    11: {2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 9: 9, 10: 10, 12: 12, 15: 15, 20: 20, 30: 30, 40: 40},
    12: {2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 9: 9, 10: 10, 12: 12, 15: 15, 20: 20, 30: 30, 40: 40},
}


def get_missiles_hit(roll: int, rack_size: int) -> int:
    """
    Determine how many missiles hit based on cluster roll.

    Args:
        roll: 2d6 roll result (2-12)
        rack_size: Number of missiles in the rack (2, 4, 5, 6, 10, 15, 20)

    Returns:
        Number of missiles that hit
    """
    roll = max(2, min(12, roll))  # Clamp to valid range

    if rack_size not in MISSILE_HIT_TABLE[roll]:
        # Find closest match
        sizes = sorted(MISSILE_HIT_TABLE[roll].keys())
        if rack_size < sizes[0]:
            return MISSILE_HIT_TABLE[roll][sizes[0]]
        if rack_size > sizes[-1]:
            return MISSILE_HIT_TABLE[roll][sizes[-1]]
        # Interpolate
        for i, s in enumerate(sizes):
            if s >= rack_size:
                return MISSILE_HIT_TABLE[roll][s]

    return MISSILE_HIT_TABLE[roll].get(rack_size, 1)


# =============================================================================
# Convenience Functions
# =============================================================================

def get_all_weapons() -> list[Weapon]:
    """Get a list of all registered weapons."""
    return list(WEAPON_CATALOG.values())


def get_weapons_by_type(weapon_type: WeaponType) -> list[Weapon]:
    """Get all weapons of a specific type."""
    return [w for w in WEAPON_CATALOG.values() if w.weapon_type == weapon_type]


def get_weapons_by_class(weapon_class: WeaponClass) -> list[Weapon]:
    """Get all weapons of a specific class."""
    return [w for w in WEAPON_CATALOG.values() if w.weapon_class == weapon_class]


def get_clan_weapons() -> list[Weapon]:
    """Get all Clan tech weapons."""
    return [w for w in WEAPON_CATALOG.values() if w.is_clan]


def get_is_weapons() -> list[Weapon]:
    """Get all Inner Sphere weapons."""
    return [w for w in WEAPON_CATALOG.values() if not w.is_clan]


# =============================================================================
# Advanced Weapon Mode Functions
# =============================================================================

@dataclass
class UltraACResult:
    """Result of an Ultra AC double-tap attempt."""
    shots_fired: int      # 1 or 2
    jammed: bool          # True if weapon jammed
    heat_generated: int   # Total heat (weapon heat * shots)
    ammo_used: int        # Total ammo used


def resolve_ultra_ac_fire(weapon: Weapon, double_tap: bool = False) -> UltraACResult:
    """
    Resolve Ultra AC firing mode.

    Ultra ACs can fire once normally, or attempt double-tap (fire twice).
    Double-tap has a chance to jam the weapon on a roll of 2 on 2d6.

    Reference: weapons.h ULTRA flag behavior

    Args:
        weapon: The Ultra AC weapon
        double_tap: Whether to attempt double-tap mode

    Returns:
        UltraACResult with shots fired and jam status
    """
    if not weapon.special & WeaponFlags.ULTRA:
        return UltraACResult(shots_fired=1, jammed=False,
                            heat_generated=weapon.heat, ammo_used=1)

    if not double_tap:
        return UltraACResult(shots_fired=1, jammed=False,
                            heat_generated=weapon.heat, ammo_used=1)

    # Double-tap mode: 2 shots but risk jam on roll of 2
    from core.randomness import roll
    jam_roll = roll('jam_rolls')

    if jam_roll == 2:
        # Jammed! Weapon fired once before jamming
        return UltraACResult(shots_fired=1, jammed=True,
                            heat_generated=weapon.heat, ammo_used=1)

    return UltraACResult(shots_fired=2, jammed=False,
                        heat_generated=weapon.heat * 2, ammo_used=2)


@dataclass
class RotaryACResult:
    """Result of a Rotary AC firing attempt."""
    shots_fired: int      # 2, 4, or 6
    jammed: bool          # True if weapon jammed
    heat_generated: int   # Total heat (weapon heat * shots)
    ammo_used: int        # Total ammo used


def resolve_rotary_ac_fire(weapon: Weapon, rate: int = 2) -> RotaryACResult:
    """
    Resolve Rotary AC firing mode.

    Rotary ACs can fire at rates of 2, 4, or 6 shots per turn.
    Higher rates have increased jam chance.
    - 2 shots: Jam on 2 (2d6)
    - 4 shots: Jam on 2-3 (2d6)
    - 6 shots: Jam on 2-4 (2d6)

    Reference: weapons.h RAC flag behavior

    Args:
        weapon: The Rotary AC weapon
        rate: Fire rate (2, 4, or 6)

    Returns:
        RotaryACResult with shots fired and jam status
    """
    if not weapon.special & WeaponFlags.RAC:
        return RotaryACResult(shots_fired=1, jammed=False,
                             heat_generated=weapon.heat, ammo_used=1)

    # Clamp rate to valid values
    rate = max(2, min(6, rate))
    if rate not in (2, 4, 6):
        rate = 2

    from core.randomness import roll
    jam_roll = roll('jam_rolls')

    # Jam thresholds based on rate
    jam_threshold = {2: 2, 4: 3, 6: 4}

    if jam_roll <= jam_threshold[rate]:
        # Jammed! Weapon fires reduced shots before jamming
        fired = max(1, rate // 2)
        return RotaryACResult(shots_fired=fired, jammed=True,
                             heat_generated=weapon.heat * fired, ammo_used=fired)

    return RotaryACResult(shots_fired=rate, jammed=False,
                         heat_generated=weapon.heat * rate, ammo_used=rate)


@dataclass
class LBXACResult:
    """Result of an LBX AC firing attempt."""
    mode: str             # "slug" or "cluster"
    damage: int           # Damage per hit (10 for slug, 1 per pellet for cluster)
    pellets: int          # Number of pellets (1 for slug, damage value for cluster)
    bth_modifier: int     # BTH modifier (-1 for cluster vs mobile targets)


def get_lbx_fire_mode(weapon: Weapon, cluster_mode: bool = False,
                       target_moved: bool = False) -> LBXACResult:
    """
    Get LBX AC firing mode statistics.

    LBX ACs can fire normal slugs or cluster rounds.
    Cluster mode fires pellets like a shotgun with -1 BTH vs. moving targets.
    Each pellet does 1 damage and is rolled separately for hit location.

    Reference: weapons.h LBX flag behavior

    Args:
        weapon: The LBX AC weapon
        cluster_mode: Whether to use cluster ammo
        target_moved: Whether target moved (for cluster BTH bonus)

    Returns:
        LBXACResult with mode and damage info
    """
    if not weapon.special & WeaponFlags.LBX:
        return LBXACResult(mode="slug", damage=weapon.damage,
                          pellets=1, bth_modifier=0)

    if not cluster_mode:
        return LBXACResult(mode="slug", damage=weapon.damage,
                          pellets=1, bth_modifier=0)

    # Cluster mode: fires weapon.damage pellets of 1 damage each
    bth_mod = -1 if target_moved else 0
    return LBXACResult(mode="cluster", damage=1,
                      pellets=weapon.damage, bth_modifier=bth_mod)


@dataclass
class StreakResult:
    """Result of a Streak missile lock attempt."""
    locked: bool          # Whether lock was achieved
    missiles: int         # Number of missiles if locked (all hit)


def resolve_streak_lock(weapon: Weapon, base_bth: int) -> StreakResult:
    """
    Resolve Streak missile lock attempt.

    Streak missiles are all-or-nothing: either all missiles hit or none fire.
    The lock roll uses the same target number as a normal attack.
    No ammo is consumed if lock fails.

    Reference: weapons.h STREAK flag behavior

    Args:
        weapon: The Streak missile weapon
        base_bth: Base to-hit number for the attack

    Returns:
        StreakResult with lock status and missile count
    """
    if not weapon.special & WeaponFlags.STREAK:
        # Not a streak weapon, normal firing
        return StreakResult(locked=True, missiles=weapon.missiles)

    from core.randomness import roll
    lock_roll = roll('lock_rolls')

    if lock_roll >= base_bth:
        # Lock achieved - all missiles will hit
        return StreakResult(locked=True, missiles=weapon.missiles)

    # Lock failed - no missiles fire, no ammo consumed
    return StreakResult(locked=False, missiles=0)


def is_pulse_weapon(weapon: Weapon) -> bool:
    """Check if weapon is a pulse laser."""
    return bool(weapon.special & WeaponFlags.PULSE)


def is_ultra_capable(weapon: Weapon) -> bool:
    """Check if weapon can use Ultra double-tap mode."""
    return bool(weapon.special & WeaponFlags.ULTRA)


def is_rotary_capable(weapon: Weapon) -> bool:
    """Check if weapon can use Rotary multi-shot mode."""
    return bool(weapon.special & WeaponFlags.RAC)


def is_lbx_capable(weapon: Weapon) -> bool:
    """Check if weapon can use LBX cluster mode."""
    return bool(weapon.special & WeaponFlags.LBX)


def is_streak_weapon(weapon: Weapon) -> bool:
    """Check if weapon is a Streak missile system."""
    return bool(weapon.special & WeaponFlags.STREAK)


def is_indirect_fire_capable(weapon: Weapon) -> bool:
    """Check if weapon can use indirect fire."""
    return bool(weapon.special & WeaponFlags.IDF)


def is_gauss_weapon(weapon: Weapon) -> bool:
    """Check if weapon is a Gauss rifle (no heat, ammo explosion)."""
    return bool(weapon.special & WeaponFlags.GAUSS)


IS_COOLANT_GUN = register_weapon(Weapon(
    name='IS.CoolantGun',weapon_type=WeaponType.TAMMO,
    weapon_class=WeaponClass.BALLISTIC,damage=3,heat=0,vrt=15,crits=1,
    tonnage=1,range_short=1,range_medium=2,range_long=3,
    ammo_per_ton=25,uses_ammo=True,special=WeaponFlags.CHEAT,bv=15))


def get_pulse_bth_modifier(weapon: Weapon) -> int:
    """Get BTH modifier for pulse weapons (-2)."""
    if is_pulse_weapon(weapon):
        return -2
    return 0


def get_mrm_bth_modifier(weapon: Weapon) -> int:
    """Get BTH modifier for MRM weapons (+1)."""
    if weapon.special & WeaponFlags.MRM:
        return 1
    return 0


def get_heavy_weapon_bth_modifier(weapon: Weapon) -> int:
    """Get BTH modifier for heavy weapons (+1)."""
    if weapon.special & WeaponFlags.HVYW:
        return 1
    return 0


def _register_missing_construction_weapons():
    """Complete active source metadata without changing any existing runtime ID."""
    from entities.construction_weapon_data import WEAPON_ROWS
    for row in WEAPON_ROWS:
        name,vrt,kind,heat,damage,minimum,short,medium,long,wmin,wshort,wmedium,wlong,crits,ammo,weight,explosion,flags=row
        if name in WEAPON_CATALOG:
            continue
        special=WeaponFlags.NONE
        for flag in flags:
            special |= WeaponFlags[flag]
        weapon_type=WeaponType[kind]
        category={WeaponType.TBEAM:WeaponClass.ENERGY,WeaponType.TAMMO:WeaponClass.BALLISTIC,
                  WeaponType.TMISSILE:WeaponClass.MISSILE,WeaponType.TARTILLERY:WeaponClass.BALLISTIC,
                  WeaponType.THAND:WeaponClass.PHYSICAL}[weapon_type]
        missiles=int(name.rsplit('-',1)[1]) if weapon_type==WeaponType.TMISSILE and name.rsplit('-',1)[-1].isdigit() else 1
        register_weapon(Weapon(name=name,vrt=vrt,weapon_type=weapon_type,weapon_class=category,
            heat=heat,damage=damage,range_min=minimum,range_short=short,range_medium=medium,range_long=long,
            range_min_water=wmin,range_short_water=wshort,range_medium_water=wmedium,range_long_water=wlong,
            crits=crits,ammo_per_ton=ammo,tonnage=weight/100,explosive_damage=explosion,special=special,
            uses_ammo=ammo>0,missiles=missiles,damage_per_missile=damage if weapon_type==WeaponType.TMISSILE else 0))


_register_missing_construction_weapons()
