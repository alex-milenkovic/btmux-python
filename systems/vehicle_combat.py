# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/crit.c
#   btech/mech.advanced.c
#   btech/mech.events.c
#   btech/mech.hitloc.c

"""
Vehicle combat system for BTMux Python reimplementation.

This module implements vehicle-specific combat mechanics including:
- Vehicle hit location tables
- Vehicle critical hit effects
- Motive damage system
- Turret mechanics

Reference:
- BTMux btech/src/btech/crit.c lines 765-1003, 1100-1300
- BTMux btech/src/btech/mech.hitloc.c lines 520-900
"""
from core.randomness import roll as source_roll

import random
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Optional, List, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from entities.vehicle import Vehicle, VehicleLocation
    from entities.mech import Mech

from entities.mech import VehicleLocation, MoveType, UnitType, MechStatus, SectionConfig, CritStatus, FireMode
from entities.vehicle import Vehicle, TankCritStatus


# =============================================================================
# Vehicle Critical Hit Types
# =============================================================================

class VehicleCritType(IntEnum):
    """
    Vehicle critical hit types.

    Reference: crit.c vehicle critical handlers
    """
    NONE = 0
    DRIVER_HIT = auto()           # +2 piloting
    COMMANDER_HIT = auto()        # +1 BTH, +1 piloting, crew stunned
    CREW_STUNNED = auto()         # Limited actions for one turn
    CREW_KILLED = auto()          # All crew killed, vehicle disabled
    SENSOR_HIT = auto()           # +1 BTH
    WEAPON_JAM = auto()           # Weapon temporarily disabled
    WEAPON_DESTROYED = auto()     # Weapon permanently destroyed
    STABILIZER_DESTROYED = auto() # Double movement mod for section weapons
    TURRET_JAM = auto()           # Turret jammed (can be unjammed)
    TURRET_LOCK = auto()          # Turret permanently locked
    TURRET_BLOWN_OFF = auto()     # Turret destroyed
    ENGINE_HIT = auto()           # Vehicle immobilized (or VTOL landing)
    FUEL_TANK_HIT = auto()        # Vehicle explodes (ICE only)
    AMMO_EXPLOSION = auto()       # All ammo explodes
    MOTIVE_DAMAGE_MINOR = auto()  # -1 MP
    MOTIVE_DAMAGE_MAJOR = auto()  # -2 MP
    MOTIVE_DESTROYED = auto()     # Immobilized
    CARGO_HIT = auto()            # Cargo/infantry damage
    # VTOL-specific
    COPILOT_HIT = auto()          # +1 BTH
    PILOT_HIT = auto()            # +2 piloting, may lose altitude
    ROTOR_DAMAGED = auto()        # -1 MP
    TAIL_ROTOR_DAMAGED = auto()
    ROTOR_DESTROYED = auto()      # VTOL crashes


# =============================================================================
# Critical Hit Result
# =============================================================================

@dataclass
class VehicleCritResult:
    """Result of a vehicle critical hit."""
    crit_type: VehicleCritType = VehicleCritType.NONE
    effect_applied: bool = False
    vehicle_destroyed: bool = False
    crew_killed: bool = False
    immobilized: bool = False
    message: str = ""
    messages: List[str] = field(default_factory=list)


# =============================================================================
# Vehicle Hit Location Tables
# =============================================================================

# Hit location tables for ground vehicles
# Based on BTMux mech.hitloc.c

# Front arc hit table (2d6)
VEHICLE_FRONT_HIT_TABLE = {
    2: (VehicleLocation.FSIDE, True),   # Critical
    3: (VehicleLocation.FSIDE, True, "motive"),   # Motive damage
    4: (VehicleLocation.FSIDE, True, "motive"),   # Motive damage
    5: (VehicleLocation.FSIDE, False),
    6: (VehicleLocation.FSIDE, False),
    7: (VehicleLocation.FSIDE, False),
    8: (VehicleLocation.FSIDE, False),
    9: (VehicleLocation.FSIDE, False),
    10: "turret_or_front",  # Turret if present, else front
    11: "turret_or_front",  # Turret if present, else front
    12: (VehicleLocation.FSIDE, True),   # Critical
}

# Left side hit table (2d6)
VEHICLE_LEFT_HIT_TABLE = {
    2: (VehicleLocation.LSIDE, True),   # Critical
    3: (VehicleLocation.LSIDE, True, "motive"),   # Motive destroyed
    4: (VehicleLocation.LSIDE, True, "motive"),   # Motive damage
    5: (VehicleLocation.LSIDE, True, "motive"),   # Motive damage
    6: (VehicleLocation.LSIDE, False),
    7: (VehicleLocation.LSIDE, False),
    8: (VehicleLocation.LSIDE, False),
    9: (VehicleLocation.LSIDE, False),
    10: "turret_or_side",
    11: "turret_lock_or_side",
    12: (VehicleLocation.LSIDE, True),   # Critical
}

# Right side hit table (2d6)
VEHICLE_RIGHT_HIT_TABLE = {
    2: (VehicleLocation.RSIDE, True),   # Critical
    3: (VehicleLocation.RSIDE, True, "motive"),   # Motive destroyed
    4: (VehicleLocation.RSIDE, True, "motive"),   # Motive damage
    5: (VehicleLocation.RSIDE, True, "motive"),   # Motive damage
    6: (VehicleLocation.RSIDE, False),
    7: (VehicleLocation.RSIDE, False),
    8: (VehicleLocation.RSIDE, False),
    9: (VehicleLocation.RSIDE, False),
    10: "turret_or_side",
    11: "turret_lock_or_side",
    12: (VehicleLocation.RSIDE, True),   # Critical
}

# Rear hit table (2d6)
VEHICLE_REAR_HIT_TABLE = {
    2: (VehicleLocation.BSIDE, True),   # Critical
    3: (VehicleLocation.BSIDE, True, "motive"),   # Motive destroyed
    4: (VehicleLocation.BSIDE, True, "motive"),   # Motive damage
    5: (VehicleLocation.BSIDE, True, "motive"),   # Motive damage
    6: (VehicleLocation.BSIDE, False),
    7: (VehicleLocation.BSIDE, False),
    8: (VehicleLocation.BSIDE, False),
    9: (VehicleLocation.BSIDE, False),
    10: "turret_or_rear",
    11: "turret_lock_or_rear",
    12: (VehicleLocation.BSIDE, True),   # Critical
}


