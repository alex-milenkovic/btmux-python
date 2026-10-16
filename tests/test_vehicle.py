"""
Tests for vehicle entity and combat systems.

This module tests:
- Vehicle entity creation and properties
- Vehicle sections and armor
- Tank critical status flags
- Vehicle hit location tables
- Vehicle critical hit effects
- Motive damage system
- Turret mechanics
- Vehicle templates
"""

import unittest
from unittest.mock import patch, MagicMock

from entities.vehicle import (
    Vehicle,
    VehicleSection,
    TankCritStatus,
    is_vehicle,
    is_vtol,
    get_vehicle_section_name,
)
from entities.mech import (
    Mech,
    VehicleLocation,
    UnitType,
    MoveType,
    MechStatus,
    SectionConfig,
    Specials,
)


class TestVehicleCreation(unittest.TestCase):
    """Test vehicle entity creation."""

    def test_create_basic_vehicle(self):
        """Test creating a basic vehicle."""
        vehicle = Vehicle(name="TestTank", vehicle_type="TST-1T")
        self.assertEqual(vehicle.name, "TestTank")
        self.assertEqual(vehicle.vehicle_type, "TST-1T")
        self.assertEqual(vehicle.unit_type, UnitType.VEH_GROUND)
        self.assertEqual(vehicle.move_type, MoveType.TRACK)

    def test_create_test_vehicle(self):
        """Test the factory method for creating test vehicles."""
        vehicle = Vehicle.create_test_vehicle(
            name="Alpha",
            tonnage=50,
            move_type=MoveType.TRACK,
            has_turret=True,
        )
        self.assertEqual(vehicle.name, "Alpha")
        self.assertEqual(vehicle.tonnage, 50)
        self.assertTrue(vehicle.has_turret)
        self.assertEqual(vehicle.sections[VehicleLocation.FSIDE].armor, 30)
        self.assertEqual(vehicle.sections[VehicleLocation.TURRET].internal, 10)

    def test_create_vtol(self):
        """Test creating a VTOL vehicle."""
        vehicle = Vehicle.create_test_vehicle(
            name="Chopper",
            move_type=MoveType.VTOL,
        )
        self.assertEqual(vehicle.unit_type, UnitType.VTOL)
        self.assertEqual(vehicle.move_type, MoveType.VTOL)
        self.assertTrue(vehicle.is_vtol)
        self.assertEqual(vehicle.sections[VehicleLocation.ROTOR].armor, 2)

    def test_vehicle_sections_initialized(self):
        """Test that all sections are initialized."""
        vehicle = Vehicle()
        self.assertEqual(len(vehicle.sections), 6)
        for section in vehicle.sections:
            self.assertIsInstance(section, VehicleSection)


class TestVehicleStatus(unittest.TestCase):
    """Test vehicle status properties and flags."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

    def test_is_started(self):
        """Test is_started property."""
        self.assertFalse(self.vehicle.is_started)
        self.vehicle.set_status(MechStatus.STARTED)
        self.assertTrue(self.vehicle.is_started)

    def test_is_destroyed(self):
        """Test is_destroyed property."""
        self.assertFalse(self.vehicle.is_destroyed)
        self.vehicle.set_status(MechStatus.DESTROYED)
        self.assertTrue(self.vehicle.is_destroyed)

    def test_is_immobilized(self):
        """Test is_immobilized property."""
        self.assertFalse(self.vehicle.is_immobilized)
        self.vehicle.set_status(MechStatus.FALLEN)  # FALLEN = immobilized for vehicles
        self.assertTrue(self.vehicle.is_immobilized)

    def test_is_moving(self):
        """Test is_moving property."""
        self.assertFalse(self.vehicle.is_moving)
        self.vehicle.speed = 36.0
        self.assertTrue(self.vehicle.is_moving)

    def test_set_and_clear_status(self):
        """Test set_status and clear_status methods."""
        self.vehicle.set_status(MechStatus.STARTED)
        self.assertTrue(self.vehicle.has_status(MechStatus.STARTED))
        self.vehicle.clear_status(MechStatus.STARTED)
        self.assertFalse(self.vehicle.has_status(MechStatus.STARTED))


class TestTankCritStatus(unittest.TestCase):
    """Test tank-specific critical status flags."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

    def test_turret_jammed_flag(self):
        """Test turret jammed flag."""
        self.assertFalse(self.vehicle.turret_jammed)
        self.vehicle.set_tank_crit_status(TankCritStatus.TURRET_JAMMED)
        self.assertTrue(self.vehicle.turret_jammed)

    def test_turret_locked_flag(self):
        """Test turret locked flag."""
        self.assertFalse(self.vehicle.turret_locked)
        self.vehicle.set_tank_crit_status(TankCritStatus.TURRET_LOCKED)
        self.assertTrue(self.vehicle.turret_locked)

    def test_crew_stunned_flag(self):
        """Test crew stunned flag."""
        self.assertFalse(self.vehicle.crew_stunned)
        self.vehicle.set_tank_crit_status(TankCritStatus.CREW_STUNNED)
        self.assertTrue(self.vehicle.crew_stunned)

    def test_clear_tank_crit_status(self):
        """Test clearing tank critical status."""
        self.vehicle.set_tank_crit_status(TankCritStatus.TURRET_JAMMED)
        self.assertTrue(self.vehicle.turret_jammed)
        self.vehicle.clear_tank_crit_status(TankCritStatus.TURRET_JAMMED)
        self.assertFalse(self.vehicle.turret_jammed)


