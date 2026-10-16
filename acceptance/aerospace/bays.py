"""Dropship doors, command gates and real map/personnel transfers."""
import re
from . import step,eq,invoke,position,make_unit,events,messages,check,U,M,S,C
from core.events import EventType as E
from entities.map import GameMap
from entities.mech import FireMode as F
from systems import dropships as d


def setup(w):
    ship=w['u'];ship.unit_type=U.DS;ship.set_status(S.LANDED);w['ship']=ship
    for sec in ship.sections:
        for slot in sec.criticals:slot.type=0
    ship.sections[5].criticals[0].type=d.MECHDOOR
    maps=[]
    for i in range(4):
        board=GameMap(10,10);board._id=1001+i;board.name='bay'+str(i);board.in_character=True
        w['engine'].register_entity(board);w['personnel'].add(board,-1);maps.append(board)
    w['bays']=maps
    d.create_bays(ship,[board._id for board in maps])
    u=make_unit(w,'B');w['u']=u;position(u,10,9)
    return u,ship


@step(r'bay setup fixture (.+)')
def config_fixture(w,text):
    setup(w);w['fixture']=text
    if 'old-four' not in text:w['ship'].aero_bays=[-1]*4
    w['before']=list(w['ship'].aero_bays)
    if text.startswith('four'):w['args']=[1001,1002,1003,1004]
    elif text.startswith('no-arguments'):w['args']=[]
    elif text.startswith('one-valid'):w['args']=[1001]
    elif text.startswith('five'):w['args']=[1001]*5
    elif text.startswith('valid-map-then'):w['args']=[1002,999]
    else:w['args']=[w['u']._id]


@step(r'createbays executes')
def create(w):
    ship=w['ship'];r=d.create_bays(ship,w['args']);w['result']=r
    check(w,'four-bays',ship.aero_bays==[1001,1002,1003,1004]);check(w,'each-parent-set',all(b.onmap==ship._id for b in w['bays']))
    check(w,'all-slots-minus1',ship.aero_bays==[-1]*4);check(w,'old-map-parents-retained',all(b.onmap==ship._id for b in w['bays']))
    check(w,'first-assigned',ship.aero_bays[0]==1001);check(w,'trailing-minus1',ship.aero_bays[1:]==[-1]*3)
    check(w,'invalid-count',not r[0] and 'number of arguments' in r[1]);check(w,'unchanged',ship.aero_bays==w['before'])
    check(w,'first-assigned-and-parent-set',ship.aero_bays[0]==1002 and w['bays'][1].onmap==ship._id);check(w,'remaining-old-slots-retained',ship.aero_bays[1:]==w['before'][1:])
    check(w,'argument-not-map',not r[0] and 'not a map' in r[1])


@step(r'door fixture (.+)')
def doors_fixture(w,text):
    u,ship=setup(w);w['fixture']=text
    if 'AFT' in text:ship.sections[4].criticals[0].type=d.MECHDOOR
    if 'two-doors' in text:ship.sections[5].criticals[1].type=d.MECHDOOR
    if 'destroyed' in text:ship.sections[5].criticals[0].firemode|=F.DESTROYED_MODE
    if 'disabled' in text:ship.sections[5].criticals[0].firemode|=F.DISABLED_MODE
    if 'aerodoor' in text:ship.sections[5].criticals[0].type=d.AERODOOR
    if 'AERO' in text:u.unit_type=U.AERO;u.move_type=M.FLY
    if 'VTOL' in text:u.unit_type=U.VTOL;u.move_type=M.VTOL
    match=re.search(r'DS(\d+),(\d+);facing(\d+).*seer(\d+),(\d+)',text)
    if match:
        x,y,f,sx,sy=map(int,match.groups());position(ship,x,y);ship.facing=f;position(u,sx,sy)


@step(r'bay number direction adjacency and openness are queried')
def doors(w):
    u,ship=w['u'],w['ship']
    numbers=[d.bay_number(ship,i) for i in range(6)]
    check(w,'nose-bay0',numbers[0]==0 and d.bay_direction(ship,0)==0);check(w,'aft-bay1',numbers[3]==1 and d.bay_direction(ship,1)==3)
    check(w,'other-dirs-minus1',all(numbers[i]==-1 for i in (1,2,4,5)))
    opened=d.bay_open(u,ship,1001)
    check(w,'nose-bay0-closed',numbers[0]==0 and not opened);check(w,'aft-bay1-open',numbers[3]==1 and d.bay_open(u,ship,1002))
    check(w,'bay0-open',opened);check(w,'bay0-closed',not opened);check(w,'adjacent-bay0',d.adjacent_bay(u,ship)==0)


