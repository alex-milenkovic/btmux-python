"""
Tests for systems/los.py — the LOS geometry layer (mech.los.c, map.los.c,
mech.lostracer.c ports).
"""

import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.map import (
    GameMap, GRASSLAND, LIGHT_FOREST, HEAVY_FOREST, WATER, MOUNTAINS,
    FIRE, SMOKE,
)
from entities.mech import Mech, MechStatus, CritStatus, UnitType, Specials
import systems.los as los
from systems.los import (
    MECHLOSFLAG_SEEN, MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS, MECHLOSFLAG_SEEC2,
    MECHLOSFLAG_MNTN, MECHLOSFLAG_WOOD, MECHLOSFLAG_WATER, MECHLOSFLAG_PARTIAL,
    MECHLOSFLAG_FIRE, MECHLOSFLAG_SMOKE, MECHLOSFLAG_BLOCK,
    MECHLOSMAX_WOOD, MECHLOSMAX_WATER,
    trace_los, get_adj_hex, calculate_los_flag, actual_elevation,
    add_terrain_mod, in_line_of_sight, in_line_of_sight_nb,
    mech_los_flag_wood_count, mech_los_flag_water_count,
    mech_to_mech_los_flag,
)


def make_map(width=20, height=20):
    """Flat grass map with sane visibility (map_update-style values)."""
    gamemap = GameMap(width, height)
    gamemap.mapvis = 30
    gamemap.maxvis = 60
    gamemap.maplight = 2
    return gamemap


def make_mech(gamemap, x, y, z=0, name="M"):
    mech = Mech(name=name)
    mech.set_hex_position(x, y, z)
    gamemap.add_mech(mech)
    return mech


def adjacent(a, b):
    """b is one of a's six neighbours (per GetAdjHex)."""
    return b in [get_adj_hex(a[0], a[1], d) for d in range(6)]


class TestTraceLOS(unittest.TestCase):
    """TraceLOS (mech.lostracer.c:208-431)."""

    def setUp(self):
        self.map = make_map()

    def test_same_hex(self):
        # THE base case: just the end hex (mech.lostracer.c:245-249)
        self.assertEqual(trace_los(self.map, 3, 3, 3, 3), [(3, 3)])

    def test_vertical_south(self):
        # start excluded, end included (mech.lostracer.c:251-261)
        self.assertEqual(trace_los(self.map, 2, 1, 2, 5),
                         [(2, 2), (2, 3), (2, 4), (2, 5)])

    def test_vertical_north(self):
        self.assertEqual(trace_los(self.map, 2, 5, 2, 1),
                         [(2, 4), (2, 3), (2, 2), (2, 1)])

    def test_90_degree_tie_prefers_higher_hex(self):
        # (2,3)->(6,3): each odd column is a tie; equal elevation stores the
        # second candidate (Store_BestOf else branch, mech.lostracer.c:168)
        coords = trace_los(self.map, 2, 3, 6, 3)
        self.assertEqual(coords[-1], (6, 3))
        self.assertNotIn((2, 3), coords)
        self.assertIn((3, 4), coords)
        # raising a tie candidate's elevation makes it win (defender-best)
        self.map.set_elevation(3, 3, 2)
        coords = trace_los(self.map, 2, 3, 6, 3)
        self.assertIn((3, 3), coords)
        self.assertNotIn((3, 4), coords)

    def test_general_case_path_properties(self):
        # (0,0)->(3,2) is none of the special cases: connected chain of
        # adjacent hexes, start excluded, end last.
        coords = trace_los(self.map, 0, 0, 3, 2)
        self.assertEqual(coords[-1], (3, 2))
        self.assertNotIn((0, 0), coords)
        path = [(0, 0)] + coords
        for a, b in zip(path, path[1:]):
            self.assertTrue(adjacent(a, b), f"{a} -> {b} not adjacent")
        self.assertEqual(len(set(coords)), len(coords))

    def test_30_degree_tie_direction(self):
        # (2,2)->(4,5): |dy| == 3*|dx|/2 -> the 30-degree special case
        # (mech.lostracer.c:285-334)
        coords = trace_los(self.map, 2, 2, 4, 5)
        self.assertEqual(coords[-1], (4, 5))
        self.assertNotIn((2, 2), coords)
        path = [(2, 2)] + coords
        for a, b in zip(path, path[1:]):
            self.assertTrue(adjacent(a, b), f"{a} -> {b} not adjacent")


