# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.tic.c
#   btech/mech.update.c
#   btech/mech.utils.c

"""Heat sink capacity and delayed cutoff commands (mech.update.c/mech.tic.c)."""
from entities.mech import CritStatus, Specials, MechStatus
from core.randomness import float32
from systems.movement_commands import notify, pending, legs


def active_capacity(unit):
    return unit.effective_heat_sinks - unit.disabled_sinks


def enable_some_sinks(unit, requested):
    amount = min(requested, unit.disabled_sinks, switching_limit(unit))
    unit.disabled_sinks -= amount
    unit.minus_heat = float32(unit.minus_heat + amount)
    return amount


def disable_some_sinks(unit, requested):
    amount = min(requested, active_capacity(unit), switching_limit(unit))
    unit.disabled_sinks += amount
    unit.minus_heat = float32(unit.minus_heat - amount)
    return amount


def switching_limit(unit):
    return 4 if unit.specials & (Specials.DOUBLE_HEAT_TECH | Specials.CLAN_TECH) else 2


def leg_heat_sinks(unit):
    from entities.crittypes import i2special, Special
    from systems.combat import part_is_nonfunctional
    return sum(slot.type == i2special(Special.HEAT_SINK)
               and not part_is_nonfunctional(unit, loc, index)
               for loc in legs(unit)
               for index, slot in enumerate(unit.sections[loc].criticals))


def heat_cutoff(engine, unit, caller=None):
    from core.effects import notify_actor
    from core.events import EventType
    actor = unit.pilot if caller is None else caller
    def reply(ok,message):
        if not getattr(message,'notified',False):notify_actor(unit,actor,message)
        return ok,message
    if not getattr(engine,'heatcutoff_enabled',True):return reply(False,'This command has been disabled.')
    error = common_checks(unit,caller,pilot_only=True)
    if error:return reply(False,error)
    if engine.has_event(EventType.HEAT_CUTOFF,unit):
        return reply(False,'You are already toggling heat cutoff status. Please be patient.')
    engage = not unit.has_crit_status(CritStatus.HEATCUTOFF)
    message = ('Engaging' if engage else 'Disengaging') + ' heat dissipation cutoff...'
    reply(True,message)
    unit._engine = engine
    unit._cutoff_event = engine.events.schedule(4,EventType.HEAT_CUTOFF,heat_cutoff_event,unit,engage)
    return True,message


def heat_cutoff_event(event):
    unit = event.data
    unit._cutoff_event = None
    if event.data2:
        notify(unit,'%cyHeat dissipation cutoff engaged!%c')
        unit.set_crit_status(CritStatus.HEATCUTOFF)
    else:
        notify(unit,'%cgHeat dissipation cutoff disengaged!%c')
        unit.clear_crit_status(CritStatus.HEATCUTOFF)


def common_checks(unit, caller=None, *, started=False, mapped=False, pilot_only=False):
    """Use the repaired common_checks owner with the command's exact flag subset."""
    from systems.combat_commands import command_guard
    return command_guard(unit, started=started, map_required=mapped,
                         pilot_only=pilot_only, caller=caller,
                         wizard=getattr(caller, 'wizard', False))
