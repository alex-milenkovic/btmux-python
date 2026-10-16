"""Independent command and landing/charge boundary checks from mech.physical.c."""
from combat_support import *

_base_fixture=fixture
def fixture(periodic=True):
    d=_base_fixture(periodic)
    d['units'][1]['real']=[1024.0750399750987,677.25,0]
    return d

RESECT=(0,1,2,3,5,6)

def armtech(d,attack,loc=1,count=None):
    parts={'axe':('AXE',3),'claw':('CLAW',3),'saw':('DUAL_SAW',7),'sword':('SWORD',3),'mace':('MACE',5)}
    if attack in parts:
        part,n=parts[attack]
        for i in range(n if count is None else count):slot(d,loc,i+4,special=part)

def physical_cases():
    for attack in ('punch','axe','claw','saw','sword','mace'):
        for limb in ('','L','R','B'):
            d=fixture(False);armtech(d,attack,0);armtech(d,attack,1);d['random']['streams']['physical_attack']=[12,12];d['actions']=[cmd(attack,*([limb] if limb else []))]
            n=2 if limb in ('','B') and attack in ('punch','claw') else 1
            damage={'punch':5,'axe':10,'claw':7,'saw':7,'sword':6,'mace':12}[attack]*n
            def check(o,n=n,damage=damage):
                checks((o['results'][0]['accepted'],True),(loss(o),damage),(len(draws(o,'physical_attack')),n))
                eq(sum(s['recycle']==30 for s in state(o)['sections']),n)
            yield Case(d,check,label=f'physicals-command-{attack}-{limb or "default"}',mode='normal')
    for attack,needed in [('axe',3),('claw',3),('saw',7),('sword',3),('mace',5)]:
        for count in (needed-1,needed):
            d=fixture(False);armtech(d,attack,1,count);d['random']['streams']['physical_attack']=[12];d['actions']=[cmd(attack,'R')]
            yield Case(d,lambda o,count=count,needed=needed:checks((o['results'][0]['accepted'],count==needed),(len(draws(o,'physical_attack')),int(count==needed))),label=f'physicals-tech-count-{attack}-{count}',mode='normal')
    for cls in ('MECH','GROUND','BA','MW','AERO'):
        for quad in (False,True):
            d=fixture(False);d['units'][0].update(**{'class':cls},movement='QUAD' if quad else 'BIPED');d['random']['streams']['physical_attack']=[12,12];d['actions']=[cmd('punch')]
            yield Case(d,lambda o,cls=cls,quad=quad:eq(o['results'][0]['accepted'],cls=='MECH' and not quad),label=f'physicals-arm-class-{cls}-quad{quad}',mode='normal')
    for attack in ('punch','axe','sword','mace','saw','claw','kick','trip'):
        for guard in ('busy','jumping','stun','map-safe','personal-safe'):
            d=fixture(False);armtech(d,attack);d['random']['streams']['physical_attack']=[12]
            if guard=='busy':section(d,5,recycle=10)
            if guard=='jumping':d['units'][0]['status']=8|64
            if guard=='stun':d['units'][0]['crit_status']=1073741824
            if guard=='map-safe':d['map']['flags']=512
            if guard=='personal-safe':d['units'][1].update(**{'class':'MW'},real=[1024.0750399750987,935.25,0])
            d['actions']=[cmd(attack,'R')]
            yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),(draws(o,'physical_attack'),[]),(loss(o),0)),label=f'physicals-guard-{attack}-{guard}',mode='normal')
    for attack,weight,base in [('punch',10,5),('sword',10,7),('saw',7,7),('kick',5,11)]:
        for heat in (8,9):
            for advantage in (False,True):
                for broken in (0,1,2):
                    for glance in (False,True):
                        d=fixture(False);d['units'][0].update(tonnage=55,heat=heat,specials=1,melee_specialist=advantage)
                        for i in range(broken):slot(d,1,2-i,firemode=1)
                        damage=(base*(2 if heat==9 and attack!='saw' else 1)+advantage)
                        if attack in ('punch','kick'):damage//=2**broken
                        if glance:damage=(damage+1)//2
                        d['actions']=[diag('physical-damage',target='v',attack=attack,section='RA',weight=weight,glancing=glance)]
                        yield Case(d,lambda o,damage=damage:eq(loss(o),damage),label=f'physicals-damage-order-{attack}-{heat}-{advantage}-{broken}-{glance}')
    for attack in ('punch','axe','kick'):
        for elevation in (-1,0,1):
            for prone in (False,True):
                d=fixture(False);d['units'][1]['fallen']=prone;d['map']['hexes']=[dict(at=[3,3],terrain='CLEAR',elevation=max(elevation,0)),dict(at=[3,2],terrain='CLEAR',elevation=max(-elevation,0))]
                d['units'][0]['at'][2]=max(elevation,0);d['units'][1]['at'][2]=max(-elevation,0)
                d['random']['streams']['physical_location']=[1]*20
                family=('normal' if prone else 'punch' if elevation>0 else 'kick') if attack=='kick' else ('normal' if prone else 'kick') if elevation<0 else 'punch' if attack=='punch' or elevation>0 else 'normal'
                loc={'normal':4,'punch':0,'kick':6}[family]
                d['actions']=[diag('physical-damage',target='v',attack=attack)]
                yield Case(d,lambda o,loc=loc:checks((o['results'][0]['location_hit'],loc),(state(o,'v')['sections'][loc]['armor']<200,True)),label=f'physicals-elevation-table-{attack}-{elevation}-{prone}')
    for command in ('kick','trip'):
        for hit in (False,True):
            d=fixture(False);d['random']['streams'].update(physical_attack=[12 if hit else 2],pilot_rolls=[12]*100);d['actions']=[cmd(command,'R')]
            yield Case(d,lambda o,command=command,hit=hit:checks((loss(o),10 if command=='kick' and hit else 0),(len(draws(o,'pilot_rolls')),1 if command=='trip' and hit or command=='kick' else 0)),label=f'physicals-{command}-pilot-hit{hit}',mode='normal')

