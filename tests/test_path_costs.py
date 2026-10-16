"""Focused btspath.c behavior, independent of generated acceptance tests."""
import copy
import unittest
from unittest.mock import patch

from entities import map as terrain
from entities.map import GameMap
from entities.mech import Mech
from physics.path_costs import (
    mech_tile_cost, hover_tank_tile_cost, tracked_tank_tile_cost,
)


COSTS = (mech_tile_cost, hover_tank_tile_cost, tracked_tank_tile_cost)


class TestPathCosts(unittest.TestCase):
    def setUp(self):
        self.map = GameMap(4, 4)

    def hex(self, x, name, elevation):
        self.map.set_terrain(x, 0, getattr(terrain, name))
        self.map.set_elevation(x, 0, elevation)

    def check_costs(self, expected):
        for function, value in zip(COSTS, expected):
            with self.subTest(function=function.__name__):
                actual = function(self.map, 0, 0, 1, 0)
                self.assertIs(type(actual), int)
                self.assertEqual(actual, value)

    def test_destination_terrain_charges(self):
        for name, expected in (
            ('GRASSLAND', (1, 1, 1)), ('LIGHT_FOREST', (2, 2, 2)),
            ('ROUGH', (2, 2, 2)), ('HEAVY_FOREST', (3, 0, 0)),
            ('MOUNTAINS', (3, 3, 3)), ('WATER', (1, 1, 0)),
        ):
            with self.subTest(terrain=name):
                self.hex(1, name, 0)
                self.check_costs(expected)

    def test_default_terrain_does_not_inherit_movement_restrictions(self):
        for name in ('ROAD', 'BUILDING', 'WALL', 'DESERT', 'BRIDGE',
                     'SNOW', 'ICE', 'HIGHWATER', 'UNKNOWN_TERRAIN',
                     'FIRE', 'SMOKE', 'TFIRE'):
            with self.subTest(terrain=name):
                self.hex(1, name, 1)
                self.check_costs((2, 2, 2))

    def test_absolute_elevation_limits_in_both_directions(self):
        for source, destination, expected in (
            (0, 1, (2, 2, 2)), (1, 0, (2, 2, 2)),
            (0, 2, (3, 0, 0)), (2, 0, (3, 0, 0)),
            (0, 3, (0, 0, 0)), (3, 0, (0, 0, 0)),
        ):
            self.hex(0, 'GRASSLAND', source)
            self.hex(1, 'GRASSLAND', destination)
            self.check_costs(expected)

    def test_signed_depth_and_water_gate_order(self):
        for source, z1, destination, z2, expected in (
            ('GRASSLAND', 0, 'WATER', 1, (0, 1, 0)),
            ('GRASSLAND', 1, 'WATER', 1, (0, 0, 0)),
            ('WATER', 3, 'WATER', 2, (0, 1, 0)),
            ('WATER', 3, 'WATER', 1, (0, 0, 0)),
            ('WATER', 1, 'GRASSLAND', 1, (3, 0, 0)),
            ('GRASSLAND', 2, 'WATER', 0, (3, 0, 0)),
            ('GRASSLAND', 3, 'WATER', 0, (0, 0, 0)),
            ('GRASSLAND', 1, 'ICE', 1, (3, 0, 0)),
            ('ICE', 2, 'ICE', 1, (2, 2, 2)),
            ('ICE', 1, 'BRIDGE', 1, (3, 0, 0)),
            ('ICE', 1, 'HIGHWATER', 1, (3, 0, 0)),
        ):
            with self.subTest(source=source, z1=z1, destination=destination, z2=z2):
                self.hex(0, source, z1)
                self.hex(1, destination, z2)
                self.check_costs(expected)

    def test_terrain_surcharge_combines_with_elevation(self):
        self.hex(1, 'HEAVY_FOREST', 2)
        self.check_costs((5, 0, 0))
        self.hex(1, 'MOUNTAINS', 1)
        self.check_costs((4, 4, 4))
        self.hex(1, 'LIGHT_FOREST', 1)
        self.check_costs((3, 3, 3))

    def test_source_forest_is_not_an_entry_restriction(self):
        self.hex(0, 'HEAVY_FOREST', 1)
        self.hex(1, 'GRASSLAND', 1)
        self.check_costs((1, 1, 1))

    def test_invalid_coordinates_never_read_cells(self):
        self.map = GameMap(2, 4)
        with patch.object(self.map, 'base_elevation', side_effect=AssertionError('read')), \
                patch.object(self.map, 'rterrain', side_effect=AssertionError('read')):
            for coordinates in ((0, 0, -1, 0), (0, 0, 2, 0), (0, 0, 0, -1),
                                (0, 0, 0, 4), (-1, 0, 1, 0), (2, 0, 1, 0),
                                (0, -1, 1, 0), (0, 4, 1, 0), (0, 0, 1, 2)):
                for function in COSTS:
                    with self.subTest(coordinates=coordinates, function=function.__name__):
                        self.assertEqual(function(self.map, *coordinates), 0)

    def test_legacy_row_guard_only_applies_to_destination(self):
        for function in COSTS:
            self.assertEqual(function(GameMap(2, 4), 0, 3, 1, 1), 1)
            self.assertEqual(function(GameMap(4, 2), 0, 0, 3, 1), 1)

    def test_same_hex_and_distant_hexes_are_priced(self):
        for function in COSTS:
            self.assertEqual(function(self.map, 0, 0, 0, 0), 1)
            self.assertEqual(function(self.map, 0, 0, 3, 3), 1)

    def test_delegates_to_real_terrain_and_signed_floor_accessors(self):
        # A double verifies the boundary, not implemented decoration storage.
        with patch.object(self.map, 'rterrain', return_value=terrain.WATER), \
                patch.object(self.map, 'base_elevation', side_effect=lambda x, y: -3):
            self.check_costs((0, 1, 0))

    def test_queries_preserve_existing_map_and_occupants(self):
        self.hex(1, 'WATER', 1)
        mech = Mech.create_test_mech()
        mech.x, mech.y = 1, 0
        self.map.add_mech(mech)
        before_map = copy.deepcopy({k: v for k, v in vars(self.map).items()
                                    if k != 'mechs_on_map'})
        before_mech = copy.deepcopy({k: v for k, v in vars(mech).items() if k != 'map'})
        self.check_costs((0, 1, 0))
        for function in COSTS:
            self.assertEqual(function(self.map, -1, 0, 1, 0), 0)
        self.assertEqual({k: v for k, v in vars(self.map).items() if k != 'mechs_on_map'}, before_map)
        self.assertEqual({k: v for k, v in vars(mech).items() if k != 'map'}, before_mech)
        self.assertEqual(self.map.mechs_on_map, [mech])
        self.assertIs(mech.map, self.map)
