"""
Tests for the movement system.

Tests cover:
- Turn rate calculations
- Heading updates (turning)
- Speed updates (acceleration/deceleration)
- Position updates (movement)
- Hex crossing detection
- Integration with game loop
"""

import unittest
import math

from physics.movement import (
    MOVE_TICK, MOVE_MOD,
    MP1, MP2, MP3, MP4, MP5, KPH_PER_MP,
    calculate_turn_rate, update_heading,
    calculate_effective_max_speed, calculate_heat_speed_reduction, update_speed,
    move_mech, check_hex_crossing, on_hex_entered,
    update_movement,
    movement_periodic, register_movement_system,
    mech_move_event, start_move_event,
)
from physics.hexmath import hex_to_float, float_to_hex, SCALEMAP
from entities.mech import Mech, MechStatus, MoveType, CritStatus, Specials


def place_on_map(mech, engine=None, board=None):
    """Movement validates mapindex through the live map lookup before motion."""
    from entities.map import GameMap
    board = board if board is not None else GameMap(100, 100)
    board._id = 100
    if engine is not None:
        engine.register_entity(board)
    board.add_mech(mech)
    return board


class TestMovementConstants(unittest.TestCase):
    """Test movement constants are correctly defined."""

    def test_move_tick(self):
        """MOVE_TICK should be 1 (updates every tick)."""
        self.assertEqual(MOVE_TICK, 1)

    def test_move_mod(self):
        """MOVE_MOD should be 0.5."""
        self.assertEqual(MOVE_MOD, 0.5)

    def test_mp_constants(self):
        """MP constants should be correct."""
        self.assertEqual(MP1, 10.75)
        self.assertEqual(MP2, 21.5)
        self.assertEqual(MP3, 32.25)
        self.assertEqual(MP4, 43.0)
        self.assertEqual(MP5, 53.75)

    def test_kph_per_mp(self):
        """KPH_PER_MP should equal MP1."""
        self.assertEqual(KPH_PER_MP, 10.75)


class TestTurnRate(unittest.TestCase):
    """Test turn rate calculations."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.max_speed = 64.5  # 6/9 movement

    def test_turn_rate_stationary(self):
        """Stationary mechs should turn faster than moving ones."""
        self.mech.speed = 0.0
        rate_stationary = calculate_turn_rate(self.mech, self.mech.max_speed)

        self.mech.speed = 30.0
        rate_moving = calculate_turn_rate(self.mech, self.mech.max_speed)

        self.assertGreater(rate_stationary, rate_moving)

    def test_turn_rate_quad_faster(self):
        """Quads should turn faster than bipeds."""
        self.mech.move_type = MoveType.BIPED
        rate_biped = calculate_turn_rate(self.mech, self.mech.max_speed)

        self.mech.move_type = MoveType.QUAD
        rate_quad = calculate_turn_rate(self.mech, self.mech.max_speed)

        self.assertGreater(rate_quad, rate_biped)

    def test_turn_rate_running_penalty(self):
        """Running should reduce turn rate."""
        walk_speed = self.mech.max_speed * 2.0 / 3.0

        self.mech.speed = walk_speed - 5.0  # Walking
        rate_walking = calculate_turn_rate(self.mech, self.mech.max_speed)

        self.mech.speed = self.mech.max_speed  # Running
        rate_running = calculate_turn_rate(self.mech, self.mech.max_speed)

        self.assertGreater(rate_walking, rate_running)

    def test_fasa_overspeed_cannot_turn(self):
        """UpdateHeading sets a zero offset above the effective maximum."""
        self.mech.speed = 1000.0  # Absurdly fast
        rate = calculate_turn_rate(self.mech, 1.0)  # Very low max speed
        self.assertEqual(rate, 0.0)


class TestUpdateHeading(unittest.TestCase):
    """Test heading update function."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.facing = 0
        self.mech.max_speed = 64.5

    def test_no_change_when_at_target(self):
        """Should return False when already at desired facing."""
        self.mech.facing = 90
        self.mech.desired_facing = 90
        result = update_heading(self.mech)
        self.assertFalse(result)
        self.assertEqual(self.mech.facing, 90)

    def test_turn_right(self):
        """Should turn right (clockwise) when target is to the right."""
        self.mech.facing = 0
        self.mech.desired_facing = 90
        update_heading(self.mech)
        self.assertGreater(self.mech.facing, 0)

    def test_turn_left(self):
        """Should turn left (counterclockwise) when target is to the left."""
        self.mech.facing = 90
        self.mech.desired_facing = 0
        update_heading(self.mech)
        self.assertLess(self.mech.facing, 90)

    def test_turn_wrap_around_0(self):
        """Should handle wrapping around 0/360 correctly."""
        self.mech.facing = 350
        self.mech.desired_facing = 10
        # Should turn right (through 0), not left (through 180)
        update_heading(self.mech)
        # Either still > 350 (turned right and wrapped) or == 10 (reached target)
        self.assertTrue(self.mech.facing > 350 or self.mech.facing <= 10)

    def test_sets_chead_flag(self):
        """Should set CHEAD flag when heading changes."""
        self.mech.facing = 0
        self.mech.desired_facing = 90
        self.mech.clear_crit_status(CritStatus.CHEAD)

        update_heading(self.mech)

        self.assertTrue(self.mech.has_crit_status(CritStatus.CHEAD))

    def test_reaches_target_eventually(self):
        """Should reach target heading within reasonable ticks."""
        self.mech.facing = 0
        self.mech.desired_facing = 180
        self.mech.speed = 0  # Stationary = faster turning

        for _ in range(100):  # Should reach 180 within 100 ticks
            if self.mech.facing == 180:
                break
            update_heading(self.mech)

        self.assertEqual(self.mech.facing, 180)


