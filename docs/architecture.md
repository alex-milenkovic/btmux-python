# Architecture

BTMux Engine runs the simulation in Python: commands change live units and schedule
work, the engine advances that work, and clients read the resulting state. A
session from `tools` assembles these pieces into a usable world. It does not start
a background loop or provide a network server.

Start with the [Python API](python-api.md) for runnable examples, or
[client integration](client-integration.md) for a presentation adapter. The
[C-to-Python guide](porting/C_TO_PYTHON.md) describes source correspondence and
compatibility choices.

## Source layout

| Directory | Responsibility and useful entry points |
| --- | --- |
| [core](../core/) | Scheduling and shared services: [game loop](../core/game_loop.py), [events](../core/events.py), [randomness](../core/randomness.py), [attributes](../core/attributes.py), [object discovery](../core/object_services.py), and [effects](../core/effects.py). |
| [entities](../entities/) | Mutable simulation objects: `Mech` and its sections/critical slots, `GameMap`, pilots, vehicles, weapons, and `Autopilot`. Also map-object and binary map-storage structures. |
| [data](../data/) | Built-in designs, equipment tables, template readers/directories, optional catalogue configuration, and persistent character records. |
| [physics](../physics/) | Hex geometry, continuous motion, collision, jumps, flight, terrain, weather, flooding, and path costs. See [path-cost semantics](path_costs.md). |
| [systems](../systems/) | Gameplay commands and services: startup, heat, sensors/LOS, targeting, attacks, damage, communications, personnel, construction, repairs, displays, and Battlesheep AI. |
| [tools](../tools/) | Python session adapters and module CLIs. They validate input, assemble dependencies, call production systems, and serialize observations. |
| [tests](../tests/), [hardening](../hardening/), [properties](../properties/) | Focused behavioral checks and fixtures. |
| [features](../features/), [acceptance](../acceptance/), [qa](../qa/), [specs](../specs/) | Executable feature definitions/bindings, independent checks, optional C oracles, and source mappings. See [QA prerequisites](../qa/README.md). |
| [examples/gameplay_scenarios](../examples/gameplay_scenarios/) | Command-driven encounters, their interface manifest, and [AI encounters](../examples/gameplay_scenarios/AI.md). |

The distribution is named `btmux-engine`; imports retain the top-level names
`core`, `entities`, `data`, `physics`, `systems`, and `tools`. Normal execution
uses the standard library. These directories describe responsibilities, not a
strict one-way import hierarchy: systems share domain objects and call each other
at gameplay boundaries.

## Who owns the world?

There is no single serialized “world” object. A session holds the cooperating
owners:

| Owner | What it keeps |
| --- | --- |
| `session.engine` | Clocks, pending events, registered live entities, object-type update handlers, randomness, and local effects. |
| `session.units`, `session.maps` | Public name-to-object dictionaries. `session.map` is the first/default map. |
| Each `GameMap` | Terrain/elevation, environmental state, ordered unit roster, and directed line-of-sight (LOS) cache. LOS answers are viewer-to-target, so the reverse direction can differ. |
| Each unit | Position, speed, facing, status flags, sections, critical slots, pilot references, targets, heat, and other live gameplay state. Critical slots are authoritative for equipment and weapon enumeration. |
| `session.personnel` | Live numeric-ID registry and containment: which actors/units/objects are inside which objects. |
| `session.characters`, `session.directory`, `session.inventory` | Character records, construction templates, and inventory/technician attributes, respectively. |
| `engine.object_registry` in display sessions | Durable discovery/containment metadata plus a resolver for live objects; it is not a serializer for an entire unit. |
| `session.autopilots` | Named built-in AI controllers, also registered with the engine and personnel services. |

Several identities coexist. A session name such as `"Scout"` selects a unit in
an action; its numeric `_id` is the source-style object identity used by gameplay
references. A two-character contact ID such as `"SC"` is for player targeting and
radio commands. A roster slot (`mapnumber`) is neither of those identities.
The engine's internal entity dictionary uses Python `id(entity)` to retain live
objects; that address must not be used as a client or saved-game ID.

