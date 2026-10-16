"""Damage entry observations exercise shared armor and critical consumers."""
import re
from . import step,eq,loc,invoke,mount,component,events,S,F,Special
from systems.combat import apply_damage_with_transfer as hit
from core.events import EventType as E

@step(r'section (\w+) armor (\d+) and Fuselage armor (\d+)')
def armor(w,name,amount,fuselage):
    w['location']=loc(name);w['u'].sections[3].armor=int(fuselage);w['u'].sections[loc(name)].armor=int(amount)
    w['pilot_before']=w['u'].pilot_hits

@step(r'section (\w+) armor zero and Fuselage armor (\d+)')
def empty(w,name,fuselage):armor(w,name,'0',fuselage)

@step(r'an ordinary nonrear hit deals (\d+) to that section')
def damage(w,amount):invoke(w,hit,w['u'],w['location'],int(amount))

def craft_result(w,result):
    u=w['u']
    if result=='destroyed':eq(u.is_destroyed,True)
    else:
        eq(u.is_destroyed,False)
        if result=='thrust-lost':eq((u.speed,u.max_speed,u.vertical_speed),(0,0,0));assert u.is_fallen
        if result=='shared-head-injury':eq(u.pilot_hits,w['pilot_before']+1)
        if result=='no-cockpit-injury':eq(u.pilot_hits,w['pilot_before'])
        if result=='no-new-engine-depletion-effect':assert not u.is_fallen;eq(events(w,E.FALL),[])
    eq([s.internal for s in u.sections[:6]],[10]*6)

@step(r'section armor Fuselage armor and craft result are (\d+) (\d+) and (.+)')
def outcome(w,armor,fuselage,result):
    eq((w['u'].sections[w['location']].armor,w['u'].sections[3].armor),(int(armor),int(fuselage)));craft_result(w,result)

@step(r'Fuselage armor is (\d+) and the craft result is (.+)')
def routed(w,armor,result):eq(w['u'].sections[3].armor,int(armor));craft_result(w,result)

@step(r'the fighter damage boundary (.+)')
def boundary(w,text):
    w['fixture']=text;u=w['u']
    for name,value in re.findall(r'(Right_Wing|Left_Wing|Fuselage|Engine|Nose)(\d+)',text):u.sections[loc(name)].armor=int(value)
    if text.startswith('empty-'):u.sections[3].armor=0;u.si=50
    w['location']=loc(text.split('-')[0].rstrip('0123456789')) if not text.startswith(('empty-','all-')) else 3
    if 'CASE' in text:u.sections[0].config|=__import__('entities.mech',fromlist=['SectionConfig']).SectionConfig.CASE_TECH
    if 'deferred-critical' in text:component(w,3,0,Special.HEAT_SINK);w['streams'].update(critical_rolls=[8],critical_slot=[0])

@step(r'the specified damage entry runs')
def entry(w):
    text=w['fixture']
    if text=='all-positive-armor-SI0':return
    amount=re.search(r'(?:hit|internal-only)(\d+)',text)
    invoke(w,hit,w['u'],w['location'],int(amount[1]),'rear' in text,is_critical='deferred-critical' in text,
           internal='internal-only' in text,transfer='transfer-enabled' in text or 'explicit-transfer' in text or 'CASE' in text)

def observe(w,text):
    u=w['u']
    if 'component_result' in w:
        from .criticals import component_observe
        return component_observe(w,text)
    if text.startswith('source-rear-remap'):eq((u.sections[3].armor,u.sections[2].armor),(25,15))
    elif text=='Left_Wing10-Fuselage30':eq((u.sections[1].armor,u.sections[3].armor),(10,30))
    elif text.startswith('Nose0-'):
        eq(u.sections[0].armor,0);eq(u.sections[3].armor,25 if 'Fuselage25' in text else 30);eq(u.sections[0].internal,10)
    elif text.startswith('destroyed'):eq(u.is_destroyed,True)
    elif text=='alive-before-damage':eq(u.is_destroyed,False);eq(u.si,0)
    elif text.startswith('Fuselage29'):
        eq(u.sections[3].armor,29);assert u.sections[3].criticals[0].firemode&F.DESTROYED_MODE;assert not u.is_fallen
    else:raise AssertionError(text)

@step(r'Engine armor 3 with flight state (\w+)')
def engine(w,state):
    w['u'].sections[5].armor=3;w['u'].speed=w['u'].max_speed=60;w['u'].vertical_speed=10
    if state=='landed':w['u'].set_status(S.LANDED)

@step(r'ordinary damage 3 exhausts Engine armor')
def engine_hit(w):invoke(w,hit,w['u'],5,3)

@step(r'the observable engine outcome is (.+)')
def engine_result(w,text):
    eq((w['u'].speed,w['u'].max_speed,w['u'].vertical_speed),(0,0,0))
    eq(len(events(w,E.FALL)),0 if 'no-new' in text else 1)

@step(r'a ready fighter weapon in (\w+) with armor 3')
def retained(w,name):armor(w,name,'3','30');w['slot']=mount(w,loc(name))

@step(r'ordinary damage 8 exhausts that armor')
def exhaust(w):damage(w,'8')

@step(r'internals remain 10 and the individual weapon remains functional')
def intact(w):eq(w['u'].sections[w['location']].internal,10);eq(w['slot'].firemode,0)