class TestEffectiveMaxSpeed(unittest.TestCase):
    """Test effective max speed calculations."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.max_speed = 64.5

    def test_base_speed(self):
        """With no modifiers, should return base max speed."""
        speed = calculate_effective_max_speed(self.mech)
        self.assertEqual(speed, 64.5)

    def test_masc_bonus(self):
        """MASC should increase max speed by 4/3."""
        self.mech.set_status(MechStatus.MASC_ENABLED)
        speed = calculate_effective_max_speed(self.mech)
        self.assertAlmostEqual(speed, 64.5 * 4.0 / 3.0, places=2)

    def test_supercharger_bonus(self):
        """Supercharger should increase max speed by 4/3."""
        self.mech.set_status(MechStatus.SCHARGE_ENABLED)
        speed = calculate_effective_max_speed(self.mech)
        self.assertAlmostEqual(speed, 64.5 * 4.0 / 3.0, places=2)

    def test_masc_plus_supercharger(self):
        """MASC + Supercharger should give 2.5x bonus."""
        self.mech.set_status(MechStatus.MASC_ENABLED)
        self.mech.set_status(MechStatus.SCHARGE_ENABLED)
        speed = calculate_effective_max_speed(self.mech)
        self.assertAlmostEqual(speed, 64.5 / 1.5 * 2.5, places=2)

    def test_triple_myomer_at_high_heat(self):
        """TSM should add 1.5 MP when heat >= 9."""
        self.mech.specials = Specials.TRIPLE_MYOMER_TECH
        self.mech.heat = 9.0
        speed = calculate_effective_max_speed(self.mech)
        self.assertAlmostEqual(speed, 86, places=2)

    def test_triple_myomer_at_low_heat(self):
        """TSM should not add bonus when heat < 9."""
        self.mech.specials = Specials.TRIPLE_MYOMER_TECH
        self.mech.heat = 8.0
        speed = calculate_effective_max_speed(self.mech)
        self.assertEqual(speed, 64.5)


class TestHeatSpeedReduction(unittest.TestCase):
    """Test heat-based speed reduction."""

    def test_no_reduction_below_5(self):
        """No speed reduction below 5 heat."""
        mult = calculate_heat_speed_reduction(4.9, 64.5)
        self.assertEqual(mult, 1.0)

    def test_reduction_at_5_heat(self):
        """Should have reduction at 5+ heat."""
        mult = calculate_heat_speed_reduction(5.0, 64.5)
        self.assertLess(mult, 1.0)

    def test_increasing_reduction(self):
        """Higher heat should mean more reduction."""
        # Use higher max_speed (faster mech) to avoid both reaching 0
        mult_5 = calculate_heat_speed_reduction(5.0, 100.0)
        mult_10 = calculate_heat_speed_reduction(10.0, 100.0)
        mult_15 = calculate_heat_speed_reduction(15.0, 100.0)
        mult_20 = calculate_heat_speed_reduction(20.0, 100.0)
        mult_25 = calculate_heat_speed_reduction(25.0, 100.0)

        self.assertGreater(mult_5, mult_10)
        self.assertGreater(mult_10, mult_15)
        self.assertGreater(mult_15, mult_20)
        self.assertGreaterEqual(mult_20, mult_25)  # May equal at extreme values


class TestUpdateSpeed(unittest.TestCase):
    """Test speed update function."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.max_speed = 64.5
        self.mech.speed = 0.0
        self.mech.desired_speed = 0.0

    def test_no_change_when_at_target(self):
        """Should return False when already at desired speed."""
        self.mech.speed = 30.0
        self.mech.desired_speed = 30.0
        result = update_speed(self.mech)
        self.assertFalse(result)

    def test_acceleration(self):
        """Should accelerate toward desired speed."""
        self.mech.speed = 0.0
        self.mech.desired_speed = 64.5
        update_speed(self.mech)
        self.assertGreater(self.mech.speed, 0.0)

    def test_deceleration(self):
        """Should decelerate toward desired speed."""
        self.mech.speed = 64.5
        self.mech.desired_speed = 0.0
        update_speed(self.mech)
        self.assertLess(self.mech.speed, 64.5)

    def test_reverse_speed(self):
        """Should handle negative (reverse) speeds."""
        self.mech.speed = 0.0
        self.mech.desired_speed = -30.0
        update_speed(self.mech)
        self.assertLess(self.mech.speed, 0.0)

    def test_full_desired_speed_is_preserved(self):
        """UpdateSpeed consumes full desired speed; commands enforce limits."""
        self.mech.desired_speed = 200.0  # Way over max
        for _ in range(100):
            update_speed(self.mech)
        self.assertEqual(self.mech.speed, 200.0)

    def test_quad_accelerates_faster(self):
        """Quads should accelerate faster than bipeds."""
        self.mech.move_type = MoveType.BIPED
        self.mech.speed = 0.0
        self.mech.desired_speed = 64.5
        update_speed(self.mech)
        biped_speed = self.mech.speed

        self.mech.move_type = MoveType.QUAD
        self.mech.speed = 0.0
        update_speed(self.mech)
        quad_speed = self.mech.speed

        self.assertGreater(quad_speed, biped_speed)

    def test_no_movement_when_fallen(self):
        """Should not change speed when fallen."""
        self.mech.set_status(MechStatus.FALLEN)
        self.mech.speed = 30.0
        self.mech.desired_speed = 64.5
        result = update_speed(self.mech)
        self.assertFalse(result)
        self.assertEqual(self.mech.speed, 30.0)

    def test_no_movement_when_jumping(self):
        """Should not change speed when jumping."""
        self.mech.set_status(MechStatus.JUMPING)
        self.mech.speed = 30.0
        self.mech.desired_speed = 64.5
        result = update_speed(self.mech)
        self.assertFalse(result)

    def test_reaches_target_eventually(self):
        """Should reach target speed within reasonable ticks."""
        self.mech.desired_speed = 64.5
        for _ in range(100):
            update_speed(self.mech)
            if abs(self.mech.speed - 64.5) < 0.1:
                break

        self.assertAlmostEqual(self.mech.speed, 64.5, places=0)


