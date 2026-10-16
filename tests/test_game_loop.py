"""
Tests for the game loop and engine.

Run with: python -m pytest tests/test_game_loop.py -v
Or just:  python tests/test_game_loop.py
"""

import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.game_loop import GameEngine, EngineState, MECHEVENT, HEAT_TICK, MOVE_TICK
from core.events import EventType, Event


def test_engine_creation():
    """Test basic engine creation."""
    engine = GameEngine()

    assert engine.tick == 0
    assert engine.state == EngineState.STOPPED
    assert engine.tick_duration == 1.0
    print("Engine creation test passed")


def test_engine_process_tick():
    """Test processing a single tick."""
    engine = GameEngine()
    results = []

    def callback(e):
        results.append(("event", e.data))

    engine.schedule_event(1, EventType.MOVE, callback, data="test")

    # Process tick
    events_run, periodics_run = engine.process_tick()

    assert engine.tick == 1
    assert events_run == 1
    assert results == [("event", "test")]
    print("Process tick test passed")


def test_engine_periodic_updates():
    """Test periodic update system."""
    engine = GameEngine()
    results = []

    def heat_update(eng):
        results.append(("heat", eng.tick))

    def move_update(eng):
        results.append(("move", eng.tick))

    # Register periodics
    engine.register_periodic("heat", 2, heat_update)  # Every 2 ticks
    engine.register_periodic("move", 1, move_update)  # Every tick

    # Run 4 ticks
    for _ in range(4):
        engine.process_tick()

    # Move should run every tick (4 times)
    move_runs = [r for r in results if r[0] == "move"]
    assert len(move_runs) == 4

    # Heat should run every 2 ticks (2 times)
    heat_runs = [r for r in results if r[0] == "heat"]
    assert len(heat_runs) == 2

    print("Periodic updates test passed")


def test_engine_entity_management():
    """Test entity registration and event cancellation."""
    engine = GameEngine()
    results = []

    def callback(e):
        results.append(e.data)

    # Create mock entities
    mech1 = {"name": "mech1"}
    mech2 = {"name": "mech2"}

    engine.register_entity(mech1)
    engine.register_entity(mech2)

    assert len(engine.get_entities()) == 2

    # Schedule events for both
    engine.schedule_event(1, EventType.MOVE, callback, data=mech1)
    engine.schedule_event(1, EventType.HEAT, callback, data=mech1)
    engine.schedule_event(1, EventType.MOVE, callback, data=mech2)

    # Unregister mech1 - should cancel its events
    engine.unregister_entity(mech1)

    assert len(engine.get_entities()) == 1

    # Run tick
    engine.process_tick()

    # Only mech2's event should have run
    assert len(results) == 1
    assert results[0] == mech2
    print("Entity management test passed")


def test_engine_has_event():
    """Test checking for pending events."""
    engine = GameEngine()

    def dummy(e):
        pass

    mech = {"name": "test"}

    assert not engine.has_event(EventType.MOVE, mech)

    engine.schedule_event(5, EventType.MOVE, dummy, data=mech)
    assert engine.has_event(EventType.MOVE, mech)
    assert not engine.has_event(EventType.HEAT, mech)
    print("Has event test passed")


def test_engine_event_time_remaining():
    """Test getting time remaining until event."""
    engine = GameEngine()

    def dummy(e):
        pass

    mech = {"name": "test"}

    # No event
    assert engine.event_time_remaining(EventType.MOVE, mech) is None

    # Schedule event
    engine.schedule_event(10, EventType.MOVE, dummy, data=mech)
    assert engine.event_time_remaining(EventType.MOVE, mech) == 10

    # Run 3 ticks
    engine.run_ticks(3)
    assert engine.event_time_remaining(EventType.MOVE, mech) == 7
    print("Event time remaining test passed")


def test_engine_on_tick_callback():
    """Test tick callbacks."""
    engine = GameEngine()
    ticks_seen = []

    def tick_callback(tick):
        ticks_seen.append(tick)

    engine.on_tick(tick_callback)

    engine.run_ticks(5)

    assert ticks_seen == [1, 2, 3, 4, 5]
    print("On tick callback test passed")


def test_engine_cancel_events():
    """Test various event cancellation methods."""
    engine = GameEngine()
    results = []

    def callback(e):
        results.append((e.event_type.name, e.data))

    mech = {"name": "test"}

    # Schedule multiple events
    engine.schedule_event(1, EventType.MOVE, callback, data=mech)
    engine.schedule_event(1, EventType.HEAT, callback, data=mech)
    engine.schedule_event(1, EventType.JUMP, callback, data=mech)

    # Cancel by type
    canceled = engine.cancel_events_of_type(EventType.MOVE)
    assert canceled == 1

    # Cancel for entity
    engine.schedule_event(1, EventType.STAND, callback, data=mech)
    canceled = engine.cancel_events_for(mech)
    # Should have canceled HEAT, JUMP, and STAND
    assert canceled == 3

    engine.process_tick()
    assert results == []  # All canceled
    print("Cancel events test passed")


