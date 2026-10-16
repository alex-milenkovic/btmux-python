"""
Tests for systems/targeting.py — the lock layer (mech.combat.c settarget,
mech.sensor.c sensor command, mech.events.c PLOS/lock events).

losinfo is hand-filled (dict keyed (looker._id, target._id)) — these tests
do not depend on the LOS update wave.
"""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.events import EventType
from core.game_loop import GameEngine
from entities.map import GameMap
from entities.mech import Mech, MechStatus, Specials
from systems.los import (
    MECHLOSFLAG_SEEN, MECHLOSFLAG_SEEC2, MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS,
)
from systems.targeting import (
    INITIAL_PLOS_TICK, PLOS_TICK, SCHANGE_TICK,
    clear_target, fa_mech_range, fl_mech_range, list_contacts, lock_event,
    locking, lose_lock, plos_event, set_sensors, set_target, set_target_hex,
    sixth_sense_check, start_plos_event, stop_lock,
)

SEES_P = MECHLOSFLAG_SEESP | MECHLOSFLAG_SEEC2
SEES_S = MECHLOSFLAG_SEESS | MECHLOSFLAG_SEEC2


def _row(row, name, default=None):
    return row.get(name, default) if isinstance(row, dict) else \
        getattr(row, name, default)


def pick_free_sensor_letters(mech, count=2):
    """Letters of non-default sensors this mech may switch to."""
    from systems.sensors import sensors
    from systems.targeting import can_change_to
    picks = []
    for idx, row in enumerate(sensors):
        if idx == 0:
            continue
        if not can_change_to(mech, idx)[0]:
            continue
        picks.append((idx, _row(row, 'matchletter')[0]))
        if len(picks) == count:
            break
    return picks


class TargetingFixture(unittest.TestCase):
    """Engine + map + two started mechs, hand-filled losinfo."""

    def setUp(self):
        self.engine = GameEngine()
        self.map = GameMap(60, 60)
        self.map._id = 1000
        self.engine.register_entity(self.map)
        self.a = Mech.create_test_mech(name="Alpha")
        self.b = Mech.create_test_mech(name="Bravo")
        self.a.set_hex_position(50, 50)
        self.b.set_hex_position(50, 53)
        for m in (self.a, self.b):
            self.map.add_mech(m)
            self.engine.register_entity(m)
            m.set_status(MechStatus.STARTED)
        self.map.losinfo = {}

    def see(self, looker, target, flag):
        self.map.losinfo[(looker._id, target._id)] = flag


class TestRangeMacros(TargetingFixture):

    def test_fa_mech_range_vertical(self):
        # Same column, 3 hexes apart, same elevation -> exactly 3.0 hexes
        self.assertAlmostEqual(fa_mech_range(self.a, self.b), 3.0, places=5)

    def test_fl_mech_range_ignores_map(self):
        # FlMechRange (btmacros.h:655) is FaMechRange; the map arg is unused
        self.assertEqual(fl_mech_range(None, self.a, self.b),
                         fa_mech_range(self.a, self.b))


class TestSetTarget(TargetingFixture):

    def test_fails_without_sees_bits(self):
        self.a.targ_x = 7
        ok, msg = set_target(self.engine, self.a, self.b)
        self.assertFalse(ok)
        self.assertEqual(msg, "That is not a valid targetID. Try again.")
        # No state change
        self.assertEqual(self.a.target, -1)
        self.assertEqual(self.a.targ_x, 7)
        self.assertFalse(self.a.has_status(MechStatus.LOCK_TARGET))

    def test_fails_with_none_target(self):
        ok, msg = set_target(self.engine, self.a, None)
        self.assertFalse(ok)
        self.assertEqual(msg, "That is not a valid targetID. Try again.")

    def test_success_sets_lock_state(self):
        self.see(self.a, self.b, SEES_P)
        ok, msg = set_target(self.engine, self.a, self.b)
        self.assertTrue(ok)
        self.assertEqual(msg, "Target set to Bravo [].")
        self.assertEqual(self.a.target, self.b._id)
        self.assertTrue(self.a.has_status(MechStatus.LOCK_TARGET))

    def test_success_with_secondary_only(self):
        self.see(self.a, self.b, SEES_S)
        ok, _ = set_target(self.engine, self.a, self.b)
        self.assertTrue(ok)
        self.assertEqual(self.a.target, self.b._id)

    def test_success_clears_other_lock_modes(self):
        self.a.set_status(MechStatus.LOCK_HEX)
        self.see(self.a, self.b, SEES_P)
        set_target(self.engine, self.a, self.b)
        self.assertFalse(self.a.has_status(MechStatus.LOCK_HEX))
        self.assertTrue(self.a.has_status(MechStatus.LOCK_TARGET))

    def test_success_leaves_targ_xy_alone(self):
        # C oddity: the mech-lock case never touches TargX/TargY
        # (mech.combat.c:230-240)
        self.a.targ_x = 12
        self.a.targ_y = 34
        self.see(self.a, self.b, SEES_P)
        set_target(self.engine, self.a, self.b)
        self.assertEqual(self.a.targ_x, 12)
        self.assertEqual(self.a.targ_y, 34)


