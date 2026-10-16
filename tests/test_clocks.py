"""
Tests for the three-clock architecture (core clock behavior).

Clock 1 - dispatch: timer.c:135 dispatch() -> glue.c:911-937
    UpdateSpecialObjects(): catch-up loop clamped at 20 (glue.c:925-927),
    frozen-now modulo gate for the object sweep (glue.c:898-909),
    muxevent_run per iteration (event.c:209-246).
Clock 2 - heartbeat: tick.c:82-88 heartbeat_run() - no catch-up; walks
    mechs (mech.events.c:27-43) and increments global_tick (tick.c:34,87).
    Weapon/section recycling is slaved to muxevent_tick, not to heartbeat
    invocation count (mech.update.c:1539-1630, btmacros.h:430-432).
Clock 3 - player commands: executed the instant input arrives, between
    ticks (engine.inject_command).

The ported timing constants themselves are pinned in tests/test_constants.py;
this module only asserts the one new clock constant.

NOTE: lag-asymmetry integration tests (movement/combat under skewed clocks)
are added to this file by a later workstream - keep new core-clock tests in
the classes below and add integration classes at the bottom.
"""

import sys
import unittest

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.events import EventType
from core.game_loop import (
    DISPATCH_CATCHUP_CLAMP, HEAT_TICK, GameEngine,
    mech_update, register_special_objects,
)
from entities.mech import Location, Mech, MechStatus, WeaponState


def make_started_mech(name: str = "ClockMech") -> Mech:
    """A started test mech."""
    mech = Mech.create_test_mech(name=name)
    mech.set_status(MechStatus.STARTED)
    return mech


def arm_weapon(mech: Mech, section: int = Location.RARM, critical: int = 0,
               data: int = 30) -> WeaponState:
    """
    Register a recycling weapon on a mech.

    The recycle countdown lives in the weapon's FIRST crit slot .data
    (mech.utils.c:1030-1066 - FindWeapons_Advanced records the first slot of
    each crit run), which is what systems.combat.fire_weapon sets to
    WEAPON_TICK * vrt.
    """
    ws = WeaponState(section=section, critical=critical, weapon_idx=0,
                     recycle=data)
    mech.weapons.append(ws)
    from entities.crittypes import i2weapon
    mech.sections[section].criticals[critical].type = i2weapon(0)
    mech.sections[section].criticals[critical].data = data
    return ws


class TestDispatchCatchup(unittest.TestCase):
    """The dispatch clock's catch-up loop (glue.c:911-937)."""

    def test_first_dispatch_runs_once(self):
        """lastrun == 0 means the very first dispatch runs exactly once."""
        # glue.c:919,923 - static lastrun = 0; times = lastrun ? ... : 1
        engine = GameEngine()
        engine.skip_seconds(5)
        engine.process_tick()
        self.assertEqual(engine.sim_now, 6)
        self.assertEqual(engine.muxevent_tick, 1)

    def test_skip_seconds_alone_does_not_dispatch(self):
        """skip_seconds moves the wall clock only."""
        engine = GameEngine()
        engine.process_tick()
        engine.skip_seconds(5)
        self.assertEqual(engine.muxevent_tick, 1)
        self.assertEqual(engine.sim_now, 6)

    def test_catchup_runs_all_missed_seconds(self):
        """skip_seconds(5) -> next dispatch runs 6 iterations."""
        # glue.c:923 - times = mudstate.now - lastrun
        engine = GameEngine()
        engine.process_tick()                       # sim_now=1, tick=1
        engine.skip_seconds(5)                      # sim_now=6, lagged
        engine.process_tick()                       # sim_now=7, times=6
        self.assertEqual(engine.sim_now, 7)
        self.assertEqual(engine.muxevent_tick, 7)   # advanced 6

    def test_catchup_runs_due_events(self):
        """Events scheduled in the skipped stretch fire during catch-up."""
        engine = GameEngine()
        engine.process_tick()
        fired = []
        engine.schedule_event(3, EventType.MOVE,
                              lambda e: fired.append(engine.muxevent_tick))
        engine.skip_seconds(5)
        engine.process_tick()
        self.assertEqual(fired, [4])                # tick 1 + delay 3

    def test_clamp_at_20(self):
        """A hopeless lag is clamped: muxevent_tick loses the excess."""
        # glue.c:925-927 - if (times > 20) times = 20; /* Machine's
        # hopelessly lagged, we don't want to make it [much] worse */
        engine = GameEngine()
        engine.process_tick()                       # sim_now=1, tick=1
        engine.skip_seconds(30)                     # sim_now=31
        engine.process_tick()                       # times=31 -> clamped 20
        self.assertEqual(engine.sim_now, 32)
        self.assertEqual(engine.muxevent_tick, 21)  # 1 + 20, 11s lost forever
        # And the loss is permanent: the next tick advances by 1 only.
        engine.process_tick()
        self.assertEqual(engine.muxevent_tick, 22)
        self.assertEqual(engine.sim_now, 33)

    def test_clamp_constant(self):
        """Pin the ported clamp value."""
        self.assertEqual(DISPATCH_CATCHUP_CLAMP, 20)  # glue.c:925-927


