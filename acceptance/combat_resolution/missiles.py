"""Missile boundaries, glancing rows, and swarm target eligibility."""
from dataclasses import replace
from . import step,unit,session,call,dice,eq,position
from .modes import mount
from .commands import acquire_contacts
from .ammunition import bin_at
from entities.weapon import get_weapon
from entities.mech import MechStatus as S,Specials,AmmoMode as A
from entities.crittypes import i2weapon,i2ammo
from systems import missile as m


@step(r'a target with enabled ready IS AMS heat 0 ammo 2 and recycle value 4')
def ams_fixture(w):
    mount(w,'IS.SRM-6',4)
    v=unit(w,'v');weapon=replace(get_weapon('IS.Anti-MissileSystem'),vrt=4,heat=1)
    session(w).weapon_overrides[weapon.index]=weapon
    v.sections[4].criticals[4].type=i2weapon(weapon.index)
    v.sections[4].criticals[9].type=i2ammo(weapon.index)
    v.sections[4].criticals[9].data=2
    v.specials|=Specials.IS_ANTI_MISSILE_TECH
    v.status|=S.AMS_ENABLED
    v.weap_heat=0
    acquire_contacts(w)
    unit(w).target=v._id


@step(r'boundary (\S+) resolves a salvo of 6 with AMS draw 5')
def boundary(w,name):
    from systems.combat import resolve_attack
    u,v=unit(w),unit(w,'v');weapon=get_weapon('IS.SRM-6')
    if name.startswith('ordinary'):
        if name=='ordinary-swarm-hit':u.sections[4].criticals[4].ammomode=A.SWARM_MODE
        w['result']=call(w,resolve_attack,u,v,weapon,1,7,to_hit_roll=12 if name.endswith('swarm-hit') else 6,
            section=4,w_section=4,w_critical=4,w_ammo_mode=u.sections[4].criticals[4].ammomode,
            cluster_roll=12,ams_roll=5,location_rolls=[7]*6)
    else:
        w['result']=call(w,m.missile_hit_target,u,v,weapon,4,4,7,8 if name.endswith('-hit') else 6,6,12,
                        cluster_roll=12,ams_roll=5,location_rolls=[7]*6)


@step(r'AMS ammo is (\d+) heat is (\d+) recycle is (\d+) and returned shotdown is (\d+)')
def ams_result(w,ammo,heat,recycle,down):
    v=unit(w,'v')
    eq((v.sections[4].criticals[9].data,v.weap_heat,v.sections[4].criticals[4].data,w['result'].ams_shot_down),
       tuple(map(int,(ammo,heat,recycle,down))))


@step(r'ordinary unguided missiles with initial d6 draws 1 2 3')
def index_fixture(w):
    mount(w,'IS.SRM-6',4)
    dice(w,'missile_pre_roll',[1,2,3])


@step(r'fresh cluster roll is (\d+) and glancing is ([01])')
def index(w,roll,glance):
    dice(w,'missile_cluster',[int(roll)])
    w['index']=call(w,m.missile_hit_index,unit(w),get_weapon('IS.SRM-6'),4,4,unit(w,'v'),glance=glance=='1')


@step(r'missile hit-table index is (-?\d+)')
def index_result(w,value):eq(w['index'],int(value))


@step(r'a swarm leaving target A with candidates in roster order B then C')
def swarm_fixture(w):
    from copy import copy
    a=unit(w,'v');b=copy(a);c=copy(a)
    b._id=777;c._id=778;b.name='B';c.name='C'
    a.map.add_mech(b);a.map.add_mech(c)
    # The shooter is outside the local swarm acquisition radius.
    position(unit(w),10,10)
    position(a,3,3);position(b,3,2);position(c,4,3)
    from systems.los import MECHLOSFLAG_SEESP
    a.map.losinfo={(a._id,b._id):MECHLOSFLAG_SEESP,(a._id,c._id):MECHLOSFLAG_SEESP}
    w['swarm_a'],w['swarm_b'],w['swarm_c']=a,b,c


@step(r'B has condition (\S+) and C is an eligible enemy within one hex')
def swarm_condition(w,condition):
    from physics.hexmath import SCALEMAP
    a,b=w['swarm_a'],w['swarm_b'];visited=[a];fof=condition.endswith('SWARM1')
    if condition.startswith('enemy-at-'):
        b.fx=a.fx+float(condition[9:])*SCALEMAP;b.fy=a.fy
        if condition == 'enemy-at-1.9':
            # First float32 position outside the source 1.9 comparison.
            # The preceding float produces 1.8999999761581421 (inside).
            b.fx=1636.8251953125
    elif condition=='already-visited':visited.append(b)
    elif condition=='combat-safe':b.status|=S.COMBAT_SAFE
    elif condition.startswith('friendly-'):b.team=unit(w).team
    elif condition=='no-LOS':a.map.losinfo[(a._id,b._id)]=0
    w['next']=call(w,m.swarm_next_target,unit(w),a,visited,fof)


@step(r'next swarm target is (B|C)')
def next_result(w,name):eq(w['next'].name,name)