@step(r'entry fixture (.+)')
def entry_fixture(w,text):
    u,ship=setup(w);w['fixture']=text;w['argument']=''
    if 'no-matching' in text:position(u,2,2)
    if 'two-landed' in text:
        second=make_unit(w,'C',U.DS);second.set_status(S.LANDED);second.sections[5].criticals[0].type=d.MECHDOOR;second.aero_bays=[1001,-1,-1,-1]
    if 'two-arguments' in text:w['argument']='AA BB'
    if 'VTOL' in text:u.unit_type=U.VTOL;u.move_type=M.VTOL;u.fuel=0;w['engine'].nofusion_vtol_fuel=True
    if 'jumping' in text:u.set_status(S.JUMPING)
    if 'standing' in text:u._stand_event=w['engine'].schedule_event(100,E.STAND,lambda e:None,data=u)
    if 'OOD' in text:u.cocoon=1
    if text.startswith('DS'):
        u.unit_type=U.DS
        if 'no-carrier' not in text:u.specials2|=0x80000
        if 'matching-aerodoor' in text:ship.sections[5].criticals[0].type=d.AERODOOR
    if 'door-destroyed' in text:ship.sections[5].criticals[0].firemode|=F.DESTROYED_MODE
    for label,name in (('relative-speed','speed'),('relative-vertical','vertical_speed')):
        match=re.search(label+r'([\d.]+)',text)
        if match:setattr(u,name,float(match[1]))
    if 'different-Z' in text:u.z=1
    if 'legless' in text:
        for i in (5,6):u.sections[i].internal=u.sections[i].armor=0
    if 'lock-denied' in text:w['bays'][0].enter_lock='false';w['bays'][0].fail_message='Custom bay failure.'
    if 'pending-other' in text:
        other=make_unit(w,'C');w['engine'].schedule_event(12,E.ENTER_HANGAR,d.enter_event,data=other,data2=1002 if 'different-bay' in text else 1001)
    if 'explicit-target' in text:ship.clear_status(S.LANDED);w['argument']=ship.contact_id


def entry_checks(w,r):
    w['result']=r;ok,msg=r;u=w['u']
    fragments={'ambiguous':'Multiple enterable','no-bay':'No DS bay','invalid-count':'number of arguments','fuel-refusal':'lack fuel','mid-jump-refusal':'mid-jump','stand-first-refusal':'Stand first','mid-flight-refusal':'mid-flight','too-large':'too large','craft-cannot-enter':"can't enter bays",'door-jammed':'jammed','speed-difference-refusal':'Speed difference','vertical-difference-refusal':'Vertical speed','elevation-refusal':'same elevation','without-legs-refusal':'Without legs','custom-failure':'Custom bay failure','door-busy':'Someone else'}
    for label,text in fragments.items():check(w,label,not ok and text in msg)
    pending=events(w,E.ENTER_HANGAR)
    check(w,'entry-due12',ok and len(pending)==1 and pending[0].tick==12);check(w,'no-event',not pending)


@step(r'enterbay executes')
def entry(w):entry_checks(w,invoke(w,d.enter_bay,w['u'],w['argument']))


@step(r'a queued entry changes by (.+)')
def queued(w,text):
    u,ship=setup(w);w['fixture']=text
    if 'carried-unit' in text:u.carrying=make_unit(w,'C')._id
    if text.startswith('MW'):
        u.unit_type=U.MW;u.in_character=True;w['bays'][0].in_character=False
    if 'swarmer' in text:
        suit=make_unit(w,'C',U.BSUIT);suit.swarm_target=u;w['swarmer']=suit
    eq(invoke(w,d.enter_bay,u)[0],True)
    if 'shuts-down' in text:u.clear_status(S.STARTED)
    if 'unconscious' in text:u.set_status(S.UNCONSCIOUS)
    match=re.search(r'unit-speed([\d.]+);maximum(\d+)',text)
    if match:u.speed=float(match[1]);u.max_speed=float(match[2]);u.clear_crit_status(C.LOAD_OK|C.SPEED_OK)
    if 'door-destroyed' in text:ship.sections[5].criticals[0].firemode|=F.DESTROYED_MODE
    if 'lock-denied' in text:w['bays'][0].enter_lock='false'
    if 'other-bay-neighbor' in text:ship.sections[4].criticals[0].type=d.MECHDOOR;position(u,10,11)
    if 'moves-away' in text:position(u,2,2)


