# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.advanced.c
#   btech/mech.ecm.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.ecm.h
#   btech/src/btech/mech.h
#   btech/src/include/btconfig.h

"""
ECM / ECCM — port of mech.ecm.c (Kipsta's Mar 2001 multi-unit rewrite).

The C keeps all ECM state in MECH.status2 (mech.h:1026-1041); the Python
Mech dataclass has no status2 field, so this module reads/writes a plain
`status2` attr (getattr default 0, setattr on write) — the same convention
systems/sensors.py already uses for SLITE_ON.

Contract mirror attrs: check_ecm() always (re)writes four plain int attrs
on the mech it checks, 0 when clear, so the getattr touchpoints in
systems/sensors.py never see stale values:

- mech.ecm_disturbed        = AnyECMDisturbed(mech)   (btmacros.h:765)
- mech.ecm_protected        = ECMProtected(mech)      (btmacros.h:771)
- mech.angel_ecm_protected  = AngelECMProtected(mech) (btmacros.h:804)
- mech.angel_ecm_disturbed  = AngelECMDisturbed(mech) (btmacros.h:805)

The ENABLED bits are toggled by the mech_ecm/mech_eccm command family,
ported at the bottom of this module from mech.advanced.c:37-138.  (An
earlier note here pointed at mech.ecm.c for the commands — wrong:
mech.ecm.c:290 is only a "moved" comment; the commands live in
mech.advanced.c.)  The toggles do NOT recompute ECM state immediately:
the C only marks the unit for a LOS update and leaves the recompute to
the periodic ECM scan (mech.advanced.c:67-78).
"""

from entities.mech import CritStatus, SectionConfig, Specials

# --- MECH.status2 bits (mech.h:1026-1041) ---
ECM_ENABLED = 0x00000001          # (a) Unit ECM is enabled
ECCM_ENABLED = 0x00000002         # (b) Unit ECCM is enabled
ECM_DISTURBANCE = 0x00000004      # (c) Unit affected by ECM
ECM_PROTECTED = 0x00000008        # (d) Unit protected by ECM
ECM_COUNTERED = 0x00000010        # (e) ECM countered by ECCM
SLITE_ON = 0x00000020             # (f) Unit SLITE is enabled
STH_ARMOR_ON = 0x00000040         # (g) Unit has stealth armor enabled
NULLSIGSYS_ON = 0x00000080        # (h) Unit has nullsig enabled
ANGEL_ECM_ENABLED = 0x00000100    # (i) Unit Angel ECM is enabled
ANGEL_ECCM_ENABLED = 0x00000200   # (j) Unit Angel ECCM is enabled
ANGEL_ECM_PROTECTED = 0x00000400  # (k) Unit protected by Angel ECM
ANGEL_ECM_DISTURBED = 0x00000800  # (l) Unit affected by Angel ECM
PER_ECM_ENABLED = 0x00001000      # (m) Unit Personal ECM is enabled
PER_ECCM_ENABLED = 0x00002000     # (n) Unit Personal ECCM is enabled

ECM_RANGE = 6                     # btconfig.h:212

# Section special: iNARC ECM beacon attached (mech.h:706)
INARC_ECM_ATTACHED = 0x00000008

# sendECMNotification message types (mech.ecm.h:24-27)
ECM_NOTIFY_DISTURBED = 0
ECM_NOTIFY_UNDISTURBED = 1
ECM_NOTIFY_COUNTERED = 2
ECM_NOTIFY_UNCOUNTERED = 3


# =============================================================================
# status2 accessor macros (btmacros.h:741-811)
# =============================================================================

def _status2(mech) -> int:
    """MechStatus2 (btmacros.h): plain attr, calloc-default 0."""
    return getattr(mech, 'status2', 0)


def ecm_enabled(mech) -> int:
    """ECMEnabled (btmacros.h:744)."""
    return _status2(mech) & ECM_ENABLED


def eccm_enabled(mech) -> int:
    """ECCMEnabled (btmacros.h:745)."""
    return _status2(mech) & ECCM_ENABLED


def per_ecm_enabled(mech) -> int:
    """PerECMEnabled (btmacros.h:756)."""
    return _status2(mech) & PER_ECM_ENABLED


def per_eccm_enabled(mech) -> int:
    """PerECCMEnabled (btmacros.h:757)."""
    return _status2(mech) & PER_ECCM_ENABLED


def angel_ecm_enabled(mech) -> int:
    """AngelECMEnabled (btmacros.h:795)."""
    return _status2(mech) & ANGEL_ECM_ENABLED


