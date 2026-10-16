# Client integration

A client supplies presentation, input transport and a policy for advancing time.
The engine owns unit/map state and gameplay decisions. Embed a
`tools.autopilot.AutopilotSession` for the full composition, or a narrower
[Python session](python-api.md#choose-an-adapter-and-configure-it) when fewer
services are needed.

There are two distinct process interfaces: the engine's batch JSON CLI and a
separate consumer's long-lived JSON-lines adapter. The engine package does not
turn `python -m tools.autopilot` into a continuous server.

## The engine contract a client needs

| Responsibility | Interface |
| --- | --- |
| Initialize | Construct a session from a scenario document, including `actions: []`, maps, units, caller/character setup, configuration and random inputs. Choose writable storage roots first. |
| Submit a command | `session.action({"op": "command", "unit": name, "name": command, "args": text})`. A command executes immediately, without advancing time. |
| Advance time | `session.action({"op": "advance", "seconds": n})`, or `session.invoke(session.engine.process_tick)` for one complete tick. |
| Read state | `session.snapshot()` / `{"op": "inspect"}` for inspection; live objects and display/HUD queries for a compact actor-specific view. |
| Receive output | Keep each action's result and connect an actor's notification sink with `engine.effects.connect_client(actor, send, render=None)`. |
| Persist | Call the relevant map, character, template, economy, repair or AI owner. An inspection snapshot is not a universal restore file. |

The session constructor does not run its `actions` array and starts no background
timer. Application code owns both subsequent calls and their order. Use a single
simulation owner for commands, ticks, persistence and state projection. A reader
thread may queue input, but should not mutate the session concurrently.

When creating actors manually, populate their identity/location and register
the unit in every service your composition uses. The
[direct-engine example](python-api.md#embedding-gameengine-directly) explains the
basic map/engine distinction. Persistent player resolution belongs to
`systems.hud.player_unit` and the personnel registry; a controlled unit can change
after ejection, boarding or disembarking.

## Batch JSON execution

`tools.core_simulation` and `tools.autopilot` each read one complete JSON document,
execute its ordered `actions`, write one JSON result document, and exit. Use
`--input FILE` or stdin; stdin must reach EOF. Newline-delimited requests are not
multiple batch requests.

Save this complete input as `scenario.json`:

```json
{
  "map": {
    "size": [
      20,
      20
    ]
  },
  "units": [
    {
      "name": "Scout",
      "id": 1,
      "at": [
        5,
        5,
        0
      ],
      "started": false
    }
  ],
  "random": {
    "seed": 7
  },
  "actions": [
    {
      "op": "command",
      "unit": "Scout",
      "name": "startup"
    },
    {
      "op": "advance",
      "seconds": 30
    },
    {
      "op": "command",
      "unit": "Scout",
      "name": "speed",
      "args": "20"
    },
    {
      "op": "advance",
      "seconds": 3
    }
  ]
}
```

Run it with:

```sh
python -B -m tools.core_simulation --input scenario.json
```

A subprocess caller can instead send the serialized document on stdin and close
that input stream. The output has `results` in action order, the final `state`,
and named `draws`. This input finishes at event tick 33. Use
`tools.autopilot` for a document containing AI controllers; see the
[scenario guide](running-scenarios.md) and [AI schema](autopilot-cli.md).

Check both process status and action results. A gameplay refusal can be a valid
result with exit status zero. The core CLI reports invalid input on stderr and
exits nonzero; the AI CLI uses a structured stderr error for outer failures.
Full-session adapters catch many individual action errors into `results` and can
continue, so a zero exit status alone is not proof that every action succeeded.
Earlier successful actions are not rolled back.

Other module CLIs have their own contracts: the standalone movement tool uses
`--script`, the heat tool requires `--input`, and `tools.path_cost` accepts direct
query arguments. Do not assume they all share core/AI stdin behavior.

## Existing continuous client execution path

The separate Godot consumer starts one long-lived Python process and communicates
through pipes. Its bootstrap uses `BTMUX_ENGINE_ROOT` to select a source checkout
and verifies that the expected engine entry point exists. That variable belongs
to the consumer bootstrap, not the engine package API. An installed-package
adapter can use ordinary imports, as in the portable example below.

The runtime constructs a `LiveSession(AutopilotSession)`, creates its maps/units
and actor, attaches services, and keeps that session alive between requests.
The subclass suppresses batch event/heartbeat observation traces and routes
torso-rotation aliases to the existing maneuver command. The runtime translates
console input to ordinary `session.action` commands and projects the result for
the client. Client-specific presentation and convenience controls stay in this
adapter.

The Godot bridge owns process startup/shutdown, stdin writes, stdout/stderr
draining and reconnect. It buffers incomplete stdout data until a newline,
decodes each JSON object, and waits for a `hello` message before accepting input.
Python owns ticking. A bounded input queue feeds the same runtime loop that
executes commands and advances one complete simulated second at a time.

### Sequencing on the wire

The current consumer uses these conventions; they are an adapter protocol, not
the batch CLI schema:

| Direction/message | Meaning |
| --- | --- |
| Client `{"id": 17, "command": "speed 20"}` | A command request. The bridge increments its request counter before writing a complete line and flushing. |
| Runtime `hello` | A fresh session identity, actor/unit identity and timing information. |
| Runtime `notice` | Delivered text, independently of whether a request is awaiting its reply. |
| Runtime `reply` | `request` echoes the request `id`; `ok`/`accepted` and `lines` report the ordinary command outcome. |
| Runtime `pose` | Compact current player/visible-world state. A map-activation message precedes the first pose on a newly active map. |
| Runtime `timing` | Changed wall-time pacing information. |
| Runtime `error` | Invalid requests or runtime/connection failures; not every error has a request ID or a completed-session envelope. |

Packets emitted by a running runtime carry `session`, increasing `seq`, and the
current engine `tick`. Request IDs identify client operations; sequence numbers
order emitted packets. Neither is the event tick. Several packets can share a
tick, and unsolicited notices/poses can arrive between replies.

For a normal single-command dispatch, the runtime collects addressed notices,
sends them, sends its reply, and then projects current state. It suppresses reply
text already delivered as a notice by that particular command, while retaining
repeated notice events. Convenience operations can emit additional replies or
timing messages; correlate by message type and request, rather than treating the
next stdout line as the answer.

Reset constructs a new session identity and restarts packet sequence numbering.
Reconnect starts a new process/session; it does not implicitly resume a saved
world. On a new `hello`, discard stale interpolation, selection and outstanding
request state. Request IDs provide correlation, not duplicate suppression:
replaying a command after an uncertain disconnect can execute it again.

### Who advances time?

The current continuous runtime calls
`session.invoke(session.engine.process_tick)` from a monotonic wall-clock loop.
One call advances one simulated second. Its time-compression setting changes
the wall interval between complete steps: at 2×, a tick is paced every 0.5 wall
seconds. It does not pass a fractional simulation delta into the engine.
The runtime rebases pacing after a long suspension to avoid a burst of catch-up
steps.

A different adapter may use explicit client-issued advances, as below. Choose one
owner and policy. Do not run `engine.run()` and also advance the same session from
a render callback. For pause, stop issuing manual ticks; the engine's async
`pause` flag is not a persistent suspended loop. See
[run/tick methods](python-api.md#running-and-stopping) and
[clock semantics](architecture.md#dispatch-heartbeat-and-map-clocks).

## A portable JSON-lines adapter

The following is an executable example of an application-owned protocol. Save it
as `bridge_example.py` and run `python -u -B bridge_example.py` after installing
the engine. It needs no separate client checkout, map file, catalogue or third-party
library. It defines its own `command`/`advance`/`state`/`quit` requests; these
requests are not accepted directly by the engine's batch CLI or identical to the
Godot consumer's wire format.

This adapter keeps one session, permits five ordinary commands, sends addressed
notices, returns the original command result, and emits a compact view of its
one controlled unit. Time advances only on an `advance` request.

```python
import json
import sys
import uuid
from tempfile import TemporaryDirectory

from systems.armor_display import plain
from tools.autopilot import AutopilotSession
from tools.combat_resolution import reject_constant, unique_fields

# This example disables observation traces, not gameplay callbacks.
class ClientSession(AutopilotSession):
    def observe_event(self, *args):
        pass

    def observe_heartbeat(self, *args):
        pass

with TemporaryDirectory(prefix="btmux-client-") as storage:
    session = ClientSession({
        "hud_display": {"root": storage},
        "map": {"name": "training", "id": 1000, "size": [20, 20]},
        "units": [{"name": "Scout", "id": 1, "contact_id": "SC",
                   "at": [5, 5, 0], "started": False}],
        "random": {"seed": 7},
        "actions": [],
    })
    notices = []
    actor = session.units["Scout"].command_actor
    session.engine.effects.connect_client(actor, notices.append, render=plain)
    session_id = uuid.uuid4().hex
    sequence = 0

    def emit(kind, **fields):
        global sequence
        sequence += 1
        print(json.dumps(dict(
            fields, type=kind, session=session_id,
            seq=sequence, tick=session.engine.tick,
        ), allow_nan=False), flush=True)

    def flush_notices():
        for notice in notices:
            emit("notice", text=plain(notice), recipient=actor._id)
        notices.clear()

    def view():
        unit = session.units["Scout"]
        return dict(
            unit_id=unit._id, map_id=unit.mapindex,
            contact_id=unit.contact_id, at=[unit.x, unit.y, unit.z],
            position=[unit.fx, unit.fy, unit.fz], facing=unit.facing,
            speed=unit.speed, desired_speed=unit.desired_speed,
            started=unit.is_started, heat=unit.heat,
        )

    allowed = {"startup", "shutdown", "speed", "heading", "status"}
    emit("hello", actor_id=actor._id, unit_id=1)
    emit("state", view=view())
    for line in sys.stdin:
        if not line.strip():
            continue
        request = None
        try:
            message = json.loads(
                line, object_pairs_hook=unique_fields,
                parse_constant=reject_constant,
            )
            if not isinstance(message, dict):
                raise ValueError("Request must be an object")
            request = message["id"]
            if type(request) is not int or request < 1:
                raise ValueError("id must be a positive integer")
            op = message["op"]
            if op == "quit":
                emit("reply", request=request, ok=True, result={})
                break
            if op == "command":
                name = message["name"]
                args = message.get("args", "")
                if not isinstance(name, str) or name not in allowed:
                    raise ValueError("Unsupported command")
                if not isinstance(args, str):
                    raise ValueError("args must be text")
                result = session.action(dict(
                    op="command", unit="Scout", name=name, args=args,
                ))
            elif op == "advance":
                seconds = message["seconds"]
                if type(seconds) is not int or not 0 <= seconds <= 60:
                    raise ValueError("seconds must be an integer from 0 to 60")
                result = session.action({"op": "advance", "seconds": seconds})
            elif op == "state":
                result = {}
            else:
                raise ValueError("Unsupported operation")
            flush_notices()
            ok = result.get("accepted", result.get("ok", True))
            emit("reply", request=request, ok=bool(ok), result=result)
        except (ValueError, TypeError, KeyError, IndexError, OSError, OverflowError) as error:
            flush_notices()
            emit("error", request=request, msg=str(error))
        emit("state", view=view())
```

Send these lines on stdin. The first speed request is refused because the
reactor is stopped; after startup and 30 ticks, the second succeeds.

```jsonl
{"id":1,"op":"command","name":"speed","args":"20"}
{"id":2,"op":"command","name":"startup"}
{"id":3,"op":"advance","seconds":30}
{"id":4,"op":"command","name":"speed","args":"20"}
{"id":5,"op":"advance","seconds":3}
{"id":6,"op":"state"}
{"id":7,"op":"command","name":"diagnose"}
{"id":8,"op":"quit"}
```

Request 7 demonstrates a transport error for an unsupported command. Request 8
replies and ends the loop; EOF also closes it. At request 6, the tick is 33 and
speed is positive. Every emitted line is JSON; partial reads still need
buffering on the receiving side.

The example's storage is intentionally temporary and its command surface small.
For an enduring application, choose durable roots, resolve the controlled unit
from the actor on each request, and add the commands/views you need. Keep
application logs on stderr. Bound retained observation history for a long-lived
process; disabling the two observers does not stop all other diagnostic lists
from growing. Preserve event queues, random state and gameplay histories while
managing those observations.

## Results, notifications and errors

There are three separate questions to answer:

1. Did the transport parse and route the request?
2. Did the gameplay command accept it?
3. Did its eventual gameplay effect complete, and what happened?

`accepted: true` can mean startup was scheduled, a turn was requested or a shot
was fired and missed. Show the command's reply promptly, then render authoritative
state and later notices. Do not predict a hit, teleport to a destination or finish
a repair merely because the input was accepted.

Use `accepted` when present, otherwise the operation's `ok` and structured result.
Preserve `error`/`error_kind` and external-effect fields such as `blocked`,
`effects_complete`, `outcome` or `applied`. An external request marked
`applied: false` has not performed the persistent/remote action. Refused commands
and malformed requests should leave the connection usable when the adapter can
continue; an engine exception may follow partial mutation, so inspect current
state before choosing recovery behavior.

`engine.effects.connect_client(actor, callback, render=plain)` receives
notifications addressed to that actor through the engine's notification system.
`systems.armor_display.plain` removes source color markup; a richer client can
supply its own renderer. The portable example retains both the original result
and notices; a UI can suppress only matching reply copies from the same command.
Do not concatenate every unit's diagnostic log into a player's feed.

Full `snapshot()` output contains administrative information about units,
contacts, callbacks and stores. For player views, use the existing contact,
status and HUD services and apply their identification/visibility results.
[HUD queries](hud-status-cli.md) expose structured records and optional legacy
`wire` text with CRLF. A `HudSession` connection key is separate from a runtime's
session token or a unit identity.

## Identifiers and coordinates

| Value | Interpretation |
| --- | --- |
| Session unit name | Dictionary key for `action.unit`. Keep the key distinct from a mutable display name. |
| Numeric unit/actor/map ID | Stable source-style identity, `_id` internally. Unit IDs are positive; map IDs are nonnegative and must not collide with units. |
| Contact ID | Two-character player-facing token for targeting/radio; read it from current state rather than deriving it from an object ID. |
| `mapnumber` | A map roster slot, which can change on transfer. |
| `at: [x, y, z]` | Integer map column, row and elevation level. |
| `fx`, `fy`, `fz` | Continuous engine coordinates, not metres, pixels or a renderer's world units. |
| `speed` / `desired_speed` | Actual/requested speed in KPH for ordinary movement commands. |
| `facing` / `desired_facing` | Headings in degrees: nominal north 0, east 90, south 180, west 270. |

Use [physics.hexmath](../physics/hexmath.py) conversions:
`hex_to_float(x, y)` returns the engine-space centre and `float_to_hex(fx, fy)`
resolves its cell. Even-numbered columns are offset downward by half a hex;
increasing `y` runs south. `SCALEMAP` is 322.5 engine units per hex height and
`ZSCALE` is 64.5 per elevation level. Use engine helpers for range, bearing and
boundary ties rather than substituting an axial-grid formula.

Project those coordinates into your chosen render axes and scale at the client
boundary. Interpolate between received positions for display. Collisions,
crossings, LOS and target validity remain engine results. After a map transfer,
activate the destination map before applying its first position; a map change
can occur within the same persistent session.

Weapon numbers and JSON section/slot indices are zero-based; template/editor
slots are one-based. HUD source catalogue indices can differ from internal
weapon indices. Read the selected interface's schema and the
[six-location layout](six-location-aerofighters-cli.md) instead of assuming every
unit has Mech section names.

## Persistence and reconnect

Configure file-backed owners before initialization. `hud_display.root` selects
default child stores for a full session, while `file_root`, `construction.root`,
`pilots.root` and `repair_economy.root` can select them individually.

A durable client needs an explicit restore strategy. Retain map/environment
data, unit designs and live state, characters, stock and repair queues through
their owners, and restore AI after its referenced world/units exist.
`ai_save`/`ai_load` preserve controllers and their supported events, not unit
damage, movement, random inputs or the global clock. Environment snapshots also
have a defined subsystem scope. See the
[Python persistence table and example](python-api.md#persistence-entry-points).

For replay, preserve initial conditions, configuration, seed/finite inputs and
the actual ordering of commands and tick advances. An input log tied only to
wall-clock timestamps is insufficient if pacing or request ordering changes.
Keep reconnect semantics visible: starting a fresh scenario and restoring an
existing world are distinct application operations.

Continue with [architecture](architecture.md), [Python API](python-api.md), and
the [scenario guide](running-scenarios.md).