class TestVehicleMovement(unittest.TestCase):
    """Test vehicle movement methods."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()
        self.vehicle.cruise_speed = 36.0
        self.vehicle.flank_speed = 54.0
        self.vehicle.max_speed = 54.0

    def test_set_desired_speed(self):
        """Test setting desired speed."""
        self.vehicle.set_desired_speed(40.0)
        self.assertEqual(self.vehicle.desired_speed, 40.0)

    def test_set_desired_speed_clamped(self):
        """Test that desired speed is clamped to valid range."""
        self.vehicle.set_desired_speed(100.0)
        self.assertEqual(self.vehicle.desired_speed, 54.0)
        self.vehicle.set_desired_speed(-100.0)
        self.assertEqual(self.vehicle.desired_speed, -36.0)

    def test_stop(self):
        """Test stopping the vehicle."""
        self.vehicle.speed = 36.0
        self.vehicle.desired_speed = 36.0
        self.vehicle.stop()
        self.assertEqual(self.vehicle.desired_speed, 0.0)

    def test_immobilize(self):
        """Test immobilizing the vehicle."""
        self.vehicle.speed = 36.0
        self.vehicle.immobilize()
        self.assertEqual(self.vehicle.max_speed, 0.0)
        self.assertEqual(self.vehicle.speed, 0.0)
        self.assertTrue(self.vehicle.is_immobilized)

    def test_reduce_speed(self):
        """Test reducing max speed (motive damage)."""
        initial_max = self.vehicle.max_speed
        self.vehicle.reduce_speed(10.75)  # -1 MP
        self.assertAlmostEqual(self.vehicle.max_speed, initial_max - 10.75, places=2)

    def test_halve_speed(self):
        """Test halving max speed (severe motive damage)."""
        initial_max = self.vehicle.max_speed
        self.vehicle.halve_speed()
        self.assertAlmostEqual(self.vehicle.max_speed, initial_max / 2.0, places=2)


class TestTurretMechanics(unittest.TestCase):
    """Test turret mechanics."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle(has_turret=True)

    def test_has_turret(self):
        """Test has_turret property."""
        self.assertTrue(self.vehicle.has_turret)
        # Destroy turret
        self.vehicle.sections[VehicleLocation.TURRET].armor = 0
        self.vehicle.sections[VehicleLocation.TURRET].internal = 0
        self.assertFalse(self.vehicle.has_turret)

    def test_set_turret_facing(self):
        """Test setting turret facing."""
        self.vehicle.set_turret_facing(90)
        self.assertEqual(self.vehicle.turret_facing, 90)

    def test_turret_facing_normalized(self):
        """Test that turret facing is normalized."""
        self.vehicle.set_turret_facing(450)
        self.assertEqual(self.vehicle.turret_facing, 90)

    def test_turret_facing_blocked_when_jammed(self):
        """Test that jammed turret can't rotate."""
        self.vehicle.jam_turret()
        self.vehicle.turret_facing = 0
        self.vehicle.set_turret_facing(90)
        self.assertEqual(self.vehicle.turret_facing, 0)

    def test_turret_facing_blocked_when_locked(self):
        """Test that locked turret can't rotate."""
        self.vehicle.lock_turret()
        self.vehicle.turret_facing = 0
        self.vehicle.set_turret_facing(90)
        self.assertEqual(self.vehicle.turret_facing, 0)

    def test_jam_turret(self):
        """Test jamming the turret."""
        self.vehicle.jam_turret()
        self.assertTrue(self.vehicle.turret_jammed)
        self.assertFalse(self.vehicle.turret_locked)

    def test_lock_turret(self):
        """Test locking the turret."""
        self.vehicle.lock_turret()
        self.assertTrue(self.vehicle.turret_locked)
        self.assertFalse(self.vehicle.turret_jammed)

    def test_unjam_turret_success(self):
        """Test successfully unjamming the turret."""
        self.vehicle.jam_turret()
        self.assertTrue(self.vehicle.turret_jammed)
        result = self.vehicle.unjam_turret()
        self.assertTrue(result)
        self.assertFalse(self.vehicle.turret_jammed)

    def test_unjam_turret_fails_when_locked(self):
        """Test that unjamming fails when turret is locked."""
        self.vehicle.lock_turret()
        result = self.vehicle.unjam_turret()
        self.assertFalse(result)
        self.assertTrue(self.vehicle.turret_locked)

    def test_absolute_turret_facing(self):
        """Test calculating absolute turret facing."""
        self.vehicle.facing = 90
        self.vehicle.turret_facing = 45
        self.assertEqual(self.vehicle.get_absolute_turret_facing(), 135)


