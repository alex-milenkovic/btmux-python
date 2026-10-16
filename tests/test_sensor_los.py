"""
Tests for the sensor/LOS sweep layer (Workstream D):

- in_weapon_arc              (InWeaponArc, mech.utils.c:420-457)
- sensor_can_see             (Sensor_CanSee, mech.sensor.c:79-158)
- sensor_do_we_see_now       (Sensor_DoWeSeeNow, mech.sensor.c:333-461)
- update_los_info            (update_LOSinfo, mech.sensor.c:463-580)
- check_ecm                  (checkECM, mech.ecm.c:103-290)
- map_update / engine wiring (map.c:596, mech.update.c:2986)
"""

import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.game_loop import GameEngine, wire_standard_systems
from entities.map import GameMap, MOUNTAINS
from entities.mech import Mech, MechStatus, CritStatus
from physics.hexmath import (
    hex_to_float, in_weapon_arc,
    NOARC, FORWARDARC, LSIDEARC, RSIDEARC, REARARC, TURRETARC,
)
from systems import los
from systems import sensors as sensors_mod
from systems.los import (
    MECHLOSFLAG_SEEN, MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS,
    MECHLOSFLAG_SEEC2, MECHLOSFLAG_BLOCK, MECHMAPFLAG_MOVED,
)
from systems.sensors import (
    SENSOR_VIS, SENSOR_IR,
    fa_mech_range, sensor_can_see, sensor_do_we_see_now, update_los_info,
)
from systems.ecm import (
    check_ecm, ECM_ENABLED, ECCM_ENABLED, ECM_COUNTERED, ECM_DISTURBANCE,
)


def make_map(width=30, height=30):
    gamemap = GameMap(width, height)
    gamemap._id = 1000
    gamemap.mapvis = 30
    gamemap.maxvis = 60
    gamemap.maplight = 2      # daylight
    gamemap.cloudbase = 200
    return gamemap


def make_mech(gamemap, x, y, name="M", team=1, started=True):
    mech = Mech.create_test_mech(name)
    mech.set_hex_position(x, y)
    mech.team = team
    if started:
        mech.set_status(MechStatus.STARTED)
    gamemap.add_mech(mech)
    return mech


def wall(gamemap, x):
    """Raise a full-height mountain wall along column x."""
    for y in range(gamemap.map_height):
        gamemap.set_terrain(x, y, MOUNTAINS)
        gamemap.set_elevation(x, y, 9)


class TestInWeaponArc(unittest.TestCase):
    """InWeaponArc (mech.utils.c:420-457)."""

    def setUp(self):
        self.map = make_map()
        self.mech = make_mech(self.map, 10, 10)
        self.mech.facing = 0

    def arc_to_hex(self, x, y):
        fx, fy = hex_to_float(x, y)
        return in_weapon_arc(self.mech, fx, fy)

    def test_north_is_forward(self):
        self.assertEqual(self.arc_to_hex(10, 5), FORWARDARC)

    def test_south_is_rear(self):
        self.assertEqual(self.arc_to_hex(10, 15), REARARC)

    def test_east_is_right_side(self):
        # relat = 0 - 90 -> 270: RSIDEARC (>=240, <300)
        self.assertEqual(self.arc_to_hex(15, 10), RSIDEARC)

    def test_west_is_left_side(self):
        # relat = 0 - 270 -> 90: LSIDEARC (>60, <=120)
        self.assertEqual(self.arc_to_hex(5, 10), LSIDEARC)

    def test_facing_carries_the_arc(self):
        self.mech.facing = 90
        self.assertEqual(self.arc_to_hex(15, 10), FORWARDARC)
        self.assertEqual(self.arc_to_hex(10, 5), LSIDEARC)

    def test_torso_twist_right_pulls_east_into_forward(self):
        # C oddity: twist is 59 degrees, not 60 (mech.utils.c:429-433).
        # relat = 0 - 90 + 59 = -31 -> 329: forward.
        self.mech.set_status(MechStatus.TORSO_RIGHT)
        self.assertEqual(self.arc_to_hex(15, 10), FORWARDARC)

    def test_torso_twist_left_pulls_west_into_forward(self):
        # relat = 0 - 270 - 59 = -329 -> 31: forward.
        self.mech.set_status(MechStatus.TORSO_LEFT)
        self.assertEqual(self.arc_to_hex(5, 10), FORWARDARC)

    def test_los_module_delegates(self):
        fx, fy = hex_to_float(10, 15)
        self.assertEqual(los.in_weapon_arc(self.mech, fx, fy), REARARC)