class TestCalculateLOSFlag(unittest.TestCase):
    """CalculateLOSFlag (mech.los.c:61-284) over a vertical trace."""

    def setUp(self):
        self.map = make_map()
        self.mech = make_mech(self.map, 5, 2)

    def flag_to_hex(self, x, y, hex_range=6.0, ff=0):
        return calculate_los_flag(self.mech, None, self.map, x, y, ff,
                                  hex_range)

    def test_clear_ground_no_block(self):
        flag = self.flag_to_hex(5, 8)
        self.assertEqual(flag, MECHLOSFLAG_SEEC2)

    def test_seen_bit_preserved_from_previous_flag(self):
        # new_flag = (ff & SEEN) + SEEC2 (mech.los.c:64)
        ff = MECHLOSFLAG_SEEN | MECHLOSFLAG_SEESP | MECHLOSFLAG_BLOCK
        flag = self.flag_to_hex(5, 8, ff=ff)
        self.assertEqual(flag, MECHLOSFLAG_SEEN | MECHLOSFLAG_SEEC2)

    def test_off_map_hex_target_blocks(self):
        # mech.los.c:80-83
        flag = self.flag_to_hex(-1, 8)
        self.assertTrue(flag & MECHLOSFLAG_BLOCK)

    def test_beyond_maxvis_blocks(self):
        # mech.los.c:85-90
        flag = self.flag_to_hex(5, 8, hex_range=61.0)
        self.assertTrue(flag & MECHLOSFLAG_BLOCK)

    def test_aa_tech_extends_range_to_180(self):
        self.mech.specials |= Specials.AA_TECH
        flag = self.flag_to_hex(5, 8, hex_range=61.0)
        self.assertFalse(flag & MECHLOSFLAG_BLOCK)

    def test_both_above_10_always_los(self):
        # mech.los.c:105-106
        self.mech.z = 10                      # pos_z = 11.5
        target = make_mech(self.map, 5, 8, z=10)
        self.map.set_elevation(5, 5, 9)       # would block at ground level
        flag = calculate_los_flag(self.mech, target, self.map, 5, 8, 0, 6.0)
        self.assertEqual(flag, MECHLOSFLAG_SEEC2)

    def test_same_hex_always_los(self):
        target = make_mech(self.map, 5, 2)
        flag = calculate_los_flag(self.mech, target, self.map, 5, 2, 0, 0.0)
        self.assertEqual(flag, MECHLOSFLAG_SEEC2)

    def test_light_woods_count_one(self):
        self.map.set_terrain(5, 5, LIGHT_FOREST)
        flag = self.flag_to_hex(5, 8)
        self.assertEqual(mech_los_flag_wood_count(flag), 1)
        self.assertFalse(flag & MECHLOSFLAG_BLOCK)

    def test_heavy_woods_count_two(self):
        self.map.set_terrain(5, 5, HEAVY_FOREST)
        flag = self.flag_to_hex(5, 8)
        self.assertEqual(mech_los_flag_wood_count(flag), 2)

    def test_mixed_woods_accumulate(self):
        self.map.set_terrain(5, 4, LIGHT_FOREST)
        self.map.set_terrain(5, 5, HEAVY_FOREST)
        self.map.set_terrain(5, 6, HEAVY_FOREST)
        flag = self.flag_to_hex(5, 8)
        self.assertEqual(mech_los_flag_wood_count(flag), 5)

    def test_woods_in_target_hex_not_counted(self):
        # i < coordcount - 1 rule (mech.los.c:213)
        self.map.set_terrain(5, 8, HEAVY_FOREST)
        flag = self.flag_to_hex(5, 8)
        self.assertEqual(mech_los_flag_wood_count(flag), 0)

    def test_woods_saturate_at_bounded_max(self):
        # BOUNDED(0, woods, MECHLOSMAX_WOOD - 1) (mech.los.c:274)
        self.mech.set_hex_position(5, 1)
        for yy in range(2, 12):
            self.map.set_terrain(5, yy, HEAVY_FOREST)   # 10 * 2 = 20
        flag = self.flag_to_hex(5, 12, hex_range=11.0)
        self.assertEqual(mech_los_flag_wood_count(flag), MECHLOSMAX_WOOD - 1)

    def test_shallow_water_counts(self):
        self.map.set_terrain(5, 5, WATER)     # depth 0
        flag = self.flag_to_hex(5, 8)
        self.assertEqual(mech_los_flag_water_count(flag), 1)
        self.assertFalse(flag & MECHLOSFLAG_BLOCK)

    def test_deep_water_hex_target_is_other_world(self):
        # land viewer to an underwater hex: one-world mismatch blocks
        # (mech.los.c:133-137)
        self.map.set_terrain(5, 8, WATER)
        self.map.set_elevation(5, 8, 2)       # end_z = -2 + 0.1
        flag = self.flag_to_hex(5, 8)
        self.assertTrue(flag & MECHLOSFLAG_BLOCK)

    def test_intervening_hill_blocks(self):
        # height >= pos_z && terrain != BRIDGE (mech.los.c:246-249)
        self.map.set_elevation(5, 5, 2)
        flag = self.flag_to_hex(5, 8)
        self.assertTrue(flag & MECHLOSFLAG_BLOCK)

    def test_low_mountains_set_mntn_flag(self):
        self.map.set_terrain(5, 5, MOUNTAINS)  # elev 0: under LOS, in range
        flag = self.flag_to_hex(5, 8)
        self.assertTrue(flag & MECHLOSFLAG_MNTN)
        self.assertFalse(flag & MECHLOSFLAG_BLOCK)

    def test_fire_and_smoke_flags(self):
        self.map.set_terrain(5, 4, FIRE)
        self.map.set_terrain(5, 6, SMOKE)
        flag = self.flag_to_hex(5, 8)
        self.assertTrue(flag & MECHLOSFLAG_FIRE)
        self.assertTrue(flag & MECHLOSFLAG_SMOKE)

    def test_fire_in_target_hex_not_flagged(self):
        # i < coordcount - 1 rule (mech.los.c:202-208)
        self.map.set_terrain(5, 8, FIRE)
        flag = self.flag_to_hex(5, 8)
        self.assertFalse(flag & MECHLOSFLAG_FIRE)

    def test_partial_cover_from_hex_before_target(self):
        # BT_PARTIAL rule: elevation of hex-before-target == MechZ(target)+1
        # (mech.los.c:261-266)
        target = make_mech(self.map, 5, 8)
        self.map.set_elevation(5, 7, 1)
        flag = calculate_los_flag(self.mech, target, self.map, 5, 8, 0, 6.0)
        self.assertTrue(flag & MECHLOSFLAG_PARTIAL)
        self.assertFalse(flag & MECHLOSFLAG_BLOCK)

    def test_no_partial_for_fallen_target(self):
        # dopartials requires a non-fallen CLASS_MECH (mech.los.c:140-141)
        target = make_mech(self.map, 5, 8)
        target.set_status(MechStatus.FALLEN)
        self.map.set_elevation(5, 7, 1)
        flag = calculate_los_flag(self.mech, target, self.map, 5, 8, 0, 6.0)
        self.assertFalse(flag & MECHLOSFLAG_PARTIAL)

    def test_partial_cover_half_submerged_target(self):
        # MechZ(target) == -1 && MechRTerrain(target) == WATER
        # (mech.los.c:267-268)
        self.map.set_terrain(5, 8, WATER)
        self.map.set_elevation(5, 8, 1)
        target = make_mech(self.map, 5, 8, z=-1)
        flag = calculate_los_flag(self.mech, target, self.map, 5, 8, 0, 6.0)
        self.assertTrue(flag & MECHLOSFLAG_PARTIAL)
        self.assertEqual(mech_los_flag_water_count(flag), 1)
        self.assertFalse(flag & MECHLOSFLAG_BLOCK)


