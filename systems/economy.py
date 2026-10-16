# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.utils.c
#   btech/src/btech/mech.h
#   btech/template.c

"""In-session part prices and the source FASA unit-cost calculation."""
from dataclasses import dataclass, field
from core.randomness import float32 as f32
from entities.mech import UnitType as U, MoveType as M, Specials as S, AmmoMode as A
from entities.crittypes import Special, is_weapon, is_ammo, is_special, weapon2i, special2i, i2special
from entities.weapon import get_weapon_by_index, WeaponType as T
from systems.parts import round_to_halfton


class CostTables:
    """template.c's distinct zero-initialized unsigned64 part-price arrays."""
    def __init__(self): self.values = [0] * 1024

    def get(self, part):
        if part >= 1024: raise ValueError('Part exceeds source cost table')
        return self.values[part] if part > 0 else 0

    def set(self, part, value):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**64:
            raise ValueError('Cost must be an unsigned 64-bit integer')
        if part >= 1024: raise ValueError('Part exceeds source cost table')
        if part > 0: self.values[part] = value


@dataclass
class Calculation:
    value: float = 0
    components: list = field(default_factory=list)

    def add(self, label, value, *, subtract=False):
        operand = f32(value)
        amount = -operand if subtract else operand
        self.value = f32(self.value + amount)
        self.components.append(dict(label=label, amount=amount, subtotal=self.value))
        if getattr(self,'_debug',None) is not None: self._debug(label,operand,subtract)

    def multiply(self, label, value):
        self.value = f32(self.value * f32(value))
        self.components.append(dict(label=label, multiplier=f32(value), subtotal=self.value))


def calculation(unit=None, kind='Addprice -', initial=0):
    """A source float accumulator with optional MUX debug-channel output."""
    result = Calculation(value=f32(initial))
    if unit is not None and getattr(unit._engine,'cost_debug',False):
        def emit(label,amount,subtract):
            from core.effects import send_debug
            prefix,separator = kind,' '
            if kind=='AddDefBV' and subtract:
                prefix,separator = 'SubDefBV','-'
            numeric = f'{amount:8.0f}' if kind=='Addprice -' else f'{amount:8.2f}'
            send_debug(unit,f'{prefix} {label:>25}{separator}{numeric}')
        result._debug = emit
    return result


def actuator_cost(unit, loc, leg=False, result=None):
    result = calculation(unit) if result is None else result
    rates = (150, 80, 120) if leg else (100, 50, 80)
    for slot in unit.sections[loc].criticals:
        for kind, rate, label in zip((Special.UPPER_ACTUATOR, Special.LOWER_ACTUATOR, Special.HAND_OR_FOOT_ACTUATOR), rates,
                                      ('Upper Actuator', 'Lower Actuator', 'Actuator' if leg else 'Hand Actuator')):
            if slot.type == i2special(kind): result.add(('LEG ' if leg else 'ARM ') + label, unit.tonnage * rate)
    return result


def suspension_factor(unit):
    if unit.move_type == M.WHEEL: return 20
    if unit.move_type in (M.HULL, M.SUB): return 30
    table = {M.FOIL: (60,105,150,195,255,300,345,390,435,480),
             M.HOVER: (40,85,130,175,235), M.VTOL: (50,95,140)}.get(unit.move_type)
    if table:
        return next((value for i,value in enumerate(table) if unit.tonnage <= (i + 1) * 10), table[-1])
    return 0


