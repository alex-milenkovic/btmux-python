# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   btech/src/include/btconfig.h

"""
Pilot entity for BTMux Python reimplementation.

The C has no pilot struct: a machine stores a `dbref pilot` handle (mech.h:933)
and reads the numbers back out of that player object's skill attributes on
demand (`char_getskilltarget`, called from FindPilotPiloting / FindPilotGunnery,
mech.utils.c:580-629).  This module is the Python stand-in for "whatever object
MechPilot() points at" - the skills only, since M1 keeps pilot injury state on
the Mech (`mech.pilot_hits`, mirroring `MechPilotStatus`, mech.h:922).

Skill resolution itself lives in systems/piloting.py (`find_pilot_piloting`,
`find_spilot_piloting`, `find_pilot_gunnery`) because the C chain is keyed off
the machine, not the pilot.

Reference:
- BTMux btech/src/btech/mech.h line 933 - dbref pilot (the pilot handle)
- BTMux btech/src/btech/btmacros.h lines 58-72 - GotPilot/RGotPilot validity
- BTMux btech/src/btech/mech.utils.c lines 580-629 - skill resolution chain
- BTMux btech/src/include/btconfig.h lines 179-183 - DEFAULT_* fallbacks

Deliberate divergence from the C: when no pilot is present the C falls back to
DEFAULT_GUNNERY 6 / DEFAULT_PILOTING 6 (btconfig.h:179-180).  The factory
defaults below are gunnery 4 / piloting 5 instead, because the Python port's
entire test suite is calibrated to 4/5 (e.g. systems/combat.py's BTH base).
The C values are recorded as C_DEFAULT_GUNNERY / C_DEFAULT_PILOTING
documentation-asserts in tests/test_constants.py.
"""

from dataclasses import dataclass


# =============================================================================
# Pilot
# =============================================================================

@dataclass
class Pilot:
    """
    A MechWarrior: the skill numbers the resolution chain reads.

    In the C these live on the player object the machine's `pilot` dbref points
    at and are fetched per call by `char_getskilltarget` (mech.utils.c:588,
    627).  Skill names are per unit class / weapon class
    (`FindPilotingSkillName` mech.utils.c:513-565, `FindGunnerySkillName`
    mech.utils.c:457-511); M1 collapses those to one piloting and one gunnery
    number - see the TODO in systems/piloting.find_pilot_gunnery.

    Injuries/consciousness stay on the Mech (`mech.pilot_hits`) as they do in
    the C (`MechPilotStatus`, mech.h:922), so this stays skills-only.

    Reference: mech.h line 933 - dbref pilot
    """

    name: str = "MechWarrior"
    gunnery: int = 4                 # Divergence: C DEFAULT_GUNNERY is 6 (btconfig.h:179)
    piloting: int = 5                # Divergence: C DEFAULT_PILOTING is 6 (btconfig.h:180)
    perception: int = 6
