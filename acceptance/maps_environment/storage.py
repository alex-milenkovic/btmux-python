import io
from struct import pack
from entities.map_storage import Coding,save_dynamic,load_dynamic
from entities.map_objects import bits_for
from systems import map_membership as membership
from . import step,eq,board,unit,attempt,TERRAIN


@step(r'a width 9 map has no allocated bit rows')
def empty_bits(w): board(w); w['bits']=bits_for(w['map'])


@step(r'bit (mine|hangar) is set at column (\d+) row 0')
def set_bit(w,kind,x):
    w['bit']=1 if kind=='mine' else 2; w['x']=int(x)
    w['bits'].set(w['x'],0,w['bit'])


@step(r'the byte index is (\d+) the query value is (\d+) and allocated byte count is 3')
def bit_result(w,index,value):
    bits=w['bits']; x=w['x']
    eq(bits.position(x,0)[0],int(index)); eq(bits.query(x,0,w['bit']),int(value)); eq(bits.size(),3)


@step(r'mine and hangar bits are set at column 1 row 0 on a width 9 map')
def both_bits(w): empty_bits(w); w['bits'].set(1,0,1); w['bits'].set(1,0,2)


@step(r'clear_hex_bits uses selector (\d+)')
def clear_bits(w,selector): w['bits'].clear(int(selector))


@step(r'mine query is (\d+) and hangar query is (\d+)')
def queries(w,mine,hangar): eq(w['bits'].query(1,0,1),int(mine)); eq(w['bits'].query(1,0,2),int(hangar))


@step(r'a width 9 map has row state (.+)')
def rows(w,state):
    empty_bits(w)
    if state!='never-allocated': w['bits'].set(0,0,1)
    if state=='allocated-all-zero': w['bits'].unset(0,0,1)
    if state=='two-nonzero-rows': w['bits'].set(0,1,2)


@step(r'the bit record is saved')
def save_bits(w): w['wire']=w['bits'].save()


@step(r'the type marker is (absent|9) and allocated bytes afterward are (\d+)')
def bit_save_result(w,marker,size):
    eq(str(w['wire'][0]) if w['wire'] else 'absent',marker); eq(w['bits'].size(),int(size))


@step(r'a fresh coding dictionary starts at counter zero')
def coding(w): w['coding']=Coding()


@step(r'the terrain elevation requests are (.+)')
def coding_requests(w,requests):
    import re
    w['pairs']=[(TERRAIN[name],int(elev)) for name,elev in (re.fullmatch(r'(.+?)(\d+)',value).groups() for value in requests.split(','))]
    w['indices']=[w['coding'].index(*pair) for pair in w['pairs']]


@step(r'returned indices are (.+) and each safe inverse lookup reproduces its pair')
def coding_result(w,indices):
    eq(w['indices'],list(map(int,indices.split(','))))
    eq([w['coding'].inverse(index) for index in w['indices']],w['pairs'])


@step(r'a coding dictionary has allocated (\d+) distinct safe pairs')
def allocated(w,count):
    coding(w)
    for value in range(int(count)): w['coding'].index(' ',value)


@step(r'initialization clears the arrays and grass zero is requested')
def reinitialize(w): w['coding'].initialize(); w['index']=w['coding'].index(' ',0)


@step(r'the returned index is (\d+)')
def new_index(w,index): eq(w['index'],int(index))


def roster(w,text):
    b=board(w); ids=[] if text=='empty' else list(map(int,text.split(',')))
    count=len(ids); b.roster_ids=ids; b.mechflags=[0]*count; b.slot_los=[[0]*count for _ in ids]
    w['units']={}
    for index,identity in enumerate(ids):
        if identity<0: b.mechs_on_map.append(None); continue
        u=unit(w,identity); u.map=b; u.mapindex=b._id; u.mapnumber=index
        b.mechs_on_map.append(u); w['units'][identity]=u
    membership.publish_los(b)


@step(r'a map has roster (.+) and a valid unit with ID (\d+)')
def roster_add(w,before,identity):
    roster(w,before); w['unit']=w['units'].get(int(identity)) or unit(w,identity)


@step(r'the unit is added to the map')
def add(w): membership.add(w['map'],w['unit'])


