# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.bth.c
#   btech/mech.combat.c
#   btech/mech.enhanced.criticals.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/failures.h
#   btech/src/btech/mech.h

"""
Enhanced weapon criticals — partial weapon damage instead of instant kills.

Port of mech.enhanced.criticals.c, including weapon status/readouts,
plus the split-crit walkers it leans on
(FindSplitCrits / GetSplitData, mech.utils.c:1472-1528) and the weapon
temp-nuke (jam) nibble accessors (btmacros.h:317-320).

A critted weapon may keep working with a damage flag instead of dying:
warped barrels, damaged ammo feeds, knocked-out focus crystals.  The
flags' effects hook into the fire path (BTH, heat, damage, jam/explode
rolls, ammo-switch locks) — mech.bth.c:412, mech.combat.c:1164-1218,
:1383, :1475.
"""
from core.randomness import roll as source_roll

from typing import TYPE_CHECKING, Optional, Tuple

from entities.crittypes import Special, i2special
from entities.weapon import WeaponType
from entities.mech import (
    NUM_CRITICALS,
    FireMode,
    Location,
    UnitType,
)

if TYPE_CHECKING:
    from entities.mech import Mech

# Weapon damage flags (mech.h:670-676)
WEAP_DAM_MODERATE = 0x00000001    # +1 to hit
WEAP_DAM_EN_FOCUS = 0x00000002    # Energy: -1 damage, +1 BTH at med/long
WEAP_DAM_EN_CRYSTAL = 0x00000004  # Energy: +1 heat; roll-2 explosion
WEAP_DAM_BALL_BARREL = 0x00000008  # Ballistic: roll-2 jam
WEAP_DAM_BALL_AMMO = 0x00000010   # Ballistic: feed damaged, no ammo switch
WEAP_DAM_MSL_RANGING = 0x00000020  # Missile: +1 BTH at med/long
WEAP_DAM_MSL_AMMO = 0x00000040    # Missile: feed damaged, no ammo switch

# Weapon temp-nuke (failure) states (failures.h:35-42)
FAIL_NONE = 0
FAIL_JAMMED = 1
FAIL_SHORTED = 2
FAIL_DUD = 3
FAIL_EMPTY = 4
FAIL_DESTROYED = 5
FAIL_AMMOJAMMED = 6
FAIL_AMMOCRITJAMMED = 7


# =============================================================================
# Temp-nuke nibble (btmacros.h:317-320): jams live in the upper 4 bits of
# the slot's brand byte
# =============================================================================

def part_temp_nuke(crit) -> int:
    """PartTempNuke (btmacros.h:319)."""
    return crit.brand >> 4


def set_part_temp_nuke(crit, value: int) -> None:
    """SetPartTempNuke (btmacros.h:320): keep the brand nibble."""
    crit.brand = (crit.brand & 0x0F) + (value << 4)


# =============================================================================
# Split-crit walkers (mech.utils.c:1472-1528)
# =============================================================================

def find_split_crits(mech: 'Mech', sect: int, crit_type: int,
                     crit: int) -> int:
    """
    Find the SPLIT_CRIT marker slot in `sect` whose data points back at
    `crit`.  Port of FindSplitCrits (mech.utils.c:1472-1481).
    """
    from entities.crittypes import crits_in_loc

    section = mech.sections[sect]
    for i in range(crits_in_loc(mech, sect)):
        slot = section.criticals[i]
        if slot.type == crit_type and slot.data == crit:
            return i
    return -1