# =============================================================================
# Vehicle Critical Hit Tables by Location
# =============================================================================

# Ground vehicle front critical table (roll 6-12)
GROUND_FRONT_CRIT_TABLE = {
    6: VehicleCritType.DRIVER_HIT,
    7: VehicleCritType.WEAPON_JAM,
    8: VehicleCritType.STABILIZER_DESTROYED,
    9: VehicleCritType.SENSOR_HIT,
    10: VehicleCritType.COMMANDER_HIT,
    11: VehicleCritType.WEAPON_DESTROYED,
    12: VehicleCritType.CREW_KILLED,
}

# Ground vehicle side critical table (roll 6-12)
GROUND_SIDE_CRIT_TABLE = {
    6: VehicleCritType.CARGO_HIT,
    7: VehicleCritType.WEAPON_JAM,
    8: VehicleCritType.CREW_STUNNED,
    9: VehicleCritType.STABILIZER_DESTROYED,
    10: VehicleCritType.WEAPON_DESTROYED,
    11: VehicleCritType.ENGINE_HIT,
    12: VehicleCritType.FUEL_TANK_HIT,
}

# Ground vehicle rear critical table (roll 6-12)
GROUND_REAR_CRIT_TABLE = {
    6: VehicleCritType.WEAPON_JAM,
    7: VehicleCritType.CARGO_HIT,
    8: VehicleCritType.STABILIZER_DESTROYED,
    9: VehicleCritType.WEAPON_DESTROYED,
    10: VehicleCritType.ENGINE_HIT,
    11: VehicleCritType.AMMO_EXPLOSION,
    12: VehicleCritType.FUEL_TANK_HIT,
}

# Ground vehicle turret critical table (roll 6-12)
GROUND_TURRET_CRIT_TABLE = {
    6: VehicleCritType.STABILIZER_DESTROYED,
    7: VehicleCritType.TURRET_JAM,
    8: VehicleCritType.WEAPON_JAM,
    9: VehicleCritType.TURRET_LOCK,
    10: VehicleCritType.WEAPON_DESTROYED,
    11: VehicleCritType.TURRET_BLOWN_OFF,
    12: VehicleCritType.AMMO_EXPLOSION,
}

# VTOL front critical table (roll 6-12)
VTOL_FRONT_CRIT_TABLE = {
    6: VehicleCritType.COPILOT_HIT,
    7: VehicleCritType.WEAPON_JAM,
    8: VehicleCritType.STABILIZER_DESTROYED,
    9: VehicleCritType.SENSOR_HIT,
    10: VehicleCritType.PILOT_HIT,
    11: VehicleCritType.WEAPON_DESTROYED,
    12: VehicleCritType.CREW_KILLED,
}

# VTOL side critical table (roll 6-12)
VTOL_SIDE_CRIT_TABLE = {
    6: VehicleCritType.WEAPON_JAM,
    7: VehicleCritType.CARGO_HIT,
    8: VehicleCritType.STABILIZER_DESTROYED,
    9: VehicleCritType.WEAPON_DESTROYED,
    10: VehicleCritType.ENGINE_HIT,
    11: VehicleCritType.AMMO_EXPLOSION,
    12: VehicleCritType.FUEL_TANK_HIT,
}

# VTOL rear critical table (roll 6-12)
VTOL_REAR_CRIT_TABLE = {
    6: VehicleCritType.CARGO_HIT, 7: VehicleCritType.WEAPON_JAM,
    8: VehicleCritType.STABILIZER_DESTROYED, 9: VehicleCritType.WEAPON_DESTROYED,
    10: VehicleCritType.SENSOR_HIT, 11: VehicleCritType.ENGINE_HIT,
    12: VehicleCritType.FUEL_TANK_HIT,
}

# VTOL rotor critical table (roll 6-12)
VTOL_ROTOR_CRIT_TABLE = {
    6: VehicleCritType.ROTOR_DAMAGED,
    7: VehicleCritType.ROTOR_DAMAGED,
    8: VehicleCritType.ROTOR_DAMAGED,
    9: VehicleCritType.TAIL_ROTOR_DAMAGED,
    10: VehicleCritType.TAIL_ROTOR_DAMAGED,
    11: VehicleCritType.ROTOR_DESTROYED,
    12: VehicleCritType.ROTOR_DESTROYED,
}


# =============================================================================
# Dice Rolling
# =============================================================================

def roll_1d6() -> int:
    """Roll one 6-sided die."""
    from core.randomness import number
    return number(1, 6)


def roll_2d6() -> int:
    """Roll two 6-sided dice."""
    return source_roll()


# =============================================================================
# Hit Location Functions
# =============================================================================

class VehicleHitGroup(IntEnum):
    """Attack direction for hit location determination."""
    FRONT = 0
    LEFTSIDE = 1
    RIGHTSIDE = 2
    REAR = 3


def get_vehicle_hit_location(
    vehicle: 'Vehicle',
    hit_group: VehicleHitGroup,
    roll: Optional[int] = None,
) -> tuple[VehicleLocation, bool, Optional[str]]:
    """
    Determine hit location on a vehicle based on 2d6 roll.

    Args:
        vehicle: The target vehicle
        hit_group: Attack direction
        roll: Optional pre-rolled 2d6

    Returns:
        Tuple of (location, is_critical, special_effect)
        special_effect can be "motive" for motive damage
    """
    if roll is None:
        roll = roll_2d6()

    roll = max(2, min(12, roll))

    # Select appropriate table
    if hit_group == VehicleHitGroup.FRONT:
        table = VEHICLE_FRONT_HIT_TABLE
        default_loc = VehicleLocation.FSIDE
    elif hit_group == VehicleHitGroup.LEFTSIDE:
        table = VEHICLE_LEFT_HIT_TABLE
        default_loc = VehicleLocation.LSIDE
    elif hit_group == VehicleHitGroup.RIGHTSIDE:
        table = VEHICLE_RIGHT_HIT_TABLE
        default_loc = VehicleLocation.RSIDE
    else:  # REAR
        table = VEHICLE_REAR_HIT_TABLE
        default_loc = VehicleLocation.BSIDE

    result = table.get(roll, (default_loc, False))

    # Handle special cases
    if isinstance(result, str):
        # Turret or body
        if "turret" in result and vehicle.has_turret:
            if "lock" in result:
                # Turret lock critical on hit
                return (VehicleLocation.TURRET, True, "turret_lock")
            return (VehicleLocation.TURRET, False, None)
        else:
            return (default_loc, False, None)
    elif len(result) == 3:
        return (result[0], result[1], result[2])
    else:
        return (result[0], result[1], None)


