"""
Unit tests for the command-level fire entry (fire_weapon_number,
mech.combat.c:372-712) and the Workstream-D BTH terms wired into
calculate_bth (terrain/sensor, mech.bth.c:368-373; unstable lock,
mech.bth.c:269-281).

losinfo is hand-filled (dict keyed (looker._id, target._id)) — these tests
do not depend on the LOS update wave; the rollpad acceptance test
(tests/test_rollpad.py) covers the live plumbing.
"""

import sys
import unittest

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.game_loop import GameEngine
from data.templates import get_template, create_mech_from_template
from entities.map import GameMap, HEAVY_FOREST, LIGHT_FOREST
from entities.mech import MechStatus
from entities.weapon import get_weapon_by_index
from physics.hexmath import FORWARDARC, LSIDEARC, REARARC, TURRETARC
from systems.combat import (
    UNSTABLE_LOCK_HIPSHOT, calculate_bth, fire_weapon_number,
)
from systems.los import (
    MECHLOSFLAG_PARTIAL, MECHLOSFLAG_SEEC2, MECHLOSFLAG_SEEN,
    MECHLOSFLAG_SEESP,
)
from systems.targeting import set_target

SEES = MECHLOSFLAG_SEEN | MECHLOSFLAG_SEESP | MECHLOSFLAG_SEEC2


def total_armor(mech) -> int:
    # Front + rear: the fixture attacker sits behind its north-facing
    # targets, so hits land on rear plates.
    return sum(s.armor + s.rear for s in mech.sections)


class FireGatingFixture(unittest.TestCase):
    """Engine + map + started template mechs, hand-filled losinfo.

    Attacker at (10,10) facing north; Bravo 3 hexes due north (forward
    arc); Charlie 3 hexes due south (rear arc)."""

    def setUp(self):
        self.engine = GameEngine()
        self.map = GameMap(30, 30)
        self.map._id = 1000
        self.engine.register_entity(self.map)
        self.map.mapvis = 30
        self.map.maplight = 2
        self.map.maxvis = 60
        self.map.losinfo = {}
        self.att = create_mech_from_template(get_template("TestMech"),
                                             name="Alpha")
        self.dfn = create_mech_from_template(get_template("TestMech"),
                                             name="Bravo")
        self.thd = create_mech_from_template(get_template("TestMech"),
                                             name="Charlie")
        self.att.set_hex_position(10, 10)
        self.att.facing = 0
        self.dfn.set_hex_position(10, 7)
        self.thd.set_hex_position(10, 13)
        for m in (self.att, self.dfn, self.thd):
            self.map.add_mech(m)
            self.engine.register_entity(m)
            m.set_status(MechStatus.STARTED)

    def see(self, looker, target, flag=SEES):
        self.map.losinfo[(looker._id, target._id)] = flag

    def lock(self, target=None):
        target = target if target is not None else self.dfn
        self.see(self.att, target)
        ok, msg = set_target(self.engine, self.att, target)
        self.assertTrue(ok, msg)


# =============================================================================
# Case 1 gates (fire at the default target, mech.combat.c:527-628)
# =============================================================================