def angel_eccm_enabled(mech) -> int:
    """AngelECCMEnabled (btmacros.h:796)."""
    return _status2(mech) & ANGEL_ECCM_ENABLED


def ecm_countered(mech) -> int:
    """ECMCountered (btmacros.h:773)."""
    return _status2(mech) & ECM_COUNTERED


def ecm_active(mech) -> bool:
    """ECMActive (btmacros.h:741): enabled and not countered."""
    return bool(ecm_enabled(mech)) and not ecm_countered(mech)


def per_ecm_active(mech) -> bool:
    """PerECMActive (btmacros.h:753)."""
    return bool(per_ecm_enabled(mech)) and not ecm_countered(mech)


def angel_ecm_active(mech) -> bool:
    """AngelECMActive (btmacros.h:792)."""
    return bool(angel_ecm_enabled(mech)) and not ecm_countered(mech)


def ecm_disturbed(mech) -> int:
    """ECMDisturbed (btmacros.h:770)."""
    return _status2(mech) & ECM_DISTURBANCE


def ecm_protected(mech) -> bool:
    """ECMProtected (btmacros.h:771): flagged, or own (personal) ECM active."""
    return bool(_status2(mech) & ECM_PROTECTED) or ecm_active(mech) or \
        per_ecm_active(mech)


def angel_ecm_protected(mech) -> bool:
    """AngelECMProtected (btmacros.h:804): flagged, or own Angel ECM active."""
    return bool(_status2(mech) & ANGEL_ECM_PROTECTED) or angel_ecm_active(mech)


def angel_ecm_disturbed(mech) -> int:
    """AngelECMDisturbed (btmacros.h:805)."""
    return _status2(mech) & ANGEL_ECM_DISTURBED


def any_ecm_disturbed(mech) -> bool:
    """AnyECMDisturbed (btmacros.h:765)."""
    return bool(ecm_disturbed(mech)) or bool(angel_ecm_disturbed(mech))


def _set_bit(mech, bit: int) -> None:
    mech.status2 = _status2(mech) | bit


def _clear_bit(mech, bit: int) -> None:
    mech.status2 = _status2(mech) & ~bit


# =============================================================================
# checkAllSections (mech.utils.c:2447-2468)
# =============================================================================

def check_section_for_special(mech, special_to_find: int, w_sec: int) -> int:
    """checkSectionForSpecial (mech.utils.c:2459-2468)."""
    section = mech.sections[w_sec]
    if section_destroyed(mech, w_sec):
        return 0
    if section.specials & special_to_find:
        return 1
    return 0


def check_all_sections(mech, special_to_find: int) -> int:
    """checkAllSections (mech.utils.c:2447-2457)."""
    for i in range(len(mech.sections)):
        if check_section_for_special(mech, special_to_find, i):
            return 1
    return 0


# =============================================================================
# MarkForLOSUpdate / notifications
# =============================================================================

def mark_for_los_update(mech) -> None:
    """
    Flag the mech for the LOS sweep.  Port of MarkForLOSUpdate
    (mech.utils.c:2242-2251): mapless mechs are ignored; bumps the map's
    moves counter (mech.utils.c:2248) and sets the mech's map flag
    (mechflags[mapnumber] = 1 -> mapflag |= MECHMAPFLAG_MOVED).
    """
    from systems.los import MECHMAPFLAG_MOVED
    from systems.targeting import indexed_map
    obj_map = indexed_map(mech)
    if obj_map is None:
        return
    obj_map.moves = getattr(obj_map, 'moves', 0) + 1       # mech.utils.c:2248
    mech.mapflag = MECHMAPFLAG_MOVED
    slot=getattr(mech,'mapnumber',-1)
    if 0<=slot<len(obj_map.mechflags) and obj_map.roster_ids[slot]==mech._id:
        obj_map.mechflags[slot]=MECHMAPFLAG_MOVED


NOTIFY_HOOK = None


def _notify(mech, message: str) -> None:
    from systems.movement_commands import notify
    notify(mech, message)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


def _has_working_ecm_suite(obj_mech) -> bool:
    """HasWorkingECMSuite (btmacros.h:784-788)."""
    from systems.sensors import FC_INFILTRATORII_STEALTH_TECH
    if ((obj_mech.specials & Specials.ECM_TECH) and
            not (obj_mech.crit_status & CritStatus.ECM_DESTROYED)):
        return True
    if (_has_angel_ecm_tech(obj_mech) and
            not (obj_mech.crit_status & CritStatus.ANGEL_ECM_DESTROYED)):
        return True
    return bool(getattr(obj_mech, 'infantry_specials', 0) &
                FC_INFILTRATORII_STEALTH_TECH)


