"""Direct effects, deferred slot criticals and sequential missile damage."""
import re
from . import step,eq,invoke,mount,component,Special,F,C,S,U,position,make_unit
from systems import hit_locations as h,criticals as c,damage as d
from systems.combat import HitGroup as H,apply_damage_with_transfer as hit
from entities.mech import Specials,MoveType as M

@step(r'armor (\d+) original armor (\d+) threshold (\d+) and chance (\d+)')
def gate(w,armor,original,threshold,chance):
    s=w['u'].sections[0];s.armor=int(armor);s.armor_orig=int(original)
    w['threshold']=int(threshold);w['streams']['crittable_chance']=[int(chance)]

@step(r'the fighter critical gate runs')
def gate_run(w):w['result']=invoke(w,h.crittable,w['u'],0,w.get('threshold',90))

@step(r'gate (true|false) consumes (.+)')
def gate_result(w,result,domain):
    eq(w['result'],result=='true');dice=[(lo,hi) for name,_,lo,hi in w['draws'] if name=='crittable_chance']
    eq(dice,[] if domain=='none' else [tuple(map(int,domain.split('..')))])

def override(w,text):
    if text=='critproof':w['u'].specials|=Specials.CRITPROOF_TECH
    elif text=='Move_NONE':w['u'].move_type=M.NONE
    else:w['engine'].vcrit=int(text[-1])

@step(r'fighter gate overrides (.+)')
def overrides(w,text):override(w,text)

@step(r'the critical gate runs on zero original armor')
def zero_gate(w):w['u'].sections[0].armor_orig=0;gate_run(w)

@step(r'the gate is (true|false) without random draws')
def no_draw(w,result):eq(w['result'],result=='true');eq(w['draws'],[])

@step(r'positive original armor and (.+)')
def positive(w,text):override(w,text)

@step(r'the direct fighter effect case (.+)')
def direct_setup(w,text):
    w['fixture']=text;u=w['u'];w['engine'].sim_now=42
    for sec in u.sections:sec.armor=80
    if 'weapon' in text or 'global' in text or 'same-type' in text or text.startswith('two-Nose'):
        mount(w,0)
        if not text.startswith('one-global'):mount(w,0,1)
        if text.startswith(('first-of','second-global-mount-destroyed')):u.sections[0].criticals[0 if text.startswith('first') else 1].firemode|=F.DESTROYED_MODE
        if 'recycling' in text:u.sections[0].criticals[1].data=5
        w['streams']['fighter_weapon_choice']=[0]
    elif text.startswith('sink'):
        if 'no-local' not in text:component(w,5,0,Special.HEAT_SINK);component(w,5,1,Special.HEAT_SINK)
        if 'first-sink-destroyed' in text:u.sections[5].criticals[0].firemode|=F.DESTROYED_MODE
    elif text.startswith('rear'):
        if 'landed' in text:u.set_status(S.LANDED)
        if 'destroyed' in text:u.set_status(S.DESTROYED)
        if 'already-spinning' in text:u.set_crit_status(C.SPINNING);u.start_spin=13
    else:
        from entities.crittypes import i2bomb
        u.sections[3].criticals[0].type=i2bomb(2)

@step(r'the source table or named helper executes')
def direct(w):
    text=w['fixture'];u=w['u']
    if text.startswith('sink'):invoke(w,d.destroy_heat_sink,u,5)
    elif text.startswith('rear'):invoke(w,h.find_hit_location,u,H.BACK,int(re.search(r'rear(\d+)',text)[1]),profile='legacy')
    elif text.startswith('front'):invoke(w,h.find_hit_location,u,H.FRONT,10,profile='legacy')
    else:
        from systems.damage_commands import lose_weapon
        invoke(w,lose_weapon,u,0)

@step(r'the equipment or control observation is (.+)')
def direct_result(w,text):
    u=w['u'];slots=u.sections[0].criticals
    if text in ('no-candidate-no-selection-draw','no-destruction'):
        eq(slots[0].firemode,0)
        if text.startswith('no-candidate'):eq(w['draws'],[])
    elif text.startswith(('global-mount0','first-redestroyed-second-retained')):assert slots[0].firemode&F.DESTROYED_MODE;eq(slots[1].firemode,0)
    elif text.startswith('sinks25'):eq(u.real_num_sinks,25);assert all(not s.type for s in u.sections[5].criticals)
    elif text.startswith(('first-sink','first-redestroyed-capacity')):
        eq(u.real_num_sinks,23);assert u.sections[5].criticals[0].firemode&F.DESTROYED_MODE;eq(u.sections[5].criticals[1].firemode,0)
    elif text=='spinning-start-time-set':assert u.has_crit_status(C.SPINNING);eq(u.start_spin,42)
    elif text=='no-spin':assert not u.has_crit_status(C.SPINNING)
    elif text=='start-time-preserved':eq(u.start_spin,13)
    else:assert u.sections[3].criticals[0].type;eq(u.damage_taken,0)

@step(r'Engine armor 18 original 20 and rear roll 2 with chance 6 passing threshold 90')
def deferred(w):
    s=w['u'].sections[5];s.armor=18;s.armor_orig=20
    for i in range(3):component(w,5,i,Special.HEAT_SINK)
    w['streams'].update(crittable_chance=[6],critical_slot=[0]*3)
    w['selected']=invoke(w,h.find_hit_location,w['u'],H.BACK,2,profile='legacy')

