"""Named simulation dice preserve normal gameplay outside their context."""
import unittest
from unittest.mock import Mock, patch
from core.randomness import draw, use_source


class TestSimulationDice(unittest.TestCase):
    def test_nested_context_restores_outer_source_then_normal_randomness(self):
        normal = Mock(return_value=6)
        with use_source(lambda name, lo, hi, fallback: 3):
            self.assertEqual(draw('ice_d6', 1, 6, normal), 3)
            with use_source(lambda name, lo, hi, fallback: 1):
                self.assertEqual(draw('ice_d6', 1, 6, normal), 1)
            self.assertEqual(draw('ice_d6', 1, 6, normal), 3)
        normal.assert_not_called()
        self.assertEqual(draw('ice_d6', 1, 6, normal), 6)
        normal.assert_called_once_with()

    def test_failed_simulation_does_not_leave_dice_installed(self):
        def exhausted(*args):
            raise ValueError('exhausted')
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            with use_source(exhausted):
                draw('pilot_rolls', 2, 12, lambda: 7)
        self.assertEqual(draw('pilot_rolls', 2, 12, lambda: 7), 7)

    def test_real_piloting_compares_supplied_dice_to_actual_target(self):
        from entities.mech import Mech, MechStatus
        from entities.pilot import Pilot
        from systems.piloting import make_piloting_roll
        unit = Mech(pilot=Pilot(piloting=5))
        unit.set_status(MechStatus.STARTED)
        with use_source(lambda name, lo, hi, fallback: 6):
            result = make_piloting_roll(unit, 2)
        self.assertEqual((result.roll, result.target, result.success), (6, 7, False))
        with patch('systems.piloting.random.randint', return_value=6):
            result = make_piloting_roll(unit, 2)
        self.assertEqual((result.roll, result.target, result.success), (12, 7, True))
