# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_radio.c
#   btech/mech.notify.c

"""Source communications command checks and radio operations."""
from entities.mech import MechStatus as S
from systems.notifications import LBUF_SIZE
import re

FREQ_DIGITAL, FREQ_MUTE, FREQ_RELAY, FREQ_INFO, FREQ_SCAN, FREQ_REST = 1, 2, 4, 8, 16, 32
RADIO_RELAY, RADIO_INFO, RADIO_SCAN, RADIO_NODIGITAL = 1, 2, 4, 8
COLORS = 'xrgybmcwXRGYBMCW'

MECH_STARTED = 1
MECH_PILOT = 2
MECH_PILOT_CON = 4
MECH_MAP = 8
MECH_CONSISTENT = 16
MECH_PILOTONLY = 32
MECH_USUALSP = 28
MECH_USUALSM = 22
MECH_USUAL = 31
MECH_USUALS = 30
MECH_USUALO = 63


def common_checks(unit, actor, flags):
    """None permits the command; any string rejects it.

    An empty string is a silent failure or a notice already delivered before
    side effects. Callers must test `is not None` and must not re-emit empties.
    """
    if unit is None:
        return ''
    if flags & MECH_CONSISTENT and not getattr(unit, 'allocated', True):
        return 'Invalid unit!'
    unit.last_use = 0
    if flags & MECH_STARTED:
        if unit.is_destroyed:
            return 'You are destroyed!'
        if not unit.is_started:
            return 'Reactor is not online!'
    if flags & MECH_PILOT and unit.has_status(S.BLINDED):
        return 'You are momentarily blinded!'
    pilot = unit.pilot
    is_pilot = actor is pilot or (actor is not None and pilot is not None
                                 and getattr(actor, '_id', None) == getattr(pilot, '_id', -1))
    if flags & MECH_PILOT_CON and unit.is_unconscious and (not unit.is_started or is_pilot):
        return 'You are unconscious....zzzzzzz'
    if (flags & MECH_PILOTONLY and not getattr(actor, 'wizard', False)
            and unit.in_character and not is_pilot):
        return 'Now now, only the pilot can push that button.'
    if flags & MECH_MAP:
        if unit.mapindex < 0:
            return 'You are on no map!'
        from systems.targeting import indexed_map
        board = indexed_map(unit)
        engine = getattr(unit, '_engine', None)
        if board is None:
            from systems.startup import shutdown
            from systems.notifications import personal_notify
            personal_notify(actor, 'You are on an invalid map! Map index reset!')
            if engine is not None:
                ok, message = shutdown(engine, unit, caller=actor,
                                       wizard=getattr(actor, 'wizard', False))
                if not ok and message:
                    personal_notify(actor, message)
            unit.mapindex = -1
            return ''
        unit.map = board
    return None


def channels(unit):
    value = getattr(unit, 'radio_type', 0)
    if value < 0:
        raise ValueError('Negative encoded radio type is outside the supported domain')
    count = value % 16
    for name, empty in (('freq', 0), ('freqmodes', 0), ('chantitle', '')):
        values = list(getattr(unit, name, []))
        values.extend([empty] * max(0, count - len(values)))
        setattr(unit, name, values)
    return count


def capability(unit):
    channels(unit)
    return getattr(unit, 'radio_type', 0) // 16


def setter_arguments(unit, text):
    text = text.lstrip()
    if not text:
        raise ValueError('Invalid input!')
    index = ord(text[0].upper()) - ord('A')
    if not 0 <= index < channels(unit):
        raise ValueError('Invalid channel-letter!')
    text = text[1:].lstrip()
    if not text:
        raise ValueError('Invalid input!')
    if text[0] != '=':
        raise ValueError('Missing =!')
    return index, text[1:].lstrip()


