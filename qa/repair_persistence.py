"""Procedure 9: independently constructed records and separate-process journeys."""
from qa.repair_events import *
from qa.repair_inventory import damaged

CALLBACK={43:'repairpart',44:'replacegun',45:'reattach',46:'reload',47:'armor',48:'internal',49:'removesection',50:'removepart',51:'removegun',52:'repairgun',53:'repairpart',54:'mountbomb',55:'unmountbomb',57:'replacesuit',58:'repairenhcrit'}
def record(kind,remaining=100,loc=4,pos=3,extra=0,ident=10,payload=None):return json.dumps([ident,kind,remaining,7*65536+loc+pos*16+extra*256 if payload is None else payload])+'\n'
def mapping_fixture(kind):
    u=unit(profile='sparse');loc=4;pos=3;extra=0
    if kind in (44,51,52):gun(u,loc=loc,pos=pos,fire_mode=0 if kind==51 else 1,brand=18)
    elif kind==58:gun(u,'IS.PPC',loc=loc,pos=2,brand=16);setslot(u,loc,pos,firemode=8,weap_damage_flags=2)
    elif kind==46:setslot(u,loc,pos,ammo='IS.SRM-6',data=8)
    elif kind in (45,49,57):
        loc=0;pos=0
        if kind==57:u=unit(kind='BSUIT',profile='sparse');u['repair']['max_suits']=4
        if kind in (45,57):damaged(u,loc)
        else:extra=2
    elif kind in (47,48):pos=2;u['sections'][4]['armor' if kind==47 else 'internal']=7
    elif kind in (54,55):setslot(u,loc,pos,type=385)
    else:setslot(u,loc,pos,type=HEATSINK,firemode=0 if kind==50 else 1,brand=16);extra=2 if kind==50 else 0
    return u,loc,pos,extra

def persistence():
    for i,(name,row) in enumerate(rows('persistence',1),1):
        u=unit();setslot(u,4,3,type=HEATSINK,firemode=1);d=doc(u,characters=[actor(),actor(7)]);c=Case(name,d)
        if i<=5:
            due=20 if i==3 else 10 if i==4 else 120
            d['actions']=([scheduled(delay=due,fake=i==2)] if i!=5 else [op('schedule',unit='u',callback='mech_move_event',delay=100)])+[diag('queue_tick',amount=20),repair('save')]
            want=[[-1]] if i==5 else [[10,53,-100 if i==2 else 1 if i in (3,4) else 100,7*65536+4+3*16],[-1]]
            c.expect('results.2.text',want,'json_lines')
        else:
            text=record(56 if i in (8,9) else 52 if i==11 else 99 if i==12 else 53,remaining=-100 if i in (7,9) else 100)
            if i in (10,11):gun(u,loc=4,pos=3,brand=16,fire_mode=1);u['sections'][4]['slots']=[]
            if i==13:text+= '[10, 53,'
            if i==14:text+=record(53,ident=99999)
            if i==15:text=record(53,payload=2**31)
            if i not in (13,):text+='[-1]\n'
            d['actions']=([advance(500)] if i in (6,7) else [])+[repair('load',text=text),inspect()];load_index=1 if i in (6,7) else 0
            c.expect(f'results.{load_index}.loaded',0 if i in (8,12,15) else 1).expect(f'results.{load_index}.skipped',1 if i in (8,12) else 0)
            if i>=13:c.expect(f'results.{load_index}.error','' if i==13 else 'reference' if i==14 else 'range','contains')
            else:c.expect(f'results.{load_index}.error',None)
            if i in (6,7,10,11):
                d['actions'] +=[advance(99),inspect(),advance(1),inspect()]
                c.expect(f'results.{len(d["actions"])-3}.units.u.sections.4.slots.3.firemode',1).expect(slotpath(pos=3)+'.firemode',1 if i==7 else 0).expect('state.repair_jobs',[])
                if i in (10,11):c.expect(slotpath(pos=4)+'.firemode',1 if i==10 else 0)
                if i in (6,7):c.expect('state.time',600)
                c.expect('state.economy.objects.1000.ECONPARTS','');drawcheck(c,'tech_rolls',[])
            if i==9:c.expect('state.repair_jobs.0.fake',True).expect('state.repair_jobs.0.due',100)
        yield c
    for name,row in rows('persistence',2):
        kind=int(re.search(r'type(\d+)',row['initial'])[1]);u,loc,pos,extra=mapping_fixture(kind)
        d=doc(u,characters=[actor(),actor(7)],actions=[repair('load',text=record(kind,loc=loc,pos=pos,extra=extra)+'[-1]\n'),inspect(),advance(99),inspect(),advance(1),inspect()]);c=Case(name,d)
        c.result(loaded=1,skipped=0,error=None).expect('results.1.repair_jobs.0.callback',CALLBACK[kind]).expect('results.3.units.u.sections','results.1.units.u.sections','same_as')
        if kind in (43,44,52,53):c.expect(slotpath(loc,pos)+'.firemode',0).expect(slotpath(loc,pos)+'.brand',2 if kind in (44,52) else 0)
        if kind in (44,52):c.expect(slotpath(loc,pos+1)+'.firemode',0)
        if kind in (45,57):c.expect(f'state.units.u.sections.{loc}.internal',10)
        if kind==46:c.expect(slotpath(loc,pos)+'.data',15)
        if kind in (47,48):
            field='armor' if kind==47 else 'internal';c.expect(f'state.units.u.sections.{loc}.{field}',8).expect('state.repair_jobs.0.due',280 if kind==47 else 640)
        elif kind==49:c.expect('state.units.u.sections.0.internal',0).expect('state.economy.objects.1000.ECONPARTS',stocks((INTERNAL,0,10),(ARMOR,0,10),(ELECTRIC,0,5)))
        elif kind in (50,51):c.expect(slotpath(loc,pos)+'.firemode',1)
        elif kind in (54,55):
            for key in ('economy','repair_messages','inboxes'):c.expect('state.'+key,'results.1.'+key,'same_as')
            for key in ('sections','status','speed','desired_speed','carried_cargo','aerospace'):c.expect('state.units.u.'+key,'results.1.units.u.'+key,'same_as')
        elif kind==58:c.expect(slotpath(loc,pos)+'.weap_damage_flags',0).expect(slotpath(loc,2)+'.brand',0)
        if kind not in (47,48):c.expect('state.repair_jobs',[])
        drawcheck(c,'tech_rolls',[]);yield c

