"""Normal APS bindings: isolated live state, production operations, independent assertions."""
import re
from core.game_loop import GameEngine
from core.randomness import use_source,use_simulation
from entities.map import GameMap
from entities.mech import Mech,UnitType as U,MoveType as M,MechStatus as S,FireMode as F,AmmoMode as A,SectionConfig as C,Specials
from entities.crittypes import i2special,i2weapon,i2ammo,Special
from entities.weapon import get_weapon,WEAPON_CATALOG
from data.characters import CharacterStore
from data.construction_catalog import source_part,source_id
from systems.characters import set_value
from systems.economic_inventory import InventoryStore
from systems.technician import Technician
from systems.repair_jobs import RepairJobs
from systems.repair_work import RepairWork
from systems.repair_reports import RepairReports
from systems.cargo_commands import CargoCommands

BACKGROUND='the repair economy source contract and isolated shared engine fixture'


def base(w):
    w.clear();w.update(repair_economy=True,engine=GameEngine(),streams={},draws=[],checks={})
    e=w['engine'];e.randomness.mt.seed(1)
    board=GameMap(30,30);board._id=1000;board.name='hangar';board.mapvis=60;board.maxvis=100;board.maplight=2
    e.register_entity(board);w['board']=board
    u=Mech();u._id=10;u.name='repair unit';u.contact_id='UU';u._engine=e;u.repair_stall=True
    u.in_character=False;u.measured_mass=u.tonnage*1024;u.location=1000;u.set_hex_position(10,10)
    for sec in u.sections:sec.armor=sec.armor_orig=10;sec.internal=sec.internal_orig=10
    board.add_mech(u);e.register_entity(u);w['u']=u
    chars=CharacterStore();chars.create(7,'Technician',location=10,tech=True,is_player=True,connected=True)
    actor=chars.actor(7);u.command_actor=u.pilot=actor;w['actor']=actor;w['characters']=chars
    for attr in ('Build','Reflexes','Intuition','Learn','Charisma'):set_value(chars,7,attr,5)
    for name in ('Technician-Battlemech','Technician-Mechanic','Technician-Aerospace','Technician-Weapons'):set_value(chars,7,name,0)
    inv=InventoryStore();inv.register(1000,board,in_character=False);inv.register(10,u);inv.register(7,actor)
    w['inventory']=inv;w['tech']=Technician(e,inv);w['jobs']=RepairJobs(e,w['tech'],inv)
    w['work']=RepairWork(w['jobs']);w['reports']=RepairReports(w['work']);w['cargo']=CargoCommands(inv)


def invoke(w,fn,*args,**kwargs):
    def source(name,lo,hi,fallback):
        if name in w['streams']:
            assert w['streams'][name],('Exhausted stream',name)
            value=w['streams'][name].pop(0);assert lo<=value<=hi,(name,value,lo,hi)
        else:value=fallback()
        w['draws'].append((name,value));return value
    with use_simulation(w['engine'].randomness),use_source(source):return fn(*args,**kwargs)


def attempt(w,fn,*args,**kwargs):
    try:w['result']=invoke(w,fn,*args,**kwargs);w['error']=''
    except ValueError as error:w['result']=None;w['error']=str(error)
    return w['result']


def command(w,name,text=''):
    return attempt(w,w['work'].command,w['actor'],w['u'],name,text)


def check(w,text,value):w['checks'][text]=value


def advance(w,seconds):
    # Run the engine queue one second at a time so recurring points use real deadlines.
    for _ in range(seconds):
        w['engine'].sim_now+=1;w['engine'].events.advance_tick();invoke(w,w['engine'].events.run_events)


def stock(w,part,count,brand=0,identity=1000):w['inventory'].set(identity,source_part(part) if isinstance(part,str) else part,brand,count)


def gun(w,width=2,loc=4,pos=0,brand=0):
    weapon=next(v for v in WEAPON_CATALOG.values() if v.crits==width and v.name.startswith('IS.') and source_part(v.name)>0)
    for index in range(pos,min(12,pos+(width if w['u'].unit_type==U.MECH else 1))):
        slot=w['u'].sections[loc].criticals[index];slot.type=i2weapon(weapon.index);slot.brand=brand
    return weapon


def skill(w,target,name='Technician-Battlemech'):
    # Mental attributes sum10, so the real source BTH is18-10-level.
    set_value(w['characters'],7,name,8-target)


def execute(w,text):
    if text==BACKGROUND:base(w);return
    match=re.fullmatch(r'repair economy state (.+)',text)
    if match:w['initial']=match[1];return
    match=re.fullmatch(r'the repair economy user performs (.+)',text)
    if match:
        from . import access_time,events,economy,parts,structure,ammo,scrap,inventory,cargo,towing,workflows
        for module in (workflows,access_time,events,economy,parts,structure,ammo,scrap,inventory,cargo,towing):
            if module.run(w,w['initial'],match[1]):return
        raise AssertionError('Unbound repair operation: '+w['initial']+' / '+match[1])
    match=re.fullmatch(r'the repair economy observation is (.+)',text)
    if match:
        key=match[1];assert key in w['checks'],('Missing observation',w['initial'],key,list(w['checks']))
        value=w['checks'][key];assert value() if callable(value) else value,(w['initial'],key,w.get('result'),w.get('error'));return
    raise AssertionError('Unbound repair economy step: '+text)