class TestFrozenNowGate(unittest.TestCase):
    """
    The object sweep's frozen-now oddity (glue.c:898-909): mudstate.now is
    snapshotted once per dispatch, so during an N-iteration catch-up an
    every-2s update runs N times if the frozen second is even, 0 if odd.
    """

    def _engine_with_counter(self):
        engine = GameEngine()
        mech = make_started_mech()
        engine.register_entity(mech)
        calls = []
        engine.register_object_type(
            "MECH", HEAT_TICK, lambda eng, m: calls.append(eng.sim_now))
        return engine, calls

    def test_normal_cadence(self):
        """Without lag, an every-2s update runs on even seconds only."""
        engine, calls = self._engine_with_counter()
        engine.process_tick()                       # sim_now=1, odd
        self.assertEqual(calls, [])
        engine.process_tick()                       # sim_now=2, even
        self.assertEqual(calls, [2])

    def test_catchup_on_even_frozen_second_runs_n_times(self):
        """Catch-up landing on an even second runs the update every iteration."""
        engine, calls = self._engine_with_counter()
        engine.run_ticks(2)                         # sim_now=2, one call
        engine.skip_seconds(3)                      # sim_now=5
        engine.process_tick()                       # sim_now=6 (even), times=4
        self.assertEqual(calls, [2, 6, 6, 6, 6])    # ran 4x at the frozen now

    def test_catchup_on_odd_frozen_second_runs_zero_times(self):
        """Catch-up landing on an odd second skips the update entirely."""
        engine, calls = self._engine_with_counter()
        engine.run_ticks(2)                         # sim_now=2, one call
        engine.skip_seconds(4)                      # sim_now=6
        engine.process_tick()                       # sim_now=7 (odd), times=5
        self.assertEqual(calls, [2])                # 0 runs despite 5 iterations

    def test_unregistered_types_are_skipped(self):
        """Entities without a matching type registration are ignored."""
        engine = GameEngine()
        engine.register_entity({"name": "not-a-mech"})
        calls = []
        engine.register_object_type("MECH", 1, lambda eng, m: calls.append(m))
        engine.run_ticks(3)
        self.assertEqual(calls, [])


