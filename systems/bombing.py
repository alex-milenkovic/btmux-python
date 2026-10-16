# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Historical Aerospace sources:
#   btech/aero.bomb.c

"""Physical aerospace payloads, ballistic release and delayed blast damage."""
from dataclasses import dataclass
import math
from entities.crittypes import is_bomb, BOMB_BASE_INDEX
from entities.mech import FireMode, MechStatus as S
from entities.part_catalog import BOMBS
from core.events import EventType
from core.randomness import float32 as f32, draw, number
from physics.hexmath import ZSCALE, hex_to_float, float_to_hex, TWOPIOVER360
from systems.movement_commands import notify
from systems.communications import common_checks, MECH_USUALS, MECH_PILOTONLY


def properties(index):
    name = BOMBS[index]
    return dict(name=name, weight=int(name.split('_')[0]), type=(1,2,0)[index%3], power=30 if index<2 else 130 if index<6 else 250)


def destroy_bomb(unit, location):
    """DestroyBomb is an empty source body."""


def payload(unit, live_only=False):
    from systems.parts import armor_string
    rows=[]
    for location,section in enumerate(unit.sections):
        for position,slot in enumerate(section.criticals):
            if not is_bomb(slot.type): continue
            destroyed=bool(slot.firemode & FireMode.DESTROYED_MODE)
            if live_only and destroyed: continue
            rows.append(dict(number=len(rows)+1,section=location,slot=position,location=armor_string(unit,location),destroyed=destroyed,**properties(slot.type-BOMB_BASE_INDEX)))
    return rows


