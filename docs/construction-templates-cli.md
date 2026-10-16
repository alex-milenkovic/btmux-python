# Construction templates CLI

Run `python3 -m tools.construction_templates --input ./tmp/input.json`, or send
the JSON document on stdin. Output contains `results`, final `state`, and the
shared simulation's `draws`. This extends the Maps (`tools.maps_environment`),
[Core](core-simulation-cli.md), and [Combat](combat-resolution-cli.md) session
interfaces. All ordinary commands, clocks, damage, repair, sensors, weather and
map operations use the same registered units and events.

`actions` is required. Add a `construction` object with `root` (local directory),
optional `files` (relative filename → ASCII brace text), and Boolean `parts`,
`clan`, `dynspeed` (all default true). Root defaults to
`./tmp/construction_templates_files`. Parent directories for fixture files are
created. Existing files remain available across fresh CLI processes. Paths must
stay within the designated root. `files` at the top level still means map files;
template files belong in `construction.files`.

`editors` is an array of `{name,id,allocated?,target?}` objects. It defaults to
one allocated editor `e` with id1 and no target. Each editor keeps an independent
target. `target` may reference a unit name or source object ID; `-1` is unset.
Commands require Boolean `privilege:true` (default), allocated editor data, then
a selected existing unit. `settarget` requires no prior target. This is a local
permission model; persistent MUX accounts and attributes are not provided.

```json
{
  "construction":{"root":"./tmp/my-templates"},
  "editors":[{"name":"builder","id":70}],
  "units":[{"name":"u","at":[3,3,0]}],
  "config":{"periodic_updates":false},
  "actions":[
    {"op":"editor","editor":"builder","name":"settarget","args":"u"},
    {"op":"editor","editor":"builder","name":"resetcrits"},
    {"op":"editor","editor":"builder","name":"settons","args":"50"},
    {"op":"editor","editor":"builder","name":"setspeed","args":"6"},
    {"op":"editor","editor":"builder","name":"addweap","args":"IS.AC/5 LT 1 2 3 4"},
    {"op":"editor","editor":"builder","name":"reload","args":"IS.AC/5 RT 1"},
    {"op":"editor","editor":"builder","name":"savetemp2","args":"CUSTOM","clock":"fixed","caller":"Builder","caller_id":70},
    {"op":"construction_readout","unit":"u"}
  ]
}
```

Editor arguments are source whitespace-delimited text, with one-based critical
slots. `setspeed` and `setjumpspeed` accept MP and store float32 KPH ×10.75.
The editor supports:

| Command | Arguments |
|---|---|
| settarget | unit name or `#id` |
| resetcrits | none; source default criticals |
| displaysection | source section abbreviation |
| settype / setmove | source initial-based selection |
| setspeed / setjumpspeed / settons / setheatsinks | scalar |
| setlrsrange / settacrange / setscanrange / setradiorange / setradio | scalar |
| setarmor | section [front [internal [rear]]] |
| repair | section A/I/R/C/S [value or critical slot] |
| addweap | exact very-long weapon name, section, critical slot(s), optional R/T/O |
| reload | exact weapon name, section, slot, optional mode character |
| restock | section, slot |
| firemode | zero-based weapon number, mode character |
| addspecial | exact special name or empty, section, slot, optional data |
| addtech / deltech / addinftech | source whitespace-separated technology names |
| showtech | none |
| setcargospace | half-tons, maximum carried-unit tons |
| loadnew / savetemp2 / savetemp | reference (modern save / legacy save) |
| restore | none, uses the unit's stored local reference |

Each editor result contains `ok`, `messages`, and optional `result`. Invalid weapon/special errors also return a structured `catalog` with the source
header and rows. A negative setarmor field emits its source warning but later fields still apply. A later
bad critical slot preserves earlier writes. The separate direct-unit infantry
delete is `{"op":"delinftech","unit":"u"}`; it has no MECHREP privilege/target
wrapper, as in C.

Template operations use `{"op":"template","kind":...,"unit":"u",...}`.
Kinds `load`, `save`, `lookup`, `write`, `read`, `delete` take `reference`.
`restore` takes a unit; `list` and `reset` need neither. `write` takes `text`;
`read` returns `text`. `save` optionally accepts `legacy:true`, `clock` (fixed
comment text), `caller`, and `caller_id`. Save names cannot contain slash.
Load clears rd/ud first and retains defined partial writes if both modern and
legacy parsing fail. Load removes the pilot; `construction_pilot` seats a new
local actor before normal startup, targeting and firing:

```json
{"op":"construction_pilot","unit":"u","actor":{"gunnery":4,"piloting":5}}
```

