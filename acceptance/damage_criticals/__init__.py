"""Task bindings operate on fresh production sessions and explicit fixtures."""
import re
from tools.damage_criticals import DamageSession
from entities.mech import Location as L, UnitType as U, MoveType as M, FireMode as F, Specials, MechStatus as S, MechStatus2 as S2, CritStatus as C
from entities.crittypes import Special, i2special, i2weapon
from entities.weapon import get_weapon
from systems import damage_commands as commands

BINDINGS=[]
def step(pattern):
    def register(fn): BINDINGS.append((pattern,fn));return fn
    return register

def eq(actual, expected):
    if isinstance(expected,float): assert abs(actual-expected)<1e-5,(actual,expected)
    else: assert actual==expected,(actual,expected)

def truth(value): return value=='True'
def unit(w): return w['damage_session'].units['u']
def session(w): return w['damage_session']
def call(w,fn,*args,**kwargs): return session(w).invoke(fn,*args,**kwargs)
def draw(w,name,values): session(w).streams[name]=list(values)
def loc(w,name):
    return commands.section_index(unit(w),name)
def setup(w, kind='MECH', **values):
    aliases={'GROUND':'VEH_GROUND','NAVAL':'VEH_NAVAL','BA':'BSUIT','airborne-VTOL':'VTOL','landed-VTOL':'VTOL'}
    kind=aliases.get(kind,kind)
    u=unit(w);u.unit_type=U[kind]
    u.move_type={'VEH_GROUND':M.TRACK,'VEH_NAVAL':M.HULL,'VTOL':M.VTOL,'AERO':M.FLY,'DS':M.FLY}.get(kind,M.BIPED)
    if kind in ('VTOL','AERO','DS'): u.set_status(S.LANDED)
    for key,val in values.items(): setattr(u,key,val)
    return u

def mount(w,category='energy',section=4,critical=0):
    from entities.mech import WeaponState
    names={'energy':'IS.MediumLaser','ballistic':'IS.AC/5','autocannon':'IS.AC/5','missile':'IS.LRM-5','flamer':'IS.Flamer','PCOMBAT':'PC.Rifle'}
    weapon=get_weapon(names.get(category,category))
    assert weapon is not None,category
    u=unit(w); size=weapon.crits if u.unit_type==U.MECH else 1
    for slot in u.sections[section].criticals[critical:critical+size]: slot.type=i2weapon(weapon.index)
    u.weapons.append(WeaponState(section=section,critical=critical,weapon_idx=weapon.index))
    w.update(weapon=weapon,section=section,slot=critical)
    return weapon

@step(r'a fresh damage session with source defaults and event time zero')
def fresh(w):
    w.clear();w['damage_session']=DamageSession({'actions':[],'config':{'periodic_updates':False},'units':[{'name':'u'},{'name':'enemy','team':2,'at':[2,4,0]}]})
    w['section']=4
    for u in session(w).units.values():
        for section in u.sections:
            for slot in section.criticals: slot.type=0
    for name in ('critical_rolls','damage_entry'): draw(w,name,[7]*100)
    draw(w,'critical_slot',[0]*100);draw(w,'pilot_rolls',[12]*100)

from . import armor, commands_steps, locations, components, recovery, vehicles, enhanced
