# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.startup.c

"""Common C combat command checks and Readnum parsing."""
import re


class NotifiedError(str):
    """A structured error whose source notice was already delivered."""
    notified = True


def read_number(text):
    match = re.match(r'\s*([+-]?\d+)', text)
    value = int(match.group(1)) if match else 0
    if not value and text != '0':
        raise ValueError('Invalid number!')
    return value


def reset_invalid_map(unit, actor, *, wizard=False):
    """common_checks: notify, run shutdown including refusals, then reset."""
    from core.effects import notify_actor
    from systems.startup import shutdown
    error=NotifiedError('You are on an invalid map! Map index reset!')
    notify_actor(unit,actor,error)
    wizard=wizard or actor==1 or getattr(actor,'_id',-1)==1 or getattr(actor,'wizard',False) or getattr(actor,'god',False)
    ok,message=shutdown(unit._engine,unit,caller=actor,wizard=wizard)
    if not ok and message:notify_actor(unit,actor,message)
    unit.mapindex=-1
    return error


def command_guard(unit, *, started=True, map_required=True, pilot_only=True,
                  caller=None, wizard=False, check_blind=True):
    """common_checks flags; omitted caller denotes the current pilot."""
    from entities.mech import MechStatus as S
    if unit is None:
        return 'Invalid unit!'
    unit.last_use=0
    if started:
        if unit.is_destroyed:
            return 'You are destroyed!'
        if not unit.is_started:
            return 'Reactor is not online!'
    if check_blind and unit.has_status(S.BLINDED):
        return 'You are momentarily blinded!'
    actor=unit.pilot if caller is None else caller
    same_pilot = (actor is unit.pilot or (actor is not None and unit.pilot is not None
                  and isinstance(getattr(actor, '_id', actor), int)
                  and getattr(actor, '_id', actor) >= 0
                  and getattr(actor, '_id', actor) == getattr(unit.pilot, '_id', unit.pilot)))
    if unit.is_unconscious and (not unit.is_started or same_pilot):
        return 'You are unconscious....zzzzzzz'
    if pilot_only and not wizard and unit.in_character and not same_pilot:
        return 'Now now, only the pilot can push that button.'
    if map_required:
        from systems.targeting import indexed_map
        if unit.mapindex >= 0 and indexed_map(unit) is None:
            return reset_invalid_map(unit,actor,wizard=wizard)
        if unit.mapindex < 0:
            return 'You are on no map!'
        unit.map = indexed_map(unit)
    return None


def parse_attributes(text, maximum):
    """mech_parseattributes/strtok uses space and tab only, with a token cap."""
    return re.findall(r'[^ \t]+', str(text))[:maximum]


def command_message(unit, text, *, caller=None, audience=None):
    """Deliver one source notice, retaining already-delivered guard errors."""
    if unit is not None and not getattr(text, 'notified', False):
        if audience is None:
            from core.effects import notify_actor
            notify_actor(unit, unit.pilot if caller is None else caller, text)
        else:
            from systems.notifications import mech_notify
            mech_notify(unit, audience, text)
    return NotifiedError(text)


class CommandMessages(list):
    """Selector errors are personal; callbacks explicitly select unit notices."""
    def __init__(self, iterable=(), *, unit=None, caller=None):
        super().__init__(iterable)
        self.owner = unit
        self.caller = caller

    def append(self, text):
        super().append(command_message(self.owner, text, caller=self.caller))

    def unit(self, text, audience=2):
        super().append(command_message(self.owner, text, audience=audience))
