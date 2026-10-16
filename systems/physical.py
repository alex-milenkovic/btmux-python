# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/mech.build.c
#   btech/mech.notify.c
#   btech/mech.physical.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/map.h
#   btech/src/btech/mech.h
#   btech/src/btech/mech.physical.h
#   btech/src/include/btconfig.h
#   src/conf.c

"""
Physical attack system for BTMux Python reimplementation.

Port of BTMux btech/src/btech/mech.physical.c:
- Punch / Claw (mech.physical.c:340-387, 591-644)
- Club (mech.physical.c:392-446, shatter at 1430-1445)
- Axe / Saw / Mace / Sword (mech.physical.c:451-789)
- Kick / Trip (mech.physical.c:791-865, trip resolution 1499-1520)
- Charge (command 867-993, resolution ChargeMech 1908-2660)
- Grabclub / Dropclub (mech.physical.c:2665-2786, DropClub btmacros.h:858)
- PhysicalAttack core (mech.physical.c:1001-1483)
- PhysicalDamage (mech.physical.c:1522-1695)
- Death From Above (legacy port, C alignment out of scope for E.7)

Config directives (src/conf.c:91-143 defaults), patched module-level in tests:
- BTECH_PHYS_USE_PSKILL = 1: physical base BTHs derive from piloting skill.
- BTECH_GLANCING_BLOWS = 1: roll == BTH is a glancing blow (half damage).
- BTECH_NEWCHARGE = 0: classic velocity-based charge damage.
- BTECH_TL3_CHARGE = 0: classic attacker self-damage on charge.
"""

from __future__ import annotations
from core.randomness import roll as source_roll
import math
from contextvars import ContextVar
from functools import wraps
from systems.notifications import identity, mech_notify, MECHALL, MECHSTARTED, MECHPILOT
from systems.parts import armor_string
from physics.collision import mech_rterrain
from dataclasses import dataclass, field
from enum import IntEnum, auto
from core.randomness import draw, float32
from systems.mines import real_tons
from systems.combat_ranges import config
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from entities.mech import Mech

from entities.mech import (
    Location, MechStatus, MechStatus2, CritStatus, SectionConfig, Specials,
    FireMode, UnitType, MoveType, VehicleLocation,
)
from entities.crittypes import Special, i2special
from entities.map import (HEAVY_FOREST, LIGHT_FOREST, SMOKE,
                          MAPFLAG_NOFRIENDLYFIRE, MAPFLAG_NOPHYSICALS)
from systems.combat import (
    HitGroup, determine_hit_group, get_hit_location, get_punch_location,
    get_kick_location, apply_damage_with_transfer, roll_1d6, roll_2d6,
    calculate_attacker_movement_modifier, calculate_target_movement_modifier,
    MP1,
)
from systems.piloting import (
    make_piloting_roll, check_for_fall, PilotingCheckReason,
    find_pilot_piloting, find_spilot_piloting,
)
from physics.jump import mech_falls
from physics.hexmath import (
    hex_distance, in_weapon_arc, FORWARDARC, LSIDEARC, RSIDEARC, SCALEMAP,
)


# =============================================================================
# Config directives (src/conf.c:91-143 defaults)
# =============================================================================

BTECH_PHYS_USE_PSKILL = 1     # src/conf.c - piloting-derived physical BTHs
BTECH_GLANCING_BLOWS = 1      # src/conf.c - roll == BTH nicks for half damage
BTECH_NEWCHARGE = 0           # src/conf.c - distance-based charge damage
BTECH_TL3_CHARGE = 0          # src/conf.c - TL3 attacker charge self-damage

# Pilot preference bits read by the physical safety gates (mech.h:746,753);
# read off a getattr-guarded `mech.prefs` attr (default 0 = fresh pilot).
MECHPREF_PKILL = 0x00000001
MECHPREF_NOFRIENDLYFIRE = 0x00000080


# =============================================================================
# Physical Attack Constants
# =============================================================================

# Recycle time in ticks after a physical attack (PHYSICAL_RECYCLE_TIME,
# btconfig.h)
PHYSICAL_RECYCLE_TIME = 60

# Section special: arm is carrying an improvised club (CARRYING_CLUB, mech.h).
# Lives here as a module constant, same pattern as systems/ecm.py's
# INARC_ECM_ATTACHED.
CARRYING_CLUB = 0x20

# Movement-path charge trigger/timeout (btconfig.h:175-176); the movement-side
# hook (physics/movement.py) fires charge_mech() when range < CHARGE_DIST_TRIGGER.
CHARGE_DIST_TRIGGER = 0.6
CHARGE_TIMER_LIMIT = 60

# KPH -> MP conversion (mech.h:54 - MP1 is 10.75 KPH per MP)
MP_PER_KPH = 0.0930233

# Arm-selection bit flags (P_LEFT/P_RIGHT, mech.physical.h)
P_LEFT = 1
P_RIGHT = 2

# TSM heat threshold (mech.physical.c:1546 - MechHeat >= 9.)
TSM_HEAT_THRESHOLD = 9

# ChargeMech recycles these six sections (resect, mech.physical.c:1697-1703)
CHARGE_SECTIONS = 6
RESECT = (Location.LARM, Location.RARM, Location.LLEG, Location.RLEG,
          Location.LTORSO, Location.RTORSO)


class PhysicalAttackType(IntEnum):
    """Types of physical attacks (PA_*, mech.physical.h)."""
    PUNCH = auto()
    KICK = auto()
    CHARGE = auto()
    DFA = auto()
    CLUB = auto()
    AXE = auto()
    SWORD = auto()
    SAW = auto()
    CLAW = auto()
    MACE = auto()
    TRIP = auto()


# phys_form (mech.physical.c:79-156). QUIRK ported as written: PA_MACE
# returns "maces" even in the no-s branch (mech.physical.c:128-130).
PHYS_FORM = {
    PhysicalAttackType.PUNCH: "punch",
    PhysicalAttackType.CLUB: "club",
    PhysicalAttackType.MACE: "maces",   # C quirk - verbatim (mech.physical.c:128-130)
    PhysicalAttackType.SWORD: "chop",
    PhysicalAttackType.AXE: "axe",
    PhysicalAttackType.KICK: "kick",
    PhysicalAttackType.TRIP: "trip",
    PhysicalAttackType.SAW: "saw",
    PhysicalAttackType.CLAW: "claw",
}

# ArmorStringFromIndex equivalents for mechs (mech.build.c naming).
LOCATION_NAMES = {
    Location.LARM: "left arm",
    Location.RARM: "right arm",
    Location.LTORSO: "left torso",
    Location.RTORSO: "right torso",
    Location.CTORSO: "center torso",
    Location.LLEG: "left leg",
    Location.RLEG: "right leg",
    Location.HEAD: "head",
}


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class PhysicalAttackResult:
    """Result of a physical attack (or a refused attack command)."""
    success: bool = False           # Attack was attempted (gates passed)
    hit: bool = False
    attack_type: PhysicalAttackType = PhysicalAttackType.PUNCH
    roll: int = 0
    bth: int = 0
    glancing: bool = False
    damage_dealt: int = 0
    location_hit: Optional[Location] = None
    attacker_fell: bool = False
    target_fell: bool = False
    is_rear: bool = False
    attacker_damage: int = 0        # Damage to attacker (charge/DFA)
    message: str = ""               # First/primary message
    messages: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.messages.append(msg)
        if not self.message:
            self.message = msg

    def notice(self, unit, msg, audience=MECHALL):
        self.add(msg)
        if not getattr(msg, 'notified', False):
            mech_notify(unit, audience, msg)

    def broadcast(self, unit, msg):
        from systems.sensors import los_broadcast
        self.add(msg)
        los_broadcast(unit, msg)


@dataclass
class ChargeResult:
    """Result of ChargeMech resolution (mech.physical.c:1908-2660)."""
    mutual: bool = False
    attacker_charging: bool = False   # mech_charge eligibility flag
    target_charging: bool = False     # target_charge eligibility flag
    attacker_hit: bool = False
    target_hit: bool = False
    attacker_bth: int = 0
    target_bth: int = 0
    attacker_roll: int = 0
    target_roll: int = 0
    damage_to_target: int = 0         # inflicted by attacker
    damage_to_attacker: int = 0       # attacker's self-damage (one-sided) or
                                      # damage inflicted by target (mutual)
    attacker_self_damage: int = 0
    target_self_damage: int = 0
    messages: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.messages.append(msg)


# =============================================================================
# Crit / section helpers
# =============================================================================

_NONFUNCTIONAL = (FireMode.DESTROYED_MODE | FireMode.BROKEN_MODE |
                  FireMode.DISABLED_MODE)


def part_is_nonfunctional(mech: 'Mech', loc: Location, slot: int) -> bool:
    """PartIsNonfunctional (btmacros.h:324): destroyed/broken/disabled crit."""
    return bool(mech.sections[loc].criticals[slot].firemode & _NONFUNCTIONAL)


def get_part_type(mech: 'Mech', loc: Location, slot: int) -> int:
    """GetPartType (btmacros.h): raw crit type in a slot."""
    return mech.sections[loc].criticals[slot].type


def okay_crit_sect(mech: 'Mech', loc: Location, slot: int,
                   special: Special) -> bool:
    """OkayCritSectS: slot holds the given Special and it is functional."""
    return (get_part_type(mech, loc, slot) == i2special(special)
            and not part_is_nonfunctional(mech, loc, slot))


def find_obj(mech: 'Mech', loc: Location, crit_type: int) -> int:
    """
    FindObj (mech.utils.c:2508-2517): count crits of the given type in a
    location that are FUNCTIONAL only - destroyed/nonfunctional crits do NOT
    count.
    """
    count = 0
    for slot, crit in enumerate(mech.sections[loc].criticals):
        if crit.type == crit_type and not part_is_nonfunctional(mech, loc, slot):
            count += 1
    return count


def sect_has_busy_weap(mech: 'Mech', loc: Location) -> bool:
    """
    SectHasBusyWeap (mech.utils.c:168-180): true iff ANY weapon in the given
    section is currently recycling.
    """
    from systems.weapon_inventory import find_weapons
    from systems.combat import part_is_nonfunctional
    runs = find_weapons(mech, loc) or []
    return not mech.is_section_destroyed(loc) and any(
        run.data > 0 and not part_is_nonfunctional(mech, loc, run.critical)
        for run in runs)


def sect_is_destroyed(mech: 'Mech', loc: Location) -> bool:
    """SectIsDestroyed (btmacros.h)."""
    from systems.damage import section_destroyed
    return section_destroyed(mech,loc)


def set_recycle_limb(mech: 'Mech', loc: Location, time: int) -> None:
    """SetRecycleLimb (mech.utils.c): section recycle counter."""
    if mech._engine is not None:
        from core.game_loop import update_recycling
        update_recycling(mech._engine, mech)
    mech.sections[loc].recycle = time


def unit_class(mech: 'Mech') -> UnitType:
    """MechType(mech)."""
    return getattr(mech, 'unit_type', UnitType.MECH)


def is_quad(mech: 'Mech') -> bool:
    """MechIsQuad (btmacros.h): MechMove == MOVE_QUAD."""
    return getattr(mech, 'move_type', MoveType.BIPED) == MoveType.QUAD


def count_destroyed_legs(mech: 'Mech') -> int:
    """CountDestroyedLegs (mech.utils.c): quads count front legs (arms)."""
    from systems.parts import count_destroyed_legs as shared_count
    return shared_count(mech)


def _has_melee_specialist(mech: 'Mech') -> bool:
    """HasBoolAdvantage(MechPilot, "melee_specialist"); default off."""
    from systems.characters import actor_advantage
    return actor_advantage(getattr(mech, 'pilot', None), 'Melee_Specialist')


def _mech_range(mech: 'Mech', target: 'Mech') -> float:
    """FaMechRange equivalent: range in hexes from cartesian coordinates."""
    from systems.targeting import find_range
    return find_range(mech.fx,mech.fy,mech.fz,target.fx,target.fy,target.fz)


def ground_elevation(unit):
    from entities.map import WATER,ICE
    terrain=unit.map.rterrain(unit.x,unit.y) if unit.map else unit.terrain
    return -abs(unit.elev) if terrain in (WATER,ICE) else abs(unit.elev)


def carrying_club(mech: 'Mech') -> bool:
    """CarryingClub (btmacros.h): either arm has CARRYING_CLUB set."""
    return bool((mech.sections[Location.LARM].specials & CARRYING_CLUB) or
                (mech.sections[Location.RARM].specials & CARRYING_CLUB))


# =============================================================================
# Weapon-presence helpers (mech.physical.c:174-215)
# =============================================================================

def have_punch(mech: 'Mech', loc: Location) -> bool:
    """have_punch (mech.physical.c:175-178): always true."""
    return True


def have_axe(mech: 'Mech', loc: Location) -> bool:
    """have_axe (mech.physical.c:183-186): AXE crits >= tons/15."""
    return find_obj(mech, loc, i2special(Special.AXE)) >= mech.tonnage // 15