@step(r'armor damage 1 runs with critical count roll (\d+)')
def deferred_hit(w,roll):
    w['streams']['critical_rolls']=[int(roll)]
    invoke(w,hit,w['u'],w['selected'][0],1,True,is_critical=w['selected'][1])

@step(r'requested Engine slot criticals are (\d+) after armor becomes 17')
def deferred_result(w,count):
    eq(w['u'].sections[5].armor,17)
    eq(sum(bool(s.firemode&F.DESTROYED_MODE) for s in w['u'].sections[5].criticals),int(count))

@step(r'the fighter component case (.+)')
def component_setup(w,text):
    w['fixture']=text;u=w['u'];w['location']=5;kind=Special.HEAT_SINK
    if text.startswith('Cockpit'):
        w['location']=4;kind=Special.LIFE_SUPPORT if 'LifeSupport' in text else Special.COCKPIT if 'Cockpit-IC' in text else Special.SENSORS
        u.lrs_range=80;u.tac_range=40;u.scan_range=20;u.base_to_hit=0
        if 'second' in text:u.set_crit_status(C.SENSORS_DAMAGED)
        if kind==Special.COCKPIT:u.in_character=True;w['pilot']=u.pilot
    elif text.startswith('Engine-component'):kind=Special.ENGINE;u.engine_heat=int(text.rsplit('engineheat',1)[1])
    if text not in ('no-eligible-slots',):component(w,w['location'],0,kind)
    if text.startswith('eligible-slot'):
        component(w,5,1,Special.HEAT_SINK).firemode=F.DESTROYED_MODE
        component(w,5,2,Special.HEAT_SINK).firemode=F.DAMAGED_MODE
    if text in ('critproof','vcrit0'):override(w,text)
    if text=='combat-safe':u.set_status(S.COMBAT_SAFE)
    w['streams']['critical_slot']=[0]

@step(r'its shared critical path resolves')
def component_run(w):w['component_result']=invoke(w,c.check_and_apply_criticals,w['u'],w['location'],1)

def component_observe(w,text):
    u=w['u'];r=w['component_result']
    if text.startswith(('no-slot','no-draw')):eq(r,[]);eq(w['draws'],[])
    elif text=='life-support-destroyed':assert u.has_crit_status(C.LIFE_SUPPORT_DESTROYED)
    elif text=='ranges40-20-10-BTH2':eq((u.lrs_range,u.tac_range,u.scan_range,u.base_to_hit),(40,20,10,2))
    elif text=='ranges0-0-0-BTH75':eq((u.lrs_range,u.tac_range,u.scan_range,u.base_to_hit),(0,0,0,75))
    elif text.startswith('craft-destroyed'):assert u.is_destroyed;eq(u.pilot,None);assert not w['pilot'].alive
    elif text.startswith('capacity24'):eq(u.real_num_sinks,24);assert u.sections[5].criticals[0].firemode&F.DESTROYED_MODE
    elif text.startswith('engineheat'):
        amount=int(re.search(r'engineheat(\d+)',text)[1]);eq(u.engine_heat,amount);eq(u.is_destroyed,amount==15)
        if amount<15:eq(u.max_speed,60)
    else:
        eq(u.sections[5].criticals[2].firemode,F.DAMAGED_MODE)
        eq([row for row in w['draws'] if row[0]=='critical_slot'],[('critical_slot',0,0,0)])
        assert u.sections[5].criticals[0].firemode&F.DESTROYED_MODE

@step(r'CHP-W5 Nose armor 24 with only global mount zero installed and full-armor chance miss')
def missiles(w):
    from .layout import load
    from systems.weapon_inventory import sync_weapon_states
    load(w);u=w['u'];u.status=S.STARTED
    for sec in u.sections:
        for s in sec.criticals:s.type=s.data=s.firemode=0
    sync_weapon_states(u);mount(w,0)
    w['attacker']=make_unit(w,'B');position(w['attacker'],10,9);u.facing=0
    w['streams'].update(crittable_chance=[22,5])

@step(r'all (\S+) damage groups hit Nose roll 3 in sequence')
def missile_run(w,family):
    from unittest.mock import patch
    from systems.missile import missile_hit
    from entities.weapon import get_weapon
    lrm=family.startswith('LRM');w['armors']=[]
    def gate(*args):w['armors'].append(w['u'].sections[0].armor);return real(*args)
    real=h.crittable
    with patch.object(h,'crittable',side_effect=gate):
        invoke(w,missile_hit,w['attacker'],w['u'],get_weapon('IS.LRM-15' if lrm else 'IS.SRM-2'),15 if lrm else 2,1 if lrm else 2,5 if lrm else 1,location_rolls=[3]*(3 if lrm else 2))

@step(r'pre-hit armors are (\S+) final armor is (\d+) and gate draw domains are (\S+)')
def missile_result(w,before,after,draws):
    eq(w['armors'],list(map(int,before.split('-'))));eq(w['u'].sections[0].armor,int(after))
    eq([(lo,hi) for name,_,lo,hi in w['draws'] if name=='crittable_chance'],[(1,71)] if draws=='1..71-only' else [(1,71),(1,11)])