class TestMoveMech(unittest.TestCase):
    """Test position update function."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.set_hex_position(10, 10, z=0)
        self.mech.facing = 0  # North
        self.mech.max_speed = 64.5
        place_on_map(self.mech)

    def test_no_movement_when_stationary(self):
        """Should not move when speed is 0."""
        self.mech.speed = 0.0
        old_fx, old_fy = self.mech.fx, self.mech.fy
        result = move_mech(self.mech)
        self.assertFalse(result)
        self.assertEqual(self.mech.fx, old_fx)
        self.assertEqual(self.mech.fy, old_fy)

    def test_moves_north(self):
        """Should move north when facing 0."""
        self.mech.facing = 0
        self.mech.speed = 64.5
        old_fy = self.mech.fy
        move_mech(self.mech)
        # North is negative Y in BTMux coordinate system
        self.assertLess(self.mech.fy, old_fy)

    def test_moves_south(self):
        """Should move south when facing 180."""
        self.mech.facing = 180
        self.mech.speed = 64.5
        old_fy = self.mech.fy
        move_mech(self.mech)
        # South is positive Y
        self.assertGreater(self.mech.fy, old_fy)

    def test_moves_east(self):
        """Should move east when facing 90."""
        self.mech.facing = 90
        self.mech.speed = 64.5
        old_fx = self.mech.fx
        move_mech(self.mech)
        # East is positive X
        self.assertGreater(self.mech.fx, old_fx)

    def test_moves_west(self):
        """Should move west when facing 270."""
        self.mech.facing = 270
        self.mech.speed = 64.5
        old_fx = self.mech.fx
        move_mech(self.mech)
        # West is negative X
        self.assertLess(self.mech.fx, old_fx)

    def test_updates_hex_position(self):
        """Should update hex position from float position."""
        self.mech.facing = 0
        self.mech.speed = 200.0  # Fast enough to definitely cross hexes

        for _ in range(10):
            move_mech(self.mech)

        # Hex position should have changed
        self.assertNotEqual((self.mech.x, self.mech.y), (10, 10))

    def test_stores_last_position(self):
        """Should store last position for hex crossing detection."""
        self.mech.facing = 0
        self.mech.speed = 200.0
        move_mech(self.mech)

        self.assertEqual(self.mech.last_x, 10)
        self.assertEqual(self.mech.last_y, 10)

    def test_lateral_movement(self):
        """Lateral movement should affect direction."""
        self.mech.facing = 0  # North
        self.mech.lateral = 90  # Sidestep right
        self.mech.speed = 64.5
        old_fx = self.mech.fx
        move_mech(self.mech)
        # Should move east (positive X) due to lateral
        self.assertGreater(self.mech.fx, old_fx)


class TestHexCrossing(unittest.TestCase):
    """Test hex crossing detection."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_hex_position(10, 10)

    def test_no_crossing_same_hex(self):
        """Should return False when in same hex."""
        self.mech.last_x = 10
        self.mech.last_y = 10
        self.assertFalse(check_hex_crossing(self.mech))

    def test_crossing_x_changed(self):
        """Should return True when X changed."""
        self.mech.last_x = 9
        self.mech.last_y = 10
        self.assertTrue(check_hex_crossing(self.mech))

    def test_crossing_y_changed(self):
        """Should return True when Y changed."""
        self.mech.last_x = 10
        self.mech.last_y = 9
        self.assertTrue(check_hex_crossing(self.mech))


