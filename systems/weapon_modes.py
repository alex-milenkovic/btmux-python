# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.advanced.c
#   btech/mech.utils.c

"""
Weapon fire-mode / ammo-mode toggle commands.

Standalone port of the mode-toggle command family; the fire-path
consumption of these modes (gof/nogof ammo filters in FindAndCheckAmmo,
multi-shot Ultra/RAC/gattling fire) is a later wave.

C references:
- mech.advanced.c:207-218   mech_ams (AMS on/off toggle)
- mech.advanced.c:252-357   mech_toggle_mode_sub_func / mech_toggle_mode_sub
- mech.advanced.c:383-785   the command family (mech_lbx, mech_artemis, ...)
- mech.utils.c:1417-1447    FindArtemisForWeapon
- mech.utils.c:2569-2699    FindAndCheckAmmo (gof/nogof derivation)

The toggle flips the crit's mode word ONLY: there is NO bin-existence
check and NO desired_ammo_loc change (verified against the C).

Integration contract for the wiring wave: ammo_mode_filters(slot, weapon)
returns the (nogof, gof) pair FindAndCheckAmmo passes into
FindAmmoForWeapon_sub (mech.utils.c:2647-2676); findAmmoInSection's
mode-filter arm (mech.utils.c:1301-1321) consumes them - do NOT implement
that in this module.

Ultra/RAC/gattling multi-shot FIRE mechanics are out of scope here (mode
toggles only); swarm/mine/smoke/thunder RESOLUTION is out of scope (mode
bits only).
"""

from systems.combat_commands import CommandMessages, parse_attributes
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from entities.crittypes import Special, i2special, weapon2i
from entities.mech import (
    AmmoMode,
    FireMode,
    Location,
    MechStatus,
    NUM_CRITICALS,
    Specials,
    UnitType,
    VehicleLocation,
)
from entities.weapon import WeaponFlags, WeaponType, get_weapon_by_index
from systems.combat import part_is_nonfunctional
from systems.enhanced_crits import (
    FAIL_AMMOJAMMED,
    is_weap_ammo_feed_locked,
    part_temp_nuke,
)

if TYPE_CHECKING:
    from entities.mech import Mech


@dataclass
class ToggleResult:
    """Outcome of a mode-toggle command: what changed, what was said."""
    success: bool = False            # a mode word actually changed
    accepted: bool = True             # selection acceptance, independent of mutation
    messages: list = field(default_factory=list)


# =============================================================================
# Weapon-number resolution
# =============================================================================

# FindWeaponNumberOnMech_Advanced result codes (mech.utils.c:1162-1217)
WEAPNUM_ILLEGAL = -1
WEAPNUM_DESTROYED = -2
WEAPNUM_RELOADING = -3
WEAPNUM_RECHARGING = -4
WEAPNUM_PHYSICAL = -5


def find_weapon_number_on_mech(mech: 'Mech', weapon_number: int, sight=False) -> tuple:
    """FindWeaponNumberOnMech_Advanced, in validated critical-slot order."""
    from systems.weapon_inventory import numbered_weapon
    run = numbered_weapon(mech, weapon_number)
    if run is None:
        return (WEAPNUM_ILLEGAL, -1, -1)
    loc, pos = run.section, run.critical
    if part_is_nonfunctional(mech, loc, pos):
        code = WEAPNUM_DESTROYED
    elif run.data > 0 and not sight:
        code = (WEAPNUM_RECHARGING if get_weapon_by_index(run.weapon_idx).weapon_type == WeaponType.TBEAM
                else WEAPNUM_RELOADING)
    elif (mech.sections[loc].recycle and not sight and
          mech.unit_type in (UnitType.MECH, UnitType.VEH_GROUND, UnitType.VTOL)):
        code = WEAPNUM_PHYSICAL
    else:
        code = run.weapon_idx
    return (code, loc, pos)


