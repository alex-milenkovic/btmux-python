# Sensor simulation interface

Run from the project root with Python 3:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/tmp" \
  python3 -m tools.sensors_los --input ./tmp/sensor-workflow.json
```

Omit `--input` to read one JSON document on stdin. Successful execution writes
one JSON object to stdout: `results` in action order, final `state`, and consumed
random `draws`. Bad schema, unknown enum/command/action, invalid geometry or
exhausted/out-of-range supplied dice returns nonzero with stderr diagnostics.
An ordinary pilot-command refusal is a valid simulation result with `ok:false`.
No sockets, GUI, MUX process, external reference tree or credentials are required.

The adapter creates real `GameMap`, `Mech`, `Pilot`, weapon critical slots and
`GameEngine` objects. Commands enter `GameEngine.inject_command`, and `advance`
runs its event clock. Snapshots do not refresh sensors, grant detection or draw
dice. Terrain map requests invoke the production LOS renderer.

## Example: acquire, designate, stabilize, cancel

Save this document in `./tmp/sensor-workflow.json`:

```json
{
  "map": {"size": [8, 8], "light": 2, "mapvis": 30},
  "units": [
    {"name": "u", "contact_id": "AA", "team": 1,
     "at": [2, 1, 0], "facing": 180, "equipment": ["TAG"]},
    {"name": "target", "contact_id": "TT", "team": 2, "at": [2, 2, 0]}
  ],
  "actions": [
    {"op": "advance", "seconds": 2},
    {"op": "command", "unit": "u", "name": "contacts"},
    {"op": "command", "unit": "u", "name": "tag", "args": ["TT"]},
    {"op": "advance", "seconds": 30},
    {"op": "inspect"},
    {"op": "command", "unit": "u", "name": "tag", "args": ["-"]},
    {"op": "advance", "seconds": 30},
    {"op": "inspect"}
  ]
}
```

The first acquisition is point blank and still runs real sensor eligibility.
TAG state becomes reciprocal at assignment; stabilization/cooldown notifications
arrive on their real deadlines. IDs in snapshots are runtime identities, not
stable numbers to hardcode between processes.

## Document fields

Only `actions` is required. Top-level fields are `map`, `units`, `config`,
`random`, `actions`, and `diagnostic_cache`.

`map` accepts:

| Field | Meaning/default |
|---|---|
| size | `[width,height]`, each 1..200; default `[8,8]` |
| default | `[terrain,elevation]` for all hexes; otherwise ordinary clear floor 0 |
| hexes | Array of `{at:[x,y],terrain,elevation,overlay?,duration?}` |
| mapvis / maxvis | Initial visibility/range, default 30/60 |
| light | 0 night, 1 dusk/dawn, 2 daylight; default 2 |
| cloudbase | Initial cloud height; default 0 |
| sensorflags | Integer disable mask, default 0 |
| weather | Raw visibility/light/wind/windspeed, optional cloudbase and trailing text |
| dark | Boolean controlling range-command elevation disclosure, default false |

Terrain names use the existing map enum names (e.g. `GRASSLAND`, `LIGHT_FOREST`,
`HEAVY_FOREST`, `WATER`, `MOUNTAINS`, `SMOKE`, `FIRE`). `CLEAR` aliases
`GRASSLAND`. Elevation stores an absolute 0..9 floor; water sign is derived by
the existing terrain service. For overlay underlay tests specify base `terrain`
plus `overlay:"FIRE"` or `"SMOKE"`. `duration` defaults to 100 ticks. These are
real timed decorations with expiration events and preserved underlays.

Weather defaults to a valid string built from the requested initial conditions.
At multiples of 25, the production parser refreshes/clamps weather and performs
the source's asymmetric light-sensor reset. A `conditions` action changes the raw
string for the next refresh; it does not immediately change the light.

`config` accepts `periodic_updates` (default true), `lock_tick` (0..100, default
0), `infrared_profile` (`unscaled` or `scaled`, default `unscaled`),
`seismic_see_stopped` (default false), and `movement_modes` (default true).
Disabling periodic updates is for isolated diagnostic cases; registration still
starts the real PLOS event when appropriate. Ordinary workflows leave it enabled.

## Unit fixtures

`units` is an array; the default is one unit named `u`. Each unit requires a
unique `name`. A fixture starts with test-mech armor/sections, a pilot, online
reactor and VV sensors. All positions are validated. Supported fields:

* Identity/location: `name`, unique two-character `contact_id` (automatic when
  omitted), `team`, `at:[x,y,z]` (default `[2,2,0]`), optional
  `real:[fx,fy,fz]` in engine Cartesian units, `class` and `movement` using the
  `UnitType`/`MoveType` enum names (default `MECH`/`BIPED`). One hex is 322.5
  Cartesian units and one elevation level is 64.5.
* Sensors/equipment: `sensors:[primary,secondary]` using `V,L,I,E,S,R,B,A,H`,
  `perception` (default 6), `sensor_hits`, `equipment`, `weapons`, `ammo`,
  `scan_range`, `radio_range`, `recycle`.
* Boolean initial state: `pilot`, `started`, `destroyed`, `conscious`, `blinded`,
  `fallen`, `hulldown`, `hidden`, `observer`, `clairvoyant`, `sl_warn`,
  `autocon_shutdown`, `in_character`.
* Numeric state: `heat`, `plus_heat`, `minus_heat`, `speed`, `desired_speed`,
  `facing`, `turret_facing`, `tonnage`, `brief`, `fire_adjustment`.
  `real_mass` is nonnegative tons (default design `tonnage`), initialized through
  the existing `update_oweight` producer and returned in unit snapshots.
  Seismic targeting reads this cache in whole tons, as C's `MechRealTons` does.
* Raw diagnostic bit words: `status`, `status2`, `crit_status`, `specials`,
  `specials2`. These initialize actual engine flags; they are not expected
  outcomes. Prefer equipment and commands for normal workflows.
* `markings` text; `sections` array with `index` and optional `armor`, `internal`,
  `specials`, `config`; these update actual section state.
* Initial references `target`, `spotter`, `tag_target`, `tagged_by` accept a
  previously declared unit name (or self) or an integer for an explicit dangling
  reference diagnostic. Normal workflows use commands to establish links.

Equipment names: `TAG`, `Guardian`, `Angel`, `Beagle`, `LightBeagle`,
`Bloodhound`, `searchlight`, `Radar`, `C3master`, `Personal`. Installed equipment
sets its real tech word and, when appropriate, critical-slot type. An
`equipment_hit` action goes through the real critical dispatcher. No fixture
boolean decides whether a unit is an artillery mech.

`weapons` accepts weapon database names such as `"IS.LRM-10"` or objects:

```json
{"name":"IS.LRM-10", "section":4, "critical":0,
 "ammo_mode":0, "fire_mode":0}
