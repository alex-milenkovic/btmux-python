"""Fixture readiness and assertion precision required by movement examples."""
import unittest
from acceptance.movement import context, cargo


class TestAcceptanceFixtureHardening(unittest.TestCase):
    def test_numeric_comparison_rejects_the_tolerance_boundary_and_larger_errors(self):
        context.near(0, '0.0000009')
        for expected in ('0.000001', '-0.000001', '0.5', '-0.5'):
            with self.subTest(expected=expected), self.assertRaises(AssertionError):
                context.near(0, expected)

    def test_fresh_session_registers_its_unit_with_both_map_and_engine(self):
        w = {}
        context.fresh(w)
        self.assertEqual([w['unit']], w['engine'].get_entities())
        self.assertIn(w['unit'], w['map'].mechs_on_map)
        self.assertIs(w['engine'], w['unit']._engine)

    def test_default_terrain_setup_is_flat_and_updates_cached_elevation(self):
        w = {}
        context.fresh(w)
        context.set_hex(w, 'GRASSLAND', 5)
        context.set_hex(w, 'GRASSLAND')
        self.assertEqual(0, w['map'].elevation(w['unit'].x, w['unit'].y))
        self.assertEqual(0, w['unit'].elev)

    def test_invalid_fixture_values_retain_actionable_diagnostics(self):
        with self.assertRaises(ValueError) as error:
            context.bounded_integer('7', 1, 6, 'die')
        self.assertEqual('die must be from 1 through 6: 7', str(error.exception))
        w = {}
        context.fresh(w)
        with self.assertRaises(ValueError) as error:
            cargo.boosts(w, 'BAD_BOOST')
        self.assertEqual('BAD_BOOST', str(error.exception))

    def test_rejected_control_commands_raise_acceptance_failures(self):
        from acceptance.movement import controls
        from entities.mech import MechStatus as S
        for operation in ('speed', 'heading', 'pending', 'replace'):
            w = {}
            context.fresh(w)
            if operation == 'speed':
                controls.speed_text(w, '64.5', '1')
                w['unit'].set_status(S.PERFORMING_ACTION)
                action = lambda: controls.speed_request(w)
            elif operation == 'heading':
                w['unit'].set_status(S.PERFORMING_ACTION)
                action = lambda: controls.heading_lateral(w, '90', '-', '6')
            elif operation == 'pending':
                action = lambda: controls.pending_lateral(w, '0', 'INVALID')
            else:
                controls.pending_lateral(w, '0', 'fl')
                action = lambda: controls.replace_lateral(w, '2', 'INVALID', '8')
            with self.subTest(operation=operation), self.assertRaises(AssertionError):
                action()

    def test_wrong_eta_expectation_is_an_acceptance_failure(self):
        from acceptance.movement import controls
        w = {}
        context.fresh(w)
        controls.eta_target(w, '4', '43')
        controls.eta_request(w)
        with self.assertRaises(AssertionError):
            controls.eta_result(w, 'IMPOSSIBLE RESULT')

    def test_eta_fixture_sets_the_distance_promised_by_the_step(self):
        from acceptance.movement import controls
        from physics.hexmath import find_range, hex_to_float
        w = {}
        context.fresh(w)
        controls.eta_target(w, '4', '43')
        u = w['unit']
        x, y = hex_to_float(u.targ_x, u.targ_y)
        self.assertAlmostEqual(4, find_range(u.fx, u.fy, x, y))

    def test_vtol_fixture_supports_real_vertical_motion(self):
        from acceptance.movement import controls
        w = {}
        context.fresh(w)
        controls.vtol(w, '53.75', '32.25')
        controls.vertical_request(w, '43')
        controls.vertical_result(w, 'ACCEPTED', '43')
        context.advance(w, '3')
        self.assertEqual(1, w['unit'].z)
        self.assertAlmostEqual(64.5, w['unit'].fz)
    def test_callback_failure_cannot_pass_after_partial_state_changes(self):
        from core.events import EventType
        w = {}
        context.fresh(w)
        def broken(event):
            w['partial'] = True
            raise ValueError('controlled callback failure')
        w['engine'].schedule_event(1, EventType.CUSTOM, broken, data=w['unit'])
        with self.assertRaisesRegex(AssertionError, 'controlled callback failure'):
            context.advance(w, '1')
        self.assertTrue(w['partial'])
