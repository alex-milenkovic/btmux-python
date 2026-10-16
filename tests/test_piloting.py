"""
Tests for the piloting skill system.

Tests cover:
- Piloting skill check mechanics
- Damage modifiers (gyro, hip, leg)
- Stagger damage accumulation
- Fall triggers
- Pilot injury system
"""

import unittest
from unittest.mock import patch

from entities.mech import Mech, MechStatus, CritStatus, Location, SectionConfig
from systems.piloting import (
    make_piloting_roll, check_for_fall, calculate_piloting_modifier,
    calculate_stagger_modifier, find_pilot_piloting,
    add_stagger_damage, clear_stagger, check_stagger,
    check_damage_fall_trigger, trigger_fall_from_critical,
    head_hit_mw_damage, handle_mw_conc, mech_recovery,
    on_damage_received, on_turn_end,
    DEFAULT_PILOTING, STAGGER_DAMAGE_THRESHOLD, MAX_PILOT_HITS,
    PILOTING_GYRO_DAMAGED, PILOTING_GYRO_DESTROYED,
    PILOTING_HIP_DAMAGED, PILOTING_LEG_DESTROYED,
    PilotingCheckReason,
)
from data.templates import get_template, create_mech_from_template


class TestPilotingModifiers(unittest.TestCase):
    """Test piloting modifier calculations."""

    def setUp(self):
        """Create a mech for testing."""
        template = get_template("TestMech")
        self.mech = create_mech_from_template(template, "PilotTest")
        self.mech.set_status(MechStatus.STARTED)

    def test_no_damage_no_modifier(self):
        """Test undamaged mech has no modifier."""
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, 0)

    def test_gyro_damaged_modifier(self):
        """Test damaged gyro adds +3."""
        self.mech.set_crit_status(CritStatus.GYRO_DAMAGED)
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, PILOTING_GYRO_DAMAGED)

    def test_gyro_destroyed_auto_fail(self):
        """Test destroyed gyro causes auto-fail modifier."""
        self.mech.set_crit_status(CritStatus.GYRO_DESTROYED)
        mod = calculate_piloting_modifier(self.mech)
        self.assertGreaterEqual(mod, PILOTING_GYRO_DESTROYED)

    def test_hip_damaged_modifier(self):
        """Test damaged hip adds +2."""
        self.mech.set_crit_status(CritStatus.HIP_DAMAGED)
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, 2)

    def test_hip_destroyed_modifier(self):
        """Test destroyed hip adds +4."""
        self.mech.set_crit_status(CritStatus.HIP_DESTROYED)
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, 4)

    def test_leg_destroyed_modifier(self):
        """Test destroyed leg adds +5."""
        self.mech.sections[Location.LLEG].config |= SectionConfig.SECTION_DESTROYED
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, PILOTING_LEG_DESTROYED)

    def test_both_legs_destroyed_modifier(self):
        """Test both legs destroyed adds +10."""
        self.mech.sections[Location.LLEG].config |= SectionConfig.SECTION_DESTROYED
        self.mech.sections[Location.RLEG].config |= SectionConfig.SECTION_DESTROYED
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, PILOTING_LEG_DESTROYED * 2)

    def test_combined_damage_modifier(self):
        """Test combined damage modifiers stack."""
        self.mech.set_crit_status(CritStatus.GYRO_DAMAGED)
        self.mech.set_crit_status(CritStatus.HIP_DAMAGED)
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, PILOTING_GYRO_DAMAGED + 2)

    def test_stagger_damage_modifier(self):
        """Test stagger damage adds modifier."""
        self.mech.stagger_damage = 40  # 2x threshold
        mod = calculate_piloting_modifier(self.mech)
        self.assertEqual(mod, 2)  # 40 / 20 = 2


class TestStaggerModifier(unittest.TestCase):
    """Test stagger modifier calculation."""

    def test_zero_stagger(self):
        """Test zero stagger gives no modifier."""
        self.assertEqual(calculate_stagger_modifier(0), 0)

    def test_below_threshold(self):
        """Test below threshold gives no modifier."""
        self.assertEqual(calculate_stagger_modifier(19), 0)

    def test_at_threshold(self):
        """Test at threshold gives +1."""
        self.assertEqual(calculate_stagger_modifier(20), 1)

    def test_double_threshold(self):
        """Test double threshold gives +2."""
        self.assertEqual(calculate_stagger_modifier(40), 2)

    def test_large_stagger(self):
        """Test large stagger scales correctly."""
        self.assertEqual(calculate_stagger_modifier(100), 5)