@step(r'the clock reaches 12 seconds')
def entered(w):
    invoke(w,w['engine'].run_ticks,12);u=w['u'];world=w['personnel']
    check(w,'no-transfer',u.map is w['map'])
    check(w,'transfer',u.map is w['bays'][0] and (u.x,u.y)==(5,5))
    check(w,'transfer-to-current-bay',u.map is w['bays'][1])
    carried=w['units'].get('C')
    check(w,'unit-and-cargo-in-bay-at5,5',u.map is w['bays'][0] and carried is not None and carried.map is u.map and (u.x,u.y,carried.x,carried.y)==(5,5,5,5))
    check(w,'locations-and-membership-updated',u.location==1001 and u in w['bays'][0].mechs_on_map and u not in w['map'].mechs_on_map and carried is not None and carried.location==1001)
    check(w,'contents-moved',u.pilot.location==1001 and u.pilot._id in world.contents(1001))
    check(w,'shell-disposal-due10',len(events(w,E.NUKEMECH))==1 and events(w,E.NUKEMECH)[0].tick==22)
    check(w,'swarmer-detached-before-transfer',w.get('swarmer') is not None and not w['swarmer'].swarm_target and w['swarmer'].map is w['map'])


@step(r'exit fixture (.+)')
def exit_fixture(w,text):
    from systems.map_transitions import transfer
    u,ship=setup(w);w['fixture']=text
    invoke(w,transfer,u,w['bays'][0]);w['personnel'].move(u._id,1001)
    position(u,0,5);u.fz=123;ship.z=2;ship.elev=2
    match=re.search(r'DS(\d+),(\d+);facing(\d+)',text)
    if match:x,y,face=map(int,match.groups());position(ship,x,y,2);ship.facing=face;ship.elev=2
    if 'airborne' in text:ship.clear_status(S.LANDED)
    if 'VTOL' in text:
        u.unit_type=U.VTOL;u.move_type=M.VTOL
        car=make_unit(w,'C');u.carrying=car._id;invoke(w,transfer,car,w['bays'][0]);w['personnel'].move(car._id,1001)
        from systems.movement_commands import maybe_move
        maybe_move(w['engine'],u)
    if 'door-destroyed' in text:ship.sections[5].criticals[0].firemode|=F.DESTROYED_MODE
    if 'parent-zombie' in text:ship.zombie=True
    if 'parent-missing' in text:w['bays'][0].onmap=999
    if 'pilot-outside' in text:u.in_character=True;w['personnel'].move(u.pilot._id,1001)
    if 'C3-network' in text:
        from systems import c3
        peer=make_unit(w,'C');invoke(w,transfer,peer,w['bays'][0]);w['peer']=peer
        from entities.mech import Specials
        u.specials|=Specials.C3_SLAVE_TECH;peer.specials|=Specials.C3_MASTER_TECH;peer.working_c3_masters=1
        c3.add(peer,u);c3.replicate(peer,u)
    u.x=-1


@step(r'the unit crosses the bay map edge')
def exit_run(w):
    from systems.map_transitions import check_edge_of_map
    u=w['u'];ship=w['ship'];invoke(w,check_edge_of_map,u);msg=messages(w)
    for x,y in ((10,9),(12,9),(0,0)):check(w,('placement-clamped' if (x,y)==(0,0) else 'parent-map')+f'{x},{y}',u.map is w['map'] and (u.x,u.y)==(x,y))
    check(w,'Z-and-elev-from-parent',(u.z,u.elev)==(ship.z,ship.elev));check(w,'ground-FZ-retained',u.fz==123)
    for label,fragment in {'ship-airborne-refusal':'still airborne','door-jammed':'jammed','imprudent-refusal':'prudent','invalid-parent-refusal':'No parent object'}.items():check(w,label,u.map is w['bays'][0] and fragment in msg)
    check(w,'flyer-Z-parent-plus1',u.z==ship.z+1);check(w,'cargo-Z-parent',w['units'].get('C') is not None and w['units']['C'].z==ship.z)
    check(w,'move-event-stopped',not events(w,E.MOVE));check(w,'transfer',u.map is w['map'] and u.location==1000)
    check(w,'intruder-alarm','INTRUDER ALERT' in msg);check(w,'real-shutdown',not u.is_started)
    check(w,'old-peers-detached',w.get('peer') is not None and u._id not in w['peer'].c3_network);check(w,'owner-network-cleared',getattr(u,'c3_network_size',0)==0)
