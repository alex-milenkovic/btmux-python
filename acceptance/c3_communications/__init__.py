"""Normal APS adapters; fixtures call production behavior and assert observations."""
import re
from core.game_loop import GameEngine
from core.randomness import use_simulation, use_source
from data.characters import CharacterStore
from entities.map import GameMap
from entities.mech import Mech, MechStatus as S, Specials, CritStatus as C
from systems.occupants import Personnel

BINDINGS = []
BACKGROUNDS = {
    'the documented public CLI with real commands clocks templates and local character inboxes': 'workflows',
    'a registered unit with source critical slots and real part functional flags': 'hardware',
    'registered same-team units on a real map with no initial networks': 'membership',
    'a started shooter and command-created eligible network using current LOS and geometry': 'ranges',
    'registered source units with real names equipment and raw display output': 'displays',
    'a registered radio with two channels and relay info scan capabilities': 'channels',
    'source-ordered relay candidates and actual directed radio-range edges': 'routing',
    'local occupants and live map membership with a documented source radio random stream': 'transmission',
    'real registered units local personnel locations and per-recipient inboxes': 'notifications',
}


def step(pattern):
    def wrap(fn):
        BINDINGS.append((pattern,fn))
        return fn
    return wrap


def eq(actual, expected):
    assert actual == expected, (actual, expected)


def base(w, family):
    w.clear()
    w.update(c3_communications=True, family=family, engine=GameEngine(), store=CharacterStore(), units={})
    w['map'] = GameMap(100,30)
    w['map']._id = 1000
    w['map'].mapvis=60; w['map'].maplight=2; w['map'].maxvis=100
    w['engine'].register_entity(w['map'])
    w['world'] = Personnel(w['engine'],w['store'])
    for name in ('A','B','C'):
        make_unit(w,name)


def make_unit(w, name):
    unit = Mech.create_test_mech()
    unit._id = 10 + len(w['units'])
    unit.name = name
    unit.contact_id = name[:1]*2
    unit.team = 1
    unit.status = S.STARTED
    unit.specials = Specials.C3_SLAVE_TECH
    unit.specials2 = 32
    unit.working_c3_masters = 1 if name == 'A' else 0
    unit.in_character = True
    unit.radio_type = 114
    unit.freq,unit.freqmodes,unit.chantitle = [17,0],[0,0],['','']
    from physics.hexmath import hex_to_float
    unit.x = unit.y = 3
    unit.fx,unit.fy = hex_to_float(3,3)
    w['map'].add_mech(unit)
    unit.mapindex = 1000
    w['engine'].register_entity(unit)
    w['world'].add(unit,1000)
    ident = unit._id+100
    w['store'].create(ident,name+' pilot',location=unit._id,connected=True)
    unit.pilot = w['store'].actor(ident)
    w['world'].add(unit.pilot,unit._id)
    w['units'][name] = unit
    from systems.los import MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS
    for peer in w['units'].values():
        w['map'].losinfo[unit._id,peer._id] = MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS
        w['map'].losinfo[peer._id,unit._id] = MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS
    return unit


def unit(w, name='A'):
    return w['units'].get(name) or make_unit(w,name)


def inbox(w,name):
    return getattr(unit(w,name).pilot,'inbox',[])


def draws(w, values, fn, *args, **kwargs):
    pending = list(values)
    calls = []
    def source(name,lo,hi,fallback):
        assert pending, ('Unexpected draw',name,lo,hi)
        value = pending.pop(0)
        assert lo <= value <= hi,(name,lo,hi,value)
        calls.append((name,value))
        return value
    with use_simulation(w['engine'].randomness),use_source(source):
        result = fn(*args,**kwargs)
    eq(pending,[])
    w['draws'] = calls
    return result


def quiet(w, fn, *args, **kwargs):
    with use_simulation(w['engine'].randomness),use_source(lambda name,lo,hi,fallback:lo):
        return fn(*args,**kwargs)


@step('|'.join(re.escape(text) for text in BACKGROUNDS))
def background(w):
    # execute_step supplies the matched background separately.
    raise AssertionError('background dispatched by execute')


def execute(w,text):
    if text in BACKGROUNDS:
        if BACKGROUNDS[text]=='workflows':
            w.clear();w.update(c3_communications=True,family='workflows')
        else:base(w,BACKGROUNDS[text])
        return
    for pattern,fn in BINDINGS:
        match = re.fullmatch(pattern,text)
        if match:
            return fn(w,*match.groups())
    raise AssertionError('Unsupported C3 step: '+text)


@step(r'the observation is (.+)')
def observation(w,expected):
    w['assert_observation'](w,expected)


from . import hardware, membership, channels, displays, ranges, routing, transmission, notifications, workflows
