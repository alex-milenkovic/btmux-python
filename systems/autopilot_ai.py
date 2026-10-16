# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_ai.c

"""Navigation from autopilot_ai.c, including the older predictive steering AI."""
from types import SimpleNamespace
from copy import copy
from entities.autopilot import AStarNode
from entities.mech import UnitType as U, MoveType as M, MechStatus as S, CritStatus, Location as L
from entities.map import LIGHT_FOREST, HEAVY_FOREST, WATER, HIGHWATER, ROUGH, MOUNTAINS
from physics.hexmath import (hex_to_float, float_to_hex, find_range, find_xy,
                            find_bearing, find_components, my_hex_dist, acceptable_degree)
from physics.movement import calculate_effective_max_speed as max_speed, terrain_speed, MP1, MOVE_MOD, MP_PER_KPH
from core.randomness import float32 as f32
from systems.autopilot_core import ai_error
from systems import movement_commands as move

MAGIC_NUM = -123456
SAFE_SCORE = 100000
MOVE_OPTIONS = [(0,1),(0,0),(0,2)] + [(h,0) for step in (1,2,3,5,10,15,20,30,40,60) for h in (-step,step)] + [(-60,2),(60,2),(-60,1),(60,1),(-80,0),(80,0),(-120,0),(120,0),(-160,0),(160,0),(-160,2),(160,2),(-160,1),(160,1)]
FAST_OPTIONS = [(0,1),(0,0),(0,2),(-10,0),(10,0),(-30,0),(30,0),(-60,0),(60,0)]
SPEED_OPTIONS = (0,1,-1)


def sendAIM(a, mech, message):
    from systems.communications import auto_reply
    auto_reply(mech, message)
    ai_error(a, message)


def AI_Info(mech, a):
    return f'Unit#{mech._id} on #{mech.mapindex} [A#{a._id}]:'


def LOCInit(mech):
    from physics.collision import mech_elevation, mech_rterrain
    return SimpleNamespace(fx=mech.fx, fy=mech.fy, e=mech_elevation(mech),
                           h=mech.facing, dh=mech.desired_facing, s=mech.speed,
                           ds=mech.desired_speed, t=mech_rterrain(mech),
                           x=mech.x, y=mech.y, lx=mech.x, ly=mech.y)


