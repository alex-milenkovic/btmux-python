from types import SimpleNamespace
from . import step,base,eq,truth
from .personnel import fresh_personnel,make
from core.randomness import use_source
from core.events import EventType as E
from entities.mech import Mech,UnitType as U,MoveType as M,MechStatus as S,MechStatus2 as S2,CritStatus as C,SectionConfig,FireMode as F,Specials,Location as L
from entities.pilot import Pilot
from entities.map import ROUGH,BUILDING
from entities.weapon import get_weapon
from systems import swarm as b


def fresh_ba(w):
    fresh_personnel(w);w['family']='battle_armor';u,t=w['unit'],w['carrier'];w['host']=t
    u.unit_type=U.BSUIT;u.infantry_specials=7;u.pilot=Pilot(piloting=0);w['actor']=u.pilot
    t.team=2;t.specials2=0
    count(w,4)

def count(w,n):
    for i,s in enumerate(w['unit'].sections):s.internal=s.internal_orig=30 if i<int(n) else 0;s.armor=30 if i<int(n) else 0

def source_high(name,lo,hi,fallback):return hi

def invoke(w,fn,*args,source=source_high,**kwargs):
    w['calls']=[]
    def draw(name,lo,hi,fallback):w['calls'].append(name);return source(name,lo,hi,fallback)
    with use_source(draw):return fn(*args,**kwargs)

@step(r'eight-section battle armor using shared source piloting damage and map membership')
def fresh(w):fresh_ba(w)
@step(r'ordinary battle armor controls on a source map with normal clock and LOS consumers')
def fresh_hide(w):fresh_ba(w);w['family']='hiding';w['board'].set_terrain(3,3,ROUGH);w['unit'].terrain=ROUGH;w['host'].status&=~S.STARTED

@step(r'source state (\S+)')
def helper(w,state):
    w['state']=state;u,t=w['unit'],w['host']
    if state.startswith('only-section7'):count(w,0);u.sections[7].internal=1
    elif state=='section0-internal1-destroyedflag':count(w,0);u.sections[0].internal=1;u.sections[0].config|=SectionConfig.SECTION_DESTROYED
    elif state=='no-map':t.map=None
    elif state in ('enemy-then-friendly-attached','friendly-only-attached','zero-ID-entry'):
        u.swarm_target=t._id
        if state=='friendly-only-attached':u.team=t.team
        elif state=='zero-ID-entry':u._id=0
        else:
            second=make(w,30);second.unit_type=U.BSUIT;second.team=t.team;second.swarm_target=t._id
    elif state=='Clan':u.specials|=Specials.CLAN_TECH
    elif state=='IS':u.specials&=~Specials.CLAN_TECH
    elif state=='host-XY3,4-Z2-elev1':t.set_hex_position(3,4);t.z=2;t.elev=1
    else:raise AssertionError(state)
@step(r'members or swarm map queries execute')
def helper_run(w):
    u,t=w['unit'],w['host'];state=w['state']
    if 'internal1' in state:w['result']=b.members(u)
    elif state in ('Clan','IS'):w['result']=(b.suit_name(u),b.suit_name(u,True))
    elif state.startswith('host-'):b.mirror(t,u);w['result']=(u.x,u.y,u.z,u.elev)
    else:w['result']=(int(b.is_swarmed(t)),int(b.is_mounted(t)),b.count_swarmers(t),b.first_swarmer(t))

@step(r'member count (\d+) team (friendly|enemy) attacker hidden (True|False) target (\S+)')
def swarm_mod(w,n,team,hidden,target):count(w,n);w['unit'].team=w['host'].team if team=='friendly' else w['host'].team+1;mod_state(w,hidden,target)
@step(r'member count (\d+) hidden (True|False) target (\S+)')
def leg_mod(w,n,hidden,target):count(w,n);mod_state(w,hidden,target)
def mod_state(w,hidden,target):
    if truth(hidden):w['unit'].crit_status|=C.HIDDEN
    if 'fallen' in target:w['host'].status|=S.FALLEN
    if 'immobile' in target:w['host'].status&=~S.STARTED
    if target=='fallen':
        from systems.combat import is_target_immobile
        eq(w['host'].unit_type,U.MECH);eq(w['host'].speed,0)
        eq(w['host'].is_started,True);eq(is_target_immobile(w['host']),False)