def list_payload(unit):
    rows=payload(unit)
    from systems.parts import mech_ids
    def centered(text):
        offset=max(0,39-len(text)//2)
        visible=' '*offset+text[:max(0,77-offset)]
        return ' '*offset+'%ch%cm'+text[:max(0,77-offset)]+'%c'+' '*max(0,78-len(visible))
    rule='%cb'+'-'*78+'%c'
    lines=[rule,centered(f'Bomb payload for {mech_ids(unit)}:'),rule]
    if not rows: lines.append(centered('No bombs installed.'))
    else:
        lines.append(f"#  {'Location':<20} {'Weight':<5} {'Power':<5} Type")
        lines.extend(f"{row['number']:<2} {row['location']:<20} {row['weight']//10:5d} {row['power']:5d}" for row in rows)
    lines.append(rule)
    return dict(ok=True,rows=rows,lines=lines)


def calc_dest(unit):
    fz=f32(unit.fz/ZSCALE); zspeed=f32(unit.start_fz/ZSCALE)
    time=f32(zspeed+math.sqrt(f32(f32(zspeed*zspeed)+f32(2*fz))))
    x,y=float_to_hex(f32(unit.fx+f32(unit.start_fx*time)),f32(unit.fy+f32(unit.start_fy*time)))
    return time,x,y


def aim(unit):
    time,x,y=calc_dest(unit)
    suffix='' if time>=2 or time<1 else 's'
    message=notify(unit,f'Estimated bomb flight time {time:.1f} second{suffix}, estimated landing hex {x},{y}.')
    return dict(ok=True,time=time,x=x,y=y,message=message)


def simulate_flight(unit,board,x,y,time):
    if time<1: return x,y
    fx,fy,fz=unit.fx,unit.fy,unit.fz
    dx,dy=hex_to_float(x,y)
    dx,dy=f32((dx-fx)/time),f32((dy-fy)/time)
    i=1
    while i<time:
        fx,fy,fz=f32(fx+dx),f32(fy+dy),f32(fz-1)
        tx,ty=float_to_hex(fx,fy)
        if board.valid(tx,ty) and board.elevation(tx,ty)>fz/ZSCALE: x,y=tx,ty
        i+=1
    return x,y


@dataclass(frozen=True)
class BombShot:
    board: object
    x: int
    y: int
    index: int
    engine: object


def hit(shot):
    from systems.damage import blast_hit_hexes
    from systems.notifications import hex_broadcast
    props=properties(shot.index)
    kind,power=props['type'],props['power']
    broadcasts=('A blast rocks the area around $H!', 'A fiery blast occurs in $H, spraying flaming gel everywhere!', "A bomb drops rain of small bomblets in $H's surroundings!")
    hex_broadcast(shot.board,shot.x,shot.y,broadcasts[kind])
    messages=(('You receive a direct hit!','receives a direct hit!','You are hit by shrapnel!','is hit by shrapnel!'),
              ('You receive a direct hit!','receives a direct hit!','You are hit by the globs of flaming gel!','is hit by the globs!'),
              ('You are hit by ton of small munitions!','is hit by many small munitions!','You are hit by some of the small munitions!','is hit by some small munitions!'))[kind]
    blast_hit_hexes(shot.board,power//2 if kind==1 else power,2 if kind==2 else 10,power if kind==1 else 0,shot.x,shot.y,*messages,0,4,1,True,1,engine=shot.engine)


def hit_event(event):
    hit(event.data)


def drop(unit,bomb_number):
    from systems.sensors import los_broadcast
    from systems.piloting import make_piloting_roll
    from systems.parts import set_cargo_weight
    if bomb_number<0: return dict(ok=False,error='Negative bomb number? Gimme a break.')
    rows=payload(unit,True)
    if not rows: return dict(ok=False,error='No bombs installed.')
    if unit.map is None: return dict(ok=False,error="You're on invalid map!")
    if not 1<=bomb_number<=len(rows): return dict(ok=False,error='No bomb with such number installed! (See BOMB LIST)')
    selected=rows[bomb_number-1]
    slot=unit.sections[selected['section']].criticals[selected['slot']]
    index=slot.type-BOMB_BASE_INDEX
    los_broadcast(unit,'detaches a small object that starts falling down..')
    notify(unit,'The ship trembles as you detach a bomb..')
    time,x,y=calc_dest(unit)
    offset=int(int(time)/10)
    unit.last_piloting_modifier=4+offset
    psr=make_piloting_roll(unit,4+offset)
    if psr.success or time<2:
        notify(unit,'Despite the slight problems, you keep the craft stable enough to drop the bomb right on target..')
    else:
        notify(unit,"The ship's lurches slightly, dropping the bomb off target!")
        maximum=6*(1+offset)
        distance=max(1,draw('bomb_scatter_distance',1,maximum,lambda:number(1,maximum))//2)
        direction=f32(draw('bomb_scatter_direction',0,359,lambda:number(0,359))*TWOPIOVER360)
        x,y=int(x+distance*math.cos(direction)),int(y+distance*math.sin(direction))
    x,y=simulate_flight(unit,unit.map,x,y,time)
    result=dict(ok=True,scheduled=False,time=time,x=x,y=y,modifier=4+offset)
    if not unit.map.valid(x,y): return result
    slot.type=0
    set_cargo_weight(unit)
    delay=max(1,int(time))
    unit._engine.schedule_event(delay,EventType.ARTILLERY_HIT,hit_event,data=BombShot(unit.map,x,y,index,unit._engine))
    result.update(scheduled=True,due=unit._engine.muxevent_tick+delay)
    return result


def command(unit,argument='',caller=None):
    from systems.map_management import readnum
    error=common_checks(unit,caller if caller is not None else getattr(unit,'pilot',None),MECH_USUALS|MECH_PILOTONLY)
    if error is not None: return dict(ok=False,error=error)
    args=str(argument).split()
    if not args: return dict(ok=False,error='(At least) one option required.')
    if len(args)>2: return dict(ok=False,error='Too many arguments!')
    if args[0].lower()=='list': return list_payload(unit)
    if unit.has_status(S.LANDED): return dict(ok=False,error='The craft is landed!')
    if args[0].lower()=='aim': return aim(unit)
    if args[0].lower()!='drop': return dict(ok=False,error='Invalid argument to BOMB!')
    if len(args)<2: return dict(ok=False,error='The BOMB commands needs to know WHICH bomb to drop!')
    try: bomb_number=readnum(args[1])
    except ValueError: return dict(ok=False,error='Invalid bomb number!')
    return drop(unit,bomb_number)
