# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.utils.c

"""The distinct new offensive/defensive and legacy source BV algorithms."""
import math
from core.randomness import float32 as f32
from entities.mech import UnitType as U, MoveType as M, Specials as S, FireMode as F, AmmoMode as A, SectionConfig as C
from entities.crittypes import Special, is_special, is_weapon, is_ammo, special2i, weapon2i, ammo2weapon_i, crits_in_loc
from entities.weapon import get_weapon_by_index, WeaponFlags as W, WeaponType as T
from systems.economy import Calculation, calculation
from systems.parts import armorpoints, intpoints

SKILL_MULTIPLIERS = (
    (2.05,2,1.95,1.90,1.85,1.80,1.75,1.70), (1.85,1.80,1.75,1.70,1.65,1.60,1.55,1.50),
    (1.65,1.60,1.55,1.50,1.45,1.40,1.35,1.30), (1.45,1.40,1.35,1.30,1.25,1.20,1.15,1.10),
    (1.25,1.20,1.15,1.10,1.05,1,.95,.90), (1.15,1.10,1.05,1,.95,.90,.85,.80),
    (1.05,1,.95,.90,.85,.80,.75,.70), (.95,.90,.85,.80,.75,.70,.65,.60),
)


def active_sinks(unit): return int(unit.effective_heat_sinks) - unit.disabled_sinks


def maximum_speed(unit):
    from physics.cargo import cargo_max_speed
    return f32(cargo_max_speed(unit))


def roundf(value):
    value = f32(value)
    return f32(math.floor(value + .5) if value >= 0 else math.ceil(value - .5))