def get_split_data(mech: 'Mech', sect: int,
                   data: int) -> Optional[Tuple[int, int, int]]:
    """
    Resolve the other half of a split-crit weapon run.

    Port of GetSplitData (mech.utils.c:1482-1528): arms split into their
    torso, torsos into CT then arm then leg, always via the side's
    SPLIT_CRIT_LEFT/RIGHT marker.  Returns (section, crit, marker_type)
    or None.
    """
    if sect == Location.RARM:
        stype = i2special(Special.SPLIT_CRIT_RIGHT)
        scrit = find_split_crits(mech, Location.RTORSO, stype, data)
        if scrit >= 0:
            return (Location.RTORSO, scrit, stype)
    elif sect == Location.LARM:
        stype = i2special(Special.SPLIT_CRIT_LEFT)
        scrit = find_split_crits(mech, Location.LTORSO, stype, data)
        if scrit >= 0:
            return (Location.LTORSO, scrit, stype)
    elif sect == Location.RTORSO:
        stype = i2special(Special.SPLIT_CRIT_RIGHT)
        for osect in (Location.CTORSO, Location.RARM, Location.RLEG):
            scrit = find_split_crits(mech, osect, stype, data)
            if scrit >= 0:
                return (osect, scrit, stype)
    elif sect == Location.LTORSO:
        stype = i2special(Special.SPLIT_CRIT_LEFT)
        for osect in (Location.CTORSO, Location.LARM, Location.LLEG):
            scrit = find_split_crits(mech, osect, stype, data)
            if scrit >= 0:
                return (osect, scrit, stype)
    return None


# =============================================================================
# Weapon-run helpers
# =============================================================================

def get_weap_data(mech: 'Mech', section: int,
                  critical: int) -> Tuple[int, int, int]:
    """
    (weapon index, crit-slot count, first crit of the run) for the weapon
    occupying a slot.  Port of getWeapData
    (mech.enhanced.criticals.c:20-38).
    """
    from entities.crittypes import weapon2i
    from entities.weapon import get_weapon_by_index
    from systems.criticals import find_first_weapon_crit

    crit_type = mech.sections[section].criticals[critical].type
    weap_index = weapon2i(crit_type)
    weapon = get_weapon_by_index(weap_index)
    weap_size = weapon.crits if weapon is not None and mech.unit_type == UnitType.MECH else 1
    first_crit = find_first_weapon_crit(mech, section, critical, 0,
                                        crit_type, weap_size)
    return weap_index, weap_size, first_crit


def _iter_run_flags(mech: 'Mech', section: int, first_crit: int,
                    weap_size: int):
    """
    Yield each slot's damage flags across a weapon's crit run, following
    the split-crit tail exactly the way the C's copy-pasted loops do
    (mech.enhanced.criticals.c:56-78 and siblings): the run's slots in
    this section, then — if the section held fewer than weap_size — the
    remainder read from the split section starting at the MARKER slot
    index (ncrit), the C's own indexing oddity, preserved.
    """
    count = 0
    section_obj = mech.sections[section]
    for i in range(first_crit, min(NUM_CRITICALS, first_crit + weap_size)):
        yield section_obj.criticals[i]
        count += 1
    if count < weap_size and mech.unit_type == UnitType.MECH:
        split = get_split_data(mech, section, first_crit)
        if split is not None:
            nloc, ncrit, _stype = split
            other = mech.sections[nloc]
            for i in range(ncrit, weap_size - count):
                if 0 <= i < len(other.criticals):
                    yield other.criticals[i]


def get_crit_added_bth(mech: 'Mech', section: int, critical: int,
                       range_bracket: int) -> int:
    """
    +1 BTH per MODERATE slot, +1 per focus/ranging slot outside short
    range.  Port of getCritAddedBTH (mech.enhanced.criticals.c:40-80).
    range_bracket uses the RANGE_* values (mech.h; RANGE_SHORT == 0).
    """
    if mech.unit_type != UnitType.MECH:
        return 0
    _wi, weap_size, first_crit = get_weap_data(mech, section, critical)
    mod = 0
    for slot in _iter_run_flags(mech, section, first_crit, weap_size):
        if slot.weap_damage_flags & WEAP_DAM_MODERATE:
            mod += 1
        if (slot.weap_damage_flags &
                (WEAP_DAM_EN_FOCUS | WEAP_DAM_MSL_RANGING)) and \
                range_bracket != RANGE_SHORT:
            mod += 1
    return mod


