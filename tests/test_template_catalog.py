import io
import errno
import tempfile
import unittest
from pathlib import Path
from entities.mech import Mech
from entities.crittypes import Special, i2special
from data.template_files import clear_mech, load_stream


def symlink_or_skip(test, link, target, *, directory=False):
    """Skip only the attempted symlink capability; other assertions still run."""
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        if (isinstance(exc, NotImplementedError) or getattr(exc, 'winerror', None) == 1314
                or getattr(exc, 'errno', None) in (errno.EPERM, errno.ENOTSUP)):
            test.skipTest(f'Host cannot create symlinks: {exc}')
        raise


class CatalogCorrectionsTest(unittest.TestCase):
    def load(self, text):
        unit = Mech(); clear_mech(unit, True)
        load_stream(unit, io.StringIO(text), 'TEST', finalize=False)
        return unit

    def test_central_crlf_multiline_and_mixed_parity(self):
        text = 'Type { Mech }\nName { First\nsecond\nlast }\nLeft_Arm\nArmor { 14 }\n'
        expected = self.load(text)
        self.assertEqual('First\r\nsecond\r\nlast ', expected.name)
        for variant in (text.replace('\n', '\r\n'), text.replace('second\n', 'second\r\n')):
            actual = self.load(variant)
            self.assertEqual((expected.name, 14), (actual.name, actual.sections[0].armor))

    def test_interior_cr_and_last_byte_quirk_remain(self):
        with self.assertRaisesRegex(ValueError, 'Error while loading: Section'):
            self.load('Tons { 55 }\nLeft_\rArm\n')
        with self.assertRaisesRegex(ValueError, 'Error while loading: Section'):
            self.load('Tons { 55 }\nLeft_Arm')
        self.assertEqual('valu', self.load('Name { value}\r\n').name)

    def test_c2_standard_improved_and_truncation(self):
        from systems.repairs import sub_magic
        for speed, slots, improved, mp in ((64.5,8,0,4),(86,5,0,5),(64.49,8,0,3),
                (64.51,8,0,4),(0,4,0,0),(64.5,5,1,2),(64.49,16,1,5)):
            with self.subTest(speed=speed, slots=slots, improved=improved):
                u = Mech(); clear_mech(u, True); u.max_speed=speed; u.specials2=128*improved
                for slot in [s for sec in u.sections[:2] for s in sec.criticals][:slots]:
                    slot.type=i2special(Special.JUMP_JET)
                sub_magic(u)
                self.assertEqual((mp,10.75*mp),(u.jump_mp,u.jump_speed))


class CatalogStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.up=self.base/'up';self.custom=self.base/'custom'
        self.up.mkdir();self.custom.mkdir()
        (self.up/'WVR-6R').write_text('Tons { 55 }\nMax_Speed { 86 }\n')

    def directory(self, root=None):
        from data.template_catalog import CatalogDirectory
        return CatalogDirectory(root or self.custom,self.up)

    def test_shadow_origin_and_immutable_replay_baselines(self):
        from core.game_loop import GameEngine
        from systems.repairs import magic
        d=self.directory();u=Mech();u._engine=GameEngine()
        self.assertTrue(d.loadnew(u,'wvr-6r'));self.assertEqual('upstream',u.template_origin)
        (self.custom/'WVR-6R').write_text('Tons { 40 }\nMax_Speed { 32.25 }\n');d.reset()
        v=Mech();v._engine=u._engine
        self.assertTrue(d.loadnew(v,'WVR-6R'));self.assertEqual(40,v.tonnage)
        self.assertEqual(2,len(d.ambiguities));self.assertEqual(2,len(d.listing()))
        self.assertTrue(d.restore(u));self.assertEqual((55,'upstream'),(u.tonnage,u.template_origin))
        self.assertEqual(40,v.tonnage)
        self.assertTrue(magic(v));self.assertEqual(32.25,v.max_speed)
        self.assertTrue(d.loadnew(v,'WVR-6R',origin='upstream'));self.assertEqual(55,v.tonnage)

    def test_catalog_load_keeps_source_case_sensitive_channel_reset(self):
        d=self.directory();u=Mech()
        self.assertTrue(d.loadnew(u,'WVR-6R'));u.freq=[7]*16
        self.assertTrue(d.loadnew(u,'wvr-6r'));self.assertEqual([0]*16,u.freq)

    def test_mutation_guards_overlap_traversal_symlinks(self):
        for root in (self.up,self.up/'child',self.base):
            with self.assertRaisesRegex(ValueError,'overlap'):self.directory(root)
        d=self.directory()
        with self.assertRaises(ValueError):d.path('../up/WVR-6R')
        with self.subTest(capability='directory symlink traversal'):
            symlink_or_skip(self,self.custom/'link',self.up,directory=True)
            with self.assertRaises(ValueError):d.path('link/WVR-6R')
        with self.assertRaisesRegex(ValueError,'read-only'):d.mutation_path('WVR-6R',origin='upstream')
        self.assertEqual(self.custom/'CUSTOM',d.mutation_path('CUSTOM'))


