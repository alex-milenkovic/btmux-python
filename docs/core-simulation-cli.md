# Core simulation JSON interface

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m tools.core_simulation --input ./tmp/core.json`,
or provide the same JSON on stdin. The required field is `actions`. Output is
one JSON object with ordered `results`, final `state`, and named-consumer `draws`.
A normal command refusal has `accepted:false` and exit status 0. Malformed input,
unknown operations, missing references, unsafe indices, nonfinite values, duplicate
JSON keys, and exhausted finite random streams produce a nonzero exit status.

This extends [Combat resolution](combat-resolution-cli.md), including its inherited
[Damage](damage-criticals-cli.md) and [Sensors](sensors-los-cli.md) input schemas and
ordinary movement, sensor, firing, damage, equipment, and TIC commands. The following
core defaults and additions override the corresponding combat defaults.

## Defaults and fixtures

The default is one started, piloted 50-ton `u`, on a clear 12×12 map, at [3,3,0],
with intact actuators and no weapons or target. Piloting/gunnery default to 5/4.
Clocks start at zero, MT starts at source seed 5489, lock acquisition takes eight
seconds, and ordinary periodic updates are enabled. Initial contact acquisition
runs after maps and local unit IDs are assigned; it can consume random inputs.
An unpiloted stopped unit still has a separate eligible command actor for startup.

Top-level fields are `actions`, `map` or `maps`, `units`, `objects`, `templates`,
`costs`, `config`, `random`, `pending_events`, and `diagnostic_cache`. The last two
are inherited combat diagnostic fixtures. For core callbacks use the `schedule`
action described below. Unknown fields are rejected.

Unit additions:

| Field | Input |
|---|---|
| `id` | Positive local object ID; defaults to unit order starting at 1 |
| `map` | Name from `maps`; defaults to the first map |
| `profile` | `normal` or `sparse`; sparse clears default actuators and armor/internal points, then reapplies explicit sections |
| `core` | Source state fields listed below |
| `actor`, `pilot_details`, `gunner` | Local actor records; pilot details require an assigned pilot |
| `pilot_owner` | `actor` or `pilot`, for ownership guards |

Map records inherit map dimensions/cells/environment and add `name`, nonnegative
`id` (default 1000 onward), boolean `linked`, nonnegative `cf` and `onmap`, numeric
`leave_target`, and `entrances:[{target,x,y,name?}]`. Target is the incoming map ID;
x/y must fit the destination. Names and object IDs must be unique. A hangar uses
flag 1, positive `cf`, a `leave_target`, and an entrance on its destination.
Local rosters and LOS rows change on transfer. Persistent teleports remain unavailable.

`objects` is a list of `{name,id,type,mymech?,weaplist?}`. Type is `AUTO` or `OTHER`;
`mymech` names a unit. These legacy AUTO fixtures record gameplay operations
that lack configured services, in source order. Registered Battlesheep controllers
use the built-in services exposed by the [autopilot interface](autopilot-cli.md).
`OTHER` is ignored by heartbeat dispatch.

`templates` contains `{name,unit}` records, where unit uses the same complete fixture
schema. `core.template_ref` selects one for repair replay. The template is retained
and replay operates on an isolated scratch copy. Missing templates produce a
reported dependency boundary; no replacement design is invented.

`costs:[{part,value}]` sets this session's source price table. Part is 1..1023;
value is an exact JSON integer in 0..18446744073709551615, including integers above
2^53. Weapon `metadata` adds integer `cost`, `ammo_cost`, `ammo_bv`, and `bv` to the
inherited catalog metadata. Overrides must agree for every mount/template of that
catalog identity and affect actual calculations in that session.

Critical slots are authoritative for weapon numbering. A mounted weapon needs its
source critical run; the C exception for weapon sizes at least nine is retained.
Malformed runs are skipped by enumeration. Mirrors are synchronized from slots.
Section armor/internal/rear/original/config fields and critical data/brand must fit
0..255; section specials fit 0..65535. This adapter accepts section basetohit/recycle
in 0..127. Encoded slot type must identify an available source catalog entry.

Actor records accept `name`, `skills` (named skill to integer -100..100), `health`
(`build`, `bruise`, `lethal`), and these fields:

- Integer: `id`, `location`, `gunnery`, `piloting`, `spotting`, `artillery`, `perception`, `technician`.
- Boolean: `valid`, `alive`, `robot`, `hardcode`, `is_player`, `connected`, `wizard`, `maneuvering_ace`, `melee_specialist`, `sixth_sense`, `dodge_maneuver`.

Default actor ID is 10000 + unit ID and location is the unit ID. Actor identity,
location, connection state, and wizard flag govern ordinary command guards.
Pilot details override inherited pilot fields while retaining unspecified metadata.
Startup reads named `skills.Sixth_Sense`, with `sixth_sense` as the local fallback,
and exposes the source communication reset as `comm_last`.
Use these actor records for core workflows; inherited `caller_is_pilot` and
`caller_wizard` are superseded during core command dispatch.

Core state fields (diagnostic fixture inputs, not commands that earn these states):

- Integer: `engine_rating`, `bv`, `bv_last`, `original_sinks`, `real_num_sinks`, `pilot_status`, `repair_remaining`, `fuel`, `fuel_orig`, `fuel_max`, `carried_cargo`, `last_startup`, `last_use`, `turn_damage`, `stagger_damage`, `stagger_level`, `last_stagger_notify`, `last_comm`, `comm_last`, `lateral`, `last_heat_tick`, `jump_heading`, `disabled_sinks`, `engine_hits`, `gyro_hits`, `sensor_hits`, `pilot_skill_base`, `base_to_hit`, `unusable_arcs`, `rnd`, `last_rnd_update`, `vis_mod`, `comm`, `per`, `last_stagger_check`, `stagger_stamp`, `last_weapon_recycle`, `going_x`, `going_y`, `last_fall_levels`, `mapflag`, `x`, `y`, `mapindex`, `facing`, `hs_engine_override`, `stall`.
- Finite numeric: `jump_length`, `start_fx`, `start_fy`, `start_fz`, `end_fx`, `end_fy`, `jump_pos`, `jump_top`, `engine_heat`, `plus_heat`, `minus_heat`, `weap_heat`, `jump_speed`, `max_speed`, `speed`, `desired_speed`.
- Boolean: `quiet`, `valid_object`, `free_fuel`, `dug_in`, `digging`, `out_of_control`.
- Text: `mechskills`, `template_ref`, `preferred_contact_id`, `contact_id` (exactly two characters).

`x` and `y` are signed 16-bit; `facing` is 0..359. Other integers must fit -2^31..2^32-1, finite numeric fields -1000000..1000000. Physical
fixtures must also respect the applicable source calculation's domain. `real_num_sinks`
uses the source fractional sink representation through the model property.
`cargo_inventory` is an array of `[encoded_part,brand,count]`, with brand 0..255 and
count 0..2^31-1. `stagger_damage_list` accepts records `{amount,occurred_at,counted}`.
`config` adds boolean `extended_gunnery`, `extended_piloting`, `complexrepair`,
`cost_debug`, `random_state`, and `nofusion_vtol_fuel`. The latter defaults false, matching C config.

`extended_gunnery` and `extended_piloting` both default to **false**, as on a
new `GameEngine`. Omitted settings use the existing broad skills: Mech ordinary
weapons share `Gunnery-Battlemech`; biped and quad control use
`Piloting-Battlemech`; ground/naval control uses `Drive`. Other broad class
mappings remain: conventional vehicle, Aerospace, Spacecraft, battle armor and
personal combat. Dedicated special-skill consumers retain their own skills.
Set either option to **true** to opt into its expanded selection independently;
for example, `{"extended_gunnery":true,"extended_piloting":false}` uses weapon-family
gunnery with broad piloting. Existing explicit configuration keeps its selected
mode. These settings select existing skills for firing, piloting and XP; they
do not migrate character values or change scalar pilot ratings, machine skill
overrides or separate-gunner eligibility.

`config.initial_global_tick` initializes the independent heartbeat counter (0..2^32-1).
Map `current_tick` initializes its legacy clock in the same range. Normal
`map_update` calls refresh it from engine event time; it is not an independently
advancing clock. Snapshots expose each map stamp and its actual `moves` counter.

## Randomness

`random` accepts exactly one of `seed`, `array_seed`, or `raw32`, plus optional
`streams`. Scalar and array seeds use source 32-bit wrapping. Array seeds must be
nonempty. `raw32` is a finite list of unsigned 32-bit words consumed by the real MT
entry points; exhaustion is an error. Number uses source high-bit rejection and
consumes rejected words. Number with equal bounds returns zero without a draw.
Roll consumes two dice and increments the shared histogram once. MNumber caches one
random value per unit per six event ticks; initial tick-zero cache is zero.

`streams` maps ordinary consumer names to finite legal values. If supplied, every
consumer reached must have a stream; absent/exhausted/out-of-range draws fail.
Common names include `pilot_rolls`, `recovery_rolls`, `attack_rolls`, `critical_rolls`,
`sensor.random`, `visibility_change`, `failure_generic_chance`, `fuel_check`,
`map_contact_id`, `fall_directions`, and the inherited combat/damage consumers.
Use emitted `draws` to inspect the actual requested names, bounds, values, and raw
word counts. Direct MT/Number diagnostics expose consumption in `state.random`;
they are not named-consumer rows. `config.random_state:true` additionally exposes
`state.random.generator.index` and all 624 generator words for reproducible stream
verification. Separate CLI executions have independent state.

## Actions and ordinary commands

| Action | Fields and behavior |
|---|---|
| `inspect` | Read actual state without advancing clocks, calculating cost/BV, or drawing randomness |
| `advance` | `seconds`: ordinary event and heartbeat progression |
| `command` | `unit` defaults `u`; `name`, optional `args` string/list, optional `actor` record or `pilot`/`caller` |
| `clock` | `name`: dispatch, heartbeat, skip_seconds, heartbeat_init, heartbeat_stop; skip_seconds requires `seconds`; dispatch optionally takes absolute wall seconds |
| `diagnose` | `kind` exact source operation below, positional `args` list; `unit` defaults `u` |
| `schedule` | Source `callback`, positive `delay`, optional integer `data` default 0, `unit`, boolean `cancelled` |
| `core` | `unit`, `values` using the core state fields above |
| `section` | `unit`, `value` section fixture record containing `index` and optional fields/slots |

Inherited actions (`place`, `configure`, and combat diagnostics with `options`)
remain available. Core diagnostics use positional `args`, never expected-result
fields. `schedule` and `callback` are explicitly diagnostic controls; ordinary
workflows should create events with actual commands, damage, and movement.

Core ordinary commands are `startup`, `shutdown`, `skills`, `repair SECTION CRIT`,
`refill SECTION CRIT`, `reattach SECTION`, `replacesuit SECTION`, `reseal SECTION`,
`detach SECTION`, `fixextra`, `recalculate`, `parts`, `cost`, `defensivebv`,
`offensivebv`, `bv [GUN PILOT]`, `rollstats`, and `eventstats`. Section names use
the inherited class-specific aliases; diagnostic section arguments are numeric.
Repair commands are local utility entry points, not a repair-economy authorization
or scheduling service. `recalculate` uses the supplied template. Cost/BV results
include components; legacy BV preserves its distinct cache/sentinel behavior.

Callbacks: `mech_startup_event` (data stage 0..5), `mech_recovery_event`,
`mech_stand_event`, `mech_standfail_event`, `mech_jump_event`,
`mech_stabilizing_event` (also `mech_jumpstabil_event`), `mech_fall_event`,
`mech_move_event`, `aero_move_event`, `mech_crewstun_event`, `unstun_crew_event`,
`check_stagger_event`, `mech_sideslip_event`, `mech_lateral_event`,
`mech_movemode_event`, `mech_unjam_ammo_event`, `mech_lock_event`,
`mech_plos_event`, and `very_fake_func`. Data for PLOS/LOCK is the owning engine.
LATERAL data is the C direction-table index 0..8, mapping respectively to offsets
300, 300, 60, 60, 240, 240, 120, 120, 0; the snapshot exposes `lateral`.

## Source diagnostics

The following table lists required positional arguments for direct function
adapters. `section` is 0..7, `critical` 0..11, `part` 0..1023, `catalog` a registered
weapon index, `coord` a signed 16-bit coordinate, `integer` a source integer,
`real` a finite number, and `boolean` a JSON boolean. Lambdas below are described
in the notes immediately after the table. All selected-unit functions read/mutate
the actual session unit.

| Operation | Positional arguments |
|---|---|
| `AcceptableDegree` | integer |
| `ArmorStringFromIndex` | integer |
| `CalcFasaCost` | none |
| `Calculate_Defensive_BV` | none |
| `Calculate_Offensive_BV` | none |
| `CountAmmoForWeapon` | catalog |
| `CountDestroyedLegs` | none |
| `FindAmmoForWeapon` | catalog, section |
| `FindArtemisForWeapon` | section, critical |
| `FindAverageGunnery` | none |
| `FindBearing` | real, real, real, real |
| `FindComponents` | real, integer |
| `FindFirstWeaponCrit` | section, special input (see notes), critical, part, special input (see notes) |
| `FindGunnerySkillName` | catalog or negative integer (no extended skill) |
| `FindHexRange` | real, real, real, real (Cartesian coordinates, like FindXYRange) |
| `FindObj` | section, part |
| `FindPilotArtyGun` | none |
| `FindPilotGunnery` | catalog or negative integer |
| `FindPilotPiloting` | none |
| `FindPilotSpotting` | none |
| `FindPilotingSkillName` | none |
| `FindRange` | real, real, real, real, real, real |
| `FindRoundsForWeapon` | catalog |
| `FindSPilotPiloting` | none |
| `FindSplitCrits` | section, part, critical |
| `FindTechSkillName` | none |
| `FindWeaponFromIndex` | catalog |
| `FindWeaponIndex` | integer |
| `FindWeapons_Advanced` | section, optional whine boolean (true), optional silence boolean (false) |
| `FindXY` | real, real, integer, real |
| `FindXYRange` | real, real, real, real |
| `FindZBearing` | real, real, real, real, real, real |
| `FullAmmo` | section, critical |
| `GetPartMod` | part |
| `GetSplitData` | section, critical |
| `GetWeaponCrits` | catalog |
| `InWeaponArc` | real, real |
| `IsInWeaponArc` | real, real, section, critical |
| `IsLegDestroyed` | section |
| `IsMechLegLess` | none |
| `MapCoordToRealCoord` | coord, coord |
| `MechPilotSkillRoll_BTH` | integer |
| `MyHexDist` | coord, coord, coord, coord, integer |
| `MyToUpper` | string |
| `ProperArmor` | none |
| `ProperInternal` | none |
| `ProperMyomer` | none |
| `ProperSectionStringFromType` | none |
| `RealCoordToMapCoord` | real, real |
| `ReverseSplitCritLoc` | section, critical |
| `SectHasBusyWeap` | section |
| `SetCargoWeight` | none |
| `alias_part` | part, section |
| `checkAllSections` | integer |
| `checkSectionForSpecial` | integer, section |
| `do_fixextra` | none |
| `do_magic` | none |
| `getRemainingArmorPercent` | none |
| `getRemainingInternalPercent` | none |
| `heat_factor` | none |
| `listmatch` | special input (see notes), string |
| `mech_Detach` | section |
| `mech_FillPartAmmo` | section, critical |
| `mech_ReAttach` | section |
| `mech_ReSeal` | section |
| `mech_RepairPart` | section, critical |
| `mech_ReplaceSuit` | section |
| `mech_armorpoints` | none |
| `mech_intpoints` | none |
| `mechtypename` | none |
| `no_locations_destroyed` | none |
| `part_weight` | part, optional boolean tables (default true) |
| `partlist` | none |
| `payloadlist` | none |
| `prolong_uncon` | integer |
| `round_to_halfton` | integer |
| `round_to_quarterton` | integer |
| `unit_parts_list` | optional integer mode, ignored as in C |
| `update_specials` | none |

`listmatch` takes a string array and sought text. `FindFirstWeaponCrit` takes
section, slot (-1..11), start critical, encoded part, positive run size (1..12).
`FindObj` uses encoded part while checkSectionForSpecial/checkAllSections use
unencoded Special index. Core aliases: GetPartWeight=part_weight,
UnitPartsList=unit_parts_list, HeatFactor=heat_factor, ProlongUncon=prolong_uncon,
debug_EventTypes=debug_event_types.

Additional operations:

| Operations | Arguments |
|---|---|
| `Number`, `MNumber` | low, high; MNumber requires ordered bounds |
| `Roll`, `do_show_stat`, `genrand_int32`, `genrand_int31`, `genrand_real1`, `genrand_real2`, `genrand_real3`, `genrand_res53` | none |
| `init_stat`, `init_genrand`, `init_by_array` | seed; array seed for init_by_array |
| `debug_event_types` | optional text; `c` selects counts |
| `initialize_part_costs`, `GetPartCost`, `SetPartCost` | none; part; part and unsigned64 value, respectively |
| `MechIDS` | optional lower-case boolean |
| `CalculateBV` | none, gun/pilot, or gun/pilot/tick; 100 skill sentinels retain source quirks |
| `CalcFasaCost_DoArmMath`, `CalcFasaCost_DoLegMath` | section |
| `MechNumHeatsinksInEngine` | none |
| `CalcFasaCost_AddPrice`, `Calc_AddOffBV`, `Calc_AddDefBV`, `Calc_SubDefBV` | initial total, label, amount |
| `FindAmmunition` | optional full-capacity boolean |
| `ammo_capacity` | encoded unsigned16 ammo, fire mode, ammo mode |
| `FindObjWithDest` | section, encoded part |
| `do_sub_magic` | optional loud boolean |
| `FindWeaponNumberOnMech`, `FindWeaponNumberOnMech_Advanced` | weapon number, optional sight boolean |
| `WeaponIsNonfunctional` | section, critical, optional run size |
| `CritsInLoc` | section |
| `MechFullNoRecycle` | mask (1 weapon, 2 physical) |
| `FindLegHeatSinks`, `FindDestructiveAmmo`, `FindInfernoAmmo`, `FindTechSkill` | none |
| `MadePilotSkillRoll`, `MadePilotSkillRoll_NoXP`, `MadePilotSkillRoll_Advanced` | optional modifier, succeed-when-fallen boolean, award-XP boolean |
| `ValidMap` | optional map name, valid-object boolean, XTYPE text, allocated boolean; defaults described below |
| `FindMechOnMap`, `FindTargetDBREFFromMapNumber` | contact token; first two characters, first roster match |
| `find_mech_in_hex` | x, y, needlos (bitmask 0..3) |
| `FindTargetXY`, `CheckEdgeOfMap`, `Leave_Hangar`, `FuelCheck`, `MarkForLOSUpdate` | none |
| `navigate_sketch_mechs`, `visit_neighbor_hexes` | x, y |
| `ChannelEmitKill` | optional attacker unit name, optional reason string/null; empty string differs from null |
| `mech_heartbeat` | none |
| `heartbeat_dispatch` | unit or object name |
| `run_by_type`, `cancel_events` | EventType enum name |
| `history_input` | array of up to 100 nonnegative counts with total at most 2^31-1; diagnostics only, callbacks do not increment C history |
| `callback` | source callback name, optional data; executes via the real event observer with current event visible |
| `calcStaggerBTHMod` | none; legacy modifier |
| `calcNewStaggerBTHMod` | level, optional weight-adjustment boolean |
| `accumulate_stagger_damage` | amount |
| `get_stagger_damage` | timestamp, optional count-and-mark boolean |
| `mark_stagger_damage`, `clear_stagger_damage` | integer stagger level |
| `clear_old_stagger_damage` | timestamp |
| `clear_all_stagger_damage` | none |

## Observable state and boundaries

State includes source event IDs/names/deadlines/data, event observer trace, inert
100-slot history, wall/event/global clocks and heartbeat timer, random word count
and Roll histogram, actual section slots, pilot/caller/skills, cargo and stagger
history, template copies, price table, map rosters/LOS, and notices. `xp_requests`,
`external_effects`, `channel_requests`, `hook_requests`, and `debug_messages`
record requested unavailable operations. An `applied:false` record is not proof
that a persistent server action succeeded. `cost_debug` records source component
messages while leaving calculated totals unchanged.

This narrower adapter uses local actor/map/template fixtures. Its legacy AUTO
objects need configured services, and its fixtures do not compose the full flight,
transport or persistent-character interfaces. Use the
[full session composition](architecture.md#how-sessions-compose),
[Battlesheep interface](autopilot-cli.md), [Aerospace interface](aerospace-cli.md)
and [historical fighter guide](six-location-aerofighters-cli.md) for those
implemented systems. External MUX character attributes, object-database
operations, server channels/hooks and client transport still require a host
application; local fixture metadata does not provide those services.
Unsupported numeric domains
are explicit, including uninitialized Clan CASE cost slots, undefined part weights,
and unsafe negative catalog indices. No NaN/Infinity is serialized as successful JSON.

## Reproducible examples

Startup reaches its sixth stage at 30 seconds:

```json
{"units":[{"name":"u","started":false,"pilot":false}],"actions":[
  {"op":"command","name":"startup"},
  {"op":"advance","seconds":29},
  {"op":"inspect"},
  {"op":"advance","seconds":1},
  {"op":"command","name":"shutdown"}]}
