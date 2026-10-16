# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_core.c
#   btech/src/glue.hcode.c

"""Controller lifecycle and destructive command queue from autopilot_core.c."""
import io
import re
import struct
from entities.autopilot import Autopilot, CommandNode, COMMANDS
from core.events import EventType, SOURCE_EVENT_IDS, SOURCE_EVENT_NAMES
from systems.notifications import personal_notify
from systems.targeting import resolve_object

MBUF_SIZE = 2048


def explode_arguments(text, maximum):
    """glue.hcode.c: consume exactly one separator; preserve the final remainder."""
    text = text.split('\0', 1)[0]
    args = []
    while text and len(args) < maximum - 1:
        match = re.search(r'[ \t]', text)
        end = match.start() if match else len(text)
        args.append(text[:end])
        text = text[end + 1:]
    if text:
        args.append(text)
    return args


def readnum(value):
    """Readnum uses atoi, but accepts a zero value only when the string is exactly 0."""
    match = re.match(r'\s*([+-]?\d+)', value or '')
    if not match:
        raise ValueError('Invalid number')
    number = int(match[1])
    if number == 0 and value != '0':
        raise ValueError('Invalid zero representation')
    if not -(1 << 31) <= number < (1 << 31):
        raise ValueError('Source signed integer overflow')
    return number


def ai_error(autopilot, message):
    from core.effects import emit_channel
    return emit_channel(autopilot, 'AI', message)


def auto_create_command_node(args=()):
    return CommandNode(list(args))


def auto_destroy_command_node(node):
    node.args.clear()


def auto_write_command_node(stream, node):
    stream.write(bytes([node.argcount]))
    for arg in node.args:
        raw = arg.encode('latin1')[:MBUF_SIZE]
        stream.write(raw.ljust(MBUF_SIZE, b'\0'))


def auto_read_command_node(stream):
    def read(size):
        data = stream.read(size)
        if len(data) != size:
            raise ValueError('Error loading command node from file - short record')
        return data
    size = read(1)[0]
    if size > 4:
        raise ValueError('Error loading command node from file - invalid argument count')
    args = [read(MBUF_SIZE).split(b'\0', 1)[0].decode('latin1') for _ in range(size + 1)]
    if args[0] not in COMMANDS:
        raise ValueError('Error loading command node from file - Invalid Command')
    if COMMANDS[args[0]][1] != size:
        raise ValueError('Error loading command node from file - invalid argument count')
    return auto_create_command_node(args)


def auto_save_commands(autopilot, stream=None):
    sink = stream if stream is not None else io.BytesIO()
    sink.write(b'\x33' + struct.pack('<I', len(autopilot.commands or ())))
    for node in autopilot.commands or ():
        auto_write_command_node(sink, node)
    sink.write(b'\x3f')
    return sink.getvalue() if stream is None else None


def auto_load_commands(autopilot, data):
    stream = io.BytesIO(data) if isinstance(data, bytes) else data
    if stream.read(1) != b'\x33':
        raise ValueError('Unable to locate START for reading AI commands')
    raw = stream.read(4)
    if len(raw) != 4:
        raise ValueError('Error loading AI command count')
    count = struct.unpack('<I', raw)[0]
    commands = [auto_read_command_node(stream) for _ in range(count)]
    if stream.read(1) != b'\x3f':
        raise ValueError('Unable to locate END for reading AI commands')
    autopilot.commands = commands


def auto_valid_progline(autopilot, position):
    return 0


def auto_show_command(node):
    return (f'{node.args[0]:<10}' + ''.join(' ' + arg for arg in node.args[1:]))[:MBUF_SIZE - 1]


def _notice(autopilot, player, text, ok=True):
    actor = resolve_object(autopilot, player) if isinstance(player, int) else player
    personal_notify(actor or autopilot, text)
    return dict(ok=ok, **({'message': text} if ok else {'error': text}))