class TestHexLock(TargetingFixture):

    def test_hex_lock_state(self):
        self.map.set_elevation(20, 21, 2)
        self.a.target = self.b._id
        ok, msg = set_target_hex(self.engine, self.a, 20, 21)
        self.assertTrue(ok)
        self.assertEqual(msg, "Target coordinates set at (X,Y) 20, 21")
        self.assertEqual(self.a.target, -1)
        self.assertEqual(self.a.targ_x, 20)
        self.assertEqual(self.a.targ_y, 21)
        self.assertEqual(self.a.targ_z, 2)
        # argc==2 case sets LOCK_TARGET, not LOCK_HEX (mech.combat.c:264)
        self.assertTrue(self.a.has_status(MechStatus.LOCK_TARGET))

    def test_hex_lock_mode_h(self):
        self.a.set_status(MechStatus.LOCK_TARGET)
        ok, msg = set_target_hex(self.engine, self.a, 20, 21, mode='h')
        self.assertTrue(ok)
        self.assertEqual(msg, "Target coordinates set to hex at (X,Y) 20, 21")
        self.assertTrue(self.a.has_status(MechStatus.LOCK_HEX))
        self.assertFalse(self.a.has_status(MechStatus.LOCK_TARGET))

    def test_hex_lock_modes_b_i_c(self):
        for letter, status in (('B', MechStatus.LOCK_BUILDING),
                               ('I', MechStatus.LOCK_HEX_IGN),
                               ('C', MechStatus.LOCK_HEX_CLR)):
            ok, _ = set_target_hex(self.engine, self.a, 20, 21, mode=letter)
            self.assertTrue(ok)
            self.assertTrue(self.a.has_status(status), letter)

    def test_invalid_mode_letter(self):
        ok, msg = set_target_hex(self.engine, self.a, 20, 21, mode='Z')
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid mode selected!")

    def test_invalid_mode_length(self):
        ok, msg = set_target_hex(self.engine, self.a, 20, 21, mode='HH')
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid lock mode!")

    def test_illegal_coordinates(self):
        self.a.targ_x = 5
        ok, msg = set_target_hex(self.engine, self.a, -1, 21)
        self.assertFalse(ok)
        self.assertEqual(msg, "Illegal coordinates!")
        self.assertEqual(self.a.targ_x, 5)      # untouched
        ok, _ = set_target_hex(self.engine, self.a, 20, 60)
        self.assertFalse(ok)


class TestClearAndLoseLock(TargetingFixture):

    def _lock(self):
        self.see(self.a, self.b, SEES_P)
        set_target(self.engine, self.a, self.b)

    def test_clear_target(self):
        self._lock()
        ok, msg = clear_target(self.a, self.engine)
        self.assertTrue(ok)
        self.assertEqual(msg, "All locks cleared.")
        self.assertEqual(self.a.target, -1)
        self.assertEqual(self.a.targ_x, -1)
        self.assertEqual(self.a.targ_y, -1)
        self.assertFalse(self.a.has_status(MechStatus.LOCK_MODES))

    def test_clear_target_cancels_settling_event(self):
        self.engine.lock_tick = 8
        self._lock()
        self.assertTrue(locking(self.engine, self.a))
        clear_target(self.a, self.engine)
        self.assertFalse(locking(self.engine, self.a))

    def test_lose_lock(self):
        self._lock()
        self.a.set_status(MechStatus.LOCK_HEX)
        lose_lock(self.a)
        self.assertEqual(self.a.target, -1)
        self.assertEqual(self.a.targ_x, -1)
        self.assertEqual(self.a.targ_y, -1)
        # StopLock inside LoseLock clears ALL lock-mode bits (btmacros.h:493,500)
        self.assertFalse(self.a.has_status(MechStatus.LOCK_MODES))

    def test_lose_lock_cancels_settling_event(self):
        self.engine.lock_tick = 8
        self._lock()
        lose_lock(self.a, self.engine)
        self.assertFalse(locking(self.engine, self.a))


