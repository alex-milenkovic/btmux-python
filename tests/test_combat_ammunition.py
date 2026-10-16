"""Ammo planning and spending use the mounted weapon's source rules."""
import unittest
from tools.combat_resolution import CombatSession
from entities.mech import FireMode as F
from systems import combat_ammunition as ammo


class AmmunitionTest(unittest.TestCase):
    def fixture(self,name,rounds=0,mode=0):
        s=CombatSession({'actions':[],'units':[{'name':'u','weapons':[{'name':name,'section':'CT',
           'metadata':{'crits':1}}],'ammo':[{'weapon':name,'rounds':rounds}]}]})
        u=s.units['u'];ws=u.weapons[0]
        u.sections[ws.section].criticals[ws.critical].firemode=mode
        return s,u,ws

    def test_gattling_caps_by_three_and_spends_across_available_rounds(self):
        s,u,ws=self.fixture('IS.MachineGun',8,F.GATTLING_MODE)
        plan=s.invoke(ammo.find_and_check,u,ws,6)
        self.assertTrue(plan.accepted)
        self.assertEqual(2,plan.gattling_shots)
        s.invoke(ammo.decrement,u,ws.weapon_idx,ws,plan)
        self.assertEqual(2,ammo.count_ammo(u,ws.weapon_idx))

    def test_firing_uses_capped_gattling_count_as_damage_and_heat(self):
        from systems.combat import fire_weapon
        s,u,ws=self.fixture('IS.MachineGun',10,F.GATTLING_MODE)
        target=s.add_unit({'name':'v','at':[3,2,0],'team':2})
        s.streams['gattling_shots']=[6]
        result=s.invoke(fire_weapon,u,target,0,1,to_hit_roll=12,location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(3,result.damage_dealt)
        self.assertEqual(3,u.weap_heat)
        self.assertEqual(1,ammo.count_ammo(u,ws.weapon_idx))

    def test_usebin_accepts_empty_intact_section_and_rejects_destroyed_section(self):
        s,u,ws=self.fixture('IS.UltraAC/5',1)
        self.assertTrue(s.invoke(ammo.usebin,u,'0 LT')['accepted'])
        slot=u.sections[ws.section].criticals[ws.critical]
        self.assertEqual(2,slot.desired_ammo_loc)
        u.sections[3].internal=0
        self.assertFalse(s.invoke(ammo.usebin,u,'0 RT')['accepted'])
        self.assertEqual(2,slot.desired_ammo_loc)
        self.assertTrue(s.invoke(ammo.usebin,u,'0 -')['accepted'])
        self.assertEqual(-1,slot.desired_ammo_loc)

    def test_warning_crossing_and_suppressed_warning_still_invalidates_weight(self):
        from entities.mech import CritStatus
        from dataclasses import replace
        from entities.weapon import get_weapon_by_index
        s,u,ws=self.fixture('IS.UltraAC/5',5)
        s.weapon_overrides[ws.weapon_idx]=replace(get_weapon_by_index(ws.weapon_idx),ammo_per_ton=20)
        self.assertEqual('red',s.invoke(ammo.expenditure_check,u,ws.weapon_idx,0))
        u.prefs=16
        u.crit_status|=CritStatus.OWEIGHT_OK
        self.assertIsNone(s.invoke(ammo.expenditure_check,u,ws.weapon_idx,0))
        self.assertFalse(u.crit_status & CritStatus.OWEIGHT_OK)

    def test_rfac_explosion_damages_internals_and_spends_two_rounds(self):
        from systems.combat import fire_weapon
        s,u,ws=self.fixture('IS.AC/5',10,F.RFAC_MODE)
        target=s.add_unit({'name':'v','team':2})
        before=u.sections[ws.section].internal
        s.streams.update(damage_entry=[7]*20,critical_rolls=[7]*20)
        result=s.invoke(fire_weapon,u,target,0,1,to_hit_roll=2)
        self.assertTrue(result.shot_aborted)
        self.assertEqual(before-5,u.sections[ws.section].internal)
        self.assertEqual(8,ammo.count_ammo(u,ws.weapon_idx))
        self.assertEqual(0,u.weap_heat)

    def test_ultra_shortage_clears_whole_mode_word_and_restores_borrow(self):
        s,u,ws=self.fixture('IS.UltraAC/5',1,F.ULTRA_MODE|F.REAR_MOUNT|F.ON_TC)
        plan=s.invoke(ammo.find_and_check,u,ws,0)
        self.assertTrue(plan.accepted)
        self.assertEqual(0,u.sections[ws.section].criticals[ws.critical].firemode)
        self.assertEqual(1,ammo.count_ammo(u,ws.weapon_idx))

    def test_unjam_catalog_number_quirk_keeps_number_zero_round(self):
        s,u,ws=self.fixture('IS.RotaryAC/5',5)
        plan=s.invoke(ammo.find_and_check,u,ws,0)
        s.invoke(ammo.decrement,u,0,ws,plan,source_number=True)
        self.assertEqual(5,ammo.count_ammo(u,ws.weapon_idx))
        s.invoke(ammo.decrement,u,1,ws,plan,source_number=True)
        self.assertEqual(4,ammo.count_ammo(u,ws.weapon_idx))

    def test_unjam_event_roll_failure_then_success_without_number_zero_spend(self):
        from systems import combat_equipment as equipment
        from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke,FAIL_AMMOJAMMED
        s,u,ws=self.fixture('IS.RotaryAC/5',5)
        slot=u.sections[ws.section].criticals[ws.critical]
        set_part_temp_nuke(slot,FAIL_AMMOJAMMED)
        self.assertTrue(s.invoke(equipment.unjam_ammo,u,'0')['accepted'])
        self.assertFalse(s.invoke(equipment.unjam_ammo,u,'0')['started'])
        s.streams['unjam_rolls']=[6]
        s.action({'op':'advance','seconds':60})
        self.assertEqual(FAIL_AMMOJAMMED,part_temp_nuke(slot))
        self.assertFalse(u.unjamming)
        self.assertTrue(s.invoke(equipment.unjam_ammo,u,'0')['accepted'])
        s.streams['unjam_rolls']=[7]
        s.action({'op':'advance','seconds':60})
        self.assertEqual(0,part_temp_nuke(slot))
        self.assertEqual(5,ammo.count_ammo(u,ws.weapon_idx))
