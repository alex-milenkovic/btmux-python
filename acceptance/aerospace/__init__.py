"""Normal APS bindings for aerospace: real fixtures, operations, observations."""
import re
from core.game_loop import GameEngine
from core.randomness import use_source,use_simulation
from data.characters import CharacterStore
from entities.map import GameMap
from entities.mech import Mech,UnitType as U,MoveType as M,MechStatus as S,CritStatus as C
from systems.occupants import Personnel

BINDINGS=[]
BACKGROUNDS={
'a registered craft on a clear level landing zone with real event scheduling':'takeoff',
'a registered craft with source terrain and a flat six-neighbor landing zone':'landing',
'an airborne registered craft with maximum 60 and source float vector arithmetic':'flight',
'a registered craft with real pilot heat sensor event and personnel services':'updates',
'a dropship with actual nearby recipients and map decorations':'exhaust',
'a craft whose payload is represented by real critical slots and inventory':'payload',
'an airborne bomber on a registered map with real timed blast damage':'bombing',
'real dropship door criticals bay maps occupants and map transitions':'bays',
'an OOC dropship with two real turret rooms distinct connected gunners and a separate parent pilot':'turrets',
 'the documented aerospace CLI with genuine templates real maps and ordinary commands':'workflows'}


def step(pattern):
    def add(fn):BINDINGS.append((pattern,fn));return fn
    return add


def eq(a,b):assert a==b,(a,b)


def near(a,b):assert abs(a-float(b))<1e-4,(a,b)


def base(w,family):
    w.clear();w.update(aerospace=True,family=family,engine=GameEngine(),store=CharacterStore(),units={},streams={},draws=[],checks={})
    e=w['engine'];e.randomness.mt.seed(1)
    # These source fixtures supply expanded Gunnery-Laser/Piloting-Biped skills.
    e.extended_gunnery = e.extended_piloting = True
    b=GameMap(30,30);b._id=1000;b.name='main';b.grav=100;b.mapvis=60;b.maxvis=100;b.maplight=2
    e.register_entity(b);w['map']=b;w['personnel']=Personnel(e,w['store'])
    w['u']=make_unit(w,'A',U.DS if family in ('takeoff','exhaust','bays','turrets') else U.AERO)
    if family in ('takeoff','bays','turrets'):w['u'].set_status(S.LANDED)
    if family=='landing':w['u'].unit_type=U.VTOL;w['u'].move_type=M.VTOL;position(w['u'],10,10,1)


def make_unit(w,name,kind=U.MECH):
    u=Mech.create_test_mech(name);u._id=10+len(w['units']);u.contact_id=name[0]*2
    u.unit_type=kind;u.move_type=M.VTOL if kind==U.VTOL else M.FLY if kind in (U.AERO,U.DS,U.SPHEROID_DS) else M.BIPED
    u.status=S.STARTED;u.in_character=False;u.fuel=1000;u.max_speed=60;u.measured_mass=u.tonnage*1024
    u.cargo_inventory=[];u.fuel_orig=1000
    u.specials=0;u.specials2=0;u.crit_status=C.NONE
    w['map'].add_mech(u);u.set_hex_position(10,10);w['engine'].register_entity(u)
    w['personnel'].add(u,1000)
    ident=100+u._id;w['store'].create(ident,name+' pilot',location=u._id,connected=True)
    from systems.characters import set_value
    for key,value in {'Build':5,'Reflexes':4,'Intuition':3,'Learn':2,'Charisma':1,'Piloting-Aerospace':6,'Piloting-Spacecraft':6,'Piloting-Biped':6,'Gunnery-Laser':7}.items():set_value(w['store'],ident,key,value)
    u.pilot=w['store'].actor(ident);w['personnel'].add(u.pilot,u._id)
    w['units'][name]=u
    from systems.los import MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS
    for peer in w['units'].values():
        w['map'].losinfo[u._id,peer._id]=w['map'].losinfo[peer._id,u._id]=MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS
    return u


def position(u,x,y,z=None):
    u.set_hex_position(x,y,u.z if z is None else z)
    u.terrain=u.map.terrain(x,y);u.elev=u.map.elevation(x,y)


def invoke(w,fn,*args,**kwargs):
    def source(name,lo,hi,fallback):
        if name in w['streams']:
            assert w['streams'][name],('exhausted',name)
            value=w['streams'][name].pop(0)
            assert lo<=value<=hi,(name,value,lo,hi)
        else:value=fallback()
        w['draws'].append((name,value,lo,hi));return value
    with use_simulation(w['engine'].randomness),use_source(source):return fn(*args,**kwargs)


def events(w,kind,u=None):return w['engine'].events.pending_events(kind,data=w['u'] if u is None else u)


def messages(w,u=None):
    u=u or w['u']
    return '\n'.join(getattr(u,'movement_messages',[])+getattr(u,'broadcasts',[])+getattr(u.pilot,'inbox',[]))


def check(w,name,value):w['checks'][name]=value


@step(r'the observation is (?!silent with no state or shot change$)(.+)')
def observations(w,text):
    for item in text.split(';'):
        assert item in w['checks'],('missing assertion',w['family'],w.get('fixture'),item,list(w['checks']))
        actual=w['checks'][item]
        assert actual() if callable(actual) else actual,(w.get('fixture'),item,w.get('result'),messages(w))


def execute(w,text):
    if text in BACKGROUNDS:base(w,BACKGROUNDS[text]);return
    for pattern,fn in BINDINGS:
        match=re.fullmatch(pattern,text)
        if match:fn(w,*match.groups());return
    raise AssertionError('Unbound aerospace step: '+text)

from . import flight,payload,bays,turrets,workflows
