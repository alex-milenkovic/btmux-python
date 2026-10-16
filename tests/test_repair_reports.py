import unittest
from tests.test_repair_work import RepairWorkTests
from entities.mech import SectionConfig as C,FireMode as F
from systems.repair_reports import RepairReports


class RepairReportTests(unittest.TestCase):
    def setUp(self):
        base=RepairWorkTests();base.setUp()
        self.unit=base.unit;self.actor=base.actor;self.work=base.work;self.jobs=base.jobs;self.store=base.store
        self.unit.sections[4].criticals[0].type=0
        self.reports=RepairReports(self.work)
    def test_ct_destroyed_diagnostic_and_public_dispatch_differ(self):
        self.unit.sections[4].armor=self.unit.sections[4].internal=0
        self.unit.sections[0].armor=5
        self.assertEqual(self.reports.damage_table(self.unit),[(0,4,0)])
        self.assertNotIn((0,4,0),self.reports.table(self.unit))
    def test_parent_flooding_suppresses_children(self):
        self.unit.sections[2].config|=C.SECTION_FLOODED;self.unit.sections[0].armor=5;self.unit.sections[3].armor=8
        self.assertEqual(self.reports.table(self.unit),[(19,2,0),(12,3,2)])
    def test_internal_row_suppresses_front_and_rear_armor(self):
        sec=self.unit.sections[4];sec.internal=8;sec.armor=5;sec.rear=3;sec.rear_orig=5
        self.assertEqual(self.reports.table(self.unit),[(14,4,2)])
        sec.internal=10
        self.assertEqual(self.reports.table(self.unit),[(12,4,5),(13,4,2)])
    def test_fix_range_keeps_snapshot_indices_after_stock_refusal(self):
        from entities.crittypes import i2special,Special
        sec=self.unit.sections[4];sec.armor=8
        for pos,kind in ((0,Special.SHOULDER_OR_HIP),(1,Special.HEAT_SINK)):
            sec.criticals[pos].type=i2special(kind);sec.criticals[pos].firemode=F.BROKEN_MODE
        self.store.set(10,547,0,2);self.store.set(10,i2special(Special.HEAT_SINK),0,1)
        results=self.reports.fix(self.actor,self.unit,'1-3')
        self.assertEqual([r['number'] for r in results],[1,2,3]);self.assertEqual(results[1]['error'],'Not enough units of Actuator in store.')
        self.assertEqual(len(self.jobs.events()),2)
    def test_reverse_range_does_nothing_and_invalid_endpoint_precedes_dispatch(self):
        for loc in (4,2,3):self.unit.sections[loc].armor=8
        self.assertEqual(self.reports.fix(self.actor,self.unit,'3-2'),[])
        with self.assertRaisesRegex(ValueError,'high'):self.reports.fix(self.actor,self.unit,'1-4')
        self.assertEqual(self.jobs.events(),[])
    def test_human_report_includes_selected_ammo_and_material(self):
        from entities.mech import AmmoMode,Specials
        from entities.crittypes import i2ammo
        from entities.weapon import get_weapon
        sec=self.unit.sections[4];sec.armor=8;self.unit.specials|=Specials.FF_TECH
        slot=sec.criticals[0];slot.type=i2ammo(get_weapon('IS.LRM-15').index);slot.data=1;slot.ammomode=AmmoMode.ARTEMIS_MODE
        rows=self.reports.human(self.actor,self.unit)
        self.assertIn('Ferrofibrous armor (2 points)',rows[0]['description'])
        self.assertIn('Artemis IV',rows[1]['description'])

    def test_pristine_reports_notify_the_actual_unit_type(self):
        from entities.mech import UnitType
        for kind,label in ((UnitType.MECH,"The 'mech is in pristine condition!"),(UnitType.VEH_GROUND,"It's in pristine condition!")):
            self.unit.unit_type=kind
            self.assertEqual(self.reports.human(self.actor,self.unit),[])
            self.assertEqual(self.work.tech.messages[-1]['text'],label)
            self.assertEqual(self.reports.machine(self.unit),'')

    def test_rear_progress_and_machine_values_use_same_table(self):
        sec=self.unit.sections[4];sec.armor=8;sec.rear=3;sec.rear_orig=5
        self.jobs.schedule(47,self.unit,7*65536+12+32,180)
        rows=self.reports.human(self.actor,self.unit)
        self.assertFalse(rows[0]['in_progress']);self.assertIsNone(rows[1]['minutes'])
        self.assertEqual(self.reports.machine(self.unit),'1|CT|12|2|0,2|CT|13|2|1')

if __name__=='__main__':unittest.main()
