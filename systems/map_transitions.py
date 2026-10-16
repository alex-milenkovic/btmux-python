# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_commands.c
#   btech/mech.utils.c
# Historical Aerospace sources:
#   btech/ds.bay.c
#   btech/mech.restrict.c

"""Source CheckEdgeOfMap and Leave_Hangar, with local map-object metadata.

Map objects supply linked, leave_target and entrances. Local personnel movement
and autopilot indices are applied; unavailable server services stay explicit.
"""
from core.events import EventType
from entities.mech import MechStatus as S, UnitType as U, MoveType as M
from physics.hexmath import hex_to_float, ZSCALE
from systems.damage import external_effect
from systems.movement_commands import notify


def transfer(unit, board, actor=None):
    """Rsetmapindex with source validation, ordered mutation and actor feedback."""
    from core.randomness import draw, number
    from core.effects import notify_actor
    from systems.targeting import valid_map, map_record, resolve_object
    from systems.parts import source_text
    from systems.map_membership import add, remove
    from systems.c3 import clear
    from entities.mech import Mech
    actor = actor if actor is not None else (getattr(unit, 'command_actor', None) or unit.pilot or 1)
    actor_id = actor if isinstance(actor, int) else getattr(actor, '_id', -1)
    def notice(text): notify_actor(unit, actor, text)
    removing = isinstance(board, int) and board == -1
    if isinstance(board, int) and board < -1:
        notice('Invalid map index!'); return False
    if not removing:
        board, error = valid_map(map_record(unit, board))
        if error: notice(error); return False
    old = None
    if unit.mapindex != -1:
        old, error = valid_map(map_record(unit, unit.mapindex))
        if error: notice(error); return False
        unit.map = old  # The registry index is authoritative over the cache.
        # Recovered Aerospace/bay transfers remove membership before networks;
        # the general profile clears networks before removal.
        aerospace = unit.unit_type in (U.AERO, U.DS, U.SPHEROID_DS) or any(
            isinstance(resolve_object(unit, getattr(m, 'onmap', 0)), Mech)
            for m in (old, board) if m is not None)
        if aerospace: remove(old, unit)
        unit.tag_target = -1
        clear(unit, ordinary=False)
        clear(unit, ordinary=True)
        if not aerospace: remove(old, unit)
    if removing:
        notice('Mech removed from map.')
        location_log(unit, f'#{actor_id} removed #{unit._id} from map #{old._id if old else -1}.')
        return True
    existing = {peer.contact_id[:2] for peer in board.mechs_on_map if peer is not None}
    if len(existing) >= 26 * 26:
        raise ValueError('Destination contact-ID space is exhausted')
    preferred = source_text(getattr(unit, 'preferred_contact_id', ''))
    state = getattr(getattr(unit, '_engine', None), 'randomness', None)
    def random_id():
        return ''.join(chr(65 + draw('map_contact_id', 0, 25,
                       lambda: number(0, 25), state=state)) for _ in range(2))
    contact = ''.join(chr(min(90,max(65,ord(letter.upper())))) for letter in preferred[:2]) if len(preferred)>1 else random_id()
    while contact in existing: contact = random_id()
    if len(board.mechs_on_map) >= 255:
        notice('There are too many mechs on that map!'); return False
    add(board, unit)
    unit.contact_id = contact
    if unit.x >= board.map_width or unit.y >= board.map_height:
        unit.x = unit.y = unit.last_x = unit.last_y = 0
        unit.fx, unit.fy = hex_to_float(0, 0)
        unit.terrain, unit.elev = board.terrain(0, 0), board.elevation(0, 0)
        notice("You're current position is out of bounds, Pos changed to 0,0")
    notice(f'MapIndex changed to {board._id}')
    notice(f'Your ID: {unit.contact_id}')
    location_log(unit, f"#{actor_id} set #{unit._id}'s mapindex to #{board._id}.")
    return True


def location_log(unit, text):
    # SendLoc is disabled in this source configuration; retain the request.
    unit.location_requests = getattr(unit, 'location_requests', [])
    unit.location_requests.append(dict(service='SendLoc', text=text, applied=False))


def flying_type(unit):
    """FlyingT uses Aerospace class or VTOL movement, including mixed templates."""
    return unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS) or unit.move_type==M.VTOL