def send_ecm_notification(obj_mech, w_msg_type: int) -> None:
    """
    sendECMNotification (mech.ecm.c:31-102), LOUD_ECM build (defined,
    VERY_LOUD_ECM undef — mech.ecm.c:28-29).
    """
    if w_msg_type == ECM_NOTIFY_DISTURBED:
        _notify(obj_mech,
                "Half your screens are suddenly filled with static!")
    elif w_msg_type == ECM_NOTIFY_UNDISTURBED:
        _notify(obj_mech, "All your systems are back to normal again!")
    elif w_msg_type == ECM_NOTIFY_COUNTERED:
        if _has_working_ecm_suite(obj_mech):
            _notify(obj_mech, "Your ECM suite's ready light turns red, "
                    "countered by enemy ECCM!")
    elif w_msg_type == ECM_NOTIFY_UNCOUNTERED:
        if _has_working_ecm_suite(obj_mech):
            _notify(obj_mech, "Your ECM suite's ready light turns green, "
                    "enemy ECCM is out of range.")


# =============================================================================
# checkECM (mech.ecm.c:103-290)
# =============================================================================

def _sync_contract_attrs(mech) -> None:
    """
    Mirror the status2 ECM state into the plain contract attrs read by the
    sensor cansee funcs (systems/sensors.py getattr touchpoints).  Always
    written, 0 when clear, so stale values never linger.
    """
    mech.ecm_disturbed = 1 if any_ecm_disturbed(mech) else 0
    mech.ecm_protected = 1 if ecm_protected(mech) else 0
    mech.angel_ecm_protected = 1 if angel_ecm_protected(mech) else 0
    mech.angel_ecm_disturbed = 1 if angel_ecm_disturbed(mech) else 0