def dfa_cases():
    import combat_examples
    for loc in RESECT:
        d=fixture();d['units'][0].update(jump_mp=3,jump_speed=32.25,piloting=4);mount(d,loc=loc,index=4,crits=1)
        d['actions']=[cmd('jump'),advance(1),dict(op='section',value=dict(index=loc,slots=[dict(index=4,data=60)])),advance(20)]
        yield Case(d,lambda o:checks((draws(o,'dfa_rolls'),[]),(loss(o),0),(state(o)['dfa_target'],-1),(state(o)['status']&64,0),(events(o,kind='JUMP'),[])),label=f'dfa-real-landing-busy-section-{loc}',mode='normal')
    for loc in (0,1,5,6):
        d=fixture();d['units'][0].update(jump_mp=3,jump_speed=32.25,piloting=4);d['actions']=[cmd('jump'),advance(1),dict(op='section',value=dict(index=loc,recycle=60)),advance(20)]
        yield Case(d,lambda o:checks((draws(o,'dfa_rolls'),[]),(loss(o),0),(state(o)['status']&64,0)),label=f'dfa-real-landing-limb-{loc}',mode='normal')
    for cls,prone,facing in [('MECH',False,180),('MECH',True,180),('GROUND',False,180),('BA',False,180),('MECH',False,0)]:
        d=fixture(False);d['units'][0].update(status=8|64|256,tonnage=55,real_mass=60,piloting=0);d['units'][1].update(**{'class':cls},fallen=prone,facing=facing)
        d['random']['streams']['physical_location']=[1]*30;d['actions']=[diag('dfa',target='v',roll=12)]
        def check(o,cls=cls,prone=prone,facing=facing):
            checks((loss(o),19),(loss(o,'u'),11),(o['results'][0]['hit'],True),(state(o)['status']&(64|256),0))
            for loc in RESECT:eq(state(o)['sections'][loc]['recycle'],30)
            if cls=='MECH' and not prone:eq(state(o,'v')['sections'][0]['armor'],181)
            if cls=='MECH' and prone:eq(state(o,'v')['sections'][4]['armor'],181)
        yield Case(d,check,label=f'dfa-target-family-{cls}-prone{prone}-facing{facing}')
    for bth in (12,13):
        d=fixture(False);d['units'][0].update(status=8|64|256,piloting=bth-3);d['random']['streams']['dfa_rolls']=[12];d['actions']=[diag('dfa',target='v')]
        yield Case(d,lambda o,bth=bth:checks((o['results'][0]['bth'],bth),(draws(o,'dfa_rolls'),[12] if bth==12 else []),(loss(o),15 if bth==12 else 0)),label=f'dfa-BTH-boundary-{bth}')
    for fallen in (False,True):
        d=fixture(False);d['units'][0].update(status=8|64|256|(128 if fallen else 0),fallen=fallen,piloting=0);d['units'][1]['piloting']=0;d['random']['streams']['pilot_rolls']=[2,12,12,12]
        d['actions']=[diag('dfa',target='v',roll=12)]
        def check(o,fallen=fallen):
            eq(o['results'][0]['hit'],True)
            if fallen:eq(draws(o,'pilot_rolls'),[])
            else:assert len(draws(o,'pilot_rolls'))>=2;eq(state(o)['fallen'],True)
        yield Case(d,check,label=f'dfa-PSR-entry-prone-{fallen}')
    d=fixture();d['units'][0].update(jump_mp=3,jump_speed=32.25);d['actions']=[cmd('jump'),advance(1),dict(op='place',unit='v',at=[8,8,0]),advance(20)]
    yield Case(d,lambda o:checks((loss(o),0),(state(o)['status']&64,0),(state(o)['dfa_target'],-1)),label='dfa-inflight-target-moves',mode='normal')

