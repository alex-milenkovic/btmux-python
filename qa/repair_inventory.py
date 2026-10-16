"""Procedure 7: ordered source damage/scrap tables and real numbered dispatch."""
from qa.repair_parts import *
from qa.repair_events import scheduled

def damaged(u,loc):u['sections'][loc].update(armor=0,internal=0,config=2)
def clear_slots(u):
    for sec in u['sections']:
        sec['slots']=[dict(index=i,type=0) for i in range(12)]

def machine(c,index,rows):
    c.expect(f'results.{index}.machine',','.join(f'{n}|{loc}|{typ}|{data}|{busy}' for n,(loc,typ,data,busy) in enumerate(rows,1)))
    c.expect(f'results.{index}.machine',[[n,loc,typ,data,busy] for n,(loc,typ,data,busy) in enumerate(rows,1)],'machine_rows')
    c.expect(f'results.{index}.rows',len(rows),'length')
    for n,(loc,typ,data,busy) in enumerate(rows):c.expect(f'results.{index}.rows.{n}.type',typ).expect(f'results.{index}.rows.{n}.location',loc).expect(f'results.{index}.rows.{n}.in_progress',busy)

def inventory():
    for i,(name,row) in enumerate(rows('inventory',1),1):
        u=unit(kind='BSUIT' if i==7 else 'VEH_GROUND' if i==14 else 'MECH',profile='sparse');d=doc(u,actions=[cmd('damages')]);c=Case(name,d);expected=[]
        if i in (1,2):damaged(u,4);u['sections'][0]['armor']=8
        if i==1:d['actions']=[diag('damage_table')];c.expect('results.0',[[0,4,0]])
        elif i==2:expected=[('RA',15,'-',0),('LA',15,'-',0),('RL',15,'-',0),('LL',15,'-',0),('H',15,'-',0)]
        elif i==3:u['sections'][4]['config']=8;u['sections'][0]['armor']=8;expected=[('CT',19,'-',0)]
        elif i==4:damaged(u,2);u['sections'][0]['armor']=8;u['sections'][3]['armor']=8;expected=[('LT',0,'-',0),('RT',12,'2',0)]
        elif i in (5,6):u['sections'][4].update(internal=8 if i==5 else 10,armor=5,rear=3);expected=[('CT',14,'2',0)] if i==5 else [('CT',12,'5',0),('CT',13,'2',0)]
        elif i==7:
            damaged(u,3)
            for sec in u['sections'][4:]:sec.update(internal=0,internal_orig=0,armor=0,armor_orig=0)
            expected=[('S4',20,'-',0)]
        elif i==8:setslot(u,4,2,ammo='IS.AC/10',data=8,firemode=4);expected=[('CT',11,'Ammo_AC/10:2',0),('CT',1,'Ammo_AC/10',0)]
        elif i in (9,10):gun(u,'IS.PPC');setslot(u,4,2,firemode=8,weap_damage_flags=6 if i==9 else 12);expected=[('CT',4 if i==9 else 5,'PPC',0)]
        elif i in (11,12):gun(u,brand=16 if i==11 else 0,fire_mode=1 if i==12 else 0);expected=[('CT',2 if i==11 else 10,'SRM-6',0)]
        elif i in (13,14):c.expect('results.0.pristine',True).expect('state.technician.messages',dict(actor=200,text='Pristine mech!' if i==13 else 'Pristine unit!'),'has')
        elif i>=15:
            u['sections'][4]['armor']=8;setslot(u,4,0,type=394,firemode=1);setslot(u,4,1,type=HEATSINK,firemode=1)
            d['repair_economy']['objects'][0]['ECONPARTS']=stocks((ARMOR,0,2),(HEATSINK,0,1),*(([(ACTUATOR,0,1)] if i==18 else [])))
            d['actions']=[cmd('damages'),cmd('fix',{15:'3-2',16:'0-2',17:'1-4',18:'2',19:'1-3'}[i]),cmd('repairs')];expected=[('CT',12,'2',0),('CT',1,'ShoulderOrHip',0),('CT',1,'HeatSink',0)]
            if i in (16,17):c.result(1,ok=False).expect('results.1.error','low' if i==16 else 'high','contains')
            else:c.result(1,ok=True)
            c.expect('state.repair_jobs',0 if i<=17 else 1 if i==18 else 2,'length')
            if i==18:c.expect('results.1.rows',[dict(number=2,command='replacepart',error=None)]).expect('state.repair_jobs.0.position',0)
            if i==19:
                c.expect('results.1.rows.0',dict(number=1,command='fixarmor',error=None)).expect('results.1.rows.1.number',2).expect('results.1.rows.1.error','stock','contains').expect('results.1.rows.2',dict(number=3,command='replacepart',error=None)).expect('state.repair_jobs',dict(type=47,location=4,position=2),'has').expect('state.repair_jobs',dict(type=43,location=4,position=1),'has').expect('state.economy.objects.1000.ECONPARTS','')
            if i<=17:drawcheck(c,'tech_rolls',[])
        if i!=1:machine(c,0,expected)
        yield c
    for i,(name,row) in enumerate(rows('inventory',2),1):
        u=unit(profile='sparse');d=doc(u);c=Case(name,d);d['actions']=[];expected=[]
        if i<=5 or i==10:
            damaged(u,4)
            # Isolate RA while retaining the actual outside-in traversal.
            for loc in (0,2,5,6,7):damaged(u,loc)
            if i==1:setslot(u,1,4,type=HEATSINK);expected=[('RA',16,'HeatSink',0)]
            if i==2:setslot(u,3,4,type=HEATSINK);d['actions']=[scheduled(49,loc=1)];expected=[('RA',15,'-',1),('RT',16,'HeatSink',0)]
            if i==3:setslot(u,1,4,type=HEATSINK,firemode=4);expected=[('RA',15,'-',0)]
            if i in (4,5,10):
                setslot(u,1,4,ammo='IS.AC/10',data=8);expected=[('RA',18,'Ammo_AC/10:8',1 if i==5 else 0)]
                if i==5:d['actions']=[scheduled(46,loc=1,pos=4)];expected.append(('RA',15,'-',0))
        elif i in (6,7):
            u['sections'][4].update(armor=8,rear=3);d['actions']=[scheduled(47,loc=12 if i==7 else 4)];expected=[('CT',12,'2',0 if i==7 else 1),('CT',13,'2',1 if i==7 else 0)]
        elif i==8:setslot(u,4,2,type=HEATSINK,firemode=1);d['actions']=[scheduled(43,pos=2,fake=True)];expected=[('CT',1,'HeatSink',1)]
        elif i==9:setslot(u,4,2,ammo='IS.AC/10',data=8);expected=[('CT',11,'Ammo_AC/10:2',0)]
        else:
            first='IS.MediumLaser' if i==11 else 'CL.GaussRifle';second='CL.GaussRifle' if i==11 else 'IS.MediumLaser'
            gun(u,first,4,0,brand=16);gun(u,second,4,6,brand=16);expected=[('CT',2,first[3:],0),('CT',2,second[3:],0)]
        d['actions'].append(cmd('damages'));idx=len(d['actions'])-1;machine(c,idx,expected)
        if i in (6,7,8):
            for n,r in enumerate(expected):
                if r[3]:c.expect(f'results.{idx}.rows.{n}.minutes',None).expect(f'results.{idx}.rows.{n}.bth',None)
        if i>=11:c.expect(f'results.{idx}.rows.0.bth',7 if i==11 else 10).expect(f'results.{idx}.rows.1.bth',9 if i==11 else 7)
        yield c
    for n,(flag,label) in enumerate([(1,'Repairs on'),(2,'Realign focus'),(4,'Charging crystal'),(8,'Barrel'),(16,'Ammo feed'),(32,'Ranging'),(64,'Ammo feed')]):
        u=unit(profile='sparse');gun(u,'IS.PPC');setslot(u,4,2,firemode=8,weap_damage_flags=flag)
        c=Case(f'inventory/enhanced-{flag}',doc(u,actions=[cmd('damages')])).expect('results.0.rows.0.type',3+n).expect('results.0.rows.0.description',label,'contains');yield c
