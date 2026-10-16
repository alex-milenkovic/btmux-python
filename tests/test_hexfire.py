"""
Unit tests for hex-targeted fire (the case-1 hex branch of
fire_weapon_number, mech.combat.c:560-628), the find_mech_in_hex probe
(mech.utils.c:2537-2567), the "HexBonus" BTH term (mech.bth.c:292-295),
the impossible-roll gate (mech.combat.c:961-966) and the hex_hit dispatch
(mech.combat.c:1992-2012).

Mech-to-mech LOS reads the cached losinfo bits (hand-filled, as in
test_fire_gating); hex LOS is computed live, so the fixture map carries
mapvis/maplight/maxvis.  Dice are pinned with explicit roll kwargs.
"""

import sys
import unittest
from unittest import mock

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.game_loop import GameEngine
from data.templates import get_template, create_mech_from_template
from entities.map import GameMap
from entities.mech import MechStatus
import systems.combat as combat
from systems.combat import (
    HEX_LOCK_MODES, fire_weapon_number, hex_hit, hex_target_id,
    mech_lock_fire,
)
from systems.los import (
    MECHLOSFLAG_SEEC2, MECHLOSFLAG_SEEN, MECHLOSFLAG_SEESP,
)
from systems.targeting import find_mech_in_hex, set_target_hex

SEES = MECHLOSFLAG_SEEN | MECHLOSFLAG_SEESP | MECHLOSFLAG_SEEC2


def total_armor(mech) -> int:
    return sum(s.armor + s.rear for s in mech.sections)


class HexFireFixture(unittest.TestCase):
    """Attacker at (10,10) facing north; Bravo 3 hexes due north; Charlie
    3 hexes due south (rear arc).  IDF tests use an AssaultMech (weapon 3
    = IS.LRM-10, RTORSO/forward arc)."""

    def setUp(self):
        self.engine = GameEngine()
        self.map = GameMap(30, 30)
        self.map._id=1000
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
            m.set_status(MechStatus.STARTED)
            self.engine.register_entity(m)
            self.map.add_mech(m)
            m.mapindex=self.map._id

    def see(self, looker, target, flag=SEES):
        self.map.losinfo[(looker._id, target._id)] = flag

    def lock_hex(self, x, y, mode=None):
        ok, msg = set_target_hex(self.engine, self.att, x, y, mode)
        self.assertTrue(ok, msg)


# =============================================================================
# find_mech_in_hex (mech.utils.c:2537-2567)
# =============================================================================

class TestFindMechInHex(HexFireFixture):

    def test_finds_first_in_map_order_and_skips_self(self):
        # Charlie shares Bravo's hex but Bravo was added first: the C's
        # linear mechsOnMap scan returns the FIRST match, no random pick
        # (mech.utils.c:2542-2564).
        self.thd.set_hex_position(10, 7)
        found = find_mech_in_hex(self.att, self.map, 10, 7, 0)
        self.assertIs(found, self.dfn)
        # Self is skipped even in its own hex (mech.utils.c:2543)
        self.assertIsNone(find_mech_in_hex(self.att, self.map, 10, 10, 0))

    def test_needlos_zero_has_no_team_filter(self):
        # Friendlies are found too (no team check outside needlos & 2)
        self.dfn.team = self.att.team
        self.assertIs(find_mech_in_hex(self.att, self.map, 10, 7, 0),
                      self.dfn)

    def test_empty_hex_returns_none(self):
        self.assertIsNone(find_mech_in_hex(self.att, self.map, 5, 5, 0))


# =============================================================================
# The probe: plain LOCK_TARGET coordinate locks only (mech.combat.c:574-586)
# =============================================================================

class TestHexProbe(HexFireFixture):

    def test_mech_lock_fire_predicate(self):
        # MechLockFire (mech.h:1078-1080): plain coordinate lock only
        self.lock_hex(10, 7)
        self.assertTrue(mech_lock_fire(self.att))
        for mode in ('B', 'I', 'C', 'H'):
            self.lock_hex(10, 7, mode)
            self.assertFalse(mech_lock_fire(self.att))

    def test_plain_lock_probe_finds_and_attacks_hex_occupant(self):
        # "look for enemies in the default hex cause they may have moved"
        # (mech.combat.c:576-586): the shot resolves against Bravo, and a
        # hex-found mech always takes the unstable-lock term
        # (MechTarget == -1 != temp->mynum, mech.bth.c:270-273); the lock
        # coordinates are due north = forward arc = +1.
        self.see(self.att, self.dfn)
        self.lock_hex(10, 7)
        armor_before = total_armor(self.dfn)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertLess(total_armor(self.dfn), armor_before)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 1)
        # No mech was "not found": no HexBonus (mech.bth.c:292-295)
        self.assertEqual(result.bth_breakdown.hex_mod, 0)

    def test_explicit_hex_mode_skips_the_probe(self):
        # All four explicit hex-lock modes are excluded from MechLockFire,
        # so Bravo standing in the locked hex is NOT engaged: the shot is
        # a pure hex impact.
        self.lock_hex(10, 7, 'H')
        armor_before = total_armor(self.dfn)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(total_armor(self.dfn), armor_before)
        # Empty-hex resolution in an explicit mode: HexBonus -4
        # (mech.bth.c:292-295)
        self.assertEqual(result.bth_breakdown.hex_mod, -4)
        # No unit hit: no unstable-lock term (mech.bth.c:270 requires
        # `target`)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 0)

    def test_plain_lock_empty_hex_gets_no_hex_bonus(self):
        # A plain LOCK_TARGET hex shot at an empty hex has no explicit
        # hex-lock bit: no -4 (mech.bth.c:292-295).
        self.lock_hex(12, 7)            # empty hex
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(result.bth_breakdown.hex_mod, 0)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 0)