def determine_vehicle_hit_group(
    attacker,
    target: 'Vehicle',
) -> VehicleHitGroup:
    """
    Determine which hit table to use based on attack angle.

    Reference: mech.hitloc.c:2833-2924 FindAreaHitGroup(), vehicle branch at
    mech.hitloc.c:2909-2922 (CLASS_VEH_GROUND / CLASS_VEH_NAVAL / CLASS_VTOL,
    and the default fallthrough at 2901-2907)

    Vehicles use the narrower fs_hw/as_hw pair - 30/30 at the default TW rules
    (mech.hitloc.c:2860-2861) - so their front arc is a third of a mech's.
    Bounds are inclusive on both ends, exactly as in the C.
    """
    from systems.combat import find_attack_direction, get_hit_arc_half_widths

    if not hasattr(attacker, 'fx'):
        # Assume front if no position (the C has no such guard - MechFX always
        # exists on a MECH; this keeps positionless callers from raising).
        return VehicleHitGroup.FRONT

    _m_fs_hw, _m_as_hw, fs_hw, as_hw = get_hit_arc_half_widths()

    ad = find_attack_direction(attacker, target)

    if ad >= (360 - fs_hw) or ad <= (0 + fs_hw):
        return VehicleHitGroup.FRONT
    elif ad >= (180 - as_hw) and ad <= (180 + as_hw):
        return VehicleHitGroup.REAR
    elif ad >= 180:
        return VehicleHitGroup.LEFTSIDE
    else:
        return VehicleHitGroup.RIGHTSIDE


# =============================================================================
# Vehicle Critical Hit Handlers
# =============================================================================

def vehicle_notice(unit, message):
    from systems.damage import _notify
    if unit is not None: _notify(unit, message)
    return message


def vehicle_broadcast(unit, message):
    from systems.sensors import los_broadcast
    los_broadcast(unit, message)


NO_VEHICLE_CRIT = 'The shot pierces your armor yet fails to hit a critical system!'


def handle_driver_hit(vehicle):
    message=vehicle_notice(vehicle, "%ch%crYour vehicle's driver takes a piece of shrapnel, making it harder to control the vehicle!%cn")
    vehicle.driver_hits=getattr(vehicle,'driver_hits',0)+1
    vehicle.pilot_skill_base+=2
    return vehicle_effect('DRIVER_HIT',message)


def handle_commander_hit(vehicle):
    message=vehicle_notice(vehicle, "%ch%crYour vehicle's commander takes a piece of shrapnel!%cn")
    vehicle.commander_hits=getattr(vehicle,'commander_hits',0)+1
    vehicle.pilot_skill_base+=1
    vehicle.base_to_hit+=1
    stun=handle_crew_stunned(vehicle)
    return vehicle_effect('COMMANDER_HIT',message,messages=[stun.message])


def handle_crew_stunned(vehicle):
    from core.events import EventType
    engine=vehicle._engine
    if engine is None: raise ValueError('crew stun requires the owning event engine')
    tank_flag(vehicle,TankCritStatus.CREW_STUNNED,True)
    message=vehicle_notice(vehicle,'%ch%crThe shot resonates throughout the crew compartment, temporarily stunning you!%cn')
    vehicle._crew_stun_until=engine.muxevent_tick+60
    engine.events.schedule(60,EventType.UNSTUN_CREW,unstun_crew,vehicle)
    limit_speed_to_cruise(vehicle)
    return vehicle_effect('CREW_STUNNED',message)


def handle_crew_killed(vehicle, attacker=None):
    from systems.damage import destroy_mech, _kill_mech_contents, KILL_TYPE_PILOT
    message=vehicle_notice(vehicle,'%ch%crThe shot ricochets around the crew compartment, instantly killing everyone!%cn')
    destroy_mech(vehicle,attacker,False,KILL_TYPE_PILOT,vehicle._engine)
    _kill_mech_contents(vehicle)
    if vehicle.speed != 0: vehicle_broadcast(vehicle,'careens out of control and starts to slow!')
    make_vehicle_fall(vehicle)
    return vehicle_effect('CREW_KILLED',message,vehicle_destroyed=True,crew_killed=True)


def handle_sensor_hit(vehicle):
    message=vehicle_notice(vehicle,'%ch%crYour sensor suite takes a hit!%cn')
    vehicle.base_to_hit+=1
    return vehicle_effect('SENSOR_HIT',message)


def handle_stabilizer_destroyed(vehicle, location):
    from systems.parts import armor_string
    section=vehicle.sections[location]
    repeated=bool(section.config & SectionConfig.STABILIZERS_DESTROYED)
    name=armor_string(vehicle,location)
    message=vehicle_notice(vehicle, f'The destroyed weapon stabilizers in your {name} take another hit!' if repeated else f'The weapon stabilizers in your {name} have been destroyed!')
    section.config|=SectionConfig.STABILIZERS_DESTROYED
    return VehicleCritResult(crit_type=VehicleCritType.STABILIZER_DESTROYED,effect_applied=not repeated,message=message)


def handle_turret_jam(vehicle):
    flags=getattr(vehicle,'tank_crit_status',0)
    if flags & TankCritStatus.TURRET_LOCKED:
        return VehicleCritResult(message=vehicle_notice(vehicle,NO_VEHICLE_CRIT))
    if flags & TankCritStatus.TURRET_JAMMED: return handle_turret_lock(vehicle)
    tank_flag(vehicle,TankCritStatus.TURRET_JAMMED,True)
    return vehicle_effect('TURRET_JAM',vehicle_notice(vehicle,'%ch%crYour turret gets jammed on its current facing!%cn'))


def handle_turret_lock(vehicle):
    if getattr(vehicle,'tank_crit_status',0)&TankCritStatus.TURRET_LOCKED:
        return VehicleCritResult(message=vehicle_notice(vehicle,NO_VEHICLE_CRIT))
    tank_flag(vehicle,TankCritStatus.TURRET_JAMMED,False)
    tank_flag(vehicle,TankCritStatus.TURRET_LOCKED,True)
    return vehicle_effect('TURRET_LOCK',vehicle_notice(vehicle,'%ch%crThe shot destroys your turret rotation mechanism!%cn'))