# =============================================================================
# FindArtemisForWeapon
# =============================================================================

def find_artemis_for_weapon(mech: 'Mech', section: int,
                            critical: int) -> bool:
    """
    Is there a functional Artemis IV crit linked to this launcher?

    Port of FindArtemisForWeapon (mech.utils.c:1417-1447): a functional
    Special.ARTEMIS_IV crit in the weapon's own section whose data equals
    first_crit + 1.  Fallbacks verbatim: a mech's CTORSO launcher may be
    served from the HEAD (first 6 slots only, :1431-1437); a ground
    vehicle's TURRET launcher from the BSIDE (:1438-1444).

    Template placement is a later wave - callers/tests build the crit
    layout directly.
    """
    desired = i2special(Special.ARTEMIS_IV)

    def _scan(loc: int, limit: int) -> bool:
        for critloop in range(limit):
            crit = mech.sections[loc].criticals[critloop]
            if (crit.type == desired and
                    not part_is_nonfunctional(mech, loc, critloop) and
                    crit.data == critical + 1):
                return True
        return False

    if _scan(section, NUM_CRITICALS):
        return True

    if mech.unit_type == UnitType.MECH and section == Location.CTORSO:
        # mech torso missile: search the head (mech.utils.c:1431-1437)
        return _scan(Location.HEAD, 6)
    elif (mech.unit_type == UnitType.VEH_GROUND and
            section == VehicleLocation.TURRET):
        # same thing for turret & aft (mech.utils.c:1438-1444)
        return _scan(VehicleLocation.BSIDE, NUM_CRITICALS)

    return False


# =============================================================================
# The toggle core
# =============================================================================

def _fmt(msg: str, index: int) -> str:
    """tprintf(msg, index) - every command message formats the number."""
    try:
        return msg % index
    except TypeError:
        return msg


