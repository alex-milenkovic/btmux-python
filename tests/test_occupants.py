"""Local contents really move; remote MUX effects stay separately observable."""
import unittest
from core.game_loop import GameEngine
from data.characters import CharacterStore,SKILLS
from data.character_values import code
from entities.mech import Mech
from systems.occupants import Personnel,tele_contents,discard_mw,kill_contents


class OccupantsTest(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.store=CharacterStore()
        self.world=Personnel(self.engine,self.store,afterlife=900,used_store=901,xploss=500)
        self.shell=Mech.create_test_mech();self.shell._id=10;self.shell.in_character=True
        self.world.add(self.shell,1000);self.engine.register_entity(self.shell)
        for ident,wizard in ((101,False),(102,True),(103,False)):
            self.store.create(ident,str(ident),wizard=wizard,location=10,lock='private')
            self.world.add(self.store.actor(ident),10)
            s=self.store.retrieve(ident);s.xp[code('Running')]=100;self.store.store(ident,s,SKILLS)

    def test_safe_original_order_wizard_slave_xp_and_loud_transfer(self):
        self.assertEqual(2,tele_contents(self.engine,10,20,2|8|4))
        self.assertEqual([102],self.world.contents(10))
        self.assertEqual([101,103],self.world.contents(20))
        for ident in (101,103):
            r=self.store.records[ident]
            self.assertEqual((20,True,''),(r['location'],r['slave'],r['lock']))
            self.assertEqual(50,self.store.retrieve(ident,SKILLS).xp[code('Running')]%16777216)
        self.assertEqual([101,103],[e['id'] for e in self.world.trace if e['kind']=='move'])
        self.assertEqual(1,tele_contents(self.engine,10,20,1|2))
        self.assertFalse(self.store.records[102].get('slave',False))

    def test_quiet_origin_suppresses_xp_but_not_transport(self):
        self.shell.quiet=True
        tele_contents(self.engine,10,20,8)
        self.assertEqual(100,self.store.retrieve(101,SKILLS).xp[code('Running')])
        self.assertEqual(20,self.store.actor(101).location)

    def test_death_and_duplicate_delayed_discard_preserve_local_effect_order(self):
        self.assertEqual(2,kill_contents(self.shell))
        self.assertFalse(self.store.actor(101).alive);self.assertTrue(self.store.actor(102).alive)
        self.assertEqual(900,self.store.actor(103).location)
        discard_mw(self.shell);discard_mw(self.shell)
        self.assertEqual(2,len(self.engine.events.pending_events()))
        for _ in range(10):self.engine.process_tick()
        self.assertEqual(901,self.shell.location)
        self.assertTrue(self.shell.going and self.shell.dark and self.shell.zombie)
        self.assertFalse(self.shell.hardcode)
        self.assertNotIn(self.shell,self.engine.get_entities())
        self.assertEqual(['leave','discard'],[e['kind'] for e in self.world.trace if e['kind'] in ('leave','discard')])
