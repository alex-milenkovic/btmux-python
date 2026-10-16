# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.move.c

"""Armor breaches and flooding (MechFloods/MechFloodsLoc)."""
from entities.mech import MechStatus as S, Location, UnitType, SectionConfig
from systems.movement_commands import notify
from systems.movement_commands import in_water, legs


def flood_location(unit, location, level):
    from systems.damage import destroy_parts
    section = unit.sections[location]
    if (unit.has_status(S.COMBAT_SAFE) or not section.internal or
            (section.armor and (section.rear or not section.rear_orig)) or
            not in_water(unit) or level >= 0 or unit.unit_type != UnitType.MECH or
            section.config & SectionConfig.SECTION_FLOODED):
        return False
    if level == -1 and not unit.is_fallen and location not in legs(unit):
        return False
    from systems.parts import armor_string
    from systems.notifications import mech_printf, MECHALL
    from systems.sensors import los_broadcast
    from entities.mech import CritStatus
    label = armor_string(unit, location)
    mech_printf(unit, MECHALL, '%%ch%%crWater floods into your %s disabling everything that was there!%%c', label)
    los_broadcast(unit, f'has a gaping hole in {label}, and water pours in!')
    section.config |= SectionConfig.SECTION_FLOODED
    unit.clear_crit_status(CritStatus.OWEIGHT_OK)
    destroy_parts(unit, unit, location, engine=unit._engine, breach=True, disable=True)
    return True


def flood_unit(unit):
    from systems.damage import destroy_mech, KILL_TYPE_FLOOD
    from physics.collision import mech_elevation
    if not in_water(unit) or unit.specials2 & 0x100000:
        return
    if unit.unit_type == UnitType.BSUIT:
        target = getattr(unit, 'swarm_target', None)
        if getattr(target, '_id', target if target is not None else -1) > 0:
            return
        from systems.occupants import kill_contents
        from systems.sensors import los_broadcast
        notify(unit, 'You somehow find yourself in water and realize this may really really suck...')
        notify(unit, 'Everything gets very dark as water starts to fill your suit and you sink towards the bottom!')
        los_broadcast(unit, 'shudders, splashes in the water for a second, then goes limp and sinks to the bottom.')
        kill_contents(unit)
        destroy_mech(unit, unit, showboom=False, reason=KILL_TYPE_FLOOD)
    elif unit.unit_type == UnitType.MECH:
        for location in range(len(unit.sections)):
            flood_location(unit, location, mech_elevation(unit))


def extinguish_in_water(unit):
    """Use the shared gel, expiry and smoke lifecycle on every water-entry path."""
    from systems.missile import water_extinguish_inferno
    return water_extinguish_inferno(unit._engine, unit).extinguished
