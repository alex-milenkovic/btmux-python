# Combat resolution JSON interface

Run `python3 -m tools.combat_resolution --input ./tmp/combat.json`, or send the
same JSON on stdin. The required top-level field is `actions`. The command emits
one JSON object containing `results`, final `state`, and `draws`. A valid command
refusal returns exit 0 with `accepted:false` and its reason. Invalid schema,
unknown commands/units/weapons, unsafe indices, nonfinite numbers, duplicate JSON
keys, and exhausted or out-of-bounds finite draws return nonzero on stderr.

The interface extends the [Damage interface](damage-criticals-cli.md) and
[Sensor interface](sensors-los-cli.md). Their section/critical/ammunition fixtures,
class-tagged shared Mech state, map cells, contact cache diagnostics, sensor
controls, damage diagnostics, and registered event engine remain available.
The separate legacy Vehicle class is not the simulation model.

## Defaults and fixtures

Defaults are a clear 12×12 map, ready piloted 50-ton `u` at [3,3,0] and enemy `v`
at [3,2,0], intact arm/leg actuators, no mounted weapons, and a stable acquired
lock from `u` to `v`. Units have unique two-character contact IDs (`00`, `01`, …).
An explicitly supplied `u.target` preserves the requested target instead. Map
positions and source skill inputs determine BTH; expected BTH/damage values are
never accepted as normal-fire fixtures. Finite draws may be supplied through
`random.streams`; omitted streams use the reproducible seed (default 0).

Optional top-level fields are `map`, `units`, `config`, `random`,
`diagnostic_cache`, and `pending_events`. Each pending event has `unit`, `callback`,
`delay` (positive seconds), and optional `data`, using the callback table below.
These are explicitly diagnostic initial states, not claims that commands created
them. Unit references resolve after all units are registered.

Map additions: `windspeed`, `winddir`, `flags`, `gravity` (percent), `temperature`,
and `mines`. Each mine has `x`, `y`, `type` (Standard, Inferno, Command, Vibra,
Trigger), `strength`, optional `extra`, and `creator`. Normal creation is also
available as `addmine`. `combat_safe` is the source build-safe map flag.

Additional unit fields:

| Fields | Meaning |
|---|---|
| `prefs`, `gunnery`, `artillery`, `spotting`, `piloting` | Source preference word and local skill inputs |
| `tonnage`, `real_mass` | Independent design and actual mass in tons; actual mass populates `rtons` at 1024 units/ton |
| `masc_counter`, `scharge_counter` | Source counters, including the supercharger callback's MASC-counter quirk |
| `digging`, `dug_in`, `melee_specialist`, `pilot_wizard` | Boolean rule inputs; the last two apply to the pilot and require a pilot |
| `caller_is_pilot`, `caller_wizard` | Command actor metadata |
| `charge_target`, `dfa_target` | Unit name, or numeric persistent ID / -1 |
| `charge_timer`, `charge_distance`, `desired_facing`, `weap_heat`, `infantry_specials` | Source numeric fields |
| `c3_network`, inherited `c3i_network` | Arrays of registered unit names for an already formed network |
| `tics` | Arrays of weapon-number arrays, in TIC-number order |
| `heat_state` | Explicit heat, plus_heat, minus_heat, weap_heat, engine_heat, num_sinks, disabled_sinks, heatboom_last, thermal_sinks inputs |

Weapons use the inherited `name`, `section`, `critical`, `fire_mode`, `ammo_mode`,
`brand`, and `metadata` record. Metadata overrides apply to all mounts of that
catalog identity in this session and must agree. Available metadata fields are
`damage`, `heat`, `vrt`, `crits`, `tonnage`, `range_min`, `range_short`,
`range_medium`, `range_long`, all four corresponding `*_water` ranges,
`missiles`, `damage_per_missile`, `special`, `ammo_per_ton`, `explosive_damage`,
numeric `weapon_type`, and the diagnostic `source_name` described below. Critical runs cannot overlap. Sections/slots expose
source type, data, brand, firemode, ammomode, weap_damage_flags, desired_ammo_loc,
and temporary-failure inputs. A weapon's first critical data byte is authoritative
recycle state; ammunition rounds live in ammo critical data bytes.

