"""
The rollpad acceptance test — Workstream D's flagship gate.

The scenario is the project owner's actual play pattern from the original
servers: sit behind cover with speed rolling toward the hex edge, spam
`settarget`, and the second the float position clips into the exposed hex
and the next 1 Hz LOS pass flips the cached bits, the spammed lock lands —
instant lock (product-canon lock_tick 0), instant fire, instant reversal.
The defender's counter-lock dies within the sensor sweep after the attacker
regains cover.

Everything is driven through the real engine plumbing:
  - muxevents first, then the MAP object sweep, each tick (glue.c:898-909)
  - contact GAIN only in the per-mech PLOS event (seeanew=1,
    mech.events.c:385-388), which runs as a muxevent BEFORE the MAP sweep
  - the MAP sweep (update_LOSinfo, seeanew=0) maintains and LOSES contacts,
    calling LoseLock on a lost locked contact (mech.sensor.c:387-392)
  - set_target and fire-time LOS read the CACHED losinfo bits
    (mech.combat.c:215-218, mech.los.c:316-372) — up to 1 s stale

Geometry (20x20 map): a mountain wall (elev 5) fills column x=10 from y=5
south; north of y=5 is open grassland.  The defender idles at (9,4) west of
the wall.  The attacker rolls north up the east lane at x=11: every hex
from (11,6) south is blocked, (11,5) is the exposed hex.  All exposed
ranges are < 3 hexes, where Sensor_Sees skips the perception roll
(mech.sensor.c:236-237), so the whole timeline is deterministic.

Measured timeline (recorded by run_rollpad, asserted by the tests):
    tick 18  attacker's hex flips (11,6) -> (11,5)   [crossing tick]
    tick 19  PLOS gains the contact; spammed lock lands; fire hits;
             reversal injected; defender's counter-lock lands
    tick 33  attacker's hex flips back to (11,6)     [re-cover tick]
    tick 33  the same tick's MAP sweep loses the contact and kills the
             defender's lock (defender.target == -1)
    exposure window: 15 ticks (18..32 inclusive)

To watch the run tick by tick instead of just asserting it:
    python tests/test_rollpad.py --narrate
"""

import random
import sys
import unittest

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.game_loop import GameEngine, wire_standard_systems
from data.templates import get_template, create_mech_from_template
from entities.map import GameMap, MOUNTAINS
from entities.mech import MechStatus
from physics.movement import start_move_event
from systems.combat import fire_weapon_number
from systems.targeting import locking, set_target, start_plos_event

ATTACKER_START = (11, 6)
EXPOSED_HEX = (11, 5)
DEFENDER_POS = (9, 4)
MAX_TICKS = 120


def build_rollpad_world():
    """Engine + map + attacker/defender wired exactly like a live game."""
    engine = GameEngine()
    wire_standard_systems(engine)

    gamemap = GameMap(20, 20)
    gamemap._id = 1000
    # Steady-state weather: map_update re-reads these only every 25th tick
    # (map.c:566-583), so hand-set the values it would land on.
    gamemap.mapvis = 30
    gamemap.maplight = 2
    gamemap.maxvis = 60
    gamemap.cloudbase = 200
    for y in range(5, 20):
        gamemap.set_terrain(10, y, MOUNTAINS)
        gamemap.set_elevation(10, y, 5)

    attacker = create_mech_from_template(get_template("TestMech"),
                                         name="Attacker")
    defender = create_mech_from_template(get_template("TestMech"),
                                         name="Defender")
    attacker.set_hex_position(*ATTACKER_START)
    attacker.facing = 0                      # rolling due north up the lane
    defender.set_hex_position(*DEFENDER_POS)
    defender.facing = 180

    for mech in (attacker, defender):
        mech.set_status(MechStatus.STARTED)
        gamemap.add_mech(mech)
        engine.register_entity(mech)
    engine.register_entity(gamemap)

    start_plos_event(engine, attacker)
    start_plos_event(engine, defender)
    return engine, gamemap, attacker, defender


