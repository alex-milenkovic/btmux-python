"""Physical diagnostics and range eligibility call the production attack path."""
from . import step,unit,session,call,dice,eq,armor,position
from .pods import arms
from .commands import acquire_contacts
from entities.mech import Location as L,Specials,UnitType as U,MechStatus as S
from systems import physical as p

WEIGHTS={'punch':10,'kick':5,'axe':5,'club':5,'sword':10,'mace':4,'saw':7,'claw':7}


@step(r'a 55-ton attacker with intact actuators and heat (\d+) and TSM installed')
def physical_fixture(w,heat):
    arms(w)
    u=unit(w);u.tonnage=55;u.heat=int(heat);u.specials|=Specials.TRIPLE_MYOMER_TECH


@step(r'physical damage diagnostic resolves (\S+) with glance ([01])')
def damage(w,attack,glance):
    w['draw_start']=len(session(w).draws)
    w['physical_result']=call(w,p.physical_damage,unit(w),unit(w,'v'),WEIGHTS[attack],p.PhysicalAttackType[attack.upper()],L.LARM,glance=='1')


@step(r'direct damage is (\d+)')
def damage_result(w,value):eq(w['physical_result'].damage_dealt,int(value))


@step(r'a ready legal physical attack against (MECH|BA|MW)')
def range_fixture(w,kind):
    arms(w)
    unit(w,'v').unit_type={'MECH':U.MECH,'BA':U.BSUIT,'MW':U.MW}[kind]
    unit(w).prefs|=1
    acquire_contacts(w)


@step(r'distance is ([0-9.]+)')
def distance(w,value):
    from physics.hexmath import SCALEMAP
    u,v=unit(w),unit(w,'v')
    v.fx=u.fx;v.fy=u.fy-float(value)*SCALEMAP
    w['physical_result']=call(w,p.physical_attack,u,5,3,p.PhysicalAttackType.KICK,L.RLEG,v,roll=12)


@step(r'range eligibility is (accepted|rejected)')
def range_result(w,expected):
    eq(w['physical_result'].success,expected=='accepted')
    if expected=='rejected':eq(w['physical_result'].message,'Target out of range!')


@step(r'a ready attacker and armored target behind it')
def fallthrough_fixture(w):
    arms(w)
    unit(w).tonnage=55
    position(unit(w,'v'),3,4)


@step(r'hit location is 0 rear is false and location draws consumed are 0')
def location_result(w):
    eq(w['physical_result'].location_hit,0)
    eq(w['physical_result'].is_rear,False)
    eq(sum(d['name'] in ('hit_location_rolls','physical_location') for d in session(w).draws[w['draw_start']:]),0)
