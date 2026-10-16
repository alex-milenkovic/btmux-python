"""
Tests for the event system.

Run with: python -m pytest tests/test_events.py -v
Or just:  python tests/test_events.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.events import Event, EventQueue, EventType


def test_event_creation():
    """Test basic event creation."""
    def dummy_callback(e):
        pass

    event = Event(
        tick=10,
        event_id=1,
        event_type=EventType.MOVE,
        callback=dummy_callback,
        data="test_data",
    )

    assert event.tick == 10
    assert event.event_id == 1
    assert event.event_type == EventType.MOVE
    assert event.data == "test_data"
    assert not event.zombie
    print("Event creation test passed")


def test_event_ordering():
    """Test that events are ordered by tick."""
    def dummy(e):
        pass

    e1 = Event(tick=10, event_id=1, event_type=EventType.MOVE, callback=dummy)
    e2 = Event(tick=5, event_id=2, event_type=EventType.MOVE, callback=dummy)
    e3 = Event(tick=15, event_id=3, event_type=EventType.MOVE, callback=dummy)

    events = sorted([e1, e2, e3])
    assert events[0].tick == 5
    assert events[1].tick == 10
    assert events[2].tick == 15
    print("Event ordering test passed")


def test_queue_schedule_and_run():
    """Test scheduling and running events."""
    queue = EventQueue()
    results = []

    def callback1(e):
        results.append(("cb1", e.tick, e.data))

    def callback2(e):
        results.append(("cb2", e.tick, e.data))

    # Schedule events
    queue.schedule(2, EventType.MOVE, callback1, data="first")
    queue.schedule(1, EventType.MOVE, callback2, data="second")

    assert queue.pending_count == 2

    # Tick 1: second event should fire
    queue.advance_tick()
    ran = queue.run_events()
    assert ran == 1
    assert results == [("cb2", 1, "second")]

    # Tick 2: first event should fire
    queue.advance_tick()
    ran = queue.run_events()
    assert ran == 1
    assert results == [("cb2", 1, "second"), ("cb1", 2, "first")]

    assert queue.pending_count == 0
    print("Schedule and run test passed")


def test_queue_cancel_event():
    """Test canceling individual events."""
    queue = EventQueue()
    results = []

    def callback(e):
        results.append(e.data)

    e1 = queue.schedule(1, EventType.MOVE, callback, data="keep")
    e2 = queue.schedule(1, EventType.MOVE, callback, data="cancel")

    # Cancel the second event
    queue.cancel_event(e2)

    queue.advance_tick()
    queue.run_events()

    assert results == ["keep"]
    print("Cancel event test passed")


def test_queue_cancel_by_type():
    """Test canceling all events of a type."""
    queue = EventQueue()
    results = []

    def callback(e):
        results.append(e.data)

    queue.schedule(1, EventType.MOVE, callback, data="move1")
    queue.schedule(1, EventType.MOVE, callback, data="move2")
    queue.schedule(1, EventType.HEAT, callback, data="heat1")

    # Cancel all MOVE events
    canceled = queue.cancel_by_type(EventType.MOVE)
    assert canceled == 2

    queue.advance_tick()
    queue.run_events()

    # Only heat event should have run
    assert results == ["heat1"]
    print("Cancel by type test passed")


def test_queue_cancel_by_data():
    """Test canceling all events with specific data."""
    queue = EventQueue()
    results = []

    def callback(e):
        results.append((e.event_type.name, e.data))

    mech1 = {"name": "mech1"}
    mech2 = {"name": "mech2"}

    queue.schedule(1, EventType.MOVE, callback, data=mech1)
    queue.schedule(1, EventType.HEAT, callback, data=mech1)
    queue.schedule(1, EventType.MOVE, callback, data=mech2)

    # Cancel all events for mech1
    canceled = queue.cancel_by_data(mech1)
    assert canceled == 2

    queue.advance_tick()
    queue.run_events()

    # Only mech2's event should have run
    assert len(results) == 1
    assert results[0][1] == mech2
    print("Cancel by data test passed")


def test_queue_count_type():
    """Test counting events by type."""
    queue = EventQueue()

    def dummy(e):
        pass

    queue.schedule(1, EventType.MOVE, dummy)
    queue.schedule(2, EventType.MOVE, dummy)
    queue.schedule(1, EventType.HEAT, dummy)

    assert queue.count_type(EventType.MOVE) == 2
    assert queue.count_type(EventType.HEAT) == 1
    assert queue.count_type(EventType.JUMP) == 0
    print("Count type test passed")


def test_queue_has_event_type_data():
    """Test checking for event existence."""
    queue = EventQueue()

    def dummy(e):
        pass

    mech = {"name": "test_mech"}

    # No events yet
    assert not queue.has_event_type_data(EventType.MOVE, mech)

    # Add event
    queue.schedule(1, EventType.MOVE, dummy, data=mech)
    assert queue.has_event_type_data(EventType.MOVE, mech)
    assert not queue.has_event_type_data(EventType.HEAT, mech)

    # Run event
    queue.advance_tick()
    queue.run_events()
    assert not queue.has_event_type_data(EventType.MOVE, mech)
    print("Has event type data test passed")


def test_queue_time_until():
    """Test getting time until an event fires."""
    queue = EventQueue()

    def dummy(e):
        pass

    mech = {"name": "test_mech"}

    # No events
    assert queue.time_until_type_data(EventType.MOVE, mech) is None

    # Schedule event for tick 5
    queue.schedule(5, EventType.MOVE, dummy, data=mech)
    assert queue.time_until_type_data(EventType.MOVE, mech) == 5

    # Advance 2 ticks
    queue.advance_tick()
    queue.advance_tick()
    assert queue.time_until_type_data(EventType.MOVE, mech) == 3
    print("Time until test passed")


def test_queue_run_by_type():
    """Test running all events of a type immediately."""
    queue = EventQueue()
    results = []

    def callback(e):
        results.append(e.data)

    # Schedule for future ticks
    queue.schedule(10, EventType.MOVE, callback, data="move1")
    queue.schedule(20, EventType.MOVE, callback, data="move2")
    queue.schedule(10, EventType.HEAT, callback, data="heat1")

    # Run all MOVE events immediately
    ran = queue.run_by_type(EventType.MOVE)
    assert ran == 2
    assert "move1" in results
    assert "move2" in results
    assert "heat1" not in results

    # MOVE events should be zombified
    assert queue.count_type(EventType.MOVE) == 0
    assert queue.count_type(EventType.HEAT) == 1
    print("Run by type test passed")


def test_queue_multiple_events_same_tick():
    """Test multiple events scheduled for the same tick."""
    queue = EventQueue()
    results = []

    def callback(e):
        results.append(e.data)

    # All at tick 1
    queue.schedule(1, EventType.MOVE, callback, data="a")
    queue.schedule(1, EventType.MOVE, callback, data="b")
    queue.schedule(1, EventType.MOVE, callback, data="c")

    queue.advance_tick()
    ran = queue.run_events()

    assert ran == 3
    assert set(results) == {"a", "b", "c"}
    print("Multiple events same tick test passed")


def test_queue_event_schedules_new_event():
    """Test that an event callback can schedule new events."""
    queue = EventQueue()
    results = []

    def rescheduling_callback(e):
        results.append(e.data)
        if e.data < 3:
            queue.schedule(1, EventType.MOVE, rescheduling_callback, data=e.data + 1)

    queue.schedule(1, EventType.MOVE, rescheduling_callback, data=1)

    # Run 3 ticks
    for _ in range(3):
        queue.advance_tick()
        queue.run_events()

    assert results == [1, 2, 3]
    print("Event scheduling new events test passed")


def test_queue_zombie_cleanup():
    """Test that zombies are properly skipped and can be purged."""
    queue = EventQueue()

    def dummy(e):
        pass

    # Schedule many events
    events = [queue.schedule(10, EventType.MOVE, dummy) for _ in range(100)]

    # Cancel half of them
    for e in events[:50]:
        e.cancel()

    assert queue.pending_count == 50

    # Purge should remove zombies from heap
    removed = queue.purge_zombies()
    assert removed == 50
    print("Zombie cleanup test passed")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_event_creation,
        test_event_ordering,
        test_queue_schedule_and_run,
        test_queue_cancel_event,
        test_queue_cancel_by_type,
        test_queue_cancel_by_data,
        test_queue_count_type,
        test_queue_has_event_type_data,
        test_queue_time_until,
        test_queue_run_by_type,
        test_queue_multiple_events_same_tick,
        test_queue_event_schedules_new_event,
        test_queue_zombie_cleanup,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\n--- {test.__name__} ---")
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