class TestFireGates(FireGatingFixture):

    def test_no_lock_fails_with_c_text(self):
        # DOCHECK0(!FindTargetXY(...), ...) (mech.combat.c:544-545)
        result = fire_weapon_number(self.engine, self.att, 0)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["You do not have a default target set!"])
        # Nothing fired: no recycle, no FIRED status
        self.assertEqual(self.att.weapons[0].recycle, 0)
        self.assertFalse(self.att.has_status(MechStatus.FIRED))

    def test_reactor_offline_gate(self):
        # cch(MECH_USUALO) runs before FireWeaponNumber (mech.combat.c:351)
        self.att.clear_status(MechStatus.STARTED)
        result = fire_weapon_number(self.engine, self.att, 0)
        self.assertEqual(result.messages, ["Reactor is not online!"])

    def test_illegal_weapon_number(self):
        # mech.combat.c:419-428 — negative and not-found chirp the same
        for bad in (-1, len(self.att.weapons)):
            result = fire_weapon_number(self.engine, self.att, bad)
            self.assertEqual(
                result.messages,
                ["The weapons system chirps: 'Illegal Weapon Number!'"])

    def test_locked_fire_resolves_roster_target(self):
        self.lock()
        armor_before = total_armor(self.dfn)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertLess(total_armor(self.dfn), armor_before)
        self.assertTrue(self.att.has_status(MechStatus.FIRED))
        self.assertGreater(self.att.weapons[0].recycle, 0)
        # Stable instant lock: no unstable-lock term
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 0)

    def test_fire_time_los_failure_reads_cached_bits(self):
        # Lock while seen, then the cache goes stale-dark (as the 1 Hz
        # sweep would write after cover): fire must fail on the CACHED
        # flag (LOS_NB, mech.combat.c:554-558).
        self.lock()
        self.map.losinfo[(self.att._id, self.dfn._id)] = 0
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["That target is not in your line of sight!"])

    def test_arc_gate_rear_target(self):
        # Charlie is due south of the north-facing attacker: no mech
        # weapon fires rearward unless rear-mounted/flipped
        # (IsInWeaponArc, mech.utils.c:1770-1786; ARCCHECK text at
        # mech.combat.c:623-626).
        self.lock(self.thd)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["Default target is not in your weapons arc!"])

    def test_arc_mapping_arm_vs_torso(self):
        # Target due west: LARM covers FORWARDARC|LSIDEARC, the RTORSO
        # AC/10 (weapon 2) only FORWARDARC (mech.utils.c:1773-1786).
        self.dfn.set_hex_position(7, 10)
        self.lock()
        laser = fire_weapon_number(self.engine, self.att, 0,
                                   to_hit_roll=12, location_roll=7)
        self.assertTrue(laser.hit)
        ac10 = fire_weapon_number(self.engine, self.att, 2,
                                  to_hit_roll=12, location_roll=7)
        self.assertEqual(ac10.messages,
                         ["Default target is not in your weapons arc!"])


# =============================================================================
# Case 2 (fire <n> <targetID> at an unlocked contact, mech.combat.c:630-655)
# — reviewed C branch allows an explicit visible target without a lock
# =============================================================================

class TestCase2ConfigGate(FireGatingFixture):

    def test_source_allows_unlocked_target(self):
        # mech.combat.c:630-655 permits visible explicit contacts.
        self.see(self.att, self.dfn)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    target=self.dfn, to_hit_roll=12,
                                    location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 2)

    def test_config_off_still_fires_at_own_lock(self):
        self.lock()
        result = fire_weapon_number(self.engine, self.att, 0,
                                    target=self.dfn,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 0)

    def test_config_on_hip_shot_is_plus_two(self):
        # No lock anywhere: FindTargetXY fails -> "HipShot-NoLock" +2
        # (mech.bth.c:278-280)
        self.see(self.att, self.dfn)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    target=self.dfn,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 2)

    def test_config_on_off_lock_forward_arc_is_plus_one(self):
        # Locked to Bravo (due north = forward arc), firing at Charlie's
        # position is off-lock: arc of the LOCK's coordinates decides
        # (mech.bth.c:272-274).  Fire at Bravo's wingman also to the
        # north to keep the fired-at unit in the weapon arc.
        self.thd.set_hex_position(11, 7)             # move Charlie north
        self.lock(self.dfn)                          # lock: forward arc
        self.see(self.att, self.thd)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    target=self.thd,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 1)

    def test_config_on_off_lock_side_arc_is_plus_two(self):
        # Lock coordinates west (left-side arc): +2 (mech.bth.c:275-276)
        self.thd.set_hex_position(7, 10)             # Charlie due west
        self.lock(self.thd)                          # lock: side arc
        self.see(self.att, self.dfn)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    target=self.dfn,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 2)

    def test_config_on_target_off_map_is_los_failure(self):
        # FindTargetDBREFFromMapNumber can only resolve same-map contacts
        # (mech.combat.c:634-636)
        stranger = create_mech_from_template(get_template("TestMech"),
                                             name="Delta")
        stranger.set_status(MechStatus.STARTED)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    target=stranger)
        self.assertEqual(result.messages,
                         ["That target is not in your line of sight!"])


