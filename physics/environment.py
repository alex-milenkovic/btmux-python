# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.weather.c

"""Authorized R1-R4 operational weather representation, controls and event owner.

These named fields and defaults are port reconstruction, not historical macros.
Source arithmetic remains in physics.weather; all clocks use the muxevent queue.
"""
from physics import weather

CONDITIONS={'precipitation','heavy_precipitation','fog','blowing_sand'}
LAYERS={'snow':1,'deep_snow':2,'mud':4,'rapids':8}
DEFAULTS=dict(cadence_ticks=60,snow_low=10,snow_high=20,heavy_snow_low=30,
              heavy_snow_high=50,melt_per_degree=10,emit=True,steam=True)
ALIASES={'precipitation':'precip','heavy_precipitation':'heavy_precip','blowing_sand':'sand'}


def integer(value,low=None,high=None):
    if type(value) is not int or (low is not None and value<low) or (high is not None and value>high):
        raise ValueError('environment requires integer in allowed range')
    return value


def names(values,allowed):
    if not isinstance(values,list) or any(not isinstance(v,str) or v not in allowed for v in values):
        raise ValueError('invalid environment names')
    return set(values)


def fields(values,allowed,required=()):
    if (not isinstance(values,dict) or values.keys()-set(allowed)
            or set(required)-values.keys()): raise ValueError('invalid environment fields')


def normalized_conditions(values):
    result=names(values,CONDITIONS)
    if 'heavy_precipitation' in result: result.discard('precipitation')
    return result


def configuration(values):
    fields(values,DEFAULTS)
    result={**DEFAULTS,**values}
    for key,value in result.items():
        if key in ('emit','steam'):
            if type(value) is not bool: raise ValueError('emit and steam require Boolean values')
        else: integer(value,1 if key=='cadence_ticks' else 0)
    if result['snow_low']>result['snow_high'] or result['heavy_snow_low']>result['heavy_snow_high']:
        raise ValueError('snow bounds must be ordered')
    return result


def initialize(board):
    board.weather_enabled=False
    board.weather_conditions=set()
    board.weather_config=dict(DEFAULTS)
    board.weather_event=None


def effects(board):
    conditions={ALIASES.get(n,n) for n in getattr(board,'weather_conditions',())}
    result=weather.calc_effects(conditions,board.temp,board.windspeed)
    return {'blowing_sand' if n=='sand' else n for n in result}


def predicates(board):
    if board is None or not getattr(board,'weather_enabled',False): return {}
    return {ALIASES.get(name,name):1 for name in effects(board)}


def gun_modifier(board,weapon_type): return weather.gun_effects(predicates(board),weapon_type)


def pilot_modifier(unit):
    if unit.map is None or not getattr(unit.map,'weather_enabled',False): return 0
    return weather.pilot_effects(unit,predicates(unit.map))


def heat_modifier(unit):
    board=unit.map
    if board is None or not getattr(board,'weather_enabled',False): return 0
    raw=predicates(board)
    value=-2 if raw.get('heavy_rain') else -1 if raw.get('rain') else 0
    value+=-2 if raw.get('blizzard') else -1 if raw.get('heavy_snow') else 0
    if 'deep_snow' in board.layers.get((unit.x,unit.y),set()):
        from systems.heat_control import leg_heat_sinks
        if leg_heat_sinks(unit)>0:value-=1
    return value


def cancel(board):
    event=getattr(board,'weather_event',None)
    if event is not None:event.cancel()
    board.weather_event=None


def eligible(board):
    engine=board._engine
    return (board.weather_enabled and engine is not None and board in engine.get_entities()
            and board.map_width>0 and board.map_height>0 and not board._grid_failed and board._terrain is not None)


def arm(board,*,restart=False,delay=None):
    if restart:cancel(board)
    if not eligible(board):cancel(board);return
    if board.weather_event is not None and not board.weather_event.zombie:return
    from core.events import EventType
    board.weather_event=board._engine.events.schedule(
        board.weather_config['cadence_ticks'] if delay is None else delay,EventType.WEATHER,callback,board)


def callback(event):
    board=event.data
    if board.weather_event is not event:return
    board.weather_event=None
    if not eligible(board):return
    try:
        config=board.weather_config
        if board.temp<=0:
            if 'heavy_precipitation' in board.weather_conditions:
                weather.grow(board,config['heavy_snow_low'],config['heavy_snow_high'])
            elif 'precipitation' in board.weather_conditions:
                weather.grow(board,config['snow_low'],config['snow_high'])
        else:
            for x in range(board.map_width):
                for y in range(board.map_height):
                    if board.layers.get((x,y),set())&{'snow','deep_snow'} or weather.is_ice_hex(board,x,y):
                        weather.melt(board,x,y,board.temp*config['melt_per_degree'],config['emit'],config['steam'])
    finally:
        arm(board)


