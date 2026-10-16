# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.obj.c
# Historical Aerospace sources:
#   btech/aero.move.c
#   btech/map.obj.c

"""Typed building links and entrances from supplied local attribute records."""
import re
from entities.map_objects import MapObject,add_object,delete_objects,resolve_map,bits_for
from systems.map_management import arguments,atoi,readnum,report
from physics.hexmath import hex_to_float,find_range


def entrance(board,direction=0):
    direction=ord(direction) if isinstance(direction,str) else direction
    return next((obj for obj in board.map_objects[6] if not direction or obj.datac==direction),None)


def by_target(board,identity):
    return next((obj for obj in board.map_objects[4] if obj.obj==identity),None)


def parse_coord(board,direction,text,x=None,y=None):
    if ',' in text:
        match=re.match(r'\s*([+-]?\d+)',text)
        if not match: return False,x,y
        x=int(match[1]); pos=match.end()
        second=re.match(r',\s*([+-]?\d+)',text[pos:])
        return (True,x,int(second[1])) if second else (False,x,y)
    offset=atoi(text)
    if offset<0: return False,x,y
    tox,toy=((1,0),(2,1),(1,2),(0,1))[direction]
    x=min(board.map_width-1,board.map_width*tox//2)
    y=min(board.map_height-1,board.map_height*toy//2)
    if tox==1: y+=-offset if toy>1 else offset
    if toy==1: x+=-offset if tox>1 else offset
    return True,max(0,min(x,board.map_width-1)),max(0,min(y,board.map_height-1))


def add_entrances(board,text):
    args=arguments(text,4); count=0
    if len(args)!=4: return 0
    for direction,arg in enumerate(args):
        success,x,y=parse_coord(board,direction,arg)
        if success:
            add_object(board,6,MapObject(x=x,y=y,datac=ord('nesw'[direction])))
            count+=1
    return count


def add_links(board,text,attributes,stats=None,stack=()):
    stats=[0,0,0] if stats is None else stats
    for value in arguments(text,500):
        target=atoi(value)
        child=resolve_map(board,target)
        if target<0 or target==board._id or child is None: continue
        coord=attributes.get(target,{}).get('BUILDCOORD','')
        if ',' not in coord: continue
        success,x,y=parse_coord(board,0,coord)
        if not success or not board.valid(x,y): continue
        if target in stack: raise ValueError('Unsupported recursive building link cycle')
        bits_for(board).set(x,y,2)
        add_object(board,4,MapObject(x=x,y=y,obj=target)); stats[0]+=1
        recursively_update(child,board._id,attributes,stats,stack)
    return stats


def recursively_update(board,parent,attributes,stats,stack=()):
    if board._id in stack: raise ValueError('Unsupported recursive building link cycle')
    stack=(*stack,board._id)
    bits=bits_for(board,False)
    if bits is not None: bits.clear(2)
    values=attributes.get(board._id,{})
    if parent>=0:
        board.onmap=parent
        delete_objects(board,5)
        add_object(board,5,MapObject(obj=parent)); stats[1]+=1
        delete_objects(board,6)
        stats[2]+=add_entrances(board,values.get('BUILDENTRANCE',''))
    delete_objects(board,4)
    add_links(board,values.get('BUILDLINKS',''),attributes,stats,stack)


def update_links(board,attributes,parent=-1,actor=None):
    attributes={int(key):value for key,value in attributes.items()}
    stats=[0,0,0]
    owner=board
    if actor is not None:
        from systems.targeting import resolve_object
        player=resolve_object(board,actor) if isinstance(actor,int) else actor
        board=resolve_map(owner,getattr(player,'location',-1))
    if board is not None: recursively_update(board,parent,attributes,stats)
    report(owner,f'Updated {stats[0]} BUILD objs, {stats[1]} LEAVE objs, {stats[2]} ENTRANCE objs.',1 if actor is None else actor)
    return stats


def linked(board): return board is not None and bool(getattr(board,'map_objects',((),)*10)[7])


def set_linked(board,actor=1):
    add_object(board,7,MapObject(datac=1))
    report(board,'Map set to linked.',actor)


def block_lz(board,text,creator=1,actor=None):
    if board is None: return
    actor=creator if actor is None else actor
    args=arguments(text,4)
    if len(args)<3: raise ValueError('Invalid arguments!')
    try:
        x,y,distance=map(readnum,args[:3]); team=readnum(args[3]) if len(args)>3 else 0
    except ValueError: raise ValueError('Invalid number!') from None
    if not board.valid(x,y): raise ValueError('X,Y out of range!')
    obj=add_object(board,9,MapObject(x=x,y=y,datai=distance,datac=team,obj=creator))
    report(board,f'Landingzone-block added to {x},{y} (distance: {distance})',actor)
    return obj


def blocked_lz(unit,board,x,y):
    fx,fy=hex_to_float(x,y)
    from physics.heights import AERO_TYPES
    for obj in board.map_objects[9]:
        if unit.unit_type in AERO_TYPES and (abs(x-obj.x)>obj.datai or abs(y-obj.y)>obj.datai):
            continue
        if obj.datac and obj.datac==unit.team: continue
        tx,ty=hex_to_float(obj.x,obj.y)
        if find_range(fx,fy,tx,ty)<=obj.datai: return True
    return False
