"""Historical fighter layout uses original design bytes and physical mounts."""
import io
import unittest
from data.template_dependency import resolve_catalog
from data.template_files import clear_mech, load_stream, dump_locations
from data.templates import fill_default_criticals
from entities.mech import Mech, UnitType as U
from entities.crittypes import Special, i2special, crits_in_loc
from systems.damage_commands import section_names, section_index


def chippewa():
    unit=Mech(); clear_mech(unit,True)
    with (resolve_catalog(True)/'CHP-W5').open() as stream:
        load_stream(unit,stream,'CHP-W5')
    return unit


class FighterLayoutTests(unittest.TestCase):
    def test_loaded_fighter_status_reports_numeric_template_types(self):
        from systems.observation import unit_report
        unit=chippewa()
        report=unit_report(unit,unit,0)
        self.assertEqual((report['type'],report['movement']),('AERO','FLY'))

    def test_previously_rejected_original_sl17_loads(self):
        unit=Mech();clear_mech(unit,True)
        with (resolve_catalog(True)/'SL-17').open() as stream:
            load_stream(unit,stream,'SL-17')
        self.assertEqual(unit.unit_type,U.AERO)
        self.assertEqual([s.internal_orig for s in unit.sections[:6]],[10]*6)
        self.assertTrue(unit.weapons)

    def test_original_design_loads_all_six_sections_and_eleven_mounts(self):
        unit=chippewa()
        self.assertEqual(section_names(unit),('Nose','Left Wing','Right Wing','Fuselage','Cockpit','Engine'))
        self.assertEqual([s.armor for s in unit.sections[:6]],[24,15,15,30,16,20])
        self.assertEqual([s.internal for s in unit.sections[:6]],[10]*6)
        self.assertEqual([(w.section,w.critical) for w in unit.weapons],
                         [(0,i) for i in range(5)]+[(1,0),(1,2),(2,0),(2,2),(5,0),(5,1)])
        self.assertEqual([s.data for s in unit.sections[3].criticals[:5]],[8,8,8,8,15])
        self.assertTrue(all(not s.type for s in unit.sections[5].criticals[2:]))
        self.assertEqual(unit.si,0); self.assertFalse(unit.is_destroyed)

    def test_builder_defaults_are_separate_from_load(self):
        unit=Mech(); unit.unit_type=U.AERO; fill_default_criticals(unit)
        kinds=(Special.LIFE_SUPPORT,Special.SENSORS,Special.COCKPIT,Special.SENSORS,Special.LIFE_SUPPORT)
        self.assertEqual([s.type for s in unit.sections[4].criticals[:5]],[i2special(k) for k in kinds])
        self.assertEqual([s.type for s in unit.sections[5].criticals],
                         [i2special(Special.ENGINE if i in (2,10) else Special.HEAT_SINK) for i in range(12)])
        self.assertTrue(all(not s.type for sec in unit.sections[:4] for s in sec.criticals))
        self.assertEqual(crits_in_loc(unit,4),5)
        self.assertEqual(section_index(unit,'Cockpit'),4)
        self.assertEqual(section_index(unit,'Engine'),5)

    def test_design_dump_preserves_depleted_fuselage_and_original_armor(self):
        unit=chippewa();unit.sections[0].armor=19;unit.sections[3].armor=0
        out=io.StringIO();dump_locations(out,unit)
        other=Mech();clear_mech(other,True);other.unit_type=U.AERO
        load_stream(other,io.StringIO(out.getvalue()),'saved')
        self.assertEqual([s.armor for s in other.sections[:6]],[24,15,15,30,16,20])
        self.assertEqual([(w.section,w.critical,w.weapon_idx) for w in other.weapons],
                         [(w.section,w.critical,w.weapon_idx) for w in unit.weapons])

    def test_dropship_names_and_slot_capacity_stay_separate(self):
        unit=Mech();unit.unit_type=U.DS
        self.assertEqual(section_names(unit),('Right Wing','Left Wing','Left Rear Wing','Right Rear Wing','Aft','Nose'))
        self.assertEqual(crits_in_loc(unit,4),12)
