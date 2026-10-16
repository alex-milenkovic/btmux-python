# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.bits.c
#   btech/map.obj.c

"""Ordered map objects shared by decorations, mines, buildings and persistence."""
from dataclasses import dataclass, field, replace
import io
import struct
from entities.map_storage import BitTable, read_exact

EMPTY_ROWS=tuple(() for _ in range(10))
TYPES=('FIRE','SMOKE','DECO','MINE','BUILDING','LEAVE','ENTRA','LINKED','TBITS','BLZ')


@dataclass(eq=False)
class MapObject:
    x: int=0
    y: int=0
    obj: int=0
    datac: int=0
    datas: int=0
    datai: int=0
    type: int=0
    event: object=field(default=None,repr=False)
    terrain: str=''
    bits: object=field(default=None,repr=False)

    def __getitem__(self,key):
        return chr(self.datac) if key=='underlying' else getattr(self,key)


def resolve_map(board,identity):
    engine=getattr(board,'_engine',None)
    if engine is None: return None
    return next((obj for obj in engine.get_entities() if getattr(obj,'xcode_type',None)=='MAP' and obj._id==identity),None)


def first_object(board,kind):
    return next(iter(getattr(board,'map_objects',EMPTY_ROWS)[kind]),None)


def next_object(board,kind,obj):
    rows=board.map_objects[kind]
    index=rows.index(obj)+1
    return rows[index] if index<len(rows) else None


def add_object(board,kind,source):
    if not 0<=kind<10: raise ValueError('invalid map object type')
    if kind==3:
        from systems.mines import Mine, MineType
        result=Mine(source.x,source.y,MineType(source.datac),source.datas,source.datai,source.obj,source.type)
    else: result=replace(source)
    board.flags |= 1
    board.map_objects[kind].insert(0,result)
    if kind==8: publish_mine_bits(board)
    return result


def find_object(board,x,y,kind=-1):
    for group in (range(10) if kind<0 else (kind,)):
        for obj in getattr(board,'map_objects',EMPTY_ROWS)[group]:
            if (obj.x,obj.y)==(x,y): return obj
    return None


def find_decorations(board,x,y):
    for kind in range(3):
        obj=find_object(board,x,y,kind)
        if obj is not None: return obj.datac
    # Older supported fixture interfaces can still supply overlay dictionaries.
    obj=getattr(board,'decorations',{}).get((x,y))
    return ord(obj['underlying']) if obj else 0


def underlying_terrain(board,x,y):
    if board is None: return 0
    char=find_decorations(board,x,y)
    return chr(char) if char else board.terrain(x,y)


def mech_underlying_terrain(unit):
    board=getattr(unit,'map',None)
    char=find_decorations(board,unit.x,unit.y) if board is not None else 0
    return chr(char) if char else unit.terrain


def delete_object(board,obj,kind,zap=1):
    if not board.flags&1: return False
    rows=board.map_objects[kind]
    if obj not in rows: return False
    rows.remove(obj)
    if kind<=2:
        if board.decorations.get((obj.x,obj.y)) is obj: board.decorations.pop((obj.x,obj.y))
        if not zap&2: board.set_terrain(obj.x,obj.y,chr(obj.datac))
        if zap:
            if board._engine is not None:
                from core.events import EventType
                board._engine.events.cancel_by_type_and_data2(EventType.DECORATION,obj)
            if obj.event is not None: obj.event.cancel()
    if kind==8: publish_mine_bits(board)
    if kind==4:
        interior=resolve_map(board,obj.obj)
        if interior is not None:
            delete_objects(interior,5)
            interior.onmap=0
    return True


def delete_objects(board,kind=None):
    for group in (range(10) if kind is None else (kind,)):
        for obj in list(board.map_objects[group]): delete_object(board,obj,group,3)
    if kind is None: board.flags &= ~1


def delete_at(board,x,y,kind):
    matches=[obj for obj in board.map_objects[kind] if (obj.x,obj.y)==(x,y)]
    for obj in matches: delete_object(board,obj,kind,1)
    return len(matches)


