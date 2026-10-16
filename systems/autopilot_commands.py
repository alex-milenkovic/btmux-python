# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_commands.c

"""Active command callbacks from autopilot_commands.c."""
import math
import re
from types import SimpleNamespace
from entities.autopilot import COMMAND_NAMES, Autopilot
from entities.mech import Mech, UnitType as U, MoveType as M, MechStatus as S, Location as L
from core.events import EventType as E
from core.randomness import draw, number, float32 as f32
from systems.targeting import indexed_map, resolve_object, resolve_unit
from systems.autopilot_core import (schedule, readnum, explode_arguments, ai_error,
    auto_get_command_arg, auto_get_command_enum, auto_goto_next_command)
from systems.autopilot_ai import (ai_set_speed, ai_set_heading, max_speed, ai_check_path,
    auto_astar_generate_path, auto_destroy_astar_path)
from systems.map_transitions import auto_cal_mapindex
from systems.autopilot import valid_special_objects
from systems import movement_commands as move
from physics.hexmath import hex_to_float, float_to_hex, find_xy, find_range, find_bearing
from entities.map import WATER, LIGHT_FOREST, HEAVY_FOREST

STARTUP_TICK = 31


def historical(a):
    from systems.autopilot import uses_event_autopilot
    return uses_event_autopilot(a.mymech)


def goto_tick(a):
    return 3 if historical(a) else 4


def leave_tick(a):
    return 5 if historical(a) else 6


def god(a):
    return resolve_object(a,1) or SimpleNamespace(_id=1,wizard=True,god=True,location=a.location)


def _valid(a, names=None):
    mech = getattr(a,'mymech',None)
    return (valid_special_objects(a)
            and a.location == a.mymechnum and not mech.is_destroyed
            and (names is None or _name(a) in names))


def _name(a):
    value = auto_get_command_enum(a,1)
    return COMMAND_NAMES[value] if value >= 0 else None


def _fail(a, message, stop=False, clear_path=False):
    ai_error(a,message)
    if stop:
        ai_set_speed(a.mymech,a,0)
    if clear_path:
        auto_destroy_astar_path(a)
    auto_goto_next_command(a,1)


def auto_command_startup(a, mech):
    from systems.startup import starting, startup
    if mech.is_started:
        return
    if not starting(a._engine,mech):
        startup(a._engine,mech,caller=a)
        # Source removes the current command even when called by AUTO_GSTART.
        auto_goto_next_command(a,STARTUP_TICK)


def auto_command_shutdown(a, mech):
    from systems.startup import shutdown
    if mech.is_started:
        shutdown(a._engine,mech,caller=a)


def _ready(a, event=None, general=False):
    mech = a.mymech
    if not mech.is_started:
        from systems.startup import starting
        if not starting(a._engine,mech):
            auto_command_startup(a,mech)
        if event is not None:
            schedule(a,STARTUP_TICK,event.event_type,event.callback,event.data2)
        return False
    from systems.parts import count_destroyed_legs
    if mech.unit_type == U.MECH and mech.is_fallen and not count_destroyed_legs(mech):
        if not a._engine.has_event(E.STAND,mech):
            move.stand(a._engine,mech,caller=a)
        if event is None:
            schedule(a,1)
        else:
            schedule(a,1,event.event_type,event.callback,event.data2)
        return False
    if general and mech.unit_type == U.VTOL and mech.has_status(S.LANDED) and not mech.is_section_destroyed(5):
        if not a._engine.has_event(E.TAKEOFF,mech):
            from physics.aerospace import takeoff
            takeoff(a._engine,mech,caller=a)
        schedule(a,1)
        return False
    return True


def auto_set_chasetarget_mode(a, mode):
    if mode == 1 or mode == 3 and a.flags & 64:
        a.flags = (a.flags | 32) & ~64
        a.chase_target,a.chasetarg_update_tick = -10,30
    elif mode == 2:
        a.flags &= ~(32|64)
    elif mode == 4 and a.flags & 32:
        a.flags = (a.flags & ~32) | 64


def start_gun(a):
    from systems.autopilot import uses_event_autopilot, auto_com_event
    a.flags = (a.flags | 1) & ~2
    if uses_event_autopilot(a.mymech):
        for kind in (E.AUTO_PROFILE,E.AUTOGUN,E.AUTO_SENSOR):
            schedule(a,1,kind,auto_com_event)


