"""Charge uses actual mass, asymmetric mutual packets and numeric identities."""
import unittest
from tools.combat_resolution import CombatSession
from entities.mech import MechStatus as S
from systems import physical as p


class ChargeCompletionTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[],'config':{'periodic_updates':False}})
        self.u,self.v=self.s.units.values()
        self.u.facing=self.u.desired_facing=0
        self.v.facing=self.v.desired_facing=180
        for unit in (self.u,self.v):
            for sec in unit.sections:sec.armor=sec.rear=200;sec.internal=100
        self.s.streams.update(charge_rolls=[12,12],pilot_rolls=[12]*20,
            hit_location_rolls=[7]*100,damage_entry=[7]*100)

    def test_old_charge_damage_uses_actual_mass(self):
        self.u.tonnage=20;self.u.rtons=50*1024
        for speed,damage in ((10.75,6),(21.5,12),(32.25,17)):
            self.u.speed=speed
            self.assertEqual(damage,p._charge_damage_to_target(self.u,self.v,True))

    def test_charge_collision_warns_receiver_and_emits_attacker_result(self):
        self.u.speed=10.75
        self.s.invoke(p.charge_mech,self.u,self.v)
        self.assertTrue(any('CRASH!!!' in m for m in self.v.movement_messages))
        self.assertTrue(any('SMASH!!!' in m for m in self.u.movement_messages))
        self.assertFalse(any('CRASH!!!' in m for m in self.u.movement_messages))

    def test_mutual_asymmetry_includes_mismatched_remainder(self):
        self.u.rtons=50*1024;self.v.rtons=65*1024
        self.u.speed=self.v.speed=10.75
        self.v.charge_target=self.u._id
        before={unit._id:sum(sec.armor+sec.rear for sec in unit.sections) for unit in (self.u,self.v)}
        r=self.s.invoke(p.charge_mech,self.u,self.v)
        self.assertTrue(r.mutual and r.attacker_hit and r.target_hit)
        self.assertEqual((11,7,7,7),(r.damage_to_target,r.damage_to_attacker,r.attacker_self_damage,r.target_self_damage))
        self.assertEqual(14,before[self.u._id]-sum(sec.armor+sec.rear for sec in self.u.sections))
        self.assertEqual(18,before[self.v._id]-sum(sec.armor+sec.rear for sec in self.v.sections))
        self.assertEqual(-1,self.v.charge_target)

    def test_one_ineligible_side_still_draws_both_charge_rolls(self):
        self.u.speed=0;self.v.speed=10.75
        self.v.charge_target=self.u._id
        r=self.s.invoke(p.charge_mech,self.u,self.v)
        self.assertFalse(r.attacker_charging)
        self.assertTrue(r.target_charging)
        self.assertEqual(2,sum(d['name']=='charge_rolls' for d in self.s.draws))

    def test_charge_command_default_does_not_require_los_and_stores_numeric_id(self):
        self.s.map.losinfo={}
        self.u.target=self.v._id
        r=self.s.invoke(p.physical_command,self.u,'charge','')
        self.assertTrue(r['accepted'])
        self.assertEqual(self.v._id,self.u.charge_target)
        r=self.s.invoke(p.physical_command,self.u,'charge','-')
        self.assertTrue(r['accepted'])
        self.assertEqual(-1,self.u.charge_target)