class TestVehicleDamage(unittest.TestCase):
    """Test vehicle damage application."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

    def test_apply_damage_to_armor(self):
        """Test applying damage that doesn't penetrate armor."""
        initial_armor = self.vehicle.sections[VehicleLocation.FSIDE].armor
        remaining = self.vehicle.apply_damage(VehicleLocation.FSIDE, 10)
        self.assertEqual(remaining, 0)
        self.assertEqual(self.vehicle.sections[VehicleLocation.FSIDE].armor, initial_armor - 10)

    def test_apply_damage_destroys_armor(self):
        """Test applying damage that destroys armor on non-turret section."""
        # Non-turret sections have no internal, so they're destroyed when armor gone
        self.vehicle.sections[VehicleLocation.LSIDE].armor = 10
        remaining = self.vehicle.apply_damage(VehicleLocation.LSIDE, 15)
        self.assertEqual(remaining, 5)  # 5 damage remaining
        self.assertTrue(self.vehicle.is_section_destroyed(VehicleLocation.LSIDE))

    def test_apply_damage_to_turret_internal(self):
        """Test applying damage to turret internal structure."""
        self.vehicle.sections[VehicleLocation.TURRET].armor = 5
        self.vehicle.sections[VehicleLocation.TURRET].internal = 10
        remaining = self.vehicle.apply_damage(VehicleLocation.TURRET, 10)
        self.assertEqual(remaining, 0)
        self.assertEqual(self.vehicle.sections[VehicleLocation.TURRET].armor, 0)
        self.assertEqual(self.vehicle.sections[VehicleLocation.TURRET].internal, 5)

    def test_total_armor(self):
        """Test calculating total remaining armor."""
        total = self.vehicle.total_armor()
        self.assertGreater(total, 0)
        # Damage some armor
        self.vehicle.apply_damage(VehicleLocation.FSIDE, 10)
        new_total = self.vehicle.total_armor()
        self.assertEqual(new_total, total - 10)


