import tempfile
import unittest
from pathlib import Path
from entities.mech import Mech,UnitType as U,MechStatus as S
from core.game_loop import GameEngine


class TemplateDirectoryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_cache_depth_case_keys_and_no_rescan_on_miss(self):
        from data.template_directory import TemplateDirectory
        (self.root/'Custom/nested').mkdir(parents=True)
        (self.root/'Custom/AS7-D').write_text('')
        (self.root/'Custom/nested/AS7-K').write_text('')
        directory=TemplateDirectory(self.root)
        self.assertEqual(self.root.resolve()/'Custom/AS7-D',directory.lookup('as7-d'))
        self.assertIsNone(directory.lookup('AS7-K'))
        self.assertIsNotNone(directory.lookup('Custom/nested/AS7-K'))
        (self.root/'new').write_text('')
        self.assertIsNone(directory.lookup('new'));directory.reset();self.assertIsNotNone(directory.lookup('new'))
        (self.root/'new').unlink();self.assertIsNone(directory.lookup('new'))

    def test_exact_reference_channels_and_identity_and_failed_load_state(self):
        from data.template_directory import TemplateDirectory
        directory=TemplateDirectory(self.root)
        (self.root/'AS7-D').write_text('Name { Atlas }\nTons { 100 }\n')
        unit=Mech();unit.template_ref='AS7-D';unit.tics[0].add(2);unit.freq=[7]*16;unit.chantitle=['hi']*16
        unit.heat=45;unit.status=S.STARTED;unit.x=3;unit._engine=GameEngine();identity=unit._id
        self.assertTrue(directory.loadnew(unit,'AS7-D'))
        self.assertEqual((identity,3,0,1),(unit._id,unit.x,unit.heat,unit.brief))
        self.assertEqual({2},unit.tics[0]);self.assertEqual(7,unit.freq[0])
        self.assertTrue(directory.loadnew(unit,'as7-d'));self.assertEqual(set(),unit.tics[0])
        self.assertFalse(directory.loadnew(unit,'missing'))
        self.assertEqual((0,'',[]),(unit.tonnage,unit.template_ref,unit.weapons))

    def test_baseline_isolation_and_save_invalidation_precedes_bad_arguments(self):
        from data.template_directory import TemplateDirectory
        directory=TemplateDirectory(self.root);(self.root/'A').write_text('Tons { 50 }\n')
        first=directory.load_reference('A');first.sections[0].internal_orig=999
        self.assertNotEqual(999,directory.load_reference('A').sections[0].internal_orig)
        self.assertIsNotNone(directory.entries)
        with self.assertRaises(ValueError):directory.save(first,'')
        self.assertIsNone(directory.entries)
        self.assertIsNone(directory.load_reference('missing'));self.assertEqual('',directory.reference_key)

    def test_legacy_source_namespace_class4_permutation_and_current_save(self):
        from data.template_directory import load_legacy_stream,save_legacy
        from data.template_files import clear_mech
        from data.construction_catalog import runtime_part
        import io
        lines=['50 20 40 20 10 64.5 0 4196']
        for i in range(8):lines+=[f'{i+1} {i+2} 0 4']+['79 0 32']+['0 0 0']*11
        lines+=['0 0']
        unit=Mech();clear_mech(unit,True);unit.unit_type=U.SPHEROID_DS
        load_legacy_stream(unit,io.StringIO('\n'.join(lines)),'old')
        self.assertEqual((4,5,6),(unit.sections[4].armor,unit.sections[5].armor,unit.sections[3].armor))
        self.assertEqual((0,80),(unit.specials,unit.radio_range))
        self.assertEqual(runtime_part(79),unit.sections[0].criticals[0].type)
        unit.sections[0].armor=7
        path=self.root/'saved';save_legacy(unit,path)
        self.assertEqual('7 2 0 0',path.read_text().splitlines()[1])
        self.assertEqual('79 0 32',path.read_text().splitlines()[2])
        for specials,expected in ((32,0),(33,1)):
            lines[0]=f'50 20 40 20 10 64.5 0 {specials}'
            load_legacy_stream(unit,io.StringIO('\n'.join(lines+['55'])),'old')
            self.assertEqual((expected,55),(unit.specials,unit.radio_range))

    def test_load_wrapper_cancels_all_events_restore_only_burning(self):
        from data.template_directory import TemplateDirectory
        from core.events import EventType
        directory=TemplateDirectory(self.root);(self.root/'A').write_text('Tons { 50 }\n')
        unit=Mech();unit._engine=GameEngine()
        for wrapper in (False,True):
            unit._engine.events.schedule(100,EventType.VEHICLE_BURN,lambda event:None,unit)
            unit._engine.events.schedule(100,EventType.BLINDREC,lambda event:None,unit)
            self.assertTrue(directory.loadnew(unit,'A',wrapper=wrapper))
            self.assertEqual(0 if wrapper else 1,unit._engine.events.count_data(unit))