def check_ecm(mech) -> None:
    """
    Recompute a unit's ECM/ECCM protection and disturbance from every unit
    within ECM_RANGE on its map.  Port of checkECM (mech.ecm.c:103-290).

    C fidelity notes:
    - The roster scan includes the unit itself (range 0.0 <= ECM_RANGE), so
      a unit's own enabled ECM counts toward its friendly totals
      (mech.ecm.c:129-131).
    - Stealth armor on, or an attached iNARC ECM pod, jams the unit with a
      +1000 unfriendly ECM weight (mech.ecm.c:185-187).
    - Angel ECM/ECCM units count double in the deltas (mech.ecm.c:190-195).
    """
    from systems.sensors import fa_mech_range

    obj_map = getattr(mech, 'map', None)
    if obj_map is None:                                    # mech.ecm.c:126-127
        _sync_contract_attrs(mech)
        return

    w_friendly_ecm = 0
    w_friendly_eccm = 0
    w_unfriendly_ecm = 0
    w_unfriendly_eccm = 0
    w_friendly_angel_ecm = 0
    w_friendly_angel_eccm = 0
    w_unfriendly_angel_ecm = 0
    w_unfriendly_angel_eccm = 0
    t_mark = 0

    for obj_other_mech in obj_map.mechs_on_map:            # mech.ecm.c:129-131
        if obj_other_mech is None:
            continue
        rng = fa_mech_range(obj_other_mech, mech)          # mech.ecm.c:133
        if rng > ECM_RANGE:
            continue

        if obj_other_mech.team == mech.team:               # mech.ecm.c:136
            if ecm_enabled(obj_other_mech):
                w_friendly_ecm += 1
            if eccm_enabled(obj_other_mech):
                w_friendly_eccm += 1
            if angel_ecm_enabled(obj_other_mech):
                w_friendly_angel_ecm += 1
            if angel_eccm_enabled(obj_other_mech):
                w_friendly_angel_eccm += 1
            if rng <= 0.5:                                 # mech.ecm.c:149-155
                if per_ecm_enabled(obj_other_mech):
                    w_friendly_ecm += 1
                if per_eccm_enabled(obj_other_mech):
                    w_friendly_eccm += 1
        else:
            if ecm_enabled(obj_other_mech):
                w_unfriendly_ecm += 1
            if eccm_enabled(obj_other_mech):
                w_unfriendly_eccm += 1
            if angel_ecm_enabled(obj_other_mech):
                w_unfriendly_angel_ecm += 1
            if angel_eccm_enabled(obj_other_mech):
                w_unfriendly_angel_eccm += 1
            if rng <= 0.5:                                 # mech.ecm.c:170-176
                if per_ecm_enabled(obj_other_mech):
                    w_unfriendly_ecm += 1
                if per_eccm_enabled(obj_other_mech):
                    w_unfriendly_eccm += 1

    # Stealth armor / attached iNARC ECM pod jams the unit (mech.ecm.c:185-187)
    if (_status2(mech) & STH_ARMOR_ON) or \
            check_all_sections(mech, INARC_ECM_ATTACHED):
        w_unfriendly_ecm += 1000

    # Generate our deltas (mech.ecm.c:189-195)
    w_friendly_ecm_delta = (w_friendly_ecm + (2 * w_friendly_angel_ecm) -
                            w_unfriendly_eccm - (2 * w_unfriendly_angel_eccm))
    w_friendly_eccm_delta = (w_friendly_eccm + (2 * w_friendly_angel_eccm) -
                             w_unfriendly_ecm - (2 * w_unfriendly_angel_ecm))

    t_check_ecm = ((w_friendly_ecm != 0) or (w_friendly_angel_ecm != 0) or
                   (w_unfriendly_eccm != 0) or (w_unfriendly_angel_eccm != 0))
    t_check_eccm = ((w_friendly_eccm != 0) or (w_friendly_angel_eccm != 0) or
                    (w_unfriendly_ecm != 0) or (w_unfriendly_angel_ecm != 0))

    # No ECM or ECCM around: reset our flags (mech.ecm.c:205-226)
    if not t_check_ecm:
        if ecm_countered(mech):
            send_ecm_notification(mech, ECM_NOTIFY_UNCOUNTERED)
            _clear_bit(mech, ECM_COUNTERED)
            t_mark = 1
        if ecm_protected(mech) or angel_ecm_protected(mech):
            _clear_bit(mech, ECM_PROTECTED)
            _clear_bit(mech, ANGEL_ECM_PROTECTED)
            t_mark = 1

    if not t_check_eccm:
        if any_ecm_disturbed(mech):
            send_ecm_notification(mech, ECM_NOTIFY_UNDISTURBED)
            _clear_bit(mech, ECM_DISTURBANCE)
            _clear_bit(mech, ANGEL_ECM_DISTURBED)
            t_mark = 1

    # Sanity check so we don't bother with the other checks (mech.ecm.c:228-234)
    if not t_check_ecm and not t_check_eccm:
        if t_mark:
            mark_for_los_update(mech)
        _sync_contract_attrs(mech)
        return

    # Now we see if our ECM has been countered (mech.ecm.c:236-260)
    if t_check_ecm:
        if w_friendly_ecm_delta <= 0:
            # They have the same or more ECCM than we have ECM
            if not ecm_countered(mech):
                send_ecm_notification(mech, ECM_NOTIFY_COUNTERED)
                _set_bit(mech, ECM_COUNTERED)
                _clear_bit(mech, ECM_PROTECTED)
                _clear_bit(mech, ANGEL_ECM_PROTECTED)
        else:
            if ecm_countered(mech):
                send_ecm_notification(mech, ECM_NOTIFY_UNCOUNTERED)
                _clear_bit(mech, ECM_COUNTERED)
            if w_friendly_ecm > 0:
                _set_bit(mech, ECM_PROTECTED)
            else:
                _clear_bit(mech, ECM_PROTECTED)
            if w_friendly_angel_ecm > 0:
                _set_bit(mech, ANGEL_ECM_PROTECTED)
            else:
                _clear_bit(mech, ANGEL_ECM_PROTECTED)

    # Now we see if we're under an enemy ECM umbrella (mech.ecm.c:262-288)
    if t_check_eccm:
        if w_friendly_eccm_delta < 0:
            # They have more ECM than we have ECCM
            if not any_ecm_disturbed(mech):
                send_ecm_notification(mech, ECM_NOTIFY_DISTURBED)
                if w_unfriendly_ecm > 0:
                    _set_bit(mech, ECM_DISTURBANCE)
                else:
                    _clear_bit(mech, ECM_DISTURBANCE)
                if w_unfriendly_angel_ecm > 0:
                    _set_bit(mech, ANGEL_ECM_DISTURBED)
                else:
                    _clear_bit(mech, ANGEL_ECM_DISTURBED)
                mark_for_los_update(mech)
        else:
            if any_ecm_disturbed(mech):
                send_ecm_notification(mech, ECM_NOTIFY_UNDISTURBED)
                _clear_bit(mech, ECM_DISTURBANCE)
                _clear_bit(mech, ANGEL_ECM_DISTURBED)
                mark_for_los_update(mech)

    _sync_contract_attrs(mech)


