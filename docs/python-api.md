# Python API

Use a session when you want the engine to construct a world and route ordinary
commands. Use `GameEngine` directly when your application will supply its own
entities, registries and service wiring. Both execute the same gameplay code.

Install with Python 3.12 or newer using the [getting-started guide](getting-started.md).
The distribution name is `btmux-engine`, while imports remain `tools`, `core`,
`entities`, `data`, `physics` and `systems`. The examples below use only the
standard library and the installed engine. Save any complete Python block as a
script and run it with `python -B your_script.py`.

## Start a session, command a unit and read its state

`AutopilotSession` composes the full set of gameplay and display adapters. AI is
optional: this example has one player-operated fixture unit and no controller.
Its temporary directory isolates the stores created during initialization.

```python
import json
from tempfile import TemporaryDirectory
from tools.autopilot import AutopilotSession

with TemporaryDirectory(prefix="btmux-example-") as storage:
    session = AutopilotSession({
        "hud_display": {"root": storage},
        "map": {"name": "training", "id": 1000, "size": [20, 20]},
        "units": [{"name": "Scout", "id": 1, "contact_id": "SC",
                   "at": [5, 5, 0], "started": False}],
        "random": {"seed": 7},
        "actions": [],
    })

    def command(name, args=""):
        result = session.action({
            "op": "command", "unit": "Scout", "name": name, "args": args,
        })
        if not result.get("accepted", result.get("ok", False)):
            raise RuntimeError(result)
        return result

    print(command("startup"))
    session.action({"op": "advance", "seconds": 30})
    assert session.units["Scout"].is_started

    command("heading", "90")
    command("speed", "20")
    session.action({"op": "advance", "seconds": 3})
    state = session.snapshot()
    scout = state["units"]["Scout"]
    print(json.dumps({
        "clocks": state["clocks"],
        "hex": scout["at"],
        "position": [scout["fx"], scout["fy"], scout["fz"]],
        "speed": scout["speed"],
        "desired_speed": scout["desired_speed"],
        "pending": scout["events"],
    }, indent=2))
    assert state["clocks"] == {"wall": 33, "event": 33, "global_tick": 33}
    assert scout["speed"] > 0
```

Startup is accepted immediately and completes after 30 ticks. The next three
ticks move the unit toward its requested heading and speed. The final clock
values are all 33; actual speed is about 9.675 KPH, while desired speed is 20 KPH.
The unit is still in its starting hex, but its `fx` and `fy` have changed.

`actions` is required even for interactive use. Constructors do not execute it.
To run a document's stored actions yourself, iterate them in order and call
`session.action(action)` once for each; the batch CLIs do exactly that.

## Choose an adapter and configure it

| Import | Use |
| --- | --- |
| `from tools.core_simulation import CoreSession` | Core world, movement, combat, clocks and inspection without the file-backed service composition. |
| `from tools.maps_environment import MapsSession` | Core plus map/environment administration and files. |
| `from tools.hud_status import DisplaySession` | Maps, construction, characters, communications, flight, repair/economy and HUD/display operations. |
| `from tools.autopilot import AutopilotSession` | All of the above plus built-in Battlesheep controllers and AI saves. |

