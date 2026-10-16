"""
Tests for the heat system.

These tests cover:
- Heat constants
- Movement heat generation
- Environment heat generation
- Heat dissipation
- Heat update calculations
- Overheat effects (shutdown, ammo explosion, pilot damage)
- Game loop integration
"""

import unittest
import random
from unittest.mock import patch, MagicMock

from systems.heat import (
    # Constants
    HEAT_TICK,
    TURN,
    HEAT_WALKING,
    HEAT_RUNNING,
    HEAT_JUMP_MINIMUM,
    HEAT_FIRE_HEX,
    HEAT_LEVEL_GREEN,
    HEAT_LEVEL_YELLOW,
    KPH_PER_MP,
    MP_PER_KPH,
    SHUTDOWN_THRESHOLDS,
    AMMO_EXPLOSION_THRESHOLDS,
    INFERNO_SINK_PENALTY,
    MAX_LEG_SINKS_BONUS,
    # Data structures
    HeatResult,
    StartupResult,
    AmmoBin,
    # Utility functions
    roll_2d6,
    get_heat_indicator,
    is_running,
    # Heat calculation functions
    calculate_movement_heat,
    calculate_environment_heat,
    calculate_engine_heat,
    calculate_plus_heat,
    calculate_minus_heat,
    decay_weapon_heat,
    update_heat,
    # Overheat functions
    check_ammo_explosion,
    check_shutdown,
    check_pilot_damage,
    check_overheat,
    apply_shutdown,
    full_heat_update,
    # Startup functions
    can_startup,
    attempt_startup,
    # Ammo explosion functions
    find_ammo_bins,
    find_destructive_ammo,
    trigger_heat_ammo_explosion,
    has_inferno_ammo,
    # Game loop integration
    heat_periodic,
    register_heat_system,
)
from entities.mech import Mech, MechStatus, MoveType, UnitType, CritStatus, Specials


class TestHeatConstants(unittest.TestCase):
    """Test heat system constants."""

    def test_heat_tick(self):
        """HEAT_TICK should be 2 (from btconfig.h)."""
        self.assertEqual(HEAT_TICK, 2)

    def test_turn(self):
        """TURN should be 30 seconds (from mech.h)."""
        self.assertEqual(TURN, 30)

    def test_movement_heat_values(self):
        """Movement heat values should match BTMux."""
        self.assertEqual(HEAT_WALKING, 1.0)
        self.assertEqual(HEAT_RUNNING, 2.0)
        self.assertEqual(HEAT_JUMP_MINIMUM, 3.0)

    def test_environment_heat(self):
        """Fire hex should generate 5 heat."""
        self.assertEqual(HEAT_FIRE_HEX, 5.0)

    def test_heat_level_thresholds(self):
        """Heat indicator thresholds should be correct."""
        self.assertEqual(HEAT_LEVEL_GREEN, 14.0)
        self.assertEqual(HEAT_LEVEL_YELLOW, 19.0)

    def test_shutdown_thresholds(self):
        """Shutdown thresholds should match BTMux."""
        self.assertEqual(SHUTDOWN_THRESHOLDS[14], 4)  # Avoid on 4+
        self.assertEqual(SHUTDOWN_THRESHOLDS[18], 6)  # Avoid on 6+
        self.assertEqual(SHUTDOWN_THRESHOLDS[22], 8)  # Avoid on 8+
        self.assertEqual(SHUTDOWN_THRESHOLDS[26], 10) # Avoid on 10+
        self.assertEqual(SHUTDOWN_THRESHOLDS[30], 99) # Automatic


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_roll_2d6_range(self):
        """roll_2d6 should return values in 2-12 range."""
        for _ in range(100):
            roll = roll_2d6()
            self.assertGreaterEqual(roll, 2)
            self.assertLessEqual(roll, 12)

    def test_get_heat_indicator_green(self):
        """Heat below 14 should be green."""
        self.assertEqual(get_heat_indicator(0.0), "green")
        self.assertEqual(get_heat_indicator(10.0), "green")
        self.assertEqual(get_heat_indicator(13.9), "green")

    def test_get_heat_indicator_yellow(self):
        """Heat 14-18 should be yellow."""
        self.assertEqual(get_heat_indicator(14.0), "yellow")
        self.assertEqual(get_heat_indicator(16.0), "yellow")
        self.assertEqual(get_heat_indicator(18.9), "yellow")

    def test_get_heat_indicator_red(self):
        """Heat 19+ should be red."""
        self.assertEqual(get_heat_indicator(19.0), "red")
        self.assertEqual(get_heat_indicator(25.0), "red")
        self.assertEqual(get_heat_indicator(50.0), "red")

    def test_is_running_true(self):
        """Speed over 2/3 max + buffer is running."""
        max_speed = 64.5
        walk_speed = 2.0 * max_speed / 3.0 + 0.1  # ~43.1
        self.assertTrue(is_running(45.0, max_speed))
        self.assertTrue(is_running(64.0, max_speed))

    def test_is_running_false(self):
        """Speed at or below 2/3 max + buffer is not running."""
        max_speed = 64.5
        self.assertFalse(is_running(0.0, max_speed))
        self.assertFalse(is_running(30.0, max_speed))
        self.assertFalse(is_running(42.0, max_speed))


