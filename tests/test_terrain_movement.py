"""
Tests for terrain-aware movement: MAPMOVEMOD scaling, terrain_speed,
and NewHexEntered effects on hex crossing.

Terrain chars below are literals pre-verified from map.h:44-63:
GRASSLAND=' ', HEAVY_FOREST='"', LIGHT_FOREST='`', WATER='~', ROUGH='%',
MOUNTAINS='^', ROAD='#', BUILDING='@', WALL='=', DESERT='}', BRIDGE='/',
SNOW='+', ICE='-', HIGHWATER='?'.
"""

import unittest
from unittest import mock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.templates import get_template, create_mech_from_template
from entities.mech import MechStatus, MoveType
from physics.movement import (
    MP1, MP2, MP3, MP_PER_KPH,
    map_move_mod, move_mech, terrain_speed, update_speed,
    on_hex_entered, new_hex_entered, move_unit_back,
    drop_thru_ice, possibly_drop_thru_ice, break_thru_ice,
)
from systems.piloting import PilotingResult

GRASSLAND = ' '
HEAVY_FOREST = '"'
LIGHT_FOREST = '`'
WATER = '~'
ROUGH = '%'
MOUNTAINS = '^'
ROAD = '#'
BRIDGE = '/'
SNOW = '+'
ICE = '-'
HIGHWATER = '?'


from entities.map import GameMap


class FakeMap(GameMap):
    """Local test double for the GameMap duck-type contract."""

    def __init__(self, width=100, height=100, movemod=100):
        super().__init__(width, height)
        self._id = 100
        self.map_width = width
        self.map_height = height
        self.movemod = movemod
        self.mechs_on_map = []
        self._hexes = {}  # (x, y) -> (terrain, elev)

    def set_hex(self, x, y, terrain, elev=0):
        self._hexes[(x, y)] = (terrain, elev)

    def set_terrain(self, x, y, terrain):
        self.set_hex(x, y, terrain, self.elevation(x, y))

    def set_elevation(self, x, y, elevation):
        self.set_hex(x, y, self.terrain(x, y), elevation)

    def valid(self, x, y):
        return 0 <= x < self.map_width and 0 <= y < self.map_height

    def terrain(self, x, y):
        return self._hexes.get((x, y), (GRASSLAND, 0))[0]

    def rterrain(self, x, y):
        return self.terrain(x, y)

    def elevation(self, x, y):
        return self._hexes.get((x, y), (GRASSLAND, 0))[1]

    def base_elevation(self, x, y):
        terrain, elev = self._hexes.get((x, y), (GRASSLAND, 0))
        return -elev if terrain in (WATER, ICE) else elev

    def water_depth(self, x, y):
        terrain, elev = self._hexes.get((x, y), (GRASSLAND, 0))
        return elev if terrain in (WATER, ICE) else 0


def make_mech(name="Alpha", x=50, y=50):
    mech = create_mech_from_template(get_template("TestMech"), name=name)
    mech.set_hex_position(x, y)
    mech.set_status(MechStatus.STARTED)
    board = FakeMap()
    board.add_mech(mech)
    return mech


PSR_PASS = PilotingResult(success=True)
PSR_FAIL = PilotingResult(success=False)


# =============================================================================
# MAPMOVEMOD
# =============================================================================