def handle_turret_blown_off(vehicle, attacker=None, *, los=1):
    from systems.damage import destroy_section
    if vehicle.is_section_destroyed(VehicleLocation.TURRET): return VehicleCritResult()
    message=vehicle_notice(vehicle,'%ch%crThe shot pops your turret clear off its housing!%cn')
    vehicle_broadcast(vehicle,"'s turret flies off!")
    destroy_section(vehicle,attacker,VehicleLocation.TURRET,engine=vehicle._engine,los=los)
    return vehicle_effect('TURRET_BLOWN_OFF',message)


def handle_engine_hit(vehicle, attacker=None):
    if vehicle.is_fallen:
        return VehicleCritResult(message=vehicle_notice(vehicle,'Your destroyed engine takes another direct hit!'))
    message=vehicle_notice(vehicle,'%ch%crYour engine takes a direct hit!%cn')
    if vehicle.unit_type==UnitType.VTOL:
        vtol_engine_landing(vehicle,attacker)
    else:
        set_max_speed(vehicle,0)
        make_vehicle_fall(vehicle)
    return vehicle_effect('ENGINE_HIT',message,immobilized=vehicle.is_fallen)


def vtol_engine_landing(vehicle, attacker):
    from physics.collision import mech_elevation, mechs_elevation, mech_rterrain
    from physics.hexmath import ZSCALE
    from entities.map import GRASSLAND, ROAD, BUILDING
    from systems.piloting import make_piloting_roll
    from physics.jump import mech_falls
    if vehicle.has_status(MechStatus.LANDED): return
    if mech_rterrain(vehicle) in (GRASSLAND,ROAD,BUILDING):
        if make_piloting_roll(vehicle,vehicle.z-mech_elevation(vehicle)).success:
            vehicle_notice(vehicle,'You land safely!')
            vehicle.set_status(MechStatus.LANDED)
            vehicle.z=mech_elevation(vehicle);vehicle.fz=vehicle.z*ZSCALE
            set_max_speed(vehicle,0)
            vehicle.vertical_speed=0
    else:
        vehicle_notice(vehicle,'The ground rushes up to meet you!')
        vehicle_notice(attacker,'You knock the VTOL out of the sky!')
        vehicle_broadcast(vehicle,'falls from the sky!')
        mech_falls(vehicle,mechs_elevation(vehicle),notify_fall=False)


def handle_fuel_tank_hit(vehicle, attacker=None):
    from entities.mech import Specials
    if not vehicle.specials & Specials.ICE_TECH: return handle_engine_hit(vehicle,attacker)
    message=vehicle_notice(vehicle,'%ch%crYour fuel tank explodes in a ball of fire!%cn')
    if vehicle is not attacker: vehicle_broadcast(vehicle,'explodes in a ball of fire!')
    fuel_explosion(vehicle,attacker,'FUELTANK')
    return vehicle_effect('FUEL_TANK_HIT',message,vehicle_destroyed=True)


def handle_ammo_explosion(vehicle, location=VehicleLocation.BSIDE, attacker=None, *, los=1):
    from entities.crittypes import is_ammo, ammo2weapon_i, crits_in_loc
    from entities.weapon import get_weapon_by_index, WeaponFlags
    from systems.ammo_dump import find_max_ammo_damage
    from systems.combat import apply_damage_with_transfer
    total=0
    for loc,section in enumerate(vehicle.sections):
        if vehicle.is_section_destroyed(loc): continue
        for slot in reversed(section.criticals[:crits_in_loc(vehicle,loc)]):
            if not is_ammo(slot.type) or not slot.data: continue
            weapon=get_weapon_by_index(ammo2weapon_i(slot.type))
            if weapon.special & WeaponFlags.GAUSS: continue
            total+=slot.data*find_max_ammo_damage(weapon)
            slot.data=0
    if not total: return handle_weapon_destroyed(vehicle,location,attacker,los=los)
    message=vehicle_notice(vehicle,'%ch%crOne of your ammo bins is struck causing a cascading explosion!%cn')
    vehicle_broadcast(vehicle,'has an internal ammo explosion!')
    apply_damage_with_transfer(vehicle,location,0,attacker=attacker,internal_damage=total,
        ignore_swarmers=True,cause=0,bth=0,attack_pilot=-1,los=0,engine=vehicle._engine)
    return vehicle_effect('AMMO_EXPLOSION',message,vehicle_destroyed=vehicle.is_destroyed)


def handle_motive_damage(vehicle: 'Vehicle', severity: str = "minor") -> VehicleCritResult:
    """
    Handle motive system damage.

    Effects vary by severity and movement type:
    - minor: -1 MP (or -2 for hover)
    - major: -2 MP
    - destroyed: Vehicle immobilized

    Reference: mech.hitloc.c vehicle hit location processing
    """
    if severity == "destroyed":
        result = VehicleCritResult(crit_type=VehicleCritType.MOTIVE_DESTROYED)
        vehicle.immobilize()
        result.effect_applied = True
        result.immobilized = True

        # Movement type specific message
        move_msgs = {
            MoveType.TRACK: "Track destroyed! Vehicle immobilized!",
            MoveType.WHEEL: "Wheel destroyed! Vehicle immobilized!",
            MoveType.HOVER: "Lift fan destroyed! Vehicle immobilized!",
        }
        result.message = move_msgs.get(vehicle.move_type, "Motive system destroyed! Vehicle immobilized!")
        return result

    elif severity == "major":
        result = VehicleCritResult(crit_type=VehicleCritType.MOTIVE_DAMAGE_MAJOR)
        vehicle.reduce_speed(21.5)  # -2 MP
        vehicle.motive_damage += 2
        result.effect_applied = True

        move_msgs = {
            MoveType.TRACK: "Track seriously damaged! -2 MP.",
            MoveType.WHEEL: "Wheel seriously damaged! -2 MP.",
            MoveType.HOVER: "Air skirt seriously damaged! -2 MP.",
        }
        result.message = move_msgs.get(vehicle.move_type, "Motive system seriously damaged! -2 MP.")
        return result

    else:  # minor
        result = VehicleCritResult(crit_type=VehicleCritType.MOTIVE_DAMAGE_MINOR)
        vehicle.reduce_speed(10.75)  # -1 MP
        vehicle.motive_damage += 1
        result.effect_applied = True

        move_msgs = {
            MoveType.TRACK: "Track damaged! -1 MP.",
            MoveType.WHEEL: "Wheel damaged! -1 MP.",
            MoveType.HOVER: "Air skirt damaged! -1 MP.",
        }
        result.message = move_msgs.get(vehicle.move_type, "Motive system damaged! -1 MP.")
        return result


