# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_radio.c

"""Radio grammar and handlers from autopilot_radio.c."""
from core.events import EventType as E
from core.randomness import draw, number
from entities.mech import UnitType as U
from systems.autopilot import uses_event_autopilot
from systems.autopilot_core import (auto_addcommand, auto_delcommand, auto_disengage,
    auto_engage, auto_init, explode_arguments, readnum, schedule)
from systems.autopilot_commands import start_gun, stop_gun, auto_set_chasetarget_mode
from systems.communications import auto_reply, auto_reply_event
from systems.targeting import contact_target, indexed_map, resolve_unit
from systems.parts import mech_ids
from systems import movement_commands as move


def _clear(a):
    auto_disengage(a,a,'')
    auto_delcommand(a,a,'-1')
    if a.target >= -1:
        command = 'autogun target '+str(a.target) if a.flags & 256 and a.target != -1 else 'autogun on'
        auto_addcommand(a,a,command)
        return command
    return None


def _replace(a, command):
    _clear(a)
    auto_addcommand(a,a,command)
    auto_engage(a,a,'')


def _restart_gun(a):
    if a.flags & 1:
        stop_gun(a)
    start_gun(a)


def auto_radio_command_autogun(a, mech, args):
    if args[1] == 'on':
        a.target,a.target_score,a.target_update_tick = -1,0,30
        a.flags &= ~256
        _restart_gun(a)
        return 'shooting at whatever I want'
    if args[1] == 'off':
        a.target,a.target_score,a.target_update_tick = -2,0,0
        a.flags &= ~256
        if a.flags & 1:
            stop_gun(a)
        return 'powering down weapons'
    if args[1] == 'threshold':
        try:
            threshold = readnum(args[2]) if len(args) == 3 else -1
        except ValueError:
            threshold = -1
        if 0 <= threshold <= 100:
            a.target_threshold = threshold
            return f'new threshold set to {threshold}%'
        return '!Invalid value used with threshold: Usage autogun threshold [0-100]'
    return "!Invalid Input for autogun: use 'on' or 'off'"


def auto_radio_command_chasetarg(a, mech, args):
    if args[1] in ('on','off'):
        auto_set_chasetarget_mode(a,1 if args[1] == 'on' else 2)
        return 'Chase Target Mode is '+('Activated' if args[1] == 'on' else 'Deactivated')
    return "!Invalid Input for chasetarg: use 'on' or 'off'"


def _follow(a, mech, args, dumb=False):
    target = contact_target(mech,args[1])
    if target is None or target._id <= 0:
        return '!Invalid target to follow'
    _replace(a,('dumbfollow' if dumb else 'follow')+' '+str(target._id))
    return f'following {args[1]}'+(' [dumbly]' if dumb else '')+f' ({a.ofsx} degrees, {a.ofsy} away)'


def auto_radio_command_dfollow(a, mech, args):
    return _follow(a,mech,args,True)


def auto_radio_command_follow(a, mech, args):
    return _follow(a,mech,args)


def _goto(a, mech, args, kind):
    try:
        x = readnum(args[1])
    except ValueError:
        return '!First number not '+('an integer' if kind == 'dumbgoto' else 'integer')
    try:
        y = readnum(args[2])
    except ValueError:
        return '!First number not an integer' if kind == 'dumbgoto' else '!Second number not integer'
    if kind == 'goto':
        if (mech.x,mech.y) == (x,y):
            return '!Already in that hex'
        board = indexed_map(mech)
        if board is None or not board.valid(x,y):
            return '!Bad hex to travel to'
    _replace(a,f'{kind} {x} {y}')
    return 'going '+({'goto':'','dumbgoto':'[dumbly] ','oldgoto':'[old version] '}[kind])+f'to {x},{y}'


def auto_radio_command_dgoto(a, mech, args):
    return _goto(a,mech,args,'dumbgoto')


def auto_radio_command_goto(a, mech, args):
    return _goto(a,mech,args,'goto')


def auto_radio_command_ogoto(a, mech, args):
    return _goto(a,mech,args,'oldgoto')


def auto_radio_command_dropoff(a, mech, args):
    _replace(a,'dropoff')
    return 'dropping off'


def auto_radio_command_embark(a, mech, args):
    target = contact_target(mech,args[1])
    if target is None or target._id <= 0:
        return '!Invalid target to embark'
    _replace(a,'embark '+str(target._id))
    return 'embarking '+args[1]


def auto_radio_command_enterbase(a, mech, args):
    command = 'enterbase '+(args[1] if len(args) > 1 else 'n')
    # Recovered Clear macro overwrites the shared buffer after formatting this
    # command when guns are enabled. The general source moved Clear earlier.
    overwritten = _clear(a)
    if uses_event_autopilot(mech) and overwritten is not None:
        command = overwritten
    auto_addcommand(a,a,command)
    auto_engage(a,a,'')
    return 'entering base'+(f' ({args[1]} side)' if len(args) > 1 else '')


