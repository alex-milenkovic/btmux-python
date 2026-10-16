from entities.mech import Specials as S,FireMode as F,AmmoMode as A,CritStatus,MechStatus
from systems import construction_weight as mass
from . import step,eq,unit,part,tech


@step(r'a (.+) mech of (\d+) tons has zero original and current internals everywhere')
def internals(w,move,tons):unit(w,'Mech',move,tons)


@step(r'internal consistency runs')
def check(w):mass.internal_check(w['unit'])


@step(r'center side arm leg and head internals become (\d+) (\d+) (\d+) (\d+) and 3 in both current and original state')
def checked(w,center,side,arm,leg):
    a,s,c,l=map(int,(arm,side,center,leg));expected=[a,a,s,s,c,l,l,3]
    for field in ('internal','internal_orig'):eq([getattr(sec,field) for sec in w['unit'].sections],expected)


@step(r'a 50-ton biped left arm has original internal (\d+) and current internal (\d+)')
def damaged(w,original,current):
    u=unit(w);u.sections[0].internal_orig=int(original);u.sections[0].internal=int(current)


@step(r'left arm original and current internal are 8 and (\d+)')
def damage_kept(w,current):eq((w['unit'].sections[0].internal_orig,w['unit'].sections[0].internal),(8,int(current)))


@step(r'a (.+) of (\d+) tons has front original internal (\d+) and current internal 0')
def front(w,kind,tons,original):unit(w,kind,tons=tons).sections[2].internal_orig=int(original)


@step(r'front original and current internals are (\d+) and (\d+)')
def front_checked(w,original,current):eq((w['unit'].sections[2].internal_orig,w['unit'].sections[2].internal),(int(original),int(current)))


@step(r'a vehicle of (\d+) tons moving by (.+)')
def vehicle(w,tons,move):unit(w,'Vehicle',move,tons)


@step(r'its suspension factor is requested')
def suspension(w):w['result']=mass.suspension(w['unit'])


@step(r'the factor is (\d+)')
def suspended(w,value):eq(w['result'],int(value))


@step(r'a (.+) moving by (.+) has stored engine rating (\d+) and engine tech (.+)')
def engine(w,kind,move,rating,flags):
    u=unit(w,kind,move);u.engine_rating=int(rating);u.max_speed=0;tech(u,flags)


@step(r'construction engine weight is calculated')
def engine_weight(w):w['result']=mass.engine_weight(w['unit'])


@step(r'calculated weight in1024ths is (-?\d+)')
def total(w,value):eq(w['result'],int(value))


@step(r'a (.+) of (\d+) tons has tech (.+)')
def crit_unit(w,kind,tons,flags):tech(unit(w,kind,tons=tons),flags)


@step(r'construction crit weight is requested for (.+)')
def critical(w,name):w['result']=mass.crit_weight(w['unit'],part(name))


def minimal(w):
    u=unit(w);u.engine_rating=200;u.original_sinks=10
    for sec,value in zip(u.sections,(10,10,15,15,20,10,10,10)):sec.internal=sec.internal_orig=value
    return u


@step(r'a 50-ton mech has engine200 original internal100 current internal100 no armor no equipment and ten original sinks')
def simple(w):minimal(w)


@step(r'its cockpit gyro structure and cargo are (.+) (.+) (.+) and (\d+)')
def components(w,cockpit,gyro,structure,cargo):
    u=w['unit'];u.specials2|=0x2000000 if cockpit=='small' else 0
    u.specials2|={'XL':0x200000,'Hardened':0x400000,'Compact':0x800000}.get(gyro,0)
    tech(u,structure);u.cargo_space=int(cargo)


@step(r'design weight is requested')
def design(w):w['result']=mass.weight(w['unit'],0)['total']


@step(r'a mech with no other items has (\d+) identical AC5 ammo bins of (\d+) rounds each and mode (.+) in a surviving section')
def ammo(w,count,rounds,mode):
    u=minimal(w)
    for slot in u.sections[0].criticals[:int(count)]:
        slot.type=part('Ammo_IS.AC/5');slot.data=int(rounds)
        if mode=='halfton':slot.firemode=F.HALFTON_MODE
        slot.ammomode={'AP':A.AC_AP_MODE,'caseless':A.AC_CASELESS_MODE}.get(mode,0)


@step(r'its ammo-only design contribution and current ammo weight are requested')
def ammo_weight(w):w['result']=(mass.weight(w['unit'],0)['terms'].get('equipment',0),mass.ammo_weight(w['unit']))


@step(r'the values in1024ths are (\d+) and (\d+)')
def ammo_total(w,design,current):eq(w['result'],(int(design),int(current)))


@step(r'a (alive|destroyed) unit of50 tons has cache flag ([01]) cached value (\d+) and computed weight (\d+) with dynspeed ([01])')
def cache(w,state,valid,cached,computed,dynamic):
    u=w['unit'];u.construction_managed=False;u.status=MechStatus.DESTROYED if state=='destroyed' else 0
    u.crit_status=CritStatus.OWEIGHT_OK if valid=='1' else 0;u.rtons=int(cached)
    w.update(computed=int(computed),dynamic=bool(int(dynamic)),calls=0)


@step(r'get_weight is called')
def cached(w):
    def compute():w['calls']+=1;return w['computed']
    w['result']=mass.get_weight(w['unit'],w['dynamic'],compute)


@step(r'the weight is (\d+) and computation count is (\d+)')
def cached_result(w,value,calls):eq((w['result'],w['calls']),(int(value),int(calls)))


@step(r'a (.+) of (\d+) tons moving by (.+) has engine rating (\d+) original internal (\d+) current internal (\d+) in front only with zero armor items and real sinks')
def vehicle_total(w,kind,tons,move,rating,original,current):
    u=unit(w,kind,move,tons);u.engine_rating=int(rating);u.sections[2].internal_orig=int(original);u.sections[2].internal=int(current)


@step(r'weight uses interactive (-?\d+)')
def interactive(w,value):w['result']=mass.weight(w['unit'],int(value))['total']


@step(r'a Mech with (\d+) total original armor and armor technology (.+)')
def armor(w,value,flags):
    u=minimal(w);u.sections[0].armor_orig=int(value);tech(u,flags)


@step(r'its design armor weight contribution is calculated')
def armor_weight(w):w['result']=mass.weight(w['unit'],0)['terms']['armor']
