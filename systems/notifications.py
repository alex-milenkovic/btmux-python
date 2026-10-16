# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.notify.c
#   btech/src/glue.c

"""Source notification audiences with delivery to ordered local occupants.

Inboxes retain raw source text. Configured local forwarding, listeners and
client render/transport callbacks execute through the owning effect service.
"""
from entities.mech import MechStatus as S

MECHPILOT, MECHSTARTED, MECHALL = 0, 1, 2
# Both configured BTPR adapters define these source allocations.
LBUF_SIZE, MBUF_SIZE, SBUF_SIZE = 16384, 2048, 256


# glue.c mecha_notify / mecha_notify_except source delivery flags.
MSG_ME, MSG_COLORIZE = 2048, 16384
PERSONAL_FLAGS = MSG_ME | MSG_COLORIZE
CONTENTS_FLAGS = MSG_ME | 4 | 8192 | MSG_COLORIZE
NUM_TURRETS = 3


def source_string(text):
    """The supported C string domain, terminated at the first NUL."""
    from systems.parts import source_text
    return source_text(text)


def _printf_integer(value, kind, flags, width, precision):
    """C integer digits, precision, sign/prefix and field padding."""
    signed = kind in 'di'
    prefix = ('-' if value < 0 else '+' if '+' in flags else ' ' if ' ' in flags else '') if signed else ''
    digits = format(abs(value), 'd' if kind in 'diu' else kind)
    if value == 0 and precision == 0:
        digits = ''
    digits = digits.rjust(precision or 0, '0')
    if '#' in flags:
        if kind == 'o' and not digits.startswith('0'):
            digits = '0' + digits
        elif kind in 'xX' and value:
            prefix = '0' + kind
    padding = max(0, width - len(prefix) - len(digits))
    if '-' in flags:
        return prefix + digits + ' ' * padding
    if '0' in flags and precision is None:
        return prefix + '0' * padding + digits
    return ' ' * padding + prefix + digits