def stop_gun(a):
    a.flags &= ~3
    from systems.autopilot import uses_event_autopilot
    if a.mymech is not None and uses_event_autopilot(a.mymech):
        for kind in (E.AUTO_PROFILE,E.AUTOGUN,E.AUTO_SENSOR):
            a._engine.cancel_events_of_type(kind,a)


def zombify(a):
    from systems.autopilot import uses_event_autopilot
    if uses_event_autopilot(a.mymech):
        # Recovered header retains AUTOGUN while suspending the event chain.
        a.flags |= 2
        for kind in (E.AUTO_PROFILE,E.AUTOGUN,E.AUTO_SENSOR):
            a._engine.cancel_events_of_type(kind,a)
    else:
        # General header's Zombify sets GUNZOMBIE then StopGun clears both bits.
        a.flags = (a.flags | 2) & ~3


def auto_command_autogun(a, mech):
    args = explode_arguments(auto_get_command_arg(a,1,1) or '',4)
    if len(args) == 1 and args[0] in ('on','off'):
        active = args[0] == 'on'
        a.target,a.target_score,a.target_update_tick = (-1,0,30) if active else (-2,0,0)
        a.flags &= ~256
        if active:
            if not _ready(a,general=True):
                return
            if a.flags & 1:
                stop_gun(a)
            start_gun(a)
        elif a.flags & 1:
            stop_gun(a)
    elif len(args) == 2 and args[0] == 'target':
        try:
            target = readnum(args[1])
        except ValueError:
            ai_error(a,f'AI Error - AI #{a._id} given bad argument for autogun command')
            return
        if resolve_unit(mech,target) is None:
            ai_error(a,f'AI Error - AI #{a._id} given bad target for autogun command')
            return
        a.target,a.target_score,a.target_update_tick = target,0,0
        a.flags |= 256
        if not _ready(a,general=True):
            return
        if a.flags & 1:
            stop_gun(a)
        start_gun(a)
    elif len(args) in (1,2):
        ai_error(a,f'AI Error - AI #{a._id} given bad argument for autogun command')


def auto_command_chasetarget(a):
    schedule(a,goto_tick(a),E.AUTOFOLLOW,auto_astar_follow_event,1)


def _target_argument(a, command):
    try:
        identity = readnum(auto_get_command_arg(a,1,1))
    except ValueError:
        ai_error(a,f'AI Error - AI #{a._id} given bad argument for {command} command')
        return None
    target = resolve_unit(a.mymech,identity)
    if target is None:
        ai_error(a,f'AI Error - AI #{a._id} unable to {command} unit #{identity}')
    return target


def auto_command_pickup(a, mech):
    from systems.occupants import pickup
    from systems.parts import mech_ids
    target = _target_argument(a,'pickup')
    if target is not None:
        return pickup(mech,god(a),mech_ids(target,True))


def auto_command_dropoff(mech):
    from systems.towing import dropoff
    a = resolve_object(mech,mech.auto)
    return dropoff(mech,god(a))


def auto_command_speed(a):
    try:
        speed = readnum(auto_get_command_arg(a,1,1)) & 0xffff
    except ValueError:
        ai_error(a,f'AI Error - AI #{a._id} given bad argument for speed command')
        return
    if not 1 <= speed <= 100:
        ai_error(a,f'AI Error - AI #{a._id} given bad argument for speed command - out side of the range')
        return
    a.speed = speed


def auto_command_embark(a, mech):
    from systems.occupants import embark
    from systems.parts import mech_ids
    if not _ready(a,general=True):
        return
    target = _target_argument(a,'embark')
    if target is not None:
        return embark(mech,god(a),mech_ids(target,True))


def auto_command_udisembark(mech):
    from systems.occupants import unit_disembark
    from core.attributes import attributes_for
    raw = attributes_for(mech).get(mech._id,'A_PILOTNUM','')
    # sscanf(buf, "#%ld", &pil): the # is literal, %ld skips whitespace
    # and accepts a signed decimal prefix followed by arbitrary text.
    match = re.match(r'#[ \t\n\r\v\f]*([+-]?[0-9]+)', raw)
    identity = int(match[1]) if match else -1
    actor = resolve_object(mech,identity)
    if actor is None:
        return dict(ok=False,error='Unable to resolve disembark pilot')
    return unit_disembark(mech,actor)


