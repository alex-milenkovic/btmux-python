"""Focused regression checks for the AUD-TEMPLATES repair delta."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.attributes import AttributeStore
from core.events import EventType as E
from core.game_loop import GameEngine
from data.construction_catalog import Catalog, source_weapon, valid_source_part
from data.template_catalog import CatalogDirectory
from data.template_directory import TemplateDirectory, load_legacy_stream
from data.template_files import clear_mech, load_stream
from entities.crittypes import Special, i2ammo, i2special, i2weapon
from entities.mech import Mech, FireMode as F, UnitType as U, Specials as S
from entities.weapon import get_weapon
from systems.construction_editor import Editor


class TemplateRepairTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def unit(self):
        unit=Mech();clear_mech(unit,True)
        return unit

    def test_clear_actual_mirrors_and_slot_bytes_preserves_other_events(self):
        from entities.vehicle import Vehicle
        for unit in (Mech(),Vehicle()):
            unit._engine=GameEngine();unit.masc_counter=8
            unit.crew_stunned=unit.tail_rotor_destroyed=unit.dumping=unit.unjamming=True
            if type(unit) is Mech:unit.turret_jammed=unit.turret_locked=True
            unit._engine.events.schedule(30,E.VEHICLE_BURN,lambda event:None,unit)
            unit._engine.events.schedule(30,E.BLINDREC,lambda event:None,unit)
            clear_mech(unit,False)
            self.assertFalse(any((unit.masc_counter,unit.crew_stunned,unit.tail_rotor_destroyed,
                                  unit.dumping,unit.unjamming,unit.turret_jammed,unit.turret_locked)))
            self.assertTrue(all(c.desired_ammo_loc==0 for s in unit.sections for c in s.criticals))
            self.assertFalse(unit._engine.has_event(E.VEHICLE_BURN,unit))
            self.assertTrue(unit._engine.has_event(E.BLINDREC,unit))

    def test_parser_skips_only_comment_line_and_numeric_crits_are_uppercase(self):
        unit=self.unit()
        text='Comment {\nTons { 50 }\nCRIT_bad {\nArmor { 7 }\ncrit_1 { HeatSink 4 - - }\nCRIT_3-1 { HeatSink 7 - - }\n'
        load_stream(unit,io.StringIO(text),'A',finalize=False)
        self.assertEqual((50,7),(unit.tonnage,unit.sections[0].armor))
        self.assertEqual([0,0,i2special(Special.HEAT_SINK)],[s.type for s in unit.sections[0].criticals[:3]])
        self.assertEqual(7,unit.sections[0].criticals[2].data)
        self.assertEqual([0,0,-1],[s.desired_ammo_loc for s in unit.sections[0].criticals[:3]])

    def test_reference_writes_persist_and_restore_retains_channels(self):
        custom=self.root/'custom';upstream=self.root/'upstream'
        (custom/'Sub').mkdir(parents=True);upstream.mkdir()
        (custom/'Sub'/'A').write_text('Tons { 50 }\nReference { A }\n')
        (upstream/'UP').write_text('Tons { 50 }\n')
        directory=CatalogDirectory(custom,upstream);unit=self.unit()
        self.assertTrue(directory.loadnew(unit,'Sub/A'))
        self.assertEqual(['A','A'],[row['value'] for row in unit.attribute_store.writes])
        unit.freq[0]=22;unit.tics[0].add(3)
        self.assertTrue(directory.restore(unit))
        self.assertEqual((22,{3}),(unit.freq[0],unit.tics[0]))
        store=AttributeStore(custom/'.state'/'attributes.json')
        self.assertEqual('A',store.get(unit._id,'A_MECHREF'))
        recreated=self.unit();recreated._id=unit._id
        self.assertTrue(CatalogDirectory(custom,upstream).restore(recreated))
        self.assertEqual('A',recreated.template_ref)
        self.assertTrue(directory.loadnew(unit,'UP'))
        self.assertEqual('UP',store.get(unit._id,'A_MECHREF'))
        self.assertFalse((upstream/'.state').exists())
        unit.freq[0]=9
        (upstream/'UP').unlink();directory.reset()
        self.assertFalse(directory.loadnew(unit,'UP'))
        self.assertEqual(9,unit.freq[0])
        self.assertEqual("No matching file for 'UP'.",unit.channel_requests[-1]['text'])

    def test_plain_directory_same_name_baselines_are_isolated(self):
        path=self.root/'A';path.write_text('Tons { 50 }\n')
        directory=TemplateDirectory(self.root);first=self.unit();second=self.unit()
        engine=GameEngine();first._engine=second._engine=engine
        self.assertTrue(directory.loadnew(first,'A'))
        path.write_text('Tons { 75 }\n');self.assertTrue(directory.loadnew(second,'A'))
        self.assertEqual((50,75),(first._catalog_baseline.tonnage,second._catalog_baseline.tonnage))
        first.sections[0].internal=0
        self.assertGreater(first._catalog_baseline.sections[0].internal,0)
        from systems.repairs import magic
        self.assertTrue(magic(first))
        self.assertEqual(50,first.tonnage)

    def test_mw_startup_macro_queues_another_one_second_event(self):
        unit=self.unit();engine=GameEngine();unit._engine=engine
        engine.events.schedule(100,E.PLOS,lambda event:None,unit)
        unit.turn_damage=19;unit.num_seen=5
        load_stream(unit,io.StringIO('Type { Mechwarrior }\n'),'MW')
        self.assertEqual((True,0,0),(unit.is_started,unit.turn_damage,unit.num_seen))
        self.assertEqual(2,engine.events.count_type(E.PLOS))
        self.assertEqual(1,engine.events.time_until_type_data(E.PLOS,unit))
        (self.root/'MW').write_text('Type { Mechwarrior }\n')
        self.assertTrue(TemplateDirectory(self.root).loadnew(unit,'MW',wrapper=True))
        self.assertEqual(0,engine.events.count_data(unit))

    def test_aerospace_profile_and_authoritative_fighter_layout(self):
        unit=self.unit()
        text='Type { AeroFighter }\nTons { 90 }\nNose\nInternals { 10 }\nCRIT_1 { HeatSink 7 - 4 }\n'
        load_stream(unit,io.StringIO(text),'LONGREFERENCE-FIGHTER')
        self.assertEqual('LONGREFERENCE-',unit.template_ref)
        self.assertEqual((0,4),(unit.sections[0].criticals[0].data,unit.sections[0].criticals[0].brand))
        self.assertFalse(any(s.config for s in unit.sections))
        self.assertTrue(any("tons of 'stuff', yet 90 ton frame." in s for s in unit.construction_messages))
        from data.template_files import load_template
        load_template(unit,Path('btmux-mechs/CHP-W5'))
        self.assertEqual([24,15,15,30,16,20],[s.armor for s in unit.sections[:6]])
        self.assertEqual(11,len(unit.weapons))
        self.assertEqual(86,unit.template_max_speed)

    def test_legacy_raw_failure_and_opaque_cargo(self):
        lines=['50 20 40 20 10 64.5 0 0']
        for _ in range(8):lines+=['1 1 0 0']+['946 0 0']+['0 0 0']*11
        unit=self.unit();load_legacy_stream(unit,io.StringIO('\n'.join(lines)),'OLD')
        self.assertTrue(valid_source_part(946));self.assertEqual(946,unit.sections[0].criticals[0].type)
        lines[2]='192 5 32';unit.sections[0].criticals[0].data=17
        with self.assertRaisesRegex(ValueError,'Invalid datatype at 0/0!'):
            load_legacy_stream(unit,io.StringIO('\n'.join(lines)),'OLD')
        slot=unit.sections[0].criticals[0]
        self.assertEqual((0,192,17),(slot.type,slot.invalid_source_type,slot.data))
        with self.assertRaisesRegex(ValueError,'Insufficient data reading section 0!'):
            load_legacy_stream(unit,io.StringIO(lines[0]),'OLD')

    def test_editor_weapon_guards_and_sink_capacity(self):
        unit=Mech.create_test_mech();editor=Editor(7,{'unit':unit});editor.target='unit'
        self.assertTrue(editor.execute('addweap','IS.AC/5 LT 1 2 3 4')['ok'])
        slot=unit.sections[2].criticals[0]
        for fire,data,recycle in ((F.DESTROYED_MODE,0,0),(0,3,0),(0,0,4)):
            slot.firemode=fire;slot.data=data;slot.ammomode=9;unit.sections[2].recycle=recycle
            self.assertEqual(['Invalid Weapon #!'],editor.execute('firemode','0 P')['messages'])
            self.assertEqual(9,slot.ammomode)
        slot.type=i2ammo(get_weapon('IS.MediumLaser').index);slot.data=7
        self.assertFalse(editor.execute('restock','LT 1')['ok']);self.assertEqual(7,slot.data)
        capacity=unit.real_num_sinks
        editor.execute('addtech','DoubleHS');self.assertEqual(capacity,unit.real_num_sinks)
        editor.execute('deltech','All');self.assertEqual(capacity,unit.real_num_sinks)
        self.assertTrue(editor.execute('setradio','2\nextra')['ok'])
        self.assertEqual(['Invalid tech: Available techs:','\tAll','\tCase'],editor.execute('deltech','bad')['messages'][:3])

    def test_source_error_audiences_ammo_and_corrected_speed(self):
        unit=self.unit();unit._engine=GameEngine();messages=[]
        with self.assertRaises(ValueError):load_stream(unit,io.StringIO('unknown\n'),'A',notify=messages.append)
        self.assertEqual(['New template loading system: A is invalid template file.'],messages)
        self.assertEqual([],unit._engine.effects.channels)
        load_stream(unit,io.StringIO('Tons { 50 }\nLeft_Arm\nCRIT_1 { Ammo_IS.AC/5 5 - - }\n'),'A',finalize=False)
        self.assertEqual(f'Invalid ammo crit for IS.AC/5 in #{unit._id} A (5/10)',unit._engine.effects.channels[-1]['text'])
        unit.desired_speed=unit.speed=90
        load_stream(unit,io.StringIO('Max_Speed { 21.5 }\n'),'A',finalize=False)
        self.assertLessEqual(unit.speed,21.5);self.assertLessEqual(unit.desired_speed,21.5)
        self.assertEqual(21.5,unit.template_max_speed)

    def test_laserams_weight_catalog_cursor_and_float_omission(self):
        from systems.construction_weight import ammo_weight,weight
        from data.templates import computers_radio_range
        from data.template_files import save_template
        unit=Mech();unit.sections[0].internal=unit.sections[0].internal_orig=10
        for name in ('IS.LaserAMS','CL.LaserAMS'):
            slot=unit.sections[0].criticals[0];slot.type=i2ammo(get_weapon(name).index);slot.data=12
            self.assertEqual(512,ammo_weight(unit))
        unit.sections[0].criticals[0].type=0;unit.radio=1;unit.computer=1
        self.assertEqual(64,computers_radio_range(unit));unit.radio_range=64
        target=self.root/'saved';save_template(unit,'A',target)
        self.assertNotIn('Radio_Range',target.read_text())
        messages=weight(unit,1)['messages']
        self.assertTrue(any('rating)' in s for s in messages));self.assertTrue(any('offset:' in s for s in messages))
        catalog=Catalog();cursor=catalog.match_result('long','absent')['cursor']
        self.assertEqual(len(catalog.sorted['long']),cursor)
        self.assertEqual(cursor+1,catalog.match_result('long','absent',cursor)['cursor'])
        catalog.names(946,3);self.assertEqual('No index for 946/0',catalog.messages[-1])
        self.assertEqual('A_ML',catalog.short_name(271))

    def test_scanner_skips_stat_failures_and_oversized_paths(self):
        for name in ('good','bad','long'): (self.root/name).write_text('')
        directory=TemplateDirectory(self.root);stat=Path.stat;encode=os.fsencode
        def checked_stat(path,*args,**kwargs):
            if path.name=='bad':raise OSError('fixture stat failure')
            return stat(path,*args,**kwargs)
        with patch.object(Path,'stat',checked_stat),patch('data.template_directory.os.fsencode',side_effect=lambda text:b'x'*1000 if text=='long' else encode(text)):
            self.assertTrue(directory.scan())
        self.assertEqual([('good','')],directory.entries)

    def test_payload_excludes_destroyed_and_bounds_legal_inventory(self):
        from systems.parts import payloadlist
        from data.construction_catalog import runtime_part
        unit=Mech(unit_type=U.BSUIT)
        entries=sorted((entry for entry in Catalog().entries.values() if entry.brand==0 and 1<=entry.source_part_id<385),key=lambda entry:len(entry.vlong),reverse=True)
        for slot,entry in zip((c for s in unit.sections for c in s.criticals),entries):slot.type=runtime_part(entry.source_part_id)
        self.assertEqual(2047,len(payloadlist(unit).encode()))
        unit=Mech();slot=unit.sections[0].criticals[0];slot.type=i2weapon(get_weapon('IS.SmallLaser').index)
        slot.firemode=F.DESTROYED_MODE;self.assertEqual('',payloadlist(unit))

    def test_catalog_report_follows_parser_and_excludes_local_state(self):
        from data.template_catalog_audit import failure_detail,transformations
        from data.template_dependency import inventory
        from data.template_files import TemplateError
        (self.root/'A').write_text('Tons { 50 }\n')
        unit=self.unit();TemplateDirectory(self.root).load_modern(unit,'A')
        store=AttributeStore(self.root/'.state'/'attributes.json')
        self.assertEqual('A',store.get(unit._id,'A_MECHREF'))
        recreated=self.unit();recreated._id=unit._id
        self.assertTrue(TemplateDirectory(self.root).restore(recreated))
        self.assertEqual('A',recreated.template_ref)
        candidates,exclusions=inventory(self.root)
        self.assertEqual(['A'],candidates)
        self.assertEqual([{'path':'.state','reason':'local template state'}],exclusions)
        detail=failure_detail(TemplateError('Unable to find absent'),'')
        self.assertEqual(('unsupported-source-equipment','absent'),(detail['classification'],detail['cause']))
        detail=failure_detail(ValueError('Critical slot bounds error'),'CRIT_3-1 { HeatSink 0 - - }\nCRIT_0 { HeatSink 0 - - }\n')
        self.assertEqual('CRIT_0',detail['cause'])
        notes=transformations(unit,'Left_Arm\ncrit_1 { Ammo_IS.AC/5 99 - - }\n')
        self.assertFalse(any('.ammo' in row['field'] for row in notes))
