"""Procedure 5: point callbacks, structural recovery, repairability/materials."""
from qa.repair_support import *
from qa.repair_parts import slotpath

def structure():
    for i,(name,row) in enumerate(rows('structure',1),1):
        u=unit();field='internal' if i in (2,7,9) else 'rear' if i==3 else 'armor';initial=4 if i==3 else 11 if i==4 else 5 if i in (5,6,7) else 9 if i in (8,9) else 7
        u['sections'][4][field]=initial
        if i==3:u['sections'][4]['rear_orig']=6
        if i==5:u['sections'][4]['internal']=9
        count=2 if i==3 else 5 if i in (5,6,7) else 1 if i in (8,9) else 3
        d=doc(u,stock=stocks((INTERNAL if field=='internal' else ARMOR,0,count)),actions=[cmd('fixinternal' if field=='internal' else 'fixarmor','CT r' if i==3 else 'CT')]);c=Case(name,d)
        if i in (4,5):
            c.result(ok=False).expect('results.0.error','No repair' if i==4 else 'internals','contains').expect('state.repair_jobs',[]).expect('state.economy.objects.1000.ECONPARTS',d['repair_economy']['objects'][0]['ECONPARTS']);drawcheck(c,'tech_rolls',[])
        else:
            failed=i>=6;rolls=[2,12] if i in (6,8) else [2,2] if failed else [12];d['random']['streams']['tech_rolls']=rolls
            d['random']['streams']['repair_percent']=[5 if i in (6,9) else 44]
            interval=540 if field=='internal' else 180;first={6:360,7:1080,8:1,9:1}.get(i,interval);points=1 if i in (8,9) else 2 if i in (3,6,7) else 3
            c.result(ok=True).expect('results.0.job.due',first).expect('results.0.job.location',12 if i==3 else 4).expect('results.0.job.payload',200*65536+(12 if i==3 else 4)+(0 if i in (8,9) else points)*16)
            d['actions'] +=[inspect()];c.expect('results.1.economy.objects.1000.ECONPARTS','')
            elapsed=0
            for j in range(points):
                duration=first if j==0 else interval
                if duration>1:
                    d['actions'] +=[advance(duration-1),inspect()];c.expect(f'results.{len(d["actions"])-1}.units.u.sections.4.{field}',initial+j)
                    duration=1
                d['actions'] +=[advance(duration),inspect()];c.expect(f'results.{len(d["actions"])-1}.units.u.sections.4.{field}',initial+j+1)
            c.expect('state.repair_jobs',[]).expect('state.units.u.sections.4.'+field,initial+points)
            if field=='rear':c.expect('state.units.u.sections.4.armor',10)
            if i in (8,9):c.expect('state.repair_messages',[])
            drawcheck(c,'tech_rolls',rolls);drawcheck(c,'repair_percent',[5 if i in (6,9) else 44] if failed else [])
            if failed:c.expect('state.technician.rolls.1.difficulty',1)
        yield c
    for i,(name,row) in enumerate(rows('structure',2),1):
        kind='BSUIT' if i in (9,10,11,12,14) else 'AERO' if i>=17 else 'MECH';u=unit(kind=kind);loc=3 if kind=='BSUIT' else 4 if i==3 else 0
        command='reseal' if i in (4,5,6,7,8) else 'replacesuit' if i in (9,10,11,12,13) else 'fixarmor' if i==18 else 'reattach'
        flooded=command=='reseal';u['sections'][loc].update(config=(8 if i!=5 else 0) if flooded else 0 if i>=17 else 2,internal=10 if flooded or i==18 else 0,armor=5 if i==18 else 10 if flooded else 0)
        setslot(u,loc,4,type=HEATSINK,firemode=2 if flooded else 1)
        if i==2:u['sections'][2].update(internal=0,armor=0,config=2)
        if kind=='BSUIT':
            u['repair']['max_suits']=4
            for j in range(4,8):u['sections'][j].update(internal=0,internal_orig=0)
            if i==10:
                for j in range(4):u['sections'][j].update(internal=0,armor=0,config=2)
        raw=stocks((INTERNAL,0,10),(600,0,2),(601,0,2),(602,0,9 if i==11 else 10)) if kind=='BSUIT' else stocks((ARMOR,0,5)) if i==18 else stocks((INTERNAL,0,10),(ELECTRIC,0,9 if i==6 else 10))
        d=doc(u,stock=raw,actions=[cmd(command,str(loc))]);c=Case(name,d)
        refuses={2:'adjacent',3:'unfixable',5:'not flooded',6:'stock',10:'No live',11:'stock',13:'Wrong unit',14:'Suits'}
        if i in refuses:
            c.result(ok=False).expect('results.0.error',refuses[i],'contains').expect('state.repair_jobs',[]).expect('state.economy.objects.1000.ECONPARTS',raw);drawcheck(c,'tech_rolls',[])
        else:
            failed=i in (7,8,12,15,16);fake=i in (8,12,16);rolls=[2,2 if fake else 12] if failed else [12]
            d['random']['streams']['tech_rolls']=rolls;d['random']['streams']['repair_percent']=[50]
            due=900 if i==18 else (5400 if failed else 3600) if flooded else (10800 if failed else 7200) if kind=='BSUIT' else 21600 if failed else 14400
            d['actions'] +=[inspect(),advance(due-1),inspect(),advance(1),inspect()]
            field='config' if flooded else 'armor' if i==18 else 'internal';before=8 if flooded else 5 if i==18 else 0;after=before if fake else 0 if flooded else 1 if i==17 else 10
            c.result(ok=True).expect('results.0.job.fake',fake).expect(f'results.1.units.u.sections.{loc}.{field}',before)
            # Point jobs have intermediate real callbacks; last point remains one short.
            c.expect(f'results.3.units.u.sections.{loc}.{field}',9 if i==18 else before).expect(f'state.units.u.sections.{loc}.{field}',after).expect('state.repair_jobs',[])
            endstock=stocks((ELECTRIC,0,5),(INTERNAL,0,5)) if i==8 else stocks((600,0,1),(601,0,1),(602,0,5),(INTERNAL,0,5)) if i==12 else ''
            c.expect('state.economy.objects.1000.ECONPARTS',endstock)
            if flooded and not fake:c.expect(slotpath(loc,4)+'.firemode',0)
            if i==17:c.expect('state.units.u.sections.0.armor',0)
            if i>=17:c.expect('state.units.u.si','results.1.units.u.si','same_as')
            drawcheck(c,'tech_rolls',rolls);drawcheck(c,'repair_percent',[50] if i in (8,12) else [])
        yield c
    for i,(name,row) in enumerate(rows('structure',3),1):
        u=unit();c=Case(name,doc(u));d=c.doc
        if i<=8:
            kind='VTOL' if i in (3,4) else 'VEH_GROUND' if i in (5,6) else 'AERO' if i==7 else 'MECH';u=unit(kind=kind);d['units']=[u]
            loc={1:4,2:0,3:5,4:0,5:4,6:0,7:3,8:4}[i];u['sections'][loc].update(internal=0,armor=0,config=2)
            if i==7:u['sections'][loc]['armor']=0
            if i==8:u['sections'][loc]['internal_orig']=0
            d['actions']=[diag('fixable'),cmd('damages'),cmd('reattach',str(loc))];d['repair_economy']['objects'][0]['ECONPARTS']=stocks((INTERNAL,0,10),(ELECTRIC,0,10))
            c.expect('results.0',i not in (1,4,6))
            if i in (1,4,6):c.result(2,ok=False).expect('results.2.error','unfixable','contains')
            else:c.result(2,ok=True)
        else:
            special={9:0x80000|0x20000000,13:0x100000|0x8000000,14:0x8000000|0x10000000,15:0x10000000,17:0x200000|0x400000,18:0x400000|0x2000000,19:0x2000000|0x4000000,20:0x4000000|0x1000000,21:0x1000000,22:8}.get(i,0)
            u['specials']=special
            if i==10:u['specials2']=3
            if i==11:u['specials2']=2|0x4000
            if i==12:u['infantry_specials']=8
            operation='proper_armor' if i<=12 else 'proper_internal' if i<=15 else 'alias_part'
            d['actions']=[diag(operation,**({'part':394 if i==16 else 403 if i==22 else 401} if i>=16 else {}))]
            expected={9:541,10:563,11:566,12:553,13:540,14:558,15:559,16:548,17:542,18:544,19:555,20:556,21:561,22:543}[i]
            c.expect('results.0',expected)
        yield c
