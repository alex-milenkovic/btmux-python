"""Pod swatting uses actual actuators, section damage, and event time."""
import unittest
from tools.combat_resolution import CombatSession
from entities.mech import Location as L,FireMode as F,UnitType as U,MechStatus as S
from systems import combat_equipment as e,missile as m


class PodTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[],'config':{'periodic_updates':False}})
        self.u=self.s.units['u']
        self.u.tonnage=55
        self.s.streams.update(pod_rolls=[12],damage_entry=[7]*20)
        self.u.sections[L.CTORSO].specials=m.INARC_HOMING_ATTACHED

    def test_tied_arm_is_left_and_success_only_removes_chosen_pod(self):
        self.u.sections[L.CTORSO].specials|=m.INARC_ECM_ATTACHED
        result=self.s.invoke(e.remove_pods_mech,self.u,'CT H')
        self.assertTrue(result['accepted'])
        self.assertEqual(L.LARM,result['arm'])
        self.assertEqual(60,self.u.sections[L.LARM].recycle)
        self.assertEqual(m.INARC_ECM_ATTACHED,self.u.sections[L.CTORSO].specials)

    def test_arm_pod_requires_other_arm_and_recycle_rejects_before_roll(self):
        self.u.sections[L.LARM].specials=m.INARC_HOMING_ATTACHED
        self.u.sections[L.RARM].recycle=1
        self.assertFalse(self.s.invoke(e.remove_pods_mech,self.u,'LA H')['accepted'])
        self.assertEqual([],self.s.draws)

    def test_failed_swat_halves_twice_before_direct_damage(self):
        self.s.streams['pod_rolls']=[2]
        self.u.sections[L.LARM].specials=m.INARC_HOMING_ATTACHED
        for slot in (1,2):self.u.sections[L.RARM].criticals[slot].firemode|=F.DESTROYED_MODE
        before=self.u.sections[L.LARM].armor
        result=self.s.invoke(e.remove_pods_mech,self.u,'LA H')
        self.assertEqual(1,result['self_damage'])
        self.assertEqual(before-1,self.u.sections[L.LARM].armor)
        self.assertTrue(self.u.sections[L.LARM].specials&m.INARC_HOMING_ATTACHED)

    def test_tank_reverse_speed_and_stopped_reactor_callback_keeps_narc(self):
        self.u.unit_type=U.VEH_GROUND
        self.u.speed=self.u.desired_speed=-10
        flags=m.NARC_ATTACHED|m.INARC_HOMING_ATTACHED|m.INARC_HAYWIRE_ATTACHED|m.INARC_ECM_ATTACHED|m.INARC_NEMESIS_ATTACHED
        self.u.sections[0].specials=flags
        self.assertTrue(self.s.invoke(e.remove_pods_tank,self.u)['accepted'])
        self.u.status&=~S.STARTED
        self.s.invoke(self.s.engine.run_ticks,60)
        self.assertEqual(m.NARC_ATTACHED,self.u.sections[0].specials)