def get_crit_added_heat(mech: 'Mech', section: int, critical: int) -> int:
    """
    +1 heat per damaged charging crystal.  Port of getCritAddedHeat
    (mech.enhanced.criticals.c:82-114); energy weapons only.
    """
    from entities.weapon import get_weapon_by_index

    weap_index, weap_size, first_crit = get_weap_data(mech, section,
                                                      critical)
    weapon = get_weapon_by_index(weap_index)
    if weapon is None or weapon.weapon_type != WeaponType.TBEAM:
        return 0
    mod = 0
    for slot in _iter_run_flags(mech, section, first_crit, weap_size):
        if slot.weap_damage_flags & WEAP_DAM_EN_CRYSTAL:
            mod += 1
    return mod


def get_crit_sub_damage(mech: 'Mech', section: int, critical: int) -> int:
    """
    -1 damage per misaligned focus.  Port of getCritSubDamage
    (mech.enhanced.criticals.c:116-151); mechs' energy weapons only.
    """
    from entities.weapon import get_weapon_by_index

    if mech.unit_type != UnitType.MECH:
        return 0
    weap_index, weap_size, first_crit = get_weap_data(mech, section,
                                                      critical)
    weapon = get_weapon_by_index(weap_index)
    if weapon is None or weapon.weapon_type != WeaponType.TBEAM:
        return 0
    mod = 0
    for slot in _iter_run_flags(mech, section, first_crit, weap_size):
        if slot.weap_damage_flags & WEAP_DAM_EN_FOCUS:
            mod += 1
    return mod


def can_weap_explode_from_damage(mech: 'Mech', section: int, critical: int,
                                 roll: int) -> bool:
    """
    Damaged crystals / ammo feeds detonate when (damaged-slot count + 1)
    reaches the fire roll.  Port of canWeapExplodeFromDamage
    (mech.enhanced.criticals.c:153-188).
    """
    if mech.unit_type != UnitType.MECH:
        return False
    _wi, weap_size, first_crit = get_weap_data(mech, section, critical)
    check = 0
    for slot in _iter_run_flags(mech, section, first_crit, weap_size):
        if slot.weap_damage_flags & (WEAP_DAM_EN_CRYSTAL |
                                     WEAP_DAM_BALL_AMMO |
                                     WEAP_DAM_MSL_AMMO):
            check += 1
    if check > 0:
        check += 1
    return check >= roll


def can_weap_jam_from_damage(mech: 'Mech', section: int, critical: int,
                             roll: int) -> bool:
    """
    Warped barrels jam the same way.  Port of canWeapJamFromDamage
    (mech.enhanced.criticals.c:190-225).
    """
    if mech.unit_type != UnitType.MECH:
        return False
    _wi, weap_size, first_crit = get_weap_data(mech, section, critical)
    check = 0
    for slot in _iter_run_flags(mech, section, first_crit, weap_size):
        if slot.weap_damage_flags & WEAP_DAM_BALL_BARREL:
            check += 1
    if check > 0:
        check += 1
    return check >= roll


def is_weap_ammo_feed_locked(mech: 'Mech', section: int,
                             critical: int) -> bool:
    """
    A damaged ammo feed can't switch ammo types.  Port of
    isWeapAmmoFeedLocked (mech.enhanced.criticals.c:227-258).
    """
    if mech.unit_type != UnitType.MECH:
        return False
    _wi, weap_size, first_crit = get_weap_data(mech, section, critical)
    for slot in _iter_run_flags(mech, section, first_crit, weap_size):
        if slot.weap_damage_flags & (WEAP_DAM_BALL_AMMO |
                                     WEAP_DAM_MSL_AMMO):
            return True
    return False


def count_damaged_slots(mech: 'Mech', section: int, first_crit: int,
                        weap_size: int) -> int:
    """Port of countDamagedSlots (mech.enhanced.criticals.c:272-294)."""
    count = 0
    for slot in _iter_run_flags(mech, section, first_crit, weap_size):
        if slot.firemode & FireMode.DAMAGED_MODE:
            count += 1
    return count