def auto_delcommand(player, autopilot, buffer):
    size = len(autopilot.commands or ())
    if not buffer:
        _notice(autopilot, player, 'No argument used : Usage delcommand [num]\n', False)
        return _notice(autopilot, player, f'Must be within the range 1 to {size} or -1 for all\n', False)
    try:
        position = readnum(buffer)
    except ValueError:
        position = 0
    if position != -1 and not 1 <= position <= size:
        return _notice(autopilot, player, f'Invalid Argument : Must be within the range 1 to {size} or -1 for all\n', False)
    if position == -1:
        for node in autopilot.commands:
            auto_destroy_command_node(node)
        autopilot.commands.clear()
        return _notice(autopilot, player, 'All the commands have been removed.\n')
    auto_destroy_command_node(autopilot.commands.pop(position - 1))
    return _notice(autopilot, player, f'Command #{position} Successfully Removed\n')


def auto_jump(player, autopilot, buffer=''):
    return _notice(autopilot, player, "jump has been temporarly disabled till I can figure out how I want to change it - Dany")


def auto_addcommand(player, autopilot, buffer):
    command = re.split(r'[ \t=]', buffer.split('\0', 1)[0], maxsplit=1)[0][:256]
    if command not in COMMANDS:
        return _notice(autopilot, player, 'Invalid Command!', False)
    count = COMMANDS[command][1]
    args = explode_arguments(buffer, count + 1) if count else [command]
    if len(args) != count + 1:
        return _notice(autopilot, player, 'Not the proper number of arguments!', False)
    node = auto_create_command_node(args)
    node.enum_value = COMMANDS[command][0]
    autopilot.commands.append(node)
    return _notice(autopilot, player, 'Command Added: ' + auto_show_command(node))


def auto_listcommands(player, autopilot, buffer=''):
    mech = resolve_object(autopilot, autopilot.location)
    lines = [f'Autopilot data for {autopilot.name}',
             f'Controling unit {getattr(mech, "name", "")}',
             f'MyRef: #{autopilot._id}  MechRef: #{autopilot.mymechnum}  MapIndex: #{autopilot.mapindex}  FSpeed: {autopilot.speed} % (Flag:{autopilot.flags})']
    lines.extend(f'#{i:<3} {auto_show_command(node)}' for i, node in enumerate(autopilot.commands or (), 1))
    if not autopilot.commands:
        lines.append('No commands have been queued to date.')
    for line in lines:
        _notice(autopilot, player, line)
    return dict(ok=True, lines=lines)


def _events(autopilot):
    engine = autopilot._engine
    return [event for event in engine.events.pending_events(data=autopilot)
            if 23 <= SOURCE_EVENT_IDS.get(event.event_type, -1) <= 32] if engine else []


def auto_eventstats(player, autopilot, buffer=''):
    counts = {}
    for event in _events(autopilot):
        kind = SOURCE_EVENT_IDS[event.event_type]
        counts[kind] = counts.get(kind, 0) + 1
    lines = ['Events by type: ', '-------------------------------']
    lines.extend(f'{SOURCE_EVENT_NAMES[kind]:<20}{count}' for kind, count in sorted(counts.items()))
    if counts:
        lines += ['-------------------------------', f'{sum(counts.values())} total']
    for line in lines:
        _notice(autopilot, player, line)
    return dict(ok=True, lines=lines)


def auto_pilot_on(autopilot):
    return len(_events(autopilot)) or autopilot.flags & 7


def auto_stop_pilot(autopilot):
    autopilot.flags &= ~7
    for event in _events(autopilot):
        event.cancel()


def auto_set_comtitle(autopilot, mech):
    from systems.communications import set_title
    from systems.parts import mech_ids
    result = set_title(mech, f'a={mech.mech_type}/{mech_ids(mech, True)}')
    _notice(autopilot, autopilot, result.get('message', result.get('error', '')))


