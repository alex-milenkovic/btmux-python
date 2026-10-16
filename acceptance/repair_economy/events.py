"""Real queue identity, callback execution, reporting and restart records."""
import json,re
from copy import deepcopy
from . import check,advance,gun,U,F,C,i2special,i2ammo,Special,get_weapon
from systems.technician import pack
from systems.repair_jobs import completely_intact_internal
from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke
from systems.combat_ammunition import full_ammo


def callback_fixture(w,kind,*,loc=4,pos=3):
    u=w['u'];slot=u.sections[loc].criticals[pos];slot.type=i2special(Special.CASE);slot.firemode=F.BROKEN_MODE
    payload=pack(7,loc,pos)
    if kind in (44,51,52):
        gun(w,2,loc,pos)
        for s in u.sections[loc].criticals[pos:pos+2]:s.firemode=F.BROKEN_MODE;set_part_temp_nuke(s,1)
        if kind==51:
            for s in u.sections[loc].criticals[pos:pos+2]:s.firemode=0
            payload=pack(7,loc,pos,2)
        elif kind==44:payload=pack(7,loc,pos,3)
    if kind==46:
        slot.type=i2ammo(get_weapon('IS.LRM-15').index);slot.firemode=0;slot.data=2
    if kind in (45,49,57):
        loc=0;pos=0;payload=pack(7,loc,pos,2 if kind==49 else 0)
        if kind!=49:u.sections[loc].armor=u.sections[loc].internal=0
        if kind==57:u.unit_type=U.BSUIT
    if kind in (47,48):
        field='armor' if kind==47 else 'internal';setattr(u.sections[loc],field,5);payload=7*65536+loc+32
    if kind==58:
        gun(w,2,loc,pos);slot.firemode=F.DAMAGED_MODE;slot.weap_damage_flags=2
    return loc,pos,payload


def callback_checks(w,kind,loc,pos):
    u=w['u'];slot=u.sections[loc].criticals[pos]
    check(w,'repairpart',not slot.firemode&F.BROKEN_MODE)
    check(w,'replacegun',all(not s.firemode&F.BROKEN_MODE and s.brand==3 for s in u.sections[loc].criticals[pos:pos+2]))
    check(w,'reattach',u.sections[loc].internal==10)
    check(w,'reload or unload by extra',slot.data==full_ammo(u,loc,pos) if kind==46 else False)
    check(w,'armor point and continuation',u.sections[loc].armor==6 and len(w['jobs'].events())==1)
    check(w,'internal point and continuation',u.sections[loc].internal==6 and len(w['jobs'].events())==1)
    check(w,'section removal',u.is_section_destroyed(loc))
    check(w,'part removal',bool(slot.firemode&F.DESTROYED_MODE))
    check(w,'gun removal',all(s.firemode&F.DESTROYED_MODE for s in u.sections[loc].criticals[pos:pos+2]))
    check(w,'whole gun repair',all(not s.firemode&F.BROKEN_MODE for s in u.sections[loc].criticals[pos:pos+2]))
    check(w,'replace suit',u.sections[loc].internal==10)
    check(w,'enhanced critical repair',not slot.firemode&F.DAMAGED_MODE and slot.weap_damage_flags==0)


