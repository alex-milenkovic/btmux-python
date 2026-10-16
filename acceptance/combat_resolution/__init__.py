"""Combat APS steps invoke production rules with deterministic input streams."""
from tools.damage_criticals import DamageSession
from physics.hexmath import hex_to_float

BINDINGS=[]
def step(pattern):
    def register(fn):
        BINDINGS.append((pattern,fn))
        return fn
    return register

def eq(actual, expected):
    assert actual==expected,(actual,expected)

def session(w): return w['combat_session']
def unit(w,name='u'): return session(w).units[name]
def call(w,fn,*args,**kwargs): return session(w).invoke(fn,*args,**kwargs)
def dice(w,name,values): session(w).streams[name]=list(values)
def armor(u): return sum(s.armor+s.rear for s in u.sections)
def position(u,x,y,z=0):
    u.x,u.y,u.z=x,y,z
    u.fx,u.fy=hex_to_float(x,y)
    u.fz=z*64.5

@step(r'a fresh combat session with source defaults and event time zero')
def fresh(w):
    w.clear()
    w['combat_session']=DamageSession(dict(actions=[],map={'size':[12,12]},
        config={'periodic_updates':False},units=[{'name':'u','at':[3,3,0]},
                                                {'name':'v','at':[3,2,0],'team':2}]))
    for u in session(w).units.values():
        for section in u.sections:
            section.armor=section.armor_orig=200
            section.rear=section.rear_orig=200
            section.internal=section.internal_orig=100
            for slot in section.criticals:
                slot.type=0
        u.weapons=[]
    for name in ('damage_entry','critical_rolls','hit_location_rolls'):
        dice(w,name,[7]*500)
    dice(w,'physical_location',[3]*500)
    dice(w,'pilot_rolls',[12]*100)

from . import area,modes,commands,equipment,ammunition,firing,groups,ranges,impacts,missiles,pods,physicals,dfa,charge,locations,integration
