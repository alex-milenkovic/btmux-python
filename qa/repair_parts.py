"""Procedure 3: actual part command debit, deadline and critical-slot repair."""
from qa.repair_access_time import source,gun
from qa.repair_support import *
def slotpath(loc=4,pos=2,prefix='state'):return f'{prefix}.units.u.sections.{loc}.slots.{pos}'
def boundary(c,due,loc=4,pos=2,before=1,after=0,field='firemode',fake=False):
    c.doc['actions'] += [inspect(),advance(due-1),inspect(),advance(1),inspect()]
    c.expect('results.0.job.due',due).expect('results.0.job.fake',fake)
    c.expect(slotpath(loc,pos,'results.1')+'.'+field,before).expect(slotpath(loc,pos,'results.3')+'.'+field,before).expect(slotpath(loc,pos)+'.'+field,after).expect('state.repair_jobs',[])
    return c

def parts():
    for i,(name,row) in enumerate(rows('parts',1),1):
        u=unit();isgun=5<=i<=12;part=source('IS.SRM-6') if isgun else HEATSINK;brand=2 if i in (8,9,10) else 0;stock=0 if i in (4,8) else 2
        if isgun:gun(u,fire_mode=0 if i==11 else 1,brand=1 if brand else 0)
        elif i==4:u['ammo']=[dict(weapon='IS.SRM-6',section=4,critical=2,rounds=8)];setslot(u,4,2,firemode=1)
        else:setslot(u,4,2,type=part,firemode=1)
        if i==13:u['sections'][4]['config']=8
        argument='CT 4' if i==12 else 'CT 3 Shannon.SRM-6' if brand else 'CT 3'
        d=doc(u,actions=[cmd('replacegun' if isgun else 'replacepart',argument)],stock=stocks((part,brand,stock)) if stock else '')
        rolls=[2,12] if i in (2,6) else [2,2] if i in (3,7) else [12];d['random']['streams']['tech_rolls']=rolls;c=Case(name,d)
        if i in (8,11,12,13):
            c.result(ok=False).expect('results.0.error',{8:'stock',11:'functional',12:'mount first',13:'flooded'}[i],'contains').expect('state.repair_jobs',[]).expect('state.economy.objects.1000.ECONPARTS',d['repair_economy']['objects'][0]['ECONPARTS']);drawcheck(c,'tech_rolls',[])
            if i==8:c.expect(slotpath()+'.brand',2)
        else:
            c.result(ok=True);fake=i in (2,3,6,7);due=(10800 if fake else 7200) if isgun else 4020 if fake else 2700
            boundary(c,due,after=1 if fake else 0,fake=fake)
            if isgun:c.expect(slotpath(pos=3)+'.firemode',1 if fake else 0)
            remaining=stock if i in (2,6) else max(0,stock-1)
            c.expect('state.economy.objects.1000.ECONPARTS',stocks((part,brand,remaining)) if remaining else '')
            if i in (9,10):c.expect(slotpath(prefix='results.1')+'.brand',1).expect(slotpath()+'.brand',2).expect(slotpath(pos=3)+'.brand',2)
            if i==4:c.expect(slotpath()+'.data',0)
            drawcheck(c,'tech_rolls',rolls)
        yield c
    for i,(name,row) in enumerate(rows('parts',2),1):
        u=unit();nonweapon=i in (9,10,11,13);width=4 if i==4 else 5 if i in (5,6,7) else 3 if i in (12,14) else 2
        weapon={2:'IS.SRM-6',3:'IS.PPC',4:'CL.LB5-XAC',5:'IS.LRM-20'}[width]
        if nonweapon:setslot(u,4,2,type=HEATSINK)
        else:gun(u,weapon)
        setslot(u,4,2,brand=16,firemode=0)
        if i==2:setslot(u,4,2,brand=0,firemode=4)
        if i==3:setslot(u,4,2,firemode=2)
        if i in (4,5,6,7,11):setslot(u,4,2,brand=0,firemode=1)
        if i==7:setslot(u,4,3,firemode=1)
        if i==12:
            setslot(u,4,3,firemode=8,weap_damage_flags=1);setslot(u,4,4,firemode=8,weap_damage_flags=2)
        if i==13:setslot(u,4,2,firemode=8,weap_damage_flags=1)
        amount=3 if i in (5,6,11) else 1;raw=stocks((ELECTRIC,0,amount),(INTERNAL,0,amount)) if i<=11 and i!=8 else stocks((ELECTRIC,0,1))
        command='repairpart' if i in (9,10,11) else 'fixenhcrit' if i>=12 else 'repairgun';pos=3 if i in (12,14) else 2
        d=doc(u,stock=raw,actions=[cmd(command,f'CT {pos+1}')]);c=Case(name,d)
        refusals={2:'temporary',3:'disabled',4:'gone for good',7:'gone for good',8:'stock',11:'destroyed',13:'no gun',14:'enhanced'}
        if i in refusals:
            c.result(ok=False).expect('results.0.error',refusals[i],'contains').expect('state.repair_jobs',[]).expect('state.economy.objects.1000.ECONPARTS',raw);drawcheck(c,'tech_rolls',[])
        else:
            fake=i in (6,10);rolls=[2] if fake else [12];d['random']['streams']['tech_rolls']=rolls
            due=1800 if i==6 else 1320 if i==10 else 900 if i in (9,12) else 1200
            field='weap_damage_flags' if i==12 else 'firemode' if i in (5,6) else 'brand'
            before=1 if i in (5,6,12) else 16;after=before if fake else 0
            boundary(c,due,pos=pos,before=before,after=after,field=field,fake=fake)
            c.expect('results.0.job.type',58 if i==12 else 53).expect('state.economy.objects.1000.ECONPARTS','')
            if i in (1,5):c.expect(slotpath(pos=3)+'.firemode',0).expect('state.units.u.weapons.0.usable',True)
            if i==6:c.expect(slotpath(pos=3,prefix='results.1')+'.firemode',1).expect(slotpath(pos=3)+'.firemode',1)
            if i==12:c.expect(slotpath()+'.brand',0).expect(slotpath(pos=4)+'.weap_damage_flags',2).expect(slotpath(pos=4)+'.firemode',8)
            drawcheck(c,'tech_rolls',rolls)
        yield c
