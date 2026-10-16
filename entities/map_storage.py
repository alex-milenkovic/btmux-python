# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.bits.c
#   btech/map.c
#   btech/map.coding.c
#   btech/map.dynamic.c
#   btech/map.obj.c
#   btech/src/include/glue_types.h

"""Defined map.coding/map.bits operations and explicit little-endian records.

Dynamic records use signed 32-bit IDs, 8-bit flags, 16-bit LOS and 32-bit
magic. Bit row-presence markers use 64 bits by default and never contain
addresses. These are documented conversions, not native MUX memory dumps.
"""
import io
import struct


class Coding:
    def __init__(self):
        self.counter = 0
        self.initialize()

    def initialize(self):
        self.forward = {}
        self.reverse = [('\0',0)] * 256

    def index(self, terrain, elevation):
        if not isinstance(terrain,str) or len(terrain)!=1 or not 0<=ord(terrain)<128 or not 0<=elevation<=9:
            raise ValueError('coding requires terrain 0..127 and elevation 0..9')
        pair=(terrain,elevation)
        if pair in self.forward: return self.forward[pair]
        if self.counter>=255: raise ValueError('source coding supports at most 255 allocations')
        index=self.counter
        self.forward[pair]=index
        self.reverse[index]=pair
        self.counter+=1
        return index

    def inverse(self,index):
        if not 0<=index<256: raise ValueError('coding index out of range')
        return self.reverse[index]


def source_int(value):
    """Reject undefined scanf int overflow before publishing narrowed fields."""
    if not -(1<<31)<=value<(1<<31): raise ValueError('unsupported source signed integer overflow')
    return value


def signed_value(value,bits):
    """Supported two's-complement source char/short assignment."""
    return (value+(1<<(bits-1)))%(1<<bits)-(1<<(bits-1))


def io_error(operation,map_id,cause):
    prefix=('load_mapdynamic(): while reading' if operation=='read' else 'save_mapdynamic(): while writing')
    return f'{prefix} #{map_id}: {cause}' if map_id is not None else f'{operation}-error: {cause}'


def read_exact(stream,size,map_id=None):
    try: data=stream.read(size)
    except OSError as error: raise ValueError(io_error('read',map_id,str(error))) from error
    if len(data)!=size: raise ValueError(io_error('read',map_id,f'short map record ({len(data)} of {size} bytes)'))
    return data


def write_exact(stream,data,map_id=None):
    try: written=stream.write(data)
    except OSError as error: raise ValueError(io_error('write',map_id,str(error))) from error
    if written!=len(data): raise ValueError(io_error('write',map_id,f'short map record ({written} of {len(data)} bytes)'))


class BitTable:
    def __init__(self,width,height):
        self.width,self.height=width,height
        self.rows=[None]*height
        self.attached=True

    @property
    def row_size(self): return (self.width+3)//4

    def position(self,x,y,access=False):
        if type(x) is not int or type(y) is not int or not 0<=x<self.width or not 0<=y<self.height: raise ValueError('bit coordinates out of range')
        index=x//4  # Authorized B1: four two-bit cells per byte.
        return index,2*(x%4)

    def set(self,x,y,bit):
        index,shift=self.position(x,y,True)
        if bit not in (1,2): raise ValueError('bit selector requires 1 or 2')
        if self.rows[y] is None: self.rows[y]=bytearray(self.row_size)
        self.rows[y][index] |= bit<<shift

    def unset(self,x,y,bit):
        self.position(x,y)
        if self.rows[y] is None: return
        index,shift=self.position(x,y,True)
        self.rows[y][index] &= ~(bit<<shift)&255

    def query(self,x,y,bit):
        self.position(x,y)
        if self.rows[y] is None: return 0
        index,shift=self.position(x,y,True)
        return self.rows[y][index] & (bit<<shift)

    def clear(self,selector):
        if selector not in (0,1,2): return
        # Reject the complete unsafe operation before modifying any row.
        for y,row in enumerate(self.rows):
            if row is not None:
                for x in range(self.width): self.position(x,y,True)
        for y,row in enumerate(self.rows):
            if row is not None:
                for x in range(self.width):
                    for bit in ((1,2) if selector==0 else (selector,)): self.unset(x,y,bit)

    def size(self): return sum(self.row_size for row in self.rows if row is not None)

    def save(self,pointer_size=8):
        if pointer_size not in (4,8): raise ValueError('pointer marker width must be 4 or 8')
        self.rows=[row if row is not None and any(row) else None for row in self.rows]
        if not any(row is not None for row in self.rows): return b''
        markers=b''.join(int(row is not None).to_bytes(pointer_size,'little') for row in self.rows)
        return b'\x09'+markers+b''.join(bytes(row) for row in self.rows if row is not None)

    @classmethod
    def load(cls,stream,width,height,pointer_size=8):
        if pointer_size not in (4,8): raise ValueError('pointer marker width must be 4 or 8')
        bits=cls(width,height)
        markers=[int.from_bytes(read_exact(stream,pointer_size),'little') for _ in range(height)]
        bits.rows=[bytearray(read_exact(stream,bits.row_size)) if marker else None for marker in markers]
        bits.attached=True  # Authorized B2: publish only fully decoded rows.
        return bits


