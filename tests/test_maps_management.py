import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from entities.map import GameMap, map_update
from entities.mech import Mech, MechStatus as S
from entities.map_objects import MapObject, add_object, bits_for
from physics.decorations import add_smoke
from tests.test_maps_objects import fixture
from systems import map_management as maps
from systems.map_conditions import set_conditions, update_conditions


class ManagementTest(unittest.TestCase):
    def test_direct_load_uses_setmap_without_refreshing_occupant_cache(self):
        engine,board=fixture(); unit=Mech(); unit._id=40; unit.x=unit.y=0
        board.add_mech(unit); unit.elev=4; unit.mapflag=0; board.mechflags[0]=0
        self.assertEqual(0,maps.load_text(board,'1 1\n~2\n','water'))
        self.assertEqual(('~',2),(board.terrain(0,0),board.elevation(0,0)))
        self.assertEqual((' ',4,0),(unit.terrain,unit.elev,unit.mapflag))

    def test_numeric_parser_preserves_prefix_and_zero_rule(self):
        self.assertEqual(['a','b'],maps.arguments(' a\tb extra',2))
        self.assertEqual(-12,maps.readnum('-12junk'))
        for text in ('00','+0','-0','blah'):
            with self.assertRaises(ValueError): maps.readnum(text)
        self.assertEqual(0,maps.readnum('0'))

    def test_check_and_direct_load_failure_have_different_effects(self):
        engine,board=fixture()
        board.name='original'
        old=add_smoke(engine,board,1,1,10)
        self.assertEqual(-2,maps.check_text('0 2\n'))
        self.assertEqual(-3,maps.check_text('2 2\n.0.1\n'))
        self.assertEqual(1,maps.check_text('1 1\n$0\n'))
        self.assertEqual(-2,maps.load_text(board,'2 2\n.0~1\n','bad'))
        self.assertTrue(old.event.zombie)
        self.assertEqual((9,9,'original'),(board.map_width,board.map_height,board.name))
        self.assertEqual([' ','~'],board._terrain[0])
        self.assertEqual(0,board.flags&1)

    def test_file_roundtrip_loss_flags_and_second_open_failure(self):
        engine,board=fixture()
        board.flags=16
        self.assertEqual(0,maps.load_text(board,"2 1\n&0'1\n",'a'*35))
        self.assertEqual((24,100,20,'a'*30),(board.flags,board.grav,board.temp,board.name))
        self.assertEqual(0,maps.load_text(board,'2 1\n&0.1\n128: +120-20\n','trailer'))
        self.assertEqual((128,120,-20),(board.flags,board.grav,board.temp))
        board.set_terrain(0,0,'&')
        self.assertEqual('2 1\n.0.1\n128: 120 -20\n',maps.save_text(board))
        self.assertEqual(' ',board.terrain(0,0))
        self.assertIn('lost',board.map_errors[-1])
        unit=Mech(); unit._id=40; engine.register_entity(unit); board.add_mech(unit)
        old=add_smoke(engine,board,0,0,30)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'one'
            path.write_text('1 1\n.0\n')
            maps.load_checked(board,path,player=2,fail_second_open=True)
        self.assertIsNone(unit.map)
        self.assertEqual(0,unit.x)
        self.assertTrue(old.event.zombie)
        self.assertEqual((2,1),(board.map_width,board.map_height))

    def test_resize_overlay_clear_and_free(self):
        engine,board=fixture()
        unit=Mech(); unit._id=40; unit.x=unit.y=8
        engine.register_entity(unit); board.add_mech(unit)
        old=add_smoke(engine,board,1,1,30)
        maps.resize(board,'2 2')
        self.assertEqual(':',board.terrain(1,1))
        self.assertTrue(old.event.zombie)
        self.assertEqual((8,8),(unit.x,unit.y))
        smoke=add_smoke(engine,board,0,0,30)
        maps.clear(board)
        self.assertFalse(smoke.event.zombie)
        self.assertEqual((0,0,0,0),(unit.x,unit.y,unit.last_x,unit.last_y))
        maps.free(board)
        self.assertTrue(smoke.event.zombie)
        self.assertIsNone(board._terrain)
        board=GameMap(9,9); bits_for(board)
        with self.assertRaisesRegex(ValueError,'Invalid map'): maps.resize(board,'bad')

    def test_addhex_only_changes_terrain_cache(self):
        engine,board=fixture()
        unit=Mech(); unit._id=40; unit.x=unit.y=1
        board.add_mech(unit); unit.elev=4
        maps.addhex(board,'1 1 ~ -20 ignored')
        self.assertEqual(('~',4,9),(unit.terrain,unit.elev,board.elevation(1,1)))
        with self.assertRaises(ValueError): maps.addhex(board,'1 1 ~ 128')