def have_claw(mech: 'Mech', loc: Location) -> bool:
    """have_claw (mech.physical.c:188-191): CLAW crits >= tons/15."""
    return find_obj(mech, loc, i2special(Special.CLAW)) >= mech.tonnage // 15


def have_saw(mech: 'Mech', loc: Location) -> bool:
    """have_saw (mech.physical.c:196-199): DUAL_SAW crits >= 7."""
    return find_obj(mech, loc, i2special(Special.DUAL_SAW)) >= 7


def have_sword(mech: 'Mech', loc: Location) -> bool:
    """have_sword (mech.physical.c:204-208): SWORD crits >= (tons+15)/20."""
    return (find_obj(mech, loc, i2special(Special.SWORD)) >=
            (mech.tonnage + 15) // 20)


def have_mace(mech: 'Mech', loc: Location) -> bool:
    """have_mace (mech.physical.c:213-216): MACE crits >= tons/10."""
    return find_obj(mech, loc, i2special(Special.MACE)) >= mech.tonnage // 10


# =============================================================================
# Common physical gates
# =============================================================================

_command_actor = ContextVar('physical_command_actor', default=None)


def _command_guard(unit):
    from systems.combat_commands import command_guard
    context = _command_actor.get()
    if context is not None and context[0] is unit:
        return command_guard(unit, caller=context[1], wizard=context[2])
    return command_guard(unit)


def _unit_notice(unit, message):
    from systems.combat_commands import NotifiedError
    if not getattr(message, 'notified', False):
        mech_notify(unit, MECHALL, message)
    return NotifiedError(message)


def _caller_notice(unit, message):
    from systems.combat_commands import NotifiedError
    from core.effects import notify_actor
    context = _command_actor.get()
    actor = context[1] if context is not None and context[0] is unit else unit.pilot
    if not getattr(message, 'notified', False):
        notify_actor(unit, actor, message)
    return NotifiedError(message)


def _physical_check(check):
    @wraps(check)
    def checked(unit, *args, **kwargs):
        ok, message = check(unit, *args, **kwargs)
        return ok, _unit_notice(unit, message) if not ok and message else message
    return checked


def _caller_check(check):
    @wraps(check)
    def checked(unit, *args, **kwargs):
        message = check(unit, *args, **kwargs)
        return _caller_notice(unit, message) if message else message
    return checked


@_physical_check
def all_limbs_recycled(mech: 'Mech') -> tuple[bool, str]:
    """all_limbs_recycled (mech.physical.c:59-74)."""
    if (mech.sections[Location.LARM].recycle or
            mech.sections[Location.RARM].recycle):
        return (False, "You still have arms recovering from another attack.")
    if (mech.sections[Location.RLEG].recycle or
            mech.sections[Location.LLEG].recycle):
        return (False, "Your legs are still recovering from your last attack.")
    return (True, "")


@_physical_check
def phys_common_checks(mech: 'Mech') -> tuple[bool, str]:
    """phys_common_checks (mech.physical.c:220-244)."""
    if mech.is_jumping:
        return (False, "You can't perform physical attacks while in the air!")
    from systems.movement_commands import pending
    from systems.movement_commands import mode_locked
    if pending(mech, '_stand_event'):
        return (False, "You are still trying to stand up!")
    # Dodging / MoveModeLock gate (mech.physical.c:232-237).
    if mech.has_status2(MechStatus2.DODGING) or mode_locked(mech):
        return (False, "You cannot use physicals while using a special "
                       "movement mode.")
    return all_limbs_recycled(mech)


def get_arm_args(arm_arg: Optional[str], mech: 'Mech',
                 have_fn: Callable[['Mech', Location], bool],
                 weapon: str) -> tuple[int, Optional[str]]:
    """
    get_arm_args (mech.physical.c:251-305): parse B/L/R arm selection and
    strip arms that lack the weapon.

    Returns (using_flags, error_message). error_message is set only for the
    single-arm refusals; both-arm mode silently strips missing arms.
    """
    using = P_LEFT | P_RIGHT
    if arm_arg:
        arm = arm_arg[0].upper()
        if arm == 'B':
            using = P_LEFT | P_RIGHT
        elif arm == 'L':
            using = P_LEFT
        elif arm == 'R':
            using = P_RIGHT

    if using == P_LEFT:
        if not have_fn(mech, Location.LARM):
            return (using, _unit_notice(mech, f"You don't have {weapon} in your left arm!"))
    elif using == P_RIGHT:
        if not have_fn(mech, Location.RARM):
            return (using, _unit_notice(mech, f"You don't have {weapon} in your right arm!"))
    else:
        if not have_fn(mech, Location.LARM):
            using &= ~P_LEFT
        if not have_fn(mech, Location.RARM):
            using &= ~P_RIGHT
    return (using, None)


# =============================================================================
# Per-arm checks (mech.physical.c:313-335, 451-476, 524-544, 646-671, 718-743)
# =============================================================================

@_physical_check
def punch_check_arm(mech: 'Mech', arm: Location) -> tuple[bool, str]:
    """punch_checkArm (mech.physical.c:313-335)."""
    arm_used = "left" if arm == Location.LARM else "right"
    if sect_is_destroyed(mech, arm):
        return (False, f"Your {arm_used} arm is destroyed, you can't punch "
                       "with it.")
    if not okay_crit_sect(mech, arm, 0, Special.SHOULDER_OR_HIP):
        return (False, f"Your {arm_used} shoulder is destroyed, you can't "
                       "punch with that arm.")
    if mech.sections[arm].specials & CARRYING_CLUB:
        return (False, f"You're carrying a club in your {arm_used} arm and "
                       "can't punch with it.")
    return (True, "")


@_physical_check
def axe_check_arm(mech: 'Mech', arm: Location) -> tuple[bool, str]:
    """axe_checkArm (mech.physical.c:451-476)."""
    arm_used = "right" if arm == Location.RARM else "left"
    if sect_is_destroyed(mech, arm):
        # C quirk: no trailing period in this message - verbatim.
        return (False, f"Your {arm_used} arm is destroyed, you can't axe "
                       "with it")
    if not okay_crit_sect(mech, arm, 0, Special.SHOULDER_OR_HIP):
        return (False, f"Your {arm_used} shoulder is destroyed, you can't "
                       "axe with that arm.")
    if not okay_crit_sect(mech, arm, 3, Special.HAND_OR_FOOT_ACTUATOR):
        # C quirk (mech.physical.c:466-469): the format string has no %s, so
        # the message always says "left hand" regardless of arm - verbatim.
        return (False, "Your left hand is destroyed, you can't axe with "
                       "that arm.")
    return (True, "")


@_physical_check
def saw_check_arm(mech: 'Mech', arm: Location) -> tuple[bool, str]:
    """saw_checkArm (mech.physical.c:524-544): no hand actuator needed."""
    arm_used = "right" if arm == Location.RARM else "left"
    if sect_is_destroyed(mech, arm):
        # C quirk: no trailing period - verbatim.
        return (False, f"Your {arm_used} arm is destroyed, you can't saw "
                       "with it")
    if not okay_crit_sect(mech, arm, 0, Special.SHOULDER_OR_HIP):
        return (False, f"Your {arm_used} shoulder is destroyed, you can't "
                       "saw with that arm.")
    return (True, "")


@_physical_check
def mace_check_arm(mech: 'Mech', arm: Location) -> tuple[bool, str]:
    """mace_checkArm (mech.physical.c:646-671)."""
    arm_used = "right" if arm == Location.RARM else "left"
    if sect_is_destroyed(mech, arm):
        return (False, f"Your {arm_used} arm is destroyed, you can't use a "
                       "mace with it.")
    if not okay_crit_sect(mech, arm, 0, Special.SHOULDER_OR_HIP):
        return (False, f"Your {arm_used} shoulder is destroyed, you can't "
                       "use a mace with that arm.")
    if not okay_crit_sect(mech, arm, 3, Special.HAND_OR_FOOT_ACTUATOR):
        return (False, f"Your {arm_used} hand is destroyed, you can't use a "
                       "mace with that arm.")
    return (True, "")


@_physical_check
def sword_check_arm(mech: 'Mech', arm: Location) -> tuple[bool, str]:
    """sword_checkArm (mech.physical.c:718-743)."""
    arm_used = "right" if arm == Location.RARM else "left"
    if sect_is_destroyed(mech, arm):
        return (False, f"Your {arm_used} arm is destroyed, you can't use a "
                       "sword with it.")
    if not okay_crit_sect(mech, arm, 0, Special.SHOULDER_OR_HIP):
        return (False, f"Your {arm_used} shoulder is destroyed, you can't "
                       "use a sword with that arm.")
    if not okay_crit_sect(mech, arm, 3, Special.HAND_OR_FOOT_ACTUATOR):
        return (False, f"Your {arm_used} hand is destroyed, you can't use a "
                       "sword with that arm.")
    return (True, "")


# =============================================================================
# Command-layer helpers
# =============================================================================

def _fail(mech, attack_type: PhysicalAttackType, msg: str) -> PhysicalAttackResult:
    result = PhysicalAttackResult(attack_type=attack_type)
    result.notice(mech, msg)
    return result


@_caller_check
def _arm_phys_check(mech: 'Mech', verb: str) -> Optional[str]:
    """
    ARM_PHYS_CHECK macro (mech.physical.c:35-39): MWs/bsuits get the
    "without a 'mech" text, every other non-mech class the "vehicle" text.
    """
    error=_command_guard(mech)
    if error:return error
    if unit_class(mech) in (UnitType.MW, UnitType.BSUIT):
        return f"You cannot {verb} without a 'mech!"
    if unit_class(mech) != UnitType.MECH:
        return f"You cannot {verb} with this vehicle!"
    return None


@_caller_check
def _quad_check(mech: 'Mech', verb: str) -> Optional[str]:
    """QUAD_CHECK macro (mech.physical.c:52-54)."""
    if unit_class(mech) == UnitType.MECH and is_quad(mech):
        return (f"What are you going to {verb} with, your front right "
                f"leg?")
    return None


def _base_tohit(mech: 'Mech', pskill_offset: int, flat: int) -> int:
    """
    btech_phys_use_pskill switch: piloting-derived base (DEFAULT) or flat
    constant (mech.physical.c:359-361, 441-444, 509-511, 563-565, 614-616,
    691-693, 764-766, 861-863).
    """
    if config(mech,'phys_use_pskill',BTECH_PHYS_USE_PSKILL):
        return find_pilot_piloting(mech) + pskill_offset
    return flat


def _arm_command(mech: 'Mech', target: Optional['Mech'], arm_arg: Optional[str],
                 attack_type: PhysicalAttackType, verb: str,
                 damage_weight: int, pskill_offset: int, flat_bth: int,
                 have_fn, weapon_name: str, check_arm_fn,
                 no_weapon_msg: str, common_checks_first: bool,
                 roll: Optional[int],
                 location_roll: Optional[int]) -> list[PhysicalAttackResult]:
    """Shared skeleton for the per-arm commands (punch/axe/saw/claw/mace/sword)."""
    msg = _arm_phys_check(mech, verb)
    if msg:
        return [_fail(mech, attack_type, msg)]
    msg = _quad_check(mech, verb)
    if msg:
        return [_fail(mech, attack_type, msg)]

    tohit = _base_tohit(mech, pskill_offset, flat_bth)

    using, err = get_arm_args(arm_arg, mech, have_fn, weapon_name)
    if err:
        return [_fail(mech, attack_type, err)]

    # PA_PUNCH/PA_CLAW run phys_common_checks at the command layer to avoid
    # double-spam when both arms attack (mech.physical.c:371-372, 619-620);
    # for the others PhysicalAttack itself performs it (:1022-1028).
    if common_checks_first:
        ok, msg = phys_common_checks(mech)
        if not ok:
            return [_fail(mech, attack_type, msg)]

    results: list[PhysicalAttackResult] = []
    for flag, arm in ((P_LEFT, Location.LARM), (P_RIGHT, Location.RARM)):
        if not (using & flag):
            continue
        if check_arm_fn is not None:
            ok, msg = check_arm_fn(mech, arm)
            if not ok:
                results.append(_fail(mech, attack_type, msg))
                continue
        results.append(physical_attack(mech, damage_weight, tohit,
                                       attack_type, arm, target, roll=roll,
                                       location_roll=location_roll))

    # C: DOCHECKMA(!using, ...) after the attack loop.
    if not using:
        results.append(_fail(mech, attack_type, no_weapon_msg))
    return results


# =============================================================================
# Physical attack commands
# =============================================================================

def mech_punch(mech: 'Mech', target: Optional['Mech'] = None,
               arm: Optional[str] = None, roll: Optional[int] = None,
               location_roll: Optional[int] = None) -> list[PhysicalAttackResult]:
    """mech_punch (mech.physical.c:340-387): tons/10, base piloting or 4."""
    return _arm_command(
        mech, target, arm, PhysicalAttackType.PUNCH, "punch",
        damage_weight=10, pskill_offset=0, flat_bth=4,
        have_fn=have_punch, weapon_name="",
        check_arm_fn=punch_check_arm,
        no_weapon_msg="",               # unreachable: have_punch is always true
        common_checks_first=True, roll=roll, location_roll=location_roll)


def mech_club(mech: 'Mech', target: Optional['Mech'] = None,
              roll: Optional[int] = None,
              location_roll: Optional[int] = None) -> PhysicalAttackResult:
    """mech_club (mech.physical.c:392-446): tons/5, base piloting-1 or 4."""
    at = PhysicalAttackType.CLUB
    msg = _arm_phys_check(mech, "club")
    if msg:
        return _fail(mech, at, msg)
    msg = _quad_check(mech, "club")
    if msg:
        return _fail(mech, at, msg)

    club_loc = -1
    if mech.sections[Location.RARM].specials & CARRYING_CLUB:
        club_loc = Location.RARM
    elif mech.sections[Location.LARM].specials & CARRYING_CLUB:
        club_loc = Location.LARM

    if club_loc == -1:
        # Improvised tree club needs forest terrain (mech.physical.c:412-416)
        if mech_rterrain(mech) not in (HEAVY_FOREST, LIGHT_FOREST):
            return _fail(mech, at, "You can not seem to find any trees around to "
                             "club with.")
        # Since we have trees nearby, assume the club goes to right hand.
        club_loc = Location.RARM

    if sect_is_destroyed(mech, Location.LARM):
        return _fail(mech, at, "Your left arm is destroyed, you can't club.")
    if sect_is_destroyed(mech, Location.RARM):
        return _fail(mech, at, "Your right arm is destroyed, you can't club.")
    if not okay_crit_sect(mech, Location.RARM, 0, Special.SHOULDER_OR_HIP):
        return _fail(mech, at, "You can't club anyone with a destroyed or missing "
                         "right shoulder.")
    if not okay_crit_sect(mech, Location.LARM, 0, Special.SHOULDER_OR_HIP):
        return _fail(mech, at, "You can't club anyone with a destroyed or missing "
                         "left shoulder.")
    if not okay_crit_sect(mech, Location.RARM, 3, Special.HAND_OR_FOOT_ACTUATOR):
        return _fail(mech, at, "You can't club anyone with a destroyed or missing "
                         "right hand.")
    if not okay_crit_sect(mech, Location.LARM, 3, Special.HAND_OR_FOOT_ACTUATOR):
        return _fail(mech, at, "You can't club anyone with a destroyed or missing "
                         "left hand.")

    # Clubbing requires both arms cycled, but PhysicalAttack only checks one;
    # check both here (mech.physical.c:436-438, SectHasBusyWeap per
    # mech.utils.c:168-180).
    if (sect_has_busy_weap(mech, Location.LARM) or
            sect_has_busy_weap(mech, Location.RARM)):
        return _fail(mech, at, "You have weapons recycling on your arms.")

    # C passes RARM as the attacking section regardless of clubLoc
    # (mech.physical.c:441-444) - clubLoc only matters for the shatter.
    return physical_attack(mech, 5, _base_tohit(mech, -1, 4), at,
                           Location.RARM, target, roll=roll,
                           location_roll=location_roll)


def mech_axe(mech: 'Mech', target: Optional['Mech'] = None,
             arm: Optional[str] = None, roll: Optional[int] = None,
             location_roll: Optional[int] = None) -> list[PhysicalAttackResult]:
    """mech_axe (mech.physical.c:478-522): tons/5, base piloting-1 or 4."""
    return _arm_command(
        mech, target, arm, PhysicalAttackType.AXE, "axe",
        damage_weight=5, pskill_offset=-1, flat_bth=4,
        have_fn=have_axe, weapon_name="an axe",
        check_arm_fn=axe_check_arm,
        no_weapon_msg="You may lack the axe, but not the will! Try punch/club "
                      "until you find one.",
        common_checks_first=False, roll=roll, location_roll=location_roll)


def mech_saw(mech: 'Mech', target: Optional['Mech'] = None,
             arm: Optional[str] = None, roll: Optional[int] = None,
             location_roll: Optional[int] = None) -> list[PhysicalAttackResult]:
    """mech_saw (mech.physical.c:546-589): flat 7 damage, base piloting-1 or 4."""
    return _arm_command(
        mech, target, arm, PhysicalAttackType.SAW, "saw",
        damage_weight=7, pskill_offset=-1, flat_bth=4,
        have_fn=have_saw, weapon_name="a saw",
        check_arm_fn=saw_check_arm,
        no_weapon_msg="You don't have a dual saw!",
        common_checks_first=False, roll=roll, location_roll=location_roll)


def mech_claw(mech: 'Mech', target: Optional['Mech'] = None,
              arm: Optional[str] = None, roll: Optional[int] = None,
              location_roll: Optional[int] = None) -> list[PhysicalAttackResult]:
    """
    mech_claw (mech.physical.c:591-644): tons/7, base piloting or 4.

    C quirk ported as written: unlike every other arm attack, mech_claw calls
    PhysicalAttack WITHOUT a per-arm check function (mech.physical.c:625-634),
    so destroyed arms/shoulders are not refused at the command layer.
    """
    return _arm_command(
        mech, target, arm, PhysicalAttackType.CLAW, "claw",
        damage_weight=7, pskill_offset=0, flat_bth=4,
        have_fn=have_claw, weapon_name="a claw",
        check_arm_fn=None,
        no_weapon_msg="You do not have any claws! Try punching/clubbing "
                      "instead!",
        common_checks_first=True, roll=roll, location_roll=location_roll)


def mech_mace(mech: 'Mech', target: Optional['Mech'] = None,
              arm: Optional[str] = None, roll: Optional[int] = None,
              location_roll: Optional[int] = None) -> list[PhysicalAttackResult]:
    """mech_mace (mech.physical.c:673-716): tons/4, base piloting-1 or 4."""
    return _arm_command(
        mech, target, arm, PhysicalAttackType.MACE, "mace",
        damage_weight=4, pskill_offset=-1, flat_bth=4,
        have_fn=have_mace, weapon_name="a mace",
        check_arm_fn=mace_check_arm,
        no_weapon_msg="You don't have a mace!",
        common_checks_first=False, roll=roll, location_roll=location_roll)


def mech_sword(mech: 'Mech', target: Optional['Mech'] = None,
               arm: Optional[str] = None, roll: Optional[int] = None,
               location_roll: Optional[int] = None) -> list[PhysicalAttackResult]:
    """mech_sword (mech.physical.c:745-789): (tons+5)/10+1, base piloting-2 or 3."""
    return _arm_command(
        mech, target, arm, PhysicalAttackType.SWORD, "chop",
        damage_weight=10, pskill_offset=-2, flat_bth=3,
        have_fn=have_sword, weapon_name="a sword",
        check_arm_fn=sword_check_arm,
        no_weapon_msg="You have no sword to chop people with!",
        common_checks_first=False, roll=roll, location_roll=location_roll)


def mech_kick(mech: 'Mech', target: Optional['Mech'] = None,
              arm: Optional[str] = None, roll: Optional[int] = None,
              location_roll: Optional[int] = None) -> PhysicalAttackResult:
    """mech_kick (mech.physical.c:801-804)."""
    return mech_kickortrip(mech, PhysicalAttackType.KICK, target, arm, roll,
                           location_roll)


def mech_trip(mech: 'Mech', target: Optional['Mech'] = None,
              arm: Optional[str] = None, roll: Optional[int] = None,
              location_roll: Optional[int] = None) -> PhysicalAttackResult:
    """mech_trip (mech.physical.c:793-796)."""
    return mech_kickortrip(mech, PhysicalAttackType.TRIP, target, arm, roll,
                           location_roll)


def mech_kickortrip(mech: 'Mech', attack_type: PhysicalAttackType,
                    target: Optional['Mech'] = None,
                    arm: Optional[str] = None, roll: Optional[int] = None,
                    location_roll: Optional[int] = None) -> PhysicalAttackResult:
    """
    mech_kickortrip (mech.physical.c:791-865): tons/5 damage, base
    piloting-2 or 3.
    """
    error=_arm_phys_check(mech,"kick")
    if error:return _fail(mech, attack_type,error)
    rl, ll = Location.RLEG, Location.LLEG
    # Quads kick with their front legs, which live in the arm slots
    # (mech.physical.c:820-823).
    if is_quad(mech):
        rl, ll = Location.RARM, Location.LARM

    # GENERIC_CHECK("kick", CountDestroyedLegs(mech)) (mech.physical.c:825;
    # macro home mech.physical.h). Messages verbatim from the identical
    # expansion in mech_charge (mech.physical.c:900-910).
    dead_legs = count_destroyed_legs(mech)
    if not is_quad(mech) and dead_legs > 1:
        return _fail(mech, attack_type, _caller_notice(mech, "Without legs? Are you kidding?"))
    if not is_quad(mech) and dead_legs > 0:
        return _fail(mech, attack_type, _caller_notice(mech, "With one leg? Are you kidding?"))
    if dead_legs > 1:
        return _fail(mech, attack_type, _caller_notice(mech, "It'd unbalance you too much in your condition.."))
    if dead_legs > 2:
        return _fail(mech, attack_type, _caller_notice(mech, "Exactly _what_ are you going to kick with?"))

    using, err = get_arm_args(arm, mech, have_punch, "")
    if err:
        return _fail(mech, attack_type, err)
    if arm is None:
        using = P_RIGHT            # C default: int using = P_RIGHT (:799)

    if using == P_LEFT:
        leg = ll
    elif using == P_RIGHT:
        leg = rl
    else:
        # "b" (both legs) makes no sense for a kick (mech.physical.c:842-846).
        return _fail(mech, attack_type,
                     "What, yer gonna LEVITATE? I Don't Think So.")

    if mech.has_crit_status(CritStatus.HIP_DAMAGED):
        return _fail(mech, attack_type, f"You can't {PHYS_FORM[attack_type]} with "
                                  "a destroyed hip.")

    return physical_attack(mech, 5, _base_tohit(mech, -2, 3), attack_type,
                           leg, target, roll=roll, location_roll=location_roll)


# =============================================================================
# PhysicalAttack core (mech.physical.c:1001-1483)
# =============================================================================

def physical_attack(mech: 'Mech', damage_weight: int, base_tohit: int,
                    attack_type: PhysicalAttackType, sect: Location,
                    target: Optional['Mech'] = None,
                    roll: Optional[int] = None,
                    location_roll: Optional[int] = None) -> PhysicalAttackResult:
    """
    PhysicalAttack (mech.physical.c:1001-1483): gates, BTH assembly, roll,
    recycle and resolution for all non-charge physicals.
    """
    result = PhysicalAttackResult(attack_type=attack_type)
    at = attack_type
    ARM_ATTACKS = (PhysicalAttackType.PUNCH, PhysicalAttackType.KICK,
                   PhysicalAttackType.AXE, PhysicalAttackType.SWORD,
                   PhysicalAttackType.CLAW, PhysicalAttackType.MACE,
                   PhysicalAttackType.SAW)

    # PA_PUNCH/PA_CLAW already ran this at the command layer
    # (mech.physical.c:1022-1028).
    if at not in (PhysicalAttackType.PUNCH, PhysicalAttackType.CLAW):
        ok, msg = phys_common_checks(mech)
        if not ok:
            result.notice(mech, msg)
            return result

    # BTH adjustments for actuator crits (mech.physical.c:1030-1076).
    if at in ARM_ATTACKS:
        if (part_is_nonfunctional(mech, sect, 1) or
                get_part_type(mech, sect, 1) != i2special(Special.UPPER_ACTUATOR)):
            base_tohit += 2
        if (part_is_nonfunctional(mech, sect, 2) or
                get_part_type(mech, sect, 2) != i2special(Special.LOWER_ACTUATOR)):
            base_tohit += 2
        # Hand/foot crits only affect punch/kick (mech.physical.c:1047-1053).
        if at in (PhysicalAttackType.PUNCH, PhysicalAttackType.KICK):
            if (part_is_nonfunctional(mech, sect, 3) or
                    get_part_type(mech, sect, 3) !=
                    i2special(Special.HAND_OR_FOOT_ACTUATOR)):
                base_tohit += 1
    elif at == PhysicalAttackType.CLUB:
        # Club checks both arms' upper/lower actuators. C QUIRK ported as
        # written (mech.physical.c:1057-1075): the GetPartType half of every
        # check reads `sect` (RARM), so the LARM checks test LARM
        # functionality but RARM part type.
        if (part_is_nonfunctional(mech, Location.RARM, 1) or
                get_part_type(mech, sect, 1) != i2special(Special.UPPER_ACTUATOR)):
            base_tohit += 2
        if (part_is_nonfunctional(mech, Location.RARM, 2) or
                get_part_type(mech, sect, 2) != i2special(Special.LOWER_ACTUATOR)):
            base_tohit += 2
        if (part_is_nonfunctional(mech, Location.LARM, 1) or
                get_part_type(mech, sect, 1) != i2special(Special.UPPER_ACTUATOR)):
            base_tohit += 2
        if (part_is_nonfunctional(mech, Location.LARM, 2) or
                get_part_type(mech, sect, 2) != i2special(Special.LOWER_ACTUATOR)):
            base_tohit += 2

    # All weapons must be cycled in the attacking limb (mech.physical.c:1079-1085).
    if sect_has_busy_weap(mech, sect):
        result.notice(mech, f"You have weapons recycling on your "
                   f"{armor_string(mech,sect)}.")
        return result

    # Resolve only after common/limb checks, separately for each attacking arm.
    from systems.targeting import resolve_unit, contact_target
    if isinstance(target, str):
        target = contact_target(mech, target[:2])
        if target is None:
            result.notice(mech, "Target is not in line of sight!")
            return result
    elif target is None:
        if mech.target == -1:
            result.notice(mech, "You do not have a target set!")
            return result
        target = resolve_unit(mech, mech.target)
        if target is None:
            result.notice(mech, "Invalid default target!")
            return result

    # Is the target swarming us? (mech.physical.c:1113).
    from systems.combat_firing import swarm_id
    swarming_us = swarm_id(target)==mech._id

    # Fallen-attacker matrix, ported as written (mech.physical.c:1119-1146).
    # QUIRK: branch 1 catches kicks/trips against every target class first, so
    # the vehicle branch's PA_PUNCH exclusion below is partially shadowed.
    if mech.is_fallen and at in (PhysicalAttackType.KICK,
                                 PhysicalAttackType.TRIP):
        result.notice(mech, f"You can't {PHYS_FORM[at]} from a prone position.")
        return result
    elif mech.is_fallen and unit_class(target) not in (UnitType.VEH_GROUND,
                                                       UnitType.BSUIT):
        result.notice(mech, f"You can't {PHYS_FORM[at]} from a prone position.")
        return result
    elif (mech.is_fallen and unit_class(target) == UnitType.BSUIT and
          not swarming_us):
        result.notice(mech, "You may only physical suits that are swarming you while "
                   "prone.")
        return result
    elif (mech.is_fallen and unit_class(target) == UnitType.VEH_GROUND and
          at != PhysicalAttackType.PUNCH):
        result.notice(mech, "You may only punch vehicles while prone.")
        return result

    range_ = _mech_range(mech, target)
    # InLineOfSight_NB gate (mech.physical.c:1150-1152); lazy import to
    # keep the module import graph acyclic.
    from systems.los import in_line_of_sight_nb
    if not in_line_of_sight_nb(mech, target, target.x, target.y, range_):
        result.notice(mech, "Target is not in line of sight!")
        return result

    max_range = 1.0
    # BSuits/MWs have to be <= 0.5 hexes (mech.physical.c:1155-1156).
    if unit_class(target) in (UnitType.BSUIT, UnitType.MW):
        max_range = 0.5
    if range_ >= max_range:
        result.notice(mech, "Target out of range!")
        return result

    if target.is_jumping:
        result.notice(mech, "You can't perform physical attacks on airborne mechs!")
        return result

    # MapNoPhysicals gate (mech.physical.c:1163, map.h:118).
    if mech.map is not None and (mech.map.flags & MAPFLAG_NOPHYSICALS):
        result.notice(mech, "You cannot perform physical attacks here!")
        return result

    # MechNoFriendlyFire / MapNoFriendlyFire team gates
    # (mech.physical.c:1165-1171).  MechPrefs (mech.h:746,753) has no
    # preference layer in the port; `mech.prefs` is a getattr-guarded plain
    # attr whose default 0 is the C's fresh-pilot preference word.
    if target.team == mech.team and \
            (getattr(mech, 'prefs', 0) & MECHPREF_NOFRIENDLYFIRE):
        result.notice(mech, "You can't attack a teammate with FFSafeties on!")
        return result
    if target.team == mech.team and mech.map is not None and \
            (mech.map.flags & MAPFLAG_NOFRIENDLYFIRE):
        result.notice(mech, "Friendly Fire? I don't think so...")
        return result

    # CLASS_MW PKiller safety gate (mech.physical.c:1173-1175).
    if unit_class(target) == UnitType.MW and \
            not (getattr(mech, 'prefs', 0) & MECHPREF_PKILL):
        result.notice(mech, "That's a living, breathing person! Switch off the "
                   "safety first, if you really want to assassinate the "
                   "target.")
        return result

    # MECH_STUNNED gate (mech.physical.c:1177-1178).
    if mech.has_crit_status(CritStatus.MECH_STUNNED):
        result.notice(mech, "You are still recovering from your stunning experience!")
        return result

    # Attack-specific checks (mech.physical.c:1181-1196).
    if (at == PhysicalAttackType.PUNCH and
            unit_class(target) == UnitType.VEH_GROUND and not mech.is_fallen):
        result.notice(mech, "You can't punch vehicles unless you are prone!")
        return result
    if at == PhysicalAttackType.TRIP and unit_class(target) != UnitType.MECH:
        result.notice(mech, "You can only trip mechs!")
        return result
    from systems.movement_commands import pending
    if at == PhysicalAttackType.TRIP and (target.is_fallen or pending(target, '_stand_event')):
        result.notice(mech, "Your target is already down!")
        return result

    # Elevation matrix, ported as written (mech.physical.c:1198-1273).
    kick_like = at in (PhysicalAttackType.KICK, PhysicalAttackType.TRIP)
    target_move = getattr(target, 'move_type', MoveType.BIPED)
    if target_move not in (MoveType.VTOL, MoveType.FLY):
        # Ground/naval target.
        if not kick_like and mech.z >= target.z:
            is_too_low = 0
            if unit_class(target) == UnitType.MECH and target.is_fallen:
                is_too_low = 1
            if (unit_class(target) == UnitType.MECH and mech.z > target.z and
                    at == PhysicalAttackType.PUNCH):
                is_too_low = 1
            if unit_class(target) not in (UnitType.MECH, UnitType.BSUIT,
                                          UnitType.DS, UnitType.SPHEROID_DS):
                is_too_low = 1
            if (at == PhysicalAttackType.PUNCH and
                    unit_class(target) == UnitType.VEH_GROUND and
                    mech.is_fallen):
                is_too_low = 0
            if (unit_class(target) == UnitType.BSUIT and
                    swarm_id(target)>0):
                result.notice(mech, "You can't directly physical suits that are "
                           "swarmed or mounted on another mech!")
                return result
            if is_too_low == 1:
                result.notice(mech, f"The target is too low in elevation for you to "
                           f"{PHYS_FORM[at]}.")
                return result

        if kick_like and mech.z < target.z:
            result.notice(mech, "The target is too high in elevation for you to kick "
                       "at.")
            return result

        if mech.z - target.z > 1 or target.z - mech.z > 1:
            result.notice(mech, "You can't attack, the elevation difference is too "
                       "large.")
            return result

        if kick_like and target.z < mech.z and (
                (unit_class(target) == UnitType.MECH and target.is_fallen) or
                unit_class(target) in (UnitType.VEH_GROUND, UnitType.BSUIT,
                                       UnitType.MW)):
            result.notice(mech, "The target is too low in elevation for you to kick.")
            return result
    else:
        # VTOL/Aero target (mech.physical.c:1249-1273). C QUIRK ported as
        # written: the first branch prints "too far away" but does NOT
        # return, falling through to the remaining checks
        # (mech.physical.c:1251-1255).
        if at != PhysicalAttackType.KICK and target.z - mech.z > 3:
            result.notice(mech, f"The target is too far away for you to "
                       f"{PHYS_FORM[at]}.")
            # no return - C fall-through quirk
        if kick_like and mech.z != target.z:
            result.notice(mech, f"The target is too far away for you to "
                       f"{PHYS_FORM[at]}.")
            return result
        if not (-1 < target.z - mech.z < 4):
            result.notice(mech, "You can't attack, the elevation difference is too "
                       "large.")
            return result

    # Weapon arc checks (mech.physical.c:1286-1322).
    if kick_like:
        # Kicks use the 'real' forward arc with torso twist stripped.
        ts = mech.status & (MechStatus.TORSO_LEFT | MechStatus.TORSO_RIGHT)
        mech.status &= ~ts
        iwa = in_weapon_arc(mech, target.fx, target.fy)
        mech.status |= ts
        if not (iwa & FORWARDARC):
            result.notice(mech, "Target is not in your 'real' forward arc!")
            return result
    else:
        iwa = in_weapon_arc(mech, target.fx, target.fy)
        if at == PhysicalAttackType.CLUB:
            # Clubs are a frontal attack (mech.physical.c:1303-1306).
            if not (iwa & FORWARDARC) and not swarming_us:
                result.notice(mech, "Target is not in your forward arc!")
                return result
        else:
            if sect == Location.RARM:
                if not ((iwa & FORWARDARC) or (iwa & RSIDEARC) or swarming_us):
                    result.notice(mech, "Target is not in your forward or right side "
                               "arc!")
                    return result
            else:
                # C QUIRK ported as written (mech.physical.c:1315-1318): the
                # `|| swarmingUs` sits OUTSIDE the negation, so a target
                # swarming us always FAILS the left-arm arc check.
                if (not ((iwa & FORWARDARC) or (iwa & LSIDEARC))) or swarming_us:
                    result.notice(mech, "Target is not in your forward or left side "
                               "arc!")
                    return result

    # Movement modifiers (mech.physical.c:1328-1334):
    # melee_specialist caps the attacker mod at 0 after a -1.
    amm = calculate_attacker_movement_modifier(mech)
    base_tohit += min(0, amm - 1) if _has_melee_specialist(mech) else amm
    base_tohit += calculate_target_movement_modifier(target, 0.0, mech)

    # BSuit terms (mech.physical.c:1337-1341).
    if unit_class(target) == UnitType.BSUIT:
        base_tohit += 1
        if at == PhysicalAttackType.KICK:
            base_tohit += 3

    # Dodging target is +2 (mech.physical.c:1343-1346; Dodging(a) =
    # MechStatus2 & DODGING, btmacros.h:886).
    if target.status2 & MechStatus2.DODGING:
        base_tohit += 2

    # Attack-type terms (mech.physical.c:1348-1358).
    if at == PhysicalAttackType.SAW:
        base_tohit += 1
    if at == PhysicalAttackType.MACE:
        base_tohit += 2
    if at == PhysicalAttackType.CLAW:
        base_tohit += 1

    # Swarmed-bsuit weapon term. C QUIRK ported as written
    # (mech.physical.c:1360-1363): the ternary's 5 branch is unreachable
    # because the guard already requires AttackType != PA_PUNCH.
    if (at != PhysicalAttackType.PUNCH and
            unit_class(target) == UnitType.BSUIT and
            swarm_id(target)>0):
        base_tohit += 3 if at != PhysicalAttackType.PUNCH else 5

    if (at == PhysicalAttackType.KICK and
            unit_class(target) == UnitType.BSUIT and
            swarm_id(target)>0):
        result.notice(mech, "You can't hit a swarmed suit with that, try a hand-held "
                   "weapon!")
        return result

    # Terrain mods (mech.physical.c:1373-1381): smoke first since it can sit
    # on top of other terrain.
    tterr = getattr(target, 'terrain', '')
    if tterr == SMOKE:
        base_tohit += 2
    elif mech_rterrain(target) == HEAVY_FOREST:
        base_tohit += 2
    elif mech_rterrain(target) == LIGHT_FOREST:
        base_tohit += 1

    result.success = True
    result.bth = base_tohit
    result.roll = roll if roll is not None else source_roll('physical_attack', roll_2d6)

    result.notice(mech, f"You try to {PHYS_FORM[at]} {identity(mech,target)}.  "
               f"BTH:  {base_tohit},\tRoll:  {result.roll}")
    result.notice(target, f"{identity(target,mech)} tries to {PHYS_FORM[at]} you!", MECHSTARTED)
    from core.effects import emit_channel
    emit_channel(mech, 'MechAttacks', f'#{mech._id} attacks #{target._id} ({PHYS_FORM[at]}) ({base_tohit}/{result.roll})')

    # Recycle the attacking section HIT OR MISS (mech.physical.c:1401).
    set_recycle_limb(mech, sect, PHYSICAL_RECYCLE_TIME)

    # Attack-specific recycles and flags (mech.physical.c:1403-1415).
    if at in (PhysicalAttackType.AXE, PhysicalAttackType.SWORD,
              PhysicalAttackType.SAW, PhysicalAttackType.MACE):
        mech.sections[sect].config |= SectionConfig.AXED
    if at == PhysicalAttackType.PUNCH:
        mech.sections[sect].config &= ~SectionConfig.AXED
    if at == PhysicalAttackType.CLUB:
        set_recycle_limb(mech, Location.LARM, PHYSICAL_RECYCLE_TIME)

    # Glancing blows (mech.physical.c:1417-1428): mode 2 lowers the effective
    # BTH by one; mode 1 (default) makes roll == BTH a half-damage nick.
    glancing=config(mech,'glancing_blows',BTECH_GLANCING_BLOWS)
    r_base_tohit = base_tohit - 1 if glancing == 2 else base_tohit
    glance = False
    if result.roll >= r_base_tohit:
        result.hit = True
        phys_succeed(mech,target,at)
        if glancing and result.roll == r_base_tohit:
            result.broadcast(target, "is nicked by a glancing blow!")
            result.notice(target, "You are nicked by a glancing blow!")
            glance = True
            result.glancing = True

        # Club always shatters on a successful hit (mech.physical.c:1430-1445).
        if at == PhysicalAttackType.CLUB:
            club_loc = -1
            if mech.sections[Location.RARM].specials & CARRYING_CLUB:
                club_loc = Location.RARM
            elif mech.sections[Location.LARM].specials & CARRYING_CLUB:
                club_loc = Location.LARM
            if club_loc != -1:
                result.notice(mech, "Your club shatters on contact.")
                result.broadcast(mech, "'s club shatters with a loud *CRACK*!")
                mech.sections[club_loc].specials &= ~CARRYING_CLUB

        if at != PhysicalAttackType.TRIP:
            physical_damage(mech, target, damage_weight, at, sect, glance,
                            result, location_roll=location_roll)
        else:
            physical_trip(mech, target, result)
    else:
        phys_fail(mech,target,at)
        # Miss handling (mech.physical.c:1449-1482).
        if unit_class(target)==UnitType.BSUIT and swarming_us:
            if not make_piloting_roll(mech,modifier=4).success:
                result.notice(mech, 'Uh oh. You miss the little buggers, but hit yourself!')
                result.broadcast(mech, 'misses, and hits itself!')
                self_hit=physical_damage(mech,mech,damage_weight,at,sect,glance,
                                         location_roll=location_roll)
                result.attacker_damage=self_hit.damage_dealt
        if at in (PhysicalAttackType.KICK, PhysicalAttackType.MACE):
            fail_roll = 0 if at == PhysicalAttackType.KICK else 2
            result.notice(mech, "You miss and try to remain standing!")
            if not make_piloting_roll(mech, modifier=fail_roll).success:
                result.notice(mech, "You lose your balance and fall down!")
                mech_falls(mech, levels=1)
                result.attacker_fell = True

    return result


# =============================================================================
# PhysicalTrip (mech.physical.c:1499-1520)
# =============================================================================

def physical_trip(mech: 'Mech', target: 'Mech',
                  result: Optional[PhysicalAttackResult] = None
                  ) -> PhysicalAttackResult:
    """
    PhysicalTrip (mech.physical.c:1499-1520): PSR+0 on the target; failure
    means MechFalls(target, 1, 0). Trips NEVER do damage.
    """
    if result is None:
        result = PhysicalAttackResult(attack_type=PhysicalAttackType.TRIP,
                                      success=True, hit=True)
    if not make_piloting_roll(target, modifier=0).success and not target.is_fallen:
        result.notice(mech, f"You trip {identity(mech,target)}!")
        result.notice(target, "You are tripped and fall to the ground!", MECHSTARTED)
        result.broadcast(target, "trips up and falls down!")
        mech_falls(target, levels=1, notify_fall=False)
        result.target_fell = True
    else:
        result.broadcast(target, "manages to stay upright!")
    return result


# =============================================================================
# PhysicalDamage (mech.physical.c:1522-1695)
# =============================================================================

def physical_damage(mech: 'Mech', target: 'Mech', weight_dmg: int,
                    attack_type: PhysicalAttackType, sect: Location,
                    glance: bool = False,
                    result: Optional[PhysicalAttackResult] = None,
                    location_roll: Optional[int] = None) -> PhysicalAttackResult:
    """
    PhysicalDamage (mech.physical.c:1522-1695): damage formula, hit-table
    selection matrix and SINGLE-lump damage application (no 5-point
    clustering).
    """
    if result is None:
        result = PhysicalAttackResult(attack_type=attack_type, success=True,
                                      hit=True)
    at = attack_type

    # Damage (mech.physical.c:1531-1556).
    if at == PhysicalAttackType.SAW:
        # Saws do a constant 7 due to their mechanical nature - TSM-immune
        # (mech.physical.c:1533-1537).
        damage = 7
    else:
        if at == PhysicalAttackType.SWORD:
            # Sword's odd weapon damage (mech.physical.c:1541-1542).
            damage = (mech.tonnage + 5) // weight_dmg + 1
        else:
            # Round down to the nearest ton - TW p145 (mech.physical.c:1545).
            damage = int(math.floor(mech.tonnage / weight_dmg))
        # TSM doubling: heat >= 9 + TSM tech (mech.physical.c:1548-1551).
        if (mech.heat >= TSM_HEAT_THRESHOLD and
                (mech.specials & Specials.TRIPLE_MYOMER_TECH)):
            damage *= 2

    # melee_specialist adds a point (mech.physical.c:1559-1561).
    if _has_melee_specialist(mech):
        damage += 1

    hit_loc: Optional[Location] = Location.LARM
    is_rear = False
    is_critical = False

    def _normal_loc() -> Location:
        nonlocal is_rear,is_critical
        from systems.hit_locations import target_hit_location
        loc,is_rear,is_critical=target_hit_location(mech,target,roll=location_roll)
        return loc
    mech_elev,target_elev=ground_elevation(mech),ground_elevation(target)

    if at == PhysicalAttackType.PUNCH:
        # Punch actuator halvings (mech.physical.c:1566-1572).
        if not okay_crit_sect(mech, sect, 2, Special.LOWER_ACTUATOR):
            damage //= 2
        if not okay_crit_sect(mech, sect, 1, Special.UPPER_ACTUATOR):
            damage //= 2

        hit_group = determine_hit_group(mech, target)
        is_rear = hit_group == HitGroup.BACK

        if unit_class(mech) == UnitType.MECH:
            if mech.is_fallen:
                # Prone punch matrix (mech.physical.c:1581-1597). C QUIRK
                # ported as written: hitloc is initialized to 0 (LARM), so a
                # combination matching no branch punches the left arm.
                hit_loc = Location.LARM
                if (unit_class(target) != UnitType.MECH or
                        (target.is_fallen and mech_elev == target_elev)):
                    hit_loc = _normal_loc()
                elif not target.is_fallen and mech_elev > target_elev:
                    hit_loc = get_punch_location(target, hit_group,
                                                 roll=location_roll)
                elif mech_elev == target_elev:
                    hit_loc = get_kick_location(target, hit_group,
                                                roll=location_roll)
            elif mech_elev < target_elev:
                if target.is_fallen or unit_class(target) != UnitType.MECH:
                    hit_loc = _normal_loc()
                else:
                    hit_loc = get_kick_location(target, hit_group,
                                                roll=location_roll)
            else:
                hit_loc = get_punch_location(target, hit_group,
                                             roll=location_roll)
        else:
            hit_loc = _normal_loc()

    elif at in (PhysicalAttackType.SWORD, PhysicalAttackType.AXE,
                PhysicalAttackType.MACE, PhysicalAttackType.CLUB):
        # Weapon matrix (mech.physical.c:1611-1637). SAW and CLAW skip
        # this matrix, retaining location0 and false rear/critical flags.
        hit_group = determine_hit_group(mech, target)
        is_rear = hit_group == HitGroup.BACK

        if unit_class(mech) == UnitType.MECH:
            if mech_elev < target_elev:
                if target.is_fallen or unit_class(target) != UnitType.MECH:
                    hit_loc = _normal_loc()
                else:
                    hit_loc = get_kick_location(target, hit_group,
                                                roll=location_roll)
            elif mech_elev > target_elev:
                hit_loc = get_punch_location(target, hit_group,
                                             roll=location_roll)
            else:
                hit_loc = _normal_loc()
        else:
            hit_loc = _normal_loc()

    elif at == PhysicalAttackType.KICK:
        # Kick actuator halvings (mech.physical.c:1641-1645).
        if not okay_crit_sect(mech, sect, 2, Special.LOWER_ACTUATOR):
            damage //= 2
        if not okay_crit_sect(mech, sect, 1, Special.UPPER_ACTUATOR):
            damage //= 2

        if target.is_fallen or unit_class(target) != UnitType.MECH:
            hit_loc = _normal_loc()
        else:
            hit_group = determine_hit_group(mech, target)
            is_rear = hit_group == HitGroup.BACK
            if mech_elev > target_elev:
                hit_loc = get_punch_location(target, hit_group,
                                             roll=location_roll)
            else:
                hit_loc = get_kick_location(target, hit_group,
                                            roll=location_roll)

    # Glancing damage (mech.physical.c:1673-1675).
    if glance:
        damage = (damage + 1) // 2

    # SINGLE-lump damage application (mech.physical.c:1678-1679: one
    # DamageMech call, no 5-point clustering).
    result.location_hit = hit_loc
    result.is_rear = is_rear
    result.damage_dealt = apply_damage_with_transfer(
        target, hit_loc, damage, is_rear=is_rear, attacker=mech,
        is_critical=is_critical, engine=mech._engine, physical=1, los=1,
        attack_pilot=mech.pilot if mech.pilot is not None else -1)

    from systems.combat_firing import swarm_id
    if target.unit_type==UnitType.BSUIT and swarm_id(target)>0 and at!=PhysicalAttackType.KICK:
        from systems.swarm import detach
        if getattr(target,'swarming',-1)>0:target.swarm_target=target.swarming
        detach(target)
        target.swarming=-1

    # Kick hit forces a PSR+0 fall check on mech targets
    # (mech.physical.c:1687-1694).
    if (unit_class(target) == UnitType.MECH and
            at == PhysicalAttackType.KICK):
        if not make_piloting_roll(target, modifier=0).success and not target.is_fallen:
            result.notice(target, "The kick knocks you to the ground!", MECHSTARTED)
            result.broadcast(target, "stumbles and falls down!")
            mech_falls(target, levels=1, notify_fall=False)
            result.target_fell = True

    return result


# =============================================================================
# Charge command (mech.physical.c:867-993)
# =============================================================================

def mech_charge(mech: 'Mech', target: Optional['Mech'] = None,
                cancel: bool = False, *, explicit: bool = True, invalid_arity: bool = False) -> PhysicalAttackResult:
    """
    mech_charge command (mech.physical.c:867-993): gates + sets the pending
    charge target. The movement path (physics/movement.py) fires
    charge_mech() when range < CHARGE_DIST_TRIGGER (mech.update.c:692-712),
    with a 60-tick timeout under btech_newcharge (mech.update.c:228-235).
    """
    result = PhysicalAttackResult(attack_type=PhysicalAttackType.CHARGE)
    error=_command_guard(mech)
    if error:
        result.notice(mech, _caller_notice(mech,error))
        return result

    # MechWarriors and battlesuits can't charge (mech.physical.c:884-886).
    if unit_class(mech) in (UnitType.MW, UnitType.BSUIT):
        result.notice(mech, _caller_notice(mech, "You cannot charge without a 'mech!"))
        return result

    # Only mechs and non-salvage ground vehicles (mech.physical.c:889-892).
    if unit_class(mech) != UnitType.MECH and (
            unit_class(mech) != UnitType.VEH_GROUND or
            (mech.specials & getattr(Specials, 'SALVAGE_TECH', 0))):
        result.notice(mech, _caller_notice(mech, "You cannot charge with this vehicle!"))
        return result

    # Leg-count gates (mech.physical.c:894-910).
    if unit_class(mech) == UnitType.MECH:
        dead_legs = count_destroyed_legs(mech)
        if not is_quad(mech) and dead_legs > 0:
            result.notice(mech, _caller_notice(mech, "With one leg? Are you kidding?"))
            return result
        if not is_quad(mech) and dead_legs > 1:
            result.notice(mech, _caller_notice(mech, "Without legs? Are you kidding?"))
            return result
        if dead_legs > 1:
            result.notice(mech, _caller_notice(mech, "It'd unbalance you too much in your condition.."))
            return result
        if dead_legs > 2:
            result.notice(mech, _caller_notice(mech, "Exactly _what_ are you going to kick with?"))
            return result

    # Movement-mode gates use the pending transition event and active bits
    # (mech.physical.c:907-910, btmacros.h:880).
    if _physical_event(mech, 'MOVEMODE'):
        result.notice(mech, _caller_notice(mech, 'You cannot charge while changing movement modes!'))
        return result
    if mech.status2 & (MechStatus2.SPRINTING | MechStatus2.EVADING):
        result.notice(mech, _caller_notice(mech, "You cannot charge while in a special movement mode!"))
        return result
    if mech.status2 & MechStatus2.DODGING:
        result.notice(mech, _caller_notice(mech, "You cannot charge while dodging!"))
        return result

    if invalid_arity:
        result.notice(mech, _caller_notice(mech, 'Invalid number of arguments!'))
        return result
    if cancel:
        mech.charge_target = -1
        mech.charge_timer = 0
        mech.charge_distance = 0.0
        result.success = True
        result.notice(mech, 'You are no longer charging.', MECHPILOT)
        return result

    from systems.targeting import resolve_unit, contact_target
    if not explicit:
        if mech.target == -1:
            result.notice(mech, 'You do not have a default target set!')
            return result
        target = resolve_unit(mech, mech.target)
        if target is None:
            result.notice(mech, 'Invalid default target!')
            mech.target = -1
            return result
    elif isinstance(target, str):
        target = contact_target(mech, target[:2])
    if target is None:
        result.notice(mech, 'Target is not in line of sight!' if explicit else 'You do not have a default target set!')
        return result
    from systems.los import in_line_of_sight_nb
    if explicit and not in_line_of_sight_nb(mech,target,target.x,target.y,_mech_range(mech,target)):
        result.notice(mech, 'Target is not in line of sight!')
        return result
    if not explicit and unit_class(target) == UnitType.MW:
        result.notice(mech, "You can't charge THAT sack of bones and squishy bits!")
        return result
    if mech.map is not None and mech.map.flags & MAPFLAG_NOFRIENDLYFIRE and mech.team == target.team:
        result.notice(mech, "You can't charge your own team!")
        mech.charge_target = -1
        return result
    if unit_class(target) == UnitType.MW:
        result.notice(mech, "You can't charge THAT sack of bones and squishy bits!")
        return result
    mech.charge_target = target._id
    result.success = True
    verb = 'Charge' if unit_class(mech) == UnitType.MECH else 'Ram'
    result.notice(mech, f'{verb} target set to {identity(mech,target)}.' if explicit else 'Charge target set to default target.')
    return result


# =============================================================================
# ChargeMech resolution (mech.physical.c:1908-2660)
# =============================================================================

def _charge_damage_to_target(mech: 'Mech', target: 'Mech',
                             plus_one: bool) -> int:
    """
    Charge damage to the chargee (mech.physical.c:2153-2168 mutual,
    2450-2462 one-sided): btech_newcharge distance formula vs classic
    velocity formula. The +1 exists only in the one-sided branch - verbatim.
    """
    rel_facing = math.radians(mech.facing - target.facing)
    if config(mech,'newcharge',BTECH_NEWCHARGE):
        base = ((float32(getattr(mech, 'charge_distance', 0.0)) * MP1) -
                target.speed * math.cos(rel_facing))
    else:
        base = mech.speed - target.speed * math.cos(rel_facing)
    damage = base * MP_PER_KPH * (real_tons(mech) + 5) / 10
    if plus_one:
        damage += 1
    return int(damage)


def _apply_charge_clusters(victim: 'Mech', attacker: Optional['Mech'],
                           group: HitGroup, damage: int, remainder=None, *, critical_state=None) -> int:
    """C five-point packets, including the mutual second-side remainder quirk."""
    from systems.hit_locations import find_hit_location
    if critical_state is None:
        critical_state = [False]
    spread = int(damage / 5)
    packets = [5] * max(0, spread)
    tail = damage - spread * 5 if remainder is None else remainder
    if tail:packets.append(tail)
    inflicted = attacker is not None and attacker is not victim
    for amount in packets:
        loc,critical_state[0]=find_hit_location(victim,group,critical=critical_state[0])
        apply_damage_with_transfer(victim,loc,amount,is_rear=group==HitGroup.BACK,
            attacker=attacker or victim,is_critical=critical_state[0],engine=victim._engine,
            physical=1 if inflicted else 2, los=1 if inflicted else 0,
            attack_pilot=attacker.pilot if inflicted and attacker.pilot is not None else -1)
    return sum(packets)


def _charge_recycle(unit: 'Mech') -> None:
    """
    Cycle the charge sections (mech.physical.c:2588-2601, 2650-2658):
    mechs recycle the six resect sections; vehicles recycle FSIDE+TURRET.
    """
    if unit_class(unit) == UnitType.MECH:
        for loc in RESECT:
            set_recycle_limb(unit, loc, PHYSICAL_RECYCLE_TIME)
    else:
        # mech.physical.c:2597-2600 (and 2438-2441)
        set_recycle_limb(unit, VehicleLocation.FSIDE, PHYSICAL_RECYCLE_TIME)
        set_recycle_limb(unit, VehicleLocation.TURRET, PHYSICAL_RECYCLE_TIME)


def _charge_bth_side(attacker: 'Mech', defender: 'Mech') -> int:
    """Mutual-branch BTH: 5 + own piloting - other's piloting + movement mods
    (mech.physical.c:2266-2282)."""
    bth = 5
    bth += find_pilot_piloting(attacker) - find_pilot_piloting(defender)
    amm = calculate_attacker_movement_modifier(attacker)
    bth += min(0, amm - 1) if _has_melee_specialist(attacker) else amm
    bth += calculate_target_movement_modifier(defender, 0.0, attacker)
    bth += 2 if defender.status2 & MechStatus2.DODGING else 0
    return bth


def _charge_debug(attacker, target, bth, roll, inflicted, received):
    from core.effects import send_debug
    send_debug(attacker, f'#{attacker._id} charges #{target._id} ({bth}/{roll}) Distance: {attacker.charge_distance:.2f} DI: {inflicted} DR: {received}')


def charge_mech(mech: 'Mech', target: 'Mech',
                roll: Optional[int] = None,
                target_roll: Optional[int] = None) -> ChargeResult:
    """
    ChargeMech (mech.physical.c:1908-2660): resolution core, fired from the
    movement path when range < CHARGE_DIST_TRIGGER (mech.update.c:692-712).
    """
    from systems.movement_commands import notify
    result = ChargeResult()
    critical_state = [False]
    def emit(message,recipient=mech,started=False,audience=MECHALL):
        result.add(message)
        mech_notify(recipient, MECHSTARTED if started else audience, message)

    # ------------------------------------------------------------------
    # Mutual charge branch (mech.physical.c:1934-2413).
    # ------------------------------------------------------------------
    if getattr(target, 'charge_target', -1) in (mech, mech._id):
        result.mutual = True
        mech_can = True
        target_can = True

        # Busy-weapon checks over resect for both units (mech.physical.c:1940-1964).
        for loc in RESECT:
            if sect_has_busy_weap(mech, loc):
                emit(f"You have weapons recycling on your "
                           f"{armor_string(mech,loc)}.")
                mech_can = False
                break
        for loc in RESECT:
            if sect_has_busy_weap(target, loc):
                emit(f"You have weapons recycling on your "
                           f"{armor_string(target,loc)}.",target)
                target_can = False
                break

        # Capability checks (mech.physical.c:1967-1971); Blinded is the
        # BLINDED status bit (mech.h:1083).
        if (not target.is_started or target.is_unconscious or
                target.has_status(MechStatus.BLINDED)):
            target_can = False
        if (not mech.is_started or mech.is_unconscious or
                mech.has_status(MechStatus.BLINDED)):
            mech_can = False

        # Speed gates (mech.physical.c:1974-1985).
        if mech.speed < MP1:
            emit("You aren't moving fast enough to charge.")
            mech_can = False
        if target.speed < MP1:
            emit("You aren't moving fast enough to charge.",target)
            target_can = False

        # Section recycle checks per class (mech.physical.c:1988-2040).
        for unit, flag_name in ((mech, 'mech'), (target, 'target')):
            ok = True
            if unit_class(unit) == UnitType.MECH:
                if (unit.sections[Location.LLEG].recycle or
                        unit.sections[Location.RLEG].recycle):
                    emit("Your legs are still recovering from your "
                               "last attack.",unit)
                    ok = False
                if (unit.sections[Location.RARM].recycle or
                        unit.sections[Location.LARM].recycle):
                    emit("Your arms are still recovering from your "
                               "last attack.",unit)
                    ok = False
            else:
                # Front side cycling (mech.physical.c:2005-2010, 2028-2035).
                if unit.sections[VehicleLocation.FSIDE].recycle:
                    emit("You are still recovering from your last "
                               "attack!",unit)
                    ok = False
            if not ok:
                if flag_name == 'mech':
                    mech_can = False
                else:
                    target_can = False

        # Jumping (mech.physical.c:2043-2060).
        if target.is_jumping:
            emit("Your target is jumping, you charge underneath it.")
            emit("You can't charge while jumping, try death from above.",target)
            mech_can = False
            target_can = False
        if mech.is_jumping:
            emit("Your target is jumping, you charge underneath it.",target)
            emit("You can't charge while jumping, try death from above.")
            mech_can = False
            target_can = False

        # Fallen (mech.physical.c:2063-2077).
        if target.is_fallen and unit_class(mech) != UnitType.VEH_GROUND:
            emit("Your target's too low for you to charge it!")
            mech_can = False
        if mech.is_fallen and unit_class(target) != UnitType.VEH_GROUND:
            emit("Your target's too low for you to charge it!",target)
            target_can = False

        # Class matrix (mech.physical.c:2080-2107).
        if (unit_class(target) == UnitType.MECH and
                unit_class(mech) != UnitType.MECH):
            emit("You can only charge mechs!",target)
            target_can = False
        if (unit_class(mech) == UnitType.MECH and
                unit_class(target) != UnitType.MECH):
            emit("You can only charge mechs!")
            mech_can = False
        if (unit_class(target) == UnitType.VEH_GROUND and
                unit_class(mech) not in (UnitType.MECH, UnitType.VEH_GROUND)):
            emit("You can only charge mechs and tanks!",target)
            target_can = False
        if (unit_class(mech) == UnitType.VEH_GROUND and
                unit_class(target) not in (UnitType.MECH, UnitType.VEH_GROUND)):
            emit("You can only charge mechs and tanks!")
            mech_can = False

        # Live vehicle stun state and turret-repair event (mech.physical.c:2110-2131).
        if getattr(mech, 'tank_crit_status', 0) & 0x10:
            emit("You are too stunned to ram!")
            mech_can = False
        if getattr(target, 'tank_crit_status', 0) & 0x10:
            emit("You are too stunned to ram!",target)
            target_can = False
        if _physical_event(mech, 'UNJAM_TURRET'):
            emit("You are too busy unjamming your turret!")
            mech_can = False
        if _physical_event(target, 'UNJAM_TURRET'):
            # C QUIRK ported as written (mech.physical.c:2141-2148 region):
            # UnjammingTurret(target) notifies MECH, not target.
            emit("You are too busy unjamming your turret!")
            target_can = False

        # Forward-arc checks (mech.physical.c:2134-2151).
        ts = mech.status & (MechStatus.TORSO_LEFT | MechStatus.TORSO_RIGHT)
        mech.status &= ~ts
        if not (in_weapon_arc(mech, target.fx, target.fy) & FORWARDARC):
            emit("Your charge target is not in your forward arc and "
                       "you are unable to charge it.")
            mech_can = False
        mech.status |= ts

        # C QUIRK ported as written (mech.physical.c:2143-2151): the second
        # arc check reads target's torso-twist bits but strips/restores them
        # on MECH's status word.
        ts = target.status & (MechStatus.TORSO_LEFT | MechStatus.TORSO_RIGHT)
        mech.status &= ~ts
        if not (in_weapon_arc(target, mech.fx, mech.fy) & FORWARDARC):
            emit("Your charge target is not in your forward arc and "
                       "you are unable to charge it.",target)
            target_can = False
        mech.status |= ts

        # Damage each side would inflict (mech.physical.c:2153-2194).
        # No +1 in the mutual branch - verbatim.
        target_damage = _charge_damage_to_target(mech, target, plus_one=False)
        if _has_melee_specialist(mech):
            target_damage += 1
        if target_damage <= 0:
            emit("Your target unit will not sustain any damage. "
                       "Charge aborted!", audience=MECHPILOT)
            mech_can = False

        mech_damage = (real_tons(target) + 5) // 10
        if _has_melee_specialist(target):
            mech_damage += 1
        if mech_damage <= 0:
            # Verbatim including the C's "dmage" typo (mech.physical.c:2190).
            emit("Your unit won't sustain any dmage. Charge aborted!",target,audience=MECHPILOT)
            target_can = False

        # BTHs (mech.physical.c:2266-2299).
        mech_bth = _charge_bth_side(mech, target)
        targ_bth = _charge_bth_side(target, mech)

        # BTH > 12 refusals (mech.physical.c:2302-2316).
        if mech_can and mech_bth > 12:
            emit(f"Charge: BTH {mech_bth}\tYou choose not to charge.")
            mech_can = False
        if target_can and targ_bth > 12:
            emit(f"Charge: BTH {targ_bth}\tYou choose not to charge.",target)
            target_can = False

        result.attacker_charging = mech_can
        result.target_charging = target_can
        result.attacker_bth = mech_bth
        result.target_bth = targ_bth

        # Neither can charge: clear target's pending fields and bail; the
        # movement hook clears mech's own after return (mech.physical.c:2319-2326).
        if not mech_can and not target_can:
            target.charge_target = -1
            target.charge_timer = 0
            target.charge_distance = 0.0
            return result

        mech_roll = roll if roll is not None else source_roll('charge_rolls', roll_2d6)
        targ_roll = target_roll if target_roll is not None else source_roll('charge_rolls', roll_2d6)
        result.attacker_roll = mech_roll
        result.target_roll = targ_roll

        if mech_can:
            emit(f"Charge: BTH {mech_bth}\tRoll: {mech_roll}")
        if target_can:
            emit(f"Charge: BTH {targ_bth}\tRoll: {targ_roll}",target)

        # First unit hits (mech.physical.c:2336-2412).
        if mech_can and mech_roll >= mech_bth:
            result.attacker_hit = True
            emit(f"CRASH!!!\n{identity(target,mech)} charges into you!",target)
            emit("SMASH!!! You crash into your target!")
            result.damage_to_target = target_damage
            _apply_charge_clusters(target, mech,
                                   determine_hit_group(mech, target),
                                   target_damage, critical_state=critical_state)

            # Attacker self-damage; C reuses target_damage ("REUSED!",
            # mech.physical.c:2367). The tl3 formula uses the ATTACKER's own
            # tonnage where the target's seems intended - verbatim.
            if config(mech,'newcharge',BTECH_NEWCHARGE) and config(mech,'tl3_charge',BTECH_TL3_CHARGE):
                self_damage = int(
                    ((float32(getattr(mech, 'charge_distance', 0.0)) * MP1) -
                     target.speed * math.cos(math.radians(
                         mech.facing - target.facing))) * MP_PER_KPH *
                    (real_tons(mech) + 5) / 20)
            else:
                self_damage = (real_tons(target) + 5) // 10
            result.attacker_self_damage = _apply_charge_clusters(mech, None,
                                   determine_hit_group(target, mech),
                                   self_damage, critical_state=critical_state)

            mech.speed = 0.0
            mech.desired_speed = 0.0
            _charge_debug(mech, target, mech_bth, mech_roll, target_damage, self_damage)

            if (unit_class(mech) == UnitType.MECH and
                    not make_piloting_roll(mech, modifier=2).success):
                emit("Your piloting skill fails and you fall over!!")
                mech_falls(mech, levels=1)
            # C QUIRK ported as written (mech.physical.c:2334-2340 region):
            # the receiving unit's PSR is gated on MechType(MECH), not
            # MechType(target).
            if (unit_class(mech) == UnitType.MECH and
                    not make_piloting_roll(target, modifier=2).success):
                emit("Your piloting skill fails and you fall over!!",target)
                mech_falls(target, levels=1)

        # Second unit hits (mech.physical.c:2415-2495).
        if target_can and targ_roll >= targ_bth:
            result.target_hit = True
            emit(f"CRASH!!!\n{identity(mech,target)} charges into you!")
            emit("SMASH!!! You crash into your target!",target)
            result.damage_to_attacker = mech_damage
            _apply_charge_clusters(mech, target,
                                   determine_hit_group(target, mech),
                                   mech_damage, critical_state=critical_state)

            # Chargee's self-damage; the C's tl3 variant here uses
            # MechChargeDistance(target) but MechRealTons(mech) - verbatim.
            if config(mech,'newcharge',BTECH_NEWCHARGE) and config(mech,'tl3_charge',BTECH_TL3_CHARGE):
                self_damage = int(
                    ((float32(getattr(target, 'charge_distance', 0.0)) * MP1) -
                     mech.speed * math.cos(math.radians(
                         target.facing - mech.facing))) * MP_PER_KPH *
                    (real_tons(mech) + 5) / 20)
            else:
                self_damage = (real_tons(mech) + 5) // 10
            result.target_self_damage = _apply_charge_clusters(target, None,
                                   determine_hit_group(mech, target),
                                   self_damage, remainder=mech_damage % 5, critical_state=critical_state)

            target.speed = 0.0
            target.desired_speed = 0.0
            _charge_debug(target, mech, targ_bth, targ_roll, mech_damage, self_damage)

            if (unit_class(mech) == UnitType.MECH and
                    not make_piloting_roll(mech, modifier=2).success):
                emit("Your piloting skill fails and you fall over!!")
                mech_falls(mech, levels=1)
            if (unit_class(target) == UnitType.MECH and
                    not make_piloting_roll(target, modifier=2).success):
                emit("Your piloting skill fails and you fall over!!",target)
                mech_falls(target, levels=1)

        # Cycle both units' sections regardless of hits
        # (mech.physical.c:2497-2513).
        _charge_recycle(mech)
        _charge_recycle(target)

        # Clear target's pending fields; mech's are cleared by the movement
        # hook after return (mech.physical.c:2519-2523).
        target.charge_target = -1
        target.charge_timer = 0
        target.charge_distance = 0.0
        return result

    # ------------------------------------------------------------------
    # One-sided charge branch (mech.physical.c:2416-2660).
    # ------------------------------------------------------------------
    result.attacker_charging = True

    # Busy-weapon check. C QUIRK ported as written (mech.physical.c:2417-2424):
    # this loop indexes sections 0..5 RAW (LARM, RARM, LTORSO, RTORSO,
    # CTORSO, LLEG) instead of iterating resect.
    for loc in (Location.LARM, Location.RARM, Location.LTORSO,
                Location.RTORSO, Location.CTORSO, Location.LLEG):
        if sect_has_busy_weap(mech, loc):
            emit(f"You have weapons recycling on your "
                       f"{armor_string(mech,loc)}.")
            result.attacker_charging = False
            return result

    # Speed gate (mech.physical.c:2427-2428).
    if mech.speed < MP1:
        emit("You aren't moving fast enough to charge.")
        result.attacker_charging = False
        return result

    # Section recycle gates (mech.physical.c:2431-2441).
    if unit_class(mech) == UnitType.MECH:
        if (mech.sections[Location.LLEG].recycle or
                mech.sections[Location.RLEG].recycle):
            emit("Your legs are still recovering from your last "
                       "attack.")
            result.attacker_charging = False
            return result
        if (mech.sections[Location.RARM].recycle or
                mech.sections[Location.LARM].recycle):
            emit("Your arms are still recovering from your last "
                       "attack.")
            result.attacker_charging = False
            return result
    else:
        # Front side cycling (mech.physical.c:2481-2483).
        if mech.sections[VehicleLocation.FSIDE].recycle:
            emit("You are still recovering from your last attack!")
            result.attacker_charging = False
            return result

    # Jumping (mech.physical.c:2444-2447).
    if target.is_jumping:
        emit("Your target is jumping, you charge underneath it.")
        result.attacker_charging = False
        return result
    if mech.is_jumping:
        emit("You can't charge while jumping, try death from above.")
        result.attacker_charging = False
        return result

    # Fallen target (mech.physical.c:2450-2452).
    if target.is_fallen and unit_class(mech) != UnitType.VEH_GROUND:
        emit("Your target's too low for you to charge it!")
        result.attacker_charging = False
        return result

    # Class matrix (mech.physical.c:2455-2462).
    if (unit_class(mech) == UnitType.MECH and
            unit_class(target) != UnitType.MECH):
        emit("You can only charge mechs!")
        result.attacker_charging = False
        return result
    if (unit_class(mech) == UnitType.VEH_GROUND and
            unit_class(target) not in (UnitType.MECH, UnitType.VEH_GROUND)):
        emit("You can only charge mechs and tanks!")
        result.attacker_charging = False
        return result

    # Forward arc, torso twist stripped (mech.physical.c:2465-2470).
    ts = mech.status & (MechStatus.TORSO_LEFT | MechStatus.TORSO_RIGHT)
    mech.status &= ~ts
    iwa = in_weapon_arc(mech, target.fx, target.fy)
    mech.status |= ts
    if not (iwa & FORWARDARC):
        emit("Your charge target is not in your forward arc and you "
                   "are unable to charge it.")
        result.attacker_charging = False
        return result

    # Damage inflicted (mech.physical.c:2473-2487): one-sided branch has the
    # +1 - verbatim.
    target_damage = _charge_damage_to_target(mech, target, plus_one=True)
    if _has_melee_specialist(mech):
        target_damage += 1
    if target_damage <= 0:
        emit("Your target pulls away from you and you are unable to "
                   "charge it.", audience=MECHPILOT)
        result.attacker_charging = False
        return result

    # BTH (mech.physical.c:2490-2502): target side uses FindSPilotPiloting
    # (quad -2 variant, systems.piloting).
    bth = 5
    bth += find_pilot_piloting(mech) - find_spilot_piloting(target)
    amm = calculate_attacker_movement_modifier(mech)
    bth += min(0, amm - 1) if _has_melee_specialist(mech) else amm
    bth += calculate_target_movement_modifier(target, 0.0, mech)
    bth += 2 if target.status2 & MechStatus2.DODGING else 0
    result.attacker_bth = bth

    # BTH > 12 refusal returns BEFORE any recycle (mech.physical.c:2505-2507).
    if bth > 12:
        emit(f"Charge: BTH {bth}\tYou choose not to charge.")
        result.attacker_charging = False
        return result

    the_roll = roll if roll is not None else source_roll('charge_rolls', roll_2d6)
    result.attacker_roll = the_roll
    emit(f"Charge: BTH {bth}\tRoll: {the_roll}")

    if the_roll >= bth:
        result.attacker_hit = True
        verb = "charge" if unit_class(mech) == UnitType.MECH else "ram"
        _physical_broadcast(mech,target,verb+'s {}!')
        emit(f"CRASH!!!\n{identity(target,mech)} {verb}s into you!",target,started=True)
        emit("SMASH!!! You crash into your target!")

        result.damage_to_target = target_damage
        _apply_charge_clusters(target, mech,
                               determine_hit_group(mech, target),
                               target_damage, critical_state=critical_state)

        # Attacker self-damage (mech.physical.c:2549-2561): classic
        # (target_tons+5)/10, tl3 distance variant gated on both directives.
        if config(mech,'newcharge',BTECH_NEWCHARGE) and config(mech,'tl3_charge',BTECH_TL3_CHARGE):
            mech_damage = int(
                ((float32(getattr(mech, 'charge_distance', 0.0)) * MP1) -
                 target.speed * math.cos(math.radians(
                     mech.facing - target.facing))) * MP_PER_KPH *
                (real_tons(target) + 5) / 20)
        else:
            mech_damage = (real_tons(target) + 5) // 10
        result.damage_to_attacker = mech_damage
        result.attacker_self_damage = _apply_charge_clusters(mech, None,
                               determine_hit_group(target, mech), mech_damage, critical_state=critical_state)

        # Both-side PSR+2 fall checks (mech.physical.c:2578-2590).
        if (unit_class(mech) == UnitType.MECH and
                not make_piloting_roll(mech, modifier=2).success):
            emit("Your piloting skill fails and you fall over!!")
            mech_falls(mech, levels=1)
        if (unit_class(target) == UnitType.MECH and
                not make_piloting_roll(target, modifier=2).success):
            emit("Your piloting skill fails and you fall over!!",target,started=True)
            mech_falls(target, levels=1)

        # Attacker speed zeroed (mech.physical.c:2593-2594).
        mech.speed = 0.0
        mech.desired_speed = 0.0
        _charge_debug(mech, target, bth, the_roll, target_damage, mech_damage)

    # Recycle the charge sections WHETHER OR NOT the roll hit - verbatim
    # (mech.physical.c:2650-2658).
    _charge_recycle(mech)
    return result


# =============================================================================
# Grabclub / Dropclub (mech.physical.c:2665-2786)
# =============================================================================

def check_grab_club_location(mech: 'Mech', section: Location,
                             emit: bool = False) -> tuple[bool, str]:
    """checkGrabClubLocation (mech.physical.c:2665-2695)."""
    locname = armor_string(mech,section)
    msg = ""
    if sect_is_destroyed(mech, section):
        msg = f"Your {locname} is destroyed."
    elif not okay_crit_sect(mech, section, 3, Special.HAND_OR_FOOT_ACTUATOR):
        msg = f"Your {locname}'s hand actuator is destroyed or missing."
    elif not okay_crit_sect(mech, section, 0, Special.SHOULDER_OR_HIP):
        msg = f"Your {locname}'s shoulder actuator is destroyed or missing."
    elif sect_has_busy_weap(mech, section):
        # Verbatim, including the C's "it's" (mech.physical.c:2686).
        msg = f"Your {locname} is still recovering from it's last attack."
    if msg:
        return (False, _unit_notice(mech,msg) if emit else "")
    return (True, "")


def drop_club(mech: 'Mech') -> list[str]:
    """
    DropClub (macro home: btmacros.h:858): clears CARRYING_CLUB with the
    shatter messages (text as in mech.physical.c:1430-1445).
    """
    if not carrying_club(mech):return []
    from systems.sensors import los_broadcast
    from systems.combat_commands import NotifiedError
    for arm in (Location.LARM,Location.RARM):
        mech.sections[arm].specials &= ~CARRYING_CLUB
    text = _unit_notice(mech, 'Your club falls to the ground and shatters.')
    observer = "'s club falls to the ground and shatters."
    los_broadcast(mech, observer)
    return [text, NotifiedError(observer)]


def _club_command(command):
    @wraps(command)
    def run(unit, *args, **kwargs):
        accepted, messages = command(unit, *args, **kwargs)
        return accepted, [_unit_notice(unit, text) if not accepted else text for text in messages]
    return run


@_club_command

def mech_grabclub(mech: 'Mech', arm: Optional[str] = None,
                  drop: bool = False) -> tuple[bool, list[str]]:
    """
    mech_grabclub (mech.physical.c:2700-2786): grab a tree as an improvised
    club (sets CARRYING_CLUB + recycles the arm), or 'grabclub -' to drop.
    """
    error=_command_guard(mech)
    if error:return False,[_caller_notice(mech,error)]
    # 'grabclub -' drops the club (mech.physical.c:2713-2722).
    if drop or (arm and arm[0] == '-'):
        if carrying_club(mech):
            return (True, drop_club(mech))
        return (False, ["You aren't currently carrying a club."])

    if is_quad(mech):
        return (False, ["Quads can't carry a club."])
    if mech.is_fallen:
        return (False, ["You can't grab a club while lying flat on your "
                        "face."])
    if mech.is_jumping:
        return (False, ["You can't grab a club while jumping!"])
    if mech.cocoon:return False,['Your rapid descent prevents that.']
    if _physical_event(mech,'UNJAM_AMMO'):return False,['You are too busy unjamming a weapon!']
    if _physical_event(mech,'REMOVE_PODS'):return False,['You are too busy removing iNARC pods!']

    # Physical-weapon exclusions (mech.physical.c:2732-2737); "an mace" is
    # the C's typo - verbatim.
    if have_axe(mech, Location.LARM) or have_axe(mech, Location.RARM):
        return (False, ["You can not grab a club if you carry an axe."])
    if have_sword(mech, Location.LARM) or have_sword(mech, Location.RARM):
        return (False, ["You can not grab a club if you carry a sword."])
    if have_mace(mech, Location.LARM) or have_mace(mech, Location.RARM):
        return (False, ["You can not grab a club if you carry an mace."])

    if arm is None:
        if check_grab_club_location(mech, Location.LARM)[0]:
            location = Location.LARM
        elif check_grab_club_location(mech, Location.RARM)[0]:
            location = Location.RARM
        else:
            return (False, ["You don't have a free arm with a working hand "
                            "actuator!"])
    else:
        a = arm[0].upper()
        if a == 'R':
            location = Location.RARM
        elif a == 'L':
            location = Location.LARM
        else:
            return (False, ["Invalid option for 'grabclub'"])
        ok, msg = check_grab_club_location(mech, location, emit=True)
        if not ok:
            return (False, [msg])

    if carrying_club(mech):
        return (False, ["You're already carrying a club."])
    if mech_rterrain(mech) not in (HEAVY_FOREST, LIGHT_FOREST):
        return (False, ["There don't appear to be any trees within grabbing "
                        "distance."])

    locname = armor_string(mech,location)
    from systems.sensors import los_broadcast
    from systems.combat_commands import NotifiedError
    observer = 'reaches down and yanks a tree out of the ground!'
    los_broadcast(mech, observer)
    message = _unit_notice(mech, f'You reach down and yank a tree out of the ground with your {locname}.')
    mech.sections[location].specials |= CARRYING_CLUB
    set_recycle_limb(mech, location, PHYSICAL_RECYCLE_TIME)
    return True, [NotifiedError(observer), message]


# =============================================================================
# Death From Above (legacy port - C alignment out of scope for E.7)
# =============================================================================

DFA_BASE_BTH = 5


def calculate_dfa_damage(mech: 'Mech') -> tuple[int, int]:
    from systems.mines import real_tons
    return (int(3*real_tons(mech)/10)+int(mech.tonnage%10!=0)+int(_has_melee_specialist(mech)),
            int(mech.tonnage/5))


def _dfa_bth_modifiers(attacker,target,base_bth):
    movement=calculate_attacker_movement_modifier(attacker)
    bth=base_bth+(min(0,movement)-1 if _has_melee_specialist(attacker) else movement)
    bth+=calculate_target_movement_modifier(target,0,attacker)
    bth+=int(target.unit_type==UnitType.BSUIT)
    bth+=2 if target.status2&MechStatus2.DODGING else 0
    return bth


def can_dfa(mech,target):
    from systems.movement_commands import mode_locked
    for loc in RESECT:
        if sect_has_busy_weap(mech,loc):return False,f'You have weapons recycling on your {armor_string(mech,loc)}.'
    if mech.map is not target.map:return False,'Your target is no longer valid.'
    if mech.status2&MechStatus2.DODGING or mode_locked(mech):return False,'You cannot use physicals while using a special movement mode.'
    if any(mech.sections[loc].recycle for loc in (Location.LLEG,Location.RLEG)):
        return False,'Your legs are still recovering from your last attack.'
    if any(mech.sections[loc].recycle for loc in (Location.LARM,Location.RARM)):
        return False,'Your arms are still recovering from your last attack.'
    if target.is_jumping or (target.unit_type in (UnitType.VTOL,UnitType.AERO,UnitType.DS) and not target.status&MechStatus.LANDED):
        return False,'Your target is airborne, you cannot land on it.'
    if mech.map and mech.team==target.team and mech.map.flags&MAPFLAG_NOFRIENDLYFIRE:
        return False,"Friendly DFA? I don't think so...."
    return True,''


def _dfa_make_prone(mech):
    from physics.jump import make_mech_fall
    make_mech_fall(mech)


def dfa_attack(mech,target,roll_override=None, *, notify_attacker=True):
    from systems.combat_ranges import config
    from systems.hit_locations import find_hit_location
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    result=PhysicalAttackResult(attack_type=PhysicalAttackType.DFA)
    def emit(message):
        result.notice(mech, message)
    allowed,message=can_dfa(mech,target)
    if not allowed:
        emit(message)
        return result
    base=find_pilot_piloting(mech) if config(mech,'phys_use_pskill',BTECH_PHYS_USE_PSKILL) else 5
    result.bth=_dfa_bth_modifiers(mech,target,base)
    if result.bth>12:
        emit(f'DFA: BTH {result.bth}\tYou choose not to attack and land from your jump.')
        return result
    result.success=True
    result.roll=roll_override if roll_override is not None else source_roll('dfa_rolls', roll_2d6)
    emit(f'DFA: BTH {result.bth}\tRoll: {result.roll}')
    mech.status&=~(MechStatus.JUMPING|MechStatus.DFA_ATTACK)
    result.hit=result.roll>=result.bth
    target_damage,self_damage=calculate_dfa_damage(mech)

    def clusters(victim,attacker,damage,table,group,rear=False):
        total=0
        critical=False
        while damage>0:
            amount=min(5,damage)
            current = ('normal' if victim.is_fallen or victim.unit_type!=UnitType.MECH else 'punch') if table=='target' else table
            if current=='punch':loc=get_punch_location(victim,group)
            elif current=='kick':loc=get_kick_location(victim,group)
            else:loc,critical=find_hit_location(victim,group,critical=critical)
            if victim is target and result.location_hit is None:result.location_hit=loc
            total+=apply_damage_with_transfer(victim,loc,amount,is_rear=rear,attacker=attacker,
                is_critical=critical,engine=mech._engine,physical=1 if victim is target else 2,
                los=1 if victim is target else 0,
                attack_pilot=attacker.pilot if victim is target and attacker.pilot is not None else -1)
            damage-=amount
        return total

    if result.hit:
        mech_notify(target,MECHSTARTED,f'DEATH FROM ABOVE!!!\n{identity(target,mech)} lands on you from above!')
        emit('You land on your target legs first!')
        _physical_broadcast(mech,target,'lands on {}!')
        group=determine_hit_group(mech,target)
        result.damage_dealt=clusters(target,mech,target_damage,
            'target',group,group==HitGroup.BACK)
        result.attacker_damage=clusters(mech,mech,self_damage,'kick',HitGroup.FRONT)
        if not mech.is_fallen:
            if not make_piloting_roll(mech,modifier=4).success:
                emit('Your piloting skill fails and you fall over!!')
                los_broadcast(mech,'stumbles and falls down!')
                mech_falls(mech,1,notify_fall=False)
                result.attacker_fell=True
            if target.unit_type==UnitType.MECH and not make_piloting_roll(target,modifier=2).success:
                mech_notify(target,MECHSTARTED,'Your piloting skill fails and you fall over!!')
                los_broadcast(target,'stumbles and falls down!')
                mech_falls(target,1,notify_fall=False)
                result.target_fell=True
    else:
        if not mech.is_fallen:
            emit('You miss your DFA attack and fall on your back!!')
            los_broadcast(mech,'misses DFA and falls down!')
        result.attacker_damage=clusters(mech,mech,self_damage,'normal',HitGroup.BACK,True)
        if not make_piloting_roll(mech,modifier=2).success:
            from systems.piloting import head_hit_mw_damage
            emit('You take personal injury from the fall!')
            head_hit_mw_damage(mech,mech,1)
        mech.speed=mech.desired_speed=0
        _dfa_make_prone(mech)
        mech.z=ground_elevation(mech)
        mech.fz=mech.z*64.5
        if mech.z<0:
            from physics.flooding import flood_unit
            flood_unit(mech)
        result.attacker_fell=True
    for loc in RESECT:set_recycle_limb(mech,loc,PHYSICAL_RECYCLE_TIME)
    return result


def _physical_event(unit, name):
    from core.events import EventType
    return bool(unit._engine and unit._engine.events.has_event_type_data(getattr(EventType,name),unit))


def physical_command(unit, command, argument='', **actor):
    """Keep caller-scoped refusals separate from source unit notifications."""
    if unit is None:
        return dict(accepted=False, text='')
    token = _command_actor.set((unit, actor.get('caller', unit.pilot), actor.get('wizard', False)))
    try:
        return _physical_command(unit, command, argument, **actor)
    finally:
        _command_actor.reset(token)


def _physical_command(unit, command, argument='', **actor):
    from systems.combat_commands import command_guard, parse_attributes
    from dataclasses import asdict
    error=command_guard(unit,**actor)
    if error:
        _caller_notice(unit,error)
        return dict(accepted=False,text=str(error))
    args=parse_attributes(argument, 2 if command=='charge' else 1 if command=='grabclub' else 5)
    if command=='charge':
        result=mech_charge(unit,args[0][:2] if args else None,
                           cancel=len(args)==1 and args[0].startswith('-'),
                           explicit=bool(args), invalid_arity=len(args)>1)
    elif command=='grabclub':
        accepted,messages=mech_grabclub(unit,args[0] if args else None)
        return dict(accepted=accepted,text='\n'.join(messages))
    elif command in ('punch','axe','sword','mace','claw','saw','club','kick','trip'):
        arm=None
        if args and len(args[0])==1 and args[0].upper() in ('L','R','B') and command!='club':
            arm=args.pop(0)
        target=args[0][:2] if args else None
        handler=globals()['mech_'+command]
        result=handler(unit,target) if command=='club' else handler(unit,target,arm=arm)
        results=result if isinstance(result,list) else [result]
        return dict(accepted=any(r.success for r in results),
                    text='\n'.join(m for r in results for m in r.messages),
                    results=[asdict(r) for r in results])
    else:
        raise ValueError(f'Unknown physical command: {command}')
    return dict(accepted=result.success,text='\n'.join(result.messages),result=asdict(result))


def phys_form(attack_type,add_s=False):
    if attack_type not in PHYS_FORM:return '??bugs??'
    verb=PHYS_FORM.get(attack_type,'??bugs??')
    return ('maces' if attack_type==PhysicalAttackType.MACE else verb+'s') if add_s else verb


def _physical_broadcast(mech,target,text):
    from systems.notifications import pair_los_broadcast
    return pair_los_broadcast(mech,target,text.replace('%','%%').replace('{}','%s'))


def phys_succeed(mech,target,attack_type):
    _physical_broadcast(mech,target,phys_form(attack_type,True)+' {}!')


def phys_fail(mech,target,attack_type):
    _physical_broadcast(mech,target,'attempts to '+phys_form(attack_type)+' {}!')


def mech_full_no_recycle(mech, mask):
    """MechFullNoRecycle: first busy section, weapon before physical."""
    for loc, section in enumerate(mech.sections):
        if mask & 1 and sect_has_busy_weap(mech,loc): return 1
        if mask & 2 and section.recycle > 0: return 2
    return 0
