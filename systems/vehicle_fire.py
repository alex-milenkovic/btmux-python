# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.fire.c

"""Advanced vehicle fire uses armor damage and per-side engine events."""
from core.randomness import roll as source_roll
import random
from core.events import EventType
from core.randomness import draw
from entities.mech import UnitType, MoveType
from systems.heat_control import common_checks
from systems.movement_commands import notify
from systems.movement_commands import pending
from systems.notifications import mech_printf, MECHALL
from systems.parts import armor_string
from systems.sensors import los_broadcast


def burning_sides(unit):
    return {loc:event for loc,event in getattr(unit,'_side_burns',{}).items() if not event.zombie}


def fire_die():
    return draw('fire_damage',1,6,lambda:random.randint(1,6))


def damage_side(unit,attacker,loc,damage):
    from systems.combat import apply_damage_with_transfer
    apply_damage_with_transfer(unit,loc,damage,attacker=attacker or unit,engine=unit._engine)


def arm_burn(engine,unit,loc):
    unit._side_burns[loc]=engine.events.schedule(60,EventType.VEHICLE_BURN,burn_event,unit,loc)


def start_burn(engine,unit,attacker=None):
    if engine is None:
        raise ValueError('Vehicle fire requires an owning engine')
    unit._engine=engine
    if not hasattr(unit,'_side_burns'):
        unit._side_burns={}
    notify(unit,'You catch on fire!')
    los_broadcast(unit, 'catches on fire!')
    for loc,section in enumerate(unit.sections):
        if section.internal and loc not in burning_sides(unit):
            damage=fire_die()
            mech_printf(unit, MECHALL, 'Your %s catches on fire!', armor_string(unit, loc))
            damage_side(unit,attacker,loc,damage)
            arm_burn(engine,unit,loc)


def burn_event(event):
    unit,loc=event.data,event.data2
    damage=fire_die()
    if unit is None:
        return
    unit._side_burns.pop(loc,None)
    if not unit.sections[loc].internal:
        return
    mech_printf(unit, MECHALL, '%%cr%%chYour %s takes damage from the fire!%%cn', armor_string(unit, loc))
    damage_side(unit,unit,loc,damage)
    if damage>1 and unit.sections[loc].internal:
        arm_burn(unit._engine,unit,loc)
    else:
        if unit.sections[loc].internal:
            mech_printf(unit, MECHALL, 'The fire burning on your %s finally goes out.', armor_string(unit, loc))
        if not burning_sides(unit):
            los_broadcast(unit, 'is no longer engulfed in flames.')


def extinguish(engine,unit,caller=None):
    error=common_checks(unit,caller,mapped=True)
    if error:
        return False,error
    if unit.is_started:
        return False,'Your tank is started! You can not extinguish the flames while your tank is started!'
    if not burning_sides(unit):
        return False,'This unit is not on fire!'
    if pending(unit,'_extinguish_event'):
        return False,"You're already trying to put out the fire!"
    unit._engine=engine
    notify(unit,'You begin to extinguish the fires!')
    unit._extinguish_event=engine.events.schedule(120,EventType.VEHICLE_EXTINGUISH,extinguish_event,unit)
    return True,'You begin to extinguish the fires!'


def extinguish_event(event):
    unit=event.data
    if unit is None:
        return
    unit._extinguish_event=None
    sides=burning_sides(unit)
    if sides:
        for event in sides.values():
            event.cancel()
        unit._side_burns.clear()
        notify(unit,'You manage to dowse the fire.')
        los_broadcast(unit, 'is no longer engulfed in flames.')


def check_vehicle_in_fire(engine,unit,from_hex=False,roll=None):
    if roll is None:
        roll=source_roll('fire_rolls', lambda:random.randint(1,6)+random.randint(1,6))
    roll += 2 if unit.move_type in (MoveType.WHEEL,MoveType.VTOL) else 4 if unit.move_type==MoveType.HOVER else 0
    if roll<8:
        return 'NONE'
    notify(unit,'%cr%chYou drive through a wall of searing flames!%cn' if from_hex else '%cr%chThe fires surround your vehicle!%cn')
    if roll<10:
        if unit.unit_type==UnitType.VTOL:
            return 'NONE'
        notify(unit, '%cr%chThe fire damages your motive system!%cn')
        from systems.vehicle_combat import motive_system_hit
        motive_system_hit(unit)
        return 'MOTIVE_HIT'
    if roll<12:
        notify(unit, '%cr%chThe fire sweeps across your unit damaging it!%cn')
        for loc,section in enumerate(unit.sections):
            damage=fire_die()
            if section.internal:
                damage_side(unit,unit,loc,damage)
        return 'SECTION_DAMAGE'
    start_burn(engine,unit)
    return 'BURNING'