def should_destroy_weapon(mech: 'Mech', section: int, critical: int,
                          increment_count: bool) -> bool:
    """
    Once more than half a weapon's slots are damaged, the next crit kills
    it.  Port of shouldDestroyWeapon (mech.enhanced.criticals.c:296-319);
    non-mechs always destroy outright.
    """
    if mech.unit_type != UnitType.MECH:
        return True
    _wi, weap_size, first_crit = get_weap_data(mech, section, critical)
    damaged = 1 if increment_count else 0
    damaged += count_damaged_slots(mech, section, first_crit, weap_size)
    return (damaged * 2) > weap_size


# Range brackets (mech.h) — used by getCritAddedBTH's short-range exemption
RANGE_SHORT = 0
RANGE_MEDIUM = 1
RANGE_LONG = 2


def score_enhanced_weapon_critical_hit(mech: 'Mech',
                                       attacker: Optional['Mech'],
                                       section: int, critical: int,
                                       notify=None) -> Optional[str]:
    """
    Roll the enhanced-crit table for a weapon slot: 2d6 + damaged slots
    + 1, bracketed into nothing / moderate / type-specific flag /
    destruction — unless the run is already half damaged, which destroys
    outright.

    Port of scoreEnhancedWeaponCriticalHit
    (mech.enhanced.criticals.c:321-430).  Returns the notify string for
    the outcome, with live MECHALL delivery at the source mutation point.
    """
    import random

    from entities.weapon import get_weapon_by_index
    from systems.criticals import destroy_weapon

    weap_index, weap_size, first_crit = get_weap_data(mech, section,
                                                      critical)
    weapon = get_weapon_by_index(weap_index)
    name = weapon.name[3:] if weapon is not None else "weapon"
    if notify is None:
        from systems.damage import _notify
        notify = _notify
    slot = mech.sections[section].criticals[critical]
    from core.randomness import draw
    crit_roll = source_roll('enhanced_rolls', lambda: random.randint(1, 6) + random.randint(1, 6))

    destroy = False
    no_crit = False
    moderate = False
    message = None

    if should_destroy_weapon(mech, section, critical, True):
        destroy = True
    else:
        crit_roll += count_damaged_slots(mech, section, first_crit,
                                         weap_size)
        crit_roll += 1

    if not destroy:
        # IsEnergy/IsMissile/IsBallistic/IsArtillery (mech.h:129-132)
        wt = weapon.weapon_type if weapon is not None else None
        is_energy = wt == WeaponType.TBEAM
        is_missile = wt == WeaponType.TMISSILE
        is_ballistic = wt in (WeaponType.TAMMO, WeaponType.TARTILLERY)
        if is_energy:
            if crit_roll <= 3:
                no_crit = True
            elif crit_roll <= 5:
                moderate = True
            elif crit_roll <= 7:
                message = ("Your %s's focusing mechanism gets knocked out "
                           "of alignment!!" % name)
                notify(mech, message)
                slot.weap_damage_flags |= WEAP_DAM_EN_FOCUS
            elif crit_roll <= 9:
                message = ("Your %s's charging crystal takes a direct "
                           "hit!!" % name)
                notify(mech, message)
                slot.weap_damage_flags |= WEAP_DAM_EN_CRYSTAL
            else:
                destroy = True
        elif is_missile:
            if crit_roll <= 3:
                no_crit = True
            elif crit_roll <= 5:
                moderate = True
            elif crit_roll <= 7:
                message = "Your %s's ranging system takes a hit!!" % name
                notify(mech, message)
                slot.weap_damage_flags |= WEAP_DAM_MSL_RANGING
            elif crit_roll <= 9:
                message = "Your %s's ammo feed is damaged!!" % name
                notify(mech, message)
                slot.weap_damage_flags |= WEAP_DAM_MSL_AMMO
            else:
                destroy = True
        elif is_ballistic:
            if crit_roll <= 3:
                no_crit = True
            elif crit_roll <= 5:
                moderate = True
            elif crit_roll <= 7:
                message = "Your %s's barrel warps from the damage!!" % name
                notify(mech, message)
                slot.weap_damage_flags |= WEAP_DAM_BALL_BARREL
            elif crit_roll <= 9:
                message = "Your %s's ammo feed is damaged!!" % name
                notify(mech, message)
                slot.weap_damage_flags |= WEAP_DAM_BALL_AMMO
            else:
                destroy = True
        else:
            destroy = True

    if destroy:
        message = "Your %s has been destroyed!!" % name
        notify(mech, message)
        destroy_weapon(mech, section, slot.type, first_crit, 1, weap_size)
        from systems.criticals import _mark_weapon_state_destroyed
        _mark_weapon_state_destroyed(mech, section, first_crit)
    else:
        # DamagePart (btmacros.h:326)
        slot.firemode |= FireMode.DAMAGED_MODE
        if no_crit:
            message = ("Your %s takes a hit but suffers no noticeable "
                       "damage!!" % name)
            notify(mech, message)
        elif moderate:
            message = "Your %s takes a hit but continues working!!" % name
            notify(mech, message)
            slot.weap_damage_flags |= WEAP_DAM_MODERATE

    return message