class TestMechUpdate(unittest.TestCase):
    """The MECH special-object update (mech.update.c:2968-2992)."""

    def test_wiring_helper_registers_mech_at_heat_tick(self):
        """register_special_objects wires MECH -> mech_update (glue.c:57-58)."""
        engine = GameEngine()
        register_special_objects(engine)
        reg = engine._object_types["MECH"]
        self.assertEqual(reg.update_time, HEAT_TICK)
        self.assertIs(reg.update_fn, mech_update)

    def test_clears_fired_flag(self):
        """MechStatus &= ~FIRED (mech.update.c:2974)."""
        engine = GameEngine()
        register_special_objects(engine)
        mech = make_started_mech()
        mech.set_status(MechStatus.FIRED)
        engine.register_entity(mech)
        engine.run_ticks(2)                         # runs at sim_now=2
        self.assertFalse(mech.has_status(MechStatus.FIRED))

    def test_vis_mod_random_walk_stays_bounded(self):
        """MechVisMod = BOUNDED(0, +Number(-40,40), 100) while started
        (mech.update.c:2983-2985); starts at 0 (calloc, glue.c:945)."""
        engine = GameEngine()
        register_special_objects(engine)
        mech = make_started_mech()
        self.assertEqual(mech.vis_mod, 0)
        engine.register_entity(mech)
        for _ in range(50):
            engine.run_ticks(2)
            self.assertGreaterEqual(mech.vis_mod, 0)
            self.assertLessEqual(mech.vis_mod, 100)

    def test_vis_mod_frozen_for_shutdown_mech(self):
        """The vismod walk is gated on Started (mech.update.c:2983)."""
        engine = GameEngine()
        register_special_objects(engine)
        mech = Mech.create_test_mech()              # not started
        mech.vis_mod = 50
        engine.register_entity(mech)
        engine.run_ticks(10)
        self.assertEqual(mech.vis_mod, 50)


class TestHeartbeatRecycling(unittest.TestCase):
    """
    Weapon recycling through the heartbeat (mech.events.c:27-43,
    btmacros.h:430-432, mech.update.c:1539-1630).
    """

    def setUp(self):
        self.engine = GameEngine()
        self.mech = make_started_mech()
        self.engine.register_entity(self.mech)
        self.ws = arm_weapon(self.mech, data=30)
        self.slot = self.mech.sections[Location.RARM].criticals[0]

    def test_countdown_tracks_muxevent_tick(self):
        """Each aligned heartbeat applies a delta of 1 muxevent_tick."""
        self.engine.run_ticks(5)
        self.assertEqual(self.slot.data, 25)
        self.assertEqual(self.ws.recycle, 25)       # mirror kept in step
        self.assertEqual(self.mech.last_weapon_recycle, 5)

    def test_suppressed_heartbeat_applies_lump_diff(self):
        """A delayed heartbeat applies the full muxevent_tick delta at once:
        recycle is slaved to the dispatch clock, not heartbeat count."""
        self.engine.run_ticks(5)                    # data 25, LWRT 5
        self.engine.heartbeat_enabled = False
        self.engine.run_ticks(10)                   # muxevent_tick -> 15
        self.assertEqual(self.slot.data, 25)        # heartbeat missed: frozen
        self.engine.heartbeat_enabled = True
        self.engine.process_tick()                  # tick 16, diff = 16-5 = 11
        self.assertEqual(self.slot.data, 25 - 11)
        self.assertEqual(self.mech.last_weapon_recycle, 16)

    def test_countdown_expires_to_zero(self):
        """diff >= data zeroes the counter (mech.update.c:1569-1583)."""
        self.slot.data = 3
        self.ws.recycle = 3
        self.engine.run_ticks(5)
        self.assertEqual(self.slot.data, 0)
        self.assertEqual(self.ws.recycle, 0)

    def test_lazy_gate_is_idempotent_per_tick(self):
        """UpdateRecycling runs recycle_weaponry at most once per
        muxevent_tick (btmacros.h:430-432)."""
        self.engine.run_ticks(1)                    # data 29, LWRT 1
        self.engine.heartbeat()                     # same tick: diff < 1
        self.engine.heartbeat()
        self.assertEqual(self.slot.data, 29)

    def test_shutdown_mech_does_not_recycle(self):
        """UpdateRecycling gates on Started && !Destroyed (btmacros.h:431)."""
        self.mech.clear_status(MechStatus.STARTED)
        self.engine.run_ticks(5)
        self.assertEqual(self.slot.data, 30)

    def test_global_tick_lags_muxevent_tick(self):
        """global_tick counts heartbeats only (tick.c:34,87) - suppressing
        the heartbeat makes it fall behind the dispatch clock for good."""
        self.engine.run_ticks(5)
        self.assertEqual(self.engine.global_tick, 5)
        self.engine.heartbeat_enabled = False
        self.engine.run_ticks(10)
        self.engine.heartbeat_enabled = True
        self.engine.run_ticks(1)
        self.assertEqual(self.engine.global_tick, 6)
        self.assertEqual(self.engine.muxevent_tick, 16)
        self.assertLess(self.engine.global_tick, self.engine.muxevent_tick)

    def test_dispatch_alone_never_touches_global_tick(self):
        """Only heartbeat() increments global_tick (tick.c:34,87)."""
        self.engine.heartbeat_enabled = False
        self.engine.run_ticks(7)
        self.engine.dispatch()
        self.assertEqual(self.engine.global_tick, 0)


