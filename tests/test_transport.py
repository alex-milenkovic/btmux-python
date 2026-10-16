"""Ordinary boarding source locks, tow sequencing, startup and cargo."""
import unittest
from core.game_loop import GameEngine
from data.characters import CharacterStore
from entities.mech import Mech,UnitType as U,MechStatus as S,FireMode as F,Location as L
from entities.map import GameMap
from systems.occupants import Personnel,embark,unit_disembark,pickup


class TransportTest(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.store=CharacterStore();self.world=Personnel(self.engine,self.store,pickup_action=0)
        self.board=GameMap(12,12);self.board._id=1000;self.engine.register_entity(self.board)
        self.own=self.make(10);self.carrier=self.make(20)
        self.carrier.car_max_ton=5;self.carrier.cargo_space=800;self.carrier.specials2=0x80000
        self.store.create(101,'Alice',location=10);self.actor=self.store.actor(101);self.world.add(self.actor,10)
        self.own.pilot=self.actor;self.own.official_pilot=101

    def make(self,ident):
        u=Mech.create_test_mech();u._id=ident;u.status=S.STARTED;u.in_character=True;u.team=1;u.tonnage=5;u.measured_mass=5*1024
        self.board.add_mech(u);u.mapindex=1000;u.set_hex_position(3,3);self.engine.register_entity(u);self.world.add(u,1000)
        from systems.sensors import update_los_info
        from systems.targeting import plos_event
        from types import SimpleNamespace
        from core.randomness import use_source
        with use_source(lambda name,lo,hi,fallback:hi):
            update_los_info(self.board)
            for other in self.board.mechs_on_map:plos_event(SimpleNamespace(data=other,data2=self.engine))
        return u

    def test_mw_lock_policy_and_source_speed_boundary(self):
        self.own.unit_type=U.MW;self.carrier.team=2;self.carrier.speed=15
        r=embark(self.own,self.actor,self.carrier);self.assertFalse(r['ok']);self.assertIn('Locked',r['error'])
        self.carrier.enter_lock='approved';self.carrier.lock_result=True
        r=embark(self.own,self.actor,self.carrier);self.assertTrue(r['ok'],r)
        self.assertEqual(20,self.actor.location);self.assertEqual(800,self.carrier.cargo_space)
        self.assertEqual([101],self.world.contents(20))

    def test_tow_first_then_shutdown_and_unit_exit_immediately_starts(self):
        tow=self.make(30);tow.tonnage=3;tow.measured_mass=3*1024;tow.set_status(S.TOWED)
        self.own.carrying=30;self.own.towed_unit=tow
        r=embark(self.own,self.actor,self.carrier);self.assertTrue(r['ok'],r)
        self.assertEqual(0,self.carrier.cargo_space)
        self.assertEqual([30,10],self.world.contents(20))
        self.assertEqual((-1,-1), (self.own.mapindex,tow.mapindex))
        self.assertEqual((3,3), (self.own.x,self.own.y));self.assertIsNone(self.own.pilot)
        self.assertFalse(tow.has_status(S.TOWED));self.assertEqual(-1,self.own.carrying)
        r=unit_disembark(self.own,self.actor);self.assertTrue(r['ok'],r)
        self.assertTrue(self.own.is_started);self.assertIs(self.actor,self.own.pilot)
        self.assertEqual(500,self.carrier.cargo_space);self.assertEqual((3,3,1000),(self.own.x,self.own.y,self.own.mapindex))
        self.assertEqual([60]*8,[s.recycle for s in self.own.sections])

    def test_failed_combined_capacity_and_unknown_lock_do_not_move(self):
        tow=self.make(30);tow.tonnage=3;tow.measured_mass=3*1024;self.own.carrying=30;self.carrier.cargo_space=799
        r=embark(self.own,self.actor,self.carrier);self.assertFalse(r['ok']);self.assertIn('towed',r['error'])
        self.assertIs(self.board,self.own.map);self.assertEqual(799,self.carrier.cargo_space)
        self.carrier.enter_lock='unknown';self.carrier.lock_result=None
        r=embark(self.own,self.actor,self.carrier);self.assertFalse(r['ok']);self.assertIn('unavailable',r['error'])

    def test_pickup_captures_occupants_and_schedules_shell_disposal(self):
        self.carrier.unit_type=U.MW;self.carrier.team=2;self.carrier.specials2=0
        self.world.move(101,20)
        self.store.create(102,'Wizard',location=20,wizard=True);self.world.add(self.store.actor(102),20)
        r=pickup(self.own,self.actor,self.carrier);self.assertTrue(r['ok'],r)
        self.assertEqual([101,102],self.world.contents(10));self.assertTrue(self.actor.slave)
        self.assertFalse(getattr(self.store.actor(102),'slave',False))
        self.assertEqual(1,len([e for e in self.engine.events.pending_events() if e.event_type.name=='NUKEMECH']))

    def test_transport_death_invokes_source_unit_actor_then_destroys_carried_unit(self):
        from systems.damage import destroy_mech
        self.engine.transported_unit_death=True
        self.board.remove_mech(self.own);self.own.map=None;self.own.mapindex=-1
        self.world.move(10,20)
        destroy_mech(self.carrier,None)
        self.assertTrue(self.own.is_destroyed)
        self.assertEqual(20,self.own.location)
        self.assertIn("isn't your mech",self.own.last_transport_exit['error'])

    def test_explosion_kills_and_discards_embarked_suits_before_outer_contents(self):
        from systems.damage import explode_unit
        from core.randomness import use_source
        self.own.unit_type=U.BSUIT;self.world.move(10,20)
        with use_source(lambda name,lo,hi,fallback:hi):explode_unit(self.carrier,None)
        self.assertFalse(self.actor.alive);self.assertEqual(900,self.actor.location)
        self.assertTrue(self.engine.has_event(__import__('core.events',fromlist=['EventType']).EventType.NUKEMECH,self.own))

    def test_transport_notices_precede_departure_and_reach_local_occupants(self):
        from unittest.mock import patch
        records=[]
        with patch('systems.sensors.los_broadcast',side_effect=lambda u,text:records.append((u._id,u.mapindex,text))):
            self.assertTrue(embark(self.own,self.actor,self.carrier)['ok'])
            self.assertTrue(unit_disembark(self.own,self.actor)['ok'])
        self.assertTrue(any(i==10 and board==1000 and 'entry ramp' in text for i,board,text in records))
        self.assertTrue(any(i==10 and text=='powers up!' for i,board,text in records))
        self.assertTrue(any(i==10 and 'emerges from the ramp' in text for i,board,text in records))
        self.assertTrue(any('unit loading ramp' in text for text in self.actor.inbox))
