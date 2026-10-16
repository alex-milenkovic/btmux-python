"""
Tests for the map/terrain module (entities/map.py).

Covers the terrain constant table, GameMap accessors, elevation sign
semantics, the mech roster / cached-terrain plumbing, the map_load file
parser (map.c:290) including its preserved oddities, and map_update
(map.c:553).
"""

import os
import tempfile
import unittest

from entities.map import (
    GameMap, map_update, base_elev, bounded, get_terrain_name_base,
    GRASSLAND, HEAVY_FOREST, LIGHT_FOREST, WATER, HIGHWATER, ROUGH,
    MOUNTAINS, ROAD, BUILDING, FIRE, TFIRE, SMOKE, WALL, DESERT, BRIDGE,
    SNOW, ICE, UNKNOWN_TERRAIN, MAX_ELEV,
    MAPX, MAPY, MAP_NAME_SIZE, DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT,
    MAPFLAG_FIRES, MAPFLAG_NOBRIDGIFY,
)
from entities.mech import Mech


def make_mech(x=0, y=0):
    mech = Mech.create_test_mech()
    mech.x = x
    mech.y = y
    return mech


def write_map(text):
    """Write map text to a temp file, return its path (caller cleans up)."""
    fd, path = tempfile.mkstemp(suffix=".map")
    with os.fdopen(fd, 'w') as fp:
        fp.write(text)
    return path


class TestTerrainConstants(unittest.TestCase):
    """Spot-check terrain chars against the C values (map.h:44-63)."""

    def test_water_ice_bridge(self):
        self.assertEqual(WATER, '~')
        self.assertEqual(ICE, '-')
        self.assertEqual(BRIDGE, '/')

    def test_other_terrain_chars(self):
        self.assertEqual(GRASSLAND, ' ')
        self.assertEqual(HEAVY_FOREST, '"')
        self.assertEqual(LIGHT_FOREST, '`')
        self.assertEqual(ROAD, '#')
        self.assertEqual(BUILDING, '@')
        self.assertEqual(FIRE, '&')
        self.assertEqual(SMOKE, ':')
        self.assertEqual(SNOW, '+')
        self.assertEqual(MAX_ELEV, 9)

    def test_terrain_names(self):
        """GetTerrainName_base port (mech.maps.c:91-125), incl. oddities."""
        self.assertEqual(get_terrain_name_base(WATER), "Water")
        self.assertEqual(get_terrain_name_base(HIGHWATER), "Water")
        self.assertEqual(get_terrain_name_base('_'), "Grassland")
        # SNOW is missing from the C switch (sic)
        self.assertEqual(get_terrain_name_base(SNOW), "Unknown")


class TestConstructor(unittest.TestCase):

    def test_dimensions_and_name(self):
        m = GameMap(5, 7, name="testmap")
        self.assertEqual(m.map_width, 5)
        self.assertEqual(m.map_height, 7)
        self.assertEqual(m.name, "testmap")

    def test_all_grassland_elev_zero(self):
        m = GameMap(4, 3)
        for x in range(4):
            for y in range(3):
                self.assertEqual(m.terrain(x, y), GRASSLAND)
                self.assertEqual(m.elevation(x, y), 0)

    def test_defaults(self):
        m = GameMap(3, 3)
        self.assertEqual(m.movemod, 100)
        self.assertEqual(m.mapvis, 0)
        self.assertEqual(m.maxvis, 0)
        self.assertEqual(m.maplight, 0)
        self.assertEqual(m.winddir, 0)
        self.assertEqual(m.windspeed, 0)
        self.assertEqual(m.cloudbase, 0)
        self.assertEqual(m.temp, 0)
        self.assertEqual(m.flags, 0)
        self.assertEqual(m.mechs_on_map, [])
        self.assertIsNone(m.losinfo)

    def test_xcode_type(self):
        self.assertEqual(GameMap.xcode_type, "MAP")