class TestPilotingRolls(unittest.TestCase):
    """Test piloting roll mechanics."""

    def setUp(self):
        """Create a mech for testing."""
        template = get_template("TestMech")
        self.mech = create_mech_from_template(template, "RollTest")
        self.mech.set_status(MechStatus.STARTED)

    def test_default_piloting_skill(self):
        """An explicitly seated template pilot supplies piloting 5."""
        skill = find_pilot_piloting(self.mech)
        self.assertEqual(skill, self.mech.pilot.piloting)

    @patch('systems.piloting.source_roll')
    def test_piloting_roll_success(self, mock_randint):
        """Test successful piloting roll."""
        mock_randint.return_value = 12  # Roll 12
        result = make_piloting_roll(self.mech)
        self.assertTrue(result.success)
        self.assertEqual(result.roll, 12)
        self.assertEqual(result.target, self.mech.pilot.piloting)

    @patch('systems.piloting.source_roll')
    def test_piloting_roll_failure(self, mock_randint):
        """Test failed piloting roll."""
        mock_randint.return_value = 2  # Roll 2
        result = make_piloting_roll(self.mech)
        self.assertFalse(result.success)
        self.assertEqual(result.roll, 2)

    @patch('systems.piloting.source_roll')
    def test_piloting_roll_with_modifier(self, mock_randint):
        """Test piloting roll with modifier."""
        mock_randint.return_value = 8  # Roll 8
        result = make_piloting_roll(self.mech, modifier=3)
        # Target = 5 + 3 = 8, roll 8, should succeed
        self.assertTrue(result.success)
        self.assertEqual(result.target, 8)

    @patch('systems.piloting.source_roll')
    def test_piloting_roll_exact_target(self, mock_randint):
        """Test piloting roll at exact target succeeds."""
        mock_randint.return_value = 5  # Source Roll returns the sum
        result = make_piloting_roll(self.mech)
        # Roll 5 >= target 5
        self.assertTrue(result.success)

    @patch('systems.piloting.source_roll', return_value=12)
    def test_piloting_roll_uses_stored_damage_modifier(self, roll):
        """MechPilotSkillRoll_BTH uses the stored critical modifier."""
        self.mech.pilot_skill_base = 8
        result = make_piloting_roll(self.mech)
        self.assertFalse(result.success)
        self.assertEqual(result.target, self.mech.pilot.piloting + 8)
        roll.assert_called_once()

    @patch('systems.piloting.source_roll')
    def test_check_for_fall_success(self, mock_randint):
        """Test successful check doesn't cause fall."""
        mock_randint.return_value = 12
        result = check_for_fall(self.mech)
        self.assertTrue(result.success)
        self.assertFalse(result.fell)
        self.assertFalse(self.mech.is_fallen)

    @patch('systems.piloting.source_roll')
    def test_check_for_fall_failure(self, mock_randint):
        """Test failed check causes fall."""
        mock_randint.return_value = 2
        result = check_for_fall(self.mech)
        self.assertFalse(result.success)
        self.assertTrue(result.fell)
        self.assertTrue(self.mech.is_fallen)


class TestStaggerSystem(unittest.TestCase):
    """Test stagger damage system."""

    def setUp(self):
        """Create a mech for testing."""
        template = get_template("TestMech")
        self.mech = create_mech_from_template(template, "StaggerTest")
        self.mech.set_status(MechStatus.STARTED)

    def test_add_stagger_below_threshold(self):
        """Test damage below threshold doesn't trigger."""
        needs_check = add_stagger_damage(self.mech, 15)
        self.assertFalse(needs_check)
        self.assertEqual(self.mech.stagger_damage, 0)

    def test_add_stagger_at_threshold(self):
        """Test damage at threshold triggers."""
        needs_check = add_stagger_damage(self.mech, 20)
        self.assertTrue(needs_check)
        self.assertEqual(self.mech.stagger_damage, 20)

    def test_add_stagger_accumulates(self):
        """Test stagger damage accumulates."""
        add_stagger_damage(self.mech, 25)
        add_stagger_damage(self.mech, 30)
        self.assertEqual(self.mech.stagger_damage, 55)

    def test_clear_stagger(self):
        """Test clearing stagger damage."""
        self.mech.stagger_damage = 50
        clear_stagger(self.mech)
        self.assertEqual(self.mech.stagger_damage, 0)

    @patch('systems.piloting.source_roll')
    def test_check_stagger_no_damage(self, mock_randint):
        """Test no check needed without stagger."""
        result = check_stagger(self.mech)
        self.assertIsNone(result)

    @patch('systems.piloting.source_roll')
    def test_check_stagger_with_damage(self, mock_randint):
        """Test check triggered with stagger."""
        mock_randint.return_value = 12
        self.mech.stagger_damage = 20
        result = check_stagger(self.mech)
        self.assertIsNotNone(result)
        self.assertEqual(result.reason, PilotingCheckReason.DAMAGE_TAKEN)


