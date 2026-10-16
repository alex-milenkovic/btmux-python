"""APS bindings run production displays against the shared simulation."""
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from entities.mech import UnitType as U,MoveType as M,MechStatus as S,CritStatus as C,FireMode as F,AmmoMode as A
from entities.crittypes import i2weapon,i2ammo,i2special,Special
from entities.weapon import get_weapon
from systems.armor_display import plain
from tools.hud_status import DisplaySession

BINDINGS=[]
N=r'(-?\d+(?:\.\d+)?)'
def step(pattern):
    def register(fn):BINDINGS.append((re.compile(pattern),fn));return fn
    return register

def eq(actual,expected):
    if actual!=expected:raise AssertionError(f'expected {expected!r}, got {actual!r}')
def truth(text):return text=='true'
def u(w):return w['s'].units['viewer']
def t(w):return w['s'].units['target']
def blank(text):return '' if text in ('unset','no-argument','none','empty') else text
def command(w,name,args=''):
    result=w['s'].action(dict(op='command',unit='viewer',name=name,args=blank(args).split()));w['result']=result;return result

def hud(w,text):
    from contextlib import nullcontext
    from unittest.mock import patch
    with patch('physics.hexmath.in_weapon_arc',return_value=w['arcs']) if 'arcs'in w else nullcontext():
        result=w['s'].action(dict(op='hudinfo',session='main',text=blank(text)))
    w['result']=result;return result

def records(w,kind='L',result=None):return [r['payload'].split(',') for r in (result or w['result'])['records'] if r['type']==kind]
def visible(w,nb=True,sensors=6):
    u(w).map.losinfo[u(w)._id,t(w)._id]=sensors|1|(0 if nb else 0x8000)
    w['s'].diagnostic_cache=True

def form(unit,text):
    for name,value in [('fuel_orig',100),('fuel',100),('tank_crit_status',0),('turret_facing',0)]:
        if not hasattr(unit,name):setattr(unit,name,value)
    text={'biped':'MECH-BIPED','quad':'MECH-QUAD','mech':'MECH-BIPED','vehicle':'VEHICLE-TRACK','turreted-vehicle':'VEHICLE-TRACK'}.get(text,text)
    unit.unit_type,unit.move_type={'MECH-BIPED':(U.MECH,M.BIPED),'MECH-QUAD':(U.MECH,M.QUAD),'VEHICLE-TRACK':(U.VEH_GROUND,M.TRACK),'VEHICLE-WHEEL':(U.VEH_GROUND,M.WHEEL),'VEHICLE-HOVER':(U.VEH_GROUND,M.HOVER),'NAVAL-HULL':(U.VEH_NAVAL,M.HULL),'NAVAL-FOIL':(U.VEH_NAVAL,M.FOIL),'NAVAL-SUB':(U.VEH_NAVAL,M.SUB),'VTOL':(U.VTOL,M.VTOL),'AERO':(U.AERO,M.FLY),'DS':(U.DS,M.FLY),'SPHEROID_DS':(U.SPHEROID_DS,M.FLY),'MW':(U.MW,M.BIPED),'BSUIT':(U.BSUIT,M.BIPED),'INSTALLATION':(U.VEH_GROUND,M.NONE)}[text]

def mount(unit,name='IS.MediumLaser',loc=0,pos=4):
    weapon=get_weapon({'MediumLaser':'IS.MediumLaser','SRM6':'IS.SRM-6'}.get(name,name))
    for index in range(pos,min(12,pos+weapon.crits)):
        slot=unit.sections[loc].criticals[index];slot.type=i2weapon(weapon.index);slot.data=slot.brand=slot.firemode=slot.ammomode=0
    return unit.sections[loc].criticals[pos]

def empty_weapons(unit):
    unit.weapons=[]
    for section in unit.sections:
        for slot in section.criticals:slot.type=slot.data=slot.brand=slot.firemode=slot.ammomode=0

def weapon_state(slot,text,ticks=0):
    text=text.replace('damaged-weapon','damaged-slot')
    slot.data=int(ticks);slot.firemode=slot.brand=0
    for word in ('broken','disabled','destroyed','jettisoned','damaged-slot','rocket-fired','half-ton'):
        if word in text and text!='temporarily-destroyed':slot.firemode|={'broken':F.BROKEN_MODE,'disabled':F.DISABLED_MODE,'destroyed':F.DESTROYED_MODE,'jettisoned':F.IS_JETTISONED_MODE,'damaged-slot':F.DAMAGED_MODE,'rocket-fired':F.ROCKET_FIRED,'half-ton':F.HALFTON_MODE}[word]
    for word,value in [('jammed',1),('shorted',2),('dud',3),('empty',4),('temporarily-destroyed',5),('ammojammed',6),('temporary-failure',1)]:
        if word in text:slot.brand=value<<4
    if text=='nonfunctional':slot.firemode=F.DESTROYED_MODE

@step(r'a fresh HUD display session with ready units and event time zero')
def fresh(w):
    Path('./tmp').mkdir(exist_ok=True);w['storage']=TemporaryDirectory(dir='./tmp',prefix='hud-aps-')
    w['s']=DisplaySession({'hud_display':{'root':w['storage'].name},'map':{'size':[100,100]},'units':[{'name':'viewer','core':{'template_ref':'HUD-1'},'contact_id':'VV','at':[2,2,0]},{'name':'target','contact_id':'TT','at':[2,4,0],'team':2}],'sessions':[{'name':'main','unit':'viewer'}],'config':{'periodic_updates':False},'actions':[]})
    empty_weapons(u(w));empty_weapons(t(w));visible(w);w['hud_status']=True

@step(r'session key is (\S+)')
def key(w,value):w['s'].sessions['main'].request('key='+blank(value))

@step(r'(?:the user submits HUD text|the user requests keyed HUD|keyed HUD text) (.+?)(?: is submitted)?')
def request(w,text):hud(w,text)

@step(r'keyed HUD (\w+) is requested')
def export(w,name):hud(w,'t 5' if name=='tactical' else name)

@step(r'a mounted weapon has states? (\S+) and recycle data (\d+)')
def mounted(w,state,ticks):w['slot']=mount(u(w));weapon_state(w['slot'],state,ticks)


def execute(w,text):
    for regex,fn in BINDINGS:
        match=regex.fullmatch(text)
        if match:return fn(w,*match.groups())
    raise ValueError('No HUD display binding: '+text)

from . import protocol,status,maps,observation,integration
