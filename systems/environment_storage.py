# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.weather.c

"""R5 versioned map snapshots. Validate a detached candidate before publication.

Legacy object/dynamic byte formats remain unchanged. Relative event ownership and
canonical decimal layer data are explicit snapshot extensions. No RNG or unit
character state is invented here; replay supplies ordinary unit/random records.
"""
import re
from copy import deepcopy
from entities.map import GameMap
from entities.mech import Mech
from entities.map_objects import (save_objects,decode_objects,add_object,bits_for,publish_mine_bits)
from entities.map_storage import save_dynamic,load_dynamic
from physics import environment as env,decorations
from core.events import EventType
from systems import buildings

SCALARS=('flags','grav','temp','winddir','windspeed','mapvis','maxvis','maplight','cloudbase',
         'movemod','cf','cfmax','regen_factor','buildflag','onmap')
CALLBACKS={'weather':(EventType.WEATHER,env.callback),
           'spread_fire':(EventType.DECORATION,decorations.spread_fire),
           'expire_fire':(EventType.DECORATION,decorations.expire_fire),
           'expire_smoke':(EventType.DECORATION,decorations.expire_smoke),
           'regen':(EventType.BREGEN,buildings.regen),'rebuild':(EventType.BREBUILD,buildings.rebuild)}


def decimal(value):
    # Python's configurable int/string resource ceiling is an explicit error.
    try:return str(env.integer(value))
    except ValueError as error:raise ValueError('layer decimal serialization exceeds configured integer resource limit') from error


def parse_decimal(value):
    if not isinstance(value,str) or not re.fullmatch(r'0|-?[1-9][0-9]*',value):raise ValueError('noncanonical layer decimal')
    try:return int(value)
    except ValueError as error:raise ValueError('layer decimal parsing exceeds configured integer resource limit') from error


def save_snapshot(engine,boards):
    if not isinstance(boards,list) or not boards or len({b._id for b in boards})!=len(boards):
        raise ValueError('snapshot requires a unique complete map list')
    for board in boards:
        if board not in engine.get_entities() or not isinstance(board,GameMap):raise ValueError('snapshot map is not registered')
        if board._grid_failed or board._terrain is None:raise ValueError('cannot snapshot unavailable grid')
    rows=[]
    for board in boards:
        cells=[dict(x=x,y=y,layers=sorted(board.layers.get((x,y),())),data=decimal(board.layer_data.get((x,y),0)))
               for x,y in sorted(board.layers.keys()|board.layer_data.keys())
               if board.layers.get((x,y)) or board.layer_data.get((x,y),0)]
        rows.append(dict(id=board._id,name=board.name,object_name=board.object_name,width=board.map_width,height=board.map_height,
            terrain=deepcopy(board._terrain),elevation=deepcopy(board._elev),
            values={key:getattr(board,key) for key in SCALARS},visibility=board.visibility_config,
            objects=save_objects(board).hex(),empty_bits=bool(board.map_objects[8]) and bits_for(board).size()==0,
            roster_count=board.first_free,dynamic=save_dynamic(board).hex(),
            weather=dict(enabled=board.weather_enabled,conditions=sorted(board.weather_conditions),
                         configuration=dict(board.weather_config),cells=cells)))
    events=[]
    for event in engine.events.pending_events():
        if event.data not in boards:continue
        name=next((key for key,(_,cb) in CALLBACKS.items() if cb is event.callback),None)
        if name is None:continue
        board=event.data
        record=dict(map=board._id,callback=name,remaining=event.tick-engine.tick)
        if record['remaining']<1:raise ValueError('snapshot cannot serialize a currently due callback')
        if event.event_type==EventType.DECORATION:
            group=0 if name in ('spread_fire','expire_fire') else 1
            if event.data2 not in board.map_objects[group]:raise ValueError('snapshot cannot serialize orphan decoration event')
            record.update(group=group,index=board.map_objects[group].index(event.data2))
        events.append(record)
    document=dict(version=1,maps=rows,events=events)
    validate_snapshot(document)  # No file or map replacement if serialization is invalid.
    return document


def required(row,keys,optional=()):
    env.fields(row,set(keys)|set(optional))
    if set(keys)-row.keys():raise ValueError('missing snapshot fields')


def byte_stream(value):
    if not isinstance(value,str):raise ValueError('snapshot bytes require hex text')
    try:return bytes.fromhex(value)
    except ValueError:raise ValueError('invalid snapshot hex') from None


