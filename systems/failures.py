# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/failures.c
#   btech/mech.notify.c
#   btech/src/btech/failures.h

"""Equipment brands, failure tables and timed recovery from failures.c/.h."""
from dataclasses import dataclass
import random
from core.randomness import draw
from core.events import EventType
from entities.crittypes import is_weapon, weapon2i
from entities.weapon import get_weapon_by_index, WeaponType, WeaponFlags
from systems.enhanced_crits import set_part_temp_nuke
from systems.movement_commands import notify

BRANDS = (
    'Lords', 'Hesperus', 'Martell', 'Magna', 'Agra',
    'Luxor', 'SperryBrowning', 'Oriente', 'Deprus', 'Armstrong',
    'Coventry', 'Shannon', 'Bical', 'Holly', 'Telos',
    'Pynes', 'Hotshot', 'Firestorm', 'Purity', 'Ventra',
    'Dalban', 'Hartford', 'Garet', 'Ares', 'Tek',
    'Duoteck', 'CeresCom', 'Achernar', 'Tek', 'Iriad',
)
SUCCESS = (80, 90, 95, 100, 101) * 6


@dataclass(frozen=True)
class FailureResult:
    type: str = 'NONE'
    modifier: int = 0


@dataclass(frozen=True)
class FailureRow:
    message: str
    data: int
    callback: str
    temporary: int
    prerequisite: str


# Ordered source messages from failures.h, including warning colors.
ROWS = (
    FailureRow('%ch%crYour weapon fails to charge properly!%cn', 15, 'WeaponDamage', 0, '0'),
    FailureRow('%ch%crYour weapon fails to charge properly!%cn', 30, 'WeaponDamage', 0, '0'),
    FailureRow('%ch%crYour weapon fails to charge properly!%cn', 45, 'WeaponDamage', 0, '0'),
    FailureRow("%ch%crFailure in the weapon's cooling system ; too much heat produced!%cn", 30, 'WeaponHeat', 0, 'REQ_HEAT'),
    FailureRow('%ch%crOdd energy reading from the weapon ; It seems to have gone offline!%cn', 0, 'WeaponSpike', 2, '0'),
    FailureRow('%ch%crWeapon melts down!%cn', 0, 'WeaponSpike', 2, '0'),
    FailureRow('%ch%crRound misfires! .. and spirals off!%cn', 0, 'WeaponDud', 0, '0'),
    FailureRow('%ch%crRound not fired!  Dud!%cn', 0, 'WeaponDud', 3, '0'),
    FailureRow('%ch%crWeapon JAMS... clearing!%cn', 0, 'WeaponJammed', 1, '0'),
    FailureRow("%ch%crFailure in the weapon's cooling system, too much heat produced!%cn", 20, 'WeaponHeat', 0, 'REQ_HEAT'),
    FailureRow("%ch%crFailure in the weapon's cooling system, too much heat produced!%cn", 40, 'WeaponHeat', 0, 'REQ_HEAT'),
    FailureRow('%ch%crRound not fired!  STUCK in chamber!%cn', 0, 'WeaponDud', 3, '0'),
    FailureRow('%ch%crRack jams, attemping to clear!%cn', 0, 'WeaponJammed', 1, '0'),
    FailureRow('%ch%crSome of your missiles veer off course!%cn', 20, 'WeaponMissiles', 0, '0'),
    FailureRow('%ch%crSome of your missiles veer off course!%cn', 40, 'WeaponMissiles', 0, '0'),
    FailureRow('%ch%crGuidance Failure!  All missile veer off course!%cn', 100, 'WeaponMissiles', 0, '0'),
    FailureRow('%ch%crWeapon power spikes.. attempting to restart!%cn', 0, 'WeaponSpike', 2, '0'),
    FailureRow('%ch%crWeapon power spikes.. Electronics fused!!%cn', 0, 'WeaponSpike', 2, '0'),
    FailureRow('%ch%crGel line clogs, sending pressure through it now!%cn', 0, 'WeaponJammed', 1, '0'),
    FailureRow('%ch%crElectric ignition shorts out! Restarting!%cn', 0, 'WeaponSpike', 2, '0'),
    FailureRow('%ch%crFuel leaks on the chassis and ignites!%cn', 100, 'WeaponHeat', 0, '0'),
    FailureRow('%ch%crFuel at critical point!! Shutting down weapon to vent heat!%cn', 0, 'WeaponSpike', 2, '0'),
    FailureRow('%ch%crEjection nozzle gums up!  Please wait while pressure is applied!%cn', 0, 'WeaponJammed', 1, '0'),
    FailureRow('%ch%crFuel canisters explode!  No fuel left to burn!%cn', 0, 'WeaponSpike', 4, '0'),
    FailureRow('%ch%crComputer Glitch!  Target lost, please reacquire!%cn', 0, 'ComputerTarget', 0, 'REQ_TARGET'),
    FailureRow('%ch%crTactical shorts out! Fixing .. Please stand by.%cn', 1, 'ComputerScanner', 0, 'REQ_TAC'),
    FailureRow('%ch%crLong Range Sensors short out! .. Fixing .. Please stand by.%cn', 2, 'ComputerScanner', 0, 'REQ_LRS'),
    FailureRow('%ch%crScanners short out! Fixing .. Please stand by.%cn', 4, 'ComputerScanner', 0, 'REQ_SCANNERS'),
    FailureRow('%ch%crA sudden *SNAP* echos in your cockpit then all your displays die!%cn', 7, 'ComputerScanner', 0, 'REQ_SCANNERS'),
    FailureRow('%ch%crYou hear a loud *SNAP* *CRACKLE* and then everything powers down!%cn', 0, 'ComputerShutdown', 0, 'REQ_COMPUTER'),
    FailureRow('none', 50, 'RadioStatic', 0, '0'),
    FailureRow('none', 70, 'RadioStatic', 0, '0'),
    FailureRow('%ch%crYour readouts register a power loss in your radio!%cn', 15, 'RadioRange', 0, 'REQ_RADIO'),
    FailureRow('%ch%crYour readouts register a power loss in your radio!%cn', 30, 'RadioRange', 0, 'REQ_RADIO'),
    FailureRow('%ch%crYour radio suddenly shorts out! Please wait for backup to come online!%cn', 0, 'RadioShort', 0, 'REQ_RADIO'),
    FailureRow('%ch%crYour entire radio system suddenly shorts out!%cn', 0, 'RadioShort', 0, 'REQ_RADIO'),
)


