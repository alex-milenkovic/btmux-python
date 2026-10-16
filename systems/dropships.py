# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Historical Aerospace sources:
#   btech/ds.bay.c
#   btech/mech.restrict.c

"""Dropship door geometry and delayed transfers through real map ownership."""
from core.events import EventType
from entities.mech import Mech, UnitType as U, MoveType as M, MechStatus as S, FireMode
from entities.map import GameMap
from entities.crittypes import i2special, Special
from physics.aerospace import adjacent, flying, is_ds, continue_flying
from physics.cargo import cargo_max_speed
from physics.hexmath import hex_to_float
from systems.communications import common_checks, MECH_USUAL
from systems.movement_commands import notify, pending
from systems.damage import external_effect

DOOR_LOCATIONS=(5,0,3,4,2,1)
MECHDOOR=i2special(Special.DS_MECHDOOR)
AERODOOR=i2special(Special.DS_AERODOOR)


def resolve(unit, identity):
    return next((obj for obj in unit._engine.get_entities() if getattr(obj,'_id',None)==identity),None)


def create_bays(ship, references):
    args=str(references).split() if isinstance(references,str) else references
    if len(args)>=5: return False,'Invalid number of arguments!'
    for i,arg in enumerate(args):
        try: identity=int(str(arg).lstrip('#'))
        except ValueError: identity=-1
        obj=resolve(ship,identity)
        if obj is None: return False,f'Argument {i+1} is invalid.'
        if not isinstance(obj,GameMap): return False,f'Argument {i+1} is not a map.'
        ship.aero_bays[i]=identity
        obj.onmap=ship._id
    ship.aero_bays[len(args):]=[-1]*(4-len(args))
    return True,f'{len(args)} bay(s) set up!'


def bay_number(ship,direction):
    count=0
    for i in range(direction+1):
        if any(slot.type in (MECHDOOR,AERODOOR) for slot in ship.sections[DOOR_LOCATIONS[i%6]].criticals):
            if i==direction: return count
            count+=1
    return -1


def bay_direction(ship,index):
    return next((i for i in range(6) if bay_number(ship,i)==index),-1)


def bearing_mod(ship): return int((ship.facing+30)/60)%6


def adjacent_bay(unit,ship):
    rotation=bearing_mod(ship)
    for i in range(6):
        if adjacent(ship.x,ship.y,rotation+i)==(unit.x,unit.y): return bay_number(ship,i)
    return -1


def matching_ships(unit):
    if unit.map is None: return []
    return [(ship,adjacent_bay(unit,ship)) for ship in unit.map.mechs_on_map
            if ship is not None and is_ds(ship) and ship.has_status(S.LANDED) and adjacent_bay(unit,ship)>=0]


def bay_open(unit,ship,reference):
    if reference<=0 or reference not in ship.aero_bays: return False
    direction=bay_direction(ship,ship.aero_bays.index(reference))
    if direction<0: return False
    from physics.heights import AERO_TYPES
    kind=AERODOOR if unit.unit_type in AERO_TYPES else MECHDOOR
    return any(slot.type==kind and not slot.firemode & FireMode.DESTROYED_MODE
               for slot in ship.sections[DOOR_LOCATIONS[direction]].criticals)


def bay_available(ship,reference):
    return reference in ship.aero_bays and reference>0 and not any(
        event.data2==reference for event in ship._engine.events.pending_events(EventType.ENTER_HANGAR))


def enter_lock(unit,board):
    """Evaluate the live LENTER attribute through the configured lock service."""
    from core.attributes import attributes_for
    expression=str(attributes_for(board,attributes_for(unit)).get(board._id,'A_LENTER',getattr(board,'enter_lock',''))).strip()
    evaluator=getattr(getattr(unit,'_engine',None),'lock_evaluator',None)
    if evaluator is not None:
        return bool(evaluator(expression,actor=unit._id,target=board._id,attribute='A_LENTER'))
    supplied=getattr(board,'lock_result',None)
    if supplied is not None: return bool(supplied)
    if expression.lower() in ('','true','*'): return True
    if expression.lower() in ('false','!*'): return False
    if expression.startswith('#') and expression[1:].isdigit(): return unit._id==int(expression[1:])
    external_effect(unit,'MUX lock evaluator',f'LENTER #{board._id}: {expression}')
    return None