class TestAccessors(unittest.TestCase):

    def setUp(self):
        self.m = GameMap(10, 8)

    def test_valid_bounds(self):
        self.assertTrue(self.m.valid(0, 0))
        self.assertTrue(self.m.valid(9, 7))
        self.assertFalse(self.m.valid(-1, 0))
        self.assertFalse(self.m.valid(0, -1))
        self.assertFalse(self.m.valid(10, 0))
        self.assertFalse(self.m.valid(0, 8))

    def test_terrain_get_set(self):
        self.m.set_terrain(3, 4, MOUNTAINS)
        self.assertEqual(self.m.terrain(3, 4), MOUNTAINS)
        self.assertEqual(self.m.terrain(4, 3), GRASSLAND)

    def test_elevation_get_set(self):
        self.m.set_elevation(2, 5, 6)
        self.assertEqual(self.m.elevation(2, 5), 6)
        self.assertEqual(self.m.elevation(5, 2), 0)

    def test_set_terrain_keeps_elevation(self):
        self.m.set_elevation(1, 1, 4)
        self.m.set_terrain(1, 1, ROUGH)
        self.assertEqual(self.m.elevation(1, 1), 4)

    def test_rterrain_equals_terrain_for_now(self):
        self.m.set_terrain(0, 0, FIRE)
        self.assertEqual(self.m.rterrain(0, 0), FIRE)


class TestElevationSign(unittest.TestCase):

    def setUp(self):
        self.m = GameMap(5, 5)

    def test_water_negative(self):
        self.m.set_terrain(1, 1, WATER)
        self.m.set_elevation(1, 1, 3)
        self.assertEqual(self.m.elevation(1, 1), 3)       # unsigned store
        self.assertEqual(self.m.base_elevation(1, 1), -3)  # signed floor

    def test_ice_negative(self):
        self.m.set_terrain(2, 2, ICE)
        self.m.set_elevation(2, 2, 2)
        self.assertEqual(self.m.base_elevation(2, 2), -2)

    def test_land_positive(self):
        self.m.set_terrain(3, 3, MOUNTAINS)
        self.m.set_elevation(3, 3, 5)
        self.assertEqual(self.m.base_elevation(3, 3), 5)

    def test_water_depth(self):
        self.m.set_terrain(1, 1, WATER)
        self.m.set_elevation(1, 1, 4)
        self.m.set_terrain(2, 2, ICE)
        self.m.set_elevation(2, 2, 1)
        self.m.set_elevation(3, 3, 7)  # grassland hill
        self.assertEqual(self.m.water_depth(1, 1), 4)
        self.assertEqual(self.m.water_depth(2, 2), 1)
        self.assertEqual(self.m.water_depth(3, 3), 0)


class TestMechRoster(unittest.TestCase):

    def setUp(self):
        self.m = GameMap(10, 10)

    def test_add_mech_initializes_cache(self):
        self.m.set_terrain(2, 3, WATER)
        self.m.set_elevation(2, 3, 4)
        mech = make_mech(2, 3)
        self.m.add_mech(mech)
        self.assertIn(mech, self.m.mechs_on_map)
        self.assertIs(mech.map, self.m)
        self.assertEqual(mech.terrain, WATER)
        self.assertEqual(mech.elev, 4)

    def test_add_mech_out_of_bounds_no_cache(self):
        mech = make_mech(99, 99)
        old_terrain = mech.terrain
        old_elev = mech.elev
        self.m.add_mech(mech)
        self.assertIs(mech.map, self.m)
        self.assertEqual(mech.terrain, old_terrain)
        self.assertEqual(mech.elev, old_elev)

    def test_remove_mech_clears_cache(self):
        mech = make_mech(1, 1)
        self.m.add_mech(mech)
        self.m.remove_mech(mech)
        self.assertNotIn(mech, self.m.mechs_on_map)
        self.assertIsNone(mech.map)
        self.assertEqual(mech.terrain, '')
        self.assertEqual(mech.elev, 0)

    def test_set_terrain_updates_standing_mech(self):
        """UpdateMechsTerrain analogue (map.c:742-757)."""
        mech = make_mech(4, 5)
        self.m.add_mech(mech)
        self.m.set_terrain(4, 5, ROUGH)
        self.assertEqual(mech.terrain, ROUGH)

    def test_set_terrain_ignores_mech_elsewhere(self):
        mech = make_mech(0, 0)
        self.m.add_mech(mech)
        self.m.set_terrain(4, 5, ROUGH)
        self.assertEqual(mech.terrain, GRASSLAND)