def validate_snapshot(document):
    required(document,('version','maps','events'))
    if type(document['version']) is not int or document['version']!=1:raise ValueError('unknown environment snapshot version')
    if not isinstance(document['maps'],list) or not document['maps']:raise ValueError('snapshot maps required')
    candidates={};source_records={}
    for row in document['maps']:
        required(row,('id','name','width','height','terrain','elevation','values','visibility','objects','roster_count','dynamic'),('weather','empty_bits','object_name'))
        identity=env.integer(row['id']);width=env.integer(row['width'],0,1000);height=env.integer(row['height'],0,1000)
        if identity in candidates:raise ValueError('duplicate snapshot map ID')
        if not isinstance(row['name'],str) or not isinstance(row['visibility'],str):raise ValueError('map name/visibility require text')
        board=GameMap(width,height,row['name']);board._id=identity
        board.object_name=row.get('object_name',row['name'])
        if not isinstance(board.object_name,str):raise ValueError('object name requires text')
        for key in ('terrain','elevation'):
            grid=row[key]
            if not isinstance(grid,list) or len(grid)!=height or any(not isinstance(r,list) or len(r)!=width for r in grid):
                raise ValueError('invalid snapshot grid dimensions')
            for r in grid:
                for value in r:
                    if key=='elevation':env.integer(value,0,9)
                    elif not isinstance(value,str) or len(value)!=1 or ord(value)>127:raise ValueError('invalid snapshot terrain')
        board._terrain=deepcopy(row['terrain']);board._elev=deepcopy(row['elevation'])
        required(row['values'],SCALARS)
        for key,value in row['values'].items():setattr(board,key,env.integer(value))
        env.integer(board.temp,-128,127);env.integer(board.grav,0,255)
        env.integer(board.winddir,-32768,32767);env.integer(board.windspeed,-32768,32767)
        board.visibility_config=row['visibility']
        records=decode_objects(byte_stream(row['objects']),width,height)
        sources=[]
        for group,obj in records:
            if group not in (5,7,8) and not board.valid(obj.x,obj.y):raise ValueError('snapshot object coordinates out of range')
            added=add_object(board,group,obj);sources.append((group,added))
            if group<=2:
                if not 0<=obj.datac<=127:raise ValueError('invalid decoration underlay')
                board.decorations[obj.x,obj.y]=added
                added.terrain=board.terrain(obj.x,obj.y)
        if type(row.get('empty_bits',False)) is not bool:raise ValueError('empty_bits requires Boolean')
        if row.get('empty_bits'):bits_for(board)
        publish_mine_bits(board)
        count=env.integer(row['roster_count'],0,255)
        dynamic=byte_stream(row['dynamic'])
        if len(dynamic)!=count*5+count*count*2+4:raise ValueError('snapshot dynamic length mismatch')
        load_dynamic(board,dynamic,count,{})
        if 'weather' in row:
            extension=row['weather'];required(extension,('enabled','conditions','configuration','cells'))
            if type(extension['enabled']) is not bool:raise ValueError('enabled requires Boolean')
            board.weather_enabled=extension['enabled']
            board.weather_conditions=env.normalized_conditions(extension['conditions'])
            board.weather_config=env.configuration(extension['configuration'])
            if not isinstance(extension['cells'],list):raise ValueError('snapshot cells require list')
            for cell in extension['cells']:
                required(cell,('x','y','layers','data'))
                x,y=env.cell(board,cell)
                if (x,y) in board.layers:raise ValueError('duplicate snapshot layer coordinate')
                board.layers[x,y]=env.names(cell['layers'],env.LAYERS)
                board.layer_data[x,y]=parse_decimal(cell['data'])
        candidates[identity]=board;source_records[identity]=sources
    if not isinstance(document['events'],list):raise ValueError('snapshot events require list')
    events=[];weather_maps=set()
    for row in document['events']:
        required(row,('map','callback','remaining'),('group','index'))
        identity=env.integer(row['map']);board=candidates.get(identity)
        if board is None:raise ValueError('event map absent from snapshot')
        name=row['callback']
        if not isinstance(name,str) or name not in CALLBACKS:raise ValueError('unknown environment callback')
        delay=env.integer(row['remaining'],1)
        obj=None
        if name=='weather':
            if not board.weather_enabled or not board.map_width or not board.map_height or identity in weather_maps:
                raise ValueError('invalid weather event ownership')
            weather_maps.add(identity)
        elif name in ('spread_fire','expire_fire','expire_smoke'):
            group=env.integer(row.get('group'));index=env.integer(row.get('index'),0)
            expected=1 if name=='expire_smoke' else 0
            objects=[obj for kind,obj in source_records[identity] if kind==group]
            if group!=expected or index>=len(objects):raise ValueError('invalid decoration event reference')
            # A self-replaced fire can own multiple live callbacks. Keep every
            # validated record in order; only weather has single-event ownership.
            obj=objects[index]
        events.append((identity,name,delay,obj))
    for identity,board in candidates.items():
        if board.weather_enabled and board.map_width and board.map_height and identity not in weather_maps:
            raise ValueError('enabled weather snapshot is missing its event')
    return candidates,events


def load_snapshot(engine,document):
    candidates,events=validate_snapshot(document)
    existing={board._id:board for board in engine.get_entities() if isinstance(board,GameMap)}
    units={unit._id:unit for unit in engine.get_entities() if isinstance(unit,Mech)}
    published={}
    for identity,candidate in candidates.items():
        board=existing.get(identity)
        if board is None:board=candidate
        else:
            engine.events.cancel_by_data(board)
            for unit in board.mechs_on_map:
                if unit is not None and unit.map is board:unit.map=None;unit.mapindex=-1;unit.mapnumber=0
            board.__dict__.update(candidate.__dict__)
        board._engine=engine
        # Registration without an early default event; restore all timers below.
        enabled=board.weather_enabled;board.weather_enabled=False
        engine.register_entity(board);board.weather_enabled=enabled
        published[identity]=board
    for board in published.values():
        board.mechs_on_map=[units.get(identity) for identity in board.roster_ids]
        for index,unit in enumerate(board.mechs_on_map):
            if unit is not None:
                unit.map=board;unit.mapindex=board._id;unit.mapnumber=index
                if board.valid(unit.x,unit.y):unit.terrain=board.terrain(unit.x,unit.y);unit.elev=board.elevation(unit.x,unit.y)
                from systems.map_conditions import update_conditions
                update_conditions(unit,board)
        from systems.map_membership import publish_los
        publish_los(board)
    for identity,name,delay,obj in events:
        board=published[identity];kind,callback=CALLBACKS[name]
        event=engine.events.schedule(delay,kind,callback,board,obj)
        if name=='weather':board.weather_event=event
        elif obj is not None:
            # Convenience handle only; cancellation sweeps all events by object.
            obj.event=event
    return published
