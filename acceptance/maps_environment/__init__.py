"""Normal APS bindings for defined map behavior and ordinary CLI workflows."""
from core.game_loop import GameEngine
from core.randomness import use_source,use_simulation
from entities.map import GameMap
from entities.mech import Mech

BINDINGS=[]
TERRAIN={'grass':' ','water':'~','rough':'%','fire':'&','smoke':':','light-forest':'`','heavy-forest':'"','bridge':'/','ice':'-','road':'#'}


def step(pattern):
    def register(function): BINDINGS.append((pattern,function)); return function
    return register


def eq(actual,expected): assert actual==expected,(actual,expected)


def board(world,width=9,height=9):
    value=GameMap(int(width),int(height)); value._id=1000
    world['engine'].register_entity(value); world['map']=value
    return value


def unit(world,identity=40):
    value=Mech.create_test_mech(); value._id=int(identity)
    world['engine'].register_entity(value); world['unit']=value
    return value


def invoke(world,function,*args,**kwargs):
    def source(name,low,high,fallback):
        values=world.get('streams',{}).get(name)
        if values is not None and not values: raise ValueError('Exhausted acceptance stream '+name)
        value=values.pop(0) if values is not None else low
        world['draws'].append((name,value,low,high))
        return value
    with use_simulation(world['engine'].randomness),use_source(source): return function(*args,**kwargs)


def run_to(world,tick):
    invoke(world,world['engine'].run_ticks,int(tick)-world['engine'].muxevent_tick)


def attempt(world,function,*args,**kwargs):
    world['error']=None
    try: world['result']=invoke(world,function,*args,**kwargs)
    except ValueError as error: world['error']=str(error)


@step(r'a fresh maps environment session with explicit source defaults')
def fresh(world):
    world.clear(); world['maps_environment']=True; world['engine']=GameEngine(); world['draws']=[]
    board(world)


from . import storage,objects,conditions,management,buildings,environment,weather_operations,integration
