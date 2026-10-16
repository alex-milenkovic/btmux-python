# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.move.c
#   btech/mech.ood.c
#   btech/mech.sensor.c
#   btech/mech.update.c
#   btech/mechrep.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/map.h
#   btech/src/btech/mech.h
#   btech/src/glue.c
#   btech/src/glue.scode.c
#   btech/src/include/btconfig.h
#   btech/template.c
# Historical Aerospace sources:
#   btech/mech.damage.c
#   btech/mech.move.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/template.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/map.h
#   src/hcode/btech/mech.events.c
#   src/hcode/btech/mech.h
#   src/hcode/btech/mech.ood.c
#   src/hcode/btech/mech.sensor.c
#   src/hcode/btech/mechrep.c
#   src/hcode/glue.c
#   src/hcode/glue.scode.c
#   src/hcode/include/btconfig.h

"""
Mech entity for BTMux Python reimplementation.

This module defines the Mech class and related data structures that represent
a BattleMech or other combat unit in the game. The structure closely follows
BTMux's MECH struct from mech.h.

Reference:
- BTMux btech/src/btech/mech.h - MECH struct (mech_ud, mech_pd, mech_rd)
- BTMux btech/src/btech/btmacros.h - Accessor macros

Key components:
- Position: x, y (hex coords), fx, fy (float coords), z, fz (elevation)
- Movement: speed, desired_speed, facing, desired_facing
- Heat: heat, plus_heat, minus_heat, heat_sinks
- Armor: per-section armor, internal structure, rear armor
- Weapons: weapon slots with type, ammo, recycle time
"""

from dataclasses import dataclass, field
from itertools import count
from enum import IntEnum, IntFlag, auto
from typing import Any, Optional
import math

_MECH_IDS = count(1)


# =============================================================================
# Location/Section Constants (from mech.h)
# =============================================================================

class Location(IntEnum):
    """
    Body section locations for mechs.

    Reference: mech.h lines 551-559
    """
    LARM = 0       # Left Arm
    RARM = 1       # Right Arm
    LTORSO = 2     # Left Torso
    RTORSO = 3     # Right Torso
    CTORSO = 4     # Center Torso
    LLEG = 5       # Left Leg
    RLEG = 6       # Right Leg
    HEAD = 7       # Head


NUM_SECTIONS = 8
NUM_CRITICALS = 12  # Critical slots per section


class VehicleLocation(IntEnum):
    """
    Body section locations for vehicles.

    Reference: mech.h lines 562-568
    """
    LSIDE = 0      # Left Side
    RSIDE = 1      # Right Side
    FSIDE = 2      # Front Side
    BSIDE = 3      # Back Side
    TURRET = 4     # Turret
    ROTOR = 5      # Rotor (VTOL only)


NUM_VEH_SECTIONS = 6


class AeroLocation(IntEnum):
    """
    Body section locations for aerospace fighters.

    Reference: pre-AT2 mech.h, six-location fighter layout.
    """
    NOSE = 0
    LWING = 1
    RWING = 2
    FUSELAGE = 3
    COCKPIT = 4
    ENGINE = 5


NUM_AERO_SECTIONS = 6


# =============================================================================
# Unit Types and Movement Types (from mech.h)
# =============================================================================

class UnitType(IntEnum):
    """
    Unit class types.

    Reference: mech.h lines 711-722
    """
    MECH = 0
    VEH_GROUND = 1
    VTOL = 2
    VEH_NAVAL = 3
    SPHEROID_DS = 4
    AERO = 5
    MW = 6           # Ejected MechWarrior
    DS = 7           # Aerodyne DropShip
    BSUIT = 8


class MoveType(IntEnum):
    """
    Movement types.

    Reference: mech.h lines 728-744
    """
    BIPED = 0
    TRACK = 1
    WHEEL = 2
    HOVER = 3
    VTOL = 4
    HULL = 5
    FOIL = 6
    FLY = 7
    QUAD = 8
    SUB = 9
    NONE = 10


# =============================================================================
# Status Flags (from mech.h)
# =============================================================================

class MechStatus(IntFlag):
    """
    Mech status flags.

    Reference: mech.h lines 987-1018
    """
    NONE = 0
    LANDED = 0x00000001           # For VTOL use only
    TORSO_RIGHT = 0x00000002      # Torso heading -= 60 degrees
    TORSO_LEFT = 0x00000004       # Torso heading += 60 degrees
    STARTED = 0x00000008          # Mech is warmed up
    PARTIAL_COVER = 0x00000010
    DESTROYED = 0x00000020
    JUMPING = 0x00000040          # Handled in UPDATE
    FALLEN = 0x00000080
    DFA_ATTACK = 0x00000100
    PERFORMING_ACTION = 0x00000200
    FLIPPED_ARMS = 0x00000400
    AMS_ENABLED = 0x00000800      # Only settable if mech has ANTI-MISSILE_TECH
    EXPLODE_SAFE = 0x00001000     # Used to prevent a unit from doing EXPLODE AMMO
    UNCONSCIOUS = 0x00002000      # Pilot is unconscious
    TOWED = 0x00004000            # Someone's towing us
    LOCK_TARGET = 0x00008000      # We mean business
    LOCK_BUILDING = 0x00010000    # Hit building
    LOCK_HEX = 0x00020000         # Hit hex (clear / ignite)
    LOCK_HEX_IGN = 0x00040000
    LOCK_HEX_CLR = 0x00080000
    MASC_ENABLED = 0x00100000     # Using MASC
    BLINDED = 0x00200000          # Pilot has been blinded momentarily
    COMBAT_SAFE = 0x00400000      # Can't be hurt
    AUTOCON_WHEN_SHUTDOWN = 0x00800000
    FIRED = 0x01000000            # Fired at something
    SCHARGE_ENABLED = 0x02000000
    HULLDOWN = 0x04000000
    UNDERSPECIAL = 0x08000000
    UNDERGRAVITY = 0x10000000
    UNDERTEMPERATURE = 0x20000000
    UNDERVACUUM = 0x40000000

    # Combined masks
    CONDITIONS = UNDERSPECIAL | UNDERGRAVITY | UNDERTEMPERATURE | UNDERVACUUM
    LOCK_MODES = LOCK_TARGET | LOCK_BUILDING | LOCK_HEX | LOCK_HEX_IGN | LOCK_HEX_CLR