@step(r'the swarm attempt computes its modifier')
def swarm_mod_run(w):w['result']=b.modifier(w['unit'],w['host'])
@step(r'attackleg computes its modifier')
def leg_mod_run(w):w['result']=b.modifier(w['unit'],w['host'],True)
@step(r'modifier is (-?\d+)')
def mod_result(w,n):eq(w['result'],int(n))

@step(r'requested action (swarm|leg) with source condition (\S+)')
def guard(w,action,condition):
    w['action']=action;w['condition']=condition;u,t=w['unit'],w['host'];w['argument']=t
    if condition.startswith('range'):
        from physics.hexmath import SCALEMAP
        t.fx=u.fx+float(condition[5:])*SCALEMAP;t.fy=u.fy
    elif condition=='stale-default':u.target=999;w['argument']=''
    elif condition=='two-arguments':w['argument']='AA BB'
    elif condition=='friendly-no-mount-tech':t.team=u.team;u.infantry_specials&=~2
    elif condition in ('enemy-pending-jettison','friendly-pending-jettison-mount-tech'):
        u.infantry_specials|=0x100;u.sections[0].criticals[0].firemode|=F.WILL_JETTISON_MODE
        if condition.startswith('friendly'):t.team=u.team
    elif condition.startswith('swarmers-on-'):
        rider=make(w,30);rider.unit_type=U.BSUIT;rider.swarm_target=u._id if condition=='swarmers-on-attacker' else t._id
    elif condition=='busy-functional-weapon-on-live-section7':
        u.sections[7].internal=1;slot=u.sections[7].criticals[0];slot.type=get_weapon('PC.SMG').index+1;slot.firemode=0;slot.data=1;u.sections[7].recycle=0
    elif condition=='section7-recycle-live':u.sections[7].internal=1;u.sections[7].recycle=1
    elif condition=='attacker-legless':
        u.unit_type=U.MECH;u.sections[L.LLEG].internal=u.sections[L.RLEG].internal=0;u.sections[L.LLEG].armor=u.sections[L.RLEG].armor=0
    elif condition=='friendly':t.team=u.team
    elif condition=='quad-no-live-legs':
        t.move_type=M.QUAD
        for i in (L.LARM,L.RARM,L.LLEG,L.RLEG):t.sections[i].internal=0
        u.sections[L.LLEG].internal=1
    else:raise AssertionError(condition)
@step(r'the ordinary command runs')
def guard_run(w):
    try:w['result']=invoke(w,b.swarm if w['action']=='swarm' else b.attackleg,w['unit'],w['actor'],w['argument'])
    except ValueError as error:w['result']={'ok':False,'error':str(error)}

@step(r'a successful leg attack with selected live leg and source critical Roll (\d+)')
def leg_critical(w,n):w['critical']=int(n);w['unit'].sections[L.LLEG].internal=30
@step(r'the action resolves')
def leg_resolve(w):
    def source(name,lo,hi,fallback):return w['critical'] if name=='leg_critical' else 2 if name in ('critical_rolls','damage_entry') else hi
    w['before_internal']=[s.internal for s in w['host'].sections]
    w['result']=invoke(w,b.attackleg,w['unit'],w['actor'],w['host'],source=source)
@step(r'effect is (\S+) and attack recycle is 30')
def leg_effect(w,effect):
    r=w['result'];eq(r['ok'],True);eq(r['success'],True);eq(r['effect'],effect)
    eq([s.recycle for s in w['unit'].sections if s.internal],[30]*b.members(w['unit']))
    if effect.startswith('destroy-leg'):eq(w['host'].sections[r['location']].internal,0)
    if effect.startswith('damage4'):eq(w['host'].damage_taken,4)

