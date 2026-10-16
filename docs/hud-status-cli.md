# HUD, status and map displays

Run `python3 -m tools.hud_status --input scenario.json`, or pipe one JSON document
to stdin. The interface extends [repair-economy-cli.md](repair-economy-cli.md),
including its simulation, maps, construction, personnel and aerospace schemas.
All commands operate on those shared units, maps, criticals and event queues.
The display implementation and weapon catalog are local Python data; ordinary
rendering does not read the C reference tree. Loading an optional historical
unit template still uses the existing explicit construction catalog interface.

```json
{
  "hud_display": {"root": "./tmp/display-example"},
  "map": {"size": [20, 20]},
  "units": [{"name": "pilot", "contact_id": "AA", "at": [5, 5, 0]}],
  "sessions": [{"name": "connection", "unit": "pilot"}],
  "config": {"periodic_updates": false},
  "actions": [
    {"op": "hudinfo", "session": "connection", "text": ""},
    {"op": "hudinfo", "session": "connection", "text": "key=demo"},
    {"op": "hudinfo", "session": "connection", "text": "gs"},
    {"op": "command", "unit": "pilot", "name": "status", "args": ["A"]},
    {"op": "command", "unit": "pilot", "name": "tactical", "args": []},
    {"op": "status_query", "unit": "pilot", "kind": "armorstatus", "section": "all"}
  ]
}
```

`results` preserves action order. Displays return `lines`, `message`, `plain` and
command-specific structured fields. Color text retains the source `%c` tokens;
`plain` removes color transport tokens. HUD returns `wire` with exact CRLF and
ordered `records` containing `class`, `type` and `payload`. JSON escapes CRLF;
decoding the string restores the wire bytes. HUD requests are case sensitive.
Each connection has an independent key, initialized empty. Macro/scode callers
can supply `macro: true` to obtain the source refusal.

A session selects either `unit` (a unit object in the local personnel registry)
or numeric `player`. Player resolution checks eligible self, location, then
carried objects. `personnel` settings expose `hardcode`, `zombie` and placement.
Keys are connection state, not unit state.

Ordinary commands use `op: command`, a unit name, command `name` and `args`
as either a raw string or an array whose values are joined with spaces. Use a raw
string to preserve radio text, whitespace and separators, for example
`{"op":"command","unit":"pilot","name":"sendchannel","args":"a=Hold  position; await orders"}`.
Each command then applies its own parser. Supported display commands are `brief`, `contacts`, `scan`, `report`,
`view`, `range`, `bearing`, `vector`, `sight`, `findcenter`, `navigate`, `lrs`,
`tactical`, `status`, `critstatus`, `weaponspecs`, and `enterbase`. Existing fire,
repair, map and aircraft commands remain available. `advance` takes `seconds`
and executes the real queue. Building entry uses TYPE_BUILD links and interior
TYPE_ENTRA objects; it waits 18 ticks, rechecks live conditions, then transfers
the unit and its tow. It is separate from the 12-tick DropShip bay command.

HUD commands are `gs we wl li am sgi oas as c cb asc wsc t con co`.
`asc` and `wsc` take a two-character target ID; `t` takes height and optional
bearing/range/`l`. Successful lists finish with one `D,Done` record, even when
empty. HUD catalog indices are source catalog indices, translated at the display
boundary from the simulation's internal weapon indices.

Read-only `status_query` kinds are `sectstatus`, `critstatus`, `armorstatus`,
`weaponstatus` and `critslot`. Section names/abbreviations follow the actual unit
layout. `armorstatus` also accepts exact lowercase `all`. Omit `section` for all
weapons; an explicitly empty section is invalid. `critslot` uses one-based `slot`
and optional `flag`: NAME, STATUS, DATA, MAXAMMO, AMMOTYPE, MODE or HALFTON.
Unknown flags use NAME. Source errors remain `#-1 ...` in `text`, with `ok: false`.

Unit `display` settings support:

- Text: `mapcolor`, `tacsize`, `lrsheight`, `contact_options`, `status_template`,
  `template_name`, `markings`.
- Booleans: `ansimap`, `hardcode`, `zombie`, `is_observator`, `pkiller`.
- Integers: `brief`, `aim`, `aim_type`, `turn_mode`, `masc_counter`,
  `scharge_counter`, `display_si`, `display_si_orig`.
- `status_expression: true` explicitly requests the unavailable MUX evaluator.
  Literal or already evaluated `status_template` text uses the source armor
  grammar; it does not interpret MUX expressions.
- `display_los_cells`: optional diagnostic objects with `x`, `y`, `flags`.
  Flags are the actual LOS-map bits (1 visited, 2 terrain, 4 elevation, 8 light),
  applied after the live LOS calculation. Results are labeled `diagnostic_los`.
  Pairwise contact LOS diagnostics use the inherited `diagnostic_cache` schema.

`display_configure` accepts a unit and `values` with the same display fields.
Read-only `display_diagnostic` actions accept `kind` and `values` for source
formatter boundaries outside normal unit storage. `kind: "armor_field"` takes
integer `current`/`original` (0..65535), optional `internal` (default 1), `width`
(0..1000, displayed width capped at 23), and boolean `repairing`, `owner`,
`divide`, `show_destroyed` (all default false). It returns the computed `level`,
colored `text` and `plain` field. `kind: "ammo_color"` takes integer `current`
(0..65535) and `maximum` (1..65535), returning the source color prefix.
`kind: "arc_string"` takes integer `mask` (0..31): forward=1, left=2, right=4,
rear=8, turret=16. It returns the source formatter's `text`, including `lv` for
mask 10. This evaluates combined raw bits that real weapon geometry cannot
produce. All diagnostics return `diagnostic: true`, leave the session unchanged,
and accept no expected glyph, color or result. Ordinary readouts use these same
formatters.

`hud_display` configuration additionally accepts `hudinfo_show_mapinfo` (0..2),
`mw_losmap`, `btech_erange`, and boolean `map_in_character` for the main map's
local identity-disclosure policy. Its `root` chooses isolated local storage beneath
which character, economy, map and construction files are created. Use a fresh
root for independent workflows.

Unavailable effects appear in `blocked`; `effects_complete: false` and
`outcome: partial` distinguish a produced readout from a completed external
effect. A refused operation returns `ok: false`. Invalid JSON/schema produces
`error_kind: invalid-input`; document-level errors exit with code 1. Missing MUX
lock evaluation never grants entry. Valid local constant/identity locks work.
No automatic reply is required when radio channel zero is unset or no autopilot
is assigned. An assigned autopilot requiring an unavailable reply is reported.

Six-location fighters retain Nose, Left Wing, Right Wing, Fuselage, Cockpit and
Engine, with five Cockpit slots and armor-only durability. The fighter diagram
uses all six armor sections. Explicit legacy SI formatter inputs are display-only
and do not create or change a gameplay SI pool. A custom fighter template using
`&:0` requires both `display_si` and `display_si_orig`; missing values produce an
explicit dependency result.

Validation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/hud_status
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.run_acceptance --suite hud_status
```