class TestMovementHeat(unittest.TestCase):
    """Test movement heat calculation."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_stationary_no_heat(self):
        """Stationary mech generates no movement heat."""
        self.mech.speed = 0.0
        heat = calculate_movement_heat(self.mech)
        self.assertEqual(heat, 0.0)

    def test_walking_heat(self):
        """Walking generates 1 heat."""
        self.mech.speed = 30.0  # Below 2/3 of 64.5
        self.mech.desired_speed = 30.0
        heat = calculate_movement_heat(self.mech)
        self.assertEqual(heat, HEAT_WALKING)

    def test_running_heat(self):
        """Running generates 2 heat."""
        self.mech.speed = 60.0  # Above 2/3 of 64.5
        self.mech.desired_speed = 60.0
        heat = calculate_movement_heat(self.mech)
        self.assertEqual(heat, HEAT_RUNNING)

    def test_jumping_minimum_heat(self):
        """Jumping generates at least 3 heat."""
        self.mech.set_status(MechStatus.JUMPING)
        self.mech.jump_speed = 10.0  # ~1 MP
        heat = calculate_movement_heat(self.mech)
        self.assertEqual(heat, HEAT_JUMP_MINIMUM)

    def test_jumping_high_mp_heat(self):
        """High jump MP generates more heat."""
        self.mech.set_status(MechStatus.JUMPING)
        self.mech.jump_speed = 64.5  # ~6 MP
        heat = calculate_movement_heat(self.mech)
        expected = 64.5 * MP_PER_KPH
        self.assertGreater(heat, HEAT_JUMP_MINIMUM)
        self.assertAlmostEqual(heat, expected, places=1)


class TestEnvironmentHeat(unittest.TestCase):
    """Test environment heat calculation."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()

    def test_no_environment_heat_normally(self):
        """No environment heat without special conditions."""
        heat = calculate_environment_heat(self.mech)
        self.assertEqual(heat, 0.0)

    def test_fire_hex_heat(self):
        """Fire hex generates 5 heat for mechs."""
        from entities.map import FIRE
        self.mech.terrain = FIRE
        heat = calculate_environment_heat(self.mech)
        self.assertEqual(heat, HEAT_FIRE_HEX)

    def test_fire_hex_not_vehicle(self):
        """Fire hex doesn't affect non-mechs."""
        self.mech.unit_type = UnitType.VEH_GROUND
        from entities.map import FIRE
        self.mech.terrain = FIRE
        heat = calculate_environment_heat(self.mech)
        self.assertEqual(heat, 0.0)


class TestEngineHeat(unittest.TestCase):
    """Test engine damage heat."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()

    def test_no_engine_heat_normally(self):
        """No engine heat without damage."""
        heat = calculate_engine_heat(self.mech)
        self.assertEqual(heat, 0.0)

    def test_engine_heat_when_damaged(self):
        """Engine criticals add +5 heat each."""
        self.mech.set_status(MechStatus.STARTED)
        self.mech.engine_heat = 5  # 1 engine crit
        heat = calculate_engine_heat(self.mech)
        self.assertEqual(heat, 5.0)

    def test_engine_heat_multiple_crits(self):
        """Multiple engine criticals stack."""
        self.mech.set_status(MechStatus.STARTED)
        self.mech.engine_heat = 15  # 3 engine crits
        heat = calculate_engine_heat(self.mech)
        self.assertEqual(heat, 15.0)

    def test_engine_heat_not_started(self):
        """Engine heat only applies when started."""
        self.mech.engine_heat = 5
        heat = calculate_engine_heat(self.mech)
        self.assertEqual(heat, 0.0)


class TestPlusHeat(unittest.TestCase):
    """Test total heat generation."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_combined_heat_sources(self):
        """Plus heat combines all sources."""
        self.mech.speed = 60.0  # Running: +2
        self.mech.desired_speed = 60.0
        self.mech.engine_heat = 5  # Engine damage: +5
        self.mech.weap_heat = 7.0  # Weapons: +7

        heat = calculate_plus_heat(self.mech)
        # Running (2) + Engine (5) + Weapons (7) = 14
        self.assertEqual(heat, 14.0)

    def test_weapon_heat_only(self):
        """Stationary mech only has weapon heat."""
        self.mech.speed = 0.0
        self.mech.weap_heat = 12.0

        heat = calculate_plus_heat(self.mech)
        self.assertEqual(heat, 12.0)


class TestMinusHeat(unittest.TestCase):
    """Test heat dissipation calculation."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.num_sinks = 10

    def test_basic_dissipation(self):
        """Basic dissipation equals heat sink count."""
        heat = calculate_minus_heat(self.mech)
        self.assertEqual(heat, 10.0)

    def test_double_heat_sinks(self):
        """Double heat sinks dissipate 2 per sink."""
        self.mech.specials = Specials.DOUBLE_HEAT_TECH
        heat = calculate_minus_heat(self.mech)
        self.assertEqual(heat, 20.0)

    def test_clan_tech_double_sinks(self):
        """Clan tech has double heat sinks."""
        self.mech.specials = Specials.CLAN_TECH
        heat = calculate_minus_heat(self.mech)
        self.assertEqual(heat, 20.0)

    def test_shallow_water_bonus(self):
        """Shallow water gives limited bonus."""
        heat = calculate_minus_heat(self.mech, in_water=True, water_depth=-1)
        # C counts actual functional leg slots; this fixture has none.
        self.assertEqual(heat, 10.0)

    def test_deep_water_bonus(self):
        """Deep water gives bigger bonus."""
        heat = calculate_minus_heat(self.mech, in_water=True, water_depth=-2)
        # min(2 * 10, 6 + 10) = min(20, 16) = 16
        self.assertEqual(heat, 16.0)

    def test_fallen_in_water(self):
        """Fallen in water gets deep water bonus."""
        self.mech.set_status(MechStatus.FALLEN)
        heat = calculate_minus_heat(self.mech, in_water=True, water_depth=-1)
        # Fallen uses deep water formula even at depth -1
        self.assertEqual(heat, 16.0)

    def test_inferno_penalty(self):
        """Inferno gel reduces dissipation."""
        self.mech.set_crit_status(CritStatus.JELLIED)
        heat = calculate_minus_heat(self.mech)
        # 10 - 6 = 4
        self.assertEqual(heat, 4.0)

    def test_inferno_minimum_zero(self):
        """Inferno can't make dissipation negative."""
        self.mech.num_sinks = 5
        self.mech.set_crit_status(CritStatus.JELLIED)
        heat = calculate_minus_heat(self.mech)
        # max(0, 5 - 6) = 0
        self.assertEqual(heat, 0.0)


