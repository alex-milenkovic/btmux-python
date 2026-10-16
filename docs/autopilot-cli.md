# Battlesheep / autopilot JSON interface

Run from the engine root:

```powershell
python -B -m tools.autopilot --input examples/gameplay_scenarios/ai_navigation.json
Get-Content -Raw examples/gameplay_scenarios/ai_combat.json | python -B -m tools.autopilot
python -B -m tests.test_autopilot_scenarios
```

`tools.autopilot.AutopilotSession` extends the existing display/gameplay session.
Its map, unit, pilot, weapon, communications, random, action and tick fields use
that session's normal schemas. It adds registered controllers and AI snapshots.
Every order uses the existing movement, startup, sensing, combat, transport or
communications system. A scenario needs no injected service callbacks.

## Controllers and commands

The optional top-level `autopilots` array contains:

```json
{
  "name": "ScoutAI",
  "id": 200,
  "unit": "Scout",
  "commands": ["speed 80", "goto 3 3"],
  "engage": true
}
```

`name`, positive `id`, and the existing unit name are required. Controller names,
object identities and attachments must be unique. `commands` defaults to `[]`;
`engage` defaults to `true`. An unengaged controller is inside its unit but has
not linked its runtime mech pointer yet. Engagement sets that link, initializes
source defaults when the mech has no AI, assigns its channel-A title, and queues
its first command decision at +1. Normal engine/controller registration installs
built-in command, sensor, profile, gun and radio services. Existing explicit
`engine.auto_services` overrides survive installation. Legacy AUTO adapter objects
retain their configured-service behavior, including when they share an engine
with a built-in controller.

Direct queue commands use the existing command action with the attached unit:

```json
{"op":"command","unit":"Scout","name":"aiaddcommand","args":"goto 3 3"}
{"op":"command","unit":"Scout","name":"aiengage","args":""}
```

| Command | Arguments / result |
|---|---|
| `aiaddcommand` | Complete source queue instruction |
| `aidelcommand` | One-based queue position, or `-1` for all |
| `aiengage`, `aidisengage` | Engage or stop pending AI callbacks |
| `ailistcommands` | Controller settings and current queue |
| `aieventstats` | Pending source AUTO event counts |
| `aijump` | Source's disabled-program-jump notice |
| `snipe` | Target contact ID and weapon selector; requires wizard/royalty |

Queue command names are case-sensitive. Active instructions are `chasetarget`,
`dumbfollow`, `dumbgoto`, `enterbase`, `follow`, `goto`, `leavebase`, `oldgoto`,
`roam`, `autogun`, `dropoff`, `embark`, `pickup`, `shutdown`, `speed`, `startup`,
and `udisembark`. Queue follow/pickup/embark targets are numeric object identities;
radio targets are the unit's two-character contact ID. `roam` accepts `map` or
`radius X Y DISTANCE`. Completed instructions are removed from the queue.

The source table also accepts `wait`, `attackleg`, `chasemode`, `cmode`, `enterbay`,
`jump`, `load`, `report`, `roammode`, `stopgun`, `swarm`, `swarmmode` and `unload`.
Their executor switch cases are disabled in the active C configuration, so these
queue entries stall. Some have separately active radio handlers. In particular,
a radio `jumpjet` order works through normal jump commands. A queued `startup`
issued to an already started unit also stays queued, matching C.

## Radio gameplay

Send through ordinary `sendchannel`, after configuring unit radios and matching
nonzero frequencies. For example:

```json
{"op":"command","unit":"Commander","name":"sendchannel","args":"a=SC go 3 3"}
{"op":"command","unit":"Commander","name":"sendchannel","args":"a=all speed 90"}
{"op":"command","unit":"Commander","name":"sendchannel","args":"a=SC follow CM"}
{"op":"command","unit":"Commander","name":"sendchannel","args":"a=SC target TA"}
{"op":"command","unit":"Commander","name":"sendchannel","args":"a=all stop"}
```