# VTOL-specific handlers

def handle_copilot_hit(vehicle):
    message=vehicle_notice(vehicle,"%ch%crYour VTOL's pilot takes a piece of shrapnel, making it harder to aim your weapons!%cn")
    vehicle.base_to_hit+=1
    return vehicle_effect('COPILOT_HIT',message)


def handle_pilot_hit(vehicle):
    message=vehicle_notice(vehicle,"%ch%crYour VTOL's copilot takes a piece of shrapnel, making it harder to control the VTOL!%cn")
    vehicle.pilot_skill_base+=2
    return vehicle_effect('PILOT_HIT',message)


def handle_rotor_damaged(vehicle):
    from physics.cargo import cargo_max_speed
    if cargo_max_speed(vehicle)<=10.75: return handle_rotor_destroyed(vehicle,los=1)
    message=vehicle_notice(vehicle,'Your rotor is damaged!')
    if not vehicle.is_fallen: set_max_speed(vehicle,vehicle.max_speed-10.75)
    return vehicle_effect('ROTOR_DAMAGED',message)


def handle_rotor_destroyed(vehicle, attacker=None, *, los=1):
    from systems.damage import destroy_section
    if vehicle.is_section_destroyed(VehicleLocation.ROTOR): return VehicleCritResult()
    message=vehicle_notice(vehicle,'%ch%crThe shot hits your fragile rotor mechanism!%cn')
    vehicle_broadcast(vehicle,"'s rotor snaps into several parts!")
    destroy_section(vehicle,attacker,VehicleLocation.ROTOR,engine=vehicle._engine,los=los)
    if attacker is None:
        vehicle_notice(vehicle,'Your rotor has been destroyed!')
        vehicle_broadcast(vehicle,"'s rotor has been destroyed!")
    return vehicle_effect('ROTOR_DESTROYED',message,immobilized=vehicle.has_status(MechStatus.LANDED))


def get_vehicle_crit_table(
    vehicle: 'Vehicle',
    location: VehicleLocation,
) -> dict:
    """Get the appropriate critical hit table for a vehicle location."""
    if vehicle.unit_type == UnitType.VTOL:
        if location == VehicleLocation.FSIDE:
            return VTOL_FRONT_CRIT_TABLE
        elif location in (VehicleLocation.LSIDE, VehicleLocation.RSIDE):
            return VTOL_SIDE_CRIT_TABLE
        elif location == VehicleLocation.BSIDE:
            return VTOL_REAR_CRIT_TABLE
        elif location == VehicleLocation.ROTOR:
            return VTOL_ROTOR_CRIT_TABLE
        else:
            return {}
    elif vehicle.unit_type == UnitType.VEH_GROUND:
        if location == VehicleLocation.FSIDE:
            return GROUND_FRONT_CRIT_TABLE
        elif location in (VehicleLocation.LSIDE, VehicleLocation.RSIDE):
            return GROUND_SIDE_CRIT_TABLE
        elif location == VehicleLocation.BSIDE:
            return GROUND_REAR_CRIT_TABLE
        elif location == VehicleLocation.TURRET:
            return GROUND_TURRET_CRIT_TABLE
        else:
            return {}
    return {}


def resolve_vehicle_critical(
    vehicle: 'Vehicle',
    location: VehicleLocation,
    roll: Optional[int] = None,
    attacker=None,
    *, los=1,
) -> VehicleCritResult:
    """
    Resolve a vehicle critical hit.

    Args:
        vehicle: The vehicle taking the critical
        location: Where the critical occurred
        roll: Optional pre-rolled 2d6 (rolls 6+ trigger criticals)

    Returns:
        VehicleCritResult with effects applied
    """
    if roll is None:
        roll = source_roll('vehicle_critical_roll', roll_2d6)
    if vehicle.move_type == MoveType.NONE:
        return VehicleCritResult(message='No critical effect.')

    # Criticals only happen on roll of 6+
    if roll < 6:
        return VehicleCritResult(message="No critical effect.")

    vehicle_notice(vehicle, "%ch%cyCRITICAL HIT!%c")
    # Get the critical table
    crit_table = get_vehicle_crit_table(vehicle, location)

    # Look up critical type
    crit_type = crit_table.get(roll, VehicleCritType.NONE)

    # Handle the critical
    handlers = {
        VehicleCritType.DRIVER_HIT: lambda: handle_driver_hit(vehicle),
        VehicleCritType.COMMANDER_HIT: lambda: handle_commander_hit(vehicle),
        VehicleCritType.CREW_STUNNED: lambda: handle_crew_stunned(vehicle),
        VehicleCritType.CREW_KILLED: lambda: handle_crew_killed(vehicle, attacker),
        VehicleCritType.SENSOR_HIT: lambda: handle_sensor_hit(vehicle),
        VehicleCritType.STABILIZER_DESTROYED: lambda: handle_stabilizer_destroyed(vehicle, location),
        VehicleCritType.TURRET_JAM: lambda: handle_turret_jam(vehicle),
        VehicleCritType.TURRET_LOCK: lambda: handle_turret_lock(vehicle),
        VehicleCritType.TURRET_BLOWN_OFF: lambda: handle_turret_blown_off(vehicle, attacker, los=los),
        VehicleCritType.ENGINE_HIT: lambda: handle_engine_hit(vehicle, attacker),
        VehicleCritType.FUEL_TANK_HIT: lambda: handle_fuel_tank_hit(vehicle, attacker),
        VehicleCritType.AMMO_EXPLOSION: lambda: handle_ammo_explosion(vehicle, location, attacker, los=los),
        VehicleCritType.MOTIVE_DAMAGE_MINOR: lambda: handle_motive_damage(vehicle, "minor"),
        VehicleCritType.MOTIVE_DAMAGE_MAJOR: lambda: handle_motive_damage(vehicle, "major"),
        VehicleCritType.MOTIVE_DESTROYED: lambda: handle_motive_damage(vehicle, "destroyed"),
        VehicleCritType.COPILOT_HIT: lambda: handle_copilot_hit(vehicle),
        VehicleCritType.PILOT_HIT: lambda: handle_pilot_hit(vehicle),
        VehicleCritType.ROTOR_DAMAGED: lambda: handle_rotor_damaged(vehicle),
        VehicleCritType.ROTOR_DESTROYED: lambda: handle_rotor_destroyed(vehicle, attacker, los=los),
        VehicleCritType.CARGO_HIT: lambda: handle_cargo_hit(vehicle),
        VehicleCritType.WEAPON_JAM: lambda: handle_weapon_jam(vehicle, location),
        VehicleCritType.WEAPON_DESTROYED: lambda: handle_weapon_destroyed(vehicle, location, attacker, los=los),
        VehicleCritType.TAIL_ROTOR_DAMAGED: lambda: handle_tail_rotor_damaged(vehicle),
    }

    handler = handlers.get(crit_type)
    if handler:
        return handler()

    return VehicleCritResult(message="Unknown critical effect.")


