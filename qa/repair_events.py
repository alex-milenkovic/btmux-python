"""Procedure 8: packed jobs, exact conflicts and source callback mutations."""
from qa.repair_parts import *
def scheduled(kind=53,loc=4,pos=3,extra=0,actor_id=7,delay=60,**kw):return diag('schedule',type=kind,payload=actor_id*65536+loc+pos*16+extra*256,delay=delay,**kw)
def events():
    for i,(name,row) in enumerate(rows('events',1),1):
        u=unit();setslot(u,4,3,type=HEATSINK,firemode=1);d=doc(u,characters=[actor(),actor(7),actor(8)]);c=Case(name,d)
        if i==1:d['actions']=[diag('pack',actor=7,loc=4,pos=3,extra=2)];c.expect('results.0',459316)
        elif i<=10:
            kind=47 if i in (6,9,10) else 51 if i==7 else 52 if i==8 else 53;loc=12 if i in (9,10) else 4
            d['actions']=[scheduled(kind,loc,extra=2 if i in (2,3,7,8) else 0,actor_id=8 if i==4 else 7,fake=i==4)]
            if i in (5,6):d['actions'].append(scheduled(kind,loc,actor_id=8,fake=True))
            query=diag('repairing',loc=4,pos=4 if i==3 else 3) if i<=4 else diag('count',type=kind,loc=12 if i==10 else 4,**({'pos':3} if i==5 else {})) if i in (5,6,9,10) else diag('scrapping_part',loc=4,pos=3)
            d['actions'].append(query);c.expect(f'results.{len(d["actions"])-1}',False if i in (3,8,9) else 2 if i in (5,6) else True if i in (2,4,7) else 1)
            if i in (5,6):d['actions'].append(diag('repairing',loc=4,pos=3) if i==5 else diag('fixing',loc=4));c.expect(f'results.{len(d["actions"])-1}',True)
        else:
            d['actions']=[scheduled(fake=i==11),advance(59),inspect(),advance(1),inspect()]
            c.expect('results.2.repair_jobs',1,'length').expect(slotpath(pos=3,prefix='results.2')+'.firemode',1).expect(slotpath(pos=3)+'.firemode',1 if i==11 else 0).expect('state.repair_jobs',[])
        drawcheck(c,'tech_rolls',[]);yield c
    for i,(name,row) in enumerate(rows('events',2),1):
        u=unit();d=doc(u,characters=[actor(),actor(7)]);c=Case(name,d)
        if i<=8:
            gun(u,'IS.PPC' if i==6 else 'IS.SRM-6',brand=18,fire_mode=1 if i!=6 else 0)
            loc=4;pos=2;kind=44 if i in (1,3) else 52 if i==2 else 58 if i==6 else 51 if i in (7,8) else 53;extra=3 if i==1 else 2 if i in (7,8) else 0
            if i==4:setslot(u,4,2,firemode=1|0x200,brand=18,data=9)
            if i==5:u['weapons']=[];u['ammo']=[dict(weapon='IS.SRM-6',section=4,critical=2,rounds=8)];setslot(u,4,2,firemode=1)
            if i==6:setslot(u,4,3,firemode=8,weap_damage_flags=2);setslot(u,4,4,firemode=8,weap_damage_flags=4);pos=3
            if i in (7,8):
                u['weapons']=[];loc=0;pos=8;start=0 if i==7 else 3
                for j in range(8,12):setslot(u,0,j,weapon='CL.GaussRifle')
                for j in range(start,start+2):setslot(u,2,j,special='SPLIT_CRIT_LEFT',data=8)
            d['actions']=[inspect(),scheduled(kind,loc,pos,extra,delay=60),advance(59),inspect(),advance(1),inspect()]
            if i in (1,2,3):
                for j in (2,3):c.expect(slotpath(pos=j)+'.firemode',0).expect(slotpath(pos=j)+'.brand',3 if i==1 else 2)
            if i==4:c.expect(slotpath()+'.firemode',0).expect(slotpath()+'.data',0)
            if i==5:c.expect(slotpath()+'.data',0).expect(slotpath()+'.firemode',0)
            if i==6:c.expect(slotpath()+'.brand',2).expect(slotpath(pos=3)+'.weap_damage_flags',0).expect(slotpath(pos=4)+'.weap_damage_flags',4)
            if i in (7,8):
                for j in range(8,12):c.expect(slotpath(0,j)+'.firemode',1)
                for j in range(start,start+2):c.expect(slotpath(2,j)+'.firemode',1 if i==7 else 0)
            c.expect('state.repair_jobs',[]).expect('results.3.units.u.sections','results.0.units.u.sections','same_as')
        elif i in (9,10):
            for sec in u['sections']:sec.update(internal=1,armor=0)
            if i==10:u['sections'][3]['internal']=0
            d['actions']=[diag('intact_internal')];c.expect('results.0',i==9)
        elif i<=13:
            kind=48 if i==12 else 47;payload=4144 if i==13 else 4+(2 if i==12 else 3)*16;delay=540 if i==12 else 180
            d['actions']=[diag('schedule',type=kind,payload=7*65536+payload,delay=delay),diag('latest')];c.expect('results.1',{11:540,12:1080,13:46620}[i])
        elif i<=18:
            kind={14:57,15:53,16:53,17:50,18:47}[i];setslot(u,4,3,type=HEATSINK);d['actions']=[]
            if i==16:d['actions'].append(advance(100));d['repair_economy']['restart']=-50
            d['actions'] +=[scheduled(kind,fake=i!=14,delay=119),cmd('repairs')];index=len(d['actions'])-1
            c.expect(f'results.{index}.result.0.actor',7).expect(f'results.{index}.result.0.location','CT').expect(f'results.{index}.result.0.minutes',1)
            desc=f'results.{index}.result.0.description';c.expect(desc,'Replacing suit CT Reseal' if i==14 else 'Failed armor repair' if i==18 else 'Scrapping' if i==17 else 'Failure','contains')
            if i==17:c.expect(desc,'Failure','not_contains')
        else:
            d['actions']=[op('schedule',unit='u',callback='mech_move_event',delay=100),cmd('checkstatus')];c.expect('results.1.result.ready',True)
        yield c