class TestUpdateHeat(unittest.TestCase):
    """Test heat level updates."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.num_sinks = 10
        self.mech.heat = 0.0

    def test_heat_increases(self):
        """Heat increases when plus > minus."""
        self.mech.speed = 60.0  # Running: +2 heat
        self.mech.desired_speed = 60.0
        self.mech.weap_heat = 15.0  # +15 heat
        # Total plus: 17, minus: 10, delta: +7

        result = update_heat(self.mech)
        self.assertEqual(result.plus_heat, 17.0)
        self.assertEqual(result.minus_heat, 10.0)
        self.assertEqual(result.delta_heat, 7.0)
        self.assertEqual(self.mech.heat, 7.0)

    def test_heat_decreases(self):
        """Heat decreases when plus < minus."""
        self.mech.heat = 15.0
        self.mech.speed = 0.0  # No movement heat
        self.mech.weap_heat = 5.0  # +5 heat
        # Total plus: 5, minus: 10, delta: -5

        result = update_heat(self.mech)
        self.assertEqual(result.delta_heat, -5.0)
        self.assertEqual(self.mech.heat, 0.0)  # C assigns max(0, plus-minus).

    def test_heat_minimum_zero(self):
        """Heat can't go below zero."""
        self.mech.heat = 5.0
        self.mech.speed = 0.0
        self.mech.weap_heat = 0.0
        # Plus: 0, minus: 10, would be -5

        result = update_heat(self.mech)
        self.assertEqual(self.mech.heat, 0.0)

    def test_heat_level_change_detected(self):
        """Heat level changes are detected."""
        self.mech.heat = 13.0  # Green
        self.mech.weap_heat = 25.0  # C assigns 25-10 = 15 (yellow).

        result = update_heat(self.mech)
        self.assertTrue(result.heat_level_changed)
        self.assertEqual(result.old_heat_level, "green")
        self.assertEqual(result.new_heat_level, "yellow")

    def test_non_mech_no_update(self):
        """Non-mechs don't get heat updates."""
        self.mech.unit_type = UnitType.VEH_GROUND
        self.mech.heat = 10.0
        self.mech.weap_heat = 20.0

        result = update_heat(self.mech)
        self.assertEqual(self.mech.heat, 10.0)


class TestWeaponHeatDecay(unittest.TestCase):
    """Test weapon heat decay."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()

    def test_weapon_heat_decays(self):
        """Weapon heat decays over time."""
        self.mech.weap_heat = 10.0
        decay_weapon_heat(self.mech, minus_heat=15.0, internal_heat=5.0)
        # Decay = (15 - 5) / 30 = 0.333
        self.assertLess(self.mech.weap_heat, 10.0)
        self.assertGreater(self.mech.weap_heat, 9.0)

    def test_weapon_heat_minimum_zero(self):
        """Weapon heat can't go negative."""
        self.mech.weap_heat = 0.1
        decay_weapon_heat(self.mech, minus_heat=20.0, internal_heat=0.0)
        self.assertEqual(self.mech.weap_heat, 0.0)


class TestShutdownCheck(unittest.TestCase):
    """Test shutdown checks."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_shutdown_boundaries_for_player_and_auto(self):
        from core.game_loop import GameEngine
        from core.randomness import use_source
        from entities.pilot import Pilot
        from entities.autopilot import Autopilot
        engine = GameEngine()
        engine.register_entity(self.mech)
        for actor in (Pilot(), Autopilot(100, self.mech)):
            self.mech.pilot = actor
            for heat in (0, 9.9, 10, 13, 13.9, 30, 30.1):
                with self.subTest(pilot=type(actor).__name__, heat=heat):
                    self.mech.heat = heat
                    before = (engine.randomness.total_rolls, engine.randomness.mt.words_consumed)
                    with use_source(lambda *args: self.fail('unexpected shutdown dice')):
                        result = engine.inject_command(self.mech, lambda: check_shutdown(self.mech))
                    self.assertEqual((heat >= 30, False), result)
                    self.assertEqual(before, (engine.randomness.total_rolls, engine.randomness.mt.words_consumed))
            for heat, target in ((14, 4), (17.9, 4), (18, 6), (21.9, 6),
                                 (22, 8), (25.9, 8), (26, 10), (29.9, 10)):
                for roll in (target - 1, target):
                    with self.subTest(pilot=type(actor).__name__, heat=heat, roll=roll):
                        self.mech.heat = heat
                        draws = []
                        def source(name, low, high, fallback):
                            draws.append(name)
                            return roll
                        before = engine.randomness.total_rolls
                        with use_source(source):
                            result = engine.inject_command(self.mech, lambda: check_shutdown(self.mech))
                        self.assertEqual((roll < target, roll >= target), result)
                        self.assertEqual(['shutdown_rolls'], draws)
                        self.assertEqual(before + 1, engine.randomness.total_rolls)

    @patch('systems.heat.roll_2d6')
    def test_shutdown_at_14_low_roll(self, mock_roll):
        """Heat 14+ with low roll causes shutdown."""
        mock_roll.return_value = 3  # Need 4+
        self.mech.heat = 14.0
        shutdown, avoided = check_shutdown(self.mech)
        self.assertTrue(shutdown)
        self.assertFalse(avoided)

    @patch('systems.heat.roll_2d6')
    def test_shutdown_at_14_high_roll(self, mock_roll):
        """Heat 14+ with high roll avoids shutdown."""
        mock_roll.return_value = 4  # Need 4+
        self.mech.heat = 14.0
        shutdown, avoided = check_shutdown(self.mech)
        self.assertFalse(shutdown)
        self.assertTrue(avoided)

    def test_automatic_shutdown_at_30(self):
        """Heat 30+ is automatic shutdown."""
        self.mech.heat = 30.0
        shutdown, avoided = check_shutdown(self.mech)
        self.assertTrue(shutdown)
        self.assertFalse(avoided)

    @patch('systems.heat.roll_2d6')
    def test_shutdown_thresholds(self, mock_roll):
        """Test various shutdown thresholds."""
        # 18+ heat needs 6+ to avoid
        mock_roll.return_value = 5
        self.mech.heat = 18.0
        shutdown, _ = check_shutdown(self.mech)
        self.assertTrue(shutdown)

        mock_roll.return_value = 6
        shutdown, _ = check_shutdown(self.mech)
        self.assertFalse(shutdown)

        # 22+ heat needs 8+ to avoid
        mock_roll.return_value = 7
        self.mech.heat = 22.0
        shutdown, _ = check_shutdown(self.mech)
        self.assertTrue(shutdown)

        # 26+ heat needs 10+ to avoid
        mock_roll.return_value = 9
        self.mech.heat = 26.0
        shutdown, _ = check_shutdown(self.mech)
        self.assertTrue(shutdown)


class TestAmmoExplosionCheck(unittest.TestCase):
    """Test ammo explosion checks."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()

    def test_no_explosion_below_19(self):
        """No explosion risk below 19 heat (without inferno)."""
        self.mech.heat = 18.0
        avoided = check_ammo_explosion(self.mech, has_inferno=False)
        self.assertTrue(avoided)

    @patch('systems.heat.roll_2d6')
    def test_explosion_at_19_low_roll(self, mock_roll):
        """Heat 19+ with low roll causes explosion."""
        mock_roll.return_value = 3  # Need 4+
        self.mech.heat = 19.0
        avoided = check_ammo_explosion(self.mech, has_inferno=False)
        self.assertFalse(avoided)

    @patch('systems.heat.roll_2d6')
    def test_explosion_at_19_high_roll(self, mock_roll):
        """Heat 19+ with high roll avoids explosion."""
        mock_roll.return_value = 4
        self.mech.heat = 19.0
        avoided = check_ammo_explosion(self.mech, has_inferno=False)
        self.assertTrue(avoided)

    def test_inferno_lower_threshold(self):
        """Inferno ammo triggers at lower heat."""
        self.mech.heat = 10.0
        # At 10 heat with inferno, need 4+ to avoid
        # Without mock, just verify it doesn't crash
        _ = check_ammo_explosion(self.mech, has_inferno=True)


