"""Live event visibility, empty source hooks and independent heartbeat source."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.events import EventQueue, EventType, prerun_event, postrun_event, very_fake_func
from core.game_loop import GameEngine


class EventLifecycleTest(unittest.TestCase):
    def test_empty_hooks_leave_event_and_history_unchanged(self):
        queue = EventQueue()
        event = queue.schedule(1, EventType.MOVE, lambda e: None)
        before = vars(event).copy()
        for hook in (prerun_event, postrun_event, very_fake_func):
            hook(event)
        self.assertEqual(before, vars(event))
        self.assertEqual([0] * 100, queue.history)

    def test_due_and_type_execution_wrap_live_callback_once(self):
        for method in ('due', 'type'):
            with self.subTest(method=method):
                queue, trace = EventQueue(), []
                queue.observe_execution = lambda phase, event: trace.append(phase)
                def callback(event):
                    trace.append('callback')
                    self.assertEqual(1, queue.count_type(EventType.UNSTUN_CREW))
                    self.assertTrue(queue.has_event_type_data(EventType.UNSTUN_CREW, self))
                queue.schedule(1, EventType.UNSTUN_CREW, callback, self)
                if method == 'due':
                    queue.muxevent_run()
                else:
                    queue.run_by_type(EventType.UNSTUN_CREW)
                self.assertEqual(['pre', 'callback', 'post'], trace)
                self.assertEqual(0, queue.count_type(EventType.UNSTUN_CREW))
                self.assertEqual([0] * 100, queue.history)

    def test_cancelled_events_never_call_hooks(self):
        queue = EventQueue()
        queue.observe_execution = lambda *args: self.fail('zombie hook')
        queue.schedule(1, EventType.STARTUP, lambda e: self.fail('zombie callback')).cancel()
        self.assertEqual(0, queue.run_by_type(EventType.STARTUP))
        self.assertEqual(0, queue.muxevent_run())

    def test_history_sort_includes_all_hundred_zero_slots(self):
        queue = EventQueue()
        queue.history[:3] = [2, 2, 1]
        rows = queue.history_rows()
        self.assertEqual([2, 0, 1], [row['type'] for row in rows])
        self.assertEqual([20, 40, 40], [row['percent'] for row in rows])
        self.assertIn('20.000%', queue.debug_event_types('history')[1])
        queue.initialize_history()
        self.assertEqual(['Event history (by use)'], queue.debug_event_types('history'))

    def test_pending_source_ids_and_cancelled_counts(self):
        queue = EventQueue()
        queue.schedule(7, EventType.STARTUP, lambda e: None)
        queue.schedule(4, EventType.FALL, lambda e: None)
        queue.schedule(3, EventType.FALL, lambda e: None).cancel()
        rows = queue.pending_rows()
        self.assertEqual([(3, 'Startup', 1), (16, 'Fall', 1)],
                         [(row['type'], row['name'], row['count']) for row in rows])
        self.assertEqual('2 total', queue.debug_event_types('')[-1])
        queue.cancel_by_type(EventType.FALL)
        queue.cancel_by_type(EventType.STARTUP)
        self.assertEqual('0 total', queue.debug_event_types('')[-1])

    def test_callback_rearms_and_old_event_remains_until_return(self):
        queue, observed = EventQueue(), []
        def callback(event):
            queue.schedule(2, EventType.RECOVERY, lambda e: observed.append('new'), self)
            observed.append(queue.count_type(EventType.RECOVERY))
        queue.schedule(1, EventType.RECOVERY, callback, self)
        queue.muxevent_run()
        self.assertEqual([2], observed)
        self.assertEqual(1, queue.count_type(EventType.RECOVERY))
        queue.muxevent_run()
        queue.muxevent_run()
        self.assertEqual([2, 'new'], observed)


class HeartbeatSourceTest(unittest.TestCase):
    def test_idempotent_timer_start_stop_and_no_catchup(self):
        engine = GameEngine()
        engine.heartbeat_stop()
        engine.heartbeat_stop()
        self.assertEqual(0, engine.heartbeat_timer_count)
        engine.heartbeat_init()
        engine.heartbeat_init()
        self.assertEqual((1, 1), (engine.heartbeat_timer_count, engine.heartbeat_deadline))
        engine.skip_seconds(50)
        engine.heartbeat()
        self.assertEqual((1, 51, 1, 0), (engine.heartbeat_timer_count, engine.heartbeat_deadline,
                                      engine.global_tick, engine.muxevent_tick))

    def test_key_order_rearm_before_dispatch_and_unsigned_tick(self):
        engine = GameEngine()
        later = SimpleNamespace(xcode_type='MECH', _id=20)
        earlier = SimpleNamespace(xcode_type='MECH', _id=3)
        engine.register_entity(later)
        engine.register_entity(earlier)
        seen = []
        engine.global_tick = 0xffffffff
        engine.sim_now = 9
        with patch('core.game_loop.mech_heartbeat', side_effect=lambda e, u: seen.append((u._id, e.heartbeat_deadline))):
            engine.heartbeat()
        self.assertEqual([(3, 10), (20, 10)], seen)
        self.assertEqual(0, engine.global_tick)

    def test_auto_missing_mech_is_skipped_and_services_are_explicit(self):
        engine = GameEngine()
        auto = SimpleNamespace(xcode_type='AUTO', _id=1, mymech=None, weaplist=None)
        engine.register_entity(auto)
        engine.heartbeat()
        self.assertFalse(getattr(auto, 'external_effects', []))
        auto.mymech = SimpleNamespace()
        engine.heartbeat()
        self.assertEqual(3, len(auto.external_effects))
        self.assertTrue(all(effect['applied'] is False for effect in auto.external_effects))

    def test_auto_available_adapters_preserve_sensor_profile_gun_order(self):
        engine, calls = GameEngine(), []
        auto = SimpleNamespace(xcode_type='AUTO', _id=1, mymech=object(), weaplist=object())
        engine.auto_services = {name: lambda obj, name=name: calls.append(name)
                                for name in ('sensor', 'profile', 'gun')}
        engine.register_entity(auto)
        engine.heartbeat()
        self.assertEqual(['sensor', 'profile', 'gun'], calls)
        calls.clear()
        engine.heartbeat()
        self.assertEqual(['sensor', 'gun'], calls)


class HistoryPrecisionTest(unittest.TestCase):
    def test_percent_rounds_multiply_before_division_as_source_float(self):
        queue = EventQueue()
        queue.history[0],queue.history[1] = 16777217,123456789
        self.assertEqual(11.963728904724121,queue.history_rows()[0]['percent'])


if __name__ == '__main__':
    unittest.main()