Addressing accepts the recipient's contact ID without case sensitivity, or the
literal lowercase `all`. Commands use the source's ordered abbreviations and
argument counts; command case matters and repeated separators preserve empty
arguments. Radio orders include `autogun`, `chasetarg`, `dfollow`, `dgoto`,
`dropoff`, `embark`, `enterbase`, `follow`, `goto`, `heading`, `help`, `hide`,
`jumpjet`, `leavebase`, `ogoto`, `pickup`, `position`, `prone`, `report`, `reset`,
`sensor`, `shutdown`, `speed`, `stand`, `startup`, `stop`, `sweight` and `target`.
`help` returns the source command list. Replies are scheduled through the existing
AUTO reply callback and transmit normally. Existing channel, range, observer and
ECM ordering is retained; the parser receives the original message at the
established communications handoff point.

General units run sensor selection, conditional weapon profiling, then gunnery
in the ordinary heartbeat. This C heartbeat runs even when the AUTOGUN flag is
clear: an `autogun off` request can therefore be followed by reacquisition on a
later heartbeat. The historical Aerospace profile instead owns gun, sensor and
profile event chains; `off` cancels those chains. Its cadences and delayed sensor
changes are preserved. Fighter weapons retain the reviewed six-location layout,
and DropShips continue to use their distinct existing adapters.

## AI persistence and inspection

```json
{"op":"ai_save","file":"ai-active.json"}
{"op":"ai_load","file":"ai-active.json"}
```

These operations use the existing session file-root/filename policy. The
`hud_display.root` option provides an isolated storage root for this full session;
the encounter test driver sets a temporary root automatically.

Version 2 AI snapshots store controller identities, attachment and pilot ownership,
scalar settings/counters, source command records, and relative deadlines/data for
owned command, navigation, gun, sensor, profile and delayed reply events. Loading
validates the entire snapshot before replacing live controllers or cancelling
their callbacks. Queues use the source's start/end tags and fixed-size command
argument records. Transient A* paths and weapon profiles are rebuilt through the
next normal AI callbacks; queued navigation restarts path generation at its saved
next decision deadline. Containment, unit links and AI pilot references are
re-established through the existing local object services. Controllers explicitly
remain non-player actors, including when restored as a unit's pilot.

Version 2 also records queue slots, including canceled slots and references to
coincident world callbacks. Restoring that layout preserves the scheduler's
existing deadline-only heap order for AI callbacks and unit-owned replies;
it does not impose a new FIFO or LIFO rule. Matching world callbacks retain
their current objects and cancellation state. Missing world callbacks leave
inert canceled slots; callbacks added since the save remain scheduled normally.
The snapshot cannot replay or rewind another subsystem's callbacks. Version 1
lacks this ordering information and must be regenerated with the updated engine.

The public loader validates the entire prospective controller handle dictionary
before replacing any objects or callbacks. Existing IDs keep their current
handles; new IDs use the saved name. Duplicate handles and conflicts with other
public objects reject the load atomically.

This is an AI subsystem snapshot, following the engine's existing subsystem
storage model. Restore/load the corresponding world and units through their
owners first when constructing another engine. AI load does not rewind unit
movement, damage, map state, the global clock, or randomness. In-session reloads
leave those owners running, as demonstrated by both navigation and Aerospace
encounters. Custom service callbacks remain engine-owned; snapshots reject
unrecognized scheduled callback functions.

Normal `inspect` and final JSON snapshots add `autopilots`, including scalar state,
queue, current transient path/profiles, inbox, and pending AI callbacks. CLI output
contains `results`, `state`, and the engine's named `draws`. Observations do not
supply AI outcomes.

Source undefined behavior is bounded locally: malformed saved nodes raise an
input error before mutation; old goto's invalid numeric/double-free path advances
with a diagnostic; undefined diagnostic coordinates use zero; roam's XOR divisor
at attempt 2 emits a diagnostic and retains its previous target. Python ownership
replaces C allocation/free and tree-walk destruction. The source's empty path
smoothing function stays a no-op.