class TestPilotDamage(unittest.TestCase):
    """Test pilot damage from heat."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()

    def test_no_damage_low_heat(self):
        """No pilot damage at low heat."""
        self.mech.heat = 14.0
        damage = check_pilot_damage(self.mech)
        self.assertEqual(damage, 0)

    def test_damage_at_15_with_life_support(self):
        """1 damage at 15+ heat with life support destroyed."""
        self.mech.heat = 15.0
        self.mech.set_crit_status(CritStatus.LIFE_SUPPORT_DESTROYED)
        damage = check_pilot_damage(self.mech)
        self.assertEqual(damage, 1)

    def test_damage_at_26_with_life_support(self):
        """2 damage at 26+ heat with life support destroyed."""
        self.mech.heat = 26.0
        self.mech.set_crit_status(CritStatus.LIFE_SUPPORT_DESTROYED)
        damage = check_pilot_damage(self.mech)
        self.assertEqual(damage, 2)


class TestApplyShutdown(unittest.TestCase):
    """Test shutdown application."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.speed = 30.0
        self.mech.desired_speed = 30.0

    def test_shutdown_clears_started(self):
        """Shutdown clears STARTED flag."""
        apply_shutdown(self.mech)
        self.assertFalse(self.mech.is_started)

    def test_shutdown_stops_movement(self):
        """Shutdown stops mech movement."""
        apply_shutdown(self.mech)
        self.assertEqual(self.mech.speed, 0.0)
        self.assertEqual(self.mech.desired_speed, 0.0)

    def test_shutdown_while_jumping(self):
        """Shutdown while jumping causes fall."""
        self.mech.set_status(MechStatus.JUMPING)
        apply_shutdown(self.mech)
        self.assertFalse(self.mech.is_jumping)
        self.assertTrue(self.mech.is_fallen)


class TestCheckOverheat(unittest.TestCase):
    """Test combined overheat check."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech._last_overheat_tick = 0

    def test_no_effects_below_10(self):
        """No overheat effects below 10 heat."""
        self.mech.heat = 9.0
        result = check_overheat(self.mech, tick=30)
        self.assertFalse(result.shutdown)
        self.assertFalse(result.ammo_explosion)
        self.assertEqual(result.pilot_damage, 0)

    def test_turn_timing(self):
        """Overheat checks only happen once per TURN."""
        self.mech.heat = 20.0
        self.mech._last_overheat_tick = 15

        # Not enough time passed (need 30 ticks)
        result = check_overheat(self.mech, tick=20)
        # No effects because not a full turn
        self.assertFalse(result.shutdown)

    def test_updates_last_check_tick(self):
        """Check updates the last overheat tick."""
        self.mech.heat = 15.0
        self.mech._last_overheat_tick = 0

        check_overheat(self.mech, tick=30)
        self.assertEqual(self.mech._last_overheat_tick, 30)


class TestFullHeatUpdate(unittest.TestCase):
    """Test full heat update function."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.num_sinks = 10

    def test_not_started_no_update(self):
        """Non-started mechs don't get heat updates."""
        self.mech.clear_status(MechStatus.STARTED)
        self.mech.heat = 10.0
        self.mech.weap_heat = 20.0

        result = full_heat_update(self.mech, tick=0)
        # Heat shouldn't change
        self.assertEqual(self.mech.heat, 10.0)

    def test_updates_heat_and_checks_overheat(self):
        """Full update handles heat and overheat."""
        self.mech.heat = 0.0
        self.mech.weap_heat = 5.0
        self.mech._last_overheat_tick = 0

        result = full_heat_update(self.mech, tick=30)
        # Heat should be updated
        self.assertIsNotNone(result.new_heat)


