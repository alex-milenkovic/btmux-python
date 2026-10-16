import unittest
from entities.mech import Mech, Location as L, FireMode as F, WeaponState
from entities.weapon import get_weapon
from entities.crittypes import i2weapon
from systems import damage_commands as commands
from systems import enhanced_crits as enhanced


class DamageCommandsTest(unittest.TestCase):
    def setUp(self):
        self.u = Mech.create_test_mech()

    def test_raw_setter_retains_atoi_and_does_not_destroy_section(self):
        self.assertEqual('1', commands.set_armor_status(self.u, 'LA', '0', '12junk'))
        self.assertEqual(12, self.u.sections[L.LARM].armor)
        self.assertEqual('1', commands.set_armor_status(self.u, 'LA', '1', 'bad'))
        self.assertEqual(0, self.u.sections[L.LARM].internal)
        self.assertFalse(self.u.is_destroyed)
        self.assertEqual('#-1 INVALID ARMORVALUE', commands.set_armor_status(self.u, 'LA', '0', '256'))

    def test_status_precedence_and_raw_mask_detail(self):
        weapon = get_weapon('IS.MediumLaser')
        self.u.weapons = [WeaponState(weapon_idx=weapon.index, section=L.RARM, critical=4)]
        slot = self.u.sections[L.RARM].criticals[4]
        slot.type = i2weapon(weapon.index)
        slot.firemode = F.DAMAGED_MODE
        slot.weap_damage_flags = enhanced.WEAP_DAM_EN_FOCUS
        self.assertEqual('DAMAGED', enhanced.weapon_status(self.u)[0]['status'])
        detail = enhanced.show_weapon_damage_and_info(self.u, L.RARM, 4)
        self.assertEqual([0, 2, 0], detail['damage_hits'])
        self.assertEqual(1, detail['damage_reduction'])
        slot.firemode |= F.DISABLED_MODE
        self.assertEqual('DISABLED', enhanced.weapon_status(self.u)[0]['status'])
        slot.firemode |= F.BROKEN_MODE
        self.assertEqual('DESTROYED', enhanced.weapon_status(self.u)[0]['status'])
