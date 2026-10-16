"""Physical damage and DFA use source clusters, guards, and landing effects."""
import unittest
from tools.combat_resolution import CombatSession
from entities.mech import Location as L,MechStatus as S,Specials
from systems import physical as p


class PhysicalCompletionTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[],'config':{'periodic_updates':False}})
        self.u,self.v=self.s.units.values()
        for unit in (self.u,self.v):
            for sec in unit.sections:sec.armor=sec.rear=200;sec.internal=100
        self.u.tonnage=55;self.u.rtons=55*1024
        self.s.streams.update(physical_location=[3]*20,damage_entry=[7]*100,
            hit_location_rolls=[7]*100,pilot_rolls=[12]*10,dfa_rolls=[12])

    def test_saw_and_claw_default_location_without_location_draw(self):
        for attack in (p.PhysicalAttackType.SAW,p.PhysicalAttackType.CLAW):
            result=self.s.invoke(p.physical_damage,self.u,self.v,7,attack,L.LARM)
            self.assertEqual(0,result.location_hit)
            self.assertFalse(result.is_rear)
        self.assertFalse(any(d['name'] in ('physical_location','hit_location_rolls') for d in self.s.draws))

    def test_physical_miss_still_recycles_for_sixty(self):
        self.v.fx=self.u.fx;self.v.fy=self.u.fy-100
        r=self.s.invoke(p.mech_punch,self.u,self.v,arm='L',roll=2)[0]
        self.assertTrue(r.success)
        self.assertFalse(r.hit)
        self.assertEqual(60,self.u.sections[L.LARM].recycle)

    def test_dfa_mass_formula_uses_actual_and_nominal_rounding(self):
        for nominal,actual,expected in ((50,50,(15,10)),(55,55,(17,11)),(55,60,(19,11)),(60,55,(16,12))):
            self.u.tonnage=nominal;self.u.rtons=actual*1024
            self.assertEqual(expected,p.calculate_dfa_damage(self.u))

    def test_dfa_hit_uses_punch_and_kick_clusters_and_six_recycles(self):
        self.u.status|=S.JUMPING|S.DFA_ATTACK
        r=self.s.invoke(p.dfa_attack,self.u,self.v)
        self.assertTrue(r.success and r.hit)
        self.assertEqual((17,11),(r.damage_dealt,r.attacker_damage))
        self.assertEqual(7,sum(d['name']=='physical_location' for d in self.s.draws))
        self.assertEqual([60]*6,[self.u.sections[loc].recycle for loc in p.RESECT])
        self.assertFalse(self.u.is_jumping)
        self.assertEqual([12,12],[d['value'] for d in self.s.draws if d['name']=='pilot_rolls'])

    def test_dfa_miss_applies_only_back_clusters_and_no_generic_fall(self):
        self.u.status|=S.JUMPING|S.DFA_ATTACK
        from entities.map import WATER
        self.s.map.set_terrain(self.u.x,self.u.y,WATER)
        self.u.elev=1
        self.s.streams['dfa_rolls']=[2]
        r=self.s.invoke(p.dfa_attack,self.u,self.v)
        self.assertTrue(r.success)
        self.assertEqual((0,11),(r.damage_dealt,r.attacker_damage))
        self.assertTrue(self.u.is_fallen)
        self.assertEqual((-1,-64.5),(self.u.z,self.u.fz))
        self.assertFalse(any(d['name']=='fall_directions' for d in self.s.draws))
        self.assertEqual([60]*6,[self.u.sections[loc].recycle for loc in p.RESECT])

    def test_dfa_declines_before_roll_and_preserves_jumping(self):
        self.u.status|=S.JUMPING|S.DFA_ATTACK
        self.u.sections[L.LLEG].recycle=1
        r=self.s.invoke(p.dfa_attack,self.u,self.v)
        self.assertFalse(r.success)
        self.assertTrue(self.u.is_jumping)
        self.assertEqual([],self.s.draws)
        self.u.sections[L.LLEG].recycle=0
        self.u.pilot.piloting=15
        self.assertFalse(self.s.invoke(p.dfa_attack,self.u,self.v).success)
        self.assertEqual([],self.s.draws)

    def test_dfa_retains_critical_flag_across_legacy_clusters_and_warns_target(self):
        from unittest.mock import patch
        self.v.status|=S.FALLEN
        def location(unit,group,critical=False):return L.CTORSO,True
        with patch('systems.hit_locations.find_hit_location',side_effect=location) as select,\
             patch('systems.physical.apply_damage_with_transfer',return_value=5):
            self.s.invoke(p.dfa_attack,self.u,self.v)
        self.assertTrue(select.call_args_list[1].kwargs['critical'])
        self.assertTrue(any('DEATH FROM ABOVE' in m for m in self.v.movement_messages))


class PhysicalCommandsTest(unittest.TestCase):
    def setUp(self):
        from tools.combat_resolution import CombatSession
        self.s=CombatSession({'actions':[],'config':{'periodic_updates':False}})
        self.u,self.v=self.s.units.values()
        self.u.facing=self.u.desired_facing=0
        self.v.fx=self.u.fx;self.v.fy=self.u.fy-100
        self.u.target=self.v._id
        self.s.streams.update(physical_attack=[12]*10,physical_location=[3]*10,pilot_rolls=[12]*10,damage_entry=[7]*10)

    def test_default_lock_punch_and_contact_parser(self):
        from systems.physical import physical_command
        r=self.s.invoke(physical_command,self.u,'punch','r')
        self.assertTrue(r['accepted'])
        self.assertEqual(60,self.u.sections[L.RARM].recycle)

    def test_common_guard_precedes_limb_checks(self):
        from systems.physical import mech_punch
        self.u.status &= ~S.STARTED
        self.u.sections[L.RARM].recycle=30
        r=self.s.invoke(mech_punch,self.u,self.v,arm='r')
        self.assertFalse(r[0].success)
        self.assertEqual('Reactor is not online!',r[0].message)

    def test_unswarmed_battlearmor_can_be_punched(self):
        from systems.physical import physical_command
        from entities.mech import UnitType
        self.v.unit_type=UnitType.BSUIT;self.v.swarm_target=-1
        r=self.s.invoke(physical_command,self.u,'punch','r')
        self.assertTrue(r['accepted'])

    def test_grabbing_during_ammo_unjam_is_refused(self):
        from systems.physical import mech_grabclub
        from core.events import EventType
        from entities.map import LIGHT_FOREST
        self.u.terrain=LIGHT_FOREST
        self.s.engine.events.schedule(20,EventType.UNJAM_AMMO,lambda e:None,self.u)
        ok,messages=self.s.invoke(mech_grabclub,self.u)
        self.assertFalse(ok)
        self.assertIn('unjam',' '.join(messages).lower())
