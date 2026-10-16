# Running scenarios

The encounter collection contains **32 general and line-of-sight scenarios**
plus **three Battlesheep AI scenarios**. Each starts with a world description,
issues ordinary commands and advances the simulation. Use them to see how one
event changes the next: a missed jump causes a fall, flooded equipment refuses
fire, or a sensor change turns a one-sided fight into an exchange.

[Getting started](getting-started.md) · [Core interface](core-simulation-cli.md) ·
[Python API](python-api.md)

## Contents

- [Choose how to run](#choose-how-to-run)
- [Run a JSON file or stdin](#run-a-json-file-or-stdin)
- [Replay and record encounters](#replay-and-record-encounters)
- [Four encounters to explore](#four-encounters-to-explore)
- [Browse all scenario families](#browse-all-scenario-families)
- [Make deterministic replays and variants](#make-deterministic-replays-and-variants)
- [Read the results](#read-the-results)
- [Choose storage for direct sessions](#choose-storage-for-direct-sessions)
- [Extend an encounter](#extend-an-encounter)

## Choose how to run

Install the package using [Getting started](getting-started.md). Unless stated
otherwise, commands below run from the **source directory**, with its environment
active.

| Goal | Interface |
|---|---|
| Execute a JSON scenario and get its results/final state | Its matching `python -m tools...` CLI |
| See intermediate milestones and a readable timeline | `tests.test_gameplay_scenarios` or `tests.test_autopilot_scenarios` |
| Issue new actions during an ongoing simulation | A Python session object, described in the [API guide](python-api.md) |
| Drive an interactive display | A session plus your application's transport; see [client integration](client-integration.md) |

The [manifest](../examples/gameplay_scenarios/manifest.json) names the CLI module
for each of the 32 general/LOS inputs. The three `ai_*.json` inputs all use
`tools.autopilot` and are listed in the [AI guide](../examples/gameplay_scenarios/AI.md).

| Module | Choose it for |
|---|---|
| [`tools.core_simulation`](core-simulation-cli.md) | Core combat, movement and sensing encounters |
| `tools.maps_environment` | Map/environment encounters such as `fire_smoke` and `los_smoke_maneuver` |
| [`tools.communications`](communications-cli.md) | C3 networks, radio and encounters using its extended unit/character schema |
| [`tools.aerospace`](aerospace-cli.md) | DropShip bays, the DropShip stacking encounter and flight workflows |
| [`tools.autopilot`](autopilot-cli.md) | Battlesheep controllers and AI orders |

These adapters share gameplay systems but accept different document fields.
Use the specified adapter when running an existing input.

There are also narrower standalone interfaces with different arguments:
`python -m tools.movement --script YOUR_FILE.json` runs a movement workflow;
`python -m tools.heat_updates --input YOUR_FILE.json` runs a
[heat workflow](heat-updates-cli.md). Both require a file. Those placeholders
refer to inputs using their own schemas, not arbitrary collection files.
For a route-cost query, use the separate [path-cost command](path_costs.md).

### Source and wheel assets

A checkout or extracted source distribution includes `examples/`, `tests/`,
`features/` and `docs/`. The wheel installs the runtime and CLI modules.
Wheel users supply their own JSON or copy a collection input from source, then
run its matching `tools.*` command from any writable directory.

The source runners locate inputs beside their test sources. They are not
wheel-installed commands. Run a copied or edited input directly; `--replay`
selects an existing collection name, not an arbitrary file.

## Run a JSON file or stdin

From the source directory, these commands work in both PowerShell and POSIX
shells:

```sh
python -B -m tools.core_simulation --input examples/gameplay_scenarios/dfa_miss.json
python -B -m tools.autopilot --input examples/gameplay_scenarios/ai_combat.json
```

Each reads one complete JSON document, executes its `actions`, prints one JSON
result document to stdout and exits. Omit `--input` to read stdin.

PowerShell:

```powershell
Get-Content -Raw examples/gameplay_scenarios/dfa_miss.json | python -B -m tools.core_simulation
Get-Content -Raw examples/gameplay_scenarios/ai_combat.json | python -B -m tools.autopilot
```

POSIX shell:

```sh
python -B -m tools.core_simulation < examples/gameplay_scenarios/dfa_miss.json
python -B -m tools.autopilot < examples/gameplay_scenarios/ai_combat.json
```

PowerShell uses `Get-Content -Raw` rather than POSIX `<` redirection. These
batch CLIs do not implement a live JSON-lines command connection.

To save stdout, use `| Set-Content -Encoding utf8 tmp/result.json` in
PowerShell or `> tmp/result.json` in a POSIX shell, after creating `tmp/`.
Read saved PowerShell output with Python's `encoding="utf-8-sig"` to support
both older PowerShell's UTF-8 byte-order mark and newer versions' output.
[Getting started](getting-started.md#run-a-saved-encounter) gives complete examples.

Direct sessions may also create their configured persistent storage. See
[storage isolation](#choose-storage-for-direct-sessions) before comparing runs.

## Replay and record encounters

Run both complete collections:

```sh
python -B -m tests.test_gameplay_scenarios
python -B -m tests.test_autopilot_scenarios
```

The first reports 32 tests, the second three; successful runs end with `OK`.
They need only the standard library. Each checks gameplay milestones and
independently executes its input through the public stdin interface, comparing
command replies, unit/map state, pending events and named random draws.
The AI collection also checks controller state.

To replay one encounter and print its detailed record:

```sh
python -B -m tests.test_gameplay_scenarios --replay los_asymmetric_sensors
python -B -m tests.test_autopilot_scenarios --replay ai_navigation
```

To write all timelines and records under ignored `tmp/` directories:

```sh
python -B -m tests.test_gameplay_scenarios --record tmp/gameplay-results
python -B -m tests.test_autopilot_scenarios --record tmp/ai-results
```

Combine the flags to record just one:

```sh
python -B -m tests.test_gameplay_scenarios --replay dfa_miss --record tmp/gameplay-results
python -B -m tests.test_autopilot_scenarios --replay ai_navigation --record tmp/ai-results
```

For each selected name, `--record` writes:

| File | Contents |
|---|---|
| `NAME.md` | A concise timeline and PASS/FAIL milestone descriptions |
| `NAME.json` | Detailed frames, command/action observations, messages, checks and random draws |
| `summary.json` | Per-encounter pass state, tick/check counts and public replay comparisons |

Open the Markdown file first, then inspect JSON for details. The records are
outputs, not inputs for `tools.*`. Original inputs stay in
`examples/gameplay_scenarios/`. A record command overwrites that encounter's
files and writes a summary for that invocation; use a new record directory to
keep separate runs.

Runners use independent temporary storage for their programmatic and CLI
executions. Recording chooses where reports go; it does not make that directory
the simulation's persistent world storage.

## Four encounters to explore

### Combat: a jump attack and its aftermath

Record the missed attack:

```sh
python -B -m tests.test_gameplay_scenarios --replay dfa_miss --record tmp/gameplay-results
```

At tick 20, the 50-ton attacker misses its DFA roll, takes 10 damage and falls;
the target takes none. The later stand and movement orders show recovery.
By the final tick, 140, the attacker is upright at `[3, 3, 0]`.

Compare [dfa_hit](../examples/gameplay_scenarios/dfa_hit.json) and
[dfa_hit_fall](../examples/gameplay_scenarios/dfa_hit_fall.json).
Their attack hits deal 15 to the target and 10 to the attacker before additional
fall damage. The variant names distinguish what actually happens after landing.
Read the timeline through recovery rather than stopping at the attack roll.

### Movement and terrain: breaking through ice

```sh
python -B -m tests.test_gameplay_scenarios --replay ice_break --record tmp/gameplay-results
```

The runner starts with an unarmored but intact left arm carrying a laser.
Crossing ice over depth-two water at tick 18 breaks the surface, causes a fall
and floods the exposed arm. At tick 70, the attempted laser shot is refused;
later movement reaches dry ground at tick 309.

Compare [ice_intact](../examples/gameplay_scenarios/ice_intact.json): the surface
holds and the laser remains usable. Inspect terrain, altitude, flooded sections
and disabled equipment together. The refusal's wording says the weapon is
destroyed, while the recorded slots show the flooding disablement.

### Line of sight: a fight one side cannot see

```sh
python -B -m tests.test_gameplay_scenarios --replay los_asymmetric_sensors --record tmp/gameplay-results
```

**Line of sight (LOS)** describes visibility between an observer and a target.
Here the Mech begins with two infrared sensors (`I/I`), while battle suits and
a dismounted personal-combat unit use visual sensors (`V/V`). Both small units
see and fire on the Mech, dealing 5 and 1 damage; the Mech's direct return shots
fail visibility checks.

The Mech later selects electromagnetic sensors (`E/E`) and acquires the suits,
while the personal-combat unit remains excluded. Visual sensing restores further
contacts, and turning changes weapon and sensor arcs. A lock on known hex
coordinates is not proof of a valid shot at the occupying unit; the encounter
also distinguishes firing at an occupant from deliberately firing at terrain.

This is why the record tracks contacts in both directions, target locks, sight
replies, weapon recovery and actual damage. The
[sensor interface](sensors-los-cli.md) and [combat interface](combat-resolution-cli.md)
explain the separate gates.

### Battlesheep: radio travel, following and retargeting

```sh
python -B -m tests.test_autopilot_scenarios --replay ai_navigation --record tmp/ai-results
```

The navigation input registers Scout and Wing controllers, gives their units
matching nonzero radio frequencies, and sends orders through the Commander's
ordinary radio. These are excerpts from its action list:

```json
[
  {"op": "command", "unit": "Commander", "name": "sendchannel", "args": "a=SC go 3 3"},
  {"op": "advance", "seconds": 2},
  {"op": "command", "unit": "Commander", "name": "sendchannel", "args": "a=all speed 90"}
]
```

`a` selects channel A, `SC` addresses the Scout's contact ID, and lowercase
`all` addresses all listening controllers. The AI speed setting is a percentage;
ordinary unit `speed` commands use km/h. Subsequent orders replace Wing's
travel with following the moving Commander. The 466-tick scenario also saves
and reloads active AI state and demonstrates arrival and cancellation.

For autonomous firing, run `--replay ai_combat`. Its orders assign target
`TA`, shut the shooter down, restart it and replace the target with `SP`.
For historical fighter behavior, use `--replay ai_aerospace`: it exercises
the separate sensor/profile/gun event chains, reload and retargeting.

AI snapshots restore controllers and their owned work against the current world;
they do not rewind movement, damage, clocks or randomness. Some historical queue
instructions are inactive, and ordinary-unit versus Aerospace gun scheduling
differs. Use the [autopilot guide](autopilot-cli.md) for active queue/radio orders
and persistence details.

## Browse all scenario families

Names below are `--replay` choices without the `.json` suffix.
The first two tables use `tests.test_gameplay_scenarios`.
The last uses `tests.test_autopilot_scenarios`.
The module column tells you how to run a linked input directly.

### General encounters

| Family | What to observe | Inputs | Module under `tools.` |
|---|---|---|---|
| C3 targeting network | Shared range changes as units move and network hardware is damaged | [c3_maneuver_damage](../examples/gameplay_scenarios/c3_maneuver_damage.json) | `communications` |
| Death from above | Jump trajectory, landing, damage, falls and recovery | [dfa_hit](../examples/gameplay_scenarios/dfa_hit.json), [dfa_hit_fall](../examples/gameplay_scenarios/dfa_hit_fall.json), [dfa_miss](../examples/gameplay_scenarios/dfa_miss.json) | `core_simulation` |
| DropShip unloading | Clear exits versus collisions in a crowded departure lane | [bay_orderly](../examples/gameplay_scenarios/bay_orderly.json), [bay_crowded](../examples/gameplay_scenarios/bay_crowded.json) | `aerospace` |
| Friendly stacking | A mover entering occupied hexes; the DropShip's different collision treatment | [stack_2](../examples/gameplay_scenarios/stack_2.json), [stack_3](../examples/gameplay_scenarios/stack_3.json); [stack_dropship](../examples/gameplay_scenarios/stack_dropship.json) | `core_simulation`; `aerospace` for `stack_dropship` |
| Ledges | Safe descent, wall avoidance, collisions and falls | [ledge_stop](../examples/gameplay_scenarios/ledge_stop.json), [ledge_collision](../examples/gameplay_scenarios/ledge_collision.json), [ledge_fall](../examples/gameplay_scenarios/ledge_fall.json) | `core_simulation` |
| Ice | Surface survival versus breakthrough, flooding and escape | [ice_intact](../examples/gameplay_scenarios/ice_intact.json), [ice_break](../examples/gameplay_scenarios/ice_break.json) | `core_simulation` |
| Artillery | Delayed impact, hit versus scatter and blast effects | [artillery_hit](../examples/gameplay_scenarios/artillery_hit.json), [artillery_scatter](../examples/gameplay_scenarios/artillery_scatter.json) | `core_simulation` |
| Reactor | Countdown, blast and surviving units | [reactor](../examples/gameplay_scenarios/reactor.json) | `communications` |
| Fire and smoke | Ignition, wind, smoke and expiration | [fire_smoke](../examples/gameplay_scenarios/fire_smoke.json) | `maps_environment` |

### Line of sight and sensors

Here **MW** is a dismounted personal-combat unit; **BSUIT** is a battle-armor team.

| Family | What to observe | Inputs | Module under `tools.` |
|---|---|---|---|
| Personal units in woods | Clear/light/heavy lanes, acquisition and later fire | [los_woods_mw_clear](../examples/gameplay_scenarios/los_woods_mw_clear.json), [los_woods_mw_light](../examples/gameplay_scenarios/los_woods_mw_light.json), [los_woods_mw_heavy](../examples/gameplay_scenarios/los_woods_mw_heavy.json) | `core_simulation` |
| Battle suits in woods | The same terrain comparison with a suit team | [los_woods_bsuit_clear](../examples/gameplay_scenarios/los_woods_bsuit_clear.json), [los_woods_bsuit_light](../examples/gameplay_scenarios/los_woods_bsuit_light.json), [los_woods_bsuit_heavy](../examples/gameplay_scenarios/los_woods_bsuit_heavy.json) | `core_simulation` |
| Hidden approach | Five-hex acquisition gate, strict under-three detection and contact retention | [los_hidden_five](../examples/gameplay_scenarios/los_hidden_five.json), [los_hidden_three](../examples/gameplay_scenarios/los_hidden_three.json) | `communications` |
| Active probes | Hidden stealth suits and differing probe eligibility | [los_hidden_probe](../examples/gameplay_scenarios/los_hidden_probe.json) | `communications` |
| Asymmetric sensing | One-way attacks, sensor changes, hex targeting and arcs | [los_asymmetric_sensors](../examples/gameplay_scenarios/los_asymmetric_sensors.json) | `core_simulation` |
| Cover transitions | Movement into woods, lost locks and reacquisition | [los_cover_transitions](../examples/gameplay_scenarios/los_cover_transitions.json) | `core_simulation` |
| Ridge and posture | Ground blockage, partial cover, prone and standing | [los_ridge_cover](../examples/gameplay_scenarios/los_ridge_cover.json) | `core_simulation` |
| Night and lighting | Light amplification, searchlight warmup and changed visibility | [los_night_searchlight](../examples/gameplay_scenarios/los_night_searchlight.json) | `core_simulation` |
| Moving smoke fight | Lost visual contacts, infrared fire and maneuver out of smoke | [los_smoke_maneuver](../examples/gameplay_scenarios/los_smoke_maneuver.json) | `maps_environment` |

Short visible distances in the woods examples come from intervening woods and
geometry. They are not a universal infantry sensor-range limit. Compare the
clear variants and the separate hiding cases before changing those conditions.

### Battlesheep AI

| Family | What to observe | Input | Module under `tools.` |
|---|---|---|---|
| Navigation and orders | Route around a ridge, radio addressing, active reload, following and cancellation | [ai_navigation](../examples/gameplay_scenarios/ai_navigation.json) | `autopilot` |
| Autonomous combat | Sensor choice, repeated fire, ammo/heat, shutdown/startup and replacement targets | [ai_combat](../examples/gameplay_scenarios/ai_combat.json) | `autopilot` |
| Historical Aerospace AI | Service deadlines, reload, gun off/on, destruction and reacquisition | [ai_aerospace](../examples/gameplay_scenarios/ai_aerospace.json) | `autopilot` |

The [collection README](../examples/gameplay_scenarios/README.md) and
[AI companion](../examples/gameplay_scenarios/AI.md) provide further encounter
details.

## Make deterministic replays and variants

Keep the same scenario, seed, action order, engine version and initial storage
to reproduce a run. Core-based sessions use the engine's Mersenne Twister random
generator. A top-level setting such as `"random": {"seed": 2}` makes the choice
explicit. Initialization can consume random draws before the first action.

Some encounters also supply **finite named streams** in `random.streams`.
These provide particular values to particular random consumers, while the real
gameplay operations still run. When streams are supplied, reached named
consumers must have valid, unexhausted values. Changing only the seed will not
replace those supplied values.

For an exploratory variant:

1. Copy an input into `tmp/`, leaving the original collection intact.
2. Change initial unit positions, teams, headings, equipment or map terrain.
3. Adjust its actions and `advance` durations to fit the new situation.
4. For ordinary seeded randomness, remove `random.streams` as a whole and keep
   or choose `random.seed`. If retaining streams, account for every reached
   consumer and inspect `draws`.
5. Run the copied JSON directly with its matching `tools.*` module and inspect
   the new result.

For example, copy the ice encounter:

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
Copy-Item examples/gameplay_scenarios/ice_break.json tmp/my-ice.json
```

```sh
mkdir -p tmp
cp examples/gameplay_scenarios/ice_break.json tmp/my-ice.json
```

Edit `tmp/my-ice.json`, then run in either shell:

```sh
python -B -m tools.core_simulation --input tmp/my-ice.json
```

Map `hexes` records select terrain and stored elevation; unit `at` values
select placement. On water and ice, stored depth and a unit's signed altitude
have different meanings. Unit `name` is used by action dispatch,
`contact_id` by many targeting/radio commands, and numeric `id` by object
references such as queued AI follow orders. Update references when renaming
or replacing units.

Ordinary movement speed arguments are km/h; one movement point (MP) is
10.75 km/h. Motion is continuous between hexes, so a position can change before
the occupied hex changes. Place `inspect` actions around the event you want
to observe and advance enough ticks for its scheduled work.

Adding gameplay commands can change later draw consumption. Even a `sight`
query can consume random inputs; it does not reserve a later shot. Use
`inspect` or a Python `snapshot()` for state observation.

The collection runner's milestones describe the original encounter. They do
not automatically become correct expectations for your edited input.

## Read the results

Start with command replies, then verify the corresponding change in state.
An accepted target lock, a sight calculation, a launched shot and a damaging
hit are separate outcomes.

| Question | Look at |
|---|---|
| Which action was refused, and why? | The corresponding raw `results` entry and its `accepted`/`ok`, text and attack fields |
| Did movement or an order finish? | Time, actual versus desired motion, unit position and pending `state.events` |
| Did the attack land? | Attack `hit`, `roll`, `bth`, `damage_dealt` and final armor/internal state |
| Why did a later shot fail? | Weapon recovery, ammunition, heat, pilot/unit condition, range, arcs and visibility |
| Can one participant see the other? | Directed map LOS rows, contacts and locks for each observer |
| What is an AI controller doing? | `state.autopilots`: settings, queue, current path/profiles, inbox and pending callbacks |
| What caused a different replay? | Input changes, initial stores and the names/order/values in `draws` |

**BTH** is the target number the attack roll must meet. **Recycle** is a weapon
or physical action's recovery delay. **A milestone** is a specific runner check,
such as a lost lock, flooded section or later successful movement.

Raw CLI state uses `state.time`; encounter records use compact observations
with `tick`, `damage` and similar fields under `frames` and `final`.
Their JSON layouts are deliberately different. Record `checks` list milestone
results, and `stdio` reports the independent replay comparisons.

Check the timeline as well as the final state. A unit can fall, recover and walk
away within one run; the final `fallen: false` does not mean that no fall
occurred. Pending callbacks can remain when a scenario ends. The CLI stops
after its actions rather than automatically running until the battlefield is idle.

## Choose storage for direct sessions

The input file's location does not set a session's working directory.
Relative storage paths resolve from the directory where you invoke Python.
An ordinary direct CLI run can create map, template, character and economy
storage even though its main result goes to stdout.

These are JSON configuration fields, not command-line flags:

| Field | Adapter providing it | Default relative directory |
|---|---|---|
| `file_root` | Maps and adapters extending it | `./tmp/maps_environment_files` |
| `construction.root` | Construction and adapters extending it | `./tmp/construction_templates_files` |
| `pilots.root` | Pilots and adapters extending it | `./tmp/pilots_characters` |
| `repair_economy.root` | Repair/economy and adapters extending it | `./tmp/repair_economy` |
| `hud_display.root` | HUD and autopilot | `./tmp/hud_status` |

HUD/autopilot sessions default the inherited roots to `maps/`, `templates/`,
`characters/` and `economy/` children of `hud_display.root`.
An explicitly supplied subsystem root takes precedence. An AI document can
therefore use `"hud_display": {"root": "./tmp/ai-run-a"}` to group its normal
storage, provided it has no separate overrides. AI save files use the map
file root. Core-only scenarios do not accept these additional storage fields.

To run an unchanged AI fixture with fresh default stores, invoke the installed
package from an unused directory. The following starts from the source root,
resolves the fixture first and returns you to the source root afterward.

PowerShell:

```powershell
$scenarioPath = (Resolve-Path examples/gameplay_scenarios/ai_navigation.json).Path
New-Item -ItemType Directory -Force tmp | Out-Null
New-Item -ItemType Directory tmp/ai-run-01 -ErrorAction Stop | Out-Null
Push-Location tmp/ai-run-01
try {
    python -B -m tools.autopilot --input $scenarioPath | Set-Content -Encoding utf8 result.json
} finally {
    Pop-Location
}
```

POSIX shell:

```sh
scenario_path="$PWD/examples/gameplay_scenarios/ai_navigation.json"
mkdir -p tmp
mkdir tmp/ai-run-01 && (
    cd tmp/ai-run-01 || exit
    python -B -m tools.autopilot --input "$scenario_path" > result.json
)
```

Use a new name such as `ai-run-02` for the next independent run.
This writes stdout to `tmp/ai-run-01/result.json` and default AI storage beneath
`tmp/ai-run-01/tmp/hud_status/`. Wheel users can resolve a copied fixture in
the same way. A scenario containing explicit absolute storage paths continues
to use those paths regardless of the working directory.

Reusing storage can affect loaded data and recorded writes. For example,
initializing an empty economy store can record a write that a subsequent run
does not need. A seed alone does not reset persistent files. Keep separate
directories for independent comparisons, or use the collection runners'
automatic isolation.

## Extend an encounter

The [core adapter](core-simulation-cli.md), [combat adapter](combat-resolution-cli.md),
[sensors](sensors-los-cli.md), [communications](communications-cli.md),
[Aerospace](aerospace-cli.md) and [autopilot](autopilot-cli.md) guides define the
corresponding inputs and actions.

For original designs, use the explicit
[template catalogue workflow](template-catalog-integration.md). For historical
fighters, read the [six-location guide](six-location-aerofighters-cli.md).
For programmatic scenario building and live controls, continue with
[Python API](python-api.md) and [client integration](client-integration.md).