class TestLockSettling(TargetingFixture):

    def test_instant_default_no_event(self):
        # engine.lock_tick absent -> getattr default 0 -> no EVENT_LOCK
        self.see(self.a, self.b, SEES_P)
        ok, _ = set_target(self.engine, self.a, self.b)
        self.assertTrue(ok)
        self.assertFalse(locking(self.engine, self.a))
        self.assertFalse(self.engine.has_event(EventType.LOCK, self.a))
        # ... and the lock itself is already live
        self.assertEqual(self.a.target, self.b._id)

    def test_settling_mode_queues_event(self):
        self.engine.lock_tick = 8
        self.see(self.a, self.b, SEES_P)
        set_target(self.engine, self.a, self.b)
        self.assertTrue(locking(self.engine, self.a))
        self.engine.run_ticks(7)
        self.assertTrue(locking(self.engine, self.a))
        self.engine.run_ticks(1)                # fires on the 8th second
        self.assertFalse(locking(self.engine, self.a))
        self.assertEqual(self.a.target, self.b._id)

    def test_settling_mode_hex_lock(self):
        self.engine.lock_tick = 8
        set_target_hex(self.engine, self.a, 20, 21)
        self.assertTrue(locking(self.engine, self.a))
        self.engine.run_ticks(8)
        self.assertFalse(locking(self.engine, self.a))

    def test_lock_event_body_runs_without_target(self):
        # mech_lock_event with no lock at all: no crash, no state change
        self.a.target = -1
        self.a.targ_x = -1
        self.a.targ_y = -1
        lock_event(SimpleNamespace(data=self.a, data2=self.engine))


class TestSixthSense(TargetingFixture):

    def test_no_ability_is_noop(self):
        with patch('systems.combat.roll_2d6') as roll:
            sixth_sense_check(self.a, self.b)
            roll.assert_not_called()

    def test_destroyed_target_is_noop(self):
        self.b.specials |= Specials.SS_ABILITY
        self.b.set_status(MechStatus.DESTROYED)
        with patch('systems.combat.roll_2d6') as roll:
            sixth_sense_check(self.a, self.b)
            roll.assert_not_called()

    def test_roll_gate_reached_with_ability(self):
        self.b.specials |= Specials.SS_ABILITY
        with patch('systems.combat.roll_2d6', return_value=9) as roll:
            sixth_sense_check(self.a, self.b)
            roll.assert_called_once()