def auto_radio_command_heading(a, mech, args):
    try:
        heading = readnum(args[1])
    except ValueError:
        return '!Number not integer'
    _clear(a)
    auto_engage(a,a,'')
    move.heading(a._engine,mech,str(heading),caller=a)
    move.speed(a._engine,mech,'0',caller=a)
    # The C writes the explanation to buffer, not mesg: parser replies "Ok."
    return ''


def auto_radio_command_help(a, mech, args):
    names = list(dict.fromkeys(row[1] for row in AUTO_COMMANDS))
    message = 'The following commands are possible: '+' '.join(names)
    auto_reply(mech,message)
    return message


def auto_radio_command_hide(a, mech, args):
    from entities.map import LIGHT_FOREST,HEAVY_FOREST,ROUGH,MOUNTAINS,BUILDING
    from systems.swarm import hide
    if not mech.specials2 & 0x40000 and mech.unit_type not in (U.BSUIT,U.MW):
        return '!Last I checked I was kind of big for that'
    from physics.collision import mech_rterrain
    terrain = mech_rterrain(mech)
    if terrain not in (LIGHT_FOREST,HEAVY_FOREST,ROUGH,MOUNTAINS) and not (mech.unit_type == U.BSUIT and terrain == BUILDING):
        return '!Invalid Terrain'
    hide(mech,a,'')
    return 'Begining to hide'


def auto_radio_command_jumpjet(a, mech, args):
    if not int(abs(mech.jump_speed)):
        return "!I don't do hiphop and jump around"
    if len(args) == 2:
        target = contact_target(mech,args[1])
        if target is None or target._id <= 0:
            return '!Unable to see such a target'
        move.jump_command(a._engine,mech,args[1],caller=a)
        return f'jumping on [{args[1]}]'
    try:
        readnum(args[1])
    except ValueError:
        return '!Invalid bearing'
    try:
        readnum(args[2])
    except ValueError:
        return '!Invalid range'
    move.jump_command(a._engine,mech,args[1]+' '+args[2],caller=a)
    return f'jump {args[1]} degrees {args[2]} hexes'


def auto_radio_command_leavebase(a, mech, args):
    try:
        direction = readnum(args[1])
    except ValueError:
        return '!Invalid value for direction'
    a.flags &= ~32
    _replace(a,'leavebase '+str(direction))
    return f'leaving base at {direction} heading'


def auto_radio_command_pickup(a, mech, args):
    target = contact_target(mech,args[1])
    if target is None or target._id <= 0:
        return '!Invalid target to pickup'
    a.flags &= ~32
    _replace(a,'pickup '+str(target._id))
    return 'picking up '+args[1]


def _two_ints(args):
    try:
        x = readnum(args[1])
    except ValueError:
        return None,None,'!Invalid first int'
    try:
        y = readnum(args[2])
    except ValueError:
        return None,None,'!Invalide second int'
    return x,y,None


def auto_radio_command_position(a, mech, args):
    x,y,error = _two_ints(args)
    if error:
        return error
    a.ofsx,a.ofsy = x,y
    return f'following {x} degrees, {y} away'


def auto_radio_command_prone(a, mech, args):
    move.prone(a._engine,mech,caller=a)
    return 'hitting the deck'


def auto_radio_command_report(a, mech, args):
    from physics.cargo import cargo_max_speed
    from systems.targeting import fa_mech_range
    from systems.los import in_line_of_sight
    from systems.notifications import identity
    from systems.heat import is_running
    state = ('Jumping' if mech.is_jumping else 'Prone' if mech.is_fallen else
             'Running' if is_running(mech.speed,cargo_max_speed(mech)) else 'Walking' if mech.speed > 1 else 'Standing')
    message = f'{state} at {mech.x}, {mech.y}, headed {mech.facing}'
    if mech.speed > 1:
        message += f' speed {mech.speed:.2f}'
    target = resolve_unit(mech,mech.target) if mech.target != -1 else None
    if target is not None:
        visible = in_line_of_sight(mech,target,target.x,target.y,fa_mech_range(mech,target))
        message += ', targeting '+identity(mech,target)+' '+('' if visible else '(not in LOS)')
    auto_reply(mech,message)
    return message


def auto_radio_command_reset(a, mech, args):
    auto_disengage(a,a,'')
    auto_delcommand(a,a,'-1')
    auto_init(a,mech)
    auto_engage(a,a,'')
    return 'all internal events and flags reset!'


def auto_radio_command_sensor(a, mech, args):
    from systems.targeting import set_sensors
    a._engine.cancel_events_of_type(E.AUTO_SENSOR,a)
    if len(args) == 3:
        set_sensors(a._engine,mech,args[1]+' '+args[2])
        a.flags |= 16
        return 'updated my sensors'
    a.flags &= ~16
    if uses_event_autopilot(mech):
        schedule(a,1,E.AUTO_SENSOR)
    return 'using my own judgement with sensors'


