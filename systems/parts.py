# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/econ_cmds.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   btech/template.c
# Historical Aerospace sources:
#   btech/aero.bomb.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.h

"""Shared part quantities, source labels, and current-unit inventory reports."""
from entities.crittypes import (Special, is_weapon, is_ammo, is_special, is_bomb, is_cargo,
                               weapon2i, ammo2weapon_i, special2i, i2special, CARGO_BASE_INDEX, BOMB_BASE_INDEX)
from entities.mech import UnitType as U, MoveType as M, Location as L, FireMode as F, SectionConfig as C, Specials as S
from entities.weapon import get_weapon_by_index, WeaponType as T, WeaponFlags as W
from entities.part_catalog import INTERNALS, CARGO, INTERNALSWEIGHT, CARGOWEIGHT, BOMBS
from core.randomness import float32 as f32
from physics.hexmath import signed_remainder


def rounded_weight(weight, increment):
    over = signed_remainder(weight, increment)
    return weight - over if over < 2 else weight + increment - over


def round_to_halfton(weight): return rounded_weight(weight, 512)
def round_to_quarterton(weight): return rounded_weight(weight, 256)
def armorpoints(unit): return sum(s.armor + s.rear for s in unit.sections)
def intpoints(unit): return sum(s.internal for s in unit.sections)
def heatsinks_in_engine(unit): return int(unit.engine_size() / 25)


def remaining_percent(original, remaining):
    return int(f32(f32(f32(remaining) / f32(original)) * 100)) if original else 0


def remaining_internal_percent(unit):
    return remaining_percent(sum(s.internal_orig for s in unit.sections), intpoints(unit))


def remaining_armor_percent(unit):
    return remaining_percent(sum(s.armor_orig + s.rear_orig for s in unit.sections), armorpoints(unit))


def source_text(text):
    """Supported C-locale text: ASCII bytes, terminated by the first NUL."""
    if not isinstance(text, str) or not text.isascii():
        raise ValueError('Unsupported source text: ASCII string required')
    return text.split('\0', 1)[0]


def mech_ids(unit, lower=False):
    result = source_text(unit.contact_id)[:2] if unit is not None else '**'
    return result.lower() if lower else result


def my_to_upper(text):
    text = source_text(text)
    return text[:1].upper() + text[1:]


def mechtypename(unit):
    names = ('mech', 'tank', 'VTOL', 'vessel', 'aerofighter', 'DropShip')
    # The C array has only six initialized elements in a CLASS_LAST+1 array.
    return names[unit.unit_type] if 0 <= unit.unit_type < len(names) else None


def section_strings(unit):
    from systems.damage_commands import section_names
    return section_names(unit)


def armor_string(unit, index):
    names = section_strings(unit)
    if names is None: return 'Invalid!!'
    high = 5 if unit.unit_type in (U.VEH_GROUND, U.VEH_NAVAL) else len(names)
    return names[index] if 0 <= index < high else 'Invalid!!'


def listmatch(values, text):
    return next((i for i, value in enumerate(values) if value.lower() == text.lower()), -1)


def is_leg_destroyed(unit, loc):
    return unit.is_section_destroyed(loc) or bool(unit.sections[loc].config & (C.SECTION_BREACHED | C.SECTION_FLOODED))


def count_destroyed_legs(unit):
    if unit.unit_type != U.MECH: return 0
    locations = [L.LLEG, L.RLEG] + ([L.LARM, L.RARM] if unit.move_type == M.QUAD else [])
    return sum(is_leg_destroyed(unit, loc) for loc in locations)


def is_mech_legless(unit):
    return unit.unit_type == U.MECH and count_destroyed_legs(unit) >= (4 if unit.move_type == M.QUAD else 2)


def reverse_split_crit_loc(unit, loc, pos):
    if unit.unit_type != U.MECH: return -1
    if loc == L.CTORSO:
        return L.RTORSO if unit.sections[loc].criticals[pos].type == i2special(Special.SPLIT_CRIT_RIGHT) else L.LTORSO
    return {L.LARM: L.LTORSO, L.LLEG: L.LTORSO, L.RARM: L.RTORSO,
            L.RLEG: L.RTORSO, L.LTORSO: L.LARM, L.RTORSO: L.RARM}.get(loc, -1)