def toggle_mode(
    mech: 'Mech',
    weapon_number: int,
    nspecisspec: int,
    nspec: int,
    mode: int,
    firemode_toggle: bool,
    onmsg: str,
    offmsg: str,
    cant: str,
    *, caller=None,
) -> ToggleResult:
    """
    Toggle a weapon's fire or ammo mode.

    Port of mech_toggle_mode_sub_func (mech.advanced.c:252-357).  Gates
    run in the C's order, messages verbatim:
      1. illegal / destroyed / reloading / recharging weapon number
      2. ammo-feed jam (PartTempNuke == FAIL_AMMOJAMMED,
         mech.advanced.c:268-269)
      3. one-shot refusal
      4. ammo-feed lock (isWeapAmmoFeedLocked, mech.advanced.c:272-273)
      5. nspecisspec == 6: Artemis linkage gate (mech.advanced.c:276-278)
      6. rocket-launcher refusal
      7. capability dispatch on nspecisspec (mech.advanced.c:287-300)

    Capability dispatch, verbatim (mech.advanced.c:287-300):
      6 - missile weapon (missile + artemis)
      5 - TAMMO weapon without the nspec special (ammo-special)
      4 - missile weapon AND the literal `.type & (IDF|DAR)` test - the C
          tests the TYPE field against special-flag bits, which is always
          0, so this arm matches EVERY missile weapon, not just
          short-range ones.  Verbatim quirk, preserved.
      2 - LRM-class: special has IDF and not DAR
      1 - weapon-special-flag match
      <= 0 - type match (e.g. TMISSILE/TARTILLERY), non-NARC weapons only

    The toggle itself: an already-set mode is cleared with the offmsg
    (except RAC fire modes / iNARC ammo modes, which KEEP the current
    setting - the Fitz quirk, mech.advanced.c:325-341); otherwise the
    whole word group (FIRE_MODES or AMMO_MODES) is cleared and the mode
    set (mech.advanced.c:344-351).  RAC/iNARC group-select with mode 0
    clears the group (mech.advanced.c:306-322).  Artillery weapons
    already set to a special round refuse a second one
    (mech.advanced.c:301-305).  On a capability miss the cant message is
    suppressed for RAC (mech.advanced.c:355-356).

    NO bin-existence check, NO desired_ammo_loc change - the toggle flips
    the mode word only.
    """
    result = ToggleResult(messages=CommandMessages(unit=mech,caller=caller))

    code, section, critical = find_weapon_number_on_mech(
        mech, weapon_number)
    if code == WEAPNUM_ILLEGAL:
        result.messages.append(
            "The weapons system chirps: 'Illegal Weapon Number!'")
        return result
    if code == WEAPNUM_DESTROYED:
        result.messages.append(
            "The weapons system chirps: 'That Weapon has been destroyed!'")
        return result
    if code == WEAPNUM_RELOADING:
        result.messages.append(
            "The weapon system chirps: 'That weapon is still reloading!'")
        return result
    if code == WEAPNUM_RECHARGING:
        result.messages.append(
            "The weapon system chirps: 'That weapon is still recharging!'")
        return result

    # The C callback does not reject physical recycle (-5). It recovers
    # the catalog index from the returned slot before checking capability.

    slot = mech.sections[section].criticals[critical]

    # mech.advanced.c:268-269
    if part_temp_nuke(slot) == FAIL_AMMOJAMMED:
        result.messages.append(
            "The ammo feed mechanism for that weapon is jammed! "
            "Unable to change modes!")
        return result

    if slot.firemode & FireMode.OS_MODE:
        result.messages.append("One-shot weapons' mode cannot be altered!")
        return result

    # mech.advanced.c:272-273
    if is_weap_ammo_feed_locked(mech, section, critical):
        result.messages.append(
            "That weapon's ammo feed mechanism is damaged!")
        return result

    if nspecisspec == 6:
        # mech.advanced.c:276-278
        if not find_artemis_for_weapon(mech, section, critical):
            result.messages.append(
                "You do not have an Artemis system for that weapon.")
            return result

    # weaptype = Weapon2I(GetPartType(...)) (mech.advanced.c:281)
    weapon = get_weapon_by_index(weapon2i(slot.type))
    if weapon is None:
        result.messages.append(
            "The weapons system chirps: 'Illegal Weapon Number!'")
        return result

    if weapon.special & WeaponFlags.ROCKET:
        result.messages.append("Rocket launchers' mode cannot be altered!")
        return result

    # Capability dispatch (mech.advanced.c:287-300)
    capable = (
        (nspecisspec == 6 and
         weapon.weapon_type == WeaponType.TMISSILE) or
        (nspecisspec == 5 and weapon.weapon_type == WeaponType.TAMMO and
         not (weapon.special & nspec)) or
        # Verbatim quirk: the C tests `MechWeapons[weaptype].type &
        # (IDF | DAR)` - the TYPE field against SPECIAL-flag bits
        # (mech.advanced.c:291-292).  TMISSILE == 1, IDF|DAR == 0x30, so
        # the & is always 0 and the arm matches every missile weapon.
        (nspecisspec == 4 and
         weapon.weapon_type == WeaponType.TMISSILE and
         not (int(weapon.weapon_type) &
              int(WeaponFlags.IDF | WeaponFlags.DAR))) or
        (nspecisspec == 2 and (weapon.special & WeaponFlags.IDF) and
         not (weapon.special & WeaponFlags.DAR)) or
        (nspecisspec == 1 and nspec and (weapon.special & nspec)) or
        (nspecisspec <= 0 and nspec and
         weapon.weapon_type == nspec and
         not (weapon.special & WeaponFlags.NARC))
    )

    if capable:
        # Artillery already-special guard (mech.advanced.c:301-305)
        if nspecisspec == 0 and (nspec & WeaponType.TARTILLERY):
            if (slot.ammomode & AmmoMode.ARTILLERY_MODES) and \
                    not (slot.ammomode & mode):
                result.messages.append(
                    "That weapon has already been set to fire special "
                    "rounds!")
                return result

        # Group RAC select: clear all RAC fire modes
        # (mech.advanced.c:306-313)
        if nspec == WeaponFlags.RAC and not mode:
            if not (slot.firemode & FireMode.RAC_MODES):
                result.messages.unit(_fmt(offmsg, weapon_number))
            else:
                slot.firemode &= ~int(FireMode.FIRE_MODES)
                result.messages.unit(_fmt(onmsg, weapon_number))
                result.success = True
            return result

        # Group iNARC select: clear all ammo modes
        # (mech.advanced.c:314-322)
        if nspec == WeaponFlags.INARC and not mode:
            if not (slot.ammomode & AmmoMode.INARC_MODES):
                result.messages.unit(_fmt(offmsg, weapon_number))
            else:
                slot.ammomode &= ~int(AmmoMode.AMMO_MODES)
                result.messages.unit(_fmt(onmsg, weapon_number))
                result.success = True
            return result

        # Already set: clear it + offmsg, except the RAC/iNARC
        # keep-current quirk (mech.advanced.c:325-341)
        if firemode_toggle:
            if slot.firemode & mode:
                if nspec != WeaponFlags.RAC:
                    slot.firemode &= ~int(mode)
                    result.success = True
                result.messages.unit(_fmt(offmsg, weapon_number))
                return result
        else:
            if slot.ammomode & mode:
                if nspec != WeaponFlags.INARC:
                    slot.ammomode &= ~int(mode)
                    result.success = True
                result.messages.unit(_fmt(offmsg, weapon_number))
                return result

        # Clear the whole word group, then set (mech.advanced.c:344-351)
        if firemode_toggle:
            slot.firemode &= ~int(FireMode.FIRE_MODES)
            slot.firemode |= mode
        else:
            slot.ammomode &= ~int(AmmoMode.AMMO_MODES)
            slot.ammomode |= mode

        result.messages.unit(_fmt(onmsg, weapon_number))
        result.success = True
        return result

    # Capability miss: cant is suppressed for RAC (mech.advanced.c:355-356)
    if nspec != WeaponFlags.RAC:
        result.messages.append(cant)
    return result


