# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/crit.c
#   btech/mech.hitloc.c
#   btech/mechrep.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h

"""
Vehicle entity for BTMux Python reimplementation.

This module defines the Vehicle class and related data structures for combat
vehicles including ground vehicles (tracked, wheeled, hover) and VTOLs.

Reference:
- BTMux btech/src/btech/mech.h - Vehicle sections, status flags
- BTMux btech/src/btech/crit.c lines 765-1003 - Vehicle critical effects
- BTMux btech/src/btech/mech.hitloc.c - Vehicle hit location tables

Key differences from Mechs:
- Vehicles have no internal structure (armor only, except turret)
- Different sections: FSIDE, BSIDE, LSIDE, RSIDE, TURRET, ROTOR
- Different critical hit tables by location
- Motive system damage instead of leg criticals
- Crew criticals (stunned, driver hit, commander hit, crew killed)
"""

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag, auto
from typing import Optional, TYPE_CHECKING
import math

from entities.mech import (
    Mech, Section,
    VehicleLocation,
    UnitType,
    MoveType,
    MechStatus,
    CritStatus,
    SectionConfig,
    Specials,
    CriticalSlot,
    FireMode,
    NUM_CRITICALS,
)


# =============================================================================
# Vehicle Constants
# =============================================================================

NUM_VEH_SECTIONS = 6


# =============================================================================
# Vehicle Critical Status Flags (from mech.h lines 1121-1126)
# =============================================================================

class TankCritStatus(IntFlag):
    """
    Vehicle-specific critical status flags.

    Reference: mech.h lines 1121-1126
    """
    NONE = 0
    TURRET_LOCKED = 0x01        # Turret permanently locked
    TURRET_JAMMED = 0x02        # Turret jammed (can be unjammed by player)
    DUG_IN = 0x04               # Vehicle is dug in
    DIGGING_IN = 0x08           # Vehicle is in process of digging in
    CREW_STUNNED = 0x10         # Crew stunned - can't fire, limited movement
    TAIL_ROTOR_DESTROYED = 0x20  # VTOL only - tail rotor destroyed


# =============================================================================
# Vehicle Section Structure
# =============================================================================

@dataclass
class VehicleSection(Section):
    """
    A vehicle body section with armor only (no internal structure except turret).

    Unlike mech sections, vehicles typically have:
    - Armor only (no internal structure for sides)
    - Internal structure for turret
    - Stabilizer damage tracking
    """
    armor: int = 0                   # External armor value
    armor_orig: int = 0              # Original armor
    internal: int = 0                # Internal (turret only has this)
    internal_orig: int = 0           # Original internal
    basetohit: int = 0               # To-hit modifiers for weapons in section
    config: SectionConfig = SectionConfig.NONE
    recycle: int = 0                 # After attack, set counter
    specials: int = 0                # Specials like attached NARC pods
    criticals: list[CriticalSlot] = field(default_factory=list)

    def __post_init__(self):
        """Initialize critical slots if not provided."""
        if not self.criticals:
            self.criticals = [CriticalSlot() for _ in range(NUM_CRITICALS)]


# =============================================================================
# Vehicle Class
# =============================================================================

