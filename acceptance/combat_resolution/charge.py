"""Charge formulas and collision trigger through the production movement path."""
from . import step,unit,session,call,dice,eq,armor,position
from .pods import arms
from systems import physical as p
from physics.movement import update_movement


def prepare(w):
    arms(w)
    u,v=unit(w),unit(w,'v')
    u.rtons=50*1024;v.rtons=50*1024
    u.facing=u.desired_facing=0;v.facing=v.desired_facing=180
    u.target=v._id;v.contact_id='BB'
    from systems.los import MECHLOSFLAG_SEESP
    session(w).map.losinfo={(u._id,v._id):MECHLOSFLAG_SEESP,(v._id,u._id):MECHLOSFLAG_SEESP}
    dice(w,'charge_rolls',[12]*10)
    w['before']=(armor(u),armor(v))


@step(r'a 50-ton actual-mass attacker at speed ([0-9.]+) and stationary 50-ton enemy')
def classic_fixture(w,speed):
    prepare(w);unit(w).speed=float(speed)


@step(r'old-charge damage is computed without melee advantage')
def classic(w):w['charge']=call(w,p.charge_mech,unit(w),unit(w,'v'))


@step(r'target damage is (\d+) and self damage is 5')
def classic_result(w,damage):
    r=w['charge'];eq(r.attacker_hit,True)
    eq((r.damage_to_target,r.attacker_self_damage),(int(damage),5))
    eq((w['before'][0]-armor(unit(w)),w['before'][1]-armor(unit(w,'v'))),(5,int(damage)))


@step(r'a valid charge selection by (\S+) and a target in the next traversed hex')
def selection(w,how):
    prepare(w)
    u=unit(w);u.speed=u.desired_speed=32.25
    eq(call(w,p.physical_command,u,'charge','' if how=='default-lock' else 'BB')['accepted'],True)


@step(r'movement reaches charge contact with a successful attack and piloting rolls')
def contact(w):
    u=unit(w)
    for _ in range(30):
        call(w,update_movement,u)
        if u.charge_target==-1:break
    w['charge']=u.last_charge_result
    w['after']=armor(unit(w,'v'))
    for _ in range(3):call(w,update_movement,u)


@step(r'charge damage occurs once and attacker speed and charge target clear')
def contacted(w):
    u=unit(w)
    eq(w['charge'].attacker_hit,True)
    assert w['after']<w['before'][1]
    eq(armor(unit(w,'v')),w['after'])
    eq((u.speed,u.desired_speed,u.charge_target),(0,0,-1))
    eq(sum(d['name']=='charge_rolls' for d in session(w).draws),1)


@step(r'mutually charging actual masses 50 and 65 with both speeds one MP facing each other')
def mutual_fixture(w):
    prepare(w)
    u,v=unit(w),unit(w,'v');u.speed=v.speed=10.75;v.rtons=65*1024
    u.charge_target=v._id;v.charge_target=u._id


@step(r'both old-charge rolls hit and all piloting checks succeed')
def mutual(w):classic(w)


@step(r'first attack damage is 11 second attack damage is 7 and each side self damage is (\d+) and (\d+)')
def mutual_result(w,first,second):
    r=w['charge']
    eq((r.damage_to_target,r.damage_to_attacker,r.attacker_self_damage,r.target_self_damage),(11,7,int(first),int(second)))
    eq((w['before'][0]-armor(unit(w)),w['before'][1]-armor(unit(w,'v'))),(7+int(first),11+int(second)))
