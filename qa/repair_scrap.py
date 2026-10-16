"""Procedure 6: source salvage commands, legacy helpers and inert callbacks."""
from qa.repair_parts import *
def scrap():
    for i,(name,row) in enumerate(rows('scrap',1),1):
        u=unit();d=doc(u,actions=[]);c=Case(name,d);loc=0 if 8<=i<=12 else 4;part=source('IS.SRM-6') if i<=3 or i==7 else 407 if i==6 else HEATSINK
        if i<=3 or i==7:gun(u)
        else:setslot(u,loc,2,type=part)
        if i<=7:
            d['actions']=[cmd('removegun' if i<=3 else 'removepart','CT 3')]
            if i in (6,7):c.result(ok=False).expect('results.0.error','Structural' if i==6 else 'weapon','contains').expect('state.repair_jobs',[]);drawcheck(c,'tech_rolls',[])
            else:
                fake=i in (3,5);rolls=[2,2] if fake else [2,12] if i in (2,4) else [12];d['random']['streams']['tech_rolls']=rolls
                boundary(c,4800 if i<=3 else 3600 if i==5 else 2400,before=0,after=0 if fake else 1,fake=fake)
                c.expect('results.3.economy.objects.1000.ECONPARTS','').expect('state.economy.objects.1000.ECONPARTS','' if fake else stocks((part,0,1)));drawcheck(c,'tech_rolls',rolls)
        elif i<=12:
            d['actions']=[cmd('removesection','LT' if i==8 else 'CT' if i==9 else 'LA')]
            if i in (8,9):
                if i==9:
                    for j in (2,3):u['sections'][j].update(internal=0,armor=0,config=2)
                c.result(ok=False).expect('results.0.error','outer','contains').expect('state.repair_jobs',[]);drawcheck(c,'tech_rolls',[])
            else:
                u['sections'][0].update(internal=10,armor=20,rear=8,rear_orig=8);fail=i==11;due=10800 if fail else 7200
                d['random']['streams']['tech_rolls']=[2 if fail else 12]
                if i==12:d['actions'].append(section(0,internal=6,armor=8))
                d['actions'] +=[inspect(),advance(due-1),inspect(),advance(1)]
                c.result(ok=True).expect('results.0.job.due',due).expect('state.units.u.sections.0.internal',0).expect(f'results.{len(d["actions"])-2}.economy.objects.1000.ECONPARTS','')
                quantities=(6,8,3) if i==12 else (6,13,3) if fail else (10,20,5)
                c.expect('state.economy.objects.1000.ECONPARTS',stocks(*[(p,0,v) for p,v in zip((INTERNAL,ARMOR,ELECTRIC),quantities)]))
        else:
            event=53 if i==13 else 52 if i==14 else 43 if i==15 else 46
            d['actions']=[diag('schedule',type=event,payload=200*65536+4+2*16,delay=60),cmd('removepart','CT 3') if i==13 else diag('can_scrap_location',loc=4)]
            if i==13:c.result(1,ok=False).expect('results.1.error','repairing','contains')
            else:c.expect('results.1',i==14)
        yield c
    for i,(name,row) in enumerate(rows('scrap',2),1):
        u=unit();d=doc(u);c=Case(name,d);weapon='IS.LRM-20' if i==3 else 'CL.LB5-XAC' if i==4 else 'IS.SRM-6';gun(u,weapon);setslot(u,4,2,firemode=1 if i in (3,4) else 8 if i==5 else 0,weap_damage_flags=1 if i==5 else 0)
        if i==6:u['weapons']=[];u['sections'][4]['slots']=[];u['ammo']=[dict(weapon='IS.SRM-6',section=4,critical=2,rounds=8)]
        rolls=[12] if i in (1,8) else [2] if i in (7,9,10) else []
        d['random']['streams']['tech_rolls']=rolls;d['random']['streams']['repair_percent']=[5 if i==10 else 50]
        d['actions']=[inspect(),diag('failure',helper=row['operation'],loc=4,pos=2),inspect()]
        c.expect('results.1',0 if i==8 else -1).expect('state.repair_jobs',[])
        raw=stocks((source(weapon),0,1)) if i==1 else stocks((ELECTRIC,0,5),(INTERNAL,0,5)) if i in (7,9) else stocks((600,0,1),(INTERNAL,0,1)) if i==10 else ''
        c.expect('state.economy.objects.1000.ECONPARTS',raw);drawcheck(c,'tech_rolls',rolls);drawcheck(c,'repair_percent',[5 if i==10 else 50] if i in (7,9,10) else [])
        if i==3:c.expect(slotpath(pos=3)+'.firemode',1)
        elif i==4:c.expect(slotpath(pos=3)+'.firemode',0)
        else:c.expect('state.units.u.sections','results.0.units.u.sections','same_as')
        yield c
    for i,(name,row) in enumerate(rows('scrap',3),1):
        u=unit();u['sections'][4]['armor']=7;setslot(u,4,2,type=HEATSINK,firemode=1);d=doc(u,stock=stocks((HEATSINK,0,2)));c=Case(name,d)
        if i<=11:
            d['actions']=[inspect(),diag('success',helper=row['operation']),inspect()];c.expect('results.1',0).expect('state','results.0','same_as')
        else:
            u['class']='AERO';u['movement']='FLY';setslot(u,7,11,type=385,firemode=1);d['repair_economy']['objects'].append(dict(id=10,ECONPARTS=stocks((385,0,2))))
            d['actions']=[inspect(),diag('schedule',type=54 if i==12 else 55,payload=200*65536+7+11*16,delay=1),advance(1),inspect()]
            for key in ('units','economy','inboxes','repair_messages','technician','cargo_messages'):c.expect('state.'+key,'results.0.'+key,'same_as')
            c.expect('state.repair_jobs',[])
        drawcheck(c,'tech_rolls',[]);yield c
