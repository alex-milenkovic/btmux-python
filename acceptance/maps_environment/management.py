from pathlib import Path
from tempfile import TemporaryDirectory
from entities.map_objects import MapObject,add_object,bits_for
from physics.decorations import add_smoke,add_fire
from systems import map_management as maps
from . import step,eq,board,unit,attempt,invoke,TERRAIN


@step(r'a 3 by 3 map has a unit at 1 1 with cached grass elevation 0 and another at 2 2')
def cached(w):
    b=board(w,3,3)
    first=unit(w,40); first.x=first.y=1; b.add_mech(first)
    other=unit(w,41); other.x=other.y=2; b.add_mech(other)
    w['unit']=first; w['other']=other


@step(r'addhex receives (.+)')
def edit(w,args): attempt(w,maps.addhex,w['map'],args.replace(',',' '))


@step(r'the outcome is (success|out-of-range|arity-error) with terrain (.+) elevation (\d+) and cached unit elevation 0')
def edit_result(w,outcome,terrain,elev):
    eq(w['error'] is None,outcome=='success')
    if outcome!='success': assert ('out of range' if outcome=='out-of-range' else 'number of arguments') in w['error']
    eq((w['map'].terrain(1,1),w['map'].elevation(1,1)),(TERRAIN[terrain],int(elev)))
    eq(w['unit'].elev,0); eq(w['unit'].terrain,TERRAIN[terrain]); eq(w['other'].terrain,' ')


@step(r'a 30 by 30 map has player TACSIZE (.+)')
def view_setup(w,value): board(w,30,30); w['tacsize']='' if value=='absent' else value.replace(',',' ')


@step(r'view is requested at -3 99')
def view(w): w['view']=maps.view(w['map'],'-3 99',w['tacsize'])


@step(r'the renderer request has center 0 29 dimensions (\d+) (\d+) and warning (none|invalid-tacsize)')
def viewed(w,height,width,warning):
    eq((w['view']['x'],w['view']['y'],w['view']['height'],w['view']['width']),(0,29,int(height),int(width)))
    eq(any('Illegal Tacsize' in message for message in w['map'].map_messages),warning=='invalid-tacsize')
    eq(w['view']['applied'],False)


@step(r'an allocated empty map has identity 41')
def allocate(w):
    w['map']=maps.initialize(41,True); w['engine'].register_entity(w['map']); w['map'].add_mech(unit(w))


@step(r'mapemit receives (.+)')
def emit(w,text): attempt(w,maps.emit,w['map'],text.replace('SPACES','   '))


@step(r'the map remains 21 by 11 grass zero with regen factor 1 and the emission is (.+)')
def emitted(w,result):
    b=w['map']; eq((b._id,b.map_width,b.map_height,b.regen_factor),(41,21,11,1))
    assert all(t==' ' for row in b._terrain for t in row); assert all(e==0 for row in b._elev for e in row)
    if result=='empty-error': assert w['error']; eq(w['unit'].movement_messages,[])
    else: eq(w['unit'].movement_messages[-1],result.replace('SPACES','   '))


@step(r'a live 2 by 2 map named old and a map file of kind (.+)')
def file_fixture(w,kind):
    board(w,2,2); w['map'].name='old'
    w['file_kind']=kind
    w['text']={'zero-width':'0 2\n','width-1001':'1001 2\n','short-row':'2 2\n.0\n',
               'valid-2x2':'2 2\n.0.0\n.0.0\n','unknown-terrain-2x2':'2 2\n$0.0\n.0.0\n'}.get(kind)


@step(r'the map file is checked before the load command')
def check(w):
    with TemporaryDirectory(dir='./tmp') as directory:
        path=Path(directory)/'map'
        if w['text'] is not None: path.write_text(w['text'])
        w['check']=maps.check_file(path)


@step(r'the check code is (-?\d+) and the existing map is (retained|replaceable)')
def checked(w,code,state):
    eq(w['check'],int(code)); eq((w['map'].map_width,w['map'].map_height,w['map'].name),(2,2,'old'))
    eq(state=='replaceable',w['check']==1)


@step(r'one elevation 3 cell has terrain (.+) with decoration (.+) and eternal fire flag (0|1)')
def saving_cell(w,terrain,deco,eternal):
    board(w,1,1); b=w['map']; b.set_elevation(0,0,3); b.set_terrain(0,0,TERRAIN[terrain])
    if deco=='fire-on-light-forest':
        b.set_terrain(0,0,'`'); add_fire(w['engine'],b,0,0,100)
    elif deco=='smoke-on-water':
        b.set_terrain(0,0,'~'); add_smoke(w['engine'],b,0,0,100)
    if eternal=='1': b.flags|=8


@step(r'the map is saved as text')
def save_text(w): w['text']=maps.save_text(w['map'])


@step(r'its terrain elevation pair is (.+) and live terrain becomes (.+)')
def pair(w,pair,live): eq(w['text'].splitlines()[1],pair); eq(w['map'].terrain(0,0),TERRAIN[live])


@step(r'a map has flags (\d+) gravity 75 and temperature -20')
def trailer_setup(w,flags): w['map'].flags=int(flags); w['map'].grav=75; w['map'].temp=-20


@step(r'it is saved and loaded into a fresh map')
def roundtrip(w):
    text=maps.save_text(w['map']); board(w); eq(maps.load_text(w['map'],text,'restored'),0); w['text']=text


@step(r'a trailer is (absent|present) and loaded gravity is (\d+) and temperature is (-?\d+)')
def trailer(w,present,grav,temp):
    eq(': ' in w['text'],present=='present'); eq((w['map'].grav,w['map'].temp),(int(grav),int(temp)))


@step(r'a 2 by 2 map has rough elevation 3 at 1 1 and bit table (absent|present-empty)')
def resize_setup(w,bits):
    board(w,2,2); w['map'].set_terrain(1,1,'%'); w['map'].set_elevation(1,1,3)
    if bits=='present-empty': bits_for(w['map'])


@step(r'resize requests dimensions (\d+) (\d+)')
def resize(w,width,height): w['size']=(int(width),int(height)); attempt(w,maps.resize,w['map'],width+' '+height)


@step(r'the resize outcome is (success|refused) with original corner (retained|removed) and new cells grass zero')
def resized(w,outcome,corner):
    eq(w['error'] is None,outcome=='success'); b=w['map']
    eq((b.map_width,b.map_height),w['size'] if outcome=='success' else (2,2))
    if corner=='retained': eq((b.terrain(1,1),b.elevation(1,1)),('%',3))
    else: eq(b.valid(1,1),False)
    for y in range(b.map_height):
        for x in range(b.map_width):
            if x>=2 or y>=2: eq((b.terrain(x,y),b.elevation(x,y)),(' ',0))
