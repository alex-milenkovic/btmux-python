"""Movement sources and additive to-hit terms from mech.bth.c."""
import unittest
from dataclasses import replace
from tools.combat_resolution import CombatSession
from entities.mech import UnitType as U, MoveType as M, MechStatus as S, Specials
from entities.weapon import get_weapon
from core.events import EventType as E
from systems.combat import calculate_attacker_movement_modifier as attack_move
from systems.combat import calculate_target_movement_modifier as target_move, calculate_bth


class BTHCompletionTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[]})
        self.u,self.v=self.s.units.values()
        self.w=get_weapon('IS.MediumLaser')

    def test_attacker_turning_reverse_tsm_and_battlesuit_precedence(self):
        self.u.desired_facing=self.u.facing+1
        self.assertEqual(1,attack_move(self.u))
        self.u.speed=-100
        self.assertEqual(2,attack_move(self.u))
        self.u.desired_facing=self.u.facing
        self.assertEqual(1,attack_move(self.u))
        self.u.max_speed=60
        self.u.speed=45
        self.assertEqual(2,attack_move(self.u))
        self.u.heat=9
        self.u.specials|=Specials.TRIPLE_MYOMER_TECH
        self.assertEqual(1,attack_move(self.u))
        self.u.unit_type=U.BSUIT
        self.u.status|=S.JUMPING
        self.assertEqual(0,attack_move(self.u))

    def test_quad_prone_and_pending_posture(self):
        self.u.status|=S.FALLEN
        self.u.move_type=M.QUAD
        self.assertEqual(0,attack_move(self.u))
        self.u.sections[0].internal=0
        self.u.sections[0].armor=0
        self.assertEqual(2,attack_move(self.u))
        self.u.status&=~S.FALLEN
        self.s.engine.events.schedule(12,E.JUMPSTABIL,lambda e:None,data=self.u)
        self.assertEqual(2,attack_move(self.u))

    def test_target_aero_swarm_and_purifier_speed_sources(self):
        self.v.unit_type=U.AERO
        self.v.speed=0
        self.v.vertical_speed=50
        self.assertEqual(2,target_move(self.v,2,self.u))
        self.u.unit_type=U.AERO
        self.assertEqual(0,target_move(self.v,2,self.u))
        self.v.unit_type=U.BSUIT
        self.v.swarming=self.u._id
        self.u.speed=50
        self.assertEqual(2,target_move(self.v,2,self.u))
        self.v.swarming=999999
        self.v.infantry_specials=8
        self.assertEqual(3,target_move(self.v,2,self.u))
        self.v.swarming=-1
        self.v.speed=21.51
        self.assertEqual(0,target_move(self.v,2,self.u))

    def test_unit_class_and_stealth_terms(self):
        for kind,mod in ((U.MW,2),(U.BSUIT,1),(U.DS,-3)):
            self.v.unit_type=kind
            self.assertEqual(mod,calculate_bth(self.u,self.v,self.w,1,4,4).other_mods)
        self.v.unit_type=U.MECH
        for flag,expected in ((0x20,1),(0x10,0),(0x40,0),(0x80,1)):
            self.v.infantry_specials=flag
            self.assertEqual(expected,calculate_bth(self.u,self.v,self.w,1,4,4).other_mods)
        self.v.infantry_specials=0x20
        w=replace(self.w,range_min=3)
        self.assertEqual(0,calculate_bth(self.u,self.v,w,1,4,4).other_mods)

    def test_aero_target_movement_scales_before_precision(self):
        from entities.mech import AmmoMode as A
        self.u.unit_type=U.AERO
        self.v.speed=70
        self.assertEqual(2,calculate_bth(self.u,self.v,self.w,1,4,4).target_move)
        self.assertEqual(0,calculate_bth(self.u,self.v,self.w,1,4,4,w_ammo_mode=A.AC_PRECISION_MODE).target_move)

    def test_flying_stinger_aa_and_vtol_are_additive(self):
        from entities.mech import AmmoMode as A
        self.v.unit_type=U.VTOL
        self.v.move_type=M.VTOL
        self.v.status&=~S.LANDED
        self.v.vertical_speed=1
        self.u.targcomp=4
        b=calculate_bth(self.u,self.v,self.w,1,4,4,w_ammo_mode=A.STINGER_MODE)
        self.assertEqual(-2,b.other_mods)
        self.assertEqual(-2,b.targcomp_mod)
        self.v.status|=S.LANDED
        b=calculate_bth(self.u,self.v,self.w,1,4,4,w_ammo_mode=A.STINGER_MODE)
        self.assertEqual(1,b.other_mods)
        self.assertEqual(1,b.targcomp_mod)
