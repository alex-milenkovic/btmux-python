"""Tow commands against map contacts, movement state and personnel contents."""
import re
from types import SimpleNamespace
from . import check,invoke,U,M,S,F,Specials,Special,i2special
from .structure import destroy
from core.events import EventType as E
from entities.mech import Mech,CritStatus
from entities.map import ICE
from systems.occupants import pickup,Personnel
from systems.towing import attach_cables,detach_cables,dropoff


def fixture(w):
    u=w['u'];u.status|=S.STARTED;u.team=1;u.in_character=True
    for loc in (0,1):
        u.sections[loc].criticals[0].type=i2special(Special.SHOULDER_OR_HIP)
        u.sections[loc].criticals[3].type=i2special(Special.HAND_OR_FOOT_ACTUATOR)
    units=[u]
    for identity in (11,12):
        target=Mech.create_test_mech();target._id=identity;target._engine=w['engine'];target.contact_id=str(identity)
        target.set_hex_position(u.x,u.y);target.team=1;target.in_character=True;target.status&=~S.STARTED
        target.measured_mass=target.tonnage*1024;target.cargo_inventory=[]
        w['board'].add_mech(target);w['engine'].register_entity(target);units.append(target)
    return units


def contacts(w):
    from systems.sensors import update_los_info
    from systems.targeting import plos_event
    update_los_info(w['board']);w['u'].pnum_seen=2
    invoke(w,plos_event,SimpleNamespace(data=w['u'],data2=w['engine']))


