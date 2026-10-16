"""Durable source XP producers and float arithmetic independent of fixtures."""
import unittest
from types import SimpleNamespace
from core.game_loop import GameEngine
from core.randomness import use_source
from data.characters import CharacterStore,ALL,SKILLS
from data.character_values import code
from entities.mech import Mech,UnitType as U,MechStatus as S,MechStatus2
from entities.weapon import get_weapon,WeaponType as T
from systems.characters import set_value
from systems import experience as x

class CharacterAwardsTest(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.engine.sim_now=101
        self.store=CharacterStore();self.unit=Mech.create_test_mech();self.target=Mech.create_test_mech()
        self.unit._id=10;self.target._id=20
        for u in (self.unit,self.target):u._engine=self.engine;u.in_character=True;u.status=S.STARTED;u.mech_bv=100;u.max_speed=43
        self.unit.team=1;self.target.team=2
        self.store.create(101,'Alice',location=10);self.actor=self.store.actor(101);self.unit.pilot=self.actor
        for name,val in dict(Build=5,Reflexes=5,Intuition=5,Learn=5,Charisma=5).items():set_value(self.store,101,name,val)
        set_value(self.store,101,'Gunnery-Battlemech',4)
        self.weapon=get_weapon('IS.MediumLaser')

    def raw(self,name):return self.store.retrieve(101,SKILLS).xp[code(name)]%16777216

    def test_selected_skills_receive_xp_without_migrating_character_values(self):
        from copy import deepcopy
        from systems import piloting
        for gun_mode, pilot_mode in ((False, False), (True, True), (True, False), (False, True)):
            with self.subTest(gunnery=gun_mode, piloting=pilot_mode):
                self.setUp()
                values = {'Gunnery-Battlemech': 4, 'Gunnery-Laser': 1,
                          'Piloting-Battlemech': 3, 'Piloting-Biped': 2}
                for name, value in values.items(): set_value(self.store, 101, name, value)
                records = deepcopy(self.store.records)
                self.engine.extended_gunnery, self.engine.extended_piloting = gun_mode, pilot_mode
                self.assertEqual(7 if gun_mode else 4, piloting.find_pilot_gunnery(self.unit, self.weapon))
                self.assertEqual(6 if pilot_mode else 5, piloting.find_pilot_piloting(self.unit))
                self.assertEqual(records, self.store.records)
                weapon = self.config()
                self.assertTrue(x.gun(self.actor, self.unit, self.target, 10, 100, weapon, 8))
                self.assertTrue(x.piloting(self.actor, self.unit, 2, True))
                self.assertEqual((0, 10) if gun_mode else (10, 0),
                    (self.raw('Gunnery-Battlemech'), self.raw('Gunnery-Laser')))
                self.assertEqual((0, 2) if pilot_mode else (2, 0),
                    (self.raw('Piloting-Battlemech'), self.raw('Piloting-Biped')))
                for name, value in values.items():
                    self.assertEqual(value, self.store.retrieve(101).get(name))

    def test_pilot_position_updates_and_sk_xp_allows_repeated_gain(self):
        self.unit.x=self.unit.y=2;self.unit.lx=self.unit.ly=1
        self.assertTrue(x.piloting(self.actor,self.unit,3,False));self.assertEqual(3,self.raw('Piloting-Battlemech'))
        self.assertEqual((2,2),(self.unit.lx,self.unit.ly))
        self.unit.x=3
        self.assertTrue(x.piloting(self.actor,self.unit,3,False));self.assertEqual(3,self.unit.lx)
        self.engine.sim_now=132
        self.assertTrue(x.piloting(self.actor,self.unit,2,True));self.assertEqual(8,self.raw('Piloting-Battlemech'))

    def test_producer_eligibility_and_exact_supplied_pilot(self):
        self.assertTrue(x.tech(self.actor,self.unit,0));self.assertEqual(1,self.raw('Technician-Battlemech'))
        self.assertTrue(x.tech(self.actor,None,3));self.assertEqual(3,self.raw('Technician-Weapons'))
        self.actor.connected=False;self.assertFalse(x.comm(self.actor,self.unit));self.actor.connected=True
        self.assertTrue(x.spot(self.actor,self.unit,self.target));self.assertEqual(1,self.raw('Gunnery-Spotting'))
        self.target.team=1;self.assertFalse(x.artillery(self.actor,self.unit,self.target))
        self.assertFalse(x.computer(self.actor,None,3))

    def test_null_unit_tech_award_applies_exact_channel_request(self):
        self.assertTrue(x.tech(self.actor,None,3))
        self.assertEqual(3,self.raw('Technician-Weapons'))
        effect=self.store.channel_requests[-1]
        self.assertEqual('MechTechXP',effect['source_channel'])
        self.assertEqual('Alice gained 3 technician-weapons XP (changing mech #-1)',effect['text'])
        self.assertTrue(effect['applied'])

    def test_computer_reports_original_reason_only_when_gain_is_accepted(self):
        self.assertTrue(x.computer(self.actor,self.unit,-3))
        self.assertEqual(1,self.raw('Computer'))
        effects=list(self.unit.channel_requests)
        self.assertEqual('Alice gained -3 computer XP (mech #10)',effects[-1]['text'])
        self.assertTrue(effects[-1]['applied'])
        self.assertFalse(x.computer(self.actor,self.unit,-4))
        self.assertEqual(effects,self.unit.channel_requests)

    def test_perception_cache_source_roll_and_cooldown_result(self):
        set_value(self.store,101,'Perception',2);self.unit.per=0
        with use_source(lambda *args:6):self.assertTrue(x.perception(self.unit,-2))
        self.assertEqual(8,self.unit.per);self.assertEqual(1,self.raw('Perception'))
        with use_source(lambda *args:6):self.assertTrue(x.perception(self.unit,-2))
        self.assertEqual(1,self.raw('Perception'))

    def config(self,**overrides):
        self.engine.xp_config=x.Config(oldxpsystem=False,xp_modifier=1,defaultweapbv=100,defaultweapdam=10,
            use_pilot_bv=False,xpgain_cap=100,missilemod=1,ammomod=1,**overrides)
        return SimpleNamespace(index=self.weapon.index,name=self.weapon.name,weapon_type=T.TBEAM,bv=100,vrt=30)

    def test_new_arithmetic_class_vrt_perunit_cap_without_old_draw(self):
        weapon=self.config()
        with use_source(lambda *args: (_ for _ in ()).throw(AssertionError('new random gate'))):
            self.assertEqual(10,x.gun_amount(self.unit,self.target,10,100,weapon,8))
            self.engine.xp_config.missilemod=.5;weapon.weapon_type=T.TMISSILE
            self.assertEqual(5,x.gun_amount(self.unit,self.target,10,100,weapon,8))
            weapon.weapon_type=T.TBEAM;self.engine.xp_config.vrtmod=True;weapon.vrt=7.5
            self.assertEqual(5,x.gun_amount(self.unit,self.target,10,100,weapon,8))
            weapon.vrt=30;self.unit.xp_mod=2;self.assertEqual(20,x.gun_amount(self.unit,self.target,10,100,weapon,8))
            self.engine.xp_config.xpgain_cap=3;self.assertEqual(3,x.gun_amount(self.unit,self.target,10,100,weapon,8))

    def test_gun_new_and_old_gate_differences(self):
        weapon=self.config();self.target.status2|=MechStatus2.NO_GUN_XP
        self.assertFalse(x.gun(self.actor,self.unit,self.target,10,100,weapon,8))
        self.engine.xp_config.oldxpsystem=True
        with use_source(lambda *args:1):self.assertTrue(x.gun(self.actor,self.unit,self.target,10,100,weapon,8))
        self.assertGreater(self.raw('Gunnery-Battlemech'),0)
        self.assertFalse(x.gun(self.actor,self.unit,self.target,10,100,weapon,2))

    def test_pilot_bv_extremes_and_old_gate_boundary(self):
        for gun,pilot,result in ((-1,0,2.25),(4,5,1),(8,0,.15),(10,0,-.05)):
            self.assertAlmostEqual(result,x.pilot_bv_factor(gun,pilot),places=6)
        with use_source(lambda *args:20):self.assertEqual(1,x.old_probability(20))
        with use_source(lambda *args:21):self.assertEqual(0,x.old_probability(20))
        with use_source(lambda *args:50):self.assertEqual(50,x.old_probability(6000))

    def test_real_psr_award_mutates_character_once(self):
        from systems.piloting import make_piloting_roll
        set_value(self.store,101,'Piloting-Battlemech',1)
        with use_source(lambda name,lo,hi,fallback:hi):result=make_piloting_roll(self.unit,0)
        self.assertTrue(result.success);self.assertEqual(1,self.raw('Piloting-Battlemech'))
        self.assertEqual(1,len(self.unit.xp_requests));self.assertTrue(self.unit.xp_requests[0]['applied'])

    def test_damage_routes_original_amount_once_before_personal_conversion(self):
        from systems.combat import apply_damage_with_transfer
        from unittest.mock import patch
        self.unit.unit_type=self.target.unit_type=U.MW
        for s in self.target.sections:s.internal=10000;s.armor=0
        seen=[]
        def number(name,lo,hi,fallback):seen.append(name);return lo
        with patch('systems.experience.gun',return_value=True) as gun,use_source(number):
            apply_damage_with_transfer(self.target,4,9,attacker=self.unit,weapon=self.weapon,bth=8)
        self.assertEqual(1,gun.call_count);self.assertEqual(9,gun.call_args.args[3])
        self.assertEqual(9,seen.count('personal_conversion'))
        self.target.set_status(S.COMBAT_SAFE)
        with patch('systems.experience.gun') as gun,use_source(number):
            apply_damage_with_transfer(self.target,4,9,attacker=self.unit,weapon=self.weapon,bth=8)
        gun.assert_not_called()

    def test_empty_mw_location_transfer_does_not_convert_or_award_twice(self):
        from systems.combat import apply_damage_with_transfer
        from unittest.mock import patch
        self.unit.unit_type=self.target.unit_type=U.MW
        for s in self.target.sections:s.internal=10000;s.armor=0
        self.target.sections[0].internal=0;seen=[]
        with patch('systems.experience.gun',return_value=True) as gun,use_source(lambda name,lo,hi,fallback:(seen.append(name) or lo)):
            apply_damage_with_transfer(self.target,0,2,attacker=self.unit,weapon=self.weapon,bth=8)
        self.assertEqual(1,gun.call_count);self.assertEqual(2,seen.count('personal_conversion'))
        self.assertEqual(0,seen.count('personal_variation'))

    def test_successful_close_sensor_detection_consumes_xp_gate_then_perception_roll(self):
        from entities.map import GameMap
        from systems.sensors import sensor_sees
        board=GameMap(12,12)
        for u in (self.unit,self.target):board.add_mech(u);u.set_hex_position(3,3)
        set_value(self.store,101,'Perception',2);self.unit.per=6;seen=[]
        def draws(name,lo,hi,fallback):
            seen.append(name);return 0 if name=='sensor.perception_xp' else 6
        with use_source(draws):self.assertTrue(sensor_sees(self.unit,self.target,0,1,0,0,1,30,2))
        self.assertEqual(['sensor.perception_xp','perception_rolls'],seen)
        self.assertEqual(1,self.raw('Perception'))

    def test_tenth_completed_ic_hex_awards_once_and_updates_last_award_position(self):
        from entities.map import GameMap
        from physics.movement import on_hex_entered
        board=GameMap(30,30);board.add_mech(self.unit)
        self.unit.set_hex_position(10,10);self.unit.hexes_walked=8
        on_hex_entered(self.unit,9,10)
        self.assertEqual(0,self.raw('Piloting-Battlemech'))
        self.unit.set_hex_position(11,10);on_hex_entered(self.unit,10,10)
        self.assertEqual(1,self.raw('Piloting-Battlemech'))
        self.assertEqual((11,10),(self.unit.lx,self.unit.ly))

    def test_touchdown_persists_first_margin_award(self):
        from physics.orbital import _touchdown_margin
        from unittest.mock import patch
        with patch('physics.orbital._touchdown_target',return_value=5),use_source(lambda *args:6):
            self.assertEqual(2,_touchdown_margin(self.unit))
        self.assertEqual(4,self.raw('Piloting-Battlemech'))

    def test_spotted_fire_awards_both_characters_only_for_actual_fire(self):
        from tests.test_spot import SpotFixture
        from systems.spot import fire_spot
        from unittest.mock import patch
        f=SpotFixture();f.setUp();f.link();f.spot_lock()
        f.engine.sim_now=101;f.tgt.team=2
        for unit,ident in ((f.att,101),(f.spt,102)):
            if ident==102:self.store.create(ident,'Bob',location=unit._id)
            actor=self.store.actor(ident);actor.location=unit._id;unit.pilot=actor;unit.in_character=True
        f.tgt.in_character=True
        with patch('systems.combat.fire_weapon',return_value='fired'):
            fire_spot(f.engine,f.att,3,sight=True)
            self.assertEqual(0,self.raw('Gunnery-Artillery'))
            self.assertEqual('fired',fire_spot(f.engine,f.att,3))
        self.assertEqual(1,self.raw('Gunnery-Artillery'))
        self.assertEqual(1,self.store.retrieve(102,SKILLS).xp[code('Gunnery-Spotting')])
