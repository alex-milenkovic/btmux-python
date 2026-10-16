import unittest
from core.game_loop import GameEngine
from entities.map import GameMap
from entities.mech import Mech, MechStatus
from physics.hexmath import hex_to_float
from systems.map_transitions import check_edge_of_map


class MapEdgesTest(unittest.TestCase):
    def fixture(self):
        engine = GameEngine()
        board = GameMap(12,12)
        board._id = 10
        unit = Mech()
        unit._id, unit.map, unit.mapindex = 1, board, 10
        unit.speed, unit.desired_speed = 20, 30
        board.mechs_on_map.append(unit)
        engine.register_entity(board)
        engine.register_entity(unit)
        return engine, board, unit

    def test_corner_pins_both_axes_and_cancels_motion(self):
        _, board, unit = self.fixture()
        unit.x, unit.y, unit.cocoon = -1, 12, 5
        check_edge_of_map(unit)
        self.assertEqual((0,11,0,0,0),(unit.x,unit.y,unit.speed,unit.desired_speed,unit.cocoon))
        self.assertEqual(hex_to_float(0,11),(unit.fx,unit.fy))

    def test_linked_map_wraps_once_without_stopping(self):
        _, board, unit = self.fixture()
        board.linked = True
        unit.x, unit.y = -1, 12
        check_edge_of_map(unit)
        self.assertEqual((11,0,20,30),(unit.x,unit.y,unit.speed,unit.desired_speed))

    def test_hangar_rubble_and_local_exit_with_persistence_boundary(self):
        engine, board, unit = self.fixture()
        outside = GameMap(12,12)
        outside._id, outside.entrances = 11, {10:dict(x=5,y=6,name='Bay')}
        engine.register_entity(outside)
        board.flags, board.leave_target, board.cf = 1, 11, 0
        unit.x, unit.y = -1, 3
        check_edge_of_map(unit)
        self.assertIs(board,unit.map)
        self.assertIn('The entrance is still filled with rubble!',unit.movement_messages)
        board.cf, unit.x = 10, -1
        check_edge_of_map(unit)
        self.assertIs(outside,unit.map)
        self.assertEqual((5,6),(unit.x,unit.y))
        self.assertNotIn(unit,board.mechs_on_map)
        self.assertIn(unit,outside.mechs_on_map)
        self.assertTrue(any(not effect['applied'] and effect['operation']=='loud_teleport' for effect in unit.external_effects))

    def test_kill_credit_is_local_and_channel_delivery_explicit(self):
        from systems.damage import channel_emit_kill
        _, _, unit = self.fixture()
        attacker = Mech()
        attacker._id = 2
        channel_emit_kill(unit,attacker,'test')
        self.assertEqual(1,attacker.units_killed)
        self.assertFalse(unit.external_effects[-1]['applied'])

    def test_kill_reason_empty_is_an_argument_and_invalid_objects_skip_hooks(self):
        from systems.damage import channel_emit_kill
        _, _, unit = self.fixture()
        channel_emit_kill(unit,reason='')
        self.assertEqual([''],unit.hook_requests[-1]['args'])
        self.assertEqual(['debug','death'],[r['channel'] for r in unit.channel_requests])
        unit.valid_object = False
        before = len(unit.channel_requests)
        channel_emit_kill(unit)
        self.assertEqual(before,len(unit.channel_requests))

    def test_hangar_exit_uses_destination_floor_and_resets_old_los(self):
        from systems.map_transitions import leave_hangar
        engine, board, unit = self.fixture()
        outside = GameMap(12,12)
        outside._id,outside.entrances = 11,{10:dict(x=5,y=6,name='Bay')}
        outside.set_elevation(5,6,3)
        board.cf,board.leave_target,board.losinfo = 10,11,{(unit._id,9):123}
        engine.register_entity(outside)
        leave_hangar(board,unit)
        self.assertEqual((5,6,3,5,6),(unit.x,unit.y,unit.z,unit.last_x,unit.last_y))
        self.assertFalse(board.losinfo)

    def test_transfer_leaves_roster_hole_without_breaking_remaining_consumers(self):
        from entities.mech import MechStatus2,UnitType,VehicleLocation
        from systems.map_transitions import transfer
        from systems.maneuver import update_autoturn_turret
        from systems.targeting import lock_event
        from types import SimpleNamespace
        engine,board,unit=self.fixture()
        target=Mech.create_test_mech()
        tracker=Mech.create_test_mech()
        target._id,tracker._id=2,3
        board.add_mech(target);board.add_mech(tracker)
        engine.register_entity(target);engine.register_entity(tracker)
        tracker.unit_type=UnitType.VEH_GROUND
        tracker.set_status(MechStatus.STARTED)
        tracker.set_status2(MechStatus2.AUTOTURN_TURRET)
        tracker.sections[VehicleLocation.TURRET].internal=1
        tracker.target=target._id
        destination=GameMap(12,12);destination._id=11
        transfer(unit,destination)
        self.assertIsNone(board.mechs_on_map[0])
        self.assertTrue(update_autoturn_turret(tracker,board))
        lock_event(SimpleNamespace(data=tracker,data2=engine))
        board.set_terrain(target.x,target.y,'f')
