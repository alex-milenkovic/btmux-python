"""Arc masks and aiming calculations use ordinary combat services."""
from . import step,eq,invoke,mount,loc,position,make_unit,U,S,F
from systems import combat as c
from entities.weapon import get_weapon

@step(r'a weapon in (\w+) mounted (normal|rear)')
def weapon(w,name,mounting):
    w['location']=loc(name);slot=mount(w,loc(name))
    if mounting=='rear':slot.firemode|=F.REAR_MOUNT

@step(r'front left right and rear arcs are checked independently')
def arcs(w):
    from physics.hexmath import find_xy
    u=w['u'];w['arcs']=[]
    for name,bearing in (('front',0),('left',270),('right',90),('rear',180)):
        x,y=find_xy(u.fx,u.fy,bearing,5)
        if c.is_in_weapon_arc(u,x,y,w['location'],0):w['arcs'].append(name)

@step(r'allowed arcs are (\S+)')
def arc_result(w,expected):eq(w['arcs'],[] if expected=='none' else expected.split('-'))

@step(r'the weapon lifecycle fixture (.+)')
def lifecycle(w,text):
    u=w['u'];w['fixture']=text;w['target']=make_unit(w,'B');position(w['target'],10,9);w['target'].team=2
    slot=mount(w,0);w['slot']=slot
    u.sections[0].armor=100 if 'armor-positive' in text else 0
    if 'recycle5' in text:slot.data=u.weapons[0].recycle=5
    if 'destroyed' in text:slot.firemode=F.DESTROYED_MODE

@step(r'firing and scheduled recycling execute')
def lifecycle_run(w):
    from core.game_loop import update_recycling
    if 'recycle5' in w['fixture']:
        invoke(w,update_recycling,w['engine'],w['u']);invoke(w,w['engine'].run_ticks,10)
    else:w['result']=invoke(w,c.fire_weapon_number,w['engine'],w['u'],0,w['target'],to_hit_roll=12)

@step(r'the observation is (fire-accepted-recycle-started|recycle-remains5|recycle-finishes|fire-refused)')
def lifecycle_result(w,text):
    if text=='recycle-remains5':eq(w['slot'].data,5)
    elif text=='recycle-finishes':eq(w['slot'].data,0)
    elif text=='fire-refused':assert not w['result'].hit
    else:assert w['result'].hit,w['result'].messages;assert w['slot'].data>0

def aiming(w,name,side):
    a=make_unit(w,'B');u=w['u'];w['attacker']=a
    position(a,10,9);u.facing={'FRONT':0,'BACK':180,'LEFTSIDE':120,'RIGHTSIDE':240}[side]
    a.aim=loc(name);a.aim_type=U.AERO

@step(r'an immobile fighter aimed location (\w+)')
def aimed(w,name):aiming(w,name,'BACK');w['u'].clear_status(S.STARTED)

@step(r'the successful aimed-shot location helper runs from BACK')
def aimed_run(w):w['result']=invoke(w,c.find_aim_hit_loc,w['attacker'],w['u'])

@step(r'it returns (\d+) with rear true and no critical request')
def aimed_result(w,index):eq(w['result'],(int(index),True,False))

@step(r'matching fighter aim type location (\w+) side (\w+) and successful TC roll 3')
def tc(w,name,side):aiming(w,name,side);w['streams'].update(tc_location=[3],hit_location_rolls=[7])

@step(r'the TC location helper runs with fallback roll 7')
def tc_run(w):w['result']=invoke(w,c.find_tc_hit_loc,w['attacker'],w['u'])

@step(r'the returned location is (\w+) through (\S+)')
def tc_result(w,name,path):
    eq(w['result'][0],loc(name));eq(any(n=='hit_location_rolls' for n,*_ in w['draws']),path=='normal-table')

@step(r'TC gate case (\S+)')
def tc_gate(w,text):
    aiming(w,'Engine','FRONT');w['streams'].update(tc_location=[2],hit_location_rolls=[7])
    if text=='mismatched-type':w['attacker'].aim_type=U.MECH

@step(r'a FRONT hit uses fallback roll 7')
def fallback(w):tc_run(w)

@step(r'it hits Nose with random observation (\S+)')
def tc_draw(w,text):eq(w['result'][0],0);eq(any(n=='tc_location' for n,*_ in w['draws']),text=='tc-d6-consumed')

@step(r'a (Laser|Missile) aimed at fighter section (\w+) against a (mobile|immobile) target with targeting computer (on|off)')
def bth(w,weapon,name,mobility,tc):
    aiming(w,name,'FRONT');w['weapon']=get_weapon('IS.MediumLaser' if weapon=='Laser' else 'IS.LRM-15')
    w['mode']=F.ON_TC if tc=='on' else 0
    if mobility=='immobile':w['u'].clear_status(S.STARTED)

@step(r'the ordinary to-hit calculation evaluates aiming')
def bth_run(w):w['result']=invoke(w,c.calculate_bth,w['attacker'],w['u'],w['weapon'],1,w_fire_mode=w['mode'])

@step(r'the aim modifier is (-?\d+)')
def bth_result(w,value):eq(w['result'].aim_mod,int(value))
