# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/hudinfo.c
#   btech/mech.tech.c
#   btech/mech.tech.commands.c
#   btech/mech.utils.c
# Historical Aerospace sources:
#   btech/mech.utils.c

"""Weapon enumeration and condition from authoritative critical slots."""
from dataclasses import dataclass
from entities.crittypes import is_weapon, weapon2i
from entities.mech import FireMode as F, UnitType as U, WeaponState, NUM_CRITICALS
from entities.weapon import get_weapon_by_index


@dataclass(frozen=True)
class WeaponRun:
    weapon_idx: int
    section: int
    critical: int
    data: int


def weapon_crits(unit, index):
    if unit.unit_type != U.MECH:
        return 1
    weapon = get_weapon_by_index(index)
    if weapon is None:
        raise ValueError(f'Unsupported weapon catalog index: {index}')
    return weapon.crits if unit.unit_type == U.MECH else 1


def find_weapons(unit, section, *, whine=True, silence=False):
    """FindWeapons_Advanced: None denotes a malformed section (-1 in C)."""
    runs, count, required, previous = [], 0, 0, -1

    def valid():
        if count and count != required and required < 9:
            if whine and not silence:
                message = (f'Error in the numcriticals for weapon on #{unit._id}! '
                           f'(Should be: {required}, is: {count})')
                from core.effects import send_error
                send_error(unit, message)
            return False
        return True

    for pos, slot in enumerate(unit.sections[section].criticals[:NUM_CRITICALS]):
        if not is_weapon(slot.type):
            if not valid(): return None
            count = 0
            continue
        index = weapon2i(slot.type)
        if not runs or not count or index != previous or count == weapon_crits(unit, index):
            if not valid(): return None
            runs.append(WeaponRun(index, section, pos, slot.data))
            previous, required, count = index, weapon_crits(unit, index), 1
        else:
            count += 1
    return runs if valid() else None


def weapon_runs(unit, *, whine=True):
    return [run for loc in range(len(unit.sections))
            for run in (find_weapons(unit, loc, whine=whine) or [])]


def numbered_weapon(unit, number):
    if number < 0:
        return None
    for loc in range(len(unit.sections)):
        runs = find_weapons(unit, loc) or []
        if number < len(runs):
            return runs[number]
        number -= len(runs)
    return None


def find_weapon_index(unit, number):
    run = numbered_weapon(unit, number)
    return run.weapon_idx if run is not None else -1


def find_weapon_from_index(unit, index):
    from systems.combat import part_is_nonfunctional
    last = (-1, -1)
    for loc in range(len(unit.sections)):
        for ordinal, run in enumerate(find_weapons(unit, loc) or []):
            if run.weapon_idx != index: continue
            last = (loc, run.critical)
            slot = unit.sections[loc].criticals[ordinal]
            # The source tests the run ordinal here, not its first critical.
            recycling = slot.data > 0 and is_weapon(slot.type) and not unit.is_section_destroyed(loc)
            if not part_is_nonfunctional(unit, loc, ordinal) and not recycling:
                return (True, *last)
    return (False, *last)


def weapon_is_nonfunctional(unit, section, critical, size=0):
    from systems.enhanced_crits import _iter_run_flags
    if size <= 0:
        size = weapon_crits(unit, weapon2i(unit.sections[section].criticals[critical].type))
    destroyed = disabled = 0
    for slot in _iter_run_flags(unit, section, critical, size):
        if slot.firemode & F.DESTROYED_MODE: destroyed += 1
        elif slot.firemode & F.DISABLED_MODE: disabled += 1
    if disabled: return 1
    if size == 1 and destroyed or size > 1 and destroyed >= size // 2: return 2
    return -destroyed


def sync_weapon_states(unit):
    """Refresh the runtime mirrors, retaining state only for the same mount."""
    old = {(w.section, w.critical, w.weapon_idx): w for w in unit.weapons}
    unit.weapons[:] = [old.get((r.section, r.critical, r.weapon_idx)) or
                      WeaponState(section=r.section, critical=r.critical, weapon_idx=r.weapon_idx)
                      for r in weapon_runs(unit)]
    return unit.weapons