def run(w,initial,operation):
    name=operation.split()[0]
    if name not in ('pickup','attachcables','detachcables','dropoff'):return False
    u,tower,load=fixture(w);actor=w['actor'];engine=w['engine'];board=w['board'];target=tower
    if name=='pickup':
        if 'enemy' in initial:target.team=0 if 'team0' in initial else 2
        if 'enemy started' in initial:target.status|=S.STARTED
        if 'quad tower' in initial:u.move_type=M.QUAD
        if 'left arm destroyed' in initial:destroy(u,0)
        if 'right broken' in initial:u.sections[1].criticals[0].firemode=F.BROKEN_MODE
        if 'no arm has both' in initial:u.sections[0].criticals[0].firemode=F.BROKEN_MODE;u.sections[1].criticals[3].firemode=F.BROKEN_MODE
        if initial.startswith('nonMech'):
            u.unit_type=U.VEH_GROUND
            if 'no SALVAGE' not in initial:u.specials|=Specials.SALVAGE_TECH
        match=re.search(r'speed([\d.]+)',initial)
        if match:u.speed=float(match[1])
        if 'vertical-1' in initial:u.vertical_speed=-1
        match=re.search(r'tower z(-?\d+)',initial)
        if match:u.z=int(match[1])
        if initial=='valid target hidden':target.crit_status|=CritStatus.HIDDEN
        if 'OOC not towable' in initial:target.in_character=False;target.towable=False
        if 'already carrying another' in initial:target.carrying=load._id;target.towed_unit=load;load.status|=S.TOWED
        if operation=='pickup MW':
            u.carrying=12;u.towed_unit=load;target.unit_type=U.MW
            personnel=Personnel(engine,w['characters'],used_store=901)
            personnel.add(u,1000);personnel.add(target,1000)
            w['characters'].create(8,'Stray',location=11);personnel.add(w['characters'].actor(8),11)
        contacts(w);result=invoke(w,pickup,u,actor,'11');w['result']=result;ok=result['ok'];err=result.get('error',result.get('message',''))
        for label,fragment in [('refuse intact enemy','enemy'),('refuse started enemy','enemy'),('refuse quad','four'),('refuse missing arm','arm'),('refuse functional actuator gate','functioning'),('refuse salvage equipment','salvage'),('refuse speed boundary','fast'),('refuse hidden','hid'),('refuse OOC',"can't tow")]:check(w,label,not ok and fragment in err.lower() and u.carrying<=0)
        check(w,'refuse height',not ok and ('above' in err or 'below' in err))
        relation=ok and u.carrying==target._id and u.towed_unit is target and target.has_status(S.TOWED)
        for label in ('accept equipment gate','accept speed boundary','accept upper height boundary','accept lower height boundary','no intact enemy refusal'):check(w,label,relation)
        check(w,'carrying relation TOWED fallen centered shutdown and mirrored position',relation and target.is_fallen and not target.is_started and not target.status&(S.TORSO_LEFT|S.TORSO_RIGHT) and (u.x,u.y,u.z,u.fx,u.fy,u.fz)==(target.x,target.y,target.z,target.fx,target.fy,target.fz))
        check(w,'prior load dropped through shared release then new tow attached',relation and target.carrying==-1 and not load.has_status(S.TOWED))
        check(w,'existing MW pickup branch before carrying rejection',ok and u.carrying==12 and w['characters'].actor(8).location==10 and not target.has_status(S.TOWED));return True
    if name=='attachcables':
        if 'enemy' in initial:load.team=2
        if 'enemy started' in initial:load.status|=S.STARTED
        if 'ground tower' in initial:tower.unit_type=U.VEH_GROUND;tower.specials|=Specials.SALVAGE_TECH
        if 'OOC towable tower' in initial:tower.in_character=False;tower.towable=True
        if 'speed0.01' in initial:tower.speed=.01
        if 'OOC towable load' in initial:load.in_character=False;load.towable=True
        if initial=='actor enemy to IC tower':tower.team=2
        if initial=='actor OOD':u.cocoon=1
        if 'different elevation' in initial:u.z=1
        if 'different real coordinates' in initial:load.fx+=.25;load.fy+=.5
        original=(load.fx,load.fy,load.fz);contacts(w)
        result=invoke(w,attach_cables,u,actor,'11 12');w['result']=result;ok=result['ok'];err=result.get('error',result.get('message',''))
        relation=ok and tower.carrying==12 and tower.towed_unit is load and load.has_status(S.TOWED)
        check(w,'attach permitted without intact enemy rejection',relation and not load.is_started)
        check(w,'attach permitted',relation)
        for label,fragment in [('refuse dedicated salvage tower','salvage'),('refuse tower not IC','ic'),('refuse exact stationary gate','moving'),('refuse started enemy','enemy'),('refuse tower team','team'),('refuse actor OOD','ood'),('refuse elevation','elevation')]:check(w,label,not ok and fragment in err.lower() and tower.carrying<=0)
        check(w,'tow attached without mirror-position branch',relation and (load.fx,load.fy,load.fz)==original and original!=(tower.fx,tower.fy,tower.fz));return True
    target=load if name=='detachcables' else tower
    tower=tower if name=='detachcables' else u
    tower.carrying=target._id;tower.towed_unit=target;target.status|=S.TOWED
    target.speed=target.desired_speed=2;target.z=3;target.fz=37
    if 'missing object' in initial:tower.carrying=999;tower.towed_unit=None
    if 'no unit' in initial:tower.carrying=-1;tower.towed_unit=None
    if 'nonpilot GOD' in initial:actor._id=1;u.status&=~S.STARTED
    if 'enemy actor' in initial:tower.team=2;tower.speed=5
    if 'elevated terrain' in initial:board.set_elevation(tower.x,tower.y,1);u.z=tower.z=1
    if 'z2 own floor0 tower floor1' in initial:
        target.x+=1;target.z=2;board.set_elevation(tower.x,tower.y,1)
    if 'on ICE' in initial:board.set_terrain(tower.x,tower.y,ICE);target.z=0
    if 'fallen shutdown' in initial:target.status|=S.FALLEN;target.status&=~S.STARTED
    contacts(w)
    result=invoke(w,detach_cables,u,actor,'11') if name=='detachcables' else invoke(w,dropoff,u,actor)
    w['result']=result;ok=result['ok'];err=result.get('error',result.get('message',''));events=engine.events.pending_events(E.FALL,target)
    clear=tower.carrying==-1 and tower.towed_unit is None
    check(w,'shared usual gate still applies',not ok and 'online' in err and not clear)
    check(w,'detach allowed without team or stationary gate',ok and clear and not target.has_status(S.TOWED) and target.speed==target.desired_speed==0)
    check(w,'relation cleared before missing-object return',not ok and clear)
    check(w,'load integer z set to tower floor no fall and FZ unchanged',ok and clear and target.z==1 and target.fz==37 and not events)
    check(w,'relation clear TOWED clear speeds0 FALL due3 payload-1',ok and clear and not target.has_status(S.TOWED) and target.speed==target.desired_speed==0 and len(events)==1 and (events[0].tick,events[0].data2)==(3,-1))
    check(w,'z1 and no fall event',ok and clear and target.z==1 and not events)
    check(w,'z0 and no fall event',ok and clear and target.z==0 and not events)
    check(w,'remains fallen shutdown after release',ok and clear and target.is_fallen and not target.is_started)
    check(w,'relation clear and no target mutation',not ok and clear and target.speed==2 and target.has_status(S.TOWED))
    check(w,'refusal no carrying unit',not ok and 'not carrying' in err)
    return True
