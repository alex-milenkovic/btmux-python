"""
Tests for the Mech entity.

Tests cover:
- Mech creation and initialization
- Position handling (hex and float coordinates)
- Movement state management
- Heat tracking
- Armor and damage application
- Status flags
- Critical slots
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.mech import (
    Mech, Section, CriticalSlot, WeaponState,
    Location, UnitType, MoveType,
    MechStatus, CritStatus, SectionConfig, Specials, FireMode,
    NUM_SECTIONS, NUM_CRITICALS
)


class TestMechCreation(unittest.TestCase):
    """Tests for Mech creation and initialization."""

    def test_default_mech(self):
        """Test creating a mech with default values."""
        mech = Mech()
        self.assertEqual(mech.name, "")
        self.assertEqual(mech.tonnage, 50)
        self.assertEqual(mech.unit_type, UnitType.MECH)
        self.assertEqual(mech.move_type, MoveType.BIPED)
        self.assertEqual(mech.num_sinks, 10)
        self.assertEqual(len(mech.sections), NUM_SECTIONS)

    def test_custom_mech(self):
        """Test creating a mech with custom values."""
        mech = Mech(
            name="Atlas",
            mech_type="AS7-D",
            tonnage=100,
            num_sinks=20,
            max_speed=32.25  # 3/5 movement
        )
        self.assertEqual(mech.name, "Atlas")
        self.assertEqual(mech.mech_type, "AS7-D")
        self.assertEqual(mech.tonnage, 100)
        self.assertEqual(mech.num_sinks, 20)
        self.assertEqual(mech.max_speed, 32.25)

    def test_create_test_mech(self):
        """Test the test mech factory method."""
        mech = Mech.create_test_mech(name="TestBot", tonnage=50)
        self.assertEqual(mech.name, "TestBot")
        self.assertEqual(mech.tonnage, 50)
        # Check armor values are set
        self.assertEqual(mech.get_armor(Location.HEAD), 9)
        self.assertEqual(mech.get_armor(Location.CTORSO), 16)
        self.assertEqual(mech.get_rear_armor(Location.CTORSO), 5)

    def test_sections_initialized(self):
        """Test that sections are properly initialized."""
        mech = Mech()
        self.assertEqual(len(mech.sections), NUM_SECTIONS)
        for section in mech.sections:
            self.assertEqual(len(section.criticals), NUM_CRITICALS)


class TestMechPosition(unittest.TestCase):
    """Tests for Mech position handling."""

    def test_default_position(self):
        """Test default position values."""
        mech = Mech()
        self.assertEqual(mech.x, 0)
        self.assertEqual(mech.y, 0)
        self.assertEqual(mech.z, 0)
        self.assertEqual(mech.fx, 0.0)
        self.assertEqual(mech.fy, 0.0)
        self.assertEqual(mech.fz, 0.0)

    def test_set_position(self):
        """Test setting position directly."""
        mech = Mech()
        mech.set_position(x=10, y=20, fx=100.0, fy=200.0, z=2, fz=129.0)
        self.assertEqual(mech.x, 10)
        self.assertEqual(mech.y, 20)
        self.assertEqual(mech.fx, 100.0)
        self.assertEqual(mech.fy, 200.0)
        self.assertEqual(mech.z, 2)
        self.assertEqual(mech.fz, 129.0)

    def test_set_position_updates_last(self):
        """Test that set_position updates last_x and last_y."""
        mech = Mech()
        mech.x = 5
        mech.y = 10
        mech.set_position(x=7, y=12, fx=0.0, fy=0.0)
        self.assertEqual(mech.last_x, 5)
        self.assertEqual(mech.last_y, 10)

    def test_hex_position_property(self):
        """Test hex_position property."""
        mech = Mech()
        mech.x = 15
        mech.y = 25
        self.assertEqual(mech.hex_position, (15, 25))

    def test_float_position_property(self):
        """Test float_position property."""
        mech = Mech()
        mech.fx = 123.45
        mech.fy = 678.90
        self.assertEqual(mech.float_position, (123.45, 678.90))

    def test_position_3d_property(self):
        """Test position_3d property."""
        mech = Mech()
        mech.fx = 100.0
        mech.fy = 200.0
        mech.fz = 300.0
        self.assertEqual(mech.position_3d, (100.0, 200.0, 300.0))

    def test_set_hex_position(self):
        """Test set_hex_position updates float coordinates."""
        mech = Mech()
        mech.set_hex_position(5, 5, z=1)
        self.assertEqual(mech.x, 5)
        self.assertEqual(mech.y, 5)
        self.assertEqual(mech.z, 1)
        # Float position should be updated (exact values depend on hexmath)
        self.assertNotEqual(mech.fx, 0.0)
        self.assertNotEqual(mech.fy, 0.0)


class TestMechMovement(unittest.TestCase):
    """Tests for Mech movement state."""

    def test_default_movement_state(self):
        """Test default movement values."""
        mech = Mech()
        self.assertEqual(mech.speed, 0.0)
        self.assertEqual(mech.desired_speed, 0.0)
        self.assertEqual(mech.facing, 0)
        self.assertEqual(mech.desired_facing, 0)

    def test_set_desired_speed(self):
        """Test setting desired speed."""
        mech = Mech(max_speed=64.5)
        mech.set_desired_speed(32.0)
        self.assertEqual(mech.desired_speed, 32.0)

    def test_set_desired_speed_clamped(self):
        """Test that desired speed is clamped to max."""
        mech = Mech(max_speed=64.5)
        mech.set_desired_speed(100.0)
        self.assertEqual(mech.desired_speed, 64.5)
        mech.set_desired_speed(-100.0)
        self.assertEqual(mech.desired_speed, -64.5)

    def test_set_desired_facing(self):
        """Test setting desired facing."""
        mech = Mech()
        mech.set_desired_facing(90)
        self.assertEqual(mech.desired_facing, 90)

    def test_set_desired_facing_normalized(self):
        """Test that facing is normalized to 0-359."""
        mech = Mech()
        mech.set_desired_facing(450)  # 450 -> 90
        self.assertEqual(mech.desired_facing, 90)
        mech.set_desired_facing(-90)  # -90 -> 270
        self.assertEqual(mech.desired_facing, 270)

    def test_stop(self):
        """Test stop method."""
        mech = Mech()
        mech.desired_speed = 50.0
        mech.stop()
        self.assertEqual(mech.desired_speed, 0.0)

    def test_walking_speed(self):
        """Test walking speed calculation."""
        mech = Mech(max_speed=64.5)
        # Walking is 2/3 of max
        self.assertAlmostEqual(mech.walking_speed, 43.0, places=1)

    def test_is_moving(self):
        """Test is_moving property."""
        mech = Mech()
        self.assertFalse(mech.is_moving)
        mech.speed = 10.0
        self.assertTrue(mech.is_moving)

    def test_is_running(self):
        """Test is_running property."""
        mech = Mech(max_speed=64.5)
        mech.speed = 30.0  # Below walking speed
        self.assertFalse(mech.is_running)
        mech.speed = 60.0  # Above walking speed
        self.assertTrue(mech.is_running)


class TestMechHeat(unittest.TestCase):
    """Tests for Mech heat system."""

    def test_default_heat(self):
        """Test default heat values."""
        mech = Mech()
        self.assertEqual(mech.heat, 0.0)
        self.assertEqual(mech.plus_heat, 0.0)
        self.assertEqual(mech.minus_heat, 0.0)

    def test_effective_heat_sinks_single(self):
        """Test effective heat sinks with single heat sinks."""
        mech = Mech(num_sinks=10)
        self.assertEqual(mech.effective_heat_sinks, 10)

    def test_effective_heat_sinks_double(self):
        """Test effective heat sinks with double heat sinks."""
        mech = Mech(num_sinks=10)
        mech.specials = Specials.DOUBLE_HEAT_TECH
        self.assertEqual(mech.effective_heat_sinks, 20)

    def test_effective_heat_sinks_clan(self):
        """Test effective heat sinks with Clan tech."""
        mech = Mech(num_sinks=10)
        mech.specials = Specials.CLAN_TECH
        self.assertEqual(mech.effective_heat_sinks, 20)

    def test_calculate_minus_heat(self):
        """Test heat dissipation calculation."""
        mech = Mech(num_sinks=10)
        self.assertEqual(mech.calculate_minus_heat(), 10.0)

    def test_calculate_minus_heat_in_water(self):
        """Test heat dissipation in water."""
        mech = Mech(num_sinks=10)
        self.assertEqual(mech.calculate_minus_heat(in_water=True), 20.0)


class TestMechStatus(unittest.TestCase):
    """Tests for Mech status flags."""

    def test_default_status(self):
        """Test default status flags."""
        mech = Mech()
        self.assertEqual(mech.status, MechStatus.NONE)
        self.assertFalse(mech.is_started)
        self.assertFalse(mech.is_destroyed)
        self.assertFalse(mech.is_jumping)

    def test_set_status(self):
        """Test setting status flags."""
        mech = Mech()
        mech.set_status(MechStatus.STARTED)
        self.assertTrue(mech.is_started)
        self.assertTrue(mech.has_status(MechStatus.STARTED))

    def test_clear_status(self):
        """Test clearing status flags."""
        mech = Mech()
        mech.set_status(MechStatus.STARTED)
        mech.clear_status(MechStatus.STARTED)
        self.assertFalse(mech.is_started)

    def test_multiple_status_flags(self):
        """Test multiple status flags."""
        mech = Mech()
        mech.set_status(MechStatus.STARTED)
        mech.set_status(MechStatus.JUMPING)
        self.assertTrue(mech.is_started)
        self.assertTrue(mech.is_jumping)
        mech.clear_status(MechStatus.STARTED)
        self.assertFalse(mech.is_started)
        self.assertTrue(mech.is_jumping)

    def test_crit_status_flags(self):
        """Test critical status flags."""
        mech = Mech()
        mech.set_crit_status(CritStatus.GYRO_DAMAGED)
        self.assertTrue(mech.has_crit_status(CritStatus.GYRO_DAMAGED))
        mech.clear_crit_status(CritStatus.GYRO_DAMAGED)
        self.assertFalse(mech.has_crit_status(CritStatus.GYRO_DAMAGED))

    def test_status_string(self):
        """Test status string generation."""
        mech = Mech()
        self.assertEqual(mech.status_string(), "IDLE")
        mech.set_status(MechStatus.STARTED)
        self.assertIn("STARTED", mech.status_string())


class TestMechArmor(unittest.TestCase):
    """Tests for Mech armor and damage."""

    def test_get_armor(self):
        """Test getting armor values."""
        mech = Mech.create_test_mech()
        self.assertEqual(mech.get_armor(Location.HEAD), 9)
        self.assertEqual(mech.get_armor(Location.CTORSO), 16)

    def test_get_internal(self):
        """Test getting internal structure values."""
        mech = Mech.create_test_mech()
        self.assertEqual(mech.get_internal(Location.HEAD), 3)
        self.assertEqual(mech.get_internal(Location.CTORSO), 16)

    def test_get_rear_armor(self):
        """Test getting rear armor values."""
        mech = Mech.create_test_mech()
        self.assertEqual(mech.get_rear_armor(Location.CTORSO), 5)

    def test_apply_damage_armor_only(self):
        """Test applying damage that only affects armor."""
        mech = Mech.create_test_mech()
        initial_armor = mech.get_armor(Location.CTORSO)
        remaining = mech.apply_damage(Location.CTORSO, 5)
        self.assertEqual(remaining, 0)
        self.assertEqual(mech.get_armor(Location.CTORSO), initial_armor - 5)

    def test_apply_damage_through_armor(self):
        """Test applying damage that goes through armor to internal."""
        mech = Mech.create_test_mech()
        # CT has 16 armor, 16 internal
        remaining = mech.apply_damage(Location.CTORSO, 20)
        self.assertEqual(remaining, 0)
        self.assertEqual(mech.get_armor(Location.CTORSO), 0)
        self.assertEqual(mech.get_internal(Location.CTORSO), 12)  # 16 - 4

    def test_apply_damage_destroys_section(self):
        """Test applying damage that destroys a section."""
        mech = Mech.create_test_mech()
        # Head has 9 armor, 3 internal = 12 total
        remaining = mech.apply_damage(Location.HEAD, 15)
        self.assertEqual(remaining, 3)  # 3 damage carries through
        self.assertTrue(mech.is_section_destroyed(Location.HEAD))

    def test_apply_rear_damage(self):
        """Test applying damage to rear armor."""
        mech = Mech.create_test_mech()
        # CT has 5 rear armor
        remaining = mech.apply_damage(Location.CTORSO, 3, is_rear=True)
        self.assertEqual(remaining, 0)
        self.assertEqual(mech.get_rear_armor(Location.CTORSO), 2)

    def test_total_armor(self):
        """Test total armor calculation."""
        mech = Mech.create_test_mech()
        total = mech.total_armor()
        # Sum of all armor + internal + rear
        self.assertGreater(total, 0)

    def test_total_armor_original(self):
        """Test total original armor calculation."""
        mech = Mech.create_test_mech()
        total_orig = mech.total_armor_original()
        # Apply some damage
        mech.apply_damage(Location.HEAD, 5)
        # Original should be unchanged
        self.assertEqual(mech.total_armor_original(), total_orig)
        # Current should be less
        self.assertLess(mech.total_armor(), total_orig)


class TestMechCriticals(unittest.TestCase):
    """Tests for critical slot management."""

    def test_get_critical(self):
        """Test getting a critical slot."""
        mech = Mech()
        crit = mech.get_critical(Location.CTORSO, 0)
        self.assertIsInstance(crit, CriticalSlot)
        self.assertEqual(crit.type, 0)  # Empty

    def test_set_critical_type(self):
        """Test setting critical slot type."""
        mech = Mech()
        mech.set_critical_type(Location.CTORSO, 0, 42)
        self.assertEqual(mech.get_critical(Location.CTORSO, 0).type, 42)

    def test_destroy_critical(self):
        """Test destroying a critical slot."""
        mech = Mech()
        mech.destroy_critical(Location.LARM, 5)
        self.assertTrue(mech.is_critical_destroyed(Location.LARM, 5))

    def test_critical_firemode(self):
        """Test critical slot fire modes."""
        mech = Mech()
        crit = mech.get_critical(Location.RARM, 0)
        crit.firemode = FireMode.REAR_MOUNT | FireMode.ON_TC
        self.assertTrue(crit.firemode & FireMode.REAR_MOUNT)
        self.assertTrue(crit.firemode & FireMode.ON_TC)


class TestSection(unittest.TestCase):
    """Tests for Section class."""

    def test_section_creation(self):
        """Test creating a section."""
        section = Section(armor=10, internal=5)
        self.assertEqual(section.armor, 10)
        self.assertEqual(section.internal, 5)
        self.assertEqual(len(section.criticals), NUM_CRITICALS)

    def test_section_config_flags(self):
        """Test section configuration flags."""
        section = Section()
        section.config = SectionConfig.CASE_TECH
        self.assertTrue(section.config & SectionConfig.CASE_TECH)


class TestCriticalSlot(unittest.TestCase):
    """Tests for CriticalSlot class."""

    def test_critical_slot_creation(self):
        """Test creating a critical slot."""
        crit = CriticalSlot(type=10, data=50)
        self.assertEqual(crit.type, 10)
        self.assertEqual(crit.data, 50)
        self.assertEqual(crit.firemode, FireMode.NONE)


class TestWeaponState(unittest.TestCase):
    """Tests for WeaponState class."""

    def test_weapon_state_creation(self):
        """Test creating a weapon state."""
        weapon = WeaponState(
            section=Location.RARM,
            critical=3,
            weapon_idx=5,
            recycle=0
        )
        self.assertEqual(weapon.section, Location.RARM)
        self.assertEqual(weapon.critical, 3)
        self.assertEqual(weapon.weapon_idx, 5)


class TestMechRepr(unittest.TestCase):
    """Tests for Mech string representation."""

    def test_repr(self):
        """Test mech repr."""
        mech = Mech(name="Atlas", mech_type="AS7-D")
        mech.x = 10
        mech.y = 20
        mech.facing = 90
        mech.speed = 32.0
        mech.heat = 5.0
        repr_str = repr(mech)
        self.assertIn("Atlas", repr_str)
        self.assertIn("AS7-D", repr_str)
        self.assertIn("10", repr_str)
        self.assertIn("20", repr_str)


if __name__ == "__main__":
    unittest.main()
