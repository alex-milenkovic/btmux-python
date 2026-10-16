import unittest
from entities.mech import Mech, UnitType
from systems.armor_display import condition, armor_field, render_template, diagram_family, armor_display, plain

class ArmorTests(unittest.TestCase):
    def setUp(self):
        self.unit=Mech.create_test_mech('display')
        self.section=self.unit.sections[0]
        self.section.internal=10
        self.section.armor_orig=99

    def test_condition_boundaries(self):
        for current,level in [(90,0),(89,1),(70,1),(69,2),(45,2),(44,3),(1,3),(0,4)]:
            self.section.armor=current
            self.assertEqual(level,condition(self.unit,0,'front')[0])
            self.assertEqual('OoxX*?'[level]*2,plain(armor_field(self.unit,0)))

    def test_owner_width_division_and_destroyed(self):
        self.section.armor=1234
        self.assertEqual('34',plain(armor_field(self.unit,0,owner=True)))
        self.section.armor=11
        self.assertEqual('2',plain(armor_field(self.unit,0,owner=True,width=1,divide=True)))
        self.assertEqual(23,len(plain(armor_field(self.unit,0,owner=True,width=30))))
        self.section.internal=0
        self.section.armor=0
        self.assertEqual('  ',armor_field(self.unit,0))
        self.assertEqual('**',plain(armor_field(self.unit,0,show_destroyed=True)))

    def test_custom_conditionals_keys_and_newlines(self):
        self.unit.sections[1].internal=0
        self.assertEqual(' AB&',plain(render_template(self.unit,'7 @0A!01B&&',True)))
        self.section.internal=0
        self.assertEqual('   &',plain(render_template(self.unit,'7 @0A!01B&&',True)))
        self.assertEqual('Key a\r\n    b',plain(render_template(self.unit,'1 a\n7 b',False)))

    def test_all_weight_boundaries_and_six_section_fighter(self):
        for tons,family in [(35,'light'),(36,'medium'),(55,'medium'),(56,'heavy'),(75,'heavy'),(76,'assault')]:
            self.unit.tonnage=tons
            self.assertEqual(family,diagram_family(self.unit))
            self.assertIn('FRONT',plain(armor_display(self.unit,True)['text']))
        self.unit.unit_type=UnitType.AERO
        result=armor_display(self.unit,True)
        for name in ['Nose','Left Wing','Right Wing','Fuselage','Cockpit','Engine']:
            self.assertIn(name,plain(result['text']))
    def test_historical_fighter_custom_armor_uses_six_sections(self):
        unit=Mech.create_test_mech('historical');unit.unit_type=UnitType.AERO;unit.status_template='7 &:0'
        unit.sections[0].internal=7
        self.assertEqual('  7',armor_display(unit,True)['plain'])
