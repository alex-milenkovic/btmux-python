"""Sequences and source boundaries reopened by the AUD-TEMPLATES review."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.attributes import AttributeStore,attributes_for
from core.events import EventType as E
from core.game_loop import GameEngine
from data.template_catalog import CatalogDirectory
from data.template_directory import TemplateDirectory,load_legacy_stream,save_legacy
from data.template_files import clear_mech,load_stream
from data.templates import MECH_TYPES
from entities.crittypes import i2weapon
from entities.mech import Mech,MechStatus as S,MechStatus2 as S2,Specials,UnitType as U
from entities.weapon import get_weapon
from systems.construction_editor import Editor


class TemplateReviewCorrections(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def unit(self):
        unit=Mech();clear_mech(unit,True);unit._id=71
        return unit

    def test_automatic_scratch_store_yields_to_durable_directory(self):
        for dual in (False,True):
            with self.subTest(dual=dual):
                root=self.root/str(dual);root.mkdir()
                upstream=self.root/('up'+str(dual));upstream.mkdir()
                (root/'SAVED').write_text('Tons { 50 }\nReference { SAVED }\n')
                factory=lambda:CatalogDirectory(root,upstream) if dual else TemplateDirectory(root)
                unit=self.unit()
                load_stream(unit,io.StringIO('Tons { 50 }\n'),'SCRATCH',finalize=False)
                scratch=unit.attribute_store
                directory=factory();self.assertTrue(directory.loadnew(unit,'SAVED'))
                self.assertIs(directory.attributes,unit.attribute_store)
                self.assertEqual(['SCRATCH'],[r['value'] for r in scratch.writes])
                self.assertEqual(['SAVED','SAVED'],[r['value'] for r in directory.attributes.writes])
                recreated=self.unit()
                self.assertTrue(factory().restore(recreated))
                self.assertEqual('SAVED',recreated.template_ref)
                self.assertFalse((upstream/'.state').exists())

    def test_engine_service_promotes_fallback_but_explicit_adapter_wins(self):
        unit=self.unit()
        load_stream(unit,io.StringIO('Tons { 50 }\n'),'SCRATCH',finalize=False)
        engine=GameEngine();engine.attributes=AttributeStore(self.root/'engine.json')
        unit._engine=engine
        self.assertIs(engine.attributes,attributes_for(unit,AttributeStore()))
        explicit=AttributeStore();unit.attribute_store=explicit
        (self.root/'SAVED').write_text('Tons { 50 }\n')
        self.assertTrue(TemplateDirectory(self.root).loadnew(unit,'SAVED'))
        self.assertIs(explicit,unit.attribute_store)
        self.assertEqual('SAVED',explicit.get(unit._id,'A_MECHREF'))
        self.assertEqual([],engine.attributes.writes)

    def test_public_load_fields_and_load_keep_durable_reference_order(self):
        from tools.construction_templates import ConstructionSession
        for name in ('FIELDS','FINAL'):(self.root/name).write_text(f'Tons {{ 50 }}\nReference {{ {name} }}\n')
        session=ConstructionSession({'construction':{'root':str(self.root)},'config':{'periodic_updates':False},'actions':[]})
        self.assertTrue(session.action({'op':'construction_diagnose','kind':'load_fields','args':['FIELDS']})['ok'])
        unit=session.unit({})
        reopened=AttributeStore(self.root/'.state'/'attributes.json')
        self.assertEqual('FIELDS',reopened.get(unit._id,'A_MECHREF'))
        self.assertTrue(session.action({'op':'template','kind':'load','reference':'FINAL'})['ok'])
        self.assertEqual('FINAL',reopened.get(unit._id,'A_MECHREF'))
        self.assertEqual(['FIELDS','FIELDS','FINAL','FINAL'],[r['value'] for r in unit.attribute_store.writes])
        recreated=self.unit();recreated._id=unit._id
        self.assertTrue(TemplateDirectory(self.root).restore(recreated))
        self.assertEqual('FINAL',recreated.template_ref)

    def test_attribute_staging_does_not_open_existing_link_or_collision(self):
        custom=self.root/'custom';upstream=self.root/'upstream'
        (custom/'.state').mkdir(parents=True);upstream.mkdir()
        protected=upstream/'KEEP';protected.write_text('unchanged catalog bytes')
        (custom/'SAVED').write_text('Tons { 50 }\n')
        # Hard links exercise the same existing-target overwrite without the
        # symlink privilege this Windows test host lacks.
        os.link(protected,custom/'.state'/'attributes.json.tmp')
        os.link(protected,custom/'.state'/'attributes.json.collision.tmp')
        directory=CatalogDirectory(custom,upstream);unit=self.unit()
        with patch('tempfile._get_candidate_names',return_value=iter(('collision','safe'))):
            self.assertTrue(directory.loadnew(unit,'SAVED'))
        self.assertEqual('unchanged catalog bytes',protected.read_text())
        self.assertEqual('SAVED',AttributeStore(custom/'.state'/'attributes.json').get(unit._id,'A_MECHREF'))
        self.assertFalse((custom/'.state'/'attributes.json.safe.tmp').exists())
        with self.assertRaisesRegex(ValueError,'Attribute path leaves'):
            AttributeStore(upstream/'attributes.json',root=custom)
        self.assertFalse((upstream/'attributes.json').exists())

    def test_empty_edit_and_default_reset_supersede_failed_legacy_type(self):
        for operation,args in (('addspecial','Empty LA 5'),('resetcrits','')):
            with self.subTest(operation=operation):
                unit=self.unit();lines=['50 20 40 20 10 64.5 0 0','1 1 0 0']+['0 0 0']*4+['192 5 32']
                with self.assertRaisesRegex(ValueError,'Invalid datatype at 0/4'):
                    load_legacy_stream(unit,io.StringIO('\n'.join(lines)),'OLD')
                slot=unit.sections[0].criticals[4];self.assertEqual(192,slot.invalid_source_type)
                editor=Editor(7,{'unit':unit});editor.target='unit'
                self.assertTrue(editor.execute(operation,args)['ok'])
                self.assertEqual(0,slot.type);self.assertFalse(hasattr(slot,'invalid_source_type'))
                target=self.root/operation;save_legacy(unit,target)
                with target.open() as stream:load_legacy_stream(self.unit(),stream,'REPAIRED')

    def test_restore_preserves_dump_callback_selection_and_wrapper_cancels(self):
        from entities.map import GameMap
        from systems.ammo_dump import DumpSelection,arm_dump,mech_dump
        (self.root/'MW').write_text('Type { Mechwarrior }\nTons { 50 }\nArmor { 10 }\nInternals { 10 }\nCRIT_1 { Ammo_IS.AC/5 20 - - }\n')
        unit=self.unit();unit._engine=engine=GameEngine();unit.map=GameMap(10,10);unit.mapindex=1
        unit.map._id=1;engine.register_entity(unit.map)
        directory=TemplateDirectory(self.root);self.assertTrue(directory.loadnew(unit,'MW'))
        selection=DumpSelection('bin',location=0,slot=0);arm_dump(unit,selection)
        event=unit._dump_event
        engine.events.schedule(60,E.UNJAM_AMMO,lambda ev:None,unit)
        self.assertTrue(directory.restore(unit))
        self.assertIs(event,unit._dump_event);self.assertEqual(selection,unit._dump_selection)
        self.assertTrue(unit.dumping);self.assertTrue(unit.unjamming)
        self.assertEqual("You're already dumping some ammo!",mech_dump(engine,unit,'LA 1')[1])
        engine.run_ticks(2)
        self.assertEqual(18,unit.sections[0].criticals[0].data)
        self.assertEqual(selection,unit._dump_event.data2)
        self.assertTrue(mech_dump(engine,unit,'stop')[0])
        self.assertFalse(engine.has_event(E.DUMP,unit))
        arm_dump(unit,selection)
        self.assertTrue(directory.loadnew(unit,'MW',wrapper=True))
        self.assertEqual(0,engine.events.count_data(unit))
        self.assertFalse(unit.dumping);self.assertFalse(unit.unjamming)
        self.assertIsNone(unit._dump_event);self.assertIsNone(unit._dump_selection)

    def test_mw_startup_recycles_current_inventory_not_replaced_ammo(self):
        from systems.weapon_inventory import sync_weapon_states
        unit=self.unit();unit._engine=engine=GameEngine();engine.events.set_tick(5)
        unit.sections[0].internal=unit.sections[0].internal_orig=10
        unit.sections[0].armor=unit.sections[0].armor_orig=10
        for pos in (0,1):
            slot=unit.sections[0].criticals[pos];slot.type=i2weapon(get_weapon('IS.SmallLaser').index);slot.data=8
        sync_weapon_states(unit);self.assertEqual(2,len(unit.weapons))
        (self.root/'MW').write_text('Type { Mechwarrior }\nTons { 50 }\nCRIT_1 { Ammo_IS.AC/5 20 - - }\n')
        TemplateDirectory(self.root).load_modern(unit,'MW')
        self.assertEqual(20,unit.sections[0].criticals[0].data)
        self.assertEqual(3,unit.sections[0].criticals[1].data)
        self.assertEqual([1],[w.critical for w in unit.weapons])
        self.assertEqual(1,engine.events.time_until_type_data(E.PLOS,unit))

    def test_legal_aerospace_type_syntax_and_none_movement_warning(self):
        for kind in (U.AERO,U.DS,U.SPHEROID_DS):
            with self.subTest(kind=kind):
                unit=self.unit()
                text=f'Type ignored {{ {MECH_TYPES[kind]} }}\nMove_Type {{ None }}\nTons {{ 90 }}\nInternals {{ 10 }}\nCRIT_1 {{ HeatSink 7 - 4 }}\n'
                load_stream(unit,io.StringIO(text),'LONGREFERENCE-FIGHTER-OVER24')
                self.assertEqual('LONGREFERENCE-',unit.template_ref)
                self.assertEqual((0,4),(unit.sections[0].criticals[0].data,unit.sections[0].criticals[0].brand))
                self.assertFalse(any(s.config for s in unit.sections))
                self.assertTrue(any("tons of 'stuff', yet 90 ton frame." in text for text in unit.construction_messages))
                self.assertEqual('LONGREFERENCE-',unit.attribute_store.writes[0]['value'])

    def test_multiline_field_type_text_does_not_select_aerospace(self):
        unit=self.unit();name='LONGREFERENCE-FIGHTER-OVER24'
        load_stream(unit,io.StringIO('Name {\nType { AeroFighter }\nCRIT_1 { HeatSink 7 - - }\n'),name,finalize=False)
        self.assertEqual(U.MECH,unit.unit_type);self.assertEqual(name[:24],unit.template_ref)
        self.assertEqual(7,unit.sections[0].criticals[0].data)
        self.assertEqual(name[:24],unit.attribute_store.writes[0]['value'])

    def test_signed_set_max_speed_and_reference_loading(self):
        for kind in (U.MECH,U.AERO):
            with self.subTest(kind=kind):
                unit=self.unit()
                text=f'Type {{ {MECH_TYPES[kind]} }}\nTons {{ 50 }}\nMax_Speed {{ -10.75 }}\n'
                load_stream(unit,io.StringIO(text),'NEGATIVE',finalize=False)
                self.assertEqual((0,0,-10.75,-10.75),(unit.max_speed,unit.template_max_speed,unit.speed,unit.desired_speed))
                (self.root/'NEGATIVE').write_text(text)
                loaded=TemplateDirectory(self.root).load_reference('NEGATIVE')
                self.assertIsNotNone(loaded)
                self.assertEqual((0,0,-10.75,-10.75),(loaded.max_speed,loaded.template_max_speed,loaded.speed,loaded.desired_speed))

    def test_nominal_gravity_preserves_fractional_cargo_limit(self):
        from entities.map import GameMap
        from physics.cargo import cargo_max_speed
        from systems.vehicle_combat import correct_speed
        unit=Mech.create_test_mech()
        unit.measured_mass=60*1024
        unit.map=GameMap(10,10);unit.map.grav=100
        unit.status|=S.UNDERSPECIAL|S.UNDERGRAVITY
        # Normal 50-ton / 60-ton load result, stored as source binary32.
        expected=49.61538314819336
        self.assertEqual(expected,cargo_max_speed(unit))
        self.assertEqual(expected,cargo_max_speed(unit))  # Warm cache.
        unit.speed=unit.desired_speed=expected
        correct_speed(unit)
        self.assertEqual((expected,expected),(unit.speed,unit.desired_speed))
        load_stream(unit,io.StringIO('Max_Speed { 64.5 }\n'),'GRAVITY',finalize=False)
        self.assertEqual((64.5,64.5,expected,expected),
                         (unit.max_speed,unit.template_max_speed,unit.speed,unit.desired_speed))

    def test_correct_speed_captures_cached_signed_limit_even_when_destroyed(self):
        from physics.cargo import cargo_max_speed,CACHE_FLAGS
        from systems.vehicle_combat import correct_speed
        for reverse in (False,True):
            unit=Mech();unit.max_speed=-10.75;unit.status|=S.DESTROYED
            unit.cached_max_speed=-9;unit.crit_status|=CACHE_FLAGS
            unit.speed=0;unit.desired_speed=-1 if reverse else 0
            correct_speed(unit)
            self.assertEqual(0,unit.max_speed)
            self.assertEqual((6,6) if reverse else (-9,-9),(unit.desired_speed,unit.speed))
            self.assertEqual(0,cargo_max_speed(unit))

    def test_historical_cached_boost_uses_live_mode_event_and_signed_result(self):
        from entities.map import GameMap
        from entities.pilot import Pilot
        from physics.cargo import cargo_max_speed,CACHE_FLAGS
        unit=Mech(unit_type=U.AERO);unit._engine=engine=GameEngine()
        unit.pilot=Pilot();unit.pilot.speed_demon=True;unit.map=GameMap(10,10);unit.map.grav=50
        unit.specials|=Specials.TRIPLE_MYOMER_TECH;unit.heat=9
        unit.status|=S.UNDERSPECIAL|S.UNDERGRAVITY;unit.status2|=S2.SPRINTING
        unit.cached_max_speed=30;unit.crit_status|=CACHE_FLAGS
        event=engine.events.schedule(60,E.MOVEMODE,lambda ev:None,unit);unit._mode_event=event
        self.assertEqual(30,cargo_max_speed(unit))
        event.cancel();self.assertEqual(50.75,cargo_max_speed(unit))
        unit.status2=0;unit.cached_max_speed=-10.75
        self.assertEqual(-10.75,cargo_max_speed(unit))

    def test_speed_writers_invalidate_a_preexisting_cargo_cache(self):
        from physics.cargo import cargo_max_speed
        from entities.crittypes import Special
        from entities.mech import MoveType,Location
        from systems.criticals import normalize_leg_actuator
        from systems.vehicle_combat import handle_rotor_damaged,correct_speed
        unit=Mech.create_test_mech();unit.measured_mass=unit.tonnage*1024
        self.assertEqual(64.5,cargo_max_speed(unit))
        normalize_leg_actuator(unit,Location.LLEG,Special.SHOULDER_OR_HIP)
        correct_speed(unit)
        self.assertEqual(32.25,cargo_max_speed(unit))
        unit=Mech(unit_type=U.VTOL,move_type=MoveType.VTOL)
        unit.max_speed=64.5;unit.speed=unit.desired_speed=64.5
        unit.measured_mass=unit.tonnage*1024
        self.assertEqual(64.5,cargo_max_speed(unit))
        handle_rotor_damaged(unit)
        self.assertEqual((53.75,53.75,53.75),(unit.max_speed,unit.speed,unit.desired_speed))
