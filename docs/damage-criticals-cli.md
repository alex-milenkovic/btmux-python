# Damage simulation CLI

Run from the project root:

```sh
python3 -m tools.damage_criticals --help
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.damage_criticals --input ./tmp/damage-example.json
```

Omit `--input` to read one JSON document from stdin. A valid workflow returns one JSON object with `results` (one per action), `state` (final inspection) and `draws` (ordered `{name,value,low,high}` records). Invalid schema, unknown identifiers, unsupported operations and exhausted/out-of-range finite dice return nonzero, useful stderr and no success document. A valid but rejected game command returns its rejection in JSON with exit zero.

## Complete example

Save this as `./tmp/damage-example.json`. The ordinary command removes three center-torso armor points; neither inspection advances time.

```json
{
  "config": {"periodic_updates": false},
  "units": [{"name": "u", "sections": [
    {"index": "CT", "armor": 20, "armor_orig": 20,
     "internal": 16, "internal_orig": 16}
  ]}],
  "random": {"seed": 0, "streams": {"damage_entry": [7]}},
  "actions": [
    {"op": "command", "name": "damage-section", "args": "CT 3 0 0"},
    {"op": "inspect"},
    {"op": "inspect"}
  ]
}
```

`state.units.u.sections[4].armor` is 17. The two inspection results are equal; `draws` contains just `damage_entry=7` with bounds 2..12.

## Initial state

Top-level fields are `actions` (required array), `map`, `units`, `config`, `random`; the existing sensor session also accepts `diagnostic_cache`. Unknown fields fail.

Defaults: clear 8×8 map; time zero; ready, conscious, 50-ton biped `u` at `[2,2,0]`; max speed 64.5; ten sinks; no weapons/critical equipment. Default undamaged section front/internal values are arms 10/8, side torsos 12/12 (rear 4), center torso 16/16 (rear 5), legs 12/12, head 9/3. Original values equal current values. Supply explicit populated section fixtures for other classes; changing class does not invent a different vehicle template.

Each `units` record requires a unique `name`. Common fields:

- `class`: `MECH`, `MW`, `BSUIT` (alias `BA`), `VEH_GROUND` (`GROUND`), `VEH_NAVAL` (`NAVAL`), `VTOL`, `AERO`, `DS`, `SPHEROID_DS`.
- `movement`: a `MoveType` name such as `BIPED`, `QUAD`, `TRACK`, `WHEEL`, `HOVER`, `HULL`, `FOIL`, `VTOL`, `FLY`, `NONE`. Class-appropriate defaults apply.
- `at`: `[x,y,z]`; `team`, unique two-character `contact_id`, `tonnage`, `facing`, `turret_facing`, `speed`, `desired_speed`, `vertical_speed`, `max_speed`, `template_max_speed`, `jump_mp`, `jump_speed`.
- Boolean `pilot` (default true), `started`, `conscious`, `fallen`, `hidden`, `hulldown`, `destroyed`, `in_character`, `armor_warnings`. `piloting` requires a pilot and is 0..20.
- Integer bitfields `status`, `status2`, `crit_status`, `crit_status2`, `tank_crit_status`, `specials`, `specials2`. Values are the source-compatible enums in `entities/mech.py`; use these for partial cover, dug-in, jumping, combat safety and equipment configuration. Ground dug-in uses bit `0x04` in `tank_crit_status`.
- Numeric `heat`, `plus_heat`, `minus_heat`, `engine_heat`, `num_sinks`, `disabled_sinks`, `base_to_hit`, `pilot_skill_base`, `pilot_hits`, `lrs_range`, `tac_range`, `scan_range`, `radio_range`, `computer`, `radio`, `working_c3_masters`, `total_c3_masters`, `fuel`, `si`, `cocoon`, `boom_start`, `aim`, `aim_type`. `aim` is an integer source section index 0..8 (8 disables aiming); `aim_type` must be a valid numeric UnitType. `measured_mass` supplies nonnegative integer measured cargo mass in 1/1024-ton units for existing cargo/tow calculations.
- `computer_brand` and `radio_brand` are aliases for `computer` and `radio`. Brand zero selects reliable level five; use brand one for failure fixtures.
- `swarm_target`, `towed_unit`: another unit's name. `c3i_network`: array of local peer names. `carrying`: numeric entity reference where already known; `towed_unit` is preferable for named fixtures. The local swarm registry also recognizes a supplied swarm relationship. Persistent MUX occupants are unavailable, not simulated by an invented occupant fixture.