class TestFallTriggers(unittest.TestCase):
    """Test fall trigger conditions."""

    def setUp(self):
        """Create a mech for testing."""
        template = get_template("TestMech")
        self.mech = create_mech_from_template(template, "FallTriggerTest")
        self.mech.set_status(MechStatus.STARTED)

    @patch('systems.piloting.source_roll')
    def test_heavy_damage_triggers_check(self, mock_randint):
        """Test 20+ damage triggers piloting check."""
        mock_randint.return_value = 12  # Pass check
        result = check_damage_fall_trigger(self.mech, 25, Location.CTORSO)
        self.assertIsNotNone(result)
        self.assertEqual(result.reason, PilotingCheckReason.DAMAGE_TAKEN)

    @patch('systems.piloting.source_roll')
    def test_light_damage_no_trigger(self, mock_randint):
        """Test below threshold damage doesn't trigger."""
        result = check_damage_fall_trigger(self.mech, 15, Location.CTORSO)
        self.assertIsNone(result)

    @patch('systems.piloting.source_roll')
    def test_leg_destruction_triggers_check(self, mock_randint):
        """Test leg destruction triggers check with +2."""
        mock_randint.return_value = 12
        # Destroy the leg
        self.mech.sections[Location.LLEG].config |= SectionConfig.SECTION_DESTROYED
        result = check_damage_fall_trigger(self.mech, 5, Location.LLEG)
        self.assertIsNotNone(result)
        self.assertEqual(result.reason, PilotingCheckReason.LEG_DESTROYED)

    @patch('systems.piloting.source_roll')
    def test_gyro_critical_triggers_check(self, mock_randint):
        """Test gyro critical triggers piloting check."""
        mock_randint.return_value = 12
        result = trigger_fall_from_critical(self.mech, "GYRO")
        self.assertIsNotNone(result)
        self.assertEqual(result.reason, PilotingCheckReason.GYRO_DAMAGED)

    @patch('systems.piloting.source_roll')
    def test_hip_critical_triggers_check(self, mock_randint):
        """Test hip critical triggers piloting check."""
        mock_randint.return_value = 12
        result = trigger_fall_from_critical(self.mech, "HIP")
        self.assertIsNotNone(result)
        self.assertEqual(result.reason, PilotingCheckReason.HIP_DAMAGED)

    def test_other_critical_no_trigger(self):
        """Test other criticals don't trigger piloting check."""
        result = trigger_fall_from_critical(self.mech, "WEAPON")
        self.assertIsNone(result)


class TestPilotInjury(unittest.TestCase):
    """Exercise the current headhitmwdamage owner and non-IC hit counter."""

    def setUp(self):
        self.mech = create_mech_from_template(get_template("TestMech"), "PilotInjuryTest")
        self.mech.set_status(MechStatus.STARTED)
        self.mech.pilot_hits = 0
        roll = patch('systems.piloting.roll_skilled', return_value=12)
        roll.start()
        self.addCleanup(roll.stop)

    def test_damage_pilot_adds_hits(self):
        head_hit_mw_damage(self.mech, None, 1)
        self.assertEqual(self.mech.pilot_hits, 1)
        self.assertFalse(self.mech.is_destroyed)

    def test_damage_pilot_accumulates(self):
        head_hit_mw_damage(self.mech, None, 2)
        head_hit_mw_damage(self.mech, None, 3)
        self.assertEqual(self.mech.pilot_hits, 5)
        self.assertFalse(self.mech.is_destroyed)

    def test_pilot_death_at_max_hits(self):
        head_hit_mw_damage(self.mech, None, MAX_PILOT_HITS)
        self.assertEqual(self.mech.pilot_hits, MAX_PILOT_HITS)
        self.assertTrue(self.mech.is_destroyed)
        self.assertIsNone(self.mech.pilot)

    def test_pilot_death_beyond_max(self):
        self.mech.pilot_hits = 4
        head_hit_mw_damage(self.mech, None, 3)
        self.assertEqual(self.mech.pilot_hits, 7)
        self.assertTrue(self.mech.is_destroyed)
        self.assertIsNone(self.mech.pilot)


