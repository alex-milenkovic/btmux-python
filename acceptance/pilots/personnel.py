from types import SimpleNamespace
from . import step,base,eq,truth
from core.game_loop import GameEngine
from core.randomness import use_source
from core.events import EventType as E
from entities.mech import Mech,UnitType as U,MoveType as M,MechStatus as S,CritStatus as C,FireMode as F,Location as L,Specials
from entities.map import GameMap
from entities.weapon import get_weapon
from data.characters import SKILLS
from data.character_values import code
from systems import occupants as o


def fresh_personnel(w):
    base(w);w['engine']=GameEngine();w['engine'].sim_now=101
    w['world']=o.Personnel(w['engine'],w['store'],pickup_action=0)
    w['board']=GameMap(12,12);w['board']._id=1000;w['engine'].register_entity(w['board'])
    w['unit']=make(w,10);w['carrier']=make(w,20)
    w['carrier'].car_max_ton=5;w['carrier'].cargo_space=800;w['carrier'].specials2=0x80000
    w['actor']=w['store'].actor(101);w['world'].add(w['actor'],10);w['unit'].pilot=w['actor'];w['unit'].official_pilot=101
    w['store'].create(102,'Wizard',wizard=True,location=10);w['world'].add(w['store'].actor(102),10)
    s=w['store'].retrieve(101);s.xp[code('Running')]=100;w['store'].store(101,s,SKILLS)


def make(w,ident):
    unit=Mech.create_test_mech();unit._id=ident;unit.status=S.STARTED;unit.in_character=True;unit.team=1
    unit.tonnage=5;unit.measured_mass=5*1024;unit.max_speed=43
    w['board'].add_mech(unit);unit.mapindex=1000;unit.set_hex_position(3,3)
    w['engine'].register_entity(unit);w['world'].add(unit,1000)
    from systems.sensors import update_los_info
    from systems.targeting import plos_event
    with use_source(lambda name,lo,hi,fallback:hi):
        update_los_info(w['board'])
        for other in w['board'].mechs_on_map:plos_event(SimpleNamespace(data=other,data2=w['engine']))
    return unit

@step(r'source-valid co-located units with ordered local occupants and empty enter locks')
def boarding(w):fresh_personnel(w);w['family']='boarding'
@step(r'a source-valid IC carrier and started allied embarking unit with no recycle and free cargo measured in hundredths of tons')
def carriers(w):fresh_personnel(w);w['family']='carriers'
@step(r'transfer flag (\d+) origin quiet (True|False) with one ordinary occupant and one wizard')
def transfer(w,flag,quiet):w['flag']=int(flag);w['unit'].quiet=truth(quiet)
@step(r'contents transfer and IC shell disposal execute')
def transfer_run(w):w['result']=o.tele_contents(w['engine'],10,20,w['flag']);o.discard_mw(w['unit'])
@step(r'count is (\d+) ordinary slave is (True|False) XP loss is (True|False) and teleport is (hush|loud)')
def transfer_result(w,count,slave,loss,mode):
    eq(w['result'],int(count));eq(getattr(w['actor'],'slave',False),truth(slave))
    xp=w['store'].retrieve(101,SKILLS).xp[code('Running')]%16777216
    eq(xp,66 if truth(loss) else 100);eq(w['actor'].location,20)
    eq([e['loud'] for e in w['world'].trace if e['kind']=='move'],[mode=='loud']*int(count))
    eq(w['engine'].has_event(E.NUKEMECH,w['unit']),True)

@step(r'MW embark condition (\S+)')
def mw_condition(w,condition):
    w['condition']=condition;u,t=w['unit'],w['carrier'];u.unit_type=U.MW
    if condition.startswith('same-team-speed'):t.speed=float(condition[15:])
    elif condition=='other-team-empty-lock':t.team=2
    elif condition=='other-team-explicit-passing-lock':t.team=2;t.enter_lock='approved';t.lock_result=True
    elif condition=='failing-lock':t.enter_lock='locked';t.lock_result=False;t.fail_message='Custom FAIL'
    elif condition.startswith('height-plus'):u.z=int(condition[-1])
    elif condition=='different-hex':u.set_hex_position(4,3)
    elif condition=='target-OOD':t.cocoon=1
    elif condition=='ground-unfixable':t.unit_type=U.VEH_GROUND;t.sections[0].internal=t.sections[0].armor=0
    elif condition=='MECH-no-head':t.sections[L.HEAD].internal=0
    elif condition=='MECH-destroyed-cockpit':t.sections[L.HEAD].criticals[2].firemode|=F.DESTROYED_MODE
    elif condition=='MECH-disabled-cockpit':t.sections[L.HEAD].criticals[2].firemode|=F.DISABLED_MODE
    else:raise AssertionError(condition)