class TestCrewMechanics(unittest.TestCase):
    """Test crew damage and status mechanics."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

    def test_stun_crew(self):
        """Test stunning the crew."""
        self.vehicle.speed = 54.0
        self.vehicle.desired_speed = 54.0
        self.vehicle.stun_crew()
        self.assertTrue(self.vehicle.crew_stunned)
        # Speed should be limited to cruise
        self.assertLessEqual(self.vehicle.speed, self.vehicle.cruise_speed)

    def test_unstun_crew(self):
        """Test unstunning the crew."""
        self.vehicle.stun_crew()
        self.assertTrue(self.vehicle.crew_stunned)
        self.vehicle.unstun_crew()
        self.assertFalse(self.vehicle.crew_stunned)

    def test_driver_hit(self):
        """Test applying driver hit."""
        initial_skill = self.vehicle.pilot_skill_base
        self.vehicle.apply_driver_hit()
        self.assertEqual(self.vehicle.driver_hits, 1)
        self.assertEqual(self.vehicle.pilot_skill_base, initial_skill + 2)

    def test_commander_hit(self):
        """Test applying commander hit."""
        initial_skill = self.vehicle.pilot_skill_base
        initial_bth = self.vehicle.base_to_hit
        self.vehicle.apply_commander_hit()
        self.assertEqual(self.vehicle.commander_hits, 1)
        self.assertEqual(self.vehicle.pilot_skill_base, initial_skill + 1)
        self.assertEqual(self.vehicle.base_to_hit, initial_bth + 1)

    def test_sensor_hit(self):
        """Test applying sensor hit."""
        initial_bth = self.vehicle.base_to_hit
        self.vehicle.apply_sensor_hit()
        self.assertEqual(self.vehicle.base_to_hit, initial_bth + 1)

    def test_kill_crew(self):
        """Test killing the crew."""
        self.vehicle.kill_crew()
        self.assertEqual(self.vehicle.crew_hits, 6)
        self.assertTrue(self.vehicle.is_destroyed)


class TestVehicleHelpers(unittest.TestCase):
    """Test helper functions."""

    def test_is_vehicle(self):
        """Test is_vehicle helper."""
        vehicle = Vehicle.create_test_vehicle()
        self.assertTrue(is_vehicle(vehicle))

        # Create a mock non-vehicle
        mock = MagicMock()
        mock.unit_type = UnitType.MECH
        self.assertFalse(is_vehicle(mock))

    def test_is_vtol(self):
        """Test is_vtol helper."""
        vehicle = Vehicle.create_test_vehicle(move_type=MoveType.TRACK)
        self.assertFalse(is_vtol(vehicle))

        vtol = Vehicle.create_test_vehicle(move_type=MoveType.VTOL)
        self.assertTrue(is_vtol(vtol))

    def test_get_vehicle_section_name(self):
        """Test section name lookup."""
        self.assertEqual(get_vehicle_section_name(VehicleLocation.FSIDE), "Front")
        self.assertEqual(get_vehicle_section_name(VehicleLocation.BSIDE), "Rear")
        self.assertEqual(get_vehicle_section_name(VehicleLocation.TURRET), "Turret")
        self.assertEqual(get_vehicle_section_name(VehicleLocation.ROTOR), "Rotor")


# =============================================================================
# Vehicle Combat Tests
# =============================================================================

from systems.vehicle_combat import (
    VehicleCritType,
    VehicleCritResult,
    VehicleHitGroup,
    get_vehicle_hit_location,
    determine_vehicle_hit_group,
    resolve_vehicle_critical,
    handle_driver_hit,
    handle_commander_hit,
    handle_crew_stunned,
    handle_crew_killed,
    handle_sensor_hit,
    handle_stabilizer_destroyed,
    handle_turret_jam,
    handle_turret_lock,
    handle_turret_blown_off,
    handle_engine_hit,
    handle_motive_damage,
    handle_rotor_destroyed,
    apply_vehicle_damage,
)


class TestVehicleHitLocation(unittest.TestCase):
    """Test vehicle hit location determination."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

    def test_front_hit_location(self):
        """Test front arc hit locations."""
        # Roll 7 should hit front
        loc, is_crit, special = get_vehicle_hit_location(
            self.vehicle, VehicleHitGroup.FRONT, roll=7
        )
        self.assertEqual(loc, VehicleLocation.FSIDE)
        self.assertFalse(is_crit)

    def test_critical_hit_on_2(self):
        """Test critical hit on roll of 2."""
        loc, is_crit, special = get_vehicle_hit_location(
            self.vehicle, VehicleHitGroup.FRONT, roll=2
        )
        self.assertTrue(is_crit)

    def test_turret_hit_when_present(self):
        """Test turret hit when turret is present."""
        loc, is_crit, special = get_vehicle_hit_location(
            self.vehicle, VehicleHitGroup.FRONT, roll=10
        )
        self.assertEqual(loc, VehicleLocation.TURRET)

    def test_no_turret_hit_when_absent(self):
        """Test no turret hit when turret is absent."""
        self.vehicle.sections[VehicleLocation.TURRET].internal_orig = 0
        loc, is_crit, special = get_vehicle_hit_location(
            self.vehicle, VehicleHitGroup.FRONT, roll=10
        )
        self.assertEqual(loc, VehicleLocation.FSIDE)

    def test_motive_damage_on_hit(self):
        """Test motive damage indicated on certain hits."""
        # Roll 3 on left side should have motive damage
        loc, is_crit, special = get_vehicle_hit_location(
            self.vehicle, VehicleHitGroup.LEFTSIDE, roll=3
        )
        self.assertEqual(special, "motive")


