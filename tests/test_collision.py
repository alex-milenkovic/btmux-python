"""
Tests for physics/collision.py: collision_check, skid_mod, and the
domino (stacking) checks.

Terrain chars are literals pre-verified from map.h:44-63.
"""

import unittest
from unittest import mock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.templates import get_template, create_mech_from_template
from entities.mech import MechStatus
from physics.collision import (
    JUMP, WALK_WALL, WALK_DROP, HIT_UNDER_BRIDGE, WALK_BACK,
    collision_check, skid_mod, mechs_in_hex,
    domino_space, domino_space_in_hex, cause_damage,
    NORMAL, PUNCH, KICK,
)
from physics.movement import MP1
from systems.piloting import PilotingResult

GRASSLAND = ' '
WATER = '~'
BRIDGE = '/'
ICE = '-'


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
        self._hexes = {}

    def set_hex(self, x, y, terrain, elev=0):
        self._hexes[(x, y)] = (terrain, elev)

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


def make_mech(name="Alpha", x=50, y=50, team=0):
    mech = create_mech_from_template(get_template("TestMech"), name=name)
    mech.set_hex_position(x, y)
    mech.set_status(MechStatus.STARTED)
    mech.team = team
    return mech


def total_armor(mech):
    return sum(s.armor + s.rear + s.internal for s in mech.sections)


PSR_PASS = PilotingResult(success=True)
PSR_FAIL = PilotingResult(success=False)


# =============================================================================
# skid_mod
# =============================================================================

class TestSkidMod(unittest.TestCase):
    def test_brackets(self):
        # mech.update.c:1632-1643
        self.assertEqual(skid_mod(0.0), -1)
        self.assertEqual(skid_mod(2.0), -1)
        self.assertEqual(skid_mod(2.5), 0)
        self.assertEqual(skid_mod(4.5), 1)
        self.assertEqual(skid_mod(7.5), 2)
        self.assertEqual(skid_mod(10.5), 4)
        self.assertEqual(skid_mod(20.0), 4)


# =============================================================================
# collision_check
# =============================================================================

class TestCollisionCheck(unittest.TestCase):
    def setUp(self):
        self.mech = make_mech()
        self.mech.terrain = GRASSLAND
        self.mech.elev = 0
        self.mech.z = 0

    def test_mode_constant_order(self):
        # enum { JUMP, WALK_WALL, WALK_DROP, HIT_UNDER_BRIDGE, WALK_BACK }
        # (mech.update.c:94-96)
        self.assertEqual((JUMP, WALK_WALL, WALK_DROP,
                          HIT_UNDER_BRIDGE, WALK_BACK), (0, 1, 2, 3, 4))

    def test_walk_wall_threshold(self):
        # Wall when (e - le) > MoveMod (2 for bipeds), mech.update.c:138
        self.mech.elev = 3
        self.assertEqual(collision_check(self.mech, WALK_WALL, 0, GRASSLAND), 1)
        self.mech.elev = 2
        self.assertEqual(collision_check(self.mech, WALK_WALL, 0, GRASSLAND), 0)

    def test_walk_drop_threshold(self):
        # Drop when (le - e) > MoveMod, mech.update.c:127
        self.mech.elev = 0
        self.assertEqual(collision_check(self.mech, WALK_DROP, 3, GRASSLAND), 1)
        self.assertEqual(collision_check(self.mech, WALK_DROP, 2, GRASSLAND), 0)

    def test_jump_hits_higher_ground(self):
        # JUMP: MechZ < e (mech.update.c:125)
        self.mech.elev = 2
        self.mech.z = 0
        self.assertEqual(collision_check(self.mech, JUMP, 0, 0), 1)
        self.mech.z = 2
        self.assertEqual(collision_check(self.mech, JUMP, 0, 0), 0)

    def test_jump_bridge_special(self):
        # mech.update.c:119-124
        self.mech.terrain = BRIDGE
        self.mech.elev = 2
        self.mech.z = -1
        self.assertEqual(collision_check(self.mech, JUMP, 0, 0), 1)
        self.mech.z = 1  # z == e - 1
        self.assertEqual(collision_check(self.mech, JUMP, 0, 0), 1)
        self.mech.z = 2
        self.assertEqual(collision_check(self.mech, JUMP, 0, 0), 0)

    def test_walk_back_returns_difference(self):
        # mech.update.c:141-142: |le - e| when reversing, 0 otherwise
        self.mech.speed = -10.0
        self.assertEqual(collision_check(self.mech, WALK_BACK, 2, GRASSLAND), 2)
        self.mech.speed = 10.0
        self.assertEqual(collision_check(self.mech, WALK_BACK, 2, GRASSLAND), 0)

    def test_ice_zeroes_elevation(self):
        # On ICE with le >= 0, e is treated as 0 (mech.update.c:106-108)
        self.mech.terrain = ICE
        self.mech.elev = 3  # would be e = -3 without the ICE clause
        self.assertEqual(collision_check(self.mech, WALK_WALL, 0, GRASSLAND), 0)
        self.assertEqual(collision_check(self.mech, WALK_DROP, 0, GRASSLAND), 0)

    def test_hit_under_bridge(self):
        # mech.update.c:144-150
        game_map = FakeMap()
        game_map.set_hex(50, 50, WATER, 1)   # last hex, base elev -1 != 0
        game_map.set_hex(50, 49, BRIDGE, 1)  # current hex, base elev 1
        self.mech.map = game_map
        self.mech.last_x, self.mech.last_y = 50, 50
        self.mech.x, self.mech.y = 50, 49
        self.mech.terrain = BRIDGE
        self.mech.elev = 1
        self.assertEqual(
            collision_check(self.mech, HIT_UNDER_BRIDGE, 0, BRIDGE), 1)
        # le != 0 -> no hit
        self.assertEqual(
            collision_check(self.mech, HIT_UNDER_BRIDGE, 1, BRIDGE), 0)