@step(r'action outcome (\S+)')
def outcome(w,kind):
    w['outcome']=kind;u,t=w['unit'],w['host'];u.speed=u.desired_speed=2
    if kind.startswith(('stop-','host-')):u.swarm_target=t._id;t.swarmer=u._id;u.status2|=S2.UNIT_MOUNTING;t.status2|=S2.UNIT_MOUNTED
    if kind.endswith('-hidden'):u.crit_status|=C.HIDDEN
    if 'failure' in kind or 'fail-draw' in kind:u.pilot.piloting=30
    if kind=='stop-unresolved-target':u.swarm_target=999
    if kind=='stop-PSR4-fail-draw7':u.sections[7].internal=u.sections[7].internal_orig=30;u.sections[7].armor=0
    if kind.startswith('leg'):u.sections[L.LLEG].internal=30
    if kind in ('swarm-success-hidden','swarm-attempt-unhidden-pendinghide'):w['engine'].schedule_event(10,E.HIDE,b.hide_event,data=u,data2=0)
    if kind=='swarm-success-hidden':w['engine'].schedule_event(10,E.LOCK,lambda e:None,data=u)
@step(r'source post-action effects complete')
def effects(w):
    u,t=w['unit'],w['host'];kind=w['outcome']
    def source(name,lo,hi,fallback):return 7 if name=='suit_fall_location' else 2 if name=='critical_rolls' else hi
    if kind.startswith('swarm-'):w['result']=invoke(w,b.swarm,u,w['actor'],t,source=source)
    elif kind.startswith('leg-'):w['result']=invoke(w,b.attackleg,u,w['actor'],t,source=source)
    elif kind=='host-destroyed':
        from systems.damage import destroy_mech
        invoke(w,destroy_mech,t,None,source=source)
    elif kind=='host-shutdown':
        from systems.startup import shutdown_state
        invoke(w,shutdown_state,w['engine'],t,source=source)
    else:invoke(w,b.detach,u,kind=='stop-intentional',source=source)

@step(r'hiding unit class (MW|BA|VTOL|MECH) camouflage (True|False) with no detecting enemy and elevation0')
def hide_type(w,kind,camo):
    u=w['unit'];u.unit_type={'MW':U.MW,'BA':U.BSUIT,'VTOL':U.VTOL,'MECH':U.MECH}[kind]
    if truth(camo):u.specials2|=0x40000
    if kind=='VTOL':u.move_type=M.VTOL;u.status|=S.LANDED
@step(r'the accepted hide request advances through one-second callbacks')
def hide_run(w):
    u=w['unit'];w['result']=b.hide(u,w['actor']);eq(w['result']['ok'],True);w['hidden_time']=None
    for n in range(1,102):
        invoke(w,w['engine'].process_tick)
        if u.has_crit_status(C.HIDDEN):w['hidden_time']=n;break
@step(r'HIDDEN first becomes true at (\d+) seconds')
def hidden_time(w,n):eq(w['hidden_time'],int(n))

@step(r'hide condition (\S+)')
def hide_condition(w,condition):
    w['condition']=condition;u,t=w['unit'],w['host']
    if condition.startswith('MW'):u.unit_type=U.MW
    if condition=='MW-speed-MP1':u.speed=10.75
    elif condition=='MW-speed-over-MP1':u.speed=10.76
    elif condition.endswith('-building'):w['board'].set_terrain(3,3,BUILDING);u.terrain=BUILDING
    elif condition.startswith('BA-swarmtarget'):u.swarm_target=int(condition[-1])
    elif condition=='VTOL-airborne-camo':u.unit_type=U.VTOL;u.move_type=M.VTOL;u.specials2|=0x40000
    elif condition=='pending-hide':b.hide(u,w['actor'])
    elif condition.startswith('enemy-'):
        t.status|=S.STARTED
        if condition=='enemy-clairvoyant-only':t.crit_status|=C.CLAIRVOYANT
        if condition=='enemy-shutdown-only':t.status&=~S.STARTED
    elif condition in ('BA-rough','elevation1-at-callback','ordinary-movement-crosses-hex','ordinary-damage-after-hidden'):pass
    else:raise AssertionError(condition)
