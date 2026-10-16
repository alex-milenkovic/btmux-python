# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.ammodump.c
#   btech/mech.utils.c
#   btech/src/btech/weapons.h

"""Ammunition dumping command, phased callbacks and single-round stream ignition."""

import random
from dataclasses import dataclass
from core.events import EventType
from core.randomness import draw
from entities.crittypes import is_ammo, ammo2weapon_i, crits_in_loc
from entities.mech import UnitType, Location, VehicleLocation
from entities.weapon import get_weapon_by_index, WeaponType
from systems.combat import part_is_nonfunctional
from systems.heat_control import common_checks
from systems.movement_commands import c_number, notify
from systems.notifications import mech_printf, MECHALL
from systems.parts import armor_string
from systems.sensors import los_broadcast


@dataclass(frozen=True)
class DumpSelection:
    kind: str
    location: int = -1
    slot: int = -1
    weapon: int = -1


def sync_dump_state(unit):
    """Rebuild mirrors from the events that survive a template reset."""
    engine=getattr(unit,'_engine',None)
    events=engine.events.pending_events(EventType.DUMP,unit) if engine is not None else []
    unit._dump_event=events[0] if events else None
    unit._dump_selection=events[0].data2 if events else None
    unit.dumping=bool(events)


def stop_dump(unit):
    engine=getattr(unit,'_engine',None)
    if engine is not None:engine.events.cancel_by_type_and_data(EventType.DUMP,unit)
    event = getattr(unit, "_dump_event", None)
    if event is not None:
        event.cancel()
    unit._dump_event = None
    unit._dump_selection = None
    unit.dumping = False


def bins(unit, selection):
    """Selection order shared by callbacks and ignition; filtering differs below."""
    if selection.kind == "bin":
        yield selection.location, selection.slot
    elif selection.kind == "location":
        for pos in range(crits_in_loc(unit, selection.location)):
            yield selection.location, pos
    else:
        last = 7 if unit.unit_type == UnitType.MECH else 5
        for loc in range(min(last, len(unit.sections) - 1), -1, -1):
            for pos in range(crits_in_loc(unit, loc) - 1, -1, -1):
                slot = unit.sections[loc].criticals[pos]
                if is_ammo(slot.type) and (
                    selection.kind == "all"
                    or ammo2weapon_i(slot.type) == selection.weapon
                ):
                    yield loc, pos


def eligible(unit, loc, pos, functional=True, nonempty=True):
    slot = unit.sections[loc].criticals[pos]
    return (
        is_ammo(slot.type)
        and (not nonempty or slot.data > 0)
        and (not functional or not part_is_nonfunctional(unit, loc, pos))
    )


def parse_selection(unit, text):
    args = text.split()[:2]
    name = args[0]
    if name.lower() == "all":
        return DumpSelection("all")
    number = c_number(name, True)
    if number or name == "0":
        return weapon_selection(unit, number)
    return section_selection(unit, args)


def weapon_selection(unit, number):
    from systems.weapon_inventory import find_weapon_index
    index = find_weapon_index(unit, number)
    if index < 0:
        raise ValueError('Invalid weapon number!')
    weapon = get_weapon_by_index(index)
    if weapon.weapon_type in (WeaponType.TBEAM, WeaponType.THAND):
        raise ValueError("That weapon doesn't use ammunition!")
    return DumpSelection('weapon', weapon=index)


def section_selection(unit, args):
    from systems.damage_commands import armor_section_from_string
    loc = armor_section_from_string(unit, args[0])
    if loc < 0:
        raise ValueError('Invalid location or weapon number!')
    if len(args) > 1 and 1 <= c_number(args[1], True) <= 12:
        return DumpSelection('bin', location=loc, slot=c_number(args[1], True)-1)
    return DumpSelection('location', location=loc)