def check_section_for_special(unit, special, loc):
    return not unit.is_section_destroyed(loc) and bool(unit.sections[loc].specials & special)


def check_all_sections(unit, special):
    return any(check_section_for_special(unit, special, i) for i in range(len(unit.sections)))


def find_obj(unit, loc, kind, with_destroyed=False):
    from systems.combat import part_is_nonfunctional
    return sum(slot.type == kind and (with_destroyed or not part_is_nonfunctional(unit, loc, pos))
               for pos, slot in enumerate(unit.sections[loc].criticals))


def part_weight(part, tables=True):
    if is_weapon(part):
        weapon = get_weapon_by_index(weapon2i(part))
        if weapon is None: raise ValueError('Unsupported weapon weight')
        return int(10.24 * (weapon.tonnage * 100))
    if is_ammo(part): return 1024
    if is_bomb(part): return 102 * int(BOMBS[part - BOMB_BASE_INDEX].split('_')[0])
    if not tables:
        return 1024 if is_special(part) and part <= i2special(Special.CLAW) else 102
    if is_special(part): values, index = INTERNALSWEIGHT, special2i(part)
    elif is_cargo(part): values, index = CARGOWEIGHT, part - CARGO_BASE_INDEX
    else: return 102
    if not 0 <= index < len(values): raise ValueError('Part index exceeds source weight table')
    return values[index]


def part_name(part):
    if is_weapon(part) or is_ammo(part):
        weapon = get_weapon_by_index(weapon2i(part) if is_weapon(part) else ammo2weapon_i(part))
        if weapon is not None:
            if is_weapon(part): return weapon.name
            if weapon.weapon_type not in (T.TBEAM, T.THAND) and not weapon.special & (W.PC_IMPA | W.PC_SHAR | W.PC_HEAT):
                return 'Ammo_' + weapon.name
    elif is_bomb(part): return 'Bomb_' + BOMBS[part - BOMB_BASE_INDEX]
    elif is_special(part) and special2i(part) < len(INTERNALS): return INTERNALS[special2i(part)]
    elif is_cargo(part) and part - CARGO_BASE_INDEX < len(CARGO): return CARGO[part - CARGO_BASE_INDEX]
    return '#-1 INVALID PART NUMBER'


def payloadlist(unit):
    from systems.weapon_inventory import weapon_runs
    weapons, ammo = {}, {}
    for run in weapon_runs(unit):
        if unit.sections[run.section].criticals[run.critical].firemode & (F.BROKEN_MODE | F.DESTROYED_MODE): continue
        weapons[run.weapon_idx] = weapons.get(run.weapon_idx, 0) + 1
    for section in unit.sections:
        for slot in section.criticals:
            if is_ammo(slot.type) and not slot.firemode & F.DESTROYED_MODE:
                ammo[slot.type] = ammo.get(slot.type, 0) + 1
    entries=[f'{get_weapon_by_index(index).name}:{count}' for index,count in weapons.items()] + [f'{part_name(part)}:{count}' for part,count in ammo.items()]
    payload=b'|'.join(text.encode('utf-8')[:119] for text in entries)
    return payload[:2047].decode('utf-8',errors='ignore')


def engine_label(unit):
    for flag, name in ((S.LE_TECH, 'Light_Engine'), (S.CE_TECH, 'Compact_Engine'),
                       (S.XXL_TECH, 'XXL_Engine'), (S.XL_TECH, 'XL_Engine'), (S.ICE_TECH, 'ICE_Engine')):
        if unit.specials & flag: return name
    return 'Engine'