Configuration adds the source defaults `phys_use_pskill:1`, `glancing_blows:1`,
`fasaturn:1`, `extendedmovemod:1`, `newcharge:0`, `tl3_charge:0`, `dig_only_fs:0`,
`digbonus:3`, `moddamagewithrange:0`, `moddamagewithwoods:0`,
`hotloadaddshalfbthmod:0`, `explode_reactor:1`, `explode_ammo:1`,
`explode_time:120`, `explode_stop:0`, `new_stagger:1`, `stagger_interval:5`,
`stagger_tonnage:1`, `advanced_vehicle_fire:0`, `heatcutoff_enabled:1`.
Damage configuration includes `erange:1`, `fasacrit:0`, `fasaadvvhlcrit:0`,
`fasaadvvtolcrit:0`, `vcrit:2`, `critlevel:100`, `exile_stun_code:0`, and the
other documented Damage settings. Ordinary periodic updates are enabled.
`periodic_updates:false` isolates diagnostics; it does not cancel explicitly
scheduled events. One event tick is one second. Weapon recycle normally uses
2×vrt; AMS uses bare vrt; physical recycle is 30 seconds.

## Actions and commands

`{"op":"command","unit":"u","name":"fire","args":["0"]}` invokes the
normal command path. `args` may be an array or command-argument string.
`{"op":"advance","seconds":30}` runs the event clock and normal consumers.
`{"op":"inspect"}` copies state without advancing time, drawing randomness,
running callbacks, or repairing state. Inherited `place`, `hex`, `section`,
`configure`, `cache`, `conditions`, and sensor observation actions remain.
`configure.values` additionally accepts charge/DFA references, charge distance and
timer, booster counters, desired facing, gunnery/artillery/piloting, weapon heat,
aim, aim type, and prefs. Fixture edits are diagnostics.

Combat commands include:

- `lock <contact>`, `lock -`, `lock X Y [B|I|C|H]`; `target`/`aim <section|->`.
- `fire`/`sight <weapon> [contact|X Y]`; `addtic`, `deltic`, `cleartic`, `listtic`,
  `firetic`, with source selector syntax, duplicate handling, and interruption.
- Weapon fire/ammo commands: flamerheat, ultra, explosive, lbx, armorpiercing,
  caseless, flechette, incendiary, precision, rapidfire, stinger, rac, gattling,
  artemis, narc, swarm, sguided, atmrange, atmexplosive, swarm1, inferno, hotload,
  cluster, smoke, mine, inarc, ams. Existing aliases remain as listed by
  `systems.weapon_modes._COMMANDS`.
- `unjamammo <weapon>`, `usebin <weapon> <section>`, `masc`, `scharge`,
  `stealtharmor`, `nullsig`, `dig`, `fixturret`, `fliparms`, `explode <reactor|ammo|stop>`.
- `shownarcpods`; MECH `removepods <section> <H|Y|E>`; vehicle `removepods`.
- `mechprefs [name [ON|OFF]]`, `safety`, `autoturret`, `disableweap <selector>`,
  `heatcutoff` (the existing four-tick heat-dissipation switch).
- `punch`, `axe`, `sword`, `mace`, `claw`, `saw`, `kick`, `trip` take optional
  single-letter limb and contact; `club [contact]`; omitted contact uses the
  live default lock. `charge [contact|-]`, `grabclub [L|R|-]`, and `jump`
  (default or explicit-contact DFA target, or bearing/range) reach movement/landing consumers.
- Existing `speed`, `heading`, `stand`, `prone`, `startup`, `shutdown`, `spot`,
  TAG/ECM/sensor/scan/report commands remain available.
- `addmine X Y TYPE STRENGTH [EXTRA]`, `detonatemines CHANNEL`.
  `c3connect` reports the unavailable persistent network-formation service;
  it does not fabricate a working network.

Weapon numbering follows mounted critical order/state. Selection rejection is
observable separately from a fired shot's success. TIC `accepted` describes
command validation; per-shot messages and shot counters expose weapon outcomes.
Inherited sensor results retain `ok`/`message` alongside `accepted`/`text`.
`listtic.result` contains `[rows, messages]`. Valid rows contain weapon number,
class-specific section label, weapon name, and nonfunctional marker. A stale
display entry is the string `Unknown - error of some sort occured`, also
included in messages. Listing retains the C menu's initial format-probe call
and subsequent two-column callback order; both can remove stale membership.