class TestUnderwaterLOS(unittest.TestCase):
    """The underwater branch of CalculateLOSFlag (mech.los.c:178-196, 278-282)."""

    def setUp(self):
        self.map = make_map()

    def submerged_mech(self, x, y, depth):
        self.map.set_terrain(x, y, WATER)
        self.map.set_elevation(x, y, depth)
        mech = make_mech(self.map, x, y, z=-depth)
        mech.set_status(MechStatus.FALLEN)    # eye at z + 0.5, underwater
        return mech

    def prep_channel(self, y0, y1, depth=2):
        for yy in range(y0, y1 + 1):
            self.map.set_terrain(5, yy, WATER)
            self.map.set_elevation(5, yy, depth)

    def test_underwater_to_underwater_counts_uwater(self):
        # 6 underwater hexes: > 2 sets MNTN (EM block), <= 6 leaves FIRE
        # clear (mech.los.c:278-282)
        self.prep_channel(2, 8)
        mech = self.submerged_mech(5, 2, 2)
        target = self.submerged_mech(5, 8, 2)
        flag = calculate_los_flag(mech, target, self.map, 5, 8, 0, 6.0)
        self.assertFalse(flag & MECHLOSFLAG_BLOCK)
        self.assertTrue(flag & MECHLOSFLAG_MNTN)
        self.assertFalse(flag & MECHLOSFLAG_FIRE)
        self.assertEqual(mech_los_flag_water_count(flag), 6)

    def test_seven_underwater_hexes_set_fire_bit_too(self):
        self.prep_channel(2, 9)
        mech = self.submerged_mech(5, 2, 2)
        target = self.submerged_mech(5, 9, 2)
        flag = calculate_los_flag(mech, target, self.map, 5, 9, 0, 7.0)
        self.assertTrue(flag & MECHLOSFLAG_MNTN)
        self.assertTrue(flag & MECHLOSFLAG_FIRE)

    def test_water_count_saturates(self):
        # BOUNDED(0, water, MECHLOSMAX_WATER - 1) (mech.los.c:273)
        self.prep_channel(2, 12)
        mech = self.submerged_mech(5, 2, 2)
        target = self.submerged_mech(5, 12, 2)
        flag = calculate_los_flag(mech, target, self.map, 5, 12, 0, 10.0)
        self.assertEqual(mech_los_flag_water_count(flag), MECHLOSMAX_WATER - 1)

    def test_sea_floor_blocks(self):
        # shallower intervening hex: height >= pos_z (mech.los.c:180-185)
        self.prep_channel(2, 8)
        self.map.set_elevation(5, 5, 1)       # floor at -1, eye at -1.5
        mech = self.submerged_mech(5, 2, 2)
        target = self.submerged_mech(5, 8, 2)
        flag = calculate_los_flag(mech, target, self.map, 5, 8, 0, 6.0)
        self.assertTrue(flag & MECHLOSFLAG_BLOCK)

    def test_underwater_to_land_blocks(self):
        # one-world mismatch (mech.los.c:133-137)
        self.prep_channel(2, 4)
        mech = self.submerged_mech(5, 2, 2)
        target = make_mech(self.map, 5, 8)
        flag = calculate_los_flag(mech, target, self.map, 5, 8, 0, 6.0)
        self.assertTrue(flag & MECHLOSFLAG_BLOCK)


