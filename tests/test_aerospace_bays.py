from tests.movement_fixture import MovementTestCase
from entities.mech import Mech, UnitType as U, MechStatus as S, FireMode
from entities.crittypes import i2special, Special
from entities.map import GameMap
from core.events import EventType
from systems import dropships as ds


class BayTests(MovementTestCase):
    def setUp(self):
        super().setUp()
        self.board._id=self.unit.mapindex=100
        self.ship=Mech.create_test_mech()
        self.ship.unit_type=U.DS
        self.ship.set_status(S.LANDED|S.STARTED)
        self.ship.set_hex_position(10,10)
        self.board.add_mech(self.ship)
        self.engine.register_entity(self.ship)
        self.ship.sections[5].criticals[0].type=i2special(Special.DS_MECHDOOR)
        self.bay=GameMap(10,10);self.bay._id=101
        self.engine.register_entity(self.bay)
        ds.create_bays(self.ship,[101])
        self.unit.set_hex_position(10,9)
        self.unit.max_speed=60

    def test_configuration_failure_keeps_earlier_assignments_and_old_tail(self):
        other=GameMap(10,10);other._id=102;self.engine.register_entity(other)
        self.ship.aero_bays=[101,101,101,101]
        self.assertFalse(ds.create_bays(self.ship,[102,999])[0])
        self.assertEqual(self.ship.aero_bays,[102,101,101,101])
        self.assertEqual(other.onmap,self.ship._id)

    def test_destroyed_door_counts_but_does_not_open(self):
        self.ship.sections[5].criticals[0].firemode|=FireMode.DESTROYED_MODE
        self.assertEqual(ds.bay_number(self.ship,0),0)
        self.assertFalse(ds.bay_open(self.unit,self.ship,101))

    def test_entry_is_delayed_and_does_not_recheck_destroyed_door(self):
        self.assertTrue(ds.enter_bay(self.unit)[0])
        self.engine.run_ticks(11)
        self.assertIs(self.unit.map,self.board)
        self.ship.sections[5].criticals[0].firemode|=FireMode.DESTROYED_MODE
        self.engine.run_ticks(1)
        self.assertIs(self.unit.map,self.bay)
        self.assertEqual((self.unit.x,self.unit.y),(5,5))

    def test_callback_speed_equality_cancels_transfer(self):
        ds.enter_bay(self.unit)
        self.unit.speed=12
        self.engine.run_ticks(12)
        self.assertIs(self.unit.map,self.board)

    def test_edge_exit_preserves_ground_fz_and_rotated_parity(self):
        from systems.map_transitions import transfer,check_edge_of_map
        transfer(self.unit,self.bay)
        self.ship.set_hex_position(11,10);self.ship.facing=60
        self.unit.fz=123
        self.unit.x=-1
        check_edge_of_map(self.unit)
        self.assertIs(self.unit.map,self.board)
        self.assertEqual((self.unit.x,self.unit.y,self.unit.fz),(12,9,123))