class TestConsciousness(unittest.TestCase):
    """handlemwconc uses [0,3,5,7,10,11], with the source index capped at 4."""

    def setUp(self):
        self.mech = create_mech_from_template(get_template("TestMech"), "ConsciousnessTest")
        self.mech.set_status(MechStatus.STARTED)
        self.mech.pilot_hits = 0

    @patch('systems.piloting.roll_skilled', return_value=12)
    def test_consciousness_check_pass(self, roll):
        self.assertTrue(handle_mw_conc(self.mech))
        self.assertFalse(self.mech.is_unconscious)
        roll.assert_called_once()

    @patch('systems.piloting.roll_skilled', return_value=2)
    def test_consciousness_check_fail(self, roll):
        self.mech.pilot_hits = 1  # one hit requires 3; no hits requires 0
        self.assertFalse(handle_mw_conc(self.mech))
        self.assertTrue(self.mech.is_unconscious)
        self.assertEqual(30, self.mech.uncon_recovery_countdown)

    @patch('systems.piloting.roll_skilled', return_value=6)
    def test_consciousness_harder_with_hits(self, roll):
        self.assertTrue(handle_mw_conc(self.mech))
        self.mech.pilot_hits = 3  # three hits requires 7
        self.assertFalse(handle_mw_conc(self.mech))
        self.assertTrue(self.mech.is_unconscious)
        self.assertEqual(2, roll.call_count)

    @patch('systems.piloting.roll_skilled', return_value=12)
    def test_pilot_recovery_success(self, roll):
        self.mech.set_status(MechStatus.UNCONSCIOUS)
        mech_recovery(self.mech)
        self.assertFalse(self.mech.is_unconscious)
        self.assertIn("The pilot regains consciousness!", self.mech.movement_messages)

    @patch('systems.piloting.roll_skilled', return_value=2)
    def test_pilot_recovery_failure(self, roll):
        self.mech.pilot_hits = 1
        self.mech.set_status(MechStatus.UNCONSCIOUS)
        mech_recovery(self.mech)
        self.assertTrue(self.mech.is_unconscious)
        self.assertEqual(30, self.mech.uncon_recovery_countdown)

    @patch('systems.piloting.roll_skilled')
    def test_pilot_recovery_not_unconscious(self, roll):
        mech_recovery(self.mech)
        self.assertFalse(self.mech.is_unconscious)
        roll.assert_not_called()


class TestCombatIntegration(unittest.TestCase):
    """Test integration with combat system."""

    def setUp(self):
        """Create a mech for testing."""
        template = get_template("TestMech")
        self.mech = create_mech_from_template(template, "CombatIntegration")
        self.mech.set_status(MechStatus.STARTED)

    @patch('systems.piloting.source_roll')
    def test_on_damage_received_heavy(self, mock_randint):
        """Test heavy damage triggers piloting check via callback."""
        mock_randint.return_value = 12
        results = on_damage_received(self.mech, 25, Location.CTORSO)
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0])

    def test_on_damage_received_light(self):
        """Test light damage doesn't trigger callback."""
        results = on_damage_received(self.mech, 10, Location.CTORSO)
        self.assertEqual(len(results), 0)

    def test_on_turn_end_clears_stagger(self):
        """Test end of turn clears stagger."""
        self.mech.stagger_damage = 50
        on_turn_end(self.mech)
        self.assertEqual(self.mech.stagger_damage, 0)


class TestPilotingCheckReason(unittest.TestCase):
    """Test piloting check reasons are tracked."""

    def setUp(self):
        """Create a mech for testing."""
        template = get_template("TestMech")
        self.mech = create_mech_from_template(template, "ReasonTest")
        self.mech.set_status(MechStatus.STARTED)

    @patch('systems.piloting.source_roll')
    def test_reason_tracked_in_result(self, mock_randint):
        """Test reason is included in result."""
        mock_randint.return_value = 12
        result = make_piloting_roll(
            self.mech,
            reason=PilotingCheckReason.JUMP_LANDING
        )
        self.assertEqual(result.reason, PilotingCheckReason.JUMP_LANDING)


if __name__ == '__main__':
    unittest.main()