# =============================================================================
# mech_ams
# =============================================================================

def mech_ams(mech: 'Mech', *, caller=None) -> ToggleResult:
    """
    Toggle the Anti-Missile System.

    Port of mech_ams (mech.advanced.c:207-218), a SILLY_TOGGLE_MACRO over
    the AMS tech specials and MechStatus.AMS_ENABLED.
    """
    result = ToggleResult(accepted=False,messages=CommandMessages(unit=mech,caller=caller))
    if not (mech.specials & (Specials.IS_ANTI_MISSILE_TECH |
                             Specials.CL_ANTI_MISSILE_TECH)):
        result.messages.append("This mech is not equipped with AMS")
        return result
    if mech.has_status(MechStatus.AMS_ENABLED):
        result.messages.unit("Anti-Missile System turned OFF")
        mech.status &= ~int(MechStatus.AMS_ENABLED)
    else:
        result.messages.unit("Anti-Missile System turned ON")
        mech.set_status(MechStatus.AMS_ENABLED)
    result.success = result.accepted = True
    return result


# =============================================================================
# Command family (mech.advanced.c:383-785)
# =============================================================================

# name -> (nspecisspec, nspec, mode, firemode_toggle, onmsg, offmsg, cant)
_COMMANDS = {
    # mech.advanced.c:383-388
    'flamerheat': (
        1, WeaponFlags.CHEAT, FireMode.HEAT_MODE, True,
        "Weapon %d has been set to HEAT mode",
        "Weapon %d has been set to normal mode",
        "That weapon cannot be set HEAT!"),
    # mech.advanced.c:389-398
    'ultra': (
        1, WeaponFlags.ULTRA, FireMode.ULTRA_MODE, True,
        "Weapon %d has been set to ultra fire mode",
        "Weapon %d has been set to normal fire mode",
        "That weapon cannot be set ULTRA!"),
    # mech.advanced.c:454-464
    'explosive': (
        1, WeaponFlags.NARC, AmmoMode.NARC_MODE, False,
        "Weapon %d has been set to fire explosive rounds",
        "Weapon %d has been set to fire NARC beacons",
        "That weapon cannot be set to fire explosive rounds!"),
    # mech.advanced.c:466-476
    'lbx': (
        1, WeaponFlags.LBX, AmmoMode.LBX_MODE, False,
        "Weapon %d has been set to LBX fire mode",
        "Weapon %d has been set to normal fire mode",
        "That weapon cannot be set LBX!"),
    # mech.advanced.c:478-488
    'armorpiercing': (
        1, WeaponFlags.RFAC, AmmoMode.AC_AP_MODE, False,
        "Weapon %d has been set to fire AP rounds",
        "Weapon %d has been set to fire normal rounds",
        "That weapon cannot fire AP rounds!"),
    # mech.advanced.c:490-498
    'caseless': (
        1, WeaponFlags.RFAC, AmmoMode.AC_CASELESS_MODE, False,
        "Weapon %d has been set to fire CASELESS rounds",
        "Weapon %d has been set to fire normal rounds",
        "That weapon cannot fire CASELESS rounds!"),
    # mech.advanced.c:500-509
    'flechette': (
        1, WeaponFlags.RFAC, AmmoMode.AC_FLECHETTE_MODE, False,
        "Weapon %d has been set to fire Flechette rounds",
        "Weapon %d has been set to fire normal rounds",
        "That weapon cannot fire Flechette rounds!"),
    # mech.advanced.c:511-521
    'incendiary': (
        1, WeaponFlags.RFAC, AmmoMode.AC_INCENDIARY_MODE, False,
        "Weapon %d has been set to fire Incendiary rounds",
        "Weapon %d has been set to fire normal rounds",
        "That weapon cannot fire Incendiary rounds!"),
    # mech.advanced.c:521-531
    'precision': (
        1, WeaponFlags.RFAC, AmmoMode.AC_PRECISION_MODE, False,
        "Weapon %d has been set to fire Precision rounds",
        "Weapon %d has been set to fire normal rounds",
        "That weapon cannot fire Precision rounds!"),
    # mech.advanced.c:533-542
    'rapidfire': (
        1, WeaponFlags.RFAC, FireMode.RFAC_MODE, True,
        "Weapon %d has been set to Rapid Fire mode",
        "Weapon %d has been set to normal fire mode",
        "That weapon cannot be set to do rapid fire!"),
    # mech.advanced.c:544-552
    'stinger': (
        2, 0, AmmoMode.STINGER_MODE, False,
        "Weapon %d has been set to fire stinger missiles.",
        "Weapon %d has been set to fire normal missiles",
        "That weapon cannot be set STINGER!"),
    # mech.advanced.c:646-654
    'gattling': (
        1, WeaponFlags.GMG, FireMode.GATTLING_MODE, True,
        "Weapon %d has been set to Gattling mode",
        "Weapon %d has been set to normal fire mode",
        "That weapon cannot be set to do gattling fire!"),
    # mech.advanced.c:657-667
    'artemis': (
        6, WeaponType.TMISSILE, AmmoMode.ARTEMIS_MODE, False,
        "Weapon %d has been set to fire Artemis IV compatible missiles.",
        "Weapon %d has been set to fire normal missiles",
        "That weapon cannot be set ARTEMIS!"),
    # mech.advanced.c:669-678
    'narc': (
        0, WeaponType.TMISSILE, AmmoMode.NARC_MODE, False,
        "Weapon %d has been set to fire Narc Beacon compatible missiles.",
        "Weapon %d has been set to fire normal missiles",
        "That weapon cannot be set NARC!"),
    # mech.advanced.c:680-689
    'swarm': (
        2, 0, AmmoMode.SWARM_MODE, False,
        "Weapon %d has been set to fire Swarm missiles.",
        "Weapon %d has been set to fire normal missiles",
        "That weapon cannot be set to fire Swarm missiles!"),
    # mech.advanced.c:691-700
    'sguided': (
        2, 0, AmmoMode.SGUIDED_MODE, False,
        "Weapon %d has been set to fire Sguided missiles.",
        "Weapon %d has been set to fire normal missiles",
        "That weapon cannot be set to fire Sguided missiles!"),
    # mech.advanced.c:702-711
    'atmrange': (
        2, WeaponType.TMISSILE, AmmoMode.ATM_ER_MODE, False,
        "Weapon %d has been set to fire Extended Range missiles.",
        "Weapon %d has been set to fire normal missiles.",
        "That weapon cannot be set to fire Extended Range missiles!"),
    # mech.advanced.c:713-722
    'atmexplosive': (
        2, WeaponType.TMISSILE, AmmoMode.ATM_HE_MODE, False,
        "Weapon %d has been set to fire High Explosive missiles.",
        "Weapon %d has been set to fire normal missiles.",
        "That weapon cannot be set to fire High Explosive missiles!"),
    # mech.advanced.c:724-733
    'swarm1': (
        2, 0, AmmoMode.SWARM1_MODE, False,
        "Weapon %d has been set to fire Swarm1 missiles.",
        "Weapon %d has been set to fire normal missiles",
        "That weapon cannot be set to fire Swarm1 missiles!"),
    # mech.advanced.c:735-743
    'inferno': (
        4, 0, AmmoMode.INFERNO_MODE, False,
        "Weapon %d has been set to fire Inferno missiles.",
        "Weapon %d has been set to fire normal missiles",
        "That weapon cannot be set to fire Inferno missiles!"),
    # mech.advanced.c:745-752
    'hotload': (
        1, WeaponFlags.IDF, FireMode.HOTLOAD_MODE, True,
        "Hotloading for weapon %d has been toggled on.",
        "Hotloading for weapon %d has been toggled off.",
        "That weapon can not be hotloaded!"),
    # mech.advanced.c:755-763
    'cluster': (
        0, WeaponType.TARTILLERY, AmmoMode.CLUSTER_MODE, False,
        "Weapon %d has been set to fire cluster rounds.",
        "Weapon %d has been set to fire normal rounds",
        "Invalid weapon type!"),
    # mech.advanced.c:765-773
    'smoke': (
        4, 0, AmmoMode.SMOKE_MODE, False,
        "Weapon %d has been set to fire smoke rounds.",
        "Weapon %d has been set to fire normal rounds",
        "Invalid weapon type!"),
    # mech.advanced.c:775-785 (cant string per the cluster/smoke pattern)
    'mine': (
        4, 0, AmmoMode.MINE_MODE, False,
        "Weapon %d has been set to fire mine rounds.",
        "Weapon %d has been set to fire normal rounds",
        "Invalid weapon type!"),
}

