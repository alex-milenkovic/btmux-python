"""Strict fixture decoding for the heat simulation command-line interface."""

from copy import deepcopy
from tools.movement_inputs import (
    fields,
    number,
    boolean,
    string,
    array,
    UNIT_FIELDS,
    section_fixture,
)
from entities.mech import (
    MechStatus as S,
    MechStatus2 as S2,
    CritStatus as C,
    Specials,
    VehicleLocation,
)
from entities.crittypes import i2special, Special
from tools.heat_equipment_inputs import location, apply_equipment
from tools.heat_event_inputs import apply_history, apply_events

EXTRA = (
    "name",
    "heat_state",
    "equipment",
    "bins",
    "history",
    "events",
    "last_stagger_check",
    "stagger_stamp",
    "last_dropship_notice",
    "fz",
    "started",
    "conscious",
    "blinded",
    "fallen",
    "free_fuel",
    "wizard",
    "auto_turret",
    "pilot_hits",
    "consistent",
    "map_valid",
    "pain_resistance",
    "searchlight",
)
CONFIG = (
    "periodic_updates",
    "heartbeat",
    "advanced_vehicle_fire",
    "new_stagger",
    "stagger_interval",
    "stagger_tonnage",
    "heatcutoff_enabled",
    "movement_modes",
    "mw3stats",
    "inferno_penalty",
)
HEAT = (
    "heat",
    "plus_heat",
    "weapon_heat",
    "engine_heat",
    "sink_technology",
    "sink_capacity",
    "disabled_capacity",
    "cutoff",
    "leg_sink_slots",
    "last_overheat_tick",
    "life_support_destroyed",
    "stealth",
    "null_signature",
)


def prepare(document):
    document = deepcopy(
        fields(
            document,
            ("map", "units", "config", "clock", "random", "actions"),
            ("actions",),
        )
    )
    array(document["actions"])
    config = fields(document.get("config", {}), CONFIG)
    for key, wanted in (("movement_modes", True), ("mw3stats", False)):
        if boolean(config.get(key, wanted)) != wanted:
            raise ValueError("unsupported compile profile: " + key)
    board = deepcopy(document.get("map", {}))
    fields(
        board,
        (
            "size",
            "default",
            "hexes",
            "gravity",
            "special_rules",
            "temperature",
            "underlying",
            "bridge_protection",
            "visibility",
            "light",
        ),
    )
    temperature = number(board.pop("temperature", 25), integer=True)
    underlays = array(board.pop("underlying", []))
    board.setdefault("size", [8, 8])
    units = []
    extras = []
    for cfg in array(document.get("units", [{"name": "u"}])):
        fields(cfg, (*UNIT_FIELDS, *EXTRA))
        base = {key: value for key, value in cfg.items() if key in UNIT_FIELDS}
        if "id" in cfg and "name" in cfg:
            raise ValueError("use name or id, not both")
        base["id"] = string(cfg.get("name", cfg.get("id", "u")))
        if "relative_position" not in base:
            base.setdefault("at", [2, 2, 0])
        base.setdefault("jump_mp", 0)
        base.setdefault("advantages", [])
        units.append(base)
        extras.append(cfg)
    return (
        document,
        dict(
            map=board,
            units=units,
            config={"periodic_updates": boolean(config.get("periodic_updates", True))},
            actions=document["actions"],
        ),
        extras,
        temperature,
        underlays,
    )


