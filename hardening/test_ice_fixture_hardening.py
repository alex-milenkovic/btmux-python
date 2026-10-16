"""Controlled ice random sources and the declared geometry of APS fixtures."""
import unittest
from acceptance.movement import context, ice as steps
from entities.map import ICE, WATER, BRIDGE
from physics import ice


def ready():
    w = {}
    context.fresh(w)
    return w


class TestIceFixtureHardening(unittest.TestCase):
    def test_neighbor_count_and_die_upper_boundaries_have_clear_diagnostics(self):
        w = ready()
        with self.assertRaises(ValueError) as error:
            steps.candidate_neighbors(w, 'WATER', '7', 'waterlike')
        self.assertEqual('neighbor count must be from 0 through 6: 7', str(error.exception))
        for operation, die, maximum in (('growth', '7', 6), ('melting', '4', 3)):
            w = ready()
            steps.candidate_neighbors(w, 'WATER' if operation == 'growth' else 'ICE', '0', 'waterlike')
            steps.ice_random(w, '100', '1', die)
            with self.assertRaises(ValueError) as error:
                steps.evolve(w, operation)
            self.assertEqual(f'neighbor die must be from 1 through {maximum}: {die}', str(error.exception))

    def test_percentage_and_triangle_dice_validate_their_exact_domains(self):
        for action in (lambda w: steps.ice_random(w, '100', '101', '6'), lambda w: steps.triangle_dice(w, '100', '101', '1', '2', '3'), lambda w: steps.melt_square(w, '100', '101')):
            with self.assertRaises(ValueError) as error:
                action(ready())
            self.assertEqual('percentage draw must be from 1 through 100: 101', str(error.exception))
        w = ready()
        steps.triangle_dice(w, '100', '1', '1', '2', '3')
        self.assertEqual([1, 2, 3], w['neighbor_dice'])
        for dice in (('7', '2', '3'), ('1', '7', '3'), ('1', '2', '7')):
            with self.assertRaises(ValueError) as error:
                steps.triangle_dice(ready(), '100', '1', *dice)
            self.assertEqual('neighbor die must be from 1 through 6: 7', str(error.exception))

    def test_square_fixture_replaces_the_board_and_checks_remaining_ice(self):
        w = ready()
        steps.ice_square(w, '3', '1')
        self.assertEqual((3, 3), (w['map'].map_width, w['map'].map_height))
        steps.count_surfaces(w, '0', '9')
        steps.melt_square(w, '50', '51')
        steps.count_surfaces(w, '0', '9')
        self.assertEqual(0, w['count'])

    def test_generic_evolution_consumes_percentage_and_neighbor_draws(self):
        for percent, draw, die, expected in ((50, 51, 3, WATER), (50, 1, 2, WATER), (50, 1, 3, ICE)):
            w = ready()
            steps.isolated_water(w, '1')
            for xy in list(ice.neighbors(w['map'], 3, 3))[:2]:
                w['map'].set_terrain(*xy, BRIDGE)
            steps.ice_random(w, str(percent), str(draw), str(die))
            steps.evolve(w, 'growth')
            self.assertEqual(expected, w['map'].terrain(3, 3))
            self.assertEqual(int(expected == ICE), w['count'])

    def test_path_fixture_uses_the_stated_source_height(self):
        w = ready()
        steps.isolated_water(w, '1')
        steps.ice_path(w, '100', '1')
        self.assertEqual(1, w['map'].elevation(3, 2))
        self.assertEqual(3, w['cost'])

    def test_unknown_ice_operation_is_rejected(self):
        for operation in (None, 'MELTING', 'XXmeltingXX'):
            with self.subTest(operation=operation), self.assertRaises(ValueError) as error:
                steps.evolve(ready(), operation)
            self.assertEqual(f'Unknown ice operation: {operation}', str(error.exception))

    def test_unspecified_percentage_draw_preserves_the_one_percent_boundary(self):
        w = ready()
        steps.isolated_water(w, '1')
        steps.ice_path(w, '1', '0')
        self.assertEqual(ICE, w['map'].terrain(3, 3))
        self.assertEqual(1, w['count'])

    def test_generated_neighbor_draw_is_checked_against_the_actual_requested_range(self):
        w = ready()
        steps.triangle(w)
        w.update(percent=100, draw=1, neighbor_dice=[7, 2, 2])
        with self.assertRaises(ValueError) as error:
            steps.evolve(w, 'growth')
        self.assertEqual('ice random draw must be from 1 through 6: 7', str(error.exception))
