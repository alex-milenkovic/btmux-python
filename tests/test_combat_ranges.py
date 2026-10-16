"""Range diagnostics preserve fractional, underwater and C3 source quirks."""
import unittest
from dataclasses import replace
from tools.combat_resolution import CombatSession
from entities.weapon import get_weapon,WeaponFlags as W
from entities.mech import FireMode as F,MechStatus2 as S2
from systems import combat_ranges as ranges


class RangeTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[]})
        self.u,self.v=self.s.units.values()
        self.w=replace(get_weapon('IS.MediumLaser'),range_min=0,range_short=3,range_medium=6,range_long=9)

    def test_rounding_and_signature_extreme_brackets(self):
        for r,expected in ((3,('SHORT',0)),(3.06,('MED',2)),(9.06,('EXTREME',8)),(12.06,('TOFAR',1000))):
            self.assertEqual(expected,ranges.by_range(self.u,self.v,4,self.w,r))
        self.v.status2|=S2.STH_ARMOR_ON
        self.assertEqual(('EXTREME',12),ranges.by_range(self.u,self.v,4,self.w,10))

    def test_underwater_minimum_falls_through_air_range(self):
        self.u.z=-2
        w=replace(self.w,range_min_water=3,range_short_water=4,range_medium_water=6,range_long_water=9)
        self.assertEqual(('SHORT',0),ranges.by_range(self.u,self.v,4,w,2))
        self.assertEqual(('SHORT',3),ranges.by_range(self.u,self.v,4,w,0))
        self.assertEqual(('NOWATER',5000),ranges.by_range(self.u,self.v,4,replace(w,range_short_water=0),2))

    def test_c3_limits_actual_range_to_long_even_with_close_peer(self):
        self.assertEqual(('SHORT',0),ranges.by_c3_range(self.u,self.v,4,self.w,9,1))
        self.assertEqual(('TOFAR',1000),ranges.by_c3_range(self.u,self.v,4,self.w,9.06,1))

    def test_c3_inverted_hotload_minimum(self):
        w=replace(self.w,special=W.IDF,range_min=6)
        self.assertEqual(('SHORT',0),ranges.by_c3_range(self.u,self.v,4,w,2.5,1,0))
        self.assertEqual(('SHORT',4),ranges.by_c3_range(self.u,self.v,4,w,2.5,1,F.HOTLOAD_MODE))

    def test_pc_ranges_scale_before_rounding(self):
        w=replace(self.w,special=W.PC_IMPA)
        self.assertEqual(('SHORT',0),ranges.by_range(self.u,self.v,4,w,.3))
        self.assertEqual(('MED',2),ranges.by_range(self.u,self.v,4,w,.306))

    def test_normal_bth_uses_fractional_minimum_before_rounded_bracket(self):
        from systems.combat import calculate_bth
        w=replace(self.w,range_min=3)
        result=calculate_bth(self.u,self.v,w,2.5,4,4)
        self.assertEqual(1,result.range_mod)

    def test_targetless_tc_bonus_is_excluded_and_missing_spotter_returns_zero(self):
        from systems.combat import calculate_bth
        from entities.mech import MechStatus
        self.u.status|=MechStatus.LOCK_HEX
        self.assertEqual(0,calculate_bth(self.u,None,self.w,1,4,4,w_fire_mode=F.ON_TC).total)
        self.assertEqual(0,calculate_bth(self.u,self.v,self.w,1,4,4,indirect_fire=2).total)

    def test_c3_range_uses_live_peers_and_keeps_first_equal_range(self):
        from copy import deepcopy
        from entities.mech import Specials, MechStatus as S
        from systems.los import MECHLOSFLAG_SEESP
        from systems.combat import calculate_bth
        peer=deepcopy(self.v)
        peer._engine=self.s.engine
        peer.map=self.u.map
        peer._id=777
        peer.team=self.u.team
        peer.specials|=Specials.C3_SLAVE_TECH
        peer.fx,peer.fy,peer.fz=self.v.fx,self.v.fy,self.v.fz
        self.u.map.add_mech(peer)
        self.s.engine.register_entity(peer)
        peer.mapindex=self.u.mapindex
        self.u.map.losinfo[(peer._id,self.v._id)]=MECHLOSFLAG_SEESP
        self.u.specials|=Specials.C3_MASTER_TECH
        self.u.working_c3_masters=1
        self.u.c3_network=[peer]
        self.assertEqual((0,777),ranges.find_c3_range(self.u,self.v,8,True))
        b=calculate_bth(self.u,self.v,self.w,8,4,4)
        self.assertEqual(('SHORT',0,777),(b.range_bracket,b.range_mod,b.c3_ref))
        b=calculate_bth(self.u,self.v,self.w,10,4,4)
        self.assertEqual(1000,b.range_mod)
        peer.status&=~S.STARTED
        self.assertEqual((8,0),ranges.find_c3_range(self.u,self.v,8,True))
        peer.status|=S.STARTED
        self.u.working_c3_masters=0
        self.assertEqual((8,0),ranges.find_c3_range(self.u,self.v,8,True))