def bits_for(board,create=True):
    obj=first_object(board,8)
    if obj is None and create:
        obj=add_object(board,8,MapObject(bits=BitTable(board.map_width,board.map_height)))
    return obj.bits if obj is not None else None


# Portable mapobj conversion: x/y i16, obj i32, type i8, datac i32,
# datas i16, datai i64. No native padding or next-pointer serialization.
RECORD=struct.Struct('<hhibihq')


def object_values(obj,kind):
    if kind==3: return (obj.x,obj.y,obj.creator,obj.mapobj_type,int(obj.type),obj.strength,obj.extra)
    return (obj.x,obj.y,obj.obj,obj.type,obj.datac,obj.datas,obj.datai)


def save_objects(board):
    result=bytearray([27])
    try:
        for kind,rows in enumerate(board.map_objects):
            if kind==8:
                if rows: result.extend(rows[0].bits.save())
            else:
                for obj in rows: result.extend(bytes([kind+1])+RECORD.pack(*object_values(obj,kind)))
    except struct.error as error: raise ValueError('object outside portable record range') from error
    return bytes(result)+b'\0\x27'


def decode_objects(data,width,height):
    """Validate records before publishing B2 storage or snapshot state."""
    stream=io.BytesIO(data)
    if read_exact(stream,1)!=b'\x1b': raise ValueError('Error: No mapobjstart found!')
    records=[]
    while True:
        marker=read_exact(stream,1)[0]
        if marker==0: break
        if marker>10: raise ValueError('invalid object type marker')
        kind=marker-1
        if kind==8:
            obj=MapObject(bits=BitTable.load(stream,width,height))
        else:
            values=RECORD.unpack(read_exact(stream,RECORD.size))
            obj=MapObject(x=values[0],y=values[1],obj=values[2],type=values[3],datac=values[4],datas=values[5],datai=values[6])
            if kind==3:
                from systems.mines import MineType
                MineType(obj.datac)
        records.append((kind,obj))
    if read_exact(stream,1)!=b'\x27': raise ValueError('Error: No mapobjend found!')
    return records


def load_objects(board,data):
    # Preflight only B2 bit rows before the source destructive object loader.
    # Non-bit framing failures retain the accepted source partial-load behavior.
    probe=io.BytesIO(data)
    if read_exact(probe,1)!=b'\x1b': raise ValueError('Error: No mapobjstart found!')
    while True:
        marker=probe.read(1)
        if not marker or marker[0] not in range(1,11):break
        if marker==b'\x09':BitTable.load(probe,board.map_width,board.map_height)
        elif len(probe.read(RECORD.size))!=RECORD.size:break
    stream=io.BytesIO(data);read_exact(stream,1)
    board.map_objects=[[] for _ in range(10)]
    board.mines=board.map_objects[3]
    board.decorations={}
    publish_mine_bits(board)
    while True:
        marker=read_exact(stream,1)[0]
        if marker==0:break
        if marker>10:raise ValueError('invalid object type marker')
        kind=marker-1
        if kind==8:obj=MapObject(bits=BitTable.load(stream,board.map_width,board.map_height))
        else:
            values=RECORD.unpack(read_exact(stream,RECORD.size))
            obj=MapObject(x=values[0],y=values[1],obj=values[2],type=values[3],datac=values[4],datas=values[5],datai=values[6])
        add_object(board,kind,obj)
        if kind==4:
            from systems.buildings import start_regen
            start_regen(resolve_map(board,obj.obj))
    if read_exact(stream,1)!=b'\x27':raise ValueError('Error: No mapobjend found!')
    publish_mine_bits(board)


def sync_mine_bits(board,covered):
    """Publish mine coverage using the authorized packed layout, retaining hangars."""
    bits=bits_for(board,bool(covered))
    if bits is None: return
    bits.clear(1)
    for x,y in sorted(covered): bits.set(x,y,1)
    # First-table attachment publishes empty rows; publish again after filling.
    publish_mine_bits(board)


def publish_mine_bits(board):
    """Mirror loaded source bits into the existing logical mine fast-path."""
    bits=bits_for(board,False)
    board.mine_hexes={(x,y) for y in range(board.map_height) for x in range(board.map_width)
                     if bits is not None and bits.query(x,y,1)} if bits is not None else set()