class TestOnHexEntered(unittest.TestCase):
    """Test hex entered callback."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_hex_position(10, 10)
        self.mech.hexes_walked = 0.0

    def test_increments_hexes_walked(self):
        """Should increment hexes_walked counter."""
        on_hex_entered(self.mech, 9, 10)
        self.assertEqual(self.mech.hexes_walked, 1.0)

    def test_breaks_hidden_status(self):
        """Should clear HIDDEN status when entering new hex."""
        self.mech.set_crit_status(CritStatus.HIDDEN)
        on_hex_entered(self.mech, 9, 10)
        self.assertFalse(self.mech.has_crit_status(CritStatus.HIDDEN))


class TestUpdateMovement(unittest.TestCase):
    """Test combined movement update."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.set_hex_position(10, 10)
        self.mech.facing = 0
        self.mech.desired_facing = 0
        self.mech.speed = 0.0
        self.mech.desired_speed = 0.0

    def test_returns_result_dict(self):
        """Should return a dict with all result fields."""
        result = update_movement(self.mech)
        self.assertIn('heading_changed', result)
        self.assertIn('speed_changed', result)
        self.assertIn('position_changed', result)
        self.assertIn('hex_crossed', result)

    def test_no_movement_when_not_started(self):
        """Should not move when mech is not started."""
        self.mech.clear_status(MechStatus.STARTED)
        self.mech.desired_speed = 64.5
        result = update_movement(self.mech)
        self.assertFalse(result['speed_changed'])
        self.assertFalse(result['position_changed'])

    def test_no_movement_when_destroyed(self):
        """Should not move when mech is destroyed."""
        self.mech.set_status(MechStatus.DESTROYED)
        self.mech.desired_speed = 64.5
        result = update_movement(self.mech)
        self.assertFalse(result['speed_changed'])

    def test_full_movement_cycle(self):
        """Should handle full movement cycle."""
        self.mech.desired_facing = 90
        self.mech.desired_speed = 64.5

        # Run several updates
        for _ in range(50):
            result = update_movement(self.mech)

        # Should have turned and accelerated
        self.assertEqual(self.mech.facing, 90)
        self.assertGreater(self.mech.speed, 0)