class TestSensorCanSee(unittest.TestCase):
    """Sensor_CanSee (mech.sensor.c:79-158)."""

    def setUp(self):
        self.map = make_map()
        self.mech = make_mech(self.map, 10, 10, name="A")
        self.target = make_mech(self.map, 14, 10, name="B", team=2)

    def can_see(self, flag=MECHLOSFLAG_SEEC2, arc=FORWARDARC, rng=4.0):
        return sensor_can_see(self.mech, self.target, flag, arc, rng,
                              self.map.mapvis, self.map.maplight,
                              self.map.cloudbase)

    def test_identical_vislight_sensors_return_3(self):
        self.assertEqual(self.can_see(), 3)

    def test_seec2_gate(self):
        # Uncalculated terrain flag -> 0 (mech.sensor.c:89-90)
        self.assertEqual(self.can_see(flag=0), 0)

    def test_invisible_target(self):
        self.target.set_crit_status(CritStatus.INVISIBLE)
        self.assertEqual(self.can_see(), 0)

    def test_block_flag_defeats_vislight(self):
        self.assertEqual(
            self.can_see(flag=MECHLOSFLAG_SEEC2 | MECHLOSFLAG_BLOCK), 0)

    def test_arc_gate_vislight_vs_fullvision_ir(self):
        # Split sensors: vislight (fullvision=0) is arc-gated, IR
        # (fullvision=1) is not (mech.sensor.c:104-106).
        self.mech.sensor = [SENSOR_VIS, SENSOR_IR]
        self.assertEqual(self.can_see(arc=REARARC), 2)   # IR only
        self.assertEqual(self.can_see(arc=FORWARDARC), 3)

    def test_same_sensor_path_has_no_arc_gate(self):
        # C oddity: with identical sensors no arc/fullvision check is made
        # (mech.sensor.c:143-157).
        self.assertEqual(self.can_see(arc=REARARC), 3)

    def test_los_module_delegates(self):
        self.assertEqual(
            los.sensor_can_see(self.mech, self.target, MECHLOSFLAG_SEEC2,
                               FORWARDARC, 4.0, self.map.mapvis,
                               self.map.maplight, self.map.cloudbase), 3)

    def test_los_to_hit_bonus_delegates(self):
        # Unseen -> 10000 (Sensor_ToHitBonus, mech.sensor.c:42-43)
        self.assertEqual(
            los.sensor_to_hit_bonus(self.mech, self.target, 0, 2, 4.0, 0),
            10000)