def partlist(unit):
    parts = {}
    excluded = {i2special(s) for s in (Special.ENDO_STEEL, Special.LT_FERRO_FIBROUS, Special.HVY_FERRO_FIBROUS, Special.FERRO_FIBROUS)}
    for section in unit.sections:
        for slot in section.criticals:
            if slot.firemode & F.DESTROYED_MODE or not slot.type or is_ammo(slot.type) or is_weapon(slot.type) or slot.type in excluded: continue
            parts[slot.type] = parts.get(slot.type, 0) + 1
    result, actuators = '', 0
    for ordinal, (part, count) in enumerate(parts.items()):
        if i2special(Special.SHOULDER_OR_HIP) <= part <= i2special(Special.HAND_OR_FOOT_ACTUATOR):
            actuators += count
            continue
        if part == i2special(Special.ENGINE): name = engine_label(unit)
        elif part == i2special(Special.GYRO):
            name = 'XL_Gyro' if unit.specials2 & 0x200000 else 'HeavyDuty_Gyro' if unit.specials2 & 0x400000 else 'Gyro'
        elif part == i2special(Special.HEAT_SINK):
            name = 'Compact_HeatSink' if unit.specials2 & 0x200 else 'Double_HeatSink' if unit.specials & (S.DOUBLE_HEAT_TECH | S.CLAN_TECH) else 'HeatSink'
        else: name = part_name(part)
        result += f'{name}:{count}' + ('|' if ordinal < len(parts) - 1 else '')
    return result + (f'|Actuator:{actuators}' if actuators else '')


def unit_parts_list(unit, mode=0):
    armor = next((name for bit, name in ((1, 'ST_ARMOR'), (2, 'HVY_FF_ARMOR'),
                 (0x4000, 'LT_FF_ARMOR'), (0x20000000, 'HD_ARMOR')) if unit.specials2 & bit),
                 'FF_ARMOR' if unit.specials & S.FF_TECH else 'ARMOR')
    internal = next((name for bit, name in ((S.REINFI_TECH, 'RE_INTERNALS'),
                    (S.COMPI_TECH, 'CO_INTERNALS'), (S.ES_TECH, 'ES_INTERNAL')) if unit.specials & bit), 'INTERNAL')
    return f'{armor}:{armorpoints(unit)}|{internal}:{intpoints(unit)}|{payloadlist(unit)}|{partlist(unit)}'


def heat_factor(unit):
    if unit.unit_type != U.MECH: return -1 if unit.specials & S.ICE_TECH else 21
    from systems.ecm import _has_working_ecm_suite
    if unit.status2 & (0x40 | 0x80) or _has_working_ecm_suite(unit): return -1
    plus, minus = f32(unit.plus_heat), f32(unit.minus_heat)
    return int(f32(plus + f32(2 * f32(plus - minus))))


def set_cargo_weight(unit):
    """SetCargoWeight with an in-memory ECONPARTS inventory adapter."""
    from systems.damage import external_effect
    pile = {}
    store=getattr(unit,'inventory_store',None)
    inventory = store.runtime_entries(unit._id) if store else getattr(unit, 'cargo_inventory', None)
    if inventory is None:
        external_effect(unit, 'persistent ECONPARTS inventory', 'SetCargoWeight')
        inventory = []
    for part, brand, count in inventory:
        pile[part] = pile.get(part, 0) + (4 if is_bomb(part) else 1) * count
    flying = unit.unit_type in (U.AERO, U.DS, U.SPHEROID_DS) or unit.move_type == M.VTOL
    if flying:
        for section in unit.sections:
            for slot in section.criticals:
                if is_bomb(slot.type) or slot.type == i2special(Special.FUELTANK):
                    pile[slot.type] = pile.get(slot.type, 0) + 1
    total = sum(part_weight(part, getattr(getattr(unit, '_engine', None), 'part_weights', True)) * count
                for part, count in pile.items() if count)
    if flying:
        original = getattr(unit, 'fuel_orig', 0)
        unit.fuel_max = original + 2000 * pile.get(i2special(Special.FUELTANK), 0)
        if unit.fuel > original: total += unit.fuel - original
    unit.carried_cargo = total
    from entities.mech import CritStatus
    unit.clear_crit_status(CritStatus.LOAD_OK)
    return total


def part_mod(unit, kind):
    if kind == i2special(Special.GYRO): value, div, bound = unit.engine_size(), 100, 3
    elif kind == i2special(Special.ENGINE): value, div, bound = unit.engine_size(), 20, 19
    else: value, div, bound = unit.tonnage, 10, 9
    over = signed_remainder(int(value), div)
    if over: value += div - over
    return max(0, min(bound, int(value / div) - 1))


def cargo_part(name):
    try: return CARGO_BASE_INDEX + CARGO.index(name)
    except ValueError: raise ValueError(f'Unsupported source cargo part: {name}') from None