Map membership and engine registration serve different purposes.
`board.add_mech(unit)` installs map membership and associated roster/LOS state;
`engine.register_entity(unit)` makes it available to the scheduler and heartbeat.
Registration also connects `_engine`, arms map environmental work, and starts
possible-LOS checks for an already started, mapped unit. Use
`board.remove_mech(unit)` and `engine.unregister_entity(unit)` when removing an
object at this level; unregistering alone does not remove its map roster entry.
Higher-level personnel and transfer operations keep their additional registries
in step. See [manual registration](python-api.md#embedding-gameengine-directly).

## How sessions compose

Each arrow below means “the class on the right subclasses the class on the left.”
The complete chain ends in `AutopilotSession`:

```text
SensorSession -> DamageSession -> CombatSession -> CoreSession
 -> MapsSession -> ConstructionSession -> PilotsSession
 -> CommunicationsSession -> AerospaceSession -> RepairEconomySession
 -> DisplaySession -> AutopilotSession
```

| Adapter | Module and additions |
| --- | --- |
| `SensorSession` | [tools.sensors_los](../tools/sensors_los.py): map/unit setup, sensing, movement commands, named draws, action invocation. |
| `DamageSession` | [tools.damage_criticals](../tools/damage_criticals.py): sections/criticals, damage operations, session-scoped weapon metadata, richer unit snapshots. |
| `CombatSession` | [tools.combat_resolution](../tools/combat_resolution.py): firing, physical attacks, ammunition/modes, combat configuration. |
| `CoreSession` | [tools.core_simulation](../tools/core_simulation.py): multiple maps, explicit IDs/actors, source randomness, clocks, core commands and diagnostics. |
| `MapsSession` | [tools.maps_environment](../tools/maps_environment.py): map administration, local files, weather/layers and environment saves. |
| `ConstructionSession` | [tools.construction_templates](../tools/construction_templates.py): template directories, catalogue access and live editors. |
| `PilotsSession` | [tools.pilots](../tools/pilots.py): persistent characters, personnel, personal combat and experience. |
| `CommunicationsSession` | [tools.communications](../tools/communications.py): radios, C3 and network commands. |
| `AerospaceSession` | [tools.aerospace](../tools/aerospace.py): aircraft, bays, turrets and related operations. |
| `RepairEconomySession` | [tools.repair_economy](../tools/repair_economy.py): stock, technicians, repair queues, cargo and towing. |
| `DisplaySession` | [tools.hud_status](../tools/hud_status.py): HUD connections, displays, object discovery and display-result formatting. |
| `AutopilotSession` | [tools.autopilot](../tools/autopilot.py): built-in Battlesheep controllers, orders/radio behavior, AI snapshots and saves. |

A subclass consumes its extra document fields, calls the parent constructor, and
adds its services. Its `action` and `command` methods handle their own operations
and delegate the remainder. This is one shared engine and object graph, not a
stack of separate simulations. Higher adapters inherit core defaults unless
their own schemas override them. The standalone movement
`tools.movement.Session` and heat `tools.heat_updates_session.Session` form a
separate chain; their inputs and run methods are different.

For a general client, `AutopilotSession` supplies the full composition even with
no AI controllers. For an isolated combat calculation, `CoreSession` avoids the
file-backed construction/personnel/economy services. Choose the narrowest adapter
that supplies the operations your application needs.

## Scenario initialization

A scenario document specifies maps, units, configuration, random inputs and an
`actions` array. Construction validates the schema, makes the engine and initial
map, creates units, sets membership/identities, applies the additional maps and
actor records, then acquires initial contacts. The fuller sessions also open
their configured local stores and attach personnel/controllers.

The constructor requires `actions` but does not execute it. Python callers can
pass `[]` and call `session.action(...)` later. A batch CLI explicitly iterates
the document's action list after construction, then emits results and a snapshot.

Core defaults include a clear 12-by-12 map, one started 50-ton fixture unit with
no weapons, broad gunnery/piloting skills, an eight-second lock delay, standard
updates, and source MT seed 5489. Such a fixture is useful for a small simulation;
load or instantiate a design when a particular equipment layout matters.
Initial contact acquisition can consume randomness, so supply the seed before
construction. Set writable roots before opening a full session; initialization
itself can write records.

## From a command to observable state

For example, a `speed` command follows this path:

```text
session.action({"op": "command", "unit": "Scout", "name": "speed", "args": "20"})
  -> session.invoke(engine.inject_command, ...)
  -> session.command(unit, "speed", "20")
  -> systems.movement_commands.speed
       checks caller and unit state
       changes desired_speed and starts a MOVE event
  -> result returned immediately

session.action({"op": "advance", "seconds": 1})
  -> session.invoke(engine.run_ticks, 1)
  -> engine.process_tick()
  -> dispatch -> due events -> physics.movement.mech_move_event
       updates actual motion, terrain transitions and related consequences
  -> object updates -> heartbeat
  -> snapshot / display queries / delivered notices expose the result
```

An accepted command need not have completed its effect: startup takes scheduled
stages, turning/motion progresses over ticks, and repairs have deadlines.
Similarly, a firing command can be accepted and miss. The firing route through
`CombatSession.command` enters `systems.combat_firing.fire_command` and then the
combat, impact, missile, damage and critical services as applicable. It produces
an attack result, changes live equipment/heat/durability, and delivers gameplay
messages. Read the actual result and subsequent state instead of inferring
success from the command text.

`session.invoke` supplies the simulation's random/draw context and temporary
weapon metadata overrides. It also catches printed engine diagnostics as an
input error. Direct system calls from a session extension should go through this
boundary. Keep mutations and observations serialized; session invocation also
uses process-wide stdout redirection and temporarily shared catalogue entries.

## Dispatch, heartbeat and map clocks

A tick normally represents one simulated second. There are several distinct
counters, retained to match source timing:

| Clock or counter | Meaning |
| --- | --- |
| `engine.sim_now` | Simulated wall-clock seconds, the analogue of C `mudstate.now`. |
| `engine.muxevent_tick` / `engine.tick` | Event scheduler time. Advanced by dispatch iterations; event deadlines use this value. |
| `engine.global_tick` | Heartbeat invocation count, incremented only by `heartbeat()` and wrapped to 32 bits. |
| `board.current_tick` | Map clock stamp refreshed from event time by `map_update`. A fixture can initialize it separately; it can remain stale with map updates disabled. |

`process_tick()` first calls `dispatch()` and then, when enabled, `heartbeat()`.
Within dispatch, due events run before the object-type sweep, generic registered
periodics, and `on_tick` callbacks. The normal object wiring updates `MECH` every
two simulated wall seconds and `MAP` every second. Movement is a per-unit,
self-rearming event chain, not a global movement periodic. Map updates stamp the
map clock, refresh LOS, and reread visibility/weather configuration every 25
event ticks; fire/smoke and other environmental work have their own events.

The heartbeat rearms its timer, visits registered objects by ascending source
object ID, dispatches MECH/AUTO work, then increments `global_tick`. Weapon and
section recycling use elapsed event time, not a count of heartbeat calls.
General-unit AI runs sensor, conditional profile, then gun services here;
historical Aerospace AI uses its own callback chains.

Explicit `dispatch(now)` models delayed source dispatch: the first invocation
runs once, subsequent catch-up is capped at 20 iterations, and `sim_now` remains
frozen for the entire catch-up. The modulo gate therefore has source-specific
behavior: a two-second update runs on every catch-up iteration if the frozen
second is even, and on none if it is odd. Heartbeat has no comparable catch-up.
For ordinary playback, use `process_tick` or `run_ticks`; reserve independent
`clock` operations for timing experiments.

Commands execute immediately between ticks through `inject_command`. There is no
engine input queue. The event heap orders by deadline only; equal-deadline
callbacks have no promised FIFO order. Preserve insertion/cancellation behavior
when replaying or extending scheduling code.

## Reproducible input

[core.randomness](../core/randomness.py) owns one source-compatible MT19937 state
per engine. Engine dispatch, heartbeat and injected commands establish that
state as their active context. Sessions additionally record named consumers and
can supply finite input streams.

A scalar seed reproduces a run with the same initial world, command sequence,
clock advances and storage inputs. Finite named streams let a focused example
choose dice without replacing the gameplay calculation. Missing, exhausted or
out-of-range inputs are errors when streams are explicitly supplied.
[Python randomness examples](python-api.md#reproducible-randomness) explain the
difference between named draws and raw generator words.

## Persistence and external services

Persistence belongs to individual owners: terrain/map objects and environment
snapshots; design templates; character records; inventory attributes; repair
queues; object-discovery metadata; and AI controllers with their owned callbacks.
An inspection snapshot is a JSON observation, not a universal restart image.

Environment and AI saves preserve their supported relative deadlines. AI reload
rebuilds transient paths/profiles and does not rewind unit movement, damage,
clocks or randomness. Repair queue load adds jobs to the current queue and has
different failure semantics from validated AI loads. Use the
[persistence entry points](python-api.md#persistence-entry-points) to select and
restore each owner deliberately.

`engine.effects` implements local notifications, channels, logs and registered
hooks. `ObjectRegistry` can resolve live objects through a supplied loader.
MUX expression evaluation and remote services require explicitly configured
adapters; a recorded `applied: false` effect is an observation of an unfulfilled
request. These boundaries let a client add transport and storage while retaining
the same gameplay systems. See [notifications and results](client-integration.md#results-notifications-and-errors)
and the [compatibility guide](porting/COMPLETION.md).

