# Credits and source provenance

BTMux Engine is a Python reimplementation of the BTMux simulation. Its
repository is named `btmux-python`; it is installed as `btmux-engine`.
Original authors retain their copyrights. The port carries forward the exact
[3030MUX Artistic License](LICENSE) and the additional notices below.

## BTMux lineage and contributors

The [upstream history](https://github.com/KrugerHeavyIndustries/btmux/blob/037f611cd0c81e75d82c82d0bbe2b2622970990c/README.md)
traces the simulation to TinyMUSE and 3056 MUSE around 1992–1993, the Animudiacs
crew's TinyMUSH work (including 3034-II/3035 and Varxsis), and Markus Stenberg's
TinyMUX adaptation for 3030 MUX. Development continued through the 3030 team,
the Exile: Exodus branch, the release under the 3030MUX Artistic License, and
later BTMux contributors. The original host also draws on TinyMUD, TinyMUSH,
PennMUSH and TinyMUX; their acknowledgments and terms are retained in the
[TinyMUX notice](notices/TinyMUX.txt).

The [original BTMux credits](notices/BTMux-CREDITS.txt) are reproduced unchanged.
They credit Guzzer and Crew, Fingon, Kip, Focus, Null/DJ, Kelvin McCorvin,
Hagbard, Daniel MacGregor (including the new AI system), Power_Shaper, Scotty,
NeverWhere, Stringfellow Hawke and Fitz. Roles described as “current” in that
file refer to its upstream release. The upstream history identifies Markus
Stenberg as Fingon, Thomas Wouters as Focus, Cord Awtry as Spectre, and Kevin
Stevens as Null.

The C files used by the port preserve the following additional attributions:

| Contributor | Examples of original notices |
|---|---|
| Markus Stenberg, Thomas Wouters, Cord Awtry and Kevin Stevens | Simulation, events, equipment, construction, combat, maps and Battlesheep files; individual years and scopes are retained in the source notices. |
| Marco Peter Hoogeveen | `bsuit.c`, copyright 1999–2000. |
| Nim | `failures.c`, “Written by: Nim”, dated 9-28-96; that file also credits Thomas Wouters. |
| Dr. Martin Brumm | `mech.pickup.c`, copyright 2002. |
| Gregory Taylor | `mech.physical.c`, copyright 2005–2006. |
| Martin Murray | `tick.c`, copyright 2005. |
| rdm and jb | Original `map.c` author/modification initials, dated 4.8.93 and 6.16.93. |
| Makoto Matsumoto, Takuji Nishimura and Mutsuo Saito | MT19937, with the original 1997–2002 and 2005 notices and redistribution terms. |

For files lacking attribution, the upstream README's rule assigns the original
host `src/` material to David Passmore and `src/hcode/` or other directories to
Markus Stenberg. The general revision's simulation is under `btech/src/`;
the historical simulation is under `src/hcode/`. “Original author: unknown”
and older initials remain as written where the source records them.

## Source versions and the Python port

| Source | Revision and scope |
|---|---|
| [General BTMux](https://github.com/KrugerHeavyIndustries/btmux/tree/037f611cd0c81e75d82c82d0bbe2b2622970990c) | `037f611cd0c81e75d82c82d0bbe2b2622970990c`, principally `btech/src/`, with referenced event/configuration support in `btech/btpr/` and `src/`. |
| [Historical Aerospace](https://github.com/KrugerHeavyIndustries/btmux/tree/96f2131705a7fe51c3c6f7da741930ff06a93644) | `96f2131705a7fe51c3c6f7da741930ff06a93644`, `src/hcode/`, before the AT2 conversion: six-location fighters, DropShips and shared Aerospace branches. |

Version `0.1.0` is the 2026 Python adaptation maintained for
[alex-milenkovic/btmux-python](https://github.com/alex-milenkovic/btmux-python).
C routines, structures, constants and display tables have been reimplemented
as Python modules, with local entity, event, session and storage services.
The source comments identify the applicable C files. Their 2026 date records
the Python adaptation; 2026-10-12 dates this revision's attribution notices,
without claiming an exact first-translation day for pre-existing modules.

The source distribution contains the modified Python source and documentation.
The wheel contains Python runtime source, acceptance helpers, catalogue pin
and packaged notices. The optional unit-template catalogue remains a separate
dependency with its own notices and unchanged pin. Graphical presentation and
live client transport belong to clients; the original MUX host infrastructure
is not bundled as a server in this engine.

The repository's `docs/porting/C_TO_PYTHON.md` supplies the detailed source/profile
crosswalk; `docs/porting/COMPLETION.md` records implementation scope and validation.
Both are included in the source distribution. Wheel users can obtain them from
the source repository. They describe the selected general and historical
behavior, including the documented heat, skill-default and weather adaptations.

## Retained notices

The following files accompany both the source distribution and wheel. In an
installed wheel they are under `btmux_engine-0.1.0.dist-info/licenses/`, retaining
the paths shown here.

| File | Purpose |
|---|---|
| [LICENSE](LICENSE) | Unchanged general upstream `COPYING`; its bytes also match the historical Aerospace `LICENSE`. This is the custom 3030MUX Artistic License, not Artistic 1.0 or 2.0. |
| [BTMux source notices](notices/BTMux.txt) | Original notice/comment blocks for the mapped simulation files and the referenced structures, tables and support sources. |
| [Original BTMux credits](notices/BTMux-CREDITS.txt) | Unchanged upstream `doc/CREDITS`, preserving the wider community acknowledgments. |
| [TinyMUX notice](notices/TinyMUX.txt) | Unchanged upstream `src/copyright.h` (also identical in `btech/btpr/include/`), including all five conditions and the Kevin Stevens feature notice. Retained for the host-derived configuration/timer portions referenced by the Python adapters. |
| [MT19937 notice](notices/MT19937.txt) | Complete original `mt19937ar.c` notice, conditions and disclaimer. The existing notice in `core/mt19937.py` is also intact. |

Package metadata uses the locally defined references
`LicenseRef-3030MUX-Artistic` (LICENSE), `LicenseRef-TinyMUX`
(`notices/TinyMUX.txt`) and `LicenseRef-MT19937` (`notices/MT19937.txt`), joined
with `AND` to record the included terms. These are descriptive references to
the actual texts, not claims of standard Artistic licensing or relicensing
of third-party material. Each component retains its applicable notices.

The BattleTech/WizKids ownership and permission paragraph in LICENSE is a
historical statement from the original upstream release.
