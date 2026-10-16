# Aerospace JSON interface

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m tools.aerospace --input ./tmp/flight.json`,
or send the same JSON on stdin. Output has ordered `results`, final `state`,
and named random `draws`. The interface extends [communications](communications-cli.md),
[pilots](pilots-cli.md), [construction](construction-templates-cli.md), and
[core simulation](core-simulation-cli.md). Units, maps, weapons, critical slots,
characters, templates, events and clocks are shared with those interfaces.

Normal refusals return `ok:false` or inherited `accepted:false` in a result.
Action validation failures return `ok:false,error`; invalid top-level input
exits nonzero with JSON on stderr. Check every result, including template load.
`inspect` records an intermediate snapshot. `advance` runs real scheduled events.
Omit `random.streams` for seeded source dice; supplying it requires a finite
stream for every consumed name, and exhaustion is an action error.

```json
{
  "maps":[{"name":"field","id":1000,"size":[30,30]}],
  "units":[{"name":"craft","id":10,"class":"VTOL","movement":"VTOL",
    "at":[10,10,0],"core":{"max_speed":60,"fuel":100},
    "aerospace":{"landed":true}}],
  "actions":[
    {"op":"command","unit":"craft","name":"takeoff"},
    {"op":"advance","seconds":1},
    {"op":"inspect"},
    {"op":"advance","seconds":2}
  ]
}
```

VTOL launch executes at the first second. Aerofighter launch takes eleven
seconds including the initial callback; dropships take301. A nonzero TAKEOFF
argument requires a wizard actor and selects the source countdown. `land`
while landed aborts a pending launch. Landed aerofighters and aerodyne dropships
use `speed`; airborne craft use `thrust`. Flight requires the ordinary pilot,
fuel, terrain and movement gates. The fixture fields below set initial state;
they are not gameplay commands that earn it.

| Command | Arguments |
|---|---|
| takeoff | optional wizard countdown |
| land | none; abort pending launch or attempt landing |
| thrust | optional kph; empty queries desired thrust |
| climb / dive | optional signed integer angle; empty queries angle |
| heading / speed / vertical / eta | inherited movement arguments |
| checklz | empty for current hex, or `x y` |
| bomb | `list`, `aim`, or `drop <one-based-live-bomb-number>` |
| createbays | zero to four map names or numeric references |
| enterbay | optional dropship contact ID |
| findcenter / navigate / tactical / lrs | live map readouts (`lrs` requires mode, e.g. `m`) |
| critstatus / status / weaponspecs | current sections, status and physical weapon catalog |

Critical slots are the payload and door authority. Use inherited `section`
actions or template/editor commands to install source parts. `bomb list`
includes destroyed bombs; release numbering skips destroyed slots. Release
removes the selected slot, refreshes carried cargo and schedules a captured
map/hex/bomb impact. No damage occurs before its event. Inferno uses the shared
timed burning service, not an immediate `weap_heat` increment.

Unit `aerospace` fields and `{"op":"aero_configure","unit":"u","values":{...}}`:

- Numeric: `start_fx`, `start_fy`, `start_fz`, `fx`, `fy`, `fz`, `speed`,
  `desired_speed`, `vertical_speed`, `max_speed`.
- Integer: `desired_angle`, `desired_facing`, `start_spin`, `fuel`, `fuel_orig`,
  `x`, `y`, `z`, `elev`, `targ_x`, `targ_y`, `targ_z`, `target`, `tac_range`,
  `lrs_range`, `carrying`, `last_dropship_notice`.
- Boolean: `landed`, `spinning`, `zombie`, `free_fuel`.
- `bays`: exactly four map names or numeric IDs; unused entries are `-1`.

Use inherited `place` to update both hex and real coordinates coherently.
Direct coordinate/vector fields permit source boundary diagnostics. Map
`bay` and `bay_configure` accept `onmap` (parent unit name/ID), `in_character`,
`enter_lock`, `lock_result`, and `fail_message`. Supported local locks are
empty/`true`/`*`, `false`/`!*`, and `#<unit-id>`. Other MUX expressions require
an explicit adapter result; otherwise entry refuses with an undelivered
lock-evaluator request. `createbays` links the maps' parent references.
Entry completes after12 seconds with source callback rechecks. Crossing a bay
map edge uses the normal movement/transfer service. Personnel and carried units
move locally; MUX notification and teleport transport requests remain external.

Top-level `turrets` holds `{name,id,parent,gunner?,arcs?,target?,targ_x?,targ_y?,
targ_z?,lockmode?}`. Names/IDs must be unique. Parent and target may name units;
gunner is a character ID. These are actual registered rooms. Create connected
characters at those room IDs using the inherited `characters` schema, then:

```json
{"op":"turret","turret":"nose","actor":200,"name":"initialize"}
{"op":"turret","turret":"nose","actor":200,"name":"lock","args":"BB"}
{"op":"turret","turret":"nose","actor":200,"name":"fire","args":"0"}
```

These are three separate action objects. Active turret commands are `bearing`,
`eta`, `findcenter`, `fire`, `lock`, `lrs`, `navigate`, `range`, `sight`,
`tactical`, `contacts`, `critstatus`, `report`, `scan`, `status`, `weaponspecs`,
`initialize`, and `deinitialize`. Source aliases `fireweapon`, `settarget`,
`lrsmap`, and `tacmap` also work. Five TIC names accept silently, as their C
bodies are disabled. Locks belong to each turret; heat, ammunition, damage and
recycling belong to the parent physical mounts. The source IC pilot-only fire
guard still applies: successful remote turret firing needs an OOC craft or a
wizard caller. Map output contains current terrain/elevation/contact cells and
rows suitable for a local console, rather than MUX terminal color rendering.

The public diagnostic `{"op":"turret_diagnose","turret":"nose","selector":1}`
invokes the source allocation helper on that object's data and reports the result.
Selector 1 resets target/target XY while preserving gunner, target Z and arcs;
selector 0 exercises the source's inert free body. Object identity stays fixed.

`aero_diagnose` directly invokes production helpers for boundary inspection:
`speed`, `heading`, `control`, `update`, `fuel`, `bridge`, `exhaust` (damage),
`warning` (severity), `lz` (optional x/y), `calc_dest`, `simulate_flight`
(x/y/time), `destroy_bomb` (direction/location), `takeoff_event` (count),
`edge`, `move`, and `doors` (ship, direction, reference). Top-level
`aerospace.blzmapmode` selects the existing blocked-LZ mode.

Snapshots add each unit's `aerospace` state/payload, all `turrets`, current
pilot/arc `overrides`, and captured `bomb` records on pending artillery-hit
events. Inherited snapshots expose rosters, map objects, critical slots,
weapon recycling, cargo, characters, inboxes and external requests.

Normal APS subprocess examples live in `acceptance/aerospace/workflows.py`.
They load genuine `DS.Union`, `Cavalry`, and `WVR-6R` designs copied from the
configured read-only pinned catalog into isolated `./tmp/` storage. Set
`BTMUX_TEMPLATE_CATALOG` if that catalog is elsewhere. No synthetic design is
substituted if a required file cannot be read or loaded. The inherited catalog
setup/verification commands are documented in the construction interface.

Repair scheduling, persistent stores, cargo transfers and towing are available in
[the repair/economy extension](repair-economy-cli.md), which shares this session.