class Journey:
    def __init__(self,name,mode):self.name,self.mode=name,mode
    def run(self):
        armor=self.mode=='armor';u=unit();u['in_character']=True;u['sections'][4]['armor']=7 if armor else 10
        if not armor:setslot(u,4,3,type=HEATSINK,firemode=1)
        d=doc(u,stock=stocks((ARMOR,0,3)) if armor else stocks((HEATSINK,0,2)),actions=[cmd('fixarmor' if armor else 'replacepart','CT' if armor else 'CT 4')]);d['random']['streams']['tech_rolls']=[12] if armor else [2,12]
        if armor:d['actions'].append(advance(180))
        d['actions'] +=[repair('save',file='journey.jsonl'),inspect()]
        first=Case(self.name+'/before',d).result(ok=True);first.expect('state.economy.objects.1000.ECONPARTS','' if armor else stocks((HEATSINK,0,2)))
        result=first.run();phases=[result]
        if result['passed']:
            output=json.loads((OUTPUT/first.name/'stdout.json').read_text());state=output['state'];records=[json.loads(l) for l in (OUTPUT/first.name/'economy/journey.jsonl').read_text().splitlines()]
            expected=[[10,47,180,200*65536+4+2*16],[-1]] if armor else [[10,43,-4020,200*65536+4+3*16],[-1]]
            phases.append(dict(case=self.name+'/disk-records',passed=records==expected,assertions=[dict(actual=records,expected=expected,passed=records==expected)],failures=[] if records==expected else ['Wrong saved record']))
            restored=deepcopy(u)
            restored['sections']=[dict(index=i,**{k:v for k,v in sec.items() if k!='slots'},slots=[dict(index=j,**{k:v for k,v in slot.items() if k!='temp_failure'}) for j,slot in enumerate(sec['slots'])]) for i,sec in enumerate(state['units']['u']['sections'])]
            remaining=180 if armor else 4020
            later=doc(restored,characters=[],actions=[advance(500),repair('load',file='journey.jsonl'),inspect(),advance(remaining-1),inspect(),advance(1),inspect()]);later['repair_economy']['objects']=[]
            if armor:later['actions'] +=[advance(180),inspect()]
            second=Case(self.name+'/after',later);second.storage_origin=first.name
            second.result(1,loaded=1,skipped=0,error=None).expect('state.economy.objects.1000.ECONPARTS',state['economy']['objects']['1000']['ECONPARTS']).expect('state.economy.objects.200.TECHTIME',state['economy']['objects']['200']['TECHTIME']).expect('state.characters.200.categories',state['characters']['200']['categories']).expect('state.repair_jobs',[])
            if armor:second.expect('results.4.units.u.sections.4.armor',8).expect('results.6.units.u.sections.4.armor',9).expect('state.units.u.sections.4.armor',10)
            else:second.expect('results.4.repair_jobs.0.fake',True).expect(slotpath(pos=3)+'.firemode',1)
            drawcheck(second,'tech_rolls',[]);phases.append(second.run())
        summary=dict(case=self.name,passed=all(p['passed'] for p in phases),assertions=[a for p in phases for a in p['assertions']],failures=[f for p in phases for f in p['failures']],phases=phases)
        folder=OUTPUT/self.name;folder.mkdir(parents=True,exist_ok=True);(folder/'assertions.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