# RAC rate select (mech.advanced.c:554-598): rate '1' is the group-clear
# arm (mode 0), '2'/'4'/'6' pick a RAC_*SHOT fire mode.
_RAC_MODES = {
    '1': (0,
          "Weapon %d has been set to fire one shot at a time.",
          "Weapon %d is already set to fire one shot at a time."),
    '2': (FireMode.RAC_TWOSHOT_MODE,
          "Weapon %d has been set to fire two shots at a time.",
          "Weapon %d is already set to fire two shots at a time."),
    '4': (FireMode.RAC_FOURSHOT_MODE,
          "Weapon %d has been set to fire four shots at a time.",
          "Weapon %d is already set to fire four shots at a time."),
    '6': (FireMode.RAC_SIXSHOT_MODE,
          "Weapon %d has been set to fire six shots at a time.",
          "Weapon %d is already set to fire six shots at a time."),
}

# iNARC pod select (mech.advanced.c:400-452): default/homing is the
# group-clear arm (mode 0); X/Y/E/Z pick a pod ammo mode.
_INARC_MODES = {
    'H': (0,
          "Weapon %d has been set to fire INARC Homing pods",
          "Weapon %d is already set to fire INARC Homing pods"),
    'X': (AmmoMode.INARC_EXPLO_MODE,
          "Weapon %d has been set to fire INARC Explosive pods",
          "Weapon %d is already set to fire INARC Explosive pods"),
    'Y': (AmmoMode.INARC_HAYWIRE_MODE,
          "Weapon %d has been set to fire INARC Haywire pods",
          "Weapon %d is already set to fire INARC Haywire pods"),
    'E': (AmmoMode.INARC_ECM_MODE,
          "Weapon %d has been set to fire INARC ECM pods",
          "Weapon %d is already set to fire INARC ECM pods"),
    'Z': (AmmoMode.INARC_NEMESIS_MODE,
          "Weapon %d has been set to fire INARC Nemesis pods",
          "Weapon %d is already set to fire INARC Nemesis pods"),
}