def set_xy(unit,x,y,*,actor=1):
    """Two-coordinate Rsetxy, shared by personnel, orbital drops and bay entry."""
    from core.effects import notify_actor
    from systems.targeting import indexed_map
    from systems.ecm import mark_for_los_update
    from systems.map_membership import clear_los
    from physics.movement import drop_set_elevation
    unit.last_use=0
    if unit.mapindex<0:
        notify_actor(unit,actor,'You are on no map!');return False
    board=indexed_map(unit)
    if board is None:
        from systems.combat_commands import reset_invalid_map
        reset_invalid_map(unit,actor)
        return False
    if not board.valid(x,y):
        notify_actor(unit,actor,'Invalid coordinates!');return False
    unit.map=board
    unit.x=unit.last_x=x;unit.y=unit.last_y=y
    unit.fx,unit.fy=hex_to_float(x,y)
    unit.terrain=board.terrain(x,y)
    mark_for_los_update(unit)
    unit.elev=board.elevation(x,y);unit.z=unit.elev-1;unit.fz=unit.z*ZSCALE
    drop_set_elevation(unit,0)
    if flying_type(unit):unit.set_status(S.LANDED)
    clear_los(unit)
    notify_actor(unit,actor,f'Pos changed to {x},{y},{unit.z}')
    actor_id=actor if isinstance(actor,int) else actor._id
    location_log(unit,f"#{actor_id} set #{unit._id}'s pos to {x},{y},{unit.z}.")
    return True


def set_team(unit,team,*,actor=1):
    from core.effects import notify_actor
    from systems.targeting import valid_map,map_record
    if unit.mapindex==-1:
        notify_actor(unit,actor,"Mech is not on a map:  Can't set team");return False
    board,error=valid_map(map_record(unit,unit.mapindex))
    if error:
        notify_actor(unit,actor,error);notify_actor(unit,actor,'Map index reset!')
        unit.mapindex=-1;return False
    unit.team=max(0,team)
    notify_actor(unit,actor,f'Team set to {unit.team}')
    return True


def auto_cal_mapindex(unit):
    from systems.targeting import resolve_object
    from core.effects import send_error
    ident = getattr(unit, 'auto', -1)
    if ident <= 0: return
    autopilot = resolve_object(unit, ident)
    if (autopilot is None or not getattr(autopilot, 'valid_object', getattr(autopilot, 'valid', True))
            or getattr(autopilot, 'location', None) != unit._id):
        send_error(unit, f'Mech #{unit._id} thinks it has the Autopilot #{ident} on it but FindObj breaks')
        unit.auto = -1
        return
    getter = getattr(autopilot, 'get_command_enum', None)
    command = getter(1) if getter is not None else getattr(autopilot, 'current_command', None)
    if command not in (3, 6, 'GOAL_ENTERBASE', 'GOAL_LEAVEBASE', 'enterbase', 'leavebase'):
        autopilot.mapindex = unit.mapindex


