"""
Tests for the jump and fall system.

Tests cover:
- Jump initiation and validation
- Jump trajectory calculations
- Landing piloting checks
- Fall damage calculations
- Standing up mechanics
"""

import unittest
import math
from unittest.mock import patch

from entities.mech import Mech, MechStatus, CritStatus, Location, MoveType, SectionConfig
from entities.pilot import Pilot
from physics.jump import (
    can_jump, mech_jump, update_jump, land_mech, mech_falls, stand_up,
    calculate_jump_altitude, make_piloting_check, get_jump_mp,
    JUMP_TICK, JUMPSTABIL_TIME, MIN_JUMP_HEAT, JUMP_HEAT_PER_MP,
    DEFAULT_PILOTING, PILOTING_GYRO_DAMAGED,
)
from physics.hexmath import hex_distance, SCALEMAP, ZSCALE
from data.templates import get_template, create_mech_from_template


class TestJumpValidation(unittest.TestCase):
    """Test jump validation logic."""

    def setUp(self):
        """Create a jump-capable mech for testing."""
        template = get_template("JumpMech")
        self.mech = create_mech_from_template(template, "TestJumper")
        self.mech.set_hex_position(50, 50)
        self.mech.set_status(MechStatus.STARTED)

    def test_can_jump_valid(self):
        """Test that a valid jump is allowed."""
        # Jump within range (5 MP)
        can, reason = can_jump(self.mech, 52, 50)
        self.assertTrue(can, reason)

    def test_cannot_jump_not_started(self):
        """Test that unstarted mech cannot jump."""
        self.mech.clear_status(MechStatus.STARTED)
        can, reason = can_jump(self.mech, 52, 50)
        self.assertFalse(can)
        self.assertIn("not started", reason.lower())

    def test_cannot_jump_destroyed(self):
        """Test that destroyed mech cannot jump."""
        self.mech.set_status(MechStatus.DESTROYED)
        can, reason = can_jump(self.mech, 52, 50)
        self.assertFalse(can)
        self.assertIn("destroyed", reason.lower())

    def test_cannot_jump_already_jumping(self):
        """Test that already jumping mech cannot jump again."""
        self.mech.set_status(MechStatus.JUMPING)
        can, reason = can_jump(self.mech, 52, 50)
        self.assertFalse(can)
        self.assertIn("already jumping", reason.lower())

    def test_cannot_jump_while_fallen(self):
        """Test that fallen mech cannot jump."""
        self.mech.set_status(MechStatus.FALLEN)
        can, reason = can_jump(self.mech, 52, 50)
        self.assertFalse(can)
        self.assertIn("fallen", reason.lower())

    def test_cannot_jump_no_jets(self):
        """Test that mech without jump jets cannot jump."""
        # Create a non-jump mech
        template = get_template("TestMech")
        mech = create_mech_from_template(template, "NoJump")
        mech.set_hex_position(50, 50)
        mech.set_status(MechStatus.STARTED)

        can, reason = can_jump(mech, 52, 50)
        self.assertFalse(can)
        self.assertIn("doesn't have jump jets", reason.lower())

    def test_cannot_jump_out_of_range(self):
        """Test that jump beyond MP range is rejected."""
        # JumpMech has 5 MP, try to jump 10 hexes
        can, reason = can_jump(self.mech, 60, 50)
        self.assertFalse(can)
        self.assertIn("out of range", reason.lower())

    def test_cannot_jump_same_hex(self):
        """Test that jumping to same hex is rejected."""
        can, reason = can_jump(self.mech, 50, 50)
        self.assertFalse(can)
        self.assertIn("already in the target hex", reason.lower())


