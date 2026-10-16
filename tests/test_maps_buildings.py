import unittest
from types import SimpleNamespace
from entities.mech import Mech
from entities.map_objects import MapObject,add_object
from tests.test_maps_objects import fixture
from entities.map import GameMap
from systems import buildings


class BuildingsTest(unittest.TestCase):
    def test_source_weapon_rows_change_actual_building_cf(self):
        from core.randomness import use_source
        from entities.weapon import get_weapon
        # Independent weapons.h rows, including differences from equal-size racks.
        for name,throw,expected in (('IS.LRM-10',3,4),('IS.LRM-10',5,5),
                                    ('IS.LRM-15',4,9),('CL.ATM-9',10,14)):
            with self.subTest(name=name,throw=throw):
                engine,exterior=fixture()
                interior=GameMap(9,9,'Depot'); interior._id=20
                interior.cf=interior.cfmax=100; engine.register_entity(interior)
                add_object(exterior,4,MapObject(x=1,y=1,obj=20))
                unit=Mech(); unit.map=exterior; unit._engine=engine
                draws=[]
                def draw(name,low,high,fallback):
                    draws.append((name,low,high)); return throw
                with use_source(draw):
                    damage=buildings.hit_building(unit,1,1,get_weapon(name).index)
                self.assertEqual(expected,damage)
                self.assertEqual(100-expected,interior.cf)
                self.assertEqual([('building_cluster',2,12)],draws)
                self.assertEqual([120],[event.tick for event in engine.events.pending_events()])

    def test_regen_reaching_zero_rearms_once_then_stops(self):
        engine,board=fixture(); board.cf=1; board.cfmax=100; board.regen_factor=-1
        buildings.regen(SimpleNamespace(data=board))
        self.assertEqual(0,board.cf)
        self.assertEqual([120],[event.tick for event in engine.events.pending_events()])
        for _ in range(120): engine.events.advance_tick(); engine.events.run_events()
        self.assertEqual(0,engine.events.pending_count)

    def test_full_damage_regen_and_zero_no_rebuild(self):
        engine,exterior=fixture()
        interior=GameMap(9,9,'hangar'); interior._id=20
        interior.cf=interior.cfmax=100
        engine.register_entity(interior)
        add_object(exterior,4,MapObject(x=1,y=1,obj=20))
        unit=Mech(); unit._id=30; unit.map=exterior; unit._engine=engine
        buildings.hit_building(unit,1,1,0,10)
        self.assertEqual(90,interior.cf)
        self.assertEqual(1,engine.events.pending_count)
        for _ in range(120): engine.events.advance_tick(); engine.events.run_events()
        self.assertEqual(91,interior.cf)
        buildings.hit_building(unit,1,1,0,200)
        self.assertEqual(0,interior.cf)
        for _ in range(120): engine.events.advance_tick(); engine.events.run_events()
        self.assertEqual(0,engine.events.pending_count)
        buildings.rebuild(SimpleNamespace(data=interior))
        self.assertEqual(1,interior.cf)
        self.assertEqual(0,engine.events.pending_count)

    def test_cf_getter_zero_and_negative_factor(self):
        engine,board=fixture()
        self.assertEqual(-1,buildings.get_cf(board))
        board.cfmax=100
        self.assertEqual(0,buildings.get_cf(board))
        board.cf=90; board.regen_factor=-1
        buildings.regen(SimpleNamespace(data=board))
        self.assertEqual(89,board.cf)
        self.assertEqual(1,engine.events.pending_count)

    def test_authorized_streak_correction_all_angel_combinations_and_bypass(self):
        from core.randomness import use_source
        from entities.weapon import IS_STREAK_SRM6,IS_SRM6
        from systems.ecm import ANGEL_ECM_DISTURBED
        from systems.combat import hit_building
        for streak in (False,True):
            for angel in (False,True):
                engine,exterior=fixture(); interior=GameMap(9,9,'Depot'); interior._id=20
                interior.cf=interior.cfmax=100; engine.register_entity(interior)
                add_object(exterior,4,MapObject(x=1,y=1,obj=20))
                unit=Mech(); unit.map=exterior; unit._engine=engine
                if angel: unit.status2|=ANGEL_ECM_DISTURBED
                draws=[]
                def draw(name,low,high,fallback): draws.append(name); return 2
                weapon=IS_STREAK_SRM6 if streak else IS_SRM6
                count=6 if streak and not angel else 2
                with use_source(draw): self.assertEqual(count,buildings.missile_count(unit,weapon))
                self.assertEqual([] if streak and not angel else ['building_cluster'],draws)
                draws.clear()
                with use_source(draw): hit_building(unit,1,1,(IS_STREAK_SRM6 if streak else IS_SRM6).index,0)
                self.assertEqual(100-2*count,interior.cf)
                self.assertEqual([] if streak and not angel else ['building_cluster'],draws)
                draws.clear()
                with use_source(draw): hit_building(unit,1,1,-999,7)
                self.assertEqual(100-2*count-7,interior.cf)
                self.assertEqual([],draws)

    def test_perception_source_guards_cached_target_and_xp_boundary(self):
        from entities.pilot import Pilot
        from core.randomness import use_source
        unit=Mech(); unit.pilot=Pilot(perception=2); unit.pilot._id=50; unit.pilot.location=unit._id
        unit._engine=fixture()[0]; unit._engine.sim_now=61
        draws=[]
        def draw(name,low,high,fallback): draws.append(name); return 8
        with use_source(draw):
            self.assertFalse(buildings.perception(unit,0))
            self.assertEqual([],draws)
            unit.in_character=True; unit.pilot.connected=False
            self.assertFalse(buildings.perception(unit,0)); self.assertEqual([],draws)
            unit.pilot.connected=True; unit.per=9
            self.assertFalse(buildings.perception(unit,0))
            unit.per=0
            self.assertTrue(buildings.perception(unit,1))
        self.assertEqual(2,unit.per)
        self.assertEqual('Perception',unit.xp_requests[-1]['skill'])
        self.assertTrue(unit.xp_requests[-1]['accepted'])