class TestFromFile(unittest.TestCase):
    """map_load port (map.c:290-377)."""

    def load(self, text):
        path = write_map(text)
        self.addCleanup(os.unlink, path)
        return GameMap.from_file(path), path

    def test_roundtrip(self):
        m, path = self.load("3 2\n^0%1@2\n~3-4=5\n")
        self.assertEqual(m.map_width, 3)
        self.assertEqual(m.map_height, 2)
        self.assertEqual(m.terrain(0, 0), MOUNTAINS)
        self.assertEqual(m.elevation(0, 0), 0)
        self.assertEqual(m.terrain(1, 0), ROUGH)
        self.assertEqual(m.elevation(1, 0), 1)
        self.assertEqual(m.terrain(2, 0), BUILDING)
        self.assertEqual(m.elevation(2, 0), 2)
        self.assertEqual(m.terrain(0, 1), WATER)
        self.assertEqual(m.elevation(0, 1), 3)
        self.assertEqual(m.terrain(1, 1), ICE)
        self.assertEqual(m.elevation(1, 1), 4)
        self.assertEqual(m.terrain(2, 1), WALL)
        self.assertEqual(m.elevation(2, 1), 5)
        self.assertEqual(m.name, os.path.basename(path)[:MAP_NAME_SIZE])

    def test_defaults_without_trailing_line(self):
        m, _ = self.load("2 1\n~1^2\n")
        self.assertEqual(m.grav, 100)   # map.c:361
        self.assertEqual(m.temp, 20)    # map.c:362
        self.assertEqual(m.flags, 0)

    def test_trailing_config_line(self):
        m, _ = self.load("2 1\n~1^2\n40: 90 -5\n")
        self.assertEqual(m.flags, 40)
        self.assertEqual(m.grav, 90)
        self.assertEqual(m.temp, -5)

    def test_terrain_remaps(self):
        """'.', TFIRE, SMOKE -> GRASSLAND; '\\'' -> LIGHT_FOREST (map.c:333-345)."""
        m, _ = self.load("4 1\n.0>1:2'3\n")
        self.assertEqual(m.terrain(0, 0), GRASSLAND)
        self.assertEqual(m.terrain(1, 0), GRASSLAND)
        self.assertEqual(m.elevation(1, 0), 1)
        self.assertEqual(m.terrain(2, 0), GRASSLAND)
        self.assertEqual(m.terrain(3, 0), LIGHT_FOREST)
        self.assertEqual(m.elevation(3, 0), 3)

    def test_fire_sets_flag(self):
        m, _ = self.load("2 1\n&1^2\n")
        self.assertEqual(m.terrain(0, 0), FIRE)
        self.assertTrue(m.flags & MAPFLAG_FIRES)

    def test_trailing_line_clobbers_fire_flag(self):
        """Oddity (sic): map->flags = i1 overwrites MAPFLAG_FIRES (map.c:365)."""
        m, _ = self.load("2 1\n&1^2\n0: 100 20\n")
        self.assertEqual(m.flags, 0)

    def test_invalid_terrain_becomes_grassland(self):
        """SNOW is not in GetTerrainName_base (sic), so it is rejected."""
        m, _ = self.load("2 1\n+3^2\n")
        self.assertEqual(m.terrain(0, 0), GRASSLAND)
        self.assertEqual(m.elevation(0, 0), 3)  # elevation kept (map.c:352)

    def test_bad_dimensions_line_raises(self):
        with self.assertRaises(ValueError):
            self.load("abc\nxyz\n")

    def test_out_of_range_dimensions_raise(self):
        # width < 1 -> defaults 21x11 (map.c:316-317) -> short rows -> -2
        with self.assertRaises(ValueError):
            self.load("0 5\n~1^2\n")

    def test_short_row_raises(self):
        with self.assertRaises(ValueError):
            self.load("2 2\n~1^2\n^3\n")

    def test_missing_file_raises(self):
        with self.assertRaises(ValueError):
            GameMap.from_file("/nonexistent/no_such.map")

    def test_leading_grassland_row_shift_oddity(self):
        # fscanf eats the first terrain space, moving non-digits into the
        # coding elevation column. Reject that undefined C array access.
        with self.assertRaisesRegex(ValueError,'coding elevation'):
            self.load("3 2\n 0#1~2\n^3%4@5\n")

    def test_bridgify_road_over_water(self):
        """make_bridges converts road between opposite water (map.c:233-241)."""
        m, _ = self.load("1 3\n~5\n#0\n~5\n")
        self.assertEqual(m.terrain(0, 1), BRIDGE)
        self.assertEqual(m.terrain(0, 0), WATER)

    def test_nobridgify_flag_keeps_road(self):
        """MapNoBridgify skips make_bridges (map.c:372, map.h:116)."""
        m, _ = self.load("1 3\n~5\n#0\n~5\n%d: 100 20\n" % MAPFLAG_NOBRIDGIFY)
        self.assertEqual(m.terrain(0, 1), ROAD)