class TestGameLoopIntegration(unittest.TestCase):
    """Test game loop integration."""

    def test_register_heat_system(self):
        """Heat system can be registered with engine."""
        engine = MagicMock()
        register_heat_system(engine)
        engine.register_periodic.assert_called_once_with(
            "heat", HEAT_TICK, heat_periodic
        )

    def test_heat_periodic_updates_mechs(self):
        """Heat periodic updates all mechs."""
        mech1 = Mech.create_test_mech()
        mech1.set_status(MechStatus.STARTED)
        mech1.weap_heat = 15.0

        mech2 = Mech.create_test_mech()
        mech2.set_status(MechStatus.STARTED)
        mech2.weap_heat = 20.0

        engine = MagicMock()
        engine.tick = 0
        engine.get_entities.return_value = [mech1, mech2]

        heat_periodic(engine)

        # Both mechs should have heat updated
        self.assertGreater(mech1.heat, 0)
        self.assertGreater(mech2.heat, 0)


class TestHeatResult(unittest.TestCase):
    """Test HeatResult dataclass."""

    def test_default_values(self):
        """HeatResult has sensible defaults."""
        result = HeatResult()
        self.assertEqual(result.plus_heat, 0.0)
        self.assertEqual(result.minus_heat, 0.0)
        self.assertEqual(result.delta_heat, 0.0)
        self.assertFalse(result.shutdown)
        self.assertFalse(result.ammo_explosion)
        self.assertEqual(result.pilot_damage, 0)


class TestTSMHeat(unittest.TestCase):
    """Test Triple Strength Myomer heat interaction."""

    def setUp(self):
        """Create TSM mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.specials = Specials.TRIPLE_MYOMER_TECH

    def test_tsm_affects_running_threshold(self):
        """TSM changes the running speed threshold at high heat."""
        self.mech.heat = 9.0
        self.mech.speed = 50.0
        self.mech.desired_speed = 50.0

        # At high heat with TSM, the max speed is higher
        # so the same absolute speed might not be "running"
        heat = calculate_movement_heat(self.mech)
        # Just verify it works without crashing
        self.assertIn(heat, [HEAT_WALKING, HEAT_RUNNING])


class TestHeatWithGameLoop(unittest.TestCase):
    """Integration tests with game loop."""

    def test_heat_accumulates_over_time(self):
        """Heat accumulates correctly over multiple ticks."""
        from core.game_loop import GameEngine
        from systems.heat import register_heat_system

        engine = GameEngine()
        register_heat_system(engine)

        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.num_sinks = 10
        mech.heat = 0.0
        mech.weap_heat = 15.0  # Weapons generating 15 heat

        engine.register_entity(mech)

        # Run for a few heat ticks
        engine.run_ticks(4)  # 2 heat updates (every 2 ticks)

        # Heat should have accumulated
        # Plus: 15 weapon, Minus: 10 sinks = +5 per update
        # After 2 updates: ~10 heat (with weapon decay)
        self.assertGreater(mech.heat, 0)

    def test_heat_dissipates_to_zero(self):
        """Heat dissipates to zero when no sources."""
        from core.game_loop import GameEngine
        from systems.heat import register_heat_system

        engine = GameEngine()
        register_heat_system(engine)

        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.num_sinks = 10
        mech.heat = 20.0
        mech.weap_heat = 0.0
        mech.speed = 0.0

        engine.register_entity(mech)

        # Run for many ticks
        engine.run_ticks(10)

        # Heat should have decreased
        self.assertLess(mech.heat, 20.0)


# =============================================================================
# Phase 4: Enhanced Heat System Tests
# =============================================================================

class TestTemperatureEffects(unittest.TestCase):
    """Test map temperature effects on heat."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.num_sinks = 10

    def test_temperature_dissipation_modifier_cold(self):
        """Cold temperatures increase dissipation."""
        from systems.heat import (
            calculate_temperature_dissipation_modifier,
            TEMP_COLD_THRESHOLD,
            TEMP_COLD_BONUS,
        )
        # Cold (10C or below)
        modifier = calculate_temperature_dissipation_modifier(-31)
        self.assertEqual(modifier, 1)

    def test_temperature_dissipation_modifier_extreme_cold(self):
        """Extreme cold increases dissipation more."""
        from systems.heat import (
            calculate_temperature_dissipation_modifier,
            TEMP_EXTREME_COLD,
            TEMP_EXTREME_COLD_BONUS,
        )
        modifier = calculate_temperature_dissipation_modifier(-41)
        self.assertEqual(modifier, 2)

    def test_temperature_dissipation_modifier_hot(self):
        """Hot temperatures reduce dissipation."""
        from systems.heat import (
            calculate_temperature_dissipation_modifier,
            TEMP_HOT_THRESHOLD,
            TEMP_HOT_PENALTY,
        )
        modifier = calculate_temperature_dissipation_modifier(51)
        self.assertEqual(modifier, -1)

    def test_temperature_dissipation_modifier_normal(self):
        """Normal temperature has no modifier."""
        from systems.heat import (
            calculate_temperature_dissipation_modifier,
            TEMP_STANDARD,
        )
        modifier = calculate_temperature_dissipation_modifier(TEMP_STANDARD)
        self.assertEqual(modifier, 0.0)

    def test_temperature_heat_generation_extreme_hot(self):
        """Extreme heat generates additional heat."""
        from systems.heat import (
            calculate_temperature_heat_generation,
            TEMP_EXTREME_HOT,
            TEMP_EXTREME_HOT_HEAT,
        )
        heat = calculate_temperature_heat_generation(TEMP_EXTREME_HOT)
        self.assertEqual(heat, 0)  # C temperature changes dissipation only.

    def test_temperature_heat_generation_normal(self):
        """Normal temperature generates no additional heat."""
        from systems.heat import (
            calculate_temperature_heat_generation,
            TEMP_STANDARD,
        )
        heat = calculate_temperature_heat_generation(TEMP_STANDARD)
        self.assertEqual(heat, 0.0)

    def test_cold_weather_improves_dissipation(self):
        """Cold weather should increase heat dissipation."""
        from systems.heat import calculate_minus_heat, TEMP_COLD_THRESHOLD, TEMP_STANDARD

        normal_dissipation = calculate_minus_heat(self.mech, map_temperature=TEMP_STANDARD)
        cold_dissipation = calculate_minus_heat(self.mech, map_temperature=-31)

        self.assertGreater(cold_dissipation, normal_dissipation)

    def test_hot_weather_reduces_dissipation(self):
        """Hot weather should reduce heat dissipation."""
        from systems.heat import calculate_minus_heat, TEMP_HOT_THRESHOLD, TEMP_STANDARD

        normal_dissipation = calculate_minus_heat(self.mech, map_temperature=TEMP_STANDARD)
        hot_dissipation = calculate_minus_heat(self.mech, map_temperature=51)

        self.assertLess(hot_dissipation, normal_dissipation)

    def test_extreme_temperature_only_changes_dissipation(self):
        """C UpdateHeat adds no independent temperature generation."""
        from systems.heat import calculate_environment_heat, TEMP_EXTREME_HOT, TEMP_STANDARD

        normal_env = calculate_environment_heat(self.mech, map_temperature=TEMP_STANDARD)
        hot_env = calculate_environment_heat(self.mech, map_temperature=TEMP_EXTREME_HOT)

        self.assertEqual(hot_env, normal_env)


