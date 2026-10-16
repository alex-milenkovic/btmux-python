"""Procedures 1–2: literal public-command/parser/time/roll boundaries."""
from qa.repair_support import *
import ast
# Source data only, never executing/importing the game: source IDs use weapons.h order.
WEAPON_ROWS=ast.literal_eval(next(n.value for n in ast.parse((ROOT/'entities/construction_weapon_data.py').read_text()).body if isinstance(n,ast.Assign) and n.targets[0].id=='WEAPON_ROWS'))
def source(name):return next(i+1 for i,r in enumerate(WEAPON_ROWS) if r[0]==name)
def gun(u,name='IS.SRM-6',loc=4,pos=2,**kw):u.setdefault('weapons',[]).append(dict(name=name,section=loc,critical=pos,**kw));return u

def access():
    for i,(name,row) in enumerate(rows('access',1),1):
        u=unit();a=actor();d=doc(u,stock=stocks((INTERNAL,0,20),(HEATSINK,0,2),(517,0,2)))
        u['sections'][4]['internal']=8
        setslot(u,4,type=HEATSINK,firemode=1)
        operation=row['operation'].split(' ',1);d['actions']=[cmd(operation[0],operation[1] if len(operation)>1 else ''),inspect()];ci=0
        if i in (7,8,11,12):
            # Public ammunition fixtures resolve catalog identity to a physical bin.
            u['sections'][4]['internal']=10;u['sections'][4]['slots']=[]
            u['ammo']=[dict(weapon='IS.SRM-6',section=4,critical=0,rounds=0)]
        if i==1:a.update(tech=False,wizard=True)
        if i==2:d['actions'].insert(0,op('schedule',unit='u',callback='mech_startup_event',delay=30,data=1));ci=1
        if i==3:u['started']=True
        if i in (4,5,6,7,8):u['repair']['stall']=False
        if i==5:
            u=unit(kind='DS');d['units']=[u];u['sections'][5]['internal']=8;u['aerospace']={'bays':[1001,-1,-1,-1]};d['repair_economy']['objects'].append(dict(id=1001,ECONPARTS=stocks((INTERNAL,0,20))))
        if i==6:a['wizard']=True;u['started']=True
        if i==8:d['repair_economy']['config']={'limitedrepairs':1}
        if i in (9,10,13,14):d['repair_economy']['objects'].append(dict(id=200,TECHTIME=str((599 if i==9 else 600)*60)))
        if i==10:a['wizard']=True
        if i==11:u['in_character']=True
        if i==12:a['tech']=False
        d['characters']=[a];c=Case(name,d)
        refusals={1:'clearance',2:'starting up',3:'started up',4:'repair stall',8:'repair stall',10:'too tired',11:'simpods'}
        if i in refusals:c.result(ci,ok=False).expect(f'results.{ci}.error',refusals[i],'contains').expect('state.repair_jobs',[]);drawcheck(c,'tech_rolls',[])
        elif i in (12,13,14):c.result(ci,ok=True);drawcheck(c,'tech_rolls',[])
        else:c.result(ci,ok=True).expect('state.repair_jobs',1,'length');drawcheck(c,'tech_rolls',[12])
        if i==14:c.result(ci,result=False).expect('state.units.u.external_effects',{'service':'intact unit template','applied':False},'has')
        if i==12:c.expect('state.units.u.sections.4.slots.0.data',15)
        if i in refusals and i!=14:c.expect('state.economy.objects.1000.ECONPARTS',d['repair_economy']['objects'][0]['ECONPARTS'])
        yield c
    values=[[0,4,0,0],[0,4,11,0],[-2,4,12,0],[-2,4,-1,0],[-1,0,0,0],[0,4,1,0],[0,12,0,0],[0,10,0,0],[0,4,1,'c'],[0,4,1,0],[0,4,4,0],[-2,4,5,0],[0,4,2,0],[0,4,2,0],False,True,[-4,4,12,0],[-2,4,2,0],[-3,4,2,0]]
    for i,(name,row) in enumerate(rows('access',2),1):
        u=unit(kind='AERO' if i in (11,12) else 'MECH');kind,arg=row['operation'].split(' ',1);kw={}
        if i>=13:gun(u)
        if i==13:setslot(u,4,2,firemode=1)
        if i==14:setslot(u,4,2,data=9)
        if i in (7,8):kw.update(position=False,rear=True)
        if i in (9,10):kw['extra']=True
        if i>=17:kw['brand']=True;arg=arg.replace('OtherPartBrand','HeatSink')
        action=diag(kind,loc=4,pos=3 if i==15 else 2) if kind=='validgun' else diag(kind,argument=arg,**kw)
        c=Case(name,doc(u,actions=[action])).expect('results.0',values[i-1]);yield c

