import unittest
from entities.mech import Mech, AmmoMode as A, Specials as S
from entities.weapon import get_weapon
from entities.crittypes import i2ammo, i2special, Special
from data.construction_catalog import source_part
from systems.repair_materials import valid_ammo_mode,find_ammo_type,repair_alias
from systems.parts import proper_armor


class RepairMaterialTests(unittest.TestCase):
    def setUp(self):self.unit=Mech();self.slot=self.unit.sections[4].criticals[0]
    def ammo(self,name):self.slot.type=i2ammo(get_weapon(name).index)
    def test_idf_compatibility_keeps_source_broad_atm_and_mml_modes(self):
        self.ammo('IS.LRM-15')
        self.assertEqual(valid_ammo_mode(self.unit,4,0,'H'),A.ATM_HE_MODE)
        self.assertEqual(valid_ammo_mode(self.unit,4,0,'#'),A.MML_LRM_MODE)
        self.assertEqual(valid_ammo_mode(self.unit,4,0,'I'),-1)
    def test_missile_commodity_priority_is_narc_before_artemis(self):
        self.ammo('IS.LRM-15'); self.slot.ammomode=A.NARC_MODE|A.ARTEMIS_MODE
        self.assertEqual(find_ammo_type(self.unit,4,0),519)
        self.slot.ammomode=A.ATM_HE_MODE
        self.assertEqual(find_ammo_type(self.unit,4,0),516)
    def test_ammo_ac_later_mode_overwrites_earlier(self):
        self.ammo('IS.AC/10'); self.slot.ammomode=A.AC_AP_MODE|A.AC_PRECISION_MODE
        self.assertEqual(find_ammo_type(self.unit,4,0),source_part('Ammo_AC10_Precision'))
    def test_source_material_precedence(self):
        self.unit.specials2=1|2
        self.assertEqual(proper_armor(self.unit),source_part('STH_Armor'))
        self.unit.specials=S.XXL_TECH|S.CE_TECH
        self.assertEqual(repair_alias(self.unit,i2special(Special.ENGINE)),source_part('XXL_Engine'))
    def test_purifier_retains_source_cargo_offset_collision(self):
        self.unit.infantry_specials=8
        self.assertEqual(proper_armor(self.unit),553)

if __name__=='__main__':unittest.main()
