import unittest
from core.game_loop import GameEngine
from core.events import EventType
from core.randomness import use_source
from entities.map import GameMap
from entities.map_objects import MapObject, add_object, delete_object, delete_objects, find_object, save_objects, load_objects
from physics import decorations


def fixture():
    engine=GameEngine()
    board=GameMap(9,9)
    board._id=10
    engine.register_entity(board)
    return engine,board


class ObjectsTest(unittest.TestCase):
    def test_prepend_copy_lookup_and_stream_reversal(self):
        engine,board=fixture()
        source=MapObject(x=1,y=1,obj=40)
        first=add_object(board,4,source)
        source.obj=50
        second=add_object(board,4,source)
        self.assertEqual(40,first.obj)
        self.assertIs(second,find_object(board,1,1,-1))
        wire=save_objects(board)
        target=GameMap(9,9)
        load_objects(target,wire)
        self.assertEqual([40,50],[o.obj for o in target.map_objects[4]])
        with self.assertRaisesRegex(ValueError,'start'): load_objects(target,b'bad')
        self.assertEqual(2,len(target.map_objects[4]))
        with self.assertRaisesRegex(ValueError,'end'): load_objects(target,wire[:-1]+b'!')
        self.assertEqual(2,len(target.map_objects[4]))

    def test_delete_zap_controls_restore_and_cancellation(self):
        for zap in range(4):
            engine,board=fixture()
            board.set_terrain(1,1,'~')
            obj=decorations.add_smoke(engine,board,1,1,30)
            event=obj.event
            delete_object(board,obj,1,zap)
            self.assertEqual(':' if zap&2 else '~',board.terrain(1,1))
            self.assertEqual(bool(zap),event.zombie)
            self.assertTrue(board.flags&1)

    def test_bulk_delete_preserves_overlay_but_cancels_timer(self):
        engine,board=fixture()
        decorations.add_smoke(engine,board,1,1,30)
        delete_objects(board)
        self.assertEqual(':',board.terrain(1,1))
        self.assertEqual(0,engine.events.count_type(EventType.DECORATION))
        self.assertFalse(board.flags&1)


class DecorationsTest(unittest.TestCase):
    def test_replacement_and_permanent_smoke(self):
        engine,board=fixture()
        board.set_terrain(1,1,'~')
        old=decorations.add_smoke(engine,board,1,1,30)
        replacement=decorations.add_smoke(engine,board,1,1,0)
        self.assertTrue(old.event.zombie)
        self.assertIsNone(replacement.event)
        self.assertEqual('~',board.rterrain(1,1))

    def test_source_duration_copy_and_first_spread(self):
        for duration,wind,next_delay in ((180,0,60),(120,0,60),(60,0,1),(180,50,20)):
            engine,board=fixture()
            board.windspeed=wind
            board.set_terrain(4,4,'`')
            obj=decorations.add_fire(engine,board,4,4,duration)
            self.assertEqual(duration,obj.datas)
            first=max(20,60-wind)
            self.assertEqual(first,obj.event.tick)
            with use_source(lambda name,low,high,fallback: 2 if high==12 else low):
                for _ in range(first):
                    engine.events.advance_tick()
                    engine.events.run_events()
            self.assertEqual(first+next_delay,obj.event.tick)
            self.assertEqual(duration-first,obj.datas)

    def test_wind_parity_and_smoke_before_fire(self):
        engine,board=fixture()
        self.assertEqual([(4,3),(3,4),(5,4),(4,2)],decorations.spread_coordinates(board,4,4,0))
        self.assertEqual([(5,4),(4,3),(5,5),(6,3)],decorations.spread_coordinates(board,4,4,30))
        board.set_terrain(1,1,'`')
        with use_source(lambda name,low,high,fallback: low):
            decorations.check_smoke(engine,board,[(1,1)])
            decorations.check_fire(engine,board,[(1,1)])
        self.assertEqual('&',board.terrain(1,1))
        self.assertEqual('`',board.rterrain(1,1))

