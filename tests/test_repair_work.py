"""Commands debit shared stores now and mutate equipment only when jobs mature."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from core.game_loop import GameEngine
from entities.mech import Mech,FireMode as F,SectionConfig as C,AmmoMode as A
from entities.crittypes import i2special,Special,i2weapon,i2ammo
from entities.weapon import get_weapon
from data.construction_catalog import source_id
from systems.economic_inventory import InventoryStore
from systems.technician import Technician
from systems.repair_jobs import RepairJobs
from systems.repair_work import RepairWork


class RepairWorkTests(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.unit=Mech();self.unit._id=12;self.unit._engine=self.engine
        self.unit.location=10;self.unit.repair_stall=True
        for sec in self.unit.sections:sec.internal=sec.internal_orig=10;sec.armor=sec.armor_orig=10
        self.actor=SimpleNamespace(_id=7,tech=True,wizard=True)
        self.store=InventoryStore();self.store.register(10);self.store.register(7,self.actor);self.store.register(12,self.unit)
        self.tech=Technician(self.engine,self.store);self.tech.roll=Mock(return_value=0)
        self.jobs=RepairJobs(self.engine,self.tech,self.store);self.work=RepairWork(self.jobs)
        self.slot=self.unit.sections[4].criticals[0];self.slot.type=i2special(Special.CASE);self.slot.firemode=F.BROKEN_MODE
    def stock(self,part,count=10):self.store.set(10,part,0,count)
    def due(self,tick):self.engine.events.set_tick(tick);self.engine.events.run_events()
    def test_part_replacement_success_only_mutates_at_deadline(self):
        self.stock(self.slot.type,2);self.work.command(self.actor,self.unit,'replacepart','CT 1')
        self.assertEqual(self.store.find(10,self.slot.type),1)
        self.due(2699);self.assertTrue(self.slot.firemode&F.BROKEN_MODE)
        self.due(2700);self.assertFalse(self.slot.firemode&F.BROKEN_MODE)
    def test_failed_replacement_recovery_keeps_stock_and_fake_job(self):
        self.stock(self.slot.type,2);self.tech.roll.side_effect=[-1,0]
        self.work.command(self.actor,self.unit,'replacepart','CT 1')
        self.assertEqual(self.store.find(10,self.slot.type),2)
        self.assertEqual(self.jobs.events()[0].tick,4020)
        self.due(4020);self.assertTrue(self.slot.firemode&F.BROKEN_MODE)
    def test_point_failure_spends_original_cost_then_restores_partial(self):
        sec=self.unit.sections[4];sec.armor=5;self.stock(547,5);self.tech.roll.side_effect=[-1,0]
        with patch('systems.repair_work.draw',return_value=5):self.work.command(self.actor,self.unit,'fixarmor','CT')
        self.assertEqual(self.store.find(10,547),0);self.assertEqual(self.jobs.events()[0].tick,360)
        self.due(360);self.assertEqual(sec.armor,6)
        self.due(540);self.assertEqual(sec.armor,7);self.assertFalse(self.jobs.events())
    def test_one_point_failure_has_one_second_callback_without_finish(self):
        self.unit.sections[4].armor=9;self.stock(547,1);self.tech.roll.side_effect=[-1,-1]
        with patch('systems.repair_work.draw',return_value=5):self.work.command(self.actor,self.unit,'fixarmor','CT')
        self.due(1);self.assertEqual(self.unit.sections[4].armor,10);self.assertEqual(self.jobs.messages,[])
    def test_reseal_missing_second_resource_preserves_first_and_dice(self):
        self.unit.sections[4].config|=C.SECTION_FLOODED;self.stock(546);self.stock(545,9)
        with self.assertRaisesRegex(ValueError,'Not enough units of Electric in store! You need to have at least 10'):self.work.command(self.actor,self.unit,'reseal','CT')
        self.assertEqual(self.store.find(10,546),10);self.tech.roll.assert_not_called()
    def test_latest_reattach_failure_has_no_legacy_refund(self):
        sec=self.unit.sections[0];sec.config|=C.SECTION_DESTROYED;sec.internal=sec.armor=0
        self.stock(546);self.stock(545);self.tech.roll.side_effect=[-1,-1]
        self.work.command(self.actor,self.unit,'reattach','LA')
        self.assertEqual(self.store.find(10,546),0);self.assertEqual(self.jobs.events()[0].tick,21600)
        self.due(21600);self.assertEqual(sec.internal,0)
    def test_ammo_mode_write_precedes_fatigue_rejection(self):
        self.slot.type=i2ammo(get_weapon('IS.LRM-15').index);self.slot.firemode=0;self.slot.data=2
        self.store.put(7,'TECHTIME','36000')
        with self.assertRaisesRegex(ValueError,'tired'):self.work.command(self.actor,self.unit,'reload','CT 1 A')
        self.assertEqual(self.slot.data,0);self.assertTrue(self.slot.ammomode&A.ARTEMIS_MODE);self.tech.roll.assert_not_called()
    def test_ammo_conversion_retains_bits_outside_source_mode_mask(self):
        self.slot.type=i2ammo(get_weapon('IS.SRM-6').index);self.slot.firemode=0
        unrelated=0x80000000
        self.slot.ammomode=unrelated|int(A.ARTEMIS_MODE);self.slot.data=2
        self.work.command(self.actor,self.unit,'toggletype','CT 1 N')
        self.assertEqual(int(self.slot.ammomode),unrelated|int(A.NARC_MODE))
        self.assertEqual(self.slot.data,15)
        self.slot.data=2
        self.store.put(7,'TECHTIME','36000')
        with self.assertRaisesRegex(ValueError,'tired'):
            self.work.command(self.actor,self.unit,'reload','CT 1 A')
        self.assertEqual(int(self.slot.ammomode),unrelated|int(A.ARTEMIS_MODE))
        self.assertEqual(self.slot.data,0)
        self.tech.roll.assert_not_called()
    def test_unload_failed_roll_is_still_real_and_returns_full_bin(self):
        from systems.combat_ammunition import full_ammo
        self.slot.type=i2ammo(get_weapon('IS.LRM-15').index);self.slot.firemode=0;self.slot.data=full_ammo(self.unit,4,0)
        self.tech.roll.return_value=-1;self.work.command(self.actor,self.unit,'unload','CT 1')
        self.assertFalse(self.jobs.events()[0].repair_fake);self.due(900)
        self.assertEqual(self.slot.data,0);self.assertEqual(self.store.find(10,516),1)
    def test_removegun_double_failure_keeps_source_normal_duration(self):
        weapon=get_weapon('IS.LargeLaser')
        for pos in (0,1):self.unit.sections[4].criticals[pos].type=i2weapon(weapon.index);self.unit.sections[4].criticals[pos].firemode=0
        self.tech.roll.side_effect=[-1,-1];self.work.command(self.actor,self.unit,'removegun','CT 1')
        self.assertEqual(self.jobs.events()[0].tick,4800);self.due(4800)
        self.assertFalse(self.slot.firemode&F.DESTROYED_MODE)
    def test_repairgun_writes_type53_with_whole_gun_callback(self):
        from systems.enhanced_crits import set_part_temp_nuke
        weapon=get_weapon('IS.LargeLaser')
        for pos in (0,1):self.unit.sections[4].criticals[pos].type=i2weapon(weapon.index)
        set_part_temp_nuke(self.slot,1);self.stock(545,1);self.stock(546,1)
        self.work.command(self.actor,self.unit,'repairgun','CT 1')
        self.assertEqual(self.jobs.report(self.unit)[0]['type'],53);self.assertEqual(self.jobs.events()[0].repair_callback,'repairgun')
    def test_legacy_refund_helper_and_inert_success_have_distinct_effects(self):
        self.assertEqual(self.work.success('replaceg_succ'),0)
        self.assertEqual(self.work.failure('replacep_fail',self.actor,self.unit,4,0),-1);self.tech.roll.assert_not_called()
        self.assertEqual(self.work.failure('replaceg_fail',self.actor,self.unit,4,0),-1)
        self.assertEqual(self.store.find(10,self.slot.type),1)
    def test_rear_armor_uses_rear_field_and_separate_payload(self):
        sec=self.unit.sections[4];sec.rear=4;sec.rear_orig=6;self.stock(547,2)
        self.work.command(self.actor,self.unit,'fixarmor','CT r')
        self.assertEqual(self.jobs.events()[0].data2%16,12)
        self.due(180);self.assertEqual((sec.rear,sec.armor),(5,10))
        self.due(360);self.assertEqual(sec.rear,6)
    def test_gun_section_and_queue_refusals_precede_equipment_damage(self):
        self.unit.sections[4].armor=self.unit.sections[4].internal=0;self.slot.type=0
        for name in ('removegun','replacegun','repairgun','fixenhcrit'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,"That part's blown off!"):
                self.work.command(self.actor,self.unit,name,'CT 1')
        self.unit.sections[4].armor=self.unit.sections[4].internal=10
        self.slot.type=i2weapon(get_weapon('IS.LargeLaser').index);self.slot.firemode=0
        self.jobs.schedule(53,self.unit,7*65536+4,60)
        with self.assertRaisesRegex(ValueError,'repairing'):
            self.work.command(self.actor,self.unit,'repairgun','CT 1')
        self.tech.roll.assert_not_called()

    def test_suit_capacity_and_index_guards_precede_resources_and_rolls(self):
        from entities.mech import UnitType
        self.unit.unit_type=UnitType.BSUIT;self.unit.max_suits=4
        for index,sec in enumerate(self.unit.sections):
            sec.internal=sec.armor=sec.internal_orig=10 if index<3 else 0
        self.unit.sections[4].internal_orig=10
        with self.assertRaisesRegex(ValueError,'Invalid suit'):
            self.work.command(self.actor,self.unit,'replacesuit','S5')
        self.unit.sections[3].internal=10
        with self.assertRaisesRegex(ValueError,'full'):
            self.work.command(self.actor,self.unit,'replacesuit','S5')
        self.tech.roll.assert_not_called();self.assertEqual(self.store.raw(10),'')

    def test_checkstatus_has_no_technician_gate(self):
        self.actor.tech=False;self.actor.wizard=False
        self.assertTrue(self.work.command(self.actor,self.unit,'checkstatus')['ready'])

if __name__=='__main__':unittest.main()