class TestMapMoveMod(unittest.TestCase):
    def test_mapless_factor_is_one(self):
        mech = make_mech()
        mech.map = None
        self.assertIsNone(mech.map)
        self.assertEqual(map_move_mod(mech), 1.0)

    def test_movemod_zero_is_one(self):
        # MAPMOVEMOD guard: movemod > 0 ? movemod/100 : 1.0 (btmacros.h:727)
        mech = make_mech()
        mech.map = FakeMap(movemod=0)
        self.assertEqual(map_move_mod(mech), 1.0)

    def test_movemod_100_matches_default_delta(self):
        m1 = make_mech("A")
        m2 = make_mech("B")
        m2.map = FakeMap(movemod=100)
        for m in (m1, m2):
            m.speed = MP1
            m.facing = 90
        fx1, fy1 = m1.fx, m1.fy
        fx2, fy2 = m2.fx, m2.fy
        move_mech(m1)
        move_mech(m2)
        self.assertAlmostEqual(m1.fx - fx1, m2.fx - fx2)
        self.assertAlmostEqual(m1.fy - fy1, m2.fy - fy2)

    def test_movemod_200_doubles_delta(self):
        m1 = make_mech("A")
        m1.map = FakeMap(movemod=100)
        m2 = make_mech("B")
        m2.map = FakeMap(movemod=200)
        for m in (m1, m2):
            m.speed = MP1
            m.facing = 90
        fx1 = m1.fx
        fx2 = m2.fx
        move_mech(m1)
        move_mech(m2)
        self.assertAlmostEqual(m2.fx - fx2, 2.0 * (m1.fx - fx1))

    def test_movemod_applies_to_jump(self):
        # The C scales the jump XY delta by MAPMOVEMOD too (mech.update.c:248-250)
        m1 = make_mech("A")
        m2 = make_mech("B")
        m2.map = FakeMap(movemod=200)
        for m in (m1, m2):
            m.set_status(MechStatus.JUMPING)
            m.jump_speed = MP3
            m.jump_heading = 90
            m.jump_length = 1000
            m.jump_top = 3
            m.start_fx, m.start_fy, m.start_fz = m.fx, m.fy, m.fz
        fx1 = m1.fx
        fx2 = m2.fx
        move_mech(m1)
        move_mech(m2)
        self.assertAlmostEqual(m2.fx - fx2, 2.0 * (m1.fx - fx1))


# =============================================================================
# terrain_speed
# =============================================================================

class TestTerrainSpeed(unittest.TestCase):
    def setUp(self):
        self.mech = make_mech()
        self.mech.z = 0

    def test_rough_and_snow(self):
        # DECREASE(MP1): tempspeed *= MP1 / (MP1 + MP1) = 0.5
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, ROUGH, 0), 50.0)
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, SNOW, 0), 50.0)

    def test_mountains(self):
        # DECREASE(MP2): *= MP1 / (MP1 + MP2) = 1/3
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, MOUNTAINS, 0),
            __import__('core.randomness', fromlist=['float32']).float32(100.0 * MP1 / (MP1 + MP2)))

    def test_forests(self):
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, LIGHT_FOREST, 0), 50.0)
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, HEAVY_FOREST, 0),
            __import__('core.randomness', fromlist=['float32']).float32(100.0 * MP1 / (MP1 + MP2)))

    def test_road_no_bonus_for_mech(self):
        # Pavement +1 MP is tracked/wheeled only (mech.update.c:958-965)
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, ROAD, 0), 100.0)

    def test_water_depths(self):
        # elev -1: DECREASE(MP1) = 0.5; elev <= -2: DECREASE(MP3) = 0.25
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, WATER, -1), 50.0)
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, WATER, -2),
            100.0 * MP1 / (MP1 + MP3))

    def test_ice_on_top_unchanged(self):
        self.mech.z = 0
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, ICE, -2), 100.0)

    def test_ice_below_treated_as_water(self):
        # Under the ice: fall through to WATER (mech.update.c:967-971)
        self.mech.z = -2
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, ICE, -2),
            100.0 * MP1 / (MP1 + MP3))

    def test_grassland_unchanged(self):
        self.assertAlmostEqual(
            terrain_speed(self.mech, 100.0, 64.5, GRASSLAND, 0), 100.0)

    def test_update_speed_uses_terrain(self):
        # On ROUGH the target speed halves; converge and check.
        mech = make_mech()
        mech.map = FakeMap()
        mech.terrain = ROUGH
        mech.elev = 0
        mech.desired_speed = mech.max_speed
        for _ in range(60):
            update_speed(mech)
        self.assertAlmostEqual(mech.speed, mech.max_speed * 0.5, places=3)

    def test_update_speed_mapless_unchanged(self):
        mech = make_mech()
        mech.desired_speed = mech.max_speed
        for _ in range(60):
            update_speed(mech)
        self.assertAlmostEqual(mech.speed, mech.max_speed, places=3)


