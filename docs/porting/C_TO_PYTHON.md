# C to Python: source and behavior navigation

This guide connects the original BTMux C simulation to the Python engine. Start with the [module crosswalk](#module-crosswalk) to find a subsystem, or search the [source identity index](#source-identity-index) for an exact C function name. The index includes all sixteen simulation modules and all five Battlesheep files, with separate historical Aerospace entries where the same C identity has different behavior.

For embedding and commands, use the [architecture](../architecture.md), [Python API](../python-api.md), [client integration](../client-integration.md) and subsystem guides linked below. [Completion and verification](COMPLETION.md) describes the implemented scope and the checks available to contributors.

## Source references and profiles

The simulation derives from the original BTMux C source and its contributors. The upstream repository is [KrugerHeavyIndustries/btmux](https://github.com/KrugerHeavyIndustries/btmux). Original source notices and function identities remain relevant when comparing implementations.

A **source profile** identifies the C revision and configuration governing a behavior. The engine combines the general simulation with the recovered Aerospace rules; these profiles describe source authority, rather than two interchangeable whole-engine modes.

| Profile | Reference revision and source subtree | Governs |
|---|---|---|
| General, `checked_in_pipeline_2026_09_15` | [Revision `037f611cd0c81e75d82c82d0bbe2b2622970990c`](https://github.com/KrugerHeavyIndustries/btmux/tree/037f611cd0c81e75d82c82d0bbe2b2622970990c), `btech/src/` | Ordinary simulation, shared infrastructure adapters and general Battlesheep behavior. Most gameplay files are in its `btech/` child. |
| Historical Aerospace, `aerospace_pre_at2_96f2131` | [Revision `96f2131705a7fe51c3c6f7da741930ff06a93644`](https://github.com/KrugerHeavyIndustries/btmux/tree/96f2131705a7fe51c3c6f7da741930ff06a93644), `src/hcode/` | Six-location fighters, flight, bombing, DropShip bays/turrets, and the Aerospace branches of shared damage, targeting, movement, construction, display and AI code. |

The historical revision immediately precedes the AT2 conversion in `776daca27710eec72c0bf548964da12c6b2c7b28`. It supplies the complete six-location fighter model: **Nose, Left Wing, Right Wing, Fuselage, Cockpit and Engine**. The newer general tree's four-location fighter refactor does not govern those rules. Fighters use the recovered armor and component behavior; DropShips retain their distinct section and damage rules. See the [six-location interface](../six-location-aerofighters-cli.md) and [Aerospace interface](../aerospace-cli.md).

The general configuration includes movement modes, ODDJUMP, HUD support and Battle Value (BV) calculations, with `EXILE_MW3STATS` disabled. Advanced economy and complex-repair helpers are available as diagnostics; ordinary repair commands retain complex repairs and free tech time disabled. Runtime options, including skill selection, remain separate from those source-build choices. Both recorded infrared alternatives belong to one source identity, and the active `char_lookupplayer` definition is distinguished from its disabled predecessor.

### Obtain optional reference checkouts

Running the Python engine does not require either C checkout. Source comparisons and some [QA tools](../../qa/README.md) use them separately; neither C tree is bundled in the Python wheel or source distribution. With Git installed, run the following commands from a source checkout to create fresh reference directories at the paths those tools expect:

```sh
git clone https://github.com/KrugerHeavyIndustries/btmux.git btmux/btmux
git -C btmux/btmux checkout --detach 037f611cd0c81e75d82c82d0bbe2b2622970990c

git clone https://github.com/KrugerHeavyIndustries/btmux.git references/btmux-pre-at2-96f2131/source
git -C references/btmux-pre-at2-96f2131/source checkout --detach 96f2131705a7fe51c3c6f7da741930ff06a93644
```

Use these commands for new directories. If references already exist, inspect their revisions before deciding whether to reuse them. The resulting C roots are `btmux/btmux/btech/src/` and `references/btmux-pre-at2-96f2131/source/src/hcode/`. To inspect a historical file without creating the second checkout:

```sh
git -C btmux/btmux show 96f2131705a7fe51c3c6f7da741930ff06a93644:src/hcode/btech/mech.hitloc.c
```

The optional unit-template catalogue is a different dependency, with its own pin and explicit setup procedure in [catalogue integration](../template-catalog-integration.md). Sessions do not download it automatically.

## From C structures to Python execution

| C concept | Python location and responsibility |
|---|---|
| `MECH`, `MAP`, `AUTO`, structure fields and accessor macros | [Mech](../../entities/mech.py), [GameMap](../../entities/map.py) and [Autopilot](../../entities/autopilot.py) objects hold unit, terrain and controller state. [Unit constants](../../entities/mech.py) and [data](../../data/) retain flags, parts, weapons and template identities. A macro can become a field, property, helper or expression rather than a same-named function. |
| Global object lookup, special-object registries and services | [GameEngine](../../core/game_loop.py) owns registered entities, map lookup, clocks and service dispatch. [Attributes](../../core/attributes.py), [characters](../../systems/characters.py) and [occupants](../../systems/occupants.py) supply the relevant local identity, preference and containment behavior. |
| Command functions and host command tables | [Session adapters](../../tools/) parse public actions and pass commands to the gameplay owners in [systems](../../systems/). Admission checks retain actor identity, permission, unit readiness, equipment and argument rules. [Communications](../../systems/communications.py) supplies shared checks used by many commands. |
| C event callbacks and heartbeat updates | [EventQueue and events](../../core/events.py) hold deadlines, callback owners, types and payloads. [GameEngine](../../core/game_loop.py) advances ticks and performs heartbeat work. Movement, heat, repairs and controllers use their normal callbacks. |
| Static arrays, dispatch tables and equipment definitions | [Data modules](../../data/), [weapon modes](../../systems/weapon_modes.py) and other subsystem tables carry the corresponding data. A table-driven command can replace many C wrapper functions. |
| Server notifications and textual displays | [Communications](../../systems/communications.py), [observation](../../systems/observation.py), [status displays](../../systems/status_display.py) and [HUD](../../systems/hud.py) produce messages and structured results through local recipients and sessions. |
| Database and file services used by gameplay | [Character storage](../../data/characters.py), [map storage](../../entities/map_storage.py), [environment storage](../../systems/environment_storage.py), [repair job storage](../../systems/repair_jobs.py) and [autopilot storage](../../systems/autopilot_storage.py) own their respective persistence formats. |

### Follow a command through its callbacks

A public action enters `Session.action(...)`; the appropriate `command(...)` adapter resolves its unit and arguments and calls the subsystem command. The command checks admission, performs its immediate state changes and notifications, and schedules any delayed work. `GameEngine.process_tick()` advances the simulation so that those callbacks can mutate state and schedule subsequent work. A session snapshot exposes the resulting state; it does not itself advance time.

For example, a startup request reaches [startup commands](../../systems/startup.py), schedules a startup event and proceeds through the normal readiness and completion checks. A speed order changes desired speed through [movement commands](../../systems/movement_commands.py); [movement callbacks](../../physics/movement.py) update actual motion. Battlesheep uses these same gameplay paths.

An individual helper can have a different entry contract from a player command. In firing, [combat admission and `resolve_attack`](../../systems/combat.py) reject an ordinary fired missile miss before AMS, pod or Swarm impact processing, while the launcher still applies its normal firing costs. Direct [missile helpers](../../systems/missile.py) retain their own miss behavior. Read both the helper and its caller when locating the equivalent C path.

`CoreSession` and `AutopilotSession` provide programmatic `action(...)`, `snapshot()` and engine access. Their module CLIs consume one JSON scenario, execute its actions, emit one JSON result and exit. A continuous client transport belongs around the session API; see [client integration](../client-integration.md). The full adapter inheritance chain and interface schemas are in the [Python API guide](../python-api.md).

## Module crosswalk

The module labels in parentheses are stable identifiers for the sixteen simulation groups. The appendix supplies every original C file and identity, including shared Aerospace mappings.

| Simulation area | Original C families | Main Python owners and public reference |
|---|---|---|
| Shared utilities (`AUD-UTILS`) | `mech.utils.c` | [Geometry](../../physics/hexmath.py), [parts](../../systems/parts.py), [weapon inventory](../../systems/weapon_inventory.py), [core diagnostics](../../tools/core_diagnostics.py); [core interface](../core-simulation-cli.md). |
| Construction and templates (`AUD-TEMPLATES`) | `mech.build.c`, `mech.consistency.c`, `mech.mechref_ident.c`, `mech.partnames.c`, `mechrep.c`, `template.c` | [Template files](../../data/template_files.py), [template directories](../../data/template_directory.py), [construction editor](../../systems/construction_editor.py), [weight](../../systems/construction_weight.py); [construction interface](../construction-templates-cli.md). |
| Maps and environment (`AUD-MAPS`) | `map.c`, `map.bits.c`, `map.coding.c`, `map.conditions.c`, `map.dynamic.c`, `map.obj.c`, `map.weather.c` | [Map state](../../entities/map.py), [map management](../../systems/map_management.py), [membership](../../systems/map_membership.py), [environment storage](../../systems/environment_storage.py), [map session](../../tools/maps_environment.py); [scenario guide](../running-scenarios.md). |
| Repair, economy and cargo (`PILOT-REPAIR`) | `mech.tech*.c`, `econ.c`, `econ_cmds.c`, `mech.pickup.c` | [Repair work](../../systems/repair_work.py), [jobs](../../systems/repair_jobs.py), [economy](../../systems/economy.py), [cargo](../../physics/cargo.py), [towing](../../systems/towing.py); [repair/economy interface](../repair-economy-cli.md). |
| Pilots, infantry and battle armor (`AUD-PILOTS`) | `btechstats.c`, `eject.c`, `pcombat.c`, `bsuit.c` | [Characters](../../systems/characters.py), [piloting](../../systems/piloting.py), [experience](../../systems/experience.py), [personal damage](../../systems/personal_damage.py), [swarm/boarding](../../systems/swarm.py); [pilot interface](../pilots-cli.md). |
| Sensors, LOS and targeting (`AUD-SENSORS`) | `mech.sensor*.c`, `mech.los.c`, `mech.lostracer.c`, `map.los.c`, `mech.ecm.c`, `mech.lite.c`, `mech.spot.c`, `mech.tag.c` | [Sensors](../../systems/sensors.py), [LOS](../../systems/los.py), [targeting](../../systems/targeting.py); [sensors/LOS interface](../sensors-los-cli.md). LOS means line of sight and is evaluated directionally for each observer. |
| Communications and C3 (`AUD-COMMS`) | `mech.c3.c`, `mech.c3.misc.c`, `mech.c3i.c`, `mech.notify.c` | [Communications](../../systems/communications.py), [C3](../../systems/c3.py), [network reports](../../systems/network_reports.py); [radio interface](../communications-cli.md), [C3 interface](../c3-communications-cli.md). |
| Heat and tick updates (`AUD-HEAT`) | `mech.update.c`, `mech.fire.c`, `mech.ammodump.c` | [Heat](../../systems/heat.py), [ammunition dumping](../../systems/ammo_dump.py), [movement](../../physics/movement.py), [cargo](../../physics/cargo.py); [heat interface](../heat-updates-cli.md). |
| Movement and surfaces (`AUD-MOVEMENT`) | `mech.move.c`, `mech.ice.c`, `mech.ood.c`, `btspath.c`, `spath.c` | [Movement commands](../../systems/movement_commands.py), [movement](../../physics/movement.py), [orbital descent](../../physics/orbital.py), [path costs](../path_costs.md). |
| Damage, criticals and failures (`AUD-DAMAGE`) | `mech.damage.c`, `crit.c`, `mech.enhanced.criticals.c`, `failures.c` | [Damage](../../systems/damage.py), [combat damage routing](../../systems/combat.py), [criticals](../../systems/criticals.py), [enhanced criticals](../../systems/enhanced_crits.py), [failures](../../systems/failures.py); [damage interface](../damage-criticals-cli.md). |
| Weapon firing (`AUD-FIRING`) | `mech.combat*.c`, `mech.bth.c`, `mech.tic.c` | [Firing commands](../../systems/combat_firing.py), [combat resolution](../../systems/combat.py), [missiles](../../systems/missile.py), [weapon groups](../../systems/tic.py); [combat interface](../combat-resolution-cli.md). |
| Physical combat (`AUD-PHYSICAL`) | `mech.physical.c`, `mech.hitloc.c` | [Physical attacks](../../systems/physical.py), [hit locations](../../systems/hit_locations.py), [vehicle combat](../../systems/vehicle_combat.py); [combat interface](../combat-resolution-cli.md). |
| Special equipment, artillery and mines (`AUD-SPECIAL-COMBAT`) | `mech.advanced.c`, `artillery.c`, `mine.c` | [Weapon modes](../../systems/weapon_modes.py), [artillery](../../systems/artillery.py), [mines](../../systems/mines.py); [combat interface](../combat-resolution-cli.md). |
| Clocks, events and startup (`AUD-CORE`) | `tick.c`, `events.c`, `mech.events.c`, `mech.startup.c`, `mech.stat.c`, `mt19937ar.c` | [Engine loop](../../core/game_loop.py), [events](../../core/events.py), [startup](../../systems/startup.py), [randomness](../../core/randomness.py), [MT19937](../../core/mt19937.py); [core interface](../core-simulation-cli.md). |
| Aerospace and DropShips (`AUD-AEROSPACE`) | `aero.move.c`, `aero.bomb.c`, `ds.bay.c`, `ds.turret.c`, plus historical branches in shared files | [Aerospace motion](../../physics/aerospace.py), [bombing](../../systems/bombing.py), [bays](../../systems/dropships.py), [turrets](../../systems/turrets.py); [Aerospace](../aerospace-cli.md) and [six-location fighters](../six-location-aerofighters-cli.md). |
| HUD, status and maps (`AUD-HUD`) | `hudinfo.c`, `mech.contacts.c`, `mech.maps.c`, `mech.scan.c`, `mech.status.c` | [HUD](../../systems/hud.py), [observation](../../systems/observation.py), [status](../../systems/status_display.py), [armor](../../systems/armor_display.py), [map display](../../systems/map_display.py); [display interface](../hud-status-cli.md). |

## Battlesheep and autonomous units

Battlesheep is implemented as a built-in controller. Its A* navigation searches for a path using accumulated travel cost and an estimate of the remaining distance. Its five-file port covers 119 active C identities, plus the retained classification of 23 inactive/empty entries and one extraction artifact.

| Original C file | Active identities | Python owner |
|---|---:|---|
| `btech/autopilot_core.c` | 24 | [Controller lifecycle, queue and codec](../../systems/autopilot_core.py) |
| `btech/autopilot_ai.c` | 24 | [A* path search, predictive steering and artillery lead](../../systems/autopilot_ai.py) |
| `btech/autopilot_commands.c` | 26 | [Command execution and movement callbacks](../../systems/autopilot_commands.py) |
| `btech/autopilot_autogun.c` | 14 | [Sensors, weapon profiles, target scoring and autonomous combat](../../systems/autopilot_autogun.py) |
| `btech/autopilot_radio.c` | 31 | [Radio parsing, orders and acknowledgments](../../systems/autopilot_radio.py) |

[Registration and service selection](../../systems/autopilot.py) connect controllers to `GameEngine`. Ordinary heartbeat dispatch visits registered objects in sorted order and obtains sensor, weapon-profile and gun services live, preserving explicit service overrides. The profile condition is evaluated after sensors. Fighters and both DropShip classes use the historical event-driven controller chains selected by `uses_event_autopilot`.

[Radio delivery](../../systems/communications.py) invokes the built-in parser at the established handoff before range/scramble processing. Addressed and broadcast orders reach normal movement, startup, combat, towing and boarding services. Delayed replies belong to the unit, so controller replacement does not silently change their ownership. The four former radio/heartbeat integration gaps are closed.

[Snapshot version 2](../../systems/autopilot_storage.py) preserves controller state, attachment, queue contents and relative service/reply deadlines. It validates before mutation and preserves the scheduler's established ordering for equal deadlines. Navigation paths and weapon profiles rebuild through their normal callbacks. World state, clocks and random state remain owned by the other services; loading an AI snapshot is not a whole-world rewind.

Some accepted queue names correspond to inactive C executor cases and retain their source stalling behavior. Radio jumping is independently active. Allocation/free, comparator and diagnostic functions have entries in the index even when their Python equivalent is container ownership, a callback or a no-op rather than another user command. See the [autopilot interface](../autopilot-cli.md) and [three runnable AI encounters](../../examples/gameplay_scenarios/AI.md).

## Arithmetic, randomness and intentional adaptations

The port preserves C arithmetic where it affects gameplay: truncation toward zero, selected binary32 (32-bit floating-point) intermediate values, source rounding, integer masks, boundary comparisons and random draw order. Python's default numeric operations are used only where they express the required calculation. [Hex geometry](../../physics/hexmath.py), [randomness](../../core/randomness.py) and [MT19937](../../core/mt19937.py) provide concrete examples. `FindBearing` gives 91 for the eastward vector in the [geometry tests](../../tests/test_core_geometry.py), because the source adds 5 before signed integer division.

Randomness belongs to each engine. A seeded MT19937 pseudorandom generator supports reproducible scenarios; named finite streams supply specific draws for targeted cases, and sessions expose consumed draws. Reproducing a result requires the same state, command path and draw order, rather than a seed alone. Event deadlines and cancellation are part of that state: equal deadlines do not imply a new FIFO guarantee.

Three current adaptations should be taken into account when comparing with older C behavior:

- **Heat shutdown begins at 14.** Below 14, neither shutdown nor shutdown-avoidance dice occur. At 14/18/22/26 heat the avoidance targets are 4/6/8/10 on ordinary 2d6; at 30 or more shutdown is automatic. Fractional heat is compared directly. The shared overheat gate remains 10, with an elapsed 30-tick interval and ammunition effects evaluated first. Player pilots and controllers use the same rule. See [heat implementation](../../systems/heat.py) and [heat interface](../heat-updates-cli.md).
- **Broad skills are the defaults.** `extended_gunnery` and `extended_piloting` both default to `false`, and either can be enabled independently. Mech weapon families normally select `Gunnery-Battlemech`; biped/quad control selects `Piloting-Battlemech`; ground/naval vehicle control selects `Drive`. Existing expanded skills, scalar ratings, overrides and separate gunners remain supported. XP follows the selected skill. See [skill selection](../../systems/piloting.py) and [core configuration](../core-simulation-cli.md).
- **Equal-bound weather growth returns the endpoint.** Eligible growth with bounds 10..10 adds 10 without consuming an ordinary MT draw. This is local to weather: shared `Number` retains its original equal-bound result of zero. Named weather injections retain their own draw accounting. See the [weather regression cases](../../tests/test_maps_reconstruction.py).

## Simulation scope and the MUX host boundary

The engine implements simulation behavior and local adapters for the host services it needs. It does not reproduce the original MUX multi-user text server's database, softcode language, command dispatcher, login/server lifecycle, legacy menus or file wrappers. The original host-infrastructure inventory contains 213 entries: 211 active and two inactive/empty, across `btdb.c`, `btech/btech.c`, `btech/mech.restrict.c`, `coolmenu.c`, `debug.c`, `glue.c`, `glue.hcode.c`, `glue.scode.c`, `mechfile.c` and `xcode_io.c`.

Those exclusions do not remove simulation effects from callers. Entity registration and local attributes replace the applicable object-access operations; session commands and diagnostics expose gameplay operations; structured display results replace host menu delivery; subsystem storage replaces the applicable persistence services. For instance, a map transfer still updates membership, LOS and network state through [map transitions](../../systems/map_transitions.py), even though the original MUX administrative dispatcher is outside the product. The [Python API](../python-api.md) describes supported embedding surfaces, and [contributing](../../CONTRIBUTING.md) explains how to test a change.

## Source identity index

Each row preserves a stable `C file::function` identity. **General** means `checked_in_pipeline_2026_09_15`; **Historical Aerospace** means `aerospace_pre_at2_96f2131`. Shared identities can have two rows, so a reader can follow both behavior profiles. Battlesheep's general entries also use the historical branches described above where applicable.

The simulation index contains **1,422 source/profile records**: **1,387 active**, **23 inactive/empty** and **12 extraction artifacts**. Its active set includes 43 supplemental historical Aerospace records in addition to the sixteen modules' 1,344 assigned active records. Battlesheep adds **143 records**, of which **119 are active**, **23 inactive/empty** and **one an extraction artifact**. These are source-navigation counts, not numbers of tests or unresolved defects.

Python targets distinguish functions/methods, inline expressions, dispatch branches and data tables. Descriptive text after a symbol identifies a branch or use; it is not another function name. Multiple targets describe split responsibilities. Inactive rows preserve disabled or empty C entries and any retained Python hook. Extraction artifacts are macro/type text captured by source extraction, not functions requiring an implementation. MUX infrastructure is accounted for separately above.

The tables are assembled from the established source inventories, with obsolete owner names resolved against the completed implementation. They intentionally omit old implementation-status fields and behavioral-finding text. For runnable encounters, use [Running scenarios](../running-scenarios.md); for verification outcomes, use [Completion](COMPLETION.md).

### File directory

| Original C file | Profiles |
|---|---|
| [btech/aero.bomb.c](#c-btech-aero-bomb-c) | Historical Aerospace |
| [btech/aero.move.c](#c-btech-aero-move-c) | Historical Aerospace |
| [btech/artillery.c](#c-btech-artillery-c) | General |
| [btech/autopilot_ai.c](#c-btech-autopilot-ai-c) | General |
| [btech/autopilot_autogun.c](#c-btech-autopilot-autogun-c) | General |
| [btech/autopilot_commands.c](#c-btech-autopilot-commands-c) | General |
| [btech/autopilot_core.c](#c-btech-autopilot-core-c) | General |
| [btech/autopilot_radio.c](#c-btech-autopilot-radio-c) | General |
| [btech/bsuit.c](#c-btech-bsuit-c) | General; Historical Aerospace |
| [btech/btechstats.c](#c-btech-btechstats-c) | General |
| [btech/btspath.c](#c-btech-btspath-c) | General |
| [btech/crit.c](#c-btech-crit-c) | General; Historical Aerospace |
| [btech/ds.bay.c](#c-btech-ds-bay-c) | Historical Aerospace |
| [btech/ds.turret.c](#c-btech-ds-turret-c) | Historical Aerospace |
| [btech/econ.c](#c-btech-econ-c) | General |
| [btech/econ_cmds.c](#c-btech-econ-cmds-c) | General |
| [btech/eject.c](#c-btech-eject-c) | General |
| [btech/failures.c](#c-btech-failures-c) | General |
| [btech/hudinfo.c](#c-btech-hudinfo-c) | General |
| [btech/map.bits.c](#c-btech-map-bits-c) | General |
| [btech/map.c](#c-btech-map-c) | General |
| [btech/map.coding.c](#c-btech-map-coding-c) | General |
| [btech/map.conditions.c](#c-btech-map-conditions-c) | General |
| [btech/map.dynamic.c](#c-btech-map-dynamic-c) | General |
| [btech/map.los.c](#c-btech-map-los-c) | General |
| [btech/map.obj.c](#c-btech-map-obj-c) | General; Historical Aerospace |
| [btech/map.weather.c](#c-btech-map-weather-c) | General |
| [btech/mech.advanced.c](#c-btech-mech-advanced-c) | General |
| [btech/mech.ammodump.c](#c-btech-mech-ammodump-c) | General |
| [btech/mech.bth.c](#c-btech-mech-bth-c) | General; Historical Aerospace |
| [btech/mech.build.c](#c-btech-mech-build-c) | General; Historical Aerospace |
| [btech/mech.c3.c](#c-btech-mech-c3-c) | General |
| [btech/mech.c3.misc.c](#c-btech-mech-c3-misc-c) | General |
| [btech/mech.c3i.c](#c-btech-mech-c3i-c) | General |
| [btech/mech.combat.c](#c-btech-mech-combat-c) | General |
| [btech/mech.combat.misc.c](#c-btech-mech-combat-misc-c) | General; Historical Aerospace |
| [btech/mech.combat.missile.c](#c-btech-mech-combat-missile-c) | General |
| [btech/mech.consistency.c](#c-btech-mech-consistency-c) | General |
| [btech/mech.contacts.c](#c-btech-mech-contacts-c) | General |
| [btech/mech.damage.c](#c-btech-mech-damage-c) | General; Historical Aerospace |
| [btech/mech.ecm.c](#c-btech-mech-ecm-c) | General |
| [btech/mech.enhanced.criticals.c](#c-btech-mech-enhanced-criticals-c) | General |
| [btech/mech.events.c](#c-btech-mech-events-c) | General |
| [btech/mech.fire.c](#c-btech-mech-fire-c) | General |
| [btech/mech.hitloc.c](#c-btech-mech-hitloc-c) | General; Historical Aerospace |
| [btech/mech.ice.c](#c-btech-mech-ice-c) | General |
| [btech/mech.lite.c](#c-btech-mech-lite-c) | General |
| [btech/mech.los.c](#c-btech-mech-los-c) | General |
| [btech/mech.maps.c](#c-btech-mech-maps-c) | General |
| [btech/mech.mechref_ident.c](#c-btech-mech-mechref-ident-c) | General |
| [btech/mech.move.c](#c-btech-mech-move-c) | General; Historical Aerospace |
| [btech/mech.notify.c](#c-btech-mech-notify-c) | General |
| [btech/mech.ood.c](#c-btech-mech-ood-c) | General |
| [btech/mech.partnames.c](#c-btech-mech-partnames-c) | General |
| [btech/mech.physical.c](#c-btech-mech-physical-c) | General |
| [btech/mech.pickup.c](#c-btech-mech-pickup-c) | General |
| [btech/mech.restrict.c](#c-btech-mech-restrict-c) | Historical Aerospace |
| [btech/mech.scan.c](#c-btech-mech-scan-c) | General |
| [btech/mech.sensor.c](#c-btech-mech-sensor-c) | General |
| [btech/mech.sensor.functions.c](#c-btech-mech-sensor-functions-c) | General |
| [btech/mech.spot.c](#c-btech-mech-spot-c) | General |
| [btech/mech.startup.c](#c-btech-mech-startup-c) | General |
| [btech/mech.stat.c](#c-btech-mech-stat-c) | General |
| [btech/mech.status.c](#c-btech-mech-status-c) | General |
| [btech/mech.tag.c](#c-btech-mech-tag-c) | General |
| [btech/mech.tech.c](#c-btech-mech-tech-c) | General |
| [btech/mech.tech.commands.c](#c-btech-mech-tech-commands-c) | General |
| [btech/mech.tech.damages.c](#c-btech-mech-tech-damages-c) | General |
| [btech/mech.tech.do.c](#c-btech-mech-tech-do-c) | General |
| [btech/mech.tech.events.c](#c-btech-mech-tech-events-c) | General |
| [btech/mech.tech.repairs.c](#c-btech-mech-tech-repairs-c) | General |
| [btech/mech.tech.saverepair.c](#c-btech-mech-tech-saverepair-c) | General |
| [btech/mech.tic.c](#c-btech-mech-tic-c) | General |
| [btech/mech.update.c](#c-btech-mech-update-c) | General; Historical Aerospace |
| [btech/mech.utils.c](#c-btech-mech-utils-c) | General; Historical Aerospace |
| [btech/mechrep.c](#c-btech-mechrep-c) | General |
| [btech/mine.c](#c-btech-mine-c) | General |
| [btech/pcombat.c](#c-btech-pcombat-c) | General |
| [btech/template.c](#c-btech-template-c) | General; Historical Aerospace |
| [events.c](#c-events-c) | General |
| [mech.lostracer.c](#c-mech-lostracer-c) | General |
| [mt19937ar.c](#c-mt19937ar-c) | General |
| [tick.c](#c-tick-c) | General |

<a id="c-btech-aero-bomb-c"></a>

### `btech/aero.bomb.c`

[Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/aero.bomb.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/aero.bomb.c::bomb_aim` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `aim` (function) |
| `btech/aero.bomb.c::bomb_drop` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `drop` (function)<br>[systems/bombing.py](../../systems/bombing.py): `payload` (function) |
| `btech/aero.bomb.c::bomb_hit` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `hit` (function) |
| `btech/aero.bomb.c::bomb_hit_event` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `hit_event` (function) |
| `btech/aero.bomb.c::bomb_hit_hexes` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `hit` (function)<br>[systems/damage.py](../../systems/damage.py): `blast_hit_hexes / blast_hit_hexes_f / blast_hit_hexf` (function) |
| `btech/aero.bomb.c::bomb_list` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `payload` (function)<br>[systems/bombing.py](../../systems/bombing.py): `list_payload` (function) |
| `btech/aero.bomb.c::bomb_name` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `properties` (function)<br>[entities/part_catalog.py](../../entities/part_catalog.py): `BOMBS` (data/table)<br>[systems/parts.py](../../systems/parts.py): `part_name` (function) |
| `btech/aero.bomb.c::BombWeight` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `properties` (function)<br>[entities/part_catalog.py](../../entities/part_catalog.py): `BOMBS` (data/table)<br>[systems/parts.py](../../systems/parts.py): `part_weight` (function) |
| `btech/aero.bomb.c::calc_dest` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `calc_dest` (function) |
| `btech/aero.bomb.c::DestroyBomb` | Historical Aerospace; AUD-AEROSPACE; inactive/empty | [systems/bombing.py](../../systems/bombing.py): `destroy_bomb` (function) |
| `btech/aero.bomb.c::mech_bomb` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `command` (function) |
| `btech/aero.bomb.c::simulate_flight` | Historical Aerospace; AUD-AEROSPACE; active | [systems/bombing.py](../../systems/bombing.py): `simulate_flight` (function) |

<a id="c-btech-aero-move-c"></a>

### `btech/aero.move.c`

[Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/aero.move.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/aero.move.c::aero_checklz` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `checklz` (function) |
| `btech/aero.move.c::aero_climb` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `vheading` (function)<br>[tools/aerospace.py](../../tools/aerospace.py): `AerospaceSession.command climb/dive` (dispatch) |
| `btech/aero.move.c::aero_ControlEffect` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `control_effect` (function) |
| `btech/aero.move.c::aero_dive` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `vheading` (function)<br>[tools/aerospace.py](../../tools/aerospace.py): `AerospaceSession.command climb/dive` (dispatch) |
| `btech/aero.move.c::aero_land` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `land` (function)<br>[physics/heights.py](../../physics/heights.py): `land_vtol` (function) |
| `btech/aero.move.c::aero_takeoff` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `takeoff` (function) |
| `btech/aero.move.c::aero_takeoff_event` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `takeoff_event` (function)<br>[physics/aerospace.py](../../physics/aerospace.py): `continue_flying` (function) |
| `btech/aero.move.c::aero_thrust` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `thrust` (function) |
| `btech/aero.move.c::aero_update` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `update` (function) |
| `btech/aero.move.c::aero_UpdateHeading` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `update_heading` (function)<br>[physics/movement.py](../../physics/movement.py): `update_heading` (function)<br>[physics/movement.py](../../physics/movement.py): `calculate_turn_rate` (function) |
| `btech/aero.move.c::aero_UpdateSpeed` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `update_speed` (function) |
| `btech/aero.move.c::aero_vheading` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `vheading` (function) |
| `btech/aero.move.c::colorstr` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `land_warning color selection` (inline) |
| `btech/aero.move.c::DS_BlastNearbyMechsAndTrees` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `exhaust` (function) |
| `btech/aero.move.c::ds_BridgeHit` | Historical Aerospace; AUD-AEROSPACE; active | [systems/hit_locations.py](../../systems/hit_locations.py): `bridge_hit` (function)<br>[systems/occupants.py](../../systems/occupants.py): `kill_contents` (function) |
| `btech/aero.move.c::DS_LandWarning` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `land_warning` (function) |
| `btech/aero.move.c::FuelCheck` | Historical Aerospace; AUD-AEROSPACE; active | [physics/heights.py](../../physics/heights.py): `fuel_check` (function)<br>[physics/heights.py](../../physics/heights.py): `aero_free_fuel` (function) |
| `btech/aero.move.c::ImproperLZ` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `improper_lz` (function)<br>[systems/map_links.py](../../systems/map_links.py): `blocked_lz` (function) |
| `btech/aero.move.c::ImproperLZ_callback` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `improper_lz neighbor loop` (inline) |
| `btech/aero.move.c::length_hypotenuse` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `update_speed norms` (inline) |
| `btech/aero.move.c::my_sqrtm` | Historical Aerospace; AUD-AEROSPACE; active | [physics/aerospace.py](../../physics/aerospace.py): `land horizontal expression` (inline)<br>[physics/heights.py](../../physics/heights.py): `land_vtol horizontal expression` (inline) |

<a id="c-btech-artillery-c"></a>

### `btech/artillery.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/artillery.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/artillery.c::artillery_cluster_hit` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_cluster_hit` (function) |
| `btech/artillery.c::artillery_direction` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_direction` (function)<br>[systems/artillery.py](../../systems/artillery.py): `artillery_shoot` (inline) |
| `btech/artillery.c::artillery_FriendlyAdjustment` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_friendly_adjustment` (function) |
| `btech/artillery.c::artillery_hit` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_hit` (function)<br>[systems/artillery.py](../../systems/artillery.py): `artillery_hit_event` (dispatch; selector `map registered`) |
| `btech/artillery.c::artillery_hit_event` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_hit_event` (function) |
| `btech/artillery.c::artillery_hit_hex` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_hit_hex` (function) |
| `btech/artillery.c::artillery_hit_neighbors` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_hit_neighbors` (function) |
| `btech/artillery.c::artillery_hit_neighbors_callback` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_hit_neighbors` (inline) |
| `btech/artillery.c::artillery_round_flight_time` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_round_flight_time` (function)<br>[systems/artillery.py](../../systems/artillery.py): `flight_time` (function) |
| `btech/artillery.c::artillery_shoot` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_shoot` (function)<br>[systems/artillery.py](../../systems/artillery.py): `ArtilleryShot` (data/table) |
| `btech/artillery.c::artillery_type` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_type` (function) |
| `btech/artillery.c::blast_arcf` | General; AUD-SPECIAL-COMBAT; active | [systems/damage.py](../../systems/damage.py): `_blast_arc` (function) |
| `btech/artillery.c::blast_hit_hex` | General; AUD-SPECIAL-COMBAT; active | [systems/artillery.py](../../systems/artillery.py): `artillery_hit_hex` (inline)<br>[physics/hexmath.py](../../physics/hexmath.py): `hex_to_float` (function) |
| `btech/artillery.c::blast_hit_hexes` | General; AUD-SPECIAL-COMBAT; active | [systems/damage.py](../../systems/damage.py): `blast_hit_hexes` (function) |
| `btech/artillery.c::blast_hit_hexesf` | General; AUD-SPECIAL-COMBAT; active | [systems/damage.py](../../systems/damage.py): `blast_hit_hexes_f` (function) |
| `btech/artillery.c::blast_hit_hexf` | General; AUD-SPECIAL-COMBAT; active | [systems/damage.py](../../systems/damage.py): `blast_hit_hexf` (function) |

<a id="c-btech-autopilot-ai-c"></a>

### `btech/autopilot_ai.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/autopilot_ai.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/autopilot_ai.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/autopilot_ai.c::ai_adjust_move` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_adjust_move` (function) |
| `btech/autopilot_ai.c::ai_check_path` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_check_path` (function) |
| `btech/autopilot_ai.c::ai_crash` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_crash` (function) |
| `btech/autopilot_ai.c::AI_Info` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `AI_Info` (function) |
| `btech/autopilot_ai.c::ai_init` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_init` (function) |
| `btech/autopilot_ai.c::ai_max_speed` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_max_speed` (function) |
| `btech/autopilot_ai.c::ai_opponents` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_opponents` (function) |
| `btech/autopilot_ai.c::ai_path_score` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_path_score` (function) |
| `btech/autopilot_ai.c::ai_run_speed` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_run_speed` (function) |
| `btech/autopilot_ai.c::ai_set_heading` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_set_heading` (function) |
| `btech/autopilot_ai.c::ai_set_speed` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_set_speed` (function) |
| `btech/autopilot_ai.c::ai_stop` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `ai_stop` (function) |
| `btech/autopilot_ai.c::astar_compare` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `astar_compare` (function) |
| `btech/autopilot_ai.c::astar_release` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `astar_release` (function; Python node ownership / garbage collection) |
| `btech/autopilot_ai.c::astar_smooth_path` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `astar_smooth_path` (function; Source-defined no-op) |
| `btech/autopilot_ai.c::auto_astar_generate_path` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `auto_astar_generate_path` (function) |
| `btech/autopilot_ai.c::auto_create_astar_node` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `auto_create_astar_node` (function) |
| `btech/autopilot_ai.c::auto_destroy_astar_path` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `auto_destroy_astar_path` (function) |
| `btech/autopilot_ai.c::getEnemies` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `getEnemies` (function) |
| `btech/autopilot_ai.c::getFriends` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `getFriends` (function) |
| `btech/autopilot_ai.c::LOCInit` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `LOCInit` (function) |
| `btech/autopilot_ai.c::mech_snipe` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `mech_snipe` (function) |
| `btech/autopilot_ai.c::mech_snipe_func` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `mech_snipe_func` (function) |
| `btech/autopilot_ai.c::sendAIM` | General; Battlesheep; active | [systems/autopilot_ai.py](../../systems/autopilot_ai.py): `sendAIM` (function) |

<a id="c-btech-autopilot-autogun-c"></a>

### `btech/autopilot_autogun.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/autopilot_autogun.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/autopilot_autogun.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/autopilot_autogun.c::auto_calc_target_score` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_calc_target_score` (function) |
| `btech/autopilot_autogun.c::auto_calc_weapon_score` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_calc_weapon_score` (function) |
| `btech/autopilot_autogun.c::auto_create_target_node` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_create_target_node` (function) |
| `btech/autopilot_autogun.c::auto_create_weapon_node` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_create_weapon_node` (function) |
| `btech/autopilot_autogun.c::auto_destroy_target_node` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_destroy_target_node` (function; Python node ownership / garbage collection) |
| `btech/autopilot_autogun.c::auto_destroy_weaplist` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_destroy_weaplist` (function) |
| `btech/autopilot_autogun.c::auto_destroy_weapon_node` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_destroy_weapon_node` (function; Python node ownership / garbage collection) |
| `btech/autopilot_autogun.c::auto_generic_compare` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_generic_compare` (function) |
| `btech/autopilot_autogun.c::auto_gun_event` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_gun_event` (function) |
| `btech/autopilot_autogun.c::auto_sensor_event` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_sensor_event` (function) |
| `btech/autopilot_autogun.c::auto_targets_callback` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_targets_callback` (function; Tree-walk release through Python ownership) |
| `btech/autopilot_autogun.c::auto_update_profile_event` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `auto_update_profile_event` (function) |
| `btech/autopilot_autogun.c::my2string` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_autogun.c::PrefVisSens` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `PrefVisSens` (function) |
| `btech/autopilot_autogun.c::SearchLightInRange` | General; Battlesheep; active | [systems/autopilot_autogun.py](../../systems/autopilot_autogun.py): `SearchLightInRange` (function) |

<a id="c-btech-autopilot-commands-c"></a>

### `btech/autopilot_commands.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/autopilot_commands.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/autopilot_commands.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/autopilot_commands.c::auto_astar_follow_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_astar_follow_event` (function) |
| `btech/autopilot_commands.c::auto_astar_goto_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_astar_goto_event` (function) |
| `btech/autopilot_commands.c::auto_astar_roam_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_astar_roam_event` (function) |
| `btech/autopilot_commands.c::auto_cal_mapindex` | General; Battlesheep; active | [systems/map_transitions.py](../../systems/map_transitions.py): `auto_cal_mapindex` (function; Existing shared transfer implementation; re-exported) |
| `btech/autopilot_commands.c::auto_com_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_com_event` (function) |
| `btech/autopilot_commands.c::auto_command_autogun` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_autogun` (function) |
| `btech/autopilot_commands.c::auto_command_chasetarget` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_chasetarget` (function) |
| `btech/autopilot_commands.c::auto_command_dropoff` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_dropoff` (function) |
| `btech/autopilot_commands.c::auto_command_embark` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_embark` (function) |
| `btech/autopilot_commands.c::auto_command_pickup` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_pickup` (function) |
| `btech/autopilot_commands.c::auto_command_roam` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_roam` (function) |
| `btech/autopilot_commands.c::auto_command_shutdown` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_shutdown` (function) |
| `btech/autopilot_commands.c::auto_command_speed` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_speed` (function) |
| `btech/autopilot_commands.c::auto_command_startup` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_startup` (function) |
| `btech/autopilot_commands.c::auto_command_udisembark` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_command_udisembark` (function) |
| `btech/autopilot_commands.c::auto_dumbfollow_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_dumbfollow_event` (function) |
| `btech/autopilot_commands.c::auto_dumbgoto_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_dumbgoto_event` (function) |
| `btech/autopilot_commands.c::auto_enter_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_enter_event` (function) |
| `btech/autopilot_commands.c::auto_follow_event` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::auto_goto_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_goto_event` (function) |
| `btech/autopilot_commands.c::auto_leave_event` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_leave_event` (function) |
| `btech/autopilot_commands.c::auto_roam_event` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::auto_roam_generate_target_hex` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_roam_generate_target_hex` (function) |
| `btech/autopilot_commands.c::auto_set_chasetarget_mode` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `auto_set_chasetarget_mode` (function) |
| `btech/autopilot_commands.c::autopilot_attackleg` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::autopilot_cmode` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::autopilot_enterbase` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::autopilot_load_cargo` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::autopilot_swarm` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::figure_out_range_and_bearing` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `figure_out_range_and_bearing` (function) |
| `btech/autopilot_commands.c::gradually_load` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_commands.c::slow_down_if_neccessary` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `slow_down_if_neccessary` (function) |
| `btech/autopilot_commands.c::speed_up_if_neccessary` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `speed_up_if_neccessary` (function) |
| `btech/autopilot_commands.c::update_wanted_heading` | General; Battlesheep; active | [systems/autopilot_commands.py](../../systems/autopilot_commands.py): `update_wanted_heading` (function) |

<a id="c-btech-autopilot-core-c"></a>

### `btech/autopilot_core.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/autopilot_core.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/autopilot_core.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/autopilot_core.c::auto_addcommand` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_addcommand` (function) |
| `btech/autopilot_core.c::auto_create_command_node` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_create_command_node` (function) |
| `btech/autopilot_core.c::auto_delcommand` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_delcommand` (function) |
| `btech/autopilot_core.c::auto_destroy_command_node` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_destroy_command_node` (function) |
| `btech/autopilot_core.c::auto_disengage` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_disengage` (function) |
| `btech/autopilot_core.c::auto_engage` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_engage` (function) |
| `btech/autopilot_core.c::auto_eventstats` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_eventstats` (function) |
| `btech/autopilot_core.c::auto_get_command_arg` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_get_command_arg` (function) |
| `btech/autopilot_core.c::auto_get_command_enum` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_get_command_enum` (function) |
| `btech/autopilot_core.c::auto_goto_next_command` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_goto_next_command` (function) |
| `btech/autopilot_core.c::auto_heartbeat` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_heartbeat` (function; Delegates to integrated engine heartbeat) |
| `btech/autopilot_core.c::auto_init` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_init` (function) |
| `btech/autopilot_core.c::auto_jump` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_jump` (function; Source-disabled command notice) |
| `btech/autopilot_core.c::auto_listcommands` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_listcommands` (function) |
| `btech/autopilot_core.c::auto_load_commands` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_load_commands` (function) |
| `btech/autopilot_core.c::auto_newautopilot` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_newautopilot` (function) |
| `btech/autopilot_core.c::auto_pilot_on` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_pilot_on` (function) |
| `btech/autopilot_core.c::auto_read_command_node` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_read_command_node` (function) |
| `btech/autopilot_core.c::auto_save_commands` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_save_commands` (function) |
| `btech/autopilot_core.c::auto_set_comtitle` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_set_comtitle` (function) |
| `btech/autopilot_core.c::auto_show_command` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_show_command` (function) |
| `btech/autopilot_core.c::auto_stop_pilot` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_stop_pilot` (function) |
| `btech/autopilot_core.c::auto_valid_progline` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_valid_progline` (function; Source-disabled validator returns zero) |
| `btech/autopilot_core.c::auto_write_command_node` | General; Battlesheep; active | [systems/autopilot_core.py](../../systems/autopilot_core.py): `auto_write_command_node` (function) |

<a id="c-btech-autopilot-radio-c"></a>

### `btech/autopilot_radio.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/autopilot_radio.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/autopilot_radio.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/autopilot_radio.c::ACMD` | General; Battlesheep; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/autopilot_radio.c::auto_attackleg` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_cmode` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_drally` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_enterbay` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_freq` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_nogun` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_notarget` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_parse_command` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_parse_command` (function) |
| `btech/autopilot_radio.c::auto_radio_command_autogun` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_autogun` (function) |
| `btech/autopilot_radio.c::auto_radio_command_chasetarg` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_chasetarg` (function) |
| `btech/autopilot_radio.c::auto_radio_command_dfollow` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_dfollow` (function) |
| `btech/autopilot_radio.c::auto_radio_command_dgoto` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_dgoto` (function) |
| `btech/autopilot_radio.c::auto_radio_command_dropoff` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_dropoff` (function) |
| `btech/autopilot_radio.c::auto_radio_command_embark` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_embark` (function) |
| `btech/autopilot_radio.c::auto_radio_command_enterbase` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_enterbase` (function) |
| `btech/autopilot_radio.c::auto_radio_command_follow` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_follow` (function) |
| `btech/autopilot_radio.c::auto_radio_command_goto` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_goto` (function) |
| `btech/autopilot_radio.c::auto_radio_command_heading` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_heading` (function) |
| `btech/autopilot_radio.c::auto_radio_command_help` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_help` (function) |
| `btech/autopilot_radio.c::auto_radio_command_hide` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_hide` (function) |
| `btech/autopilot_radio.c::auto_radio_command_jumpjet` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_jumpjet` (function) |
| `btech/autopilot_radio.c::auto_radio_command_leavebase` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_leavebase` (function) |
| `btech/autopilot_radio.c::auto_radio_command_ogoto` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_ogoto` (function) |
| `btech/autopilot_radio.c::auto_radio_command_pickup` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_pickup` (function) |
| `btech/autopilot_radio.c::auto_radio_command_position` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_position` (function) |
| `btech/autopilot_radio.c::auto_radio_command_prone` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_prone` (function) |
| `btech/autopilot_radio.c::auto_radio_command_report` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_report` (function) |
| `btech/autopilot_radio.c::auto_radio_command_reset` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_reset` (function) |
| `btech/autopilot_radio.c::auto_radio_command_sensor` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_sensor` (function) |
| `btech/autopilot_radio.c::auto_radio_command_shutdown` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_shutdown` (function) |
| `btech/autopilot_radio.c::auto_radio_command_speed` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_speed` (function) |
| `btech/autopilot_radio.c::auto_radio_command_stand` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_stand` (function) |
| `btech/autopilot_radio.c::auto_radio_command_startup` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_startup` (function) |
| `btech/autopilot_radio.c::auto_radio_command_stop` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_stop` (function) |
| `btech/autopilot_radio.c::auto_radio_command_sweight` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_sweight` (function) |
| `btech/autopilot_radio.c::auto_radio_command_target` | General; Battlesheep; active | [systems/autopilot_radio.py](../../systems/autopilot_radio.py): `auto_radio_command_target` (function) |
| `btech/autopilot_radio.c::auto_rally` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_reply` | General; Battlesheep; active | [systems/communications.py](../../systems/communications.py): `auto_reply` (function; Existing real delayed-radio scheduling; re-exported) |
| `btech/autopilot_radio.c::auto_reply_event` | General; Battlesheep; active | [systems/communications.py](../../systems/communications.py): `auto_reply_event` (function; Existing real radio callback; re-exported) |
| `btech/autopilot_radio.c::auto_roammode` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_setchanfreq` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_setchanmode` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_swarm` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_swarmcharge` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/autopilot_radio.c::auto_swarmmode` | General; Battlesheep; inactive/empty | Inactive/empty source entry; no active gameplay target. |

<a id="c-btech-bsuit-c"></a>

### `btech/bsuit.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/bsuit.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/bsuit.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/bsuit.c::bsuit_attackleg` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `attackleg` (function) |
| `btech/bsuit.c::bsuit_hide` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `hide` (function) |
| `btech/bsuit.c::bsuit_swarm` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `swarm` (function) |
| `btech/bsuit.c::BSuitMirrorSwarmedTarget` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `mirror_all` (function) |
| `btech/bsuit.c::CountBSuitMembers` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `members` (function) |
| `btech/bsuit.c::CountSwarmers` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `count_swarmers` (function) |
| `btech/bsuit.c::doBSuitCommonChecks` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `common_checks` (function) |
| `btech/bsuit.c::doJettisonChecks` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `jettison_checks` (function) |
| `btech/bsuit.c::FindBSuitTarget` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `find_target` (function) |
| `btech/bsuit.c::findSwarmers` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `first_swarmer` (function) |
| `btech/bsuit.c::GetBSuitName` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `suit_name` (function) |
| `btech/bsuit.c::GetLCaseBSuitName` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `suit_name` (function) |
| `btech/bsuit.c::IsMechMounted` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `is_mounted` (function) |
| `btech/bsuit.c::IsMechSwarmed` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `is_swarmed` (function) |
| `btech/bsuit.c::JettisonPacks` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `jettison` (function) |
| `btech/bsuit.c::mech_hide_event` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `hide_event` (function) |
| `btech/bsuit.c::StartBSuitRecycle` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `start_recycle` (function) |
| `btech/bsuit.c::StopBSuitSwarmers` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `detach_all` (function) |
| `btech/bsuit.c::StopBSuitSwarmers` | Historical Aerospace; AUD-AEROSPACE; active | [systems/swarm.py](../../systems/swarm.py): `swarmers` (function)<br>[systems/swarm.py](../../systems/swarm.py): `detach_all` (function) |
| `btech/bsuit.c::StopSwarming` | General; AUD-PILOTS; active | [systems/swarm.py](../../systems/swarm.py): `detach` (function) |
| `btech/bsuit.c::StopSwarming` | Historical Aerospace; AUD-AEROSPACE; active | [systems/swarm.py](../../systems/swarm.py): `detach` (function) |

<a id="c-btech-btechstats-c"></a>

### `btech/btechstats.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/btechstats.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/btechstats.c::AccumulateArtyXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `artillery` (function) |
| `btech/btechstats.c::AccumulateCommXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `comm` (function) |
| `btech/btechstats.c::AccumulateComputerXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `computer` (function) |
| `btech/btechstats.c::AccumulateGunXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `gun` (function; selector `cfg.oldxpsystem=False; True dispatches old`)<br>[systems/experience.py](../../systems/experience.py): `gun_amount` (function; selector `cfg.oldxpsystem=False; True dispatches old`)<br>[systems/experience.py](../../systems/experience.py): `award` (function; selector `cfg.oldxpsystem=False; True dispatches old`) |
| `btech/btechstats.c::AccumulateGunXPold` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `gun` (function; selector `cfg.oldxpsystem=True`)<br>[systems/experience.py](../../systems/experience.py): `gun_amount` (function; selector `cfg.oldxpsystem=True`)<br>[systems/experience.py](../../systems/experience.py): `old_probability` (function; selector `cfg.oldxpsystem=True`) |
| `btech/btechstats.c::AccumulatePilXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `piloting` (function) |
| `btech/btechstats.c::AccumulateSpotXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `spot` (function) |
| `btech/btechstats.c::AccumulateTechWeaponsXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `tech` (function; selector `weapons=True`)<br>[systems/experience.py](../../systems/experience.py): `award` (function; selector `weapons=True`) |
| `btech/btechstats.c::AccumulateTechXP` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `tech` (function; selector `weapons=False`) |
| `btech/btechstats.c::btthreshold_func` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `get_threshold` (function) |
| `btech/btechstats.c::char_gainxp` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `gain_xp` (function) |
| `btech/btechstats.c::char_gainxpbycode` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `gain_xp` (function) |
| `btech/btechstats.c::char_getattrsave` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `attribute_target` (function) |
| `btech/btechstats.c::char_getattrsavesucc` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `attribute_success` (function) |
| `btech/btechstats.c::char_getopposedskill` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `opposed` (function) |
| `btech/btechstats.c::char_getskillmargsucc` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `skill_margin` (function) |
| `btech/btechstats.c::char_getskillsuccess` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `skill_success` (function) |
| `btech/btechstats.c::char_getskilltarget` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `skill_target` (function) |
| `btech/btechstats.c::char_getskilltargetbycode` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `skill_target` (function) |
| `btech/btechstats.c::char_getskilltargetbycode_base` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `target_base` (function) |
| `btech/btechstats.c::char_getskilltargetbycode_noxp` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `skill_target` (function) |
| `btech/btechstats.c::char_getstatvalue` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `Stats.get` (method) |
| `btech/btechstats.c::char_getvalue` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `value` (function) |
| `btech/btechstats.c::char_getvaluecode` | General; AUD-PILOTS; active | [data/character_values.py](../../data/character_values.py): `code` (function) |
| `btech/btechstats.c::char_getxpbycode` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `control` (function; selector `control kind=get, skill, flag=2; absolute-XP set delta`) |
| `btech/btechstats.c::char_lookupplayer` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.lookup` (method) |
| `btech/btechstats.c::char_rolld6` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `roll_dice` (function; selector `kind=d6; count=num`) |
| `btech/btechstats.c::char_rollsaving` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `roll_dice` (function; selector `kind=saving`) |
| `btech/btechstats.c::char_rollskilled` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `roll_dice` (function; selector `kind=skilled`) |
| `btech/btechstats.c::char_rollunskilled` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `roll_dice` (function; selector `kind=unskilled`) |
| `btech/btechstats.c::char_setstatvalue` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `Stats.set` (method) |
| `btech/btechstats.c::char_setvalue` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `set_value` (function) |
| `btech/btechstats.c::char_xp_bonus` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `Stats.get` (method) |
| `btech/btechstats.c::clear_player` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `Stats.clear` (method) |
| `btech/btechstats.c::create_new_stats` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `Stats.fresh` (method) |
| `btech/btechstats.c::debug_setxplevel` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `threshold_control` (function) |
| `btech/btechstats.c::debug_xptop` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `xp_top` (function) |
| `btech/btechstats.c::do_charclear` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `control [clear]` (dispatch; selector `clear`)<br>[data/characters.py](../../data/characters.py): `CharacterStore.clear_record` (method) |
| `btech/btechstats.c::do_charstatus` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `control [status]` (dispatch; selector `status`) |
| `btech/btechstats.c::figure_xp_bonus` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `scaled_threshold` (function)<br>[systems/characters.py](../../systems/characters.py): `pack_xp` (function) |
| `btech/btechstats.c::figure_xp_to_next_level` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `next_threshold` (function) |
| `btech/btechstats.c::fix_pilotdamage` | General; AUD-PILOTS; active | [systems/piloting.py](../../systems/piloting.py): `fix_pilotdamage` (function) |
| `btech/btechstats.c::fun_btcharlist` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `char_list` (function) |
| `btech/btechstats.c::fun_btgetcharvalue` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `control [get]` (dispatch; selector `get`) |
| `btech/btechstats.c::fun_btsetcharvalue` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `control [set]` (dispatch; selector `set`) |
| `btech/btechstats.c::generic_retrieve_stuff` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `generic_retrieve` (function) |
| `btech/btechstats.c::generic_store_stuff` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `generic_store` (function) |
| `btech/btechstats.c::getPilotBVMod` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `pilot_bv` (function)<br>[systems/experience.py](../../systems/experience.py): `pilot_bv_factor` (function) |
| `btech/btechstats.c::handlemwconc` | General; AUD-PILOTS; active | [systems/piloting.py](../../systems/piloting.py): `handle_mw_conc` (function) |
| `btech/btechstats.c::HasBoolAdvantage` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `has_advantage` (function) |
| `btech/btechstats.c::headhitmwdamage` | General; AUD-PILOTS; active | [systems/piloting.py](../../systems/piloting.py): `head_hit_mw_damage` (function)<br>[systems/piloting.py](../../systems/piloting.py): `_character_injury` (function) |
| `btech/btechstats.c::init_btechstats` | General; AUD-PILOTS; active | [data/character_values.py](../../data/character_values.py): `VALUES / FULL_NAMES / SHORT_NAMES` (data/table)<br>[data/characters.py](../../data/characters.py): `CharacterStore.__init__` (method) |
| `btech/btechstats.c::initialize_pc` | General; AUD-PILOTS; active | [systems/personal_damage.py](../../systems/personal_damage.py): `initialize_pc` (function) |
| `btech/btechstats.c::list_charvaluestuff` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `list_values` (function) |
| `btech/btechstats.c::loc_mod` | General; AUD-PILOTS; active | [systems/personal_damage.py](../../systems/personal_damage.py): `initialize_pc [location proportions]` (dispatch; selector `location proportions`) |
| `btech/btechstats.c::lower_xp` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `lower_xp` (function) |
| `btech/btechstats.c::MadePerceptionRoll` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `perception` (function) |
| `btech/btechstats.c::mw_ic_bth` | General; AUD-PILOTS; active | [systems/piloting.py](../../systems/piloting.py): `mw_ic_bth` (function) |
| `btech/btechstats.c::mwlethaldam` | General; AUD-PILOTS; active | [systems/piloting.py](../../systems/piloting.py): `mw_lethal_damage` (function)<br>[systems/piloting.py](../../systems/piloting.py): `_character_injury` (function) |
| `btech/btechstats.c::retrieve_advs` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.retrieve [ADVS]` (dispatch; selector `ADVS`) |
| `btech/btechstats.c::retrieve_attrs` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.retrieve [ATTRS]` (dispatch; selector `ATTRS`) |
| `btech/btechstats.c::retrieve_health` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.retrieve [HEALTH]` (dispatch; selector `HEALTH`) |
| `btech/btechstats.c::retrieve_skills` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.retrieve [SKILLS]` (dispatch; selector `SKILLS`) |
| `btech/btechstats.c::retrieve_stats` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.retrieve` (method) |
| `btech/btechstats.c::show_charstatus` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `status` (function) |
| `btech/btechstats.c::silly_get_uptime_to_string` | General; AUD-PILOTS; active | [systems/characters.py](../../systems/characters.py): `duration` (function) |
| `btech/btechstats.c::store_advs` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.store [ADVS]` (dispatch; selector `ADVS`) |
| `btech/btechstats.c::store_attrs` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.store [ATTRS]` (dispatch; selector `ATTRS`) |
| `btech/btechstats.c::store_health` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.store [HEALTH]` (dispatch; selector `HEALTH`) |
| `btech/btechstats.c::store_skills` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.store [SKILLS]` (dispatch; selector `SKILLS`) |
| `btech/btechstats.c::store_stats` | General; AUD-PILOTS; active | [data/characters.py](../../data/characters.py): `CharacterStore.store` (method) |
| `btech/btechstats.c::t_mod` | General; AUD-PILOTS; active | [systems/experience.py](../../systems/experience.py): `movement_value` (function) |

<a id="c-btech-btspath-c"></a>

### `btech/btspath.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/btspath.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/btspath.c::HoverTankTileCost` | General; AUD-MOVEMENT; active | [physics/path_costs.py](../../physics/path_costs.py): `hover_tank_tile_cost` (function)<br>[physics/path_costs.py](../../physics/path_costs.py): `_tile_cost` (function)<br>[physics/path_costs.py](../../physics/path_costs.py): `_destination_cost` (function) |
| `btech/btspath.c::MechTileCost` | General; AUD-MOVEMENT; active | [physics/path_costs.py](../../physics/path_costs.py): `mech_tile_cost` (function)<br>[physics/path_costs.py](../../physics/path_costs.py): `_tile_cost` (function)<br>[physics/path_costs.py](../../physics/path_costs.py): `_destination_cost` (function) |
| `btech/btspath.c::TrackedTankTileCost` | General; AUD-MOVEMENT; active | [physics/path_costs.py](../../physics/path_costs.py): `tracked_tank_tile_cost` (function)<br>[physics/path_costs.py](../../physics/path_costs.py): `_tile_cost` (function)<br>[physics/path_costs.py](../../physics/path_costs.py): `_destination_cost` (function) |

<a id="c-btech-crit-c"></a>

### `btech/crit.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/crit.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/crit.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/crit.c::correct_speed` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `correct_speed` (function) |
| `btech/crit.c::DestroyMainWeapon` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `destroy_main_weapon` (function) |
| `btech/crit.c::DoAmmunitionCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_ammo_explosion` (function) |
| `btech/crit.c::DoCargoInfantryCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_cargo_hit` (function) |
| `btech/crit.c::DoTurretBlownOffCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_turret_blown_off` (function) |
| `btech/crit.c::DoTurretJamCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_turret_jam` (function) |
| `btech/crit.c::DoTurretLockCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_turret_lock` (function) |
| `btech/crit.c::DoVehicleCommanderHit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_commander_hit` (function) |
| `btech/crit.c::DoVehicleCrewKilledCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_crew_killed` (function) |
| `btech/crit.c::DoVehicleCrewStunnedCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_crew_stunned` (function) |
| `btech/crit.c::DoVehicleDriverCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_driver_hit` (function) |
| `btech/crit.c::DoVehicleEngineHit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_engine_hit` (function) |
| `btech/crit.c::DoVehicleFuelTankCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_fuel_tank_hit` (function) |
| `btech/crit.c::DoVehicleSensorCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_sensor_hit` (function) |
| `btech/crit.c::DoVehicleStablizerCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_stabilizer_destroyed` (function) |
| `btech/crit.c::DoVTOLCoPilotCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_copilot_hit` (function) |
| `btech/crit.c::DoVTOLPilotHit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_pilot_hit` (function) |
| `btech/crit.c::DoVTOLRotorDamagedCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_rotor_damaged` (function) |
| `btech/crit.c::DoVTOLRotorDestroyedCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_rotor_destroyed` (function) |
| `btech/crit.c::DoVTOLTailRotorDamagedCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_tail_rotor_damaged` (function) |
| `btech/crit.c::DoWeaponDestroyedCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_weapon_destroyed` (function) |
| `btech/crit.c::DoWeaponJamCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `handle_weapon_jam` (function) |
| `btech/crit.c::explode_unit` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `explode_unit` (function) |
| `btech/crit.c::HandleAdvFasaVehicleCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `resolve_vehicle_critical` (function) |
| `btech/crit.c::HandleCritical` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `check_and_apply_criticals` (function) |
| `btech/crit.c::HandleCritical` | Historical Aerospace; AUD-AEROSPACE; active | [systems/criticals.py](../../systems/criticals.py): `check_and_apply_criticals` (function) |
| `btech/crit.c::HandleFasaVehicleCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `legacy_vehicle_critical` (function) |
| `btech/crit.c::HandleMechCrit` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `apply_critical_to_slot` (function) |
| `btech/crit.c::HandleMechCrit` | Historical Aerospace; AUD-AEROSPACE; active | [systems/criticals.py](../../systems/criticals.py): `apply_critical_to_slot` (function)<br>[systems/criticals.py](../../systems/criticals.py): `handle_critical_hit Aerospace component dispatch` (dispatch)<br>[systems/criticals.py](../../systems/criticals.py): `handle_heat_sink_critical / handle_targeting_computer_critical` (function)<br>[systems/criticals.py](../../systems/criticals.py): `apply_ammo_critical` (function) |
| `btech/crit.c::HandleVehicleCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `legacy_vehicle_critical` (function) |
| `btech/crit.c::HandleVTOLCrit` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `legacy_vehicle_critical` (function) |
| `btech/crit.c::handleWeaponCrit` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `apply_weapon_critical` (function) |
| `btech/crit.c::handleWeaponCrit` | Historical Aerospace; AUD-AEROSPACE; active | [systems/criticals.py](../../systems/criticals.py): `apply_weapon_critical` (function)<br>[systems/criticals.py](../../systems/criticals.py): `apply_internal_damage_with_transfer` (function) |
| `btech/crit.c::JamMainWeapon` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `jam_main_weapon` (function) |
| `btech/crit.c::limitSpeedToCruise` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `limit_speed_to_cruise` (function) |
| `btech/crit.c::NormalizeAllActuatorCrits` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `recalculate_mech_stats` (function) |
| `btech/crit.c::NormalizeArmActuatorCrits` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `normalize_arm_actuator` (function) |
| `btech/crit.c::NormalizeLegActuatorCrits` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `normalize_leg_actuator` (function) |
| `btech/crit.c::NormalizeLocActuatorCrits` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `normalize_location_actuators` (function) |
| `btech/crit.c::pickRandomWeapon` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `pick_random_weapon` (function) |
| `btech/crit.c::StartVTOLCrash` | General; AUD-DAMAGE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `start_vtol_crash` (function) |

<a id="c-btech-ds-bay-c"></a>

### `btech/ds.bay.c`

[Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/ds.bay.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/ds.bay.c::DS_Bay_Is_EnterOK` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `bay_available` (function) |
| `btech/ds.bay.c::DS_Bay_Is_Open` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `bay_open` (function) |
| `btech/ds.bay.c::DS_Place` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `place` (function) |
| `btech/ds.bay.c::Find_DS_Bay_Dir` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `bay_direction` (function) |
| `btech/ds.bay.c::Find_DS_Bay_In_MechHex` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `bearing_mod / adjacent_bay` (function)<br>[physics/aerospace.py](../../physics/aerospace.py): `adjacent` (function) |
| `btech/ds.bay.c::Find_DS_Bay_Number` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `DOOR_LOCATIONS` (data/table)<br>[systems/dropships.py](../../systems/dropships.py): `bay_number` (function) |
| `btech/ds.bay.c::Find_Single_DS_In_MechHex` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `matching_ships` (function) |
| `btech/ds.bay.c::Leave_DS` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `leave_bay guards` (inline)<br>[systems/dropships.py](../../systems/dropships.py): `leave_bay` (function) |
| `btech/ds.bay.c::Leave_DS_Bay` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `leave_bay transfer body` (inline) |
| `btech/ds.bay.c::mech_createbays` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `create_bays` (function) |
| `btech/ds.bay.c::mech_enterbay` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `enter_bay` (function) |
| `btech/ds.bay.c::mech_enterbay_event` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `enter_event` (function)<br>[systems/dropships.py](../../systems/dropships.py): `set_xy` (function)<br>[systems/map_transitions.py](../../systems/map_transitions.py): `transfer` (function) |

<a id="c-btech-ds-turret-c"></a>

### `btech/ds.turret.c`

[Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/ds.turret.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/ds.turret.c::newturret` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `allocate` (function) |
| `btech/ds.turret.c::turret_addtic` | Historical Aerospace; AUD-AEROSPACE; inactive/empty | [systems/turrets.py](../../systems/turrets.py): `command inactive TIC dispatch` (dispatch) |
| `btech/ds.turret.c::turret_bearing` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/observation.py](../../systems/observation.py): `navigation` (function) |
| `btech/ds.turret.c::turret_cleartic` | Historical Aerospace; AUD-AEROSPACE; inactive/empty | [systems/turrets.py](../../systems/turrets.py): `command inactive TIC dispatch` (dispatch) |
| `btech/ds.turret.c::turret_contacts` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/observation.py](../../systems/observation.py): `contacts` (function) |
| `btech/ds.turret.c::turret_critstatus` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/status_display.py](../../systems/status_display.py): `own_readout/critical_display` (function) |
| `btech/ds.turret.c::turret_deinitialize` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `deinitialize` (function)<br>[systems/turrets.py](../../systems/turrets.py): `room_notice` (function) |
| `btech/ds.turret.c::turret_deltic` | Historical Aerospace; AUD-AEROSPACE; inactive/empty | [systems/turrets.py](../../systems/turrets.py): `command inactive TIC dispatch` (dispatch) |
| `btech/ds.turret.c::turret_eta` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `eta` (function) |
| `btech/ds.turret.c::turret_findcenter` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/turrets.py](../../systems/turrets.py): `delegate` (dispatch; selector `findcenter`) |
| `btech/ds.turret.c::turret_firetic` | Historical Aerospace; AUD-AEROSPACE; inactive/empty | [systems/turrets.py](../../systems/turrets.py): `command inactive TIC dispatch` (dispatch) |
| `btech/ds.turret.c::turret_fireweapon` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `fire_number/mount_guard` (function)<br>[systems/combat.py](../../systems/combat.py): `fire_weapon_number` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `firing_feedback` (function) |
| `btech/ds.turret.c::turret_initialize` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `initialize` (function)<br>[systems/turrets.py](../../systems/turrets.py): `room_notice` (function) |
| `btech/ds.turret.c::turret_listtic` | Historical Aerospace; AUD-AEROSPACE; inactive/empty | [systems/turrets.py](../../systems/turrets.py): `command inactive TIC dispatch` (dispatch) |
| `btech/ds.turret.c::turret_lrsmap` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/map_display.py](../../systems/map_display.py): `lrs` (function)<br>[systems/observation.py](../../systems/observation.py): `map_readout` (function) |
| `btech/ds.turret.c::turret_navigate` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/map_display.py](../../systems/map_display.py): `tactical(navigate=True)` (dispatch/use)<br>[systems/observation.py](../../systems/observation.py): `map_readout` (function) |
| `btech/ds.turret.c::turret_range` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/observation.py](../../systems/observation.py): `navigation` (function) |
| `btech/ds.turret.c::turret_report` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/observation.py](../../systems/observation.py): `scan(report=True)` (dispatch/use) |
| `btech/ds.turret.c::turret_scan` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/observation.py](../../systems/observation.py): `scan` (function) |
| `btech/ds.turret.c::turret_settarget` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/targeting.py](../../systems/targeting.py): `set_target/set_target_hex/clear_target/lock_command` (function) |
| `btech/ds.turret.c::turret_sight` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `fire_number/mount_guard` (function)<br>[systems/combat.py](../../systems/combat.py): `fire_weapon_number` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `firing_feedback` (function) |
| `btech/ds.turret.c::turret_status` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/status_display.py](../../systems/status_display.py): `status` (function) |
| `btech/ds.turret.c::turret_tacmap` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/map_display.py](../../systems/map_display.py): `tactical` (function)<br>[systems/observation.py](../../systems/observation.py): `map_readout` (function) |
| `btech/ds.turret.c::turret_weaponspecs` | Historical Aerospace; AUD-AEROSPACE; active | [systems/turrets.py](../../systems/turrets.py): `command/delegate` (function)<br>[systems/status_display.py](../../systems/status_display.py): `own_readout` (dispatch; selector `kind=weaponspecs`) |

<a id="c-btech-econ-c"></a>

### `btech/econ.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/econ.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/econ.c::add_entry` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.add` (method)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.change` (inline) |
| `btech/econ.c::econ_change_items` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.change` (method) |
| `btech/econ.c::econ_find_items` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.find` (method) |
| `btech/econ.c::econ_set_items` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.set` (method) |
| `btech/econ.c::find_entry` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.entry` (method) |
| `btech/econ.c::remove_entry` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.remove` (method)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.change` (inline) |

<a id="c-btech-econ-cmds-c"></a>

### `btech/econ_cmds.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/econ_cmds.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/econ_cmds.c::list_matching` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.listing` (method) |
| `btech/econ_cmds.c::loading_bay_whine` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.loading_bay` (method) |
| `btech/econ_cmds.c::mech_loadcargo` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[loadcargo]`) |
| `btech/econ_cmds.c::mech_manifest` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[manifest]`) |
| `btech/econ_cmds.c::mech_Raddstuff` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[Raddstuff]`) |
| `btech/econ_cmds.c::mech_Rfixstuff` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[Rfixstuff]`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.cleanup` (method) |
| `btech/econ_cmds.c::mech_Rremovestuff` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[Rremovestuff]`) |
| `btech/econ_cmds.c::mech_Rresetstuff` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[Rresetstuff]`) |
| `btech/econ_cmds.c::mech_stores` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[stores]`) |
| `btech/econ_cmds.c::mech_unloadcargo` | General; PILOT-REPAIR; active | [systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (dispatch; selector `[unloadcargo]`) |
| `btech/econ_cmds.c::SetCargoWeight` | General; PILOT-REPAIR; active | [systems/parts.py](../../systems/parts.py): `set_cargo_weight` (function) |
| `btech/econ_cmds.c::stuff_change_sub` | General; PILOT-REPAIR; active | [systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.transfer` (method)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.matching` (method)<br>[systems/cargo_commands.py](../../systems/cargo_commands.py): `CargoCommands.command` (inline) |

<a id="c-btech-eject-c"></a>

### `btech/eject.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/eject.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/eject.c::autoeject` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `autoeject` (function) |
| `btech/eject.c::char_disembark` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `create_mw` (function)<br>[systems/occupants.py](../../systems/occupants.py): `disembark` (function) |
| `btech/eject.c::char_eject` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `create_mw` (function)<br>[systems/occupants.py](../../systems/occupants.py): `eject` (function) |
| `btech/eject.c::discard_mw` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `discard_mw` (function) |
| `btech/eject.c::enter_mw_bay` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `enter_mw_bay` (function) |
| `btech/eject.c::mech_discard_event` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `discard_event` (function) |
| `btech/eject.c::mech_disembark` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `disembark` (function) |
| `btech/eject.c::mech_eject` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `eject` (function) |
| `btech/eject.c::mech_embark` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `embark` (function) |
| `btech/eject.c::mech_udisembark` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `unit_disembark` (function) |
| `btech/eject.c::pickup_mw` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `pickup` (function) |
| `btech/eject.c::tele_contents` | General; AUD-PILOTS; active | [systems/occupants.py](../../systems/occupants.py): `tele_contents` (function) |

<a id="c-btech-failures-c"></a>

### `btech/failures.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/failures.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/failures.c::CheckGenericFail` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `check_generic_fail` (function) |
| `btech/failures.c::CheckWeaponFailed` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `check_weapon_failed` (function) |
| `btech/failures.c::FailureComputerScanner` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureComputerShutdown` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureComputerTarget` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureRadioRange` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureRadioShort` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureRadioStatic` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureWeaponDamage` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureWeaponDud` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureWeaponHeat` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureWeaponJammed` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureWeaponMissiles` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::FailureWeaponRange` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `percentage_failure` (function) |
| `btech/failures.c::FailureWeaponSpike` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `apply_failure` (function) |
| `btech/failures.c::GetBrandIndex` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `get_brand_index` (function) |
| `btech/failures.c::GetPartBrandName` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `get_part_brand_name` (function) |
| `btech/failures.c::mech_rrec_event` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `radio_recovery` (function) |
| `btech/failures.c::mech_srec_event` | General; AUD-DAMAGE; active | [systems/failures.py](../../systems/failures.py): `scanner_recovery` (function) |

<a id="c-btech-hudinfo-c"></a>

### `btech/hudinfo.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/hudinfo.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/hudinfo.c::building_status` | General; AUD-HUD; active | [systems/display_contacts.py](../../systems/display_contacts.py): `building_contacts(hud_status)` (dispatch/use) |
| `btech/hudinfo.c::do_hudinfo` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request` (dispatch; selector `protocol parse/guards`) |
| `btech/hudinfo.c::fake_hudinfo` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request` (dispatch; selector `macro=True`) |
| `btech/hudinfo.c::FindRangeAndBearingToCenter` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `center` (function) |
| `btech/hudinfo.c::get_weaponmodes` | General; AUD-HUD; active | [systems/equipment_display.py](../../systems/equipment_display.py): `allowed_modes` (function) |
| `btech/hudinfo.c::getMech_forPlayer` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `player_unit` (function) |
| `btech/hudinfo.c::hud_advtech` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `advtech` (function) |
| `btech/hudinfo.c::hud_ammostatus` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(am)` (dispatch/use) |
| `btech/hudinfo.c::hud_arcstring` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `arcs` (function) |
| `btech/hudinfo.c::hud_armorscan` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(asc)` (dispatch/use) |
| `btech/hudinfo.c::hud_armorstatus` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(as)` (dispatch/use) |
| `btech/hudinfo.c::hud_building_contacts` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(cb)` (dispatch/use) |
| `btech/hudinfo.c::hud_conditions` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(con/co)` (dispatch/use) |
| `btech/hudinfo.c::hud_contacts` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(c)` (dispatch/use) |
| `btech/hudinfo.c::hud_damagechar` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(asc damage fields)` (dispatch/use) |
| `btech/hudinfo.c::hud_generalstatus` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `general` (function) |
| `btech/hudinfo.c::hud_getammomode` | General; AUD-HUD; active | [systems/equipment_display.py](../../systems/equipment_display.py): `AMMO_FLAGS` (data/table)<br>[systems/equipment_display.py](../../systems/equipment_display.py): `ammo_modes` (function) |
| `btech/hudinfo.c::hud_getfiremode` | General; AUD-HUD; active | [systems/equipment_display.py](../../systems/equipment_display.py): `FIRE_FLAGS` (data/table)<br>[systems/equipment_display.py](../../systems/equipment_display.py): `fire_modes` (function) |
| `btech/hudinfo.c::hud_getmapflags` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(con/co flags)` (dispatch/use) |
| `btech/hudinfo.c::hud_getweaponstatus` | General; AUD-HUD; active | [systems/equipment_display.py](../../systems/equipment_display.py): `weapon_status` (function) |
| `btech/hudinfo.c::hud_getweapscanstatus` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(wsc status)` (dispatch/use) |
| `btech/hudinfo.c::hud_limbstatus` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(li)` (dispatch/use) |
| `btech/hudinfo.c::hud_scantarget` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.scan_target` (method) |
| `btech/hudinfo.c::hud_sensorstring` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(c sensor column)` (dispatch/use) |
| `btech/hudinfo.c::hud_tactical` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `hud_tactical` (function) |
| `btech/hudinfo.c::hud_templatearmor` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(oas)` (dispatch/use) |
| `btech/hudinfo.c::hud_templateinfo` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `template_info` (function) |
| `btech/hudinfo.c::hud_typechar` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `type_char` (function) |
| `btech/hudinfo.c::hud_weaponlist` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request` (dispatch; selector `cmd=wl`)<br>[systems/equipment_display.py](../../systems/equipment_display.py): `catalog_rows` (function) |
| `btech/hudinfo.c::hud_weapons` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request` (dispatch; selector `cmd=we`)<br>[systems/weapon_inventory.py](../../systems/weapon_inventory.py): `find_weapons / weapon_runs` (function) |
| `btech/hudinfo.c::hud_weapscan` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `HudSession.request(wsc)` (dispatch/use) |
| `btech/hudinfo.c::init_hudinfo` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `COMMANDS / ACTIVE` (data/table)<br>[systems/hud.py](../../systems/hud.py): `HudSession.request` (dispatch; selector `command membership and flag gates`) |
| `btech/hudinfo.c::MaxSettableSpeed` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `template_info(maximum)` (dispatch/use) |
| `btech/hudinfo.c::MaxVerticalSpeed` | General; AUD-HUD; active | [systems/hud.py](../../systems/hud.py): `template_info(vertical)` (dispatch/use) |

<a id="c-btech-map-bits-c"></a>

### `btech/map.bits.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.bits.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.bits.c::bit_size` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.size` (method) |
| `btech/map.bits.c::clear_hex_bits` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.clear` (method) |
| `btech/map.bits.c::create_if_neccessary` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.set` (method) |
| `btech/map.bits.c::grab_us_an_array` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `bits_for` (function) |
| `btech/map.bits.c::is_hangar_hex` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.query` (method; selector `2`)<br>[tools/maps_environment.py](../../tools/maps_environment.py): `MapsSession.diagnose bit query` (dispatch; selector `bits/query`) |
| `btech/map.bits.c::is_mine_hex` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.query` (method; selector `1`)<br>[tools/maps_environment.py](../../tools/maps_environment.py): `MapsSession.diagnose bit query` (dispatch; selector `bits/query`) |
| `btech/map.bits.c::map_load_bits` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.load` (method)<br>[entities/map_objects.py](../../entities/map_objects.py): `load_objects` (function) |
| `btech/map.bits.c::map_save_bits` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.save` (method) |
| `btech/map.bits.c::set_hex_enterable` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.set` (method; selector `2`)<br>[entities/map_objects.py](../../entities/map_objects.py): `bits_for` (function) |
| `btech/map.bits.c::set_hex_mine` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.set` (method; selector `1`)<br>[entities/map_objects.py](../../entities/map_objects.py): `bits_for` (function) |
| `btech/map.bits.c::unset_hex_enterable` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.unset` (method; selector `2`)<br>[entities/map_objects.py](../../entities/map_objects.py): `bits_for` (function) |
| `btech/map.bits.c::unset_hex_mine` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `BitTable.unset` (method; selector `1`)<br>[entities/map_objects.py](../../entities/map_objects.py): `bits_for` (function) |

<a id="c-btech-map-c"></a>

### `btech/map.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.c::clear_hex` | General; AUD-MAPS; active | [systems/terrain_combat.py](../../systems/terrain_combat.py): `clear_hex` (function)<br>[systems/terrain_combat.py](../../systems/terrain_combat.py): `terrain_message` (function) |
| `btech/map.c::debug_fixmap` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `debug_fix` (function) |
| `btech/map.c::eligible_bridge_hex` | General; AUD-MAPS; active | [entities/map.py](../../entities/map.py): `eligible_bridge_hex` (function) |
| `btech/map.c::initialize_map_empty` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `initialize` (function) |
| `btech/map.c::make_bridges` | General; AUD-MAPS; active | [entities/map.py](../../entities/map.py): `make_bridges` (function) |
| `btech/map.c::map_addhex` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `addhex` (function) |
| `btech/map.c::map_checkmapfile` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `check_file` (function)<br>[systems/map_management.py](../../systems/map_management.py): `check_text` (function)<br>[systems/map_management.py](../../systems/map_management.py): `rows` (function) |
| `btech/map.c::map_clearmechs` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `clear` (function) |
| `btech/map.c::map_listmechs` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `list_mechs` (function) |
| `btech/map.c::map_load` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `load_file` (function)<br>[systems/map_management.py](../../systems/map_management.py): `load_text` (function) |
| `btech/map.c::map_loadmap` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `load_checked` (function) |
| `btech/map.c::map_mapemit` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `emit` (function) |
| `btech/map.c::map_savemap` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `save_file` (function)<br>[systems/map_management.py](../../systems/map_management.py): `save_text` (function) |
| `btech/map.c::map_setmapsize` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `resize` (function) |
| `btech/map.c::map_sizefun` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `source_sizes` (function; selector `map`) |
| `btech/map.c::map_update` | General; AUD-MAPS; active | [entities/map.py](../../entities/map.py): `map_update` (function)<br>[systems/map_conditions.py](../../systems/map_conditions.py): `visibility_values` (function) |
| `btech/map.c::map_view` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `view` (function) |
| `btech/map.c::newfreemap` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `free` (function)<br>[systems/map_management.py](../../systems/map_management.py): `initialize` (function) |
| `btech/map.c::UpdateMechsTerrain` | General; AUD-MAPS; active | [entities/map.py](../../entities/map.py): `GameMap.set_terrain` (method) |
| `btech/map.c::water_distance` | General; AUD-MAPS; active | [entities/map.py](../../entities/map.py): `water_distance` (function) |

<a id="c-btech-map-coding-c"></a>

### `btech/map.coding.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.coding.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.coding.c::Coding_GetElevation` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `Coding.inverse` (method; selector `elevation`) |
| `btech/map.coding.c::Coding_GetIndex` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `Coding.index` (method) |
| `btech/map.coding.c::Coding_GetTerrain` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `Coding.inverse` (method; selector `terrain`) |
| `btech/map.coding.c::init_map_coding` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `Coding.initialize` (method) |

<a id="c-btech-map-conditions-c"></a>

### `btech/map.conditions.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.conditions.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.conditions.c::alter_conditions` | General; AUD-MAPS; active | [systems/map_conditions.py](../../systems/map_conditions.py): `alter_conditions` (function) |
| `btech/map.conditions.c::BreachLoc` | General; AUD-MAPS; active | [systems/damage.py](../../systems/damage.py): `breach_location` (function) |
| `btech/map.conditions.c::DestroyParts` | General; AUD-MAPS; active | [systems/damage.py](../../systems/damage.py): `destroy_parts` (function) |
| `btech/map.conditions.c::map_setconditions` | General; AUD-MAPS; active | [systems/map_conditions.py](../../systems/map_conditions.py): `set_conditions` (function) |
| `btech/map.conditions.c::PossiblyBreach` | General; AUD-MAPS; active | [systems/damage.py](../../systems/damage.py): `possibly_breach` (function) |
| `btech/map.conditions.c::reactor_explosion` | General; AUD-MAPS; active | [systems/damage.py](../../systems/damage.py): `reactor_explosion` (function) |
| `btech/map.conditions.c::UpdateConditions` | General; AUD-MAPS; active | [systems/map_conditions.py](../../systems/map_conditions.py): `update_conditions` (function) |

<a id="c-btech-map-dynamic-c"></a>

### `btech/map.dynamic.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.dynamic.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.dynamic.c::add_mech_to_map` | General; AUD-MAPS; active | [systems/map_membership.py](../../systems/map_membership.py): `add` (function) |
| `btech/map.dynamic.c::do_read` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `read_exact` (function) |
| `btech/map.dynamic.c::do_write` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `write_exact` (function) |
| `btech/map.dynamic.c::eliminate_empties` | General; AUD-MAPS; active | [systems/map_membership.py](../../systems/map_membership.py): `eliminate_empties` (function) |
| `btech/map.dynamic.c::load_mapdynamic` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `load_dynamic` (function) |
| `btech/map.dynamic.c::mech_map_consistency_check` | General; AUD-MAPS; active | [systems/map_membership.py](../../systems/map_membership.py): `consistency` (function)<br>[systems/map_membership.py](../../systems/map_membership.py): `remove_from_all` (function) |
| `btech/map.dynamic.c::mech_size` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `source_sizes` (function; selector `mechs`) |
| `btech/map.dynamic.c::remove_mech_from_map` | General; AUD-MAPS; active | [systems/map_membership.py](../../systems/map_membership.py): `remove` (function)<br>[systems/map_membership.py](../../systems/map_membership.py): `clear_los` (function) |
| `btech/map.dynamic.c::save_mapdynamic` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `save_dynamic` (function) |

<a id="c-btech-map-los-c"></a>

### `btech/map.los.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.los.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.los.c::CalculateLOSMap` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `LOSMap.render` (method)<br>[systems/los.py](../../systems/los.py): `calculate_los_map` (function) |
| `btech/map.los.c::hexlit` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `LOSMap.lit` (method) |
| `btech/map.los.c::litemark_callback` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_mark_map_lights` (function) |
| `btech/map.los.c::litemark_map` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_mark_map_lights` (function) |
| `btech/map.los.c::LOSMap_Hex2Index` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `LOSMap.index` (method) |
| `btech/map.los.c::MechHeight` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `map_eye_height` (function) |
| `btech/map.los.c::MechSeesOverMountain` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_trace_map_terrain` (function) |
| `btech/map.los.c::MechSeesRange` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `map_sensor_range` (function) |
| `btech/map.los.c::MechSeesTerrain` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_trace_map_terrain` (function)<br>[systems/los.py](../../systems/los.py): `calculate_los_map` (function) |
| `btech/map.los.c::MechSeesThroughWater` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_trace_map_terrain` (function) |
| `btech/map.los.c::MechSeesThroughWoods` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_trace_map_terrain` (function) |
| `btech/map.los.c::MechSLitesRange` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_trace_map_light` (function) |
| `btech/map.los.c::set_hexlosall` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `calculate_los_map` (inline) |
| `btech/map.los.c::set_hexlosinfo` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `LOSMap.mark` (method) |
| `btech/map.los.c::set_sliteinfo` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `LOSMap.light` (method) |
| `btech/map.los.c::trace_maphexlos` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_trace_map_terrain` (function) |
| `btech/map.los.c::trace_slitelos` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `_trace_map_light` (function) |

<a id="c-btech-map-obj-c"></a>

### `btech/map.obj.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.obj.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/map.obj.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.obj.c::add_decoration` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `add_decoration` (function) |
| `btech/map.obj.c::add_entrances` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `add_entrances` (function) |
| `btech/map.obj.c::add_links` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `add_links` (function) |
| `btech/map.obj.c::add_mapobj` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `add_object` (function) |
| `btech/map.obj.c::building_rebuild_event` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `rebuild` (function) |
| `btech/map.obj.c::building_regen_event` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `regen` (function) |
| `btech/map.obj.c::CheckForFire` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `check_fire` (function) |
| `btech/map.obj.c::CheckForSmoke` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `check_smoke` (function) |
| `btech/map.obj.c::damage_cf` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `damage_cf` (function) |
| `btech/map.obj.c::del_mapobj` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `delete_object` (function) |
| `btech/map.obj.c::del_mapobjs` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `delete_objects` (function; selector `all10 types`) |
| `btech/map.obj.c::del_mapobjst` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `delete_objects` (function; selector `selected type`) |
| `btech/map.obj.c::find_decorations` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `find_decorations` (function) |
| `btech/map.obj.c::find_entrance` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `entrance` (function) |
| `btech/map.obj.c::find_entrance_by_target` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `by_target` (function) |
| `btech/map.obj.c::find_entrance_by_xy` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `find_object` (function; selector `BUILDING`) |
| `btech/map.obj.c::find_mapobj` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `find_object` (function) |
| `btech/map.obj.c::FindMyCoord` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `coordinate` (function) |
| `btech/map.obj.c::FindXEven` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `coordinate` (function)<br>[physics/decorations.py](../../physics/decorations.py): `EVEN` (data/table; selector `x`) |
| `btech/map.obj.c::FindXOdd` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `coordinate` (function)<br>[physics/decorations.py](../../physics/decorations.py): `ODD` (data/table; selector `x`) |
| `btech/map.obj.c::FindYEven` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `coordinate` (function)<br>[physics/decorations.py](../../physics/decorations.py): `EVEN` (data/table; selector `y`) |
| `btech/map.obj.c::FindYOdd` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `coordinate` (function)<br>[physics/decorations.py](../../physics/decorations.py): `ODD` (data/table; selector `y`) |
| `btech/map.obj.c::fire_dissipation_event` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `expire_fire` (function) |
| `btech/map.obj.c::fire_hex` | General; AUD-MAPS; active | [systems/terrain_combat.py](../../systems/terrain_combat.py): `fire_hex` (function)<br>[systems/terrain_combat.py](../../systems/terrain_combat.py): `terrain_message` (function) |
| `btech/map.obj.c::fire_spreading_event` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `spread_fire` (function)<br>[physics/decorations.py](../../physics/decorations.py): `spread_eligible` (function) |
| `btech/map.obj.c::first_mapobj` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `first_object` (function) |
| `btech/map.obj.c::get_building_cf` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `get_building_cf` (function) |
| `btech/map.obj.c::get_building_regen_factor` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `get_regen_factor` (function) |
| `btech/map.obj.c::get_cf` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `get_cf` (function) |
| `btech/map.obj.c::hit_building` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `missile_count` (function)<br>[systems/buildings.py](../../systems/buildings.py): `hit_building` (function) |
| `btech/map.obj.c::is_blocked_lz` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `blocked_lz` (function) |
| `btech/map.obj.c::is_blocked_lz` | Historical Aerospace; AUD-AEROSPACE; active | [systems/map_links.py](../../systems/map_links.py): `blocked_lz` (function) |
| `btech/map.obj.c::list_mapobjs` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `list_objects` (function) |
| `btech/map.obj.c::load_mapobjs` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `load_objects` (function) |
| `btech/map.obj.c::map_add_block` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `block_lz` (function) |
| `btech/map.obj.c::map_addfire` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `decoration_command` (function; selector `{'kind': 0}`) |
| `btech/map.obj.c::map_addsmoke` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `decoration_command` (function; selector `{'kind': 1}`) |
| `btech/map.obj.c::map_delobj` | General; AUD-MAPS; active | [systems/map_management.py](../../systems/map_management.py): `delobj` (function) |
| `btech/map.obj.c::map_linked` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `linked` (function) |
| `btech/map.obj.c::map_setlinked` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `set_linked` (function) |
| `btech/map.obj.c::map_underlying_terrain` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `underlying_terrain` (function) |
| `btech/map.obj.c::map_updatelinks` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `update_links` (function) |
| `btech/map.obj.c::mapobj_del` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `delete_at` (function) |
| `btech/map.obj.c::mech_underlying_terrain` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `mech_underlying_terrain` (function) |
| `btech/map.obj.c::next_mapobj` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `next_object` (function) |
| `btech/map.obj.c::obj_size` | General; AUD-MAPS; active | [entities/map_storage.py](../../entities/map_storage.py): `source_sizes` (function; selector `objects`) |
| `btech/map.obj.c::parse_coord` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `parse_coord` (function) |
| `btech/map.obj.c::possibly_start_building_regen` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `start_regen` (function) |
| `btech/map.obj.c::recursively_updatelinks` | General; AUD-MAPS; active | [systems/map_links.py](../../systems/map_links.py): `recursively_update` (function) |
| `btech/map.obj.c::save_mapobjs` | General; AUD-MAPS; active | [entities/map_objects.py](../../entities/map_objects.py): `save_objects` (function)<br>[entities/map_objects.py](../../entities/map_objects.py): `object_values` (function) |
| `btech/map.obj.c::set_building_cf` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `set_cf` (function) |
| `btech/map.obj.c::show_building_in_hex` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `query` (function; selector `{'step': False}`)<br>[systems/buildings.py](../../systems/buildings.py): `perception` (function) |
| `btech/map.obj.c::smoke_dissipation_event` | General; AUD-MAPS; active | [physics/decorations.py](../../physics/decorations.py): `expire_smoke` (function) |
| `btech/map.obj.c::steppable_base_check` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `query` (function; selector `{'step': True}`)<br>[systems/buildings.py](../../systems/buildings.py): `perception` (function) |
| `btech/map.obj.c::structure_name` | General; AUD-MAPS; active | [systems/buildings.py](../../systems/buildings.py): `structure_name` (function) |

<a id="c-btech-map-weather-c"></a>

### `btech/map.weather.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/map.weather.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/map.weather.c::calcWeatherEffects` | General; AUD-MAPS; active | [physics/weather.py](../../physics/weather.py): `calc_effects` (function)<br>[physics/environment.py](../../physics/environment.py): `effects` (function)<br>[physics/environment.py](../../physics/environment.py): `predicates` (function) |
| `btech/map.weather.c::calcWeatherGunEffects` | General; AUD-MAPS; active | [physics/weather.py](../../physics/weather.py): `gun_effects` (function)<br>[physics/environment.py](../../physics/environment.py): `gun_modifier` (function) |
| `btech/map.weather.c::calcWeatherPilotEffects` | General; AUD-MAPS; active | [physics/weather.py](../../physics/weather.py): `pilot_effects` (function)<br>[physics/environment.py](../../physics/environment.py): `pilot_modifier` (function) |
| `btech/map.weather.c::growSnow` | General; AUD-MAPS; active | [physics/weather.py](../../physics/weather.py): `grow` (function)<br>[physics/weather.py](../../physics/weather.py): `normalize_snow` (function)<br>[physics/environment.py](../../physics/environment.py): `callback` (function) |
| `btech/map.weather.c::meltSnowAndIce` | General; AUD-MAPS; active | [physics/weather.py](../../physics/weather.py): `melt` (function)<br>[physics/environment.py](../../physics/environment.py): `callback` (function)<br>[systems/environment_storage.py](../../systems/environment_storage.py): `load_snapshot` (function) |
| `btech/map.weather.c::setWeatherHeatEffects` | General; AUD-MAPS; active | [physics/weather.py](../../physics/weather.py): `heat_effects` (function)<br>[physics/environment.py](../../physics/environment.py): `heat_modifier` (function) |
| `btech/map.weather.c::validateWeatherConditions` | General; AUD-MAPS; active | [physics/weather.py](../../physics/weather.py): `validate_conditions` (function)<br>[physics/environment.py](../../physics/environment.py): `normalized_conditions` (function) |

<a id="c-btech-mech-advanced-c"></a>

### `btech/mech.advanced.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.advanced.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.advanced.c::changeNullSigSysEvent` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `signature_event` (function; selector `nullsig`) |
| `btech/mech.advanced.c::changeStealthArmorEvent` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `signature_event` (function; selector `stealtharmor`) |
| `btech/mech.advanced.c::display_mechpref` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_preferences.py](../../systems/combat_preferences.py): `preference` (function)<br>[systems/combat_preferences.py](../../systems/combat_preferences.py): `PREFERENCES` (data/table) |
| `btech/mech.advanced.c::findArmBTHMod` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `arm_bth_modifier` (function) |
| `btech/mech.advanced.c::FindMainWeapon` | General; AUD-SPECIAL-COMBAT; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `main_weapon` (function)<br>[systems/vehicle_combat.py](../../systems/vehicle_combat.py): `jam_main_weapon` (function)<br>[systems/vehicle_combat.py](../../systems/vehicle_combat.py): `destroy_main_weapon` (function) |
| `btech/mech.advanced.c::mech_ams` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_ams` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `ams`) |
| `btech/mech.advanced.c::mech_angeleccm` | General; AUD-SPECIAL-COMBAT; active | [systems/ecm.py](../../systems/ecm.py): `mech_angeleccm` (function)<br>[systems/ecm.py](../../systems/ecm.py): `_toggle` (function) |
| `btech/mech.advanced.c::mech_angelecm` | General; AUD-SPECIAL-COMBAT; active | [systems/ecm.py](../../systems/ecm.py): `mech_angelecm` (function)<br>[systems/ecm.py](../../systems/ecm.py): `_toggle` (function) |
| `btech/mech.advanced.c::mech_armorpiercing` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_armorpiercing` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['armorpiercing']` (data/table; selector `armorpiercing`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `armorpiercing`) |
| `btech/mech.advanced.c::mech_artemis` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_artemis` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['artemis']` (data/table; selector `artemis`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `artemis`) |
| `btech/mech.advanced.c::mech_atmexplosive` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_atmexplosive` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['atmexplosive']` (data/table; selector `atmexplosive`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `atmexplosive`) |
| `btech/mech.advanced.c::mech_atmrange` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_atmrange` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['atmrange']` (data/table; selector `atmrange`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `atmrange`) |
| `btech/mech.advanced.c::mech_auto_turret` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_preferences.py](../../systems/combat_preferences.py): `auto_turret` (function) |
| `btech/mech.advanced.c::mech_caseless` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_caseless` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['caseless']` (data/table; selector `caseless`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `caseless`) |
| `btech/mech.advanced.c::mech_cluster` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_cluster` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['cluster']` (data/table; selector `cluster`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `cluster`) |
| `btech/mech.advanced.c::mech_dig` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `dig` (function)<br>[systems/combat_equipment.py](../../systems/combat_equipment.py): `command` (dispatch; selector `dig`) |
| `btech/mech.advanced.c::mech_dig_event` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `dig_event` (function) |
| `btech/mech.advanced.c::mech_disableweap` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_preferences.py](../../systems/combat_preferences.py): `disable_weapon` (function) |
| `btech/mech.advanced.c::mech_disableweap_func` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_preferences.py](../../systems/combat_preferences.py): `disable_weapon` (function) |
| `btech/mech.advanced.c::mech_eccm` | General; AUD-SPECIAL-COMBAT; active | [systems/ecm.py](../../systems/ecm.py): `mech_eccm` (function)<br>[systems/ecm.py](../../systems/ecm.py): `_toggle` (function) |
| `btech/mech.advanced.c::mech_ecm` | General; AUD-SPECIAL-COMBAT; active | [systems/ecm.py](../../systems/ecm.py): `mech_ecm` (function)<br>[systems/ecm.py](../../systems/ecm.py): `_toggle` (function) |
| `btech/mech.advanced.c::mech_explode` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `explode` (function) |
| `btech/mech.advanced.c::mech_explode_event` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `explode_event` (function) |
| `btech/mech.advanced.c::mech_explosive` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_explosive` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['explosive']` (data/table; selector `explosive`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `explosive`) |
| `btech/mech.advanced.c::mech_fixturret` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `command` (dispatch; selector `fixturret`) |
| `btech/mech.advanced.c::mech_flamerheat` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_flamerheat` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['flamerheat']` (data/table; selector `flamerheat`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `flamerheat`) |
| `btech/mech.advanced.c::mech_flechette` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_flechette` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['flechette']` (data/table; selector `flechette`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `flechette`) |
| `btech/mech.advanced.c::mech_fliparms` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `command` (dispatch; selector `fliparms`) |
| `btech/mech.advanced.c::mech_gattling` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_gattling` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['gattling']` (data/table; selector `gattling`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `gattling`) |
| `btech/mech.advanced.c::mech_hotload` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_hotload` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['hotload']` (data/table; selector `hotload`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `hotload`) |
| `btech/mech.advanced.c::mech_inarc_ammo_toggle` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_inarc_ammo` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_INARC_MODES` (data/table)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `inarc`) |
| `btech/mech.advanced.c::mech_incendiary` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_incendiary` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['incendiary']` (data/table; selector `incendiary`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `incendiary`) |
| `btech/mech.advanced.c::mech_inferno` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_inferno` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['inferno']` (data/table; selector `inferno`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `inferno`) |
| `btech/mech.advanced.c::mech_lbx` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_lbx` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['lbx']` (data/table; selector `lbx`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `lbx`) |
| `btech/mech.advanced.c::mech_masc` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `booster_command` (function; selector `masc`)<br>[systems/combat_equipment.py](../../systems/combat_equipment.py): `command` (dispatch; selector `masc`) |
| `btech/mech.advanced.c::mech_masc_event` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `booster_event` (function; selector `masc`) |
| `btech/mech.advanced.c::mech_mascr_event` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `booster_regen` (function; selector `masc`) |
| `btech/mech.advanced.c::mech_mechprefs` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_preferences.py](../../systems/combat_preferences.py): `mechprefs` (function)<br>[systems/combat_preferences.py](../../systems/combat_preferences.py): `PREFERENCES` (data/table) |
| `btech/mech.advanced.c::mech_mine` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_mine` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['mine']` (data/table; selector `mine`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `mine`) |
| `btech/mech.advanced.c::mech_narc` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_narc` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['narc']` (data/table; selector `narc`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `narc`) |
| `btech/mech.advanced.c::mech_nullsig` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `signature_command` (function; selector `nullsig`)<br>[systems/combat_equipment.py](../../systems/combat_equipment.py): `command` (dispatch; selector `nullsig`) |
| `btech/mech.advanced.c::mech_pereccm` | General; AUD-SPECIAL-COMBAT; active | [systems/ecm.py](../../systems/ecm.py): `mech_pereccm` (function)<br>[systems/ecm.py](../../systems/ecm.py): `_toggle` (function) |
| `btech/mech.advanced.c::mech_perecm` | General; AUD-SPECIAL-COMBAT; active | [systems/ecm.py](../../systems/ecm.py): `mech_perecm` (function)<br>[systems/ecm.py](../../systems/ecm.py): `_toggle` (function) |
| `btech/mech.advanced.c::mech_precision` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_precision` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['precision']` (data/table; selector `precision`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `precision`) |
| `btech/mech.advanced.c::mech_rac` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_rac` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_RAC_MODES` (data/table)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `rac`) |
| `btech/mech.advanced.c::mech_rapidfire` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_rapidfire` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['rapidfire']` (data/table; selector `rapidfire`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `rapidfire`) |
| `btech/mech.advanced.c::mech_safety` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_preferences.py](../../systems/combat_preferences.py): `safety` (function) |
| `btech/mech.advanced.c::mech_scharge` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `booster_command` (function; selector `scharge`)<br>[systems/combat_equipment.py](../../systems/combat_equipment.py): `command` (dispatch; selector `scharge`) |
| `btech/mech.advanced.c::mech_scharge_event` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `booster_event` (function; selector `scharge`) |
| `btech/mech.advanced.c::mech_scharger_event` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `booster_regen` (function; selector `scharge`) |
| `btech/mech.advanced.c::mech_sguided` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_sguided` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['sguided']` (data/table; selector `sguided`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `sguided`) |
| `btech/mech.advanced.c::mech_slite` | General; AUD-SPECIAL-COMBAT; active | [systems/sensors.py](../../systems/sensors.py): `slite` (function) |
| `btech/mech.advanced.c::mech_smoke` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_smoke` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['smoke']` (data/table; selector `smoke`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `smoke`) |
| `btech/mech.advanced.c::mech_stealtharmor` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `signature_command` (function; selector `stealtharmor`)<br>[systems/combat_equipment.py](../../systems/combat_equipment.py): `command` (dispatch; selector `stealtharmor`) |
| `btech/mech.advanced.c::mech_stinger` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_stinger` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['stinger']` (data/table; selector `stinger`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `stinger`) |
| `btech/mech.advanced.c::mech_swarm` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_swarm` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['swarm']` (data/table; selector `swarm`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `swarm`) |
| `btech/mech.advanced.c::mech_swarm1` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_swarm1` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['swarm1']` (data/table; selector `swarm1`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `swarm1`) |
| `btech/mech.advanced.c::mech_toggle_mode_sub` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (function)<br>[systems/tic.py](../../systems/tic.py): `multi_weap_sel` (function) |
| `btech/mech.advanced.c::mech_toggle_mode_sub_func` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `toggle_mode` (function) |
| `btech/mech.advanced.c::mech_ultra` | General; AUD-SPECIAL-COMBAT; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `mech_ultra` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `_COMMANDS['ultra']` (data/table; selector `ultra`)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `mode_command` (dispatch; selector `ultra`) |
| `btech/mech.advanced.c::mech_unjam_turret_event` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `unjam_turret_event` (function) |
| `btech/mech.advanced.c::mech_unjamammo` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `unjam_ammo` (function) |
| `btech/mech.advanced.c::mech_unjamammo_func` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `unjam_ammo` (function) |
| `btech/mech.advanced.c::mech_usebin` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `usebin` (function) |
| `btech/mech.advanced.c::MechSliteChangeEvent` | General; AUD-SPECIAL-COMBAT; active | [systems/sensors.py](../../systems/sensors.py): `slite_change_event` (function) |
| `btech/mech.advanced.c::remove_inarc_pods_mech` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `remove_pods_mech` (function) |
| `btech/mech.advanced.c::remove_inarc_pods_tank` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `remove_pods_tank` (function) |
| `btech/mech.advanced.c::removeiNarcPodsTank` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `remove_pods_event` (function) |
| `btech/mech.advanced.c::show_narc_pods` | General; AUD-SPECIAL-COMBAT; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `show_pods` (function) |

<a id="c-btech-mech-ammodump-c"></a>

### `btech/mech.ammodump.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.ammodump.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.ammodump.c::BlowDumpingAmmo` | General; AUD-HEAT; active | [systems/ammo_dump.py](../../systems/ammo_dump.py): `blow_dumping_ammo` (function)<br>[systems/ammo_dump.py](../../systems/ammo_dump.py): `rear_hit` (function) |
| `btech/mech.ammodump.c::Dump_Decrease` | General; AUD-HEAT; active | [systems/ammo_dump.py](../../systems/ammo_dump.py): `dump_decrease` (function) |
| `btech/mech.ammodump.c::FindMaxAmmoDamage` | General; AUD-HEAT; active | [systems/ammo_dump.py](../../systems/ammo_dump.py): `find_max_ammo_damage` (function)<br>[systems/ammo_dump.py](../../systems/ammo_dump.py): `ammo_full_salvo` (function) |
| `btech/mech.ammodump.c::mech_dump` | General; AUD-HEAT; active | [systems/ammo_dump.py](../../systems/ammo_dump.py): `mech_dump` (function) |
| `btech/mech.ammodump.c::mech_dump_event` | General; AUD-HEAT; active | [systems/ammo_dump.py](../../systems/ammo_dump.py): `mech_dump_event` (function) |

<a id="c-btech-mech-bth-c"></a>

### `btech/mech.bth.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.bth.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.bth.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.bth.c::AttackMovementMods` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `calculate_attacker_movement_modifier` (function) |
| `btech/mech.bth.c::FindArtilleryBTH` | General; AUD-FIRING; active | [systems/artillery.py](../../systems/artillery.py): `artillery_bth` (function) |
| `btech/mech.bth.c::FindBTHByC3Range` | General; AUD-FIRING; active | [systems/combat_ranges.py](../../systems/combat_ranges.py): `by_c3_range` (function) |
| `btech/mech.bth.c::FindBTHByRange` | General; AUD-FIRING; active | [systems/combat_ranges.py](../../systems/combat_ranges.py): `by_range` (function)<br>[systems/combat_ranges.py](../../systems/combat_ranges.py): `underwater` (function)<br>[systems/combat_ranges.py](../../systems/combat_ranges.py): `extreme_range` (function) |
| `btech/mech.bth.c::FindNormalBTH` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `calculate_bth` (function)<br>[systems/combat.py](../../systems/combat.py): `resolve_attack` (function) |
| `btech/mech.bth.c::FindNormalBTH` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `calculate_bth Aerospace terms` (inline/use)<br>[systems/combat.py](../../systems/combat.py): `calculate_bth aiming` (inline/use) |
| `btech/mech.bth.c::TargetMovementMods` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `calculate_target_movement_modifier` (function)<br>[systems/combat.py](../../systems/combat.py): `is_target_immobile` (function) |
| `btech/mech.bth.c::TargetMovementMods` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `calculate_target_movement_modifier` (function)<br>[systems/combat.py](../../systems/combat.py): `is_target_immobile` (function) |

<a id="c-btech-mech-build-c"></a>

### `btech/mech.build.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.build.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.build.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.build.c::ArmorSectionFromString` | General; AUD-TEMPLATES; active | [systems/damage_commands.py](../../systems/damage_commands.py): `armor_section_from_string` (function)<br>[systems/damage_commands.py](../../systems/damage_commands.py): `section_names` (function) |
| `btech/mech.build.c::CheckData` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `check_data` (function) |
| `btech/mech.build.c::FillDefaultCriticals` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `fill_default_criticals` (function)<br>[data/templates.py](../../data/templates.py): `fill_default_criticals_section` (function) |
| `btech/mech.build.c::FillDefaultCriticals` | Historical Aerospace; AUD-AEROSPACE; active | [data/templates.py](../../data/templates.py): `fill_default_criticals_section` (function) |
| `btech/mech.build.c::FindSpecialItemCodeFromString` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.special_index` (method) |
| `btech/mech.build.c::ShortArmorSectionString` | General; AUD-TEMPLATES; active | [systems/damage_commands.py](../../systems/damage_commands.py): `short_section` (function)<br>[systems/damage_commands.py](../../systems/damage_commands.py): `section_names` (function) |
| `btech/mech.build.c::WeaponIndexFromString` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.weapon_index` (method) |

<a id="c-btech-mech-c3-c"></a>

### `btech/mech.c3.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.c3.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.c3.c::addMechToC3Network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `add` (function) |
| `btech/mech.c3.c::clearC3Network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `clear` (function) |
| `btech/mech.c3.c::clearMechFromC3Network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `remove` (function) |
| `btech/mech.c3.c::countMaxC3Units` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `maximum` (function) |
| `btech/mech.c3.c::countTotalC3MastersOnMech` | General; AUD-COMMS; active | [systems/criticals.py](../../systems/criticals.py): `count_total_c3_masters` (function) |
| `btech/mech.c3.c::countWorkingC3MastersOnMech` | General; AUD-COMMS; active | [systems/criticals.py](../../systems/criticals.py): `count_working_c3_masters` (function) |
| `btech/mech.c3.c::getC3MasterSize` | General; AUD-COMMS; active | [systems/criticals.py](../../systems/criticals.py): `count_working_c3_masters` (function)<br>[systems/criticals.py](../../systems/criticals.py): `count_total_c3_masters (inline size)` (inline)<br>[systems/c3.py](../../systems/c3.py): `part_of_working_master (inline size)` (inline) |
| `btech/mech.c3.c::getFreeC3NetworkPos` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `free_position` (function) |
| `btech/mech.c3.c::isPartOfWorkingC3Master` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `part_of_working_master` (function) |
| `btech/mech.c3.c::mech_c3_join_leave` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3.c::mech_c3_message` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3.c::mech_c3_network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3.c::mech_c3_targets` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3.c::replicateC3Network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `replicate` (function) |
| `btech/mech.c3.c::trimC3Network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `trim` (function) |
| `btech/mech.c3.c::validateC3Network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `validate` (function) |

<a id="c-btech-mech-c3-misc-c"></a>

### `btech/mech.c3.misc.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.c3.misc.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.c3.misc.c::buildTempNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `temporary` (function) |
| `btech/mech.c3.misc.c::debugC3` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `debug` (function) |
| `btech/mech.c3.misc.c::findC3Range` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `range_query` (function)<br>[systems/combat_ranges.py](../../systems/combat_ranges.py): `find_c3_range` (function) |
| `btech/mech.c3.misc.c::findC3RangeWithNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `range_with_network` (function) |
| `btech/mech.c3.misc.c::getMechInTempNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `temp_member` (function) |
| `btech/mech.c3.misc.c::getOtherMechInNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `other` (function) |
| `btech/mech.c3.misc.c::mechSeenByNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `seen_by_network` (function) |
| `btech/mech.c3.misc.c::sendNetworkMessage` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `send_message` (function) |
| `btech/mech.c3.misc.c::showNetworkData` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `network_data` (function)<br>[systems/network_reports.py](../../systems/network_reports.py): `remaining_percent` (function)<br>[systems/c3.py](../../systems/c3.py): `command report delivery` (dispatch) |
| `btech/mech.c3.misc.c::showNetworkTargets` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `targets` (function)<br>[systems/observation.py](../../systems/observation.py): `status_chars` (function)<br>[systems/c3.py](../../systems/c3.py): `command report delivery` (dispatch) |

<a id="c-btech-mech-c3i-c"></a>

### `btech/mech.c3i.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.c3i.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.c3i.c::addMechToC3iNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `add` (function) |
| `btech/mech.c3i.c::clearC3iNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `clear` (function) |
| `btech/mech.c3i.c::clearMechFromC3iNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `remove` (function) |
| `btech/mech.c3i.c::getFreeC3iNetworkPos` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `free_position` (function) |
| `btech/mech.c3i.c::mech_c3i_join_leave` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3i.c::mech_c3i_message` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3i.c::mech_c3i_network` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3i.c::mech_c3i_targets` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `command` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.c3i.c::replicateC3iNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `replicate` (function) |
| `btech/mech.c3i.c::validateC3iNetwork` | General; AUD-COMMS; active | [systems/c3.py](../../systems/c3.py): `validate` (function) |

<a id="c-btech-mech-combat-c"></a>

### `btech/mech.combat.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.combat.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.combat.c::canWeaponClear` | General; AUD-FIRING; active | [systems/terrain_combat.py](../../systems/terrain_combat.py): `can_weapon_clear` (function) |
| `btech/mech.combat.c::canWeaponIgnite` | General; AUD-FIRING; active | [systems/terrain_combat.py](../../systems/terrain_combat.py): `can_weapon_ignite` (function) |
| `btech/mech.combat.c::determineDamageFromHit` | General; AUD-FIRING; active | [systems/combat_impacts.py](../../systems/combat_impacts.py): `determine_damage` (function) |
| `btech/mech.combat.c::FireWeapon` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `fire_weapon` (function)<br>[systems/combat.py](../../systems/combat.py): `resolve_attack` (function)<br>[systems/combat_ammunition.py](../../systems/combat_ammunition.py): `risky_mode_failure` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `begin_shot` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `firing_feedback` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `announce_shot` (function) |
| `btech/mech.combat.c::FireWeaponNumber` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `fire_weapon_number` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `fire_number` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `mount_guard` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `target_guard` (function) |
| `btech/mech.combat.c::hex_hit` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `hex_hit` (function)<br>[systems/combat.py](../../systems/combat.py): `hit_building` (function) |
| `btech/mech.combat.c::hex_target_id` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `hex_target_id` (function) |
| `btech/mech.combat.c::HitTarget` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `resolve_attack` (function)<br>[systems/combat.py](../../systems/combat.py): `_apply_single_hit` (function) |
| `btech/mech.combat.c::mech_fireweapon` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `fire_weapon_number` (function)<br>[tools/combat_resolution.py](../../tools/combat_resolution.py): `CombatSession.command` (method)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `fire_number` (function) |
| `btech/mech.combat.c::mech_settarget` | General; AUD-FIRING; active | [systems/targeting.py](../../systems/targeting.py): `lock_command` (function)<br>[systems/targeting.py](../../systems/targeting.py): `set_target` (function)<br>[systems/targeting.py](../../systems/targeting.py): `set_target_hex` (function)<br>[systems/targeting.py](../../systems/targeting.py): `clear_target` (function) |
| `btech/mech.combat.c::mech_ss_event` | General; AUD-FIRING; active | [systems/targeting.py](../../systems/targeting.py): `sixth_sense_event` (function) |
| `btech/mech.combat.c::mech_target` | General; AUD-FIRING; active | [systems/targeting.py](../../systems/targeting.py): `aim_command` (function)<br>[systems/targeting.py](../../systems/targeting.py): `set_aim` (function) |
| `btech/mech.combat.c::possibly_clear` | General; AUD-FIRING; active | [systems/terrain_combat.py](../../systems/terrain_combat.py): `possibly_clear` (function)<br>[systems/terrain_combat.py](../../systems/terrain_combat.py): `clear_hex` (function) |
| `btech/mech.combat.c::possibly_ignite` | General; AUD-FIRING; active | [systems/terrain_combat.py](../../systems/terrain_combat.py): `possibly_ignite` (function)<br>[systems/terrain_combat.py](../../systems/terrain_combat.py): `fire_hex` (function) |
| `btech/mech.combat.c::possibly_ignite_or_clear` | General; AUD-FIRING; active | [systems/terrain_combat.py](../../systems/terrain_combat.py): `possibly_ignite_or_clear` (function)<br>[systems/combat.py](../../systems/combat.py): `possibly_ignite_or_clear` (function) |
| `btech/mech.combat.c::sendC3TrackEmit` | General; AUD-FIRING; active | [systems/combat_ranges.py](../../systems/combat_ranges.py): `send_c3_track_emit` (function) |
| `btech/mech.combat.c::sixth_sense_check` | General; AUD-FIRING; active | [systems/targeting.py](../../systems/targeting.py): `sixth_sense_check` (function) |
| `btech/mech.combat.c::weapon_failure_stuff` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `fire_weapon.check_brand_failure` (nested function)<br>[systems/combat.py](../../systems/combat.py): `resolve_attack` (function) |

<a id="c-btech-mech-combat-misc-c"></a>

### `btech/mech.combat.misc.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.combat.misc.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.combat.misc.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.combat.misc.c::ammo_expedinture_check` | General; AUD-FIRING; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `expenditure_check` (function) |
| `btech/mech.combat.misc.c::decrement_ammunition` | General; AUD-FIRING; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `decrement` (function) |
| `btech/mech.combat.misc.c::DestroyMech` | General; AUD-FIRING; active | [systems/damage.py](../../systems/damage.py): `destroy_mech` (function)<br>[systems/startup.py](../../systems/startup.py): `shutdown_state` (function) |
| `btech/mech.combat.misc.c::heat_effect` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `heat_effect` (function) |
| `btech/mech.combat.misc.c::heat_effect` | Historical Aerospace; AUD-AEROSPACE; active | [systems/missile.py](../../systems/missile.py): `heat_effect` (function) |
| `btech/mech.combat.misc.c::Inferno_Hit` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `inferno_hit` (function) |
| `btech/mech.combat.misc.c::KillMechContentsIfIC` | General; AUD-FIRING; active | [systems/damage.py](../../systems/damage.py): `_kill_mech_contents` (function)<br>[systems/occupants.py](../../systems/occupants.py): `kill_contents` (function) |
| `btech/mech.combat.misc.c::Plasma_Hit` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `apply_damage_with_transfer` (function) |
| `btech/mech.combat.misc.c::short_hextarget` | General; AUD-FIRING; active | [systems/combat.py](../../systems/combat.py): `short_hextarget` (function) |

<a id="c-btech-mech-combat-missile-c"></a>

### `btech/mech.combat.missile.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.combat.missile.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.combat.missile.c::AMSMissiles` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `ams_missiles` (function) |
| `btech/mech.combat.missile.c::LocateAMSDefenses` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `locate_ams_defenses` (function) |
| `btech/mech.combat.missile.c::Missile_Hit` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `missile_hit` (function)<br>[systems/combat.py](../../systems/combat.py): `_group_damage_func` (function) |
| `btech/mech.combat.missile.c::MissileHitIndex` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `missile_hit_index` (function) |
| `btech/mech.combat.missile.c::MissileHitTarget` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `missile_hit_target` (function)<br>[systems/combat.py](../../systems/combat.py): `_missile_weapon_hit` (function)<br>[systems/missile.py](../../systems/missile.py): `narc_attach` (function) |
| `btech/mech.combat.missile.c::SwarmHitTarget` | General; AUD-FIRING; active | [systems/missile.py](../../systems/missile.py): `swarm_hit_target` (function)<br>[systems/missile.py](../../systems/missile.py): `swarm_next_target` (function) |

<a id="c-btech-mech-consistency-c"></a>

### `btech/mech.consistency.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.consistency.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.consistency.c::ammo_weight` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `ammo_weight` (function) |
| `btech/mech.consistency.c::calc_ints` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `weight` (inline; selector `total_int/current_int`) |
| `btech/mech.consistency.c::crit_weight` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `crit_weight` (function) |
| `btech/mech.consistency.c::engine_weight` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `engine_weight` (function) |
| `btech/mech.consistency.c::mech_int_check` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `internal_check` (function; selector `Mech and dispatcher`) |
| `btech/mech.consistency.c::mech_weight` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `weight` (function) |
| `btech/mech.consistency.c::mech_weight_sub` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `weight` (function) |
| `btech/mech.consistency.c::mech_weight_sub_mech` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `weight` (function; selector `Mech branch`) |
| `btech/mech.consistency.c::mech_weight_sub_veh` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `weight` (function; selector `ground/VTOL/naval branch`) |
| `btech/mech.consistency.c::real_int` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `internal_value` (function) |
| `btech/mech.consistency.c::susp_factor` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `suspension` (function) |
| `btech/mech.consistency.c::tank_in_pieces` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `weight` (inline; selector `any(section.internal)`) |
| `btech/mech.consistency.c::vehicle_int_check` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `internal_check` (function; selector `vehicle`) |

<a id="c-btech-mech-contacts-c"></a>

### `btech/mech.contacts.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.contacts.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.contacts.c::getStatusChar` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `status_chars` (function)<br>[systems/observation.py](../../systems/observation.py): `_statuses` (function) |
| `btech/mech.contacts.c::getStatusString` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `_statuses / status_string` (function) |
| `btech/mech.contacts.c::getWeaponArc` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `weapon_arc` (function) |
| `btech/mech.contacts.c::mech_brief` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `brief` (function) |
| `btech/mech.contacts.c::mech_contacts` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `contacts` (function)<br>[systems/targeting.py](../../systems/targeting.py): `list_contacts` (function)<br>[systems/display_contacts.py](../../systems/display_contacts.py): `building_contacts / contact_lines` (function) |
| `btech/mech.contacts.c::show_brief_flags` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `brief(no argument)` (inline) |

<a id="c-btech-mech-damage-c"></a>

### `btech/mech.damage.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.damage.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.damage.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.damage.c::cause_armordamage` | General; AUD-DAMAGE; active | [systems/combat.py](../../systems/combat.py): `apply_damage_to_location` (function) |
| `btech/mech.damage.c::cause_armordamage` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `apply_damage_to_location` (function) |
| `btech/mech.damage.c::cause_internaldamage` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `cause_internal_damage` (function) |
| `btech/mech.damage.c::CountWeaponsInLoc` | General; AUD-DAMAGE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `count_weapons_in_location` (function) |
| `btech/mech.damage.c::CountWeaponsInLoc` | Historical Aerospace; AUD-AEROSPACE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `count_weapons_in_location` (function) |
| `btech/mech.damage.c::DamageMech` | General; AUD-DAMAGE; active | [systems/combat.py](../../systems/combat.py): `apply_damage_with_transfer` (function) |
| `btech/mech.damage.c::DamageMech` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `apply_damage_with_transfer` (function) |
| `btech/mech.damage.c::DestroyHeatSink` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `destroy_heat_sink` (function) |
| `btech/mech.damage.c::DestroyHeatSink` | Historical Aerospace; AUD-AEROSPACE; active | [systems/damage.py](../../systems/damage.py): `destroy_heat_sink` (function)<br>[entities/mech.py](../../entities/mech.py): `Mech.real_num_sinks` (method) |
| `btech/mech.damage.c::DestroySection` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `destroy_section` (function) |
| `btech/mech.damage.c::DestroySection` | Historical Aerospace; AUD-AEROSPACE; active | [systems/damage.py](../../systems/damage.py): `destroy_section` (function)<br>[systems/damage.py](../../systems/damage.py): `section_destroyed` (function) |
| `btech/mech.damage.c::DestroyWeapon` | General; AUD-DAMAGE; active | [systems/criticals.py](../../systems/criticals.py): `destroy_weapon` (function) |
| `btech/mech.damage.c::DestroyWeapon` | Historical Aerospace; AUD-AEROSPACE; active | [systems/criticals.py](../../systems/criticals.py): `destroy_weapon` (function)<br>[systems/criticals.py](../../systems/criticals.py): `_destroy_part` (function) |
| `btech/mech.damage.c::dodamage_func` | General; AUD-DAMAGE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `dodamage` (function) |
| `btech/mech.damage.c::FindWeaponTypeNumInLoc` | General; AUD-DAMAGE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `find_weapon_type_num_in_location` (function) |
| `btech/mech.damage.c::FindWeaponTypeNumInLoc` | Historical Aerospace; AUD-AEROSPACE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `find_weapon_type_num_in_location` (function) |
| `btech/mech.damage.c::LoseWeapon` | General; AUD-DAMAGE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `lose_weapon` (function) |
| `btech/mech.damage.c::LoseWeapon` | Historical Aerospace; AUD-AEROSPACE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `lose_weapon` (function) |
| `btech/mech.damage.c::mech_damage` | General; AUD-DAMAGE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `damage_command` (function) |
| `btech/mech.damage.c::mech_damage_section` | General; AUD-DAMAGE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `damage_command` (function) |
| `btech/mech.damage.c::MySeriousColorStr` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `serious_color` (function) |
| `btech/mech.damage.c::MySeriousnessCheck` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `armor_severity` (function) |
| `btech/mech.damage.c::MySeriousnessCheckR` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `armor_severity` (function) |
| `btech/mech.damage.c::MySeriousStr` | General; AUD-DAMAGE; active | [systems/damage.py](../../systems/damage.py): `serious_message` (function) |
| `btech/mech.damage.c::setarmorstatus_func` | General; AUD-DAMAGE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `set_armor_status` (function) |

<a id="c-btech-mech-ecm-c"></a>

### `btech/mech.ecm.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.ecm.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.ecm.c::checkECM` | General; AUD-SENSORS; active | [systems/ecm.py](../../systems/ecm.py): `check_ecm` (function)<br>[systems/ecm.py](../../systems/ecm.py): `section_destroyed` (function) |
| `btech/mech.ecm.c::sendECMNotification` | General; AUD-SENSORS; active | [systems/ecm.py](../../systems/ecm.py): `_notify` (function)<br>[systems/ecm.py](../../systems/ecm.py): `send_ecm_notification` (function) |

<a id="c-btech-mech-enhanced-criticals-c"></a>

### `btech/mech.enhanced.criticals.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.enhanced.criticals.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.enhanced.criticals.c::canWeapExplodeFromDamage` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `can_weap_explode_from_damage` (function) |
| `btech/mech.enhanced.criticals.c::canWeapJamFromDamage` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `can_weap_jam_from_damage` (function) |
| `btech/mech.enhanced.criticals.c::countDamagedSlots` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `count_damaged_slots` (function) |
| `btech/mech.enhanced.criticals.c::countDamagedSlotsFromCrit` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `count_damaged_slots_from_crit` (function) |
| `btech/mech.enhanced.criticals.c::getCritAddedBTH` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `get_crit_added_bth` (function) |
| `btech/mech.enhanced.criticals.c::getCritAddedHeat` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `get_crit_added_heat` (function) |
| `btech/mech.enhanced.criticals.c::getCritSubDamage` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `get_crit_sub_damage` (function) |
| `btech/mech.enhanced.criticals.c::getWeapData` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `get_weap_data` (function) |
| `btech/mech.enhanced.criticals.c::isWeapAmmoFeedLocked` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `is_weap_ammo_feed_locked` (function) |
| `btech/mech.enhanced.criticals.c::mech_weaponstatus` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `weapon_status` (function) |
| `btech/mech.enhanced.criticals.c::scoreEnhancedWeaponCriticalHit` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `score_enhanced_weapon_critical_hit` (function) |
| `btech/mech.enhanced.criticals.c::shouldDestroyWeapon` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `should_destroy_weapon` (function) |
| `btech/mech.enhanced.criticals.c::showWeaponDamageAndInfo` | General; AUD-DAMAGE; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `show_weapon_damage_and_info` (function) |

<a id="c-btech-mech-events-c"></a>

### `btech/mech.events.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.events.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.events.c::aero_move_event` | General; AUD-CORE; active | [physics/movement.py](../../physics/movement.py): `aero_move_event` (function)<br>[physics/aerospace.py](../../physics/aerospace.py): `update_heading` (function)<br>[physics/aerospace.py](../../physics/aerospace.py): `update_speed` (function)<br>[physics/aerospace.py](../../physics/aerospace.py): `exhaust` (function)<br>[physics/movement.py](../../physics/movement.py): `update_movement` (function) |
| `btech/mech.events.c::calcNewStaggerBTHMod` | General; AUD-CORE; active | [systems/stagger.py](../../systems/stagger.py): `stagger_modifier` (function) |
| `btech/mech.events.c::calcStaggerBTHMod` | General; AUD-CORE; active | [systems/stagger.py](../../systems/stagger.py): `legacy_modifier` (function)<br>[systems/stagger.py](../../systems/stagger.py): `stagger_modifier` (function) |
| `btech/mech.events.c::check_stagger_event` | General; AUD-CORE; active | [systems/stagger.py](../../systems/stagger.py): `check_stagger_event` (function) |
| `btech/mech.events.c::factoral` | General; AUD-CORE; active | [physics/orbital.py](../../physics/orbital.py): `fall_event: triangular severity expression` (inline; selector `abs(speed) * (abs(speed) + 1) // 2`) |
| `btech/mech.events.c::mech_crewstun_event` | General; AUD-CORE; active | [systems/hit_locations.py](../../systems/hit_locations.py): `crewstun_recovery` (function) |
| `btech/mech.events.c::mech_fall_event` | General; AUD-CORE; active | [physics/orbital.py](../../physics/orbital.py): `fall_event` (function) |
| `btech/mech.events.c::mech_heartbeat` | General; AUD-CORE; active | [core/game_loop.py](../../core/game_loop.py): `mech_heartbeat` (function)<br>[systems/stagger.py](../../systems/stagger.py): `heartbeat` (function)<br>[core/game_loop.py](../../core/game_loop.py): `update_recycling` (function) |
| `btech/mech.events.c::mech_jump_event` | General; AUD-CORE; active | [physics/jump.py](../../physics/jump.py): `_jump_event_callback` (function)<br>[physics/jump.py](../../physics/jump.py): `update_jump` (function)<br>[physics/jump.py](../../physics/jump.py): `land_mech` (function) |
| `btech/mech.events.c::mech_lateral_event` | General; AUD-CORE; active | [systems/maneuver.py](../../systems/maneuver.py): `lateral_event` (function) |
| `btech/mech.events.c::mech_lock_event` | General; AUD-CORE; active | [systems/targeting.py](../../systems/targeting.py): `lock_event` (function) |
| `btech/mech.events.c::mech_move_event` | General; AUD-CORE; active | [physics/movement.py](../../physics/movement.py): `mech_move_event` (function)<br>[physics/movement.py](../../physics/movement.py): `update_movement` (function)<br>[physics/movement.py](../../physics/movement.py): `update_heading` (function)<br>[physics/movement.py](../../physics/movement.py): `update_speed` (function)<br>[physics/movement.py](../../physics/movement.py): `move_mech` (function)<br>[physics/movement.py](../../physics/movement.py): `on_hex_entered` (function)<br>[physics/movement.py](../../physics/movement.py): `new_hex_entered` (function)<br>[physics/movement.py](../../physics/movement.py): `update_charge` (function) |
| `btech/mech.events.c::mech_movemode_event` | General; AUD-CORE; active | [systems/movement_commands.py](../../systems/movement_commands.py): `_mode_complete` (function) |
| `btech/mech.events.c::mech_plos_event` | General; AUD-CORE; active | [systems/targeting.py](../../systems/targeting.py): `plos_event` (function)<br>[systems/sensors.py](../../systems/sensors.py): `sensor_do_we_see_now` (function) |
| `btech/mech.events.c::mech_recovery_event` | General; AUD-CORE; active | [systems/piloting.py](../../systems/piloting.py): `recovery_event` (function)<br>[systems/piloting.py](../../systems/piloting.py): `mech_recovery` (function)<br>[systems/piloting.py](../../systems/piloting.py): `handle_mw_conc` (function) |
| `btech/mech.events.c::mech_sideslip_event` | General; AUD-CORE; active | [systems/maneuver.py](../../systems/maneuver.py): `sideslip_event` (function) |
| `btech/mech.events.c::mech_stabilizing_event` | General; AUD-CORE; active | [physics/jump.py](../../physics/jump.py): `_jumpstabil_callback` (function) |
| `btech/mech.events.c::mech_staggercheck_heartbeat` | General; AUD-CORE; active | [systems/stagger.py](../../systems/stagger.py): `heartbeat` (function)<br>[systems/stagger.py](../../systems/stagger.py): `check_new_damage` (function) |
| `btech/mech.events.c::mech_stand_event` | General; AUD-CORE; active | [physics/jump.py](../../physics/jump.py): `_stand_done` (function) |
| `btech/mech.events.c::mech_standfail_event` | General; AUD-CORE; active | [physics/jump.py](../../physics/jump.py): `_stand_recovered` (function) |
| `btech/mech.events.c::mech_unjam_ammo_event` | General; AUD-CORE; active | [systems/combat_equipment.py](../../systems/combat_equipment.py): `unjam_ammo_event` (function)<br>[systems/combat_ammunition.py](../../systems/combat_ammunition.py): `find_and_check` (function)<br>[systems/combat_ammunition.py](../../systems/combat_ammunition.py): `decrement` (function) |
| `btech/mech.events.c::ProlongUncon` | General; AUD-CORE; active | [systems/piloting.py](../../systems/piloting.py): `prolong_uncon` (function) |
| `btech/mech.events.c::unstun_crew_event` | General; AUD-CORE; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `unstun_crew` (function)<br>[systems/vehicle_combat.py](../../systems/vehicle_combat.py): `tank_flag` (function) |
| `btech/mech.events.c::very_fake_func` | General; AUD-CORE; inactive/empty | [core/events.py](../../core/events.py): `very_fake_func` (function) |

<a id="c-btech-mech-fire-c"></a>

### `btech/mech.fire.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.fire.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.fire.c::checkVehicleInFire` | General; AUD-HEAT; active | [systems/vehicle_fire.py](../../systems/vehicle_fire.py): `check_vehicle_in_fire` (function) |
| `btech/mech.fire.c::inferno_burn` | General; AUD-HEAT; active | [systems/missile.py](../../systems/missile.py): `inferno_burn` (function) |
| `btech/mech.fire.c::inferno_end_event` | General; AUD-HEAT; active | [systems/missile.py](../../systems/missile.py): `_inferno_end_event` (function) |
| `btech/mech.fire.c::vehicle_burn_event` | General; AUD-HEAT; active | [systems/vehicle_fire.py](../../systems/vehicle_fire.py): `burn_event` (function) |
| `btech/mech.fire.c::vehicle_extinquish_fire` | General; AUD-HEAT; active | [systems/vehicle_fire.py](../../systems/vehicle_fire.py): `extinguish` (function) |
| `btech/mech.fire.c::vehicle_extinquish_fire_event` | General; AUD-HEAT; active | [systems/vehicle_fire.py](../../systems/vehicle_fire.py): `extinguish_event` (function) |
| `btech/mech.fire.c::vehicle_start_burn` | General; AUD-HEAT; active | [systems/vehicle_fire.py](../../systems/vehicle_fire.py): `start_burn` (function) |
| `btech/mech.fire.c::water_extinguish_inferno` | General; AUD-HEAT; active | [systems/missile.py](../../systems/missile.py): `water_extinguish_inferno` (function) |

<a id="c-btech-mech-hitloc-c"></a>

### `btech/mech.hitloc.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.hitloc.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.hitloc.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.hitloc.c::crittable` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `crittable` (function) |
| `btech/mech.hitloc.c::crittable` | Historical Aerospace; AUD-AEROSPACE; active | [systems/hit_locations.py](../../systems/hit_locations.py): `crittable` (function) |
| `btech/mech.hitloc.c::DoMotiveSystemHit` | General; AUD-PHYSICAL; active | [systems/vehicle_combat.py](../../systems/vehicle_combat.py): `motive_system_hit` (function) |
| `btech/mech.hitloc.c::FindAdvFasaVehicleHitLocation` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `find_hit_location` (function)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `advanced_location` (function) |
| `btech/mech.hitloc.c::FindAimHitLoc` | General; AUD-PHYSICAL; active | [systems/combat.py](../../systems/combat.py): `find_aim_hit_loc` (function)<br>[systems/combat.py](../../systems/combat.py): `_aim_fallback` (function)<br>[systems/combat.py](../../systems/combat.py): `_vehicle_aim_mask` (function) |
| `btech/mech.hitloc.c::FindAimHitLoc` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `find_aim_hit_loc` (function) |
| `btech/mech.hitloc.c::FindAreaHitGroup` | General; AUD-PHYSICAL; active | [systems/combat.py](../../systems/combat.py): `determine_hit_group` (function)<br>[systems/combat.py](../../systems/combat.py): `get_hit_arc_half_widths` (function)<br>[systems/combat.py](../../systems/combat.py): `find_attack_direction` (function) |
| `btech/mech.hitloc.c::FindAreaHitGroup` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `determine_hit_group` (function) |
| `btech/mech.hitloc.c::FindFasaHitLocation` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `find_hit_location` (function)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `ground_location` (function; selector `FASA`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `vtol_location` (function; selector `FASA`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `naval_location` (function; selector `FASA`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `aero_location` (function; selector `FASA`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `dropship_location` (function; selector `FASA`) |
| `btech/mech.hitloc.c::FindFasaHitLocation` | Historical Aerospace; AUD-AEROSPACE; active | [systems/hit_locations.py](../../systems/hit_locations.py): `find_hit_location/aero_location/dropship_location` (function)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `aero_location/dropship_location` (function) |
| `btech/mech.hitloc.c::FindHitLocation` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `find_hit_location` (function)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `ground_location` (function; selector `legacy`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `vtol_location` (function; selector `legacy`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `naval_location` (function; selector `legacy`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `aero_location` (function; selector `legacy`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `dropship_location` (function; selector `legacy`) |
| `btech/mech.hitloc.c::FindHitLocation` | Historical Aerospace; AUD-AEROSPACE; active | [systems/hit_locations.py](../../systems/hit_locations.py): `find_hit_location/aero_location/dropship_location` (function)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `aero_location/dropship_location` (function) |
| `btech/mech.hitloc.c::FindHitLocation_CritProof` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `find_hit_location` (function)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `ground_location` (function; selector `critproof`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `vtol_location` (function; selector `critproof`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `naval_location` (function; selector `critproof`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `aero_location` (function; selector `critproof`)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `dropship_location` (function; selector `critproof`) |
| `btech/mech.hitloc.c::FindHitLocation_CritProof` | Historical Aerospace; AUD-AEROSPACE; active | [systems/hit_locations.py](../../systems/hit_locations.py): `find_hit_location/aero_location/dropship_location` (function)<br>[systems/hit_locations.py](../../systems/hit_locations.py): `aero_location/dropship_location` (function) |
| `btech/mech.hitloc.c::FindKickLocation` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `physical_location` (function) |
| `btech/mech.hitloc.c::findNARCHitLoc` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `narc_hit_location` (function) |
| `btech/mech.hitloc.c::FindPunchLocation` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `physical_location` (function) |
| `btech/mech.hitloc.c::FindSwarmHitLocation` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `swarm_hit_location` (function) |
| `btech/mech.hitloc.c::FindTargetHitLoc` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `target_hit_location` (function) |
| `btech/mech.hitloc.c::FindTCHitLoc` | General; AUD-PHYSICAL; active | [systems/combat.py](../../systems/combat.py): `find_tc_hit_loc` (function)<br>[systems/combat.py](../../systems/combat.py): `_aim_fallback` (function)<br>[systems/combat.py](../../systems/combat.py): `_vehicle_aim_mask` (function) |
| `btech/mech.hitloc.c::FindTCHitLoc` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `find_tc_hit_loc` (function) |
| `btech/mech.hitloc.c::get_bsuit_hitloc` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `live_suit_hit_location` (function) |
| `btech/mech.hitloc.c::ModifyHeadHit` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `modify_head_hit` (function) |
| `btech/mech.hitloc.c::TransferTarget` | General; AUD-PHYSICAL; active | [systems/hit_locations.py](../../systems/hit_locations.py): `transfer_target` (function) |
| `btech/mech.hitloc.c::TransferTarget` | Historical Aerospace; AUD-AEROSPACE; active | [systems/hit_locations.py](../../systems/hit_locations.py): `transfer_target` (function) |

<a id="c-btech-mech-ice-c"></a>

### `btech/mech.ice.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.ice.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.ice.c::break_sub` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `break_surface` (function) |
| `btech/mech.ice.c::break_thru_ice` | General; AUD-MOVEMENT; active | [physics/movement.py](../../physics/movement.py): `break_thru_ice` (function) |
| `btech/mech.ice.c::drop_thru_ice` | General; AUD-MOVEMENT; active | [physics/movement.py](../../physics/movement.py): `drop_thru_ice` (function) |
| `btech/mech.ice.c::growable` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `growable` (function) |
| `btech/mech.ice.c::growable_callback` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `growable` (inline) |
| `btech/mech.ice.c::ice_growth` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `_evolve` (function)<br>[physics/ice.py](../../physics/ice.py): `ice_growth` (function)<br>[physics/ice.py](../../physics/ice.py): `_ice_command` (inline) |
| `btech/mech.ice.c::ice_melt` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `_evolve` (function)<br>[physics/ice.py](../../physics/ice.py): `ice_melt` (function)<br>[physics/ice.py](../../physics/ice.py): `_ice_command` (inline) |
| `btech/mech.ice.c::map_addice` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `_ice_command` (function)<br>[physics/ice.py](../../physics/ice.py): `map_addice` (function) |
| `btech/mech.ice.c::map_delice` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `_ice_command` (function)<br>[physics/ice.py](../../physics/ice.py): `map_delice` (function) |
| `btech/mech.ice.c::meltable` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `meltable` (function) |
| `btech/mech.ice.c::meltable_callback` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `meltable` (inline) |
| `btech/mech.ice.c::possibly_blow_bridge` | General; AUD-MOVEMENT; active | [systems/combat.py](../../systems/combat.py): `possibly_blow_bridge` (function)<br>[physics/ice.py](../../physics/ice.py): `blast_surface` (function) |
| `btech/mech.ice.c::possibly_blow_ice` | General; AUD-MOVEMENT; active | [systems/combat.py](../../systems/combat.py): `possibly_blow_ice` (function)<br>[physics/ice.py](../../physics/ice.py): `blast_surface` (function) |
| `btech/mech.ice.c::possibly_drop_thru_ice` | General; AUD-MOVEMENT; active | [physics/movement.py](../../physics/movement.py): `possibly_drop_thru_ice` (function) |
| `btech/mech.ice.c::swim_except` | General; AUD-MOVEMENT; active | [physics/ice.py](../../physics/ice.py): `break_surface` (inline) |

<a id="c-btech-mech-lite-c"></a>

### `btech/mech.lite.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.lite.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.lite.c::cause_lite` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `cause_lite` (function) |
| `btech/mech.lite.c::end_lite_check` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `end_lite_check` (function)<br>[core/game_loop.py](../../core/game_loop.py): `mech_update` (inline) |
| `btech/mech.lite.c::mech_lites_target` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `mech_lites_target` (function) |

<a id="c-btech-mech-los-c"></a>

### `btech/mech.los.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.los.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.los.c::ActualElevation` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `actual_elevation` (function) |
| `btech/mech.los.c::AddTerrainMod` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `add_terrain_mod` (function) |
| `btech/mech.los.c::CalculateLOSFlag` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `calculate_los_flag` (function) |
| `btech/mech.los.c::InLineOfSight` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `in_line_of_sight` (function) |
| `btech/mech.los.c::InLineOfSight_NB` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `in_line_of_sight_nb` (function) |
| `btech/mech.los.c::mech_losemit` | General; AUD-SENSORS; active | [tools/sensors_los.py](../../tools/sensors_los.py): `SensorSession.command` (dispatch)<br>[systems/sensors.py](../../systems/sensors.py): `los_broadcast` (function) |

<a id="c-btech-mech-maps-c"></a>

### `btech/mech.maps.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.maps.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.maps.c::add_color` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `colored_character` (function) |
| `btech/mech.maps.c::colourize_tac_map` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `color_rows` (function) |
| `btech/mech.maps.c::get_lrshexstr` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `lrs.glyph` (inline) |
| `btech/mech.maps.c::GetLRSMech` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `lrs.glyph(unit)` (inline) |
| `btech/mech.maps.c::GetLRSMechChar` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `lrs_glyph` (function) |
| `btech/mech.maps.c::GetTerrainName` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `tactical(navigate terrain label)` (inline)<br>[entities/map.py](../../entities/map.py): `GameMap.terrain` (method) |
| `btech/mech.maps.c::GetTerrainName_base` | General; AUD-HUD; active | [entities/map.py](../../entities/map.py): `_TERRAIN_NAMES / get_terrain_name_base` (data/table) |
| `btech/mech.maps.c::is_oddcol` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `column parity`) |
| `btech/mech.maps.c::LRSElevation` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `lrs.glyph(elevation)` (inline) |
| `btech/mech.maps.c::LRSTerrain` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `lrs.glyph(terrain)` (inline) |
| `btech/mech.maps.c::MakeMapText` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (function)<br>[systems/map_display.py](../../systems/map_display.py): `tactical` (inline; selector `color postpass`) |
| `btech/mech.maps.c::mech_enter_event` | General; AUD-HUD; active | [systems/hangar.py](../../systems/hangar.py): `enter_event` (function) |
| `btech/mech.maps.c::mech_enterbase` | General; AUD-HUD; active | [systems/hangar.py](../../systems/hangar.py): `condition_error/destination/lock_error/enter_base` (function) |
| `btech/mech.maps.c::mech_findcenter` | General; AUD-HUD; active | [systems/turrets.py](../../systems/turrets.py): `delegate(findcenter)` (dispatch; selector `findcenter`) |
| `btech/mech.maps.c::mech_lrsmap` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `lrs` (function) |
| `btech/mech.maps.c::mech_navigate` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `tactical` (dispatch; selector `navigate=True`)<br>[systems/targeting.py](../../systems/targeting.py): `navigate_sketch_mechs` (function) |
| `btech/mech.maps.c::mech_tacmap` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `tactical` (dispatch; selector `navigate=False`) |
| `btech/mech.maps.c::parse_tacargs` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `select_center` (function) |
| `btech/mech.maps.c::set_colorscheme` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `palette` (function) |
| `btech/mech.maps.c::show_lrs_map` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `lrs` (inline; selector `LRS rendering`) |
| `btech/mech.maps.c::sketch_tac_cliffs` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `modes c/t`) |
| `btech/mech.maps.c::sketch_tac_ds` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch.ds_hex` (inline; selector `dropship cell`) |
| `btech/mech.maps.c::sketch_tac_dslz` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `mode b`) |
| `btech/mech.maps.c::sketch_tac_map` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `terrain and LOS cells`) |
| `btech/mech.maps.c::sketch_tac_mechs` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `contact and dropship overlay`) |
| `btech/mech.maps.c::sketch_tac_mines` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `mode m`) |
| `btech/mech.maps.c::sketch_tac_ownmech` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `own-mech prepass`) |
| `btech/mech.maps.c::sketch_tac_row` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `base rows`) |
| `btech/mech.maps.c::tac_dispcols` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch` (inline; selector `display width`) |
| `btech/mech.maps.c::tac_hex_offset` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `sketch.offset` (inline; selector `hex offsets`) |
| `btech/mech.maps.c::TerrainColorChar` | General; AUD-HUD; active | [systems/map_display.py](../../systems/map_display.py): `terrain_color` (function) |

<a id="c-btech-mech-mechref-ident-c"></a>

### `btech/mech.mechref_ident.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.mechref_ident.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.mechref_ident.c::find_mechname_by_mechref` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `identify` (function)<br>[data/construction_tables.py](../../data/construction_tables.py): `MECH_REFERENCES` (data/table) |

<a id="c-btech-mech-move-c"></a>

### `btech/mech.move.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.move.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.move.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.move.c::cause_damage` | General; AUD-MOVEMENT; active | [physics/collision.py](../../physics/collision.py): `cause_damage` (function) |
| `btech/mech.move.c::domino_space` | General; AUD-MOVEMENT; active | [physics/collision.py](../../physics/collision.py): `domino_space` (function) |
| `btech/mech.move.c::domino_space_in_hex` | General; AUD-MOVEMENT; active | [physics/collision.py](../../physics/collision.py): `domino_space_in_hex` (function) |
| `btech/mech.move.c::DropGetElevation` | General; AUD-MOVEMENT; active | [physics/movement.py](../../physics/movement.py): `drop_get_elevation` (function) |
| `btech/mech.move.c::DropSetElevation` | General; AUD-MOVEMENT; active | [physics/movement.py](../../physics/movement.py): `drop_set_elevation` (function) |
| `btech/mech.move.c::LandMech` | General; AUD-MOVEMENT; active | [physics/jump.py](../../physics/jump.py): `land_mech` (function)<br>[physics/jump.py](../../physics/jump.py): `_jumpstabil_callback` (function) |
| `btech/mech.move.c::LateralDesc` | General; AUD-MOVEMENT; active | [systems/maneuver.py](../../systems/maneuver.py): `LATERAL_NAMES` (data/table)<br>[systems/status_display.py](../../systems/status_display.py): `lateral_description` (function) |
| `btech/mech.move.c::mech_bootlegger` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `bootlegger` (function) |
| `btech/mech.move.c::mech_dodge` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `_mode_complete` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `set_mode` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `set_mode ordered guards` (inline)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `schedule_mode` (function) |
| `btech/mech.move.c::mech_drop` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `prone` (function) |
| `btech/mech.move.c::mech_eta` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `eta` (function) |
| `btech/mech.move.c::mech_evade` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `_mode_complete` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `set_mode` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `set_mode ordered guards` (inline)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `schedule_mode` (function) |
| `btech/mech.move.c::mech_heading` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `heading` (function) |
| `btech/mech.move.c::mech_hulldown` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `hulldown` (function) |
| `btech/mech.move.c::mech_hulldown_event` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `_hulldown_complete` (function) |
| `btech/mech.move.c::mech_jump` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `jump_command` (function)<br>[physics/jump.py](../../physics/jump.py): `mech_jump` (function)<br>[physics/jump.py](../../physics/jump.py): `update_jump` (function)<br>[physics/jump.py](../../physics/jump.py): `can_jump` (function)<br>[physics/jump.py](../../physics/jump.py): `get_jump_mp` (function)<br>[physics/jump.py](../../physics/jump.py): `_jump_event_callback` (function)<br>[physics/jump.py](../../physics/jump.py): `calculate_odd_jump_altitude` (function) |
| `btech/mech.move.c::mech_land` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `land` (function)<br>[physics/aerospace.py](../../physics/aerospace.py): `land` (function) |
| `btech/mech.move.c::mech_lateral` | General; AUD-MOVEMENT; active | [systems/maneuver.py](../../systems/maneuver.py): `lateral_event` (function)<br>[systems/maneuver.py](../../systems/maneuver.py): `set_lateral` (function)<br>[systems/maneuver.py](../../systems/maneuver.py): `can_move_laterally` (function)<br>[systems/maneuver.py](../../systems/maneuver.py): `_parse_lateral_mode` (function)<br>[systems/maneuver.py](../../systems/maneuver.py): `sideslip_event` (function) |
| `btech/mech.move.c::mech_rotatetorso` | General; AUD-MOVEMENT; active | [systems/maneuver.py](../../systems/maneuver.py): `rotate_torso` (function) |
| `btech/mech.move.c::mech_speed` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `speed` (function) |
| `btech/mech.move.c::mech_sprint` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `_mode_complete` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `set_mode` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `set_mode ordered guards` (inline)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `schedule_mode` (function) |
| `btech/mech.move.c::mech_stand` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `stand` (function)<br>[physics/jump.py](../../physics/jump.py): `stand_up` (function)<br>[physics/jump.py](../../physics/jump.py): `can_stand` (function)<br>[physics/jump.py](../../physics/jump.py): `_stand_done` (function)<br>[physics/jump.py](../../physics/jump.py): `_stand_recovered` (function) |
| `btech/mech.move.c::mech_thrash` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `thrash` (function) |
| `btech/mech.move.c::mech_turnmode` | General; AUD-MOVEMENT; active | [systems/maneuver.py](../../systems/maneuver.py): `set_turnmode` (function) |
| `btech/mech.move.c::mech_turret` | General; AUD-MOVEMENT; active | [systems/maneuver.py](../../systems/maneuver.py): `set_turret` (function) |
| `btech/mech.move.c::mech_vertical` | General; AUD-MOVEMENT; active | [systems/movement_commands.py](../../systems/movement_commands.py): `vertical` (function)<br>[physics/movement.py](../../physics/movement.py): `move_mech` (function) |
| `btech/mech.move.c::MechCargoMaxSpeed` | General; AUD-MOVEMENT; active | [physics/cargo.py](../../physics/cargo.py): `cargo_max_speed` (function)<br>[physics/cargo.py](../../physics/cargo.py): `_base_speed` (function)<br>[physics/cargo.py](../../physics/cargo.py): `_loaded_speed` (function)<br>[physics/cargo.py](../../physics/cargo.py): `_carried_mass` (function)<br>[physics/cargo.py](../../physics/cargo.py): `_adjusted_mass` (function)<br>[physics/cargo.py](../../physics/cargo.py): `_boosted_speed` (function) |
| `btech/mech.move.c::MechCargoMaxSpeed` | Historical Aerospace; AUD-AEROSPACE; active | [physics/cargo.py](../../physics/cargo.py): `cargo_max_speed and mass/cache helpers` (inline/use) |
| `btech/mech.move.c::MechFalls` | General; AUD-MOVEMENT; active | [physics/jump.py](../../physics/jump.py): `mech_falls` (function)<br>[physics/jump.py](../../physics/jump.py): `_interrupt_movement` (function)<br>[physics/jump.py](../../physics/jump.py): `_fall_damage` (function)<br>[physics/jump.py](../../physics/jump.py): `_apply_damage` (function) |
| `btech/mech.move.c::MechFloods` | General; AUD-MOVEMENT; active | [physics/flooding.py](../../physics/flooding.py): `flood_unit` (function) |
| `btech/mech.move.c::MechFloodsLoc` | General; AUD-MOVEMENT; active | [physics/flooding.py](../../physics/flooding.py): `flood_location` (function)<br>[systems/damage.py](../../systems/damage.py): `destroy_parts` (function) |
| `btech/mech.move.c::mechs_in_hex` | General; AUD-MOVEMENT; active | [physics/collision.py](../../physics/collision.py): `mechs_in_hex` (function) |

<a id="c-btech-mech-notify-c"></a>

### `btech/mech.notify.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.notify.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.notify.c::ccode` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `color_code` (function) |
| `btech/mech.notify.c::common_checks` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `common_checks` (function)<br>[systems/startup.py](../../systems/startup.py): `shutdown` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.notify.c::do_scramble` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `do_scramble` (function) |
| `btech/mech.notify.c::findCommLink` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `find_comm_link` (function) |
| `btech/mech.notify.c::GetAmmoDesc_Model_Mode` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `ammo_description` (function)<br>[systems/network_reports.py](../../systems/network_reports.py): `AMMO_DESCRIPTIONS` (data/table) |
| `btech/mech.notify.c::GetArcID` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `arc_label` (function) |
| `btech/mech.notify.c::GetMechID` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `unit_identity` (function) |
| `btech/mech.notify.c::GetMechToMechID` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `identity` (function) |
| `btech/mech.notify.c::GetMechToMechID_base` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `identity_base` (function) |
| `btech/mech.notify.c::GetMoveTypeID` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `move_type` (function) |
| `btech/mech.notify.c::GetWeaponAmmoModeLetter` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `slot_ammo_letter` (function)<br>[systems/status_display.py](../../systems/status_display.py): `weapon_display ammo-mode wrapper` (inline) |
| `btech/mech.notify.c::GetWeaponAmmoModeLetter_Model_Mode` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `ammo_letter` (function)<br>[systems/network_reports.py](../../systems/network_reports.py): `AMMO_LETTERS` (data/table) |
| `btech/mech.notify.c::GetWeaponFireModeLetter` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `slot_fire_letter` (function)<br>[systems/status_display.py](../../systems/status_display.py): `weapon_display fire-mode wrapper` (inline) |
| `btech/mech.notify.c::GetWeaponFireModeLetter_Model_Mode` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `fire_letter` (function) |
| `btech/mech.notify.c::HexLOSBroadcast` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `hex_broadcast` (function)<br>[systems/artillery.py](../../systems/artillery.py): `hex_los_broadcast` (function) |
| `btech/mech.notify.c::MapBroadcast` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `map_broadcast` (function)<br>[systems/map_management.py](../../systems/map_management.py): `emit` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.diagnose` (dispatch; selector `map-broadcast`) |
| `btech/mech.notify.c::MapLimitedBroadcast2d` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `limited_broadcast` (function)<br>[physics/hexmath.py](../../physics/hexmath.py): `find_range3d` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.diagnose` (dispatch; selector `limited-broadcast dimensions=2`) |
| `btech/mech.notify.c::MapLimitedBroadcast3d` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `limited_broadcast` (function)<br>[physics/hexmath.py](../../physics/hexmath.py): `find_range3d` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.diagnose` (dispatch; selector `limited-broadcast dimensions=3`) |
| `btech/mech.notify.c::mech_list_freqs` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `list_frequencies` (function) |
| `btech/mech.notify.c::mech_notify` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `mech_notify` (function)<br>[systems/notifications.py](../../systems/notifications.py): `deliver` (function)<br>[systems/notifications.py](../../systems/notifications.py): `personal_notify` (function)<br>[systems/occupants.py](../../systems/occupants.py): `Personnel.contents` (method)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `notify` (function) |
| `btech/mech.notify.c::mech_printf` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `mech_printf` (function)<br>[systems/notifications.py](../../systems/notifications.py): `deliver` (function) |
| `btech/mech.notify.c::mech_radio` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `directed_radio` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.notify.c::mech_sendchannel` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `send_channel` (function)<br>[systems/communications.py](../../systems/communications.py): `parse_attributes` (function)<br>[systems/communications.py](../../systems/communications.py): `parse_channel_send` (function)<br>[systems/communications.py](../../systems/communications.py): `crew_stunned` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.command` (method) |
| `btech/mech.notify.c::mech_set_channelfreq` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `set_frequency` (function) |
| `btech/mech.notify.c::mech_set_channelmode` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `set_mode` (function) |
| `btech/mech.notify.c::mech_set_channeltitle` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `set_title` (function) |
| `btech/mech.notify.c::Mech_ShowFlags` | General; AUD-COMMS; active | [systems/network_reports.py](../../systems/network_reports.py): `show_flags` (function) |
| `btech/mech.notify.c::MechBroadcast` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `map_broadcast` (function)<br>[tools/communications.py](../../tools/communications.py): `CommunicationsSession.diagnose` (dispatch; selector `mech-broadcast`) |
| `btech/mech.notify.c::MechFireBroadcast` | General; AUD-COMMS; active | [systems/combat_firing.py](../../systems/combat_firing.py): `announce_shot` (function)<br>[systems/combat.py](../../systems/combat.py): `fire_weapon announcement dispatch` (inline)<br>[systems/notifications.py](../../systems/notifications.py): `identity` (function) |
| `btech/mech.notify.c::MechLOSBroadcast` | General; AUD-COMMS; active | [systems/sensors.py](../../systems/sensors.py): `los_broadcast` (function)<br>[systems/sensors.py](../../systems/sensors.py): `possibly_see_mech` (function)<br>[systems/notifications.py](../../systems/notifications.py): `identity` (function) |
| `btech/mech.notify.c::MechLOSBroadcasti` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `pair_los_broadcast` (function)<br>[systems/physical.py](../../systems/physical.py): `_physical_broadcast` (function) |
| `btech/mech.notify.c::MechSeesHex` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `sees_hex` (function)<br>[systems/targeting.py](../../systems/targeting.py): `find_mech_in_hex` (inline)<br>[systems/artillery.py](../../systems/artillery.py): `artillery_friendly_adjustment` (inline) |
| `btech/mech.notify.c::MechSeesHexF` | General; AUD-COMMS; active | [systems/notifications.py](../../systems/notifications.py): `sees_hex` (function)<br>[systems/targeting.py](../../systems/targeting.py): `find_range` (function)<br>[entities/map.py](../../entities/map.py): `GameMap.base_elevation` (method) |
| `btech/mech.notify.c::nonrecursive_commlink` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `route_graph` (function) |
| `btech/mech.notify.c::recursive_commlink` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `route_graph` (function) |
| `btech/mech.notify.c::ScrambleMessage` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `scramble_message` (function)<br>[systems/communications.py](../../systems/communications.py): `do_scramble` (function) |
| `btech/mech.notify.c::sendchannelstuff` | General; AUD-COMMS; active | [systems/communications.py](../../systems/communications.py): `transmit` (function)<br>[systems/communications.py](../../systems/communications.py): `scan` (function)<br>[systems/communications.py](../../systems/communications.py): `autopilot_receive` (function)<br>[systems/experience.py](../../systems/experience.py): `comm` (function)<br>[systems/experience.py](../../systems/experience.py): `award` (function) |

<a id="c-btech-mech-ood-c"></a>

### `btech/mech.ood.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.ood.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.ood.c::initiate_ood` | General; AUD-MOVEMENT; active | [physics/orbital.py](../../physics/orbital.py): `initiate_ood` (function) |
| `btech/mech.ood.c::mech_ood_damage` | General; AUD-MOVEMENT; active | [physics/orbital.py](../../physics/orbital.py): `cocoon_damage` (function)<br>[systems/combat.py](../../systems/combat.py): `apply_damage_with_transfer` (function) |
| `btech/mech.ood.c::mech_ood_event` | General; AUD-MOVEMENT; active | [physics/orbital.py](../../physics/orbital.py): `ood_event` (function)<br>[physics/orbital.py](../../physics/orbital.py): `fall_event` (function)<br>[physics/orbital.py](../../physics/orbital.py): `_touchdown_target` (function)<br>[physics/orbital.py](../../physics/orbital.py): `_touchdown_margin` (function)<br>[physics/orbital.py](../../physics/orbital.py): `_crash_battlesuit` (function)<br>[physics/orbital.py](../../physics/orbital.py): `_resolve_touchdown` (function)<br>[physics/orbital.py](../../physics/orbital.py): `_settle_touchdown` (function) |

<a id="c-btech-mech-partnames-c"></a>

### `btech/mech.partnames.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.partnames.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.partnames.c::create_brandname` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.generate` (method)<br>[data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.__init__` (method) |
| `btech/mech.partnames.c::find_matching_long_part` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.match` (method; selector `long`) |
| `btech/mech.partnames.c::find_matching_short_part` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.match` (method; selector `short`) |
| `btech/mech.partnames.c::find_matching_vlong_part` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.match` (method; selector `vlong`) |
| `btech/mech.partnames.c::fun` | General; AUD-TEMPLATES; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.partnames.c::fun_btpartmatch` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.partmatch` (method) |
| `btech/mech.partnames.c::fun_btpartname` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.partname` (method) |
| `btech/mech.partnames.c::get_parts_long_name` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.names` (method; selector `long`) |
| `btech/mech.partnames.c::get_parts_short_name` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.names` (method; selector `short`) |
| `btech/mech.partnames.c::get_parts_vlong_name` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.names` (method; selector `vlong`) |
| `btech/mech.partnames.c::initialize_partname_tables` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.__init__` (method) |
| `btech/mech.partnames.c::insert_sorted_brandname` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.__init__` (method; selector `stable sorted lists`) |
| `btech/mech.partnames.c::ListForms` | General; AUD-TEMPLATES; active | [tools/construction_templates.py](../../tools/construction_templates.py): `ConstructionSession.catalog_action` (method; selector `list`) |
| `btech/mech.partnames.c::partname_func` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.packed_name` (method) |

<a id="c-btech-mech-physical-c"></a>

### `btech/mech.physical.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.physical.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.physical.c::all_limbs_recycled` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `all_limbs_recycled` (function) |
| `btech/mech.physical.c::axe_checkArm` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `axe_check_arm` (function) |
| `btech/mech.physical.c::ChargeMech` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `charge_mech` (function)<br>[systems/physical.py](../../systems/physical.py): `_charge_damage_to_target` (function)<br>[systems/physical.py](../../systems/physical.py): `_apply_charge_clusters` (function)<br>[systems/physical.py](../../systems/physical.py): `_charge_recycle` (function)<br>[systems/physical.py](../../systems/physical.py): `_charge_bth_side` (function) |
| `btech/mech.physical.c::checkGrabClubLocation` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `check_grab_club_location` (function) |
| `btech/mech.physical.c::DeathFromAbove` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `dfa_attack` (function)<br>[systems/physical.py](../../systems/physical.py): `calculate_dfa_damage` (function)<br>[systems/physical.py](../../systems/physical.py): `can_dfa` (function)<br>[systems/physical.py](../../systems/physical.py): `_dfa_make_prone` (function) |
| `btech/mech.physical.c::get_arm_args` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `get_arm_args` (function)<br>[systems/physical.py](../../systems/physical.py): `physical_command arm token parser` (inline; selector `single-character B/L/R`)<br>[systems/physical.py](../../systems/physical.py): `mech_kickortrip default` (inline; selector `arm is None`) |
| `btech/mech.physical.c::have_axe` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `have_axe` (function) |
| `btech/mech.physical.c::have_claw` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `have_claw` (function) |
| `btech/mech.physical.c::have_mace` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `have_mace` (function) |
| `btech/mech.physical.c::have_punch` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `have_punch` (function) |
| `btech/mech.physical.c::have_saw` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `have_saw` (function) |
| `btech/mech.physical.c::have_sword` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `have_sword` (function) |
| `btech/mech.physical.c::int` | General; AUD-PHYSICAL; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.physical.c::mace_checkArm` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mace_check_arm` (function) |
| `btech/mech.physical.c::mech_axe` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_axe` (function)<br>[systems/physical.py](../../systems/physical.py): `_arm_command` (function; selector `mech_axe`)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `mech_axe`) |
| `btech/mech.physical.c::mech_charge` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_charge` (function)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `charge`) |
| `btech/mech.physical.c::mech_claw` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_claw` (function)<br>[systems/physical.py](../../systems/physical.py): `_arm_command` (function; selector `mech_claw`)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `mech_claw`) |
| `btech/mech.physical.c::mech_club` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_club` (function)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `club`) |
| `btech/mech.physical.c::mech_grabclub` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_grabclub` (function)<br>[systems/physical.py](../../systems/physical.py): `check_grab_club_location` (function)<br>[systems/physical.py](../../systems/physical.py): `drop_club` (function)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `grabclub`) |
| `btech/mech.physical.c::mech_kick` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_kick` (function) |
| `btech/mech.physical.c::mech_kickortrip` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_kickortrip` (function)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `kick/trip`) |
| `btech/mech.physical.c::mech_mace` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_mace` (function)<br>[systems/physical.py](../../systems/physical.py): `_arm_command` (function; selector `mech_mace`)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `mech_mace`) |
| `btech/mech.physical.c::mech_punch` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_punch` (function)<br>[systems/physical.py](../../systems/physical.py): `_arm_command` (function; selector `mech_punch`)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `mech_punch`) |
| `btech/mech.physical.c::mech_saw` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_saw` (function)<br>[systems/physical.py](../../systems/physical.py): `_arm_command` (function; selector `mech_saw`)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `mech_saw`) |
| `btech/mech.physical.c::mech_sword` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_sword` (function)<br>[systems/physical.py](../../systems/physical.py): `_arm_command` (function; selector `mech_sword`)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `mech_sword`) |
| `btech/mech.physical.c::mech_trip` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `mech_trip` (function) |
| `btech/mech.physical.c::phys_common_checks` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `phys_common_checks` (function) |
| `btech/mech.physical.c::phys_fail` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `phys_fail` (function) |
| `btech/mech.physical.c::phys_form` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `phys_form` (function)<br>[systems/physical.py](../../systems/physical.py): `PHYS_FORM` (data/table) |
| `btech/mech.physical.c::phys_succeed` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `phys_succeed` (function) |
| `btech/mech.physical.c::PhysicalAttack` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `physical_attack` (function)<br>[systems/physical.py](../../systems/physical.py): `physical_command` (function; selector `physical attack commands`)<br>[systems/physical.py](../../systems/physical.py): `set_recycle_limb` (function) |
| `btech/mech.physical.c::PhysicalDamage` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `physical_damage` (function) |
| `btech/mech.physical.c::PhysicalTrip` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `physical_trip` (function) |
| `btech/mech.physical.c::punch_checkArm` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `punch_check_arm` (function) |
| `btech/mech.physical.c::saw_checkArm` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `saw_check_arm` (function) |
| `btech/mech.physical.c::sword_checkArm` | General; AUD-PHYSICAL; active | [systems/physical.py](../../systems/physical.py): `sword_check_arm` (function) |

<a id="c-btech-mech-pickup-c"></a>

### `btech/mech.pickup.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.pickup.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.pickup.c::mech_attachcables` | General; PILOT-REPAIR; active | [systems/towing.py](../../systems/towing.py): `attach_cables` (function)<br>[systems/towing.py](../../systems/towing.py): `attach_relation` (function) |
| `btech/mech.pickup.c::mech_detachcables` | General; PILOT-REPAIR; active | [systems/towing.py](../../systems/towing.py): `detach_cables` (function) |
| `btech/mech.pickup.c::mech_dropoff` | General; PILOT-REPAIR; active | [systems/towing.py](../../systems/towing.py): `dropoff` (function)<br>[systems/damage.py](../../systems/damage.py): `release_tow` (function)<br>[systems/towing.py](../../systems/towing.py): `release_with_debug` (function) |
| `btech/mech.pickup.c::mech_pickup` | General; PILOT-REPAIR; active | [systems/occupants.py](../../systems/occupants.py): `pickup` (function)<br>[systems/towing.py](../../systems/towing.py): `pickup_unit` (function)<br>[systems/towing.py](../../systems/towing.py): `attach_relation` (function)<br>[systems/swarm.py](../../systems/swarm.py): `mirror` (function) |

<a id="c-btech-mech-restrict-c"></a>

### `btech/mech.restrict.c`

[Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.restrict.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.restrict.c::mech_Rsetmapindex` | Historical Aerospace; AUD-AEROSPACE; active | [systems/map_transitions.py](../../systems/map_transitions.py): `transfer` (function)<br>[systems/map_membership.py](../../systems/map_membership.py): `add/remove` (function) |
| `btech/mech.restrict.c::mech_Rsetxy` | Historical Aerospace; AUD-AEROSPACE; active | [systems/dropships.py](../../systems/dropships.py): `set_xy` (function) |

<a id="c-btech-mech-scan-c"></a>

### `btech/mech.scan.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.scan.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.scan.c::mech_bearing` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `navigation` (dispatch; selector `kind=bearing`) |
| `btech/mech.scan.c::mech_range` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `navigation` (dispatch; selector `kind=range`) |
| `btech/mech.scan.c::mech_report` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `scan` (dispatch; selector `report=True`) |
| `btech/mech.scan.c::mech_scan` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `scan` (dispatch; selector `report=False`)<br>[systems/observation.py](../../systems/observation.py): `scan_effects` (function) |
| `btech/mech.scan.c::mech_sight` | General; AUD-HUD; active | [tools/sensors_los.py](../../tools/sensors_los.py): `SensorSession.command` (dispatch; selector `sight`)<br>[systems/turrets.py](../../systems/turrets.py): `delegate` (dispatch; selector `sight`)<br>[systems/combat.py](../../systems/combat.py): `fire_weapon_number` (function)<br>[systems/combat_firing.py](../../systems/combat_firing.py): `fire_number` (function) |
| `btech/mech.scan.c::mech_vector` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `navigation` (dispatch; selector `kind=vector`) |
| `btech/mech.scan.c::mech_view` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `view` (function) |
| `btech/mech.scan.c::PrintEnemyStatus` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `scan` (inline; selector `selected enemy status output`) |
| `btech/mech.scan.c::PrintEnemyWeaponStatus` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `weapon_display` (inline; selector `refresh`)<br>[systems/status_display.py](../../systems/status_display.py): `weapon_display` (dispatch; selector `owner=False`) |
| `btech/mech.scan.c::PrintReport` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `report_lines` (function)<br>[systems/observation.py](../../systems/observation.py): `unit_report` (function) |
| `btech/mech.scan.c::ShowTurretFacing` | General; AUD-HUD; active | [systems/observation.py](../../systems/observation.py): `turret_facing` (function)<br>[systems/observation.py](../../systems/observation.py): `report_lines` (inline; selector `turret text`) |

<a id="c-btech-mech-sensor-c"></a>

### `btech/mech.sensor.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.sensor.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.sensor.c::add_sensor_info` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `sensor_mode_name` (function) |
| `btech/mech.sensor.c::CanChangeTo` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `can_change_to` (function) |
| `btech/mech.sensor.c::mech_sensor` | General; AUD-SENSORS; active | [tools/sensors_los.py](../../tools/sensors_los.py): `SensorSession.command` (method)<br>[systems/targeting.py](../../systems/targeting.py): `set_sensors` (function) |
| `btech/mech.sensor.c::mech_sensorchange_event` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `sensor_change_event` (function) |
| `btech/mech.sensor.c::mech_unblind_event` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `mech_unblind` (function) |
| `btech/mech.sensor.c::mechSensorInfo` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `sensor_info` (function) |
| `btech/mech.sensor.c::my_dump_flag` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `dump_flag` (function) |
| `btech/mech.sensor.c::possibly_see_mech` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `possibly_see_mech` (function)<br>[systems/sensors.py](../../systems/sensors.py): `los_broadcast` (function) |
| `btech/mech.sensor.c::ScrambleInfraAndLiteAmp` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `scramble_infra_and_liteamp` (function) |
| `btech/mech.sensor.c::Sensor_ArcBaseChance` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `sensor_arc_base_chance` (function) |
| `btech/mech.sensor.c::Sensor_CanSee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `sensor_can_see` (function) |
| `btech/mech.sensor.c::sensor_check` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `sensor_check` (function) |
| `btech/mech.sensor.c::Sensor_DoWeSeeNow` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `sensor_do_we_see_now` (function)<br>[systems/sensors.py](../../systems/sensors.py): `contact_notice` (function) |
| `btech/mech.sensor.c::Sensor_DriverBaseChance` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `sensor_driver_base_chance` (function) |
| `btech/mech.sensor.c::sensor_light_availability_check` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `sensor_light_availability_check` (function)<br>[entities/map.py](../../entities/map.py): `map_update` (function) |
| `btech/mech.sensor.c::sensor_mode` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `sensor_mode` (function) |
| `btech/mech.sensor.c::sensor_mode_name` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `sensor_mode_name` (function) |
| `btech/mech.sensor.c::Sensor_Sees` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `sensor_sees` (function) |
| `btech/mech.sensor.c::Sensor_SeesNow` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `sensor_sees_now` (function) |
| `btech/mech.sensor.c::Sensor_ToHitBonus` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `sensor_to_hit_bonus` (function) |
| `btech/mech.sensor.c::set_sensor` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `set_sensors` (function) |
| `btech/mech.sensor.c::show_sensor` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `show_sensor` (function) |
| `btech/mech.sensor.c::update_LOSinfo` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `_update_losinfo_pair` (function)<br>[systems/sensors.py](../../systems/sensors.py): `update_los_info` (function) |
| `btech/mech.sensor.c::valid_to_notice` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `valid_to_notice` (function)<br>[systems/sensors.py](../../systems/sensors.py): `contact_notice` (function) |

<a id="c-btech-mech-sensor-functions-c"></a>

### `btech/mech.sensor.functions.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.sensor.functions.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.sensor.functions.c::bap_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `bap_csee` (function) |
| `btech/mech.sensor.functions.c::bap_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `bap_see` (function) |
| `btech/mech.sensor.functions.c::bap_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `bap_tohit` (function) |
| `btech/mech.sensor.functions.c::blood_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `blood_csee` (function) |
| `btech/mech.sensor.functions.c::blood_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `blood_see` (function) |
| `btech/mech.sensor.functions.c::blood_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `blood_tohit` (function) |
| `btech/mech.sensor.functions.c::electrom_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `electrom_csee` (function) |
| `btech/mech.sensor.functions.c::electrom_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `electrom_see` (function) |
| `btech/mech.sensor.functions.c::electrom_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `electrom_tohit` (function) |
| `btech/mech.sensor.functions.c::infrared_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `infrared_csee` (function) |
| `btech/mech.sensor.functions.c::infrared_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `infrared_see` (function) |
| `btech/mech.sensor.functions.c::infrared_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `infrared_tohit` (function) |
| `btech/mech.sensor.functions.c::liteamp_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `liteamp_csee` (function) |
| `btech/mech.sensor.functions.c::liteamp_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `liteamp_see` (function) |
| `btech/mech.sensor.functions.c::liteamp_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `liteamp_tohit` (function) |
| `btech/mech.sensor.functions.c::radar_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `radar_csee` (function) |
| `btech/mech.sensor.functions.c::radar_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `radar_see` (function) |
| `btech/mech.sensor.functions.c::radar_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `radar_tohit` (function) |
| `btech/mech.sensor.functions.c::seismic_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `seismic_csee` (function) |
| `btech/mech.sensor.functions.c::seismic_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `seismic_see` (function) |
| `btech/mech.sensor.functions.c::seismic_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `seismic_tohit` (function) |
| `btech/mech.sensor.functions.c::vislight_csee` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `vislight_csee` (function) |
| `btech/mech.sensor.functions.c::vislight_see` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `vislight_see` (function) |
| `btech/mech.sensor.functions.c::vislight_tohit` | General; AUD-SENSORS; active | [systems/sensors.py](../../systems/sensors.py): `vislight_tohit` (function) |

<a id="c-btech-mech-spot-c"></a>

### `btech/mech.spot.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.spot.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.spot.c::ClearFireAdjustments` | General; AUD-SENSORS; active | [systems/spot.py](../../systems/spot.py): `clear_fire_adjustments` (function) |
| `btech/mech.spot.c::FireSpot` | General; AUD-SENSORS; active | [systems/spot.py](../../systems/spot.py): `fire_spot` (function) |
| `btech/mech.spot.c::IsArtyMech` | General; AUD-SENSORS; active | [systems/spot.py](../../systems/spot.py): `is_artillery_mech` (function) |
| `btech/mech.spot.c::mech_check_range` | General; AUD-SENSORS; active | [systems/spot.py](../../systems/spot.py): `spot_check_event` (function) |
| `btech/mech.spot.c::mech_spot` | General; AUD-SENSORS; active | [systems/spot.py](../../systems/spot.py): `mech_spot` (function) |
| `btech/mech.spot.c::mech_spot_event` | General; AUD-SENSORS; active | [systems/spot.py](../../systems/spot.py): `spot_lock_event` (function) |

<a id="c-btech-mech-startup-c"></a>

### `btech/mech.startup.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.startup.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.startup.c::mech_shutdown` | General; AUD-CORE; active | [systems/startup.py](../../systems/startup.py): `shutdown` (function)<br>[systems/startup.py](../../systems/startup.py): `shutdown_state` (function)<br>[systems/targeting.py](../../systems/targeting.py): `stop_tag` (function)<br>[systems/swarm.py](../../systems/swarm.py): `detach` (function)<br>[systems/damage.py](../../systems/damage.py): `release_tow` (function)<br>[physics/jump.py](../../physics/jump.py): `mech_falls` (function)<br>[physics/collision.py](../../physics/collision.py): `domino_space` (function) |
| `btech/mech.startup.c::mech_startup` | General; AUD-CORE; active | [systems/startup.py](../../systems/startup.py): `startup` (function)<br>[systems/startup.py](../../systems/startup.py): `starting` (function)<br>[systems/startup.py](../../systems/startup.py): `stage_interval` (function)<br>[systems/combat_commands.py](../../systems/combat_commands.py): `command_guard` (function)<br>[systems/piloting.py](../../systems/piloting.py): `fix_pilotdamage` (function) |
| `btech/mech.startup.c::mech_startup_event` | General; AUD-CORE; active | [systems/startup.py](../../systems/startup.py): `startup_event` (function)<br>[systems/startup.py](../../systems/startup.py): `complete_startup` (function)<br>[systems/damage.py](../../systems/damage.py): `destroy_mech` (function)<br>[systems/personal_damage.py](../../systems/personal_damage.py): `initialize_pc` (function) |

<a id="c-btech-mech-stat-c"></a>

### `btech/mech.stat.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.stat.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.stat.c::do_show_stat` | General; AUD-CORE; active | [core/randomness.py](../../core/randomness.py): `RandomState.show_stat` (method)<br>[core/randomness.py](../../core/randomness.py): `RandomState.stat_rows` (method) |
| `btech/mech.stat.c::init_stat` | General; AUD-CORE; active | [core/randomness.py](../../core/randomness.py): `RandomState.init_stat` (method)<br>[core/mt19937.py](../../core/mt19937.py): `MT19937.seed` (method) |
| `btech/mech.stat.c::Number` | General; AUD-CORE; active | [core/randomness.py](../../core/randomness.py): `RandomState.number` (method)<br>[core/randomness.py](../../core/randomness.py): `number` (function)<br>[core/randomness.py](../../core/randomness.py): `draw` (function) |

<a id="c-btech-mech-status-c"></a>

### `btech/mech.status.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.status.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.status.c::ArmorEvaluateSerious` | General; AUD-HUD; active | [systems/armor_display.py](../../systems/armor_display.py): `point_condition` (function)<br>[systems/armor_display.py](../../systems/armor_display.py): `condition` (function) |
| `btech/mech.status.c::ArmorKeyInfo` | General; AUD-HUD; active | [systems/armor_display.py](../../systems/armor_display.py): `armor_key` (function) |
| `btech/mech.status.c::armorstatus_func` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `query` (dispatch; selector `kind=armorstatus`) |
| `btech/mech.status.c::canUsePhysical` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `physical_usable` (function) |
| `btech/mech.status.c::CriticalStatus` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `critical_display` (function)<br>[systems/status_display.py](../../systems/status_display.py): `menu_lines` (function) |
| `btech/mech.status.c::critslot_func` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `query section validation` (inline; selector `kind=critslot`)<br>[systems/status_display.py](../../systems/status_display.py): `query slot fields` (dispatch; selector `kind=critslot`) |
| `btech/mech.status.c::critstatus_func` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `query` (inline; selector `section validation`)<br>[systems/status_display.py](../../systems/status_display.py): `query` (dispatch; selector `critstatus`) |
| `btech/mech.status.c::DisplayTarget` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `target_lines` (function) |
| `btech/mech.status.c::evaluate_ammo_amount` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `ammo_color` (function) |
| `btech/mech.status.c::get_statustemplate_attr` | General; AUD-HUD; active | [systems/armor_display.py](../../systems/armor_display.py): `armor_display custom selection` (inline; selector `status_template/status_expression`)<br>[tools/hud_status.py](../../tools/hud_status.py): `DisplaySession.configure_display` (dispatch; selector `status_template/status_expression`) |
| `btech/mech.status.c::hasPhysical` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `physical_present` (function) |
| `btech/mech.status.c::MakeHeatScaleInfo` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `heat_bar` (inline; selector `heat scale construction`) |
| `btech/mech.status.c::mech_critstatus` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `own_readout` (dispatch; selector `critstatus`) |
| `btech/mech.status.c::mech_status` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `selected_components` (function)<br>[systems/status_display.py](../../systems/status_display.py): `status` (function) |
| `btech/mech.status.c::mech_weaponspecs` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `own_readout` (dispatch; selector `weaponspecs`)<br>[systems/status_display.py](../../systems/status_display.py): `menu_lines` (function) |
| `btech/mech.status.c::part_name` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `part_name` (dispatch; selector `long=False, position=False or positional fallback`) |
| `btech/mech.status.c::part_name_long` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `part_name` (dispatch; selector `long=True, position=False`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.listing` (method) |
| `btech/mech.status.c::pos_part_name` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `part_name` (dispatch; selector `position=True`) |
| `btech/mech.status.c::PrintArmorDamageString` | General; AUD-HUD; active | [systems/armor_display.py](../../systems/armor_display.py): `format_field` (inline; selector `nonblank field, or show_destroyed=True`) |
| `btech/mech.status.c::PrintArmorStatus` | General; AUD-HUD; active | [systems/armor_display.py](../../systems/armor_display.py): `render_template; diagram_family; armor_display` (function)<br>[data/armor_templates.py](../../data/armor_templates.py): `TEMPLATES` (data/table) |
| `btech/mech.status.c::PrintGenericStatus` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `generic_lines` (function) |
| `btech/mech.status.c::PrintHeatBar` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `heat_bar` (function) |
| `btech/mech.status.c::PrintInfoStatus` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `info_lines` (function)<br>[systems/status_display.py](../../systems/status_display.py): `status` (inline; selector `info tail`) |
| `btech/mech.status.c::PrintShortInfo` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `status` (inline; selector `short component`) |
| `btech/mech.status.c::PrintWeaponStatus` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `owner_weapon_state; weapon_display; advanced_status` (dispatch; selector `owner=True`)<br>[systems/status_display.py](../../systems/status_display.py): `status compact weapon payload` (inline; selector `compact-template plus weapons`) |
| `btech/mech.status.c::sectstatus_func` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `query` (dispatch; selector `sectstatus`) |
| `btech/mech.status.c::show_armor` | General; AUD-HUD; active | [systems/armor_display.py](../../systems/armor_display.py): `armor_field; format_field` (function) |
| `btech/mech.status.c::show_miscbrands` | General; AUD-HUD; inactive/empty | Inactive/empty source entry; no active gameplay target. |
| `btech/mech.status.c::weaponstatus_func` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `query` (dispatch; selector `kind=weaponstatus`) |
| `btech/mech.status.c::wspec_fun` | General; AUD-HUD; active | [systems/status_display.py](../../systems/status_display.py): `own_readout` (inline; selector `weapon-spec header/rows`) |

<a id="c-btech-mech-tag-c"></a>

### `btech/mech.tag.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tag.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tag.c::checkTAG` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `check_tag` (function) |
| `btech/mech.tag.c::isTAGDestroyed` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `is_tag_destroyed` (function) |
| `btech/mech.tag.c::mech_tag` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `tag` (function) |
| `btech/mech.tag.c::stopTAG` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `stop_tag` (function) |
| `btech/mech.tag.c::tag_recycle_event` | General; AUD-SENSORS; active | [systems/targeting.py](../../systems/targeting.py): `tag_recycle_event` (function) |

<a id="c-btech-mech-tech-c"></a>

### `btech/mech.tech.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tech.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tech.c::cheat_find_last` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.latest` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.latest per-event fold` (inline) |
| `btech/mech.tech.c::figure_latest_tech_event` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.latest` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.events` (inline) |
| `btech/mech.tech.c::game_lag` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `Technician.lag` (method)<br>[systems/technician.py](../../systems/technician.py): `divide` (function) |
| `btech/mech.tech.c::game_lag_time` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `Technician.lagged` (method)<br>[systems/technician.py](../../systems/technician.py): `divide` (function) |
| `btech/mech.tech.c::player_techtime` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `Technician.pending` (method)<br>[systems/technician.py](../../systems/technician.py): `Technician.timestamp` (method) |
| `btech/mech.tech.c::tech_addtechtime` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `Technician.add_time` (method) |
| `btech/mech.tech.c::tech_parsegun` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `parse_gun` (function)<br>[systems/weapon_inventory.py](../../systems/weapon_inventory.py): `weapon_runs` (inline)<br>[data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.match` (inline) |
| `btech/mech.tech.c::tech_parsepart` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `parse_part` (function)<br>[systems/technician.py](../../systems/technician.py): `parse_part` (dispatch; selector `rear=False`) |
| `btech/mech.tech.c::tech_parsepart_advanced` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `parse_part` (function)<br>[systems/technician.py](../../systems/technician.py): `parse_part` (dispatch; selector `rear=caller`) |
| `btech/mech.tech.c::tech_roll` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `Technician.roll` (method)<br>[systems/technician.py](../../systems/technician.py): `Technician.roll` (dispatch; selector `weapons=False`) |
| `btech/mech.tech.c::tech_status` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `Technician.status` (method) |
| `btech/mech.tech.c::tech_weapon_roll` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `Technician.roll` (method)<br>[systems/technician.py](../../systems/technician.py): `Technician.roll` (dispatch; selector `weapons=True`) |

<a id="c-btech-mech-tech-commands-c"></a>

### `btech/mech.tech.commands.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tech.commands.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tech.commands.c::CanScrapLoc` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.can_scrap_location` (method) |
| `btech/mech.tech.commands.c::CanScrapPart` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.can_scrap_part` (method)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot repair guard` (inline) |
| `btech/mech.tech.commands.c::Invalid_Repair_Path` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `invalid_repair_path` (function) |
| `btech/mech.tech.commands.c::Invalid_Scrap_Path` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `invalid_scrap_path` (function) |
| `btech/mech.tech.commands.c::SomeoneAttaching` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `kind=45,pos=None`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (inline)<br>[systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.under_repair` (inline) |
| `btech/mech.tech.commands.c::SomeoneFixing` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.fixing` (method) |
| `btech/mech.tech.commands.c::SomeoneFixingA` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `kind=47,pos=None`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.points` (inline) |
| `btech/mech.tech.commands.c::SomeoneFixingI` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `kind=48,pos=None`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.points` (inline) |
| `btech/mech.tech.commands.c::SomeoneRepairing` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.repairing` (method) |
| `btech/mech.tech.commands.c::SomeoneRepairing_s` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `pos=provided`) |
| `btech/mech.tech.commands.c::SomeoneReplacingSuit` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `kind=57,pos=None`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (inline)<br>[systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.under_repair` (inline) |
| `btech/mech.tech.commands.c::SomeoneResealing` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `kind=56,pos=None`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (inline)<br>[systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.under_repair` (inline) |
| `btech/mech.tech.commands.c::SomeoneScrappingLoc` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `kind=49,pos=None`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (inline)<br>[systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.under_repair` (inline) |
| `btech/mech.tech.commands.c::SomeoneScrappingPart` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.scrapping_part` (method) |
| `btech/mech.tech.commands.c::tech_check_loc` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `pos=None`) |
| `btech/mech.tech.commands.c::tech_check_locpart` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.count` (dispatch; selector `pos=provided`) |
| `btech/mech.tech.commands.c::tech_checkstatus` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[checkstatus]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command checkstatus` (dispatch; selector `name=checkstatus`) |
| `btech/mech.tech.commands.c::tech_fixarmor` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[fixarmor]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.points` (dispatch; selector `fixarmor`) |
| `btech/mech.tech.commands.c::tech_fixenhcrit` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[fixenhcrit]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `fixenhcrit`) |
| `btech/mech.tech.commands.c::tech_fixextra` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[fixextra]`)<br>[systems/repairs.py](../../systems/repairs.py): `fixextra` (inline) |
| `btech/mech.tech.commands.c::tech_fixinternal` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[fixinternal]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.points` (dispatch; selector `fixinternal`) |
| `btech/mech.tech.commands.c::tech_magic` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[magic]`)<br>[systems/repairs.py](../../systems/repairs.py): `magic` (function)<br>[systems/repairs.py](../../systems/repairs.py): `replay_template` (function)<br>[systems/construction_weight.py](../../systems/construction_weight.py): `internal_check` (function) |
| `btech/mech.tech.commands.c::tech_reattach` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[reattach]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (dispatch; selector `reattach`) |
| `btech/mech.tech.commands.c::tech_reload` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[reload]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `reload`) |
| `btech/mech.tech.commands.c::tech_removegun` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[removegun]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `removegun`) |
| `btech/mech.tech.commands.c::tech_removepart` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[removepart]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `removepart`) |
| `btech/mech.tech.commands.c::tech_removesection` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[removesection]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (dispatch; selector `removesection`) |
| `btech/mech.tech.commands.c::tech_repairgun` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[repairgun]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `repairgun`) |
| `btech/mech.tech.commands.c::tech_repairpart` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[repairpart]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `repairpart`) |
| `btech/mech.tech.commands.c::tech_replacegun` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[replacegun]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.replace` (dispatch; selector `replacegun`) |
| `btech/mech.tech.commands.c::tech_replacepart` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[replacepart]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.replace` (dispatch; selector `replacepart`) |
| `btech/mech.tech.commands.c::tech_replacesuit` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[replacesuit]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (dispatch; selector `replacesuit`) |
| `btech/mech.tech.commands.c::tech_reseal` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[reseal]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.structure` (dispatch; selector `reseal`) |
| `btech/mech.tech.commands.c::tech_toggletype` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[toggletype]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `toggletype`) |
| `btech/mech.tech.commands.c::tech_unload` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[unload]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.validate_slot` (dispatch; selector `unload`) |
| `btech/mech.tech.commands.c::TECHCOMMANDH` | General; PILOT-REPAIR; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.tech.commands.c::unit_is_fixable` | General; PILOT-REPAIR; active | [systems/damage.py](../../systems/damage.py): `unit_is_fixable` (function) |
| `btech/mech.tech.commands.c::ValidGunPos` | General; PILOT-REPAIR; active | [systems/technician.py](../../systems/technician.py): `valid_gun_position` (function)<br>[systems/weapon_inventory.py](../../systems/weapon_inventory.py): `find_weapons` (inline) |

<a id="c-btech-mech-tech-damages-c"></a>

### `btech/mech.tech.damages.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tech.damages.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tech.damages.c::check_for_damage` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.check_damage` (method) |
| `btech/mech.tech.damages.c::check_for_scrappage` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.check_scrap` (method) |
| `btech/mech.tech.damages.c::damages_func` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.machine` (method) |
| `btech/mech.tech.damages.c::fix_entry` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.fix` (method)<br>[systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.fix` (inline) |
| `btech/mech.tech.damages.c::is_under_repair` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.under_repair` (method) |
| `btech/mech.tech.damages.c::make_damage_table` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.damage_table` (method) |
| `btech/mech.tech.damages.c::make_scrap_table` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.scrap_table` (method) |
| `btech/mech.tech.damages.c::show_mechs_damage` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.human` (method) |
| `btech/mech.tech.damages.c::tech_fix` | General; PILOT-REPAIR; active | [systems/repair_reports.py](../../systems/repair_reports.py): `RepairReports.fix` (method) |

<a id="c-btech-mech-tech-do-c"></a>

### `btech/mech.tech.do.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tech.do.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tech.do.c::FindAmmoType` | General; PILOT-REPAIR; active | [systems/repair_materials.py](../../systems/repair_materials.py): `find_ammo_type` (function) |
| `btech/mech.tech.do.c::fixarmor_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[fixarmor_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `fixarmor_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::fixarmor_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[fixarmor_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `fixarmor_fail`) |
| `btech/mech.tech.do.c::fixarmor_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[fixarmor_succ]`) |
| `btech/mech.tech.do.c::fixinternal_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[fixinternal_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `fixinternal_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::fixinternal_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[fixinternal_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `fixinternal_fail`) |
| `btech/mech.tech.do.c::fixinternal_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[fixinternal_succ]`) |
| `btech/mech.tech.do.c::PARTCHECK` | General; PILOT-REPAIR; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.tech.do.c::reattach_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[reattach_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `reattach_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::reattach_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[reattach_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `reattach_fail`) |
| `btech/mech.tech.do.c::reattach_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[reattach_succ]`) |
| `btech/mech.tech.do.c::reload_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[reload_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `reload_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::reload_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[reload_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `reload_fail`) |
| `btech/mech.tech.do.c::reload_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[reload_succ]`) |
| `btech/mech.tech.do.c::repair_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[repair_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `repair_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::repairenhcrit_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[repairenhcrit_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `repairenhcrit_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::repairenhcrit_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[repairenhcrit_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `repairenhcrit_fail`) |
| `btech/mech.tech.do.c::repairenhcrit_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[repairenhcrit_succ]`) |
| `btech/mech.tech.do.c::repairg_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[repairg_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `repairg_fail`) |
| `btech/mech.tech.do.c::repairg_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[repairg_succ]`) |
| `btech/mech.tech.do.c::repairp_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[repairp_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `repairp_fail`) |
| `btech/mech.tech.do.c::repairp_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[repairp_succ]`) |
| `btech/mech.tech.do.c::replace_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[replace_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `replace_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::replaceg_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[replaceg_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `replaceg_fail`) |
| `btech/mech.tech.do.c::replaceg_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[replaceg_succ]`) |
| `btech/mech.tech.do.c::replacep_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[replacep_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `replacep_fail`) |
| `btech/mech.tech.do.c::replacep_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[replacep_succ]`) |
| `btech/mech.tech.do.c::replacesuit_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[replacesuit_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `replacesuit_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::replacesuit_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[replacesuit_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `replacesuit_fail`) |
| `btech/mech.tech.do.c::replacesuit_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[replacesuit_succ]`) |
| `btech/mech.tech.do.c::reseal_econ` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.economy` (dispatch; selector `[reseal_econ]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.costs` (inline; selector `reseal_econ`)<br>[systems/economic_inventory.py](../../systems/economic_inventory.py): `InventoryStore.consume` (method) |
| `btech/mech.tech.do.c::reseal_fail` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (dispatch; selector `[reseal_fail]`)<br>[systems/repair_work.py](../../systems/repair_work.py): `RepairWork.failure` (inline; selector `reseal_fail`) |
| `btech/mech.tech.do.c::reseal_succ` | General; PILOT-REPAIR; inactive/empty | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.success` (dispatch; selector `[reseal_succ]`) |
| `btech/mech.tech.do.c::TFUNC_LOC` | General; PILOT-REPAIR; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.tech.do.c::TFUNC_LOC_RESEAL` | General; PILOT-REPAIR; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.tech.do.c::TFUNC_LOC_VAL` | General; PILOT-REPAIR; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.tech.do.c::TFUNC_LOCPOS` | General; PILOT-REPAIR; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.tech.do.c::TFUNC_LOCPOS_VAL` | General; PILOT-REPAIR; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.tech.do.c::valid_ammo_mode` | General; PILOT-REPAIR; active | [systems/repair_materials.py](../../systems/repair_materials.py): `valid_ammo_mode` (function) |

<a id="c-btech-mech-tech-events-c"></a>

### `btech/mech.tech.events.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tech.events.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tech.events.c::completely_intact_int` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `completely_intact_internal` (function) |
| `btech/mech.tech.events.c::muxevent_tickmech_mountbomb` | General; PILOT-REPAIR; inactive/empty | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[mountbomb]`) |
| `btech/mech.tech.events.c::muxevent_tickmech_reattach` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[reattach]`) |
| `btech/mech.tech.events.c::muxevent_tickmech_reload` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[reload]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `reload`) |
| `btech/mech.tech.events.c::muxevent_tickmech_removegun` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[removegun]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `removegun`) |
| `btech/mech.tech.events.c::muxevent_tickmech_removepart` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[removepart]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `removepart`) |
| `btech/mech.tech.events.c::muxevent_tickmech_removesection` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[removesection]`) |
| `btech/mech.tech.events.c::muxevent_tickmech_repairarmor` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[armor]`) |
| `btech/mech.tech.events.c::muxevent_tickmech_repairenhcrit` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[repairenhcrit]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `repairenhcrit`) |
| `btech/mech.tech.events.c::muxevent_tickmech_repairgun` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[repairgun]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `repairgun`) |
| `btech/mech.tech.events.c::muxevent_tickmech_repairinternal` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[internal]`) |
| `btech/mech.tech.events.c::muxevent_tickmech_repairpart` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[repairpart]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `repairpart`) |
| `btech/mech.tech.events.c::muxevent_tickmech_replacegun` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[replacegun]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `replacegun`) |
| `btech/mech.tech.events.c::muxevent_tickmech_replacesuit` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[replacesuit]`) |
| `btech/mech.tech.events.c::muxevent_tickmech_reseal` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[reseal]`) |
| `btech/mech.tech.events.c::muxevent_tickmech_umountbomb` | General; PILOT-REPAIR; inactive/empty | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.execute` (dispatch; selector `[unmountbomb]`) |

<a id="c-btech-mech-tech-repairs-c"></a>

### `btech/mech.tech.repairs.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tech.repairs.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tech.repairs.c::describe_repairs` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.describe` (method) |
| `btech/mech.tech.repairs.c::tech_repairs` | General; PILOT-REPAIR; active | [systems/repair_work.py](../../systems/repair_work.py): `RepairWork.command` (dispatch; selector `[repairs]`)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.report` (method) |

<a id="c-btech-mech-tech-saverepair-c"></a>

### `btech/mech.tech.saverepair.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tech.saverepair.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tech.saverepair.c::loadrepairs` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.load` (method) |
| `btech/mech.tech.saverepair.c::save_event` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.save` (method)<br>[systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.save` (inline) |
| `btech/mech.tech.saverepair.c::saverepairs` | General; PILOT-REPAIR; active | [systems/repair_jobs.py](../../systems/repair_jobs.py): `RepairJobs.save` (method) |

<a id="c-btech-mech-tic-c"></a>

### `btech/mech.tic.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.tic.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.tic.c::addtic_sub` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `add_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::addtic_sub_func` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `add_tic` (function) |
| `btech/mech.tic.c::cleartic_sub` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `clear_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::cleartic_sub_func` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `clear_tic` (function) |
| `btech/mech.tic.c::deltic_sub` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `del_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::deltic_sub_func` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `del_tic` (function) |
| `btech/mech.tic.c::firetic_sub` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `fire_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::firetic_sub_func` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `fire_tic.fire` (nested function) |
| `btech/mech.tic.c::heat_cutoff` | General; AUD-FIRING; active | [systems/heat_control.py](../../systems/heat_control.py): `heat_cutoff` (function)<br>[systems/heat_control.py](../../systems/heat_control.py): `common_checks` (function) |
| `btech/mech.tic.c::heat_cutoff_event` | General; AUD-FIRING; active | [systems/heat_control.py](../../systems/heat_control.py): `heat_cutoff_event` (function) |
| `btech/mech.tic.c::listtic_fun` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `list_tic` (function) |
| `btech/mech.tic.c::listtic_sub` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `list_tic` (function) |
| `btech/mech.tic.c::mech_addtic` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `add_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::mech_cleartic` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `clear_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::mech_deltic` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `del_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::mech_firetic` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `fire_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |
| `btech/mech.tic.c::mech_listtic` | General; AUD-FIRING; active | [systems/tic.py](../../systems/tic.py): `list_tic` (function)<br>[systems/tic.py](../../systems/tic.py): `tic_command` (function) |

<a id="c-btech-mech-update-c"></a>

### `btech/mech.update.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.update.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.update.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.update.c::ammo_explosion` | General; AUD-HEAT; active | [systems/criticals.py](../../systems/criticals.py): `ammo_explosion` (function)<br>[systems/criticals.py](../../systems/criticals.py): `apply_ammo_critical` (function)<br>[systems/heat.py](../../systems/heat.py): `trigger_heat_ammo_explosion` (function) |
| `btech/mech.update.c::ammo_explosion` | Historical Aerospace; AUD-AEROSPACE; active | [systems/heat.py](../../systems/heat.py): `trigger_heat_ammo_explosion` (function)<br>[systems/criticals.py](../../systems/criticals.py): `ammo_explosion` (function) |
| `btech/mech.update.c::bridge_set_elevation` | General; AUD-HEAT; active | [physics/movement.py](../../physics/movement.py): `bridge_set_elevation` (function) |
| `btech/mech.update.c::bridge_w_elevation` | General; AUD-HEAT; active | [physics/collision.py](../../physics/collision.py): `bridge_w_elevation` (function) |
| `btech/mech.update.c::CheckDamage` | General; AUD-HEAT; active | [systems/stagger.py](../../systems/stagger.py): `check_damage` (function)<br>[systems/stagger.py](../../systems/stagger.py): `check_legacy_stability` (function) |
| `btech/mech.update.c::CheckNavalHeight` | General; AUD-HEAT; active | [physics/heights.py](../../physics/heights.py): `check_naval_height` (function) |
| `btech/mech.update.c::CheckVTOLHeight` | General; AUD-HEAT; active | [physics/heights.py](../../physics/heights.py): `land_vtol` (function)<br>[physics/heights.py](../../physics/heights.py): `check_vtol_height` (function) |
| `btech/mech.update.c::CheckVTOLHeight` | Historical Aerospace; AUD-AEROSPACE; active | [physics/heights.py](../../physics/heights.py): `check_vtol_height` (function) |
| `btech/mech.update.c::ClearAllStaggerDamage` | General; AUD-HEAT; active | [systems/stagger.py](../../systems/stagger.py): `clear_all` (function)<br>[physics/jump.py](../../physics/jump.py): `mech_falls` (function)<br>[systems/movement_commands.py](../../systems/movement_commands.py): `prone` (function)<br>[systems/physical.py](../../systems/physical.py): `_dfa_make_prone` (function) |
| `btech/mech.update.c::ClearStaggerDamage` | General; AUD-HEAT; active | [systems/stagger.py](../../systems/stagger.py): `clear_expired` (function) |
| `btech/mech.update.c::collision_check` | General; AUD-HEAT; active | [physics/collision.py](../../physics/collision.py): `collision_check` (function) |
| `btech/mech.update.c::CurrentCountedStaggerDamage` | General; AUD-HEAT; active | [systems/stagger.py](../../systems/stagger.py): `current_damage` (dispatch; selector `(counted=True)`) |
| `btech/mech.update.c::CurrentStaggerDamage` | General; AUD-HEAT; active | [systems/stagger.py](../../systems/stagger.py): `current_damage` (dispatch; selector `(counted=False)`) |
| `btech/mech.update.c::DisableSomeHS` | General; AUD-HEAT; active | [systems/heat_control.py](../../systems/heat_control.py): `disable_some_sinks` (function) |
| `btech/mech.update.c::DSOkToNotify` | General; AUD-HEAT; active | [physics/heights.py](../../physics/heights.py): `dropship_notice` (function) |
| `btech/mech.update.c::EnableSomeHS` | General; AUD-HEAT; active | [systems/heat_control.py](../../systems/heat_control.py): `enable_some_sinks` (function) |
| `btech/mech.update.c::fiery_death` | General; AUD-HEAT; active | [physics/heights.py](../../physics/heights.py): `fiery_death` (function) |
| `btech/mech.update.c::HandleOverheat` | General; AUD-HEAT; active | [systems/heat.py](../../systems/heat.py): `check_overheat` (function)<br>[systems/heat.py](../../systems/heat.py): `apply_shutdown` (function)<br>[systems/startup.py](../../systems/startup.py): `shutdown_state` (function) |
| `btech/mech.update.c::HandleOverheat` | Historical Aerospace; AUD-AEROSPACE; active | [systems/heat.py](../../systems/heat.py): `check_overheat` (function)<br>[systems/heat.py](../../systems/heat.py): `check_shutdown/apply_shutdown` (function)<br>[systems/heat.py](../../systems/heat.py): `apply_shutdown` (function) |
| `btech/mech.update.c::MarkStaggerDamage` | General; AUD-HEAT; active | [systems/stagger.py](../../systems/stagger.py): `mark_damage` (function) |
| `btech/mech.update.c::mech_update` | General; AUD-HEAT; active | [core/game_loop.py](../../core/game_loop.py): `mech_update` (function) |
| `btech/mech.update.c::move_mech` | General; AUD-HEAT; active | [physics/movement.py](../../physics/movement.py): `move_mech` (function)<br>[physics/movement.py](../../physics/movement.py): `update_movement` (function)<br>[physics/movement.py](../../physics/movement.py): `on_hex_entered` (function)<br>[physics/movement.py](../../physics/movement.py): `update_charge` (function)<br>[physics/jump.py](../../physics/jump.py): `update_jump` (function)<br>[physics/jump.py](../../physics/jump.py): `calculate_odd_jump_altitude` (function) |
| `btech/mech.update.c::move_mech` | Historical Aerospace; AUD-AEROSPACE; active | [physics/movement.py](../../physics/movement.py): `move_mech` (function)<br>[physics/movement.py](../../physics/movement.py): `on_hex_entered` (function)<br>[physics/movement.py](../../physics/movement.py): `update_movement` (function) |
| `btech/mech.update.c::move_unit_back` | General; AUD-HEAT; active | [physics/movement.py](../../physics/movement.py): `move_unit_back` (function) |
| `btech/mech.update.c::NewHexEntered` | General; AUD-HEAT; active | [physics/movement.py](../../physics/movement.py): `new_hex_entered` (function) |
| `btech/mech.update.c::NewHexEntered` | Historical Aerospace; AUD-AEROSPACE; active | [physics/movement.py](../../physics/movement.py): `new_hex_entered historical flight branch` (dispatch; selector `MOVE_FLY`) |
| `btech/mech.update.c::OverheatMods` | General; AUD-HEAT; active | [systems/combat.py](../../systems/combat.py): `calculate_overheat_modifier` (function) |
| `btech/mech.update.c::recycle_weaponry` | General; AUD-HEAT; active | [core/game_loop.py](../../core/game_loop.py): `recycle_weaponry` (function) |
| `btech/mech.update.c::recycle_weaponry` | Historical Aerospace; AUD-AEROSPACE; active | [core/game_loop.py](../../core/game_loop.py): `recycle_weaponry` (function) |
| `btech/mech.update.c::RemoveStaggerDamage` | General; AUD-HEAT; active | [systems/stagger.py](../../systems/stagger.py): `remove_damage` (function) |
| `btech/mech.update.c::SkidMod` | General; AUD-HEAT; active | [physics/collision.py](../../physics/collision.py): `skid_mod` (function) |
| `btech/mech.update.c::terrain_speed` | General; AUD-HEAT; active | [physics/movement.py](../../physics/movement.py): `terrain_speed` (function) |
| `btech/mech.update.c::updateAutoturnTurret` | General; AUD-HEAT; active | [systems/maneuver.py](../../systems/maneuver.py): `update_autoturn_turret` (function) |
| `btech/mech.update.c::UpdateHeading` | General; AUD-HEAT; active | [physics/movement.py](../../physics/movement.py): `update_heading` (function)<br>[physics/movement.py](../../physics/movement.py): `calculate_turn_rate` (function) |
| `btech/mech.update.c::UpdateHeading` | Historical Aerospace; AUD-AEROSPACE; active | [physics/movement.py](../../physics/movement.py): `calculate_turn_rate` (function)<br>[physics/movement.py](../../physics/movement.py): `update_heading` (function) |
| `btech/mech.update.c::UpdateHeat` | General; AUD-HEAT; active | [systems/heat.py](../../systems/heat.py): `update_heat` (function)<br>[systems/heat.py](../../systems/heat.py): `full_heat_update` (function)<br>[systems/heat.py](../../systems/heat.py): `update_from_environment` (function) |
| `btech/mech.update.c::UpdateHeat` | Historical Aerospace; AUD-AEROSPACE; active | [systems/heat.py](../../systems/heat.py): `update_from_environment / full_heat_update` (function)<br>[systems/heat.py](../../systems/heat.py): `update_heat` (function) |
| `btech/mech.update.c::UpdatePilotSkillRolls` | General; AUD-HEAT; active | [systems/stability.py](../../systems/stability.py): `update_pilot_skill_rolls` (function)<br>[systems/stability.py](../../systems/stability.py): `check_stability` (function)<br>[systems/stability.py](../../systems/stability.py): `damage_overspeed_legs` (function) |
| `btech/mech.update.c::UpdateSpeed` | General; AUD-HEAT; active | [physics/movement.py](../../physics/movement.py): `update_speed` (function)<br>[physics/movement.py](../../physics/movement.py): `calculate_heat_speed_reduction` (function)<br>[physics/cargo.py](../../physics/cargo.py): `cargo_max_speed` (function) |

<a id="c-btech-mech-utils-c"></a>

### `btech/mech.utils.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mech.utils.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/mech.utils.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mech.utils.c::AcceptableDegree` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `acceptable_degree` (function) |
| `btech/mech.utils.c::alias_part` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `alias_part` (function) |
| `btech/mech.utils.c::ArmorStringFromIndex` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `armor_string` (function)<br>[systems/damage_commands.py](../../systems/damage_commands.py): `section_names` (function) |
| `btech/mech.utils.c::Calc_AddDefBV` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `Calculation.add` (method)<br>[systems/economy.py](../../systems/economy.py): `calculation` (function) |
| `btech/mech.utils.c::Calc_AddOffBV` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `Calculation.add` (method)<br>[systems/economy.py](../../systems/economy.py): `calculation` (function) |
| `btech/mech.utils.c::Calc_SubDefBV` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `Calculation.add` (method)<br>[systems/economy.py](../../systems/economy.py): `calculation` (function) |
| `btech/mech.utils.c::CalcFasaCost` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `fasa_cost` (function) |
| `btech/mech.utils.c::CalcFasaCost_AddPrice` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `Calculation.add` (method)<br>[systems/economy.py](../../systems/economy.py): `calculation` (function) |
| `btech/mech.utils.c::CalcFasaCost_DoArmMath` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `actuator_cost` (function; selector `leg=False`) |
| `btech/mech.utils.c::CalcFasaCost_DoLegMath` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `actuator_cost` (function; selector `leg=True`) |
| `btech/mech.utils.c::Calculate_Defensive_BV` | General; AUD-UTILS; active | [systems/battle_value.py](../../systems/battle_value.py): `defensive_bv` (function) |
| `btech/mech.utils.c::Calculate_Offensive_BV` | General; AUD-UTILS; active | [systems/battle_value.py](../../systems/battle_value.py): `offensive_bv` (function) |
| `btech/mech.utils.c::CalculateBV` | General; AUD-UTILS; active | [systems/battle_value.py](../../systems/battle_value.py): `calculate_bv` (function)<br>[systems/battle_value.py](../../systems/battle_value.py): `SKILL_MULTIPLIERS` (data/table) |
| `btech/mech.utils.c::ChannelEmitKill` | General; AUD-UTILS; active | [systems/damage.py](../../systems/damage.py): `channel_emit_kill` (function) |
| `btech/mech.utils.c::checkAllSections` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `check_all_sections` (function)<br>[systems/ecm.py](../../systems/ecm.py): `check_all_sections` (function)<br>[systems/missile.py](../../systems/missile.py): `check_all_sections` (function) |
| `btech/mech.utils.c::CheckEdgeOfMap` | General; AUD-UTILS; active | [systems/map_transitions.py](../../systems/map_transitions.py): `check_edge_of_map` (function) |
| `btech/mech.utils.c::checkSectionForSpecial` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `check_section_for_special` (function)<br>[systems/ecm.py](../../systems/ecm.py): `check_section_for_special` (function)<br>[systems/missile.py](../../systems/missile.py): `check_all_sections` (function) |
| `btech/mech.utils.c::CountAmmoForWeapon` | General; AUD-UTILS; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `count_ammo` (function) |
| `btech/mech.utils.c::CountDestroyedLegs` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `count_destroyed_legs` (function) |
| `btech/mech.utils.c::CritsInLoc` | General; AUD-UTILS; active | [entities/crittypes.py](../../entities/crittypes.py): `crits_in_loc` (function) |
| `btech/mech.utils.c::CritsInLoc` | Historical Aerospace; AUD-AEROSPACE; active | [entities/crittypes.py](../../entities/crittypes.py): `crits_in_loc` (function) |
| `btech/mech.utils.c::do_fixextra` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `fixextra` (function) |
| `btech/mech.utils.c::do_magic` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `magic` (function)<br>[systems/repairs.py](../../systems/repairs.py): `replay_template` (function) |
| `btech/mech.utils.c::do_sub_magic` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `sub_magic` (function) |
| `btech/mech.utils.c::find_mech_in_hex` | General; AUD-UTILS; active | [systems/targeting.py](../../systems/targeting.py): `find_mech_in_hex` (function) |
| `btech/mech.utils.c::FindAmmoForWeapon` | General; AUD-UTILS; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `find_normal_ammo_for_weapon` (function) |
| `btech/mech.utils.c::FindAmmoForWeapon_sub` | General; AUD-UTILS; active | [systems/combat.py](../../systems/combat.py): `find_ammo_for_weapon` (function) |
| `btech/mech.utils.c::findAmmoInSection` | General; AUD-UTILS; active | [systems/combat.py](../../systems/combat.py): `find_ammo_in_section` (function) |
| `btech/mech.utils.c::FindAmmunition` | General; AUD-UTILS; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `find_ammunition` (function) |
| `btech/mech.utils.c::FindAndCheckAmmo` | General; AUD-UTILS; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `find_and_check` (function)<br>[systems/weapon_modes.py](../../systems/weapon_modes.py): `ammo_mode_filters` (function) |
| `btech/mech.utils.c::FindArtemisForWeapon` | General; AUD-UTILS; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `find_artemis_for_weapon` (function) |
| `btech/mech.utils.c::FindAverageGunnery` | General; AUD-UTILS; active | [systems/battle_value.py](../../systems/battle_value.py): `calculate_bv` (function)<br>[tools/core_diagnostics.py](../../tools/core_diagnostics.py): `PURE[FindAverageGunnery]` (dispatch; selector `FindAverageGunnery`) |
| `btech/mech.utils.c::FindBearing` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `find_bearing` (function) |
| `btech/mech.utils.c::FindComponents` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `find_components` (function) |
| `btech/mech.utils.c::FindDestructiveAmmo` | General; AUD-UTILS; active | [systems/heat.py](../../systems/heat.py): `find_destructive_ammo` (function)<br>[systems/heat.py](../../systems/heat.py): `find_ammo_bins` (function)<br>[systems/ammo_dump.py](../../systems/ammo_dump.py): `ammo_full_salvo` (function) |
| `btech/mech.utils.c::FindFirstWeaponCrit` | General; AUD-UTILS; active | [systems/criticals.py](../../systems/criticals.py): `find_first_weapon_crit` (function) |
| `btech/mech.utils.c::FindGunnerySkillName` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_gunnery_skill_name` (function) |
| `btech/mech.utils.c::FindHexRange` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `find_range` (function) |
| `btech/mech.utils.c::FindInfernoAmmo` | General; AUD-UTILS; active | [systems/heat.py](../../systems/heat.py): `find_destructive_ammo` (function)<br>[systems/heat.py](../../systems/heat.py): `find_ammo_bins` (function)<br>[systems/ammo_dump.py](../../systems/ammo_dump.py): `ammo_full_salvo` (function) |
| `btech/mech.utils.c::FindLegHeatSinks` | General; AUD-UTILS; active | [systems/heat_control.py](../../systems/heat_control.py): `leg_heat_sinks` (function) |
| `btech/mech.utils.c::FindMechOnMap` | General; AUD-UTILS; active | [systems/targeting.py](../../systems/targeting.py): `contact_target` (function) |
| `btech/mech.utils.c::FindObj` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `find_obj` (function)<br>[systems/physical.py](../../systems/physical.py): `find_obj` (function) |
| `btech/mech.utils.c::FindObjWithDest` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `find_obj` (function) |
| `btech/mech.utils.c::FindPilotArtyGun` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_pilot_arty_gun` (function)<br>[systems/piloting.py](../../systems/piloting.py): `machine_skill` (function)<br>[systems/piloting.py](../../systems/piloting.py): `valid_pilot` (function)<br>[systems/piloting.py](../../systems/piloting.py): `skill_target` (function) |
| `btech/mech.utils.c::FindPilotGunnery` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_pilot_gunnery` (function)<br>[systems/piloting.py](../../systems/piloting.py): `skill_target` (function)<br>[systems/piloting.py](../../systems/piloting.py): `valid_pilot` (function)<br>[systems/piloting.py](../../systems/piloting.py): `machine_skill` (function) |
| `btech/mech.utils.c::FindPilotingSkillName` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_piloting_skill_name` (function) |
| `btech/mech.utils.c::FindPilotPiloting` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_pilot_piloting` (function)<br>[systems/piloting.py](../../systems/piloting.py): `machine_skill` (function)<br>[systems/piloting.py](../../systems/piloting.py): `valid_pilot` (function)<br>[systems/piloting.py](../../systems/piloting.py): `skill_target` (function) |
| `btech/mech.utils.c::FindPilotSpotting` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_pilot_spotting` (function)<br>[systems/piloting.py](../../systems/piloting.py): `machine_skill` (function)<br>[systems/piloting.py](../../systems/piloting.py): `valid_pilot` (function)<br>[systems/piloting.py](../../systems/piloting.py): `skill_target` (function) |
| `btech/mech.utils.c::FindRange` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `find_range3d` (function) |
| `btech/mech.utils.c::FindRoundsForWeapon` | General; AUD-UTILS; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `find_rounds_for_weapon` (function) |
| `btech/mech.utils.c::FindSPilotPiloting` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_spilot_piloting` (function) |
| `btech/mech.utils.c::FindSplitCrits` | General; AUD-UTILS; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `find_split_crits` (function) |
| `btech/mech.utils.c::FindTargetDBREFFromMapNumber` | General; AUD-UTILS; active | [systems/targeting.py](../../systems/targeting.py): `contact_target` (function) |
| `btech/mech.utils.c::FindTargetXY` | General; AUD-UTILS; active | [systems/combat.py](../../systems/combat.py): `find_target_xy` (function) |
| `btech/mech.utils.c::FindTechSkill` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_tech_skill` (function) |
| `btech/mech.utils.c::FindTechSkillName` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `find_tech_skill_name` (function) |
| `btech/mech.utils.c::FindWeaponFromIndex` | General; AUD-UTILS; active | [systems/weapon_inventory.py](../../systems/weapon_inventory.py): `find_weapon_from_index` (function) |
| `btech/mech.utils.c::FindWeaponIndex` | General; AUD-UTILS; active | [systems/weapon_inventory.py](../../systems/weapon_inventory.py): `find_weapon_index` (function) |
| `btech/mech.utils.c::FindWeaponNumberOnMech` | General; AUD-UTILS; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `find_weapon_number_on_mech` (function) |
| `btech/mech.utils.c::FindWeaponNumberOnMech_Advanced` | General; AUD-UTILS; active | [systems/weapon_modes.py](../../systems/weapon_modes.py): `find_weapon_number_on_mech` (function) |
| `btech/mech.utils.c::FindWeapons_Advanced` | General; AUD-UTILS; active | [systems/weapon_inventory.py](../../systems/weapon_inventory.py): `find_weapons` (function) |
| `btech/mech.utils.c::FindXY` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `find_xy` (function) |
| `btech/mech.utils.c::FindXYRange` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `find_range` (function) |
| `btech/mech.utils.c::FindZBearing` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `find_z_bearing` (function) |
| `btech/mech.utils.c::FullAmmo` | General; AUD-UTILS; active | [systems/combat_ammunition.py](../../systems/combat_ammunition.py): `full_ammo` (function)<br>[systems/combat_ammunition.py](../../systems/combat_ammunition.py): `ammo_capacity` (function) |
| `btech/mech.utils.c::GetPartCost` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `CostTables.get` (method) |
| `btech/mech.utils.c::GetPartMod` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `part_mod` (function) |
| `btech/mech.utils.c::GetPartWeight` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `part_weight` (function) |
| `btech/mech.utils.c::getRemainingArmorPercent` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `remaining_armor_percent` (function)<br>[systems/network_reports.py](../../systems/network_reports.py): `remaining_percent` (function) |
| `btech/mech.utils.c::getRemainingInternalPercent` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `remaining_internal_percent` (function)<br>[systems/network_reports.py](../../systems/network_reports.py): `remaining_percent` (function) |
| `btech/mech.utils.c::GetSplitData` | General; AUD-UTILS; active | [systems/enhanced_crits.py](../../systems/enhanced_crits.py): `get_split_data` (function) |
| `btech/mech.utils.c::GetWeaponCrits` | General; AUD-UTILS; active | [systems/weapon_inventory.py](../../systems/weapon_inventory.py): `weapon_crits` (function) |
| `btech/mech.utils.c::GetWeaponCrits` | Historical Aerospace; AUD-AEROSPACE; active | [systems/weapon_inventory.py](../../systems/weapon_inventory.py): `weapon_crits` (function) |
| `btech/mech.utils.c::HeatFactor` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `heat_factor` (function) |
| `btech/mech.utils.c::int` | General; AUD-UTILS; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.utils.c::InWeaponArc` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `in_weapon_arc` (function) |
| `btech/mech.utils.c::IsInWeaponArc` | General; AUD-UTILS; active | [systems/combat.py](../../systems/combat.py): `is_in_weapon_arc` (function) |
| `btech/mech.utils.c::IsInWeaponArc` | Historical Aerospace; AUD-AEROSPACE; active | [systems/combat.py](../../systems/combat.py): `is_in_weapon_arc` (function)<br>[physics/hexmath.py](../../physics/hexmath.py): `in_weapon_arc` (function) |
| `btech/mech.utils.c::IsLegDestroyed` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `is_leg_destroyed` (function) |
| `btech/mech.utils.c::IsMechLegLess` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `is_mech_legless` (function) |
| `btech/mech.utils.c::Leave_Hangar` | General; AUD-UTILS; active | [systems/map_transitions.py](../../systems/map_transitions.py): `transfer` (function)<br>[systems/map_transitions.py](../../systems/map_transitions.py): `leave_hangar` (function) |
| `btech/mech.utils.c::listmatch` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `listmatch` (function) |
| `btech/mech.utils.c::MadePilotSkillRoll` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `make_piloting_roll` (function) |
| `btech/mech.utils.c::MadePilotSkillRoll_Advanced` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `make_piloting_roll` (function) |
| `btech/mech.utils.c::MadePilotSkillRoll_NoXP` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `make_piloting_roll` (function) |
| `btech/mech.utils.c::MapCoordToRealCoord` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `hex_to_float` (function) |
| `btech/mech.utils.c::MarkForLOSUpdate` | General; AUD-UTILS; active | [systems/ecm.py](../../systems/ecm.py): `mark_for_los_update` (function) |
| `btech/mech.utils.c::mech_armorpoints` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `armorpoints` (function) |
| `btech/mech.utils.c::mech_Detach` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `detach` (function) |
| `btech/mech.utils.c::mech_FillPartAmmo` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `fill_part_ammo` (function) |
| `btech/mech.utils.c::mech_intpoints` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `intpoints` (function) |
| `btech/mech.utils.c::mech_ReAttach` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `reattach` (function) |
| `btech/mech.utils.c::mech_RepairPart` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `repair_part` (function) |
| `btech/mech.utils.c::mech_ReplaceSuit` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `replace_suit` (function) |
| `btech/mech.utils.c::mech_ReSeal` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `reseal` (function) |
| `btech/mech.utils.c::MechFullNoRecycle` | General; AUD-UTILS; active | [systems/physical.py](../../systems/physical.py): `mech_full_no_recycle` (function)<br>[systems/spot.py](../../systems/spot.py): `mech_full_no_recycle` (function) |
| `btech/mech.utils.c::MechIDS` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `mech_ids` (function)<br>[systems/hud.py](../../systems/hud.py): `identity` (inline)<br>[systems/observation.py](../../systems/observation.py): `contacts` (inline) |
| `btech/mech.utils.c::MechNumHeatsinksInEngine` | General; AUD-UTILS; active | [tools/core_diagnostics.py](../../tools/core_diagnostics.py): `diagnose` (dispatch; selector `MechNumHeatsinksInEngine`) |
| `btech/mech.utils.c::MechPilotSkillRoll_BTH` | General; AUD-UTILS; active | [systems/piloting.py](../../systems/piloting.py): `piloting_bth` (function) |
| `btech/mech.utils.c::mechtypename` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `mechtypename` (function) |
| `btech/mech.utils.c::MNumber` | General; AUD-UTILS; active | [systems/sensors.py](../../systems/sensors.py): `m_number` (function)<br>[core/randomness.py](../../core/randomness.py): `draw` (function)<br>[core/randomness.py](../../core/randomness.py): `RandomState.number` (method)<br>[tools/core_diagnostics.py](../../tools/core_diagnostics.py): `diagnose` (dispatch; selector `MNumber`)<br>[tools/sensors_los.py](../../tools/sensors_los.py): `SensorSession.invoke` (method) |
| `btech/mech.utils.c::multi_weap_sel` | General; AUD-UTILS; active | [systems/tic.py](../../systems/tic.py): `multi_weap_sel` (function) |
| `btech/mech.utils.c::MyHexDist` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `my_hex_dist` (function) |
| `btech/mech.utils.c::MyToUpper` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `my_to_upper` (function)<br>[systems/buildings.py](../../systems/buildings.py): `damage_cf` (inline)<br>[systems/buildings.py](../../systems/buildings.py): `query` (inline) |
| `btech/mech.utils.c::navigate_sketch_mechs` | General; AUD-UTILS; active | [systems/targeting.py](../../systems/targeting.py): `navigate_sketch_mechs` (function) |
| `btech/mech.utils.c::no_locations_destroyed` | General; AUD-UTILS; active | [systems/repairs.py](../../systems/repairs.py): `no_locations_destroyed` (function) |
| `btech/mech.utils.c::ProperArmor` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `proper_armor` (function) |
| `btech/mech.utils.c::ProperInternal` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `proper_internal` (function) |
| `btech/mech.utils.c::ProperMyomer` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `proper_myomer` (function) |
| `btech/mech.utils.c::ProperSectionStringFromType` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `section_strings` (function)<br>[systems/damage_commands.py](../../systems/damage_commands.py): `section_names` (function) |
| `btech/mech.utils.c::ProperSectionStringFromType` | Historical Aerospace; AUD-AEROSPACE; active | [systems/damage_commands.py](../../systems/damage_commands.py): `section_names` (function)<br>[entities/mech.py](../../entities/mech.py): `AeroLocation` (data/table) |
| `btech/mech.utils.c::RealCoordToMapCoord` | General; AUD-UTILS; active | [physics/hexmath.py](../../physics/hexmath.py): `float_to_hex` (function)<br>[physics/hexmath.py](../../physics/hexmath.py): `_short_coordinates` (function) |
| `btech/mech.utils.c::ReverseSplitCritLoc` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `reverse_split_crit_loc` (function) |
| `btech/mech.utils.c::Roll` | General; AUD-UTILS; active | [core/randomness.py](../../core/randomness.py): `roll` (function)<br>[core/randomness.py](../../core/randomness.py): `RandomState.roll` (method) |
| `btech/mech.utils.c::round_to_halfton` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `round_to_halfton` (function)<br>[systems/parts.py](../../systems/parts.py): `rounded_weight` (function)<br>[physics/hexmath.py](../../physics/hexmath.py): `signed_remainder` (function)<br>[tools/core_diagnostics.py](../../tools/core_diagnostics.py): `PURE` (dispatch; selector `round_to_halfton`) |
| `btech/mech.utils.c::round_to_quarterton` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `round_to_quarterton` (function)<br>[systems/parts.py](../../systems/parts.py): `rounded_weight` (function)<br>[physics/hexmath.py](../../physics/hexmath.py): `signed_remainder` (function)<br>[tools/core_diagnostics.py](../../tools/core_diagnostics.py): `PURE` (dispatch; selector `round_to_quarterton`) |
| `btech/mech.utils.c::SectHasBusyWeap` | General; AUD-UTILS; active | [systems/physical.py](../../systems/physical.py): `sect_has_busy_weap` (function)<br>[systems/weapon_inventory.py](../../systems/weapon_inventory.py): `find_weapons` (function)<br>[systems/combat.py](../../systems/combat.py): `part_is_nonfunctional` (function)<br>[systems/damage.py](../../systems/damage.py): `section_destroyed` (function)<br>[systems/damage.py](../../systems/damage.py): `external_effect` (function) |
| `btech/mech.utils.c::SetPartCost` | General; AUD-UTILS; active | [systems/economy.py](../../systems/economy.py): `CostTables.set` (method) |
| `btech/mech.utils.c::UnitPartsList` | General; AUD-UTILS; active | [systems/parts.py](../../systems/parts.py): `unit_parts_list` (function)<br>[systems/parts.py](../../systems/parts.py): `payloadlist` (function)<br>[systems/parts.py](../../systems/parts.py): `partlist` (function) |
| `btech/mech.utils.c::ValidMap` | General; AUD-UTILS; active | [systems/targeting.py](../../systems/targeting.py): `valid_map` (function) |
| `btech/mech.utils.c::visit_neighbor_hexes` | General; AUD-UTILS; active | [entities/map.py](../../entities/map.py): `neighbors` (function)<br>[systems/artillery.py](../../systems/artillery.py): `neighbors` (function)<br>[entities/map.py](../../entities/map.py): `visit_neighbor_hexes` (function) |
| `btech/mech.utils.c::void` | General; AUD-UTILS; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mech.utils.c::WeaponIsNonfunctional` | General; AUD-UTILS; active | [systems/weapon_inventory.py](../../systems/weapon_inventory.py): `weapon_is_nonfunctional` (function) |

<a id="c-btech-mechrep-c"></a>

### `btech/mechrep.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mechrep.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mechrep.c::clear_mech` | General; AUD-TEMPLATES; active | [data/template_files.py](../../data/template_files.py): `clear_mech` (function)<br>[data/template_files.py](../../data/template_files.py): `_ZERO_FIELDS` (data/table) |
| `btech/mechrep.c::free_template_list` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.reset` (method) |
| `btech/mechrep.c::funcname` | General; AUD-TEMPLATES; extraction artifact | Macro/type extraction artifact; no callable target. |
| `btech/mechrep.c::invalid_section` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `invalid_section` (function) |
| `btech/mechrep.c::load_mechdata` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `load_legacy_stream` (function)<br>[data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.load_legacy` (method) |
| `btech/mechrep.c::load_mechdata2` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.load_modern` (method) |
| `btech/mechrep.c::load_refmech` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.load_reference` (method)<br>[data/template_catalog.py](../../data/template_catalog.py): `CatalogDirectory.load_reference` (method) |
| `btech/mechrep.c::mech_loadnew` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.loadnew` (method) |
| `btech/mechrep.c::mechref_path` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.lookup` (method)<br>[data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.old_lookup` (method) |
| `btech/mechrep.c::mechrep_gettechstring` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `show_tech` (function; selector `names`) |
| `btech/mechrep.c::mechrep_Raddinftech` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.technology` (method; selector `addinftech`) |
| `btech/mechrep.c::mechrep_Raddspecial` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.add_special` (method) |
| `btech/mechrep.c::mechrep_Raddtech` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.technology` (method; selector `addtech`) |
| `btech/mechrep.c::mechrep_Raddweap` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.add_weapon` (method) |
| `btech/mechrep.c::mechrep_Rdelinftech` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `delinftech` (function) |
| `btech/mechrep.c::mechrep_Rdeltech` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.technology` (method; selector `deltech`) |
| `btech/mechrep.c::mechrep_Rdisplaysection` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `displaysection`) |
| `btech/mechrep.c::mechrep_Rfiremode` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.ammunition` (method) |
| `btech/mechrep.c::mechrep_Rloadnew` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.loadnew` (method; selector `wrapper=True`)<br>[systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `loadnew`) |
| `btech/mechrep.c::mechrep_Rreload` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.ammunition` (method) |
| `btech/mechrep.c::mechrep_Rrepair` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.repair` (method) |
| `btech/mechrep.c::mechrep_Rresetcrits` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `resetcrits`) |
| `btech/mechrep.c::mechrep_Rrestock` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.ammunition` (method) |
| `btech/mechrep.c::mechrep_Rrestore` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.restore` (method)<br>[systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `restore`)<br>[data/template_catalog.py](../../data/template_catalog.py): `CatalogDirectory.restore` (method) |
| `btech/mechrep.c::mechrep_Rsavetemp` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.save` (method; selector `legacy`)<br>[data/template_directory.py](../../data/template_directory.py): `save_legacy` (function) |
| `btech/mechrep.c::mechrep_Rsavetemp2` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.save` (method; selector `modern`) |
| `btech/mechrep.c::mechrep_Rsetarmor` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setarmor`) |
| `btech/mechrep.c::mechrep_Rsetheatsinks` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setheatsinks`) |
| `btech/mechrep.c::mechrep_Rsetjumpspeed` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setjumpspeed`) |
| `btech/mechrep.c::mechrep_Rsetlrsrange` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setlrsrange`) |
| `btech/mechrep.c::mechrep_Rsetmove` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setmove`) |
| `btech/mechrep.c::mechrep_Rsetradio` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setradio`) |
| `btech/mechrep.c::mechrep_Rsetradiorange` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setradiorange`) |
| `btech/mechrep.c::mechrep_Rsetscanrange` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setscanrange`) |
| `btech/mechrep.c::mechrep_Rsetspeed` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setspeed`) |
| `btech/mechrep.c::mechrep_Rsettacrange` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `settacrange`) |
| `btech/mechrep.c::mechrep_Rsettarget` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `settarget`) |
| `btech/mechrep.c::mechrep_Rsettons` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `settons`) |
| `btech/mechrep.c::mechrep_Rsettype` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `settype`) |
| `btech/mechrep.c::mechrep_Rshowtech` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `show_tech` (function) |
| `btech/mechrep.c::mechrep_setcargospace` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor._command` (dispatch; selector `setcargospace`) |
| `btech/mechrep.c::newfreemechrep` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `Editor.__init__` (method) |
| `btech/mechrep.c::scan_template_dir` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.scan` (method; selector `files and subdirectories`) |
| `btech/mechrep.c::scan_templates` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.scan` (method) |
| `btech/mechrep.c::techstatus_func` | General; AUD-TEMPLATES; active | [systems/construction_editor.py](../../systems/construction_editor.py): `show_tech` (function; selector `status`) |
| `btech/mechrep.c::tmplcmp` | General; AUD-TEMPLATES; active | [data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.lookup` (method)<br>[data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.scan` (method) |
| `btech/mechrep.c::unable_to_find_proper_type` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `runtime_part` (function) |

<a id="c-btech-mine-c"></a>

### `btech/mine.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/mine.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/mine.c::add_mine` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `add_mine` (function) |
| `btech/mine.c::add_mine_on_map` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `recalculate_minefields` (inline) |
| `btech/mine.c::explode_mines` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `explode_mines` (function) |
| `btech/mine.c::make_mine_explode` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `make_mine_explode` (function) |
| `btech/mine.c::map_add_mine` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `map_add_mine` (function) |
| `btech/mine.c::mine_damage_mechs` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `make_mine_explode` (inline) |
| `btech/mine.c::possible_mine_explosion` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `possible_mine_explosion` (function) |
| `btech/mine.c::possible_mine_poof` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `possible_mine_poof` (function) |
| `btech/mine.c::possibly_remove_mines` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `possibly_remove_mines` (function) |
| `btech/mine.c::recalculate_minefields` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `recalculate_minefields` (function) |
| `btech/mine.c::show_mines_in_hex` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `show_mines_in_hex` (function) |
| `btech/mine.c::update_mine` | General; AUD-SPECIAL-COMBAT; active | [systems/mines.py](../../systems/mines.py): `make_mine_explode` (inline) |

<a id="c-btech-pcombat-c"></a>

### `btech/pcombat.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/pcombat.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/pcombat.c::armor_effect` | General; AUD-PILOTS; active | [systems/personal_damage.py](../../systems/personal_damage.py): `personal_armor_effect` (function) |
| `btech/pcombat.c::dam_to_pc_conversion` | General; AUD-PILOTS; active | [systems/personal_damage.py](../../systems/personal_damage.py): `damage_to_personal` (function) |
| `btech/pcombat.c::pc_to_dam_conversion` | General; AUD-PILOTS; active | [systems/personal_damage.py](../../systems/personal_damage.py): `personal_to_damage` (function) |
| `btech/pcombat.c::pcombat_hitloc` | General; AUD-PILOTS; active | [systems/personal_damage.py](../../systems/personal_damage.py): `personal_location` (function) |

<a id="c-btech-template-c"></a>

### `btech/template.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/btech/template.c) · [Historical Aerospace C](https://github.com/KrugerHeavyIndustries/btmux/blob/96f2131705a7fe51c3c6f7da741930ff06a93644/src/hcode/btech/template.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `btech/template.c::AmmoIFromString` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `legacy_ammo_id` (function) |
| `btech/template.c::BuildBitString` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `bit_names` (function) |
| `btech/template.c::BuildBitString2` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `bit_names2` (function) |
| `btech/template.c::BuildBitString3` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `bit_names3` (function) |
| `btech/template.c::BuildBitStringwdelim2` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `bit_names_delim2` (function) |
| `btech/template.c::BuildBitVector` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `parse_bit_vector` (function) |
| `btech/template.c::BuildBitVectorNoErr` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `parse_bit_vector_lenient` (function) |
| `btech/template.c::BuildBitVectorWithDelim` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `parse_bit_vector_delim` (function) |
| `btech/template.c::CheckSpecialsList` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `check_specials_list` (function) |
| `btech/template.c::compare_array` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `name_index` (function) |
| `btech/template.c::computer_conversion` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `computer_conversion` (function) |
| `btech/template.c::count_special_items` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `count_special_items` (function) |
| `btech/template.c::DefaultFuelByType` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `default_fuel_by_type` (function) |
| `btech/template.c::DefaultFuelByType` | Historical Aerospace; AUD-AEROSPACE; active | [data/templates.py](../../data/templates.py): `default_fuel_by_type` (function) |
| `btech/template.c::dump_item` | General; AUD-TEMPLATES; active | [data/template_files.py](../../data/template_files.py): `dump_item` (function) |
| `btech/template.c::dump_locations` | General; AUD-TEMPLATES; active | [data/template_files.py](../../data/template_files.py): `dump_locations` (function) |
| `btech/template.c::DumpMechSpecialObjects` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.special_dump` (method) |
| `btech/template.c::dumpweapon_fun` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.weapon_dump` (method) |
| `btech/template.c::DumpWeapons` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.weapon_dump` (method) |
| `btech/template.c::find_section` | General; AUD-TEMPLATES; active | [data/template_files.py](../../data/template_files.py): `find_section` (function) |
| `btech/template.c::generic_computer_multiplier` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `generic_computer_multiplier` (function) |
| `btech/template.c::generic_radio_multiplier` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `generic_radio_multiplier` (function) |
| `btech/template.c::generic_radio_type` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `generic_radio_type` (function) |
| `btech/template.c::get_weight` | General; AUD-TEMPLATES; active | [systems/construction_weight.py](../../systems/construction_weight.py): `get_weight` (function) |
| `btech/template.c::InvalidVehicleItem` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `invalid_vehicle_item` (function) |
| `btech/template.c::load_template` | General; AUD-TEMPLATES; active | [data/template_files.py](../../data/template_files.py): `load_template` (function)<br>[data/template_files.py](../../data/template_files.py): `load_stream` (function)<br>[data/template_files.py](../../data/template_files.py): `load_critical` (function)<br>[data/template_files.py](../../data/template_files.py): `finish_load` (function) |
| `btech/template.c::load_template` | Historical Aerospace; AUD-AEROSPACE; active | [data/template_files.py](../../data/template_files.py): `load_template / load_stream` (function)<br>[data/template_files.py](../../data/template_files.py): `load_critical` (function)<br>[data/template_directory.py](../../data/template_directory.py): `TemplateDirectory.loadnew` (method)<br>[data/template_catalog.py](../../data/template_catalog.py): `CatalogDirectory.loadnew` (method) |
| `btech/template.c::my_shortform` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `short_form` (function) |
| `btech/template.c::one_arg` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `next_arg` (function) |
| `btech/template.c::one_arg_delim` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `next_arg_delim` (function) |
| `btech/template.c::part_figure_out_name` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.generate` (method; selector `vlong`) |
| `btech/template.c::part_figure_out_name_sub` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.generate` (method; selector `long/vlong`) |
| `btech/template.c::part_figure_out_shname` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.generate` (method; selector `short`) |
| `btech/template.c::part_figure_out_sname` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `Catalog.generate` (method; selector `long`) |
| `btech/template.c::partlist_func` | General; AUD-TEMPLATES; active | [systems/parts.py](../../systems/parts.py): `partlist` (function) |
| `btech/template.c::payloadlist_func` | General; AUD-TEMPLATES; active | [systems/parts.py](../../systems/parts.py): `payloadlist` (function) |
| `btech/template.c::read_desc` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `read_brace_block` (function) |
| `btech/template.c::save_template` | General; AUD-TEMPLATES; active | [data/template_files.py](../../data/template_files.py): `save_template` (function)<br>[data/template_files.py](../../data/template_files.py): `saved_specials` (function) |
| `btech/template.c::techlist_func` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `tech_list` (function) |
| `btech/template.c::try_to_find_name` | General; AUD-TEMPLATES; active | [data/template_files.py](../../data/template_files.py): `save_template` (function; selector `empty-name lookup`) |
| `btech/template.c::update_oweight` | General; AUD-TEMPLATES; active | [data/templates.py](../../data/templates.py): `update_oweight` (function) |
| `btech/template.c::update_specials` | General; AUD-TEMPLATES; active | [systems/parts.py](../../systems/parts.py): `update_specials` (function) |
| `btech/template.c::WeaponIFromString` | General; AUD-TEMPLATES; active | [data/construction_catalog.py](../../data/construction_catalog.py): `weapon_id` (function) |

<a id="c-events-c"></a>

### `events.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/events.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `events.c::debug_EventTypes` | General; AUD-CORE; active | [core/events.py](../../core/events.py): `EventQueue.debug_event_types` (method)<br>[core/events.py](../../core/events.py): `EventQueue.history_rows` (method)<br>[core/events.py](../../core/events.py): `EventQueue.pending_rows` (method) |
| `events.c::muxevent_count_initialize` | General; AUD-CORE; active | [core/events.py](../../core/events.py): `EventQueue.initialize_history` (method) |
| `events.c::postrun_event` | General; AUD-CORE; inactive/empty | [core/events.py](../../core/events.py): `postrun_event` (function) |
| `events.c::prerun_event` | General; AUD-CORE; inactive/empty | [core/events.py](../../core/events.py): `prerun_event` (function) |

<a id="c-mech-lostracer-c"></a>

### `mech.lostracer.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/mech.lostracer.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `mech.lostracer.c::GetAdjHex` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `get_adj_hex` (function) |
| `mech.lostracer.c::TraceLOS` | General; AUD-SENSORS; active | [systems/los.py](../../systems/los.py): `trace_los` (function) |

<a id="c-mt19937ar-c"></a>

### `mt19937ar.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/mt19937ar.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `mt19937ar.c::genrand_int31` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.int31` (method)<br>[core/randomness.py](../../core/randomness.py): `RandomState.number` (method) |
| `mt19937ar.c::genrand_int32` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.int32` (method) |
| `mt19937ar.c::genrand_real1` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.real1` (method) |
| `mt19937ar.c::genrand_real2` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.real2` (method) |
| `mt19937ar.c::genrand_real3` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.real3` (method) |
| `mt19937ar.c::genrand_res53` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.res53` (method) |
| `mt19937ar.c::init_by_array` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.init_by_array` (method) |
| `mt19937ar.c::init_genrand` | General; AUD-CORE; active | [core/mt19937.py](../../core/mt19937.py): `MT19937.seed` (method) |

<a id="c-tick-c"></a>

### `tick.c`

[General C](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/btech/src/tick.c)

| C source identity | Profile / module / activity | Python file and symbol |
|---|---|---|
| `tick.c::heartbeat_dispatch` | General; AUD-CORE; active | [core/game_loop.py](../../core/game_loop.py): `GameEngine.heartbeat_dispatch` (method)<br>[core/game_loop.py](../../core/game_loop.py): `GameEngine.auto_heartbeat` (method) |
| `tick.c::heartbeat_init` | General; AUD-CORE; active | [core/game_loop.py](../../core/game_loop.py): `GameEngine.heartbeat_init` (method) |
| `tick.c::heartbeat_run` | General; AUD-CORE; active | [core/game_loop.py](../../core/game_loop.py): `GameEngine.heartbeat` (method) |
| `tick.c::heartbeat_stop` | General; AUD-CORE; active | [core/game_loop.py](../../core/game_loop.py): `GameEngine.heartbeat_stop` (method) |
