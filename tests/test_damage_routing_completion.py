"""Damage eligibility, routing and grouped equipment regressions."""
import unittest
from unittest.mock import patch
from entities.mech import Mech, Location as L, MechStatus as S, MechStatus2, Specials, FireMode
from entities.crittypes import Special, i2special
from core.randomness import use_source
from systems.combat import apply_damage_with_transfer
from systems.criticals import apply_internal_damage_with_transfer, apply_critical_to_slot
from tests.test_damage_failures import Draws

class RoutingTest(unittest.TestCase):
    def setUp(self):
        self.u=Mech.create_test_mech()
        self.a=Mech.create_test_mech()
        for section in self.u.sections:
            for slot in section.criticals: slot.type=0
        arm=self.u.sections[L.LARM]
        arm.armor=2; arm.internal=3
        torso=self.u.sections[L.LTORSO]
        torso.armor=4; torso.internal=20

    def test_safety_consumes_entry_roll_preserves_modes(self):
        self.u.status |= S.COMBAT_SAFE
        self.u.status2 |= MechStatus2.SPRINTING
        draws=Draws(7)
        with use_source(draws): apply_damage_with_transfer(self.u,L.LARM,10,attacker=self.a)
        self.assertEqual(2,self.u.sections[L.LARM].armor)
        self.assertTrue(self.u.status2 & MechStatus2.SPRINTING)
        self.assertEqual(1,len(draws.calls))

    def test_internal_containment_and_ordinary_transfer(self):
        with patch('systems.combat.roll_2d6',return_value=7):
            apply_internal_damage_with_transfer(self.u,L.LARM,8,attacker=self.a)
        self.assertEqual((4,15),(self.u.sections[L.LTORSO].armor,self.u.sections[L.LTORSO].internal))
        self.assertEqual(8,self.u.damage_taken)
        self.assertEqual(8,self.a.damage_inflicted)

    def test_dead_arm_skips_critical_roll_and_preserves_armor_path(self):
        self.u.sections[L.LARM].internal=0
        with use_source(Draws(7,7)):
            apply_damage_with_transfer(self.u,L.LARM,3,attacker=self.a)
        self.assertEqual(1,self.u.sections[L.LTORSO].armor)

    def test_double_sink_destroys_group_and_removes_two_capacity_only_once(self):
        self.u.specials |= Specials.DOUBLE_HEAT_TECH
        self.u.num_sinks=5
        for i in range(3): self.u.sections[L.LTORSO].criticals[i].type=i2special(Special.HEAT_SINK)
        apply_critical_to_slot(self.u,L.LTORSO,1)
        apply_critical_to_slot(self.u,L.LTORSO,2)
        self.assertEqual(8,self.u.effective_heat_sinks)
        self.assertTrue(all(s.firemode & (FireMode.BROKEN_MODE|FireMode.DESTROYED_MODE) for s in self.u.sections[L.LTORSO].criticals[:3]))