## Diagnostics

Use `{"op":"diagnose","unit":"u","kind":"combat-bth","options":{"weapon":0,"target":"v"}}`.
Unknown option keys are errors. `weapon` below is a mounted ordinal, and `target`
is a fixture unit name. Omitted range uses actual three-dimensional separation.
Diagnostics invoke the named production rules, recording their real side effects.
They are not normal command coverage.

| Kind | Options |
|---|---|
| `combat-range` | weapon, target, distance, network_range (explicit arithmetic only), ordinary (C3 versus C3i) |
| `combat-bth` | weapon, target, distance, indirect_fire, spotter; normal BTH rules (use ordinary `sight` for artillery BTH) |
| `artillery-bth` | weapon, distance, indirect (boolean); source artillery arithmetic |
| `artillery-launch` | weapon, x, y, hit (boolean, default true); capture and schedule a real projectile without the fire-command gates or resource tail |
| `ammunition-check` | weapon, offset; source warning threshold and weight-check invalidation |
| `combat-attack` | weapon, target, distance, roll, cluster_roll, location_roll, aim_roll, tc_roll (1..6), x, y; resolution layer, without the fire command's resource tail |
| `missile-hit` | weapon, target, bth, roll, incoming, player_roll, cluster_roll, ams_roll; direct callback can spend AMS resources on a miss |
| `missile-index` | weapon, target, glancing; actual pre-draw and guidance rules |
| `swarm-next` | target, visited (array of fixture unit names), enemy_only; select the next live roster candidate |
| `physical-damage` | target, attack, section, weight, glancing |
| `physical-attack` | target, attack, section, weight, bth, roll |
| `dfa` | target, roll; direct resolution, distinct from ordinary `jump` landing |
| `charge` | target, roll, target_roll |
| `blast` | signed damage, cluster, heat, x, y, source_real (optional two-number world-coordinate origin), table (normal/punch/kick), safeup, safedown, underwater, neighbors; optional target_message, observer_message, neighbor_target_message, neighbor_observer_message are strings or null |
| `combat-callback` | name, data; executes exactly one callback |
| `terrain-hit` | weapon, x, y, damage, hit (0/1), operation (hex/ignite-clear/ice/bridge/building) |
| `mine-contact` | reason (step/land/fall/drop) |
| `mine-discovery` | range, x, y |
| `artillery-flight` | range |
| `artillery-direction` | bearing |

Callbacks: `explode` (encoded integer countdown), `unjam-ammo` (weapon ordinal),
`dig`, `unjam-turret`, `remove-pods` (unused integer data), `signature`
(`["stealtharmor"|"nullsig", boolean]`), `booster` and `booster-regen`
(`"masc"|"scharge"`). Pending callbacks use the same names/data and real event
kinds, including distinct supercharger and null-signature kinds.
`jump-stabil` runs the existing jump stabilization callback. `sixth-sense`
accepts integer severity, including negative values, so its source bounds and
pilot/consciousness checks can be observed. These callbacks also work in
`pending_events`. Blast coordinates may lie outside the map (bounded to
-200..400 for the diagnostic); the production bounds guard remains observable.
Blast damage is bounded to -100000..100000, cluster size to 1..100000, and
neighbor radius to 0..20. The optional real origin changes arc and attenuation;
omitting it uses the center of the specified hex.
Inherited hit-location/profile, critical, weapon-failure, motive, destruction,
transfer, and damage diagnostics are documented in the Damage interface.

## Observations and randomness

Unit state includes armor/internal/rear values, every critical, authoritative
weapon readouts, heat, movement, target/aim/spotter/swarm relationships, prefs,
TICs, charge/DFA state, actual mass, booster counters, shots fired/hit/missed,
messages, and pending unit event deadlines. Executed DFA/charge results are
included when present. Map state includes mines and covered hexes, captured
projectiles, artillery impacts, decorations/expiry, and current/underlying
terrain for every cell. Global pending event deadlines include projectiles.
External effects include exact `service`, `operation`, and `applied:false`.
Unit inspection includes `turret_facing`. Global `countdowns` entries expose
unit name, deadline, and exact encoded EXPLODE event data; displayed countdown
text may use a different value according to the source encoding. Aim indices
accept 0..8 (8 means no aim), and aim type must be a defined unit class.