class TestSetSensors(TargetingFixture):

    def setUp(self):
        super().setUp()
        picks = pick_free_sensor_letters(self.a, 2)
        self.assertGreaterEqual(len(picks), 2, "sensor table too small")
        (self.idx1, self.l1), (self.idx2, self.l2) = picks

    def test_invalid_letters(self):
        ok, msg = set_sensors(self.engine, self.a, "~ ~")
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid arguments!")
        self.assertFalse(self.engine.has_event(EventType.SCHANGE, self.a))

    def test_too_many_args(self):
        ok, msg = set_sensors(self.engine, self.a, "V I E")
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid number of arguments!")

    def test_show_path_no_change(self):
        before = list(self.a.sensor)
        ok, _ = set_sensors(self.engine, self.a, "")
        self.assertTrue(ok)
        self.assertEqual(self.a.sensor, before)
        self.assertFalse(self.engine.has_event(EventType.SCHANGE, self.a))

    def test_change_is_delayed_by_schange_tick(self):
        ok, _ = set_sensors(self.engine, self.a,
                            "%s %s" % (self.l1, self.l2))
        self.assertTrue(ok)
        self.assertTrue(self.engine.has_event(EventType.SCHANGE, self.a))
        self.engine.run_ticks(SCHANGE_TICK - 1)
        self.assertEqual(self.a.sensor, [0, 0])    # not yet applied
        self.engine.run_ticks(1)
        self.assertEqual(self.a.sensor[0], self.idx1)
        self.assertEqual(self.a.sensor[1], self.idx2)

    def test_change_wipes_lock_but_not_status(self):
        self.see(self.a, self.b, SEES_P)
        set_target(self.engine, self.a, self.b)
        set_sensors(self.engine, self.a, "%s %s" % (self.l1, self.l2))
        self.engine.run_ticks(SCHANGE_TICK)
        # mech.sensor.c:694 clears ONLY MechTarget: LOCK_TARGET status and
        # targ_x/y are left alone (C oddity, kept)
        self.assertEqual(self.a.target, -1)
        self.assertTrue(self.a.has_status(MechStatus.LOCK_TARGET))

    def test_same_pair_schedules_nothing(self):
        from systems.sensors import sensors
        cur = _row(sensors[0], 'matchletter')[0]
        ok, _ = set_sensors(self.engine, self.a, "%s %s" % (cur, cur))
        self.assertTrue(ok)
        self.assertFalse(self.engine.has_event(EventType.SCHANGE, self.a))

    def test_not_started_is_silent_success(self):
        self.a.clear_status(MechStatus.STARTED)
        ok, _ = set_sensors(self.engine, self.a,
                            "%s %s" % (self.l1, self.l2))
        self.assertTrue(ok)                     # set_sensor returns 0 (C)
        self.assertFalse(self.engine.has_event(EventType.SCHANGE, self.a))

    def test_shutdown_before_apply_discards_change(self):
        set_sensors(self.engine, self.a, "%s %s" % (self.l1, self.l2))
        self.a.clear_status(MechStatus.STARTED)
        self.engine.run_ticks(SCHANGE_TICK)
        self.assertEqual(self.a.sensor, [0, 0])

    def test_rerequest_replaces_pending_change(self):
        # StopSensorChange before MECHEVENT (mech.sensor.c:793-795):
        # only one pending EVENT_SCHANGE
        set_sensors(self.engine, self.a, "%s %s" % (self.l1, self.l1))
        set_sensors(self.engine, self.a, "%s %s" % (self.l2, self.l2))
        self.engine.run_ticks(SCHANGE_TICK)
        self.assertEqual(self.a.sensor, [self.idx2, self.idx2])


class TestPlosEvent(TargetingFixture):

    def setUp(self):
        super().setUp()
        self.c = Mech.create_test_mech(name="Charlie")
        self.c.set_hex_position(52, 50)
        self.c.set_status(MechStatus.STARTED)
        self.map.add_mech(self.c)
        self.engine.register_entity(self.c)

    def _fire(self):
        plos_event(SimpleNamespace(data=self.a, data2=self.engine))

    def test_start_plos_event_duplicate_guard(self):
        start_plos_event(self.engine, self.a)
        start_plos_event(self.engine, self.a)
        self.assertEqual(self.engine.events.count_data(self.a), 1)

    def test_sweep_calls_only_not_seen_and_writes_back(self):
        self.a.pnum_seen = 1
        self.see(self.a, self.b, MECHLOSFLAG_SEEN)     # already SEEN: skipped
        returned = MECHLOSFLAG_SEEN | SEES_P
        mock = MagicMock(return_value=returned)
        with patch('systems.sensors.sensor_do_we_see_now', mock, create=True):
            self._fire()
        mock.assert_called_once()
        args = mock.call_args[0]
        self.assertIs(args[0], self.a)
        self.assertIs(args[5], self.c)
        self.assertEqual(args[1], 0)                   # prior flag
        self.assertEqual((args[3], args[4]), (-1, -1))
        self.assertEqual((args[9], args[10]), (1, 0))  # seeanew, paranoia
        # writeback landed in losinfo
        self.assertEqual(self.map.losinfo[(self.a._id, self.c._id)], returned)
        # pnum_seen: zeroed, then ++ once for the one not-SEEN unit
        self.assertEqual(self.a.pnum_seen, 1)

    def test_early_out_when_pnum_zero_still_rearms(self):
        self.a.pnum_seen = 0
        mock = MagicMock()
        with patch('systems.sensors.sensor_do_we_see_now', mock, create=True):
            self._fire()
        mock.assert_not_called()
        # re-arm happens BEFORE the early-out (mech.events.c:368-370)
        self.assertTrue(self.engine.has_event(EventType.PLOS, self.a))

    def test_no_rearm_when_shut_down(self):
        self.a.clear_status(MechStatus.STARTED)
        self.a.pnum_seen = 1
        mock = MagicMock()
        with patch('systems.sensors.sensor_do_we_see_now', mock, create=True):
            self._fire()
        mock.assert_not_called()
        self.assertFalse(self.engine.has_event(EventType.PLOS, self.a))

    def test_rearms_through_engine_queue(self):
        self.a.pnum_seen = 1
        mock = MagicMock(return_value=0)
        start_plos_event(self.engine, self.a)
        with patch('systems.sensors.sensor_do_we_see_now', mock, create=True):
            self.engine.run_ticks(INITIAL_PLOS_TICK)   # first sweep
            calls = mock.call_count
            self.assertGreater(calls, 0)
            self.a.pnum_seen = 1
            self.engine.run_ticks(PLOS_TICK)           # re-armed sweep
            self.assertGreater(mock.call_count, calls)
        self.assertTrue(self.engine.has_event(EventType.PLOS, self.a))


