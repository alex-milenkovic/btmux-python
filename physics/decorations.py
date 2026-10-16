# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.obj.c

"""Source timed decorations, ordered fire spread and underlying terrain."""
import random
from core.events import EventType
from core.randomness import draw, roll
from entities.map import SMOKE, FIRE, LIGHT_FOREST, HEAVY_FOREST, GRASSLAND, ROUGH, WALL, BUILDING
from entities.map_objects import MapObject, add_object, delete_object, find_decorations


def number(name,low,high):
    return draw(name,low,high,lambda:random.randint(low,high))


def fire_speed(board): return max(20,60-board.windspeed)


def schedule(engine,board,obj,delay,callback):
    if board._engine is None: board._engine=engine
    if engine is None: raise ValueError('Timed decoration requires an owning engine')
    obj.event=engine.events.schedule(delay,EventType.DECORATION,callback,board,obj)
    return obj.event


def add_smoke(engine,board,x,y,duration=120):
    return add_decoration(engine,board,x,y,SMOKE,duration)


def add_fire(engine,board,x,y,duration=None):
    if duration is None: duration=number('fire_duration',60,180)
    return add_decoration(engine,board,x,y,FIRE,duration)


def add_decoration(engine,board,x,y,terrain,duration,kind=None):
    if not board.valid(x,y): return None
    kind=(0 if terrain==FIRE else 1 if terrain==SMOKE else 2) if kind is None else kind
    if type(duration) is not int: raise ValueError('decoration duration requires an integer')
    if duration and kind in (0,1) and engine is None: raise ValueError('Timed decoration requires an owning engine')
    from entities.map_storage import signed_value
    underlying=board.rterrain(x,y)
    for group in range(3):
        for obj in list(board.map_objects[group]):
            if (obj.x,obj.y)==(x,y): delete_object(board,obj,group,1)
    old=board.decorations.pop((x,y),None)
    if old is not None and old['event'] is not None: old['event'].cancel()
    board.set_terrain(x,y,terrain)
    obj=add_object(board,kind,MapObject(x=x,y=y,datac=ord(underlying),datas=signed_value(duration,16),terrain=terrain))
    board.decorations[x,y]=obj
    if duration:
        if kind==1: schedule(engine,board,obj,duration,expire_smoke)
        elif kind==0: schedule(engine,board,obj,fire_speed(board),spread_fire)
    return obj


def live(event,kind):
    board,obj=event.data,event.data2
    if obj not in board.map_objects[kind]:
        board.external_effects.append(dict(service='source orphan decoration',operation=event.callback.__name__,applied=False))
        return False
    return True


def expire_smoke(event):
    if live(event,1): delete_object(event.data,event.data2,1,0)


def expire_fire(event):
    if not live(event,0): return
    board,obj=event.data,event.data2
    delete_object(board,obj,0,0)
    if board.rterrain(obj.x,obj.y) in (LIGHT_FOREST,HEAVY_FOREST):
        board.set_terrain(obj.x,obj.y,GRASSLAND if number('fire_dissipation',1,6)<3 else ROUGH)


EVEN={0:((0,-1),(-1,0),(1,0)),60:((1,0),(0,-1),(1,1)),120:((1,1),(1,0),(0,1)),
      180:((0,1),(1,1),(-1,1)),240:((-1,1),(0,1),(1,0)),300:((-1,0),(0,-1),(-1,1))}
ODD={0:((0,-1),(1,-1),(-1,-1)),60:((1,-1),(0,-1),(1,0)),120:((1,0),(1,-1),(0,1)),
     180:((0,1),(1,0),(-1,0)),240:((-1,0),(0,1),(1,-1)),300:((-1,-1),(-1,0),(0,-1))}


def coordinate(board,x,y,index,wind):
    if index not in (0,1,2): raise ValueError('spread index requires 0..2')
    rounded=int((wind+30)/60)*60
    rounded-=int(rounded/360)*360
    dx,dy=(ODD if x%2 else EVEN).get(rounded,((0,0),)*3)[index]
    result=(x+dx,y+dy)
    return result if board.valid(*result) else (-1,-1)


def spread_coordinates(board,x,y,wind):
    result=[coordinate(board,x,y,i,wind) for i in range(3)]
    return result+[coordinate(board,*result[0],0,wind)]


def spread_eligible(board,threshold):
    return roll('fire_spread')>=threshold and number('fire_wind',1,60)<=board.windspeed


def check_smoke(engine,board,coords):
    for x,y in coords:
        if not board.valid(x,y) or find_decorations(board,x,y) or board.terrain(x,y) in (WALL,BUILDING): continue
        add_smoke(engine,board,x,y,number('smoke_duration',90,150))


def check_fire(engine,board,coords):
    for x,y in coords:
        if board.valid(x,y) and board.rterrain(x,y) in (LIGHT_FOREST,HEAVY_FOREST): add_fire(engine,board,x,y)


def spread_fire(event):
    if not live(event,0): return
    board,obj=event.data,event.data2
    engine=board._engine
    smoke=spread_coordinates(board,obj.x,obj.y,board.winddir)
    fires=[xy if spread_eligible(board,threshold) else (-1,-1) for xy,threshold in zip(smoke,(9,11,11,12))]
    check_smoke(engine,board,smoke)
    check_fire(engine,board,fires)
    if obj not in board.map_objects[0]:
        # C's free-list reuses the just-deleted origin record. Continue with
        # its replacement, including its newly drawn lifetime and timer.
        from entities.map_objects import find_object
        obj=find_object(board,obj.x,obj.y,0)
    from entities.map_storage import signed_value
    obj.datas=signed_value(obj.datas-fire_speed(board),16)
    repeat=obj.datas>fire_speed(board)
    schedule(engine,board,obj,fire_speed(board) if repeat else obj.datas,spread_fire if repeat else expire_fire)