def enter_bay(unit,argument='',caller=None):
    error=common_checks(unit,caller if caller is not None else getattr(unit,'pilot',None),MECH_USUAL)
    if error is not None: return False,error
    if unit.unit_type==U.VTOL and unit.fuel<=0: return False,'You lack fuel to maneuver in!'
    if unit.is_jumping: return False,'While in mid-jump? No way.'
    if unit.unit_type==U.MECH and (unit.is_fallen or pending(unit,'_stand_event')): return False,'Crawl inside? I think not. Stand first.'
    if unit.cocoon: return False,'While in mid-flight? No way.'
    args=str(argument).split()
    if len(args)>=2: return False,'Hmm, invalid number of arguments?'
    if args:
        from systems.targeting import contact_target
        ship=contact_target(unit,args[0])
        if ship is None: return False,'Invalid target!'
        index=adjacent_bay(unit,ship)
        if index<0: return False,'You see no bays in your hex.'
    else:
        matches=matching_ships(unit)
        if not matches: return False,'No DS bay found in your hex!'
        if len(matches)>1: return False,'Multiple enterable things found ; use the id for specifying which you want.'
        ship,index=matches[0]
    if is_ds(unit) and not unit.specials2 & 0x80000: return False,"Your craft can't enter bays."
    reference=ship.aero_bays[index] if index<len(ship.aero_bays) else -1
    if not bay_open(unit,ship,reference): return False,'The door has been jammed!'
    if is_ds(unit): return False,'Your unit is a bit too large to fit in there.'
    if abs(unit.speed-ship.speed)>10.75: return False,"Speed difference's too large to enter!"
    if ship.z!=unit.z: return False,'Get to same elevation before thinking about entering!'
    if abs(int(unit.vertical_speed-ship.vertical_speed))>10: return False,'Vertical speed difference is too great to enter safely!'
    from systems.parts import is_mech_legless
    if unit.unit_type==U.MECH and unit.move_type!=M.QUAD and is_mech_legless(unit): return False,'Without legs? Are you kidding?'
    board=resolve(unit,reference)
    if not isinstance(board,GameMap): return False,'You sense wrongness in fabric of space.'
    if unit._engine.has_event(EventType.ENTER_HANGAR,unit): return False,'You are already entering the hangar!'
    allowed=enter_lock(unit,board)
    if allowed is None: return False,'Enter lock service unavailable.'
    if not allowed: return False,getattr(board,'fail_message','') or 'You are unable to enter the bay!'
    if not bay_available(ship,reference): return False,'Someone else is using the door at the moment.'
    from systems.notifications import hex_broadcast
    hex_broadcast(unit.map,unit.x,unit.y,'The bay doors at $h start to open..')
    unit._engine.schedule_event(12,EventType.ENTER_HANGAR,enter_event,data=unit,data2=reference)
    return True,'Bay entry scheduled.'


def move_object(unit,destination):
    personnel=getattr(unit._engine,'personnel',None)
    if personnel is not None and unit._id in personnel.objects: personnel.move(unit._id,destination,loud=True)
    else: external_effect(unit,'local personnel registry','loud_teleport')


def set_xy(unit,x,y):
    from systems.map_transitions import set_xy as place
    return place(unit,x,y,actor=1)