class DependencyTest(unittest.TestCase):
    def setUp(self):
        import subprocess
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        def git(*args):return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.DEVNULL)
        self.git=git;git('init');(self.root/'TEST').write_bytes(b'Type { Mech }\nTons { 50 }\n')
        git('add','TEST');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
        self.lock={'revision':git('rev-parse','HEAD').decode().strip(),'url':'fixture','directory':'fixture'}

    def test_pin_eol_content_missing_and_revision(self):
        from data.template_dependency import verify
        self.assertEqual('verified',verify(self.root,lock=self.lock)['outcome'])
        p=self.root/'TEST';p.write_bytes(p.read_bytes().replace(b'\n',b'\r\n'));before=p.read_bytes()
        self.assertEqual('verified-EOL-only',verify(self.root,lock=self.lock)['outcome']);self.assertEqual(before,p.read_bytes())
        p.write_bytes(before+b'Tons { 60 }\r\n')
        self.assertEqual('drift-error',verify(self.root,lock=self.lock)['outcome'])
        p.unlink();self.assertEqual(['TEST'],verify(self.root,lock=self.lock)['missing_tracked'])
        self.assertEqual('revision-error',verify(self.root,lock=self.lock|{'revision':'0'*40})['outcome'])
        self.assertEqual('missing-error',verify(self.root/'missing',lock=self.lock)['outcome'])

    def test_disabled_and_path_precedence(self):
        from data.template_dependency import resolve_catalog
        env={'BTMUX_TEMPLATE_CATALOG':'environment'}
        self.assertIsNone(resolve_catalog(False,environ=env))
        self.assertIsNone(resolve_catalog(None,environ=env))
        self.assertEqual((Path.cwd()/'environment').resolve(),resolve_catalog(True,environ=env))
        self.assertEqual((Path.cwd()/'explicit').resolve(),resolve_catalog('explicit',environ=env))
        self.assertEqual(Path(__file__).resolve().parents[1]/'btmux-mechs',resolve_catalog(True,environ={}))


class AuditTest(unittest.TestCase):
    def test_audit_reports_long_name_reachable_through_source_fallback(self):
        from data.template_catalog_audit import audit
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);name='A'*35
            (root/name).write_text('Type { Mech }\nTons { 50 }\n')
            row=audit(root)['files'][0]
            self.assertTrue(row['discoverable'])
            self.assertEqual(name,row['reference_winner'])
            self.assertTrue(row['selected_by_reference'])

    def test_complete_inventory_failures_collisions_deep_files_and_isolation(self):
        from data.template_catalog_audit import audit
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'deep/next').mkdir(parents=True);(root/'.git').mkdir()
            (root/'A').write_text('Type { Mech }\nTons { 50 }\nLeft_Arm\nCRIT_1 { IS.MediumLaser - - - }\n')
            (root/'deep/a').write_text('Type { nonsense }\n');(root/'deep/next/LATE').write_text('Type { Vehicle }\nTons { 20 }\n')
            (root/'.git/ignored').write_text('bad')
            with self.subTest(capability='audit symlink isolation'):
                symlink_or_skip(self,root/'escape',Path(temp).resolve().parent,directory=True)
            report=audit(root)
            self.assertEqual((3,2,1,1),(report['candidates'],report['successes'],report['failures'],len(report['ambiguities'])))
            self.assertEqual('complete-with-failures',report['outcome']);self.assertFalse(report['verified'])
            late=next(row for row in report['files'] if row['path']=='deep/next/LATE')
            self.assertFalse(late['discoverable']);self.assertEqual(0,late['state']['mounts'])
            self.assertEqual(report,audit(root,reverse=True))


