# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.update.c

"""Per-turn stability checks and narrow dependency accounting."""

import math
from core.randomness import float32
from entities.mech import MechStatus as S, CritStatus as C, Specials, UnitType, MoveType
from systems.piloting import make_piloting_roll
from systems.movement_commands import pending, legs, MP1
from physics.cargo import cargo_max_speed
from systems.movement_commands import notify


def missing_update(unit, name):
    """Expose an unavailable production prerequisite without claiming execution."""
    if not hasattr(unit, "unavailable_updates"):
        unit.unavailable_updates = set()
    unit.unavailable_updates.add(name)


def update_pilot_skill_rolls(engine, unit):
    from systems.stagger import check_damage

    tick = engine.muxevent_tick
    boundary = (tick + (tick & 1)) % 30 == 0
    if boundary and not unit.is_fallen and not unit.is_jumping and not unit.cocoon:
        check_stability(unit)
    if unit.unit_type == UnitType.MECH:
        check_damage(engine, unit)
    else:
        unit.turn_damage = 0
    if boundary and unit.is_started and unit.move_type != MoveType.NONE:
        from systems.failures import check_generic_fail
        check_generic_fail(unit, -1)


def stability_max_speed(unit):
    maximum = float32(cargo_max_speed(unit))
    if unit.heat >= 9 and unit.specials & Specials.TRIPLE_MYOMER_TECH:
        maximum = float32(math.ceil((round(cargo_max_speed(unit) / 1.5 / MP1) + 1) * 1.5) * MP1)
    return maximum


def gravity_overspeed(unit):
    return (
        unit.has_status(S.UNDERSPECIAL)
        and unit.has_status(S.UNDERGRAVITY)
        and not pending(unit, "_mode_event")
        and unit.speed > unit.max_speed
        and unit.unit_type == UnitType.MECH
    )


def damage_overspeed_legs(unit):
    from systems.combat import apply_damage_with_transfer
    from entities.mech import Location as L

    damage = int(float32(unit.speed - unit.max_speed) / MP1 + 1)
    notify(unit, "Your legs take some damage!")
    locations = ((L.LARM, L.RARM) if unit.move_type == MoveType.QUAD else ()) + (L.LLEG, L.RLEG)
    for loc in locations:
        if not unit.is_section_destroyed(loc):
            apply_damage_with_transfer(unit, loc, damage, attacker=unit, internal=True, ignore_swarmers=True)


def check_stability(unit):
    from systems.heat import is_running

    maximum = stability_max_speed(unit)
    gravity = gravity_overspeed(unit)
    modifier = 3 if not unit.is_started else None
    if gravity or (
        is_running(unit.speed, maximum)
        and unit.has_crit_status(C.GYRO_DAMAGED | C.HIP_DAMAGED)
    ):
        modifier = 0
    if modifier is None or make_piloting_roll(unit, modifier).success:
        return
    if gravity:
        damage_overspeed_legs(unit)
    else:
        from physics.jump import mech_falls

        from systems.sensors import los_broadcast
        notify(unit, 'Your damaged mech falls as you try to run!')
        los_broadcast(unit, 'falls down.')
        mech_falls(unit, 1, notify_fall=False)
