"""
Unit tests for the spotter layer (systems/spot.py, port of mech.spot.c):
the spot command (mech.spot.c:106-188), the EVENT_SPOT_CHECK watchdog
(mech.spot.c:38-62), the FireSpot hand-off (mech.combat.c:514-523,
417-419; mech.spot.c:190-292) and the indirect-fire BTH terms
(mech.bth.c:78-86, 301-307, 369-373).

Mech-to-mech LOS reads the hand-filled losinfo cache; dice are pinned with
explicit roll kwargs.
"""

import sys
import unittest

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.events import EventType
from core.game_loop import GameEngine
from data.templates import get_template, create_mech_from_template
from entities.map import GameMap, LIGHT_FOREST
from entities.mech import MechStatus, UnitType
from entities.weapon import get_weapon_by_index
from systems.combat import calculate_bth, fire_weapon_number
from systems.los import (
    MECHLOSFLAG_SEEC2, MECHLOSFLAG_SEEN, MECHLOSFLAG_SEESP,
)
from systems.piloting import DEFAULT_SPOTTING, find_pilot_spotting
from systems.spot import mech_spot
from systems.targeting import set_target, set_target_hex

SEES = MECHLOSFLAG_SEEN | MECHLOSFLAG_SEESP | MECHLOSFLAG_SEEC2

NON_IDF_CHIRP = ("The weapon system chirps: 'Somone is spotting for you. "
                 "Remove your spotter to fire non-IDF weapons'")


def total_armor(mech) -> int:
    return sum(s.armor + s.rear for s in mech.sections)


class SpotFixture(unittest.TestCase):
    """att: AssaultMech (weapon 3 = IS.LRM-10, IDF; weapon 0 = PPC) at
    (10,20); spt: TestMech spotter at (10,10); tgt: TestMech at (10,7).
    All same team."""

    def setUp(self):
        self.engine = GameEngine()
        self.map = GameMap(30, 30)
        self.map._id = 100
        self.engine.register_entity(self.map)
        self.map.mapvis = 30
        self.map.maplight = 2
        self.map.maxvis = 60
        self.map.losinfo = {}
        self.att = create_mech_from_template(get_template("AssaultMech"),
                                             name="Alpha")
        self.spt = create_mech_from_template(get_template("TestMech"),
                                             name="Sierra")
        self.tgt = create_mech_from_template(get_template("TestMech"),
                                             name="Tango")
        self.att.set_hex_position(10, 20)
        self.att.facing = 0
        self.spt.set_hex_position(10, 10)
        self.tgt.set_hex_position(10, 7)
        for m in (self.att, self.spt, self.tgt):
            m.set_status(MechStatus.STARTED)
            self.map.add_mech(m)
            self.engine.register_entity(m)
        self.LRM, self.PPC = 3, 0

    def see(self, looker, target, flag=SEES):
        self.map.losinfo[(looker._id, target._id)] = flag

    def make_spotter(self):
        ok, msg = mech_spot(self.engine, self.spt, self.spt)
        self.assertTrue(ok, msg)

    def link(self):
        """Full spotter setup: spt self-spots, att links to spt."""
        self.make_spotter()
        self.see(self.att, self.spt)
        ok, msg = mech_spot(self.engine, self.att, self.spt)
        self.assertTrue(ok, msg)

    def spot_lock(self, target=None):
        """The spotter locks a mech (default tgt)."""
        target = target if target is not None else self.tgt
        self.see(self.spt, target)
        ok, msg = set_target(self.engine, self.spt, target)
        self.assertTrue(ok, msg)


# =============================================================================
# The spot command (mech.spot.c:106-188)
# =============================================================================