def save_dynamic(board,stream=None):
    count=len(board.roster_ids)
    if count>255 or len(board.mechflags)!=count or len(board.slot_los)<count or any(len(row)<count for row in board.slot_los[:count]):
        raise ValueError('invalid dynamic array dimensions')
    sink=io.BytesIO() if stream is None else stream
    write=lambda data: write_exact(sink,data,board._id)
    try:
        write(struct.pack('<'+'i'*count,*board.roster_ids))
        write(bytes(board.mechflags))
        for row in board.slot_los[:count]: write(struct.pack('<'+'H'*count,*row[:count]))
        write(struct.pack('<I',0x67134269))
    except struct.error as error: raise ValueError('dynamic value outside record domain') from error
    return sink.getvalue() if stream is None else None


def load_dynamic(board,data,count,registry):
    if not 0<=count<=255: raise ValueError('dynamic count requires 0..255')
    stream=io.BytesIO(data) if isinstance(data,bytes) else data
    read=lambda size: read_exact(stream,size,board._id)
    ids=list(struct.unpack('<'+'i'*count,read(4*count)))
    flags=list(read(count))
    los=[list(struct.unpack('<'+'H'*count,read(2*count))) for _ in range(count)]
    magic=struct.unpack('<I',read(4))[0]
    if magic!=0x67134269:
        raise ValueError(f'load_mapdynamic(): while reading #{board._id}: Magic number mismatch (0x{magic:08X} != 0x67134269)')
    board.roster_ids,board.mechflags,board.slot_los=ids,flags,los
    board.mechs_on_map=[registry.get(key) for key in ids]
    board.losinfo={(a,b):los[i][j] for i,a in enumerate(ids) for j,b in enumerate(ids) if a>=0 and b>=0}


def source_sizes(board,profile='LP64'):
    """Source MAP/mapobj sizeof estimates for explicit C data-model profiles."""
    if board is None: return {'map':0,'mechs':0,'objects':0,'profile':profile}
    if profile not in ('LP64','ILP32'): raise ValueError('ABI profile requires LP64 or ILP32')
    pointer=8 if profile=='LP64' else 4
    def layout(fields):
        offset=0; maximum=1
        for size,align in fields:
            offset=(offset+align-1)//align*align+size
            maximum=max(maximum,align)
        return (offset+maximum-1)//maximum*maximum
    char=(1,1); short=(2,2); integer=(4,4); ptr=(pointer,pointer)
    xcode=(layout([integer,ptr]),pointer)  # GlueType and size_t, glue_types.h.
    map_size=layout([xcode,ptr,ptr,(31,1),short,short,char,char,short,char,char,short,char,short,short,
                     integer,(10*pointer,pointer),short,short,ptr,char,char,ptr,ptr,ptr,short,short,integer,integer])
    obj_size=layout([short,short,ptr,char,integer,short,ptr,ptr])
    count=len(board.roster_ids)
    return {'profile':profile,'map':map_size+(pointer if board._terrain is not None else 0),
            'mechs':count*(pointer+1+pointer+count*2),'objects':obj_size*sum(map(len,board.map_objects)),
            'sizeof_map':map_size,'sizeof_mapobj':obj_size,'pointer':pointer,'dbref':pointer}
