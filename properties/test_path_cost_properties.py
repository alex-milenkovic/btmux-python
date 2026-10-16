"""Finite-domain properties, run separately from ordinary unit discovery.

Use itertools enumeration and unittest subtests for deterministic coverage and
concrete counterexamples without an external generator dependency. These check
relations and invariants; the focused unit/APS suites own exact terrain prices.
"""
import copy
from itertools import product
import unittest
from unittest.mock import patch

from entities import map as terrain
from physics.path_costs import (
    mech_tile_cost, hover_tank_tile_cost, tracked_tank_tile_cost,
)


COSTS = (mech_tile_cost, hover_tank_tile_cost, tracked_tank_tile_cost)
TERRAINS = (' ', '"', '`', '~', '?', '%', '^', '#', '@', '&', '>', ':',
            '=', '}', '/', '+', '-', '$')


def query_map(source, destination, source_height, destination_height):
    game_map = terrain.GameMap(2, 1)
    for x, code, height in ((0, source, source_height), (1, destination, destination_height)):
        game_map.set_terrain(x, 0, code)
        game_map.set_elevation(x, 0, height)
    return game_map


def costs(game_map, coordinates=(0, 0, 1, 0)):
    return tuple(function(game_map, *coordinates) for function in COSTS)


class TestPathCostProperties(unittest.TestCase):
    def test_all_terrain_height_pairs_preserve_state_and_obey_cost_bounds(self):
        for source, destination, z1, z2 in product(TERRAINS, TERRAINS, range(10), range(10)):
            with self.subTest(source=source, destination=destination, z1=z1, z2=z2):
                game_map = query_map(source, destination, z1, z2)
                occupant = object()  # Pricing must not inspect or replace occupants.
                game_map.mechs_on_map.append(occupant)
                before = copy.deepcopy({k: v for k, v in vars(game_map).items()
                                        if k != 'mechs_on_map'})
                result = costs(game_map)
                self.assertEqual(costs(game_map), result)
                self.assertEqual({k: v for k, v in vars(game_map).items()
                                  if k != 'mechs_on_map'}, before)
                self.assertEqual(game_map.mechs_on_map, [occupant])
                difference = abs(game_map.base_elevation(0, 0) - game_map.base_elevation(1, 0))
                for cost, maximum, climb_limit in zip(result, (5, 4, 4), (2, 1, 1)):
                    self.assertIs(type(cost), int)
                    self.assertTrue(0 <= cost <= maximum)
                    if difference > climb_limit:
                        self.assertEqual(cost, 0)
                if destination == terrain.WATER:
                    self.assertIn(result[1], (0, 1))
                    self.assertEqual(result[2], 0)
                    if z2:
                        self.assertEqual(result[0], 0)

    def test_source_terrain_is_irrelevant_when_signed_floor_is_unchanged(self):
        for source, destination, z1, z2 in product(TERRAINS, TERRAINS, range(10), range(10)):
            with self.subTest(source=source, destination=destination, z1=z1, z2=z2):
                game_map = query_map(source, destination, z1, z2)
                original = costs(game_map)
                equivalent = terrain.ICE if source in (terrain.WATER, terrain.ICE) else terrain.GRASSLAND
                game_map.set_terrain(0, 0, equivalent)
                self.assertEqual(costs(game_map), original)

    def test_common_height_translation_and_reversal_on_uniform_dry_terrain(self):
        dry = set(TERRAINS) - {terrain.WATER, terrain.ICE}
        for code, z1, z2 in product(sorted(dry), range(10), range(10)):
            original = costs(query_map(code, code, z1, z2))
            for shift in range(-min(z1, z2), 10 - max(z1, z2)):
                with self.subTest(terrain=code, z1=z1, z2=z2, shift=shift):
                    shifted = query_map(code, code, z1 + shift, z2 + shift)
                    self.assertEqual(costs(shifted), original)
                    self.assertEqual(costs(shifted, (1, 0, 0, 0)), original)

    def test_coordinate_guards_reject_without_cell_reads_on_rectangular_maps(self):
        for width, height in product(range(1, 5), repeat=2):
            game_map = terrain.GameMap(width, height)
            with patch.object(game_map, 'base_elevation', return_value=0) as floor, \
                    patch.object(game_map, 'rterrain', return_value=terrain.GRASSLAND) as real:
                for fx, fy, tx, ty in product(range(-1, width + 1), range(-1, height + 1),
                                             range(-1, width + 1), range(-1, height + 1)):
                    with self.subTest(size=(width, height), endpoints=(fx, fy, tx, ty)):
                        permitted = (0 <= fx < width and 0 <= fy < height
                                     and 0 <= tx < width and 0 <= ty < min(width, height))
                        floor.reset_mock()
                        real.reset_mock()
                        self.assertEqual(costs(game_map, (fx, fy, tx, ty)),
                                         (1, 1, 1) if permitted else (0, 0, 0))
                        if not permitted:
                            floor.assert_not_called()
                            real.assert_not_called()

    def test_relocation_and_unrelated_hexes_do_not_change_prices(self):
        for code, elevation in product(TERRAINS, range(10)):
            expected = costs(query_map(terrain.GRASSLAND, code, 0, elevation))
            for fx, fy, tx, ty in product(range(3), repeat=4):
                if (fx, fy) == (tx, ty):
                    continue
                with self.subTest(terrain=code, elevation=elevation, endpoints=(fx, fy, tx, ty)):
                    game_map = terrain.GameMap(3, 3)
                    for x, y in product(range(3), repeat=2):
                        game_map.set_terrain(x, y, terrain.HEAVY_FOREST)
                        game_map.set_elevation(x, y, 9)
                    game_map.set_terrain(fx, fy, terrain.GRASSLAND)
                    game_map.set_elevation(fx, fy, 0)
                    game_map.set_terrain(tx, ty, code)
                    game_map.set_elevation(tx, ty, elevation)
                    self.assertEqual(costs(game_map, (fx, fy, tx, ty)), expected)