# =============================================================================
# new_hex_entered
# =============================================================================

def enter_hex(mech, game_map, old_hex, new_hex, speed, old_z=None):
    """Place mech as if it just crossed old_hex -> new_hex, then fire
    on_hex_entered with a plausible delta."""
    mech.map = game_map
    mech.last_x, mech.last_y = old_hex
    mech.x, mech.y = new_hex
    mech.speed = speed
    mech.desired_speed = speed
    if old_z is not None:
        mech.z = old_z
    # caches of the OLD hex (what the mech had before crossing)
    mech.terrain = game_map.terrain(*old_hex)
    mech.elev = game_map.elevation(*old_hex)
    last_z = mech.z
    on_hex_entered(mech, old_hex[0], old_hex[1],
                   deltax=10.0, deltay=-10.0, last_z=last_z)


class TestNewHexEntered(unittest.TestCase):
    def test_suit_water_stop_uses_overwritten_elevation_cost_for_x_rollback(self):
        from entities.mech import UnitType
        game_map = FakeMap()
        game_map.set_hex(50, 49, WATER, 1)
        mech = make_mech()
        mech.unit_type = UnitType.BSUIT
        before = mech.fx, mech.fy
        with mock.patch('systems.piloting.make_piloting_roll', return_value=PSR_PASS):
            enter_hex(mech, game_map, (50, 50), (50, 49), 3 * MP1, old_z=0)
        self.assertEqual((50, 50, 0, 0), (mech.x, mech.y, mech.speed, mech.desired_speed))
        self.assertAlmostEqual(before[0] - MP1, mech.fx, places=3)
        self.assertAlmostEqual(before[1] + 10, mech.fy, places=3)

    def test_water_running_roll_observes_queued_sprint_exit(self):
        from core.game_loop import GameEngine
        from core.events import EventType
        from entities.mech import MechStatus2
        from entities.pilot import Pilot
        from physics.cargo import cargo_max_speed
        game_map = FakeMap()
        game_map.set_hex(50, 49, WATER, 1)
        mech = make_mech()
        mech.max_speed = 64.5
        mech.measured_mass = mech.tonnage * 1024
        mech.pilot = Pilot()
        mech.pilot.speed_demon = True
        mech.set_status2(MechStatus2.SPRINTING)
        engine = GameEngine()
        engine.register_entity(game_map)
        game_map.add_mech(mech)
        engine.register_entity(mech)
        self.assertEqual(96.75, cargo_max_speed(mech))
        with mock.patch('systems.piloting.make_piloting_roll', return_value=PSR_FAIL) as roll, mock.patch('physics.jump.mech_falls') as fall:
            enter_hex(mech, game_map, (50, 50), (50, 49), 60 + MP1, old_z=0)
        self.assertTrue(engine.has_event(EventType.MOVEMODE, mech))
        self.assertEqual(86, cargo_max_speed(mech))
        roll.assert_called_once_with(mech, 1, award_xp=False, succeed_when_fallen=False)
        fall.assert_called_once_with(mech, 1, notify_fall=True)


    def test_mapless_is_noop(self):
        mech = make_mech()
        mech.map = None
        mech.terrain = ''
        walked = mech.hexes_walked
        on_hex_entered(mech, 49, 50)
        self.assertEqual(mech.hexes_walked, walked + 1.0)
        self.assertEqual(mech.terrain, '')
        self.assertEqual(mech.speed, 0.0)
        # direct call is also a no-op
        new_hex_entered(mech, 1.0, 1.0, 0)
        self.assertEqual(mech.speed, 0.0)

    def test_cache_update_on_crossing(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, LIGHT_FOREST, 1)
        mech = make_mech()
        enter_hex(mech, game_map, (50, 50), (50, 49), MP1)
        self.assertEqual(mech.terrain, LIGHT_FOREST)
        self.assertEqual(mech.elev, 1)
        # DropSetElevation snapped Z to the hex elevation (mech.update.c:651)
        self.assertEqual(mech.z, 1)

    def test_walk_wall_stop_without_fall(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, GRASSLAND, 3)  # 3 levels up > MoveMod 2
        mech = make_mech()
        with mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_PASS):
            enter_hex(mech, game_map, (50, 50), (50, 49), 3 * MP1, old_z=0)
        # moved back, stopped, Z restored
        self.assertEqual((mech.x, mech.y), (50, 50))
        self.assertEqual(mech.speed, 0)
        self.assertEqual(mech.desired_speed, 0)
        self.assertEqual(mech.z, 0)
        self.assertFalse(mech.is_fallen)

    def test_walk_wall_fall_on_failed_psr(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, GRASSLAND, 3)
        mech = make_mech()
        with mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_FAIL):
            enter_hex(mech, game_map, (50, 50), (50, 49), 3 * MP1, old_z=0)
        self.assertEqual((mech.x, mech.y), (50, 50))
        self.assertTrue(mech.is_fallen)
        self.assertEqual(mech.speed, 0)
        self.assertEqual(mech.z, 0)  # MechZ = lastelevation (mech.update.c:1774)

    def test_walk_wall_two_levels_is_climbable(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, GRASSLAND, 2)  # exactly MoveMod: no wall
        mech = make_mech()
        enter_hex(mech, game_map, (50, 50), (50, 49), 3 * MP1, old_z=0)
        self.assertEqual((mech.x, mech.y), (50, 49))
        self.assertFalse(mech.is_fallen)
        # elevation-change slowdown: 2 levels costs MP2 (mech.update.c:1838-1852)
        self.assertAlmostEqual(mech.speed, 3 * MP1 - MP2)

    def test_walk_drop_stop_moves_back(self):
        game_map = FakeMap()
        game_map.set_hex(50, 50, GRASSLAND, 3)
        game_map.set_hex(50, 49, GRASSLAND, 0)  # 3 levels down > MoveMod
        mech = make_mech()
        with mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_PASS):
            enter_hex(mech, game_map, (50, 50), (50, 49), 2 * MP1, old_z=3)
        self.assertEqual((mech.x, mech.y), (50, 50))
        self.assertEqual(mech.speed, 0)
        self.assertEqual(mech.desired_speed, 0)
        self.assertEqual(mech.z, 3)
        self.assertFalse(mech.is_fallen)

    def test_walk_drop_fall_levels(self):
        game_map = FakeMap()
        game_map.set_hex(50, 50, GRASSLAND, 3)
        game_map.set_hex(50, 49, GRASSLAND, 0)
        mech = make_mech()
        with mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_FAIL), \
             mock.patch('physics.jump.mech_falls') as falls:
            enter_hex(mech, game_map, (50, 50), (50, 49), 2 * MP1, old_z=3)
        # MechFalls(mech, lastelevation - elevation) (mech.update.c:1804)
        falls.assert_called_once_with(mech, 3, notify_fall=False)
        self.assertEqual((mech.x, mech.y), (50, 49))
        self.assertEqual(mech.speed, 0)
        self.assertEqual(mech.desired_speed, 0)

    def test_skidcliff_uses_skid_mod(self):
        # With btech_skidcliff, the wall PSR modifier is
        # SkidMod(fabs(MechSpeed)/MP1) (mech.update.c:1752-1754)
        game_map = FakeMap()
        game_map.set_hex(50, 49, GRASSLAND, 3)
        mech = make_mech()
        with mock.patch.object(game_map, 'btech_skidcliff', 1, create=True), \
             mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_PASS) as psr:
            enter_hex(mech, game_map, (50, 50), (50, 49), 5 * MP1, old_z=0)
        psr.assert_called_once_with(mech, 1, succeed_when_fallen=True, award_xp=False)  # skid_mod(5.0) == 1

    def test_wall_psr_modifier_default_rules(self):
        # Without skidcliff: (int)(fabs(speed + MP1)/MP1)/3 (mech.update.c:1748-1750)
        game_map = FakeMap()
        game_map.set_hex(50, 49, GRASSLAND, 3)
        mech = make_mech()
        with mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_PASS) as psr:
            enter_hex(mech, game_map, (50, 50), (50, 49), 8 * MP1, old_z=0)
        psr.assert_called_once_with(mech, 3, succeed_when_fallen=True, award_xp=False)  # int(9.0) // 3

    def test_water_entry(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, WATER, 2)  # depth 2 water
        mech = make_mech()
        with mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_PASS):
            enter_hex(mech, game_map, (50, 50), (50, 49), 3 * MP1, old_z=0)
        self.assertEqual((mech.x, mech.y), (50, 49))
        self.assertEqual(mech.z, -2)
        self.assertFalse(mech.is_fallen)
        # elevation-change slowdown |0 - (-2)| = 2 levels -> -MP2
        self.assertAlmostEqual(mech.speed, 3 * MP1 - MP2)
        # desired speed clamped to walking speed of MMaxSpeed
        self.assertLessEqual(mech.desired_speed, 2.0 * mech.max_speed / 3.0)

    def test_water_entry_failed_psr_falls(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, WATER, 2)
        mech = make_mech()
        with mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_FAIL), \
             mock.patch('physics.jump.mech_falls') as falls:
            enter_hex(mech, game_map, (50, 50), (50, 49), 3 * MP1, old_z=0)
        falls.assert_called_once_with(mech, 1, notify_fall=False)  # mech.update.c:1939

    def test_ice_holds_when_roll_misses(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, ICE, 2)
        mech = make_mech()
        with mock.patch('physics.movement.random.randint', return_value=6):
            enter_hex(mech, game_map, (50, 50), (50, 49), MP1, old_z=0)
        self.assertEqual(mech.terrain, ICE)
        self.assertEqual(mech.z, 0)  # standing on top of the ice
        self.assertFalse(mech.is_fallen)

    def test_ice_breaks_on_one(self):
        # Number(1,6) == 1 drops the mech through (mech.ice.c:108)
        game_map = FakeMap()
        game_map.set_hex(50, 49, ICE, 2)
        mech = make_mech()
        with mock.patch('physics.movement.random.randint', return_value=1), \
             mock.patch('physics.jump.mech_falls') as falls:
            enter_hex(mech, game_map, (50, 49 + 1), (50, 49), MP1, old_z=0)
        self.assertEqual(mech.terrain, WATER)  # mech.ice.c:76
        falls.assert_called_once_with(mech, 2, notify_fall=False)  # MechFalls(mech, MechElev) :79

    def test_iced_skips_new_hex_entered(self):
        game_map = FakeMap()
        game_map.set_hex(50, 49, ICE, 2)
        mech = make_mech()
        with mock.patch('physics.movement.possibly_drop_thru_ice',
                        return_value=1), \
             mock.patch('physics.movement.new_hex_entered') as nhe:
            enter_hex(mech, game_map, (50, 50), (50, 49), MP1, old_z=0)
        nhe.assert_not_called()  # mech.update.c:662-663

    def test_break_thru_ice_sets_water(self):
        mech = make_mech()
        mech.terrain = ICE
        break_thru_ice(mech)
        self.assertEqual(mech.terrain, WATER)

    def test_domino_called_on_crossing(self):
        game_map = FakeMap()
        mech = make_mech()
        with mock.patch('physics.collision.domino_space') as dom:
            enter_hex(mech, game_map, (50, 50), (50, 49), MP1)
        dom.assert_called_once_with(mech, 0)  # mech.update.c:681

    def test_move_unit_back(self):
        # mech.update.c:1648-1661
        mech = make_mech()
        fx, fy = mech.fx, mech.fy
        mech.last_x, mech.last_y = mech.x, mech.y
        mech.x += 1
        mech.fx += 10.0
        mech.fy += -4.0
        move_unit_back(mech, 10.0, -4.0, 2, ROUGH, 2)
        self.assertAlmostEqual(mech.fx, fx)
        self.assertAlmostEqual(mech.fy, fy)
        self.assertEqual(mech.x, mech.last_x)
        self.assertEqual(mech.z, 2)
        self.assertEqual(mech.terrain, ROUGH)
        self.assertEqual(mech.elev, 2)


if __name__ == '__main__':
    unittest.main()