def apply_heat(unit, value):
    value = fields(value, HEAT)
    technology = string(value.get("sink_technology", "SINGLE"))
    tech = {
        "SINGLE": Specials.NONE,
        "DOUBLE": Specials.DOUBLE_HEAT_TECH,
        "CLAN": Specials.CLAN_TECH,
    }[technology]
    capacity = number(value.get("sink_capacity", 10), 0, integer=True)
    disabled = number(value.get("disabled_capacity", 0), 0, capacity, True)
    factor = 2 if tech else 1
    if capacity % factor:
        raise ValueError("capacity must be divisible by sink efficiency")
    unit.specials |= tech
    unit.num_sinks = capacity // factor
    unit.disabled_sinks = disabled
    for key, attr in (
        ("heat", "heat"),
        ("plus_heat", "plus_heat"),
        ("weapon_heat", "weap_heat"),
        ("engine_heat", "engine_heat"),
    ):
        setattr(unit, attr, number(value.get(key, getattr(unit, attr)), 0))
    unit._last_overheat_tick = number(value.get("last_overheat_tick", 0), integer=True)
    for key, flag in (
        ("cutoff", C.HEATCUTOFF),
        ("life_support_destroyed", C.LIFE_SUPPORT_DESTROYED),
    ):
        if boolean(value.get(key, False)):
            unit.set_crit_status(flag)
    for key, flag in (
        ("stealth", S2.STH_ARMOR_ON),
        ("null_signature", S2.NULLSIGSYS_ON),
    ):
        if boolean(value.get(key, False)):
            unit.set_status2(flag)
    count = number(value.get("leg_sink_slots", 0), 0, 12, True)
    # Install concrete functional sink parts in the supplied leg-slot fixture.
    if count > unit.num_sinks * (
        3 if technology == "DOUBLE" else 2 if technology == "CLAN" else 1
    ):
        raise ValueError("leg sink slots exceed physical sink capacity")
    from systems.movement_commands import legs

    locations = legs(unit)
    for i in range(count):
        unit.sections[locations[i % len(locations)]].criticals[
            i // len(locations)
        ].type = i2special(Special.HEAT_SINK)


def apply_unit(session, unit, cfg):
    # Default armor/internal 100; preserve explicitly supplied section fixtures.
    for loc, section in enumerate(unit.sections):
        section.armor = section.armor_orig = 100
        section.internal = section.internal_orig = 100
        section.rear = section.rear_orig = 100 if loc in (2, 3, 4) else 0
    for section in cfg.get("sections", []):
        section_fixture(unit, section)
    apply_heat(unit, cfg.get("heat_state", {}))
    for key, flag, inverse in (
        ("started", S.STARTED, False),
        ("conscious", S.UNCONSCIOUS, True),
        ("blinded", S.BLINDED, False),
        ("fallen", S.FALLEN, False),
    ):
        if key in cfg:
            value = boolean(cfg[key]) != inverse
            if value:
                unit.set_status(flag)
            else:
                unit.clear_status(flag)
    unit.free_fuel = boolean(cfg.get("free_fuel", False))
    unit.fz = number(cfg.get("fz", unit.fz))
    unit.pilot_hits = number(cfg.get("pilot_hits", 0), 0, 6, True)
    if boolean(cfg.get('pain_resistance', False)):
        if unit.pilot is None:
            raise ValueError('pain_resistance requires a pilot')
        unit.pilot.pain_resistance = True
    if boolean(cfg.get('searchlight', False)):
        unit.set_status2(S2.SLITE_ON)
        unit.set_crit_status(C.SLITE_LIT)
    if session.callers[unit.name] is not None:
        session.callers[unit.name].wizard = boolean(cfg.get("wizard", False))
    if not boolean(cfg.get("consistent", True)):
        raise ValueError("inconsistent unit fixture")
    if not boolean(cfg.get("map_valid", True)):
        unit.map = None
    if boolean(cfg.get("auto_turret", False)):
        unit.set_status2(S2.AUTOTURN_TURRET)
    if "turret" in cfg:
        turret = cfg["turret"]
        unit.sections[VehicleLocation.TURRET].internal = (
            100 if turret.get("present", True) else 0
        )
    unit.last_stagger_check = number(cfg.get("last_stagger_check", 0), integer=True)
    unit.stagger_stamp = number(cfg.get("stagger_stamp", -1), -1, 29, True)
    unit.last_dropship_notice = number(cfg.get("last_dropship_notice", 0), integer=True)
    apply_history(unit, cfg)
    apply_equipment(unit, cfg)
    apply_events(session, unit, cfg)
