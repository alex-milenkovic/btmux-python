"""Real template ejection and actor transfer, with independent radio randomness."""
import tempfile,unittest
from pathlib import Path
from core.game_loop import GameEngine
from core.events import EventType as E
from core.randomness import RandomState
from data.characters import CharacterStore
from data.template_catalog import CatalogDirectory
from data.template_dependency import resolve_catalog
from entities.map import GameMap
from entities.mech import Mech,MechStatus as S,FireMode as F,Location as L
from systems.occupants import Personnel,eject,disembark,autoeject


class EjectionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.engine=GameEngine();self.engine.randomness=RandomState(7)
        self.store=CharacterStore();self.world=Personnel(self.engine,self.store)
        self.engine.template_directory=CatalogDirectory(Path(self.temp.name)/'custom',resolve_catalog(True))
        self.world.radio_source=lambda:123456
        self.unit=Mech.create_test_mech();self.unit._id=10;self.unit.in_character=True;self.unit.official_pilot=101
        self.unit.x=self.unit.y=3;self.unit.status=S.STARTED
        self.board=GameMap(12,12);self.board._id=1000
        self.engine.register_entity(self.board);self.board.add_mech(self.unit)
        self.engine.register_entity(self.unit);self.world.add(self.unit,1000)
        self.store.create(101,'Alice',location=10);self.actor=self.store.actor(101);self.world.add(self.actor,10);self.unit.pilot=self.actor

    def test_manual_loads_real_template_moves_before_source_death(self):
        result=eject(self.unit,self.actor)
        self.assertTrue(result['ok'],result)
        mw=self.world.objects[result['unit']]
        self.assertEqual(mw._id,self.actor.location);self.assertTrue(self.actor.alive)
        self.assertEqual('MechWarrior',mw.template_ref);self.assertEqual(123456,mw.freq[0])
        self.assertEqual(101,mw.official_pilot);self.assertTrue(self.unit.is_destroyed)
        self.assertTrue(self.unit.sections[L.HEAD].criticals[2].firemode&F.DESTROYED_MODE)
        self.assertEqual('CH',mw.contact_id)
        self.assertEqual(2,self.engine.randomness.mt.words_consumed)

    def test_missing_template_rolls_back_and_preserves_actor_and_cockpit(self):
        self.store.records[101]['mwtemplate']='not-present'
        before=set(self.world.objects)
        result=eject(self.unit,self.actor)
        self.assertFalse(result['ok']);self.assertIn('MWTemplate',result['error'])
        self.assertEqual(before,set(self.world.objects));self.assertEqual(10,self.actor.location)
        self.assertFalse(self.unit.is_destroyed)
        self.assertFalse(self.unit.sections[L.HEAD].criticals[2].firemode&F.DESTROYED_MODE)

    def test_disembark_boundary_fall_and_original_survives(self):
        self.unit.clear_status(S.STARTED);self.unit.z=2;self.unit.speed=21.5
        result=disembark(self.unit,self.actor);self.assertTrue(result['ok'],result)
        mw=self.world.objects[result['unit']]
        self.assertEqual((2,True),(mw.z,mw.opaque));self.assertFalse(self.unit.is_destroyed)
        events=[e for e in self.engine.events.pending_events() if e.event_type==E.FALL]
        self.assertEqual([(3,-5)],[(e.tick,e.data2) for e in events])
        self.assertEqual(0,mw.fz)

    def test_auto_airdrop_and_battlesuit_climbout_differ(self):
        result=autoeject(self.unit,self.actor,False);self.assertTrue(result['ok'],result)
        mw=self.world.objects[result['unit']]
        self.assertEqual(150,mw.z);self.assertTrue(self.engine.has_event(E.OOD,mw))
        self.assertFalse(hasattr(mw,'official_pilot'))
        self.world.move(101,10)
        result=autoeject(self.unit,self.actor,True);mw=self.world.objects[result['unit']]
        self.assertFalse(self.engine.has_event(E.OOD,mw));self.assertEqual(0,mw.z)

    def test_last_battlesuit_member_escape_uses_captured_pilot_and_all_eight_members(self):
        from entities.mech import UnitType as U,SectionConfig
        from systems.damage import destroy_section
        from core.randomness import use_source
        self.unit.unit_type=U.BSUIT
        for section in self.unit.sections:section.internal=section.internal_orig=0
        self.unit.sections[0].internal=self.unit.sections[0].internal_orig=1
        self.unit.sections[7].internal=self.unit.sections[7].internal_orig=1
        with use_source(lambda *args: (_ for _ in ()).throw(AssertionError('not last member'))):
            destroy_section(self.unit,None,0)
        self.assertFalse(self.unit.is_destroyed);self.assertEqual(10,self.actor.location)
        with use_source(lambda name,lo,hi,fallback:25):destroy_section(self.unit,None,7)
        self.assertTrue(self.unit.is_destroyed);self.assertNotEqual(10,self.actor.location)
        self.assertTrue(self.actor.alive)
        mw=self.world.objects[self.actor.location]
        self.assertFalse(self.engine.has_event(E.OOD,mw))
        self.assertTrue(self.engine.has_event(E.NUKEMECH,self.unit))

    def test_reactor_autoescape_precedes_head_death(self):
        from systems.damage import reactor_explosion
        from core.randomness import use_source
        with use_source(lambda name,lo,hi,fallback:hi):reactor_explosion(self.unit,self.unit)
        self.assertTrue(self.unit.is_destroyed);self.assertEqual(0,self.unit.sections[L.HEAD].internal)
        self.assertNotEqual(10,self.actor.location);self.assertTrue(self.actor.alive)
        self.assertTrue(self.engine.has_event(E.OOD,self.world.objects[self.actor.location]))

    def test_player_template_override_retains_source_loaded_class(self):
        from entities.mech import UnitType
        self.store.records[101]['mwtemplate']='WVR-6R'
        result=eject(self.unit,self.actor)
        self.assertTrue(result['ok'],result)
        shell=self.world.objects[result['unit']]
        self.assertEqual(UnitType.MECH,shell.unit_type)
        self.assertEqual('WVR-6R',shell.template_ref)
        self.assertEqual(shell._id,self.actor.location)