class SinkCapacityTranslationTest(unittest.TestCase):
    def test_modern_flags_do_not_reinterpret_source_dissipation(self):
        from entities.mech import Specials
        for tech in ('Clan','DoubleHS'):
            for fields in (f'Heat_Sinks {{ 34 }}\nSpecials {{ {tech} }}\n',
                           f'Specials {{ {tech} }}\nHeat_Sinks {{ 34 }}\n'):
                with self.subTest(fields=fields):
                    u=Mech();clear_mech(u,True)
                    load_stream(u,io.StringIO(fields),'SINKS',finalize=False)
                    self.assertTrue(u.specials & (Specials.CLAN_TECH|Specials.DOUBLE_HEAT_TECH))
                    self.assertEqual((34,17),(u.real_num_sinks,u.num_sinks))
                    with self.assertRaises(ValueError):load_stream(u,io.StringIO('BadSection\n'),'SINKS',finalize=False)
                    self.assertEqual(34,u.real_num_sinks)

    def test_legacy_flags_do_not_reinterpret_source_dissipation(self):
        from entities.mech import Specials
        from data.template_directory import load_legacy_stream
        u=Mech();clear_mech(u,True)
        text=f'50 20 40 20 34 64.5 0 {int(Specials.DOUBLE_HEAT_TECH)}\n'+('20 5 0 0\n'+'0 0 0\n'*12)*8+'0 0\n55\n'
        load_legacy_stream(u,io.StringIO(text),'SINKS')
        self.assertEqual((34,17,55),(u.real_num_sinks,u.num_sinks,u.radio_range))


from tests.movement_fixture import MovementTestCase


class CatalogNavalConsumerTest(MovementTestCase):
    def test_surface_hull_and_foil_can_set_speed_and_heading(self):
        from entities.mech import UnitType,MoveType
        from entities.map import WATER
        from systems import movement_commands as commands
        self.unit.unit_type=UnitType.VEH_NAVAL;self.unit.terrain=WATER;self.unit.z=0
        for move in (MoveType.HULL,MoveType.FOIL):
            self.unit.move_type=move
            self.assertFalse(commands.in_water(self.unit))  # Keep strict submerged consumers.
            self.assertTrue(commands.speed(self.engine,self.unit,'10.75')[0])
            self.assertTrue(commands.heading(self.engine,self.unit,'120')[0])
            self.assertEqual((10.75,120),(self.unit.desired_speed,self.unit.desired_facing))

    def test_grounded_or_above_water_craft_are_still_rejected(self):
        from entities.mech import UnitType,MoveType
        from entities.map import WATER,GRASSLAND
        from systems import movement_commands as commands
        self.unit.unit_type=UnitType.VEH_NAVAL;self.unit.move_type=MoveType.HULL
        for terrain,z in ((GRASSLAND,0),(WATER,1)):
            self.unit.terrain=terrain;self.unit.z=z
            self.assertFalse(commands.speed(self.engine,self.unit,'10.75')[0])
            self.assertFalse(commands.heading(self.engine,self.unit,'120')[0])


class CatalogAuxiliaryStorageTest(unittest.TestCase):
    setUp=CatalogStorageTest.setUp

    def test_map_storage_cannot_create_or_write_inside_catalog(self):
        from unittest.mock import patch
        from tools.construction_templates import ConstructionSession
        # Dependency verification has its own real-Git tests; isolate routing.
        with patch('data.template_dependency.require_verified'):
            doc={'construction':{'catalog':str(self.up),'root':str(self.custom)},
                 'file_root':str(self.up/'maps'),'actions':[]}
            with self.assertRaisesRegex(ValueError,'overlap'):ConstructionSession(doc)
            self.assertFalse((self.up/'maps').exists())
            maps=self.base/'maps';maps.mkdir()
            with self.subTest(capability='map storage symlink protection'):
                symlink_or_skip(self,maps/'WVR-6R',self.up/'WVR-6R')
                doc['file_root']=str(maps)
                doc['files']={'WVR-6R':{'text':'do not overwrite'}}
                before=(self.up/'WVR-6R').read_bytes()
                with self.assertRaisesRegex(ValueError,'read-only'):ConstructionSession(doc)
                self.assertEqual(before,(self.up/'WVR-6R').read_bytes())
