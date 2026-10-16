"""Sink switching, integrated heat and applied injury APS fixtures."""
from .context import *
from entities.mech import Specials
from entities.crittypes import i2special,Special
from systems import heat as rules
from systems.heat_control import heat_cutoff
from core.game_loop import register_special_objects


def sinks(w,technology,capacity,disabled,weapon):
    u=w['unit']
    tech={'SINGLE':Specials.NONE,'DOUBLE':Specials.DOUBLE_HEAT_TECH,'CLAN':Specials.CLAN_TECH}[technology]
    u.specials=tech
    capacity=int(capacity)
    if capacity% (2 if tech else 1) or not 0<=int(disabled)<=capacity:
        raise ValueError('invalid sink capacity')
    u.num_sinks=capacity//(2 if tech else 1)
    u.disabled_sinks=int(disabled)
    u.weap_heat=float(weapon)


step(r'a stationary mech with sink technology (SINGLE|DOUBLE|CLAN) capacity (\d+) disabled capacity (\d+) and weapon heat '+N)(sinks)


@step(r'heat cutoff is (engaged|disengaged)')
def cutoff(w,value):
    flag(w['unit'],C.HEATCUTOFF,value=='engaged','crit_status')


@step(r'(?:one|1) heat update occurs before the overheat check is due')
def update(w):
    for _ in range(1):
        invoke(w,rules.full_heat_update,w['unit'],2,in_water=w.get('water',False),water_depth=w['unit'].z,
               map_temperature=w.get('temperature',25) if w.get('special',False) else 25)


@step(r'(\d+) heat updates occur before the overheat check is due')
def updates(w,count):
    for _ in range(int(count)):
        update(w)


@step(r'disabled capacity is (\d+) dissipation is '+N+r' and current heat is '+N)
def values(w,disabled,dissipation,heat):
    equal(w['unit'].disabled_sinks,int(disabled));near(w['unit'].minus_heat,dissipation);near(w['unit'].heat,heat)


@step(r'disabled capacity is (\d+) and current heat is zero')
def disabled(w,value):
    equal(w['unit'].disabled_sinks,int(value));near(w['unit'].heat,0)


@step(r'a mech with cutoff initially '+B)
def initial(w,value):
    flag(w['unit'],C.HEATCUTOFF,boolean(value),'crit_status')


@step(r'the pilot requests heatcutoff (\d+) times and advances (\d+) seconds')
def request(w,count,seconds):
    for _ in range(int(count)):
        w['accepted']+=heat_cutoff(w['engine'],w['unit'],w['unit'].pilot)[0]
    advance(w,seconds)


@step(r'exactly one cutoff request was accepted')
def accepted(w):
    equal(w['accepted'],1)


@step(r'cutoff is '+B+r' and a cutoff transition is '+B)
def cutoff_result(w,active,pending):
    equal(w['unit'].has_crit_status(C.HEATCUTOFF),boolean(active))
    equal(w['unit']._cutoff_event is not None,boolean(pending))


def legslots(w,count):
    u=w['unit']
    for loc in (Location.LLEG,Location.RLEG):
        for slot in u.sections[loc].criticals:
            if slot.type==i2special(Special.HEAT_SINK):slot.type=0
    for i in range(int(count)):
        u.sections[(Location.LLEG,Location.RLEG)[i%2]].criticals[i//2].type=i2special(Special.HEAT_SINK)


@step(r'a stationary single-sink mech with capacity 10 disabled capacity 8 four functional leg sink slots and weapon heat '+N)
def submerged(w,weapon):
    sinks(w,'SINGLE',10,8,weapon);legslots(w,4)


@step(r'the upright mech is at depth one in water with heat cutoff engaged')
def shallow(w):
    terrain(w,'WATER',-1);w['unit'].z=-1;w['water']=True;cutoff(w,'engaged')


@step(r'a stationary mech with capacity 10 no disabled sinks old heat '+N+r' weapon heat 20 and started state '+B)
def retained(w,old,started):
    sinks(w,'SINGLE',10,0,20);w['unit'].heat=float(old);flag(w['unit'],S.STARTED,boolean(started))


@step(r'previous plus heat is 20 with no engine or environment heat')
def previous(w):
    w['unit'].plus_heat=20;w['unit'].engine_heat=0


@step(r'the standard dispatcher advances (\d+) seconds(?: without a movement event)?')
def dispatch(w,seconds):
    register_special_objects(w['engine']);advance(w,seconds)


@step(r'current heat is '+N+r' and retained weapon heat is '+N)
def heat_retained(w,heat,retained):
    near(w['unit'].heat,heat);near(w['unit'].weap_heat,retained)


@step(r'a stationary mech with active capacity (\d+) weapon heat 20 jellied state '+B+r' and special-map rules '+B)
def environment(w,capacity,jellied,special):
    sinks(w,'SINGLE',capacity,0,20);flag(w['unit'],C.JELLIED,boolean(jellied),'crit_status');w['special']=boolean(special)


@step(r'map temperature is '+N+r' Celsius with no water bonus')
def temperature(w,value):
    w['temperature']=int(value)


@step(r'dissipation is '+N+r' and current heat is '+N)
def result(w,dissipation,heat):
    near(w['unit'].minus_heat,dissipation);near(w['unit'].heat,heat)


@step(r'a mech with active capacity (\d+) functional submerged leg sink slots (\d+) and weapon heat 20')
def water_sinks(w,capacity,count):
    sinks(w,'SINGLE',capacity,0,20);legslots(w,count)


@step(r'the mech is in water at Z '+N+r' and fallen state '+B)
def water(w,z,fallen):
    terrain(w,'WATER',z);w['unit'].z=int(z);w['water']=int(z)<0;flag(w['unit'],S.FALLEN,boolean(fallen))


@step(r'a stationary started mech without ammo at current heat '+N+r' and last overheat check tick 0')
def overheat(w,value):
    w['unit'].heat=float(value);w['unit']._last_overheat_tick=0


@step(r'the due overheat evaluation runs at event tick (\d+) with shutdown roll (\d+)')
def check(w,tick,roll):
    with patch('systems.heat.roll_2d6',return_value=int(roll)):
        invoke(w,rules.check_overheat,w['unit'],int(tick))


@step(r'the mech remains started '+B+r' and last overheat check tick is (\d+)')
def checked(w,started,last):
    equal(w['unit'].is_started,boolean(started));equal(w['unit']._last_overheat_tick,int(last))


@step(r'a mech with destroyed life support and no prior pilot injuries')
def life(w):
    w['unit'].set_crit_status(C.LIFE_SUPPORT_DESTROYED)


@step(r'a heat update produces heat '+N+r' at event tick (\d+)')
def injury(w,heat,tick):
    w['unit'].weap_heat=float(heat)+w['unit'].effective_heat_sinks
    with patch('systems.heat.roll_2d6',return_value=12):
        invoke(w,rules.full_heat_update,w['unit'],int(tick))


@step(r'the pilot has (\d+) applied heat injuries')
def injured(w,count):
    equal(w['unit'].pilot_hits,int(count))