def test_engine_run_ticks():
    """Test running multiple ticks without delay."""
    engine = GameEngine()

    initial_tick = engine.tick
    engine.run_ticks(100)

    assert engine.tick == initial_tick + 100
    print("Run ticks test passed")


def test_engine_stats():
    """Test engine statistics."""
    engine = GameEngine()

    def dummy(e):
        pass

    # Schedule some events
    engine.schedule_event(1, EventType.MOVE, dummy)
    engine.schedule_event(2, EventType.MOVE, dummy)

    engine.run_ticks(5)

    stats = engine.get_stats()
    assert stats["tick"] == 5
    assert stats["total_ticks"] == 5
    assert stats["total_events_run"] == 2
    assert stats["pending_events"] == 0
    assert stats["state"] == "STOPPED"
    print("Stats test passed")


def test_mechevent_macro():
    """Test MECHEVENT convenience function."""
    engine = GameEngine()
    results = []

    def move_callback(e):
        results.append(("moved", e.data["name"]))

    mech = {"name": "Atlas"}

    event = MECHEVENT(engine, mech, EventType.MOVE, move_callback, 1)

    assert event.data == mech
    assert event.event_type == EventType.MOVE

    engine.process_tick()

    assert results == [("moved", "Atlas")]
    print("MECHEVENT macro test passed")


def test_engine_periodic_disable():
    """Test disabling periodic updates."""
    engine = GameEngine()
    results = []

    def update(eng):
        results.append(eng.tick)

    periodic = engine.register_periodic("test", 1, update)

    # Run 2 ticks - should run
    engine.run_ticks(2)
    assert len(results) == 2

    # Disable and run 2 more
    periodic.enabled = False
    engine.run_ticks(2)
    assert len(results) == 2  # No new runs

    # Re-enable
    periodic.enabled = True
    engine.run_ticks(2)
    assert len(results) == 4
    print("Periodic disable test passed")


def test_engine_unregister_periodic():
    """Test removing periodic updates."""
    engine = GameEngine()
    results = []

    def update(eng):
        results.append(eng.tick)

    engine.register_periodic("test", 1, update)

    engine.run_ticks(2)
    assert len(results) == 2

    # Remove the periodic
    removed = engine.unregister_periodic("test")
    assert removed

    engine.run_ticks(2)
    assert len(results) == 2  # No new runs

    # Try to remove again
    removed = engine.unregister_periodic("test")
    assert not removed
    print("Unregister periodic test passed")


def test_engine_async_run():
    """Test async run for a limited number of ticks."""
    engine = GameEngine(tick_duration=0.01)  # Fast for testing
    results = []

    def callback(e):
        results.append(e.tick)

    engine.schedule_event(1, EventType.MOVE, callback)
    engine.schedule_event(2, EventType.MOVE, callback)
    engine.schedule_event(3, EventType.MOVE, callback)

    # Run asynchronously for 5 ticks
    asyncio.run(engine.run(max_ticks=5))

    assert engine.tick == 5
    assert results == [1, 2, 3]
    print("Async run test passed")


def test_engine_event_chains():
    """Test events that schedule follow-up events."""
    engine = GameEngine()
    positions = []

    class MockMech:
        def __init__(self):
            self.x = 0

    mech = MockMech()

    def move_event(e):
        mech.x += 1
        positions.append(mech.x)
        if mech.x < 5:
            # Schedule next move
            engine.schedule_event(1, EventType.MOVE, move_event, data=mech)

    # Start the chain
    engine.schedule_event(1, EventType.MOVE, move_event, data=mech)

    # Run enough ticks
    engine.run_ticks(10)

    assert positions == [1, 2, 3, 4, 5]
    assert mech.x == 5
    print("Event chains test passed")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_engine_creation,
        test_engine_process_tick,
        test_engine_periodic_updates,
        test_engine_entity_management,
        test_engine_has_event,
        test_engine_event_time_remaining,
        test_engine_on_tick_callback,
        test_engine_cancel_events,
        test_engine_run_ticks,
        test_engine_stats,
        test_mechevent_macro,
        test_engine_periodic_disable,
        test_engine_unregister_periodic,
        test_engine_async_run,
        test_engine_event_chains,
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