class TestSensorDoWeSeeNow(unittest.TestCase):
    """Sensor_DoWeSeeNow (mech.sensor.c:333-461)."""

    def setUp(self):
        self.map = make_map()
        self.mech = make_mech(self.map, 10, 10, name="A", team=1)
        self.target = make_mech(self.map, 12, 10, name="B", team=2)

    def dwsn(self, flag, seeanew, rng=2.0, paranoia=0):
        return sensor_do_we_see_now(
            self.mech, flag, rng, -1, -1, self.target, self.map.mapvis,
            self.map.maplight, self.map.cloudbase, seeanew, paranoia)

    def test_not_started_returns_flag_unchanged(self):
        self.mech.clear_status(MechStatus.STARTED)
        self.assertEqual(self.dwsn(MECHLOSFLAG_SEEC2, 1), MECHLOSFLAG_SEEC2)

    def test_seeanew_zero_only_bumps_pnum_seen(self):
        # The update_LOSinfo pass never gains contacts (mech.sensor.c:409-413)
        f = self.dwsn(MECHLOSFLAG_SEEC2, 0)
        self.assertEqual(f, MECHLOSFLAG_SEEC2)
        self.assertEqual(self.mech.pnum_seen, 1)

    def test_contact_gain_at_point_blank(self):
        # range < 3 auto-succeeds Sensor_Sees (mech.sensor.c:236)
        f = self.dwsn(MECHLOSFLAG_SEEC2, 1)
        self.assertTrue(f & MECHLOSFLAG_SEEN)
        self.assertTrue(f & MECHLOSFLAG_SEESP)
        self.assertTrue(f & MECHLOSFLAG_SEESS)
        self.assertEqual(self.mech.num_seen, 1)     # enemy contact
        self.assertEqual(self.mech.pnum_seen, 0)

    def test_contact_gain_at_range_with_forced_roll(self):
        with mock.patch.object(sensors_mod.random, 'randint',
                               return_value=1):
            f = self.dwsn(MECHLOSFLAG_SEEC2, 1, rng=10.0)
        self.assertTrue(f & MECHLOSFLAG_SEEN)
        self.assertTrue(f & (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS))

    def test_contact_gain_failed_roll_bumps_pnum_seen(self):
        with mock.patch.object(sensors_mod.random, 'randint',
                               return_value=10000):
            f = self.dwsn(MECHLOSFLAG_SEEC2, 1, rng=10.0)
        self.assertFalse(f & MECHLOSFLAG_SEEN)
        self.assertEqual(self.mech.pnum_seen, 1)

    def test_contact_loss(self):
        self.mech.num_seen = 1
        f = self.dwsn(MECHLOSFLAG_SEEN | MECHLOSFLAG_SEEC2 |
                      MECHLOSFLAG_BLOCK, 0)
        self.assertFalse(f & MECHLOSFLAG_SEEN)
        self.assertFalse(f & (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS))
        self.assertEqual(self.mech.num_seen, 0)     # decremented
        self.assertEqual(self.mech.pnum_seen, 1)

    def test_contact_loss_drops_lock(self):
        # LoseLock on losing the locked target (mech.sensor.c:387-392)
        self.mech.set_status(MechStatus.LOCK_TARGET)
        self.mech.target = self.target._id
        self.dwsn(MECHLOSFLAG_SEEN | MECHLOSFLAG_SEEC2 |
                  MECHLOSFLAG_BLOCK, 0)
        self.assertEqual(self.mech.target, -1)

    def test_contact_loss_keeps_other_locks(self):
        other = make_mech(self.map, 20, 20, name="C", team=2)
        self.mech.set_status(MechStatus.LOCK_TARGET)
        self.mech.target = other._id
        self.dwsn(MECHLOSFLAG_SEEN | MECHLOSFLAG_SEEC2 |
                  MECHLOSFLAG_BLOCK, 0)
        self.assertEqual(self.mech.target, other._id)