class TestSectionRecycle(unittest.TestCase):
    """Physical-attack section recycle (mech.update.c:1594-1626)."""

    def setUp(self):
        self.engine = GameEngine()
        self.mech = make_started_mech()
        self.engine.register_entity(self.mech)

    def test_section_recycle_expires_via_heartbeat(self):
        """Section.recycle (set by systems.physical) now counts down."""
        self.mech.sections[Location.LARM].recycle = 5
        self.engine.run_ticks(3)
        self.assertEqual(self.mech.sections[Location.LARM].recycle, 2)
        self.engine.run_ticks(2)
        self.assertEqual(self.mech.sections[Location.LARM].recycle, 0)

    def test_section_recycle_lump_diff(self):
        """Section recycle gets the same muxevent_tick delta treatment."""
        self.mech.sections[Location.RARM].recycle = 10
        self.engine.heartbeat_enabled = False
        self.engine.run_ticks(4)                    # muxevent_tick 4, no beat
        self.assertEqual(self.mech.sections[Location.RARM].recycle, 10)
        self.engine.heartbeat_enabled = True
        self.engine.process_tick()                  # diff = 5 in one lump
        self.assertEqual(self.mech.sections[Location.RARM].recycle, 5)


class TestInjectCommand(unittest.TestCase):
    """Clock 3: player commands run immediately, between ticks."""

    def test_executes_immediately_and_logs(self):
        engine = GameEngine()
        executed = []
        result = engine.inject_command(
            "PilotA", lambda: executed.append(engine.muxevent_tick) or 42,
            "fire ppc")
        self.assertEqual(executed, [0])             # ran before any tick
        self.assertEqual(result, 42)
        self.assertEqual(engine.command_log, [(0, 0, "PilotA", "fire ppc")])

    def test_log_records_tick_and_sequence(self):
        engine = GameEngine()
        engine.inject_command("PilotA", lambda: None, "startup")
        engine.run_ticks(3)
        engine.inject_command("PilotB", lambda: None, "turn 90")
        self.assertEqual(engine.command_log, [
            (0, 0, "PilotA", "startup"),
            (3, 1, "PilotB", "turn 90"),
        ])


# =============================================================================
# B8: lag-asymmetry integration tests
#
# The classes above pin the clamp / frozen-now / lump-diff mechanics at unit
# level; these run them through the FULL stack - wire_standard_systems, real
# template mechs, event-driven movement (physics.movement.start_move_event)
# and the fire pipeline (systems.combat.fire_weapon) - and show how lag hits
# movement (dispatch clock events) and weapon recycle (heartbeat clock,
# slaved to muxevent_tick) together.
# =============================================================================

from core.game_loop import wire_standard_systems
from data.templates import create_mech_from_template, get_template
from entities.weapon import get_weapon_by_index
from physics.movement import start_move_event
from systems.combat import WEAPON_TICK, fire_weapon