def auto_init(autopilot, mech):
    values = dict(ofsx=0, ofsy=0, auto_cmode=1, auto_cdist=2, auto_nervous=0,
                  auto_goweight=44, auto_fweight=55, speed=100, flags=0,
                  target=-2, target_score=0, target_threshold=50, target_update_tick=30,
                  chase_target=-10, chasetarg_update_tick=30, follow_update_tick=10)
    for key, value in values.items():
        setattr(autopilot, key, value)


def schedule(autopilot, delay, kind=EventType.AUTOCOM, callback=None, data2=0):
    if callback is None:
        from systems.autopilot import auto_com_event
        callback = auto_com_event
    return autopilot._engine.schedule_event(delay, kind, callback, data=autopilot, data2=data2)


def auto_engage(player, autopilot, buffer=''):
    from entities.mech import Mech
    autopilot.mymechnum = autopilot.location
    autopilot.mymech = mech = resolve_object(autopilot, autopilot.location)
    if not isinstance(mech, Mech):
        return _notice(autopilot, player, "Error: The autopilot isn't inside a 'mech!", False)
    if auto_pilot_on(autopilot):
        return _notice(autopilot, player, "The autopilot's already online! You have to disengage it first.", False)
    if mech.autopilot <= 0:
        auto_init(autopilot, mech)
    mech.auto = autopilot._id
    auto_set_comtitle(autopilot, mech)
    autopilot.mapindex = mech.mapindex
    result = _notice(autopilot, player, 'Engaging autopilot...')
    schedule(autopilot, 1)
    return result


def auto_disengage(player, autopilot, buffer=''):
    if not auto_pilot_on(autopilot):
        return _notice(autopilot, player, "The autopilot's already offline! You have to engage it first.", False)
    auto_stop_pilot(autopilot)
    return _notice(autopilot, player, 'Autopilot has been disengaged.')


def auto_goto_next_command(autopilot, time=1):
    if not autopilot.commands:
        ai_error(autopilot, f"Internal AI Error: Trying to remove the first command from AI #{autopilot._id} but the command node doesn't exist\n")
        return
    auto_destroy_command_node(autopilot.commands.pop(0))
    schedule(autopilot, time)


def auto_get_command_arg(autopilot, command_number, arg_number):
    if not 1 <= command_number <= len(autopilot.commands or ()) or not 0 <= arg_number < 5:
        ai_error(autopilot, f'Internal AI Error: Invalid Command #{command_number} Arg #{arg_number} for AI #{autopilot._id}')
        return None
    args = autopilot.commands[command_number - 1].args
    if arg_number >= len(args):
        ai_error(autopilot, f"Internal AI Error: Trying to access Arg #{arg_number} for AI #{autopilot._id} Command #{command_number} but it doesn't exist")
        return None
    return args[arg_number][:MBUF_SIZE]


def auto_get_command_enum(autopilot, command_number):
    if not autopilot.commands:
        return -1
    if not 1 <= command_number <= len(autopilot.commands):
        ai_error(autopilot, f'Internal AI Error: Invalid Command #{command_number} for AI #{autopilot._id}')
        return -1
    return autopilot.commands[command_number - 1].command_enum


def auto_newautopilot(engine, key, unit=None, *, selector=1, autopilot=None):
    if selector:
        autopilot = Autopilot(key, unit)
        engine.register_entity(autopilot)
        return autopilot
    auto_stop_pilot(autopilot)
    autopilot.commands = None
    autopilot.astar_path = None
    autopilot.weaplist = None
    autopilot.profile = [None] * 30
    mech = resolve_object(autopilot, autopilot.mymechnum)
    if mech is not None and mech.autopilot == autopilot._id:
        mech.auto = -1
    if mech is not None and mech.pilot is autopilot:
        mech.pilot = None
    people = getattr(engine,'personnel',None)
    if people is not None and people.objects.get(autopilot._id) is autopilot:
        people._unlink(autopilot._id)
        del people.objects[autopilot._id]
    autopilot.allocated = False
    engine.unregister_entity(autopilot)


def auto_heartbeat(autopilot):
    return autopilot._engine.auto_heartbeat(autopilot)

