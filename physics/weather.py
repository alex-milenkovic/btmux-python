# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.weather.c

"""Source weather arithmetic plus authorized R2 normalization and ice adapter.

Operational representation, commands and clocks are defined in environment.py.
Raw macro probes remain available independently of the Boolean live predicates.
"""
from entities.weapon import WeaponType as W
from entities.mech import MoveType
from physics.decorations import add_smoke
from core.randomness import draw,number as source_number


class SnowRandom:
    """Extend accepted unbounded snow rates using the same source MT stream.

    Equal bounds produce fixed weather growth without consuming MT words.
    Unequal ordinary ranges keep Number's exact sequence. Wider ranges concatenate
    32-bit words and reject excess candidates; one named draw remains visible.
    """
    def number(self,low,high):
        if low==high:return low
        if low<=high<=0xffffffff:return source_number(low,high)
        span=high-low
        bits=span.bit_length();words=(bits+31)//32
        while True:
            value=0
            for _ in range(words):value=(value<<32)|source_number(0,0xffffffff)
            value >>= words*32-bits
            if value<=span:return low+value


def number(name,low,high):
    if type(low) is not int or type(high) is not int or low<0 or high<low:
        raise ValueError('snow sampling requires ordered nonnegative integers')
    sampler=SnowRandom()
    return draw(name,low,high,lambda:sampler.number(low,high),state=sampler)


def validate_conditions(conditions):
    result=set(conditions)
    if 'heavy_precip' in result: result.discard('precip')
    return result


def calc_effects(weather,temp,windspeed):
    effects={'high_winds'} if windspeed>60 else {'winds'} if windspeed>=30 else set()
    if 'heavy_precip' in weather:
        if temp<=0:
            if 'high_winds' in effects: effects.remove('high_winds'); effects.add('blizzard')
            else: effects.add('heavy_snow')
        else: effects.add('heavy_rain')
    elif 'precip' in weather: effects.add('snow' if temp<=0 else 'rain')
    if 'fog' in weather: effects.add('fog')
    if 'sand' in weather: effects.add('sand')
    return effects


def gun_effects(raw,weapon_type):
    mod=1 if raw.get('rain',0) else 0
    if raw.get('blizzard',0): mod+=2 if weapon_type==W.TAMMO else 1
    elif raw.get('heavy_snow',0): mod+=1
    if raw.get('fog',0) and weapon_type==W.TBEAM: mod+=1
    if raw.get('sand',0): mod+=1 if weapon_type==W.TAMMO else 2
    if raw.get('high_winds',0) & int(not raw.get('blizzard',0)):
        if weapon_type==W.TAMMO: mod+=2
    if raw.get('winds',0) and weapon_type==W.TAMMO: mod+=1
    return mod


def pilot_effects(unit,raw):
    board=unit.map
    if board is None or unit.is_jumping or unit.z>board.base_elevation(unit.x,unit.y): return 0
    mod=int(any(raw.get(effect,0) for effect in ('heavy_rain','heavy_snow','high_winds','blizzard')))
    if unit.move_type!=MoveType.HOVER:
        layers=board.layers.get((unit.x,unit.y),set())
        mod+=int('deep_snow' in layers)+int('mud' in layers)+2*int('rapids' in layers)
    return mod


def heat_effects(board,unit,raw,leg_sinks=None,*,temperature=True):
    if raw.get('heavy_rain',0): unit.minus_heat-=2
    elif raw.get('rain',0): unit.minus_heat-=1
    if raw.get('blizzard',0): unit.minus_heat-=2
    elif raw.get('heavy_snow',0): unit.minus_heat-=1
    if temperature and board.temp < -30: unit.minus_heat+=(-30-board.temp+9)//10
    elif temperature and board.temp > 50: unit.minus_heat-=(board.temp-50+9)//10
    if 'deep_snow' in board.layers.get((unit.x,unit.y),set()):
        if leg_sinks is None:
            from systems.heat_control import leg_heat_sinks
            leg_sinks=leg_heat_sinks(unit)
        if leg_sinks>0: unit.minus_heat-=1
    return unit.minus_heat


