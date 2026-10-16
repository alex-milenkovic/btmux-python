# Pilots, infantry and battle armor CLI

Run a JSON document through `python3 -m tools.pilots --input <path>`, or supply it
on standard input. The response contains ordered `results`, final `state`, and
actual named `draws`. The interface extends the accepted Construction, Maps,
Core, Combat and Sensor commands; their existing argument syntax still applies.
All storage roots in the following example are local writable directories.

Both `config.extended_gunnery` and `config.extended_piloting` default to false.
Mech weapons use `Gunnery-Battlemech`, biped/quad control uses
`Piloting-Battlemech`, and ground/naval control uses `Drive`. Existing broad
mappings for the other classes and dedicated special skills are retained.
Explicit true opts into either expanded selector independently, including
mixed settings; see [core configuration](core-simulation-cli.md). Selection
also governs the corresponding XP skill. Stored character values are not
migrated, and scalar ratings, machine overrides and separate gunners retain
their existing behavior.

```json
{
  "pilots": {"root": "./tmp/example-characters"},
  "construction": {"root": "./tmp/example-templates", "catalog": true},
  "file_root": "./tmp/example-maps",
  "config": {"periodic_updates": false, "extended_piloting": false},
  "characters": [
    {"id": 101, "name": "Alice", "location": 10, "wizard": true,
     "values": {"Build": 5, "Reflexes": 5, "Running": 4}}
  ],
  "units": [{"name": "u", "id": 10, "class": "MW", "character": 101,
             "in_character": true, "started": true, "at": [3, 3, 0]}],
  "actions": [
    {"op": "character", "kind": "status", "caller": 101},
    {"op": "character", "kind": "skill", "player": 101, "name": "Running"},
    {"op": "character", "kind": "save"},
    {"op": "inspect"}
  ]
}
```

For a fresh process reload, use the same `pilots.root` and omit the `characters`
creation records. IDs may not be created twice. Character categories are stored
as source text in per-character JSON files; the engine reads that text through
the production parser. A unit's `character` attaches the existing record by ID.
A record's `location` determines actual pilot eligibility; attaching a character
does not teleport it. Ordered local contents are exposed in `state.personnel`.

Character creation supports `values`, raw `categories` (`health`, `attrs`,
`skills`, `advs`), `location`, IC/player/connected/valid/alive metadata, privileges
`wizard`, `wiz_r`, `god`, and `pcequip`/`mwtemplate`. Character values are source
skill levels, not direct combat BTH. Unattached legacy pilot fixtures retain their
accepted direct-BTH meanings. Stored Speed_Demon, Maneuvering_Ace, Dodge_Maneuver,
Melee_Specialist and Pain_Resistance values feed existing movement, physical
combat and explosion consumers; only value1 enables these Boolean advantages. The full 119-name table is available through
`{"op":"character","kind":"values"}`.

Character actions use `op: character` and a `kind`:

| Kind | Inputs / result |
|---|---|
| `get`, `set` | `caller`, optional `target`, `name`, `flag`, and setter `amount`; source permission checks apply |
| `status`, `clear` | `caller`, optional `target`; source control permissions apply |
| `create` | `record`, with the same schema as a creation entry |
| `save`, `reload` | Persist records or reread the character directory |
| `list`, `values`, `lookup` | Source lists and lookup; use `name`, optional `player`, or `flag` as appropriate |
| `target` | `player`, `name`, optional `modifier`, `use_xp`; effective source BTH |
| `skill`, `margin` | `player`, `name`, optional `modifier`; actual Number-based character dice |
| `opposed` | `player`, `name`, `other`, optional `other_skill`; ordered opposed rolls |
| `attribute`, `advantage` | `player`, `name`; attribute saving roll or exact-one Boolean advantage |
| `dice` | `name` (`saving`, `unskilled`, `skilled`, `d6`), optional `count` |
| `gain`, `lower`, `next` | Skill `name`/`amount`/optional `override`, loss `promillage`, or next threshold |
| `threshold`, `getthreshold`, `top` | Source `args` control string or skill `name`; threshold logs include `caller` |
| `duration` | Seconds in `amount`; source duration formatting |

The diagnostic `op: character_diagnose` exposes raw category/array boundaries.
It supports `read`, `store`, `pack`, and `categories`, requires `player`, and
accepts category `mask` (HEALTH1, SKILLS2, ATTRS4, ADVS8, ALL15). This is separate
from player-facing permission checks and ordinary gameplay consumers.

Ordinary unit controls use `op: command`, a unit name, command `name`, and either
an argument string or an array of strings. `actor: <character-ID>` selects an
invoking character without changing the unit's pilot. Commands include `eject`,
`disembark`, `udisembark`, `embark <contact-ID>`, `pickup <contact-ID>`,
`swarm <contact-ID>`, `swarm -`, `attackleg <contact-ID>`, `hide`, and `jettison`.
Use the unit's two-character contact ID, as with existing targeting commands.
`advance` and the accepted `clock` operations execute normal event callbacks.
Newly created MechWarriors appear as `mw<dbref>` in the unit registry and can be
controlled through the same interface. Their templates come from the genuine
read-only catalog or the writable custom template directory. Source MechWarrior
templates load already started. Ejection/disembark creation registers the new
unit with the normal contact/event lifecycle; use ordinary movement and firing
after advancing that clock, without a redundant startup command.