def number(consumer, low, high):
    return draw('failure_' + consumer, low, high, lambda: random.randint(low, high))


def get_brand_index(part_type):
    if part_type in (-1, -2):
        return 24 if part_type == -1 else 30
    if not is_weapon(part_type):
        return -1
    weapon = get_weapon_by_index(weapon2i(part_type))
    if weapon is None or weapon.special & (WeaponFlags.PC_IMPA | WeaponFlags.PC_SHAR | WeaponFlags.PC_HEAT):
        return -1
    if 'Flamer' in weapon.name:
        return 18
    return {WeaponType.TBEAM: 0, WeaponType.TAMMO: 6, WeaponType.TMISSILE: 12}.get(weapon.weapon_type, -1)


def get_part_brand_name(part_type, level):
    category = get_brand_index(part_type)
    if not level or category < 0:
        return None
    index = category * 5 // 6 + level - 1
    return BRANDS[index] if 0 <= index < len(BRANDS) else None


def radio_recovery(event):
    unit, value = event.data, event.data2
    unit.radio_range += value
    if not unit.is_destroyed and value == unit.radio_range:
        notify(unit, 'Your radio is now operational again.')


def scanner_recovery(event):
    unit, value = event.data, event.data2
    kind = value // 256
    if kind in (0, 1, 2):
        field, label = (('tac_range', 'tactical scanners'), ('lrs_range', 'long-range scanners'), ('scan_range', 'scanners'))[kind]
        setattr(unit, field, value)
        if not unit.is_destroyed:
            notify(unit, f'Your {label} are operational again.')


def schedule_recovery(unit, callback, value):
    engine = unit._engine
    if engine is None:
        raise ValueError('equipment recovery requires the owning event engine')
    upper = number('recovery_upper', 40, 200)
    delay = number('recovery_delay', 30, upper)
    engine.events.schedule(delay, EventType.MRECOVERY, callback, unit, value)


def prerequisite_met(unit, prerequisite, weapon=None):
    if prerequisite == 'REQ_HEAT':
        return bool(weapon.heat)
    if prerequisite == 'REQ_TARGET':
        return unit.target > 0
    if prerequisite == 'REQ_TAC':
        return unit.tac_range != 0
    if prerequisite == 'REQ_LRS':
        return unit.lrs_range != 0
    if prerequisite == 'REQ_SCANNERS':
        return all((unit.tac_range, unit.lrs_range, unit.scan_range))
    if prerequisite == 'REQ_RADIO':
        return unit.radio_range != 0
    return True


