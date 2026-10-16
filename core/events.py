# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btpr/event.c
#   btech/mech.events.c
#   btech/mech.spot.c
#   btech/src/btech/mech.events.h
#   btech/src/glue.c
#   events.c

"""
Event system for BTMux Python reimplementation.

This module implements a priority queue-based event system similar to BTMux's
muxevent system in btech/btpr/event.c.

Key concepts:
- Events are scheduled to fire at a specific tick
- Events have a type (for categorization and bulk operations)
- Events can be canceled by marking them as "zombies"
- Priority queue ensures events fire in tick order

Reference: BTMux btech/btpr/event.c
"""

import heapq
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Optional
from collections import defaultdict


class EventType(IntEnum):
    """
    Event types matching BTMux's mech.events.h categories.

    Types are used for:
    - Categorizing events for debugging/stats
    - Bulk operations (cancel all events of a type)
    - Running all events of a type immediately
    """
    # Core movement/position events
    MOVE = auto()
    STARTUP = auto()
    LOCK = auto()
    STAND = auto()
    JUMP = auto()
    FALL = auto()
    LATERAL = auto()

    # Weapon/combat events
    RECYCLE = auto()           # Weapon recycling
    SPOT_CHECK = auto()        # Spotter link watchdog (EVENT_SPOT_CHECK,
                               # mech.spot.c:38-62, re-armed at SPOT_TICK)
    SPOT_LOCK = auto()
    TAG_RECYCLE = auto()
    SLITE_CHANGE = auto()
    HIDE = auto()

    # Recovery/status events
    RECOVERY = auto()          # Pilot recovery from unconscious
    JUMPSTABIL = auto()        # Jump stabilization
    SCHANGE = auto()           # Sensor change
    BLINDREC = auto()          # Blind recovery

    MRECOVERY = auto()         # Equipment radio/scanner recovery
    CREWSTUN = auto()
    UNSTUN_CREW = auto()

    # Heat events
    HEAT_CUTOFF = auto()
    DUMP = auto()
    VEHICLE_BURN = auto()
    VEHICLE_EXTINGUISH = auto()
    INFERNO = auto()
    HEAT = auto()              # Heat update (periodic)

    # Map/LOS events
    PLOS = auto()              # Possible line of sight

    MOVEMODE = auto()
    HULLDOWN = auto()
    OOD = auto()
    STANDFAIL = auto()

    # Misc
    CUSTOM = auto()            # Custom/user events
    PERIODIC = auto()          # Periodic system updates
    ARTILLERY_HIT = auto()
    SIXTH_SENSE = auto()
    STEALTH_ARMOR = auto()
    NSS = auto()
    DIG = auto()
    UNJAM_TURRET = auto()
    EXPLODE = auto()
    MASC_FAIL = auto()
    MASC_REGEN = auto()
    SCHARGE_FAIL = auto()
    SCHARGE_REGEN = auto()
    UNJAM_AMMO = auto()
    REMOVE_PODS = auto()
    TAKEOFF = auto()
    DECORATION = auto()
    CHECK_STAGGER = auto()
    SIDESLIP = auto()
    AERO_MOVE = auto()
    BREGEN = auto()
    BREBUILD = auto()
    NUKEMECH = auto()
    ENTER_HANGAR = auto()
    REPAIR_REPLACEPART = auto()
    REPAIR_REPLACEGUN = auto()
    REPAIR_REATTACH = auto()
    REPAIR_RELOAD = auto()
    REPAIR_ARMOR = auto()
    REPAIR_INTERNAL = auto()
    REPAIR_REMOVESECTION = auto()
    REPAIR_REMOVEPART = auto()
    REPAIR_REMOVEGUN = auto()
    REPAIR_REPAIRGUN = auto()
    REPAIR_REPAIRPART = auto()
    REPAIR_MOUNTBOMB = auto()
    REPAIR_UNMOUNTBOMB = auto()
    REPAIR_RESEAL = auto()
    REPAIR_REPLACESUIT = auto()
    REPAIR_ENHCRIT = auto()
    AUTOCOM = auto()
    AUTOGUN = auto()
    AUTO_SENSOR = auto()
    AUTO_PROFILE = auto()
    AUTO_REPLY = auto()
    AUTOGOTO = auto()
    AUTOLEAVE = auto()
    AUTOFOLLOW = auto()
    AUTOENTERBASE = auto()
    AUTO_ROAM = auto()
    WEATHER = 1000            # Port-owned R4 event, outside source IDs.


