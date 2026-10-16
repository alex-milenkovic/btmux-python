"""Shared real-engine fixtures and strict assertions for heat acceptance."""
import random
from contextlib import ExitStack,redirect_stdout
from io import StringIO
from unittest.mock import patch
from core.randomness import use_source
from core.game_loop import GameEngine
from entities.mech import Mech,MechStatus as S,MechStatus2 as S2,CritStatus as C,Location
from entities.map import GameMap
from entities.pilot import Pilot
from tools.path_cost_inputs import terrain_value

BINDINGS=[]
N=r'(-?\d+(?:\.\d+)?)'
B=r'(True|False)'


def step(pattern):
    def decorate(function):
        BINDINGS.append((pattern,function))
        return function
    return decorate


from acceptance.assertions import boolean, equal, near


def flag(unit,flag,value,word='status'):
    current=getattr(unit,word)
    setattr(unit,word,current|flag if value else current&~flag)


@step(r'a fresh heat session with standard ready units and independent clocks')
def fresh(w):
    random.seed(0)
    u=Mech.create_test_mech()
    u.name='unit'
    u.set_status(S.STARTED)
    u.pilot=Pilot()
    u.set_hex_position(3,3)
    u.measured_mass=u.tonnage*1024
    board=GameMap(12,12)
    board.grav=100
    board.add_mech(u)
    engine=GameEngine()
    engine.register_entity(u)
    u._engine=engine
    w.update(unit=u,map=board,engine=engine,dice={},rolls=[],accepted=0)


def terrain(w,name,elevation=0):
    u=w['unit'];board=w['map']
    board.set_terrain(u.x,u.y,terrain_value(name))
    board.set_elevation(u.x,u.y,abs(int(elevation)))
    u.elev=abs(int(elevation))


def invoke(w,function,*args,**kwargs):
    from systems import piloting,stagger,stability
    original=piloting.make_piloting_roll
    def observe(*a,**k):
        result=original(*a,**k)
        w['rolls'].append(dict(modifier=a[1] if len(a)>1 else k.get('modifier',0),roll=result.roll,success=result.success))
        return result
    def dice(name,lo,hi,fallback):
        value=w['dice'].get(name)
        if isinstance(value,list):
            if not value:
                raise ValueError('exhausted dice: '+name)
            value=value.pop(0)
        if value is None:
            return fallback()
        if not lo<=value<=hi:
            raise ValueError('dice outside actual range: '+name)
        return value
    captured=StringIO()
    with ExitStack() as stack:
        stack.enter_context(use_source(dice))
        for module in (stagger,stability):
            stack.enter_context(patch.object(module,'make_piloting_roll',side_effect=observe))
        stack.enter_context(redirect_stdout(captured))
        result=function(*args,**kwargs)
    assert 'raised exception:' not in captured.getvalue().lower(),captured.getvalue()
    return result


def advance(w,seconds):
    return invoke(w,w['engine'].run_ticks,int(seconds))


@step(r'the engine advances (\d+) seconds?')
def advance_step(w,seconds):
    advance(w,seconds)