class TestStartupSystem(unittest.TestCase):
    """Test hot startup mechanics."""

    def setUp(self):
        """Create test mech."""
        self.mech = Mech.create_test_mech()
        # Not started by default

    def test_can_startup_normal(self):
        """Normal mech can startup."""
        from systems.heat import can_startup
        can_start, message = can_startup(self.mech)
        self.assertTrue(can_start)

    def test_cannot_startup_already_started(self):
        """Already-started mech cannot startup again."""
        from systems.heat import can_startup
        self.mech.set_status(MechStatus.STARTED)
        can_start, message = can_startup(self.mech)
        self.assertFalse(can_start)
        self.assertIn("already running", message)

    def test_cannot_startup_destroyed(self):
        """Destroyed mech cannot startup."""
        from systems.heat import can_startup
        self.mech.set_status(MechStatus.DESTROYED)
        can_start, message = can_startup(self.mech)
        self.assertFalse(can_start)
        self.assertIn("destroyed", message)

    def test_cannot_startup_high_heat(self):
        """Cannot startup if heat > 14."""
        from systems.heat import can_startup, STARTUP_HEAT_IMPOSSIBLE_THRESHOLD
        self.mech.heat = STARTUP_HEAT_IMPOSSIBLE_THRESHOLD + 1
        can_start, message = can_startup(self.mech)
        self.assertFalse(can_start)
        self.assertIn("Heat too high", message)

    def test_cold_startup_succeeds(self):
        """Cold startup (heat < 9) succeeds without check."""
        from systems.heat import attempt_startup
        self.mech.heat = 5.0
        result = attempt_startup(self.mech)
        self.assertTrue(result.success)
        self.assertFalse(result.piloting_required)
        self.assertTrue(self.mech.is_started)

    @patch('systems.heat.roll_2d6')
    def test_hot_startup_requires_check(self, mock_roll):
        """Hot startup (heat >= 9) requires piloting check."""
        from systems.heat import attempt_startup, STARTUP_HEAT_PILOTING_THRESHOLD
        mock_roll.return_value = 12  # High roll succeeds
        self.mech.heat = STARTUP_HEAT_PILOTING_THRESHOLD
        result = attempt_startup(self.mech)
        self.assertTrue(result.piloting_required)
        self.assertTrue(result.success)

    @patch('systems.heat.roll_2d6')
    def test_hot_startup_can_fail(self, mock_roll):
        """Hot startup can fail with low roll."""
        from systems.heat import attempt_startup, STARTUP_HEAT_PILOTING_THRESHOLD
        mock_roll.return_value = 3  # Low roll fails
        self.mech.heat = STARTUP_HEAT_PILOTING_THRESHOLD
        result = attempt_startup(self.mech)
        self.assertTrue(result.piloting_required)
        self.assertFalse(result.success)
        self.assertFalse(self.mech.is_started)

    def test_startup_blocked_high_heat(self):
        """Startup is blocked if heat > 14, not just check required."""
        from systems.heat import attempt_startup, STARTUP_HEAT_IMPOSSIBLE_THRESHOLD
        self.mech.heat = STARTUP_HEAT_IMPOSSIBLE_THRESHOLD + 1
        result = attempt_startup(self.mech)
        self.assertFalse(result.success)
        self.assertTrue(result.heat_blocked)