# =============================================================================
# LOS / spotter / arc gates (mech.combat.c:599-628)
# =============================================================================

class TestHexGates(HexFireFixture):

    def darken(self):
        # range > maxvis makes the live hex-LOS flag plain BLOCK
        # (see tests/test_sensor_los.py) - the cheapest way to kill hex LOS
        self.map.maxvis = 0

    def test_non_idf_requires_hex_los(self):
        # DOCHECK0(!LOS, ...) (mech.combat.c:612-616)
        self.darken()
        self.lock_hex(12, 7)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["That hex target is not in your line of sight!"])

    def _idf_attacker(self):
        idf = create_mech_from_template(get_template("AssaultMech"),
                                        name="Delta")
        idf.set_hex_position(10, 20)
        idf.facing = 0
        idf.set_status(MechStatus.STARTED)
        self.engine.register_entity(idf)
        self.map.add_mech(idf)
        idf.mapindex=self.map._id
        return idf      # weapon 3 = IS.LRM-10 (IDF), RTORSO/forward arc

    def test_idf_no_spotter_gate_message(self):
        # mudconf.btech_idf_requires_spotter defaults ON (src/conf.c:141);
        # gate text at mech.combat.c:604-610.
        self.darken()
        idf = self._idf_attacker()
        ok, msg = set_target_hex(self.engine, idf, 10, 13)
        self.assertTrue(ok, msg)
        result = fire_weapon_number(self.engine, idf, 3, to_hit_roll=12)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["That hex target is not in your direct line of "
                          "sight and you do not have a spotter set!!"])

    def test_idf_blindfire_when_config_off(self):
        # With the spotter requirement off, IDF weapons are exempt from
        # the hex LOS gate (mech.combat.c:612-614): LRM blindfire.
        self.darken()
        self.engine.idf_requires_spotter = False
        idf = self._idf_attacker()
        ok, msg = set_target_hex(self.engine, idf, 10, 13)  # 7 hexes north
        self.assertTrue(ok, msg)
        result = fire_weapon_number(self.engine, idf, 3,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertTrue(idf.has_status(MechStatus.FIRED))

    def test_arc_gate(self):
        # ARCCHECK (mech.combat.c:624-628): the locked hex is due south of
        # the north-facing attacker.
        self.lock_hex(10, 13, 'H')
        self.thd.set_hex_position(12, 13)   # empty the hex, keep it dull
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["Default target is not in your weapons arc!"])


# =============================================================================
# Impossible-roll gate (mech.combat.c:961-966)
# =============================================================================

class TestImpossibleRoll(HexFireFixture):

    def test_bth_over_12_draws_but_never_fires(self):
        self.att.base_to_hit = 20
        self.lock_hex(12, 7)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12)
        self.assertTrue(result.roll_impossible)
        self.assertFalse(result.hit)
        self.assertEqual(result.roll, 12)   # Source draws before the impossible check.
        # Exact C text (mech.combat.c:962-965); &name[3] skips "IS."
        self.assertEqual(
            result.messages,
            ["Fire %s at (%d,%d) - BTH: %d  Roll: Impossible!"
             % ("MediumLaser", 12, 7, result.bth)])
        # Returned BEFORE the post-fire tail: no heat, no recycle, no FIRED
        self.assertEqual(self.att.weap_heat, 0.0)
        self.assertEqual(self.att.weapons[0].recycle, 0)
        self.assertFalse(self.att.has_status(MechStatus.FIRED))

    def test_mech_lock_fire_has_the_same_impossible_gate(self):
        # Both branches draw before rejecting BTH > 12 without firing.
        from systems.targeting import set_target
        self.att.base_to_hit = 20
        self.see(self.att, self.dfn)
        ok, msg = set_target(self.engine, self.att, self.dfn)
        self.assertTrue(ok, msg)
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12)
        self.assertTrue(result.roll_impossible)
        self.assertEqual(result.roll, 12)


# =============================================================================
# hex_hit dispatch (mech.combat.c:1992-2012) and the miss path
# (mech.combat.c:1339-1351)
# =============================================================================