# mech.h TON_*_FIRST values. template.c has an extra cargo name before these
# families; looking up their display names changes the material IDs C returns.
SIZED_MATERIAL_BASES = {
    'Sensors': 157, 'Myomer': 167, 'TripleMyomer': 177,
    'Internal': 187, 'ES_Internal': 197, 'JumpJet': 207,
    'UpperArmActuator': 217, 'LowerArmActuator': 227, 'HandActuator': 237,
    'UpperLegActuator': 247, 'LowerLegActuator': 257, 'FootActuator': 267,
    'Engine': 277, 'XL_Engine': 297, 'ICE_Engine': 317, 'Light_Engine': 337,
    'CO_Internal': 357, 'RE_Internal': 367, 'Gyro': 377, 'XL_Gyro': 381,
    'HD_Gyro': 385, 'Compact_Gyro': 389, 'XXL_Engine': 393,
    'Compact_Engine': 413,
}


def sized_material(name, modifier):
    return CARGO_BASE_INDEX + SIZED_MATERIAL_BASES[name] + modifier


def proper_armor(unit):
    name = ('FF_Armor' if unit.specials & S.FF_TECH else 'HD_Armor' if unit.specials & S.HARDA_TECH
            else 'STH_Armor' if unit.specials2 & 1 else 'HVY_FF_Armor' if unit.specials2 & 2
            else 'LT_FF_Armor' if unit.specials2 & 0x4000 else None if unit.infantry_specials & 8 else 'Armor')
    if name is None: return CARGO_BASE_INDEX + 41  # Source PURIFIER_ARMOR cargo offset.
    return cargo_part(name)


def complex_repair(unit, option):
    return getattr(getattr(unit, '_engine', None), 'complexrepair', False) if option is None else option


def proper_internal(unit, complexrepair=None):
    name = ('ES_Internal' if unit.specials & S.ES_TECH else 'RE_Internal' if unit.specials & S.REINFI_TECH
            else 'CO_Internal' if unit.specials & S.COMPI_TECH else 'Internal')
    if complex_repair(unit, complexrepair): return sized_material(name, part_mod(unit, 0))
    elif name in ('RE_Internal', 'CO_Internal'): name += 's'
    return cargo_part(name)


def proper_myomer(unit):
    return sized_material('TripleMyomer' if unit.specials & S.TRIPLE_MYOMER_TECH else 'Myomer', part_mod(unit, 0))


def alias_part(unit, part, loc, complexrepair=None):
    if not is_special(part): return part
    kind = special2i(part)
    complexrepair = complex_repair(unit, complexrepair)
    mod = part_mod(unit, part)
    if kind <= Special.HAND_OR_FOOT_ACTUATOR:
        if not complexrepair: return cargo_part('Actuator')
        limb = ('Leg' if loc in (L.LLEG, L.RLEG) or unit.move_type == M.QUAD and loc in (L.LARM, L.RARM)
                else 'Arm' if loc in (L.LARM, L.RARM) else None)
        if limb:
            name = ('Upper' + limb + 'Actuator' if kind in (Special.SHOULDER_OR_HIP, Special.UPPER_ACTUATOR)
                    else 'Lower' + limb + 'Actuator' if kind == Special.LOWER_ACTUATOR
                    else 'HandActuator' if limb == 'Arm' else 'FootActuator')
            return sized_material(name, mod)
    elif kind == Special.ENGINE:
        name = next((label for flag, label in ((S.XL_TECH, 'XL_Engine'), (S.ICE_TECH, 'ICE_Engine'),
                     (S.CE_TECH, 'Compact_Engine'), (S.XXL_TECH, 'XXL_Engine'), (S.LE_TECH, 'Light_Engine')) if unit.specials & flag), 'Engine')
        if complexrepair: return sized_material(name, mod)
        if name != 'Engine': return cargo_part(name)
    elif kind == Special.HEAT_SINK:
        if unit.specials & (S.DOUBLE_HEAT_TECH | S.CLAN_TECH): return cargo_part('Double_HeatSink')
        if unit.specials2 & 0x200: return cargo_part('Compact_HeatSink')
    elif kind == Special.GYRO:
        name = 'XL_Gyro' if unit.specials2 & 0x200000 else 'HD_Gyro' if unit.specials2 & 0x400000 else 'Compact_Gyro' if unit.specials2 & 0x800000 else 'Gyro'
        if complexrepair: return sized_material(name, mod)
        if name != 'Gyro': return cargo_part('HeavyDuty_Gyro' if name == 'HD_Gyro' else name)
    elif complexrepair and kind in (Special.SENSORS, Special.JUMP_JET):
        return sized_material('Sensors' if kind == Special.SENSORS else 'JumpJet', mod)
    return part


