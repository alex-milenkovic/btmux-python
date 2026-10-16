import io
from entities.map_objects import MapObject,add_object,delete_object,save_objects,load_objects,RECORD
from physics.decorations import add_smoke,add_fire,expire_fire,spread_fire
from core.events import EventType
from systems.map_management import delobj
from . import step,eq,board,attempt,invoke,run_to,TERRAIN


@step(r'a map contains FIRE objects in list order A B and BUILD objects in list order C D')
def ordered(w):
    for kind,names in ((0,'BA'),(4,'DC')):
        for name in names: add_object(w['map'],kind,MapObject(x=1,y=1,obj=ord(name),datac=ord(' ')))


@step(r'the object snapshot operation is (.+)')
def snapshot(w,operation):
    w['operation']=operation; wire=save_objects(w['map']); w['wire']=wire; w['error']=None
    if operation=='save-then-load': load_objects(w['map'],wire)
    elif operation=='load-bad-start': attempt(w,load_objects,w['map'],b'!'+wire[1:])
    elif operation=='load-bad-end': attempt(w,load_objects,w['map'],wire[:-1]+b'!')


@step(r'the result is (27,FIRE-A,FIRE-B,BUILD-C,BUILD-D,0,39|FIRE-B,FIRE-A,BUILD-D,BUILD-C|error-retain-existing|error-after-record-load)')
def stream_result(w,result):
    labels=[]
    if w['operation']=='save':
        wire=io.BytesIO(w['wire']); labels.append(str(wire.read(1)[0]))
        while True:
            kind=wire.read(1)[0]
            if not kind: labels.extend(('0',str(wire.read(1)[0]))); break
            record=RECORD.unpack(wire.read(RECORD.size))
            labels.append(('FIRE' if kind==1 else 'BUILD')+'-'+chr(record[2]))
        eq(','.join(labels),result)
    else:
        labels=[('FIRE' if kind==0 else 'BUILD')+'-'+chr(obj.obj) for kind in (0,4) for obj in w['map'].map_objects[kind]]
        expected='FIRE-A,FIRE-B,BUILD-C,BUILD-D' if result=='error-retain-existing' else 'FIRE-B,FIRE-A,BUILD-D,BUILD-C'
        eq(','.join(labels),expected)
        if result.startswith('error'): assert w['error']


@step(r'a timed smoke object covers water and has a pending event')
def smoke(w):
    w['map'].set_terrain(1,1,'~'); w['object']=add_smoke(w['engine'],w['map'],1,1,30)
    w['event']=w['object'].event


@step(r'that single object is deleted with zap (\d+)')
def zap(w,zap): delete_object(w['map'],w['object'],1,int(zap))


@step(r'raw terrain is (water|smoke) and its pending event is (retained|cancelled) while MAPO remains set')
def deleted(w,terrain,event):
    eq(w['map'].terrain(1,1),TERRAIN[terrain]); eq(w['event'].zombie,event=='cancelled'); assert w['map'].flags&1


@step(r'two mine objects and one BLZ object share hex 1 1 and a fourth object is elsewhere')
def deletion_setup(w):
    for _ in range(2): add_object(w['map'],3,MapObject(x=1,y=1,datac=1,datas=5))
    add_object(w['map'],9,MapObject(x=1,y=1)); add_object(w['map'],9,MapObject(x=2,y=2))
    w['map'].mine_hexes={(8,8)}


@step(r'delobj receives (.+)')
def delete_command(w,text): attempt(w,delobj,w['map'],text.replace(',',' '))


@step(r'deleted count is (\d+) with mine recalculation (yes|no|type-error)')
def deletion_result(w,count,recalculate):
    if recalculate=='type-error': assert 'Invalid type!' in w['error']; eq(sum(map(len,w['map'].map_objects)),4)
    else:
        eq(w['result'],int(count)); eq(w['map'].mine_hexes=={(8,8)},recalculate=='no')


@step(r'water elevation 2 at hex 1 1 receives smoke duration 30 at tick 0')
def smoke_clock(w): smoke(w); w['map'].set_elevation(1,1,2)


@step(r'the next action is (.+) and the clock reaches (\d+)')
def lifecycle(w,action,tick):
    if action!='none':
        run_to(w,10)
        if action=='replace-at-10-duration-40': add_smoke(w['engine'],w['map'],1,1,40)
        elif action=='delete-at-10': delete_object(w['map'],w['object'],1,1)
        else: raise ValueError(action)
    run_to(w,tick)


@step(r'raw terrain is (water|smoke) with underlying water and pending decoration count (\d+)')
def smoke_result(w,terrain,count):
    eq(w['map'].terrain(1,1),TERRAIN[terrain]); eq(w['map'].rterrain(1,1),'~')
    eq(w['engine'].events.count_type(EventType.DECORATION),int(count))


@step(r'an isolated light forest receives fire duration (\d+) at tick 0 with windspeed (\d+)')
def fire(w,duration,wind):
    board(w,1,1); w['map'].set_terrain(0,0,'`'); w['map'].windspeed=int(wind)
    w['object']=add_fire(w['engine'],w['map'],0,0,int(duration))


@step(r'the fire is inspected immediately and its first scheduled event runs')
def fire_event(w):
    obj=w['object']; w['initial']=obj.datas; w['first']=obj.event.tick; run_to(w,w['first'])


@step(r'stored initial duration is (\d+) first deadline is (\d+) and next callback is (spread|dissipate) at (\d+)')
def fire_result(w,duration,first,callback,deadline):
    eq(w['initial'],int(duration)); eq(w['first'],int(first)); eq(w['object'].event.tick,int(deadline))
    eq(w['object'].event.callback,spread_fire if callback=='spread' else expire_fire)


@step(r'a fire object has underlying (.+) and no surviving spread event')
def dissipate_setup(w,terrain):
    w['map'].set_terrain(1,1,TERRAIN[terrain]); w['object']=add_fire(w['engine'],w['map'],1,1,30)
    w['object'].event.cancel()


@step(r'its dissipation callback runs with forest roll (\d+)')
def dissipate(w,roll):
    w['streams']={'fire_dissipation':[int(roll)]}
    invoke(w,expire_fire,w['object'].event)


@step(r'final terrain is (.+) and the forest draw is (consumed|unused)')
def dissipated(w,terrain,draw): eq(w['map'].terrain(1,1),TERRAIN[terrain]); eq(bool(w['draws']),draw=='consumed')