class TestAmmoBinFinding(unittest.TestCase):
    """Test ammo bin location functions."""

    def setUp(self):
        """Create test mech with ammo."""
        from entities.crittypes import i2ammo
        from entities.mech import Location, CriticalSlot, FireMode
        from entities.weapon import get_weapon

        self.mech = Mech.create_test_mech()

        # There is no flat "AMMO" crit type: ammo occupies the [193, 385) range
        # of the crit-type namespace, one entry per weapon
        # (mech.h:109 AMMO_BASE_INDEX, mech.h:157 I2Ammo).
        self.ac10 = get_weapon("IS.AC/10")

        # Add ammo bin to right torso (slot 0)
        self.mech.sections[Location.RTORSO].criticals[0].type = i2ammo(self.ac10.index)
        self.mech.sections[Location.RTORSO].criticals[0].data = 10  # 10 rounds
        self.mech.sections[Location.RTORSO].criticals[0].ammomode = 0  # Normal

    def test_find_ammo_bins_finds_ammo(self):
        """find_ammo_bins should locate ammo."""
        from systems.heat import find_ammo_bins
        bins = find_ammo_bins(self.mech)
        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0].ammo_count, 10)

    def test_find_ammo_bins_reads_weapon_damage(self):
        """Bin damage comes from the owning weapon, not a hardcoded 1.

        Reference: crit.c:1698-1699 - weapindx = Ammo2WeaponI(critType);
        damage = critData * MechWeapons[weapindx].damage
        """
        from systems.heat import find_ammo_bins
        bins = find_ammo_bins(self.mech)
        self.assertEqual(bins[0].weapon_damage, self.ac10.damage)
        self.assertEqual(bins[0].missiles_per_shot, 1)  # Ballistic, not missile

    def test_find_ammo_bins_missile_salvo(self):
        """Missile bins carry the full salvo multiplier.

        Reference: crit.c:1700-1704 - damage *= MissileHitTable[].
        num_missiles[10] (the roll-12 column, i.e. rack size)
        """
        from entities.crittypes import i2ammo
        from entities.mech import Location
        from entities.weapon import get_weapon
        from systems.heat import find_ammo_bins

        srm6 = get_weapon("IS.SRM-6")
        self.mech.sections[Location.LTORSO].criticals[0].type = i2ammo(srm6.index)
        self.mech.sections[Location.LTORSO].criticals[0].data = 15

        bins = [b for b in find_ammo_bins(self.mech) if b.location == Location.LTORSO]
        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0].weapon_damage, srm6.damage)
        self.assertEqual(bins[0].missiles_per_shot, 6)

    def test_find_ammo_bins_retains_empty_but_selection_skips_it(self):
        """Catalog enumeration retains empty bins; only positive damage can win."""
        from entities.crittypes import i2ammo
        from systems.heat import find_ammo_bins
        from entities.mech import Location

        # Add empty ammo bin
        self.mech.sections[Location.LTORSO].criticals[0].type = i2ammo(self.ac10.index)
        self.mech.sections[Location.LTORSO].criticals[0].data = 0  # Empty

        bins = find_ammo_bins(self.mech)
        self.assertEqual(len(bins), 2)
        from systems.heat import find_destructive_ammo
        self.assertGreater(find_destructive_ammo(self.mech).ammo_count, 0)

    def test_find_ammo_bins_skips_destroyed(self):
        """find_ammo_bins skips destroyed slots."""
        from systems.heat import find_ammo_bins
        from entities.mech import Location, FireMode

        # Destroy the ammo bin
        self.mech.sections[Location.RTORSO].criticals[0].firemode |= FireMode.DESTROYED_MODE

        bins = find_ammo_bins(self.mech)
        self.assertEqual(len(bins), 0)

    def test_find_destructive_ammo(self):
        """find_destructive_ammo returns a valid bin."""
        from systems.heat import find_destructive_ammo
        bin = find_destructive_ammo(self.mech)
        self.assertIsNotNone(bin)
        self.assertEqual(bin.ammo_count, 10)

    def test_find_destructive_ammo_no_ammo(self):
        """find_destructive_ammo returns None if no ammo."""
        from systems.heat import find_destructive_ammo
        from entities.mech import Location

        # Clear the ammo
        self.mech.sections[Location.RTORSO].criticals[0].data = 0

        bin = find_destructive_ammo(self.mech)
        self.assertIsNone(bin)

    def test_find_random_excludes_gauss(self):
        """find_destructive_ammo excludes gauss ammo.

        Gauss-ness is a property of the weapon, not an ammomode bit: the C
        tests MechWeapons[weapindx].special & (GAUSS | NOBOOM)
        (crit.c:1705-1709), so the bin has to belong to a Gauss weapon.  The
        old 0x02 ammomode flag was a port-side invention with no C analogue -
        the real ammomode bits are mech.h:636-666 (0x02 is ARTEMIS_MODE).
        """
        from entities.crittypes import i2ammo
        from entities.mech import Location
        from entities.weapon import get_weapon
        from systems.heat import find_destructive_ammo

        gauss = get_weapon("IS.GaussRifle")
        self.mech.sections[Location.RTORSO].criticals[0].type = i2ammo(gauss.index)

        bin = find_destructive_ammo(self.mech)
        self.assertIsNone(bin)  # Gauss doesn't explode from heat

    def test_noboom_ammo_still_cooks_off(self):
        """NOBOOM ammo DOES explode from heat - only GAUSS is exempt.

        Reference: mech.utils.c:1547-1548 - FindDestructiveAmmo `continue`s on
        `MechWeapons[weapindx].special & GAUSS` only.  The GAUSS|NOBOOM test is
        the critical-hit path's (crit.c:1705-1709), not the cook-off's.
        IS.PlasmaRifle is the NOBOOM entry (weapons.h:342-343).
        """
        from entities.crittypes import i2ammo
        from entities.mech import Location
        from entities.weapon import WeaponFlags, get_weapon
        from systems.heat import find_ammo_bins, find_destructive_ammo

        plasma = get_weapon("IS.PlasmaRifle")
        self.assertTrue(plasma.special & WeaponFlags.NOBOOM)
        self.mech.sections[Location.RTORSO].criticals[0].type = i2ammo(plasma.index)

        bins = find_ammo_bins(self.mech)
        self.assertEqual(len(bins), 1)
        self.assertFalse(bins[0].is_gauss)
        self.assertEqual(bins[0].weapon_damage, plasma.damage)
        self.assertIsNotNone(find_destructive_ammo(self.mech))