@step(r'the ordinary embark command executes')
def mw_run(w):w['result']=o.embark(w['unit'],w['actor'],w['carrier'])

@step(r'pickup target team (friendly|enemy) pickup_action (\d+) and picker (\S+)')
def pick(w,team,action,picker):
    w['pickup']=True;u,t=w['unit'],w['carrier'];t.unit_type=U.MW;t.specials2=0;t.team=1 if team=='friendly' else 2
    w['world'].pickup_action=int(action);w['picker']=picker;w['pickup_team']=team
    if picker.startswith('BA'):u.unit_type=U.BSUIT
    if picker=='VTOL':u.unit_type=U.VTOL;u.move_type=M.VTOL;u.status|=S.LANDED
    if picker=='BA-salvage':u.specials|=Specials.SALVAGE_TECH
    for ident in (101,102):w['world'].move(ident,20)
    w['world'].trace.clear()
@step(r'ordinary pickup passes its source position and LOS gates')
def pick_run(w):w['result']=o.pickup(w['unit'],w['actor'],w['carrier'])
@step(r'shell state (IC|nonIC) after a successful occupant transfer')
def discard(w,state):
    w['unit'].in_character=state=='IC';o.tele_contents(w['engine'],10,20,1);o.discard_mw(w['unit'])
@step(r'the normal clock advances to (\d+)')
def advance(w,time):
    with use_source(lambda name,lo,hi,fallback:hi):w['engine'].run_ticks(int(time))
@step(r'the shell is (\S+)')
def discarded(w,result):
    u=w['unit'];eq(w['world'].contents(10),[])
    if result=='leave-hook-then-used-store-dark-zombie-no-hardcode':
        eq(u.location,901);eq((u.dark,u.zombie,u.hardcode),(True,True,False))
        eq([e['kind'] for e in w['world'].trace if e['kind'] in ('leave','discard')],['leave','discard'])
        assert u not in w['engine'].get_entities()
    else:
        eq(u.location,1000);assert u in w['engine'].get_entities()
        eq(w['engine'].has_event(E.NUKEMECH,u),result=='still-present-empty')

@step(r'embark condition (\S+)')
def carrier_condition(w,condition):
    import re
    w['condition']=condition;u,t=w['unit'],w['carrier']
    match=re.fullmatch(r'tons(\d+)-free(\d+)-max(\d+)',condition)
    if match:u.tonnage,t.cargo_space,t.car_max_ton=map(int,match.groups())
    elif condition.startswith('own5-towed3-free'):
        tow=make(w,30);tow.tonnage=3;tow.measured_mass=3*1024;tow.status|=S.TOWED
        u.carrying=30;u.towed_unit=tow;w['tow']=tow;t.cargo_space=int(condition.split('-free')[1].split('-')[0])
    elif condition=='target-speed0.01':t.speed=.01
    elif condition=='own-MMaxSpeed-below-MP1':u.max_speed=1
    elif condition=='own-hidden':u.crit_status|=C.HIDDEN
    elif condition=='section-recycle':u.sections[7].recycle=1
    elif condition=='weapon-recycle':u.sections[0].criticals[0].type=get_weapon('PC.SMG').index+1;u.sections[0].criticals[0].data=1
    elif condition=='BA-noncarrier-with-capacity':u.unit_type=U.BSUIT;t.specials2=0
    elif condition=='MECH-noncarrier':t.specials2=0
    elif condition=='own-carrying-target':u.carrying=t._id
    elif condition=='jumping-target':t.status|=S.JUMPING
    else:raise AssertionError(condition)
@step(r'ordinary unit embark runs')
def carrier_run(w):mw_run(w)


def carry(w):
    u,t=w['unit'],w['carrier'];w['board'].remove_mech(u);u.map=None;u.mapindex=-1;u.status&=~S.STARTED
    w['world'].move(u._id,t._id);t.cargo_space=0
@step(r'carried unit condition (\S+)')
def exit_condition(w,condition):
    carry(w);w['condition']=condition;u,t=w['unit'],w['carrier']
    if condition=='IC-wrong-official-owner':u.official_pilot=999
    elif condition=='IC-wizard':w['actor'].wizard=True;u.official_pilot=999
    elif condition=='repairs-pending':u.repair_remaining=1
    elif condition.startswith('carrier-speed-'):
        from physics.cargo import cargo_max_speed
        t.speed=cargo_max_speed(t)*2/3+(1 if condition.endswith('overwalk') else 0)
    elif condition=='carrier-no-map':t.mapindex=-1
    elif condition=='BA-ground-carrier-stopped':u.unit_type=U.BSUIT;t.status&=~S.STARTED
    elif condition=='MECH-ground-carrier-stopped':t.status&=~S.STARTED
    elif condition=='MECH-ground-carrier-started':pass
    elif condition=='nonflyer-abovefloor':t.z=2
    elif condition=='landed-flyer-abovefloor-carrier-started':t.z=2;u.unit_type=U.VTOL;u.move_type=M.VTOL;u.status|=S.LANDED
    else:raise AssertionError(condition)