def broadcast(board,x,y,message):
    from systems.artillery import hex_los_broadcast
    hex_los_broadcast(board,x,y,message)


def is_ice_hex(board,x,y):
    from entities.map_objects import underlying_terrain
    return underlying_terrain(board,x,y)=='-'


def melt(board,x,y,depth,emit=False,steam=False,*,ice=None):
    if type(depth) is not int:raise ValueError('snow depth requires an integer')
    if board is None or depth<=0: return
    if not board.valid(x,y): raise ValueError('Snow coordinates out of range')
    old=set(board.layers.get((x,y),set())); layers=set(old)
    data=board.layer_data.get((x,y),0); length=0
    if ice is None: ice=is_ice_hex(board,x,y)
    prospective=min(max(0,data),depth) if layers&{'snow','deep_snow'} else 0
    if ice and depth>=board.base_elevation(x,y)*200:prospective=board.base_elevation(x,y)*200
    if steam and prospective>0 and board._engine is None:
        raise ValueError('Timed decoration requires an owning engine')
    if layers&{'snow','deep_snow'}:
        remaining=max(0,data-depth); length=abs(remaining-data)
        layers-= {'snow','deep_snow'}
        if remaining: layers.add('snow' if remaining<=1000 else 'deep_snow')
        board.layers[x,y]=layers; board.layer_data[x,y]=remaining
        if emit:
            if not layers&{'snow','deep_snow'}: broadcast(board,x,y,'%ch%cgThe snow in $h melts to nothingness!%cn')
            elif 'deep_snow' in old and 'deep_snow' not in layers: broadcast(board,x,y,'%ch%cgThe snow in $h visibly melts!%cn')
    if ice is None: ice=is_ice_hex(board,x,y)
    if ice and depth>=board.base_elevation(x,y)*200:
        from physics.ice import break_surface
        if emit: broadcast(board,x,y,'The ice at $h breaks apart!')
        break_surface(board,None,x,y,'goes swimming as ice breaks!')
        # Authorized overlay adapter: old smoke must not restore broken ice.
        for group in board.map_objects[:3]:
            for obj in group:
                if (obj.x,obj.y)==(x,y): obj.datac=ord('~')
        length=board.base_elevation(x,y)*200
    if length>0 and steam:
        if length>90: length=90+number('snow_steam',0,length//20)
        add_smoke(board._engine,board,x,y,length)


def grow(board,low_depth,high_depth):
    if type(low_depth) is not int or type(high_depth) is not int:raise ValueError('snow depth requires an integer')
    if board._grid_failed or board._terrain is None:raise ValueError('map grid unavailable')
    board.snow_validation_trace=[]
    if low_depth==0 and high_depth==0: return
    low,high=sorted((abs(low_depth),abs(high_depth)))
    sign=-1 if low_depth<0 or high_depth<0 else 1
    for x in range(board.map_width):
        for y in range(board.map_height):
            if board.terrain(x,y) in ('/','&','~','-'): continue
            depth=number('snow_growth',low,high)*sign
            if not depth: continue
            layers=set(board.layers.get((x,y),set()))
            if depth<0:
                if not layers&{'snow','deep_snow'}: continue
            elif not {'snow','deep_snow'}<=layers: board.layers[x,y]={'snow'}
            board.layer_data[x,y]=board.layer_data.get((x,y),0)+depth
            board.snow_validation_trace=getattr(board,'snow_validation_trace',[])
            board.snow_validation_trace.append(dict(x=x,y=y,data=board.layer_data[x,y],
                layers=sorted(board.layers.get((x,y),layers))))
            normalize_snow(board,x,y)


def normalize_snow(board,x,y):
    data=max(0,board.layer_data.get((x,y),0))
    layers=set(board.layers.get((x,y),set()))-{'snow','deep_snow'}
    if data: layers.add('snow' if data<=1000 else 'deep_snow')
    board.layers[x,y]=layers
    board.layer_data[x,y]=data


def command(board,name,values):
    from physics.environment import command as dispatch
    return dispatch(board,name,values)


def mapping_status():
    return {'service':'weather-macro-values','applied':True,'blocked':False,
            'representation':'authorized R1 named conditions and Boolean effects; port layer bits 1,2,4,8'}