@step(r'the hide request or pending callback executes')
def hide_condition_run(w):
    u=w['unit'];condition=w['condition'];w['result']=b.hide(u,w['actor'])
    if condition=='elevation1-at-callback':u.z=1
    if condition.startswith('enemy-') or condition=='elevation1-at-callback':invoke(w,w['engine'].process_tick)
    if condition=='ordinary-movement-crosses-hex':
        from physics.movement import on_hex_entered
        u.set_hex_position(4,3);invoke(w,on_hex_entered,u,3,3)
    if condition=='ordinary-damage-after-hidden':
        invoke(w,w['engine'].run_ticks,61);eq(u.has_crit_status(C.HIDDEN),True)
        from systems.combat import apply_damage_with_transfer
        invoke(w,apply_damage_with_transfer,u,0,1,attacker=u)

@step(r'CAN_JETTISON (True|False) with pending slots (\d+) and live members (\d+)')
def packs(w,capable,pending,members):
    count(w,int(members));w['pending']=int(pending)
    if truth(capable):w['unit'].infantry_specials|=0x200
    for i in range(int(pending)):pack_slot(w,0,i)
def pack_slot(w,section,index):
    slot=w['unit'].sections[section].criticals[index];slot.type=get_weapon('PC.SMG').index+1
    slot.firemode=F.WILL_JETTISON_MODE|F.BROKEN_MODE|F.DISABLED_MODE|F.DAMAGED_MODE
    return slot
@step(r'the ordinary jettison command runs')
def packs_run(w):w['result']=b.jettison(w['unit'],w['actor'])
@step(r'a jettisonable weapon in (live-section0|destroyed-section7) with source pending flags')
def pack_runtime(w,section):
    w['pack_section']=0 if section=='live-section0' else 7;w['unit'].infantry_specials|=0x200
    for s in w['unit'].sections:
        for slot in s.criticals:slot.type=0;slot.firemode=0;slot.data=0
    w['slot']=pack_slot(w,w['pack_section'],0)
    if section=='destroyed-section7':w['unit'].sections[7].internal=w['unit'].sections[7].armor=0
@step(r'jettison is followed by ordinary fire and another jettison')
def pack_runtime_run(w):
    from systems.combat import fire_weapon
    packs_run(w);w['fire']=invoke(w,fire_weapon,w['unit'],w['host'],0,0)
    w['second']=b.jettison(w['unit'],w['actor'])
@step(r'fire is unavailable and second jettison reports no packs')
def pack_runtime_result(w):
    eq(w['fire'].hit,False);assert any('destroy' in m.lower() or 'functional' in m.lower() for m in w['fire'].messages),w['fire'].messages
    eq(w['second']['count'],0);eq(w['slot'].data,0)

ERRORS={'range-error':'out of range','argument-error':'Invalid arguments','mount-tech-error':'mounting','jettison-error':'jettisons','crowded-error':'no room','weapon-busy-error':'weapons recycling','section-busy-error':'recovering','legless-error':'no legs','friendly-error':'friendly','unsupported-nontermination':'nontermination','speed-error':'complete stop','terrain-error':"isn't going to work",'swarm-error':'Not while on','landed-error':'landed','already-hiding-error':'already','not-capable-error':'no backpack'}