def time_cases():
    for i,(name,row) in enumerate(rows('time',1),1):
        u=unit();d=doc(u);acts=[];c=Case(name,d)
        if i<=6:
            acts=[op('clock',name='skip_seconds',seconds=1000)]
            old={2:999,3:1059,4:1060,5:1059,6:900}.get(i)
            if old is not None:d['repair_economy']['objects'].append(dict(id=200,TECHTIME=str(old)))
            if i<=4:acts.append(cmd('techstatus'));c.result(1,pending=i in (3,4),minutes=1 if i==4 else 0)
            else:acts.append(diag('add_time',minutes=2));c.expect('results.1',179 if i==5 else 120).expect('state.economy.objects.200.TECHTIME','1179' if i==5 else '1120')
        elif i<=9:
            # Advance establishes event tick; restart offset independently sets elapsed wall.
            if i!=9:acts=[advance(100)]
            d['repair_economy']['restart']=-20 if i==7 else 10 if i==8 else -120
            acts.append(diag('lag',amount=100));c.result(len(acts)-1,lag={7:20,8:-10,9:0}[i],adjusted={7:120,8:90,9:100}[i])
        elif i in (10,11):
            setslot(u,4,type=HEATSINK,firemode=1 if i==10 else 0,brand=0 if i==10 else 16)
            d['repair_economy']['objects']=[dict(id=1000,ECONPARTS=stocks((HEATSINK,0,1),(ELECTRIC,0,1),(INTERNAL,0,1))),dict(id=200,TECHTIME='59')]
            acts=[cmd('replacepart' if i==10 else 'repairpart','CT 1')]
            c.result(ok=True).expect('results.0.job.due',2700 if i==10 else 959).expect('state.economy.objects.200.TECHTIME','2759' if i==10 else '959')
        else:
            d['repair_economy']['config']={'variabletechtime':1,'techtime_mod':10};acts=[diag('variable',minutes=60,margin={12:2,13:0,14:10}[i])]
            if i==14:c.result(ok=False).expect('results.0.error','divisor','contains')
            else:c.expect('results.0',50 if i==12 else 60)
        d['actions']=acts;yield c
    for i,(name,row) in enumerate(rows('time',2),1):
        d=doc();u=d['units'][0];a=d['characters'][0];c=Case(name,d)
        if i<=7:
            kind={2:'VEH_GROUND',3:'AERO',4:'VTOL',5:'BSUIT'}.get(i,'MECH');d['units']=[unit(kind=kind)];u=d['units'][0];u['in_character']=i not in (4,6,7)
            skill=8 if i in (1,2,6,7) else 7;diff={1:1,2:1,3:2,4:2,5:0,6:1,7:1}[i];total={1:9,2:8,3:10,4:10,5:7,6:9,7:5}[i]
            family='Technician-Mechanic' if i==2 else 'Technician-Aerospace' if i in (3,4) else 'Technician-Weapons' if i>=6 else 'Technician-Battlemech'
            a['values'][family]=8-skill
            if i==6:a['values']['Tech_Aptitude']=1;d['random']['streams']['tech_d6']=[1,4,5]
            else:d['random']['streams']['tech_rolls']=[total]
            d['actions']=[diag('roll',amount=diff,brand=i>=6),op('inspect')]
            c.expect('results.0',total-skill-diff).expect('state.technician.rolls.0',dict(actor=200,unit=10,weapons=i>=6,difficulty=diff,target=skill+diff,roll=total,margin=total-skill-diff))
            xp={1:2,3:2,5:1}.get(i)
            tag={'Technician-Battlemech':'TecBat','Technician-Mechanic':'TecMec','Technician-Aerospace':'TecAer','Technician-Weapons':'TecWea'}[family]
            if xp:c.expect('state.characters.200.categories.skills',f'{tag}:{8-skill},{xp+(1<<24 if i==3 else 0)},0/','contains')
            else:c.expect('state.characters.200.categories.skills',',','not_contains')
            drawcheck(c,'tech_d6' if i==6 else 'tech_rolls',[1,4,5] if i==6 else [total])
        else:
            large=i in (9,10);weapon='CL.GaussRifle' if large else 'IS.MediumLaser';loc=0 if i<=9 else 4
            d['units']=[unit(kind='AERO' if i<=9 else 'MECH')];u=d['units'][0]
            if i>=10:u['specials']=32
            gun(u,weapon,loc,0,fire_mode=1);d['repair_economy']['objects'][0]['ECONPARTS']=stocks((source(weapon),0,1))
            d['actions']=[cmd('replacegun','0')];c.result(ok=True).expect('state.technician.rolls.0.difficulty',3 if large else 1).expect('results.0.job.due',(180 if i==10 else 60)*60)
        yield c