class TestGameLoopIntegration(unittest.TestCase):
    """Test integration with game loop."""

    def test_movement_periodic_updates_mechs(self):
        """movement_periodic should update all registered mechs."""
        from core.game_loop import GameEngine

        engine = GameEngine()
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.set_hex_position(10, 10)
        mech.desired_speed = 64.5
        mech.speed = 0.0

        engine.register_entity(mech)
        movement_periodic(engine)

        self.assertGreater(mech.speed, 0.0)

    def test_register_movement_system(self):
        """register_movement_system should set up periodic."""
        from core.game_loop import GameEngine

        engine = GameEngine()
        register_movement_system(engine)

        # Should have registered a periodic
        self.assertEqual(len(engine._periodics), 1)
        self.assertEqual(engine._periodics[0].name, "movement")
        self.assertEqual(engine._periodics[0].interval, MOVE_TICK)


class TestMovementWithGameLoop(unittest.TestCase):
    """Integration tests running movement through game loop."""

    def test_mech_moves_over_time(self):
        """Mech should move when game loop runs."""
        from core.game_loop import GameEngine

        engine = GameEngine()
        register_movement_system(engine)

        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.set_hex_position(50, 50)
        mech.desired_speed = 64.5
        mech.facing = 90  # East
        mech.desired_facing = 90

        place_on_map(mech, engine)
        engine.register_entity(mech)

        old_x = mech.x
        old_fx = mech.fx

        # Run 20 ticks
        engine.run_ticks(20)

        # Should have moved east
        self.assertGreater(mech.fx, old_fx)

    def test_mech_turns_over_time(self):
        """Mech should turn toward desired facing over time."""
        from core.game_loop import GameEngine

        engine = GameEngine()
        register_movement_system(engine)

        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.set_hex_position(50, 50)
        mech.facing = 0
        mech.desired_facing = 180
        mech.speed = 0  # Stationary for faster turning

        place_on_map(mech, engine)
        engine.register_entity(mech)

        # Run 50 ticks
        engine.run_ticks(50)

        # Should have turned to face 180
        self.assertEqual(mech.facing, 180)


class TestMoveEvent(unittest.TestCase):
    """Test event-driven movement (mech_move_event, mech.events.c:319-347)."""

    def setUp(self):
        from core.game_loop import GameEngine

        self.engine = GameEngine()
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.set_hex_position(50, 50)
        self.mech.facing = 90  # East
        self.mech.desired_facing = 90
        self.mech.speed = 0.0
        self.mech.desired_speed = 0.0
        from entities.map import GameMap
        place_on_map(self.mech, self.engine)
        self.engine.register_entity(self.mech)

    def test_move_event_moves_mech(self):
        """start_move_event + run_ticks should move the mech each second,
        matching what movement_periodic would have done."""
        self.mech.desired_speed = 64.5

        # Reference mech updated directly N times (what the periodic does)
        reference = Mech.create_test_mech()
        place_on_map(reference)
        reference.set_status(MechStatus.STARTED)
        reference.set_hex_position(50, 50)
        reference.facing = 90
        reference.desired_facing = 90
        reference.speed = 0.0
        reference.desired_speed = 64.5

        start_move_event(self.engine, self.mech)
        self.engine.run_ticks(20)

        for _ in range(20):
            update_movement(reference)

        self.assertGreater(self.mech.fx, hex_to_float(50, 50)[0])
        self.assertAlmostEqual(self.mech.fx, reference.fx, places=6)
        self.assertAlmostEqual(self.mech.fy, reference.fy, places=6)
        self.assertAlmostEqual(self.mech.speed, reference.speed, places=6)

    def test_chain_dies_when_stationary(self):
        """The event chain should die once speed, desired speed, and facing
        are all settled (stationary mech has NO movement event)."""
        from core.events import EventType

        self.mech.desired_speed = 64.5
        start_move_event(self.engine, self.mech)
        self.engine.run_ticks(10)

        self.assertTrue(self.engine.has_event(EventType.MOVE, self.mech))

        # Order a stop; decel is max_speed/20 per tick, so 30 ticks suffices
        self.mech.desired_speed = 0.0
        self.engine.run_ticks(30)

        self.assertEqual(self.mech.speed, 0.0)
        self.assertFalse(self.engine.has_event(EventType.MOVE, self.mech))

    def test_start_move_event_no_duplicates(self):
        """Calling start_move_event twice should schedule only one event."""
        from core.events import EventType

        self.mech.desired_speed = 64.5
        start_move_event(self.engine, self.mech)
        start_move_event(self.engine, self.mech)

        self.assertTrue(self.engine.events.has_event_type_data(EventType.MOVE, self.mech))
        self.assertEqual(self.engine.events.count_type(EventType.MOVE), 1)

    def test_restart_after_chain_dies(self):
        """Setting desired_speed after the chain died + start_move_event
        should resume movement."""
        from core.events import EventType

        # Let a movement chain run and die
        self.mech.desired_speed = 64.5
        start_move_event(self.engine, self.mech)
        self.engine.run_ticks(10)
        self.mech.desired_speed = 0.0
        self.engine.run_ticks(30)
        self.assertFalse(self.engine.has_event(EventType.MOVE, self.mech))

        old_fx = self.mech.fx

        # Order movement again and re-arm
        self.mech.desired_speed = 64.5
        start_move_event(self.engine, self.mech)
        self.engine.run_ticks(10)

        self.assertGreater(self.mech.speed, 0.0)
        self.assertGreater(self.mech.fx, old_fx)
        self.assertTrue(self.engine.has_event(EventType.MOVE, self.mech))