# =============================================================================
# Damage Application
# =============================================================================

def apply_vehicle_damage(
    vehicle: 'Vehicle',
    location: VehicleLocation,
    damage: int,
    is_critical: bool = False,
    special_effect: Optional[str] = None,
) -> tuple[int, List[VehicleCritResult]]:
    """
    Apply damage to a vehicle at a specific location.

    Args:
        vehicle: The target vehicle
        location: Where damage is applied
        damage: Amount of damage
        is_critical: Whether this triggers automatic critical
        special_effect: Special effect like "motive" damage

    Returns:
        Tuple of (damage_dealt, list of critical results)
    """
    crit_results = []

    # Handle special effects
    if special_effect == "motive" and not vehicle.is_immobilized:
        # Motive damage on hit
        crit_result = handle_motive_damage(vehicle, "minor")
        crit_results.append(crit_result)

    if special_effect == "turret_lock" and vehicle.has_turret:
        if not vehicle.turret_locked:
            crit_result = handle_turret_lock(vehicle)
            crit_results.append(crit_result)

    # Apply armor damage
    remaining = vehicle.apply_damage(location, damage)
    damage_dealt = damage - remaining

    # Check for critical hit
    if is_critical or remaining > 0:
        crit_roll = roll_2d6()
        crit_result = resolve_vehicle_critical(vehicle, location, crit_roll)
        if crit_result.effect_applied:
            crit_results.append(crit_result)

    # Check for vehicle destruction
    if vehicle.is_section_destroyed(VehicleLocation.FSIDE):
        vehicle.set_status(MechStatus.DESTROYED)

    return (damage_dealt, crit_results)


def motive_system_hit(unit, roll_modifier=0):
    """DoMotiveSystemHit, including notices before speed/fall consequences."""
    from systems.movement_commands import notify
    from systems.notifications import mech_printf, MECHALL
    from systems.sensors import los_broadcast
    roll = source_roll('motive_rolls', lambda: random.randint(1,6)+random.randint(1,6)) + roll_modifier
    roll += 2 if unit.move_type == MoveType.WHEEL else 4 if unit.move_type in (MoveType.HOVER, MoveType.FOIL) else 0
    if roll < 8:
        return
    kind = {MoveType.TRACK:'tank', MoveType.WHEEL:'vehicle', MoveType.HOVER:'hovercraft', MoveType.HULL:'ship', MoveType.FOIL:'hydrofoil', MoveType.SUB:'submarine'}.get(unit.move_type, 'weird unidentifiable toy (warn a wizard!)')
    notify(unit, '%ch%cyCRITICAL HIT!%c')
    if roll < 12:
        unit.pilot_skill_base += 1 if roll < 10 else 2
    if unit.is_fallen:
        notify(unit, '%cr%chYour destroyed motive system takes another hit!%cn')
    elif roll < 10:
        mech_printf(unit, MECHALL, '%%cr%%chYour motive system takes a minor hit, making it harder to control your %s!%%cn', kind)
    elif roll < 12:
        mech_printf(unit, MECHALL, '%%cr%%chYour motive system takes a moderate hit, slowing you down and making it harder to control your %s!%%cn', kind)
    else:
        mech_printf(unit, MECHALL, '%%cr%%chYour motive system is destroyed! Your %s can no longer move!%%cn', kind)
    if roll < 12 and unit.speed != 0:
        los_broadcast(unit, 'wobbles slightly.' if roll < 10 else 'wobbles violently.')
    elif roll >= 12 and unit.speed > 0:
        los_broadcast(unit, 'shakes violently then begins to slow down.')
    if roll >= 10:
        set_max_speed(unit, unit.max_speed - 10.75 if roll < 12 else 0.0)
        if roll >= 12:
            make_vehicle_fall(unit)
        # Both branches correct again after the setter refreshes cargo weight.
        correct_speed(unit)


def vehicle_draw(name, low, high, fallback=None, *, state=None):
    from core.randomness import draw
    return draw('vehicle_' + name, low, high, fallback or (lambda: random.randint(low, high)), state=state)


def vehicle_effect(kind, message, **kwargs):
    return VehicleCritResult(crit_type=VehicleCritType[kind], effect_applied=True, message=message, **kwargs)


def tank_flag(unit, flag, enabled):
    flags = getattr(unit, 'tank_crit_status', 0)
    unit.tank_crit_status = TankCritStatus(int(flags) | int(flag) if enabled else int(flags) & ~int(flag))
    field = {TankCritStatus.CREW_STUNNED: 'crew_stunned',
             TankCritStatus.TAIL_ROTOR_DESTROYED: 'tail_rotor_destroyed',
             TankCritStatus.TURRET_JAMMED: 'turret_jammed',
             TankCritStatus.TURRET_LOCKED: 'turret_locked'}.get(flag)
    if field and not isinstance(getattr(type(unit), field, None), property):
        setattr(unit, field, enabled)


def unstun_crew(event):
    unit = event.data
    from core.events import EventType
    if len(unit._engine.events.pending_events(EventType.UNSTUN_CREW, unit)) > 1:
        return
    from systems.movement_commands import notify
    notify(unit, "Your head clears and you're able to control your vehicle again.")
    tank_flag(unit, TankCritStatus.CREW_STUNNED, False)


def limit_speed_to_cruise(unit):
    from physics.cargo import cargo_max_speed
    import math
    maximum = int(cargo_max_speed(unit))
    if unit.move_type == MoveType.VTOL:
        maximum = int(math.sqrt(max(0, maximum * maximum - unit.vertical_speed ** 2)))
    if maximum * 2 / 3 < unit.desired_speed:
        unit.desired_speed = maximum * 2 / 3 - 0.1