def mech_dump(engine, unit, text, caller=None):
    error = common_checks(unit, caller, started=True, mapped=True)
    if error:
        return False, error
    if not text.split():
        return False, "Not enough arguments to the function"
    if unit.is_jumping:
        return False, "You can't dump ammo while jumping!"
    from systems.heat import is_running
    from physics.cargo import cargo_max_speed

    if is_running(unit.desired_speed, cargo_max_speed(unit)):
        return False, "You can't dump ammo while running!"
    name = text.split()[0].lower()
    if name == "stop":
        if not unit.dumping:
            return False, "You aren't dumping anything!"
        message = notify(unit, "Ammo dumping halted.")
        stop_dump(unit)
        los_broadcast(unit, "no longer has ammo dumping from hatches on its back.")
        return True, message
    number = c_number(text.split()[0], True)
    if number < 0:
        from core.effects import send_error
        actor = caller if caller is not None else unit.pilot
        send_error(unit, f"CHEATER: #{getattr(actor, '_id', actor)} tried to crash mux with command 'dump {number}'!")
    if unit.dumping and name != "all":
        return False, "You're already dumping some ammo!"
    try:
        selection = parse_selection(unit, text)
    except ValueError as error:
        return False, str(error)
    available = any(
        eligible(unit, loc, pos, functional=selection.kind != "all")
        for loc, pos in bins(unit, selection)
    )
    if selection.kind == 'weapon':
        from systems.combat import find_ammo_for_weapon
        found = find_ammo_for_weapon(unit, selection.weapon, -1, start=0)
        if found is None:
            return False, "You don't have any ammunition for that weapon stored on this mech!"
        if unit.sections[found[0]].criticals[found[1]].data == 0:
            return False, 'You are out of ammunition for that weapon already!'
    elif not available:
        if selection.kind == 'bin':
            return False, f'There is no ammunition in {armor_string(unit, selection.location)} crit {selection.slot+1}!'
        if selection.kind == 'location':
            return False, f'There is no ammunition in {armor_string(unit, selection.location)}!'
        return False, 'You have no ammo to dump!'
    if unit.dumping and unit._dump_selection.kind == 'all':
        return False, "You're already dumping your ammo!"
    if selection.kind == 'all':
        stop_dump(unit)
        message = 'Starting dumping of all ammunition..'
        notify(unit, message)
    else:
        if selection.kind == 'weapon':
            message = f'Starting dumping {get_weapon_by_index(selection.weapon).name[3:]} ammunition..'
        elif selection.kind == 'bin':
            message = f'Starting dumping of ammunition in {armor_string(unit, selection.location)} crit {selection.slot+1}..'
        else:
            message = f'Starting dumping of ammunition in {armor_string(unit, selection.location)}..'
        mech_printf(unit, MECHALL, '%s', message)
    los_broadcast(unit, 'starts dumping ammo from hatches on its back.')
    unit._engine = engine
    unit._dump_selection = selection
    arm_dump(unit)
    return True, message


def arm_dump(unit,selection=None):
    if selection is not None:unit._dump_selection=selection
    unit.dumping = True
    unit._dump_event = unit._engine.events.schedule(
        1, EventType.DUMP, mech_dump_event, unit, unit._dump_selection
    )


def ammo_expenditure_check(unit, weapon, offset):
    from systems.combat_ammunition import expenditure_check
    return expenditure_check(unit, weapon.index, offset)