def fasa_cost(unit):
    from entities.source_weapon_numbers import SOURCE_WEAPON_NAMES, source_weapon
    from systems.weapon_inventory import find_weapons, weapon_crits
    from systems.combat_ammunition import find_ammunition
    from core.effects import send_debug
    result = calculation(unit)
    if unit is None: result.value = 2**64 - 1; return result
    if unit.unit_type not in (U.MECH, U.VEH_GROUND, U.VEH_NAVAL, U.VTOL, U.BSUIT): return result
    tons, specials, second = int(unit.tonnage), unit.specials, unit.specials2
    clan, suit = bool(specials & S.CLAN_TECH), unit.unit_type == U.BSUIT
    case_sections = {loc for loc, sec in enumerate(unit.sections) if any(is_ammo(slot.type) for slot in sec.criticals)}
    if clan and len(case_sections) != len(unit.sections):
        raise ValueError('Source cost has uninitialized Clan CASE sections')
    if unit.unit_type == U.MECH:
        result.add('ES/Co Internals' if specials & (S.ES_TECH | S.COMPI_TECH) else 'RE Internals' if specials & S.REINFI_TECH else 'Std Internals',
                   tons * (1600 if specials & (S.ES_TECH | S.COMPI_TECH) else 6400 if specials & S.REINFI_TECH else 400))
        result.add('Small Cockpit' if second & 0x2000000 else 'Cockpit', 175000 if second & 0x2000000 else 200000)
        result.add('LifeSupport', 50000)
        result.add('Sensors', tons * 2000)
        result.add('TS Myomer' if specials & S.TRIPLE_MYOMER_TECH else 'Myomer', tons * (16000 if specials & S.TRIPLE_MYOMER_TECH else 2000))
        for loc in (0,1): actuator_cost(unit, loc, result=result)
        for loc in (5,6): actuator_cost(unit, loc, True, result)
        gyros = (int(unit.engine_size()) + 99) // 100
        name, rate = ('XL Gyro',375000) if second & 0x200000 else ('Compact Gyro',600000) if second & 0x800000 else ('HD Gyro',1000000) if second & 0x400000 else ('Gyro',300000)
        result.add(name, gyros * rate)
    elif suit:
        result.add('Clan Point' if clan else 'IS Squad', 3500000 if clan else 2400000)
    else:
        amp = turret = 0
        for loc, sec in enumerate(unit.sections):
            for slot in sec.criticals:
                if not is_weapon(slot.type): continue
                weapon = get_weapon_by_index(weapon2i(slot.type))
                weight = int(weapon.tonnage * 100) * 1024 // 100 // weapon_crits(unit, weapon.index)
                if loc == 4: turret += weight
                # Source IsEnergy(part) indexes with the encoded type, one ahead.
                try: raw = SOURCE_WEAPON_NAMES.index(weapon.name) + 1
                except ValueError: raise ValueError('Source IsEnergy(part) catalog metadata unavailable') from None
                if source_weapon(raw).weapon_type == T.TBEAM:
                    amp += weight
                    send_debug(unit,f'PAmp Weight: {weight}')
        result.add('Internals', tons * 1000)
        result.add('Cockpit & Controls', tons * 500)
        if specials & S.ICE_TECH: result.add('Power Amplifiers', 20000 * (amp // 1024) // 10)
        result.add('Turret', 5000 * (turret // 10) // 1024)
        if unit.move_type in (M.HOVER,M.FOIL,M.SUB): result.add('Lift/Dive Equip', tons * 2000)
        if unit.move_type == M.VTOL: result.add('Rotor', tons * 4000)
    engine_size = 0
    if not suit:
        base = next((price for bit,price in ((S.CE_TECH,10000),(S.LE_TECH,15000),(S.XL_TECH,20000),
                    (S.XXL_TECH,100000),(S.ICE_TECH,1250)) if specials & bit),5000)
        engine_size = int(unit.engine_size()) - suspension_factor(unit)
        if engine_size < 0: raise ValueError('Source unsigned engine price is outside defined signed-int range')
        price = base * engine_size * tons // 75
        if price > 2**31 - 1: raise ValueError('Source engine price exceeds signed-int domain')
        result.add('Engine',price)
        jets = int(f32(unit.jump_speed) * 0.0930233)
        if jets > 0: result.add('Jumpjets',tons * jets * jets * (500 if second & 0x80 else 200))
        double = bool(specials & (S.DOUBLE_HEAT_TECH | S.CLAN_TECH))
        sinks = int(unit.effective_heat_sinks)
        if double: sinks = max(0,min(500,sinks // 2))
        cost = 6000 if double else 3000 if second & 0x200 else 2000
        if not (double or second & 0x200 or specials & S.ICE_TECH): sinks = max(0,min(500,sinks - 10))
        result.add('Heat Sinks',sinks * cost)
        armor = sum(sec.armor_orig + sec.rear_orig for sec in unit.sections)
        if specials & S.FF_TECH: armor = armor * 50 // (60 if clan else 56)
        elif second & 2: armor = armor * 50 // 62
        elif second & 0x4000: armor = armor * 50 // 53
        weight = f32(round_to_halfton(armor * 1024 // 16) / 1024)
        rate = 20000 if specials & S.FF_TECH else 50000 if second & 1 else 15000 if specials & S.HARDA_TECH or second & 0x4000 else 25000 if second & 2 else 10000
        result.add('Armor',int(f32(weight * rate)))
    for loc in range(len(unit.sections)):
        for run in find_weapons(unit, loc) or []:
            weapon = get_weapon_by_index(run.weapon_idx)
            result.add(weapon.name, weapon.cost)
    ammunition = find_ammunition(unit)
    if ammunition and getattr(unit._engine,'cost_debug',False):
        send_debug(unit,'Ammo Costs')
    for group in ammunition:
        weapon = get_weapon_by_index(group.weapon_idx)
        if group.maximum <= 0 or weapon.ammo_per_ton <= 0: raise ValueError('Source ammo price division by zero')
        value = (weapon.ammo_cost // (weapon.ammo_per_ton // group.maximum) if group.maximum < weapon.ammo_per_ton
                 else weapon.ammo_cost * (group.maximum // weapon.ammo_per_ton) * (2 if group.mode & A.ARTEMIS_MODE else 1))
        result.add(weapon.name, value)
    masc = bloodhound = 0
    sword = False
    # CalcFasaCost uses mech.h CASEII (50), not CASE_II (33).
    prices = {Special.CASE:('Int Case',50000), 50:('Int CaseII',175000), Special.AXE:('Int Axe',5000),
              Special.BEAGLE_PROBE:('BAP',100000), Special.LIGHT_BAP:('LightBAP',50000),
              Special.ARTEMIS_IV:('ArtemisIV FCS',100000), Special.ANGELECM:('Angel ECM',375000),
              Special.C3_MASTER:('C3M',300000), Special.C3_SLAVE:('C3S',250000), Special.C3I:('C3I',375000),
              Special.ECM:('ECM',100000), Special.TAG:('TAG',50000), Special.TARGETING_COMPUTER:('TargComp',10000)}
    for sec in unit.sections:
        for slot in sec.criticals:
            if not is_special(slot.type): continue
            kind = special2i(slot.type)
            if kind == Special.MASC: masc += 1
            elif kind == Special.BLOODHOUND_PROBE: bloodhound += 1
            elif kind == Special.SWORD: sword = True
            elif kind in prices: result.add(*prices[kind])
    if bloodhound // 3: result.add('Bloodhound',500000 * (bloodhound // 3))
    if masc: result.add('MASC',masc * engine_size * 1000)
    if sword: result.add('Sword',f32(round_to_halfton(tons * 1024 // 20) / 1024) * 10000)
    if clan:
        for _ in unit.sections: result.add('Clan CASE Section',50000)
    divisor = 100 if unit.unit_type == U.MECH else {M.TRACK:100,M.WHEEL:200,M.HOVER:50,M.VTOL:30,M.HULL:200,M.FOIL:75,M.SUB:50}.get(unit.move_type)
    multiplier = .75 if suit else f32(1 + f32(f32(tons) / divisor)) if divisor else 1
    if second & 0x10000: result.add('OmniMech',int(result.value * .25))
    result.multiply('Unit movement multiplier',multiplier)
    result.value = int(result.value)
    return result