def correct_speed(unit):
    from physics.cargo import cargo_max_speed
    from systems.parts import set_cargo_weight
    from core.randomness import float32
    maximum = float32(cargo_max_speed(unit))
    unit.max_speed = max(0.0, unit.max_speed)
    set_cargo_weight(unit)
    sign = -1 if unit.desired_speed < -0.1 else 1
    if sign < 0:
        maximum = float32(maximum * 2.0 / 3.0)
    if abs(unit.desired_speed) > maximum:
        unit.desired_speed = sign * maximum
    if abs(unit.speed) > maximum:
        unit.speed = sign * maximum


def set_max_speed(unit, value):
    """SetMaxSpeed: store first, invalidate the cache, then correct live speed."""
    from core.randomness import float32
    unit.max_speed = float32(value)
    unit.clear_crit_status(CritStatus.SPEED_OK)
    correct_speed(unit)


def make_vehicle_fall(unit):
    from physics.jump import make_mech_fall
    make_mech_fall(unit)


def start_vtol_crash(unit):
    from physics.orbital import fall_event
    from core.events import EventType
    if unit.is_fallen: return
    unit.speed=unit.desired_speed=0
    set_max_speed(unit,0)
    if not unit.has_status(MechStatus.LANDED):
        if unit._engine is None: raise ValueError('VTOL crash requires the owning event engine')
        vehicle_notice(unit,'You ponder F = ma, S = F/m, S = at^2 => S=agt^2 in relation to the ground.')
        unit.vertical_speed=0
        vehicle_notice(unit,'You start free-fall.. Enjoy the ride!')
        vehicle_broadcast(unit,'starts to fall to the ground!')
        unit._engine.events.schedule(3,EventType.FALL,fall_event,unit,-1)


def handle_tail_rotor_damaged(unit):
    if getattr(unit,'tank_crit_status',0)&TankCritStatus.TAIL_ROTOR_DESTROYED:
        return VehicleCritResult(message=vehicle_notice(unit,'Your damaged tail rotor suffers more damage!'))
    tank_flag(unit,TankCritStatus.TAIL_ROTOR_DESTROYED,True)
    message=vehicle_notice(unit,'%ch%crYour tail rotor is damaged, slowing you down!%cn')
    limit_speed_to_cruise(unit)
    return vehicle_effect('TAIL_ROTOR_DAMAGED',message)


def pick_random_weapon(unit, location, ignore_jams=False):
    from entities.crittypes import is_weapon
    from entities.mech import FireMode
    from systems.enhanced_crits import part_temp_nuke
    candidates = [i for i, slot in enumerate(unit.sections[location].criticals)
                  if is_weapon(slot.type) and not slot.firemode & (FireMode.BROKEN_MODE | FireMode.DESTROYED_MODE)
                  and not (ignore_jams and part_temp_nuke(slot))]
    return candidates[vehicle_draw('weapon_slot', 0, len(candidates)-1)] if candidates else -1


def handle_weapon_jam(unit, location):
    from entities.crittypes import weapon2i
    from entities.weapon import get_weapon_by_index, WeaponType
    from systems.enhanced_crits import set_part_temp_nuke
    from core.game_loop import update_recycling
    if unit.is_section_destroyed(location): return VehicleCritResult()
    critical=pick_random_weapon(unit,location,True)
    if critical<0: return VehicleCritResult(message=vehicle_notice(unit,NO_VEHICLE_CRIT))
    slot=unit.sections[location].criticals[critical]
    weapon=get_weapon_by_index(weapon2i(slot.type))
    ballistic=weapon.weapon_type==WeaponType.TAMMO
    message=vehicle_notice(unit,f'%ch%crThe shot temporarily jams your {weapon.name[3:]}!%c' if ballistic else f'%ch%crThe shot causes your {weapon.name[3:]} to temporarily short out!%c')
    set_part_temp_nuke(slot,1 if ballistic else 2)
    if unit._engine: update_recycling(unit._engine,unit)
    slot.data=vehicle_draw('jam_recycle',60,120)
    for ws in unit.weapons:
        if (ws.section,ws.critical)==(location,critical): ws.recycle=slot.data
    return vehicle_effect('WEAPON_JAM',message)


def handle_weapon_destroyed(unit, location, attacker=None, *, los=1):
    from systems.criticals import apply_weapon_critical, find_first_weapon_crit, destroy_weapon
    from entities.crittypes import weapon2i
    from entities.weapon import get_weapon_by_index
    if unit.is_section_destroyed(location): return VehicleCritResult()
    critical=pick_random_weapon(unit,location)
    if critical<0: return VehicleCritResult(message=vehicle_notice(unit,NO_VEHICLE_CRIT))
    result=apply_weapon_critical(unit,location,critical,attacker,engine=unit._engine,los=los,special_only=True)
    if result is not None:
        return vehicle_effect('WEAPON_DESTROYED',result.message,messages=result.messages,vehicle_destroyed=result.mech_destroyed)
    kind=unit.sections[location].criticals[critical].type
    first=find_first_weapon_crit(unit,location,-1,0,kind,1)
    destroy_weapon(unit,location,kind,first,1,1)
    name=get_weapon_by_index(weapon2i(kind)).name[3:]
    return vehicle_effect('WEAPON_DESTROYED',vehicle_notice(unit,f'%ch%crYour {name} is destroyed!%c'))


def main_weapon(unit):
    from systems.weapon_inventory import find_weapons
    maximum,selected=0,None
    for section in range(len(unit.sections)):
        if unit.is_section_destroyed(section):
            continue
        for run in find_weapons(unit, section) or []:
            slot=unit.sections[run.section].criticals[run.critical]
            if slot.firemode & (FireMode.BROKEN_MODE|FireMode.DESTROYED_MODE): continue
            from core.randomness import source_state
            weight=vehicle_draw('weapon_weight',0,2**31-1,state=source_state(unit))
            if weight>maximum:
                maximum,selected=weight,run
    if selected is None: return None
    return next((ws for ws in unit.weapons if (ws.section,ws.critical,ws.weapon_idx)==(selected.section,selected.critical,selected.weapon_idx)),selected)


def jam_main_weapon(unit):
    from systems.enhanced_crits import set_part_temp_nuke
    from entities.weapon import get_weapon_by_index
    ws=main_weapon(unit)
    if ws:
        set_part_temp_nuke(unit.sections[ws.section].criticals[ws.critical],5)
        vehicle_notice(unit,f'%ch%crYour {get_weapon_by_index(ws.weapon_idx).name[3:]} is jammed!%c')
    return ws