`personnel` unit fields configure `official_pilot`, `location`, `enter_lock`,
`lock_result`, `fail_message`, `location_ic`, `hardcode`, `opaque`, `going`, `dark`,
and `zombie`. An empty enter lock uses the source team rule. A nonempty lock with
an explicit true/false `lock_result` uses that supplied service decision. A lock
without a decision reports its unavailable external evaluator. Failure attributes
and loud transfer hooks are recorded separately from actual local movement.

`op: personnel` supports `attach` (`player`), `configure` (`values`),
`initialize`, `discard`, `enter_bay` (`destination`), `kill_contents`,
`fix_health`, `consciousness_target`, `head`/`lethal` (`amount`), and `transfer`
(`origin`, `destination`, source `flags`). Injury operations use the same live
health, consciousness, death and recovery code called by damage. Transport flags
are ALL1, SLAVE2, LOUD4 and XP8.

`PCEQUIP` uses the exact source order: four armor digits, right-hand weapon,
left-hand weapon, right ammunition count, left ammunition count. For example,
`1234 PC.SMG PC.LaserRifle 10 10`. Initialization processes the left weapon first,
then the right, and validates armor last. A source-compatible partial error keeps
prior writes and the initialized flag. Armor digits map to head, torso, arms and
legs; they encode armor types, not remaining armor points.

`op: personal` exposes `to_normal`, `to_personal`, `location`, and `armor`, with
`unit`, `amount`, and optional `weapon`, `location`, `id`. Ordinary firing uses
these same conversions and armor effects. The source armor diagnostic `id:-2`
skips only the variation draw; subsequent applicable luck/block draws remain.

XP configuration lives under `pilots.xp`: `oldxpsystem`, `bthmod`, `missilemod`,
`ammomod`, `defaultweapdam`, `xp_modifier`, `defaultweapbv`, `use_pilot_bv`,
`vrtmod`, `perunit`, and `xpgain_cap`. Defaults match the source. `op: experience`
exposes the actual producer functions: `tech`, `techweapons`, `computer`, `comm`,
`piloting`, `perception`, `spot`, `artillery`, and `gun`; it also supports
`configure` with a `config` object. Unit, player, reason, target, weapon, damage,
multiplier, BTH, modifier and addanyway inputs select source arguments. These
producer diagnostics complement ordinary firing, PSR, movement, orbital landing,
spotting and sensor-detection consumers. Applied durable XP requests are visible
per unit; external MUX XP-channel delivery is reported separately. Null-unit
technician requests and threshold wizard-log requests appear in
`state.character_external_effects` as unapplied. Computer reports retain the
original reason even when the actual XP award is clamped to one.

`pilots` also accepts `afterlife`, `used_store`, `xploss` (default666),
`in_character`, `pickup_action` (default1), `xploss_for_mw` and
`transported_unit_death`. Emergency radio draws use a separate host PRNG, matching
the source's separation from combat MT. Supplying finite `radio_draws` provides
raw nonnegative host values, reduced modulo1000000; exhaustion is an explicit
failure. Host library sequences are not claimed to match every C platform.

Normal acceptance is `python -m tools.run_acceptance --suite pilots`; see
[QA prerequisites](../qa/README.md). Its workflow bindings launch this public
CLI in isolated subprocesses. The independent driver is `python -m qa.pilots`.

## QA source diagnostics

`pilot_diagnose` exposes source helpers through the same public JSON CLI. These
are diagnostic operations, separate from ordinary commands and clock-driven
workflows. They run the production helper and return its actual result; they do
not accept expected outcomes or replace dependencies with callbacks.

| `kind` | Inputs/result |
|---|---|
| `definitions` | All 119 value records: code, name, numeric type/flags, threshold, short alias |
| `pilot-bv` | Integer `gunnery`, `piloting`; source factor or unsupported-domain error |
| `movement-value` | Numeric `speed`; source XP movement bin |
| `old-probability` | `difficulty`; consumes finite `xp_old_gate` draw |
| `visibility` | `unit`, `target`; actual cached LOS, fresh geometric flags, range and sensor indices |
| `swarm-query` | `unit`, optional `target`; eight-member count and ordered mapped swarm queries |
| `modifier` | `unit`, `target`, optional Boolean `leg`; actual source action modifier |
| `common-checks` | `unit`; shared section/weapon guard result |
| `recycle` | `unit`, nonnegative integer `amount`; real member recycling |
| `detach` | `unit`, optional Boolean `intentional`; real detach/PSR/damage path |
| `mirror` | `unit`, `target`; actual rider coordinate mirroring |
| `head`, `lethal` | `unit`, integer `amount`; shared pilot injury consumer |
| `damage-entry` | `unit` attacker, `target`, `weapon`, nonnegative `amount`, section 0..7, physical flag 0..2, optional `bth`; actual shared damage and XP routing |

Swarm/helper diagnostics accept `source_id` and `no_map` for invalid source-object
domains. The registered identity/map is restored before returning; these inputs
are not ordinary object creation or travel controls. `experience` / `gun` also
accepts diagnostic `weapon_fields` (`bv`, `vrt`, numeric `weapon_type`) to exercise
source structure/configuration arithmetic with the real XP producer and durable
character. It does not alter the registered weapon or a later shot.

An administrative template load cancels the object's pending events. A loaded
MechWarrior is already started by the source template loader: use public
`{"op":"register","unit":"u"}` before advancing a newly loaded simulation
fixture, then allow LOS updates before firing. Ordinary ejection/disembark
creation performs this registration itself. Registration is explicit setup;
`personnel` / `initialize` remains a diagnostic initializer, whereas created
pilot objects use the ordinary shared initializer automatically.