def update_specials(unit):
    """Template inventory's technology recomputation, shared by repair replay."""
    from collections import Counter
    from entities.crittypes import crits_in_loc
    from entities.mech import CritStatus
    from systems.combat import part_is_nonfunctional
    from core.effects import send_error
    first_bits = (S.BEAGLE_PROBE_TECH | S.TRIPLE_MYOMER_TECH | S.MASC_TECH | S.ECM_TECH |
                  S.C3_SLAVE_TECH | S.C3_MASTER_TECH | S.ARTEMIS_IV_TECH | S.ES_TECH | S.FF_TECH |
                  S.IS_ANTI_MISSILE_TECH | S.CL_ANTI_MISSILE_TECH | S.LIGHT_BAP_TECH)
    unit.specials &= ~first_bits
    if unit.unit_type == U.MECH: unit.specials &= ~(S.XL_TECH | S.XXL_TECH | S.CE_TECH | S.LE_TECH)
    unit.specials2 &= ~(1 | 0x10 | 0x1000 | 2 | 0x4000 | 0x8000 | 0x20 | 0x800 | 0x1000000)
    unit.infantry_specials = getattr(unit, 'infantry_specials', 0) & ~0xF8
    all_parts, working, section_counts = Counter(), Counter(), []
    clan = bool(unit.specials & S.CLAN_TECH)
    for loc, sec in enumerate(unit.sections):
        counts = Counter()
        sec.config &= ~C.CASE_TECH
        for pos, slot in enumerate(sec.criticals[:crits_in_loc(unit, loc)]):
            if is_special(slot.type):
                kind = special2i(slot.type)
                counts[kind] += 1
                all_parts[kind] += 1
                if not part_is_nonfunctional(unit, loc, pos): working[kind] += 1
                if kind == Special.CASE:
                    unit.sections[3 if unit.unit_type == U.VEH_GROUND else loc].config |= C.CASE_TECH
            if is_weapon(slot.type):
                weapon = get_weapon_by_index(weapon2i(slot.type))
                if weapon and weapon.special & W.AMS:
                    unit.specials |= S.CL_ANTI_MISSILE_TECH if weapon.special & W.CLAT else S.IS_ANTI_MISSILE_TECH
        section_counts.append(counts)
        engines = counts[Special.ENGINE]
        if loc != L.CTORSO and engines:
            unit.specials |= S.XXL_TECH if engines > 3 else (S.XL_TECH if clan else S.LE_TECH) if engines == 2 else S.XL_TECH
        elif loc == L.CTORSO and engines < 4 and unit.unit_type == U.MECH: unit.specials |= S.CE_TECH
    if unit.specials & S.CE_TECH and unit.specials & (S.XXL_TECH | S.XL_TECH | S.LE_TECH):
        send_error(unit, f'#{unit._id} apparently is very weird: Compact engine AND XL/XXL?')
    for kind, flag, functional in ((Special.ARTEMIS_IV, S.ARTEMIS_IV_TECH, False), (Special.ECM, S.ECM_TECH, False),
            (Special.BEAGLE_PROBE, S.BEAGLE_PROBE_TECH, True), (Special.LIGHT_BAP, S.LIGHT_BAP_TECH, True),
            (Special.C3_SLAVE, S.C3_SLAVE_TECH, True)):
        if (working if functional else all_parts)[kind]: unit.specials |= flag
    if all_parts[Special.TAG]: unit.specials2 |= 0x8000
    if working[Special.TARGETING_COMPUTER]:
        unit.specials2 |= 0x1000000
        for loc, sec in enumerate(unit.sections):
            for slot in sec.criticals[:crits_in_loc(unit, loc)]:
                if not is_weapon(slot.type): continue
                weapon = get_weapon_by_index(weapon2i(slot.type))
                if (weapon and weapon.weapon_type in (T.TBEAM, T.TAMMO) and
                        weapon.name[3:] not in ('Flamer', 'MachineGun', 'LightMachineGun', 'HeavyMachineGun') and
                        not weapon.special & (W.PC_IMPA | W.PC_SHAR | W.PC_HEAT)):
                    slot.firemode |= F.ON_TC
    if working[Special.MASC] >= max(1, int(unit.tonnage / (25 if clan else 20))): unit.specials |= S.MASC_TECH
    thresholds = ((Special.FERRO_FIBROUS, 7 if clan else 14, S.FF_TECH, False, False),
                  (Special.ENDO_STEEL, 7 if clan else 14, S.ES_TECH, False, False),
                  (Special.TRIPLE_STRENGTH_MYOMER, 6, S.TRIPLE_MYOMER_TECH, False, False),
                  (Special.ANGELECM, 2, 0x1000, True, True), (Special.HVY_FERRO_FIBROUS, 21, 2, True, False),
                  (Special.LT_FERRO_FIBROUS, 7, 0x4000, True, False), (Special.C3I, 2, 0x20, True, True),
                  (Special.BLOODHOUND_PROBE, 3, 0x800, True, False))
    for kind, need, flag, second, functional in thresholds:
        count = (working if functional else all_parts)[kind]
        if count >= need or unit.unit_type != U.MECH and count:
            if second: unit.specials2 |= flag
            else: unit.specials |= flag
        elif count and unit.unit_type == U.MECH and kind in (Special.FERRO_FIBROUS, Special.ENDO_STEEL,
                  Special.TRIPLE_STRENGTH_MYOMER, Special.HVY_FERRO_FIBROUS, Special.LT_FERRO_FIBROUS):
            label = {Special.FERRO_FIBROUS: 'FF', Special.ENDO_STEEL: 'ES',
                     Special.TRIPLE_STRENGTH_MYOMER: 'TSM', Special.HVY_FERRO_FIBROUS: 'HvyFF',
                     Special.LT_FERRO_FIBROUS: 'LtFF'}[kind]
            send_error(unit, f'{getattr(unit, "template_ref", unit.mech_type)} (#{unit._id}) is missing {label} Crits {count}/{need}!')
    if all_parts[Special.NULL_SIGNATURE_SYSTEM] and (unit.unit_type != U.MECH or
            all(counts[Special.NULL_SIGNATURE_SYSTEM] for loc, counts in enumerate(section_counts) if loc != L.HEAD)):
        unit.specials2 |= 0x10
    if all_parts[Special.STEALTH_ARMOR] and unit.specials & S.ECM_TECH and (unit.unit_type != U.MECH or
            all(counts[Special.STEALTH_ARMOR] >= 2 for loc, counts in enumerate(section_counts) if loc not in (L.HEAD, L.CTORSO))):
        unit.specials2 |= 1
    if unit.unit_type == U.BSUIT:
        suits = sum(bool(sec.internal) for sec in unit.sections)
        for i, kind in enumerate((Special.PURIFIER_ARMOR, Special.KAGE_STEALTH_UNIT, Special.ACHILEUS_STEALTH_UNIT,
                                 Special.INFILTRATOR_STEALTH_UNIT, Special.INFILTRATORII_STEALTH_UNIT)):
            if (all_parts if i == 0 else working)[kind] >= suits: unit.infantry_specials |= 8 << i
    if all_parts[Special.C3_MASTER]:
        from systems.criticals import count_total_c3_masters, count_working_c3_masters
        unit.total_c3_masters, unit.working_c3_masters = count_total_c3_masters(unit), count_working_c3_masters(unit)
        if unit.total_c3_masters: unit.specials |= S.C3_MASTER_TECH
        if unit.working_c3_masters: unit.crit_status &= ~CritStatus.C3_DESTROYED
        else: unit.crit_status |= CritStatus.C3_DESTROYED


def weapon_is_recycling(unit,loc,pos):
    """btmacros.h WpnIsRecycling, including source section durability."""
    from systems.combat import part_is_nonfunctional
    slot=unit.sections[loc].criticals[pos]
    return slot.data>0 and is_weapon(slot.type) and not part_is_nonfunctional(unit,loc,pos) and not unit.is_section_destroyed(loc)