class TestHeatTriggeredExplosion(unittest.TestCase):
    """Test heat-triggered ammo explosion."""

    def setUp(self):
        """Create test mech with ammo."""
        from entities.crittypes import i2ammo
        from entities.mech import Location
        from entities.weapon import get_weapon

        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

        # Add ammo bin to right torso (ammo type = I2Ammo(weapon index),
        # mech.h:157)
        self.mech.sections[Location.RTORSO].criticals[0].type = i2ammo(
            get_weapon("IS.AC/10").index)
        self.mech.sections[Location.RTORSO].criticals[0].data = 10

    def test_trigger_explosion_destroys_bin(self):
        """trigger_heat_ammo_explosion destroys the bin."""
        from systems.heat import trigger_heat_ammo_explosion
        from entities.mech import Location, FireMode

        result = trigger_heat_ammo_explosion(self.mech)

        self.assertIsNotNone(result)
        # Check bin is destroyed
        crit = self.mech.sections[Location.RTORSO].criticals[0]
        self.assertTrue(crit.firemode & FireMode.DESTROYED_MODE)
        self.assertEqual(crit.data, 10)  # DestroyPart preserves bin data.

    def test_trigger_explosion_returns_result(self):
        """trigger_heat_ammo_explosion returns explosion result."""
        from systems.heat import trigger_heat_ammo_explosion

        result = trigger_heat_ammo_explosion(self.mech)

        self.assertIsNotNone(result)
        self.assertIsNotNone(result.message)

    def test_trigger_explosion_no_ammo(self):
        """trigger_heat_ammo_explosion returns None if no ammo."""
        from systems.heat import trigger_heat_ammo_explosion
        from entities.mech import Location

        # Clear ammo
        self.mech.sections[Location.RTORSO].criticals[0].data = 0

        result = trigger_heat_ammo_explosion(self.mech)
        self.assertIsNone(result)


class TestEnhancedOverheatCheck(unittest.TestCase):
    """Test enhanced overheat checking with actual explosions."""

    def setUp(self):
        """Create test mech."""
        from entities.crittypes import i2ammo
        from entities.mech import Location
        from entities.weapon import get_weapon

        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech._last_overheat_tick = 0

        # Add ammo for explosion (ammo type = I2Ammo(weapon index), mech.h:157)
        self.mech.sections[Location.RTORSO].criticals[0].type = i2ammo(
            get_weapon("IS.AC/10").index)
        self.mech.sections[Location.RTORSO].criticals[0].data = 10

    @patch('systems.heat.roll_2d6')
    def test_overheat_triggers_explosion(self, mock_roll):
        """check_overheat triggers actual explosion when check fails."""
        from systems.heat import check_overheat

        mock_roll.return_value = 2  # Fail explosion check
        self.mech.heat = 19.0

        result = check_overheat(self.mech, tick=30)

        self.assertTrue(result.ammo_explosion)
        self.assertGreater(len(result.messages), 0)

    @patch('systems.heat.roll_2d6')
    def test_overheat_no_ammo_no_explosion(self, mock_roll):
        """check_overheat doesn't explode if no ammo."""
        from systems.heat import check_overheat
        from entities.mech import Location

        # Clear ammo
        self.mech.sections[Location.RTORSO].criticals[0].data = 0

        mock_roll.return_value = 2  # Would fail check
        self.mech.heat = 19.0

        result = check_overheat(self.mech, tick=30)

        # Roll fails but no ammo to explode
        self.assertFalse(result.ammo_explosion)


class TestStartupResult(unittest.TestCase):
    """Test StartupResult dataclass."""

    def test_default_values(self):
        """StartupResult has sensible defaults."""
        from systems.heat import StartupResult
        result = StartupResult()
        self.assertFalse(result.success)
        self.assertFalse(result.heat_blocked)
        self.assertFalse(result.piloting_required)


class TestEnhancedHeatResult(unittest.TestCase):
    """Test enhanced HeatResult fields."""

    def test_new_fields_exist(self):
        """HeatResult has new explosion fields."""
        result = HeatResult()
        self.assertEqual(result.ammo_explosion_damage, 0)
        self.assertEqual(result.ammo_explosion_location, -1)
        self.assertFalse(result.mech_destroyed)
        self.assertEqual(result.messages, [])


class TestJelliedDissipationWiring(unittest.TestCase):
    """Additive: the inferno burn (systems/missile.py) drives the existing
    JELLIED -6 dissipation consumer without any API change
    (mech.update.c:1449-1453 via calculate_minus_heat)."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.num_sinks = 10

    def test_inferno_burn_applies_minus_six_through_existing_api(self):
        """inferno_burn sets JELLIED; calculate_minus_heat keeps its
        signature and drops by INFERNO_SINK_PENALTY."""
        from core.game_loop import GameEngine
        from systems.missile import inferno_burn

        engine = GameEngine()
        self.assertEqual(calculate_minus_heat(self.mech), 10.0)
        inferno_burn(engine, self.mech, 5)
        self.assertEqual(calculate_minus_heat(self.mech), 4.0)

    def test_dissipation_restored_when_burn_ends(self):
        from core.game_loop import GameEngine
        from systems.missile import inferno_burn

        engine = GameEngine()
        inferno_burn(engine, self.mech, 5)
        engine.run_ticks(6)
        self.assertFalse(self.mech.has_crit_status(CritStatus.JELLIED))
        self.assertEqual(calculate_minus_heat(self.mech), 10.0)

    def test_jellied_penalty_stacks_with_water_bonus(self):
        """Deep water 16 sinks - 6 jelly = 10 (mech.update.c:1449-1453
        applies the -6 after the water bonus)."""
        self.mech.set_crit_status(CritStatus.JELLIED)
        heat = calculate_minus_heat(self.mech, in_water=True,
                                    water_depth=-2)
        self.assertEqual(heat, 10.0)


if __name__ == '__main__':
    unittest.main()
