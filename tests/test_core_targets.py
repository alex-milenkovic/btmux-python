"""Registry, target-coordinate and navigate canvas source contracts."""
import unittest
from unittest.mock import patch
from entities.mech import Mech
from entities.map import GameMap
from systems import targeting, combat, ecm
from tests.test_core_startup import fixture


class TargetUtilitiesTest(unittest.TestCase):
    def test_stored_missing_unit_never_uses_hex_and_other_map_unit_resolves(self):
        engine, unit, _ = fixture()
        unit.targ_x, unit.targ_y, unit.targ_z = 2, 3, 3
        self.assertEqual(193.5, combat.find_target_xy(unit)[2])
        unit.target = 99999
        self.assertIsNone(combat.find_target_xy(unit))
        target = Mech()
        target.fx, target.fy, target.fz = 1, 2, 3
        engine.register_entity(target)
        unit.target = target._id
        self.assertEqual((1, 2, 3), combat.find_target_xy(unit))

    def test_contact_prefix_case_first_match_and_self(self):
        engine, unit, _ = fixture()
        unit.contact_id = 'AB'
        peer = Mech(contact_id='Ab')
        unit.map.add_mech(peer)
        engine.register_entity(peer)
        unit.map.mechs_on_map.insert(0, None)
        self.assertIs(unit, targeting.contact_target(unit, 'abSuffix'))
        self.assertIsNone(targeting.contact_target(unit, 'zz'))

    def test_valid_map_checks_metadata_before_allocation(self):
        board = GameMap(3, 3)
        for record, error in ((None, 'Index out of range!'),
                ({'valid': False, 'xtype': 'MAP', 'object': board}, 'Index out of range!'),
                ({'xtype': '', 'object': board}, 'That is not a valid map! (no XTYPE!)'),
                ({'xtype': 'map', 'object': board}, 'That is not a valid map!'),
                ({'xtype': 'MAP', 'object': None}, 'The map has not been allocated!!')):
            self.assertEqual((None, error), targeting.valid_map(record))
        self.assertEqual((board, ''), targeting.valid_map({'xtype': 'MAP', 'object': board}))

    def test_los_flag_replaced_and_mapless_no_op(self):
        _, unit, _ = fixture()
        unit.mapflag, unit.map.moves = 7, 4
        ecm.mark_for_los_update(unit)
        self.assertEqual((1, 5), (unit.mapflag, unit.map.moves))
        unit.map = None
        ecm.mark_for_los_update(unit)
        self.assertEqual(1, unit.mapflag)

    def test_navigation_draws_other_roster_then_own_marker_last(self):
        _, unit, _ = fixture()
        unit.set_hex_position(3, 3)
        peer = Mech()
        peer.set_hex_position(3, 3)
        unit.map.add_mech(peer)
        rows = ['.' * 28 for _ in range(14)]
        with patch.object(targeting, 'in_line_of_sight', return_value=True) as los:
            result = targeting.navigate_sketch_mechs(unit, unit.map, 3, 3, rows)
        self.assertEqual('*', result[6][14])
        self.assertEqual(1, sum(row.count('*') for row in result))
        self.assertEqual(.5, los.call_args.args[-1])
        self.assertEqual(rows, ['.' * 28 for _ in range(14)])


if __name__ == '__main__': unittest.main()