class MechStatus2(IntFlag):
    """
    Second status word (MechStatus2 / rd.status2).

    Reference: mech.h lines 1026-1063.  systems/ecm.py predates this enum
    and keeps equal-valued module constants for the ECM bits.
    """
    NONE = 0
    ECM_ENABLED = 0x00000001          # Unit ECM is enabled
    ECCM_ENABLED = 0x00000002         # Unit ECCM is enabled
    ECM_DISTURBANCE = 0x00000004      # Unit affected by ECM
    ECM_PROTECTED = 0x00000008        # Unit protected by ECM
    ECM_COUNTERED = 0x00000010        # ECM countered by ECCM
    SLITE_ON = 0x00000020             # Searchlight is on
    STH_ARMOR_ON = 0x00000040         # Stealth armor enabled
    NULLSIGSYS_ON = 0x00000080        # Null signature system enabled
    ANGEL_ECM_ENABLED = 0x00000100
    ANGEL_ECCM_ENABLED = 0x00000200
    ANGEL_ECM_PROTECTED = 0x00000400
    ANGEL_ECM_DISTURBED = 0x00000800
    PER_ECM_ENABLED = 0x00001000      # Personal (iNARC-pod) ECM
    PER_ECCM_ENABLED = 0x00002000
    AUTOTURN_TURRET = 0x00004000      # Auto-turret tracks locked target
    SPRINTING = 0x00010000
    EVADING = 0x00020000
    DODGING = 0x00040000
    ATTACKEMIT_MECH = 0x00080000
    UNIT_MOUNTED = 0x00100000         # Mounted by a battlesuit
    UNIT_MOUNTING = 0x00200000        # Mounting another unit
    FORTIFIED = 0x00400000
    WEAPONS_HOLD = 0x00800000         # Unable to fire
    NO_GUN_XP = 0x01000000

    # Grouping masks (mech.h:1062-1063)
    MOVE_MODES = SPRINTING | EVADING | DODGING
    MOVE_MODES_LOCK = SPRINTING | EVADING


class CritStatus(IntFlag):
    """
    Critical damage status flags.

    Reference: mech.h lines 1088-1118
    """
    NONE = 0
    GYRO_DESTROYED = 0x00000001
    SENSORS_DAMAGED = 0x00000002
    TAG_DESTROYED = 0x00000004
    HIDDEN = 0x00000008
    GYRO_DAMAGED = 0x00000010
    HIP_DAMAGED = 0x00000020
    LIFE_SUPPORT_DESTROYED = 0x00000040
    ANGEL_ECM_DESTROYED = 0x00000080
    C3I_DESTROYED = 0x00000100
    NSS_DESTROYED = 0x00000200
    SLITE_DEST = 0x00000400
    SLITE_LIT = 0x00000800
    LOAD_OK = 0x00001000          # Carried load recalculated
    OWEIGHT_OK = 0x00002000       # Own weight recalculated
    SPEED_OK = 0x00004000         # Total speed recalculated
    HEATCUTOFF = 0x00008000
    TOWABLE = 0x00010000
    HIP_DESTROYED = 0x00020000
    TC_DESTROYED = 0x00040000
    C3_DESTROYED = 0x00080000
    ECM_DESTROYED = 0x00100000
    BEAGLE_DESTROYED = 0x00200000
    JELLIED = 0x00400000          # Got inferno gel on us
    PC_INITIALIZED = 0x00800000   # PC-initialization done already
    SPINNING = 0x01000000
    CLAIRVOYANT = 0x02000000      # See everything
    INVISIBLE = 0x04000000        # Unable to be seen
    CHEAD = 0x08000000            # Altered heading
    OBSERVATORIC = 0x10000000
    BLOODHOUND_DESTROYED = 0x20000000
    MECH_STUNNED = 0x40000000


class SectionConfig(IntFlag):
    """
    Section configuration flags.

    Reference: mech.h lines 694-700
    """
    NONE = 0
    CASE_TECH = 0x01              # Section has CASE technology
    SECTION_DESTROYED = 0x02     # Section has been destroyed
    SECTION_BREACHED = 0x04      # Section has been exposed to vacuum
    SECTION_FLOODED = 0x08       # Section has been flooded with water
    AXED = 0x10                   # Arm was used to axe/sword someone
    STABILIZERS_DESTROYED = 0x20  # Vehicle only - double attacker mod
    CASEII_TECH = 0x40           # Section has CASE II technology