def _run_command(mech: 'Mech', weapon_number: int,
                 name: str, *, caller=None) -> ToggleResult:
    spec = _COMMANDS[name]
    return toggle_mode(mech, weapon_number, *spec, caller=caller)


def mech_flamerheat(mech, n): return _run_command(mech, n, 'flamerheat')
def mech_ultra(mech, n): return _run_command(mech, n, 'ultra')
def mech_explosive(mech, n): return _run_command(mech, n, 'explosive')
def mech_lbx(mech, n): return _run_command(mech, n, 'lbx')
def mech_armorpiercing(mech, n): return _run_command(mech, n,
                                                     'armorpiercing')
def mech_caseless(mech, n): return _run_command(mech, n, 'caseless')
def mech_flechette(mech, n): return _run_command(mech, n, 'flechette')
def mech_incendiary(mech, n): return _run_command(mech, n, 'incendiary')
def mech_precision(mech, n): return _run_command(mech, n, 'precision')
def mech_rapidfire(mech, n): return _run_command(mech, n, 'rapidfire')
def mech_stinger(mech, n): return _run_command(mech, n, 'stinger')
def mech_gattling(mech, n): return _run_command(mech, n, 'gattling')
def mech_artemis(mech, n): return _run_command(mech, n, 'artemis')
def mech_narc(mech, n): return _run_command(mech, n, 'narc')
def mech_swarm(mech, n): return _run_command(mech, n, 'swarm')
def mech_sguided(mech, n): return _run_command(mech, n, 'sguided')
def mech_atmrange(mech, n): return _run_command(mech, n, 'atmrange')
def mech_atmexplosive(mech, n): return _run_command(mech, n,
                                                    'atmexplosive')
