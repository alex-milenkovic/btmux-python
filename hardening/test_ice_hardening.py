"""C dice distributions, even-column adjacency and ice command behavior."""
import unittest
from unittest.mock import patch
from entities.map import GameMap, WATER, ICE, BRIDGE
from entities.mech import Mech, MechStatus
from physics import ice, movement


class TestIceHardening(unittest.TestCase):
    def test_even_interior_neighbors_match_c_hex_geometry(self):
        board = GameMap(5, 5)
        self.assertEqual(set(ice.neighbors(board, 2, 2)),
                         {(2, 1), (3, 2), (3, 3), (2, 3), (1, 3), (1, 2)})

    def test_growth_and_melt_use_the_c_neighbor_die_ranges(self):
        for source, count, action, bounds, value in ((BRIDGE, 2, ice.growable, (1, 6), 3),
                                                   (ICE, 6, ice.meltable, (1, 3), 1)):
            board = GameMap(5, 5)
            for xy in list(ice.neighbors(board, 2, 2))[:count]:
                board.set_terrain(*xy, source)
            with self.subTest(action=action.__name__), patch.object(ice.random, 'randint', return_value=value) as draw:
                self.assertTrue(action(board, 2, 2))
                draw.assert_called_once_with(*bounds)

    def test_percent_draws_cover_inclusive_one_through_one_hundred(self):
        board = GameMap(1, 1)
        board.set_terrain(0, 0, WATER)
        with patch.object(ice.random, 'randint', return_value=1) as draw:
            self.assertEqual(1, ice.ice_growth(board, 1))
            draw.assert_called_once_with(1, 100)

    def test_melting_delivers_ice_break_feedback_to_the_occupant(self):
        board = GameMap(1, 1)
        board.set_terrain(0, 0, ICE)
        board.set_elevation(0, 0, 2)
        unit = Mech.create_test_mech()
        unit.set_status(MechStatus.COMBAT_SAFE)
        board.add_mech(unit)
        messages = []
        with patch.object(movement, 'NOTIFY_HOOK', side_effect=lambda who, text: messages.append((who, text))), patch.object(ice.random, 'randint', return_value=1):
            self.assertEqual(1, ice.ice_melt(board, 100))
        self.assertIn((unit, 'goes swimming as ice breaks!'), messages)
        self.assertEqual(unit.last_fall_levels, 2)
        self.assertEqual(unit.terrain, WATER)

    def test_ice_commands_report_exact_counts_and_round_trip_surfaces(self):
        board = GameMap(1, 2)
        for y in range(2):
            board.set_terrain(0, y, WATER)
            board.set_elevation(0, y, 2)
        with patch.object(ice.random, 'randint', return_value=100):
            self.assertEqual((True, "No hexes 'iced'."), ice.map_addice(board, '-1'))
            self.assertEqual((True, "2 hexes 'iced'."), ice.map_addice(board, '+100'))
            self.assertEqual([ICE, ICE], [board.terrain(0, y) for y in range(2)])
            self.assertEqual((True, 'No hexes melted.'), ice.map_delice(board, '-1'))
            self.assertEqual((True, '2 hexes melted.'), ice.map_delice(board, '101'))
            self.assertEqual([WATER, WATER], [board.terrain(0, y) for y in range(2)])
            self.assertEqual([2, 2], [board.elevation(0, y) for y in range(2)])

    def test_ice_commands_distinguish_bad_arity_from_bad_numbers(self):
        board = GameMap(1, 1)
        for command in (ice.map_addice, ice.map_delice):
            for text, error in (('', 'Invalid arguments!'), ('1 2', 'Invalid arguments!'),
                                ('x', 'Invalid number!'), ('2.5', 'Invalid number!')):
                with self.subTest(command=command.__name__, argument=text):
                    self.assertEqual((False, error), command(board, text))