# =============================================================================
# mechs_in_hex
# =============================================================================

class TestMechsInHex(unittest.TestCase):
    def setUp(self):
        self.map = FakeMap()
        self.a = make_mech("A", team=0)
        self.b = make_mech("B", team=0)
        self.c = make_mech("C", team=1)
        self.map.mechs_on_map = [self.a, self.b, self.c]

    def test_count_all(self):
        self.assertEqual(mechs_in_hex(self.map, 50, 50, -1, 0), 3)

    def test_count_friendly(self):
        self.assertEqual(mechs_in_hex(self.map, 50, 50, 1, 0), 2)

    def test_count_enemy(self):
        self.assertEqual(mechs_in_hex(self.map, 50, 50, 0, 0), 1)

    def test_skips_destroyed_and_jumping(self):
        self.b.set_status(MechStatus.DESTROYED)
        self.c.set_status(MechStatus.JUMPING)
        self.assertEqual(mechs_in_hex(self.map, 50, 50, -1, 0), 1)

    def test_skips_other_hex(self):
        self.c.set_hex_position(51, 50)
        self.assertEqual(mechs_in_hex(self.map, 50, 50, -1, 0), 2)


# =============================================================================
# domino_space
# =============================================================================

class TestDominoSpace(unittest.TestCase):
    def make_stack(self, n=3, team=0):
        game_map = FakeMap()
        mechs = [make_mech(chr(ord('A') + i), team=team) for i in range(n)]
        for m in mechs:
            m.map = game_map
        game_map.mechs_on_map = list(mechs)
        return game_map, mechs

    def test_no_map_returns_zero(self):
        mech = make_mech()
        self.assertEqual(domino_space(mech, 0), 0)

    def test_two_in_hex_is_fine(self):
        # cnt <= 2 -> no stacking problem (mech.move.c:2169-2170)
        game_map, mechs = self.make_stack(2)
        self.assertEqual(domino_space(mechs[0], 0), 0)

    def test_stacking_disabled(self):
        game_map, mechs = self.make_stack(3)
        with mock.patch('physics.collision.BTECH_STACKING', 0):
            self.assertEqual(domino_space(mechs[0], 0), 0)

    def test_friendly_stack_causes_damage(self):
        # Default btech_stacking == 2 (conf.c:133): a bump deals damage to
        # both the mover and the bumped mech (mech.move.c:2127-2140).
        game_map, mechs = self.make_stack(3)
        me = mechs[0]
        me.speed = 64.5  # fast enough that td > 1
        before_me = total_armor(me)
        before_others = [total_armor(m) for m in mechs[1:]]
        result = domino_space(me, 0)
        self.assertEqual(result, 1)
        self.assertLess(total_armor(me), before_me)
        after_others = [total_armor(m) for m in mechs[1:]]
        self.assertTrue(any(a < b for a, b in zip(after_others,
                                                  before_others)))

    def test_psr_mode_fall_and_stop(self):
        # btech_stacking == 1: failed PSR -> MechFalls(me, 1) and stop
        # (mech.move.c:2141-2150)
        game_map, mechs = self.make_stack(3)
        me = mechs[0]
        me.speed = 64.5
        me.desired_speed = 64.5
        with mock.patch('physics.collision.BTECH_STACKING', 1), \
             mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_FAIL):
            result = domino_space(me, 0)
        self.assertEqual(result, 1)
        self.assertTrue(me.is_fallen)
        self.assertEqual(me.speed, 0)
        self.assertEqual(me.desired_speed, 0)

    def test_psr_mode_success_still_stops(self):
        game_map, mechs = self.make_stack(3)
        me = mechs[0]
        me.speed = 64.5
        me.desired_speed = 64.5
        with mock.patch('physics.collision.BTECH_STACKING', 1), \
             mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_PASS):
            result = domino_space(me, 0)
        self.assertEqual(result, 1)
        self.assertFalse(me.is_fallen)
        self.assertEqual(me.speed, 0)

    def test_same_vector_no_damage(self):
        # Both going in the same direction at the same speed: td == 0
        # (mech.move.c:2085-2093, 2096-2097)
        game_map, mechs = self.make_stack(3)
        for m in mechs:
            m.speed = 32.25
            m.facing = 0
        before = [total_armor(m) for m in mechs]
        result = domino_space_in_hex(game_map, mechs[0], 50, 50, 1, 0, 3)
        self.assertEqual(result, 0)
        self.assertEqual([total_armor(m) for m in mechs], before)

    def test_jump_mode_psr_modifier(self):
        # mode 1/2, stacking != 2: PSR at cnt + JumpSpeedMP/2
        # (mech.move.c:2123)
        game_map, mechs = self.make_stack(3)
        me = mechs[0]
        me.jump_speed = 5 * MP1  # JumpSpeedMP == 5
        with mock.patch('physics.collision.BTECH_STACKING', 1), \
             mock.patch('systems.piloting.make_piloting_roll',
                        return_value=PSR_PASS) as psr:
            result = domino_space_in_hex(game_map, me, 50, 50, 1, 2, 3)
        self.assertEqual(result, 1)
        psr.assert_called_once_with(me, 3 + 5 // 2)

    def test_unstarted_target_not_picked(self):
        # domino_space_in_hex skips !Started targets (mech.move.c:2053-2054)
        game_map, mechs = self.make_stack(3)
        me = mechs[0]
        me.speed = 64.5
        for m in mechs[1:]:
            m.clear_status(MechStatus.STARTED)
        result = domino_space_in_hex(game_map, me, 50, 50, 1, 0, 3)
        self.assertEqual(result, 0)


# =============================================================================
# cause_damage
# =============================================================================

class TestCauseDamage(unittest.TestCase):
    def test_zero_damage_noop(self):
        mech = make_mech()
        before = total_armor(mech)
        cause_damage(mech, mech, 0, NORMAL)
        self.assertEqual(total_armor(mech), before)

    def test_self_damage_front(self):
        # att == mech uses the FRONT group (mech.move.c:2004-2005)
        mech = make_mech()
        before = total_armor(mech)
        cause_damage(mech, mech, 5, KICK)
        self.assertEqual(total_armor(mech), before - 5)

    def test_clusters_of_five(self):
        # 12 damage arrives as 5/5/2 clusters (mech.move.c:2013-2035)
        mech = make_mech()
        before = total_armor(mech)
        cause_damage(mech, mech, 12, PUNCH)
        self.assertEqual(total_armor(mech), before - 12)


if __name__ == '__main__':
    unittest.main()