The [architecture guide](architecture.md#how-sessions-compose) lists intermediate
adapters. Their schemas extend their parents; a field accepted by a later
adapter is not automatically accepted by `CoreSession`. Unknown fields are
rejected rather than silently ignored.

| Input | Purpose |
| --- | --- |
| `map` or `maps` | One map or a list of named maps; do not supply both. Supply explicit IDs for persistent references. |
| `units` | Named unit fixtures, equipment, positions, pilots and source object IDs. Omission in core creates its default unit; `[]` creates no units. |
| `config` | Simulation options such as `lock_tick`, `periodic_updates`, `extended_gunnery` and `extended_piloting`. |
| `random` | Seed, raw words or finite named inputs, configured before initialization can draw. |
| `hud_display.root` | For display/AI sessions, a common writable root. Default child roots are `characters`, `templates`, `economy` and `maps`, plus `objects.json` for discovery metadata. Explicit child-root settings take precedence. |
| `construction`, `pilots`, `repair_economy`, `file_root` | Configure those owners individually when using narrower adapters or separate storage locations. |
| `characters`, `sessions`, `autopilots` | Persistent character creation records, HUD connections, and AI controller records for the applicable adapters. |

Standard updates are enabled by default. `periodic_updates: false` skips standard
MECH/MAP update registration; it does not disable the event queue or the
heartbeat. `CoreSession` and its descendants default to an eight-second lock
delay. The narrower sensor adapter defaults to instant locks.

Broad gunnery and piloting are the defaults. Set either `extended_gunnery` or
`extended_piloting` to `true` independently to select expanded skills. These
options select skills; they do not rewrite character records.
The [core skill configuration](core-simulation-cli.md#defaults-and-fixtures)
describes these selectors.

The optional original template catalogue requires explicit setup and verification.
Enable it with `construction.catalog: true` or a directory string, while keeping
`construction.root` writable and separate. `BTMUX_TEMPLATE_CATALOG` selects the
upstream location when enabled; it does not enable the catalogue by itself.
See [catalogue integration](template-catalog-integration.md). Built-in
`data.templates` designs need no external catalogue.

### Schema reference

Use these guides for complete field and command tables:

- [Core](core-simulation-cli.md), [combat](combat-resolution-cli.md),
  [damage](damage-criticals-cli.md), and [sensors/LOS](sensors-los-cli.md).
- [Construction](construction-templates-cli.md) and [characters/personnel](pilots-cli.md).
- [Communications](communications-cli.md) and [C3](c3-communications-cli.md).
- [Aerospace](aerospace-cli.md), including [six-location fighters](six-location-aerofighters-cli.md).
- [Repair/economy](repair-economy-cli.md), [HUD/displays](hud-status-cli.md), and
  [Battlesheep AI](autopilot-cli.md).
- Map administration and environment save/load fields are defined by
  [MapsSession](../tools/maps_environment.py); the
  [encounter manifest](../examples/gameplay_scenarios/manifest.json) identifies
  runnable map scenarios.

## Actions and command results

`session.action(mapping)` is the general dispatch boundary. Common operations
are `command` (unit name, command name, arguments), `advance` (nonnegative integer
`seconds`), and `inspect` (the current snapshot). An `advance` runs complete ticks
without sleeping. A command runs immediately at the current event tick.

For composed sessions, `args` can be a raw string or an array of simple arguments.
Preserve raw strings for radio text and commands whose separators matter.
The optional `actor` selects the caller under the relevant adapter's schema:
core supports inline actor records or `"pilot"`/`"caller"`, while the pilots
composition additionally accepts persistent numeric character IDs. A caller is
distinct from the unit's seated pilot; normal command guards use that identity,
location and privileges.

Results retain each operation's contract:

| Result | How to use it |
| --- | --- |
| `{"accepted": false, "text": "..."}` | A normal gameplay refusal. Display it; time/state can still be inspected. |
| `{"ok": false, "error": "..."}` or a `message` | Another operation's refusal or input failure; some adapters also provide `error_kind`. |
| An accepted firing result with `attack` | Inspect `attack.hit` and the attack fields. Acceptance alone does not mean a hit or damage. |
| `lines`, `plain`, `message`, `text`, structured rows | Command-specific presentation data. Display sessions add plain text where applicable. |
| `blocked`, `effects_complete`, `outcome`, `applied` | Whether requested external/display effects completed. Preserve partial/refused outcomes instead of reporting every recorded request as performed. |
| A number, list, `null` or empty object | A valid result for some diagnostics, mutations or time advances; no universal success envelope is imposed. |

The first example's helper checks `accepted` with `ok` as a fallback for its three
ordinary commands. A general adapter must also keep the original result and
respect the selected operation's schema.

Core input errors normally raise `ValueError`, `KeyError`, `TypeError` or another
documented boundary exception. Later adapters catch many action errors into
result dictionaries; constructors can still raise. Do not assume a failure
rolls back prior actions or every partially performed operation. In particular,
repair queue loading reports a valid loaded prefix on malformed input.

Call `action` rather than `command` from an application. `command(unit, name, args)`
is an implementation hook and by itself bypasses the action's invocation context
and command logging. For an extension that must call a production function
directly, use `session.invoke(function, *args, **kwargs)`. To drive one complete
tick at that boundary, use `session.invoke(session.engine.process_tick)`.

## Snapshots and inspection

`session.snapshot()` and `action({"op": "inspect"})` return JSON-compatible
observations. They do not advance simulation time. In the core and composed
sessions, useful fields include:

- `time` and `clocks`, plus `heartbeat_timer` and pending `events`.
- `units[name]` with `id`, `contact_id`, `map`/`mapindex`, `at`, `fx`/`fy`/`fz`,
  speed/facing, sections/slots, weapons, pilots, messages and unit-owned events.
- `maps[name]` with map identity, roster, clock and directed LOS information;
  higher adapters add map, personnel, economy and other details.
- `random` consumption/histogram information; `session.draws` separately holds
  named draw records. `AutopilotSession` also adds `autopilots`.

Field shapes depend on the selected adapter. In particular, composed unit
snapshots use separate `fx`/`fy`/`fz` fields; the sensor-only snapshot has a
`real` array. Unit `at` always expresses the discrete coordinates in these
examples.

`session.units["Scout"]` and `session.maps["training"]` expose live objects.
Read them for a compact application view; use commands to change ordinary
gameplay state. Assigning `speed` or `target` directly bypasses the guards and
scheduled work those commands perform. Full snapshots are useful for inspection
and replay comparisons; they are not save files or visibility-filtered player
messages. A client should select observations appropriate to its actor.

## Reproducible randomness

The engine uses source-compatible MT19937 through
`core.randomness.RandomState`. Core defaults to seed 5489. Set a seed explicitly
for examples; reproduce the same initialization, command/tick order, options and
storage contents as well as the same seed.

`random` accepts one of `seed`, `array_seed` or `raw32`, plus optional `streams`.
Array seeds must be nonempty. Raw words are finite unsigned 32-bit inputs to the
generator entry points, including rejection sampling. This complete example
demonstrates both seeded rolls and a rejected raw word:

```python
from tools.core_simulation import CoreSession

def replay():
    session = CoreSession({
        "units": [{"name": "u", "started": False, "pilot": False}],
        "config": {"periodic_updates": False},
        "random": {"seed": 7},
        "actions": [],
    })
    values = [session.action({"op": "diagnose", "kind": "Roll"})
              for _ in range(4)]
    return values, session.snapshot()["random"]

assert replay() == replay()
print(replay()[0])

words = CoreSession({
    "units": [{"name": "u", "started": False, "pilot": False}],
    "config": {"periodic_updates": False},
    "random": {"raw32": [4294967295, 0]},
    "actions": [],
})
assert words.action({"op": "diagnose", "kind": "Number", "args": [1, 6]}) == 1
assert words.snapshot()["random"]["words_consumed"] == 2
```

The seeded rolls are `[3, 7, 10, 8]`. These diagnostics require a unit reference
even though the random state belongs to the engine. The stopped, unpiloted
fixture avoids initialization draws.

For focused scenarios, `random.streams` maps named consumers such as
`attack_rolls`, `pilot_rolls` or `visibility_change` to finite lists of legal
values. In core/composed sessions, supplying `streams` makes it strict: every
reached named consumer must be present, with enough values in range. Inspect
`session.draws` to discover actual names, bounds, values and `raw_words` consumed;
initial contact acquisition can consume values before the first action.

Direct MT/Number/Roll diagnostics expose consumption in `state.random` rather
than necessarily adding named-consumer rows. `config.random_state: true` adds the
generator index and 624 words to that observation. This is useful for verification,
not a general world restore API. Avoid reseeding midway through a run unless the
reseed itself is part of the recorded input.

## Embedding GameEngine directly

`GameEngine()` starts with an event queue, random state and effects service, but
without registered entities, object-type updates or generic periodics.
`wire_standard_systems(engine)` installs the normal MECH/MAP updates and enables
heartbeat. It does not construct maps, units, characters, inventory or HUD
sessions.

This complete example creates a built-in design, establishes its caller and map
membership, sends a real speed command and advances three ticks:

```python
from core.game_loop import GameEngine, wire_standard_systems
from core.randomness import RandomState
from data.templates import JUMP_MECH_TEMPLATE, create_mech_from_template
from entities.map import GameMap
from entities.mech import MechStatus
from systems.movement_commands import speed

engine = GameEngine()
engine.randomness = RandomState(seed=7)
wire_standard_systems(engine)

board = GameMap(20, 20, "training")
board._id = 1000
board.grav = 100
board.visibility_config = "30 2 0 0 200"
engine.register_entity(board)

unit = create_mech_from_template(JUMP_MECH_TEMPLATE, name="Scout")
unit._id = 1
unit.pilot._id = 10001
unit.pilot.location = unit._id
unit.command_actor = unit.pilot
unit.set_hex_position(5, 5, 0)
unit.set_status(MechStatus.STARTED)
board.add_mech(unit)
engine.register_entity(unit)

ticks = []
engine.on_tick(ticks.append)
ok, message = engine.inject_command(
    unit.pilot,
    lambda: speed(engine, unit, "20", caller=unit.pilot),
    label="speed 20",
)
assert ok, message
engine.run_ticks(3)
assert ticks == [1, 2, 3]
assert engine.tick == engine.global_tick == 3
print(engine.tick, unit.speed, unit.x, unit.y)

board.remove_mech(unit)
engine.unregister_entity(unit)
engine.unregister_entity(board)
```

`create_mech_from_template` supplies sections, equipment and a pilot.
`MechStatus.STARTED` establishes the starting fixture here; a gameplay startup
command would schedule its normal startup stages. Map visibility and gravity
are set explicitly because a bare `GameMap` has source-style zero defaults for
those fields.

For a full application, also attach the relevant personnel, inventory, template
and discovery services, or use a session to do it. Numeric IDs must remain unique.
Adding only to a session's name dictionary does not register an object; registering
only with the engine does not attach it to a map or to personnel.

### Registration and scheduling methods

| Method | Contract |
| --- | --- |
| `register_entity(entity)` / `unregister_entity(entity, cancel_events=True)` | Track an object; unregister normally cancels events whose primary owner is that object. Maintain map/personnel membership separately. |
| `get_entities()` | List registered live objects in registration order. |
| `register_object_type(name, update_time, update_fn)` | Call `update_fn(engine, entity)` for matching `xcode_type` (or uppercased class name) through the simulated-wall-time modulo gate. Zero disables that type's update. |
| `register_periodic(name, interval, callback)` | A generic `callback(engine)` with a positive interval and the same modulo gate; returns an enabled/disabled `PeriodicUpdate` record. |
| `schedule_event(delay, event_type, callback, data=None, data2=None)` | Return an `Event`. Delay is at least one tick; callback receives that event. Use `EventType` from `core.events`. |
| `cancel_events_for(entity)` / `cancel_events_of_type(kind, entity=None)` | Cancel matching events. `Event.cancel()` also marks one event canceled. |
| `has_event(kind, entity)` / `event_time_remaining(kind, entity)` | Query scheduled work; absent work has no remaining-time value. |
| `on_tick(callback)` | Call `callback(event_tick)` after each dispatch iteration, before the following heartbeat. |
| `inject_command(actor, fn, label="")` | Run a zero-argument function immediately under engine randomness and return its result; append a command-log record after successful return. |

`engine.events.pending_events()` exposes actual pending events. Their
`event_type`, `tick`, `data` and `data2` describe category, deadline and ownership.
Equal deadlines are not a FIFO guarantee. See [clock behavior](architecture.md#dispatch-heartbeat-and-map-clocks)
before using independent clock methods.

### Running and stopping

| Method | Effect |
| --- | --- |
| `process_tick()` | One dispatch followed by one enabled heartbeat; no sleep. Returns `(events_run, periodics_run)` from dispatch. The second count covers generic periodics, not object sweeps. |
| `run_ticks(count)` | `count` complete ticks without wall-clock delays; returns `None`. |
| `await engine.run(max_ticks=N)` | Paced asynchronous loop. Use a positive tick limit or omit it to run until stopped. |
| `run_sync(max_ticks=N)` | Blocking wrapper around `asyncio.run(engine.run(...))`; use outside an already running asyncio loop. |
| `stop()` | Set the running-loop state to stopped. It does not cancel pending events or prevent later manual ticks. |
| `pause()` / `resume()` | Change the state flag. The async loop has no suspended waiting phase: a pause can make it exit and finalize as stopped. Use application-owned pacing for a resumable pause. |
| `dispatch(now=None)`, `heartbeat()`, `skip_seconds(seconds)` | Independent source-clock controls for timing tests or specialized hosts. They are not substitutes for an ordinary complete tick. |

`tick_duration` controls real-time pacing in `run` (default 1.0 seconds), not the
amount of simulation time per tick. A custom client loop should own pacing or
use `run`, rather than driving both simultaneously. Manual `run_ticks` works
regardless of the running-loop state.

## Persistence entry points

Choose writable, application-owned roots. Reusing a root intentionally reuses
its records; for independent runs use fresh roots as above. For a new process,
recreate the associated unit IDs, design/live unit state, actors and service
configuration before restoring subsystem references. Avoid resupplying creation
records or initial attribute overrides when you intend to retain existing data.

| Owner | Session entry points / Python owner | Saved scope |
| --- | --- | --- |
| Map terrain | `map_command` with `name: "save"`/`"load"` and filename `args`; `systems.map_management.save_file/load_file` | Terrain file. Not a whole combat state. |
| Map object/dynamic records | `map_file` with `kind: "save_objects"`/`"load_objects"` or `"save_dynamic"`/`"load_dynamic"`; `entities.map_objects` and `entities.map_storage` | Object lists or roster/flag/LOS bytes. Dynamic load needs external `count` and existing unit identities. |
| Environment snapshot | `map_command` with `name: "environment.save"`/`"environment.load"`; `systems.environment_storage.save_snapshot(engine, boards)` / `load_snapshot(engine, document)` | Version 1 map terrain, objects, dynamic records, weather/layers, supported environmental callbacks and relative deadlines. Does not save live unit/character or RNG state. |
| Construction | `template` with `kind: "save"`/`"load"`, `reference` and `unit`; `data.template_directory.TemplateDirectory` | Design templates. Modern saves use design armor/full ammunition, so they are not damage checkpoints. |
| Characters | `character` with `kind: "save"`/`"reload"`; `data.characters.CharacterStore` | Character records, stats/skills and stored metadata. Most changes persist as they occur. |
| Economy | `repair` with `kind: "persist"`; `systems.economic_inventory.InventoryStore` | Inventory and technician attributes in its `objects.json`; normal writes persist too. |
| Repair work | `repair` with `kind: "save"`/`"load"` and optional `file`; `session.repair_jobs.save()/load(text)` | Repair queue records only. Load once into a fresh queue: loading appends jobs, can retain a valid prefix on error, and does not repeat costs/rolls/XP. |
| Discovery/attributes | `core.object_services.ObjectRegistry` and `core.attributes.AttributeStore` | Durable metadata/attributes; an application resolver supplies live unit objects. |
| AI | `ai_save`/`ai_load` with `file`; `systems.autopilot_storage.save_snapshot(engine, controllers=None)` / `load_snapshot(engine, document, preflight=None)` | Version 2 controller identity, attachment, scalar state, commands, supported callbacks, relative deadlines and scheduler-layout information. |

Environment loading validates candidate data before publication and replaces the
restored maps' owned events with the supported saved environmental callbacks.
Include all required maps and links. Unsupported map-owned callback types are
not general-purpose checkpoint data.

AI loading validates before replacing controllers/callbacks. Paths and weapon
profiles rebuild through ordinary callbacks; matching unrelated world callbacks
remain owned by their original systems. AI load does not rewind clocks, random
state, movement or damage. Use the session action when working with
`AutopilotSession` so its public controller-name dictionary updates too.
[AI persistence details](autopilot-cli.md#ai-persistence-and-inspection) describe
version and callback constraints. [Repair persistence](repair-economy-cli.md#fixture-and-persistence-controls)
has different, source-compatible load behavior.

Here is a complete map/AI save-and-reload example. Both files live beneath the
session's map file root. The assertions show that restoring these owners does
not restore the unit's earlier position or rewind event time.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from tools.autopilot import AutopilotSession

with TemporaryDirectory(prefix="btmux-save-") as storage:
    session = AutopilotSession({
        "hud_display": {"root": storage},
        "map": {"name": "field", "id": 1000, "size": [20, 20]},
        "units": [{"name": "Scout", "id": 1, "at": [5, 5, 0]}],
        "autopilots": [{"name": "ScoutAI", "id": 200, "unit": "Scout",
                       "commands": ["goto 8 5"]}],
        "random": {"seed": 7},
        "actions": [],
    })
    saved_map = session.action({
        "op": "map_command", "name": "environment.save",
        "args": {"file": "field.json", "maps": [1000]},
    })
    assert saved_map["version"] == 1, saved_map
    saved_ai = session.action({"op": "ai_save", "file": "ai.json"})
    assert saved_ai["ok"], saved_ai

    session.action({"op": "advance", "seconds": 2})
    unit = session.units["Scout"]
    before = (session.engine.tick, unit.fx, unit.fy, unit.fz)
    loaded_map = session.action({
        "op": "map_command", "name": "environment.load",
        "args": {"file": "field.json"},
    })
    assert loaded_map["version"] == 1, loaded_map
    loaded_ai = session.action({"op": "ai_load", "file": "ai.json"})
    assert loaded_ai["ok"], loaded_ai
    assert (session.engine.tick, unit.fx, unit.fy, unit.fz) == before
    assert (Path(storage) / "maps" / "ai.json").is_file()
    print(loaded_ai)
```

Use short plain filenames for the inherited map/AI file interface; it takes a
basename and truncates names to 30 characters. Other storage owners have their
own path rules. The example's files disappear on leaving the temporary-directory
context. For durable use, configure a persistent root and retain the rest of the
world through its appropriate owners or a reproducible scenario plus input log.

Continue with [client integration](client-integration.md) for transport,
notifications and actor-specific views, or [CONTRIBUTING](../CONTRIBUTING.md) for
tests and source conventions.

