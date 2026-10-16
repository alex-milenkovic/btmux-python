"""Procedure 4: compatibility/commodity boundaries and normal ammo journeys."""
from qa.repair_parts import boundary,slotpath
from qa.repair_access_time import source,gun
from qa.repair_support import *

def bin(u,weapon='IS.SRM-6',rounds=8,mode=0):
    u['ammo']=[dict(weapon=weapon,section=4,critical=2,rounds=rounds)];setslot(u,4,2,ammomode=mode);return u

def ammo():
    # Explicit QA metadata supplies source type/special combinations, not outcomes.
    expected=[-1,0,-1,1,-1,2,-1,4,128,-1,256,-1,64,512,1024,2048,4096,8192,16384,32768,65536,262144,-1,131072,524288,2097152,1048576,4194304,-1,-1]
    for i,(name,row) in enumerate(rows('ammo',1),1):
        u=unit();special=0;wtype=1
        if i==1:special=16384
        if i==4:special=2
        if i==5:special=32
        if i in (7,14,15,16,17):special=512
        if i in (9,11,12,24,25,26,27,28,29):special=16+(32 if i==29 else 0)
        if 18<=i<=23:wtype=3;special=2048 if i!=23 else 0
        gun(u,'IS.SRM-6',0,0,metadata=dict(weapon_type=wtype,special=special))
        if i!=3:bin(u)
        else:gun(u,loc=4,pos=2,metadata=dict(weapon_type=wtype,special=special))
        yield Case(name,doc(u,actions=[diag('ammo_mode',loc=4,pos=2,argument=row['operation'].split()[-1])])).expect('results.0',expected[i-1]).expect('draws',[])
    weapons=['CL.StreakSRM-6','CL.StreakLRM-10','IS.ELRM-15','IS.LR_DFM-5','IS.SR_DFM-2','IS.LRM-15','IS.SRM-6','IS.MRM-20','IS.AC/10','CL.LB20-XAC','CL.LB10-XAC','CL.LB5-XAC','CL.LB2-XAC','IS.AC/10','IS.LightAC/5','IS.iNarcBeacon','IS.LRM-15','IS.LRM-15','IS.LRM-15',None]
    wanted=[518,598,599,596,597,516,517,560,None,515,514,513,512,592,659,568,519,553,516,401]
    modes={10:1,11:1,12:1,13:1,14:8192|65536,15:262144,16:512|1024,17:4|2,18:256,19:2097152}
    for i,(name,row) in enumerate(rows('ammo',2),1):
        u=unit();weapon=weapons[i-1]
        if weapon:bin(u,weapon,mode=modes.get(i,0))
        else:setslot(u,4,2,type=401)
        expected=wanted[i-1] if i!=9 else source(weapon)+192
        yield Case(name,doc(u,actions=[diag('ammo_type',loc=4,pos=2)])).expect('results.0',expected).expect('draws',[])
    for i,(name,row) in enumerate(rows('ammo',3),1):
        rounds=10 if i in (3,6,8) else 0 if i==9 else 2 if i==10 else 8
        u=bin(unit(),'IS.SRM-6',rounds,0x80000000 if i==10 else 0)
        gun(u,'IS.SRM-6',0,0,metadata={'ammo_per_ton':10})
        # Public catalog metadata selects ten rounds; Narc leaves that capacity intact.
        if i==10:u['in_character']=False
        d=doc(u,stock=stocks((517,0,1)) if i<=2 else '',actions=[cmd('reload' if i<=5 else 'unload' if i<=9 else 'toggletype','CT 3'+(' N' if i in (3,4,5,10) else ''))]);c=Case(name,d)
        if i==4:d['repair_economy']['objects'].append(dict(id=200,TECHTIME='36000'))
        if i==10:d['characters'][0]['tech']=False
        if i in (3,4,5,9):
            c.result(ok=False).expect('results.0.error',{3:'full',4:'tired',5:'stock',9:'empty'}[i],'contains').expect('state.repair_jobs',[])
            c.expect(slotpath()+'.data',0 if i in (4,5,9) else 10).expect(slotpath()+'.ammomode',4 if i in (4,5) else 0);drawcheck(c,'tech_rolls',[])
        elif i==10:c.result(ok=True).expect(slotpath()+'.data',10).expect(slotpath()+'.ammomode',0x80000000|4);drawcheck(c,'tech_rolls',[])
        else:
            fail=i in (2,8);d['random']['streams']['tech_rolls']=[2 if fail else 12]
            boundary(c,900 if fail else 600,before=rounds,after=8 if i==2 else 10 if i==1 else 0,field='data',fake=i==2)
            c.expect('results.1.economy.objects.1000.ECONPARTS','').expect('state.economy.objects.1000.ECONPARTS',stocks((517,0,1)) if i in (6,8) else '')
            drawcheck(c,'tech_rolls',[2 if fail else 12])
        yield c