def apply_failure(unit, category, outcome, section=None, critical=None):
    """Apply a selected table row; selection/prerequisites remain production rules."""
    if category not in (0, 6, 12, 18, 24, 30) or not 1 <= outcome <= 6:
        raise ValueError('invalid failure table coordinates')
    row = ROWS[category + outcome - 1]
    slot = unit.sections[section].criticals[critical] if section is not None else None
    weapon = get_weapon_by_index(weapon2i(slot.type)) if slot is not None else None
    if not prerequisite_met(unit, row.prerequisite, weapon):
        return FailureResult()
    if row.message != 'none':
        notify(unit, row.message)
    action = row.callback
    if action.startswith('Radio'):
        from systems.damage import external_effect
        external_effect(unit, 'mech.notify.c radio transmission', 'deliver radio failure to recipients')
    if action == 'RadioStatic':
        return FailureResult('STATIC', row.data)
    if action in ('RadioShort', 'RadioRange'):
        amount = unit.radio_range if action == 'RadioShort' else min(unit.radio_range - 1, row.data)
        schedule_recovery(unit, radio_recovery, amount)
        unit.radio_range -= amount
    elif action == 'ComputerTarget':
        unit.target = -1
    elif action == 'ComputerShutdown':
        if unit.is_started:
            from systems.startup import shutdown
            ok, message = shutdown(unit._engine, unit, caller=unit)
            if not ok and message and not getattr(message, 'notified', False):
                from core.effects import notify_actor
                notify_actor(unit, unit, message)
    elif action == 'ComputerScanner':
        for mask, field, offset in ((1, 'tac_range', 0), (2, 'lrs_range', 256), (4, 'scan_range', 512)):
            if row.data & mask:
                schedule_recovery(unit, scanner_recovery, getattr(unit, field) + offset)
                setattr(unit, field, 0)
    elif action == 'WeaponMissiles':
        set_part_temp_nuke(slot, row.temporary)
        return FailureResult('CRAZY_MISSILES', row.data)
    elif action in ('WeaponDamage', 'WeaponHeat', 'WeaponRange'):
        return percentage_failure(weapon, action[6:].upper(), row.data)
    elif action == 'WeaponDud':
        from core.game_loop import update_recycling
        if row.temporary == 0:
            if unit._engine is not None:update_recycling(unit._engine,unit)
            slot.data = weapon.vrt
            return FailureResult()
        set_part_temp_nuke(slot, 5 if outcome == 6 else row.temporary)
        if unit._engine is not None:update_recycling(unit._engine,unit)
        slot.data = 30 + number('dud_recycle', 1, 60)
        return FailureResult('WEAPON_DUD')
    elif action in ('WeaponJammed', 'WeaponSpike'):
        set_part_temp_nuke(slot, 5 if action == 'WeaponSpike' and outcome == 6 else row.temporary)
        if action != 'WeaponSpike' or outcome != 6:
            from core.game_loop import update_recycling
            if unit._engine is not None:update_recycling(unit._engine,unit)
            slot.data = number('weapon_recycle', 20, 40)
        return FailureResult('POWER_SPIKE' if action == 'WeaponSpike' else 'WEAPON_JAMMED')
    return FailureResult()


def failure_weapon_range(weapon, unit=None, section=4):
    """EGunRangeWithCheck, including the source default extended-range switch."""
    from entities.mech import MoveType
    extended = getattr(getattr(unit, '_engine', None), 'erange', 1)
    underwater = unit is not None and unit.z < 0 and (
        unit.z < -1 or unit.is_fallen or section in (5, 6) or
        unit.move_type == MoveType.QUAD and section in (0, 1))
    if underwater:
        base = next((n for n in (weapon.range_long_water, weapon.range_medium_water,
                                weapon.range_short_water) if n > 0), 0)
        return max(base, weapon.range_medium_water * 2) if extended and weapon.range_long_water > 0 else base
    base = weapon.range_long * (20 if weapon.weapon_type == WeaponType.TARTILLERY else 1)
    return max(base, weapon.range_medium * 2) if extended else base


def percentage_failure(weapon, kind, percentage, unit=None, section=4):
    base = {'DAMAGE': weapon.damage, 'HEAT': weapon.heat,
            'RANGE': failure_weapon_range(weapon, unit, section)}[kind]
    return FailureResult(kind, int(base * percentage / 100))


def parts_enabled(unit):
    return getattr(unit._engine, 'parts', 1)


def select_failure(category, level, generic):
    chance = number('generic_chance' if generic else 'weapon_chance', 1, 5000 if generic else 10)
    if (generic and chance != 42) or (not generic and chance < 9):
        return None
    level = level or 5
    index = int((category + level - 1) * 5 / 6)
    if not 0 <= index < len(SUCCESS):return None  # Undefined C table access.
    if number('reliability', 1, 100) <= SUCCESS[index]:
        return None
    outcome = number('outcome', 1, 6)
    return number('outcome', 1, 6) if outcome == 6 else outcome


def check_generic_fail(unit, part_type):
    category = get_brand_index(part_type)
    if category < 0 or not parts_enabled(unit):
        return FailureResult()
    level = unit.computer if part_type == -1 else unit.radio
    outcome = select_failure(category, level, True)
    return apply_failure(unit, category, outcome) if outcome else FailureResult()


def check_weapon_failed(unit, section, critical):
    slot = unit.sections[section].criticals[critical]
    category = get_brand_index(slot.type)
    if category < 0 or not parts_enabled(unit):
        return FailureResult()
    outcome = select_failure(category, slot.brand & 15, False)
    return apply_failure(unit, category, outcome, section, critical) if outcome else FailureResult()