def source_printf(template, *args):
    """Supported C printf conversions; unused variadic arguments are legal."""
    import re
    template = source_string(template)
    conversion = re.compile(r'%([-+ #0]*)(\*|[0-9]*)(\.(?:\*|[0-9]*))?(hh|ll|[hlLzjt])?([diuoxXfFeEgGcs%])')
    pieces, position, used = [], 0, 0

    def argument():
        nonlocal used
        if used >= len(args):
            raise ValueError('Missing printf argument')
        value = args[used]
        used += 1
        return value

    while position < len(template):
        if template[position] != '%':
            end = template.find('%', position)
            end = len(template) if end < 0 else end
            pieces.append(template[position:end]); position = end
            continue
        match = conversion.match(template, position)
        if match is None:
            raise ValueError('Unsupported source printf conversion')
        flags, width, precision, length, kind = match.groups()
        position = match.end()
        if kind == '%':
            if flags or width or precision or length:
                raise ValueError('Invalid source percent conversion')
            pieces.append('%'); continue
        width = int(argument()) if width == '*' else int(width or 0)
        precision = (int(argument()) if precision == '.*' else int(precision[1:] or 0)) if precision else None
        if width < 0:
            flags += '-'
            width = -width
        if precision is not None and precision < 0:
            precision = None
        value = argument()
        if kind in 'diuoxX':
            bits = 64 if length in ('ll', 'l', 'z', 'j', 't') else 8 if length == 'hh' else 16 if length == 'h' else 32
            value = int(value) % (1 << bits)
            if kind in 'di' and value >= 1 << (bits - 1): value -= 1 << bits
            pieces.append(_printf_integer(value, kind, flags, width, precision))
            continue
        if kind == 's' or kind == 'c' and isinstance(value, str):
            value = source_string(value)
        form = '%' + flags + (str(width) if width else '') + ('.' + str(precision) if precision is not None else '') + kind
        try:
            pieces.append(form % value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError('Invalid source printf arguments') from error
    return source_string(''.join(pieces))


def personal_notify(actor, message, *, sender=None, flags=PERSONAL_FLAGS, _path=()):
    if actor is None:
        return False
    message = message.split('\0', 1)[0]
    if not message or id(actor) in _path:
        return False
    if not hasattr(actor, 'inbox'):
        actor.inbox = []
    actor.inbox.append(message)
    if not hasattr(actor, 'notification_requests'):
        actor.notification_requests = []
    request = dict(service='local notify_checked forwarding/listeners/client transport',
                   recipient=getattr(actor, '_id', -1), message=message,
                   sender=getattr(actor, '_id', -1) if sender is None else sender,
                   flags=flags, applied=False)
    actor.notification_requests.append(request)
    from core.effects import effect_sink
    sink = effect_sink(actor)
    if sink is not None:
        sink.notify(actor, request, _path + (id(actor),))
        request['applied'] = True
    return True


def deliver(unit, audience, message):
    if unit.is_unconscious or unit.has_status(S.BLINDED) or unit._id < 0:
        return []
    world = getattr(getattr(unit, '_engine', None), 'personnel', None)
    pilot = getattr(unit, 'pilot', None)
    if audience == MECHPILOT:
        if (pilot is not None and getattr(pilot, '_id', 0) > 0
                and getattr(pilot, 'location', None) == unit._id):
            return [pilot._id] if personal_notify(pilot, message) else []
        audience = MECHALL
    allowed = ((audience == MECHALL and not unit.is_destroyed)
               or (audience == MECHSTARTED and unit.is_started))
    if not allowed or world is None:
        return []
    containers = [unit._id]
    if getattr(unit._engine, 'arc_override', 0):
        containers.extend(i for i in getattr(unit, 'aero_turrets', [])[:NUM_TURRETS] if i > 0)
    recipients = []
    for container in containers:
        for ident in world.contents(container):
            if ident == container:
                continue
            actor = world.objects.get(ident)
            if actor is not None and personal_notify(actor, message, sender=-5, flags=CONTENTS_FLAGS):
                recipients.append(ident)
    return recipients


def mech_notify(unit, audience, message):
    # Retain the existing diagnostic log/hook independently of recipient gates.
    from systems.movement_commands import notify
    notify(unit, message, audience=None)
    return deliver(unit, audience, message)


def mech_printf(unit, audience, template, *args):
    if unit.is_unconscious or unit.has_status(S.BLINDED) or unit._id < 0:
        return []
    return mech_notify(unit, audience, source_printf(template, *args)[:LBUF_SIZE - 1])


def identity_base(viewer, target, identified):
    if target is None or target._id < 0 or not getattr(target, 'valid', True):
        return ''
    name = target.name if identified else 'something'
    contact = target.contact_id
    if identified and viewer.team == target.team:
        contact = contact.lower()
    return f'{name} [{contact}]'[:SBUF_SIZE - 1]


def identity(viewer, target):
    from systems.los import in_line_of_sight_nb
    if viewer is None or target is None or target._id < 0 or not getattr(target, 'valid', True):
        return ''
    return identity_base(viewer, target, bool(in_line_of_sight_nb(viewer, target, 0, 0, 0)))


def object_name(obj):
    """Database Name, distinct from the unit's MECHNAME/contact display."""
    return getattr(obj,'object_name',obj.name)


def unit_identity(unit):
    if unit is None or unit._id < 0 or not getattr(unit, 'valid', True):
        return ''
    from systems.parts import mech_ids
    return f'{unit.name} [{mech_ids(unit)}]'[:SBUF_SIZE - 1]


def room_notify(board, message, exception=None):
    """Local notify_except: address room contents, including non-unit objects."""
    engine = getattr(board, '_engine', None)
    world = getattr(engine, 'personnel', None)
    objects = dict(getattr(world, 'objects', {}))
    if engine is not None:
        for obj in engine.get_entities():
            objects.setdefault(getattr(obj, '_id', -1), obj)
    identities = world.contents(board._id) if world is not None else []
    identities += [ident for ident, obj in objects.items()
                   if getattr(obj, 'location', None) == board._id and ident not in identities]
    recipients = []
    for ident in identities:
        if ident == exception or ident not in objects:
            continue
        personal_notify(objects[ident], message)
        recipients.append(ident)
    return recipients


def map_broadcast(board, message, source=None, target=None):
    if board is None:
        return
    for unit in board.mechs_on_map:
        if unit is not None and unit is not source and unit is not target:
            mech_notify(unit, MECHSTARTED, message)


def limited_broadcast(board, x, y, z, radius, message, dimensions=3):
    from systems.targeting import find_range
    import math
    from core.randomness import float32
    if not math.isfinite(radius):
        raise ValueError('Broadcast radius must be a finite source float')
    try:
        radius = float32(radius)
    except OverflowError as error:
        raise ValueError('Broadcast radius exceeds source float range') from error
    if not math.isfinite(radius):
        raise ValueError('Broadcast radius exceeds source float range')
    count = 0
    for unit in board.mechs_on_map:
        if unit is None or dimensions == 2 and unit._id < 0 or dimensions == 3 and unit._id == -1:
            continue
        distance = find_range(x, y, 0 if dimensions == 2 else z,
                              unit.fx, unit.fy, 0 if dimensions == 2 else unit.fz)
        if distance <= radius:
            count += 1
            mech_notify(unit, MECHSTARTED, message)
    return count


def sees_hex(unit, board, x, y, fx=None, fy=None):
    from systems.los import in_line_of_sight
    from systems.targeting import find_range
    from physics.hexmath import hex_to_float, ZSCALE
    if fx is None:
        fx, fy = hex_to_float(x, y)
    distance = find_range(unit.fx, unit.fy, unit.fz, fx, fy, board.base_elevation(x,y) * ZSCALE)
    return in_line_of_sight(unit, None, x, y, distance)


def _hex_expansion(message, plain, alert):
    """Validate source writes, including substitution NULs and final '$'."""
    pieces, index, size = [], 0, 0
    while index < len(message):
        token = message[index:index + 2]
        if token in ('$h', '$H'):
            text = plain if token == '$h' else alert
            size += len(text)
            # strcpy/snprintf writes a temporary terminator at this position.
            if size >= LBUF_SIZE:
                raise ValueError('Hex broadcast expansion exceeds source buffer')
            pieces.append(text)
            index += 2
        else:
            if size >= LBUF_SIZE:
                raise ValueError('Hex broadcast expansion exceeds source buffer')
            pieces.append(message[index])
            size += 1
            index += 1
    if pieces[-1] == '$':
        pieces.pop()
        size -= 1
    if size >= LBUF_SIZE:
        raise ValueError('Hex broadcast expansion exceeds source buffer')
    return ''.join(pieces)


def hex_broadcast(board, x, y, message):
    if board is None:
        return
    from physics.hexmath import hex_to_float
    message = source_string(message)
    if not message:
        raise ValueError('Empty hex broadcast is outside the defined source buffer domain')
    fx, fy = hex_to_float(x, y)
    for unit in board.mechs_on_map:
        if unit is None or not sees_hex(unit, board, x, y, fx, fy):
            continue
        same = (unit.x, unit.y) == (x, y)
        plain = 'your hex' if same else f'{x},{y}'
        alert = '%ch%crYOUR HEX%cn' if same else f'%ch%cy{x},{y}%cn'
        mech_notify(unit, MECHSTARTED, _hex_expansion(message, plain, alert))


def pair_los_broadcast(source, target, template):
    from systems.sensors import possibly_see_mech
    from systems.los import in_line_of_sight
    from systems.targeting import fa_mech_range
    if source.map is None:
        return
    possibly_see_mech(source)
    possibly_see_mech(target)
    for observer in source.map.mechs_on_map:
        if observer is None or observer is source or observer is target:
            continue
        a = in_line_of_sight(observer,source,source.x,source.y,fa_mech_range(observer,source))
        b = in_line_of_sight(observer,target,target.x,target.y,fa_mech_range(observer,target))
        if not a and not b:
            continue
        text = source_printf(template, identity(observer,target) if b else 'someone')[:LBUF_SIZE - 1]
        text = (identity(observer,source) if a else 'Someone') + ('' if text.startswith("'") else ' ') + text
        mech_notify(observer, MECHSTARTED, text[:LBUF_SIZE - 1])
