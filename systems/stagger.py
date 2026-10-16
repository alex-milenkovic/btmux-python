# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.update.c

"""Chronological whole-hit stagger accounting using the simulation wall clock."""


from entities.mech import UnitType
from systems.piloting import make_piloting_roll
from systems.movement_commands import notify


def record_damage(unit, amount, engine=None, attacker=None):
    if amount <= 0 or unit.is_fallen:
        return
    engine = engine or unit._engine
    if engine is None:
        # Detached units use the zero epoch; insertion is never retimestamped.
        now, mode = 0, 1
    else:
        now, mode = engine.sim_now, getattr(engine, "new_stagger", 1)
    if mode and unit.unit_type == UnitType.MECH:
        unit.stagger_damage_list.append(
            dict(amount=amount, occurred_at=now, counted=False, attacker=attacker)
        )
    else:
        unit.turn_damage += amount


def stagger_modifier(unit, level, weight=True):
    if not unit.is_started:
        return 999
    tons = unit.tonnage
    modifier = 1 if tons <= 35 else 0 if tons <= 55 else -1 if tons <= 75 else -2
    return level - 1 + (modifier if weight else 0)


def heartbeat(engine, unit):
    mode = getattr(engine, "new_stagger", 1)
    if mode < 1 or unit.unit_type != UnitType.MECH:
        return
    now = engine.sim_now
    if (
        not unit.is_fallen
        and not unit.is_jumping
        and now - unit.last_stagger_check >= getattr(engine, "stagger_interval", 5)
    ):
        unit.last_stagger_check = now
        check_new_damage(engine, unit)
    clear_expired(unit, now)


def check_new_damage(engine, unit):
    now = engine.sim_now
    new, previous = current_damage(unit, now), current_damage(unit, now, True)
    if new < 20:
        return
    level = new // 20
    if getattr(engine, "new_stagger", 1) == 2:
        remove_damage(unit, level)
    else:
        mark_damage(unit, level)
        level = (new + previous) // 20
    from systems.sensors import los_broadcast
    messages = {
        1: ('%cy%chThe damage causes you to stagger a little.%cn', 'stumbles slightly!'),
        2: ('%crThe damage causes you to stagger even more!%cn', 'starts to stagger from the damage!'),
    }
    personal, broadcast = messages.get(level, (
        '%cr%chThe damage causes you to stagger violently while attempting to keep your footing!%cn',
        'staggers back and forth attempting to keep its footing!'))
    notify(unit, personal)
    los_broadcast(unit, broadcast)
    notify(unit, 'You stagger from the damage!')
    modifier = stagger_modifier(unit, level, getattr(engine, "stagger_tonnage", True))
    if not make_piloting_roll(unit, modifier).success:
        from physics.jump import mech_falls
        notify(unit, 'You loose the battle with gravity and tumble over!!')
        los_broadcast(unit, 'tumbles over, staggered by the damage!')
        mech_falls(unit, 1, notify_fall=False)


def legacy_modifier(unit):
    if not unit.is_started:
        return 999
    return stagger_modifier(unit, int(unit.stagger_damage / 20)) + 1


def check_stagger_event(event):
    from core.events import EventType
    from systems.sensors import los_broadcast
    unit = event.data
    from core.effects import send_debug
    send_debug(unit, f'Triggered stagger check for {unit._id}.')
    if unit.stagger_damage < 20 or unit.is_fallen or unit.unit_type != UnitType.MECH:
        stop_stagger_check(unit)
        return
    if unit.is_jumping:
        return
    notify(unit, 'You stagger from the damage!')
    if not make_piloting_roll(unit, legacy_modifier(unit)).success:
        from physics.jump import mech_falls
        notify(unit, 'You loose the battle with gravity and tumble over!!')
        los_broadcast(unit, 'tumbles over, staggered by the damage!')
        mech_falls(unit, 1, notify_fall=False)
    stop_stagger_check(unit)
    unit.stagger_damage = -10


def check_legacy_stability(unit):
    if unit.is_jumping or unit.is_fallen or unit.cocoon:
        return
    notify(unit, "You stagger from the damage!")
    if not make_piloting_roll(unit, 1).success:
        from physics.jump import mech_falls

        from systems.sensors import los_broadcast
        notify(unit, 'You fall over from all the damage!')
        los_broadcast(unit, 'falls down, staggered by the damage!')
        mech_falls(unit, 1, notify_fall=False)


def check_damage(engine, unit):
    if getattr(engine, "new_stagger", 1):
        return
    now = engine.muxevent_tick % 30
    stamped = unit.stagger_stamp >= 0
    if (
        unit.unit_type not in (UnitType.DS, UnitType.SPHEROID_DS)
        and unit.turn_damage >= 20
        and (not stamped or unit.stagger_stamp == now)
    ):
        check_legacy_stability(unit)
        unit.turn_damage = 0
        unit.stagger_stamp = now
    elif (stamped and unit.stagger_stamp == now) or (not stamped and not now):
        unit.turn_damage = 0
        unit.stagger_stamp = -1


def current_damage(unit, now, counted=False):
    return sum(
        n["amount"]
        for n in unit.stagger_damage_list
        if now - n["occurred_at"] <= 60 and bool(n["counted"]) == counted
    )


def mark_damage(unit, level):
    total = 0
    for node in unit.stagger_damage_list:
        if total >= level * 20:
            break
        if not node["counted"]:
            total += node["amount"]
            node["counted"] = True


def remove_damage(unit, level):
    total = 0
    while unit.stagger_damage_list and total < level * 20:
        total += unit.stagger_damage_list.pop(0)["amount"]


def clear_all(unit):
    unit.stagger_damage_list.clear()


def clear_expired(unit, now):
    while (
        unit.stagger_damage_list
        and now - unit.stagger_damage_list[0]["occurred_at"] >= 60
    ):
        unit.stagger_damage_list.pop(0)


def stop_stagger_check(unit):
    from core.events import EventType
    from core.effects import send_debug
    if unit._engine is not None:
        unit._engine.cancel_events_of_type(EventType.CHECK_STAGGER, unit)
    unit.stagger_damage = unit.last_stagger_notify = 0
    send_debug(unit, f'Stopping stagger check for {unit._id}.')