class TestListContacts(TargetingFixture):

    def setUp(self):
        super().setUp()
        self.c = Mech.create_test_mech(name="Charlie")
        self.c.set_hex_position(52, 50)
        self.c.set_status(MechStatus.STARTED)
        self.map.add_mech(self.c)
        self.engine.register_entity(self.c)

    def test_only_sees_flagged_units(self):
        self.see(self.a, self.b, SEES_P)
        # (a, c) has no SEES bits -> excluded
        contacts = list_contacts(self.a)
        self.assertEqual(len(contacts), 1)
        self.assertIs(contacts[0]['mech'], self.b)

    def test_contact_fields(self):
        self.see(self.a, self.b, SEES_P)
        set_target(self.engine, self.a, self.b)
        contact = list_contacts(self.a)[0]
        self.assertEqual(contact['id'], self.b._id)
        self.assertAlmostEqual(contact['range'], 3.0, places=5)
        self.assertEqual(contact['bearing'], 180)      # due south
        self.assertTrue(contact['sees_primary'])
        self.assertFalse(contact['sees_secondary'])
        self.assertTrue(contact['locked_by_me'])
        self.assertTrue(contact['friend'])             # same default team
        self.assertFalse(contact['destroyed'])
        self.assertTrue(contact['started'])
        self.assertEqual((contact['x'], contact['y']), (50, 53))
        self.assertEqual(contact['sort_range'], contact['range'])

    def test_secondary_only_included(self):
        self.see(self.a, self.c, SEES_S)
        contacts = list_contacts(self.a)
        self.assertEqual(len(contacts), 1)
        self.assertIs(contacts[0]['mech'], self.c)
        self.assertTrue(contacts[0]['sees_secondary'])
        self.assertFalse(contacts[0]['locked_by_me'])

    def test_destroyed_contact_sort_range(self):
        self.see(self.a, self.b, SEES_P)
        self.b.set_status(MechStatus.DESTROYED)
        contact = list_contacts(self.a)[0]
        # rangelist += 10000 for destroyed units (mech.contacts.c:448-450)
        self.assertAlmostEqual(contact['sort_range'],
                               contact['range'] + 10000, places=5)

    def test_empty_without_map(self):
        self.map.remove_mech(self.a)
        self.assertEqual(list_contacts(self.a), [])


class TestAimReset(TargetingFixture):
    """
    MechAim resets whenever the lock does.

    StopLock sets MechAim(a) = NUM_SECTIONS (btmacros.h:494); LoseLock
    repeats the reset with its "Location-specific targeting powers down."
    notify (btmacros.h:500).
    """

    def test_stop_lock_resets_aim(self):
        """Test StopLock resets aim to NUM_SECTIONS (btmacros.h:494)."""
        from entities.mech import NUM_SECTIONS, Location
        self.a.aim = int(Location.RARM)
        stop_lock(self.a, self.engine)
        self.assertEqual(self.a.aim, NUM_SECTIONS)

    def test_lose_lock_resets_aim(self):
        """Test LoseLock resets aim to NUM_SECTIONS (btmacros.h:500)."""
        from entities.mech import NUM_SECTIONS, Location
        self.a.aim = int(Location.CTORSO)
        self.a.target = self.b._id
        lose_lock(self.a, self.engine)
        self.assertEqual(self.a.aim, NUM_SECTIONS)
        self.assertEqual(self.a.target, -1)

    def test_set_target_wipes_previous_aim(self):
        """Test re-locking runs StopLock, wiping a stale aim
        (mech.combat.c:233 StopLock; btmacros.h:494)."""
        from entities.mech import NUM_SECTIONS, Location
        self.see(self.a, self.b, SEES_P)
        self.a.aim = int(Location.LARM)
        ok, _ = set_target(self.engine, self.a, self.b)
        self.assertTrue(ok)
        self.assertEqual(self.a.aim, NUM_SECTIONS)


if __name__ == '__main__':
    unittest.main()