def auto_com_event(event):
    a = event.data
    if not valid_special_objects(a):
        return
    mech = a.mymech
    if resolve_object(mech,mech.mapindex) is None:
        a.mapindex = mech.mapindex
        a.flags |= 4
        if _name(a) != 'udisembark':
            return
    if a.mapindex < 0:
        a.mapindex = mech.mapindex
    if not _valid(a):
        return
    command = _name(a)
    goals = {
        'chasetarget':(goto_tick(a),E.AUTOFOLLOW,auto_astar_follow_event,1),
        'dumbgoto':(goto_tick(a),E.AUTOGOTO,auto_dumbgoto_event,0),
        'dumbfollow':(goto_tick(a),E.AUTOFOLLOW,auto_dumbfollow_event,0),
        'enterbase':(1,E.AUTOENTERBASE,auto_enter_event,1),
        'follow':(goto_tick(a),E.AUTOFOLLOW,auto_astar_follow_event,1),
        'goto':(goto_tick(a),E.AUTOGOTO,auto_astar_goto_event,1),
        'leavebase':(leave_tick(a),E.AUTOLEAVE,auto_leave_event,1),
        'oldgoto':(goto_tick(a),E.AUTOGOTO,auto_goto_event,0)}
    if command in goals:
        if command == 'oldgoto' and not _ready(a,general=True):
            return
        return schedule(a,*goals[command])
    if command == 'roam':
        return auto_command_roam(a,mech)
    if command == 'startup':
        return auto_command_startup(a,mech)
    handlers = {
        'autogun':lambda:auto_command_autogun(a,mech),
        'dropoff':lambda:auto_command_dropoff(mech),
        'embark':lambda:auto_command_embark(a,mech),
        'pickup':lambda:auto_command_pickup(a,mech),
        'shutdown':lambda:auto_command_shutdown(a,mech),
        'speed':lambda:auto_command_speed(a),
        'udisembark':lambda:auto_command_udisembark(mech)}
    if command in handlers:
        handlers[command]()
        auto_goto_next_command(a,1)
    # wait/jump and the other literal-disabled switch cases stall in the source.


def speed_up_if_neccessary(a,mech,tx,ty,bearing):
    board = indexed_map(mech)
    if board is None and not historical(a):
        return
    if (bearing < 0 or abs(int(mech.desired_speed)) < 2) and (bearing < 0 or abs(bearing-mech.facing) <= 30) and (mech.x,mech.y) != (tx,ty):
        ai_set_speed(mech,a,max_speed(mech)*(2/3 if not historical(a) and board.rterrain(mech.x,mech.y) == WATER else 1))


def update_wanted_heading(a,mech,bearing):
    return ai_set_heading(mech,a,bearing)


def slow_down_if_neccessary(a,mech,distance,bearing,tx,ty):
    distance = max(0,distance)
    if distance > 2:
        return 0
    if abs(bearing-mech.facing) > 30:
        ai_set_speed(mech,a,0)
        update_wanted_heading(a,mech,bearing)
    elif (tx,ty) == (mech.x,mech.y):
        ai_set_speed(mech,a,0)
    else:
        ai_set_speed(mech,a,f32(f32(.4+distance/2.0)*max_speed(mech)))
    return 1


def figure_out_range_and_bearing(mech,tx,ty):
    x,y = hex_to_float(tx,ty)
    return find_range(mech.fx,mech.fy,x,y),find_bearing(mech.fx,mech.fy,x,y)


def _steer(a,x,y):
    mech = a.mymech
    distance,bearing = figure_out_range_and_bearing(mech,x,y)
    speed_up_if_neccessary(a,mech,x,y,bearing)
    slow_down_if_neccessary(a,mech,distance,bearing,x,y)
    update_wanted_heading(a,mech,bearing)


def _movement_event(event,names):
    a = event.data
    if not _valid(a,names):
        return False
    if indexed_map(a) is None:
        label = {'dumbgoto':'goto [dumbly]','dumbfollow':'follow [dumbly]','chasetarget':'follow'}.get(_name(a),_name(a))
        _fail(a,f'Internal AI Error - Attempting to {label} with AI #{a._id} but AI is not on a valid Map (#{a.mapindex}).')
        return False
    return _ready(a,event)


def _xy(a):
    coordinates = [0,0]
    for index in range(2):
        argument = auto_get_command_arg(a,1,index+1)
        try:
            coordinates[index] = readnum(argument)
        except ValueError:
            which = ('first','second')[index]
            detail = '' if argument is None else f" '{argument}'"
            if _name(a) == 'goto':
                # C diagnostic prints uninitialized coordinates on malformed input;
                # use the successfully parsed prefix and zero for undefined values.
                prefix = f'Internal AI Error - Attempting to generate an astar path for AI #{a._id} to hex {coordinates[0]},{coordinates[1]} but was unable to'
            else:
                prefix = f'Internal AI Error - Attempting to goto [dumbly] with AI #{a._id} but was unable to'
            _fail(a,prefix+f' - bad {which} argument{detail} - going to next command')
            return None
    return tuple(coordinates)