class TestLateralTranslation(unittest.TestCase):
    """move_mech translates along facing + lateral for ground units
    (mech.update.c:351-354); VTOL/SUB never apply lateral
    (mech.update.c:459-464)."""

    def make_mech(self, move_type=MoveType.BIPED, lateral=0):
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.set_hex_position(10, 10)
        mech.facing = 0
        mech.max_speed = 64.5
        mech.speed = 64.5
        mech.move_type = move_type
        mech.lateral = lateral
        place_on_map(mech)
        return mech

    def test_ground_unit_applies_lateral(self):
        """Facing north with a 300 (front-left) offset drifts west."""
        mech = self.make_mech(lateral=300)
        old_fx = mech.fx
        move_mech(mech)
        self.assertLess(mech.fx, old_fx)

    def test_quad_applies_lateral(self):
        mech = self.make_mech(move_type=MoveType.QUAD, lateral=60)
        old_fx = mech.fx
        move_mech(mech)
        self.assertGreater(mech.fx, old_fx)

    def test_vtol_ignores_lateral(self):
        """A VTOL facing north moves straight north whatever its
        lateral field says."""
        mech = self.make_mech(move_type=MoveType.VTOL, lateral=300)
        old_fx = mech.fx
        move_mech(mech)
        self.assertAlmostEqual(mech.fx, old_fx, places=6)

    def test_sub_ignores_lateral(self):
        mech = self.make_mech(move_type=MoveType.SUB, lateral=90)
        old_fx = mech.fx
        move_mech(mech)
        self.assertAlmostEqual(mech.fx, old_fx, places=6)


class TestQuadLateralSpeedPenalty(unittest.TestCase):
    """Quad with nonzero lateral: DECREASE_OLD(MP1)
    (mech.update.c:924-925, 1069-1078)."""

    def make_quad(self, lateral):
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.move_type = MoveType.QUAD
        mech.max_speed = 64.5
        mech.speed = 64.5
        mech.desired_speed = 64.5
        mech.lateral = lateral
        return mech

    def test_lateral_quad_slows(self):
        mech = self.make_quad(lateral=60)
        for _ in range(30):
            update_speed(mech)
        expected = 64.5 * (64.5 - MP1) / 64.5
        self.assertAlmostEqual(mech.speed, expected, places=2)

    def test_straight_quad_full_speed(self):
        mech = self.make_quad(lateral=0)
        for _ in range(30):
            update_speed(mech)
        self.assertAlmostEqual(mech.speed, 64.5, places=2)