The cache scans root files plus one immediate non-dot directory level. Entries
compare case-insensitively over24 characters; scanned filenames truncate at34.
Root entries precede subdirectory entries; within each directory names are
enumerated in bytewise order, and equal comparison keys keep that insertion
order. `lookup.ambiguities` reports all equivalent candidates; the first wins.
This is the port's stable tie policy, not a claim about C qsort/bsearch tie order.
A miss keeps the cache; an unreadable hit invalidates once. A slash-containing
reference uses direct/old ordered-subdirectory lookup. Save resets the cache even
if its arguments subsequently fail.

`construction_readout` returns source/runtime IDs for every critical, modes,
data, brand, electronics, reference, technology, payload, design terms and current
cached mass. Mass units are1/1024 ton. `construction_validate` optionally takes
`correct` (default true) and `interactive` (default0); it performs ordinary internal
validation then reports weight. Unchanged originals preserve combat damage.
Managed file/editor units fingerprint weight inputs before cache use, so firing,
damage and repair are visible at the next readout. This adapter does not add
speed rules. The existing cargo-speed consumer now takes computed construction mass
for managed units (including a managed tow), honoring dynspeed. Explicit legacy
fixture mass remains supported for units outside construction management.

Catalog operations use `op:catalog` and `kind`: `names` (text base name or source
`part`, optional brand); `match` (form short/long/vlong, text, cursor default−1);
`partname` (packed number in text and form selector); `partmatch` (text);
`list` (sorted form); `weapons`; `specials`; `identify`; `weapon_index`;
`special_index`; `weapon_id`; `legacy_ammo_id`. The last helper keeps source
index+101, distinct from modern ammo base193. Packed stride is1024. `wizard`
controls partname/partmatch's source guard.

Diagnostic fixture extensions are explicit: each unit may carry `construction`
fields `zeroed`, computer/radio/radio_type, si/si_orig/fuel_orig, mech_bv,
cargo_space/max_suits/car_max_ton, original_sinks/hs_engine_override/rtons/xp_mod/
units_killed, unit_era/unit_tro/template_ref/name, and16-entry freq/freqmodes/
chantitle arrays. `construction_value` applies the same object as `values`.
`construction_diagnose` takes `kind` and positional `args`: engine_weight,
crit_weight (runtime part ID), weight (interactive), ammo_weight, ammo_mod (zero-based
section and slot), finish_load (Clan-item-seen, parts), find_section, showtech, clear
(clear_channels), load_modern, load_legacy, mode_masks, suspension, get_weight.
These are boundary probes; ordinary load/edit/save remains the gameplay path.

Construction command errors return `ok:false` without terminating subsequent
actions. Invalid top-level JSON/schema returns nonzero with a structured error on
stderr. Invalid arrays, unsupported IDs and unsafe memory-domain inputs are errors.
The source's defined arithmetic, partial writes, modern design-armor/capacity
serialization and legacy current-armor/format losses remain observable.

The mixed-mode parser correction allows modern pipe mode tokens
from either fire or ammo tables in one field, rejects every unknown token, and
assigns both masks only after successful validation. The standalone strict parsers
and editor tech parsers retain their separate-table rules.

Modern loads record requested persistent `A_MECHREF` writes under each unit's
`construction.external_effects`, explicitly marked `delivered:false`. Local
reference storage and restore work; persistent MUX attribute delivery is unavailable.
The legacy literal4196 mask removes Clan32:32→0 and33→1, retaining radio55.

Additional QA boundary readouts under `construction_diagnose` expose the existing
source helpers: `parse_bits` takes `[parser, table, text]`, where parser is
`strict`, `lenient`, or `delimited` and table is `fire`, `ammo`, or an array of
names; `read_desc` takes `[same_line, remaining_stream?]`; `computer_conversion`
takes no arguments; `section_index` takes section text; `short_section` takes a
zero-based location. `load_fields` takes a reference and exposes immediate modern
field writes without finalization. `load_reference` takes a reference and returns
an isolated cached template snapshot or null. These are diagnostic boundary
coverage; the ordinary procedures use live load/edit/save/restore commands.

The construction readout also exposes all sixteen channel frequencies, modes and
titles under `channels`, and the numeric `infantry_specials` mask.

`weight_cache` reports value and recomputation count. With no arguments it uses
the real weight calculation; an optional integer isolates only the cache
computation dependency, and the result explicitly marks `fixture:true`.

`construction.create_root` defaults to true. Set it to false to skip initial
directory creation and expose ordinary missing-directory lookup/save errors.
Explicit fixture files still create their parent directories. Name/Era/TRO loads reject values beyond
the C storage limits of 30/24/24 ASCII characters before assigning that field.