def _follow_argument(a, dumb=False):
    argument = auto_get_command_arg(a,1,1)
    try:
        return readnum(argument)
    except ValueError:
        detail = '' if argument is None else f" '{argument}'"
        label = ' [dumbly]' if dumb else ''
        _fail(a,f'Internal AI Error - AI #{a._id} attempting to follow target{label} but was unable to - bad argument{detail} - going to next command')
        return None


def auto_goto_event(event):
    a = event.data
    if not _valid(a) or not _ready(a,general=True):
        return
    pos = _xy(a)
    if pos is None:
        return
    mech = a.mymech
    if (mech.x,mech.y) == pos and abs(int(mech.speed) if historical(a) else mech.speed) < .5:
        ai_set_speed(mech,a,0)
        auto_goto_next_command(a,1)
        return
    distance,bearing = figure_out_range_and_bearing(mech,*pos)
    if slow_down_if_neccessary(a,mech,distance,bearing,*pos) or ai_check_path(mech,a,*hex_to_float(*pos)):
        schedule(a,goto_tick(a),E.AUTOGOTO,auto_goto_event)


def auto_dumbgoto_event(event):
    if not _movement_event(event,('dumbgoto',)):
        return
    a,mech = event.data,event.data.mymech
    pos = _xy(a)
    if pos is None:
        return
    if (mech.x,mech.y) == pos and abs(int(mech.speed) if historical(a) else mech.speed) < .5:
        ai_set_speed(mech,a,0)
        auto_goto_next_command(a,1)
        return
    _steer(a,*pos)
    schedule(a,goto_tick(a),E.AUTOGOTO,auto_dumbgoto_event)


def _walk_path(event,mode):
    a,mech = event.data,event.data.mymech
    delay = 3 if mode == 'roam' else goto_tick(a)
    if not a.astar_path:
        label = 'roam' if mode == 'roam' else 'follow'
        _fail(a,f'Internal AI Error - Attempting to {label} Astar path for AI #{a._id} - but the path is not there',stop=mode=='follow',clear_path=True)
        return
    node = a.astar_path[0]
    if node is None:
        label = 'roam' if mode == 'roam' else 'follow'
        _fail(a,f'Internal AI Error - Attemping to {label} Astar path for AI #{a._id} - but the current astar node does not exist',stop=mode=='follow',clear_path=True)
        return
    if (mech.x,mech.y) == (node.x,node.y):
        if len(a.astar_path) == 1:
            ai_set_speed(mech,a,0)
            auto_destroy_astar_path(a)
            if mode == 'goto':
                auto_goto_next_command(a,1)
            else:
                schedule(a,delay,event.event_type,event.callback,int(mode=='roam'))
            return
        a.astar_path.pop(0)
        if mode == 'roam':
            a.roam_update_tick += 1
    else:
        _steer(a,node.x,node.y)
        if mode == 'follow':
            a.follow_update_tick += 1
        elif mode == 'roam':
            a.roam_update_tick += 1
    schedule(a,delay,event.event_type,event.callback)


def auto_astar_goto_event(event):
    if not _movement_event(event,('goto',)):
        return
    a = event.data
    if event.data2:
        pos = _xy(a)
        if pos is None:
            return
        board = indexed_map(a)
        if pos[0] < 0 or pos[1] < 0 or pos[0] >= board.map_width or pos[1] >= board.map_width:
            _fail(a,f'Internal AI Error - Attempting to generate an astar path for AI #{a._id} to bad hex ({pos[0]}, {pos[1]})')
            return
        if not auto_astar_generate_path(a,a.mymech,*pos):
            _fail(a,f'Internal AI Error - Attempting to generate an astar path for AI #{a._id} to hex {pos[0]},{pos[1]} but was unable to')
            return
    _walk_path(event,'goto')


