"""Physical fighter weapons keep historical arcs, aiming and recycle behavior."""
import unittest
from unittest.mock import patch
from tests.test_aim import _pair
from entities.mech import UnitType as U,MechStatus as S,FireMode as F
from entities.weapon import get_weapon
from systems import combat as c
from tools.combat_resolution import CombatSession


class FighterWeaponTests(unittest.TestCase):
    def test_fuselage_covers_all_arcs_and_engine_only_rear(self):
        u,_=_pair();u.unit_type=U.AERO
        for arc in (c.FORWARDARC,c.LSIDEARC,c.RSIDEARC,c.REARARC):
            with patch('physics.hexmath.in_weapon_arc',return_value=arc):
                self.assertEqual(c.is_in_weapon_arc(u,0,0,3,0),arc)
                self.assertEqual(c.is_in_weapon_arc(u,0,0,5,0),arc if arc==c.REARARC else 0)
                self.assertEqual(c.is_in_weapon_arc(u,0,0,4,0),0)

    def test_cockpit_penalty_precedes_targeting_computer(self):
        a,t=_pair();t.unit_type=U.AERO;a.aim=4
        for started,expected in ((True,25),(False,7)):
            t.set_status(S.STARTED) if started else t.clear_status(S.STARTED)
            for mode in (0,F.ON_TC):
                self.assertEqual(c.calculate_bth(a,t,get_weapon('IS.MediumLaser'),1,w_fire_mode=mode).aim_mod,expected)

    def test_fighter_tc_engine_front_falls_back_and_cockpit_back_falls_through(self):
        a,t=_pair();t.unit_type=U.AERO;a.aim_type=U.AERO
        a.aim=5
        self.assertEqual(c.find_tc_hit_loc(a,t,success_roll=3,location_roll=7)[0],0)
        t.facing=180;a.aim=4
        self.assertEqual(c.find_tc_hit_loc(a,t,success_roll=3,location_roll=7)[0],4)

    def test_ready_weapon_fires_with_zero_armor_and_recycling_freezes(self):
        session=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0],
            'weapons':[{'name':'IS.MediumLaser','section':'LA'}]},
            {'name':'v','at':[3,2,0],'team':2}]})
        u,v=session.units.values();u.unit_type=U.AERO;u.sections[0].armor=0
        result=session.invoke(c.fire_weapon_number,session.engine,u,0,v,to_hit_roll=12)
        self.assertTrue(result.hit,result.messages)
        cooldown=u.sections[0].criticals[0].data;self.assertGreater(cooldown,0)
        session.engine.run_ticks(10)
        self.assertEqual(u.sections[0].criticals[0].data,cooldown)