`map` accepts `size:[width,height]`, `default:[terrain,elevation]`, `hexes:[{at:[x,y],terrain,elevation}]`, `combat_safe` and existing sensor-map fields (`mapvis`, `maxvis`, `light`, `cloudbase`, `sensorflags`, `weather`, `dark`). Terrain can use named constants such as `CLEAR`, `ROUGH`, `WATER`, `ICE`, `ROAD`, `BUILDING`. Air units at z=0 default to landed; provide explicit `status`/position for airborne cases.

### Sections, slots and weapons

`sections` is an array of overrides. Each requires `index`: numeric 0..7 or class section name; MECH aliases `LA`, `RA`, `LT`, `RT`, `CT`, `LL`, `RL`, `HD` are supported. Vehicle names are `LSIDE`, `RSIDE`, `FSIDE`, `BSIDE`, `TURRET`, `ROTOR`. AERO names are `NOSE` (0), `LWING` (1), `RWING` (2), `FUSELAGE` (3), `COCKPIT` (4), `ENGINE` (5); canonical names such as `Left_Wing` also work. DropShips retain their separate six-section names and indices; BA supports numeric source locations.

Section fields: `armor`, `armor_orig`, `rear`, `rear_orig`, `internal`, `internal_orig`, `config`, `specials`, `basetohit`, `recycle`, and `slots`. Values are nonnegative integers. Changing a fixture value is distinct from executing damage; a zero internal override does not automatically dispatch destruction.

Each slot requires `index` 0..11. Choose at most one type representation: `special` (a `Special` enum name), `weapon` (catalog name), `ammo` (catalog weapon name), or numeric `type`. Additional inputs are `data`, `brand`, `firemode`, `ammomode`, `weap_damage_flags`, `desired_ammo_loc` (-1..7) and `temp_failure` (0..15). `temp_failure` writes the high brand nibble through the production accessor. Unknown special/catalog types and unsafe indices are rejected. Numeric bomb/cargo values use the source namespace; cargo has no implemented content effect in the C critical callback itself.

Use `weapons` to create actual mounted weapon runs and their `WeaponState` records. A string means a catalog name; the record form is:

```json
{"name":"IS.AC/5", "section":"RT", "critical":0,
 "brand":1, "fire_mode":0, "ammo_mode":0,
 "metadata":{"damage":5,"heat":1,"vrt":20}}
```

Each run occupies the catalog's critical size for MECH and one slot for other classes. Overlaps and runs extending past slot 11 fail. Apply `sections[].slots` afterward to describe damaged slots and split markers (`SPLIT_CRIT_LEFT` / `SPLIT_CRIT_RIGHT`, with source `data` linkage).

Optional weapon `metadata` overrides the shared C-style weapon type within this session only: `damage`, `heat`, `vrt`, `crits`, `tonnage`, `range_min`, `range_short`, `range_medium`, `range_long`, `missiles`, `damage_per_missile`, `special`, `ammo_per_ton`, `explosive_damage`, `weapon_type` (0 beam, 1 missile, 2 artillery, 3 ballistic, 4 hand), `range_short_water`, `range_medium_water`, `range_long_water`. Overrides of one type must agree; these are initial metadata, never expected computed outputs. The shared catalog is restored after each invocation. Supply ammunition through slot records or existing `ammo` records `{weapon,rounds,section,critical,ammo_mode}`.

## Configuration and randomness

Source defaults:

```json
{"parts":1,"vcrit":2,"fasacrit":0,"fasaadvvhlcrit":0,
 "fasaadvvtolcrit":0,"tankfriendly":0,"tankshield":0,
 "divrotordamage":0,"critlevel":100,"exile_stun_code":0,
 "hit_arcs":0,"stackpole":1,"inferno_penalty":0,"transported_unit_death":0,"erange":1}
```

The ordinary engine dispatch is enabled by default (`periodic_updates:true`); `advance` then runs heat, recycle, stability and other existing registered consumers. Use `false` for a narrow diagnostic fixture while retaining scheduled event delivery. Existing sensor options and `movement_modes` remain available. This port uses its existing movement-modes-enabled compile profile. One MP is 10.75 kph and a turn is 30 ticks.

`random` takes integer `seed` (default zero) and `streams`, an object of finite integer arrays. Omitted streams use seeded production dice; a supplied empty or exhausted stream fails. Values must fit the bounds requested by the consumer. The trace records consumption, including early-return behavior; it does not provide outcomes to the rules.