# =============================================================================
# Enable/disable commands (mech.advanced.c:37-138)
# =============================================================================
# Verbatim shape: the toggles do NOT call check_ecm() — they only mark the
# unit for a LOS update; the periodic ECM scan recomputes the protection /
# disturbance state afterwards (mech.advanced.c:67-78).
#
# Toggle semantics (the C's TOGGLE/TOGGLE2 macros): if the set-bit is
# already on -> turn it off with the offline message; else -> turn it on
# with the online message AND clear the opposing bit (ECM<->ECCM mutual
# exclusion within each pair).  Lacking the tech special -> the "isn't
# equipped" message.  Each command returns the C notify texts as a
# list[str].


ANGEL_ECM_TECH = 0x1000                    # mech.h:1179


def _has_angel_ecm_tech(mech) -> bool:
    """
    MechSpecials2 & ANGEL_ECM_TECH — the TOGGLE2 equipment gate for the
    angel pair (mech.advanced.c:37-138).
    """
    return bool(int(getattr(mech, 'specials2', 0)) & ANGEL_ECM_TECH)


def _toggle(mech, set_bit, opposing_bit, on_msg, off_msg):
    from systems.combat_commands import CommandMessages
    messages = CommandMessages(unit=mech)
    if _status2(mech) & set_bit:
        messages.unit(off_msg)
        _clear_bit(mech, set_bit)
    else:
        messages.unit(on_msg)
        _set_bit(mech, set_bit)
        _clear_bit(mech, opposing_bit)
    mark_for_los_update(mech)
    return messages


def _ecm_command(mech, family, counter, *, caller=None, wizard=False):
    from systems.combat_commands import command_guard, CommandMessages
    messages = CommandMessages(unit=mech, caller=caller)
    error = command_guard(mech, caller=caller, wizard=wizard)
    if error:
        messages.append(error)
        return messages
    from systems.sensors import FC_INFILTRATORII_STEALTH_TECH
    label, equipped, destroyed, on, off = {
        'guardian': ('', bool(mech.specials & Specials.ECM_TECH), bool(mech.crit_status & CritStatus.ECM_DESTROYED), ECM_ENABLED, ECCM_ENABLED),
        'angel': ('Angel ', _has_angel_ecm_tech(mech), bool(mech.crit_status & CritStatus.ANGEL_ECM_DESTROYED), ANGEL_ECM_ENABLED, ANGEL_ECCM_ENABLED),
        'personal': ('Personal ', bool(mech.infantry_specials & FC_INFILTRATORII_STEALTH_TECH), False, PER_ECM_ENABLED, PER_ECCM_ENABLED),
    }[family]
    if destroyed:
        messages.append(f'Your {"Guardian" if family=="guardian" else "Angel"} ECM has been destroyed already!')
        return messages
    if not equipped:
        article = 'a' if family=='personal' else 'an'
        messages.append(f"This unit isn't equipped with {article} {label}ECM suite!")
        mark_for_los_update(mech)
        return messages
    return _toggle(mech, off if counter else on, on if counter else off,
                   f'You turn your {label}ECM suite online ({"ECCM" if counter else "ECM"} mode).',
                   f'You turn your {label}ECM suite offline.')


def mech_ecm(mech, **actor): return _ecm_command(mech, 'guardian', False, **actor)
def mech_eccm(mech, **actor): return _ecm_command(mech, 'guardian', True, **actor)
def mech_angelecm(mech, **actor): return _ecm_command(mech, 'angel', False, **actor)
def mech_angeleccm(mech, **actor): return _ecm_command(mech, 'angel', True, **actor)
def mech_perecm(mech, **actor): return _ecm_command(mech, 'personal', False, **actor)
def mech_pereccm(mech, **actor): return _ecm_command(mech, 'personal', True, **actor)


def section_destroyed(mech, index):
    from entities.mech import UnitType
    section=mech.sections[index]
    dropship=mech.unit_type in (UnitType.DS,UnitType.SPHEROID_DS)
    aero=mech.unit_type==UnitType.AERO or dropship
    return section.armor==0 and (aero or section.internal==0) and not dropship