def mech_swarm1(mech, n): return _run_command(mech, n, 'swarm1')
def mech_inferno(mech, n): return _run_command(mech, n, 'inferno')
def mech_hotload(mech, n): return _run_command(mech, n, 'hotload')
def mech_cluster(mech, n): return _run_command(mech, n, 'cluster')
def mech_smoke(mech, n): return _run_command(mech, n, 'smoke')
def mech_mine(mech, n): return _run_command(mech, n, 'mine')


def mech_rac(mech: 'Mech', weapon_number: int,
             rate: str = '1', *, caller=None) -> ToggleResult:
    """
    RAC rate-of-fire select (mech.advanced.c:554-598).

    An unknown rate argument falls back to the one-shot arm, like the
    C's switch default.
    """
    mode, onmsg, offmsg = _RAC_MODES.get(str(rate)[:1], _RAC_MODES['1'])
    return toggle_mode(mech, weapon_number, 1, WeaponFlags.RAC, mode,
                       True, onmsg, offmsg,
                       "That weapon is not a RotaryAC!", caller=caller)


def mech_inarc_ammo(mech: 'Mech', weapon_number: int,
                    pod: str = 'H', *, caller=None) -> ToggleResult:
    """
    iNARC pod-type select (mech_inarc_ammo_toggle,
    mech.advanced.c:400-452).

    An unknown pod argument falls back to homing, like the C's switch
    default.  NB the C passes tFireMode=1 for the no-arg homing arm and
    0 for the explicit variants; the homing arm has mode 0 so it always
    reaches the iNARC group-clear branch either way - the port passes
    firemode_toggle=False uniformly.
    """
    mode, onmsg, offmsg = _INARC_MODES.get(
        str(pod).upper()[:1] or 'H', _INARC_MODES['H'])
    return toggle_mode(mech, weapon_number, 1, WeaponFlags.INARC, mode,
                       False, onmsg, offmsg,
                       "That weapon is not an INARC launcher!", caller=caller)


