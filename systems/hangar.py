# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.maps.c

"""Building entrances use the shared map links and eighteen-tick event queue."""
from core.events import EventType
from entities.mech import UnitType as U, MechStatus as S
from entities.map_objects import find_object,resolve_map
from systems.map_links import entrance
from systems.dropships import enter_lock,set_xy,move_object,resolve
from systems.communications import common_checks,MECH_USUAL
from systems.movement_commands import pending,notify
from physics.cargo import cargo_max_speed
from physics.cargo import MP1
from systems.observation import response


def condition_error(unit,completion=False):
    if completion and (not unit.is_started or unit.is_unconscious):return 'Entry cancelled.'
    if unit.is_jumping:return 'While in mid-jump? No way.'
    if unit.unit_type==U.MECH and (unit.is_fallen or pending(unit,'_stand_event')):return 'Crawl inside? I think not. Stand first.'
    if unit.cocoon:return 'While in mid-flight? No way.'
    if unit.unit_type==U.VTOL and unit.fuel<=0:return 'You lack fuel to maneuver in!'
    if not completion:
        if unit.unit_type in (U.VTOL,U.AERO,U.DS,U.SPHEROID_DS) and not unit.status&S.LANDED:return 'You need to land before you can enter the hangar.'
        if unit.unit_type in (U.DS,U.SPHEROID_DS):return "Heh, you're trying to be funny, right, a DropShip entering hangar?"
    maximum=cargo_max_speed(unit)
    if abs(unit.speed)*5>=maximum and abs(maximum)>=MP1:return 'You are moving too fast to enter the hangar!'
    return None


def destination(unit,direction):
    link=find_object(unit.map,unit.x,unit.y,4) if unit.map else None
    if link is None:return None,None,None,'You see nothing to enter here!'
    board=resolve_map(unit.map,link.obj)
    door=entrance(board,direction) if board else None
    if door is None:return link,board,None,'You sense wrongness in fabric of space..'
    return link,board,door,None


def lock_error(unit,board):
    allowed=enter_lock(unit,board)
    if allowed is None:return 'Enter lock service unavailable.',['MUX-expression-lock']
    if not allowed and (board.buildflag&8 or board.cf>=board.cfmax//2):
        from core.attributes import attributes_for
        return attributes_for(board,attributes_for(unit)).get(board._id,'A_FAIL',getattr(board,'fail_message','')) or 'The hangar is locked.',[]
    return None,[]


def enter_base(unit,argument='',caller=None):
    from systems.combat_commands import parse_attributes
    args=parse_attributes(str(argument),2)
    if len(args)>1:return response(False,'Invalid arguments to command!')
    direction=args[0].lower() if args and len(args[0])==1 else 0
    error=common_checks(unit,caller if caller is not None else getattr(unit,'pilot',None),MECH_USUAL)
    if error is None:error=condition_error(unit)
    if error is not None:return response(False,error)
    link,board,door,error=destination(unit,direction)
    if error:
        if link is not None:
            from core.effects import send_error
            notify(unit,error)
            send_error(unit,f'Error: No {"map" if board is None else "entrance"} existing for mapindex #{link.obj} (@ {link.x},{link.y} of #{unit.mapindex})')
            return response(False,error,notified=True)
        return response(False,error)
    error,blocked=lock_error(unit,board)
    if error:
        if blocked:return response(False,error,blocked=blocked)
        from core.effects import did_it
        actor=caller if caller is not None else getattr(unit,'command_actor',unit.pilot)
        did_it(unit,actor,board,'A_FAIL',error,None,None,'A_AFAIL')
        return response(False,error,notified=True)
    if unit._engine.has_event(EventType.ENTER_HANGAR,unit):return response(False,'You are already entering the hangar!')
    from systems.notifications import hex_broadcast
    hex_broadcast(unit.map,unit.x,unit.y,'The doors at $h start to open..')
    unit._engine.schedule_event(18,EventType.ENTER_HANGAR,enter_event,data=unit,data2=direction)
    return response(scheduled=True,due=unit._engine.tick+18)


def enter_event(event):
    unit=event.data
    if condition_error(unit,True):return
    link,board,door,error=destination(unit,event.data2)
    if error:return
    error,blocked=lock_error(unit,board)
    if error:notify(unit,error);return
    from systems.swarm import detach_all
    from systems.sensors import los_broadcast
    from systems.ecm import mark_for_los_update
    from systems.map_transitions import transfer
    from systems.buildings import structure_name
    from systems.damage import external_effect
    source_map=unit.map
    from systems.movement_commands import historical_aircraft
    historical=historical_aircraft(unit)
    detach_all(unit,intentional=True,historical=historical)
    notify(unit,f'You enter {structure_name(source_map,link)}.')
    los_broadcast(unit,f'has entered {structure_name(source_map,link)} at {unit.x},{unit.y}.')
    mark_for_los_update(unit)
    if unit.unit_type==U.MW and not getattr(board,'in_character',False):
        from systems.occupants import enter_mw_bay
        enter_mw_bay(unit,board._id)
        unit.building_entries=getattr(unit,'building_entries',0)+1
        return
    else:
        carried=resolve(unit,unit.carrying) if unit.carrying>0 else None
        x,y=unit.x,unit.y
        transfer(unit,board,actor=1);set_xy(unit,door.x,door.y)
        if historical:
            los_broadcast(unit,f'has entered {structure_name(source_map,link)} at {unit.x},{unit.y}.')
        else:
            los_broadcast(unit,f'has entered {structure_name(source_map,link)} at {x},{y}.')
            if carried is not None:los_broadcast(carried,f'has entered {structure_name(source_map,link)} at {x},{y}.')
        move_object(unit,board._id)
        if carried is not None:
            transfer(carried,board,actor=1);set_xy(carried,door.x,door.y);move_object(carried,board._id)
    unit.building_entries=getattr(unit,'building_entries',0)+1
    from systems.map_transitions import auto_cal_mapindex
    auto_cal_mapindex(unit)