class Specials(IntFlag):
    """
    Mech special equipment/tech flags.

    Reference: mech.h lines 1129-1160
    """
    NONE = 0
    TRIPLE_MYOMER_TECH = 0x01
    CL_ANTI_MISSILE_TECH = 0x02
    IS_ANTI_MISSILE_TECH = 0x04
    DOUBLE_HEAT_TECH = 0x08
    MASC_TECH = 0x10
    CLAN_TECH = 0x20
    FLIPABLE_ARMS = 0x40
    C3_MASTER_TECH = 0x80
    C3_SLAVE_TECH = 0x100
    ARTEMIS_IV_TECH = 0x200
    ECM_TECH = 0x400
    BEAGLE_PROBE_TECH = 0x800
    SALVAGE_TECH = 0x1000
    CARGO_TECH = 0x2000
    SLITE_TECH = 0x4000
    LIGHT_BAP_TECH = 0x8000
    AA_TECH = 0x10000
    NS_TECH = 0x20000
    SS_ABILITY = 0x40000         # Has sixth sense
    FF_TECH = 0x80000            # Has ferro-fib armor
    ES_TECH = 0x100000           # Has endo-steel internals
    XL_TECH = 0x200000
    ICE_TECH = 0x400000          # ICE engine
    FORCE_SHS = 0x800000
    LE_TECH = 0x1000000          # Light engine
    XXL_TECH = 0x2000000
    CE_TECH = 0x4000000
    REINFI_TECH = 0x8000000
    COMPI_TECH = 0x10000000
    HARDA_TECH = 0x20000000
    CRITPROOF_TECH = 0x40000000


# =============================================================================
# Weapon Fire Modes (from mech.h)
# =============================================================================

class FireMode(IntFlag):
    """
    Weapon fire mode flags.

    Reference: mech.h lines 611-631
    """
    NONE = 0
    DESTROYED_MODE = 0x00000001   # Part is destroyed
    DISABLED_MODE = 0x00000002    # Part is disabled
    BROKEN_MODE = 0x00000004      # Part of a destroyed weapon/item
    DAMAGED_MODE = 0x00000008     # Part is damaged from enhanced critical
    ON_TC = 0x00000010            # Weapon mounted with targeting computer
    REAR_MOUNT = 0x00000020       # Weapon is rear mounted
    HOTLOAD_MODE = 0x00000040     # Weapon's being hotloaded
    HALFTON_MODE = 0x00000080     # Weapon is in halfton mode
    OS_MODE = 0x00000100          # Weapon's one-shot
    OS_USED = 0x00000200          # One-shot ammo has been used
    ULTRA_MODE = 0x00000400       # Weapon in Ultra firing mode
    RFAC_MODE = 0x00000800        # Rapid fire AC
    GATTLING_MODE = 0x00001000    # Gattling MGs
    RAC_TWOSHOT_MODE = 0x00002000   # RAC two shot mode
    RAC_FOURSHOT_MODE = 0x00004000  # RAC four shot mode
    RAC_SIXSHOT_MODE = 0x00008000   # RAC six shot mode
    HEAT_MODE = 0x00010000         # Toggle flamer into heat mode
    WILL_JETTISON_MODE = 0x00020000
    IS_JETTISONED_MODE = 0x00040000
    OMNI_BASE_MODE = 0x00080000    # Part of omni base config
    ROCKET_FIRED = 0x00100000      # Rocket launcher has been fired

    # Aggregate masks (mech.h:611-666)
    RAC_MODES = RAC_TWOSHOT_MODE | RAC_FOURSHOT_MODE | RAC_SIXSHOT_MODE
    FIRE_MODES = (HOTLOAD_MODE | ULTRA_MODE | RFAC_MODE | GATTLING_MODE |
                  RAC_MODES | HEAT_MODE)


class AmmoMode(IntFlag):
    """
    Special ammo mode flags (the crit slot's `ammomode` field).

    Reference: mech.h lines 611-666.

    NB: INFERNO_MODE (0x40) is the same C value systems/criticals.py:91
    already carries as AMMO_INFERNO_MODE — do not redefine it elsewhere.
    """
    NONE = 0
    LBX_MODE = 0x00000001
    ARTEMIS_MODE = 0x00000002
    NARC_MODE = 0x00000004
    CLUSTER_MODE = 0x00000008
    MINE_MODE = 0x00000010
    SMOKE_MODE = 0x00000020
    INFERNO_MODE = 0x00000040
    SWARM_MODE = 0x00000080
    SWARM1_MODE = 0x00000100
    INARC_EXPLO_MODE = 0x00000200
    INARC_HAYWIRE_MODE = 0x00000400
    INARC_ECM_MODE = 0x00000800
    INARC_NEMESIS_MODE = 0x00001000
    AC_AP_MODE = 0x00002000
    AC_FLECHETTE_MODE = 0x00004000
    AC_INCENDIARY_MODE = 0x00008000
    AC_PRECISION_MODE = 0x00010000
    STINGER_MODE = 0x00020000
    AC_CASELESS_MODE = 0x00040000
    SGUIDED_MODE = 0x00080000
    ATM_ER_MODE = 0x00100000
    ATM_HE_MODE = 0x00200000
    MML_LRM_MODE = 0x00400000

    # Aggregate masks (mech.h:611-666)
    ARTILLERY_MODES = CLUSTER_MODE | MINE_MODE | SMOKE_MODE
    INARC_MODES = (INARC_EXPLO_MODE | INARC_HAYWIRE_MODE | INARC_ECM_MODE |
                   INARC_NEMESIS_MODE)
    MISSILE_MODES = (ARTEMIS_MODE | NARC_MODE | INFERNO_MODE | SWARM_MODE |
                     SWARM1_MODE | STINGER_MODE | SGUIDED_MODE)
    AC_MODES = (AC_AP_MODE | AC_FLECHETTE_MODE | AC_INCENDIARY_MODE |
                AC_PRECISION_MODE | AC_CASELESS_MODE)
    ATM_MODES = ATM_ER_MODE | ATM_HE_MODE
    AMMO_MODES = (LBX_MODE | AC_MODES | MISSILE_MODES | INARC_MODES |
                  ARTILLERY_MODES | ATM_MODES | MML_LRM_MODE)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class CriticalSlot:
    """
    A single critical slot in a section.

    Reference: mech.h struct critical_slot (lines 599-608)
    """
    type: int = 0                    # Type of item (weapon index, special, etc.)
    brand: int = 0                   # Brand number and damage (upper 4 bits)
    data: int = 0                    # Info like ammo remaining
    firemode: FireMode = FireMode.NONE
    ammomode: int = 0                # Special ammo type in use
    weap_damage_flags: int = 0       # Enhanced critical damage flags
    desired_ammo_loc: int = -1       # Location of desired ammo bin

    def __setattr__(self,name,value):
        # A rejected legacy ID represents the preceding failed type write only.
        # Every later authoritative write, including Empty -> Empty, replaces it.
        if name=='type':self.__dict__.pop('invalid_source_type',None)
        object.__setattr__(self,name,value)


