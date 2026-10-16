"""All historical aspect tables with real pre-hit side effects."""
from . import step,setup,loc,eq,invoke,mount,component,Special,F,C,S
from systems import hit_locations as h
from systems.combat import HitGroup as H

def table_case(side,roll,profile):
    w={};setup(w);u=w['u'];w['engine'].sim_now=42
    for i in range(6):
        u.sections[i].armor=80;mount(w,i,0);mount(w,i,1);component(w,i,3,Special.HEAT_SINK)
    from entities.crittypes import i2bomb
    u.sections[3].criticals[4].type=i2bomb(2)
    w['streams']['fighter_weapon_choice']=[0]
    w['result']=invoke(w,h.find_hit_location,u,H[side],int(roll),profile=profile)
    return w

@step(r'legacy and FASA independently select side (\w+) roll (\d+)')
def profiles(w,side,roll):w['tables']=[table_case(side,roll,p) for p in ('legacy','FASA')]

@step(r'both return (\w+) and the pre-damage effect is (\S+)')
def active_result(w,name,effect):
    for case in w['tables']:
        u=case['u'];location,critical=case['result'];eq(location,loc(name))
        eq(critical,effect.startswith('deferred'))
        eq(bool(u.crit_status&C.SPINNING),effect=='control')
        eq(u.real_num_sinks,23 if effect.startswith('sink') else 25)
        dead=[(i,j) for i,s in enumerate(u.sections) for j,p in enumerate(s.criticals) if p.firemode&F.DESTROYED_MODE]
        eq(dead,[(location,0 if effect.startswith('weapon') else 3)] if effect.startswith(('weapon','sink')) else [])
        if effect=='control':eq(u.start_spin,42)
        if effect=='inert-bomb-hook':assert u.sections[3].criticals[4].type;eq(u.damage_taken,0)
        eq([s.armor for s in u.sections[:6]],[80]*6)
        assert not any(n in ('critical_rolls','crittable_chance') for n,*_ in case['draws'])

@step(r'the critproof table selects side (\w+) roll (\d+)')
def proof(w,side,roll):w['table']=table_case(side,roll,'critproof')

@step(r'it returns (\w+) without table effects or critical chance draws')
def proof_result(w,name):
    c=w['table'];eq(c['result'],(loc(name),False));eq(c['draws'],[])
    assert not c['u'].has_crit_status(C.SPINNING)
    assert all(not s.firemode for sec in c['u'].sections for s in sec.criticals)

@step(r'the fighter table configuration (.+)')
def config(w,text):
    from entities.mech import Specials
    w['engine'].fasacrit=int(text.endswith('on'))
    if text.startswith('critproof'):w['u'].specials|=Specials.CRITPROOF_TECH
    w['streams']['hit_location_rolls']=[3,2]

@step(r'ordinary combat requests a hit location')
def dispatch(w):
    from unittest.mock import patch
    with patch.object(h,'aero_location',wraps=h.aero_location) as call:
        w['result']=invoke(w,h.find_hit_location,w['u'],H.FRONT)
    w['profile']=call.call_args.args[3]

@step(r'the selected historical profile is (\w+)')
def selected(w,profile):eq(w['profile'],profile);eq(w['result'][0],0 if profile=='legacy' else 4)