def clear_layers(board):
    board.layers={};board.layer_data={}


def reset(board):
    cancel(board);initialize(board);clear_layers(board)


def resized(board):
    board.layers={xy:value for xy,value in board.layers.items() if board.valid(*xy)}
    board.layer_data={xy:value for xy,value in board.layer_data.items() if board.valid(*xy)}
    arm(board,restart=True)


def cell(board,values):
    x=integer(values['x']);y=integer(values['y']);board.require_cell(x,y)
    return x,y


def show(board,cells=()):
    positions=[]
    for position in cells:
        if not isinstance(position,list) or len(position)!=2:raise ValueError('cells require coordinate pairs')
        x,y=position;integer(x);integer(y);board.require_cell(x,y);positions.append((x,y))
    event=board.weather_event
    return dict(enabled=board.weather_enabled,conditions=sorted(board.weather_conditions),effects=sorted(effects(board)),
        temperature=board.temp,winddir=board.winddir,windspeed=board.windspeed,**board.weather_config,
        deadline=event.tick if event is not None and not event.zombie else None,
        modifiers_enabled=board.weather_enabled,
        cells=[dict(x=x,y=y,layers=sorted(board.layers.get((x,y),())),
                    layer_bits=sum(LAYERS[n] for n in board.layers.get((x,y),())),
                    data=board.layer_data.get((x,y),0)) for x,y in positions])


def set_weather(board,values):
    fields(values,{'enabled','conditions','temperature','winddir','windspeed'}|DEFAULTS.keys())
    config=configuration({**board.weather_config,**{k:v for k,v in values.items() if k in DEFAULTS}})
    conditions=normalized_conditions(values['conditions']) if 'conditions' in values else board.weather_conditions
    enabled=values.get('enabled',True)
    if type(enabled) is not bool:raise ValueError('enabled requires Boolean')
    temp=integer(values.get('temperature',board.temp),-128,127)
    wind=integer(values.get('winddir',board.winddir),-32768,32767)
    speed=integer(values.get('windspeed',board.windspeed),-32768,32767)
    changed=(config!=board.weather_config or conditions!=board.weather_conditions or enabled!=board.weather_enabled
             or (temp,wind,speed)!=(board.temp,board.winddir,board.windspeed))
    if 'temperature' in values:
        from systems.map_conditions import set_conditions
        set_conditions(board,f'{board.grav} {temp} {int(bool(board.flags&4))} {int(bool(board.flags&16))}')
    if 'winddir' in values or 'windspeed' in values:
        from systems.map_conditions import visibility_values
        message=visibility_values(board.visibility_config)[5]
        board.visibility_config=f'{board.mapvis} {board.maplight} {wind} {speed} {board.cloudbase}'
        if len(message)>5:board.visibility_config+=' '+message
    board.temp,board.winddir,board.windspeed=temp,wind,speed
    board.weather_config=config;board.weather_conditions=set(conditions);board.weather_enabled=enabled
    if changed:arm(board,restart=True)
    return show(board)


def command(board,name,values):
    if name=='weather.set':return set_weather(board,values)
    if name=='weather.show':
        fields(values,{'cells'});return show(board,values.get('cells',()))
    if name in ('weather.enable','weather.disable','weather.reset'):
        fields(values,())
        if name=='weather.reset':reset(board)
        else:
            enabled=name=='weather.enable'
            if enabled!=board.weather_enabled:board.weather_enabled=enabled;arm(board,restart=True)
        return show(board)
    if name=='layer.set':
        fields(values,{'x','y','layers','data'},{'x','y','layers','data'})
        x,y=cell(board,values);layers=names(values['layers'],LAYERS);data=integer(values['data'])
        board.layers[x,y]=layers;board.layer_data[x,y]=data
        if layers&{'snow','deep_snow'}:weather.normalize_snow(board,x,y)
        return show(board,[[x,y]])
    if name=='snow.grow':
        fields(values,{'low','high'},{'low','high'});low=integer(values['low']);high=integer(values['high'])
        if board._grid_failed or board._terrain is None:raise ValueError('map grid unavailable')
        weather.grow(board,low,high);return show(board)
    if name=='snow.melt':
        fields(values,{'x','y','depth','emit','steam'},{'x','y','depth'});x,y=cell(board,values);depth=integer(values['depth'])
        emit=values.get('emit',board.weather_config['emit']);steam=values.get('steam',board.weather_config['steam'])
        if type(emit) is not bool or type(steam) is not bool:raise ValueError('emit and steam require Boolean values')
        weather.melt(board,x,y,depth,emit,steam);return show(board,[[x,y]])
    raise ValueError('unknown environment command')