class TestJumpInitiation(unittest.TestCase):
    """Test jump initiation mechanics."""

    def setUp(self):
        """Create a jump-capable mech for testing."""
        template = get_template("JumpMech")
        self.mech = create_mech_from_template(template, "TestJumper")
        self.mech.set_hex_position(50, 50)
        self.mech.set_status(MechStatus.STARTED)
        self.mech.heat = 0.0
        self.mech.plus_heat = 0.0

    def test_jump_sets_status(self):
        """Test that initiating jump sets JUMPING status."""
        result = mech_jump(self.mech, 52, 50)
        self.assertTrue(result.success)
        self.assertTrue(self.mech.is_jumping)

    def test_jump_stores_destination(self):
        """Test that jump stores target coordinates."""
        mech_jump(self.mech, 53, 51)
        self.assertEqual(self.mech.going_x, 53)
        self.assertEqual(self.mech.going_y, 51)

    def test_jump_stores_origin(self):
        """Test that jump stores starting position."""
        orig_fx = self.mech.fx
        orig_fy = self.mech.fy
        mech_jump(self.mech, 52, 50)
        self.assertEqual(self.mech.start_fx, orig_fx)
        self.assertEqual(self.mech.start_fy, orig_fy)

    def test_jump_calculates_heading(self):
        """Test that jump heading is calculated correctly."""
        # Jump directly east (increasing X, same Y)
        mech_jump(self.mech, 55, 50)
        # Heading should be roughly 90 (east)
        self.assertTrue(60 <= self.mech.jump_heading <= 120,
                       f"Heading {self.mech.jump_heading} not eastward")

    def test_jump_generates_heat(self):
        """Test that jumping generates heat."""
        initial_heat = self.mech.plus_heat
        result = mech_jump(self.mech, 52, 50)
        self.assertEqual(self.mech.plus_heat, initial_heat)  # normal heat update owns it
        self.assertGreaterEqual(result.heat_generated, MIN_JUMP_HEAT)

    def test_jump_heat_scales_with_distance(self):
        """Test that longer jumps generate more heat."""
        mech1 = create_mech_from_template(get_template("JumpMech"), "Short")
        mech1.set_hex_position(50, 50)
        mech1.set_status(MechStatus.STARTED)

        mech2 = create_mech_from_template(get_template("JumpMech"), "Long")
        mech2.set_hex_position(50, 50)
        mech2.set_status(MechStatus.STARTED)

        result1 = mech_jump(mech1, 51, 50)  # 1 hex
        result2 = mech_jump(mech2, 55, 50)  # ~5 hexes

        self.assertLessEqual(result1.heat_generated, result2.heat_generated)

    def test_jump_stops_ground_movement(self):
        """Test that jumping stops ground movement."""
        self.mech.speed = 32.0
        self.mech.desired_speed = 64.0
        mech_jump(self.mech, 52, 50)
        self.assertEqual(self.mech.speed, 0.0)
        self.assertEqual(self.mech.desired_speed, 64.0)


class TestJumpTrajectory(unittest.TestCase):
    """Test jump trajectory calculations."""

    def test_altitude_parabolic(self):
        """Test that altitude follows parabolic arc."""
        jump_length = 1000.0
        start_fz = 0.0
        end_fz = 0.0
        jump_top = 100

        # At start (progress=0)
        alt_start = calculate_jump_altitude(0, jump_length, start_fz, end_fz, jump_top)
        self.assertAlmostEqual(alt_start, 0.0, places=1)

        # At midpoint (progress=jump_length/2) - should be at peak
        alt_mid = calculate_jump_altitude(jump_length/2, jump_length, start_fz, end_fz, jump_top)
        self.assertAlmostEqual(alt_mid, jump_top, places=1)

        # At end (progress=jump_length)
        alt_end = calculate_jump_altitude(jump_length, jump_length, start_fz, end_fz, jump_top)
        self.assertAlmostEqual(alt_end, 0.0, places=1)

    def test_altitude_with_elevation_change(self):
        """Test altitude calculation with different start/end elevations."""
        jump_length = 1000.0
        start_fz = 0.0
        end_fz = 64.5  # 1 level up
        jump_top = 100

        # At end, should be at end_fz
        alt_end = calculate_jump_altitude(jump_length, jump_length, start_fz, end_fz, jump_top)
        self.assertAlmostEqual(alt_end, end_fz, places=1)

    def test_altitude_zero_length(self):
        """Test altitude calculation with zero jump length."""
        alt = calculate_jump_altitude(0, 0, 100.0, 100.0, 50)
        self.assertEqual(alt, 100.0)


class TestJumpUpdate(unittest.TestCase):
    """Test jump position updates."""

    def setUp(self):
        """Create a jumping mech for testing."""
        template = get_template("JumpMech")
        self.mech = create_mech_from_template(template, "TestJumper")
        self.mech.set_hex_position(50, 50)
        self.mech.set_status(MechStatus.STARTED)
        from entities.map import GameMap
        board = GameMap(100, 100)
        board._id = 100
        board.add_mech(self.mech)
        # Initiate a jump
        mech_jump(self.mech, 53, 50)

    def test_jump_update_changes_position(self):
        """Test that jump update moves the mech."""
        orig_fx = self.mech.fx

        # Update several ticks
        for _ in range(5):
            if self.mech.is_jumping:
                update_jump(self.mech)

        # Position should have changed
        self.assertNotEqual(self.mech.fx, orig_fx)

    def test_jump_completes_at_destination(self):
        """Test that jump completes when reaching destination."""
        # Update until no longer jumping
        max_iterations = 100
        for _ in range(max_iterations):
            if not self.mech.is_jumping:
                break
            update_jump(self.mech)

        # Should have landed
        self.assertFalse(self.mech.is_jumping)
        # Should be at destination
        self.assertEqual(self.mech.x, 53)
        self.assertEqual(self.mech.y, 50)