Each draw records `name`, `low`, `high`, and consumed `value`, in order.
Combat streams include `attack_rolls` (2..12), `attack_dice` (1..6),
`aim_rolls` (2..12), `missile_pre_roll` (1..6), `missile_cluster` (2..12),
`ams_rolls` (1..6 or 2..12), `swarm_rolls` (2..12), `physical_attack` (2..12),
`physical_location` (1..6), `hit_location_rolls` (2..12), `swarm_location`
(2..12), `dfa_rolls`/`charge_rolls`/`pilot_rolls`/`damage_entry` (2..12),
`booster_rolls`/`unjam_rolls`/`pod_rolls` (2..12), and the named artillery,
terrain, mine, gattling, plasma, failure, and critical streams at their actual
source bounds. Supply enough follow-up damage/piloting draws for secondary
consequences. Missing streams use seed fallback; a supplied empty/exhausted
stream always fails. Inspection consumes none.

## Runnable artillery example

```json
{
  "units": [{
    "name": "u", "at": [3, 3, 0], "artillery": 0,
    "weapons": [{"name": "IS.Sniper", "section": "CT", "metadata": {"crits": 1}}],
    "ammo": [{"weapon": "IS.Sniper", "rounds": 10}]
  }],
  "random": {"streams": {"attack_rolls": [12]}},
  "actions": [
    {"op": "command", "name": "lock", "args": ["3", "1", "H"]},
    {"op": "command", "name": "fire", "args": ["0"]},
    {"op": "inspect"},
    {"op": "advance", "seconds": 10},
    {"op": "inspect"}
  ]
}
```

The first inspection contains a captured projectile and no impact; the second
contains the actual impact and no projectile. Ammo/heat/recycle start at firing.
For the complete workflows, the executable fixture construction is in
`acceptance/combat_resolution/integration.py`: a self-designated spotter supplies
artillery coordinates, speed creates movement mine contact, jump creates DFA,
a RAC jam is cleared after 60 seconds, stealth settles before stable-lock fire,
a two-weapon TIC creates two shells, and vehicle pod removal changes ECM through
normal updates. These are acceptance fixtures, not production case-name switches.

Persistent occupant transfer, persistent XP, mine object scripts, building-object
damage and C3 network formation remain explicit unavailable effects. Successful
assertions about those records do not mean the missing effect happened.

`map-unregister` is a diagnostic with no options. It unregisters the current map
from the engine so pending projectile callbacks can exercise deleted-map handling.

Unit inspection includes `cocoon`, the source orbital-drop shell state.

Firing fixture controls include `config.idf_requires_spotter` (default 1),
`config.arc_override` (default 0), and `units[].unusable_arcs` (default 0).
Arc words are source firing-arc bit masks; these model already assigned control.

Weapon metadata also accepts `source_name`: nonempty text up to 100 characters.
This diagnostic overrides the name-based C predicates and artillery noun mapping
for a known mounted catalog identity, while keeping its explicit numeric metadata.
It permits testing names missing from the Python catalog; it does not install a
new gameplay weapon. Metadata overrides and name aliases are scoped to each action.
Unit inspection includes `minus_heat` for the live heat-dissipation consumer.

`swarm-hit` is a diagnostic entry into the production SWARM chain. It accepts
`weapon`, `target`, `bth`, `roll`, `incoming`, optional `enemy_only` (false), and
optional `player_roll` (defaults to `roll`). It reports ordered target IDs,
remaining missiles and applied damage; subsequent rolls use `swarm_rolls`.
The source ignores `incoming` and initializes from the weapon's full salvo.

`impact-damage` exposes production damage shaping before armor dispatch. Inputs
are `weapon`, optional `target` and `distance`, optional `failure_type` (null or
`DAMAGE`), nonnegative integer `failure_modifier`, and `temporary` (false).
It returns `damage` and retains any production terrain side effects. It is a
calculation diagnostic, not a normal weapon discharge.