@step(r'ordinary unit disembark runs')
def exit_run(w):
    with use_source(lambda name,lo,hi,fallback:hi):w['result']=o.unit_disembark(w['unit'],w['actor'])
@step(r'carried unit class (\S+) exits at carrier XYZ with invoking actor inside')
def exit_class(w,kind):
    carry(w);w['exit_class']=kind;w['unit'].unit_type={'BA':U.BSUIT,'MECH':U.MECH,'MW':U.MW,'ground':U.VEH_GROUND,'VTOL':U.VTOL}[kind]
    if kind=='BA':w['unit'].sections[7].internal=0
@step(r'the ordinary exit completes')
def exit_complete(w):exit_run(w)
@step(r'immediate startup and cargo credit occur with section recycle (\S+)')
def exit_result(w,recycle):
    u=w['unit'];eq(w['result']['ok'],True);eq(u.is_started,True);eq(w['carrier'].cargo_space,500);eq(u.pilot,w['actor'])
    eq((u.x,u.y,u.z),(w['carrier'].x,w['carrier'].y,w['carrier'].z))
    expected=[20 if s.internal else 0 for s in u.sections] if recycle=='live-members20' else [0 if i==5 and recycle=='all-except5-60' else 60 for i in range(8)]
    eq([s.recycle for s in u.sections],expected)

ERRORS={'speed-error':'moving too fast','locked-error':'Locked','height-error':'high above','samehex-error':'same hex','landing-error':'land first','wreck-error':'twisted metal','head-error':'head go','cockpit-missing-error':'stole the cockpit','cockpit-stuck-error':"won't budge",'pickup-class-error':"can't pick up",'cargo-error':'Not enough cargospace','class-tonnage-error':'too large','combined-cargo-error':'towed unit','overload-error':'overloaded','hidden-error':'hidden','physical-recycle-error':'recovering','weapon-recycle-error':'weapons recycling','carrier-required':"can't handle your mass",'towing-target-error':'towing','jump-error':'jumping','owner-error':"isn't your mech",'repair-error':'repairs','map-error':'not on a map'}

def result(w,expected):
    r=w['result'];u,t=w['unit'],w['carrier']
    if expected in ERRORS:
        eq(r['ok'],False);needle=ERRORS[expected]
        if expected=='speed-error' and w.get('condition')=='carrier-speed-overwalk':needle='faster than walk'
        assert needle in r['error'],(expected,r);return
    if expected=='FAIL-and-AFAIL':
        eq(r['ok'],False);eq(r['error'],'Custom FAIL');assert any(e.get('service')=='MUX FAIL/AFAIL' and not e['delivered'] for e in w['world'].trace);return
    eq(r['ok'],True)
    if expected=='accepted-transfer-all':eq(w['world'].contents(20),[101,102]);eq(w['world'].contents(10),[]);eq(w['actor'].location,20)
    elif expected.startswith('all-contents'):
        eq(w['world'].contents(10),[101,102]);eq(w['world'].contents(20),[])
        eq(getattr(w['actor'],'slave',False),'nonwiz-slave' in expected);eq(getattr(w['store'].actor(102),'slave',False),False)
        eq([e['loud'] for e in w['world'].trace if e['kind']=='move'],['loud' in expected]*2)
    elif expected in ('accepted-free0','both-board-free0-tow-cleared'):
        eq(t.cargo_space,0);eq(u.mapindex,-1);eq(u.location,20);eq(u.is_started,False)
        if expected.startswith('both'):
            eq(w['world'].contents(20),[30,10]);eq(u.carrying,-1);eq(w['tow'].has_status(S.TOWED),False)
    elif expected=='climbout-no-fall':eq(r['path'],'climbout');eq(getattr(u,'last_fall_levels',None),None)
    elif expected=='breakout-fall4':eq(r['path'],'breakout');eq(u.last_fall_levels,4)
    elif expected=='ramp':eq(r['path'],'ramp')
    elif expected=='OOD':eq(r['path'],'OOD');eq(w['engine'].has_event(E.OOD,u),True)
    elif expected=='ramp-clear-landed':eq(r['path'],'ramp');eq(u.has_status(S.LANDED),False)
    else:eq(expected,'accepted')