def set_frequency(unit, text, actor=None):
    board = unit.map
    try:
        index, value = setter_arguments(unit, text)
        if not value:
            raise ValueError('Invalid input!')
        match = re.match(r'[+-]?\d+', value)
        frequency = int(match[0]) if match else 0
        if not frequency and value != '0':
            raise ValueError('Invalid frequency!')
        if frequency < 0:
            raise ValueError('Are you trying to kid me?')
        if frequency > 999999:
            raise ValueError('Invalid frequency - range is from 0 to 999999.')
    except ValueError as error:
        return dict(ok=False, error=str(error))
    from core.effects import notify_actor
    actor = actor if actor is not None else getattr(unit, 'command_actor', unit.pilot)
    message = f'Channel {chr(65 + index)} set to {frequency}.'
    notify_actor(unit, actor, message)
    unit.freq[index] = frequency
    if frequency and board is not None:
        for peer in board.mechs_on_map:
            if peer is None or peer is unit or peer.team == unit.team:
                continue
            for i in range(channels(peer)):
                if peer.freq[i] == frequency and not peer.freqmodes[i] & FREQ_SCAN:
                    external_request(unit, 'MechFreqs', f'ALERT: Possible abuse by #{unit._id} (Team {unit.team}) setting freq {frequency} matching #{peer._id} (Team {peer.team})!')
    return dict(ok=True, message=message, notified=True)


def set_title(unit, text):
    try:
        index, title = setter_arguments(unit, text)
        raw = title.encode('ascii')
    except (ValueError, UnicodeError) as error:
        return dict(ok=False, error=str(error))
    unit.chantitle[index] = raw[:15].decode('ascii')
    message = f'Channel {chr(65 + index)} title '
    message += f'set to set to {title}.' if title else 'cleared.'
    return dict(ok=True, message=message[:LBUF_SIZE - 1])


