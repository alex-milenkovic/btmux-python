"""Preferences change live consumers; powered-down Gauss stays unusable."""
import unittest
from core.game_loop import GameEngine
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, WeaponState, UnitType, MoveType
from entities.map import GameMap
from entities.pilot import Pilot
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems import combat_preferences as prefs


class PreferencesTest(unittest.TestCase):
    def setUp(self):
        self.u=Mech.create_test_mech()
        self.u.pilot=Pilot()
        self.u.set_status(S.STARTED)
        self.u.map=GameMap(8,8)
        self.e=GameEngine()
        self.u.map._id=100
        self.e.register_entity(self.u.map)
        self.e.register_entity(self.u)
        self.u.map.add_mech(self.u)

    def test_inverted_and_normal_bits_and_live_fields(self):
        for name,setting,bit in (('MWSafety','OFF',1),('ArmorWarn','OFF',8),('AmmoWarn','OFF',16),
                                 ('FFSafety','ON',128),('SLWarn','ON',2),('AutoFall','ON',4),
                                 ('AutoconShutdown','ON',64),('BTHDebug','ON',512)):
            self.u.prefs=0
            reply=prefs.mechprefs(self.u,f'{name} {setting}')
            self.assertTrue(reply['accepted'])
            self.assertEqual(bit,self.u.prefs)
            self.assertEqual(setting,prefs.preference(self.u,name)['state'])
        self.assertTrue(self.u.sl_warn)
        self.assertTrue(self.u.autocon_shutdown)
        self.assertFalse(self.u.armor_warnings)
        self.assertFalse(self.u.ammo_warnings)

    def test_invalid_setting_is_atomic_and_negative_preference_color(self):
        prefs.mechprefs(self.u,'autofall on')
        self.assertIn('%crON',prefs.preference(self.u,'AutoFall')['text'])
        result=prefs.mechprefs(self.u,'AutoFall nonsense')
        self.assertFalse(result['accepted'])
        self.assertEqual(4,self.u.prefs)
        prefs.mechprefs(self.u,'AutoFall')
        self.assertEqual(0,self.u.prefs)

    def test_class_tagged_turret_obeys_raw_jammed_and_locked_flags(self):
        from systems.maneuver import update_autoturn_turret
        self.u.unit_type=UnitType.VEH_GROUND
        self.u.status2 |= S2.AUTOTURN_TURRET
        self.u.target=-1
        self.u.targ_x,self.u.targ_y=4,4
        for flags in (1,2,3):
            self.u.tank_crit_status=flags
            self.u.turret_facing=37
            self.assertFalse(update_autoturn_turret(self.u,self.u.map))
            self.assertEqual(37,self.u.turret_facing)
        self.u.tank_crit_status=0
        self.assertTrue(update_autoturn_turret(self.u,self.u.map))

    def test_safety_no_common_guard_and_mw_rejection(self):
        self.u.clear_status(S.STARTED)
        self.u.map=None
        self.assertTrue(prefs.safety(self.u,'off')['accepted'])
        self.assertEqual(1,self.u.prefs)
        self.u.unit_type=UnitType.MW
        self.assertFalse(prefs.safety(self.u,'on')['accepted'])
        self.assertEqual(1,self.u.prefs)

    def test_disable_gauss_is_permanent_temp_state_and_fire_rejects(self):
        from systems.enhanced_crits import part_temp_nuke,FAIL_DESTROYED
        from systems.combat import fire_weapon
        weapon=get_weapon('IS.GaussRifle')
        slot=self.u.sections[0].criticals[4]
        for crit in range(4,4 + weapon.crits):
            self.u.sections[0].criticals[crit].type=i2weapon(weapon.index)
        self.u.weapons=[WeaponState(section=0,critical=4,weapon_idx=weapon.index)]
        self.assertTrue(prefs.disable_weapon(self.u,'0')['accepted'])
        self.assertEqual(FAIL_DESTROYED,part_temp_nuke(slot))
        result=fire_weapon(self.u,None,0,1)
        self.assertIsNone(result.bth_breakdown)
        self.assertEqual(0,slot.data)

    def test_autoturret_command_toggles_bit_and_rejects_missing_turret(self):
        from entities.mech import VehicleLocation as V
        self.u.unit_type=UnitType.VEH_GROUND
        self.u.move_type=MoveType.TRACK
        self.assertTrue(prefs.auto_turret(self.u)['accepted'])
        self.assertTrue(self.u.status2 & S2.AUTOTURN_TURRET)
        self.u.sections[V.TURRET].internal=0
        self.assertFalse(prefs.auto_turret(self.u)['accepted'])
        self.assertTrue(self.u.status2 & S2.AUTOTURN_TURRET)