class TestUpdateLosInfo(unittest.TestCase):
    """update_LOSinfo (mech.sensor.c:463-580)."""

    def setUp(self):
        self.map = make_map()
        self.a = make_mech(self.map, 10, 10, name="A", team=1)
        self.b = make_mech(self.map, 14, 10, name="B", team=2)
        self.key_ab = (self.a._id, self.b._id)
        self.key_ba = (self.b._id, self.a._id)

    def test_first_sweep_fills_losinfo_both_directions(self):
        self.assertEqual(self.map.losinfo[self.key_ab], 0)
        self.assertEqual(self.map.losinfo[self.key_ba], 0)
        update_los_info(self.map)
        self.assertTrue(self.map.losinfo[self.key_ab] & MECHLOSFLAG_SEEC2)
        self.assertTrue(self.map.losinfo[self.key_ba] & MECHLOSFLAG_SEEC2)
        self.assertFalse(self.map.losinfo[self.key_ab] & MECHLOSFLAG_BLOCK)

    def test_sweep_alone_never_gains_contact(self):
        # seeanew=0: could-see only bumps pnum_seen (mech.sensor.c:409-413)
        update_los_info(self.map)
        self.assertFalse(self.map.losinfo[self.key_ab] &
                         (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS))
        self.assertEqual(self.a.pnum_seen, 1)
        self.assertEqual(self.b.pnum_seen, 1)

    def test_open_ground_maintains_contact_with_sees_bits(self):
        # Once SEEN (PLOS gain simulated), the sweep keeps the SEES bits up.
        update_los_info(self.map)
        self.map.losinfo[self.key_ab] |= MECHLOSFLAG_SEEN
        update_los_info(self.map)
        f = self.map.losinfo[self.key_ab]
        self.assertTrue(f & MECHLOSFLAG_SEEN)
        self.assertTrue(f & MECHLOSFLAG_SEESP)
        self.assertTrue(f & MECHLOSFLAG_SEESS)

    def test_mountain_wall_blocks_and_loses_contact(self):
        update_los_info(self.map)
        self.map.losinfo[self.key_ab] |= MECHLOSFLAG_SEEN
        update_los_info(self.map)
        self.assertTrue(self.map.losinfo[self.key_ab] & MECHLOSFLAG_SEESP)
        wall(self.map, 12)
        update_los_info(self.map)
        f = self.map.losinfo[self.key_ab]
        self.assertTrue(f & MECHLOSFLAG_BLOCK)
        self.assertFalse(f & (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS))
        self.assertFalse(f & MECHLOSFLAG_SEEN)

    def test_terrain_change_recomputes_without_moved_flag(self):
        # This checkout's moved-gating is `if(1)` (mech.sensor.c:477, 517):
        # every pair recomputes every sweep, MOVED or not.
        update_los_info(self.map)
        self.map.losinfo[self.key_ab] |= MECHLOSFLAG_SEEN
        update_los_info(self.map)
        self.assertTrue(self.map.losinfo[self.key_ab] & MECHLOSFLAG_SEESP)
        wall(self.map, 12)
        self.assertEqual(self.a.mapflag, 0)     # no MOVED flag set
        update_los_info(self.map)
        self.assertFalse(self.map.losinfo[self.key_ab] &
                         (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS))

    def test_moved_flags_cleared_after_sweep(self):
        # map->mechflags[i] = 0 for the whole roster (mech.sensor.c:574-575)
        self.a.mapflag |= MECHMAPFLAG_MOVED
        self.b.mapflag |= MECHMAPFLAG_MOVED
        update_los_info(self.map)
        self.assertEqual(self.a.mapflag, 0)
        self.assertEqual(self.b.mapflag, 0)

    def test_contact_loss_drops_lock_end_to_end(self):
        update_los_info(self.map)
        self.map.losinfo[self.key_ab] |= MECHLOSFLAG_SEEN
        update_los_info(self.map)
        self.a.set_status(MechStatus.LOCK_TARGET)
        self.a.target = self.b._id
        wall(self.map, 12)
        update_los_info(self.map)
        self.assertEqual(self.a.target, -1)

    def test_out_of_maxvis_is_plain_block(self):
        # range > maxvis at low Z: flag becomes BLOCK alone, wiping
        # SEEN/SEEC2 (mech.sensor.c:489-493).
        self.map.maxvis = 3
        update_los_info(self.map)
        self.assertEqual(self.map.losinfo[self.key_ab], MECHLOSFLAG_BLOCK)
        self.assertEqual(self.map.losinfo[self.key_ba], MECHLOSFLAG_BLOCK)

    def test_non_started_looker_skipped_but_still_a_target(self):
        self.b.clear_status(MechStatus.STARTED)
        update_los_info(self.map)
        self.assertIn(self.key_ab, self.map.losinfo)
        self.assertEqual(self.map.losinfo[self.key_ba], 0)

    def test_ecm_looker_triggers_check_ecm_on_target(self):
        # ECM side call of the sweep (mech.sensor.c:481-483)
        self.a.status2 = ECM_ENABLED
        update_los_info(self.map)
        self.assertEqual(self.b.ecm_disturbed, 1)
        self.assertEqual(self.b.angel_ecm_disturbed, 0)