@dataclass
class Section:
    """
    A body section with armor and critical slots.

    Reference: mech.h struct section_struct (lines 679-691)
    """
    armor: int = 0                   # External armor value
    internal: int = 0                # Internal structure value
    rear: int = 0                    # Rear armor value (torsos only)
    armor_orig: int = 0              # Original armor
    internal_orig: int = 0           # Original internal
    rear_orig: int = 0               # Original rear armor
    basetohit: int = 0               # To-hit modifiers for weapons in section
    config: SectionConfig = SectionConfig.NONE
    recycle: int = 0                 # After physical attack, set counter
    specials: int = 0                # Specials like attached NARC pods
    criticals: list[CriticalSlot] = field(default_factory=list)

    def __post_init__(self):
        """Initialize critical slots if not provided."""
        if not self.criticals:
            self.criticals = [CriticalSlot() for _ in range(NUM_CRITICALS)]


@dataclass
class WeaponState:
    """
    Runtime state for a weapon (separate from CriticalSlot).

    This tracks weapon-specific state like recycle time.
    """
    section: int = 0                 # Section location
    critical: int = 0                # Critical slot index (first of the run)
    weapon_idx: int = 0              # Weapon type index
    recycle: int = 0                 # Ticks until weapon can fire again
    ammo_section: int = -1           # Section containing ammo
    ammo_critical: int = -1          # Critical slot of ammo bin

    # The C has no such flag: a weapon is dead when its crit slots are
    # nonfunctional (PartIsNonfunctional, btmacros.h:324). This mirror exists
    # because the port keeps a parallel weapon list; systems.criticals keeps it
    # in step when a weapon crit lands.
    destroyed: bool = False


# =============================================================================
# Main Mech Class
# =============================================================================

