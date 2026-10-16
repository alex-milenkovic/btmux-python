import unittest
from entities.mech import Mech,FireMode as F,SectionConfig as C,UnitType
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems.status_display import query,critical_display,weapon_display,selected_components

class QueryTests(unittest.TestCase):
    def setUp(self):
        self.unit=Mech.create_test_mech('status');self.loc=self.unit.sections[0]
        self.loc.internal_orig=10;self.loc.internal=4;self.loc.armor=7;self.loc.armor_orig=20;self.loc.rear=2;self.loc.rear_orig=5
        self.slot=self.loc.criticals[0];self.slot.type=i2weapon(get_weapon('IS.MediumLaser').index)
    def test_section_values_and_error(self):
        self.assertEqual('7/20|4/10|2/5',query(self.unit,'armorstatus','Left Arm'))
        self.assertEqual('#-1 INVALID SECTION',query(self.unit,'armorstatus','ALL'))
        self.loc.internal=0;self.loc.config|=C.SECTION_FLOODED
        self.assertEqual('-1',query(self.unit,'sectstatus','Left Arm'))
    def test_slot_priority_and_bounds(self):
        self.slot.firemode=F.DESTROYED_MODE|F.DISABLED_MODE
        self.assertEqual('Disabled',query(self.unit,'critslot','Left Arm',1,'STATUS'))
        self.assertEqual('#-1 NOT AMMO',query(self.unit,'critslot','Left Arm',1,'MAXAMMO'))
        self.unit.unit_type=UnitType.AERO;self.unit.sections[4].internal_orig=1
        self.assertEqual('#-1 INVALID CRITICAL',query(self.unit,'critslot','Cockpit',6,'NAME'))
    def test_weapon_query_fields_and_critical_order(self):
        result=query(self.unit,'weaponstatus',None).split(',')[0].split('|')
        self.assertEqual(8,len(result));self.assertEqual('0',result[-1])
        self.slot.firemode|=F.BROKEN_MODE
        self.assertEqual('2',query(self.unit,'weaponstatus',None).split(',')[0].split('|')[-1])
        self.assertEqual([1,7,2,8,3,9,4,10,5,11,6,12],[s['number'] for s in critical_display(self.unit,0)['slots']])
    def test_owner_recycle_rounds_up_and_selection_precedence(self):
        self.slot.data=5
        self.assertEqual('3',weapon_display(self.unit)['weapons'][0]['status'])
        self.assertEqual(['short','target'],selected_components('S A W'))
        self.assertEqual(['compact-template'],selected_components('N'))
        self.assertEqual(['generic','info','heat'],selected_components('Info'))
    def test_battlesuit_enemy_header_and_owner_recycle_padding(self):
        self.unit.unit_type=UnitType.BSUIT;self.unit.sections[0].recycle=5
        self.assertIn('----- Weapon ------ [##]  Holder ------ Status',weapon_display(self.unit,False)['lines'])
        self.assertIn('Team status (special attacks): 3    ',weapon_display(self.unit)['lines'])