```

Sparse source FASA cost is 2604999, with exact unsigned64 price storage:

```json
{"config":{"periodic_updates":false},"units":[{"name":"u","profile":"sparse",
  "max_speed":0,"core":{"engine_rating":200}}],"actions":[
  {"op":"command","name":"cost"},
  {"op":"diagnose","kind":"SetPartCost","args":[1,18446744073709551615]},
  {"op":"diagnose","kind":"GetPartCost","args":[1]}]}
```

Source Number rejects the first word, returns 1, and reports two words consumed:

```json
{"random":{"raw32":[4294967295,0]},"actions":[
  {"op":"diagnose","kind":"Number","args":[1,6]}]}
```

## Recovery QA diagnostic additions

`muxevent_count_initialize` takes no arguments and calls the real initializer for
all 100 history slots. A scheduled callback's external trace contains `pre`,
`callback`, and `post` phases; each row includes `pending_same_type`, the live
count at that phase. The production pre/post hook bodies remain unchanged.

`ValidMap` accepts optional arguments `(map_name, valid_object, xtype, allocated)`.
Defaults are the first map, true, `"MAP"`, true. These represent source lookup
metadata and allow ordered guard checks, including empty or differently cased
XTYPE. They do not relocate units or create a persistent MUX object.

Material selectors return exact C numeric IDs. `mech.h`'s `TON_*` bases precede
the corresponding cargo-name offsets by one because `template.c` includes an
extra name. `ProperInternal`, `ProperMyomer`, and sized `alias_part` preserve the
header IDs; the cargo-name and weight tables retain their original ordering.
FASA's `CASEII` cost constant is 50, distinct from equipment `CASE_II` 33.

`state.heartbeat_trace` records each actual registry dispatch's ID/type, wall and
event times, global counter and already-rearmed timer deadline. It is recorded by
an optional observer; it does not dispatch entities or alter their state.

`queue_event(type, delay)` schedules an intentional empty callback under the given
event enum for pending-list/cancellation diagnostics. Delay is1..100000. It does
not claim to exercise that type's gameplay callback. `callback` accepts an optional
third boolean to supply a null unit only for the source-null-safe
`mech_crewstun_event`.

`multi_weap_sel(text, mode, stop_after?)` invokes the real selector in mode0..3 and
reports ordered callback `calls` and source validation `messages`. The diagnostic
callback records ranges and optionally stops after1..96 calls (0 means no stop).
Ordinary TIC/fire commands remain the consumer tests for actual gameplay changes.

A map clock fixture can start with a distinct value; normal `map_update` calls
replace it with engine event time. `MNumber` uses engine event time when the unit
belongs to an engine. The heartbeat trace includes MAP and
OTHER registry entries even though their dispatch does no MECH/AUTO work.
