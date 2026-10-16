"""Normal APS bindings for the approved pilots card; independent QA is separate."""
import tempfile
from pathlib import Path
from core.randomness import RandomState,use_simulation,use_source
from data.characters import CharacterStore
from systems import characters as c
from entities.mech import Mech

BINDINGS=[]
def step(pattern):
    def decorate(fn):BINDINGS.append((pattern,fn));return fn
    return decorate

def eq(actual,expected):assert actual==expected,(actual,expected)
def truth(text):return text=='True'
def base(w):
    w.clear();w['pilots']=True;w['temp']=tempfile.TemporaryDirectory(dir='./tmp')
    w['root']=Path(w['temp'].name);w['store']=CharacterStore(w['root']/'characters')
    w['store'].create(101,'Alice');w['player']=101;w['unit']=Mech();w['random']=RandomState(1);w['calls']=[]

def values(w,**values):
    for name,val in values.items():c.set_value(w['store'],101,name,val)

def draws(w,values,fn,*args,**kwargs):
    source_values=list(values);pending=iter(source_values);calls=[]
    def source(name,lo,hi,fallback):
        try:value=next(pending)
        except StopIteration:raise AssertionError('Unexpected draw '+name)
        assert lo<=value<=hi,(name,lo,hi,value)
        calls.append(name);return value
    try:
        with use_simulation(w['random']),use_source(source):return fn(*args,**kwargs)
    finally:
        w['calls']=calls;eq(len(calls),len(source_values))

def numbers(text):return [] if text=='none' else list(map(int,text.split(',')))

from . import personal,skills,character,experience,health,awards,personnel,ejection,battle_armor,workflows

@step(r'result is (\S+)')
def result_dispatch(w,expected):
    if w.get('family') in ('boarding','carriers'):return personnel.result(w,expected)
    if w.get('family')=='ejection':return ejection.result(w,expected)
    if w.get('family') in ('battle_armor','hiding'):return battle_armor.result(w,expected)
    raise AssertionError(('Unknown result family',w.get('family'),expected))
