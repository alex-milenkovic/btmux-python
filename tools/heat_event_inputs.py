"""Decode scheduled events and stagger history in heat workflow fixtures."""

from tools.movement_inputs import fields, number, boolean, array
from tools.heat_equipment_inputs import location


def apply_events(session, unit, cfg):
    events = fields(cfg.get("events", {}), ("inferno", "burns", "extinguish", "cutoff"))
    from core.events import EventType
    from systems import vehicle_fire, heat_control
    from systems.missile import inferno_burn

    if "inferno" in events:
        inferno_burn(session.engine, unit, number(events["inferno"], 1, integer=True))
    unit._side_burns = {}
    for item in array(events.get("burns", [])):
        fields(item, ("section", "remaining"), ("section", "remaining"))
        loc = location(unit, item["section"])
        if loc in unit._side_burns:
            raise ValueError("duplicate side burn")
        unit._side_burns[loc] = session.engine.events.schedule(
            number(item["remaining"], 1, integer=True),
            EventType.VEHICLE_BURN,
            vehicle_fire.burn_event,
            unit,
            loc,
        )
    if "extinguish" in events:
        unit._extinguish_event = session.engine.events.schedule(
            number(events["extinguish"], 1, integer=True),
            EventType.VEHICLE_EXTINGUISH,
            vehicle_fire.extinguish_event,
            unit,
        )
    if "cutoff" in events:
        item = fields(
            events["cutoff"], ("remaining", "engage"), ("remaining", "engage")
        )
        unit._cutoff_event = session.engine.events.schedule(
            number(item["remaining"], 1, integer=True),
            EventType.HEAT_CUTOFF,
            heat_control.heat_cutoff_event,
            unit,
            boolean(item["engage"]),
        )


def apply_history(unit, cfg):
    history = array(cfg.get("history", []))
    last = None
    for node in history:
        fields(node, ("amount", "wall", "counted"), ("amount", "wall", "counted"))
        timestamp = number(node["wall"], integer=True)
        if last is not None and timestamp < last:
            raise ValueError("history must be chronological")
        unit.stagger_damage_list.append(
            dict(
                amount=number(node["amount"], 1, integer=True),
                occurred_at=timestamp,
                counted=boolean(node["counted"]),
            )
        )
        last = timestamp
