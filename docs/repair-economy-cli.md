# Repair, economy and cargo JSON interface

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m tools.repair_economy --input ./tmp/repair.json`,
or send the JSON on stdin. This extends the [aerospace session](aerospace-cli.md),
including its construction, characters, combat, movement, notifications and clocks.
It adds ordinary maintenance and cargo commands to those same engine objects.
Output contains ordered `results`, actual final `state` and consumed random `draws`.
Use `inspect` for intermediate snapshots and `advance` for real scheduled work.
Check each result: command refusals and action validation errors have `ok:false,error`;
inherited commands may use `accepted:false`. Invalid top-level input exits nonzero.

This example repairs three points of front armor. Copy it to the input file above.
The first point completes at180 seconds; the last at540. Resources are consumed
at command time. All paths are writable local adapters; use a fresh directory for
an independent fixture. Supplying initial object attributes deliberately writes them.

```json
{
  "pilots":{"root":"./tmp/repair-demo/characters"},
  "construction":{"root":"./tmp/repair-demo/templates"},
  "file_root":"./tmp/repair-demo/maps",
  "repair_economy":{"root":"./tmp/repair-demo/economy",
    "objects":[{"id":1000,"ECONPARTS":"[547,0,3]"}]},
  "map":{"id":1000},
  "config":{"periodic_updates":false},
  "units":[{"name":"u","id":10,"character":101,"started":false,
    "repair":{"stall":true},"measured_mass":51200,
    "sections":[{"index":4,"internal":10,"internal_orig":10,
      "armor":7,"armor_orig":10}]}],
  "characters":[{"id":101,"name":"Technician","tech":true,"location":10,
    "values":{"Build":5,"Reflexes":5,"Intuition":5,"Learn":5,
      "Technician-Battlemech":6}}],
  "random":{"streams":{"tech_rolls":[12]}},
  "actions":[
    {"op":"command","unit":"u","name":"fixarmor","args":"CT"},
    {"op":"inspect"},
    {"op":"advance","seconds":540},
    {"op":"command","unit":"u","name":"checkstatus"}
  ]
}
```

## Ordinary commands

Use `{"op":"command","unit":"u","name":"replacepart","args":"CT 1"}`.
Unit names identify live units; contact IDs identify pickup/cable targets. An integer
`actor` on a command selects a real character without changing the unit's pilot.
An omitted unit selects `u`, or the inherited default unit.

| Commands | Arguments |
|---|---|
| `replacepart`, `repairpart`, `removepart` | section and one-based critical slot |
| `replacegun` | zero-based global mount, or section/one-based slot; optional catalog brand name |
| `repairgun`, `removegun`, `fixenhcrit` | zero-based global mount, or section/one-based slot |
| `reload` | section/slot, optional ammunition letter |
| `unload` | section/slot |
| `toggletype` | section/slot and required ammunition letter (`-` means normal) |
| `fixarmor` | section, optionally `r` for rear armor |
| `fixinternal`, `reattach`, `reseal`, `removesection`, `replacesuit` | section (`S1`..`S8` for suits, limited by template maximum) |
| `fixextra`, `magic` | no arguments; retain their source clearance and template dependencies |
| `techstatus`, `checkstatus`, `repairs`, `damages` | technician backlog, unit completion estimate, pending jobs, or ordered repair/salvage plan |
| `fix` | one-based damage row, or `low-high` snapshot range |
| `manifest`, `stores` | optional long-name inventory filter |
| `Raddstuff`, `Rremovestuff` | catalog selector and positive count; actor's room |
| `Rfixstuff`, `Rresetstuff` | clean or clear actor's room inventory |
| `loadcargo`, `unloadcargo` | catalog selector and positive count |
| `pickup`, `dropoff` | target contact for pickup; no arguments for dropoff |
| `attachcables`, `detachcables` | tower/load contacts, or tower contact respectively |

Maintenance uses real Tech clearance, startup/stall guards, unit-family or weapons
skills, absolute technician backlog, shared stock and the event queue. A successful
command means the work was queued; inspect its deadline and subsequent state.
Some failures queue a fake job that reserves time and conflicts without repairing.
`fix` continues its original numbered snapshot after a row refuses resources.
Readout rows use `null` minutes/BTH for work already queued.

## Fixture and persistence controls

`repair_economy` accepts `root` (default `./tmp/repair_economy`), integer `restart`
for the lag calculation, `config`, and `objects`. Configuration keys are
`limitedrepairs` (default0), `maxtechtime` (600 minutes), `variabletechtime` (0),
and `techtime_mod` (0). Use defined positive variable-time divisors; invalid
arithmetic is reported explicitly. These options do not enable the obsolete
free-time or complex-repair compile-time branches.

Each object record has a required nonnegative `id`, with optional text `ECONPARTS`,
`TECHTIME`, `MECHSKILLS`, and boolean `in_character`. Maps, units and characters are
registered by real identity. `ECONPARTS` holds `[source-part-id,brand,count],...`;
it is shared by stores, repairs, salvage, cargo and mass calculation. Source IDs
are distinct from the runtime weapon/ammunition IDs in critical slots. Ordinary
find/change retain first-duplicate semantics; cleanup and listings aggregate.
Inventory and technician attributes persist in `root/objects.json` after writes.
Character skills and flags persist in the inherited character directory.

Characters add boolean `tech`; inherited `wizard` remains separate. The `actor`
action below also sets `god` for pickup/cable guard diagnostics. Source GOD identity
is character ID1, including the inventory administrator match-limit exception.
Units add `repair:{stall,towable,location,max_suits,burn_recovery_countdown}`. Booleans are strict;
`max_suits` is0..8 and comes from original templates when loaded. `location`
updates the actual personnel object relationship. Hangar `MECHSKILLS` is the
loading-bay `x y [reveal]` text; the optional nonzero third integer reveals required
coordinates after a position refusal. Unit Location must equal its map ID for
cargo transfer. Repairs use the unit's Location; DropShips use `aerospace.bays[0]`.

Fixture-only units that carry cargo or tow need `measured_mass` in1024 units/ton,
or a loaded construction template. No mass is guessed for missing dependencies.
Use inherited `section` actions for actual slot `type`, `brand`, `firemode`,
`ammomode`, `data`, `weap_damage_flags` and armor/internal fields. Existing aerospace,
map/contact, character and movement fixture controls remain available.

| `op:"repair"`, `kind` | Additional fields and result |
|---|---|
| `objects`, `persist` | inspect all object attributes, or flush them |
| `configure_object` | `values:{id,ECONPARTS?,TECHTIME?,MECHSKILLS?,in_character?}` |
| `configure` | `unit`, `values:{stall?,towable?,location?,max_suits?}` |
| `actor` | `actor` ID, `values:{tech?,wizard?,god?,location?}`; location updates contents too |
| `config` | `values` containing the four repair configuration keys |
| `status` | `actor` ID; technician backlog |
| `attribute` | `object`, `attribute` (`ECONPARTS`, `TECHTIME`, `MECHSKILLS`), optional text `value` |
| `find`, `change`, `set`, `remove`, `add` | `object`, source numeric `part` or catalog long name, optional `brand`0..5; change/set/add require integer `count`; add appends a raw entry; remove deletes the first raw matching entry and returns whether an attribute write occurred |
| `inventory` | `object`; structured current inventory listing |
| `save`, `load` | optional local `file` (default `repairs.jsonl`); load alternatively accepts `text` |

Save/load handles the repair queue only. Save actual unit/section state separately
through the existing fixture/session controls; recreate the same object IDs when
loading into a fresh process. To retain persisted stock/backlog, omit initial
attribute overrides and reuse the inventory and character roots. A queue load
adds jobs to the current queue, so load a checkpoint once into a fresh queue.
No resource debit, skill roll or XP is repeated by loading.

The stable local format is one JSON array per line:
`[unit_id,source_event_type,signed_remaining_seconds,packed_payload]`, terminated
by `[-1]`. Remaining time is clamped to1; negative means fake. Records are ordered
by source type, then the queue's source-compatible traversal order. This is not
native C binary compatibility: C's long/int width mismatch is ABI dependent.
Malformed/truncated or invalid-reference input retains the valid loaded prefix
and returns a bounded `error`; unknown types are skipped. The source omission of
real type56 means real reseal jobs are skipped; fake type56 jobs are restored.

## Diagnostics and observations

`op:"repair_diagnose"` accepts `unit` and optional real `actor`. Diagnostic `loc`
is zero-based, `pos` zero-based, and `extra` unsigned8-bit; rear point jobs encode
location+8. These controls call production helpers and do not replace commands.

| `kind` | Additional fields |
|---|---|
| `parsepart` | `argument`, optional booleans `position`, `rear`, `extra` |
| `parsegun` | `argument`, optional boolean `brand` |
| `validgun` | `loc`, `pos` |
| `pack` | `loc`, `pos`, `extra`; actor ID must fit0..32767 |
| `schedule` | source `type`43..58, `payload`, optional `delay`, `fake`, `callback` |
| `count` | source `type`, `loc`, optional `pos`; preserves count-valued queries |
| `repairing`, `scrapping_part`, `can_scrap_part` | `loc`, `pos` |
| `fixing`, `can_scrap_location`, `repair_path`, `scrap_path` | `loc` |
| `latest`, `intact_internal`, `fixable`, `damage_table`, `scrap_table`, `machine` | no additional fields; fixable uses the existing class-specific repairability predicate |
| `economy`, `failure`, `success` | source `helper` name; economy/failure use `loc`, `pos`, optional `amount` |
| `roll` | integer modifier `amount`, boolean `brand:true` selects weapons skill |
| `add_time`, `variable` | `minutes`; variable also requires signed `margin` |
| `lag` | optional integer `amount` to adjust |
| `queue_tick` | nonnegative `amount` up to1000000 sets the event clock without dispatch or wall-clock advancement; a diagnostic fixture for due/overdue queue checkpoints |
| `cargo_weight`, `correct_speed`, `proper_armor`, `proper_internal` | no additional fields |
| `alias_part` | source `part` ID or catalog name |
| `ammo_mode`, `ammo_type` | `loc`, `pos`; ammo_mode also requires letter `argument` |

Source event IDs:43 part replacement,44 gun replacement,45 reattachment,46 ammo,
47 armor,48 internal,49 section removal,50 part removal,51 gun removal,52 gun repair,
53 part repair,54/55 inert bomb callbacks,56 reseal,57 suit,58 enhanced critical.
The live repairgun command intentionally queues its whole-gun callback under53;
a save/load restores the type53 part-only callback, as C does. Explicit callbacks
use the names exposed in `state.repair_jobs`; they are diagnostics for valid source
locations and criticals, not a way to install arbitrary engine code.

Named finite random streams are `tech_rolls` (2..12), `tech_d6` (1..6, three dice
per aptitude roll), and `repair_percent` (5..44 for points,5..94 for legacy refunds).
Inherited sensor/combat consumers need their own streams when reached. Omit
`random.streams` to use the shared seeded generator. The character advantage is
`Tech_Aptitude`. Inspect consumed draws rather than assuming a failed prerequisite
rolled dice. `advance` runs both clocks normally; inherited `clock skip_seconds`
advances wall time without dispatch, and `clock dispatch` resumes the event loop.
`state.clocks` and `repair_economy.restart` support reproducible lag inspections.

Snapshots add raw object attributes and writes, technician configuration/messages/
rolls, repair completion messages, cargo messages, and each job's type, actor,
unit, location, position, extra, packed payload, due/remaining, fake flag and callback.
Each unit includes its real carrying relationship and repair fixture fields.
Existing character inboxes, personnel contents and external requests remain visible.

## Source limitations and external boundaries

The local attribute/character stores and notification inboxes operate. MUX network
channel delivery, logging transport, opaque server lock evaluation, attribute hooks
and client rendering remain explicit undelivered requests in the inherited adapters.
No server delivery is claimed. Missing original templates are reported by the
existing construction adapter; scratch/catalog roots cannot overlap.

Eleven success helpers return0 without mutation; both bomb-fitting callbacks are
inert. Pickup/cables share `carrying`/`towed_unit` with movement and release.
Cargo speed deliberately uses the previous cargo weight for its first clamp.
AeroFighters retain Nose,Left Wing,Right Wing,Fuselage,Cockpit,Engine and armor-based
destruction. Reattachment at zero armor restores bookkeeping internal1 and leaves
the location armor-destroyed; subsequent armor repair still refuses that location.
This source limitation is preserved. Positive damaged armor can be repaired normally;
SI does not replace the approved fighter rules.

Diagnostic `burn_recovery_countdown` is an integer0..1000000 fixture field for
the existing tow burning-target guard. Unit `repair` snapshots expose its current
value and `swarm_target` alongside the shared carrying relation.