class TestLanding(unittest.TestCase):
    """Test landing mechanics."""

    def setUp(self):
        """Create a mech that just jumped."""
        template = get_template("JumpMech")
        self.mech = create_mech_from_template(template, "TestJumper")
        self.mech.set_hex_position(50, 50)
        self.mech.set_status(MechStatus.STARTED | MechStatus.JUMPING)

    def test_landing_clears_jump_status(self):
        """Test that landing clears JUMPING status."""
        land_mech(self.mech)
        self.assertFalse(self.mech.is_jumping)

    @patch('physics.jump.random.randint')
    def test_landing_piloting_success(self, mock_randint):
        """Test successful landing piloting check."""
        # Roll 12 (always succeeds)
        mock_randint.return_value = 6
        success = land_mech(self.mech)
        self.assertTrue(success)
        self.assertFalse(self.mech.is_fallen)

    @patch('physics.jump.random.randint')
    def test_landing_piloting_failure_causes_fall(self, mock_randint):
        """Test that failed landing piloting check causes fall."""
        # Roll 2 (always fails)
        mock_randint.return_value = 1
        self.mech.sections[Location.LLEG].basetohit = 1
        success = land_mech(self.mech)
        self.assertFalse(success)
        self.assertTrue(self.mech.is_fallen)

    @patch('physics.jump.random.randint')
    def test_landing_with_gyro_damage_harder(self, mock_randint):
        """Test that gyro damage makes landing harder."""
        # A roll of 6 succeeds on piloting 5 (need 5+) but fails
        # with GYRO_DAMAGED's +3 modifier (need 8+).
        mock_randint.return_value = 3
        self.assertTrue(land_mech(self.mech))
        self.assertFalse(self.mech.is_fallen)

        self.mech.clear_status(MechStatus.FALLEN)
        self.mech.set_status(MechStatus.JUMPING)
        self.mech.set_crit_status(CritStatus.GYRO_DAMAGED)
        self.mech.pilot_skill_base = 3  # The critical handler accumulates this.
        self.assertFalse(land_mech(self.mech))
        self.assertTrue(self.mech.is_fallen)


class TestFalling(unittest.TestCase):
    """Test falling mechanics."""

    def setUp(self):
        """Create a mech for fall testing."""
        template = get_template("JumpMech")
        self.mech = create_mech_from_template(template, "FallTest")
        self.mech.set_hex_position(50, 50)
        self.mech.set_status(MechStatus.STARTED)

    def test_fall_sets_status(self):
        """Test that falling sets FALLEN status."""
        mech_falls(self.mech, levels=1)
        self.assertTrue(self.mech.is_fallen)

    def test_fall_clears_jumping(self):
        """Test that falling clears JUMPING status."""
        self.mech.set_status(MechStatus.JUMPING)
        mech_falls(self.mech)
        self.assertFalse(self.mech.is_jumping)

    def test_fall_stops_movement(self):
        """Test that falling stops movement."""
        self.mech.speed = 32.0
        self.mech.desired_speed = 64.0
        mech_falls(self.mech)
        self.assertEqual(self.mech.speed, 0.0)

    def test_fall_causes_damage(self):
        """Test that falling causes damage."""
        orig_armor = self.mech.total_armor()
        result = mech_falls(self.mech, levels=1)
        self.assertGreater(result.damage_taken, 0)
        # Armor should have decreased
        self.assertLess(self.mech.total_armor(), orig_armor)

    def test_fall_damage_scales_with_levels(self):
        """Test that falling more levels causes more damage."""
        # Create two mechs
        mech1 = create_mech_from_template(get_template("JumpMech"), "Fall1")
        mech2 = create_mech_from_template(get_template("JumpMech"), "Fall2")
        mech1.set_status(MechStatus.STARTED)
        mech2.set_status(MechStatus.STARTED)

        # Fall different amounts (average over multiple falls)
        total_dmg_1 = sum(mech_falls(create_mech_from_template(
            get_template("JumpMech"), f"F1_{i}"), levels=1).damage_taken
            for i in range(20))
        total_dmg_3 = sum(mech_falls(create_mech_from_template(
            get_template("JumpMech"), f"F3_{i}"), levels=3).damage_taken
            for i in range(20))

        # 3-level falls should average more damage
        self.assertGreater(total_dmg_3 / 20, total_dmg_1 / 20)

    @patch('physics.jump.random.randint')
    def test_fall_pilot_injury(self, mock_randint):
        """Test that pilot can be injured in fall."""
        # Roll 2 (always fails piloting check)
        mock_randint.return_value = 1
        initial_hits = self.mech.pilot_hits

        result = mech_falls(self.mech, levels=3)

        # Pilot should have taken damage
        self.assertEqual(result.pilot_damage, 1)
        self.assertEqual(self.mech.pilot_hits, initial_hits + 1)