class TestVehicleHitGroup(unittest.TestCase):
    """
    Test vehicle attack-direction arcs.

    Reference: mech.hitloc.c:2833-2924 FindAreaHitGroup(), vehicle branch at
    mech.hitloc.c:2909-2922. Vehicles use the fs_hw/as_hw pair, which is 30/30
    at the default btech_hit_arcs = 0 (mech.hitloc.c:2860-2861, default at
    src/conf.c:93) - a much narrower front arc than a mech's 90.

    ad is the bearing from the TARGET to the ATTACKER minus the target's facing
    (mech.hitloc.c:2881-2884). The attacker below sits due north of the target,
    where hex_bearing((50,50) -> (50,45)) is exactly 0, so rotating the target's
    facing picks an exact attack direction.
    """

    def setUp(self):
        self.attacker = Mech.create_test_mech()
        self.attacker.set_hex_position(50, 45)
        self.vehicle = Vehicle.create_test_vehicle()
        self.vehicle.set_hex_position(50, 50)

    def test_vehicle_front_arc(self):
        """Test ad == 0 is FRONT (mech.hitloc.c:2913)."""
        self.vehicle.facing = 0
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.FRONT)

    def test_vehicle_front_arc_inclusive_at_30(self):
        """Test ad == 30 is still FRONT (mech.hitloc.c:2913 - `ad <= (0 + fs_hw)`)."""
        self.vehicle.facing = 330
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.FRONT)

    def test_vehicle_side_arc_starts_past_30(self):
        """
        Test ad == 60 is a side hit for a vehicle.

        A mech at ad 60 is still FRONT (90 half-width, mech.hitloc.c:2857) but a
        vehicle's front arc stops at 30 (mech.hitloc.c:2860), so this is
        RIGHTSIDE via mech.hitloc.c:2919-2920.
        """
        self.vehicle.facing = 300
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.RIGHTSIDE)

    def test_vehicle_left_side_arc(self):
        """Test ad == 300 is LEFTSIDE (mech.hitloc.c:2917-2918 - ad >= 180)."""
        self.vehicle.facing = 60
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.LEFTSIDE)

    def test_vehicle_rear_arc(self):
        """Test ad == 180 is REAR (mech.hitloc.c:2915-2916)."""
        self.vehicle.facing = 180
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.REAR)

    def test_vehicle_rear_arc_inclusive_bounds(self):
        """Test ad == 150 and ad == 210 are REAR (mech.hitloc.c:2915)."""
        self.vehicle.facing = 210  # ad == 150
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.REAR)
        self.vehicle.facing = 150  # ad == 210
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.REAR)

    def test_attacker_behind_north_facing_vehicle_is_rear(self):
        """
        Test a shot from behind a north-facing vehicle is REAR.

        The pre-A3 code took the bearing attacker->target and returned FRONT for
        this geometry; mech.hitloc.c:2882-2884 measures target->attacker.
        """
        self.vehicle.facing = 0
        self.attacker.set_hex_position(50, 55)  # due south of the vehicle
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.REAR)

    def test_vehicle_arcs_widen_under_classic_rules(self):
        """
        Test btech_hit_arcs = 1 gives vehicles a 45 degree front half-width.

        mech.hitloc.c:2864-2869 - classic BTMUX rules set fs_hw = m_fs_hw = 45.
        """
        self.vehicle.facing = 320  # ad == 40
        # Default TW widths: past the 30 degree front half-width -> side hit
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.RIGHTSIDE)
        with patch('systems.combat.BTECH_HIT_ARCS', 1):
            self.assertEqual(
                determine_vehicle_hit_group(self.attacker, self.vehicle),
                VehicleHitGroup.FRONT)

    def test_bearing_uses_subhex_float_positions(self):
        """
        Test the attack direction comes from MechFX/MechFY, not hex centers.

        mech.hitloc.c:2882-2883 passes the float cartesian positions to
        FindBearing (which takes floats, mech.utils.c:395-418). At hex centers
        this geometry is ad 0 (FRONT); with real in-hex offsets it is ad 32,
        which is already outside a vehicle's 30 degree front half-width
        (mech.hitloc.c:2860) and so a RIGHTSIDE hit (mech.hitloc.c:2919-2920).
        The attacker is adjacent here because sub-hex offsets swing the bearing
        hardest at short range.
        """
        from physics.hexmath import float_to_hex

        self.vehicle.facing = 0
        self.attacker.set_hex_position(50, 49)   # adjacent, due north
        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.FRONT)

        self.attacker.fx += 100.0
        self.vehicle.fx -= 100.0
        # Both units are still standing in their own hexes.
        self.assertEqual(
            float_to_hex(self.attacker.fx, self.attacker.fy), (50, 49))
        self.assertEqual(
            float_to_hex(self.vehicle.fx, self.vehicle.fy), (50, 50))

        self.assertEqual(
            determine_vehicle_hit_group(self.attacker, self.vehicle),
            VehicleHitGroup.RIGHTSIDE)

    def test_no_position_defaults_to_front(self):
        """Test a positionless attacker falls back to FRONT."""
        self.assertEqual(
            determine_vehicle_hit_group(object(), self.vehicle),
            VehicleHitGroup.FRONT)