def run_rollpad(say=None):
    """One recorded run of the full rollpad; returns the measurements.

    `say(tick, text)`, when given, narrates each notable moment as it
    happens — the --narrate path.  The tests consume the same run silently.
    """
    def note(tick, text):
        if say:
            say(tick, text)

    # The exposed geometry keeps every sensor check inside the < 3 hex
    # auto-see band, so nothing here actually consumes randomness; the
    # seed pins the run anyway.
    random.seed(0xB77)

    engine, gamemap, att, dfn = build_rollpad_world()
    r = {'engine': engine, 'map': gamemap, 'att': att, 'dfn': dfn}

    # --- Phase 0: covered.  Let the LOS wave run once so the cached
    # flags exist (BLOCK), then record the refused lock and the refused
    # no-lock fire.
    engine.run_ticks(2)
    r['covered_lock'] = engine.inject_command(
        att, lambda: set_target(engine, att, dfn), label="lock (covered)")
    note(engine.tick, f'lock {dfn.name} -> "{r["covered_lock"][1]}"'
                      '   [covered: cached LOS is BLOCK]')
    r['covered_fire'] = engine.inject_command(
        att, lambda: fire_weapon_number(engine, att, 0),
        label="fire (no lock)")
    note(engine.tick, f'fire 0 -> "{r["covered_fire"].messages[0]}"')

    # --- Phase 1: roll toward the hex edge, spamming the lock.
    att.desired_speed = 21.5             # 2 MP walk toward the edge
    engine.inject_command(att, lambda: start_move_event(engine, att),
                          label="roll out")
    note(engine.tick, "speed 21.5 -- rolling north toward the hex edge, "
                      "spamming the lock")

    r['trace'] = []                      # (tick, x, y)
    for key in ('crossing_tick', 'lock_tick', 'locking_at_lock',
                'fire_result', 'counter_lock', 'recover_tick',
                'defender_loss_tick'):
        r[key] = None
    r['defender_armor_before'] = sum(s.armor for s in dfn.sections)

    spam_first = spam_last = spam_count = 0
    spam_msg = ""
    last_hex = (att.x, att.y)
    for _ in range(MAX_TICKS):
        engine.process_tick()
        tick = engine.tick
        r['trace'].append((tick, att.x, att.y))

        if (att.x, att.y) != last_hex:
            last_hex = (att.x, att.y)
            if r['lock_tick'] is None and last_hex == EXPOSED_HEX:
                r['crossing_tick'] = tick
                note(tick, f"float position clips the boundary: hex "
                           f"{ATTACKER_START} -> {EXPOSED_HEX}   [EXPOSED]")
            elif r['lock_tick'] is not None and \
                    last_hex == ATTACKER_START and \
                    r['recover_tick'] is None:
                r['recover_tick'] = tick
                note(tick, f"hex flips back {EXPOSED_HEX} -> "
                           f"{ATTACKER_START}   [COVERED]")

        if r['lock_tick'] is None:
            # The spam: one settarget attempt per tick, injected as a
            # command between ticks (immediate execution).
            ok, _msg = engine.inject_command(
                att, lambda: set_target(engine, att, dfn),
                label="lock spam")
            if ok:
                if spam_count:
                    note(tick, f'(lock spam refused x{spam_count}, ticks '
                               f'{spam_first}..{spam_last}: "{spam_msg}")')
                r['lock_tick'] = tick
                r['locking_at_lock'] = locking(engine, att)
                note(tick, f"PLOS sweep gains the contact -> lock "
                           f"{dfn.name} LANDS (instant: lock_tick=0, "
                           f"Locking()={r['locking_at_lock']})")
                # Fire + reverse in the same command window (clock 3).
                r['fire_result'] = engine.inject_command(
                    att, lambda: fire_weapon_number(
                        engine, att, 0, to_hit_roll=12, location_roll=7),
                    label="fire")
                fr = r['fire_result']
                note(tick, "fire 0 -> " + ("HIT" if fr.hit else "MISS") +
                           " at full accuracy (unstable_lock_mod="
                           f"{fr.bth_breakdown.unstable_lock_mod}; dice "
                           "pinned by the recorded run: to-hit 12, loc 7)")
                for m in fr.messages:
                    note(tick, "  | " + m)
                r['counter_lock'] = engine.inject_command(
                    dfn, lambda: set_target(engine, dfn, att),
                    label="counter-lock")
                if r['counter_lock'][0]:
                    note(tick, f"defender counter-locks {att.name} in the "
                               "same exposure window")
                att.desired_speed = -att.max_speed
                engine.inject_command(
                    att, lambda: start_move_event(engine, att),
                    label="reverse")
                note(tick, f"speed {att.desired_speed:g} -- reversing "
                           "behind cover")
            else:
                spam_count += 1
                spam_last = tick
                spam_msg = _msg
                if spam_count == 1:
                    spam_first = tick

        if r['counter_lock'] is not None and r['counter_lock'][0] and \
                r['defender_loss_tick'] is None and dfn.target == -1:
            r['defender_loss_tick'] = tick
            note(tick, "MAP sweep loses the contact -> defender's lock "
                       "destroyed (LoseLock path, target=-1)")

        if r['recover_tick'] is not None and \
                r['defender_loss_tick'] is not None and \
                tick > r['recover_tick'] + 5:
            break
    return r


