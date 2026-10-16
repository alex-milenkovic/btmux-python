from entities.map import map_update
from entities.mech import MechStatus as S,Location as L,SectionConfig
from systems.map_conditions import set_conditions
from systems.damage import possibly_breach
from . import step,eq,unit,attempt,invoke,run_to


@step(r'a map starts with flags (\d+)')
def flags(w,value): w['map'].flags=int(value)


@step(r'a map starts with flags 16 gravity 100 and temperature 20')
def standard(w): w['map'].flags=16; w['map'].grav=100; w['map'].temp=20


@step(r'setconditions receives (.+)')
def set_value(w,args): attempt(w,set_conditions,w['map'],args.replace(',',' '))


@step(r'map flags are (\d+) gravity is (\d+) and temperature is (-?\d+)')
def values(w,flags,gravity,temp): eq((w['map'].flags,w['map'].grav,w['map'].temp),tuple(map(int,(flags,gravity,temp))))


@step(r'the outcome is (success|gravity-error|temperature-error|vacuum-error|underground-error|arity-error) and invalid requests preserve all existing values')
def validated(w,result):
    if result=='success': eq(w['error'],None)
    else:
        assert ('2 options' if result=='arity-error' else result.split('-')[0]) in w['error'],w['error']
        eq((w['map'].flags,w['map'].grav,w['map'].temp),(16,100,20))


@step(r'an intact unbreached arm belongs to a unit with special (0|1) and vacuum (0|1)')
def breached_setup(w,special,vacuum):
    u=unit(w); w['map'].add_mech(u)
    if special=='1': u.set_status(S.UNDERSPECIAL)
    if vacuum=='1': u.set_status(S.UNDERVACUUM)


@step(r'possibly breach is attempted with next roll (\d+)')
def breach(w,value): w['streams']={'breach_rolls':[int(value)]}; invoke(w,possibly_breach,w['unit'],w['unit'],L.LARM)


@step(r'roll consumption is (unused|used) and breached is (true|false)')
def breach_result(w,used,breached):
    eq(bool(w['draws']),used=='used'); eq(bool(w['unit'].sections[L.LARM].config&SectionConfig.SECTION_BREACHED),breached=='true')


@step(r'a map has initial visibility 10 light 1 and a valid occupant')
def visibility_setup(w):
    w['map'].mapvis=10; w['map'].maplight=1; w['map'].add_mech(unit(w))


@step(r'A_MAPVIS is (.+)')
def config(w,value): w['map'].visibility_config=value.replace(',',' ')


@step(r'map_update executes at event tick 25')
def refresh(w): run_to(w,25); invoke(w,map_update,w['engine'],w['map'])


@step(r'visibility is (\d+) maximum visibility (\d+) light (\d+) wind (-?\d+) speed (-?\d+) and cloudbase (-?\d+)')
def visibility(w,*values): eq(tuple(getattr(w['map'],key) for key in ('mapvis','maxvis','maplight','winddir','windspeed','cloudbase')),tuple(map(int,values)))


@step(r'tick 25 refresh uses A_MAPVIS (.+)')
def message_refresh(w,value): config(w,value); refresh(w)


@step(r'the change message is (absent|abcdef) and cloudbase is (-?\d+)')
def change_message(w,message,cloud):
    eq(w['map'].cloudbase,int(cloud)); eq('abcdef' in w['unit'].movement_messages,message=='abcdef')