```

Default section is 4; automatic slots advance by the weapon's actual critical
size. Explicit slots must fit and cannot overlap equipment. All occupied
critical slots receive the selected mode. `ammo_mode` and `fire_mode` use the
engine's `AmmoMode`/`FireMode` integer bits. For semiguided tests use
`int(entities.mech.AmmoMode.SGUIDED_MODE)`; this reaches the actual sight/BTH
consumer. Artillery classification uses weapon database metadata.

`ammo` entries require `weapon` (database name) and `rounds` (0..255), with
optional `section` (default 2), `critical` (default array index), `ammo_mode`
(default 0). Bins cannot overlap installed equipment. Sight works without ammo;
normal ammunition-using fire requires a compatible loaded bin.

## Actions and commands

Action-specific unknown fields are errors. Global actions need no unit named
`u`; other actions default `unit` to `u` if omitted.

| op | Fields and effect |
|---|---|
| command | `unit`, `name`, optional `args` array; run the pilot command |
| advance | `seconds` nonnegative integer; run real events/ticks |
| inspect | Return a read-only state snapshot |
| map | `unit`, `origin:[x,y]`, `size:[width,height]`; render terrain and diagnostic flags |
| conditions | `weather` string for the next 25-tick refresh |
| place | `unit`, `at:[x,y,z]`, optional `real`; relocation diagnostic, marks LOS |
| remove | `unit`; remove from map and engine registry |
| flash | `source` unit name, `duration`, optional `chance` 0..100; real flash/recovery function |
| equipment_hit | `unit`, `equipment`, optional `attacker` unit name; real installed critical hit |
| diagnose | `unit`, `kind`, optional `target` unit name; explicit production-rule inspection |

Supported commands: `sensor`, `brief`, `contacts`, `scan`, `report`, `view`,
`bearing`, `range`, `vector`, `tag`, `slite`, `spot`, `target`, `speed`, `heading`,
`ecm`, `eccm`, `angelecm`, `angeleccm`, `perecm`, `pereccm`, `losemit`, `startup`,
`shutdown`, `sight`, `fire`. `args` are joined as the command text, e.g.
`["I","E"]`, `["A","3"]`, `["TT","W"]`, or `[0]` for sight weapon zero.

Sensor/brief/contact/scan/target grammar follows the specification. `sight` and
`fire` take a weapon number and optional locked contact ID. Establish a lock with
`target TT` first; supplying a contact does not bypass the engine's default
locked-fire policy. To exercise movement, issue `speed`/`heading` and advance
the normal engine. `place` is explicitly diagnostic, not a movement substitute.

## Diagnostics, results and randomness

`diagnostic_cache` is an optional array of `{viewer,target,flags}` using unit
names. It seeds the real ordered LOS cache and labels the final state as a
diagnostic-cache run. Omit it for acquisition/lifecycle tests.

Diagnostic kinds are `map-maintenance`, `plos`, `ecm`, `tag`, `end-light`,
`illumination`, `height`, `terrain-modifier`, `status`, `legacy-sensor-info`,
`random-window`, `los`, and `eligibility`. These call production rules; they do
not accept desired outcomes. The normal command/event paths remain available
without diagnostics.

Map results contain row-major `flags` and `cells`. Bits: visited=1, terrain=2,
elevation=4, lit=8. A visited hidden cell does not disclose terrain/elevation:
those fields are null. Rectangles must fit the map and be at most 70x45.

Snapshots include time; unit runtime/contact IDs; real/hex coordinates; active
and wanted sensors; perception and seen counts; lock/spot/TAG state; light/ECM
bits; sorted pending event deadlines; notifications; armor; actual weapon
recycle/ammo mode and bin rounds; current map conditions. Command results carry
`ok`, `message` and structured data. Sight/fire include `attack`, its resolved
`target_id`, BTH breakdown and `observer_modifier` (the FireSpot input; artillery
uses its own BTH formula). This makes occupant selection observable without
causing damage during sight.

`random` accepts `seed` (default 0) and optional `streams` mapping named draws
to finite arrays of integers. Examples are `sensor.random` (31-bit MNumber
source), `sensor.detect`, `sensor.flash`; bounds of each actual consumed draw
are included in the returned `draws`. Missing streams use seeded default dice.
An explicitly supplied stream never silently refills when exhausted. MNumber
reuses one underlying draw for each unit's six-second event window. The adapter
does not promise the C PRNG's exact global stream ordering.

Unavailable external services are reported explicitly by the interface.
Building/mine and artillery-impact branches return explicit unavailable results;
the interface does not create substitute XP, autopilot behavior or artillery hits.

## QA diagnostic controls

The executable QA driver is `python3 qa/sensors_los.py`; `--only tag` selects a
feature and `--only tag/01-01` reproduces one row. Inputs, stdout, stderr, exit
codes and independent assertions are saved beneath `tmp/qa-sensors-los/`.

`conditions` also accepts `sensorflags` (unsigned 32-bit), applied immediately
to the real map configuration. Weather still changes only on the 25-tick refresh.
This permits acquire/lock/disable/lose workflows without injecting contact results.

Additional explicit scenario diagnostics are:

| Action | Fields | Meaning |
|---|---|---|
| register | unit | Repeat live registration to check acquisition-chain deduplication |
| configure | unit, values | Set the limited fixture fields below and mark LOS |
| cache | unit, target, flags | Seed ordered cached LOS; marks output diagnostic_cache=true |
| hex | value | Apply the documented map hex/decoration schema to the live map |
| roster-hole | none | Append a missing roster slot to verify safe maintenance |

`configure.values` accepts booleans `started`, `conscious`, `blinded`,
`destroyed`, `sl_warn`, `autocon_shutdown`; integer words `status`, `status2`,
`crit_status`, `specials`, `specials2`, `tank_crit_status`; integer fields
`targ_x`, `targ_y`, `targ_z`, `brief`, `radio_range`, `scan_range`, `team`,
`targcomp`, `cocoon`, `carrying`, `stagger_level`, `fire_adjustment`; numeric
`speed`, `desired_speed`, `heat`, `plus_heat`, `minus_heat`, `vertical_speed`;
text `contact_options`; and name-or-ID references `spotter`, `target`,
`tag_target`, `tagged_by`, `swarm_target`. Setting diagnostic state does not
simulate a corresponding command. Use commands for lifecycle verification.
Unknown fields and nonnumeric/nonboolean values are rejected. Diagnostic
`options`, when supplied, must be an object; null, arrays and scalar values reject.

`diagnose` additionally accepts `trace` (coordinates and computed LOS flags),
`sensor-chance` (driver and arc percentages), `flags` with `options.value`, and
`sensor-description` with `options.index` (out-of-bounds returns the literal
string `"None"`, matching C). `random-window` accepts `options.low/high` and
returns the production inclusive-interval result; reversed intervals reject.
`notice` takes `options.los`, `options.seeanew` (0..3), and `options.gain` to
exercise the actual notification predicate against diagnostic state. It never
changes detection or creates a successful acquisition.

Snapshots additionally expose `brief`, equipment words, map membership and
ordered contact flags by fixture name. These are read-only diagnostics.

C3-master critical handling is a named dependency: the actual critical dispatcher
returns `effect_applied:false` with an unavailable diagnostic because working/
total master accounting and `countWorkingC3MastersOnMech` are not implemented.
The C3-equipped TAG command and the existing C3-destroyed predicate are supported;
this does not claim to implement C3 network damage.

`pending-hide` with `unit` and positive `seconds` creates an explicitly diagnostic
HIDE event sentinel. It verifies acquisition cancellation only: if the sentinel
reaches its deadline it fails instead of fabricating a hide completion.
`diagnose kind=reactor-explosion` invokes the existing production reactor blast
and its sensor flash caller; this is a diagnostic producer, not a simulated
critical-hit sequence. Unit snapshots include `rear_armor` and `internal` beside
front `armor`, so rear hits are observable too.