def leave_hangar(board, unit):
    from systems.sensors import los_broadcast
    from systems.swarm import swarmers, detach
    from physics.cargo import cargo_max_speed
    if not getattr(board,'cf',0):
        notify(unit,'The entrance is still filled with rubble!')
        return False
    engine, old_id = unit._engine, unit.mapindex
    from systems.map_links import by_target
    target_id = board.map_objects[5][0].obj if board.map_objects[5] else getattr(board,'leave_target',None)
    from systems.targeting import resolve_object
    from systems.notifications import unit_identity
    from core.effects import send_error
    destination = resolve_object(unit, target_id)
    los_broadcast(unit,'has left the hangar.')
    carried = resolve_object(unit, unit.carrying) if unit.carrying > 0 else None
    from entities.mech import Mech
    if not isinstance(carried, Mech): carried = None
    transfer(unit, destination, actor=1)
    if carried is not None: transfer(carried, destination, actor=1)
    if unit.mapindex == old_id:
        send_error(unit, f'#{unit._id} {unit_identity(unit)} attempted to leave, but no target map?')
        notify(unit,'Exit of this map is.. fubared. Please contact a wizard')
        return False
    destination = unit.map
    if destination is None: return False
    object_entrance=by_target(destination,old_id)
    entrance=({'x':object_entrance.x,'y':object_entrance.y,'name':'the '+board.name}
              if object_entrance is not None else getattr(destination,'entrances',{}).get(old_id))
    if entrance is None:
        send_error(unit, f'#{unit._id} {unit_identity(unit)} attempted to leave, but no target place was found? setting the mech at 0,0 at {unit.mapindex}.')
        notify(unit,'Weird bug happened during leave. Please contact a wizard. ')
        return True
    for suit in swarmers(unit): detach(suit,intentional=True)
    name = entrance.get('name')
    if name is None:
        external_effect(unit,'persistent-map-objects','structure_name')
    else: notify(unit,f'You have left {name}.')
    unit.x, unit.y = entrance['x'], entrance['y']
    unit.last_x,unit.last_y = unit.x,unit.y
    unit.fx, unit.fy = hex_to_float(unit.x,unit.y)
    unit.terrain,unit.elev = destination.terrain(unit.x,unit.y),destination.elevation(unit.x,unit.y)
    unit.z = unit.elev - 1
    unit.fz = unit.z * ZSCALE
    from physics.movement import drop_set_elevation
    drop_set_elevation(unit,0)
    from systems.ecm import mark_for_los_update
    mark_for_los_update(unit)
    if unit.move_type == M.VTOL or unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS):
        unit.clear_status(S.LANDED)
        unit.z += 1
        unit.fz = unit.z * ZSCALE
        engine.cancel_events_of_type(EventType.MOVE,unit)
    if carried is not None:
        for key in ('fx','fy','fz','x','y','z','last_x','last_y','terrain','elev'): setattr(carried,key,getattr(unit,key))
        from systems.ecm import mark_for_los_update
        from physics.flooding import flood_unit
        mark_for_los_update(carried)
        flood_unit(carried)
    if name is not None: los_broadcast(unit,f'has left {name} at {unit.x},{unit.y}.')
    from systems.dropships import move_object
    move_object(unit, unit.mapindex)
    if carried is not None: move_object(carried, unit.mapindex)
    if unit.in_character and getattr(unit.pilot,'location',None) != unit._id:
        notify(unit,'%ch%cr%cf%ciINTRUDER ALERT! INTRUDER ALERT!%c')
        notify(unit,'%ch%cr%cfAutomatic self-destruct sequence initiated...%c')
        from systems.startup import shutdown
        shutdown(engine,unit,wizard=True)
    auto_cal_mapindex(unit)
    unit.speed = min(unit.speed,cargo_max_speed(unit))
    return True


def check_edge_of_map(unit):
    from systems.targeting import indexed_map, resolve_object
    from core.effects import send_error
    board, engine = indexed_map(unit), unit._engine
    if board is None:
        notify(unit,'You are on an invalid map! Map index reset!', audience=0)
        if engine is not None:
            from systems.startup import shutdown
            shutdown(engine,unit)
        send_error(unit, f'CheckEdgeofMap:invalid map:Mech: {unit._id}  Index: {unit.mapindex}')
        unit.mapindex = -1
        return
    unit.map = board
    from systems.map_links import linked as map_linked
    linked, pinned = map_linked(board) or getattr(board,'linked',False), 0
    for axis, limit, low, high in (('x',board.map_width,4,2),('y',board.map_height,1,3)):
        value = getattr(unit,axis)
        if value < 0:
            setattr(unit,axis,value + limit if linked else 0)
            pinned = -1 if linked else low
        elif value >= limit:
            setattr(unit,axis,value - limit if linked else limit - 1)
            pinned = -1 if linked else high
    if pinned > 0:
        from entities.mech import Mech
        parent = resolve_object(unit, getattr(board, 'onmap', 0))
        if getattr(board, 'onmap', 0) and isinstance(parent, Mech):
            from systems.dropships import leave_bay
            if leave_bay(board,unit): return
        elif board.flags & 1 and (board.map_objects[5] or getattr(board,'leave_target',None) is not None):
            if leave_hangar(board,unit): return
    if not pinned: return
    unit.fx, unit.fy = hex_to_float(unit.x,unit.y)
    if pinned < 0: return
    notify(unit,'You cannot move off this map!')
    aero = unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS)
    if unit.is_jumping and not aero:
        from physics.jump import land_mech
        land_mech(unit,event_queue=engine.events if engine else None)
    unit.cocoon = 0
    unit.speed = unit.desired_speed = 0
    if aero:
        unit.start_fx = unit.start_fy = unit.start_fz = 0
        if not unit.has_status(S.LANDED) and engine is not None:
            from systems.movement_commands import maybe_move
            maybe_move(engine,unit)