# mech.events.h IDs deliberately do not reuse Python Enum auto values.
SOURCE_EVENT_IDS = {
    EventType.AUTOGOTO:23, EventType.AUTOLEAVE:24, EventType.AUTOFOLLOW:28,
    EventType.AUTOENTERBASE:29, EventType.AUTO_ROAM:32,
    EventType.AUTOCOM:25, EventType.AUTOGUN:26,
    EventType.AUTO_SENSOR:27, EventType.AUTO_PROFILE:31, EventType.AUTO_REPLY:30,
    EventType.REPAIR_REPLACEPART:43, EventType.REPAIR_REPLACEGUN:44,
    EventType.REPAIR_REATTACH:45, EventType.REPAIR_RELOAD:46,
    EventType.REPAIR_ARMOR:47, EventType.REPAIR_INTERNAL:48,
    EventType.REPAIR_REMOVESECTION:49, EventType.REPAIR_REMOVEPART:50,
    EventType.REPAIR_REMOVEGUN:51, EventType.REPAIR_REPAIRGUN:52,
    EventType.REPAIR_REPAIRPART:53, EventType.REPAIR_MOUNTBOMB:54,
    EventType.REPAIR_UNMOUNTBOMB:55, EventType.REPAIR_RESEAL:56,
    EventType.REPAIR_REPLACESUIT:57, EventType.REPAIR_ENHCRIT:58,
    EventType.ENTER_HANGAR: 73,
    EventType.NUKEMECH: 39,
    EventType.BREGEN: 17, EventType.BREBUILD: 18,
    EventType.MOVE: 1, EventType.ARTILLERY_HIT: 2, EventType.STARTUP: 3,
    EventType.LOCK: 4, EventType.STAND: 5, EventType.JUMP: 6,
    EventType.RECYCLE: 7, EventType.JUMPSTABIL: 8, EventType.RECOVERY: 9,
    EventType.SCHANGE: 10, EventType.DECORATION: 11, EventType.SPOT_LOCK: 12,
    EventType.PLOS: 13, EventType.SPOT_CHECK: 14, EventType.TAKEOFF: 15,
    EventType.FALL: 16, EventType.DUMP: 19, EventType.MASC_FAIL: 20,
    EventType.MASC_REGEN: 21, EventType.MRECOVERY: 33, EventType.BLINDREC: 34,
    EventType.INFERNO: 35, EventType.SIXTH_SENSE: 36, EventType.HIDE: 37,
    EventType.OOD: 38, EventType.LATERAL: 40, EventType.EXPLODE: 41,
    EventType.DIG: 42, EventType.STANDFAIL: 60, EventType.SLITE_CHANGE: 61,
    EventType.HEAT_CUTOFF: 62, EventType.VEHICLE_BURN: 63, EventType.UNSTUN_CREW: 64,
    EventType.CREWSTUN: 65, EventType.UNJAM_TURRET: 66, EventType.UNJAM_AMMO: 67,
    EventType.STEALTH_ARMOR: 68, EventType.NSS: 69, EventType.TAG_RECYCLE: 70,
    EventType.REMOVE_PODS: 71, EventType.VEHICLE_EXTINGUISH: 72,
    EventType.HULLDOWN: 74, EventType.SCHARGE_FAIL: 76, EventType.SCHARGE_REGEN: 77,
    EventType.CHECK_STAGGER: 78, EventType.MOVEMODE: 79, EventType.SIDESLIP: 80,
    EventType.AERO_MOVE: 1,
}
SOURCE_EVENT_NAMES = (
    'NONAME', 'Move', 'DHIT', 'Startup', 'Lock', 'Stand', 'Jump', 'Recycle',
    'JumpSt', 'PRecov', 'SChange', 'DecRemv', 'SpotLck', 'PLos', 'ChkRng',
    'Takeoff', 'Fall', 'BRegen', 'BRebuild', 'Dump', 'MASCF', 'MASCR', 'AmmoWarn',
    'AutoGoto', 'AutoLeave', 'AutoCo', 'AutoGun', 'AutoSensor', 'AutoFollow',
    'AutoEnter', 'AutoReply', 'AutoProfile', 'AutoRoam', 'MRec', 'BlindR', 'Burn',
    'SixthS', 'Hidin', 'OOD', 'Misc', 'Lateral', 'SelfExp', 'DigIn', 'TRepl',
    'TReplG', 'TReat', 'TRelo', 'TFix', 'TFixI', 'TScrL', 'TScrP', 'TScrG',
    'TRepaG', 'TRepaP', 'TMoB', 'TUMoB', 'TRese', 'TRepSuit', 'TRepNHCrit',
    '59', 'StandF', 'SliteC', 'HeatCutOff', 'VechBurn', 'UnStunCrew', 'StunCrew',
    'UnJamTurret', 'UnJamAmmo', 'StArmor', 'NSS', 'TagRecycle', 'RemPods',
    'Extinguish', 'EntHangar', 'Hulldown', '75', 'SchFail', 'SchRegen',
    'CkStagger', 'MoveMode', 'Sideslip',
)



