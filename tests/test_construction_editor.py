import unittest
from entities.mech import Mech,Specials as S,FireMode as F,AmmoMode as A,UnitType as U
from entities.crittypes import i2special,Special


class ConstructionEditorTest(unittest.TestCase):
    def setUp(self):
        from systems.construction_editor import Editor
        self.unit=Mech();self.units={'unit':self.unit};self.editor=Editor(7,self.units)
        self.editor.target='unit'

    def command(self,name,args='',**kwargs):return self.editor.execute(name,args,**kwargs)

    def test_guard_order_and_independent_editor_target(self):
        self.editor.allocated=False
        result=self.command('resetcrits',privilege=False)
        self.assertEqual(["I'm sorry Dave, can't do that."],result['messages'])
        self.assertEqual(3,len(self.command('resetcrits')['messages']))
        self.editor.allocated=True;self.editor.target=-1
        self.assertIn('target first',self.command('resetcrits')['messages'][0])
        self.assertTrue(self.command('settarget','unit')['ok'])
        self.assertTrue(self.command('resetcrits')['ok'])
        self.assertEqual(i2special(Special.ENGINE),self.unit.sections[4].criticals[0].type)

    def test_scalar_type_and_move_fallthrough(self):
        self.command('setspeed','2.5 ignored');self.assertEqual(26.875,self.unit.max_speed)
        self.command('settons','50suffix');self.assertEqual(50,self.unit.tonnage)
        self.command('settype','N');self.assertEqual(U.VEH_NAVAL,self.unit.unit_type)
        self.assertEqual(2,len(self.command('setmove','FLY')['messages']));self.assertEqual(10,self.unit.move_type)
        self.assertEqual([],self.command('setmove','Haze')['messages']);self.assertEqual(10,self.unit.move_type)
        self.unit.specials=S.CLAN_TECH;self.command('setradio','0')
        self.assertEqual((1,2,64),(self.unit.radio,self.unit.radio_type,self.unit.radio_range))

    def test_sequential_armor_and_weapon_slot_failure(self):
        self.unit.sections[4].armor=self.unit.sections[4].armor_orig=20
        self.command('setarmor','CT -1 18 6')
        self.assertEqual((20,18,6),(self.unit.sections[4].armor,self.unit.sections[4].internal,self.unit.sections[4].rear))
        for slot in self.unit.sections[2].criticals:slot.data=7
        result=self.command('addweap','IS.PPC LT 1 2 13')
        self.assertFalse(result['ok'])
        self.assertEqual([7,7],[s.data for s in self.unit.sections[2].criticals[:2]])
        self.assertTrue(all(s.type for s in self.unit.sections[2].criticals[:2]))
        self.assertFalse(self.unit.sections[2].criticals[2].type)

    def test_runtime_inventory_preserves_unedited_mount_and_replaces_removed_one(self):
        self.command('addweap','IS.MediumLaser LT 1')
        old=self.unit.weapons[0];old.recycle=9
        self.command('addweap','IS.MediumLaser RT 1');self.assertIs(old,self.unit.weapons[0])
        self.command('addspecial','HeatSink LT 1')
        self.assertEqual(1,len(self.unit.weapons));self.assertEqual(3,self.unit.weapons[0].section)

    def test_reload_halfton_preservation_and_firemode_distinctions(self):
        self.command('reload','IS.AC/5 LT 1 +');slot=self.unit.sections[2].criticals[0];slot.ammomode=A.AC_AP_MODE
        self.command('reload','IS.AC/5 LT 1 L');self.assertEqual((128,8193,10),(slot.firemode,slot.ammomode,slot.data))
        self.command('addweap','IS.AC/5 RT 1 2 3 4 O')
        weapon=self.unit.sections[3].criticals[0];weapon.ammomode=A.AC_AP_MODE
        self.command('firemode','0 L');self.assertEqual((256,1),(weapon.firemode,weapon.ammomode))
        self.command('firemode','0 -');self.assertEqual((0,0),(weapon.firemode,weapon.ammomode))
        self.command('firemode','0 Z');self.assertEqual(0,weapon.ammomode)
        self.command('firemode','0 J');self.assertTrue(weapon.firemode&F.WILL_JETTISON_MODE)

    def test_special_modes_and_strict_tech_and_conditional_removal(self):
        slot=self.unit.sections[2].criticals[0];slot.firemode=7;slot.ammomode=3
        self.command('addspecial','Masc LT 1 7');self.assertEqual((7,3,7),(slot.firemode,slot.ammomode,slot.data))
        self.assertTrue(self.unit.specials&S.MASC_TECH)
        self.assertFalse(self.command('addtech','Clan AngelECM_Tech')['ok'])
        self.assertFalse(self.unit.specials&S.CLAN_TECH)
        self.unit.infantry_specials=1;self.command('deltech','all')
        self.assertEqual((0,7,7,3,1),(slot.type,slot.data,slot.firemode,slot.ammomode,self.unit.infantry_specials))
        # Source removes orphan MASC only if some enabling flag/config is present.
        slot.type=i2special(Special.MASC);self.command('deltech','all');self.assertEqual(i2special(Special.MASC),slot.type)

    def test_cargo_and_current_only_repair(self):
        self.command('setcargospace','5000 101');self.assertEqual((250000,100),(self.unit.cargo_space,self.unit.car_max_ton))
        self.assertFalse(self.command('setcargospace','5001 1')['ok']);self.assertEqual(250000,self.unit.cargo_space)
        self.command('setarmor','CT 20 16 5');self.command('repair','CT A')
        self.assertEqual((0,20),(self.unit.sections[4].armor,self.unit.sections[4].armor_orig))

    def test_technology_notifications_and_nonfinite_scalar_boundary(self):
        from systems.construction_editor import show_tech
        result=self.command('addspecial','ArtemisIV LT 1 4')
        self.assertEqual(["Artemis IV Fire-Control System added to 'Mech.",
            'System will control the weapon which starts at slot 4.',
            'Critical slot Left Torso (1) filled.'],result['messages'])
        self.unit.specials|=S.CLAN_TECH|S.DOUBLE_HEAT_TECH
        messages=show_tech(self.unit)['messages']
        self.assertIn('    Mech automatically has CASE in all sections',messages)
        self.assertIn('Artemis IV Fire-Control System',messages)
        before=self.unit.max_speed
        for value in ('nan','-inf','1e999','3e38'):
            self.assertFalse(self.command('setspeed',value)['ok'])
            self.assertEqual(before,self.unit.max_speed)

    def test_invalid_equipment_reports_source_catalog(self):
        result=self.command('addweap','unknown LT 1')
        self.assertFalse(result['ok']);self.assertEqual(178,len(result['catalog']['rows']))
        result=self.command('addspecial','unknown LT 1')
        self.assertFalse(result['ok']);self.assertIn('HeatSink',result['catalog']['rows'])

    def test_public_bomb_installation_uses_physical_catalog_and_location_bounds(self):
        from systems.bombing import payload
        self.unit.unit_type=U.AERO
        self.assertTrue(self.command('addbomb','Bomb_10_Standard F 12')['ok'])
        self.assertEqual(387,self.unit.sections[3].criticals[11].type)
        self.assertEqual(1,len(payload(self.unit)))
        for args in ('Bomb_10_Standard C 6','Bomb_10_Standard E 13',
                     'IS.MediumLaser F 12','unknown F 12'):
            self.assertFalse(self.command('addbomb',args)['ok'])
        self.assertEqual(387,self.unit.sections[3].criticals[11].type)
        self.assertEqual(0,self.unit.sections[4].criticals[5].type)