class TestVehicleCriticalEffects(unittest.TestCase):
    """Test vehicle critical hit effects."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

        from core.game_loop import GameEngine
        self.engine = GameEngine()
        self.engine.register_entity(self.vehicle)

    def test_driver_hit_effect(self):
        """Test driver hit critical effect."""
        result = handle_driver_hit(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.DRIVER_HIT)
        self.assertTrue(result.effect_applied)
        self.assertEqual(self.vehicle.driver_hits, 1)
        self.assertEqual(self.vehicle.pilot_skill_base, 2)

    def test_commander_hit_effect(self):
        """Test commander hit critical effect."""
        result = handle_commander_hit(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.COMMANDER_HIT)
        self.assertTrue(result.effect_applied)
        self.assertEqual(self.vehicle.commander_hits, 1)
        self.assertTrue(self.vehicle.crew_stunned)

    def test_crew_stunned_effect(self):
        """Test crew stunned critical effect."""
        result = handle_crew_stunned(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.CREW_STUNNED)
        self.assertTrue(result.effect_applied)
        self.assertTrue(self.vehicle.crew_stunned)

    def test_crew_killed_effect(self):
        """Test crew killed critical effect."""
        result = handle_crew_killed(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.CREW_KILLED)
        self.assertTrue(result.crew_killed)
        self.assertTrue(result.vehicle_destroyed)
        self.assertTrue(self.vehicle.is_destroyed)

    def test_sensor_hit_effect(self):
        """Test sensor hit critical effect."""
        result = handle_sensor_hit(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.SENSOR_HIT)
        self.assertEqual(self.vehicle.base_to_hit, 1)

    def test_stabilizer_destroyed_effect(self):
        """Test stabilizer destroyed critical effect."""
        result = handle_stabilizer_destroyed(self.vehicle, VehicleLocation.TURRET)
        self.assertEqual(result.crit_type, VehicleCritType.STABILIZER_DESTROYED)
        self.assertTrue(result.effect_applied)
        self.assertTrue(
            self.vehicle.sections[VehicleLocation.TURRET].config &
            SectionConfig.STABILIZERS_DESTROYED
        )

    def test_stabilizer_already_destroyed(self):
        """Test stabilizer hit when already destroyed."""
        self.vehicle.sections[VehicleLocation.TURRET].config |= SectionConfig.STABILIZERS_DESTROYED
        result = handle_stabilizer_destroyed(self.vehicle, VehicleLocation.TURRET)
        self.assertFalse(result.effect_applied)

    def test_turret_jam_effect(self):
        """Test turret jam critical effect."""
        result = handle_turret_jam(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.TURRET_JAM)
        self.assertTrue(result.effect_applied)
        self.assertTrue(self.vehicle.turret_jammed)

    def test_turret_jam_becomes_lock(self):
        """Test that second turret jam becomes lock."""
        self.vehicle.jam_turret()
        result = handle_turret_jam(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.TURRET_LOCK)
        self.assertTrue(self.vehicle.turret_locked)
        self.assertFalse(self.vehicle.turret_jammed)

    def test_turret_lock_effect(self):
        """Test turret lock critical effect."""
        result = handle_turret_lock(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.TURRET_LOCK)
        self.assertTrue(result.effect_applied)
        self.assertTrue(self.vehicle.turret_locked)

    def test_turret_blown_off_effect(self):
        """Test turret blown off critical effect."""
        result = handle_turret_blown_off(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.TURRET_BLOWN_OFF)
        self.assertTrue(result.effect_applied)
        self.assertTrue(self.vehicle.is_section_destroyed(VehicleLocation.TURRET))

    def test_engine_hit_effect(self):
        """Test engine hit critical effect."""
        result = handle_engine_hit(self.vehicle)
        self.assertEqual(result.crit_type, VehicleCritType.ENGINE_HIT)
        self.assertTrue(result.effect_applied)
        self.assertTrue(result.immobilized)
        self.assertTrue(self.vehicle.is_immobilized)


class TestMotiveDamage(unittest.TestCase):
    """Test motive system damage."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()
        self.vehicle.max_speed = 54.0
        self.vehicle.flank_speed = 54.0
        self.vehicle.cruise_speed = 36.0

    def test_minor_motive_damage(self):
        """Test minor motive damage (-1 MP)."""
        initial_speed = self.vehicle.max_speed
        result = handle_motive_damage(self.vehicle, "minor")
        self.assertEqual(result.crit_type, VehicleCritType.MOTIVE_DAMAGE_MINOR)
        self.assertTrue(result.effect_applied)
        self.assertAlmostEqual(
            self.vehicle.max_speed, initial_speed - 10.75, places=2
        )
        self.assertEqual(self.vehicle.motive_damage, 1)

    def test_major_motive_damage(self):
        """Test major motive damage (-2 MP)."""
        initial_speed = self.vehicle.max_speed
        result = handle_motive_damage(self.vehicle, "major")
        self.assertEqual(result.crit_type, VehicleCritType.MOTIVE_DAMAGE_MAJOR)
        self.assertTrue(result.effect_applied)
        self.assertAlmostEqual(
            self.vehicle.max_speed, initial_speed - 21.5, places=2
        )
        self.assertEqual(self.vehicle.motive_damage, 2)

    def test_motive_destroyed(self):
        """Test motive system destroyed (immobilized)."""
        result = handle_motive_damage(self.vehicle, "destroyed")
        self.assertEqual(result.crit_type, VehicleCritType.MOTIVE_DESTROYED)
        self.assertTrue(result.immobilized)
        self.assertTrue(self.vehicle.is_immobilized)
        self.assertEqual(self.vehicle.max_speed, 0.0)