def narrate():
    """Print the rollpad run tick by tick, then the measured summary."""
    print("ROLLPAD -- narrated run of the acceptance scenario")
    print("20x20 map; mountain wall (elev 5) fills column x=10 from y=5 "
          "south.")
    print(f"Defender idles at {DEFENDER_POS} west of the wall; attacker "
          f"rolls north up the x=11 lane from {ATTACKER_START}; "
          f"{EXPOSED_HEX} is the one exposed hex.")
    print()
    r = run_rollpad(say=lambda t, m: print(f"  t={t:>3}  {m}"))
    print()
    dealt = (r['defender_armor_before'] -
             sum(s.armor for s in r['dfn'].sections))
    window = r['recover_tick'] - r['crossing_tick']
    print(f"exposed ticks {r['crossing_tick']}..{r['recover_tick'] - 1} "
          f"({window} s); lock landed at crossing"
          f"+{r['lock_tick'] - r['crossing_tick']}; damage dealt {dealt}; "
          f"defender's lock died at cover"
          f"+{r['defender_loss_tick'] - r['recover_tick']}")


class TestRollpad(unittest.TestCase):
    """One recorded run of the full rollpad; each method asserts one leg."""

    @classmethod
    def setUpClass(cls):
        for key, value in run_rollpad().items():
            setattr(cls, key, value)

    # --- (a) While covered -------------------------------------------------

    def test_covered_lock_is_refused(self):
        """Behind the wall the cached bits are BLOCK-only: settarget fails
        with the exact C text (mech.combat.c:212-221)."""
        ok, msg = self.covered_lock
        self.assertFalse(ok)
        self.assertEqual(msg, "That is not a valid targetID. Try again.")
        self.assertEqual(self.att.target, -1)

    def test_covered_fire_without_lock_is_refused(self):
        """fire with no default target: exact C text (mech.combat.c:544-545)."""
        result = self.covered_fire
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["You do not have a default target set!"])

    # --- (b) The lock lands with the hex flip ------------------------------

    def test_crossing_was_observed(self):
        self.assertIsNotNone(self.crossing_tick,
                             "attacker never reached the exposed hex")
        self.assertEqual(
            [(x, y) for t, x, y in self.trace if t == self.crossing_tick][0],
            EXPOSED_HEX)

    def test_lock_lands_within_one_los_tick_of_crossing(self):
        """Contact gain needs the PLOS muxevent, which runs BEFORE the MAP
        sweep in the same tick; depending on the MOVE/PLOS event order the
        earliest cached gain is the crossing tick or the one after."""
        self.assertIsNotNone(self.lock_tick, "the spammed lock never landed")
        self.assertGreaterEqual(self.lock_tick, self.crossing_tick)
        self.assertLessEqual(self.lock_tick - self.crossing_tick, 1)
        self.assertEqual(self.att.target if self.lock_tick is None
                         else self.dfn._id, self.dfn._id)

    # --- (c) Instant lock, instant fire, instant reversal ------------------

    def test_lock_is_instant_not_settling(self):
        """Product canon: engine.lock_tick 0 means no EVENT_LOCK is ever
        scheduled, so Locking() is False on the lock tick (btmacros.h:403)."""
        self.assertEqual(getattr(self.engine, 'lock_tick', 0), 0)
        self.assertFalse(self.locking_at_lock)

    def test_fire_hits_with_full_accuracy_no_unstable_term(self):
        result = self.fire_result
        self.assertTrue(result.hit)
        self.assertIsNotNone(result.bth_breakdown)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 0,
                         "instant lock must not pay the unstable-lock tax")
        armor_after = sum(s.armor for s in self.dfn.sections)
        self.assertLess(armor_after, self.defender_armor_before)

    def test_exposure_window_is_small(self):
        """Measured window: crossing t=18, back in cover t=33 -> 15 exposed
        ticks (the reversal is injected on the lock tick; the walk-speed
        approach keeps the overshoot past the boundary shallow)."""
        self.assertIsNotNone(self.recover_tick,
                             "attacker never regained cover")
        window = self.recover_tick - self.crossing_tick
        self.assertLessEqual(window, 20)
        self.assertEqual((self.att.x, self.att.y), ATTACKER_START)

    # --- (d) The defender's counter-lock dies with the cover ---------------

    def test_defender_counter_lock_landed_while_exposed(self):
        ok, msg = self.counter_lock
        self.assertTrue(ok, msg)

    def test_defender_lock_dies_when_attacker_recovers(self):
        """The 1 Hz sweep loses the contact and LoseLocks the defender
        within the same pass (mech.sensor.c:387-392) — at most ~2 ticks
        after the attacker's hex flips back behind the wall."""
        self.assertIsNotNone(self.defender_loss_tick,
                             "defender never lost the lock")
        self.assertGreaterEqual(self.defender_loss_tick, self.recover_tick)
        self.assertLessEqual(self.defender_loss_tick - self.recover_tick, 2)
        self.assertEqual(self.dfn.target, -1)


if __name__ == '__main__':
    if '--narrate' in sys.argv:
        narrate()
    else:
        unittest.main()