def build_battle_engine():
    """
    A fully wired engine with a moving mech and a mech that just fired.

    Runner (TestMech) is ordered to 40 KPH at tick 0 via an injected command
    that arms its per-mech MOVE event chain; Gunner (AssaultMech) fires its
    medium laser (weapon 1, vrt 20 -> recycle WEAPON_TICK * 20 = 40 s) as a
    deterministic miss - the recycle countdown starts either way
    (mech.combat.c:1353-1354) and a miss adds no damage randomness.

    Returns:
        (engine, runner, gunner, slot) - slot is the fired weapon's first
        crit slot; its data byte is the recycle countdown (mech.h:599-608).
    """
    engine = GameEngine()
    wire_standard_systems(engine)

    runner = create_mech_from_template(get_template("TestMech"), name="Runner")
    runner.set_status(MechStatus.STARTED)
    runner.set_hex_position(50, 50)
    runner.facing = 0
    runner.desired_facing = 0

    gunner = create_mech_from_template(get_template("AssaultMech"), name="Gunner")
    gunner.set_status(MechStatus.STARTED)
    gunner.set_hex_position(50, 55)
    gunner.facing = 0

    # The source move callback stops its chain when the unit has no map.
    from entities.map import GameMap
    board = GameMap(100, 100)
    board._id = 1000
    engine.register_entity(board)
    board.add_mech(runner)
    board.add_mech(gunner)
    engine.register_entity(runner)
    engine.register_entity(gunner)

    # Clock 3: both orders arrive before the first tick.
    engine.inject_command(
        "Runner",
        lambda: (runner.set_desired_speed(40.0),
                 start_move_event(engine, runner)),
        "move 40")
    engine.inject_command(
        "Gunner",
        lambda: fire_weapon(gunner, runner, 1, 5.0,
                            to_hit_roll=2, location_roll=7),
        "fire 1")

    ws = gunner.weapons[1]
    slot = gunner.sections[ws.section].criticals[ws.critical]
    return engine, runner, gunner, slot


# Recycle set by the fire above: WEAPON_TICK * vrt (mech.combat.c:1353-1354)
def _fired_recycle(gunner) -> int:
    return WEAPON_TICK * get_weapon_by_index(gunner.weapons[1].weapon_idx).vrt


class TestLagCatchupWithinClamp(unittest.TestCase):
    """
    Lag within the clamp: skip_seconds(5) -> the next dispatch runs 6
    catch-up iterations (glue.c:923) and NOTHING is lost - movement events
    fire per iteration and the delayed heartbeat applies the muxevent_tick
    delta in one lump (mech.update.c:1549).
    """

    def test_movement_and_recycle_both_catch_up_fully(self):
        lagged, l_runner, l_gunner, l_slot = build_battle_engine()
        control, c_runner, c_gunner, c_slot = build_battle_engine()
        start_fy = l_runner.fy

        lagged.run_ticks(4)
        lagged.skip_seconds(5)      # server stalls for 5 s
        lagged.process_tick()       # times = 10 - 4 = 6 (glue.c:923)
        control.run_ticks(10)       # unlagged twin: 10 clean seconds

        # muxevent_tick advanced all 6 missed seconds in one dispatch
        self.assertEqual(lagged.muxevent_tick, 10)
        self.assertEqual(lagged.muxevent_tick, control.muxevent_tick)

        # The runner moved, and its position is EXACTLY the uninterrupted
        # 10-second position: the MOVE event chain ran once per catch-up
        # iteration (event.c:209-246).
        self.assertNotEqual(l_runner.fy, start_fy)
        self.assertEqual((l_runner.fx, l_runner.fy),
                         (c_runner.fx, c_runner.fy))
        self.assertEqual((l_runner.x, l_runner.y), (c_runner.x, c_runner.y))
        self.assertEqual(l_runner.speed, c_runner.speed)

        # Recycle caught up too: the first post-lag heartbeat applied
        # diff = muxevent_tick - MechLWRT = 6 in one lump.
        recycle = _fired_recycle(l_gunner)
        self.assertEqual(l_slot.data, recycle - 10)
        self.assertEqual(l_slot.data, c_slot.data)