class TestChargeHook(unittest.TestCase):
    """Charge trigger hook in update_movement (mech.update.c:361-367,
    228-235, 692-712; btconfig.h:175-176)."""

    def setUp(self):
        from entities.map import GameMap

        self.map = GameMap(30, 30)
        self.map._id = 100
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.set_hex_position(10, 10)
        self.map.add_mech(self.mech)
        self.mech.speed = self.mech.desired_speed = 1
        self.mech.charge_target = -1
        self.mech.charge_timer = 0
        self.mech.charge_distance = 0.0

        self.target = Mech.create_test_mech(name="Victim")
        self.target.set_hex_position(20, 10)
        self.target._id = 2
        self.map.add_mech(self.target)

    def test_constants(self):
        from physics.movement import CHARGE_DIST_TRIGGER, CHARGE_TIMER_LIMIT
        self.assertEqual(CHARGE_DIST_TRIGGER, 0.6)
        self.assertEqual(CHARGE_TIMER_LIMIT, 60)

    def test_distance_accrual(self):
        """charge_distance accrues the hexes moved this tick."""
        self.mech.charge_target = self.target._id
        self.map.btech_newcharge = 1
        self.mech.facing = 90
        self.mech.desired_facing = 90
        self.mech.speed = 64.5
        self.mech.desired_speed = 64.5

        result = update_movement(self.mech)

        # 64.5 KPH * MOVE_MOD / SCALEMAP = 0.1 hexes per tick
        self.assertAlmostEqual(self.mech.charge_distance,
                               abs(self.mech.speed) * MOVE_MOD / SCALEMAP,
                               places=6)
        self.assertEqual(self.mech.charge_timer, 1)
        self.assertEqual(result['messages'], [])

    def test_no_charge_no_bookkeeping(self):
        """charge_target == -1: the hook does not run."""
        self.mech.speed = 64.5
        self.mech.desired_speed = 64.5
        update_movement(self.mech)
        self.assertEqual(self.mech.charge_timer, 0)
        self.assertEqual(self.mech.charge_distance, 0.0)

    def test_timeout_under_newcharge(self):
        """Timer past CHARGE_TIMER_LIMIT resets the charge, but only
        under btech_newcharge (mech.update.c:228-235)."""
        from types import SimpleNamespace

        self.mech.charge_target = self.target._id
        self.mech.charge_timer = 60
        self.mech.engine = SimpleNamespace(btech_newcharge=1)

        update_movement(self.mech)
        self.assertEqual(self.mech.charge_timer, 61)  # C postincrement compares the old 60.
        update_movement(self.mech)

        self.assertIn("Charge timed out, charge reset.", self.mech.movement_messages)
        self.assertEqual(self.mech.charge_target, -1)
        self.assertEqual(self.mech.charge_timer, 0)
        self.assertEqual(self.mech.charge_distance, 0.0)

    def test_no_timeout_under_default_config(self):
        """btech_newcharge defaults to 0 (src/conf.c:91-143): no timeout."""
        self.mech.charge_target = self.target._id
        self.mech.charge_timer = 60

        result = update_movement(self.mech)

        self.assertEqual(result['messages'], [])
        self.assertEqual(self.mech.charge_target, self.target._id)
        self.assertEqual(self.mech.charge_timer, 60)

    def test_invalid_target_resets(self):
        self.mech.charge_target = 999999999   # no such unit

        result = update_movement(self.mech)

        self.assertIn("Invalid CHARGE target!", self.mech.movement_messages)
        self.assertEqual(self.mech.charge_target, -1)
        self.assertEqual(self.mech.charge_timer, 0)
        self.assertEqual(self.mech.charge_distance, 0.0)

    def test_trigger_at_close_range(self):
        """Range < CHARGE_DIST_TRIGGER (0.6) hands off to charge_mech
        and resets the charge state (mech.update.c:692-712)."""
        from unittest import mock

        self.target.set_hex_position(10, 10)   # same hex: range 0
        self.mech.charge_target = self.target._id

        with mock.patch('systems.physical.charge_mech',
                        create=True) as charge_mech:
            update_movement(self.mech)

        charge_mech.assert_called_once_with(self.mech, self.target)
        self.assertEqual(self.mech.charge_target, -1)
        self.assertEqual(self.mech.charge_timer, 0)
        self.assertEqual(self.mech.charge_distance, 0.0)

    def test_no_trigger_at_long_range(self):
        """No handoff while the target is out of trigger range."""
        from unittest import mock

        self.mech.charge_target = self.target._id   # 10 hexes away

        with mock.patch('systems.physical.charge_mech',
                        create=True) as charge_mech:
            update_movement(self.mech)

        charge_mech.assert_not_called()
        self.assertEqual(self.mech.charge_target, self.target._id)


if __name__ == '__main__':
    unittest.main()
