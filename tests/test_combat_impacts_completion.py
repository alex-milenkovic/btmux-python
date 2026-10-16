"""Damage shaping and glancing thresholds through real impact resolution."""
import unittest
from dataclasses import replace
from unittest.mock import patch
from tools.combat_resolution import CombatSession
from entities.weapon import get_weapon,WeaponFlags as W
from entities.mech import UnitType as U,AmmoMode as A,FireMode as F
from systems.combat import resolve_attack


class ImpactCompletionTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[]})
        self.u,self.v=self.s.units.values()
        self.w=replace(get_weapon('IS.MediumLaser'),damage=9)
        self.s.streams.update(damage_entry=[7]*100,critical_rolls=[7]*100)

    def damage(self,weapon=None,distance=1,**kw):
        from systems.combat_impacts import determine_damage
        from physics.hexmath import SCALEMAP
        self.v.fx,self.v.fy,self.v.fz=self.u.fx+distance*SCALEMAP,self.u.fy,self.u.fz
        return self.s.invoke(determine_damage,self.u,self.v,weapon or self.w,distance,4,0,**kw)

    def test_hvy_gauss_and_snub_ranges(self):
        for name,values in (('IS.HeavyGaussRifle',(25,20,10)),('IS.SnubNosedPPC',(10,8,5))):
            weapon=get_weapon(name)
            self.assertIsNotNone(weapon)
            for distance,expected in zip((1,weapon.range_short+.1,weapon.range_medium+.1),values):
                self.assertEqual(expected,self.damage(weapon,distance))

    def test_flechette_incendiary_and_battlesuit_exclusion(self):
        self.v.unit_type=U.MW
        self.assertEqual(36,self.damage(ammo_mode=A.AC_FLECHETTE_MODE))
        self.assertEqual(11,self.damage(ammo_mode=A.AC_INCENDIARY_MODE))
        self.v.unit_type=U.BSUIT
        self.assertEqual(9,self.damage(ammo_mode=A.AC_FLECHETTE_MODE))
        self.v.unit_type=U.MECH
        self.assertEqual(4,self.damage(ammo_mode=A.AC_FLECHETTE_MODE))

    def test_energy_range_and_failure_floor(self):
        self.s.engine.moddamagewithrange=1
        self.assertEqual(10,self.damage())
        self.assertEqual(8,self.damage(distance=7))
        self.assertEqual(4,self.damage(distance=10))
        self.assertEqual(1,self.damage(failure_type='DAMAGE',failure_modifier=99))

    def test_woods_absorb_and_clear_only_on_actual_hit(self):
        from entities.map import LIGHT_FOREST
        self.s.map.set_terrain(self.v.x,self.v.y,LIGHT_FOREST)
        self.s.engine.moddamagewithwoods=1
        with patch('systems.combat.possibly_ignite_or_clear') as clear:
            self.assertEqual(9,self.damage(temporary=True))
            clear.assert_not_called()
            self.assertEqual(7,self.damage())
            self.assertEqual(9,clear.call_args.args[3])

    def test_glancing_modes_at_threshold_and_neighbors(self):
        for mode,roll,damage in ((0,6,0),(0,7,9),(1,6,0),(1,7,5),(1,8,9),(2,5,0),(2,6,5),(2,7,9)):
            with self.subTest(mode=mode,roll=roll):
                self.setUp()
                for sec in self.v.sections:sec.armor=sec.rear=200;sec.internal=100
                self.s.engine.glancing_blows=mode
                result=self.s.invoke(resolve_attack,self.u,self.v,self.w,1,7,to_hit_roll=roll,location_roll=7)
                self.assertEqual(damage,result.damage_dealt)

    def test_ordinary_missile_miss_does_not_roll_cluster_or_activate_ams(self):
        # HitTarget tests player_roll against the unlowered missile BTH.
        from systems import missile
        for mode in (0, 1, 2):
            with self.subTest(glancing=mode), \
                    patch('systems.combat._missile_weapon_hit') as dispatch, \
                    patch.object(missile,'locate_ams_defenses',return_value=None) as ams, \
                    patch.object(missile,'missile_hit_index') as cluster:
                self.s.engine.glancing_blows=mode
                r=self.s.invoke(resolve_attack,self.u,self.v,get_weapon('IS.SRM-6'),1,7,to_hit_roll=6)
                self.assertEqual(7,r.bth)
                self.assertFalse(r.hit)
                self.assertEqual(0,r.damage_dealt)
                self.assertFalse(any(text.startswith('Attack hit!') for text in r.messages))
                dispatch.assert_not_called()
                ams.assert_not_called()
                cluster.assert_not_called()
                self.assertEqual([],self.s.draws)

    def test_flamer_heat_uses_base_damage_even_when_glancing(self):
        self.s.engine.glancing_blows=1
        weapon=replace(self.w,name='IS.Flamer')
        self.v.weap_heat=10
        self.s.invoke(resolve_attack,self.u,self.v,weapon,1,7,to_hit_roll=7,w_fire_mode=F.HEAT_MODE)
        self.assertEqual(19,self.v.weap_heat)
