"""Game entities - mechs, weapons."""

from .mech import (
    # Main classes
    Mech,
    Section,
    CriticalSlot,
    WeaponState,
    # Location enums
    Location,
    VehicleLocation,
    AeroLocation,
    # Type enums
    UnitType,
    MoveType,
    # Status flags
    MechStatus,
    CritStatus,
    SectionConfig,
    Specials,
    FireMode,
    # Constants
    NUM_SECTIONS,
    NUM_CRITICALS,
    NUM_VEH_SECTIONS,
    NUM_AERO_SECTIONS,
)

from .weapon import (
    # Main classes
    Weapon,
    # Enums
    WeaponType,
    WeaponClass,
    WeaponFlags,
    RangeBracket,
    # Catalog functions
    WEAPON_CATALOG,
    get_weapon,
    get_weapon_by_index,
    get_all_weapons,
    get_weapons_by_type,
    get_weapons_by_class,
    get_clan_weapons,
    get_is_weapons,
    # Missile hit table
    MISSILE_HIT_TABLE,
    get_missiles_hit,
    # Range constants
    RANGE_BTH_MODIFIERS,
    # Pre-registered weapons (commonly used)
    IS_MEDIUM_LASER,
    IS_LARGE_LASER,
    IS_PPC,
    IS_AC10,
    IS_AC20,
    IS_GAUSS_RIFLE,
    IS_SRM6,
    IS_LRM10,
    IS_LRM20,
    CL_ER_MEDIUM_LASER,
    CL_ER_LARGE_LASER,
    CL_ERPPC,
    CL_ULTRA_AC10,
    CL_LRM20,
    CL_STREAK_SRM6,
)

__all__ = [
    # Main classes - Mech
    "Mech",
    "Section",
    "CriticalSlot",
    "WeaponState",
    # Main classes - Weapon
    "Weapon",
    # Location enums
    "Location",
    "VehicleLocation",
    "AeroLocation",
    # Type enums
    "UnitType",
    "MoveType",
    # Weapon enums
    "WeaponType",
    "WeaponClass",
    "WeaponFlags",
    "RangeBracket",
    # Status flags
    "MechStatus",
    "CritStatus",
    "SectionConfig",
    "Specials",
    "FireMode",
    # Constants
    "NUM_SECTIONS",
    "NUM_CRITICALS",
    "NUM_VEH_SECTIONS",
    "NUM_AERO_SECTIONS",
    # Weapon catalog
    "WEAPON_CATALOG",
    "get_weapon",
    "get_weapon_by_index",
    "get_all_weapons",
    "get_weapons_by_type",
    "get_weapons_by_class",
    "get_clan_weapons",
    "get_is_weapons",
    "MISSILE_HIT_TABLE",
    "get_missiles_hit",
    "RANGE_BTH_MODIFIERS",
    # Pre-registered weapons
    "IS_MEDIUM_LASER",
    "IS_LARGE_LASER",
    "IS_PPC",
    "IS_AC10",
    "IS_AC20",
    "IS_GAUSS_RIFLE",
    "IS_SRM6",
    "IS_LRM10",
    "IS_LRM20",
    "CL_ER_MEDIUM_LASER",
    "CL_ER_LARGE_LASER",
    "CL_ERPPC",
    "CL_ULTRA_AC10",
    "CL_LRM20",
    "CL_STREAK_SRM6",
]