class TestVTOLCriticals(unittest.TestCase):
    """Test VTOL-specific critical effects."""

    def setUp(self):
        self.vtol = Vehicle.create_test_vehicle(move_type=MoveType.VTOL)

        from core.game_loop import GameEngine
        self.engine = GameEngine()
        self.engine.register_entity(self.vtol)

    def test_rotor_destroyed_while_flying(self):
        """Test rotor destroyed while VTOL is airborne."""
        self.vtol.z = 5  # Flying
        result = handle_rotor_destroyed(self.vtol)
        self.assertEqual(result.crit_type, VehicleCritType.ROTOR_DESTROYED)
        self.assertFalse(result.vehicle_destroyed)
        self.assertFalse(self.vtol.is_destroyed)
        from core.events import EventType
        self.assertTrue(any(e.event_type == EventType.FALL for e in self.engine.events._events.values()))

    def test_rotor_destroyed_while_landed(self):
        """Test rotor destroyed while VTOL is landed."""
        self.vtol.set_status(MechStatus.LANDED)
        result = handle_rotor_destroyed(self.vtol)
        self.assertEqual(result.crit_type, VehicleCritType.ROTOR_DESTROYED)
        self.assertTrue(result.immobilized)
        self.assertFalse(result.vehicle_destroyed)