@dataclass
class Mech:
    """
    A BattleMech or other combat unit.

    This class represents the complete state of a mech, following BTMux's
    MECH struct which is divided into:
    - mech_ud: Unit data (mostly static, loaded from template)
    - mech_pd: Position data (location, facing)
    - mech_rd: Runtime data (speed, heat, status)

    Reference: mech.h lines 757-968
    """

    # === Identity (from mech_ud) ===
    name: str = ""                   # 30 char ID for the mech
    mech_type: str = ""              # Mechref (template name)

    # === Unit Classification (from mech_ud) ===
    unit_type: UnitType = UnitType.MECH
    move_type: MoveType = MoveType.BIPED
    tonnage: int = 50                # Weight in tons

    # === Base Stats (from mech_ud) ===
    num_sinks: int = 10              # Number of heat sinks
    max_speed: float = 64.5          # Max speed in KPH (running)
    walk_speed: int = 0              # Walk speed MP
    run_speed: int = 0               # Run speed MP
    jump_mp: int = 0                 # Jump movement points (0 = no jump jets)

    # === Sensors (from mech_ud) ===
    tac_range: int = 15              # Tactical range
    lrs_range: int = 30              # Long range sensors
    scan_range: int = 20             # Scanner range

    # === Position Data (from mech_pd) ===
    # Hex grid position (integer)
    x: int = 0                       # Hex X coordinate
    y: int = 0                       # Hex Y coordinate
    z: int = 0                       # Elevation level

    # Float position (sub-hex precision)
    fx: float = 0.0                  # Cartesian X position
    fy: float = 0.0                  # Cartesian Y position
    fz: float = 0.0                  # Cartesian Z position

    # Last position (for hex crossing detection)
    last_x: int = 0
    last_y: int = 0

    # Facing in degrees (0-359, 0 = North)
    facing: int = 0
    facing_fraction: int = 0          # Low five bits of source RFacing.

    # Terrain at current position — cached copies of the hex under the mech,
    # updated on hex entry (MechTerrain/MechElev, btmacros.h:224/116).
    # terrain holds the map terrain char ('' = no map); elev is the stored
    # unsigned hex elevation (0-9).
    terrain: str = ''
    elev: int = 0

    # Map the mech is on (C keeps a dbref handle, mech.h mech->mapindex;
    # GameMap.add_mech()/remove_mech() maintain this).  String annotation
    # keeps entities.mech free of an entities.map import.
    map: Optional['GameMap'] = None
    mapindex: int = -1               # Registry identity; -1 means no map.

    # Pilot
    # The C keeps only a dbref handle here (mech.h:933 "dbref pilot") and reads
    # the skills off that object per call (mech.utils.c:588,627); None = no
    # pilot, which drops the skill chain onto the DEFAULT_* fallbacks.
    # String annotation keeps entities.mech free of an entities.pilot import.
    pilot: Optional['Pilot'] = None   # MechWarrior in the cockpit (skills)
    pilot_status: int = 0            # Damage pilot has taken (legacy)
    pilot_hits: int = 0              # Pilot injury count (0-6, 6 = death)
    team: int = 0                    # Team affiliation

    # === Runtime Data (from mech_rd) ===
    # Movement
    speed: float = 0.0               # Current speed in KPH
    desired_speed: float = 0.0       # Target speed in KPH
    desired_facing: int = 0          # Target facing (degrees)
    lateral: int = 0                 # Lateral movement mode (quads)
    hexes_walked: float = 0.0        # Hexes walked counter

    # Movement command state and event handles (mech.move.c / mech.ood.c).
    cocoon: int = 0
    carrying: int = -1
    swarm_target: Optional['Mech'] = None
    digging: bool = False
    dug_in: bool = False
    dumping: bool = False
    unjamming: bool = False
    crew_stunned: bool = False
    tail_rotor_destroyed: bool = False
    desired_angle: int = 0
    start_spin: int = 0
    aero_bays: list[int] = field(default_factory=lambda: [-1] * 4)
    fuel: int = 0
    fuel_orig: int = 0
    free_fuel: bool = False
    in_character: bool = False
    movement_messages: list[str] = field(default_factory=list)
    measured_mass: Optional[int] = None
    carried_cargo: int = 0
    towed_unit: Optional['Mech'] = None
    _mode_event: Any = None
    _hulldown_event: Any = None
    _stand_event: Any = None
    _stabil_event: Any = None
    _standfail_event: Any = None
    _startup_event: Any = None
    boot_messages: list[str] = field(default_factory=list)
    last_startup: int = 0
    comm: int = 6
    comm_last: int = 0
    _engine: Any = None

    # Jump state
    jump_heading: int = 0
    jump_speed: float = 0.0          # Persistent jump capability in KPH
    jump_length: int = 0             # Total jump distance
    jump_top: int = 0                # Max MPs left for vertical
    going_x: int = 0                 # Jump target hex X
    going_y: int = 0                 # Jump target hex Y
    start_fx: float = 0.0            # Jump origin X
    start_fy: float = 0.0            # Jump origin Y
    start_fz: float = 0.0            # Jump origin Z
    end_fz: float = 0.0              # Jump destination Z

    # Stagger state (accumulated damage for piloting checks)
    stagger_damage: int = 0          # Damage accumulated this turn

    # Heat
    heat: float = 0.0                # Current heat level
    plus_heat: float = 0.0           # Heat being produced
    minus_heat: float = 0.0          # Heat being dissipated
    weap_heat: float = 0.0           # Weapon heat factor
    disabled_sinks: int = 0          # Disabled dissipation capacity, not physical sinks
    _cutoff_event: Any = None
    engine_heat: int = 0             # +5 per engine critical hit

    # Critical hit tracking
    engine_hits: int = 0             # Engine critical hits (3 = destroyed)
    gyro_hits: int = 0               # Gyro critical hits (2 = destroyed)
    sensor_hits: int = 0             # Sensor critical hits (2 = blind)
    # Active sensor modes [primary, secondary] — indices into the sensors[]
    # table (systems/sensors.py).  Port of char sensor[2] (mech.h:819);
    # calloc default 0 = vislight on both.
    sensor: list = field(default_factory=lambda: [0, 0])
    # MechPNumSeen — possible-LOS contact counter driving the PLOS sweep
    # early-out (mech.events.c:372, mech.sensor.c).
    pnum_seen: int = 0
    # Per-mech map flags: MECHMAPFLAG_MOVED = 1 (map.h:131), set on hex
    # entry (MarkForLOSUpdate), consumed/cleared by update_LOSinfo.
    mapflag: int = 0

    # Status flags
    status: MechStatus = MechStatus.NONE
    status2: int = 0                 # MechStatus2 word (mech.h:1026-1063)
    crit_status: CritStatus = CritStatus.NONE
    specials: Specials = Specials.NONE
    specials2: int = 0               # More tech specials
    tag_target: int = 0
    tagged_by: int = 0
    per: int = 6
    num_seen: int = 0
    brief: int = 0
    sl_warn: bool = False
    prefs: int = 0
    autocon_shutdown: bool = False
    contact_id: str = ''
    markings: str = ''
    # MechInfantrySpecials word (mech.h; calloc default 0)
    infantry_specials: int = 0

    # Computer and radio levels (rd "char computer" / "char radio";
    # calloc default 0, template.c:2716-2722 fills them at load)
    computer: int = 0
    radio: int = 0
    # ud.radio_range; template fallback DEFAULT_RADIORANGE (template.c:2728,
    # btconfig.h:188) — systems/spot.py:166 already reads it with this default
    radio_range: int = 80

    # MechRTonsV — cached real weight in 1/1024 tons, valid while
    # CritStatus.OWEIGHT_OK is set (template.c:2311-2327)
    rtons: int = 0

    # CargoSpace (rd field; calloc default 0)
    cargo_space: int = 0

    # Engine rating (rd.erat, btmacros.h:151); 0 falls back to the computed
    # walkMP * tons form (MechEngineSizeC, btmacros.h:50-51) via
    # engine_size().
    engine_rating: int = 0

    # Stackpole window start — the tick the CT first took internal damage
    # while still at full internal (mech.damage.c:315-317).  The C's rd is
    # calloc-zeroed, so a fresh unit's boom_start is 0; ported as-is.
    boom_start: int = 0

    # Old-style stagger accumulator (MechTurnDamage, used when
    # btech_newstagger is off; mech.damage.c:639)
    turn_damage: int = 0
    # New-style stagger damage list (rd.staggerDamageList,
    # mech.damage.c:604-637): (amount, occurred_at_tick, attacker, counted)
    stagger_damage_list: list = field(default_factory=list)
    # rd.lastStaggerNotify (btmacros.h:864-868)
    last_stagger_check: int = 0
    stagger_stamp: int = -1
    unavailable_updates: set = field(default_factory=set)
    last_stagger_notify: int = 0

    # MNumber cache (MechRnd / MechLastRndU, mech.utils.c:115-122): one
    # random per RANDOM_TICK window per unit
    rnd: int = 0
    last_rnd_update: int = 0

    # EVENT_BLINDREC countdown (mech.sensor.c:920-921), fired by
    # systems.piloting.piloting_periodic
    blind_recovery_countdown: int = 0

    # Supercharger overload counter (MechSChargeCounter)
    scharge_counter: int = 0

    # Vertical speed (VTOL/aero rd field; DestroyAndDump zeroes it)
    vertical_speed: float = 0.0

    # Kill-reason string from destroy_mech (ChannelEmitKill's reason)
    kill_reason: str = ''

    # Weapon recycle bookkeeping - MechLWRT analogue (mech.h:870-873
    # "time_t last_weapon_recycle": updated only on an 'as needed' basis;
    # recycle_weaponry compares muxevent_tick against it and applies the
    # whole delta in one lump).
    last_weapon_recycle: int = 0

    # Visibility modifier, 0-100 (mech.h:821 "char vis_mod").  The C never
    # assigns it at creation - the XCODE object is calloc'd (glue.c:945),
    # so it starts at 0; mech_update random-walks it while started
    # (mech.update.c:2983-2985).
    vis_mod: int = 0

    # Combat
    base_to_hit: int = 0             # Total to-hit modifiers from crits
    pilot_skill_base: int = 0        # Constant skill mods
    target: int = -1                 # Current target (dbref)
    # NB: targ_x/targ_y initialize to -1 in the C (mechrep.c:530-532), and
    # LoseLock resets them to -1 (btmacros.h:500); -1 = no hex lock.
    targ_x: int = -1                 # Target hex coordinates (-1 = none)
    targ_y: int = -1
    targ_z: int = 0

    # Spotter unit for indirect fire (C keeps a dbref, mech_rd "dbref
    # spotter"; -1 = none) and the artillery fire-adjustment counter.
    spotter: int = -1
    fire_adjustment: int = 0

    # Aimed shot state (mech_rd "char aim" / "char aim_type"): aim holds
    # the section being aimed at; NUM_SECTIONS is the no-aim sentinel.
    aim: int = NUM_SECTIONS
    aim_type: int = 0

    # Targeting computer mode (mech_rd "char targcomp").  Plain attribute:
    # the C has no mode-switch command — MechTargComp is written only via
    # softcode (glue.scode.c:468).
    targcomp: int = 0

    # Charge attack state (mech_rd chgtarget/chargetimer/chargedist)
    charge_target: int = -1          # dbref of charge target (-1 = none)
    charge_timer: int = 0
    charge_distance: float = 0.0

    # Turret autoturn / vehicle turn-mode toggles
    autoturn_turret: bool = False
    turn_mode: bool = False

    # TICs — trigger groups of weapon numbers.  The C stores each tic as a
    # bitmask, "unsigned long tic[NUM_TICS][TICLONGS]" (mech.h:593-596,
    # mech.h:960); the port deliberately deviates to one set of weapon
    # numbers per tic with identical semantics (see systems/tic.py, which
    # owns the NUM_TICS = 4 constant).  Per-instance default_factory —
    # never a shared mutable default.
    tics: list[set[int]] = field(
        default_factory=lambda: [set() for _ in range(4)])

    # Sections and weapons
    sections: list[Section] = field(default_factory=list)
    weapons: list[WeaponState] = field(default_factory=list)

    # Statistics
    shots_fired: int = 0
    shots_hit: int = 0
    shots_missed: int = 0
    damage_taken: int = 0
    damage_inflicted: int = 0
    units_killed: int = 0

    # Internal tracking
    _id: int = field(default_factory=lambda: next(_MECH_IDS))  # Unique instance ID

    def __post_init__(self):
        """Initialize sections if not provided."""
        if not self.sections:
            self.sections = [Section() for _ in range(NUM_SECTIONS)]

    # =========================================================================
    # Position Properties
    # =========================================================================

    @property
    def hex_position(self) -> tuple[int, int]:
        """Get hex grid position as (x, y) tuple."""
        return (self.x, self.y)

    @property
    def float_position(self) -> tuple[float, float]:
        """Get float position as (fx, fy) tuple."""
        return (self.fx, self.fy)

    @property
    def position_3d(self) -> tuple[float, float, float]:
        """Get full 3D position as (fx, fy, fz) tuple."""
        return (self.fx, self.fy, self.fz)

    def set_position(self, x: int, y: int, fx: float, fy: float, z: int = 0, fz: float = 0.0) -> None:
        """Set both hex and float positions."""
        self.last_x = self.x
        self.last_y = self.y
        self.x = x
        self.y = y
        self.fx = fx
        self.fy = fy
        self.z = z
        self.fz = fz

    def set_hex_position(self, x: int, y: int, z: int = 0) -> None:
        """Set hex position and update float position to hex center."""
        from physics.hexmath import hex_to_float, ZSCALE
        self.last_x = self.x
        self.last_y = self.y
        self.x = x
        self.y = y
        self.z = z
        self.fx, self.fy = hex_to_float(x, y)
        self.fz = z * ZSCALE

    # =========================================================================
    # Status Properties
    # =========================================================================

    @property
    def is_started(self) -> bool:
        """Check if mech is started (warmed up)."""
        return bool(self.status & MechStatus.STARTED)

    @property
    def is_destroyed(self) -> bool:
        """Check if mech is destroyed."""
        return bool(self.status & MechStatus.DESTROYED)

    @property
    def is_jumping(self) -> bool:
        """Check if mech is currently jumping."""
        return bool(self.status & MechStatus.JUMPING)

    @property
    def is_fallen(self) -> bool:
        """Check if mech has fallen."""
        return bool(self.status & MechStatus.FALLEN)

    @property
    def is_unconscious(self) -> bool:
        """Check if pilot is unconscious."""
        return bool(self.status & MechStatus.UNCONSCIOUS)

    @property
    def autopilot(self):
        """Radio's public alias for the shared MechAuto identity."""
        return getattr(self, 'auto', -1)

    @autopilot.setter
    def autopilot(self, value):
        self.auto = value

    def engine_size(self) -> int:
        """
        Engine rating: the stored value when set, else walkMP * tons.

        Port of MechEngineSize (btmacros.h:50-51, 151-152):
        rd.erat > 0 ? rd.erat : rint((2 * MechMaxSpeed / KPH_PER_MP) / 3)
                               * MechTons.
        """
        if self.engine_rating > 0:
            return self.engine_rating
        return self.derived_engine_size()

    def derived_engine_size(self) -> int:
        """MechEngineSizeC, ignoring the cached engine rating."""
        from core.randomness import float32
        return round((float32(2 * float32(self.max_speed)) / 10.75) / 3) * self.tonnage

    def has_status2(self, flag: 'MechStatus2') -> bool:
        return bool(self.status2 & flag)

    def set_status2(self, flag: 'MechStatus2') -> None:
        self.status2 |= flag

    def clear_status2(self, flag: 'MechStatus2') -> None:
        self.status2 = MechStatus2(int(self.status2) & ~int(flag))

    @property
    def is_moving(self) -> bool:
        """Check if mech is moving (non-zero speed)."""
        return abs(self.speed) > 0.0

    @property
    def is_running(self) -> bool:
        """Check if mech is running (> walking speed)."""
        walk_speed = self.walking_speed
        return self.speed > walk_speed + 0.1

    @property
    def walking_speed(self) -> float:
        """Calculate walking speed (2/3 of max)."""
        return 2.0 * self.max_speed / 3.0

    # =========================================================================
    # Status Flag Methods
    # =========================================================================

    def set_status(self, flag: MechStatus) -> None:
        """Set a status flag."""
        self.status |= flag

    def clear_status(self, flag: MechStatus) -> None:
        """Clear a status flag."""
        self.status = MechStatus(int(self.status) & ~int(flag))

    def has_status(self, flag: MechStatus) -> bool:
        """Check if a status flag is set."""
        return bool(self.status & flag)

    def set_crit_status(self, flag: CritStatus) -> None:
        """Set a critical status flag."""
        self.crit_status |= flag

    def clear_crit_status(self, flag: CritStatus) -> None:
        """Clear a critical status flag."""
        self.crit_status = CritStatus(int(self.crit_status) & ~int(flag))

    def has_crit_status(self, flag: CritStatus) -> bool:
        """Check if a critical status flag is set."""
        return bool(self.crit_status & flag)

    # =========================================================================
    # Movement Methods
    # =========================================================================

    def set_desired_speed(self, speed: float) -> None:
        """Set desired speed, clamped to valid range."""
        # Clamp to -max_speed to +max_speed
        self.desired_speed = max(-self.max_speed, min(self.max_speed, speed))

    def __setattr__(self, name, value):
        # Direct degree assignments implement SetFacing; UpdateHeading restores
        # the fractional bits explicitly after its RFacing assignment.
        if name == 'facing':
            object.__setattr__(self, 'facing_fraction', 0)
        object.__setattr__(self, name, value)

    def set_desired_facing(self, facing: int) -> None:
        """Set desired facing, normalized to 0-359."""
        self.desired_facing = facing % 360
        if self.desired_facing < 0:
            self.desired_facing += 360

    def stop(self) -> None:
        """Stop movement."""
        self.desired_speed = 0.0

    # =========================================================================
    # Heat Methods
    # =========================================================================

    @property
    def effective_heat_sinks(self) -> int:
        """Get effective number of heat sinks (accounting for efficiency)."""
        # Double heat sinks dissipate 2 heat each
        if self.specials & (Specials.CLAN_TECH | Specials.DOUBLE_HEAT_TECH):
            return self.num_sinks * 2
        return self.num_sinks

    @property
    def real_num_sinks(self) -> int:
        """MechRealNumsinks stores dissipation, including partial DHS groups."""
        return int(self.effective_heat_sinks)

    @real_num_sinks.setter
    def real_num_sinks(self, capacity):
        factor = 2 if self.specials & (Specials.CLAN_TECH | Specials.DOUBLE_HEAT_TECH) else 1
        self.num_sinks = capacity / factor

    def calculate_minus_heat(self, in_water: bool = False) -> float:
        """
        Calculate heat dissipation rate.

        Heat sinks in water are doubled (simplified for now).
        """
        base_dissipation = float(self.effective_heat_sinks)
        if in_water:
            base_dissipation *= 2.0
        return base_dissipation

    # =========================================================================
    # Section/Armor Methods
    # =========================================================================

    def get_section(self, loc: Location) -> Section:
        """Get a section by location."""
        return self.sections[loc]

    def get_armor(self, loc: Location) -> int:
        """Get current armor value for a location."""
        return self.sections[loc].armor

    def get_internal(self, loc: Location) -> int:
        """Get current internal structure for a location."""
        return self.sections[loc].internal

    def get_rear_armor(self, loc: Location) -> int:
        """Get rear armor for a torso location."""
        return self.sections[loc].rear

    def apply_damage(self, loc: Location, damage: int, is_rear: bool = False) -> int:
        """
        Apply damage to a location.

        Returns remaining damage that transferred through.
        """
        section = self.sections[loc]

        # Apply to rear armor if specified and this is a torso
        if is_rear and loc in (Location.LTORSO, Location.RTORSO, Location.CTORSO):
            if section.rear >= damage:
                section.rear -= damage
                return 0
            else:
                damage -= section.rear
                section.rear = 0
        else:
            # Apply to front armor
            if section.armor >= damage:
                section.armor -= damage
                return 0
            else:
                damage -= section.armor
                section.armor = 0

        # Apply remaining to internal
        if section.internal >= damage:
            section.internal -= damage
            return 0
        else:
            remaining = damage - section.internal
            section.internal = 0
            section.config |= SectionConfig.SECTION_DESTROYED
            return remaining

    def is_section_destroyed(self, loc: Location) -> bool:
        """Check if a section is destroyed."""
        from systems.damage import section_destroyed
        return section_destroyed(self, loc)

    def total_armor(self) -> int:
        """Get total remaining armor across all sections."""
        total = 0
        for section in self.sections:
            total += section.armor + section.internal + section.rear
        return total

    def total_armor_original(self) -> int:
        """Get total original armor across all sections."""
        total = 0
        for section in self.sections:
            total += section.armor_orig + section.internal_orig + section.rear_orig
        return total

    # =========================================================================
    # Critical Slot Methods
    # =========================================================================

    def get_critical(self, loc: Location, slot: int) -> CriticalSlot:
        """Get a critical slot."""
        return self.sections[loc].criticals[slot]

    def set_critical_type(self, loc: Location, slot: int, crit_type: int) -> None:
        """Set the type of a critical slot."""
        self.sections[loc].criticals[slot].type = crit_type

    def destroy_critical(self, loc: Location, slot: int) -> None:
        """Mark a critical slot as destroyed."""
        self.sections[loc].criticals[slot].firemode |= FireMode.DESTROYED_MODE

    def is_critical_destroyed(self, loc: Location, slot: int) -> bool:
        """Check if a critical slot is destroyed."""
        return bool(self.sections[loc].criticals[slot].firemode & FireMode.DESTROYED_MODE)

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def create_test_mech(cls, name: str = "TestMech", tonnage: int = 50) -> 'Mech':
        """
        Create a basic test mech with default values.

        This is useful for testing and will be replaced by proper template
        loading in Phase 7.
        """
        mech = cls(
            name=name,
            mech_type="TST-1A",
            tonnage=tonnage,
            num_sinks=10,
            max_speed=64.5,  # 6/9 movement (4 walk, 6 run)
        )

        # Initialize with standard mech armor layout
        # Head
        mech.sections[Location.HEAD].armor = 9
        mech.sections[Location.HEAD].armor_orig = 9
        mech.sections[Location.HEAD].internal = 3
        mech.sections[Location.HEAD].internal_orig = 3

        # Center Torso
        mech.sections[Location.CTORSO].armor = 16
        mech.sections[Location.CTORSO].armor_orig = 16
        mech.sections[Location.CTORSO].rear = 5
        mech.sections[Location.CTORSO].rear_orig = 5
        mech.sections[Location.CTORSO].internal = 16
        mech.sections[Location.CTORSO].internal_orig = 16

        # Side Torsos
        for loc in [Location.LTORSO, Location.RTORSO]:
            mech.sections[loc].armor = 12
            mech.sections[loc].armor_orig = 12
            mech.sections[loc].rear = 4
            mech.sections[loc].rear_orig = 4
            mech.sections[loc].internal = 12
            mech.sections[loc].internal_orig = 12

        # Arms
        for loc in [Location.LARM, Location.RARM]:
            mech.sections[loc].armor = 10
            mech.sections[loc].armor_orig = 10
            mech.sections[loc].internal = 8
            mech.sections[loc].internal_orig = 8

        # Legs
        for loc in [Location.LLEG, Location.RLEG]:
            mech.sections[loc].armor = 12
            mech.sections[loc].armor_orig = 12
            mech.sections[loc].internal = 12
            mech.sections[loc].internal_orig = 12

        return mech

    # =========================================================================
    # String Representation
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"Mech(name='{self.name}', type='{self.mech_type}', "
            f"pos=({self.x},{self.y}), facing={self.facing}, "
            f"speed={self.speed:.1f}, heat={self.heat:.1f})"
        )

    def status_string(self) -> str:
        """Get a human-readable status string."""
        flags = []
        if self.is_started:
            flags.append("STARTED")
        if self.is_destroyed:
            flags.append("DESTROYED")
        if self.is_jumping:
            flags.append("JUMPING")
        if self.is_fallen:
            flags.append("FALLEN")
        if self.is_moving:
            flags.append("MOVING")
        if self.is_running:
            flags.append("RUNNING")
        return " | ".join(flags) if flags else "IDLE"
