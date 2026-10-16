import io
import unittest
from entities.mech import Mech, FireMode as F, UnitType as U
from entities.weapon import get_weapon
from entities.crittypes import i2weapon, i2ammo


class TemplateFilesTest(unittest.TestCase):
    def test_initial_section_zero_and_uppercase_numeric_critical_command(self):
        from data.template_files import load_stream
        unit=self.unit()
        load_stream(unit,io.StringIO('Armor { 12 }\ncrit_1 { HeatSink - - - }\n'),'CUSTOM',finalize=False)
        self.assertEqual(12,unit.sections[0].armor)
        self.assertEqual(0,unit.sections[0].criticals[0].type)
        with self.assertRaisesRegex(ValueError,'Section unknown not found'):
            load_stream(unit,io.StringIO('Tons { 50 }\nunknown\n'),'CUSTOM')

    def test_reference_is_case_sensitive_and_named_external_effect_is_separate(self):
        from data.template_files import load_stream,isolated_template
        unit=self.unit()
        load_stream(unit,io.StringIO('Reference { custom }\n'),'CUSTOM')
        self.assertTrue(any('reference' in message.lower() for message in unit.construction_messages))
        self.assertEqual({'service':'local object attributes','attribute':'A_MECHREF','value':'CUSTOM','delivered':True},unit.construction_external_effects[-1])
        baseline=isolated_template(unit);baseline.freq[0]=9
        self.assertEqual(0,unit.freq[0])

    def unit(self):
        from data.template_files import clear_mech
        unit=Mech();clear_mech(unit,True)
        return unit

    def test_loader_order_basename_defaults_and_explicit_crit_inventory(self):
        from data.template_files import load_stream
        unit=self.unit()
        load_stream(unit,io.StringIO('Fuel { 100 }\nType { AeroFighter }\nReference { wrong }\nUnit_Era { X }\nNose\nCRIT_1 { CL.ERLargeLaser - - }\n'),'AS7-D')
        self.assertEqual(('AS7-D',2400,2400,'Undefined'),(unit.template_ref,unit.fuel,unit.fuel_orig,unit.unit_era))
        self.assertEqual((5,5,35,35,70,140,27),(unit.computer,unit.radio,unit.scan_range,unit.tac_range,unit.lrs_range,unit.radio_range,unit.radio_type))
        self.assertEqual(1,len(unit.weapons))
        self.assertEqual(i2weapon(get_weapon('CL.ERLargeLaser').index),unit.sections[0].criticals[0].type)
        self.assertTrue(all(not slot.type for slot in unit.sections[3].criticals))

    def test_clan_item_prefix_case_preserves_source_defaults(self):
        from data.template_files import load_stream
        for name in ('CL.ERLargeLaser', 'cl.erlargelaser', 'cL.eRlargeLaser'):
            with self.subTest(name=name):
                unit = self.unit()
                load_stream(unit, io.StringIO(f'Left_Arm\nCRIT_1 {{ {name} - - - }}\n'), 'CASE')
                self.assertEqual((5, 5, 27, 35, 140),
                                 (unit.computer, unit.radio, unit.radio_type,
                                  unit.scan_range, unit.radio_range))
                self.assertEqual(5, unit.sections[0].criticals[0].brand)

    def test_field_string_bounds_reject_overflow_after_prior_writes(self):
        from data.template_files import load_stream
        for field, attribute, limit in (('Name', 'name', 30), ('Unit_Era', 'unit_era', 24), ('Unit_TRO', 'unit_tro', 24)):
            with self.subTest(field=field):
                unit = self.unit()
                load_stream(unit, io.StringIO(f'{field} {{ ' + 'x' * limit + ' }\n'), 'BOUNDS', finalize=False)
                self.assertEqual('x' * limit, getattr(unit, attribute))
                with self.assertRaisesRegex(ValueError, 'source string bounds'):
                    load_stream(unit, io.StringIO('Tons { 55 }\n' + f'{field} {{ ' + 'y' * (limit + 1) + ' }\n'), 'BOUNDS', finalize=False)
                self.assertEqual(55, unit.tonnage)
                self.assertEqual('x' * limit, getattr(unit, attribute))

    def test_mixed_mode_failure_retains_prior_writes_but_not_new_masks(self):
        from data.template_files import load_stream
        unit=self.unit();slot=unit.sections[0].criticals[0];slot.firemode=128;slot.ammomode=1
        with self.assertRaisesRegex(ValueError,'mode'):
            load_stream(unit,io.StringIO('Left_Arm\nCRIT_1 { IS.AC/5 - RearMount|unknown 4 }\n'),'X')
        self.assertEqual((i2weapon(get_weapon('IS.AC/5').index),0,128,1),(slot.type,slot.data,slot.firemode,slot.ammomode))
        self.assertEqual(0,len(unit.weapons))  # Incomplete AC5 run is not a valid mount.
        for text,expected in [('RearMount|Precision',(32,65536)),('rearMOUNT|precision',(32,65536)),('-', (0,0))]:
            load_stream(unit,io.StringIO(f'Left_Arm\nCRIT_1 {{ IS.AC/5 - {text} 4 }}\n'),'X')
            self.assertEqual(expected,(slot.firemode,slot.ammomode));self.assertEqual(4,slot.brand)

    def test_ammo_normalization_capacity_and_range_metadata(self):
        from data.template_files import load_stream
        for qty,expected,half in [(5,10,True),(15,20,False),(30,20,False),(10,10,True)]:
            unit=self.unit();unit.sections[0].criticals[1].weap_damage_flags=77
            unit.sections[0].criticals[0].desired_ammo_loc=4
            unit.sections[0].criticals[1].desired_ammo_loc=5
            load_stream(unit,io.StringIO(f'Left_Arm\nCRIT_1-2 {{ Ammo_IS.AC/5 {qty} - - }}\n'),'X')
            for slot in unit.sections[0].criticals[:2]:
                self.assertEqual(expected,slot.data);self.assertEqual(half,bool(slot.firemode&F.HALFTON_MODE))
            self.assertEqual(77,unit.sections[0].criticals[1].weap_damage_flags)
            self.assertEqual((-1,5),tuple(s.desired_ammo_loc for s in unit.sections[0].criticals[:2]))

    def test_modern_save_originals_capacity_and_mixed_mode_reload(self):
        from data.template_files import dump_locations,load_stream,dump_item
        unit=self.unit();unit.unit_type=U.MECH;sec=unit.sections[0]
        sec.armor_orig=20;sec.armor=7;sec.internal_orig=sec.internal=8
        slot=sec.criticals[0];slot.type=i2ammo(get_weapon('IS.LB5-XAC').index);slot.data=3;slot.firemode=128;slot.ammomode=1
        stream=io.StringIO();dump_locations(stream,unit)
        text=stream.getvalue();self.assertIn('20',text);self.assertIn('Halfton|LBX/Cluster',text)
        loaded=self.unit();load_stream(loaded,io.StringIO(text),'saved')
        other=loaded.sections[0].criticals[0]
        self.assertEqual((10,128,1),(other.data,other.firemode,other.ammomode))
        slot.type=i2weapon(get_weapon('IS.PPC').index)
        for other in sec.criticals[1:6]:other.type=slot.type;other.data=3;other.firemode=128;other.ammomode=1
        self.assertEqual(3,dump_item(io.StringIO(),unit,0,0))

    def test_unsafe_ranges_rejected_before_write_and_unknown_fields_distinct(self):
        from data.template_files import load_stream
        for text,message in [('Left_Arm\nCRIT_12-13 { HeatSink - - - }\n','bounds'),('Left_Arm\nCRIT_-1 { HeatSink - - - }\n','bounds'),('unknown\n','New template loading system: X is invalid template file'),('Left_Arm\nunknown\n','Section unknown not found')]:
            unit=self.unit()
            with self.assertRaisesRegex(ValueError,message):load_stream(unit,io.StringIO(text),'X')
            self.assertTrue(all(not slot.type for slot in unit.sections[0].criticals))
