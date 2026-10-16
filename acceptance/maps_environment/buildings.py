from types import SimpleNamespace
from entities.map_objects import MapObject,add_object,bits_for
from core.events import EventType
from systems import buildings as buildings, map_links as links
from . import step,eq,board,unit,invoke,run_to


def building(w,cf,maximum=100):
    exterior=w['map']; interior=board(w); interior._id=2000; interior.name='Depot'
    interior.cf=int(cf); interior.cfmax=int(maximum)
    w['map']=exterior; w['interior']=interior
    add_object(exterior,4,MapObject(x=1,y=1,obj=2000))
    exterior.add_mech(unit(w))
    w['unit'].x=w['unit'].y=1


@step(r'a building has CF (\d+) maximum (\d+) and no timers')
def cf_setup(w,cf,maximum): building(w,cf,maximum)


@step(r'it takes explicit damage (\d+) at tick 0')
def damage(w,damage): invoke(w,buildings.hit_building,w['unit'],1,1,-1,int(damage))


def deadline(w):
    return next((str(event.tick) for event in w['engine'].events.pending_events() if event.event_type==EventType.BREGEN),'none')


@step(r'CF becomes (\d+) and newly scheduled regen deadline is (none|\d+)')
def damage_result(w,cf,tick): eq(w['interior'].cf,int(cf)); eq(deadline(w),tick)


@step(r'a building with CF (\d+) maximum 100 and regen factor (-?\d+) has a regen event due at 120')
def regen_setup(w,cf,factor):
    building(w,cf); w['interior'].regen_factor=int(factor)
    w['engine'].events.schedule(120,EventType.BREGEN,buildings.regen,w['interior'])


@step(r'the event runs at tick 120')
def regen(w): run_to(w,120)


@step(r'CF is (\d+) and next regen deadline is (none|\d+)')
def regen_result(w,cf,tick): damage_result(w,cf,tick)


@step(r'the rebuild callback is invoked diagnostically')
def rebuild(w): buildings.rebuild(SimpleNamespace(data=w['interior']))


@step(r'CF is (\d+) and no timer is scheduled')
def rebuilt(w,cf): damage_result(w,cf,'none')


@step(r'a building at CF 100 has exterior flags (\d+) and interior flags (\d+)')
def safety(w,exterior,interior): building(w,100); w['map'].buildflag=int(exterior); w['interior'].buildflag=int(interior)


@step(r'a unit hits it with explicit damage 10')
def safety_hit(w): damage(w,'10')


@step(r'CF is (\d+) and scratches-paint notification is (present|absent)')
def safe(w,cf,scratch):
    eq(w['interior'].cf,int(cf)); eq('Your shot only scratches the paint!' in w['unit'].movement_messages,scratch=='present')


@step(r'a same-elevation unit stands on a valid hangar for a building with flags (\d+) and CF 75')
def visible_setup(w,flags):
    building(w,75); w['interior'].buildflag=int(flags); w['unit'].z=0; bits_for(w['map']).set(1,1,2)


@step(r'the query (step|scan) uses a successful perception roll if required')
def query(w,kind):
    from entities.pilot import Pilot
    w['unit'].in_character=True; w['unit'].pilot=Pilot(perception=6)
    w['streams']={'perception_rolls':[12]}
    w['visible']=invoke(w,buildings.query,w['unit'],1,1,step=kind=='step')


@step(r'the building CF is (shown|hidden)')
def seen(w,value): eq(w['visible'],75 if value=='shown' else None)


@step(r'a map has width (\d+) and height (\d+)')
def dimensions(w,width,height): board(w,width,height)


@step(r'direction (north|east|south|west) uses coordinate input (.+)')
def coordinate(w,direction,text): w['coord']=links.parse_coord(w['map'],('north','east','south','west').index(direction),text)


@step(r'parse outcome is (success|failure) and coordinates are (.+)')
def coord_result(w,result,xy):
    valid,x,y=w['coord']; eq(valid,result=='success')
    expected=(None,None) if xy=='unset' else tuple(None if v=='unset' else int(v) for v in xy.split(','))
    eq((x,y),expected)


@step(r'a block at the tested landing hex has radius (-?\d+) and exempt team (\d+)')
def lz(w,radius,team): links.block_lz(w['map'],f'1 1 {radius} {team}')


@step(r'a team 2 unit tests landing at that same hex')
def test_lz(w): u=unit(w); u.team=2; w['blocked']=links.blocked_lz(u,w['map'],1,1)


@step(r'blocked is (true|false)')
def lz_result(w,blocked): eq(w['blocked'],blocked=='true')


@step(r'a valid map starts without LINKED objects')
def no_links(w): eq(links.linked(w['map']),False)


@step(r'the linked command sequence is (.+)')
def linked(w,sequence):
    from systems.map_management import delobj
    for command in sequence.split(','):
        if command=='set': links.set_linked(w['map'])
        elif command=='delete-type': delobj(w['map'],'LINKED')
        elif command=='query': links.linked(w['map'])
        else: raise ValueError(command)


@step(r'the linked query is (true|false) and LINKED count is (\d+)')
def linked_result(w,result,count): eq(links.linked(w['map']),result=='true'); eq(len(w['map'].map_objects[7]),int(count))