class TestStandingUp(unittest.TestCase):
    """Test standing up mechanics."""

    def setUp(self):
        """Create a fallen mech for testing."""
        template = get_template("JumpMech")
        self.mech = create_mech_from_template(template, "FallenTest")
        self.mech.set_hex_position(50, 50)
        self.mech.set_status(MechStatus.STARTED | MechStatus.FALLEN)

    def test_can_stand_when_fallen(self):
        """Test that fallen mech can attempt to stand."""
        from physics.jump import can_stand
        can, reason = can_stand(self.mech)
        self.assertTrue(can, reason)

    def test_cannot_stand_when_not_fallen(self):
        """Test that non-fallen mech cannot stand (already standing)."""
        from physics.jump import can_stand
        self.mech.clear_status(MechStatus.FALLEN)
        can, reason = can_stand(self.mech)
        self.assertFalse(can)
        self.assertIn("not fallen", reason.lower())

    def test_cannot_stand_gyro_destroyed(self):
        """Test that mech with destroyed gyro cannot stand."""
        from physics.jump import can_stand
        self.mech.set_crit_status(CritStatus.GYRO_DESTROYED)
        can, reason = can_stand(self.mech)
        self.assertFalse(can)
        self.assertIn("gyro", reason.lower())

    def test_cannot_stand_both_legs_destroyed(self):
        """Test that mech with both legs destroyed cannot stand."""
        from physics.jump import can_stand
        self.mech.sections[Location.LLEG].armor =         self.mech.sections[Location.LLEG].internal = 0
        self.mech.sections[Location.RLEG].armor =         self.mech.sections[Location.RLEG].internal = 0
        can, reason = can_stand(self.mech)
        self.assertFalse(can)
        self.assertIn("no legs", reason.lower())

    @patch('physics.jump.random.randint')
    def test_stand_success(self, mock_randint):
        """Test successful stand attempt."""
        mock_randint.return_value = 6  # Roll 12
        success, _ = stand_up(self.mech)
        self.assertTrue(success)
        self.assertFalse(self.mech.is_fallen)

    @patch('physics.jump.random.randint')
    def test_stand_failure(self, mock_randint):
        """Test failed stand attempt."""
        mock_randint.return_value = 1  # Roll 2
        success, _ = stand_up(self.mech)
        self.assertFalse(success)
        self.assertTrue(self.mech.is_fallen)


class TestPilotingChecks(unittest.TestCase):
    """Test piloting check mechanics."""

    def setUp(self):
        """Create a mech for piloting tests."""
        template = get_template("JumpMech")
        self.mech = create_mech_from_template(template, "PilotTest")
        self.mech.set_status(MechStatus.STARTED)

    @patch('core.randomness.roll')
    def test_piloting_check_success(self, mock_randint):
        """Test successful piloting check."""
        mock_randint.return_value = 12  # Source Roll returns the sum
        success, roll, target = make_piloting_check(self.mech)
        self.assertTrue(success)
        self.assertEqual(roll, 12)
        self.assertEqual(target, self.mech.pilot.piloting)

    @patch('core.randomness.roll')
    def test_piloting_check_failure(self, mock_randint):
        """Test failed piloting check."""
        mock_randint.return_value = 2  # Source Roll returns the sum
        success, roll, target = make_piloting_check(self.mech)
        self.assertFalse(success)
        self.assertEqual(roll, 2)

    @patch('core.randomness.roll')
    def test_piloting_check_with_modifier(self, mock_randint):
        """Test piloting check with modifier."""
        mock_randint.return_value = 8  # Source Roll returns the sum
        success, roll, target = make_piloting_check(self.mech, modifier=3)
        # Target = 5 (base) + 3 (modifier) = 8
        # Roll 8 >= 8, should succeed
        self.assertTrue(success)
        self.assertEqual(target, 8)

    def test_piloting_check_gyro_destroyed_auto_fail(self):
        """Test that destroyed gyro causes auto-fail."""
        self.mech.set_crit_status(CritStatus.GYRO_DESTROYED)
        success, _, target = make_piloting_check(self.mech)
        self.assertFalse(success)
        self.assertEqual(target, 99)  # Impossible target

    def test_piloting_check_gyro_damaged_modifier(self):
        """Test that damaged gyro adds modifier."""
        self.mech.set_crit_status(CritStatus.GYRO_DAMAGED)
        _, _, target = make_piloting_check(self.mech)
        self.assertEqual(target, self.mech.pilot.piloting + PILOTING_GYRO_DAMAGED)


