# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/autopilot_core.c
#   btech/btpr/event.c
#   btech/mech.combat.c
#   btech/mech.events.c
#   btech/mech.lite.c
#   btech/mech.update.c
#   btech/src/btech/btmacros.h
#   btech/src/glue.c
#   btech/src/include/btconfig.h
#   src/conf.c
#   src/timer.c
#   tick.c
# Historical Aerospace sources:
#   btech/mech.update.c
#   src/hcode/btech/autopilot_core.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.combat.c
#   src/hcode/glue.c
#   src/hcode/include/btconfig.h

"""
Game loop and engine for BTMux Python reimplementation.

This module implements the C's faithful three-clock architecture:

Clock 1 - dispatch (timer.c:135 dispatch() -> glue.c UpdateSpecialObjects):
    Once per simulated second, snapshot the wall clock (sim_now), compute how
    many seconds elapsed since the last run (clamped to 20, glue.c:925-927)
    and loop that many times: run due muxevents (advancing muxevent_tick,
    event.c:209-246), then walk objects in registration order through a
    `now % updateTime == 0` gate with `now` FROZEN for the whole catch-up
    loop (glue.c:898-909).

Clock 2 - heartbeat (tick.c): an independent 1 Hz timer with NO catch-up
    construct (tick.c:82-88).  Walks objects -> mech_heartbeat
    (mech.events.c:27-43) -> UpdateRecycling, then increments global_tick
    (tick.c:34,87).  Weapon recycling is slaved to the dispatch clock's
    muxevent_tick, not to heartbeat invocation count: a delayed heartbeat
    applies the full delta in one lump.

Clock 3 - player commands: executed the instant input arrives, between
    ticks - there is no command queue in the sim (see inject_command).

Reference:
- BTMux src/timer.c - dispatch()
- BTMux btech/src/glue.c - UpdateSpecialObjects(), SpecialObjects[] table
- BTMux btech/src/tick.c - heartbeat_run(), global_tick
- BTMux btech/src/btech/mech.events.c - mech_heartbeat()
- BTMux btech/src/btech/mech.update.c - mech_update(), recycle_weaponry()
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from enum import IntEnum

from .events import EventQueue, EventType, Event
from .randomness import RandomState, simulation_method


# Timing constants from BTMux btconfig.h (btech/src/include/btconfig.h)
HEAT_TICK = 2       # Heat updates every 2 ticks             (btconfig.h:132)
MOVE_TICK = 1       # Movement updates every tick            (btconfig.h:134)
LOS_TICK = 1        # LOS updates every tick                 (btconfig.h:146)
WEAPON_TICK = 2     # Weapon recycle base                    (btconfig.h:136)
JUMP_TICK = 1       # Jump progression                       (btconfig.h:133)
FALL_TICK = 3       # Fall event interval                    (btconfig.h:156)

# Sensor / LOS cadences (not consumed yet - Workstream D wires them)
# LOCK_TICK is the lock-settling delay the C schedules from settarget
# (mech.combat.c:239, guarded by #if LOCK_TICK > 0).  The C constant is 8; the
# product canon defaults it to 0 (instant, stable locks - no settling penalty).
# TODO: the gameplay default of 0 is Workstream D policy - see
# PLANNING_JULY_2026.md section 1.3.  This is the ported C value.
LOCK_TICK = 8               # Lock settling delay            (btconfig.h:210)
PLOS_TICK = 1               # Possible-LOS sweep interval    (btconfig.h:148)
INITIAL_PLOS_TICK = 1       # First PLOS sweep after startup (btconfig.h:145)
SCHANGE_TICK = 10           # Sensor mode change delay       (btconfig.h:149)
SPOT_TICK = 10              # Spotting range recheck         (btconfig.h:150)
HIDE_TICK = 10              # Seconds per hiding "turn"      (btconfig.h:147)
RANDOM_TICK = 6             # Same rnd# reused this long     (btconfig.h:165)

# Misc unit cadences (not consumed yet)
STARTUP_TIME = 30           # Full reactor startup duration  (btconfig.h:153)
UNCONSCIOUS_TIME = 30       # Unconsciousness duration       (btconfig.h:154)
LATERAL_TICK = 6            # Quad lateral movement change   (btconfig.h:131)
MASC_TICK = 60              # MASC regen / fail interval     (btconfig.h:163)
DROP_TO_STAND_RECYCLE = MOVE_TICK * 12  # Stand-up recycle   (btconfig.h:142)

# The dispatch catch-up clamp (glue.c:925-927).  This is the ONLY place the
# simulation actually loses time: when the machine lags more than this many
# seconds, muxevent_tick itself falls behind wall-clock and never recovers.
DISPATCH_CATCHUP_CLAMP = 20


class EngineState(IntEnum):
    """Game engine states."""
    STOPPED = 0
    RUNNING = 1
    PAUSED = 2


@dataclass
class PeriodicUpdate:
    """
    A periodic update that runs at a fixed interval.

    Used for systems like heat dissipation, LOS updates, etc.

    Gating matches the C's UpdateSpecialObject_func (glue.c:898-909): the
    callback runs when `sim_now % interval == 0`, with sim_now frozen across
    a whole dispatch catch-up loop.  last_run is kept as bookkeeping only.
    """
    name: str
    interval: int  # Ticks between updates
    callback: Callable[['GameEngine'], None]
    last_run: int = 0  # Last tick this ran (bookkeeping only)
    enabled: bool = True


@dataclass
class ObjectTypeRegistration:
    """
    A special-object type registration, one row of the C's SpecialObjects[]
    table (glue.c:56-68), e.g. { "MECH", ..., HEAT_TICK, mech_update, ... }.

    update_fn is called as update_fn(engine, entity) for every registered
    entity of this type whenever `sim_now % update_time == 0`.
    """
    name: str
    update_time: int
    update_fn: Callable[['GameEngine', Any], None]


class GameEngine:
    """
    Main game engine managing the three clocks and the event system.

    Per simulated second (process_tick / run_ticks):
    1. dispatch(): advance sim_now, catch-up loop of muxevent runs +
       object-type sweeps + legacy periodics (clock 1)
    2. heartbeat(): recycle bookkeeping, global_tick++ (clock 2, suppressible
       via heartbeat_enabled so tests can make the clocks visibly diverge)

    Player commands (clock 3) execute immediately via inject_command().

    Usage:
        engine = GameEngine()
        engine.register_periodic("heat", HEAT_TICK, update_heat)
        await engine.run()  # Or engine.run_sync() for blocking

    Attributes:
        tick: Current game tick (alias of muxevent_tick)
        muxevent_tick: The dispatch clock's event tick (event.c muxevent_tick)
        global_tick: Heartbeat counter - incremented ONLY by heartbeat()
            (tick.c:34,87 - incremented there and nowhere else)
        sim_now: Simulated wall-clock seconds (mudstate.now analogue)
        events: The event queue
        tick_duration: Seconds per tick (default 1.0)
        heartbeat_enabled: If False, process_tick skips the heartbeat clock
        command_log: (muxevent_tick, seq, actor, label) per injected command
    """

    def __init__(self, tick_duration: float = 1.0):
        """
        Initialize the game engine.

        The engine is BARE on construction: no periodics and no object types
        are pre-registered (wiring helpers like register_special_objects and
        the systems' register_*_system functions do that explicitly).

        Args:
            tick_duration: Real-time seconds per game tick (default 1.0)
        """
        self._events = EventQueue()
        self.randomness = RandomState()
        from .effects import LocalEffects
        self.effects = LocalEffects()
        self._periodics: list[PeriodicUpdate] = []
        self._state = EngineState.STOPPED
        self._tick_duration = tick_duration

        # Clock state
        # sim_now is the simulated wall clock (mudstate.now, absolute seconds
        # in the C; here it starts at 0 and the first processed second is 1).
        self.sim_now: int = 0
        # global_tick is the heartbeat counter (tick.c:34) - incremented only
        # by heartbeat() (tick.c:87) and nowhere else.
        self.global_tick: int = 0
        # UpdateSpecialObjects' `static time_t lastrun = 0` (glue.c:919):
        # 0 means "never ran", making the first dispatch run exactly once.
        self._last_dispatch_run: int = 0

        # Special-object type registry (SpecialObjects[] analogue, glue.c:56)
        self._object_types: dict[str, ObjectTypeRegistration] = {}

        # mudconf.btech_idf_requires_spotter (src/conf.c:141, default 1):
        # IDF weapons fired at a target/hex outside the firer's own line of
        # sight require a spotter (mech.combat.c:564-569, 604-610).  Set to
        # False for spotterless LRM blindfire.
        self.idf_requires_spotter: bool = True

        # Broad combat skills are the default; each expanded selector is opt-in.
        self.extended_gunnery: bool = False
        self.extended_piloting: bool = False

        # Clock 3: injected player commands
        self.heartbeat_enabled: bool = True
        self.auto_services = {}
        self.explode_reactor = 1
        self.command_log: list[tuple[int, int, Any, str]] = []
        self._command_seq: int = 0

        # Stats
        self._total_events_run = 0
        self._total_ticks = 0
        self._start_time: Optional[float] = None

        # Callbacks
        self._on_tick_callbacks: list[Callable[[int], None]] = []
        self._entities: dict[int, Any] = {}  # Tracked entities by id

    @property
    def tick(self) -> int:
        """Current game tick (alias of muxevent_tick)."""
        return self._events.tick

    @property
    def muxevent_tick(self) -> int:
        """
        The dispatch clock's event tick (event.c muxevent_tick).

        Advanced only inside dispatch()'s catch-up loop; weapon recycling is
        slaved to this counter, NOT to the heartbeat.
        """
        return self._events.tick

    @property
    def events(self) -> EventQueue:
        """The event queue."""
        return self._events

    @property
    def state(self) -> EngineState:
        """Current engine state."""
        return self._state

    @property
    def tick_duration(self) -> float:
        """Seconds per game tick."""
        return self._tick_duration

    @tick_duration.setter
    def tick_duration(self, value: float) -> None:
        """Set seconds per game tick."""
        if value <= 0:
            raise ValueError("tick_duration must be positive")
        self._tick_duration = value

    @property
    def uptime(self) -> float:
        """Seconds since engine started (0 if not running)."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    # --- Entity Management ---

    def register_entity(self, entity: Any) -> None:
        """
        Register an entity with the engine for tracking.

        Entities can be mechs, maps, or other game objects. Registration
        order is retained for the dispatch sweep; heartbeat visits source
        object keys in ascending order.
        """
        self._entities[id(entity)] = entity
        from entities.autopilot import Autopilot
        if isinstance(entity, Autopilot):
            from systems.autopilot import install_builtin_services
            install_builtin_services(self)
        if hasattr(entity, '_engine'):
            entity._engine = self
            if getattr(entity,'xcode_type',None)=='MAP':
                from physics.environment import arm
                arm(entity)
            if getattr(entity, 'is_started', False) and getattr(entity, 'map', None) is not None:
                from systems.targeting import start_plos_event
                entity.per = getattr(entity.pilot, 'perception', 6)
                start_plos_event(self, entity)
            remaining = getattr(entity, 'uncon_recovery_countdown', 0)
            if remaining > 0:
                from systems.piloting import recovery_event
                if not self.has_event(EventType.RECOVERY, entity):
                    self.schedule_event(remaining, EventType.RECOVERY, recovery_event, data=entity)
                entity.uncon_recovery_countdown = 0
            if getattr(entity, 'burn_recovery_countdown', 0) > 0:
                from systems.missile import inferno_burn
                inferno_burn(self, entity, 0)

    def unregister_entity(self, entity: Any, *, cancel_events: bool = True) -> None:
        """Unregister an entity and cancel all its events."""
        entity_id = id(entity)
        if entity_id in self._entities:
            del self._entities[entity_id]
            if cancel_events: self._events.cancel_by_data(entity)
            if getattr(entity,'xcode_type',None)=='MAP':
                from physics.environment import cancel
                cancel(entity)

    def get_entities(self) -> list[Any]:
        """Get all registered entities."""
        return list(self._entities.values())

    @staticmethod
    def _object_type_of(entity: Any) -> str:
        """
        The special-object type name of an entity (GTYPE analogue).

        Uses an explicit `xcode_type` attribute if present, else the upper-
        cased class name (so entities.mech.Mech is a "MECH", matching the
        SpecialObjects[] row at glue.c:57).
        """
        explicit = getattr(entity, "xcode_type", None)
        if explicit:
            return explicit
        return type(entity).__name__.upper()

    # --- Event Scheduling ---

    def schedule_event(
        self,
        delay: int,
        event_type: EventType,
        callback: Callable[[Event], None],
        data: Any = None,
        data2: Any = None,
    ) -> Event:
        """
        Schedule an event to fire after a delay.

        This is the primary way to schedule one-shot events.

        Args:
            delay: Ticks until event fires (minimum 1)
            event_type: Category of event
            callback: Function to call when event fires
            data: Primary data (typically the mech/entity)
            data2: Secondary data (optional)

        Returns:
            The scheduled Event (can be canceled)
        """
        return self._events.schedule(delay, event_type, callback, data, data2)

    def cancel_events_for(self, entity: Any) -> int:
        """Cancel all events associated with an entity."""
        return self._events.cancel_by_data(entity)

    def cancel_events_of_type(self, event_type: EventType, entity: Any = None) -> int:
        """
        Cancel events of a specific type.

        Args:
            event_type: Type of events to cancel
            entity: If provided, only cancel events with this data

        Returns:
            Number of events canceled
        """
        if entity is not None:
            return self._events.cancel_by_type_and_data(event_type, entity)
        return self._events.cancel_by_type(event_type)

    def has_event(self, event_type: EventType, entity: Any) -> bool:
        """Check if an entity has a pending event of a type."""
        return self._events.has_event_type_data(event_type, entity)

    def event_time_remaining(self, event_type: EventType, entity: Any) -> Optional[int]:
        """Get ticks until an entity's event of a type fires."""
        return self._events.time_until_type_data(event_type, entity)

    # --- Periodic Updates ---

    def register_periodic(
        self,
        name: str,
        interval: int,
        callback: Callable[['GameEngine'], None],
    ) -> PeriodicUpdate:
        """
        Register a periodic update function.

        Periodic updates run every N ticks, used for systems like:
        - Heat dissipation (HEAT_TICK = 2)
        - Movement updates (MOVE_TICK = 1)
        - LOS recalculation (LOS_TICK = 1)

        Args:
            name: Name for this periodic (for debugging)
            interval: Ticks between updates
            callback: Function to call, receives the engine

        Returns:
            The PeriodicUpdate object (can be disabled)
        """
        periodic = PeriodicUpdate(
            name=name,
            interval=interval,
            callback=callback,
            last_run=self._events.tick,
        )
        self._periodics.append(periodic)
        return periodic

    def unregister_periodic(self, name: str) -> bool:
        """Remove a periodic update by name."""
        for i, p in enumerate(self._periodics):
            if p.name == name:
                del self._periodics[i]
                return True
        return False

    def register_object_type(
        self,
        name: str,
        update_time: int,
        update_fn: Callable[['GameEngine', Any], None],
    ) -> ObjectTypeRegistration:
        """
        Register a special-object type update, one SpecialObjects[] row
        (glue.c:56-68), e.g. register_object_type("MECH", HEAT_TICK,
        mech_update).

        During each dispatch iteration, every registered entity whose type
        name matches is walked through a `sim_now % update_time == 0` gate
        (glue.c:898-909) and update_fn(engine, entity) is called when due.

        Args:
            name: Type name ("MECH", "MAP", ...), matched against
                _object_type_of(entity)
            update_time: Seconds between updates (0 = never, as in the C)
            update_fn: Called as update_fn(engine, entity)

        Returns:
            The ObjectTypeRegistration
        """
        registration = ObjectTypeRegistration(
            name=name,
            update_time=update_time,
            update_fn=update_fn,
        )
        self._object_types[name] = registration
        return registration

    def unregister_object_type(self, name: str) -> bool:
        """Remove a special-object type registration by name."""
        return self._object_types.pop(name, None) is not None

    def _run_object_sweep(self) -> int:
        """
        Walk all registered entities in registration order through the
        `now % updateTime == 0` gate and run their type's update function.

        Port of the rb_walk over UpdateSpecialObject_func (glue.c:898-909,
        929-933).  sim_now is FROZEN for the whole catch-up loop in
        dispatch(), so during an N-iteration catch-up an every-2s update
        runs N times if the frozen second is even and 0 times if odd - the
        C's oddity, ported deliberately.
        """
        ran = 0
        for entity in list(self._entities.values()):
            registration = self._object_types.get(self._object_type_of(entity))
            if registration is None:
                continue
            # UpdateSpecialObject_func (glue.c:903-906): skip updateTime 0,
            # then gate on mudstate.now % updateTime.
            if not registration.update_time:
                continue
            if self.sim_now % registration.update_time:
                continue
            try:
                registration.update_fn(self, entity)
            except Exception as e:
                print(f"Object update '{registration.name}' raised exception: {e}")
            ran += 1
        return ran

    def _run_periodics(self) -> int:
        """
        Run all periodic updates that are due under the frozen-now modulo
        gate (`sim_now % interval == 0`, same semantics as the object sweep,
        glue.c:898-909).  Replaces the old since-last-run gate.
        """
        ran = 0
        for periodic in self._periodics:
            if not periodic.enabled:
                continue
            if self.sim_now % periodic.interval:
                continue
            try:
                periodic.callback(self)
            except Exception as e:
                print(f"Periodic '{periodic.name}' raised exception: {e}")
            periodic.last_run = self._events.tick
            ran += 1
        return ran

    # --- Tick Callbacks ---

    def on_tick(self, callback: Callable[[int], None]) -> None:
        """
        Register a callback to run every tick.

        The callback receives the current tick number.
        This runs after events and periodics (once per dispatch iteration,
        so it also fires during catch-up).
        """
        self._on_tick_callbacks.append(callback)

    # --- Clock 1: dispatch ---

    @simulation_method
    def dispatch(self, now: Optional[int] = None) -> tuple[int, int]:
        """
        Run the dispatch clock for one wall-clock second.

        Port of dispatch() -> UpdateSpecialObjects() (timer.c:135,
        glue.c:911-937).  Advances sim_now by 1 (or snapshots the given
        `now`, the mudstate.now analogue), computes how many seconds
        elapsed since the last run and loops that many times:
        (a) muxevent_run - advance muxevent_tick and run due events,
        (b) the object-type sweep, (c) legacy generic periodics,
        then the on_tick callbacks.

        sim_now is frozen across the whole catch-up loop (glue.c:898-909):
        during an N-iteration catch-up, an every-2s update runs N times if
        the frozen second is even and 0 times if odd.

        Args:
            now: New value for sim_now; if None, sim_now advances by 1

        Returns:
            Tuple of (events_run, periodics_run) totals over all iterations
        """
        if now is None:
            self.sim_now += 1
        else:
            self.sim_now = now

        # glue.c:923: times = lastrun ? (mudstate.now - lastrun) : 1
        times = (self.sim_now - self._last_dispatch_run) if self._last_dispatch_run else 1
        if times > DISPATCH_CATCHUP_CLAMP:
            times = DISPATCH_CATCHUP_CLAMP  # Machine's hopelessly lagged,
            # we don't want to make it [much] worse (glue.c:925-927)

        events_run = 0
        periodics_run = 0

        for _ in range(times):
            # (a) muxevent_run (glue.c:930): advances muxevent_tick and runs
            # everything due (event.c:209-246)
            n = self._events.muxevent_run()
            events_run += n
            self._total_events_run += n
            self._total_ticks += 1

            # (b) object-type sweep with frozen sim_now (glue.c:931-933)
            self._run_object_sweep()

            # (c) legacy generic periodics, same frozen-now modulo gate
            periodics_run += self._run_periodics()

            # Tick callbacks
            current_tick = self._events.tick
            for callback in self._on_tick_callbacks:
                try:
                    callback(current_tick)
                except Exception as e:
                    print(f"Tick callback raised exception: {e}")

        # glue.c:935: lastrun = mudstate.now
        self._last_dispatch_run = self.sim_now

        return events_run, periodics_run

    def skip_seconds(self, seconds: int) -> None:
        """
        Advance the simulated wall clock WITHOUT dispatching.

        This simulates the server lagging: the next dispatch() sees the
        elapsed time and runs its catch-up loop (clamped at
        DISPATCH_CATCHUP_CLAMP, glue.c:925-927).  The heartbeat has no
        catch-up construct, so any heartbeats in the skipped stretch are
        simply lost (tick.c:82-88).

        Args:
            seconds: Seconds to skip
        """
        self.sim_now += seconds

    # --- Clock 2: heartbeat ---

    @property
    def heartbeat_enabled(self):
        return self._heartbeat_enabled

    @heartbeat_enabled.setter
    def heartbeat_enabled(self, enabled):
        self._heartbeat_enabled = bool(enabled)
        self._heartbeat_deadline = self.sim_now + 1 if enabled else None

    @property
    def heartbeat_deadline(self):
        return self._heartbeat_deadline

    @property
    def heartbeat_timer_count(self):
        return int(self._heartbeat_deadline is not None)

    def heartbeat_init(self):
        if not self.heartbeat_enabled:
            self.heartbeat_enabled = True

    def heartbeat_stop(self):
        if self.heartbeat_enabled:
            self.heartbeat_enabled = False

    def heartbeat_dispatch(self, entity):
        kind = self._object_type_of(entity)
        if kind == 'MECH':
            mech_heartbeat(self, entity)
        elif kind == 'AUTO':
            self.auto_heartbeat(entity)

    def auto_heartbeat(self, autopilot):
        """autopilot_core.c's ordering; actual autonomous services are adapters."""
        from systems.autopilot import uses_event_autopilot
        mech = getattr(autopilot, 'mymech', None)
        if mech is None or uses_event_autopilot(mech):
            return
        def run(name):
            from systems.autopilot import autopilot_service
            callback = autopilot_service(self,name,autopilot)
            if callback is not None:
                callback(autopilot)
            else:
                from systems.damage import external_effect
                external_effect(autopilot, 'autopilot gameplay', 'AUTO heartbeat '+name)
        run('sensor')
        if getattr(autopilot, 'weaplist', None) is None or self.global_tick % 180 == 0:
            run('profile')
        run('gun')

    @simulation_method
    def heartbeat(self) -> None:
        """
        Run the heartbeat clock once.

        Port of heartbeat_run (tick.c:82-88): the C re-arms the 1 Hz libevent
        timer first, walks all objects (heartbeat_dispatch, tick.c:61-80,
        MECHs -> mech_heartbeat), then increments global_tick (tick.c:34,87 -
        incremented here and nowhere else).  There is NO catch-up construct:
        a missed heartbeat is not made up.  Recycle timing survives anyway
        because recycle_weaponry is slaved to muxevent_tick and applies the
        full delta in one lump on the next heartbeat.
        """
        self._heartbeat_deadline = self.sim_now + 1
        for entity in sorted(list(self._entities.values()), key=lambda item: getattr(item, '_id', id(item))):
            observer = getattr(self, 'observe_heartbeat_dispatch', None)
            if observer is not None:
                observer(entity)
            self.heartbeat_dispatch(entity)
        self.global_tick = (self.global_tick + 1) & 0xffffffff

    # --- Clock 3: player commands ---

    @simulation_method
    def inject_command(self, actor: Any, fn: Callable[[], Any], label: str = "") -> Any:
        """
        Execute a player command immediately (clock 3).

        In the C, player commands execute the instant input arrives, between
        ticks - there is no command queue in the sim.  Calling this between
        process_tick() calls reproduces that by construction.  The command is
        appended to command_log as (muxevent_tick, seq, actor, label).

        Args:
            actor: Who issued the command (any object; logged as-is)
            fn: Zero-argument callable performing the command
            label: Human-readable command label for the log

        Returns:
            Whatever fn() returns
        """
        seq = self._command_seq
        self._command_seq += 1
        result = fn()
        self.command_log.append((self._events.tick, seq, actor, label))
        return result

    # --- Main Loop ---

    def process_tick(self) -> tuple[int, int]:
        """
        Process a single simulated second: drive BOTH 1 Hz clocks.

        1. dispatch() - clock 1: events, object sweeps, periodics
        2. heartbeat() - clock 2: recycle bookkeeping, global_tick++
           (skipped when heartbeat_enabled is False, letting tests make the
           two clocks visibly diverge)

        The two clocks are separately-schedulable 1 Hz sources in the C
        (SIGALRM vs libevent); they are phase-aligned here by default.

        Returns:
            Tuple of (events_run, periodics_run) from the dispatch clock
        """
        events_run, periodics_run = self.dispatch()

        if self.heartbeat_enabled:
            self.heartbeat()

        return events_run, periodics_run

    async def run(self, max_ticks: Optional[int] = None) -> None:
        """
        Run the game loop asynchronously.

        This is the preferred way to run the engine in an async context.

        Args:
            max_ticks: If set, stop after this many ticks
        """
        if self._state == EngineState.RUNNING:
            raise RuntimeError("Engine is already running")

        self._state = EngineState.RUNNING
        self._start_time = time.time()
        ticks_run = 0

        try:
            while self._state == EngineState.RUNNING:
                tick_start = time.time()

                # Process the tick
                self.process_tick()
                ticks_run += 1

                # Check max ticks
                if max_ticks is not None and ticks_run >= max_ticks:
                    break

                # Calculate sleep time
                elapsed = time.time() - tick_start
                sleep_time = self._tick_duration - elapsed

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                elif elapsed > self._tick_duration * 2:
                    # We're lagging badly, log a warning
                    print(f"Warning: Tick took {elapsed:.3f}s (target: {self._tick_duration}s)")

        finally:
            self._state = EngineState.STOPPED

    def run_sync(self, max_ticks: Optional[int] = None) -> None:
        """
        Run the game loop synchronously (blocking).

        This is a convenience method for non-async contexts.

        Args:
            max_ticks: If set, stop after this many ticks
        """
        asyncio.run(self.run(max_ticks))

    def run_ticks(self, count: int) -> None:
        """
        Run a specific number of simulated seconds without real-time delays.

        Each iteration drives both clocks once (dispatch, then heartbeat).
        Useful for testing and simulation fast-forward.

        Args:
            count: Number of ticks to process
        """
        for _ in range(count):
            self.process_tick()

    def stop(self) -> None:
        """Signal the engine to stop after the current tick."""
        self._state = EngineState.STOPPED

    def pause(self) -> None:
        """Pause the engine (not implemented in async loop yet)."""
        self._state = EngineState.PAUSED

    def resume(self) -> None:
        """Resume the engine from paused state."""
        if self._state == EngineState.PAUSED:
            self._state = EngineState.RUNNING

    # --- Stats ---

    def get_stats(self) -> dict:
        """Get engine statistics."""
        return {
            "tick": self._events.tick,
            "sim_now": self.sim_now,
            "global_tick": self.global_tick,
            "total_ticks": self._total_ticks,
            "total_events_run": self._total_events_run,
            "pending_events": self._events.pending_count,
            "periodics": len(self._periodics),
            "object_types": len(self._object_types),
            "entities": len(self._entities),
            "uptime": self.uptime,
            "state": self._state.name,
        }


# =============================================================================
# MECH special-object update (dispatch clock, SpecialObjects[] row)
# =============================================================================

def mech_update(engine, mech):
    """The C standard HEAT_TICK dispatcher, with explicit unavailable delegates."""
    from entities.mech import MechStatus as S, MechStatus2 as S2
    from physics.heights import AERO_TYPES
    from systems.stability import update_pilot_skill_rolls, missing_update
    if mech is None:
        return
    mech.clear_status(S.FIRED)
    if mech.unit_type in AERO_TYPES:
        from physics.aerospace import update as aero_update
        aero_update(engine, mech)
        return
    if mech.is_started or mech.has_status(S.UNCONSCIOUS):
        update_pilot_skill_rolls(engine, mech)
    if mech.is_started or mech.plus_heat > 0.1:
        from systems.heat import update_from_environment
        update_from_environment(mech, engine.muxevent_tick)
    if mech.is_started:
        from core.randomness import draw
        mech.vis_mod = max(0, min(100, mech.vis_mod + draw('visibility_change', -40, 40, lambda: random.randint(-40, 40))))
    from systems.ecm import check_ecm
    check_ecm(mech)
    from systems.targeting import check_tag
    from systems.sensors import end_lite_check
    check_tag(mech)
    end_lite_check(mech)
    if mech.status2 & S2.AUTOTURN_TURRET:
        from systems.maneuver import update_autoturn_turret
        update_autoturn_turret(mech, mech.map)


def register_special_objects(engine: GameEngine) -> None:
    """
    Wire the C's SpecialObjects[] table (glue.c:56-68) into the engine.

    MECH -> mech_update at HEAT_TICK (glue.c:57-58).
    MAP -> map_update at LOS_TICK (glue.c:62-63); the map must be added to
    the engine as an entity (add_entity) to be swept, mirroring MAP being an
    XCODE special object.
    """
    from entities.map import map_update
    engine.register_object_type("MECH", HEAT_TICK, mech_update)
    engine.register_object_type("MAP", LOS_TICK, map_update)


def wire_standard_systems(engine: GameEngine) -> None:
    """
    Apply the C server's default wiring to a bare engine.

    Port of the standing SpecialObjects[] table (glue.c:56-68) plus the
    always-on clocks - this is what a freshly booted server has running:

    - Clock 1 (dispatch): MECH -> mech_update at HEAT_TICK via
      register_special_objects (glue.c:57-58) - clears FIRED, runs the heat
      system, walks vis_mod.
    - Movement is NOT a periodic: it is per-mech and event-driven.  Speed /
      heading commands call physics.movement.start_move_event, which arms a
      self-re-arming EVENT_MOVE chain; a stationary mech has no movement
      event (mech.events.c:319-347).  Nothing to register here.
    - Clock 2 (heartbeat) is on: weapon/section recycling counts down via
      mech_heartbeat -> recycle_weaponry (tick.c:82-88, mech.update.c:1539).
    """
    register_special_objects(engine)
    engine.heartbeat_enabled = True


# =============================================================================
# Heartbeat pipeline (clock 2)
# =============================================================================

def mech_heartbeat(engine: GameEngine, mech: Any) -> None:
    """
    Per-heartbeat MECH update.

    Port of mech_heartbeat (mech.events.c:27-43):
    - UpdateRecycling(mech) (:28)
    - Newstagger check (mech.events.c:29-35), gated on
      mudconf.btech_newstagger >= 1 and CLASS_MECH; skips fallen/jumping
      mechs, then mech_staggercheck_heartbeat + ClearStaggerDamage.
    - Aero/VTOL idle FuelCheck (mech.events.c:37-40).
    """
    update_recycling(engine, mech)
    from systems.stagger import heartbeat
    heartbeat(engine, mech)
    from entities.mech import UnitType, MechStatus
    if (mech.unit_type in (UnitType.AERO, UnitType.VTOL)
            and not mech.has_status(MechStatus.LANDED) and mech.speed == 0 and mech.vertical_speed == 0):
        from physics.heights import fuel_check
        fuel_check(mech)


def update_recycling(engine: GameEngine, mech: Any) -> None:
    """
    Lazy, idempotent-per-tick recycle gate.

    Port of UpdateRecycling (btmacros.h:430-432): run recycle_weaponry only
    for started, non-destroyed units whose last_weapon_recycle is not
    already at the current muxevent_tick.
    """
    from entities.mech import MechStatus

    if (mech.has_status(MechStatus.STARTED)
            and not mech.has_status(MechStatus.DESTROYED)
            and mech.last_weapon_recycle != engine.muxevent_tick):
        recycle_weaponry(engine, mech)


def recycle_weaponry(engine: GameEngine, mech: Any) -> int:
    """Recycle live weapon runs and each section in source section order."""
    from entities.mech import UnitType, FireMode
    from entities.crittypes import is_weapon
    from entities.weapon import get_weapon_by_index
    from systems.weapon_inventory import find_weapons
    from systems.combat import part_is_nonfunctional
    from systems.enhanced_crits import part_temp_nuke, set_part_temp_nuke, FAIL_DESTROYED
    from systems.notifications import mech_printf, MECHSTARTED
    from systems.parts import armor_string
    diff = engine.muxevent_tick - mech.last_weapon_recycle
    if diff < 1:
        if diff < 0:
            mech.last_weapon_recycle = engine.muxevent_tick
        return 1
    mech.last_weapon_recycle = engine.muxevent_tick
    if not mech.is_started or mech.is_destroyed:
        return 0
    lowest = 0
    engine.arc_override = 1
    try:
        for loc, section in enumerate(mech.sections):
            for run in find_weapons(mech, loc) or []:
                slot = section.criticals[run.critical]
                if not (slot.data > 0 and is_weapon(slot.type) and not part_is_nonfunctional(mech, loc, run.critical) and not mech.is_section_destroyed(loc)):
                    continue
                historical=mech.unit_type in (UnitType.AERO,UnitType.DS,UnitType.SPHEROID_DS)
                if not historical and (part_temp_nuke(slot) == FAIL_DESTROYED or mech.is_section_destroyed(loc)):
                    slot.data = 0
                if diff >= slot.data:
                    slot.data = 0
                    weapon = get_weapon_by_index(run.weapon_idx)
                    name = weapon.name[3:]
                    if mech.unit_type == UnitType.MW:
                        message = f'%cgYou are ready to attack again with {name}.%c'
                    elif part_temp_nuke(slot):
                        message = f'%cg{name} is operational again.%c'
                    elif slot.firemode & FireMode.ROCKET_FIRED:
                        message = ''
                    else:
                        message = f'%cg{name} finished recycling.%c'
                    mech_printf(mech, MECHSTARTED, '%s', message)
                    set_part_temp_nuke(slot, 0)
                elif part_temp_nuke(slot) != FAIL_DESTROYED:
                    slot.data -= diff
                    lowest = slot.data if not lowest else min(lowest, slot.data)
                for state in mech.weapons:
                    if state.section == loc and state.critical == run.critical:
                        state.recycle = slot.data
            if section.recycle and mech.unit_type in (UnitType.MECH, UnitType.BSUIT, UnitType.VEH_GROUND, UnitType.VTOL):
                if diff >= section.recycle and not mech.is_section_destroyed(loc):
                    section.recycle = 0
                    prefix = '' if mech.unit_type == UnitType.BSUIT else 'Your '
                    mech_printf(mech, MECHSTARTED, '%%cg%s%s has finished its previous action.%%c', prefix, armor_string(mech, loc))
                else:
                    # mech_section.recycle is a source char, including wrap on
                    # a destroyed section with an overdue counter.
                    section.recycle = (section.recycle - diff + 128) % 256 - 128
                    lowest = section.recycle if not lowest else min(lowest, section.recycle)
    finally:
        engine.arc_override = 0
    return lowest


def MECHEVENT(
    engine: GameEngine,
    mech: Any,
    event_type: EventType,
    callback: Callable[[Event], None],
    delay: int,
    data2: Any = None,
) -> Event:
    """
    Schedule an event for a mech, matching BTMux's MECHEVENT macro.

    This is a convenience function that matches the BTMux pattern:
        MECHEVENT(mech, EVENT_TYPE, callback_func, delay, extra_data)

    Args:
        engine: The game engine
        mech: The mech entity (becomes event.data)
        event_type: Type of event
        callback: Callback function
        delay: Ticks until event
        data2: Extra data (optional)

    Returns:
        The scheduled Event
    """
    return engine.schedule_event(delay, event_type, callback, data=mech, data2=data2)