@dataclass(frozen=True)
class SourceEventType:
    """Opaque source type for persisted no-op events outside known callbacks."""
    value: int

    @property
    def name(self):
        return f'SOURCE_{self.value}'


def source_event_type(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid source event type')
    known = next((kind for kind,number in SOURCE_EVENT_IDS.items() if number == value), None)
    if known is not None:
        return known
    kind = SourceEventType(value)
    SOURCE_EVENT_IDS[kind] = value
    return kind


def prerun_event(event):
    """Intentional empty body from events.c."""


def postrun_event(event):
    """Intentional empty body from events.c."""


def very_fake_func(event):
    """Intentional empty body from mech.events.c."""


@dataclass(order=True)
class Event:
    """
    A scheduled event in the game engine.

    Events are ordered by their scheduled tick for priority queue operations.

    Attributes:
        tick: The game tick when this event should fire
        event_id: Unique identifier for this event
        event_type: Category of event (for bulk operations)
        callback: Function to call when event fires
        data: Primary data passed to callback
        data2: Secondary data (optional, for compatibility with BTMux)
        zombie: If True, event is canceled and will be skipped
    """
    tick: int
    event_id: int = field(compare=False)
    event_type: EventType = field(compare=False)
    callback: Callable[['Event'], None] = field(compare=False, repr=False)
    data: Any = field(compare=False, default=None)
    data2: Any = field(compare=False, default=None)
    zombie: bool = field(compare=False, default=False)

    def cancel(self) -> None:
        """Mark this event as canceled (zombie)."""
        self.zombie = True


class EventQueue:
    """
    Priority queue-based event scheduler.

    Similar to BTMux's muxevent system, this maintains:
    - A min-heap priority queue ordered by tick time
    - Per-type lists for fast type-based operations
    - A global tick counter

    Usage:
        queue = EventQueue()
        queue.schedule(delay=5, event_type=EventType.MOVE, callback=my_func, data=mech)

        # In game loop:
        queue.advance_tick()
        queue.run_events()  # Runs all events scheduled for current tick
    """

    def __init__(self, initial_tick: int = 0):
        """
        Initialize the event queue.

        Args:
            initial_tick: Starting tick value (default 0)
        """
        self._tick = initial_tick
        self._heap: list[Event] = []
        self._next_event_id = 0
        # Track events by type for fast lookups
        self._events_by_type: dict[EventType, set[int]] = defaultdict(set)
        # Track events by data for fast lookups
        self._events_by_data: dict[int, set[int]] = defaultdict(set)
        # Map event_id to event for lookups
        self._events: dict[int, Event] = {}
        self.history = [0] * 100
        self.observe_execution = None

    def initialize_history(self):
        self.history[:] = [0] * 100

    def history_rows(self):
        order = list(range(100))
        for i in range(99):
            for j in range(i+1, 100):
                if self.history[order[i]] > self.history[order[j]]:
                    order[i], order[j] = order[j], order[i]
        total = sum(self.history)
        rows = []
        for kind in order:
            if not self.history[kind]:
                continue
            if kind >= len(SOURCE_EVENT_NAMES):
                raise ValueError('unsupported source event name index')
            from core.randomness import float32
            rows.append(dict(type=kind, name=SOURCE_EVENT_NAMES[kind], count=self.history[kind],
                             percent=float32(float32(100.0*float32(self.history[kind]))/float32(total or 1))))
        return rows

    def pending_rows(self):
        counts = defaultdict(int)
        ports = defaultdict(int)
        for event in self._events.values():
            if event.zombie:
                continue
            source_id = SOURCE_EVENT_IDS.get(event.event_type)
            if source_id is None:
                ports[event.event_type.name] += 1
            else:
                counts[source_id] += 1
        rows = [dict(type=kind, name=SOURCE_EVENT_NAMES[kind] if kind<len(SOURCE_EVENT_NAMES) else f'SOURCE_{kind}', count=counts[kind]) for kind in sorted(counts)]
        rows.extend(dict(type=None, name='port:'+name, count=count) for name, count in sorted(ports.items()))
        return rows

    def debug_event_types(self, argument=''):
        if argument:
            return ['Event history (by use)'] + [
                '{type:<3d}{name:<20}{count:10d} {percent:.3f}%'.format(**row)
                for row in self.history_rows()]
        rows = self.pending_rows()
        total = sum(row['count'] for row in rows)
        lines = ['Events by type: ', '-------------------------------']
        lines.extend('{name:<20}{count}'.format(**row) for row in rows)
        if total:
            lines.append('-------------------------------')
        return lines + [f'{total} total']

    def _execute(self, event):
        # The event remains in type/data lists throughout the callback.
        if self.observe_execution is not None:
            self.observe_execution('pre', event)
        prerun_event(event)
        event.callback(event)
        postrun_event(event)
        if self.observe_execution is not None:
            self.observe_execution('post', event)

    @property
    def tick(self) -> int:
        """Current game tick."""
        return self._tick

    @property
    def pending_count(self) -> int:
        """Number of non-zombie events in queue."""
        return sum(1 for e in self._events.values() if not e.zombie)

    def advance_tick(self) -> None:
        """Advance the tick counter by 1."""
        self._tick += 1

    def set_tick(self, tick: int) -> None:
        """Set the tick counter to a specific value."""
        self._tick = tick

    def schedule(
        self,
        delay: int,
        event_type: EventType,
        callback: Callable[[Event], None],
        data: Any = None,
        data2: Any = None,
    ) -> Event:
        """
        Schedule an event to fire after a delay.

        Args:
            delay: Ticks from now until event fires (minimum 1)
            event_type: Category of event
            callback: Function to call when event fires
            data: Primary data to pass to callback
            data2: Secondary data (optional)

        Returns:
            The scheduled Event object (can be used to cancel)
        """
        # BTMux enforces minimum delay of 1
        if delay < 1:
            delay = 1

        event_id = self._next_event_id
        self._next_event_id += 1

        event = Event(
            tick=self._tick + delay,
            event_id=event_id,
            event_type=event_type,
            callback=callback,
            data=data,
            data2=data2,
        )

        heapq.heappush(self._heap, event)
        self._events[event_id] = event
        self._events_by_type[event_type].add(event_id)

        # Track by data object id for fast lookups
        if data is not None:
            self._events_by_data[id(data)].add(event_id)

        return event

    def schedule_at(
        self,
        tick: int,
        event_type: EventType,
        callback: Callable[[Event], None],
        data: Any = None,
        data2: Any = None,
    ) -> Event:
        """
        Schedule an event to fire at a specific tick.

        Args:
            tick: Absolute tick when event should fire
            event_type: Category of event
            callback: Function to call when event fires
            data: Primary data to pass to callback
            data2: Secondary data (optional)

        Returns:
            The scheduled Event object
        """
        delay = tick - self._tick
        return self.schedule(delay, event_type, callback, data, data2)

    def muxevent_run(self) -> int:
        """
        Advance the tick and run everything due.

        Port of muxevent_run (btech/btpr/event.c:209-246): each call bumps
        muxevent_tick by one and executes all events scheduled for it.  The
        dispatch clock calls this once per catch-up iteration
        (glue.c:929-930).

        Returns:
            Number of events that were executed
        """
        self.advance_tick()
        return self.run_events()

    def run_events(self) -> int:
        """
        Run all events scheduled for the current tick or earlier.

        Returns:
            Number of events that were executed
        """
        executed = 0

        while self._heap:
            # Peek at the next event
            event = self._heap[0]

            # Stop if event is in the future
            if event.tick > self._tick:
                break

            # Pop the event
            heapq.heappop(self._heap)

            # Skip zombies, but still clean them up
            if event.zombie:
                self._cleanup_event(event)
                continue

            # Execute the event
            try:
                self._execute(event)
            except Exception as e:
                # Log but don't crash the game loop
                print(f"Event {event.event_id} ({event.event_type.name}) raised exception: {e}")

            executed += 1
            self._cleanup_event(event)

        return executed

    def _cleanup_event(self, event: Event) -> None:
        """Remove an event from tracking structures."""
        event_id = event.event_id

        if event_id in self._events:
            del self._events[event_id]

        self._events_by_type[event.event_type].discard(event_id)

        if event.data is not None:
            self._events_by_data[id(event.data)].discard(event_id)

    def cancel_event(self, event: Event) -> None:
        """
        Cancel a scheduled event.

        The event will be marked as a zombie and skipped when its tick comes.
        This is O(1) - we don't remove from the heap.
        """
        event.cancel()

    def cancel_by_type(self, event_type: EventType) -> int:
        """
        Cancel all events of a specific type.

        Args:
            event_type: The type of events to cancel

        Returns:
            Number of events canceled
        """
        count = 0
        for event_id in list(self._events_by_type[event_type]):
            if event_id in self._events:
                event = self._events[event_id]
                if not event.zombie:
                    event.cancel()
                    count += 1
        return count

    def cancel_by_data(self, data: Any) -> int:
        """
        Cancel all events with a specific data object.

        This is useful for canceling all events related to a specific mech.

        Args:
            data: The data object to match

        Returns:
            Number of events canceled
        """
        count = 0
        data_id = id(data)
        for event_id in list(self._events_by_data[data_id]):
            if event_id in self._events:
                event = self._events[event_id]
                if not event.zombie:
                    event.cancel()
                    count += 1
        return count

    def cancel_by_type_and_data(self, event_type: EventType, data: Any) -> int:
        """
        Cancel all events of a type with specific data.

        Args:
            event_type: The type of events to cancel
            data: The data object to match

        Returns:
            Number of events canceled
        """
        count = 0
        data_id = id(data)
        type_events = self._events_by_type[event_type]
        data_events = self._events_by_data[data_id]

        for event_id in type_events & data_events:
            if event_id in self._events:
                event = self._events[event_id]
                if not event.zombie:
                    event.cancel()
                    count += 1
        return count

    def cancel_by_type_and_data2(self, event_type: EventType, data2: Any) -> int:
        """Cancel every callback owned by a secondary object (source StopDec)."""
        count = 0
        for event_id in tuple(self._events_by_type[event_type]):
            event = self._events.get(event_id)
            if event is not None and not event.zombie and event.data2 is data2:
                event.cancel()
                count += 1
        return count

    def count_type(self, event_type: EventType) -> int:
        """Count non-zombie events of a specific type."""
        count = 0
        for event_id in self._events_by_type[event_type]:
            if event_id in self._events and not self._events[event_id].zombie:
                count += 1
        return count

    def count_data(self, data: Any) -> int:
        """Count non-zombie events with specific data."""
        count = 0
        for event_id in self._events_by_data[id(data)]:
            if event_id in self._events and not self._events[event_id].zombie:
                count += 1
        return count

    def has_event_type_data(self, event_type: EventType, data: Any) -> bool:
        """Check if any non-zombie event exists with type and data."""
        data_id = id(data)
        type_events = self._events_by_type[event_type]
        data_events = self._events_by_data[data_id]

        for event_id in type_events & data_events:
            if event_id in self._events and not self._events[event_id].zombie:
                return True
        return False

    def time_until_type_data(self, event_type: EventType, data: Any) -> Optional[int]:
        """
        Get ticks until next event of type with data fires.

        Returns:
            Ticks until event, or None if no such event exists
        """
        data_id = id(data)
        type_events = self._events_by_type[event_type]
        data_events = self._events_by_data[data_id]

        min_tick = None
        for event_id in type_events & data_events:
            if event_id in self._events:
                event = self._events[event_id]
                if not event.zombie:
                    if min_tick is None or event.tick < min_tick:
                        min_tick = event.tick

        if min_tick is not None:
            return min_tick - self._tick
        return None

    def pending_events(self, event_type=None, data=None):
        """Live queue inspection, including the callback currently executing."""
        return sorted((event for event in self._events.values() if not event.zombie
                       and (event_type is None or event.event_type == event_type)
                       and (data is None or event.data is data)), key=lambda event: (event.tick, event.event_id))

    def heap_events(self):
        """Heap slots, including zombies whose removal can change equal-tick order."""
        return tuple(self._heap)

    def restore_slots(self, slots, removed):
        """Restore validated subsystem slots without changing the tick-only heap.

        Each slot is (absolute tick, retained/new Event or None). Missing world
        anchors become inert zombies, preserving the saved heap shape without
        replaying world callbacks. Current events outside the snapshot are then
        inserted normally. The caller validates the layout before any mutation.
        """
        retained = {id(event) for _,event in slots if event is not None}
        removed = set(removed) | {event.event_id for event in self._heap
            if getattr(event,'_restore_padding',False) and id(event) not in retained}
        extras = [event for event in self._heap
                  if id(event) not in retained and event.event_id not in removed]
        for event_id in removed:
            event = self._events.get(event_id)
            if event is not None:
                self._cleanup_event(event)
        heap = []
        for tick,event in slots:
            if event is None:
                event = Event(tick,-1,EventType.CUSTOM,very_fake_func,zombie=True)
                event._restore_padding = True
            if self._events.get(event.event_id) is not event:
                if event.event_id < 0 or event.event_id in self._events:
                    event.event_id = self._next_event_id
                self._next_event_id = max(self._next_event_id,event.event_id+1)
                self._events[event.event_id] = event
                self._events_by_type[event.event_type].add(event.event_id)
                if event.data is not None:
                    self._events_by_data[id(event.data)].add(event.event_id)
            heap.append(event)
        self._heap = heap
        for event in extras:
            heapq.heappush(self._heap,event)

    def last_time_until_type_data(self, event_type, data):
        """muxevent_last_type_data: latest remaining deadline, not the next one."""
        events = self.pending_events(event_type, data)
        return max(0, max(event.tick for event in events) - self._tick) if events else None

    def run_by_type(self, event_type: EventType) -> int:
        """
        Run all events of a type immediately, regardless of tick.

        This is used by BTMux for things like running all tech events
        at once during a reset.

        Args:
            event_type: The type of events to run

        Returns:
            Number of events executed
        """
        executed = 0
        for event_id in sorted(self._events_by_type[event_type], reverse=True):
            if event_id in self._events:
                event = self._events[event_id]
                if not event.zombie:
                    try:
                        self._execute(event)
                    except Exception as e:
                        print(f"Event {event.event_id} raised exception: {e}")
                    executed += 1
                    event.cancel()  # Mark as zombie so it's skipped later
        return executed

    def purge_zombies(self) -> int:
        """
        Remove all zombie events from the heap.

        This is an O(n) operation and should be called periodically
        to prevent memory growth.

        Returns:
            Number of zombies removed
        """
        old_len = len(self._heap)
        self._heap = [e for e in self._heap if not e.zombie]
        heapq.heapify(self._heap)
        return old_len - len(self._heap)