class TestMechSpotCommand(SpotFixture):

    def test_self_arg_sets_spotter(self):
        ok, msg = mech_spot(self.engine, self.spt, self.spt)
        self.assertTrue(ok)
        self.assertEqual(msg, "You are now set as a spotter.")
        self.assertEqual(self.spt.spotter, self.spt._id)

    def test_self_arg_blocked_while_recycling(self):
        # MechFullNoRecycle gate (mech.spot.c:143)
        ws = self.spt.weapons[0]
        self.spt.sections[ws.section].criticals[ws.critical].data = 4
        ok, msg = mech_spot(self.engine, self.spt, self.spt)
        self.assertFalse(ok)
        self.assertEqual(msg, "You have weapons recycling!")
        self.assertEqual(self.spt.spotter, -1)

    def test_dash_clears_own_spotting_and_fire_adjustments(self):
        # '-' as a spotter: "You spot no longer." + ClearFireAdjustments
        # (mech.spot.c:132-136, 90-104)
        self.make_spotter()
        self.att.spotter = self.spt._id
        self.att.fire_adjustment = 3
        ok, msg = mech_spot(self.engine, self.spt, '-')
        self.assertTrue(ok)
        self.assertEqual(msg, "You spot no longer.")
        self.assertEqual(self.spt.spotter, -1)
        self.assertEqual(self.att.fire_adjustment, 0)

    def test_dash_drops_datalink(self):
        self.link()
        ok, msg = mech_spot(self.engine, self.att, '-')
        self.assertTrue(ok)
        self.assertEqual(msg, "You disable the datalink to spotter.")
        self.assertEqual(self.att.spotter, -1)

    def test_enemy_target_is_hidden(self):
        # Team gate shares the not-found text (mech.spot.c:153-155)
        self.make_spotter()
        self.spt.team = self.att.team + 1
        self.see(self.att, self.spt)
        ok, msg = mech_spot(self.engine, self.att, self.spt)
        self.assertFalse(ok)
        self.assertEqual(msg, "That target does not exist!")

    def test_mw_cannot_spot_and_cannot_be_spotter(self):
        # (mech.spot.c:126-127, 157-158)
        self.att.unit_type = UnitType.MW
        ok, msg = mech_spot(self.engine, self.att, self.spt)
        self.assertEqual(
            msg, "Spot ? You ? What with, your pretty blue eyes ? Hah!")
        self.att.unit_type = UnitType.MECH
        self.make_spotter()
        self.spt.unit_type = UnitType.MW
        self.see(self.att, self.spt)
        ok, msg = mech_spot(self.engine, self.att, self.spt)
        self.assertEqual(
            msg, "Spot ? That puny being ?! What with, those clear brown "
                 "eyes ? Hah!")

    def test_target_must_be_set_up_as_spotter(self):
        # (mech.spot.c:159-160)
        self.see(self.att, self.spt)
        ok, msg = mech_spot(self.engine, self.att, self.spt)
        self.assertFalse(ok)
        self.assertEqual(msg, "That 'mech is not set up as spotter!")

    def test_los_gate(self):
        # (mech.spot.c:183) - no losinfo entry = no LOS
        self.make_spotter()
        ok, msg = mech_spot(self.engine, self.att, self.spt)
        self.assertFalse(ok)
        self.assertEqual(msg, "You do not have LOS to that target!")

    def test_link_success(self):
        self.make_spotter()
        self.see(self.att, self.spt)
        self.att.fire_adjustment = 5
        ok, msg = mech_spot(self.engine, self.att, self.spt)
        self.assertTrue(ok)
        self.assertEqual(msg, f"Sierra [{self.spt.contact_id.lower()}] set as spotter.")
        self.assertEqual(self.att.spotter, self.spt._id)
        self.assertEqual(self.att.fire_adjustment, 0)


# =============================================================================
# EVENT_SPOT_CHECK watchdog (mech.spot.c:38-62)
# =============================================================================

class TestSpotCheckEvent(SpotFixture):

    def link(self):
        # Only a completed artillery handshake arms the C watchdog. The
        # callback tests seed that event; ordinary link tests stay above.
        super().link()
        from systems.spot import spot_check_event
        self.engine.schedule_event(10, EventType.SPOT_CHECK, spot_check_event,
                                   data=self.att, data2=(self.engine,self.spt))

    def run_check(self, ticks=10):
        for _ in range(ticks):
            self.engine.process_tick()

    def test_healthy_link_rearms(self):
        self.link()
        self.assertTrue(self.engine.has_event(EventType.SPOT_CHECK,
                                              self.att))
        self.run_check()
        # Still linked, watchdog re-armed (mech.spot.c:61)
        self.assertEqual(self.att.spotter, self.spt._id)
        self.assertTrue(self.engine.has_event(EventType.SPOT_CHECK,
                                              self.att))

    def test_drop_when_spotter_stops_spotting(self):
        # MechSpotter(spotter) == -1 clause (mech.spot.c:55)
        self.link()
        self.spt.spotter = -1
        self.run_check()
        self.assertEqual(self.att.spotter, -1)
        self.assertFalse(self.engine.has_event(EventType.SPOT_CHECK,
                                               self.att))

    def test_drop_when_spotter_on_different_map(self):
        # spotter->mapindex != mech->mapindex clause (mech.spot.c:56)
        self.link()
        self.map.remove_mech(self.spt)
        other = GameMap(30, 30)
        other.add_mech(self.spt)
        self.run_check()
        self.assertEqual(self.att.spotter, -1)
        self.assertFalse(self.engine.has_event(EventType.SPOT_CHECK,
                                               self.att))

    def test_silent_stop_when_link_already_cleared(self):
        # MechSpotter(mech) == -1 early-out (mech.spot.c:46-47): no re-arm
        self.link()
        self.att.spotter = -1
        self.run_check()
        self.assertFalse(self.engine.has_event(EventType.SPOT_CHECK,
                                               self.att))