class TerrainConsumersTest(unittest.TestCase):
    def test_cached_overlay_without_decoration_keeps_cached_fallback(self):
        from entities.mech import Mech
        from physics.collision import mech_rterrain
        from systems.sensors import _mech_rterrain
        engine,board=fixture(); unit=Mech(); unit.map=board; unit.x=unit.y=1; unit.terrain=':'
        board.set_terrain(1,1,'~')
        self.assertEqual(':',mech_rterrain(unit))
        self.assertEqual(':',_mech_rterrain(unit))
        add_object(board,2,MapObject(x=1,y=1,datac=ord('%')))
        self.assertEqual('%',mech_rterrain(unit))

    def test_fire_hex_and_clear_hex_exact_intentional_messages(self):
        from entities.mech import Mech
        from systems.terrain_combat import fire_hex,clear_hex
        engine,board=fixture(); unit=Mech(); unit.map=board; unit._engine=engine
        board.set_terrain(1,1,'`')
        with use_source(lambda name,low,high,fallback:low): fire_hex(unit,1,1,False)
        self.assertEqual('You accidentally ignite 1,1!',unit.movement_messages[-1])
        self.assertEqual('&',board.terrain(1,1))
        board.set_terrain(2,2,'`')
        with use_source(lambda name,low,high,fallback:1): clear_hex(unit,2,2,False)
        self.assertEqual('You accidentally clear 2,2!',unit.movement_messages[-1])
        self.assertEqual('%',board.terrain(2,2))

class MineBitsTest(unittest.TestCase):
    def test_first_mine_and_recreated_table_reach_discovery_and_movement(self):
        from unittest.mock import patch
        from entities.mech import Mech
        from entities.map_objects import bits_for
        from systems import mines
        for producer in ('ordinary','admin'):
            with self.subTest(producer=producer):
                engine,board=fixture();unit=Mech.create_test_mech();unit._id=40
                unit.x=unit.y=1;unit.z=0;engine.register_entity(unit);board.add_mech(unit)
                self.assertIsNone(bits_for(board,False))
                from entities.pilot import Pilot
                unit.in_character=True;unit.pilot=Pilot(perception=6)
                unit.pilot._id=50;unit.pilot.location=unit._id
                if producer=='ordinary':
                    mines.add_mine(board,1,1,5)
                    self.assertEqual(set(),board.mine_hexes)
                    mines.recalculate_minefields(board)
                else:mines.map_add_mine(board,'1 1 STANDARD 5')
                for recreated in (False,True):
                    with self.subTest(recreated=recreated):
                        if recreated:
                            delete_objects(board,8)
                            self.assertEqual(set(),board.mine_hexes)
                            self.assertEqual(0,mines.possible_mine_poof(unit,'step'))
                            self.assertFalse(mines.show_mines_in_hex(unit,1,1,1))
                            mines.recalculate_minefields(board)
                        self.assertEqual({(1,1)},board.mine_hexes)
                        self.assertEqual(4,bits_for(board,False).query(1,1,1))
                        with use_source(lambda name,low,high,fallback:high):
                            self.assertTrue(mines.show_mines_in_hex(unit,1,1,1))
                        with patch('systems.mines.blast_hit_hexes') as blast:
                            self.assertEqual(1,mines.possible_mine_poof(unit,'step'))
                            blast.assert_called_once()

    def test_mine_coverage_uses_shared_safe_bits_and_keeps_hangar_bit(self):
        from systems.mines import map_add_mine,recalculate_minefields
        from entities.map_objects import bits_for
        engine,board=fixture(); bits_for(board).set(1,1,2)
        map_add_mine(board,'1 1 STANDARD 5')
        self.assertEqual(4,bits_for(board).query(1,1,1))
        self.assertEqual(8,bits_for(board).query(1,1,2))
        board.mines.clear(); recalculate_minefields(board)
        self.assertEqual(0,bits_for(board).query(1,1,1))
        self.assertEqual(8,bits_for(board).query(1,1,2))