def charge_cases():
    d=fixture(False);d['units'][0].update(charge_target='v',charge_timer=35,charge_distance=8);d['actions']=[cmd('charge','-')]
    yield Case(d,lambda o:checks((state(o)['charge_target'],-1),(state(o)['charge_timer'],0),(state(o)['charge_distance'],0.0)),label='charge-clear-all-fields',mode='normal')
    for condition in ('no-lock','bad-id','friendly','MW','BA','VTOL','dodging','sprinting','legless'):
        d=fixture(False)
        if condition=='no-lock':d['units'][0]['target']=-1
        if condition=='friendly':d['map']['flags']=256;d['units'][1]['team']=0
        if condition in ('MW','BA','VTOL'):d['units'][0]['class']=condition
        if condition in ('dodging','sprinting'):d['units'][0]['status2']=262144 if condition=='dodging' else 65536
        if condition=='legless':section(d,5,armor=0,internal=0)
        d['actions']=[cmd('charge',*(['ZZ'] if condition=='bad-id' else []))]
        yield Case(d,lambda o:eq(o['results'][0]['accepted'],False),label='charge-selection-guard-'+condition,mode='normal')
    for mutual in (False,True):
        for loc in range(8):
            d=fixture(False);d['units'][0].update(speed=10.75,piloting=0);d['units'][1].update(speed=10.75 if mutual else 0,piloting=0,charge_target='u' if mutual else -1)
            mount(d,loc=loc,index=4,crits=1);slot(d,loc,4,data=60);d['random']['streams']['charge_rolls']=[12,12];d['actions']=[diag('charge',target='v')]
            eligible=loc not in (RESECT if mutual else range(6))
            yield Case(d,lambda o,eligible=eligible,mutual=mutual:checks((o['results'][0]['attacker_charging'],eligible),(o['results'][0]['attacker_hit'],eligible),(len(draws(o,'charge_rolls')),2 if mutual else int(eligible))),label=f'charge-busy-scan-mutual{mutual}-section{loc}')
    for speed in (-10.75,0,10.749,10.75):
        d=fixture(False);d['units'][0]['speed']=speed;d['actions']=[diag('charge',target='v',roll=12)]
        yield Case(d,lambda o,speed=speed:checks((o['results'][0]['attacker_hit'],speed>=10.75),(loss(o),6 if speed>=10.75 else 0)),label=f'charge-signed-speed-{speed}')
    for new,tl3 in [(0,0),(1,0),(1,1)]:
        for facing in (0,180):
            d=fixture(False);d['config'].update(newcharge=new,tl3_charge=tl3);d['units'][0].update(speed=32.25,charge_distance=4,real_mass=60,tonnage=55,piloting=0);d['units'][1].update(speed=10.75,real_mass=75,tonnage=65,facing=facing,piloting=0)
            relative=(4 if new else 3)-(1 if facing==0 else -1);targetdamage=int(relative*65/10+1);selfdamage=int(relative*80/20) if new and tl3 else 8
            d['actions']=[diag('charge',target='v',roll=12)]
            yield Case(d,lambda o,targetdamage=targetdamage,selfdamage=selfdamage:checks((loss(o),targetdamage),(loss(o,'u'),selfdamage),(state(o)['speed'],0.0)),label=f'charge-formula-new{new}-tl{tl3}-facing{facing}')
    for hits in ((12,12),(12,2),(2,12),(2,2)):
        for eligible in ((True,True),(False,True),(True,False),(False,False)):
            d=fixture(False);d['units'][0].update(speed=10.75,charge_target='v');d['units'][1].update(speed=10.75,charge_target='u',real_mass=65,tonnage=65)
            for i,ok in enumerate(eligible):
                if not ok:section(d,0,unit=i,recycle=20)
            d['random']['streams']['charge_rolls']=list(hits);d['actions']=[diag('charge',target='v')]
            def check(o,hits=hits,eligible=eligible):
                hit1=eligible[0] and hits[0]==12;hit2=eligible[1] and hits[1]==12
                checks((o['results'][0]['attacker_hit'],hit1),(o['results'][0]['target_hit'],hit2),(len(draws(o,'charge_rolls')),2 if any(eligible) else 0),(state(o)['speed'],0.0 if hit1 else 10.75),(state(o,'v')['speed'],0.0 if hit2 else 10.75),(state(o,'v')['charge_target'],-1))
                eq(loss(o),11*hit1+7*hit2);eq(loss(o,'u'),7*hit1+7*hit2)
            yield Case(d,check,label=f'charge-mutual-outcomes-{hits[0]}-{hits[1]}-{eligible[0]}-{eligible[1]}')

def all_cases():
    yield from physical_cases()
    yield from dfa_cases()
    yield from charge_cases()
