"""Dump selection, callback cadence and real rear-hit damage bindings."""
from .context import *
from systems import ammo_dump as rules
from entities.weapon import Weapon,WeaponType,register_weapon
from entities.crittypes import i2ammo
from entities.mech import WeaponState,FireMode

WEAPONS=[register_weapon(Weapon('APS.HeatAmmo'+name,weapon_type=WeaponType.TAMMO,damage=10,ammo_per_ton=30)) for name in ('A','B')]


def bin_at(w,loc,pos,rounds,per_ton=30,index=0,damage=10,category='BALLISTIC',salvo=1):
    weapon=WEAPONS[index]
    weapon.weapon_type={'BALLISTIC':WeaponType.TAMMO,'MISSILE':WeaponType.TMISSILE,'ARTILLERY':WeaponType.TARTILLERY,'MISSILE_NO_TABLE':WeaponType.TMISSILE}[category]
    weapon.damage=int(damage);weapon.ammo_per_ton=int(per_ton);weapon.missiles=int(salvo)
    weapon.ammo_full_salvo=None if category == 'MISSILE_NO_TABLE' else int(salvo)
    slot=w['unit'].sections[loc].criticals[pos]
    slot.type=i2ammo(weapon.index);slot.data=int(rounds);slot.firemode=FireMode.NONE
    w['unit'].weapons=[WeaponState(weapon_idx=v.index,section=Location.LARM,critical=i+4) for i,v in enumerate(WEAPONS)]
    return slot


def selector(value):
    return {'WEAPON_A':'0','WEAPON_B':'1'}.get(value,value)


def request(w,value):
    result=rules.mech_dump(w['engine'],w['unit'],selector(value),w['unit'].pilot)
    w['accepted']+=result[0];w['last_accepted']=result[0]
    return result


@step(r'a functional bin with (\d+) rounds of ammunition rated (\d+) rounds per ton')
def one_bin(w,rounds,per_ton):
    w['bin']=bin_at(w,Location.LTORSO,0,rounds,per_ton)


@step(r'the event clock starts at (\d+)')
def start_clock(w,tick):
    w['engine'].events.set_tick(int(tick))


step(r'the pilot requests dump selector (.+)')(request)


@step(r'the bin contains (\d+) rounds and dumping is '+B)
def remaining(w,rounds,pending):
    equal(w['bin'].data,int(rounds));equal(w['unit'].dumping,boolean(pending))


@step(r'LT slot 1 holds weapon A ammo LT slot 2 holds weapon B ammo and RT slot 1 holds weapon A ammo')
def three(w):
    bin_at(w,Location.LTORSO,0,3);bin_at(w,Location.LTORSO,1,3,index=1);bin_at(w,Location.RTORSO,0,3)


@step(r'every bin contains 3 rounds rated 30 per ton and all bins are functional')
def three_defaults(w):
    for loc,pos in ((Location.LTORSO,0),(Location.LTORSO,1),(Location.RTORSO,0)):
        equal(w['unit'].sections[loc].criticals[pos].data,3)


@step(r'LT slot 1 contains (\d+) LT slot 2 contains (\d+) and RT slot 1 contains (\d+) rounds')
def three_result(w,a,b,c):
    equal([w['unit'].sections[loc].criticals[pos].data for loc,pos in ((Location.LTORSO,0),(Location.LTORSO,1),(Location.RTORSO,0))],[int(a),int(b),int(c)])


@step(r'the pilot performs dump workflow (ALL|ALL_STOP|ALL_ALL|BIN_ALL|ALL_BIN|ALL_SHUTDOWN) before advancing 2 seconds')
def workflow(w,actions):
    for action in actions.split('_'):
        if action=='SHUTDOWN':
            from systems.heat import apply_shutdown
            apply_shutdown(w['unit'])
        else:
            request(w,{'ALL':'all','STOP':'stop','BIN':'LT 1'}[action])
    advance(w,2)