def ammo_warning_levels(unit, weapon):
    entries = [
        slot
        for section in unit.sections
        for slot in section.criticals
        if is_ammo(slot.type) and ammo2weapon_i(slot.type) == weapon.index
    ]
    count = sum(slot.data for slot in entries)
    from entities.mech import FireMode, AmmoMode

    slots = 0
    for entry in entries:
        modifier = (
            1
            if entry.firemode & FireMode.HALFTON_MODE
            or entry.ammomode & (AmmoMode.AC_AP_MODE | AmmoMode.AC_PRECISION_MODE)
            else 0.5 if entry.ammomode & AmmoMode.AC_CASELESS_MODE else 2
        )
        slots = int(slots + modifier)  # C compound assignment into an int.
    threshold = max(3, min(30, slots * weapon.ammo_per_ton // 8))
    return count, threshold


def dump_decrease(unit, loc, pos, tick):
    if not eligible(unit, loc, pos):
        return 0
    slot = unit.sections[loc].criticals[pos]
    weapon = get_weapon_by_index(ammo2weapon_i(slot.type))
    if weapon is None or weapon.ammo_per_ton <= 0:
        raise ValueError(
            "Ammo bin requires a positive rounds-per-ton weapon definition"
        )
    rate = weapon.ammo_per_ton
    if rate < 30 and tick % (30 // rate):
        return 2
    removed = 1 if rate < 30 else min(slot.data, rate // 30)
    ammo_expenditure_check(unit, weapon, removed - 1)
    slot.data -= removed
    return 2 if slot.data else 1


def mech_dump_event(event):
    unit = event.data
    unit._dump_event = None
    unit.dumping = False
    if not unit.is_started:
        unit._dump_selection = None
        return
    selection = event.data2
    work = max(
        (
            dump_decrease(unit, l, p, unit._engine.tick)
            for l, p in bins(unit, selection)
        ),
        default=0,
    )
    if work > 1:
        arm_dump(unit,selection)
        return
    unit._dump_selection = None
    if selection.kind == "location" and not work:
        return
    if selection.kind == "all":
        message = "All ammunition dumped."
    elif selection.kind == "weapon":
        message = f"Ammunition for {get_weapon_by_index(selection.weapon).name[3:]} dumped!"
    elif selection.kind == "bin":
        message = f"Ammunition in {armor_string(unit, selection.location)} crit {selection.slot+1} dumped!"
    else:
        message = f"All ammunition in {armor_string(unit, selection.location)} dumped."
    if selection.kind == "all":
        notify(unit, message)
    else:
        mech_printf(unit, MECHALL, '%s', message)
    los_broadcast(unit, "no longer has ammo dumping from hatches on its back.")


def blow_dumping_ammo(unit, attacker, location):
    # Damage transfer/destruction can cancel DUMP without updating its mirrors.
    sync_dump_state(unit)
    selection = getattr(unit, "_dump_selection", None)
    if not unit.dumping or selection is None:
        return 0
    candidates = []
    for loc, pos in bins(unit, selection):
        if selection.kind == "bin" or eligible(
            unit,
            loc,
            pos,
            functional=selection.kind == "location",
            nonempty=selection.kind != "weapon",
        ):
            candidates.append((loc, pos))
    if not candidates:
        return 0
    index = draw(
        "dump_candidates",
        0,
        len(candidates) - 1,
        lambda: random.randrange(len(candidates)),
    )
    loc, pos = candidates[index]
    slot = unit.sections[loc].criticals[pos]
    damage = find_max_ammo_damage(get_weapon_by_index(ammo2weapon_i(slot.type)))
    if damage > 0:
        from systems.combat import apply_damage_with_transfer

        los_broadcast(unit, "'s rear armor lights up as ammo being dumped ignites!")
        mech_printf(unit, MECHALL, '%%ch%%crSome of the %s ammo dumping out of your mech ignites!%%cn', get_weapon_by_index(ammo2weapon_i(slot.type)).name[3:])
        apply_damage_with_transfer(
            unit, location, damage, True, attacker, engine=unit._engine,
            ignore_swarmers=True, cause=-1, attack_pilot=-1, los=1
        )
        if slot.data > 0:
            slot.data -= 1
        notify(unit, "%ch%crAll ammo dumping operations have stopped!%cn")
        stop_dump(unit)
    return damage


def rear_hit(unit, attacker, location, is_rear, weapon):
    if (
        weapon is not None
        and unit.unit_type == UnitType.MECH
        and is_rear
        and location in (Location.CTORSO, Location.LTORSO, Location.RTORSO)
    ):
        return blow_dumping_ammo(unit, attacker, location)
    return 0


# weapons.h:MissileHitTable keyed by catalog identity; an unmatched weapon
# keeps its base damage even if its rack size resembles a listed weapon.
AMMO_FULL_SALVO = {
    "CL.LB10-XAC": 10,
    "CL.LB20-XAC": 20,
    "CL.LB2-XAC": 2,
    "CL.LB5-XAC": 5,
    "CL.LRM-10": 10,
    "CL.LRM-15": 15,
    "CL.LRM-20": 20,
    "CL.StreakLRM-5": 5,
    "CL.StreakLRM-10": 10,
    "CL.StreakLRM-15": 15,
    "CL.StreakLRM-20": 20,
    "CL.LRM-5": 5,
    "CL.SRM-2": 2,
    "CL.SRM-4": 4,
    "CL.SRM-6": 6,
    "CL.StreakSRM-2": 2,
    "CL.StreakSRM-4": 4,
    "CL.StreakSRM-6": 6,
    "CL.ATM-3": 3,
    "CL.ATM-6": 6,
    "CL.ATM-9": 9,
    "CL.ATM-12": 12,
    "CL.UltraAC/10": 2,
    "CL.UltraAC/20": 2,
    "CL.UltraAC/2": 2,
    "CL.UltraAC/5": 2,
    "CL.AC/2": 2,
    "CL.AC/5": 2,
    "CL.AC/10": 2,
    "CL.AC/20": 2,
    "IS.LRM-5": 5,
    "IS.LRM-10": 10,
    "IS.LRM-15": 15,
    "IS.LRM-20": 20,
    "IS.SRM-2": 2,
    "IS.SRM-4": 4,
    "IS.SRM-6": 6,
    "IS.StreakSRM-2": 2,
    "IS.StreakSRM-4": 4,
    "IS.StreakSRM-6": 6,
    "IS.LB20-XAC": 20,
    "IS.LB10-XAC": 10,
    "IS.LB2-XAC": 2,
    "IS.LB5-XAC": 5,
    "IS.UltraAC/20": 2,
    "IS.UltraAC/10": 2,
    "IS.UltraAC/5": 2,
    "IS.UltraAC/2": 2,
    "IS.AC/2": 2,
    "IS.AC/5": 2,
    "IS.AC/10": 2,
    "IS.AC/20": 2,
    "IS.LightAC/2": 2,
    "IS.LightAC/5": 2,
    "IS.Thunderbolt-5": 1,
    "IS.Thunderbolt-10": 1,
    "IS.Thunderbolt-15": 1,
    "IS.Thunderbolt-20": 1,
    "IS.ELRM-10": 10,
    "IS.ELRM-5": 5,
    "IS.ELRM-15": 15,
    "IS.ELRM-20": 20,
    "IS.LR_DFM-10": 10,
    "IS.LR_DFM-5": 5,
    "IS.LR_DFM-15": 15,
    "IS.LR_DFM-20": 20,
    "IS.SR_DFM-2": 2,
    "IS.SR_DFM-4": 4,
    "IS.SR_DFM-6": 6,
    "IS.NarcBeacon": 1,
    "CL.NarcBeacon": 1,
    "IS.MRM-10": 10,
    "IS.MRM-20": 20,
    "IS.MRM-30": 30,
    "IS.MRM-40": 40,
    "IS.iNarcBeacon": 1,
    "IS.RL-10": 10,
    "IS.RL-15": 15,
    "IS.RL-20": 20,
    "IS.InfantrySRM": 1,
    "IS.InfantryLRM": 1,
}


def ammo_full_salvo(weapon):
    if weapon.weapon_type in (WeaponType.TMISSILE, WeaponType.TARTILLERY):
        salvo = getattr(weapon, "ammo_full_salvo", AMMO_FULL_SALVO.get(weapon.name))
        if salvo is not None:
            return salvo
    return 1


def find_max_ammo_damage(weapon):
    return weapon.damage * ammo_full_salvo(weapon)