class TestResolveVehicleCritical(unittest.TestCase):
    """Test critical hit resolution."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

    def test_no_critical_on_low_roll(self):
        """Test no critical on roll < 6."""
        result = resolve_vehicle_critical(self.vehicle, VehicleLocation.FSIDE, roll=5)
        self.assertFalse(result.effect_applied)

    def test_critical_on_roll_6(self):
        """Test critical on roll of 6."""
        result = resolve_vehicle_critical(self.vehicle, VehicleLocation.FSIDE, roll=6)
        # Roll 6 on front = driver hit
        self.assertEqual(result.crit_type, VehicleCritType.DRIVER_HIT)

    def test_critical_on_roll_12(self):
        """Test critical on roll of 12."""
        result = resolve_vehicle_critical(self.vehicle, VehicleLocation.FSIDE, roll=12)
        # Roll 12 on front = crew killed
        self.assertEqual(result.crit_type, VehicleCritType.CREW_KILLED)
        self.assertTrue(result.crew_killed)


class TestApplyVehicleDamage(unittest.TestCase):
    """Test vehicle damage application with criticals."""

    def setUp(self):
        self.vehicle = Vehicle.create_test_vehicle()

    def test_apply_damage_no_critical(self):
        """Test applying damage without critical."""
        initial_armor = self.vehicle.sections[VehicleLocation.FSIDE].armor
        damage_dealt, crit_results = apply_vehicle_damage(
            self.vehicle, VehicleLocation.FSIDE, 10, is_critical=False
        )
        self.assertEqual(damage_dealt, 10)
        self.assertEqual(
            self.vehicle.sections[VehicleLocation.FSIDE].armor,
            initial_armor - 10
        )

    def test_apply_damage_with_motive_effect(self):
        """Test applying damage with motive damage effect."""
        damage_dealt, crit_results = apply_vehicle_damage(
            self.vehicle, VehicleLocation.LSIDE, 10,
            special_effect="motive"
        )
        # Should have motive damage result
        motive_crits = [r for r in crit_results
                        if r.crit_type == VehicleCritType.MOTIVE_DAMAGE_MINOR]
        self.assertGreater(len(motive_crits), 0)


# =============================================================================
# Vehicle Template Tests
# =============================================================================

from data.templates import (
    VehicleTemplate,
    VehicleArmorLayout,
    VehicleWeaponMount,
    get_vehicle_template,
    list_vehicle_templates,
    create_vehicle_from_template,
    LIGHT_TANK_TEMPLATE,
    MEDIUM_TANK_TEMPLATE,
    HEAVY_TANK_TEMPLATE,
    WHEELED_APC_TEMPLATE,
    HOVER_TANK_TEMPLATE,
    VTOL_TEMPLATE,
)


class TestVehicleTemplates(unittest.TestCase):
    """Test vehicle template system."""

    def test_list_vehicle_templates(self):
        """Test listing available vehicle templates."""
        templates = list_vehicle_templates()
        self.assertIn("LightTank", templates)
        self.assertIn("MediumTank", templates)
        self.assertIn("HeavyTank", templates)
        self.assertIn("WheeledAPC", templates)
        self.assertIn("HoverTank", templates)
        self.assertIn("AttackVTOL", templates)
        self.assertEqual(len(templates), 6)

    def test_get_vehicle_template(self):
        """Test getting a vehicle template by name."""
        template = get_vehicle_template("LightTank")
        self.assertIsNotNone(template)
        self.assertEqual(template.name, "LightTank")
        self.assertEqual(template.tonnage, 25)

    def test_get_nonexistent_template(self):
        """Test getting a nonexistent template."""
        template = get_vehicle_template("NonExistent")
        self.assertIsNone(template)

    def test_create_vehicle_from_template(self):
        """Test creating a vehicle from a template."""
        template = get_vehicle_template("LightTank")
        vehicle = create_vehicle_from_template(template, name="Alpha")
        self.assertEqual(vehicle.name, "Alpha")
        self.assertEqual(vehicle.tonnage, 25)
        self.assertEqual(vehicle.move_type, MoveType.TRACK)
        self.assertEqual(vehicle.sections[VehicleLocation.FSIDE].armor, 24)
        self.assertEqual(vehicle.sections[VehicleLocation.TURRET].armor, 18)
        self.assertEqual(vehicle.sections[VehicleLocation.TURRET].internal, 6)

    def test_light_tank_template(self):
        """Test LightTank template values."""
        self.assertEqual(LIGHT_TANK_TEMPLATE.tonnage, 25)
        self.assertEqual(LIGHT_TANK_TEMPLATE.cruise_mp, 4)
        self.assertEqual(LIGHT_TANK_TEMPLATE.move_type, MoveType.TRACK)
        self.assertTrue(LIGHT_TANK_TEMPLATE.has_turret)

    def test_wheeled_apc_no_turret(self):
        """Test WheeledAPC has no turret."""
        self.assertFalse(WHEELED_APC_TEMPLATE.has_turret)
        vehicle = create_vehicle_from_template(WHEELED_APC_TEMPLATE)
        self.assertEqual(vehicle.sections[VehicleLocation.TURRET].armor, 0)

    def test_hover_tank_template(self):
        """Test HoverTank template values."""
        self.assertEqual(HOVER_TANK_TEMPLATE.move_type, MoveType.HOVER)
        self.assertEqual(HOVER_TANK_TEMPLATE.cruise_mp, 8)
        self.assertEqual(HOVER_TANK_TEMPLATE.flank_mp, 12)

    def test_vtol_template(self):
        """Test AttackVTOL template values."""
        self.assertEqual(VTOL_TEMPLATE.unit_type, UnitType.VTOL)
        self.assertEqual(VTOL_TEMPLATE.move_type, MoveType.VTOL)
        vehicle = create_vehicle_from_template(VTOL_TEMPLATE)
        self.assertTrue(vehicle.is_vtol)
        self.assertEqual(vehicle.sections[VehicleLocation.ROTOR].armor, 2)

    def test_template_speed_calculations(self):
        """Test template speed calculations."""
        template = get_vehicle_template("MediumTank")
        cruise = template.calculate_cruise_speed()
        flank = template.calculate_flank_speed()
        self.assertAlmostEqual(cruise, 4 * 10.75, places=2)
        self.assertAlmostEqual(flank, 6 * 10.75, places=2)


class TestVehicleStatusString(unittest.TestCase):
    """Test vehicle status string representation."""

    def test_idle_status(self):
        """Test idle status string."""
        vehicle = Vehicle.create_test_vehicle()
        self.assertEqual(vehicle.status_string(), "IDLE")

    def test_started_status(self):
        """Test started status string."""
        vehicle = Vehicle.create_test_vehicle()
        vehicle.set_status(MechStatus.STARTED)
        self.assertIn("STARTED", vehicle.status_string())

    def test_multiple_status_flags(self):
        """Test multiple status flags in string."""
        vehicle = Vehicle.create_test_vehicle()
        vehicle.set_status(MechStatus.STARTED)
        vehicle.jam_turret()
        status = vehicle.status_string()
        self.assertIn("STARTED", status)
        self.assertIn("TURRET_JAMMED", status)


if __name__ == '__main__':
    unittest.main()