# =============================================================================
# FireSpot hand-off (mech.combat.c:514-523, 417-419)
# =============================================================================

class TestFireSpotHandoff(SpotFixture):

    def test_idf_with_spotter_attacks_spotters_locked_mech(self):
        # No attacker LOS to Tango, no attacker lock: the LRM still fires
        # through the spotter (mech.combat.c:514-519, mech.spot.c:221-253).
        self.link()
        self.spot_lock()
        armor_before = total_armor(self.tgt)
        result = fire_weapon_number(self.engine, self.att, self.LRM,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertLess(total_armor(self.tgt), armor_before)
        self.assertTrue(self.att.has_status(MechStatus.FIRED))

    def test_non_idf_with_spotter_refuses(self):
        # (mech.combat.c:521-523; both typos verbatim)
        self.link()
        self.spot_lock()
        result = fire_weapon_number(self.engine, self.att, self.PPC,
                                    to_hit_roll=12)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages, [NON_IDF_CHIRP])

    def test_self_spotter_cannot_fire_at_all(self):
        # (mech.combat.c:417-419)
        self.make_spotter()
        result = fire_weapon_number(self.engine, self.spt, 0)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages, ["You cannot fire while spotting."])

    def test_missing_spotter_object(self):
        # getMech failure text, typo verbatim (mech.spot.c:210)
        self.link()
        self.spot_lock()
        self.att.spotter = 999999999            # dangling dbref
        result = fire_weapon_number(self.engine, self.att, self.LRM)
        self.assertEqual(result.messages,
                         ["There is no spotter avilable to IDF with!"])

    def test_spotter_no_longer_spotting_resets_link(self):
        # (mech.spot.c:212-216)
        self.link()
        self.spot_lock()
        self.spt.spotter = -1
        result = fire_weapon_number(self.engine, self.att, self.LRM)
        self.assertEqual(result.messages, ["You do not have a spotter!"])
        self.assertEqual(self.att.spotter, -1)

    def test_unconscious_and_blinded_spotter(self):
        # (mech.spot.c:217-218)
        self.link()
        self.spot_lock()
        self.spt.set_status(MechStatus.UNCONSCIOUS)
        result = fire_weapon_number(self.engine, self.att, self.LRM)
        self.assertEqual(result.messages, ["Your spotter is unconscious!"])
        self.spt.clear_status(MechStatus.UNCONSCIOUS)
        self.spt.set_status(MechStatus.BLINDED)
        result = fire_weapon_number(self.engine, self.att, self.LRM)
        self.assertEqual(result.messages,
                         ["Your spotter can't see a thing!"])

    def test_spotter_lost_los_to_its_target(self):
        # Typo verbatim (mech.spot.c:228)
        self.link()
        self.spot_lock()
        self.see(self.spt, self.tgt, 0)         # cache goes dark
        result = fire_weapon_number(self.engine, self.att, self.LRM)
        self.assertEqual(result.messages,
                         ["You spotter does not have a target in LOS!"])

    def test_spotter_without_any_target(self):
        # (mech.spot.c:254-257)
        self.link()
        result = fire_weapon_number(self.engine, self.att, self.LRM)
        self.assertEqual(result.messages,
                         ["Your spotter has no target set!"])

    def test_spotter_hex_lock_probes_the_hex(self):
        # Spotter locked a hex containing Tango: find_mech_in_hex on the
        # SPOTTER's coordinates engages Tango (mech.spot.c:258-268).  The
        # hex-found mech makes the spotter's LOS check a mech check, which
        # reads the cached SEES bits (mech.spot.c:279).
        self.link()
        self.see(self.spt, self.tgt)
        ok, msg = set_target_hex(self.engine, self.spt, 10, 7)
        self.assertTrue(ok, msg)
        armor_before = total_armor(self.tgt)
        result = fire_weapon_number(self.engine, self.att, self.LRM,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit, result.messages)
        self.assertLess(total_armor(self.tgt), armor_before)

    def test_spotter_empty_hex_is_a_hex_impact(self):
        # Empty spotted hex: target None, no HexBonus (the FIRER holds no
        # hex-lock bit; mech.bth.c:292-295 reads the firer's status).
        self.link()
        ok, msg = set_target_hex(self.engine, self.spt, 12, 7)
        self.assertTrue(ok, msg)
        result = fire_weapon_number(self.engine, self.att, self.LRM,
                                    to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit, result.messages)
        self.assertEqual(result.bth_breakdown.hex_mod, 0)