class TestPilotSkillWiring(unittest.TestCase):
    """
    Test that the landing/fall/stand rolls read the pilot, not a constant.

    Every pilot skill roll in the C goes through MechPilotSkillRoll_BTH
    (mech.utils.c:666-675), whose line 668 is
    `mods += FindSPilotPiloting(mech) + MechPilotSkillBase(mech)`: the base is
    the seated pilot's skill (FindPilotPiloting, mech.utils.c:580-590) plus the
    quad's -2 (FindSPilotPiloting, mech.utils.c:592-595).  The three roll sites
    ported here are LandMech (mech.move.c:1639), MechFalls (mech.move.c:1834)
    and mech_stand (mech.move.c:612).

    All rolls below are mocked to 2d6 = 4, which clears a piloting-2 target and
    misses a piloting-5 one.
    """

    def _jumper(self, pilot, quad=False):
        """Build a started JumpMech with the given pilot (None = empty cockpit)."""
        mech = create_mech_from_template(get_template("JumpMech"), "SkillTest")
        mech.pilot = pilot
        mech.set_hex_position(50, 50)
        mech.set_status(MechStatus.STARTED)
        if quad:
            # MechMove(mech) == MOVE_QUAD is the -2 case (mech.utils.c:594)
            mech.move_type = MoveType.QUAD
        return mech

    @patch('physics.jump.random.randint')
    def test_landing_reads_pilot_piloting(self, mock_randint):
        """Test a piloting-2 pilot lands where a piloting-5 pilot falls."""
        mock_randint.return_value = 2  # 2d6 = 4

        veteran = self._jumper(Pilot(piloting=2))
        veteran.sections[Location.LLEG].basetohit = 1
        veteran.set_status(MechStatus.JUMPING)
        self.assertTrue(land_mech(veteran))
        self.assertFalse(veteran.is_fallen)

        green = self._jumper(Pilot(piloting=5))
        green.sections[Location.LLEG].basetohit = 1
        green.set_status(MechStatus.JUMPING)
        self.assertFalse(land_mech(green))
        self.assertTrue(green.is_fallen)

    @patch('physics.jump.random.randint')
    def test_fall_injury_reads_pilot_piloting(self, mock_randint):
        """Test the fall injury roll (mech.move.c:1834) uses the pilot's skill."""
        mock_randint.return_value = 2  # 2d6 = 4

        # Target = skill + levels: veteran 2+1=3 (made), green 5+1=6 (missed)
        veteran = self._jumper(Pilot(piloting=2))
        self.assertEqual(mech_falls(veteran, levels=1).pilot_damage, 0)
        self.assertEqual(veteran.pilot_hits, 0)

        green = self._jumper(Pilot(piloting=5))
        self.assertEqual(mech_falls(green, levels=1).pilot_damage, 1)
        self.assertEqual(green.pilot_hits, 1)

    @patch('physics.jump.random.randint')
    def test_stand_reads_pilot_piloting(self, mock_randint):
        """Test the stand roll (mech.move.c:612) uses the pilot's skill."""
        mock_randint.return_value = 2  # 2d6 = 4

        veteran = self._jumper(Pilot(piloting=2))
        veteran.set_status(MechStatus.FALLEN)
        success, _ = stand_up(veteran)
        self.assertTrue(success)
        self.assertFalse(veteran.is_fallen)

        green = self._jumper(Pilot(piloting=5))
        green.set_status(MechStatus.FALLEN)
        success, _ = stand_up(green)
        self.assertFalse(success)
        self.assertTrue(green.is_fallen)

    @patch('physics.jump.random.randint')
    def test_quad_landing_bonus(self, mock_randint):
        """Test a quad's -2 reaches the landing roll (mech.utils.c:594)."""
        mock_randint.return_value = 2  # 2d6 = 4

        quad = self._jumper(Pilot(piloting=5), quad=True)  # target 5 - 2 = 3
        quad.sections[Location.LLEG].basetohit = 1
        quad.set_status(MechStatus.JUMPING)
        self.assertTrue(land_mech(quad))

        biped = self._jumper(Pilot(piloting=5))            # target 5
        biped.sections[Location.LLEG].basetohit = 1
        biped.set_status(MechStatus.JUMPING)
        self.assertFalse(land_mech(biped))

    @patch('physics.jump.random.randint')
    def test_quad_fall_injury_bonus(self, mock_randint):
        """Test a quad's -2 reaches the fall injury roll (mech.utils.c:594)."""
        mock_randint.return_value = 2  # 2d6 = 4

        quad = self._jumper(Pilot(piloting=5), quad=True)  # target 5 - 2 + 1 = 4
        self.assertEqual(mech_falls(quad, levels=1).pilot_damage, 0)

        biped = self._jumper(Pilot(piloting=5))            # target 5 + 1 = 6
        self.assertEqual(mech_falls(biped, levels=1).pilot_damage, 1)

    @patch('physics.jump.random.randint')
    def test_quad_stand_bonus(self, mock_randint):
        """Test a quad's -2 reaches the stand roll (mech.utils.c:594)."""
        mock_randint.return_value = 2  # 2d6 = 4

        quad = self._jumper(Pilot(piloting=5), quad=True)  # target 5 - 2 = 3
        quad.set_status(MechStatus.FALLEN)
        self.assertTrue(stand_up(quad)[0])

        biped = self._jumper(Pilot(piloting=5))            # target 5
        biped.set_status(MechStatus.FALLEN)
        self.assertFalse(stand_up(biped)[0])

    def test_quad_piloting_check_target(self):
        """Test make_piloting_check applies the quad's -2 (mech.utils.c:594)."""
        quad = self._jumper(Pilot(piloting=5), quad=True)
        _, _, target = make_piloting_check(quad)
        self.assertEqual(target, 5 - 2)

    def test_empty_cockpit_falls_back_to_default(self):
        """Test a machine with nobody in it rolls against DEFAULT_PILOTING."""
        # FindPilotPiloting's final fallback (mech.utils.c:589)
        empty = self._jumper(None)
        _, _, target = make_piloting_check(empty)
        self.assertEqual(target, DEFAULT_PILOTING)

        # An explicitly seated Pilot retains piloting 5; missing pilot uses 6.
        seated = self._jumper(Pilot())
        _, _, seated_target = make_piloting_check(seated)
        self.assertEqual(seated_target, 5)

    @patch('physics.jump.random.randint')
    def test_empty_cockpit_landing_unchanged(self, mock_randint):
        """Test an empty cockpit lands exactly as the pre-pilot code did."""
        mock_randint.return_value = 2  # 2d6 = 4, under DEFAULT_PILOTING 5
        empty = self._jumper(None)
        empty.sections[Location.LLEG].basetohit = 1
        empty.set_status(MechStatus.JUMPING)
        self.assertFalse(land_mech(empty))
        self.assertTrue(empty.is_fallen)

    def test_explicit_piloting_skill_overrides_pilot(self):
        """Test make_piloting_check's explicit skill still wins over the pilot."""
        mech = self._jumper(Pilot(piloting=2))
        _, _, override_target = make_piloting_check(mech, piloting_skill=8)
        self.assertEqual(override_target, 8)

        _, _, pilot_target = make_piloting_check(mech)
        self.assertEqual(pilot_target, 2)


class TestJumpMPRetrieval(unittest.TestCase):
    """Test jump MP retrieval."""

    def test_get_jump_mp_from_mech(self):
        """Test getting jump MP from mech attribute."""
        template = get_template("JumpMech")
        mech = create_mech_from_template(template, "Test")
        mp = get_jump_mp(mech)
        self.assertEqual(mp, 5)

    def test_get_jump_mp_no_jets(self):
        """Test getting jump MP from mech without jets."""
        template = get_template("TestMech")
        mech = create_mech_from_template(template, "Test")
        mp = get_jump_mp(mech)
        self.assertEqual(mp, 0)


if __name__ == '__main__':
    unittest.main()