def auto_astar_follow_event(event):
    if not _movement_event(event,('follow','chasetarget')):
        return
    a,mech = event.data,event.data.mymech
    identity = _follow_argument(a)
    if identity is None:
        return
    target = resolve_unit(mech,identity)
    if target is None:
        _fail(a,f'Internal AI Error - Attempting to follow unit #{identity} with AI #{a._id} but its not a valid unit.',stop=True)
        return
    if target.is_destroyed or target.mapindex != mech.mapindex:
        _fail(a,f'Internal AI Error - Attempting to follow unit #{identity} with AI #{a._id} but it is either dead or not on the same map.',stop=True)
        return
    x,y = float_to_hex(*find_xy(target.fx,target.fy,target.facing+a.ofsx,a.ofsy))
    if not indexed_map(a).valid(x,y):
        x,y = target.x,target.y
    if (mech.x,mech.y) == (x,y) and target.speed < .5:
        ai_set_speed(mech,a,0)
        auto_destroy_astar_path(a)
        schedule(a,goto_tick(a),E.AUTOFOLLOW,auto_astar_follow_event)
        return
    if event.data2:
        auto_destroy_astar_path(a)
    if a.astar_path is None or a.follow_update_tick >= 10:
        found = auto_astar_generate_path(a,mech,x,y)
        if not found and (x,y) != (mech.x,mech.y):
            x,y = target.x,target.y
            a.follow_update_tick = 10
            found = auto_astar_generate_path(a,mech,x,y)
        if not found:
            _fail(a,f'Internal AI Error - Attempting to generate an astar path for AI #{a._id} to hex {x},{y} to follow unit #{identity}, but was unable to.',stop=True)
            return
        a.follow_update_tick = 0
    _walk_path(event,'follow')


def auto_dumbfollow_event(event):
    if not _movement_event(event,('dumbfollow',)):
        return
    a,mech = event.data,event.data.mymech
    identity = _follow_argument(a,True)
    if identity is None:
        return
    leader = resolve_unit(mech,identity)
    if leader is None or leader.is_destroyed:
        _fail(a,f'Internal AI Error - AI #{a._id} attempting to follow target [dumbly] but was unable to - bad or dead target - going to next command')
        return
    radians = math.radians(270+leader.desired_facing+a.ofsx)
    x,y = leader.x+int(a.ofsy*math.cos(radians)),leader.y+int(a.ofsy*math.sin(radians))
    if (mech.x,mech.y) == (x,y):
        if abs(leader.speed) > 1 or abs(mech.speed) > 1:
            ai_set_heading(mech,a,leader.facing)
            if mech.speed != leader.speed:
                move.speed(a._engine,mech,f'{leader.speed:.2f}',caller=a)
    else:
        distance,bearing = figure_out_range_and_bearing(mech,x,y)
        speed_up_if_neccessary(a,mech,x,y,-1)
        if leader.speed < 10.75:
            slow_down_if_neccessary(a,mech,distance+1,bearing,x,y)
        update_wanted_heading(a,mech,bearing)
    schedule(a,goto_tick(a),E.AUTOFOLLOW,auto_dumbfollow_event)


def auto_leave_event(event):
    if not _movement_event(event,('leavebase',)):
        return
    a,mech = event.data,event.data.mymech
    if event.data2:
        a.mapindex = mech.mapindex
    argument = auto_get_command_arg(a,1,1)
    try:
        direction = readnum(argument)
    except ValueError:
        detail = '' if argument is None else f" '{argument}'"
        ai_error(a,f'Internal AI Error - Attempting to leavebase with AI #{a._id} but was given bad argument{detail} defaulting to direction = 0')
        direction = 0
    if mech.mapindex != a.mapindex:
        a.mapindex = mech.mapindex
        ai_set_speed(mech,a,0)
        auto_goto_next_command(a,1)
        return
    speed_up_if_neccessary(a,mech,-1,-1,direction)
    update_wanted_heading(a,mech,direction)
    schedule(a,leave_tick(a),E.AUTOLEAVE,auto_leave_event)


