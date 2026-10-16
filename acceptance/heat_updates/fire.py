"""Advanced fire table, side events and water lifecycle APS steps."""
from .context import *
from entities.mech import UnitType,MoveType
from systems import vehicle_fire as rules
from systems.missile import heat_effect,inferno_burn,water_extinguish_inferno
from core.game_loop import GameEngine
from entities.map import SMOKE


@step(r'advanced vehicle fire is enabled for class (VEH_GROUND|VTOL) movement (TRACK|WHEEL|HOVER|VTOL)')
def advanced(w,kind,movement):
    u=w['unit'];u.unit_type=UnitType[kind];u.move_type=MoveType[movement]
    w['engine'].advanced_vehicle_fire=True
    for section in u.sections:section.internal=section.armor=1000


@step(r'external non-inferno heat reaches the vehicle with fire roll (\d+) and section damage dice (\d+)')
def external(w,roll,die):
    w['dice'].update(fire_rolls=int(roll),fire_damage=int(die),motive_rolls=8)
    from unittest.mock import patch
    from systems.vehicle_combat import motive_system_hit
    def record(*args,**kwargs):
        w['motive']=True
        return motive_system_hit(*args,**kwargs)
    w['armor_before']=sum(s.armor for s in w['unit'].sections)
    with patch('systems.vehicle_combat.motive_system_hit',side_effect=record):
        invoke(w,heat_effect,w['engine'],None,w['unit'],1)


@step(r'the fire response is (NONE|MOTIVE_HIT|SECTION_DAMAGE|BURNING)')
def response(w,expected):
    actual='BURNING' if rules.burning_sides(w['unit']) else 'MOTIVE_HIT' if w.get('motive') else 'SECTION_DAMAGE' if sum(s.armor for s in w['unit'].sections)<w['armor_before'] else 'NONE'
    equal(actual,expected)


@step(r'a tracked ground vehicle with advanced vehicle fire enabled and exactly one live side having 100 front armor and 100 internal')
def one_side(w):
    advanced(w,'VEH_GROUND','TRACK')
    for section in w['unit'].sections:section.internal=0
    w['unit'].sections[0].internal=w['unit'].sections[0].armor=100


@step(r'inferno starts a side burn with initial die (\d+) and the next burn die is (\d+)')
def inferno(w,initial,next_die):
    w['dice']['fire_damage']=[int(initial),int(next_die)]
    invoke(w,heat_effect,w['engine'],None,w['unit'],1,True)


@step(r'that side has lost (\d+) armor and pending side burns number (\d+)')
def side_result(w,damage,pending):
    equal(100-w['unit'].sections[0].armor,int(damage));equal(len(rules.burning_sides(w['unit'])),int(pending))


@step(r'a vehicle with one persistent side fire sufficient armor and started state '+B)
def persistent(w,started):
    one_side(w);w['unit'].sections[0].armor=1000;w['dice']['fire_damage']=3
    invoke(w,rules.start_burn,w['engine'],w['unit']);flag(w['unit'],S.STARTED,boolean(started))


@step(r'the pilot requests extinguish (\d+) times and advances (\d+) seconds')
def request(w,count,seconds):
    for _ in range(int(count)):
        w['accepted']+=rules.extinguish(w['engine'],w['unit'],w['unit'].pilot)[0]
    advance(w,seconds)


@step(r'accepted extinguish commands number (\d+) burning is '+B+r' and extinguishing is '+B)
def extinguish_result(w,count,burning,pending):
    equal(w['accepted'],int(count));equal(bool(rules.burning_sides(w['unit'])),boolean(burning));equal(getattr(w['unit'],'_extinguish_event',None) is not None,boolean(pending))


@step(r'a jellied mech with a live inferno expiry in (\d+) seconds')
def jelly(w,duration):
    inferno_burn(w['engine'],w['unit'],int(duration))


@step(r'it enters terrain (WATER|ICE|BRIDGE|HIGHWATER) with signed elevation (-?\d+) Z (-?\d+) and fallen state '+B)
def enter(w,name,elevation,z,fallen):
    terrain(w,name,elevation);w['unit'].z=int(z);flag(w['unit'],S.FALLEN,boolean(fallen))
    water_extinguish_inferno(w['engine'],w['unit'])


@step(r'jellied is '+B+r' and a 120 second steam decoration is '+B)
def steam(w,jellied,steam):
    equal(w['unit'].has_crit_status(C.JELLIED),boolean(jellied))
    decoration=w['map'].decorations.get((w['unit'].x,w['unit'].y))
    equal(decoration is not None,boolean(steam))
    if decoration:
        equal(decoration['event'].tick-w['engine'].tick,120);equal(decoration['terrain'],SMOKE)


@step(r'a pending inferno expiry is '+B)
def expiry(w,value):
    equal(getattr(w['unit'],'_burn_event',None) is not None,boolean(value))
