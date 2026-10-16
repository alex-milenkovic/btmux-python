"""Surface blast distributions and visible occupant consequences from C."""
import unittest
from unittest.mock import patch
from entities.map import GameMap, ICE, WATER, BRIDGE, GRASSLAND
from entities.mech import Mech, MechStatus, UnitType, MoveType
from physics import ice
from physics import movement
from systems import damage


def occupied(kind=ICE, depth=2, vehicle=False):
    board = GameMap(3, 3)
    board.set_terrain(1, 1, kind)
    board.set_elevation(1, 1, depth)
    unit = Mech.create_test_mech()
    unit.set_status(MechStatus.COMBAT_SAFE)
    unit.set_hex_position(1, 1, depth if kind == BRIDGE else 0)
    if vehicle:
        unit.unit_type, unit.move_type = UnitType.VEH_GROUND, MoveType.TRACK
    board.add_mech(unit)
    return board, unit


class TestSurfacesHardening(unittest.TestCase):
    def test_blast_draw_ranges_and_exact_thresholds(self):
        for kind, depth, limit in ((ICE, 2, 15), (BRIDGE, 3, 40)):
            for hit in (False, True):
                board, unit = occupied(kind, depth)
                messages = []
                with self.subTest(kind=kind, hit=hit), patch('systems.combat.roll_1d6', return_value=1), patch.object(ice.random, 'randint', return_value=limit) as draw, patch.object(movement, 'NOTIFY_HOOK', side_effect=lambda who, text: messages.append((who, text))):
                    self.assertEqual(hit, ice.blast_surface(board, 1, 1, limit if hit else limit - 1))
                    draw.assert_called_once_with(1, limit)
                    self.assertEqual(WATER if hit else kind, board.terrain(1, 1))
                    if hit:
                        self.assertIn((unit, 'goes swimming as the surface breaks!'), messages)
                    elif kind == BRIDGE:
                        self.assertEqual([(unit, 'The bridge at 1,1 shudders from direct hit!')], messages)
                    else:
                        self.assertEqual([], messages)

    def test_protected_bridges_and_ordinary_ground_do_not_draw_or_break(self):
        for kind in (BRIDGE, GRASSLAND):
            board, _ = occupied(kind)
            board.bridges_cs = True
            with self.subTest(kind=kind), patch.object(ice.random, 'randint') as draw:
                self.assertFalse(ice.blast_surface(board, 1, 1, 1000))
                draw.assert_not_called()
                self.assertEqual(kind, board.terrain(1, 1))

    def test_default_break_feedback_and_vehicle_flood_death(self):
        board, unit = occupied(vehicle=True)
        messages, deaths = [], []
        with patch.object(movement, 'NOTIFY_HOOK', side_effect=lambda who, text: messages.append((who, text))), patch.object(damage, 'NOTIFY_HOOK', side_effect=lambda who, text: deaths.append((who, text))):
            ice.break_surface(board, None, 1, 1)
        self.assertIn((unit, 'goes swimming!'), messages)
        self.assertIn((unit, 'Water renders your vehicle inoperable.'), messages)
        self.assertEqual([(unit, 'You have been destroyed!')], deaths)
        self.assertTrue(unit.is_destroyed)
        self.assertEqual('FLOOD', unit.kill_reason)
        self.assertEqual(-2, unit.z)
