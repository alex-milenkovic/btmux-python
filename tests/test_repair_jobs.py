"""Repair events share engine time, retain failure identity and survive restart."""
import json
import unittest
from core.game_loop import GameEngine
from entities.mech import Mech, FireMode as F
from entities.crittypes import i2special, Special
from systems.economic_inventory import InventoryStore
from systems.technician import Technician, pack
from systems.repair_jobs import RepairJobs


class RepairJobsTests(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine(); self.unit=Mech(); self.unit._id=12; self.unit._engine=self.engine
        self.store=InventoryStore(); self.store.register(12,self.unit)
        self.jobs=RepairJobs(self.engine,Technician(self.engine,self.store),self.store)
        self.slot=self.unit.sections[4].criticals[3]
        self.slot.type=i2special(Special.CASE); self.slot.firemode=F.BROKEN_MODE

    def test_fake_and_real_jobs_hold_same_lock_until_exact_deadline(self):
        for fake in (True,False):
            self.engine.events.set_tick(0)
            self.jobs.schedule(53,self.unit,pack(7,4,3,2),60,fake=fake)
            self.assertTrue(self.jobs.repairing(self.unit,4,3))
            self.assertFalse(self.jobs.repairing(self.unit,4,4))
            self.engine.events.set_tick(59); self.engine.events.run_events()
            self.assertTrue(self.slot.firemode & F.BROKEN_MODE)
            self.engine.events.set_tick(60); self.engine.events.run_events()
            self.assertFalse(self.jobs.repairing(self.unit,4,3))
            self.assertEqual(bool(self.slot.firemode & F.BROKEN_MODE),fake)

    def test_source_conflicts_count_and_keep_rear_distinct(self):
        for _ in range(2):self.jobs.schedule(47,self.unit,pack(7,12),60,fake=True)
        self.assertEqual(self.jobs.count(self.unit,47,12),2)
        self.assertEqual(self.jobs.count(self.unit,47,4),0)
        self.assertTrue(self.jobs.can_scrap_location(self.unit,4))
        self.assertFalse(self.jobs.can_scrap_location(self.unit,12))
        self.jobs.schedule(44,self.unit,pack(7,4,3),60)
        self.assertTrue(self.jobs.can_scrap_location(self.unit,4))
        self.assertFalse(self.jobs.can_scrap_part(self.unit,4,3))

    def test_point_callbacks_recur_and_zero_amount_still_repairs_one(self):
        sec=self.unit.sections[4]; sec.armor=2; sec.armor_orig=10
        self.jobs.schedule(47,self.unit,7*65536+4+3*16,180)
        self.assertEqual(self.jobs.latest(self.unit),540)
        for tick,armor in ((180,3),(360,4),(540,5)):
            self.engine.events.set_tick(tick); self.engine.events.run_events()
            self.assertEqual(sec.armor,armor)
        self.assertFalse(self.jobs.events(self.unit))
        messages=len(self.jobs.messages)
        self.jobs.schedule(47,self.unit,pack(7,4),1)
        self.engine.events.set_tick(541); self.engine.events.run_events()
        self.assertEqual(sec.armor,6); self.assertEqual(len(self.jobs.messages),messages)

    def test_latest_uses_unmasked_amount_while_callback_masks_it(self):
        self.jobs.schedule(47,self.unit,7*65536+4144,180)
        self.assertEqual(self.jobs.latest(self.unit),46620)

    def test_save_clamps_due_time_and_preserves_fake_sign_and_actor(self):
        self.jobs.schedule(53,self.unit,pack(7,4,3),10,fake=True)
        self.engine.events.set_tick(20)
        rows=[json.loads(line) for line in self.jobs.save().splitlines()]
        self.assertEqual(rows,[[12,53,-1,pack(7,4,3)],[-1]])

    def test_load_bounds_bad_reference_and_keeps_valid_prefix(self):
        report=self.jobs.load('\n'.join(json.dumps(r) for r in ([12,53,100,pack(7,4,3)],[99,53,100,0],[-1])))
        self.assertEqual(report['loaded'],1); self.assertIn('reference',report['error'])
        self.engine.events.set_tick(100); self.engine.events.run_events()
        self.assertFalse(self.slot.firemode & F.BROKEN_MODE)

    def test_load_real_reseal_is_skipped_fake_reseal_survives(self):
        self.engine.events.set_tick(500)
        report=self.jobs.load('[12,56,100,0]\n[12,56,-100,0]\n[-1]')
        self.assertEqual(report['loaded'],1)
        event=self.jobs.events()[0]
        self.assertEqual(event.tick,600); self.assertTrue(event.repair_fake)

    def test_out_of_range_load_does_not_fabricate_job(self):
        result=self.jobs.load('[12,53,100,2147483648]\n[-1]')
        self.assertIn('range',result['error']); self.assertEqual(self.jobs.events(),[])
    def test_dropship_repairs_use_shared_first_aero_bay(self):
        from entities.mech import UnitType
        self.unit.unit_type=UnitType.DS;self.unit.location=10;self.unit.aero_bays=[99,-1,-1,-1]
        self.assertEqual(self.jobs.store_for(self.unit),99)

if __name__=='__main__':unittest.main()