@step(r'the resulting roster is (.+)')
def roster_result(w,text): eq(w['map'].roster_ids,[] if text=='empty' else list(map(int,text.split(','))))


@step(r'the assigned slot is (\d+)')
def slot(w,value): eq(w['unit'].mapnumber,int(value))


@step(r'a map has roster (.+) with consistent unit slots')
def remove_setup(w,before): roster(w,before)


@step(r'the operation is (eliminate|remove\d+)')
def operation(w,operation):
    if operation=='eliminate': membership.eliminate_empties(w['map'])
    else: membership.remove(w['map'],w['units'][int(operation[6:])])


@step(r'a dynamic snapshot uses count (\d+) with stream condition (.+)')
def dynamic(w,count,condition):
    w['count']=int(count)
    roster(w,'10,20' if int(count) else 'empty')
    if int(count): w['map'].mechflags=[1,2]; w['map'].slot_los=[[1,17],[29,4]]
    wire=save_dynamic(w['map'])
    w['expected_dynamic']=(list(w['map'].roster_ids),list(w['map'].mechflags),[list(row) for row in w['map'].slot_los])
    lengths={'short-roster':7,'short-flags':9,'short-LOS':15,'missing-magic':0}
    if condition in lengths: wire=wire[:lengths[condition]]
    if condition=='wrong-magic': wire=pack('<I',0)
    w['wire']=wire


@step(r'the snapshot is loaded through the documented persistence interface')
def load(w): attempt(w,load_dynamic,w['map'],w['wire'],w['count'],w['units'])


@step(r'the result is (empty-arrays|exact-roundtrip|read-error|magic-error)')
def dynamic_result(w,result):
    if result.endswith('error'): assert result in w['error'],w['error']
    else:
        eq(w['error'],None)
        eq((w['map'].roster_ids,w['map'].mechflags,w['map'].slot_los),w['expected_dynamic'])


@step(r'a map of width (\d+) has both bits set at its last valid column')
def edge_setup(w,width):
    board(w,int(width),1);w['x']=int(width)-1
    bits=bits_for(w['map']);bits.set(w['x'],0,1);bits.set(w['x'],0,2)


@step(r'its bit stream is saved and loaded into a fresh map of identical dimensions')
def edge_roundtrip(w):
    from entities.map_objects import save_objects,load_objects
    wire=save_objects(w['map']);width=w['map'].map_width
    board(w,width,1);load_objects(w['map'],wire)


@step(r'byte index is (\d+) mine query is (\d+) hangar query is (\d+) and allocated row bytes are (\d+)')
def edge_result(w,index,mine,hangar,size):
    bits=bits_for(w['map'],False);assert bits is not None
    eq(bits.position(w['x'],0)[0],int(index));eq(bits.query(w['x'],0,1),int(mine))
    eq(bits.query(w['x'],0,2),int(hangar));eq(bits.size(),int(size));eq(bits.attached,True)


@step(r'a width 5 map has an attached bit table with a mine at column 4')
def loaded_setup(w):board(w,5,1);bits_for(w['map']).set(4,0,1)


@step(r'the storage command sequence is (.+)')
def storage_sequence(w,sequence):
    from entities.map_objects import save_objects,load_objects,delete_objects
    from systems.map_management import resize
    if sequence=='truncated-load':attempt(w,load_objects,w['map'],save_objects(w['map'])[:-3])
    elif sequence=='set-column-5':attempt(w,bits_for(w['map']).set,5,0,1)
    else:
        if sequence.startswith('clear-all'):bits_for(w['map']).clear(0)
        if sequence.startswith('delete-TBITS'):delete_objects(w['map'],8)
        attempt(w,resize,w['map'],'9 9')


@step(r'the result is (error-and-original-mine-retained|bounds-error-and-original-mine-retained|refused-with-width-5|success-without-bit-table)')
def storage_result(w,result):
    if result=='success-without-bit-table':eq(w['error'],None);eq(w['map'].map_width,9);eq(bits_for(w['map'],False),None)
    else:
        assert w['error'];eq(w['map'].map_width,5)
        if result.endswith('mine-retained'):eq(bits_for(w['map']).query(4,0,1),1)