class TestCheckEcm(unittest.TestCase):
    """checkECM (mech.ecm.c:103-290)."""

    def setUp(self):
        self.map = make_map()
        self.mech = make_mech(self.map, 10, 10, name="A", team=1)

    def test_ecmless_mech_is_stable_noop(self):
        make_mech(self.map, 12, 10, name="B", team=2)
        initial_mapflag = self.mech.mapflag
        for _ in range(2):
            check_ecm(self.mech)
            self.assertEqual(self.mech.ecm_disturbed, 0)
            self.assertEqual(self.mech.ecm_protected, 0)
            self.assertEqual(self.mech.angel_ecm_protected, 0)
            self.assertEqual(self.mech.angel_ecm_disturbed, 0)
        self.assertEqual(getattr(self.mech, 'status2', 0), 0)
        self.assertEqual(self.mech.mapflag, initial_mapflag)

    def test_mapless_mech_gets_zeroed_attrs(self):
        loner = Mech.create_test_mech("Loner")
        check_ecm(loner)
        self.assertEqual(loner.ecm_disturbed, 0)
        self.assertEqual(loner.ecm_protected, 0)

    def test_enemy_ecm_disturbs(self):
        enemy = make_mech(self.map, 13, 10, name="E", team=2)
        enemy.status2 = ECM_ENABLED
        check_ecm(self.mech)
        self.assertEqual(self.mech.ecm_disturbed, 1)
        self.assertEqual(self.mech.angel_ecm_disturbed, 0)
        # New disturbance marks for LOS update (mech.ecm.c:265-280)
        self.assertTrue(self.mech.mapflag & MECHMAPFLAG_MOVED)

    def test_enemy_ecm_out_of_range_is_ignored(self):
        enemy = make_mech(self.map, 20, 10, name="E", team=2)  # 10 > ECM_RANGE
        enemy.status2 = ECM_ENABLED
        check_ecm(self.mech)
        self.assertEqual(self.mech.ecm_disturbed, 0)

    def test_own_ecm_protects_self(self):
        # The roster scan includes the unit itself (mech.ecm.c:129-131)
        self.mech.status2 = ECM_ENABLED
        check_ecm(self.mech)
        self.assertEqual(self.mech.ecm_protected, 1)
        self.assertEqual(self.mech.ecm_disturbed, 0)

    def test_friendly_eccm_counters_enemy_ecm(self):
        ally = make_mech(self.map, 11, 10, name="F", team=1)
        ally.status2 = ECCM_ENABLED
        enemy = make_mech(self.map, 13, 10, name="E", team=2)
        enemy.status2 = ECM_ENABLED
        check_ecm(self.mech)
        # ECCM delta = 1 - 1 = 0, not < 0 -> no disturbance
        self.assertEqual(self.mech.ecm_disturbed, 0)

    def test_enemy_eccm_counters_own_ecm(self):
        self.mech.status2 = ECM_ENABLED
        enemy = make_mech(self.map, 13, 10, name="E", team=2)
        enemy.status2 = ECCM_ENABLED
        check_ecm(self.mech)
        self.assertTrue(self.mech.status2 & ECM_COUNTERED)
        self.assertEqual(self.mech.ecm_protected, 0)

    def test_disturbance_clears_when_ecm_leaves(self):
        enemy = make_mech(self.map, 13, 10, name="E", team=2)
        enemy.status2 = ECM_ENABLED
        check_ecm(self.mech)
        self.assertEqual(self.mech.ecm_disturbed, 1)
        enemy.status2 = 0
        self.mech.mapflag = 0
        check_ecm(self.mech)
        self.assertEqual(self.mech.ecm_disturbed, 0)
        self.assertFalse(self.mech.status2 & ECM_DISTURBANCE)
        # Clearing the disturbance also marks for LOS update
        self.assertTrue(self.mech.mapflag & MECHMAPFLAG_MOVED)