def destroy_main_weapon(unit):
    from systems.criticals import destroy_weapon, find_first_weapon_crit
    from entities.crittypes import i2weapon
    from entities.weapon import get_weapon_by_index
    ws = main_weapon(unit)
    if ws:
        part_type = i2weapon(ws.weapon_idx)
        first = find_first_weapon_crit(unit, ws.section, -1, 0, part_type, 1)
        size = get_weapon_by_index(ws.weapon_idx).crits if unit.unit_type == UnitType.MECH else 1
        destroy_weapon(unit, ws.section, part_type, 1, first, size)
        vehicle_notice(unit,f"%ch%crYour {get_weapon_by_index(ws.weapon_idx).name[3:]} is destroyed!%c")
    return ws


def fuel_explosion(unit, attacker, reason):
    from systems.damage import destroy_mech, explode_unit
    from physics.heights import mech_elevation
    from physics.hexmath import ZSCALE
    unit.z = mech_elevation(unit)
    unit.fz = unit.z * ZSCALE
    unit.speed = unit.vertical_speed = 0
    destroy_mech(unit, attacker, showboom=True, reason=reason, engine=unit._engine)
    explode_unit(unit, attacker)


def legacy_vehicle_critical(unit, location, attacker=None, *, fasa=False, vtol=False, los=1):
    """The independent legacy charts, including their silent preliminary exits."""
    from systems.damage import destroy_mech, destroy_section, explode_unit, _kill_mech_contents
    from systems.piloting import head_hit_mw_damage
    if not vtol and unit.move_type==MoveType.NONE: return VehicleCritResult()
    if not vtol and not fasa:
        if location==VehicleLocation.TURRET:
            if vehicle_draw('turret_gate',1,3)==2:
                if getattr(unit,'tank_crit_status',0)&TankCritStatus.TURRET_LOCKED: return VehicleCritResult()
                vehicle_notice(unit,'%ch%cyCRITICAL HIT!%c')
                tank_flag(unit,TankCritStatus.TURRET_LOCKED,True)
                return vehicle_effect('TURRET_LOCK',vehicle_notice(unit,'Your turret takes a direct hit and locks up!'))
        else:
            preliminary=vehicle_draw('motive_gate',1,10)
            if preliminary<=5:
                if unit.is_fallen: return VehicleCritResult()
                vehicle_notice(unit,'%ch%cyCRITICAL HIT!%c')
                minor={MoveType.TRACK:'One of your tracks is damaged!',MoveType.WHEEL:'One of your wheels is damaged!',MoveType.HOVER:'Your air skirt is damaged!',MoveType.HULL:'Your craft suddenly slows!',MoveType.SUB:'Your craft suddenly slows!',MoveType.FOIL:'Your craft suddenly slows!'}
                major={MoveType.TRACK:'One of your tracks is destroyed, immobilizing your vehicle!',MoveType.WHEEL:'One of your wheels is destroyed, immobilizing your vehicle!',MoveType.HOVER:'Your lift fan is destroyed, immobilizing your vehicle!',MoveType.HULL:'Your engines cut out and you drift to a halt!',MoveType.SUB:'Your engines cut out and you drift to a halt!',MoveType.FOIL:'Your engines cut out and you drift to a halt!'}
                message=(major if preliminary==5 else minor).get(unit.move_type,'')
                if message: vehicle_notice(unit,message)
                set_max_speed(unit,0 if preliminary==5 else unit.max_speed-10.75)
                if preliminary==5: make_vehicle_fall(unit)
                return vehicle_effect('MOTIVE_DESTROYED' if preliminary==5 else 'MOTIVE_DAMAGE_MINOR',message)
    vehicle_notice(unit,'%ch%cyCRITICAL HIT!%c')
    roll=vehicle_draw('legacy_critical',0,5)
    if roll==0 and not vtol:
        head_hit_mw_damage(unit,attacker,1)
        return vehicle_effect('CREW_STUNNED','')
    if roll==1:
        selected=jam_main_weapon(unit)
        return vehicle_effect('WEAPON_JAM','') if selected else VehicleCritResult()
    if roll==2:
        message=vehicle_notice(unit,'Your engine takes a direct hit!' if vtol else "Your engine takes a direct hit!  You can't move anymore.")
        if vtol: vtol_engine_landing(unit,attacker)
        set_max_speed(unit,0)
        return vehicle_effect('ENGINE_HIT',message)
    if roll in (0,3):
        message=vehicle_notice(unit,'Your cockpit is destroyed!' if vtol else 'Your armor is pierced and you are killed instantly!')
        if vtol and not unit.has_status(MechStatus.LANDED):
            vehicle_notice(attacker,'You knock the VTOL out of the sky!')
            vehicle_broadcast(unit,'falls down from the sky!' if roll==0 else 'falls from the sky!')
        destroy_mech(unit,attacker,False,'COCKPIT' if vtol else 'PILOT',unit._engine)
        _kill_mech_contents(unit)
        return vehicle_effect('CREW_KILLED',message,vehicle_destroyed=True,crew_killed=True)
    reason='FUELTANK' if roll==4 else 'POWERPLANT'
    message=vehicle_notice(unit,'Your fuel tank explodes in a ball of fire!' if roll==4 else 'Your power plant explodes!')
    if unit is not attacker or vtol and roll==5:
        vehicle_broadcast(unit,("'s fule tank explodes in a ball of fire!" if fasa and not vtol else "'s fuel tank explodes in a ball of fire!") if roll==4 else "'s power plant suddenly explodes!")
    if vtol:
        from physics.collision import mech_elevation
        from physics.hexmath import ZSCALE
        unit.z=mech_elevation(unit);unit.fz=unit.z*ZSCALE
        unit.speed=unit.vertical_speed=0
    destroy_mech(unit,attacker,True,reason,unit._engine)
    if roll==5 and (fasa or vtol) and unit.sections[VehicleLocation.BSIDE].config&SectionConfig.CASE_TECH:
        destroy_section(unit,attacker,VehicleLocation.BSIDE,engine=unit._engine,los=los)
    else: explode_unit(unit,attacker)
    return vehicle_effect('FUEL_TANK_HIT' if roll==4 else 'AMMO_EXPLOSION',message,vehicle_destroyed=True)


def handle_cargo_hit(unit):
    from systems.movement_commands import notify
    message = 'The shot pierces your armor yet fails to hit a critical system!'
    notify(unit, message)
    return VehicleCritResult(crit_type=VehicleCritType.CARGO_HIT, message=message)