def defensive_bv(unit):
    result = calculation(unit,'AddDefBV')
    specials, second, kind = unit.specials, unit.specials2, unit.unit_type
    clan = bool(specials & S.CLAN_TECH)
    result.add('Armor', armorpoints(unit) * 2.5)
    engine = .75 if specials & S.LE_TECH else 1
    if specials & S.XL_TECH: engine = .75 if clan else .5
    if specials & S.XXL_TECH: engine = .5
    if kind != U.MECH: engine = 1
    result.add('Internal/Engine', intpoints(unit) * 1.5 * engine)
    if kind == U.MECH: result.add('Gyro (Mech Only)', unit.tonnage * (1 if second & 0x400000 else .5))
    ecm = bap = 0
    for loc, section in enumerate(unit.sections):
        central = loc in (4,5,6,7)
        case = bool(section.config & C.CASE_TECH)
        xl = bool(specials & (S.XL_TECH | S.XXL_TECH))
        for slot in section.criticals:
            if is_special(slot.type):
                ecm += special2i(slot.type) == Special.ECM
                bap += special2i(slot.type) == Special.BEAGLE_PROBE
            elif is_ammo(slot.type):
                weapon = get_weapon_by_index(ammo2weapon_i(slot.type))
                if weapon is None: raise ValueError('Unsupported defensive ammunition catalog index')
                if weapon.special & W.AMS: result.add('AMS Ammo', weapon.ammo_bv)
                if kind == U.MECH:
                    if central and clan: result.add('Explosive Ammo', 15, subtract=True)
                    elif xl: result.add('Exp Ammo in XL/XXL', 15, subtract=True)
                    elif central or not case: result.add('Exp Ammo Fusion/!CASE', 15, subtract=True)
            elif is_weapon(slot.type):
                weapon = get_weapon_by_index(weapon2i(slot.type))
                if weapon is None: raise ValueError('Unsupported defensive weapon catalog index')
                if weapon.special & W.A_POD: result.add('A POD', weapon.bv)
                if weapon.special & W.AMS: result.add('AMS', weapon.bv)
                if weapon.special & W.GAUSS:
                    if central and clan: result.add('Gauss Crit', 1, subtract=True)
                    elif xl: result.add('Gauss Crit XL/XXL', 1, subtract=True)
                    elif central and not case: result.add('Gauss Crit !Case', 1, subtract=True)
                    elif loc in (0,1) and not unit.sections[loc + 2].config & C.CASE_TECH:
                        result.add('Gauss Crit Fusion/!Case', 1, subtract=True)
    needed = 2 if kind == U.MECH and not clan else 1
    if ecm >= needed: result.add('ECM', 61)
    if bap >= needed: result.add('BAP', 10)
    reduction = {M.TRACK:('Tracked',.1),M.WHEEL:('Wheeled',.2),M.HOVER:('Hover',.3),
                 M.SUB:('Naval',.4),M.FOIL:('Naval',.4),M.HULL:('Naval',.4),M.VTOL:('VTOL',.3)}.get(unit.move_type)
    if reduction: result.add('UnitType ' + reduction[0], result.value * reduction[1], subtract=True)
    speed = maximum_speed(unit)
    running, jumping = int(speed / 10.75), int(f32(unit.jump_speed) / 10.75)
    if specials & S.TRIPLE_MYOMER_TECH: running = math.ceil((round((speed / 1.5) / 10.75) + 1) * 1.5)
    if specials & S.MASC_TECH:
        if second & 0x40: running = int((running * 2 // 3) * 2.5)
        running = running * 2 // 3 * 2
    elif second & 0x40: running = running * 2 // 3 * 2
    modifier = next((mod for bound, mod in ((24,6),(17,5),(9,4),(6,3),(4,2),(2,1)) if running > bound),0)
    if kind in (U.BSUIT,U.VTOL,U.AERO): modifier += 1
    if jumping > running: modifier += 1
    # Source uses specials, where STEALTH_ARMOR_TECH's bit is also TSM.
    if specials & 1: modifier += 2
    result.add(f'MoveMod (MP: {running} MM: {modifier})', f32(result.value * f32(modifier * .1)))
    result.value = f32(roundf(result.value * 100) / 100)
    return result


def offensive_bv(unit):
    from systems.weapon_inventory import weapon_runs
    result = calculation(unit,'AddOffBV')
    capacity = 6 + active_sinks(unit) - max(int(f32(unit.jump_speed) / 10.75),2)
    weapons = [get_weapon_by_index(run.weapon_idx) for run in weapon_runs(unit)]
    weapons = [weapon for weapon in weapons if not weapon.special & W.AMS]
    if len(weapons) > 64: raise ValueError('Source offensive BV weapon table exceeds 64 entries')
    heat = 0
    for weapon in reversed(sorted(weapons,key=lambda weapon:weapon.bv)):
        result.add(weapon.name, int(weapon.bv / 2) if heat + weapon.heat > capacity else weapon.bv)
        heat += weapon.heat
    result.add('MechTonnage',unit.tonnage)
    return result


def calculate_bv(unit, gunstat=100, pilstat=100, *, tick=None):
    from systems.combat import part_is_nonfunctional
    from systems.weapon_modes import find_artemis_for_weapon
    from systems.piloting import find_pilot_piloting, find_pilot_gunnery
    result = Calculation()
    if unit is None: return result
    tick = getattr(unit._engine,'muxevent_tick',0) if tick is None else tick
    if gunstat == 100 or pilstat == 100:
        if tick - getattr(unit,'bv_last',0) < 30:
            result.value = getattr(unit,'bv',0)
            return result
        unit.bv_last = tick
    piloting = find_pilot_piloting(unit) if gunstat == 100 else pilstat
    gunnery = find_pilot_gunnery(unit,0) if pilstat == 100 else gunstat
    kind, move, specials, second = unit.unit_type, unit.move_type, unit.specials, unit.specials2
    aero, ds, clan = kind in (U.AERO,U.DS,U.SPHEROID_DS), kind in (U.DS,U.SPHEROID_DS), bool(specials & S.CLAN_TECH)
    jump_speed = f32(unit.jump_speed)
    armor = internal = off_weapons = def_weapons = heat = deduct = 0
    def record(label, value): result.components.append(dict(label=label, value=value))
    for loc, section in enumerate(unit.sections):
        armor += section.armor * (200 if specials & S.HARDA_TECH else 100)
        if kind == U.MECH and loc in (2,3,4): armor += section.rear * (200 if specials & S.HARDA_TECH else 100)
        if aero: internal = getattr(unit,'si',0)
        else: internal += section.internal * (50 if specials & S.COMPI_TECH else 200 if specials & S.REINFI_TECH else 100)
        pos = 0
        while pos < crits_in_loc(unit,loc):
            index = pos
            slot = section.criticals[index]
            part = slot.type
            pos += 1
            weapon = None
            if is_weapon(part):
                weapon = get_weapon_by_index(weapon2i(part))
                if weapon is None: raise ValueError('Unsupported legacy weapon catalog index')
                if kind == U.MECH: pos += weapon.crits - 1
                if part_is_nonfunctional(unit,loc,index): continue
                if weapon.vrt <= 0: raise ValueError('Legacy BV requires positive weapon recycle time')
                ratio = f32(3000 / f32(weapon.vrt * 100))
                if weapon.special & W.AMS:
                    def_weapons += int(f32(f32(weapon.bv * 100) * f32(3000 // (weapon.vrt * 100))))
                else:
                    off_weapons += int(f32(f32(weapon.bv * (50 if slot.firemode & F.REAR_MOUNT else 100)) * ratio))
                    if weapon.weapon_type == T.TMISSILE and find_artemis_for_weapon(unit,loc,index): off_weapons += weapon.bv * 20
                if kind == U.MECH and not slot.firemode & F.REAR_MOUNT:
                    amount = int(f32(f32(weapon.heat * 100) * ratio))
                    if weapon.special & W.ULTRA: amount *= 2
                    if weapon.special & W.STREAK: amount = int(amount / 2)
                    heat += amount
            elif is_ammo(part):
                if part_is_nonfunctional(unit,loc,index) or not slot.data: continue
                weapon = get_weapon_by_index(ammo2weapon_i(part))
                if weapon is None or weapon.ammo_per_ton <= 0 or weapon.vrt <= 0:
                    raise ValueError('Legacy BV has invalid ammunition denominator')
                multiplier = 4 if slot.ammomode & A.AC_AP_MODE else 6 if slot.ammomode & A.AC_PRECISION_MODE else 1.5 if slot.ammomode & (A.SWARM_MODE|A.SWARM1_MODE|A.STINGER_MODE) else 1
                multiplier = f32(f32(multiplier) * f32(f32(slot.data) / f32(weapon.ammo_per_ton)))
                amount = int(f32(f32(f32((weapon.bv // 10) * 100) * multiplier) * f32(3000 / f32(weapon.vrt * 100))))
                if weapon.special & W.AMS: def_weapons += amount
                else: off_weapons += amount
            explosive = is_ammo(part) or is_weapon(part) and weapon.special & W.GAUSS
            if explosive and kind == U.MECH:
                central = loc in (4,5,6,7)
                if (clan and central or specials & (S.XL_TECH|S.XXL_TECH|S.ICE_TECH|S.LE_TECH) or
                        central and not section.config & C.CASE_TECH or loc in (0,1) and
                        not section.config & C.CASE_TECH and not unit.sections[loc + 2].config & C.CASE_TECH):
                    deduct += 2000
    record('Armor before class multiplier',armor)
    record('Internal before engine multiplier',internal)
    record('Weapons and ammunition offense',off_weapons)
    record('Weapons and ammunition defense',def_weapons)
    if kind == U.MECH:
        heat = int(heat + (max(jump_speed / 10.75 * 100,300) if jump_speed > 0 else 200))
        if second & (0x10|1): heat += 1000
        deduct += max(0,heat - active_sinks(unit) * 100) * 5
    record('Heat',heat)
    record('Deductions',deduct)
    if specials & S.ECM_TECH: def_weapons += 6100
    if specials & S.BEAGLE_PROBE_TECH: off_weapons += 1200 if clan else 1000
    if specials & (S.XL_TECH|S.XXL_TECH|S.LE_TECH): multiplier = 1.125 if specials & (S.CLAN_TECH|S.LE_TECH) else .75
    elif specials & S.ICE_TECH or kind in (U.VEH_GROUND,U.VEH_NAVAL): multiplier = .5
    else: multiplier = 1.5
    if kind == U.MECH: armor *= 2
    internal = int(f32(f32(internal) * f32(multiplier)))
    base_speed = maximum_speed(unit)
    speed = base_speed
    if specials & S.MASC_TECH or second & 0x40:
        speed = f32(speed * (2.5 if specials & S.MASC_TECH and second & 0x40 else 1.5))
    if specials & S.TRIPLE_MYOMER_TECH: speed = f32((f32(2 * speed) / 3 + 10.75) * 1.5)
    multiplier = next((mult for bound,mult in ((2,1),(4,1.1),(6,1.2),(9,1.3),(13,1.4),(18,1.5),(24,1.6)) if speed <= bound * 10.75),1.7)
    if ds: multiplier = 1
    elif aero: multiplier = 1.1
    multiplier = f32(multiplier)
    if second & (0x10|1): multiplier = f32(multiplier + 1.5)
    infantry = getattr(unit,'infantry_specials',0)
    for bit, value in ((0x10,.75),(0x20,1.5),(8,2),(0x40,.75),(0x40,2)):
        if infantry & bit: multiplier = f32(multiplier + value)
    defense = max(1, armor + internal + unit.tonnage * 100 + def_weapons - deduct)
    if kind != U.MECH:
        reduction = {M.TRACK:.8,M.WHEEL:.7,M.HOVER:.6,M.VTOL:.4,M.FOIL:.5,M.SUB:.5,M.HULL:.5}.get(move,1)
        defense = int(defense * reduction - deduct)
    defense = int(f32(f32(defense) * multiplier))
    record('Defense',defense)
    if (kind == U.MECH or aero) and heat > active_sinks(unit) * 100:
        amount = int((int(active_sinks(unit) / 100) * off_weapons) / heat)
        off_weapons = amount + int((off_weapons - amount) / 2)
    speed = f32(2 * base_speed) / 3 if ds else base_speed
    base = (((speed / 10.75) + bool(specials & S.MASC_TECH) + bool(specials & S.TRIPLE_MYOMER_TECH) + bool(second & 0x40) - 5) / 10) + 1
    if base < 0: raise ValueError('Legacy BV speed power has a negative base')
    multiplier = f32(math.pow(base,1.2))
    if second & 0x10000: multiplier = f32(multiplier + .3)
    off_weapons = int(f32(f32(off_weapons) * multiplier))
    if kind not in (U.AERO,U.DS) and jump_speed > 0:
        off_weapons = int(off_weapons + jump_speed / 10.75 * (100 * int(unit.tonnage / 5)))
    record('Offense',off_weapons)
    multiplier = f32(SKILL_MULTIPLIERS[max(0,min(7,gunnery))][max(0,min(7,piloting))])
    result.value = int(f32(f32(int((off_weapons + defense) / 100)) * multiplier))
    record('Skill multiplier',multiplier)
    return result