class TestLagLossThroughClamp(unittest.TestCase):
    """
    Lag beyond the clamp: skip_seconds(30) -> only 20 catch-up iterations
    run (glue.c:925-927 - "Machine's hopelessly lagged").  The clamp is the
    ONE loss mechanism, and it hits movement and recycle IDENTICALLY,
    because both are slaved to muxevent_tick, which itself fell behind.
    """

    def test_movement_and_recycle_lose_the_same_seconds(self):
        lagged, l_runner, l_gunner, l_slot = build_battle_engine()
        control, c_runner, c_gunner, c_slot = build_battle_engine()

        lagged.process_tick()       # sim_now=1, tick=1
        lagged.skip_seconds(30)     # sim_now=31
        lagged.process_tick()       # times = 32-1 = 31 -> clamped to 20

        # 31 wall-clock seconds elapsed but the sim ran only 21 of them.
        self.assertEqual(lagged.sim_now, 32)
        self.assertEqual(lagged.muxevent_tick, 21)
        lost = 32 - 1 - 20  # = 11 seconds, gone forever (glue.c:925-927)

        # The lagged world is EXACTLY a clean 21-second world - internally
        # consistent, just behind the wall clock...
        control.run_ticks(21)
        self.assertEqual((l_runner.fx, l_runner.fy),
                         (c_runner.fx, c_runner.fy))
        self.assertEqual(l_slot.data, c_slot.data)
        recycle = _fired_recycle(l_gunner)
        self.assertEqual(l_slot.data, recycle - 21)

        # ...and vs a server that kept up (32 clean seconds), BOTH systems
        # are short the same `lost` seconds through the clamp.
        wall, w_runner, w_gunner, w_slot = build_battle_engine()
        wall.run_ticks(32)
        self.assertEqual(w_slot.data, recycle - 32)
        self.assertEqual(l_slot.data - w_slot.data, lost)   # recycle lost 11 s
        self.assertNotEqual((l_runner.fx, l_runner.fy),
                            (w_runner.fx, w_runner.fy))     # movement too


class TestHeartbeatSuppressionDivergence(unittest.TestCase):
    """
    Heartbeat suppressed while dispatch runs: the two 1 Hz clocks visibly
    diverge (tick.c has no catch-up, tick.c:82-88), but recycle survives
    because recycle_weaponry is slaved to muxevent_tick and applies the
    full delta on the next heartbeat (mech.update.c:1549).
    """

    def test_recycle_lands_correct_and_clocks_diverge(self):
        engine, runner, gunner, slot = build_battle_engine()
        recycle = _fired_recycle(gunner)

        engine.run_ticks(3)
        self.assertEqual(slot.data, recycle - 3)
        self.assertEqual(engine.global_tick, 3)

        # Heartbeat clock stops for k=7 seconds; dispatch keeps running.
        pos_before = (runner.fx, runner.fy)
        engine.heartbeat_enabled = False
        engine.run_ticks(7)
        self.assertEqual(engine.muxevent_tick, 10)
        self.assertEqual(engine.global_tick, 3)          # no beats counted
        self.assertEqual(slot.data, recycle - 3)         # countdown frozen
        # Movement is a dispatch-clock event chain - unaffected.
        self.assertNotEqual((runner.fx, runner.fy), pos_before)

        # One heartbeat after re-enabling: diff = 11 - 3 = 8 in one lump,
        # landing the countdown exactly where an unsuppressed run would be.
        engine.heartbeat_enabled = True
        engine.process_tick()
        self.assertEqual(slot.data, recycle - 11)

        # global_tick lags muxevent_tick by exactly k - the clocks have
        # diverged for good (tick.c:34,87).
        self.assertEqual(engine.global_tick, 4)
        self.assertEqual(engine.muxevent_tick, 11)
        self.assertEqual(engine.muxevent_tick - engine.global_tick, 7)


if __name__ == "__main__":
    unittest.main()