def mode_command(mech, name, text, *, caller=None, wizard=False):
    """Text entry for the mode family; callback refusal continues selection."""
    from systems.combat_commands import command_guard
    from systems.tic import multi_weap_sel
    from systems.movement_commands import notify
    name=name.lower()
    if name not in _COMMANDS and name not in ('rac','inarc','ams'):
        raise ValueError('Unknown weapon mode command')
    result=ToggleResult(accepted=False,messages=CommandMessages(unit=mech,caller=caller))
    if name!='rac':
        error=command_guard(mech,map_required=name=='inarc',caller=caller,wizard=wizard)
        if error:
            result.messages.append(error)
            return result
    if name=='ams':
        result=mech_ams(mech,caller=caller)
    else:
        args=parse_attributes(text,2 if name in ('rac','inarc') else 1)
        if not args:
            result.messages.append('Please specify a weapon number.')
            return result
        def toggle(unit,index,high):
            if name=='rac':one=mech_rac(unit,index,args[1] if len(args)>1 else '1',caller=caller)
            elif name=='inarc':one=mech_inarc_ammo(unit,index,args[1] if len(args)>1 else 'H',caller=caller)
            else:one=_run_command(unit,index,name,caller=caller)
            result.success |= one.success
            result.messages.extend(one.messages)
            return 0
        result.accepted=multi_weap_sel(mech,args[0],1,toggle,result.messages)
    return result


# =============================================================================
# gof/nogof derivation for the wiring wave
# =============================================================================

def ammo_mode_filters(slot, weapon=None) -> tuple:
    """
    Derive FindAndCheckAmmo's (nogof, gof) pair from a firing crit.

    Pure helper for the later fire-path wiring; findAmmoInSection's
    consumption of the pair (mech.utils.c:1301-1321) is combat.py work,
    NOT this module's.

    Per FindAndCheckAmmo (mech.utils.c:2647-2676):
    - mod = slot.ammomode & AMMO_MODES
    - mod == 0 (no special mode): nogof = AMMO_MODES, gof = 0 - any bin
      NOT in a special mode is usable.
    - else: gof = mod, and nogof = (~mod) & ARTILLERY_MODES for artillery
      weapons (mech.utils.c:2668-2669) or (~mod) & AMMO_MODES otherwise
      (mech.utils.c:2670-2671).
    """
    mod = slot.ammomode & AmmoMode.AMMO_MODES
    if not mod:
        return (int(AmmoMode.AMMO_MODES), 0)
    if weapon is not None and \
            weapon.weapon_type == WeaponType.TARTILLERY:
        nogof = (~mod) & AmmoMode.ARTILLERY_MODES
    else:
        nogof = (~mod) & AmmoMode.AMMO_MODES
    return (int(nogof), int(mod))