@dataclass
class Vehicle(Mech):
    """
    A combat vehicle (ground or VTOL).

    Vehicles differ from mechs in several key ways:
    - Only armor (no internal structure) for main body sections
    - Turret may have internal structure
    - Different critical hit tables
    - Motive system damage instead of leg actuators
    - Crew status affects vehicle operation
    """

    # === Identity ===
    name: str = ""                   # Vehicle designation
    vehicle_type: str = ""           # Reference/model

    # === Unit Classification ===
    unit_type: UnitType = UnitType.VEH_GROUND
    move_type: MoveType = MoveType.TRACK
    tonnage: int = 50                # Weight in tons

    # === Base Stats ===
    num_sinks: int = 0               # Heat sinks (most vehicles have 0)
    max_speed: float = 54.0          # Max speed in KPH (cruise * 1.5)
    cruise_speed: float = 36.0       # Cruise speed in KPH
    flank_speed: float = 54.0        # Flank speed in KPH

    # === Sensors ===
    tac_range: int = 15
    lrs_range: int = 30
    scan_range: int = 20

    # === Position Data ===
    x: int = 0
    y: int = 0
    z: int = 0
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    last_x: int = 0
    last_y: int = 0
    facing: int = 0
    turret_facing: int = 0           # Turret offset from hull facing
    terrain: int = 0
    elev: int = 0

    # === Crew ===
    crew_hits: int = 0               # Combined crew damage
    driver_hits: int = 0             # Driver damage (+2 piloting each)
    commander_hits: int = 0          # Commander damage (+1 BTH, +1 piloting each)
    team: int = 0

    mapflag: int = 0  # shared LOS invalidation used by turret and map commands

    # === Runtime Data ===
    speed: float = 0.0
    desired_speed: float = 0.0
    desired_facing: int = 0
    vertical_speed: float = 0.0      # VTOL vertical movement
    hexes_moved: float = 0.0

    # === Heat (most vehicles don't track this) ===
    heat: float = 0.0

    # === Status Flags ===
    status: MechStatus = MechStatus.NONE
    crit_status: CritStatus = CritStatus.NONE
    status2: int = 0                # C second status word, including AUTOTURN_TURRET
    tank_crit_status: TankCritStatus = TankCritStatus.NONE
    specials: Specials = Specials.NONE

    # === Damage Modifiers ===
    base_to_hit: int = 0             # Total BTH modifier from criticals
    pilot_skill_base: int = 0        # Driving skill modifier from criticals
    motive_damage: int = 0           # Accumulated motive system hits

    # === Combat ===
    target: int = -1
    # -1 = no hex lock (mechrep.c:530-532; LoseLock resets to -1, btmacros.h:500)
    targ_x: int = -1
    targ_y: int = -1
    targ_z: int = 0

    # === Sections ===
    sections: list[VehicleSection] = field(default_factory=list)

    # === Statistics ===
    shots_fired: int = 0
    shots_hit: int = 0
    damage_taken: int = 0
    damage_inflicted: int = 0
    units_killed: int = 0

    # === Internal ===

    def __post_init__(self):
        """Initialize sections if not provided."""
        if not self.sections:
            self.sections = [VehicleSection() for _ in range(NUM_VEH_SECTIONS)]

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
        """Check if vehicle is started."""
        return bool(self.status & MechStatus.STARTED)

    @property
    def is_destroyed(self) -> bool:
        """Check if vehicle is destroyed."""
        return bool(self.status & MechStatus.DESTROYED)

    @property
    def is_immobilized(self) -> bool:
        """Check if vehicle is immobilized (fallen flag for vehicles)."""
        return bool(self.status & MechStatus.FALLEN)

    @property
    def is_landed(self) -> bool:
        """Check if VTOL is landed."""
        return bool(self.status & MechStatus.LANDED)

    @property
    def is_moving(self) -> bool:
        """Check if vehicle is moving."""
        return abs(self.speed) > 0.0

    @property
    def is_vtol(self) -> bool:
        """Check if this is a VTOL."""
        return self.unit_type == UnitType.VTOL

    @property
    def has_turret(self) -> bool:
        """Check if vehicle has an operational turret."""
        return (self.sections[VehicleLocation.TURRET].internal_orig > 0 and
                not self.is_section_destroyed(VehicleLocation.TURRET))

    @property
    def turret_locked(self) -> bool:
        """Check if turret is locked."""
        return bool(self.tank_crit_status & TankCritStatus.TURRET_LOCKED)

    @property
    def turret_jammed(self) -> bool:
        """Check if turret is jammed (can be unjammed)."""
        return bool(self.tank_crit_status & TankCritStatus.TURRET_JAMMED)

    @property
    def crew_stunned(self) -> bool:
        """Check if crew is stunned."""
        return bool(self.tank_crit_status & TankCritStatus.CREW_STUNNED)

    @crew_stunned.setter
    def crew_stunned(self, value):
        if value: self.tank_crit_status |= TankCritStatus.CREW_STUNNED
        else: self.clear_tank_crit_status(TankCritStatus.CREW_STUNNED)

    # =========================================================================
    # Status Flag Methods
    # =========================================================================

    def set_status(self, flag: MechStatus) -> None:
        """Set a status flag."""
        self.status |= flag

    def clear_status(self, flag: MechStatus) -> None:
        """Clear a status flag."""
        self.status &= ~flag

    def has_status(self, flag: MechStatus) -> bool:
        """Check if a status flag is set."""
        return bool(self.status & flag)

    def set_tank_crit_status(self, flag: TankCritStatus) -> None:
        """Set a tank critical status flag."""
        self.tank_crit_status |= flag

    def clear_tank_crit_status(self, flag: TankCritStatus) -> None:
        """Clear a tank critical status flag."""
        self.tank_crit_status = TankCritStatus(int(self.tank_crit_status) & ~int(flag))

    def has_tank_crit_status(self, flag: TankCritStatus) -> bool:
        """Check if a tank critical status flag is set."""
        return bool(self.tank_crit_status & flag)

    # =========================================================================
    # Movement Methods
    # =========================================================================

    def set_desired_speed(self, speed: float) -> None:
        """Set desired speed, clamped to valid range."""
        self.desired_speed = max(-self.cruise_speed, min(self.flank_speed, speed))

    def set_desired_facing(self, facing: int) -> None:
        """Set desired facing, normalized to 0-359."""
        self.desired_facing = facing % 360
        if self.desired_facing < 0:
            self.desired_facing += 360

    def stop(self) -> None:
        """Stop movement."""
        self.desired_speed = 0.0

    def immobilize(self) -> None:
        """Immobilize the vehicle (set max speed to 0)."""
        self.max_speed = 0.0
        self.clear_crit_status(CritStatus.SPEED_OK)
        self.cruise_speed = 0.0
        self.flank_speed = 0.0
        self.speed = 0.0
        self.desired_speed = 0.0
        self.set_status(MechStatus.FALLEN)  # FALLEN is used for immobilized vehicles

    def reduce_speed(self, mp_reduction: float = 10.75) -> None:
        """
        Reduce max speed by MP equivalent.

        In BTMux, 1 MP = ~10.75 KPH.
        """
        self.max_speed = max(0.0, self.max_speed - mp_reduction)
        self.clear_crit_status(CritStatus.SPEED_OK)
        self.flank_speed = max(0.0, self.flank_speed - mp_reduction)
        self.cruise_speed = max(0.0, self.cruise_speed - mp_reduction * 2 / 3)

        # Cap current speed if needed
        if self.speed > self.flank_speed:
            self.speed = self.flank_speed
        if self.desired_speed > self.flank_speed:
            self.desired_speed = self.flank_speed

    def halve_speed(self) -> None:
        """Halve max speed (for severe motive damage)."""
        self.max_speed /= 2.0
        self.clear_crit_status(CritStatus.SPEED_OK)
        self.flank_speed /= 2.0
        self.cruise_speed /= 2.0

        if self.speed > self.flank_speed:
            self.speed = self.flank_speed
        if self.desired_speed > self.flank_speed:
            self.desired_speed = self.flank_speed

    # =========================================================================
    # Turret Methods
    # =========================================================================

    def set_turret_facing(self, facing: int) -> None:
        """Set turret facing relative to hull."""
        if self.turret_locked or self.turret_jammed:
            return
        self.turret_facing = facing % 360
        if self.turret_facing < 0:
            self.turret_facing += 360

    def get_absolute_turret_facing(self) -> int:
        """Get turret facing in absolute degrees."""
        return (self.facing + self.turret_facing) % 360

    def jam_turret(self) -> None:
        """Jam the turret (can be unjammed)."""
        if not self.turret_locked:
            self.set_tank_crit_status(TankCritStatus.TURRET_JAMMED)

    def lock_turret(self) -> None:
        """Lock the turret permanently."""
        self.clear_tank_crit_status(TankCritStatus.TURRET_JAMMED)
        self.set_tank_crit_status(TankCritStatus.TURRET_LOCKED)

    def unjam_turret(self) -> bool:
        """
        Attempt to unjam the turret.

        Returns True if successful.
        """
        if self.turret_locked:
            return False
        if self.turret_jammed:
            self.clear_tank_crit_status(TankCritStatus.TURRET_JAMMED)
            return True
        return True  # Already unjammed

    # =========================================================================
    # Section/Armor Methods
    # =========================================================================

    def get_section(self, loc: VehicleLocation) -> VehicleSection:
        """Get a section by location."""
        return self.sections[loc]

    def get_armor(self, loc: VehicleLocation) -> int:
        """Get current armor value for a location."""
        return self.sections[loc].armor

    def get_internal(self, loc: VehicleLocation) -> int:
        """Get current internal structure for a location (turret only)."""
        return self.sections[loc].internal

    def is_section_destroyed(self, loc: VehicleLocation) -> bool:
        """Check if a section is destroyed."""
        from systems.damage import section_destroyed
        return section_destroyed(self, loc)

    def apply_damage(self, loc: VehicleLocation, damage: int) -> int:
        """
        Apply damage to a location.

        For vehicles, damage goes to armor first, then internal (turret only).
        For side sections without internal, destruction occurs when armor is gone.

        Returns remaining damage that could not be absorbed.
        """
        section = self.sections[loc]

        # Apply to armor first
        if section.armor >= damage:
            section.armor -= damage
            return 0
        else:
            damage -= section.armor
            section.armor = 0

        # Apply to internal structure (turret has internal, sides don't)
        if section.internal > 0:
            if section.internal >= damage:
                section.internal -= damage
                return 0
            else:
                remaining = damage - section.internal
                section.internal = 0
                section.config |= SectionConfig.SECTION_DESTROYED
                return remaining
        else:
            # No internal structure - section destroyed when armor gone
            section.config |= SectionConfig.SECTION_DESTROYED
            return damage

    def total_armor(self) -> int:
        """Get total remaining armor across all sections."""
        total = 0
        for section in self.sections:
            total += section.armor + section.internal
        return total

    def total_armor_original(self) -> int:
        """Get total original armor across all sections."""
        total = 0
        for section in self.sections:
            total += section.armor_orig + section.internal_orig
        return total

    # =========================================================================
    # Crew Methods
    # =========================================================================

    def stun_crew(self) -> None:
        """Stun the crew - limits movement and prevents attacks."""
        self.set_tank_crit_status(TankCritStatus.CREW_STUNNED)
        # Crew stunned limits speed to cruise
        if self.speed > self.cruise_speed:
            self.speed = self.cruise_speed
        if self.desired_speed > self.cruise_speed:
            self.desired_speed = self.cruise_speed

    def unstun_crew(self) -> None:
        """Clear crew stunned status."""
        self.clear_tank_crit_status(TankCritStatus.CREW_STUNNED)

    def apply_driver_hit(self) -> None:
        """Apply a driver hit (+2 to piloting/driving)."""
        self.driver_hits += 1
        self.pilot_skill_base += 2

    def apply_commander_hit(self) -> None:
        """Apply a commander hit (+1 BTH, +1 piloting)."""
        self.commander_hits += 1
        self.pilot_skill_base += 1
        self.base_to_hit += 1

    def apply_sensor_hit(self) -> None:
        """Apply a sensor hit (+1 BTH)."""
        self.base_to_hit += 1

    def kill_crew(self) -> None:
        """Kill the crew - vehicle destroyed but potentially salvageable."""
        self.crew_hits = 6
        self.set_status(MechStatus.DESTROYED)

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def create_test_vehicle(
        cls,
        name: str = "TestVehicle",
        tonnage: int = 50,
        move_type: MoveType = MoveType.TRACK,
        has_turret: bool = True,
    ) -> 'Vehicle':
        """
        Create a basic test vehicle with default values.
        """
        unit_type = UnitType.VEH_GROUND
        if move_type == MoveType.VTOL:
            unit_type = UnitType.VTOL

        vehicle = cls(
            name=name,
            vehicle_type="TST-VH",
            unit_type=unit_type,
            move_type=move_type,
            tonnage=tonnage,
            cruise_speed=36.0,
            flank_speed=54.0,
            max_speed=54.0,
        )

        # Initialize armor for all sections
        # Front side - heavier armor
        vehicle.sections[VehicleLocation.FSIDE].armor = 30
        vehicle.sections[VehicleLocation.FSIDE].armor_orig = 30

        # Left and Right sides
        vehicle.sections[VehicleLocation.LSIDE].armor = 20
        vehicle.sections[VehicleLocation.LSIDE].armor_orig = 20
        vehicle.sections[VehicleLocation.RSIDE].armor = 20
        vehicle.sections[VehicleLocation.RSIDE].armor_orig = 20

        # Back side - lighter armor
        vehicle.sections[VehicleLocation.BSIDE].armor = 15
        vehicle.sections[VehicleLocation.BSIDE].armor_orig = 15

        # Turret (if present) - has internal structure
        if has_turret:
            vehicle.sections[VehicleLocation.TURRET].armor = 20
            vehicle.sections[VehicleLocation.TURRET].armor_orig = 20
            vehicle.sections[VehicleLocation.TURRET].internal = 10
            vehicle.sections[VehicleLocation.TURRET].internal_orig = 10

        # Rotor (VTOL only)
        if move_type == MoveType.VTOL:
            vehicle.sections[VehicleLocation.ROTOR].armor = 2
            vehicle.sections[VehicleLocation.ROTOR].armor_orig = 2

        return vehicle

    # =========================================================================
    # String Representation
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"Vehicle(name='{self.name}', type='{self.vehicle_type}', "
            f"pos=({self.x},{self.y}), facing={self.facing}, "
            f"speed={self.speed:.1f})"
        )

    def status_string(self) -> str:
        """Get a human-readable status string."""
        flags = []
        if self.is_started:
            flags.append("STARTED")
        if self.is_destroyed:
            flags.append("DESTROYED")
        if self.is_immobilized:
            flags.append("IMMOBILIZED")
        if self.is_moving:
            flags.append("MOVING")
        if self.turret_locked:
            flags.append("TURRET_LOCKED")
        if self.turret_jammed:
            flags.append("TURRET_JAMMED")
        if self.crew_stunned:
            flags.append("CREW_STUNNED")
        if self.is_vtol and self.is_landed:
            flags.append("LANDED")
        return " | ".join(flags) if flags else "IDLE"


# =============================================================================
# Helper Functions
# =============================================================================

def is_vehicle(unit) -> bool:
    """Check if a unit is a vehicle."""
    if hasattr(unit, 'unit_type'):
        return unit.unit_type in (UnitType.VEH_GROUND, UnitType.VTOL, UnitType.VEH_NAVAL)
    return isinstance(unit, Vehicle)


def is_vtol(unit) -> bool:
    """Check if a unit is a VTOL."""
    if hasattr(unit, 'unit_type'):
        return unit.unit_type == UnitType.VTOL
    return False


def get_vehicle_section_name(loc: VehicleLocation, move_type: MoveType = MoveType.TRACK) -> str:
    """Get human-readable name for a vehicle section."""
    names = {
        VehicleLocation.FSIDE: "Front",
        VehicleLocation.BSIDE: "Rear",
        VehicleLocation.LSIDE: "Left Side",
        VehicleLocation.RSIDE: "Right Side",
        VehicleLocation.TURRET: "Turret",
        VehicleLocation.ROTOR: "Rotor",
    }
    return names.get(loc, "Unknown")