class TestCachedReaders(unittest.TestCase):
    """InLineOfSight / InLineOfSight_NB (mech.los.c:303-372, ADVANCED_LOS)."""

    def setUp(self):
        self.map = make_map()
        self.mech = make_mech(self.map, 5, 2, name="A")
        self.target = make_mech(self.map, 5, 8, name="B")

    def cache(self, flag):
        self.map.losinfo = {(self.mech._id, self.target._id): flag}

    def test_sees_primary_from_cache(self):
        self.cache(MECHLOSFLAG_SEEC2 | MECHLOSFLAG_SEESP)
        self.assertEqual(in_line_of_sight(self.mech, self.target, 5, 8, 6.0),
                         MECHLOSFLAG_SEESP)

    def test_block_bit_passes_through_when_seen(self):
        # sensor lock without LOS: return includes BLOCK (mech.los.c:362-365)
        self.cache(MECHLOSFLAG_SEESS | MECHLOSFLAG_BLOCK)
        self.assertEqual(in_line_of_sight(self.mech, self.target, 5, 8, 6.0),
                         MECHLOSFLAG_SEESS | MECHLOSFLAG_BLOCK)

    def test_no_sees_bits_means_zero(self):
        self.cache(MECHLOSFLAG_SEEC2 | MECHLOSFLAG_SEEN | MECHLOSFLAG_BLOCK)
        self.assertEqual(in_line_of_sight(self.mech, self.target, 5, 8, 6.0), 0)

    def test_missing_key_and_none_losinfo_mean_unseen(self):
        self.map.losinfo = {}
        self.assertEqual(in_line_of_sight(self.mech, self.target, 5, 8, 6.0), 0)
        self.map.losinfo = None
        self.assertEqual(in_line_of_sight(self.mech, self.target, 5, 8, 6.0), 0)
        self.assertEqual(mech_to_mech_los_flag(self.map, self.mech,
                                               self.target), 0)

    def test_cache_is_stale_by_design(self):
        # fire-time LOS reads the cached bits even if the terrain now blocks
        self.cache(MECHLOSFLAG_SEESP)
        self.map.set_elevation(5, 5, 9)       # wall added after LOS update
        self.assertEqual(in_line_of_sight(self.mech, self.target, 5, 8, 6.0),
                         MECHLOSFLAG_SEESP)

    def test_clairvoyant_always_sees(self):
        # mech.los.c:337-339
        self.map.losinfo = None
        self.mech.set_crit_status(CritStatus.CLAIRVOYANT)
        self.assertEqual(in_line_of_sight(self.mech, self.target, 5, 8, 6.0), 1)

    def test_no_map_returns_zero(self):
        loner = Mech(name="C")
        self.assertEqual(in_line_of_sight(loner, self.target, 5, 8, 6.0), 0)

    def test_nb_same_mech_is_one(self):
        # mech.los.c:307-308
        self.assertEqual(in_line_of_sight_nb(self.mech, self.mech, 5, 2, 0.0), 1)

    def test_nb_filters_block(self):
        # mech.los.c:311-312
        self.cache(MECHLOSFLAG_SEESP | MECHLOSFLAG_BLOCK)
        self.assertEqual(
            in_line_of_sight_nb(self.mech, self.target, 5, 8, 6.0), 0)
        self.cache(MECHLOSFLAG_SEESP)
        self.assertEqual(
            in_line_of_sight_nb(self.mech, self.target, 5, 8, 6.0),
            MECHLOSFLAG_SEESP)

    def test_hex_target_recalculates_terrain_flag(self):
        # target=None path: CalculateLOSFlag + Sensor_CanSee (mech.los.c:369-371)
        seen = {}

        def fake_can_see(mech, target, flag, arc, hex_range, mapvis,
                         maplight, cloudbase):
            seen['flag'] = flag
            return 3

        with mock.patch.object(los, 'sensor_can_see', fake_can_see):
            result = in_line_of_sight(self.mech, None, 5, 8, 6.0)
        self.assertEqual(result, 3)
        self.assertTrue(seen['flag'] & MECHLOSFLAG_SEEC2)
        self.assertFalse(seen['flag'] & MECHLOSFLAG_BLOCK)