def ai_crash(board, mech, loc):
    if board is None:
        return 0
    maximum = max_speed(mech)
    changed = loc.h != loc.dh and not mech.has_crit_status(CritStatus.GYRO_DESTROYED)
    if changed:
        if mech.unit_type in (U.AERO, U.DS, U.SPHEROID_DS):
            maximum = f32(maximum * 5)
        norm = loc.h - loc.dh
        mw = 60 if mech.unit_type in (U.MW, U.BSUIT) else 1
        offset = int((3 if abs(loc.s) < 1 else 2) * maximum * MP_PER_KPH * mw)
        if abs(loc.s) >= 1 and abs(norm) > offset and loc.s > maximum * 2 / 3:
            offset = int(offset - (offset // 2) * (3.0 * loc.s / maximum - 2.0))
        offset = int(offset * MOVE_MOD)
        if norm < 0:
            norm += 360
        if mech.unit_type in (U.DS, U.SPHEROID_DS):
            offset = min(offset, 10)
        if norm > 180:
            loc.h = (loc.h + offset) % 360
            if norm + offset >= 360:
                loc.h = loc.dh
        else:
            loc.h = (loc.h - offset) % 360
            if norm - offset < 0:
                loc.h = loc.dh
    wanted = loc.ds
    if mech.unit_type != U.MW and mech.move_type != M.VTOL and (mech.move_type != M.FLY or mech.has_status(S.LANDED)):
        wanted = terrain_speed(mech, wanted, maximum, loc.t, loc.e)
    if changed:
        from physics.movement import btech_config
        slowdown = btech_config(mech, 'btech_slowdown', 2)
        if slowdown == 2:
            diff = abs(mech.facing - mech.desired_facing)
            if diff > 180:
                diff = 360 - diff
            if diff:
                wanted = f32(wanted * (10 - ((diff - 1) // 30 + 2)) / 10)
        elif slowdown == 1:
            wanted = f32(wanted * (2.0 / 3.0 if loc.h != loc.dh else 3.0 / 4.0))
    if mech.move_type == M.QUAD and mech.lateral:
        wanted -= MP1
    wanted = max(0.0, wanted)
    if loc.ds < 0:
        wanted = -wanted
    acceleration = maximum / (10 if mech.move_type == M.QUAD else 20)
    if wanted < loc.s:
        loc.s = f32(max(wanted, loc.s - acceleration))
    elif wanted > loc.s:
        loc.s = f32(min(wanted, loc.s + acceleration))
    dx, dy = find_components(f32(loc.s * MOVE_MOD), loc.h)
    loc.fx, loc.fy = f32(loc.fx + dx), f32(loc.fy + dy)
    loc.lx, loc.ly = loc.x, loc.y
    loc.x, loc.y = float_to_hex(loc.fx, loc.fy)
    if not board.valid(loc.x, loc.y):
        return 1
    if (loc.lx, loc.ly) != (loc.x, loc.y):
        old = loc.e
        terrain = board.rterrain(loc.x, loc.y)
        if terrain == HEAVY_FOREST and mech.unit_type != U.MECH:
            return 1
        if terrain == HIGHWATER:
            return 1
        if terrain == WATER:
            if mech.move_type in (M.TRACK, M.WHEEL):
                return 1
            if mech.unit_type == U.MECH:
                depth = board.elevation(loc.x, loc.y)
                locations = ((L.LLEG, L.RLEG, L.LARM, L.RARM) if mech.move_type == M.QUAD else (L.LLEG, L.RLEG)) if depth == -1 else range(len(mech.sections))
                if depth < 0:
                    for index in locations:
                        section = mech.sections[index]
                        if section.internal and (not section.armor or not section.rear and section.rear_orig):
                            return 1
        loc.e = board.elevation(loc.x, loc.y)
        if mech.move_type == M.HOVER:
            loc.e = max(0, loc.e)
        loc.t = terrain
        if abs(loc.e - old) > (2 if mech.unit_type == U.MECH else 1 if mech.unit_type == U.VEH_GROUND else 100000):
            return 1
    return 0


def _neighbor_state(mech, board, friends):
    # C file-static slots belong to the simulation, not the scanning mech.
    # Keep inactive slots too: a shorter scan does not clear their out flags.
    owner = getattr(mech, '_engine', None) or board
    key = '_ai_friends' if friends else '_ai_enemies'
    state = getattr(owner, key, None)
    if state is None:
        state = SimpleNamespace(slots=[], count=0)
        setattr(owner, key, state)
    return state


def _nearby(mech, board, reset, friends):
    state = _neighbor_state(mech, board, friends)
    if reset:
        for row in state.slots[:state.count]:
            row.loc, row.out = LOCInit(row.mech), False
        return 0
    from systems.targeting import fa_mech_range
    state.count = 0
    for index, unit in enumerate(board.mechs_on_map):
        if unit is None or unit.is_destroyed:
            continue
        if friends:
            if unit.team != mech.team or unit.unit_type != U.MECH:
                continue
        elif unit.team == mech.team or unit.has_status(S.COMBAT_SAFE):
            continue
        if fa_mech_range(mech, unit) > 50:
            continue
        if state.count == len(state.slots):
            state.slots.append(SimpleNamespace(out=False))
        row = state.slots[state.count]
        row.mech, row.loc, row.index = unit, LOCInit(unit), index
        state.count += 1
    return state.count


def getEnemies(mech, board, reset=0):
    return _nearby(mech, board, reset, False)


def getFriends(mech, board, reset=0):
    return _nearby(mech, board, reset, True)


def ai_path_score(mech, board, a, options, gotenemy, dx, dy, delx=0.0, dely=0.0):
    states = []
    for heading, speed in options:
        loc = LOCInit(mech)
        loc.dh = acceptable_degree(loc.dh + heading)
        if speed == 2:
            loc.ds = f32(loc.ds * 2.0 / 3.0)
        elif speed == 1:
            loc.ds = min(max_speed(mech), f32(max(MP1, loc.ds) * 4.0 / 3.0))
        states.append(SimpleNamespace(loc=loc, msc=0, bsc=0, dan=0, tdan=0, out=0, stack=0, br=9999))
    friend_state = _neighbor_state(mech, board, True)
    enemy_state = _neighbor_state(mech, board, False)
    friends = friend_state.slots[:friend_state.count]
    enemies = enemy_state.slots[:enemy_state.count]
    for tick in range(32):
        dx, dy = f32(dx + delx), f32(dy + dely)
        for state, option in zip(states, options):
            loc = state.loc
            if state.out:
                continue
            if ai_crash(board, mech, loc):
                state.out = tick + 1
                continue
            distance = int(find_range(loc.fx, loc.fy, dx, dy))
            state.br = min(state.br, distance)
            state.msc += 4 * (2 * (50 - state.br) + 100 - distance)
            state.msc -= int(loc.h != loc.dh)
            if (loc.x, loc.y) != (loc.lx, loc.ly):
                state.msc += 10 - (5 if loc.t == WATER else 0)
            if option[1] != 1 and max_speed(mech) > .1:
                state.msc -= int((100 - int(min(100, max(0, 100 * loc.ds / max_speed(mech))))) / 30)
        if mech.unit_type == U.MECH:
            for friend in friends:
                if not friend.out:
                    friend.out = bool(ai_crash(board, friend.mech, friend.loc))
            for state in states:
                if state.out or state.stack:
                    continue
                loc = state.loc
                sharing = [f for f in friends if not f.out and (loc.x,loc.y) == (f.loc.x,f.loc.y)]
                if len(sharing) > 1 and ((loc.x,loc.y) != (loc.lx,loc.ly) or any((f.loc.x,f.loc.y) != (f.loc.lx,f.loc.ly) for f in sharing)):
                    state.stack = tick + 1
                if gotenemy:
                    state.tdan = 0
        if gotenemy:
            for enemy in enemies:
                if enemy.out:
                    continue
                enemy.out = bool(ai_crash(board, enemy.mech, enemy.loc))
                for state in states:
                    loc = state.loc
                    if state.out:
                        continue
                    distance = my_hex_dist(loc.x,loc.y,enemy.loc.x,enemy.loc.y,0)
                    if distance >= 100:
                        continue
                    delta = distance - a.auto_cdist
                    if a.auto_cmode == 0:
                        state.bsc += 5 * min(distance,a.auto_cdist) + max(0,delta)
                    elif a.auto_cmode == 1:
                        state.bsc -= (10 if delta < 0 else 2) * abs(delta)
                    elif a.auto_cmode == 2:
                        state.bsc -= (2 if delta < 0 else 10) * abs(delta)
                    if distance > 28:
                        continue
                    state.tdan += 40 - min(40,distance)
                    bearing = (loc.h - find_bearing(loc.fx,loc.fy,enemy.loc.fx,enemy.loc.fy)) % 360
                    if mech.unit_type == U.MECH and 90 <= bearing <= 270:
                        state.tdan += (5 + (20 if 120 <= bearing <= 240 else 0)) * (29 - min(29,distance))
                    elif mech.unit_type == U.VEH_GROUND:
                        section, factor = ((3,10) if 135 <= bearing <= 225 else (1,7) if 45 <= bearing < 135 else (0,7) if 225 < bearing <= 315 else (2,5))
                        armor = mech.sections[section]
                        lost = 100 - 100 * armor.armor // max(1,armor.armor_orig)
                        state.tdan += int(factor * (29 - min(29,distance)) * lost / 100)
                # This reduction is inside the enemy loop in C.
                for state in states:
                    if state.out:
                        continue
                    loc = state.loc
                    distance = int(find_range(loc.fx,loc.fy,dx,dy))
                    if delx != 0 or dely != 0:
                        state.tdan += min(100,distance*distance)
                    if enemies:
                        state.tdan = int(state.tdan / len(enemies))
                    state.tdan += (400 if loc.s <= 2*MP1 else 300 if loc.s <= 4*MP1 else 200 if loc.s <= 6*MP1 else 100 if loc.s <= 9*MP1 else 0)
                    state.dan += int(state.tdan * (32-tick) / 16)
    for field in ('msc','bsc','dan') if gotenemy else ('msc',):
        for prefix, op in (('w_',min),('b_',max)):
            current = getattr(a,prefix+field)
            values = [getattr(s,field) for s in states]
            setattr(a,prefix+field,op(values if current == MAGIC_NUM else values+[current]))
    def normalized(value,low,high,scale):
        return int(scale*(value-low)/(high-low)) if high != low else 0
    best, index, length = 0,-1,0
    for i, state in enumerate(states):
        out = state.out or 33
        stack = state.stack or out
        score = (out - int((out-stack)/2))*SAFE_SCORE + normalized(state.msc,a.w_msc,a.b_msc,100*a.auto_goweight)
        if gotenemy:
            score += normalized(state.bsc,a.w_bsc,a.b_bsc,100*a.auto_fweight) - normalized(state.dan,a.w_dan,a.b_dan,100*(a.auto_fweight+a.auto_goweight))
        if score > best or index >= 0 and score == best and SPEED_OPTIONS[options[i][1]] > SPEED_OPTIONS[options[index][1]]:
            best,index,length = score,i,out-1
    return length,index,best


def ai_max_speed(mech, a):
    return int(mech.desired_speed == max_speed(mech))


def ai_opponents(a, mech):
    if a.auto_nervous:
        a.auto_nervous -= 1
        return 1
    if mech.num_seen:
        a.auto_nervous = 30
    return mech.num_seen


def ai_run_speed(mech, a):
    if not ai_max_speed(mech,a):
        return move.speed(a._engine,mech,'run',caller=a)


def ai_stop(mech, a):
    if mech.desired_speed > .1:
        return move.speed(a._engine,mech,'stop',caller=a)


def ai_set_speed(mech, a, speed):
    if mech is None or a is None:
        return
    wanted = f32(max(0,min(speed,f32(max_speed(mech)*a.speed/100.0))))
    if mech.desired_speed != wanted:
        return move.speed(a._engine,mech,f'{wanted:f}',caller=a)


def ai_set_heading(mech, a, heading):
    if heading != mech.desired_facing:
        return move.heading(a._engine,mech,str(heading),caller=a)


def ai_adjust_move(a, mech, text, heading, speed, score):
    ai_set_heading(mech,a,mech.desired_facing+heading)
    label = '' if speed == 0 else '+accelerating' if speed == 1 else '+decelerating'
    ai_error(a,f'{AI_Info(mech,a)} state: {text}{label} (hmod:{heading}) sc:{score}')
    if speed == 1:
        ai_set_speed(mech,a,f32(max(MP1,mech.desired_speed)*4.0/3.0))
    elif speed == 2:
        ai_set_speed(mech,a,int(mech.desired_speed*2.0/3.0))


def ai_check_path(mech, a, dx, dy, delx=0.0, dely=0.0):
    enemy = ai_opponents(a,mech)
    engine, board = a._engine, mech.map
    if a.last_upd > engine.sim_now or engine.sim_now-a.last_upd > 15:
        if engine.tick-a.last_upd > 240:
            for key in ('b_msc','w_msc','b_bsc','w_bsc','b_dan'):
                setattr(a,key,MAGIC_NUM)
            a.b_dan = 21600  # Source assigns b_dan twice; w_dan is retained.
        else:
            for field,mod in (('msc',3),('bsc',5),('dan',8)):
                low,high = getattr(a,'w_'+field),getattr(a,'b_'+field)
                if low != MAGIC_NUM and high != MAGIC_NUM:
                    setattr(a,'w_'+field,int((low*(mod-1)+high)/mod))
                    setattr(a,'b_'+field,int((low+high*(mod-1))/mod))
            a.b_dan = max(a.b_dan,21600)
        a.last_upd = engine.sim_now
    if mech.unit_type == U.MECH:
        getFriends(mech,board)
    if enemy:
        getEnemies(mech,board)
    from systems.autopilot import uses_event_autopilot
    cadence = 3 if uses_event_autopilot(mech) else 4
    thorough = not (engine.tick//cadence)%4
    options = MOVE_OPTIONS if thorough else FAST_OPTIONS
    length,index,score = ai_path_score(mech,board,a,options,enemy,dx,dy,delx,dely)
    safe = int(score/SAFE_SCORE) >= 8
    if safe:
        label = ('combat(/twitchy)' if enemy else 'moving')
        ai_adjust_move(a,mech,('' if thorough else '[f]')+label,*options[index],score)
    if enemy or safe:
        return 1
    ai_stop(mech,a)
    ai_error(a,f'{AI_Info(mech,a)} state: panic')
    sendAIM(a,mech,'PANIC! Unable to comply with order.')
    return 0


def ai_init(a, mech):
    a.auto_cmode,a.auto_cdist,a.auto_nervous = 1,2,0
    a.auto_goweight,a.auto_fweight,a.speed,a.flags,a.target = 44,55,100,0,-1


def mech_snipe_func(mech, player, index, high, target):
    from systems.artillery import artillery_round_flight_time
    from systems.targeting import set_target_hex
    from systems.combat import fire_weapon_number
    loc = LOCInit(target)
    now,crashed = 0,False
    while artillery_round_flight_time(mech.fx,mech.fy,loc.fx,loc.fy) > now:
        if not crashed:
            crashed = bool(ai_crash(mech.map,target,loc))
        now += 1
    if (mech.targ_x,mech.targ_y) != (loc.x,loc.y):
        set_target_hex(mech._engine,mech,loc.x,loc.y,caller=player)
    fire_weapon_number(mech._engine,mech,index,caller=player)
    return 0


def mech_snipe(player, mech, buffer):
    from systems.targeting import find_mech_on_map
    from systems.weapon_inventory import weapon_runs
    if not (getattr(player,'wizard',False) or getattr(player,'royalty',False) or player == 1):
        return dict(ok=False,error='Permission denied.')
    args = buffer.split()[:3]
    if len(args) != 2:
        return dict(ok=False,error='Please supply target ID _and_ weapon(s) to use')
    target = find_mech_on_map(mech.map,args[0])
    if target is None or target._id <= 0:
        return dict(ok=False,error='Invalid target!')
    from systems.tic import multi_weap_sel
    messages = []
    accepted = multi_weap_sel(mech,args[1],1,lambda unit,low,high: mech_snipe_func(unit,player,low,high,target),messages)
    return dict(ok=accepted,messages=messages)


def auto_create_astar_node(x,y,x_parent,y_parent,g_score,h_score):
    from entities.map_storage import signed_value
    g,h = signed_value(g_score,16),signed_value(h_score,16)
    return AStarNode(x,y,x_parent,y_parent,g,h,g+h,x*1000+y)


def astar_compare(a,b,arg=None):
    return a-b


def astar_release(key,data):
    """Python owns node lifetimes; removing tree/list references releases them."""


def auto_astar_generate_path(a,mech,end_x,end_y):
    from systems.targeting import indexed_map
    board = indexed_map(a)
    auto_destroy_astar_path(a)
    a.astar_path = []
    if board is None or not board.valid(end_x,end_y) or not board.valid(mech.x,mech.y):
        return 0
    start = auto_create_astar_node(mech.x,mech.y,-1,-1,0,0)
    scores,opened,closed = {0:start},{(start.x,start.y):start},{}
    destination = hex_to_float(end_x,end_y)
    while scores:
        node = scores.pop(min(scores))
        pos = node.x,node.y
        opened.pop(pos)
        closed[pos] = node
        if pos == (end_x,end_y):
            path = [node]
            while (node.x_parent,node.y_parent) != (mech.x,mech.y) and (node.x,node.y) != (mech.x,mech.y):
                node = closed[node.x_parent,node.y_parent]
                path.insert(0,node)
            a.astar_path = path
            return 1
        fx,fy = hex_to_float(*pos)
        for bearing in range(0,360,60):
            next_real = find_xy(fx,fy,bearing,1.0)
            x,y = float_to_hex(*next_real)
            if not board.valid(x,y) or (x,y) in closed:
                continue
            difference = abs(board.elevation(*pos)-board.elevation(x,y))
            if difference > (2 if mech.unit_type == U.MECH else 1 if mech.unit_type == U.VEH_GROUND else 100000):
                continue
            terrain = board.terrain(x,y)
            if mech.unit_type == U.VEH_GROUND:
                if terrain == LIGHT_FOREST and mech.move_type != M.TRACK or terrain == HEAVY_FOREST:
                    continue
                if terrain in (WATER,HIGHWATER) and mech.move_type != M.HOVER and not getattr(mech,'specials2',0)&0x100000:
                    continue
            g = node.g_score + 100
            from physics.collision import mechs_in_hex
            stacked = mechs_in_hex(board,x,y,1,mech.team)
            from systems.autopilot import uses_event_autopilot
            if stacked > 2 and not uses_event_autopilot(mech):
                g += 150
            g += {LIGHT_FOREST:50,ROUGH:50,HEAVY_FOREST:100,MOUNTAINS:100,WATER:200,HIGHWATER:200}.get(terrain,0)
            h = int(f32(100*find_range(*next_real,*destination)))
            child = opened.get((x,y))
            if child is not None:
                if g >= child.g_score:
                    continue
                scores.pop(child.f_score)
                child.g_score,child.f_score = g,g+child.h_score
                child.x_parent,child.y_parent = pos
            else:
                child = auto_create_astar_node(x,y,*pos,g,h)
            # Source increments colliding f scores, rather than a stable heap key.
            while child.f_score in scores:
                child.f_score += 1
            scores[child.f_score] = child
            opened[x,y] = child
    return 0


def astar_smooth_path(a):
    """The active C function explicitly does nothing (unfinished smoothing)."""


def auto_destroy_astar_path(a):
    if a.astar_path is not None:
        a.astar_path.clear()
    a.astar_path = None