# =============================================================================
# calculate_bth: unstable-lock kwarg (mech.bth.c:269-281)
# =============================================================================

class TestUnstableLockTerm(FireGatingFixture):

    def bth(self, **kwargs):
        weapon = get_weapon_by_index(self.att.weapons[0].weapon_idx)
        return calculate_bth(self.att, self.dfn, weapon, 3.0, **kwargs)

    def test_default_no_term(self):
        self.assertEqual(self.bth().unstable_lock_mod, 0)

    def test_forward_and_turret_arcs_plus_one(self):
        for arc in (FORWARDARC, TURRETARC, FORWARDARC | LSIDEARC):
            b = self.bth(unstable_lock_arc=arc)
            self.assertEqual(b.unstable_lock_mod, 1)

    def test_off_arc_plus_two(self):
        for arc in (LSIDEARC, REARARC, 0):
            b = self.bth(unstable_lock_arc=arc)
            self.assertEqual(b.unstable_lock_mod, 2)

    def test_hip_shot_plus_two(self):
        b = self.bth(unstable_lock_arc=UNSTABLE_LOCK_HIPSHOT)
        self.assertEqual(b.unstable_lock_mod, 2)

    def test_term_summed_into_total(self):
        base = self.bth().total
        self.assertEqual(self.bth(unstable_lock_arc=FORWARDARC).total,
                         base + 1)
        self.assertEqual(
            self.bth(unstable_lock_arc=UNSTABLE_LOCK_HIPSHOT).total,
            base + 2)


# =============================================================================
# calculate_bth: terrain/sensor term (mech.bth.c:368-373)
# =============================================================================

class TestTerrainMod(FireGatingFixture):

    def bth(self):
        weapon = get_weapon_by_index(self.att.weapons[0].weapon_idx)
        return calculate_bth(self.att, self.dfn, weapon, 3.0)

    def test_light_woods_target_daylight_vislight(self):
        # Vislight in full day on an unlit target: (2-2)=0 light penalty +
        # nwood_count = target's own light-forest hex = 1
        # (mech.sensor.functions.c:163-173)
        self.map.set_terrain(self.dfn.x, self.dfn.y, LIGHT_FOREST)
        self.see(self.att, self.dfn)
        self.assertEqual(self.bth().terrain_mod, 1)

    def test_heavy_woods_target_is_two(self):
        self.map.set_terrain(self.dfn.x, self.dfn.y, HEAVY_FOREST)
        self.see(self.att, self.dfn)
        self.assertEqual(self.bth().terrain_mod, 2)

    def test_partial_cover_adds_three_and_flags_target(self):
        self.see(self.att, self.dfn, SEES | MECHLOSFLAG_PARTIAL)
        self.assertEqual(self.bth().terrain_mod, 3)
        # AddTerrainMod's side effect (mech.los.c:291-296)
        self.assertTrue(self.dfn.has_status(MechStatus.PARTIAL_COVER))

    def test_not_seen_sentinel_leaves_terrain_mod_zero(self):
        # Sensor_ToHitBonus returns 10000 without SEES bits
        # (mech.sensor.c:38-40); the j < 1000 gate skips the term
        # (mech.bth.c:370-372)
        self.see(self.att, self.dfn, 0)
        self.assertEqual(self.bth().terrain_mod, 0)

    def test_mapless_calculate_bth_unchanged(self):
        att = create_mech_from_template(get_template("TestMech"), name="X")
        dfn = create_mech_from_template(get_template("TestMech"), name="Y")
        att.set_status(MechStatus.STARTED)
        weapon = get_weapon_by_index(att.weapons[0].weapon_idx)
        b = calculate_bth(att, dfn, weapon, 3.0)
        self.assertEqual(b.terrain_mod, 0)
        self.assertEqual(b.unstable_lock_mod, 0)


if __name__ == '__main__':
    unittest.main()