class FakeEngine:
    def __init__(self, tick):
        self.muxevent_tick = tick


class TestMapUpdate(unittest.TestCase):
    """map_update port (map.c:553-598)."""

    def test_fires_on_25th_tick(self):
        m = GameMap(3, 3)
        map_update(FakeEngine(25), m)
        self.assertEqual(m.mapvis, 30)      # BOUNDED(0, 30, 60)
        self.assertEqual(m.maxvis, 60)      # BOUNDED(24, 90, 60)
        self.assertEqual(m.maplight, 2)     # BOUNDED(0, 2, 2)
        self.assertEqual(m.cloudbase, 200)
        self.assertEqual(m.winddir, 0)
        self.assertEqual(m.windspeed, 0)

    def test_fires_on_tick_zero_and_fifty(self):
        for tick in (0, 50):
            m = GameMap(3, 3)
            map_update(FakeEngine(tick), m)
            self.assertEqual(m.mapvis, 30, "tick %d" % tick)

    def test_skips_off_ticks(self):
        m = GameMap(3, 3)
        m.mapvis = 99
        m.maxvis = 99
        m.maplight = 1
        m.cloudbase = 42
        for tick in (1, 24, 26, 49):
            map_update(FakeEngine(tick), m)
        self.assertEqual(m.mapvis, 99)
        self.assertEqual(m.maxvis, 99)
        self.assertEqual(m.maplight, 1)
        self.assertEqual(m.cloudbase, 42)

    def test_update_with_mechs_on_map(self):
        """Light/vis change loop over mechs runs without error (map.c:584-594)."""
        m = GameMap(10, 10)
        mech = Mech.create_test_mech()
        mech.x, mech.y = 1, 1
        m.add_mech(mech)
        map_update(FakeEngine(25), m)
        self.assertEqual(m.maplight, 2)


class TestHelpers(unittest.TestCase):

    def test_bounded(self):
        self.assertEqual(bounded(0, -5, 60), 0)
        self.assertEqual(bounded(0, 30, 60), 30)
        self.assertEqual(bounded(0, 90, 60), 60)
        self.assertEqual(bounded(24, 90, 60), 60)

    def test_base_elev_helper(self):
        self.assertEqual(base_elev(WATER, 3), -3)
        self.assertEqual(base_elev(ICE, 2), -2)
        self.assertEqual(base_elev(MOUNTAINS, 4), 4)


if __name__ == '__main__':
    unittest.main()
