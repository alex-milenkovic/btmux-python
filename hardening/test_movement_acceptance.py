"""Regression checks for acceptance blind spots found during hardening."""
import unittest

from acceptance.movement.context import fresh
from acceptance.movement.controls import heading_lateral
from acceptance.movement.modes import hull_workflow, quad
from acceptance.movement import ice
from acceptance.movement.context import set_hex


class TestMovementAcceptance(unittest.TestCase):
    def test_invalid_lateral_cannot_pass_by_retaining_original_offset(self):
        world = {}
        fresh(world)
        with self.assertRaises(AssertionError):
            heading_lateral(world, '360', 'x', '6')

    def test_existing_lateral_request_keeps_the_valid_no_change_feedback(self):
        world = {}
        fresh(world)
        heading_lateral(world, '360', '-', '6')
        self.assertEqual(world['unit'].desired_facing, 0)
        self.assertEqual(world['unit'].lateral, 0)

    def test_unknown_hulldown_workflow_is_not_interpreted_as_lowering(self):
        for name in ('lOWER', 'LOWERxSHUTDOWN', 'RAISE_UNKNOWN'):
            world = {}
            fresh(world)
            quad(world, '64.5')
            with self.subTest(workflow=name), self.assertRaises(ValueError):
                hull_workflow(world, name, '10')

    def test_unknown_terrain_is_a_fixture_validation_failure(self):
        world = {}
        fresh(world)
        with self.assertRaises(ValueError):
            set_hex(world, 'iCE')

    def test_impossible_neighbor_count_cannot_be_silently_clipped(self):
        world = {}
        fresh(world)
        with self.assertRaises(ValueError):
            ice.candidate_neighbors(world, 'WATER', '9', 'waterlike')

    def test_ice_random_fixtures_reject_impossible_draws(self):
        for operation, draw, die in (('growth', '0', '6'), ('growth', '1', '8'),
                                      ('melting', '1', '5'), ('growth', '101', '6')):
            world = {}
            fresh(world)
            ice.candidate_neighbors(world, 'WATER' if operation == 'growth' else 'ICE', '0',
                                    'waterlike' if operation == 'growth' else 'ICE')
            with self.subTest(operation=operation, draw=draw, die=die), self.assertRaises(ValueError):
                ice.ice_random(world, '100', draw, die)
                ice.evolve(world, operation)

    def test_triangle_uses_its_declared_percentage_draw(self):
        world = {}
        fresh(world)
        ice.triangle(world)
        ice.triangle_dice(world, '50', '51', '3', '2', '2')
        ice.evolve(world, 'growth')
        self.assertEqual(world['count'], 0)

    def test_surface_expected_terrain_is_validated(self):
        from acceptance.movement.surfaces import surface_result, surface_target, chance_result
        world = {}
        fresh(world)
        surface_target(world, 'ICE', '2', 'False')
        with self.assertRaises(ValueError):
            surface_result(world, 'iCE', '2')
        world['dropped'] = False
        with self.assertRaises(ValueError):
            chance_result(world, 'iCE', 'False')

    def test_surface_and_fall_dice_reject_impossible_fixture_values(self):
        from acceptance.movement.surfaces import chance
        from acceptance.movement.settling import fall
        for action in (lambda w: chance(w, '7'), lambda w: fall(w, '1', '0')):
            world = {}
            fresh(world)
            with self.assertRaises(ValueError):
                action(world)

    def test_orbital_pilot_and_interception_rolls_validate_two_dice(self):
        from acceptance.movement.orbital import orbit_setup, touchdown_terrain, interception
        for action in (lambda w: orbit_setup(w, '50', '20', '13'),
                       lambda w: touchdown_terrain(w, 'GRASSLAND', '11', '1'),
                       lambda w: interception(w, '5', '13')):
            world = {}
            fresh(world)
            with self.assertRaises(ValueError):
                action(world)