def set_mode(unit, text):
    try:
        index, value = setter_arguments(unit, text)
        mode = 0
        for char in value:
            upper = char.upper()
            requirements = {'D': (RADIO_NODIGITAL, True, "Your radio can't handle digital frequencies!"),
                            'I': (RADIO_INFO, False, 'This unit is unable to use info functionality.'),
                            'E': (RADIO_RELAY, False, 'This unit is unable to relay.'),
                            'S': (RADIO_SCAN, False, 'This unit is unable to scan.')}
            if upper in requirements:
                flag, forbidden, error = requirements[upper]
                if bool(capability(unit) & flag) == forbidden:
                    raise ValueError(error)
            if upper in 'DIUES':
                mode |= dict(D=1, I=8, U=2, E=4, S=16)[upper]
            elif char in COLORS:
                mode = mode % FREQ_REST + (COLORS.index(char) + 1) * FREQ_REST
            else:
                break
        if not mode & FREQ_DIGITAL:
            if mode & FREQ_RELAY:
                raise ValueError('Error: Need digital transfer for relay to work.')
            if mode & FREQ_INFO:
                raise ValueError('Error: Need digital transfer for transfer info to work.')
    except ValueError as error:
        return dict(ok=False, error=str(error))
    unit.freqmodes[index] = mode
    message = f'Channel {chr(65 + index)} <send> mode set to '
    if not value:
        return dict(ok=True, message=message + 'analog.')
    flags = ''.join(char for char, bit in (('I',8), ('U',2), ('E',4), ('S',16)) if mode & bit) or '-'
    if mode // FREQ_REST:
        flags += '/color:' + COLORS[mode // FREQ_REST - 1]
    return dict(ok=True, message=message + ('digital' if mode & 1 else 'analog') + f' (flags:{flags}).')


def color_code(unit, index, observer=False, team=0):
    channels(unit)
    state = getattr(unit, '_engine', None) or unit
    result = getattr(state, '_radio_color_buffer', '')
    if observer:
        if team > 15:
            team %= 15
        table = ('%cw','%cc','%cm','%cb','%cy','%cg','%cr','%ch%cx','%ch%cw','%ch%cc','%ch%cm','%ch%cb','%ch%cy','%ch%cg','%ch%cr')
        if 1 <= team <= 15:
            result = table[team - 1][:5]
    else:
        color = unit.freqmodes[index] // FREQ_REST
        if not 0 <= color <= len(COLORS):
            raise ValueError('Radio color exceeds allocated source color table')
        result = '' if not color else (('%c' + COLORS[color - 1]) if color < 9 else ('%ch%c' + COLORS[color - 1].lower()))[:5]
    state._radio_color_buffer = result
    return result


def list_frequencies(unit):
    rows = ['# -- Mode -- Frequency -- Comtitle']
    for i in range(channels(unit)):
        mode = unit.freqmodes[i]
        if not 0 <= mode // 32 <= 16:
            raise ValueError('Radio color exceeds allocated source color table')
        flags = ('D' if mode & 1 else 'A') + ('R' if mode & 4 else '-') + ('M' if mode & 2 else '-')
        flags += 'S' if mode & 16 else COLORS[mode // 32 - 1] if mode >= 32 else 'I' if mode & 8 else '-'
        rows.append(f'{chr(65+i)}    {flags}    {unit.freq[i]:<9d}    {unit.chantitle[i]}')
    return rows


def parse_attributes(text):
    args = []
    while len(args) < 2 and text:
        if text[0] == '=':
            args.append('=')
            text = text[1:]
            continue
        match = re.search(r'[ \t=]', text)
        length = match.start() if match else len(text)
        args.append(text[:length])
        text = text[length:]
        if text and text[0] != '=':
            text = text[1:]
    if text:
        args.append(text)
    return args


def parse_channel_send(unit, text):
    args = parse_attributes(text)
    error = 'Invalid format! Usage: sendchannel <letter>=<string>'
    if len(args) != 3 or len(args[0]) > 1:
        raise ValueError(error)
    char = args[0]
    index = 0
    if char and 'a' <= char <= 'z':
        index = ord(char) - ord('a')
    if char and 'A' <= char <= 'Z':
        index = ord(char) - ord('Z')
    if not 0 <= index < channels(unit):
        raise ValueError(error)
    if any(ord(char) < 32 or ord(char) > 127 for char in args[2]):
        raise ValueError('Invalid: No control characters in radio messages, please.')
    return index, args[2]


def route_graph(edges, recursive=False):
    """Literal source DFS order, including last-equal winner and backup depth."""
    count = len(edges)
    if count < 2 or count > 250 or any(len(row) != count for row in edges):
        raise ValueError('Invalid or unsupported communication graph array')
    best, best_path, iterations = 9999, [], 0
    done = [False] * count
    path, loops = [0] * count, [0] * count

    def backup():
        # Explicit frames avoid Python's smaller recursion ceiling while keeping
        # each recursive invocation/return and its 10000-entry bound unchanged.
        nonlocal best, best_path
        entries = 0
        stack = [(0, 0, 1, False)]
        while stack:
            node, depth, start, entered = stack.pop()
            if not entered:
                entries += 1
                if entries > 10000 or depth >= best:
                    if depth:
                        done[node] = False
                    continue
                path[depth] = node
            for j in range(start, count):
                if edges[node][j] and not done[j]:
                    if j == count - 1:
                        best, best_path = depth, path[:depth]
                    else:
                        done[j] = True
                        stack.append((node, depth, j + 1, True))
                        stack.append((j, depth + 1, 1, False))
                        break
            else:
                if depth:
                    done[node] = False
        return entries

    if recursive:
        iterations = backup()
    else:
        depth = 0
        loops[0] = 1
        while depth >= 0:
            node = path[depth]
            j = loops[depth]
            while j < count:
                if edges[node][j] and not done[j]:
                    if j == count - 1:
                        best, best_path = depth + 1, path[:depth + 1]
                        j = count
                        break
                    if depth + 1 < best:
                        done[j] = True
                        loops[depth] = j + 1
                        depth += 1
                        loops[depth], path[depth] = 1, j
                        break
                j += 1
            if j == count:
                if depth > 0:
                    depth -= 1
                    done[loops[depth] - 1] = False
                else:
                    depth -= 1
            iterations += 1
            if iterations == 100001:
                best, best_path = 9999, []
                done[:] = [False] * count
                backup()
                break
    return dict(path=best_path, best=best, iterations=iterations) if best != 9999 else None


def find_comm_link(board, sender, receiver, frequency, recursive=False):
    from entities.mech import MoveType
    from systems.targeting import fa_mech_range
    peers = [sender]
    for unit in board.mechs_on_map:
        if unit is None or unit is sender or unit is receiver or unit.team != sender.team:
            continue
        if unit.move_type != MoveType.NONE and not unit.is_started or unit.move_type == MoveType.NONE and unit.is_destroyed:
            continue
        if not capability(unit) & RADIO_RELAY:
            continue
        for i in range(channels(unit)):
            if unit.freq[i] == frequency and unit.freqmodes[i] & FREQ_RELAY:
                peers.append(unit)
    peers.append(receiver)
    if len(peers) == 2:
        return None
    edges = [[i != j and fa_mech_range(origin, destination) <= origin.radio_range
              for j, destination in enumerate(peers)] for i, origin in enumerate(peers)]
    result = route_graph(edges, recursive)
    if result is None:
        return None
    return dict(result, indexes=result['path'], path=[peers[i]._id for i in result['path']],
                candidates=[u._id for u in peers])


def external_request(unit, service, operation):
    """Preserve distinct ordered source calls, even identical channel requests."""
    if not hasattr(unit, 'external_effects'):
        unit.external_effects = []
    request = dict(service=service, operation=operation, applied=False)
    unit.external_effects.append(request)
    channel = {'AI': 'MechAI', 'MechFreqs': 'MechFreqs', 'ZeroFrequencies': 'ZeroFrequencies'}.get(service)
    if channel is not None:
        from core.effects import emit_channel
        result = emit_channel(unit, channel, operation)
        request['applied'] = result['applied']
    return request


def radio_number(low, high):
    from core.randomness import draw, number
    if low > high:
        raise ValueError('Invalid source radio Number range')
    return draw('radio_number', low, high, lambda: number(low, high))


def do_scramble(message, chance, bth):
    from core.randomness import roll
    result = []
    for byte in message.encode('latin1'):
        if byte >= 128:
            raise ValueError('Source signed-char scrambling overflow is unsupported')
        value = byte
        if radio_number(1, 100) > chance and roll('radio_roll') < bth + 5:
            sign = -1 if radio_number(1, 2) == 1 else 1
            value += sign * radio_number(1, 10)
            if not -128 <= value <= 127:
                raise ValueError('Source signed-char scrambling overflow is unsupported')
        result.append(chr(min(255, max(33, value))))
    return ''.join(result)


def scramble_message(message, distance, sender_range, receiver_range, title='', bth=0,
                     under_ecm=False, digital=0, path=()):
    from physics.hexmath import find_bearing
    header = ''
    if digital > 1 and len(path) > 1:
        nodes = []
        for previous, relay in zip(path, path[1:]):
            bearing = int(find_bearing(relay.fx, relay.fy, previous.fx, previous.fy))
            nodes.append(f'[{relay.contact_id}]-h:{bearing:03d}')
        header = '{R-path:' + '/'.join(nodes) + '} '
    text = (header + (f'<{title}> ' if title else '') + message)[:LBUF_SIZE - 1]
    xp = False
    if not digital:
        maximum = max(receiver_range, int((sender_range + receiver_range) / 2))
        if distance > sender_range:
            text = do_scramble(text, int(100 * sender_range / max(1, distance)), bth)
            xp = True
        if distance > maximum:
            chance = 100 - int((100 - int(100 * maximum / max(1, distance))) / 2)
            text = do_scramble(text, chance, bth)
            xp = True
    if under_ecm and distance >= 1:
        text = do_scramble(text, radio_number(30, 50), bth)
        xp = True
    return text, xp


def scan(receiver, frequency, message):
    from systems.notifications import mech_notify, MECHALL
    length = len(message.encode('ascii'))
    noticed = False
    for i in range(channels(receiver)):
        if not receiver.freqmodes[i] & FREQ_SCAN:
            continue
        if radio_number(1, 100) > min(80, length):
            continue
        if not noticed:
            mech_notify(receiver, MECHALL, 'You notice a unknown transmission your scanner.. ')
            noticed = True
        difference = abs(frequency - receiver.freq[i])
        if not difference:
            raise ValueError('Source scanner percentage divides by zero')
        step = max(1, radio_number(1, min(99, length)) * difference // 100)
        percent = step * 100 // difference
        accuracy = 'somewhat' if percent < 30 else 'fairly well' if percent < 60 else 'precisely' if percent < 95 else 'exactly'
        mech_notify(receiver, MECHALL, f'Your systems manage to zero on it {accuracy} on channel {chr(65+i)}.')
        receiver.freq[i] += step if receiver.freq[i] < frequency else -step


def autopilot_receive(unit, channel, message):
    from systems.ecm import ecm_disturbed
    from systems.targeting import resolve_object
    ident = unit.autopilot
    if ident <= 0 or not unit.freq[channel]:
        return
    obj = resolve_object(unit, ident)
    if obj is None or not getattr(obj, 'allocated', True):
        unit.autopilot = -1
    elif getattr(obj, 'location', -1) != unit._id:
        external_request(unit, 'AI', f'Autopilot #{ident} (Location: #{obj.location}) reported on Mech #{unit._id} but not in the proper location')
    elif not ecm_disturbed(unit):
        request = external_request(unit, 'autopilot parser', dict(autopilot=ident, channel=channel, message=message))
        engine = getattr(unit, '_engine', None)
        from systems.autopilot import autopilot_service
        parser = autopilot_service(engine,'radio',obj) if engine is not None else None
        if parser is not None:
            parser(obj, unit, channel, message)
            request['applied'] = True
        else:
            request['dependency'] = 'Deferred AUTO command parser; configure engine.auto_services[radio]'


def auto_reply_event(event):
    from entities.mech import Mech
    from systems.targeting import indexed_map, resolve_object
    unit = event.data
    if (not isinstance(unit, Mech) or not getattr(unit, 'hardcode', True)
            or getattr(unit, 'xcode_type', 'MECH') != 'MECH'
            or resolve_object(unit, unit._id) is not unit):
        return
    board = indexed_map(unit)
    if board is not None:
        unit.map = board
        transmit(unit, 0, event.data2)


def auto_reply(unit, message):
    from systems.targeting import resolve_object
    from core.events import EventType
    from core.randomness import draw, number
    channels(unit)
    # freq[0] is a stored source slot even on a radio with no usable channels.
    if not getattr(unit, 'freq', []) or not unit.freq[0] or unit.autopilot <= 0:
        return None
    obj = resolve_object(unit, unit.autopilot)
    if (obj is None or not getattr(obj, 'allocated', True)
            or not getattr(obj, 'valid', True) or not getattr(obj, 'valid_object', True)
            or getattr(obj, 'location', -1) != unit._id):
        unit.autopilot = -1
        return None
    engine = getattr(unit, '_engine', None)
    if engine is None:
        raise ValueError('Autopilot reply requires an owning engine')
    delay = draw('radio_reply_delay', 1, 2, lambda: number(1, 2), state=engine.randomness)
    return engine.schedule_event(delay, EventType.AUTO_REPLY, auto_reply_event, data=unit, data2=message)


def transmit(sender, channel, message):
    from entities.mech import CritStatus
    from systems.ecm import any_ecm_disturbed
    from systems.notifications import mech_notify, MECHALL
    from systems.targeting import fa_mech_range, resolve_unit
    from physics.hexmath import find_bearing
    board = sender.map
    channels(sender)
    if len(message.encode('latin1')) >= LBUF_SIZE:
        raise ValueError('Radio message exceeds source input buffer')
    if not sender.radio_range:
        return []
    if board is None:
        raise ValueError('Radio transmission requires a resolved map')
    observations = []
    for receiver in board.mechs_on_map:
        if receiver is None or receiver._id == 2 or receiver.is_destroyed:
            continue
        digital = bool(sender.freqmodes[channel] & FREQ_DIGITAL)
        observer = bool(receiver.crit_status & CritStatus.OBSERVATORIC)
        distance = int(fa_mech_range(sender, receiver))
        bearing = int(find_bearing(receiver.fx, receiver.fy, sender.fx, sender.fy))
        selected = next((i for i in range(channels(receiver))
                         if (receiver.freq[i] == sender.freq[channel] or observer)
                         and not receiver.freqmodes[i] & FREQ_MUTE
                         and not (digital and capability(receiver) & RADIO_NODIGITAL)), None)
        if selected is None:
            if not digital and capability(receiver) & RADIO_SCAN and sender.freq[channel]:
                scan(receiver, sender.freq[channel], message)
            continue
        if observer:
            color = color_code(receiver, selected, True, sender.team)
            bracket = f'[{chr(65+selected)}:{bearing}]' if digital else f'({chr(65+selected)}:{bearing})'
            text = f'{color}{bracket} <{getattr(sender,"faction","")}:{sender.contact_id}:{sender.freq[channel]}> <{sender.chantitle[channel]}> {message}%c'
            text = text[:LBUF_SIZE - 1]
            recipients = mech_notify(receiver, MECHALL, text)
            observations.append(dict(unit=receiver._id, channel=selected, text=text, recipients=recipients, observer=True))
        autopilot_receive(receiver, selected, message)
        digital = bool(sender.freqmodes[channel] & FREQ_DIGITAL)
        if not receiver.radio_range:
            continue
        path = [sender]
        if digital:
            if distance > sender.radio_range:
                route = find_comm_link(board, sender, receiver, sender.freq[channel])
                if route is None:
                    continue
                path = [resolve_unit(sender, ident) for ident in route['path']]
            if receiver is not sender and (any_ecm_disturbed(sender) or any_ecm_disturbed(receiver)):
                continue
            mode = 2 if receiver.freqmodes[selected] & FREQ_INFO else 1
            text, xp = scramble_message(message, distance, sender.radio_range, sender.radio_range,
                                         sender.chantitle[channel], getattr(receiver, 'comm', 0), digital=mode, path=path)
            if len(path) >= 2:
                bearing = int(find_bearing(receiver.fx, receiver.fy, path[-1].fx, path[-1].fy))
            text = f'{color_code(receiver,selected)}[{chr(65+selected)}:{bearing:03d}] {text}%c' if not observer else text
        else:
            text, xp = scramble_message(message, distance, sender.radio_range, receiver.radio_range,
                                         sender.chantitle[channel], getattr(receiver, 'comm', 0),
                                         receiver is not sender and (any_ecm_disturbed(sender) or any_ecm_disturbed(receiver)))
            text = f'{color_code(receiver,selected)}({chr(65+selected)}:{bearing:03d}) {text}%c' if not observer else text
        if not observer:
            text = text[:LBUF_SIZE - 1]
            recipients = mech_notify(receiver, MECHALL, text)
            observations.append(dict(unit=receiver._id, channel=selected, text=text, recipients=recipients, observer=False))
        tick = getattr(getattr(receiver, '_engine', None), 'muxevent_tick', 0)
        if xp and receiver.in_character and getattr(receiver, 'comm_last', 0) + 60 < tick:
            from systems.experience import comm
            comm(receiver.pilot, receiver)
            receiver.comm_last = tick
    return observations


def send_channel(unit, actor, text):
    error = common_checks(unit, actor, MECH_USUALS)
    if error is None:
        if unit.is_destroyed or not unit.radio_range:
            error = 'Your communication gear is inoperative.'
        elif crew_stunned(unit):
            error = 'You are too stunned to use the radio!'
    if error is not None:
        return dict(ok=False, error=error)
    try:
        index, message = parse_channel_send(unit, text)
    except ValueError as error:
        return dict(ok=False, error=str(error))
    if not unit.freq[index] and getattr(unit.map, 'in_character', False):
        from systems.notifications import object_name
        external_request(unit, 'ZeroFrequencies',
                         f'Player #{getattr(actor, "_id", -1)} ({object_name(actor)}) in mech #{unit._id} '
                         f'(channel {chr(65 + index)}) on map #{unit.mapindex} 0-freqs "{message}"')
    deliveries = transmit(unit, index, message)
    from systems.mines import explode_mines
    mines = explode_mines(unit, unit.freq[index])
    return dict(ok=True, deliveries=deliveries, mines=mines)


def directed_radio(unit, actor, text):
    from entities.mech import CritStatus
    from systems.targeting import contact_target, fa_mech_range
    from systems.los import in_line_of_sight
    from systems.notifications import mech_printf, identity, MECHSTARTED
    error = common_checks(unit, actor, MECH_USUAL)
    if error is not None:
        return dict(ok=False, error=error)
    if unit.crit_status & CritStatus.OBSERVATORIC:
        return dict(ok=False, error="You can't radio anyone.")
    args = parse_attributes(text)
    if len(args) != 3 or len(args[0]) != 2 or args[1] != '=':
        return dict(ok=False, error='Invalid format! Usage: radio <letter><letter>=<message>')
    target = contact_target(unit, args[0])
    if target is None or not in_line_of_sight(unit, target, target.x, target.y, fa_mech_range(unit, target)):
        return dict(ok=False, error='Target is not in line of sight!')
    mech_printf(unit, MECHSTARTED, "You radio %s with, '%s'", identity(unit,target), args[2])
    mech_printf(target, MECHSTARTED, "%s radios you with, '%s'", identity(target,unit), args[2])
    auto_reply(target, f"{identity(target,unit)} radio'ed me '{args[2]}'"[:LBUF_SIZE - 1])
    return dict(ok=True)


def crew_stunned(unit):
    from core.events import EventType
    engine = getattr(unit, '_engine', None)
    return engine is not None and engine.has_event(EventType.UNSTUN_CREW, unit)