# =============================================================================
# Indirect-fire BTH terms (mech.bth.c:78-86, 301-307, 369-373)
# =============================================================================

class TestSpotBTH(SpotFixture):

    def spotted_shot(self):
        result = fire_weapon_number(self.engine, self.att, self.LRM,
                                    to_hit_roll=12, location_roll=7)
        self.assertIsNotNone(result.bth_breakdown, result.messages)
        return result.bth_breakdown

    def test_unpiloted_spotter_skill_term(self):
        # BTHADD("Spotting", FindPilotSpotting(spotter) - 4)
        # (mech.bth.c:78-86); unpiloted spotter -> DEFAULT_SPOTTING = 8
        # (btconfig.h:181) -> +4.
        self.assertEqual(find_pilot_spotting(self.spt), DEFAULT_SPOTTING)
        self.link()
        self.spot_lock()
        b = self.spotted_shot()
        self.assertEqual(b.spotting_mod, DEFAULT_SPOTTING - 4)

    def test_idf_terrain_carries_spotter_side_terrain(self):
        # spotTerrain = 1 + AddTerrainMod(spotter, target, ...) + spotter
        # movement + locking penalty (mech.spot.c:232-241); light woods on
        # the target adds 1 -> IDFTerrain = 2 (mech.bth.c:301-303).
        self.map.set_terrain(self.tgt.x, self.tgt.y, LIGHT_FOREST)
        self.link()
        self.spot_lock()
        b = self.spotted_shot()
        self.assertEqual(b.idf_terrain_mod, 2)

    def test_attacker_terrain_mod_suppressed_when_indirect(self):
        # mech.bth.c:369-373: AddTerrainMod(mech, ...) only runs when
        # indirectFire >= 1000.  The attacker sees the wooded target too,
        # yet contributes no terrain term of its own.
        self.map.set_terrain(self.tgt.x, self.tgt.y, LIGHT_FOREST)
        self.see(self.att, self.tgt)
        self.link()
        self.spot_lock()
        b = self.spotted_shot()
        self.assertEqual(b.terrain_mod, 0)
        self.assertEqual(b.idf_terrain_mod, 2)

    def test_no_unstable_lock_when_spotted(self):
        # mech.bth.c:270: the unstable-lock disjunction requires !spotter;
        # the attacker has no lock at all yet takes no hip-shot term.
        self.link()
        self.spot_lock()
        b = self.spotted_shot()
        self.assertEqual(b.unstable_lock_mod, 0)

    def test_self_spotting_plus_one(self):
        # BTHADD("Spotting", 1) while the firer is its own spotter
        # (mech.bth.c:305-307) - asserted on calculate_bth directly since
        # a self-spotter cannot reach the fire path (mech.combat.c:417-419).
        weapon = get_weapon_by_index(self.att.weapons[self.PPC].weapon_idx)
        base = calculate_bth(self.att, self.tgt, weapon, 5.0)
        self.att.spotter = self.att._id
        spotting = calculate_bth(self.att, self.tgt, weapon, 5.0)
        self.assertEqual(spotting.spotting_mod, 1)
        self.assertEqual(spotting.total, base.total + 1)


if __name__ == '__main__':
    unittest.main()