class ConditionsTest(unittest.TestCase):
    def test_conditions_clear_only_selected_flags_and_apply_to_units(self):
        engine,board=fixture(); unit=Mech(); unit._id=40; board.add_mech(unit)
        unit.status=S.STARTED
        set_conditions(board,'120 -40 1 1 ignored')
        self.assertEqual(S.CONDITIONS,unit.status&S.CONDITIONS)
        set_conditions(board,'100 20')
        self.assertEqual(16,board.flags)
        self.assertEqual(S.STARTED,unit.status)
        with self.assertRaises(ValueError): set_conditions(board,'100 20 00')
        self.assertEqual(16,board.flags)
        unit.status|=S.CONDITIONS
        update_conditions(unit,None)
        self.assertEqual(S.STARTED,unit.status)

    def test_visibility_fifth_conversion_failure_cannot_produce_message(self):
        engine,board=fixture(); unit=Mech(); unit._id=40; board.add_mech(unit)
        board.visibility_config='40 1 60 8 not_a_cloud message'
        engine.events.set_tick(25)
        map_update(engine,board)
        self.assertEqual((40,1,60,8,200),(board.mapvis,board.maplight,board.winddir,board.windspeed,board.cloudbase))
        self.assertFalse(any('not_a_cloud' in message for message in getattr(unit,'messages',[])))
        board.visibility_config='10+2-60+3+250 clouds are gathering\nignored'
        map_update(engine,board)
        self.assertEqual((10,2,-60,3,250),(board.mapvis,board.maplight,board.winddir,board.windspeed,board.cloudbase))

class ObjectCommandsTest(unittest.TestCase):
    def test_delete_mines_recalculates_even_empty_type_and_lists_order(self):
        from systems.mines import map_add_mine
        engine,board=fixture()
        map_add_mine(board,'1 1 STANDARD 5',creator=40)
        map_add_mine(board,'2 2 INFERNO 7',creator=41)
        self.assertEqual([41,40],[mine.creator for mine in board.map_objects[3]])
        self.assertTrue(board.flags&1)
        maps.delobj(board,'MINE 2 2')
        self.assertEqual({(1,1)},board.mine_hexes)
        maps.delobj(board,'MINE')
        board.mine_hexes={(1,1)}
        maps.delobj(board,'MINE')
        self.assertEqual(set(),board.mine_hexes)
        self.assertEqual('0 objects deleted!',board.map_messages[-1])
        add_object(board,4,MapObject(x=1,y=2,obj=41))
        self.assertTrue(any('BUILDING' in line and '41' in line for line in maps.list_objects(board)))

    def test_core_fixture_identity_matches_shared_dynamic_roster(self):
        from tools.core_simulation import CoreSession
        session=CoreSession({'units':[{'name':'a','id':101},{'name':'b','id':102}],
                             'config':{'periodic_updates':False},'actions':[]})
        self.assertEqual([101,102],session.map.roster_ids)
        self.assertEqual([0,1],[session.units[name].mapnumber for name in ('a','b')])
