# Historical six-location fighters

`python3 -m tools.aerospace --input ./tmp/fighter.json` exposes the existing
construction, pilot, flight, combat, bombing and damage services in one public
JSON session. The fighter rules follow historical revision
`96f2131705a7fe51c3c6f7da741930ff06a93644`; DropShips retain their separate rules.

| Index | Canonical section | Legal critical slots |
|---:|---|---:|
| 0 | Nose | 12 |
| 1 | Left Wing | 12 |
| 2 | Right Wing | 12 |
| 3 | Fuselage | 12 |
| 4 | Cockpit | 5 |
| 5 | Engine | 12 |

Template/editor slots are one-based. JSON section/slot indices and weapon
numbers are zero-based. Critical snapshots keep the common eight-by-twelve
backing storage. `critstatus`, `status`, `weaponstatus` and construction readouts
use live six-location names and equipment.

Load the unchanged `CHP-W5` through the existing `template` operation. Either use
the configured read-only catalog (`construction.catalog:true`, with
`BTMUX_TEMPLATE_CATALOG` selecting its directory), or copy its unchanged text
into the session's `construction.files` adapter. Writable construction, pilot
and map roots must be writable and separate from the original catalog; `./tmp/`
is one suitable example, not a required location.
See [construction inputs](construction-templates-cli.md) and
[aerospace inputs](aerospace-cli.md) for the complete session schema.

An ordinary session has a clear level map, a unit with a real local character,
and these actions after load:

```json
[
  {"op":"personnel","unit":"u","kind":"attach","player":110},
  {"op":"command","unit":"u","name":"startup"},
  {"op":"advance","seconds":30},
  {"op":"command","unit":"u","name":"speed","args":"60"},
  {"op":"advance","seconds":10},
  {"op":"command","unit":"u","name":"takeoff"},
  {"op":"advance","seconds":12},
  {"op":"command","unit":"u","name":"climb","args":"0"},
  {"op":"command","unit":"u","name":"thrust","args":"40"},
  {"op":"advance","seconds":6},
  {"op":"command","unit":"u","name":"land"},
  {"op":"inspect"}
]
```

The pilot needs the ordinary Aerospace piloting skill. Broad gunnery defaults
use `Gunnery-Aerospace` for fighters and `Gunnery-Spacecraft` for DropShips.
Weapon-family gunnery applies when `config.extended_gunnery` is explicitly
`true`; see the [core skill configuration](core-simulation-cli.md#defaults-and-fixtures).
Startup seats the character and schedules six boot stages. Takeoff needs
actual taxi speed at least 32.25. Use sufficient clear runway and map space.
The normal acceptance workflow executes this sequence without assigning speed,
fuel, thrust or successful flight results after loading.

CHP-W5 retains armor `24,15,15,30,16,20`, internals 10 in each section, 11
physical weapons, five Fuselage ammo bins, 750 fuel, 25 sinks and maximum speed
86. Its absent SI field remains zero and does not make the craft destroyed.
File load clears the pilot; attach one before ordinary commands. `resetcrits`
is a separate builder command that installs Cockpit and Engine defaults; loading
a design preserves its physical contents without filling its empty slots.

Use `fire` with a zero-based mount number and visible contact, such as `0 BB`
for the first Nose laser or `2 BB` for an LRM-15. Observe actual slot cooldown,
heat, Fuselage ammo and target armor. Missile groups apply sequentially. Fuselage
weapons cover all arcs, Engine weapons cover the rear, and Cockpit has no firing
arc. A functional weapon in an armor-depleted fighter section can fire, but its
subsequent cooldown freezes while the section remains depleted.

For boundary cases, the existing `diagnose` operation calls production damage
and critical functions. For example:

```json
{"op":"diagnose","unit":"u","kind":"damage",
 "options":{"section":"Nose","amount":8,"internal":true,"transfer":true}}
```

`transfer` defaults to false. A normal hit depletes positive armor and discards
excess; the next hit on that empty section routes to Fuselage. A hit reaching
already-empty Fuselage destroys the craft, regardless of SI. Internal-only
fighter damage also hits armor. Explicit transfer forwards excess, subject to
CASE/Clan containment for an internal entry. Actual ammo explosions enable that
entry themselves. Cockpit hits use shared pilot injury; Cockpit depletion kills
the craft. Engine depletion zeros thrust and schedules airborne falling.

Other existing diagnostics include `location` (legacy/FASA/critproof),
`crittable`, `critical`, `slot`, `transfer`, `weapon-count`, `weapon-type`,
`aim-location` and `tc-location`. They expose actual side effects and ordered
draws; they do not accept expected results. Fighter partial-armor gate draws use
1..11, full-armor gates use 1..71, and direct weapon selection uses
`fighter_weapon_choice` over 0..N-1. See [damage inputs](damage-criticals-cli.md).

Normal `aim Cockpit` adds +7 against an immobile target and +25 against a mobile
target for non-missile weapons, before targeting-computer precedence. Ordinary
aiming accepts all six locations; TC aiming retains historical aspect masks
and vehicle-switch fallthrough. The `sight` result exposes the BTH breakdown.

Save with `{"op":"template","unit":"u","kind":"save","reference":"copy"}`
to a new local reference, then load it in a fresh process. Save serializes design
armor/internals and full ammo capacity, including depleted sections; it is not
a combat-state checkpoint. Bomb payload remains physical slots and uses the
existing `bomb list`, `bomb aim`, `bomb drop N` commands and timed impact events.

The public editor can equip a local copy before flight:

```json
{"op":"editor","editor":"e","name":"addbomb","args":"Bomb_10_Standard F 12"}
```

`addbomb <Bomb_name> <section> <slot>` requires an editor target and the existing
editor privilege checks. It validates the template catalog's bomb name and the
section's legal slot limit, then installs the physical part through the template
critical parser. This construction affordance was added for public equipment
setup; it is not a claimed historical C command. It does not execute bombing or
assign an impact outcome. Normal cargo recalculation and bombing use that part.

Normal APS verification:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/tmp" python3 -m tools.run_acceptance --suite six_location_aerofighters
```

All six features are parsed, generated and executed. Public workflows live in
`acceptance/six_location_aerofighters/workflows.py`. See
[QA prerequisites](../qa/README.md) for optional developer tools and source inputs.
Original files and the historical source remain read-only.
