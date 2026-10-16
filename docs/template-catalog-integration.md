# BTMux template catalog integration

The optional design dependency is [btmux-mechs](https://github.com/KrugerHeavyIndustries/btmux-mechs)
at `b587745c0f6d41515e76b20109953b73f8277599`, recorded in
[template-catalog.lock.json](../template-catalog.lock.json). Python and Git are
required. The existing Construction CLI loads the original files directly.

From a fresh project checkout, materialize and verify the pinned dependency:

```sh
mkdir -p ./tmp
python3 -m tools.template_catalog setup
python3 -m tools.template_catalog verify
```

Setup clones only when the directory is absent. An existing directory is inspected
without checkout/reset/cleanup or file normalization. Revision/content mismatches
return a structured diagnostic and status 1. EOL-only differences are compatible
and reported separately. Normal sessions never download or update anything.
`--path PATH` chooses another dependency directory for either command.

Enable the catalog explicitly in a Construction input document:

```json
{
  "construction": {"catalog": true, "root": "./tmp/custom-templates"},
  "units": [{"name": "u", "at": [3, 3, 0]}],
  "config": {"periodic_updates": false},
  "actions": [
    {"op": "template", "kind": "list"},
    {"op": "template", "kind": "lookup", "reference": "WVR-6R"},
    {"op": "template", "kind": "load", "reference": "WVR-6R", "unit": "u", "origin": "upstream"},
    {"op": "construction_readout", "unit": "u"},
    {"op": "template", "kind": "save", "reference": "MY-WVR", "unit": "u", "clock": "example"}
  ]
}
```

Save that JSON as `./tmp/catalog-session.json`, then run:

```sh
python3 -m tools.construction_templates --input ./tmp/catalog-session.json
```

`construction.catalog` accepts true or an explicit directory string. Explicit
strings take precedence over `BTMUX_TEMPLATE_CATALOG`, then the default
`btmux-mechs` beside the installed project code. Explicit/environment paths are
relative to the invocation directory; the default is relative to the code root.
Omitting catalog or setting false preserves the original single-root interface,
even when the environment variable is set. Enabled catalogs must verify against
the pin before session creation. `construction.root` is the writable custom
root and retains its existing default `./tmp/construction_templates_files`.

A worktree can run setup for its own clone or explicitly select the existing
read-only clone. For an invocation from another directory, install the Python
project and use an absolute catalog path or a path relative to that directory:

```sh
BTMUX_TEMPLATE_CATALOG=/path/to/btmux-mechs \
  python3 -m tools.construction_templates --input ./catalog-session.json
```

These paths are explicit configuration examples. `catalog:true` still must appear in the input.

Lists include reference, relative path, origin, comparison key and collision
membership. Lookup reports `selected` and all equivalent `ambiguities`. Custom
files win by default; `origin:"upstream"` or `origin:"custom"` explicitly selects
a root for lookup/load/read. Each root retains the existing one-level discovery,
24-character case-insensitive comparison and cache rules. See the
[Construction interface](construction-templates-cli.md) for command syntax.
`op:catalog` still means the equipment/part catalog.

Save, editor save, write, delete and initial fixture files use custom storage.
Upstream mutation requests, overlapping roots, traversal and resolved symlink
escapes fail before writing. The inherited map-file interface also rejects
storage or resolved file paths inside the catalog. A custom save can shadow an upstream reference;
both remain listed. Restore retains the originally selected origin/path, and
repair replay uses a per-unit intact baseline so shadows and other loaded units
cannot replace that baseline. A fresh explicit custom load uses the custom file.

Loading clears the pilot. Seat one with `construction_pilot` before ordinary
startup, motion, targeting and firing. Numeric speed-command arguments are KPH.
Modern saves serialize design armor and full ammo; they are not transient combat
snapshots. Preserve the accepted mixed fire/ammo mode correction and legacy 4196
flag behavior described in the Construction contract.

Two compatibility corrections apply to shared production code:

* C1 accepts LF and CRLF centrally, including multiline values. It preserves
  interior CR, source final-byte deletion, bounds and ordered failure writes.
* C2 corrects the source integer `(2 / 3)` standard jump cap to floating two-thirds,
  retaining float32 max speed, the established `1/10.75` conversion, truncation,
  installed-slot counting, improved-jet halving/cap and sink behavior. WVR-6R
  now has 5 MP/53.75 KPH; BLR-1G and WHM-6R remain 0. Repair/replay uses the same rule.

The catalog also exposed a loader translation defect: assigning a Clan/DoubleHS
flag after `Heat_Sinks` could double Python's reported dissipation. C's
`MechRealNumsinks` is direct storage (`btmacros.h:169`), so flag assignment must
preserve that value. Modern and legacy readers now preserve the source capacity
across technology assignment. MadCat-Prime keeps 34 and Grendel-Prime keeps 24.
This is a Python translation repair, not an additional change to C gameplay.
Synthetic constructors retain their physical-sink representation.

Monitor also exposed a translation error in speed/heading guards: the port used
strictly submerged `InWater` where C uses `WaterBeast && NotInWater`. Hull/foil
craft may now maneuver at the water surface (`OnWater`, Z<=0), while land and
above-water cases remain rejected. Other submerged-water consumers retain their
strict predicate. This restores the existing C command behavior.

Run the complete raw audit without writing inside the dependency:

```sh
python3 -m tools.template_catalog audit --output ./tmp/catalog-full-report.json
python3 -m tools.template_catalog audit --reverse --output ./tmp/catalog-reverse-report.json
```

`--path` may select an unpinned/drifted disposable fixture for audit; the report
marks it unverified. This does not weaken ordinary session verification. Audit
inventories actual regular files recursively, records metadata/symlink exclusions
and missing tracked files, and attempts each raw file with a fresh cleared unit
through the modern production loader/finalizer. It preserves the first error
without legacy fallback. Reports contain hashes, types, provenance, discovery,
collisions, partial failure state, concrete failure causes and normalization notes.
Order is stable; `--reverse` changes execution order only. Exit 0 means a complete
inventory with no load failures, exit 2 a complete inventory with load failures,
and exit 1 a configuration/interruption error. Parsing success alone does not
establish gameplay compatibility.

The [six-location fighter interface](six-location-aerofighters-cli.md) supports
the original CHP-W5 layout with all six locations. Use `audit` for current
catalogue compatibility results; parser success alone does not establish every
design's gameplay compatibility.

Optional acceptance verification:

```sh
python -B -m tools.run_acceptance --suite template_catalog
```

See [QA prerequisites](../qa/README.md) for the external feature parser.
For an installed wheel, prefer `setup --path PATH` and `verify --path PATH`, then
set `BTMUX_TEMPLATE_CATALOG` or `construction.catalog` to that directory. The
default is beside the installed packages and may not be a writable location.
The distribution includes the same pinned lock as the root lock file.