def enter_event(event):
    unit=event.data
    maximum=cargo_max_speed(unit)
    if (not unit.is_started or unit.is_unconscious or unit.is_jumping or
        unit.unit_type==U.MECH and (unit.is_fallen or pending(unit,'_stand_event')) or unit.cocoon or
        abs(unit.speed)*5>=maximum and abs(maximum)>=10.75 or unit.unit_type==U.VTOL and unit.fuel<=0): return
    original=resolve(unit,event.data2)
    if not isinstance(original,GameMap): return
    ship=resolve(unit,getattr(original,'onmap',-1))
    if not isinstance(ship,Mech): return
    index=adjacent_bay(unit,ship)
    if not 0<=index<len(ship.aero_bays): return
    board=resolve(unit,ship.aero_bays[index])
    if not isinstance(board,GameMap): return
    from systems.swarm import detach_all
    from systems.sensors import los_broadcast
    from systems.ecm import mark_for_los_update
    from systems.map_transitions import transfer
    detach_all(unit,intentional=True,historical=True)
    notify(unit,'You enter bay.')
    los_broadcast(unit,f'has entered {ship.contact_id} at {unit.x},{unit.y}.')
    mark_for_los_update(unit)
    if unit.unit_type==U.MW and not getattr(board,'in_character',False):
        from systems.occupants import enter_mw_bay
        enter_mw_bay(unit,board._id)
        return
    carried=resolve(unit,unit.carrying) if unit.carrying>0 else None
    transfer(unit,board,actor=1);set_xy(unit,5,5)
    los_broadcast(unit,'has entered the bay.')
    move_object(unit,board._id)
    if carried is not None:
        transfer(carried,board,actor=1);set_xy(carried,5,5);move_object(carried,board._id)


def place(ship,unit,from_bay):
    if from_bay not in ship.aero_bays or unit.map is None:
        notify(unit,'Reality collapse imminent.');return False
    direction=bay_direction(ship,ship.aero_bays.index(from_bay))
    x,y=adjacent(ship.x,ship.y,bearing_mod(ship)+direction)
    x=max(0,min(x,unit.map.map_width-1));y=max(0,min(y,unit.map.map_height-1))
    unit.x=unit.last_x=x;unit.y=unit.last_y=y
    unit.z,unit.elev=ship.z,ship.elev
    unit.fx,unit.fy=hex_to_float(x,y)
    unit.terrain=unit.map.terrain(x,y)
    return True


def leave_bay(board,unit):
    ship=resolve(unit,getattr(board,'onmap',-1))
    if not isinstance(ship,Mech): notify(unit,'Invalid : No parent object?');return False
    if not bay_open(unit,ship,board._id): notify(unit,'The door has been jammed!');return False
    if not ship.has_status(S.LANDED) and not flying(unit): notify(unit,"The 'ship is still airborne!");return False
    if getattr(ship,'zombie',False): notify(unit,"You don't feel leaving right now would be prudent..");return False
    from systems.swarm import detach_all
    from systems.sensors import los_broadcast
    from systems.map_transitions import transfer
    from systems.notifications import pair_los_broadcast
    from systems.ecm import mark_for_los_update
    detach_all(unit,intentional=True,historical=True);los_broadcast(unit,'has left the bay.')
    transfer(unit,ship.mapindex,actor=1)
    carried=resolve(unit,unit.carrying) if unit.carrying>0 else None
    if not isinstance(carried,Mech): carried=None
    if carried is not None: transfer(carried,ship.mapindex,actor=1)
    if unit.mapindex == board._id:
        notify(unit,"Fatal error: Unable to find the map 'ship is on.");return False
    move_object(unit,unit.mapindex)
    if carried is not None: move_object(carried,unit.mapindex)
    notify(unit,'You have left the bay.')
    place(ship,unit,board._id)
    if carried is not None:
        for key in ('x','y','z','fx','fy','fz','last_x','last_y','terrain','elev'): setattr(carried,key,getattr(unit,key))
        mark_for_los_update(carried)
        from physics.flooding import flood_unit
        flood_unit(carried)
    pair_los_broadcast(unit,ship,"has left %s's bay.")
    notify(ship,f'{unit.contact_id} has left the bay.')
    continue_flying(unit)
    if unit.in_character and getattr(unit.pilot,'location',None)!=unit._id:
        notify(unit,'%ch%cr%cf%ciINTRUDER ALERT! INTRUDER ALERT!%c')
        notify(unit,'%ch%cr%cfAutomatic self-destruct sequence initiated.%c')
        from systems.startup import shutdown
        shutdown(unit._engine,unit,wizard=True)
    return True