def count_damaged_slots_from_crit(mech, section, critical):
    _, size, first = get_weap_data(mech, section, critical)
    return count_damaged_slots(mech, section, first, size)


def show_weapon_damage_and_info(mech, section, critical):
    """Legacy display uses raw mask sums and its own zero-count split bounds."""
    _, size, first = get_weap_data(mech, section, critical)
    slots = list(mech.sections[section].criticals[first:min(12, first+size)])
    if mech.unit_type == UnitType.MECH:
        split = get_split_data(mech, section, first)
        if split:
            loc, index, _ = split
            slots += mech.sections[loc].criticals[index:size]
    counts = [0, 0, 0]
    damage = [0, 0, 0]
    for slot in slots:
        if slot.firemode & FireMode.DAMAGED_MODE:
            counts[0] += 1
            for i, mask in enumerate((1, 2|8|32, 4|16|64)):
                damage[i] += slot.weap_damage_flags & mask
        elif slot.firemode & FireMode.DESTROYED_MODE:
            counts[1] += 1
        elif slot.firemode & FireMode.DISABLED_MODE:
            counts[2] += 1
    from entities.weapon import get_weapon_by_index
    index, _, _ = get_weap_data(mech, section, critical)
    weapon = get_weapon_by_index(index)
    from systems.parts import armor_string
    messages = []
    def hits(count):return f'{count} hit' + ('s' if count > 1 else '')
    if damage[0]:messages.append(f'      General damage ({hits(damage[0])}): +{damage[0]} to hit.')
    if weapon is not None:
        wt = weapon.weapon_type
        if damage[1]:
            n = damage[1]
            if wt == WeaponType.TBEAM:
                messages.append(f'      Focus misalignment ({hits(n)}): -{n} damage. +{n} to hit at >{weapon.range_short} hexes.')
            elif wt == WeaponType.TMISSILE:
                messages.append(f'      Ranging system damage ({hits(n)}): +{n} to hit at >{weapon.range_short} hexes.')
            elif wt in (WeaponType.TAMMO, WeaponType.TARTILLERY):
                messages.append(f'      %cr%chBarrel damage ({hits(n)}): Jams on a {n+1} or less.%c')
        if damage[2]:
            n = damage[2]
            if wt == WeaponType.TBEAM:
                messages.append(f'      Charging crystal damage ({hits(n)}): +{n} heat. Explodes on {n+1} or less.%c')
            elif wt in (WeaponType.TMISSILE, WeaponType.TAMMO, WeaponType.TARTILLERY):
                messages.append(f"      Ammo feed damage ({hits(n)}): Can't switch ammo. Explodes on {n+1} or less.")
    if counts[0] and not any(damage):messages.append('      Damaged, but fully operational.')
    preferred = mech.sections[section].criticals[critical].desired_ammo_loc
    if preferred >= 0:messages.append(f'      Prefered ammo source: {armor_string(mech,preferred)}')
    if any(counts):messages.append(f'      Slot status: Damaged: {counts[0]}. Destroyed: {counts[1]}. Disabled: {counts[2]}')
    if counts[0] or preferred >= 0 or any(counts):messages.append(' ')
    return dict(damage_hits=damage, damaged=counts[0], destroyed=counts[1], disabled=counts[2],
        preferred_ammo_location=mech.sections[section].criticals[critical].desired_ammo_loc,
        bth_short=get_crit_added_bth(mech, section, critical, 0),
        bth_long=get_crit_added_bth(mech, section, critical, 1),
        damage_reduction=get_crit_sub_damage(mech, section, critical),
        extra_heat=get_crit_added_heat(mech, section, critical),
        text='\n'.join(messages))