def result(w,expected):
    u,t=w['unit'],w['host'];r=w.get('result')
    if expected in ERRORS:eq(r['ok'],False);assert ERRORS[expected] in r['error'],r;return
    if expected=='members1':eq(r,1)
    elif expected in ('Point-point','Squad-squad'):eq(r,tuple(expected.split('-')))
    elif expected=='mirror-XY3,4-Z3-elev2':eq(r,(3,4,3,2))
    elif expected in ('swarmed0-mounted0-count0-firstnone','ignored'):eq(r,(0,0,0,None))
    elif expected=='swarmed1-mounted1-count2-firstenemy':eq(r,(1,1,2,u))
    elif expected=='swarmed0-mounted1-count1':eq(r,(0,1,1,u))
    elif expected=='default-cleared-minus1':eq(r['ok'],False);eq(u.target,-1)
    elif expected in ('attempt','attempt-source-attacker-count'):
        eq(r['ok'],True);eq([s.recycle for s in u.sections if s.internal],[20]*b.members(u))
        if expected=='attempt-source-attacker-count':eq(b.count_swarmers(u),0);assert b.count_swarmers(t)>=1
    elif expected=='attached-both-flags-facing270-speeds0-unhidden-lock-stopped-recycle20':
        eq(r['success'],True);eq(u.swarm_target,t._id);eq((bool(u.status2&S2.UNIT_MOUNTING),bool(t.status2&S2.UNIT_MOUNTED)),(True,True))
        eq((u.facing,u.desired_facing,u.speed,u.desired_speed),(270,270,0,0));eq(u.has_crit_status(C.HIDDEN),False)
        eq(w['engine'].has_event(E.LOCK,u),False);eq(w['engine'].has_event(E.HIDE,u),False)
        eq([s.recycle for s in u.sections if s.internal],[20]*b.members(u))
    elif expected in ('unattached-unhidden-recycle20','hidden-retained-recycle30'):
        eq(r['success'],False);eq(u.swarm_target,None);eq(u.has_crit_status(C.HIDDEN),expected.startswith('hidden'))
        eq([s.recycle for s in u.sections if s.internal],[30 if expected.startswith('hidden') else 20]*b.members(u))
    elif expected in ('unattached-speed0-recycle20','unattached-speed0-recycle30','intentional20-no-detachment-PSR'):
        eq(u.swarm_target,None);eq(u.speed,0);eq([s.recycle for s in u.sections if s.internal],[30 if expected.endswith('30') else 20]*b.members(u))
        if expected.startswith('intentional'):eq(w['calls'],[])
    elif expected=='damage11-section7-then-survivors45':
        eq(u.swarm_target,None);eq(u.sections[7].internal,19);eq([s.recycle for s in u.sections if s.internal],[45]*b.members(u));eq(u.speed,0)
    elif expected=='unchanged':eq(u.swarm_target,999);eq(u.speed,2);eq(w['calls'],[])
    elif expected=='riders-remain-attached':eq(u.swarm_target,t._id);eq(t.is_started,False)
    elif expected=='pendinghide-retained-recycle20':eq(w['engine'].has_event(E.HIDE,u),True);eq([s.recycle for s in u.sections if s.internal],[20]*b.members(u))
    elif expected in ('scheduled','ignored-enemy'):eq(r['ok'],True);eq(w['engine'].has_event(E.HIDE,u),True);eq(u.has_crit_status(C.HIDDEN),False)
    elif expected in ('cancelled-not-hidden','pending-hide-cancelled'):eq(w['engine'].has_event(E.HIDE,u),False);eq(u.has_crit_status(C.HIDDEN),False)
    elif expected=='unhidden':eq(u.has_crit_status(C.HIDDEN),False)
    elif expected=='already-jettisoned':eq(r['ok'],True);eq(r['count'],0);assert 'nothing' in r['message']
    elif expected.startswith('destroy'):
        eq(r['ok'],True);eq(r['count'],w['pending'])
        for i in range(w['pending']):eq(u.sections[0].criticals[i].firemode,F.WILL_JETTISON_MODE|F.DAMAGED_MODE|F.DESTROYED_MODE|F.IS_JETTISONED_MODE)
        assert ('your backpack' if expected.endswith('singular') else 'backpacks') in r['message'],r
    else:raise AssertionError(expected)