@step(r'accepted dump commands number (\d+) the bin contains (\d+) rounds and dumping is '+B)
def lifecycle(w,count,rounds,pending):
    equal(w['accepted'],int(count));remaining(w,rounds,pending)


@step(r'a ready mech with maximum speed 64.5 KPH and ammo condition (LOADED|EMPTY|BROKEN_LOADED)')
def condition(w,value):
    one_bin(w,0 if value=='EMPTY' else 3,30)
    if value=='BROKEN_LOADED':w['bin'].firemode|=FireMode.BROKEN_MODE


@step(r'desired speed is '+N+r' KPH and jumping is '+B)
def moving(w,speed,jumping):
    w['unit'].desired_speed=float(speed);flag(w['unit'],S.JUMPING,boolean(jumping))


@step(r'the dump command is (ACCEPTED|REJECTED) and dumping is '+B)
def command_result(w,outcome,pending):
    equal(w['last_accepted'],outcome=='ACCEPTED');equal(w['unit'].dumping,boolean(pending))


@step(r'a mech dumping a bin of (\d+) rounds each causing (\d+) damage')
def ignite_fixture(w,rounds,damage):
    w['bin']=bin_at(w,Location.LTORSO,0,rounds,damage=damage)
    request(w,'LT 1')


@step(r'all armor and internal values are sufficient to survive both hits')
def armor(w):
    for section in w['unit'].sections:
        section.armor=section.rear=section.internal=1000


def hit(w,location='CT',arc='REAR',cause='WEAPON'):
    from systems.combat import apply_damage_with_transfer
    loc={'CT':Location.CTORSO,'LT':Location.LTORSO,'RT':Location.RTORSO,'LLEG':Location.LLEG}[location]
    before=w['unit'].sections[loc].rear
    weapon=WEAPONS[0] if cause=='WEAPON' else None
    invoke(w,apply_damage_with_transfer,w['unit'],loc,1,arc=='REAR',weapon=weapon,engine=w['engine'])
    ordinary=1 if arc=='REAR' and loc in (Location.CTORSO,Location.LTORSO,Location.RTORSO) else 0
    w['extra']=before-w['unit'].sections[loc].rear-ordinary


step(r'a 1 point hit strikes (CT|LT|RT|LLEG) from (REAR|FRONT) with cause (WEAPON|INTERNAL_EFFECT)')(hit)


@step(r'extra rear armor damage is (\d+) ammo remaining is (\d+) and dumping is '+B)
def ignition_result(w,damage,rounds,pending):
    equal(w['extra'],int(damage));remaining(w,rounds,pending)


@step(r'the only dumping bin has 3 rounds for weapon category (BALLISTIC|MISSILE|ARTILLERY|MISSILE_NO_TABLE) base damage (\d+) and maximum salvo (\d+)')
def category(w,category,base,salvo):
    w['bin']=bin_at(w,Location.LTORSO,0,3,damage=base,category=category,salvo=salvo)
    armor(w);request(w,'LT 1')


@step(r'a weapon hit ignites that dumping stream at a surviving rear torso')
def ignite(w):
    hit(w)


@step(r'LT slot 1 has 3 rounds of A doing 10 damage and RT slot 1 has 4 rounds of B doing 5 damage')
def two(w):
    bin_at(w,Location.LTORSO,0,3,damage=10);bin_at(w,Location.RTORSO,0,4,index=1,damage=5);armor(w)


@step(r'dump selector (.+) is requested and a rear torso weapon hit selects candidate (\d+)')
def selected(w,value,index):
    request(w,value);w['dice']['dump_candidates']=int(index);hit(w)


@step(r'A has (\d+) rounds B has (\d+) rounds and extra rear armor damage is (\d+)')
def selected_result(w,a,b,damage):
    equal(w['unit'].sections[Location.LTORSO].criticals[0].data,int(a));equal(w['unit'].sections[Location.RTORSO].criticals[0].data,int(b));equal(w['extra'],int(damage))


@step(r'no dumping event remains')
def done(w):
    equal(w['unit'].dumping,False);equal(w['unit']._dump_event,None)