def weapon_status(mech, *, emit=None):
    from entities.weapon import get_weapon_by_index
    rows = []
    from systems.weapon_inventory import find_weapons
    from systems.parts import armor_string
    for section in range(len(mech.sections)):
        for ws in find_weapons(mech, section) or []:
            slot = mech.sections[ws.section].criticals[ws.critical]
            failure = part_temp_nuke(slot)
            if slot.firemode & (FireMode.DESTROYED_MODE|FireMode.BROKEN_MODE) or failure == FAIL_DESTROYED:
                status = 'DESTROYED'
            elif slot.firemode & FireMode.DISABLED_MODE:
                status = 'DISABLED'
            elif failure:
                status = {1:'JAMMED',2:'SHORTED',3:'DUD',4:'EMPTY',6:'AMMOJAM'}.get(failure, '')
            elif mech.unit_type == UnitType.MECH and count_damaged_slots_from_crit(mech, ws.section, ws.critical):
                status = 'DAMAGED'
            else:
                status = 'OPERATIONAL'
            name = get_weapon_by_index(ws.weapon_idx).name[3:]
            colors = {'DESTROYED':'%ch%crDESTROYED%c','DISABLED':'%cr%chDISABLED%c',
                      'JAMMED':'%cyJAMMED%c','SHORTED':'%cbSHORTED%c','EMPTY':'%ccEMPTY%c',
                      'DUD':'%cyDUD%c','AMMOJAM':'%cyAMMOJAM%c','DAMAGED':'%cy%chDAMAGED%c',
                      'OPERATIONAL':'%cg%chOPERATIONAL%cn'}
            text = f'[{len(rows):2d}] {name[:29]:29s} || {armor_string(mech,ws.section)[:18]:18s}'
            if status:text += '|| ' + colors[status]
            if emit is not None:emit(text)
            detail = show_weapon_damage_and_info(mech, ws.section, ws.critical)
            if emit is not None and detail['text']:
                for line in detail['text'].split('\n'):emit(line)
            rows.append(dict(ordinal=len(rows), section=int(ws.section), critical=ws.critical, name=name,
                status=status, recycle=slot.data, usable=status in ('OPERATIONAL','DAMAGED') and slot.data==0, detail=detail, text=text + ('\n' + detail['text'] if detail['text'] else '')))
    return rows


def weapon_status_command(unit, caller=None):
    from systems.combat_commands import command_guard
    from core.effects import notify_actor
    actor = unit.pilot if caller is None else caller
    error = command_guard(unit, started=False, pilot_only=False, caller=actor)
    if error:
        if not getattr(error,'notified',False):notify_actor(unit,actor,error)
        return dict(accepted=False, weapons=[], message=error)
    lines = ['=========================WEAPON SYSTEMS STATUS=========================',
             '[##] -------- Weapon Name -------- || Location -------- || Status -----']
    for line in lines:notify_actor(unit,actor,line)
    def emit(line):
        lines.append(line)
        notify_actor(unit,actor,line)
    rows = weapon_status(unit, emit=emit)
    return dict(accepted=True, weapons=rows, text='\n'.join(lines))
