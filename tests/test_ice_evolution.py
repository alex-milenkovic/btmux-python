"""Surface changes exercise real maps and occupants, independently of APS."""
import unittest
from unittest.mock import patch

from entities.map import GameMap, WATER, ICE, BRIDGE, GRASSLAND
from entities.mech import Mech, MoveType, UnitType
from physics import ice


class IceEvolutionTests(unittest.TestCase):
    def test_percentage_commands_reject_surplus_before_surface_effects(self):
        for command, terrain in ((ice.map_addice, WATER), (ice.map_delice, ICE)):
            with self.subTest(command=command.__name__):
                board = GameMap(1, 1)
                board.set_terrain(0, 0, terrain)
                unit = Mech.create_test_mech()
                board.add_mech(unit)
                before = (unit.status, unit.z, unit.fz)
                with patch.object(ice.random, 'randint') as draw, patch.object(ice, 'break_surface') as surface:
                    self.assertFalse(command(board, '100 ignored')[0])
                draw.assert_not_called()
                surface.assert_not_called()
                self.assertEqual(terrain, board.terrain(0, 0))
                self.assertEqual(before, (unit.status, unit.z, unit.fz))


    def test_growth_keeps_new_ice_waterlike_until_scan_finishes(self):
        board = GameMap(7, 7)
        for xy in ((3, 3), (3, 4), (4, 3)):
            board.set_terrain(*xy, WATER)
            board.set_elevation(*xy, 2)
        with patch.object(ice.random, 'randint', side_effect=[1, 3, 1, 2, 1, 2]):
            self.assertEqual(1, ice.ice_growth(board, 100))
        self.assertEqual([ICE, WATER, WATER],
                         [board.terrain(*xy) for xy in ((3, 3), (3, 4), (4, 3))])
        self.assertEqual(2, board.elevation(3, 3))

    def test_melt_uses_earlier_changes_in_the_scan(self):
        board = GameMap(4, 4)
        for x in range(4):
            for y in range(4):
                board.set_terrain(x, y, ICE)
        with patch.object(ice.random, 'randint', side_effect=lambda lo, hi: 1 if hi == 100 else 3):
            self.assertEqual(16, ice.ice_melt(board, 100))

    def test_neighbors_clip_edges_and_use_column_parity(self):
        board = GameMap(4, 4)
        self.assertEqual({(0, 1), (1, 0), (1, 1)}, set(ice.neighbors(board, 0, 0)))
        self.assertEqual({(1, 0), (2, 0), (2, 1), (1, 2), (0, 1), (0, 0)},
                         set(ice.neighbors(board, 1, 1)))

    def test_growth_does_not_count_ice_or_highwater(self):
        board = GameMap(3, 3)
        board.set_terrain(1, 1, WATER)
        for xy in ice.neighbors(board, 1, 1):
            board.set_terrain(*xy, ICE)
        with patch.object(ice.random, 'randint', return_value=100) as draw:
            self.assertEqual(1, ice.ice_growth(board, 101))
            self.assertEqual(1, draw.call_count)

    def test_shared_bridge_break_preserves_occupant_cached_height(self):
        board = GameMap(2, 2)
        board.set_terrain(0, 0, BRIDGE)
        board.set_elevation(0, 0, 3)
        unit = Mech.create_test_mech()
        unit.z = 3
        unit.move_type = MoveType.HOVER
        board.add_mech(unit)
        with patch('physics.jump.mech_falls') as fall:
            ice.break_surface(board, None, 0, 0)
            fall.assert_called_once_with(unit, 4, notify_fall=False)
        self.assertEqual((WATER, 1, WATER, 3),
                         (board.terrain(0, 0), board.elevation(0, 0), unit.terrain, unit.elev))

    def test_percentage_commands_validate_and_do_not_clamp(self):
        board = GameMap(1, 1)
        board.set_terrain(0, 0, WATER)
        for argument in ('', 'a', '+0', '-0', '00'):
            self.assertFalse(ice.map_addice(board, argument)[0])
        self.assertEqual((True, "No hexes 'iced'."), ice.map_addice(board, '-1'))
        self.assertEqual((True, "1 hexes 'iced'."), ice.map_addice(board, '101x'))

    def test_blast_threshold_and_bridge_protection(self):
        for terrain, damage, draw, protected, expected in (
            (ICE, 5, 5, False, WATER), (ICE, 5, 6, False, ICE),
            (BRIDGE, 10, 10, False, WATER), (BRIDGE, 40, 1, True, BRIDGE),
        ):
            board = GameMap(1, 1)
            board.set_terrain(0, 0, terrain)
            board.set_elevation(0, 0, 3)
            board.bridges_cs = protected
            with patch.object(ice.random, 'randint', return_value=draw):
                ice.blast_surface(board, 0, 0, damage)
            self.assertEqual(expected, board.terrain(0, 0))