class TestMovementMarksForLosUpdate(unittest.TestCase):
    """MarkForLOSUpdate at the NewHexEntered tail (mech.update.c:2695)."""

    def test_new_hex_entered_sets_moved_flag(self):
        from physics.movement import new_hex_entered
        gamemap = make_map()
        mech = make_mech(gamemap, 10, 10)
        mech.last_x, mech.last_y = 9, 10
        new_hex_entered(mech, 322.5, 0.0, 0)
        self.assertTrue(mech.mapflag & MECHMAPFLAG_MOVED)


class TestEngineWiring(unittest.TestCase):
    """map_update -> update_LOSinfo (map.c:596) and mech_update -> checkECM
    (mech.update.c:2986) through the standard engine wiring."""

    def test_map_sweep_fills_losinfo(self):
        engine = GameEngine()
        wire_standard_systems(engine)
        gamemap = make_map()
        a = make_mech(gamemap, 10, 10, name="A", team=1)
        b = make_mech(gamemap, 10, 9, name="B", team=2)
        engine.register_entity(gamemap)
        engine.register_entity(a)
        engine.register_entity(b)
        engine.run_ticks(3)
        self.assertIsNotNone(gamemap.losinfo)
        self.assertTrue(gamemap.losinfo[(a._id, b._id)] & MECHLOSFLAG_SEEC2)
        self.assertTrue(gamemap.losinfo[(b._id, a._id)] & MECHLOSFLAG_SEEC2)
        # Live registration now starts PLOS. At point blank this acquires
        # deterministically, leaving no unacquired candidate count.
        self.assertTrue(gamemap.losinfo[(a._id,b._id)] & MECHLOSFLAG_SEEN)
        self.assertEqual(a.pnum_seen, 0)

    def test_mech_sweep_runs_check_ecm(self):
        engine = GameEngine()
        wire_standard_systems(engine)
        gamemap = make_map()
        a = make_mech(gamemap, 10, 10, name="A", team=1)
        b = make_mech(gamemap, 12, 10, name="B", team=2)
        b.status2 = ECM_ENABLED
        engine.register_entity(gamemap)
        engine.register_entity(a)
        engine.register_entity(b)
        engine.run_ticks(4)                     # MECH sweep at HEAT_TICK = 2
        self.assertEqual(a.ecm_disturbed, 1)
        self.assertEqual(b.ecm_protected, 1)    # own ECM protects


class TestFaMechRange(unittest.TestCase):
    """FaMechRange (btmacros.h:733-735)."""

    def test_flat_range_matches_hex_distance(self):
        gamemap = make_map()
        a = make_mech(gamemap, 10, 10, name="A")
        b = make_mech(gamemap, 10, 14, name="B")   # same column: 1.0/hex
        self.assertAlmostEqual(fa_mech_range(a, b), 4.0, places=3)

    def test_z_counts(self):
        gamemap = make_map()
        a = make_mech(gamemap, 10, 10, name="A")
        b = make_mech(gamemap, 10, 10, name="B")
        b.set_hex_position(10, 10, 5)           # 5 levels = 1 hex (ZSCALE)
        self.assertAlmostEqual(fa_mech_range(a, b), 1.0, places=3)


if __name__ == '__main__':
    unittest.main()