def auto_enter_event(event):
    a,mech = event.data,event.data.mymech
    if not _valid(a,('enterbase',)):
        return
    board = indexed_map(a)
    if board is None:
        _fail(a,f'Internal AI Error - Attempting to enterbase with AI #{a._id} but AI is not on a valid Map (#{a.mapindex}).')
        return
    if not historical(a) and mech.mapindex != a.mapindex:
        a.mapindex = mech.mapindex
        auto_goto_next_command(a,1)
        return
    from entities.map_objects import find_object
    if not find_object(board,mech.x,mech.y,4):
        _fail(a,f'Internal AI Error - Attempting to enterbase with AI #{a._id} but there is nothing at {mech.x}, {mech.y} to enter')
        return
    if event.data2:
        a.mapindex = mech.mapindex
    if not _ready(a,SimpleNamespace(data=a,data2=0,event_type=E.AUTOENTERBASE,callback=auto_enter_event)):
        return
    arg = auto_get_command_arg(a,1,1)
    if arg is None:
        _fail(a,f'Internal AI Error - Attempting to enterbase with AI #{a._id} but was given bad argument - going to next command')
        return
    direction = arg[:1].lower()
    direction = direction if direction in ('n','s','w','e') else ''
    if historical(a) and mech.mapindex != a.mapindex:
        a.mapindex = mech.mapindex
        auto_goto_next_command(a,1)
        return
    if mech.desired_speed != 0:
        ai_set_speed(mech,a,0)
    if mech.speed == 0 and not a._engine.has_event(E.ENTER_HANGAR,mech):
        from systems.hangar import enter_base
        enter_base(mech,direction,caller=god(a))
    schedule(a,1,E.AUTOENTERBASE,auto_enter_event)


def auto_command_roam(a,mech):
    args = explode_arguments(auto_get_command_arg(a,1,1) or '',4)
    if args == ['map']:
        a.roam_type = 1
    elif len(args) == 4 and args[0] == 'radius':
        values = []
        for field,argument in zip(('anchor_hex_x','anchor_hex_y','anchor_distance'),args[1:]):
            try:
                values.append(readnum(argument))
            except ValueError:
                _fail(a,f'AI Error - AI #{a._id} given bad argument ({field}) for roam command')
                return
        x,y,distance = values
        board = indexed_map(a)
        if board is None:
            _fail(a,f'Internal AI Error - Attempting to roam with AI #{a._id} but AI is not on a valid Map (#{a.mapindex}).')
            return
        if not board.valid(x,y) or distance > 30:
            _fail(a,f'AI Error - AI #{a._id} given bad argument (bad anchor hex or bad anchor distance) {x},{y} : {distance} hexes for roam command')
            return
        a.roam_type = 2
        a.roam_anchor_hex_x,a.roam_anchor_hex_y,a.roam_anchor_distance = x,y,distance
    else:
        _fail(a,f'AI Error - AI #{a._id} given bad argument for roam command')
        return
    schedule(a,3,E.AUTO_ROAM,auto_astar_roam_event,1)


def auto_roam_generate_target_hex(a,mech,board,attempt):
    x,y,maximum = (mech.x,mech.y,50) if a.roam_type == 1 else (a.roam_anchor_hex_x,a.roam_anchor_hex_y,a.roam_anchor_distance) if a.roam_type == 2 else (0,0,0)
    divisor = 2 ^ attempt  # XOR in the active source, not exponentiation.
    if divisor == 0:
        ai_error(a,'AI roam source divisor is zero on attempt 2; retaining previous target')
        return
    maximum = int(maximum/divisor)
    for _ in range(3):
        distance = 1.0 if maximum < 1 else float(draw('ai_roam_range',1,maximum,lambda:number(1,maximum),state=a._engine.randomness))
        bearing = draw('ai_roam_bearing',0,359,lambda:number(0,359),state=a._engine.randomness)
        tx,ty = float_to_hex(*find_xy(*hex_to_float(x,y),bearing,distance))
        if not board.valid(tx,ty):
            continue
        terrain = board.terrain(tx,ty)
        if terrain == LIGHT_FOREST and mech.unit_type == U.VEH_GROUND and mech.move_type != M.TRACK:
            continue
        if terrain == HEAVY_FOREST and mech.unit_type == U.VEH_GROUND:
            continue
        if terrain == WATER and mech.move_type != M.HOVER:
            continue
        a.roam_target_hex_x,a.roam_target_hex_y = tx,ty
        break


def auto_astar_roam_event(event):
    if not _movement_event(event,('roam',)):
        return
    a,mech = event.data,event.data.mymech
    if event.data2 or a.roam_update_tick >= 100:
        for attempt in range(3):
            auto_roam_generate_target_hex(a,mech,indexed_map(a),attempt)
            x,y = a.roam_target_hex_x,a.roam_target_hex_y
            if x != -1 and y != -1 and auto_astar_generate_path(a,mech,x,y):
                break
        if not a.astar_path:
            schedule(a,3,E.AUTO_ROAM,auto_astar_roam_event,1)
            return
        a.roam_update_tick = 0
    _walk_path(event,'roam')

