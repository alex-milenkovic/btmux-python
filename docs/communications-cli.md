# C3 and communications CLI

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m tools.communications --input ./tmp/input.json`
or supply the JSON document on stdin. This extends the [Pilots CLI](pilots-cli.md),
[Combat CLI](combat-resolution-cli.md), and [Core CLI](core-simulation-cli.md):
real maps, templates, characters, clocks, criticals, mines, startup/shutdown,
movement and firing use the existing engine. Use isolated storage under `./tmp/`
for scratch runs. Characters retain their existing durable skill/XP format.

The result is `{results, state, draws}`. `state.inboxes` maps local recipient IDs
to ordered raw messages. It is independent of unit diagnostic message logs.
`state.units.<name>.communications` shows channel arrays, encoded radio type,
C3/C3i `{size, slots, peers}`, CommXP timestamp and autopilot reference. The fixed
source arrays have 11 C3 or 5 C3i slots, padded with -1; `peers` is the stored
prefix, not a promise that every entry is currently usable. Existing snapshots
also expose unit radio range, XP requests and external effects.

`state.external_notification_requests` records the unexecuted MUX
notify_checked forwarding/listener/client-transport requests for local messages.
Each includes recipient, raw message and `applied:false`; repeated calls remain
separate. Inboxes prove local reception only. Frequency-abuse, zero-frequency,
AI diagnostics and XP server-channel requests remain separately named external
effects; no MUX server connection is created.

Legacy AUTO objects without configured services report an unapplied parser or
reply dependency. Registered Battlesheep controllers install built-in services:
received radio text goes through `autopilot_receive` to the controller parser,
and the parser request is marked `applied:true`. Controller replies use the
engine event/radio path. See the [autopilot interface](autopilot-cli.md) for
controller creation, radio orders and replies. This local AI path does not
apply the separate external MUX notification requests.

## Commands

Commands use `{"op":"command","unit":"A","name":"c3i","args":"BB"}`.
Arguments can be a string, retaining source whitespace, or an array joined by
spaces. Existing commands keep their established argument conventions.

| Command | Arguments / behavior |
|---|---|
| `c3`, `c3i` | Two-character contact ID joins; `-` leaves. |
| `c3message`, `c3imessage` | Text; leading whitespace removed, raw source network prefix retained. |
| `c3targets`, `c3itargets` | Ordered, masked contacts with real and shared range. |
| `c3network`, `c3inetwork` | Current usable peers and source status rows. |
| `setchannelfreq` | `a=17`; source integer-prefix parser and exact-zero rules. |
| `setchanneltitle` | `a=Ops`; title stores at most 15 ASCII bytes. |
| `setchannelmode` | `a=DI`, `a=DE`; D digital, I info, U mute, E relay, S scan, source color letters. |
| `listfreqs` (`listchannels` alias) | Source four-character mode columns. |
| `sendchannel` | `a=hello`; real delivery, relay, scan, scramble, CommXP and command-mine processing. |
| `radio` | `BB=hello`; direct ordinary-LOS radio with its own eligibility rules. |

Keep the source parser quirks: uppercase `A` in sendchannel is invalid while
uppercase `Z` selects channel A; nonletter selectors default to A. Setter commands
use ordinary case-insensitive letters. Source gate order and error text are
retained. Shutdown, ECM and unconsciousness have different effects on stored
membership, contribution and reception. Digital relays use the origin's range
and current geometry; INFO headers describe the actual selected path.

## Fixture inputs and diagnostics

A unit's optional `communications` object accepts `radio_type`, `radio_range`,
`freq`, `freqmodes`, `chantitle`, `comm`, `comm_last`, `autopilot`, `last_use`,
`specials`, `specials2`, `crit_status`, `status`, `status2`,
`working_c3_masters`, `total_c3_masters`, `mapindex`, `tank_crit_status`,
`stagger_damage`, `c3_network`, `c3_network_size`, `c3i_network`,
`c3i_network_size`, `aero_turrets`, `allocated`, `faction`, and `map_ic`.
Network/turret arrays accept registered unit names or integer IDs. Encoded radio
114 means two channels with relay, info and scan capabilities (114 % 16 = 2;
114 // 16 = 7). C3i tech is specials2 bit32. Ordinary creation should use real
templates/equipment; explicit counters and arrays are source diagnostics.

The diagnostic operation is `communications_diagnose` with a `kind` and optional
`unit`/`target`. It calls the production functions directly. Available kinds:

| Kinds | Additional inputs |
|---|---|
| `configure` | `values`: same communication fixture object. |
| `network`, `validate`, `temporary`, `reports` | `ordinary` (default true). |
| `clear` | `ordinary`, `propagate` (default true). |
| `remove`, `replicate`, `add`, `free` | `target`, `ordinary`. |
| `masters`, `master-window` | Window uses numeric `section`, `slot`. |
| `range`, `network-visibility` | `target`, `ordinary`; range also `distance`, `reference`. |
| `identity`, `status`, `flags`, `color` | Identity/status use target; status `index`1..5; flags `spaces`,`level`; color `index`,`observer`,`team`. |
| `notify` | `audience`0 pilot /1 started /2 all; `message`. |
| `map-broadcast`, `mech-broadcast`, `los-broadcast`, `pair-broadcast` | `message`; optional target for mech broadcast, required target for pair. Pair message has one `%s`. |
| `limited-broadcast`, `hex-broadcast` | `x`,`y`,`message`; limited also `z`,`radius`,`dimensions`2/3 in real coordinates. |
| `common-checks` | `actor` numeric character ID, `flags` numeric source mask. |
| `route`, `route-graph` | Route uses target and frequency; graph uses square `edges`; optional `recursive`. |
| `scramble`, `scramble-bytes`, `transmit` | Scramble: message, distance, sender_range, receiver_range, title, bth, ecm, digital. Bytes: message, chance, bth. Transmit: index, message. |
| `ammo`, `fire-letter`, `debug` | Ammo: weapon name, mode. Fire: mode. Debug is silent by default. |

These diagnostics supplement ordinary commands; raw network arrays or synthetic
route graphs do not demonstrate formation, actual firing or delivery. Undefined
source domains (oversized network/route arrays, out-of-allocation critical
windows, radio input buffers without a terminator, signed-char scramble overflow,
scanner division by zero) raise explicit errors. Defined snprintf truncation is
retained for output buffers.

Radio randomness uses the existing source stream: `radio_number` for Number and
`radio_roll` for Roll. Other operations can consume their own streams, including
sensor detection, combat and experience. Follow Core's finite-stream rules when
supplying `random.streams`; a partial finite stream is rejected on a missing
consumer. A seeded simulation can instead use the existing PRNG. Emergency MW
channel creation retains Pilots' separate `pilots.radio_draws` host-random source.

## Verification scope

The independent public-interface driver runs with:

```sh
python -B -m qa.communications
```

The optional acceptance pipeline runs all families, including ordinary workflows:

```sh
python -B -m tools.run_acceptance --suite c3_communications
```

See [QA prerequisites](../qa/README.md) for the external feature parser and C
reference requirements. `--only` selects a feature in the acceptance runner;
`--family` selects a family in the independent driver.

Additional source diagnostics used by independent QA:

- `temporary` accepts `check_ecm`, `check_started` and `check_unconscious` booleans
  to expose the existing distinct source helper gates.
- `temp-member` and `other-member` accept `ordinary` and `index`; the latter also
  accepts the three gate booleans. They return the resolved unit ID or null.
- `move-label`, `arc-label` (`arc` bitmask), `slot-letters` (`section`, `slot`) and
  `percentages` expose actual presentation functions and physical slot modes.
- `identity` accepts `null_viewer`, `null_target` and temporary `source_id` for
  explicit source object-domain diagnostics. IDs are restored after the call.
- `notify` and `printf` accept temporary `source_id`; `printf` also accepts
  `format_args`. The ordinary recipient registry remains the source of delivery.
- `common-checks` accepts `null_unit` to test the source null-data guard.

These operations are explicit diagnostics, not substitutes for ordinary
formation, firing, transfers or real recipient inboxes.


QA procedure affordances also available to other CLI users:

- `personnel` with `kind:"caller"`, `unit` and `player` selects an existing local
  character as the command caller, retaining the unit's pilot and occupants.
- `hulldown` dispatches the existing movement command with its ordinary caller
  checks; use a QUAD with supported ground state.
- `schedule` accepts `vehicle_burn_event` and `vehicle_extinguish_event`, with
  `unit`, `delay`, and optional integer `data` (burn section). These schedule the
  real callbacks; they are explicit event diagnostics, not ordinary ignition.