class TestAddTerrainMod(unittest.TestCase):
    """AddTerrainMod (mech.los.c:286-301)."""

    def setUp(self):
        self.map = make_map()
        self.mech = make_mech(self.map, 5, 2, name="A")
        self.target = make_mech(self.map, 5, 8, name="B")

    def test_partial_bit_sets_partial_cover_status(self):
        self.map.losinfo = {(self.mech._id, self.target._id):
                            MECHLOSFLAG_SEESP | MECHLOSFLAG_PARTIAL}
        result = add_terrain_mod(self.mech, self.target, self.map, 6.0, 0)
        self.assertTrue(self.target.has_status(MechStatus.PARTIAL_COVER))
        # Real Sensor_ToHitBonus: vislight primary, seen w/ SEESP, PARTIAL
        # -> +3 partial-cover penalty (vislight_tohit,
        # mech.sensor.functions.c:170-173).
        self.assertEqual(result, 3)

    def test_no_partial_bit_clears_status_and_unseen_is_10000(self):
        self.target.set_status(MechStatus.PARTIAL_COVER)
        self.map.losinfo = {(self.mech._id, self.target._id):
                            MECHLOSFLAG_SEEC2}
        result = add_terrain_mod(self.mech, self.target, self.map, 6.0, 0)
        self.assertFalse(self.target.has_status(MechStatus.PARTIAL_COVER))
        self.assertEqual(result, 10000)       # Sensor_ToHitBonus (mech.sensor.c:42-43)

    def test_no_target_returns_zero(self):
        self.assertEqual(add_terrain_mod(self.mech, None, self.map, 6.0, 0), 0)


class TestActualElevation(unittest.TestCase):
    """ActualElevation (mech.los.c:36-53)."""

    def setUp(self):
        self.map = make_map()

    def test_no_map(self):
        self.assertEqual(actual_elevation(None, 5, 5, None), 0.0)

    def test_bare_hex(self):
        self.map.set_elevation(5, 5, 3)
        self.assertEqual(actual_elevation(self.map, 5, 5, None), 3.0999999046325684)

    def test_standing_mech(self):
        mech = make_mech(self.map, 5, 5, z=2)
        self.assertAlmostEqual(actual_elevation(self.map, 5, 5, mech), 3.5)

    def test_fallen_mech(self):
        mech = make_mech(self.map, 5, 5, z=2)
        mech.set_status(MechStatus.FALLEN)
        self.assertAlmostEqual(actual_elevation(self.map, 5, 5, mech), 2.5)


if __name__ == '__main__':
    unittest.main()