| Stream | Draw domain / consumer |
|---|---|
| `hit_location_rolls` | 2..12; normal and delegated profile entry rolls |
| `physical_attack` | 2..12; ordinary punch/kick attack decision |
| `tc_location` | 1..6; targeting-computer success, only for matching aim type |
| `missile_pre_roll`, `missile_cluster` | three preliminary 1..6 draws, then fresh 2..12 when not hotloading |
| `physical_location` | 1..6; punch/kick/head reroll |
| `swarm_location` | 2..12; swarm table |
| `crittable_chance` | fighters: 1..11 or 1..71; other classes retain their 1..12 or 1..71 rules |
| `fighter_weapon_choice` | 0..N-1; fighter direct weapon-loss candidates, excluding global mount 0 |
| `dug_in`, `suit_choice`, `dropship_wing` | 1..100; live member index; 1..2 |
| `damage_entry`, `critical_rolls`, `tow_rolls`, `interception_rolls`, `breach_rolls`, `stackpole_rolls` | 2..12; corresponding damage decision |
| `critical_slot` | 0..N-1 in the current candidate list |
| `critical_mw_gate` | 1..2 |
| `pilot_rolls`, `attack_rolls`, `enhanced_rolls` | 2..12 |
| `vehicle_critical_roll`, `motive_rolls` | 2..12 |
| `vehicle_weapon_slot`, `vehicle_lose_weapon` | candidate index 0..N-1; ordinal 1..N |
| `vehicle_weapon_weight` | 0..2147483647; one per candidate |
| `vehicle_jam_recycle` | 60..120 |
| `vehicle_legacy_critical`, `vehicle_motive_gate`, `vehicle_turret_gate` | 0..5; 1..10; 1..3 |
| `failure_weapon_chance`, `failure_generic_chance` | 1..10; 1..5000 |
| `failure_reliability`, `failure_outcome` | 1..100; 1..6 (six rerolled once) |
| `failure_weapon_recycle`, `failure_dud_recycle` | 20..40; 1..60 |
| `failure_recovery_upper`, `failure_recovery_delay` | 40..200 first, then 30..that upper value |

Other existing consumers (personal damage, heat, ejection, cluster and piloting) expose their names and exact requested bounds in `draws`. Reuse those names to pin a subsequent fresh workflow. Never reuse a mutated session to compare alternative table rolls.

## Actions and diagnostics

`unit` defaults to `u` for actor-specific actions. `command` accepts `name` and `args` (text or an array). Supported task commands are `damage`, `damage-section`, `setarmorstatus`, `dodamage`, `weaponstatus`, `fire`, `sight`, `target`, `ammo`, `speed`, `heading`, `turret`, `startup`, `shutdown`, `aim`, `punch`, `kick`, `stand`, `prone`; existing sensor commands remain available. Weapon numbers are zero-based. `ammo` takes `[weapon_number,mode_command]`, using a name from the production mode registry; unsupported mode names fail. Use actual mode command names from `systems/weapon_modes.py:_COMMANDS`.

- `damage`: `total cluster rear critical`; total 1..1000, positive cluster no larger than total. Drops the remainder and rejects MW.
- `damage-section`: `section total rear critical`; flags are integers, not restricted to 0/1.
- `setarmorstatus`: `section kind value`; kind 0=front, 1=internal, 2=rear, value 0..255. Returns the C-style validation string.
- `dodamage`: `total cluster direction`; directions 0..7 front, 8..15 rear, 16..21 table selection. Retains the final smaller cluster.
- `aim`: one target section index, or `-` to disable; invokes the normal aim command against the current lock.
- `punch` / `kick`: limb selector and contact ID (for example `["L","01"]`); ordinary physical attack guards apply.
- `stand` / `prone`: normal movement commands, including pending events and limb guards.
- `advance`: `{op:"advance",seconds:N}` executes N ticks; `inspect` returns a snapshot without advancing, repairing, rolling or dispatching.
- `section`: `{op:"section",unit:"u",value:{index:4,armor:10}}` is a fixture edit.
- `configure`: existing sensor-session state overrides (status words, speed/heat, target references). For damage-only initial fields use the unit fixture, not arbitrary runtime attribute writes.

Diagnostics use `{op:"diagnose",unit:"u",kind:NAME,options:{...}}`. They call production functions, including side effects. Section defaults to index 4 (CT for Mechs, Cockpit for fighters), slot to zero, attacker to none. `rear`, `critical`, `internal`, `transfer`, `ignore_swarmers`, `breach`, `disable` are booleans. `side` is `FRONT`, `BACK`, `LEFTSIDE`, `RIGHTSIDE`.

