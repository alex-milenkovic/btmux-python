"""Decode physical weapon and ammunition slots for heat workflow fixtures."""

from tools.movement_inputs import fields, number, boolean, string, array
from entities.mech import Location, VehicleLocation, UnitType, WeaponState, FireMode
from entities.crittypes import i2ammo, i2weapon, crits_in_loc
from entities.weapon import Weapon, WeaponType, register_weapon


def location(unit, value):
    aliases = {
        "CT": Location.CTORSO,
        "LT": Location.LTORSO,
        "RT": Location.RTORSO,
        "LA": Location.LARM,
        "RA": Location.RARM,
        "LL": Location.LLEG,
        "RL": Location.RLEG,
        "HD": Location.HEAD,
    }
    enum = (
        Location
        if unit.unit_type in (UnitType.MECH, UnitType.MW, UnitType.BSUIT)
        else VehicleLocation
    )
    name = string(value)
    if enum is VehicleLocation:
        name = {"FRONT": "FSIDE", "REAR": "BSIDE"}.get(name, name)
    return aliases[name] if name in aliases and enum is Location else enum[name]


def slot_at(unit, cfg):
    loc = location(unit, cfg["section"])
    pos = number(cfg["slot"], 1, crits_in_loc(unit, loc), True) - 1
    return loc, pos, unit.sections[loc].criticals[pos]


def apply_equipment(unit, cfg):
    equipment = array(cfg.get("equipment", []))
    occupied = set()
    for item in equipment:
        apply_weapon(unit, item, occupied)
    for item in array(cfg.get("bins", [])):
        apply_bin(unit, item, occupied)


def apply_weapon(unit, item, occupied):
    fields(
        item,
        (
            "name",
            "category",
            "damage",
            "ammo_per_ton",
            "salvo",
            "table_match",
            "section",
            "slot",
            "recycle",
            "temporary_failure",
            "fired_rocket",
        ),
        ("name", "category", "damage", "section", "slot"),
    )
    kind = {
        "ENERGY": WeaponType.TBEAM,
        "BALLISTIC": WeaponType.TAMMO,
        "MISSILE": WeaponType.TMISSILE,
        "ARTILLERY": WeaponType.TARTILLERY,
        "HAND": WeaponType.THAND,
    }[string(item["category"])]
    rate = number(item.get("ammo_per_ton", 0), 0, integer=True)
    if kind not in (WeaponType.TBEAM, WeaponType.THAND) and rate <= 0:
        raise ValueError("ammunition needs positive rounds per ton")
    weapon = register_weapon(
        Weapon(
            string(item["name"]),
            weapon_type=kind,
            damage=number(item["damage"], 0, integer=True),
            ammo_per_ton=rate,
            missiles=number(item.get("salvo", 1), 1, integer=True),
        )
    )
    weapon.ammo_full_salvo = (
        weapon.missiles
        if boolean(
            item.get(
                "table_match", kind in (WeaponType.TMISSILE, WeaponType.TARTILLERY)
            )
        )
        else None
    )
    loc, pos, slot = slot_at(unit, item)
    if (loc, pos) in occupied:
        raise ValueError("duplicate equipment slot")
    occupied.add((loc, pos))
    slot.type = i2weapon(weapon.index)
    slot.data = number(item.get("recycle", 0), 0, integer=True)
    if boolean(item.get('fired_rocket', False)):
        slot.firemode |= FireMode.ROCKET_FIRED
    from systems.enhanced_crits import set_part_temp_nuke

    set_part_temp_nuke(
        slot,
        {"NONE": 0, "TEMPORARY": 1, "DESTROYED": 5}[
            item.get("temporary_failure", "NONE")
        ],
    )
    unit.weapons.append(
        WeaponState(
            weapon_idx=weapon.index, section=loc, critical=pos, recycle=slot.data
        )
    )


def apply_bin(unit, item, occupied):
    fields(
        item,
        ("weapon", "section", "slot", "rounds", "condition", "inferno"),
        ("weapon", "section", "slot", "rounds"),
    )
    index = number(item["weapon"], 0, len(unit.weapons) - 1, True)
    from entities.weapon import get_weapon_by_index

    weapon = get_weapon_by_index(unit.weapons[index].weapon_idx)
    if weapon.ammo_per_ton <= 0:
        raise ValueError("energy/hand weapon cannot have an ammo bin")
    loc, pos, slot = slot_at(unit, item)
    if (loc, pos) in occupied:
        raise ValueError("duplicate equipment/bin slot")
    occupied.add((loc, pos))
    slot.type = i2ammo(weapon.index)
    slot.data = number(item["rounds"], 0, integer=True)
    if boolean(item.get('inferno', False)):
        from entities.mech import AmmoMode
        from entities.weapon import WeaponType
        if weapon.weapon_type != WeaponType.TMISSILE:
            raise ValueError('inferno ammunition requires a missile weapon')
        slot.ammomode |= AmmoMode.INFERNO_MODE
    slot.firemode = {
        "FUNCTIONAL": FireMode.NONE,
        "BROKEN": FireMode.BROKEN_MODE,
        "DESTROYED": FireMode.DESTROYED_MODE,
        "DISABLED": FireMode.DISABLED_MODE,
    }[item.get("condition", "FUNCTIONAL")]