class TestHexHitDispatch(HexFireFixture):

    def dispatch(self, mode=None):
        """hex_hit with a given explicit lock mode; returns stub mocks."""
        self.att.clear_status(MechStatus.LOCK_MODES)
        if mode is not None:
            self.att.set_status(mode)
        with mock.patch.object(combat, 'hit_building') as hb, \
                mock.patch.object(combat, 'possibly_ignite_or_clear') as pic, \
                mock.patch.object(combat, 'possibly_blow_ice') as ice, \
                mock.patch.object(combat, 'possibly_blow_bridge') as br:
            hex_hit(self.att, 12, 7, 1, 0, 5, 1)
        return hb, pic, ice, br

    def test_plain_lock_is_a_noop(self):
        # Pure dispatch: nothing without an explicit hex-lock bit
        # (mech.combat.c:1995-1997)
        self.att.set_status(MechStatus.LOCK_TARGET)
        hb, pic, ice, br = self.dispatch()
        for stub in (hb, pic, ice, br):
            stub.assert_not_called()

    def test_lock_building_hit_calls_hit_building(self):
        hb, pic, ice, br = self.dispatch(MechStatus.LOCK_BUILDING)
        hb.assert_called_once_with(self.att, 12, 7, 1, 5)
        pic.assert_not_called()

    def test_lock_building_miss_skips_hit_building(self):
        self.att.clear_status(MechStatus.LOCK_MODES)
        self.att.set_status(MechStatus.LOCK_BUILDING)
        with mock.patch.object(combat, 'hit_building') as hb:
            hex_hit(self.att, 12, 7, 1, 0, 5, 0)    # ishit == 0
        hb.assert_not_called()

    def test_lock_hex_ignites_and_blows_ice_and_bridge(self):
        hb, pic, ice, br = self.dispatch(MechStatus.LOCK_HEX)
        pic.assert_called_once_with(self.att, 1, 0, 5, 12, 7, 1)
        ice.assert_called_once_with(self.att, 1, 12, 7)
        br.assert_called_once_with(self.att, 1, 12, 7)
        hb.assert_not_called()

    def test_lock_hex_ign_and_clr_ignite_only(self):
        for mode in (MechStatus.LOCK_HEX_IGN, MechStatus.LOCK_HEX_CLR):
            hb, pic, ice, br = self.dispatch(mode)
            pic.assert_called_once_with(self.att, 1, 0, 5, 12, 7, 1)
            ice.assert_not_called()
            br.assert_not_called()

    def test_fired_hex_hit_carries_weapon_and_damage(self):
        # End-to-end: an explicit-mode hex hit dispatches through hex_hit
        # (mech.combat.c:1800-1802) with the firing weapon's index and
        # damage.
        self.lock_hex(12, 7, 'H')
        with mock.patch.object(combat, 'hex_hit') as hh:
            result = fire_weapon_number(self.engine, self.att, 0,
                                        to_hit_roll=12)
        self.assertTrue(result.hit)
        weapon_idx = self.att.weapons[0].weapon_idx
        hh.assert_called_once_with(self.att, 12, 7, weapon_idx, 0, 5, 1)

    def test_miss_still_fires_ignite_machinery(self):
        # possibly_ignite_or_clear(..., intentional=0) on a hex-shot MISS
        # (mech.combat.c:1339-1351); hex_hit itself is not reached.
        self.att.base_to_hit = 4        # BTH 4+4-4 = 4 > roll 2
        self.lock_hex(12, 7, 'H')
        with mock.patch.object(combat, 'possibly_ignite_or_clear') as pic, \
                mock.patch.object(combat, 'hex_hit') as hh:
            result = fire_weapon_number(self.engine, self.att, 0,
                                        to_hit_roll=2)
        self.assertFalse(result.hit)
        weapon_idx = self.att.weapons[0].weapon_idx
        pic.assert_called_once_with(self.att, weapon_idx, 0, 5, 12, 7, 0)
        hh.assert_not_called()
        # A missing shot was still a shot: recycle + FIRED
        self.assertTrue(self.att.has_status(MechStatus.FIRED))
        self.assertGreater(self.att.weapons[0].recycle, 0)


# =============================================================================
# Firing-message flavor (hex_target_id, mech.combat.c:1814-1826)
# =============================================================================

class TestHexTargetId(HexFireFixture):

    def test_flavor_strings_verbatim(self):
        cases = [
            (MechStatus.LOCK_HEX_IGN, "at the hex, trying to ignite it"),
            (MechStatus.LOCK_HEX_CLR, "at the hex, trying to clear it"),
            (MechStatus.LOCK_HEX, "at the hex"),
            (MechStatus.LOCK_BUILDING, "at the building at"),
        ]
        for mode, expected in cases:
            self.att.clear_status(MechStatus.LOCK_MODES)
            self.att.set_status(mode)
            self.assertEqual(hex_target_id(self.att), expected)
        self.att.clear_status(MechStatus.LOCK_MODES)
        self.assertEqual(hex_target_id(self.att), "at")

    def test_fired_message_carries_flavor(self):
        self.lock_hex(12, 7, 'I')
        result = fire_weapon_number(self.engine, self.att, 0,
                                    to_hit_roll=12)
        self.assertIn(
            "You fire MediumLaser at the hex, trying to ignite it (12,7)!",
            result.messages)


if __name__ == '__main__':
    unittest.main()
