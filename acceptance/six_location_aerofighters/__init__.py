"""Normal APS bindings for the historical fighter migration."""
import re
from acceptance.aerospace import base,invoke,eq,near,position,make_unit,events,messages
from entities.mech import UnitType as U,MoveType as M,MechStatus as S,CritStatus as C,FireMode as F
from entities.crittypes import i2special,i2weapon,Special
from entities.weapon import get_weapon

BACKGROUNDS={
'the historical fighter template and construction fixture described in docs/six-location-aerofighters-cli.md',
'a fresh fighter with six sections internal and original internal 10 no environmental damage or critical request unless the case overrides it',
'a fresh fighter with viable armor equipment and deterministic dice for every table case',
'a fighter using historical critical rules with vcrit 2 moving type Fly and a conscious pilot unless the case overrides it',
'a source-compatible fighter with functional physical weapon slots and ordinary firing prerequisites satisfied',
'independent public CLI sessions using unchanged original templates and the procedures in qa/six_location_aerofighters.py'}
BINDINGS=[]
NAMES=('Nose','Left_Wing','Right_Wing','Fuselage','Cockpit','Engine')

def step(pattern):
    def register(fn):BINDINGS.append((pattern,fn));return fn
    return register

def loc(name):return NAMES.index(name)

def setup(w):
    base(w,'fighter');w.pop('aerospace');w['six_location_aerofighters']=True
    u=w['u'];u.unit_type=U.AERO;u.move_type=M.FLY
    for section in u.sections:
        section.armor=section.armor_orig=100;section.internal=section.internal_orig=10
        for slot in section.criticals:slot.type=slot.data=slot.firemode=slot.ammomode=0
    u.weapons=[];u.si=0;u.real_num_sinks=25
    w['engine'].vcrit=2;w['engine'].fasacrit=0
    w['streams'].update(damage_entry=[7]*100,tow_rolls=[7]*100,pilot_rolls=[12]*100)

def mount(w,location,index=0,name='IS.MediumLaser'):
    from systems.weapon_inventory import sync_weapon_states
    slot=w['u'].sections[location].criticals[index]
    slot.type=i2weapon(get_weapon(name).index)
    sync_weapon_states(w['u']);return slot

def component(w,location,index,kind):
    slot=w['u'].sections[location].criticals[index];slot.type=i2special(kind);return slot

def execute(w,text):
    if text in BACKGROUNDS:setup(w);return
    for pattern,fn in BINDINGS:
        match=re.fullmatch(pattern,text)
        if match:fn(w,*match.groups());return
    raise AssertionError('Unbound historical fighter step: '+text)

from . import layout,damage,tables,criticals,weapons,workflows