def auto_radio_command_shutdown(a, mech, args):
    from systems.startup import shutdown
    shutdown(a._engine,mech,caller=a)
    return 'shutting down'


def auto_radio_command_speed(a, mech, args):
    try:
        speed = readnum(args[1])
    except ValueError:
        return '!Invalid value - not a number'
    if speed < 1 or speed > 100:
        return '!Invalid speed'
    a.speed = speed
    return f'setting speed to {speed} %'


def auto_radio_command_stand(a, mech, args):
    move.stand(a._engine,mech,caller=a)
    return 'standing up'


def auto_radio_command_startup(a, mech, args):
    from systems.startup import startup
    override = len(args) > 1 and 'override'.startswith(args[1].lower())
    startup(a._engine,mech,'override' if override else '',caller=a)
    return 'emergency override startup triggered' if override else 'starting up'


def auto_radio_command_stop(a, mech, args):
    auto_set_chasetarget_mode(a,2)
    _clear(a)
    auto_engage(a,a,'')
    move.speed(a._engine,mech,'0',caller=a)
    return 'halting'


def auto_radio_command_sweight(a, mech, args):
    x,y,error = _two_ints(args)
    if error:
        return error
    a.auto_goweight,a.auto_fweight = max(1,x),max(1,y)
    return f"sweight'ed to {a.auto_goweight}:{a.auto_fweight}. (go:fight)"


def auto_radio_command_target(a, mech, args):
    if args[1] == '-':
        return auto_radio_command_autogun(a,mech,['autogun','on'])
    target = contact_target(mech,args[1])
    if target is None or target._id <= 0:
        return '!Unable to see such a target'
    a.target,a.target_score,a.target_update_tick = target._id,0,0
    a.flags |= 256
    _restart_gun(a)
    return f'aiming for [{args[1]}] (and ignoring everyone else)'


# Order matters: "st" without arguments selects stand, with one selects startup.
AUTO_COMMANDS = (
    ('auto','autogun',1,False),('auto','autogun',2,False),
    ('chase','chasetarg',1,False),('dfo','dfollow',1,False),('dgo','dgoto',2,False),
    ('drop','dropoff',0,False),('emb','embark',1,False),
    ('en','enterbase',0,False),('en','enterbase',1,False),
    ('fo','follow',1,False),('go','goto',2,False),
    ('he','heading',1,False),('he','help',0,True),('hi','hide',0,False),
    ('jump','jumpjet',1,False),('jump','jumpjet',2,False),
    ('le','leavebase',1,False),('ogo','ogoto',2,False),('pick','pickup',1,False),
    ('pos','position',2,False),('pr','prone',0,False),('re','report',0,True),
    ('reset','reset',0,False),('se','sensor',2,False),('se','sensor',0,False),
    ('sh','shutdown',0,False),('sp','speed',1,False),('st','stand',0,False),
    ('st','startup',0,False),('st','startup',1,False),('st','stop',0,False),
    ('sw','sweight',2,True),('ta','target',1,False))


def auto_parse_command(a, mech, channel, buffer):
    if a is None or mech is None or mech.is_destroyed:
        return None
    args = explode_arguments(buffer,2)
    if len(args) < 2 or (args[0] != 'all' and args[0].lower() != mech_ids(mech,True)):
        return None
    words = explode_arguments(args[1],5)
    match = next((row for row in AUTO_COMMANDS if words and
                  words[0].startswith(row[0]) and row[1].startswith(words[0]) and len(words) == row[2]+1),None)
    if match is None:
        auto_reply(mech,'Unable to comprehend the command.')
        return {'matched':False}
    _,name,_,silent = match
    message = globals()['auto_radio_command_'+name](a,mech,words) or ''
    if silent:
        return {'matched':True,'command':name,'message':message,'silent':True}
    if message.startswith('!'):
        reply = 'ERROR: '+message[1:]+'!'
    elif message:
        value = draw('ai_radio_ack',0,20,lambda:number(0,20),state=a._engine.randomness)
        if value in (0,1,2,4):
            prefix,suffix = 'Affirmative, ','.'
        elif value == 5:
            prefix,suffix = 'Nod, ','.'
        elif value == 6:
            prefix,suffix = 'Fine, ','.'
        elif value == 7:
            prefix,suffix = 'Aye aye, Captain, ','!'
        elif value in (8,9,10):
            prefix,suffix = 'Da, boss, ','!'
        elif value in (11,12):
            prefix,suffix = 'Ok, ','.'
        elif value == 13:
            prefix,suffix = 'Okay, okay, ', ', happy now?'
        elif value == 14:
            prefix,suffix = 'Okidoki, ','!'
        elif value in (15,16,17):
            prefix,suffix = 'Aye, ','.'
        else:
            prefix,suffix = 'Roger, Roger, ','.'
        reply = prefix+message+suffix
    else:
        reply = 'Ok.'
    auto_reply(mech,reply)
    return {'matched':True,'command':name,'message':message,'reply':reply}