| Kind | Options |
|---|---|
| `dodamage` | `total,cluster,direction,critical,message,broadcast`; preserves supplied text and final remainder |
| `damage` | `section,amount,rear,critical,internal,transfer,attacker,weapon,ammo_mode,ignore_swarmers` |
| `destroy-section`, `explode-unit`, `reactor-explosion` | `section,attacker` for section destruction; only `attacker` for explosions |
| `destroy-parts` | `section,attacker,breach,disable` |
| `critical` / `slot` | `section,count,attacker` / `section,slot,attacker` |
| `location` | `side,roll,profile,critical`; `critical` seeds the source in/out flag, omit profile for normal dispatch; direct `legacy`, `FASA`, `advanced`, `critproof` select a source table |
| `physical-location` | `side,roll,attack` (`punch` or `kick`, roll 1..6) |
| `hit-arc`, `aim-location`, `tc-location` | `target`; actual positions, configuration and stored aim determine the result |
| `target-location` / `narc-location` | `target,side,roll` / `target,section,rear,roll` |
| `swarm-location`, `transfer`, `live-suit` | `roll` / `section` / none |
| `crittable` | `section,threshold` |
| `normalize` | optional `section`; omission runs complete normalization |
| `effect` | `name,section,attacker`; names listed below |
| `failure` | `category,outcome,section,slot`; category 0 energy, 6 ballistic, 12 missiles, 18 flamer, 24 computer, 30 radio; outcome 1..6 |
| `weapon-failure`, `generic-failure` | `section,slot` / `part_type` (-1 computer, -2 radio) |
| `percentage-failure` | `weapon,type,percentage,section`; type `DAMAGE`, `HEAT`, `RANGE` |
| `brand` | `part_type,level`; raw part code and display level 0..5 |
| `enhanced`, `weapon-detail` | `section,slot,roll` / `section,slot` |
| `weapon-count`, `weapon-type` | `section` / `section,ordinal` (C location ordinal starts at one and skips global mount zero) |
| `correct-speed`, `bridge-hit`, `main-weapon-jam`, `main-weapon-destroy` | none |
| `destroy-heat-sink` | `section` |
| `motive` | optional `modifier` |
| `brand-index` | `part_type` |
| `weapon-threshold` | `section,slot,increment`; optional boolean increment |
| `weapon-modifiers` | `section,slot,range_bracket`; bracket 0 short, 1 medium, 2 long |
| `radio-recovery`, `scanner-recovery` | raw encoded callback `value` |
| `serious` | nonnegative `value`; returns source modulo-four color/text |

Vehicle effects: `driver_hit`, `commander_hit`, `crew_stunned`, `crew_killed`, `sensor_hit`, `stabilizer_destroyed`, `turret_jam`, `turret_lock`, `turret_blown_off`, `engine_hit`, `fuel_tank_hit`, `ammo_explosion`, `cargo_hit`, `rotor_damaged`, `rotor_destroyed`, `tail_rotor_damaged`, `weapon_jam`, `weapon_destroyed`.

Normal location dispatch may consume a fresh delegated roll after its entry roll. An explicit `roll` supplies that diagnostic entry roll; remaining draws still come from the real consumer. A raw `failure` selects a source row but still evaluates its prerequisites; use `weapon-failure`/`generic-failure` to test selection probabilities and early exits.

## Observations and limits

Fighter `damage` defaults to `transfer:false`: positive armor absorbs a hit and discards excess; a later hit on an empty section routes to Fuselage. `transfer:true` exposes the historical explicit transfer entry and forwards excess. `internal:true` still damages fighter armor, with CASE/Clan containment when transfer is enabled. Ordinary ammo explosions use the explicit internal transfer entry. Fighter SI is observable bookkeeping and supplies no durability. See [the fighter CLI guide](six-location-aerofighters-cli.md).

Snapshots include all eight sections/twelve slots, original/current armor/internal, source status words, weapon condition/recycle/usability and detailed text, heat/sinks, SI, pilot state, speeds, jump capability, damage counters, local relationships, recipient messages, armor notices, and pending event names/deadlines. `usable` describes local equipment/recycle readiness; ordinary fire can still reject on target, arc, ammunition or command guards.

`missing_services` reports unavailable periodic consumers; `external_effects` contains `{service,operation,applied:false}` for requested unavailable MUX operations. These records are **not successful external execution**. Radio recipient text, persistent character/XP, object creation/ejection/discard, transport contents and kill-channel delivery are reported explicitly when unavailable. Local peer C3i links can be supplied and invalidated; no remote MUX network is fabricated.

The source readout has no named branch for temporary failure 7 (`FAIL_AMMOCRITJAMMED`): status text remains empty while raw slot temp-failure 7 is visible and firing is blocked. Failure 6 is the distinct `AMMOJAM` readout.

## Independent QA

Run `PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/tmp" python3 qa/damage_criticals.py --workers 4`. `--only <feature-stem-or-case-prefix>` selects a focused rerun. Each case writes its input, stdout, stderr, exit code and assertions under `tmp/qa-damage-criticals/`. The runner parses all 13 APS files, expands every vector and executes additional source-boundary workflows through subprocesses. Specification hashes prevent changed feature or procedure text from silently reusing stale cases. Blocked external effects are counted separately.
