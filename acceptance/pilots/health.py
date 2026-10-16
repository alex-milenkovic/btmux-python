from . import step,base,eq,truth,draws,values
from core.game_loop import GameEngine
from core.events import EventType as E
from core.randomness import use_source
from systems.occupants import Personnel
from systems import piloting as p
from entities.mech import MechStatus as S

@step(r'an attached pilot with Build5 and ordinary simulation recovery events')
def fresh(w):
    base(w);values(w,Build=5);engine=GameEngine();w['engine']=engine;unit=w['unit'];unit._id=10;unit._engine=engine;unit.in_character=True
    world=Personnel(engine,w['store']);world.add(unit,1000);world.add(w['store'].actor(101),10);unit.pilot=w['store'].actor(101)

@step(r'bruise (\d+) and pain resistance (\d+)')
def bruise(w,n,pain):values(w,Bruise=int(n),Pain_Resistance=int(pain))

@step(r'IC consciousness target is read')
def conc(w):w['result']=p.mw_ic_bth(w['unit'])

@step(r'target is (\d+)')
def conc_result(w,n):eq(w['result'],int(n))

@step(r'bruise (\d+) lethal (\d+) and initial pilot hits0')
def injury(w,bruise,lethal):values(w,Bruise=int(bruise),Lethal=int(lethal));w['unit'].pilot_hits=0

@step(r'IC (head|lethal) damage (\d+) is applied with surviving consciousness rolls')
def hurt(w,kind,damage):
    w['calls']=[]
    def source(name,lo,hi,fallback):w['calls'].append(name);return hi
    with use_source(source):(p.head_hit_mw_damage if kind=='head' else p.mw_lethal_damage)(w['unit'],None,int(damage))

@step(r'stored bruise is (\d+) lethal is (\d+) hits are (\d+) and fatal is (True|False)')
def hurt_result(w,bruise,lethal,hits,fatal):
    s=w['store'].retrieve(101);eq((s.get('Bruise'),s.get('Lethal'),w['unit'].pilot_hits),tuple(map(int,(bruise,lethal,hits))))
    eq(w['unit'].is_destroyed,truth(fatal));eq(w['store'].actor(101).alive,not truth(fatal))
    if truth(fatal):eq(w['store'].actor(101).location,900);eq(w['calls'],[])

@step(r'pilot damage condition (.+)')
def condition(w,text):w['condition']=text

@step(r'damage or health synchronization occurs')
def synchronize(w):
    condition=w['condition'];unit=w['unit']
    if condition=='negative-unit-ID':
        unit._id=-1
        draws(w,[],p.head_hit_mw_damage,unit,None,1);draws(w,[],p.mw_lethal_damage,unit,None,1)
    elif condition.startswith('nonIC-'):
        unit.in_character=False;unit.pilot_hits=6 if condition=='nonIC-initial-hits6' else 5
        unit.speed=unit.desired_speed=10
        draws(w,[] if unit.pilot_hits==6 else [6,6],p.handle_mw_conc,unit)
    elif condition.startswith('fix-'):
        import re
        match=re.fullmatch(r'fix-build(\d+)-bruise(\d+)-lethal(\d+)',condition);assert match
        values(w,Build=int(match[1]),Bruise=int(match[2]),Lethal=int(match[3]));p.fix_pilotdamage(unit,unit.pilot)
    elif condition=='lethal-build0-damage1':values(w,Build=0);draws(w,[],p.mw_lethal_damage,unit,None,1)
    else:raise AssertionError(condition)

@step(r'result is (no-health-hits-or-dice|destroy-once-clear-pilot-stop|target10|hits2|bruise10-lethal9-fatal)')
def synchronized(w,result):
    u=w['unit'];s=w['store'].retrieve(101)
    if result=='no-health-hits-or-dice':eq((s.get('Bruise'),s.get('Lethal'),u.pilot_hits),(0,0,0));eq(w['calls'],[])
    elif result=='destroy-once-clear-pilot-stop':eq((u.is_destroyed,u.pilot,u.speed,u.desired_speed),(True,None,0,0))
    elif result=='target10':assert any('10' in message and 'Roll: 12' in message for message in u.movement_messages),u.movement_messages
    elif result=='hits2':eq(u.pilot_hits,2)
    else:eq((s.get('Bruise'),s.get('Lethal'),u.is_destroyed),(10,9,True))

@step(r'initial unconsciousness at time0 with recovery due30')
def unconscious(w):
    draws(w,[1,1],p.handle_mw_conc,w['unit']);eq([e.tick for e in w['engine'].events.pending_events()],[30])

@step(r'(nonfatal-injury-at10|failed-recovery-at30|explicit-prolong20-at10|successful-recovery-at30) occurs')
def subsequent(w,action):
    w['additional']=0
    if action.endswith('at10'):
        for _ in range(10):w['engine'].process_tick()
        if action.startswith('nonfatal'):draws(w,[],p.head_hit_mw_damage,w['unit'],None,1)
        else:draws(w,[],p.prolong_uncon,w['unit'],20)
    else:
        with use_source(lambda name,lo,hi,fallback:hi if action.startswith('successful') else lo):
            for _ in range(30):w['engine'].process_tick()

@step(r'next recovery is (\d+|none) and additional initial dice are 0')
def recovered(w,due):
    pending=[e.tick for e in w['engine'].events.pending_events() if e.event_type==E.RECOVERY]
    eq(pending,[] if due=='none' else [int(due)])
    if due=='none':assert not w['unit'].has_status(S.UNCONSCIOUS)