def run(w,initial,operation):
    jobs=w['jobs'];u=w['u'];e=w['engine'];inv=w['inventory'];tech=w['tech']
    if operation=='pack repair payload':check(w,str(pack(7,4,3,2)),True);return True
    if operation.startswith(('conflict ','Someone')):
        kind=47 if initial.startswith(('armor','two armor')) else int(re.search(r'type(\d+)',initial)[1])
        loc=12 if 'loc12' in initial else 4;pos=3
        for _ in range(2 if initial.startswith('two ') else 1):jobs.schedule(kind,u,pack(7,loc,pos),60,fake='fake' in initial)
        coords=re.search(r'loc(\d+)(?: pos(\d+))?',operation);at=int(coords[1]);position=int(coords[2] or 3)
        if operation.startswith('SomeoneRepairing_s'):result=jobs.count(u,kind,at,position)
        elif operation.startswith('SomeoneFixingA'):result=jobs.count(u,47,at)
        elif operation.startswith('SomeoneScrappingPart'):result=jobs.scrapping_part(u,at,position)
        else:result=jobs.repairing(u,at,position)
        check(w,'count2',result==2);check(w,'true',bool(result));check(w,'false',not result);return True
    if initial in ('fake repair delay60','real repairpart delay60'):
        _,_,payload=callback_fixture(w,53);slot=u.sections[4].criticals[3]
        jobs.schedule(53,u,payload,60,fake=initial.startswith('fake'));before=slot.firemode
        advance(w,59);held=bool(jobs.events()) and slot.firemode==before
        advance(w,1)
        check(w,'present and unchanged then absent and unchanged',held and not jobs.events() and slot.firemode==before)
        check(w,'broken then repaired and event absent',held and not jobs.events() and not slot.firemode&F.BROKEN_MODE);return True
    if operation=='completely intact internal query':
        for sec in u.sections:sec.internal=1;sec.armor=0
        if initial.startswith('one '):u.sections[4].internal=0
        result=completely_intact_internal(u);check(w,'true',result);check(w,'false',not result);return True
    if operation=='latest tech event':
        internal=initial.startswith('internal');kind=48 if internal else 47
        payload=4144 if 'payload4144' in initial else 32 if internal else 48
        jobs.schedule(kind,u,7*65536+payload,540 if internal else 180)
        value=jobs.latest(u);check(w,str(value)+' seconds'+(' from unmasked payload estimate' if 'payload4144' in initial else ''),True);return True
    if operation.startswith('repairs report'):
        kind=int(re.search(r'type(\d+)',initial)[1]);gun(w,2,4,3)
        jobs.schedule(kind,u,pack(7,4,3),119,fake=initial.startswith('fake'))
        e.events.set_tick(100);e.sim_now=150 if 'lag50' in operation else 100
        # Keep remaining119 independently of the inspection clock.
        jobs.events()[0].tick=219
        row=jobs.report(u)[0];text=row['description'];w['result']=row
        check(w,'suit description followed by reseal description','Replacing suit' in text and text.index('Replacing suit')<text.index('Reseal'))
        check(w,'actor location Failure and 1 minute',row['actor']==7 and row['location']=='CT' and 'Failure' in text and row['minutes']==1)
        check(w,'time1 minute from truncation before lag',row['minutes']==1)
        check(w,'scrapping description without Failure suffix','Scrapping' in text and 'Failure' not in text)
        check(w,'Failed armor repair label',text=='Failed armor repair');return True
    if operation=='checkstatus':
        from core.events import EventType as E
        e.schedule_event(100,E.MOVE,lambda event:None,u)
        check(w,'ready',w['work'].command(w['actor'],u,'checkstatus')['ready']);return True
    if operation=='execute callback':
        if initial.startswith(('replacegun','repairgun')):
            kind=44 if initial.startswith('replacegun') else 52
            loc,pos,payload=callback_fixture(w,kind);slots=u.sections[loc].criticals[pos:pos+2]
            brand=0 if 'requestedbrand0' in initial else 3 if kind==44 else 0
            for s in slots:s.brand=2
            jobs.schedule(kind,u,pack(7,loc,pos,brand),1);advance(w,1)
            restored=all(not s.firemode&(F.BROKEN_MODE|F.DESTROYED_MODE) and not part_temp_nuke(s) for s in slots)
            check(w,'both repaired tempnuke0 brand3',restored and all(s.brand==3 for s in slots))
            check(w,'both repaired tempnuke0 brand2',restored and all(s.brand==2 for s in slots))
            check(w,'repaired but brand2 retained',restored and all(s.brand==2 for s in slots));return True
        if initial.startswith('repairpart selected'):
            loc,pos,payload=callback_fixture(w,53);slot=u.sections[loc].criticals[pos]
            if 'ammo' in initial:slot.type=i2ammo(get_weapon('IS.LRM-15').index);slot.data=8
            else:gun(w,1,loc,pos);slot.firemode|=F.OS_USED
            slot.firemode|=F.DESTROYED_MODE;jobs.schedule(53,u,payload,1);advance(w,1)
            check(w,'repaired and oneshot expenditure cleared',not slot.firemode&(F.DESTROYED_MODE|F.OS_USED))
            check(w,'repaired ammo count0',not slot.firemode&F.DESTROYED_MODE and slot.data==0);return True
        if initial.startswith('repairenhcrit'):
            gun(w,3,4,0);slots=u.sections[4].criticals[:3]
            for s in slots:s.firemode|=F.DAMAGED_MODE;s.weap_damage_flags=2
            set_part_temp_nuke(slots[0],1);jobs.schedule(58,u,pack(7,4,1),1);advance(w,1)
            check(w,'middle clear first tempnuke0 last still damaged',not slots[1].firemode&F.DAMAGED_MODE and part_temp_nuke(slots[0])==0 and bool(slots[2].firemode&F.DAMAGED_MODE));return True
        if initial.startswith('removegun split'):
            start=int(re.search(r'start(\d+)',initial)[1]);gun(w,4,0,10)
            marker=u.sections[2].criticals[start];marker.type=i2special(Special.SPLIT_CRIT_LEFT);marker.data=10
            jobs.schedule(51,u,pack(7,0,10,0),1);advance(w,1)
            check(w,'second slots0 and1 destroyed',all(s.firemode&F.DESTROYED_MODE for s in u.sections[2].criticals[:2]))
            check(w,'second run untouched by source upper-bound quirk',not marker.firemode&F.DESTROYED_MODE);return True
    if operation.startswith('save') and ('repairpart' in initial or initial=='no tech events'):
        if initial!='no tech events':
            due=int(re.search(r'due(\d+)',initial)[1]);jobs.schedule(53,u,pack(7,4,3),due,fake=initial.startswith('fake'));e.events.set_tick(20)
        records=[json.loads(line) for line in jobs.save().splitlines()];w['result']=records
        check(w,'terminator only and no movement records',records==[[-1]])
        if len(records)>1:
            check(w,'remaining100 positive actor and payload preserved',records[0]==[10,53,100,pack(7,4,3)])
            check(w,'remaining-100 and fake marker preserved',records[0]==[10,53,-100,pack(7,4,3)])
            check(w,'remaining1',records[0][2]==1)
        return True
    if operation.startswith('load'):
        if initial.startswith('source type'):
            kind=int(re.search(r'type(\d+)',initial)[1]);loc,pos,payload=callback_fixture(w,kind);before=deepcopy(u.sections);messages=len(jobs.messages)
            jobs.load(json.dumps([10,kind,1,payload])+'\n[-1]');advance(w,1);callback_checks(w,kind,loc,pos)
            check(w,'inert bomb mount',u.sections==before and len(jobs.messages)==messages)
            check(w,'inert bomb unmount',u.sections==before and len(jobs.messages)==messages);return True
        if 'reseal type56' in initial:
            jobs.load(json.dumps([10,56,-100 if initial.startswith('fake') else 100,pack(7,4)])+'\n[-1]')
            check(w,'no reseal event scheduled',not jobs.events());check(w,'fake event scheduled at100',len(jobs.events())==1 and jobs.events()[0].tick==100 and jobs.events()[0].repair_fake);return True
        if 'repairgun' in initial:
            loc,pos,payload=callback_fixture(w,52);kind=53 if 'type53' in initial else 52
            jobs.schedule(kind,u,payload,1,callback='repairgun');text=jobs.save()
            for event in jobs.events():event.cancel()
            jobs.load(text);advance(w,1);slots=u.sections[loc].criticals[pos:pos+2]
            check(w,'selected part repaired without whole-gun callback',not slots[0].firemode&F.BROKEN_MODE and bool(slots[1].firemode&F.BROKEN_MODE))
            check(w,'whole gun repaired',all(not s.firemode&F.BROKEN_MODE for s in slots));return True
        loc,pos,payload=callback_fixture(w,53);slot=u.sections[loc].criticals[pos]
        if initial.startswith(('real repairpart','fake repairpart')):
            fake=initial.startswith('fake');e.events.set_tick(500);before=len(inv.writes)
            jobs.load(json.dumps([10,53,-100 if fake else 100,payload])+'\n[-1]')
            advance(w,99);held=bool(slot.firemode&F.BROKEN_MODE);advance(w,1)
            check(w,'unchanged then repaired at600',held and not slot.firemode&F.BROKEN_MODE and e.tick==600)
            check(w,'no repair resources or XP and event consumed',held and bool(slot.firemode&F.BROKEN_MODE) and not jobs.events() and len(inv.writes)==before and not getattr(u,'xp_requests',[]));return True
        if initial.startswith('unknown real'):
            result=jobs.load('[10,99,100,0]\n[-1]');check(w,'record skipped',result['skipped']==1 and not jobs.events());return True
        if initial.startswith('packed payload'):
            result=jobs.load('[10,53,100,2147483648]\n[-1]');check(w,'explicit range error and no fabricated event','range' in result['error'] and not jobs.events());return True
        if initial.startswith('one valid'):
            second='[10,53' if 'truncated' in initial else '[999,53,100,0]'
            result=jobs.load(json.dumps([10,53,100,payload])+'\n'+second+'\n[-1]')
            check(w,'first retained then bounded end',result['loaded']==1 and bool(result['error']))
            check(w,'first retained and bounded invalid-reference diagnostic',result['loaded']==1 and 'reference' in (result['error'] or ''));return True
    return False
