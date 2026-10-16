from unittest.mock import patch
from tests.movement_fixture import MovementTestCase
from physics import orbital
from core.events import EventType


class OrbitalTests(MovementTestCase):

    def test_ground_drop_resolves_canonical_weight_without_fixture_mass(self):
        self.unit.measured_mass = None
        success, message = orbital.initiate_ood(self.engine, self.unit, '10 10 7')
        self.assertTrue(success, message)
        self.assertEqual(self.unit.rtons//5//1024+1,self.unit.cocoon)
        self.assertTrue(self.engine.has_event(EventType.OOD, self.unit))

    def test_descent_rearms_then_touches_down_once(self):
        with patch('systems.combat.roll_2d6', return_value=12):
            self.assertTrue(orbital.initiate_ood(self.engine, self.unit, '10 10 7')[0])
            self.engine.run_ticks(3)
            self.assertEqual((1, 11), (self.unit.z, self.unit.cocoon))
            self.engine.run_ticks(1)
        self.assertEqual((0, 0), (self.unit.z, self.unit.cocoon))
        self.assertFalse(self.engine.has_event(EventType.OOD, self.unit))

    def test_breached_cocoon_falls_with_triangular_impact(self):
        orbital.initiate_ood(self.engine, self.unit, '10 10 7')
        orbital.cocoon_damage(self.unit, self.unit, 11)
        self.engine.run_ticks(3)
        self.assertEqual(5, self.unit.z)
        self.engine.run_ticks(3)
        self.assertEqual(2, self.unit.z)
        self.engine.run_ticks(3)
        self.assertEqual((0, 10), (self.unit.z, self.unit.last_fall_levels))

    def test_jump_cocoon_is_nonzero_but_not_positive(self):
        self.unit.jump_mp = 1
        self.unit.jump_speed = 1 * 10.75
        orbital.initiate_ood(self.engine, self.unit, '10 10 20')
        orbital.cocoon_damage(self.unit, self.unit, 20)
        self.assertEqual(-1, self.unit.cocoon)
        self.assertTrue(self.engine.has_event(EventType.OOD, self.unit))
        self.assertFalse(self.engine.has_event(EventType.FALL, self.unit))

    def test_invalid_drop_input_does_not_schedule_an_event(self):
        for argument in ('10', 'a 10', '10 10 bad', '10 10 -0', '-1 10 5'):
            with self.subTest(argument=argument):
                self.assertFalse(orbital.initiate_ood(self.engine, self.unit, argument)[0])
                self.assertFalse(self.engine.has_event(EventType.OOD, self.unit))

    def test_fallen_rejection_keeps_the_source_relocation_side_effect(self):
        from entities.mech import MechStatus
        self.unit.set_status(MechStatus.FALLEN)
        self.assertFalse(orbital.initiate_ood(self.engine, self.unit, '4 5 7')[0])
        self.assertEqual((4, 5), (self.unit.x, self.unit.y))
        self.assertFalse(self.engine.has_event(EventType.OOD, self.unit))

    def test_combat_safe_touchdown_skips_roll_and_damage(self):
        from entities.mech import MechStatus
        self.unit.set_status(MechStatus.COMBAT_SAFE)
        orbital.initiate_ood(self.engine, self.unit, '10 10 1')
        with patch('systems.combat.roll_2d6') as roll:
            self.engine.run_ticks(1)
        roll.assert_not_called()
        self.assertEqual((0, 0), (self.unit.z, self.unit.cocoon))
        self.assertFalse(self.unit.is_fallen)
        self.assertFalse(self.engine.has_event(EventType.OOD, self.unit))

    def test_touchdown_xp_uses_the_first_margin_before_the_second_addition(self):
        self.unit.pilot.piloting = 5
        orbital.initiate_ood(self.engine, self.unit, '10 10 1')
        from core.randomness import use_source
        with use_source(lambda name,low,high,fallback: 6):
            self.engine.run_ticks(1)
        self.assertEqual(5, self.unit.last_ood_target)
        self.assertEqual(4, self.unit.orbital_pilot_xp)
        self.assertFalse(self.unit.is_fallen)

    def test_insufficient_touchdown_roll_keeps_double_margin_and_parachute_factor(self):
        from systems.piloting import PilotingResult
        for cocoon, expected_levels in ((1, 2), (11, 4), (-1, 20)):
            with self.subTest(cocoon=cocoon):
                self.setUp()
                self.unit.pilot.piloting = 5
                orbital.initiate_ood(self.engine, self.unit, '10 10 1')
                self.unit.cocoon = cocoon
                with patch('systems.combat.roll_2d6', return_value=4), patch(
                    'systems.piloting.make_piloting_roll', return_value=PilotingResult(success=True)
                ):
                    self.engine.run_ticks(1)
                self.assertEqual(expected_levels, self.unit.last_fall_levels)
                self.assertEqual(0, self.unit.cocoon)
                self.assertTrue(self.unit.is_fallen)

    def test_cocoon_depletion_at_ground_does_not_schedule_free_fall(self):
        orbital.initiate_ood(self.engine, self.unit, '10 10 0')
        orbital.cocoon_damage(self.unit, self.unit, 99)
        self.assertEqual(0, self.unit.cocoon)
        self.assertFalse(self.engine.has_event(EventType.FALL, self.unit))
        self.engine.run_ticks(1)
        self.assertFalse(self.engine.has_event(EventType.OOD, self.unit))
