"""Source location selection observed through real mounted weapon impacts."""
from . import step,unit,session,call,dice,eq,armor
from .modes import mount
from .commands import acquire_contacts
from entities.mech import Location as L,VehicleLocation as V,UnitType as U,MechStatus as S,Specials
from systems.combat import fire_weapon


@step(r'a real firing fixture with selector condition (\S+)')
def fixture(w,condition):
    mount(w,'IS.MediumLaser',L.RARM)
    acquire_contacts(w)
    u,v=unit(w),unit(w,'v')
    u.target=v._id;u.facing=u.desired_facing=0
    v.facing=v.desired_facing=180
    u.pilot.gunnery=0
    if condition=='upright-MECH-partial-cover':
        from systems.los import MECHLOSFLAG_PARTIAL
        v.status|=S.PARTIAL_COVER
        session(w).map.losinfo[u._id,v._id]|=MECHLOSFLAG_PARTIAL
    elif condition=='MW-shooter-at-MECH-target-height':u.unit_type=U.MW
    elif condition=='BA-shooter-swarming-MECH-target':u.unit_type=U.BSUIT;u.swarm_target=v._id
    elif condition=='critproof-MECH':v.specials|=Specials.CRITPROOF_TECH
    elif condition in ('FASA-ground','advanced-ground'):
        v.unit_type=U.VEH_GROUND
        setattr(session(w).engine,'fasacrit' if condition=='FASA-ground' else 'fasaadvvhlcrit',1)
    w['condition']=condition
    w['before']=armor(v)


@step(r'an otherwise successful shot uses location draw (\d+)')
def fire(w,roll):
    roll=int(roll)
    dice(w,'physical_location',[roll] if roll<=6 else [])
    dice(w,'hit_location_rolls',[roll]*3 if roll>=2 else [])
    dice(w,'swarm_location',[roll] if roll>=2 else [])
    dice(w,'crittable_chance',[1]*5)
    dice(w,'critical_rolls',[7]*20)
    dice(w,'critical_slots',[0]*20)
    w['result']=call(w,fire_weapon,unit(w),unit(w,'v'),0,1,to_hit_roll=12)


@step(r'location family is (\S+)')
def observed(w,family):
    locations={'punch':L.LARM,'kick':L.RLEG,'swarm':L.CTORSO,'normal':L.CTORSO,
               'critproof':L.CTORSO,'FASA-vehicle':V.FSIDE,'advanced-vehicle':V.FSIDE}
    r=w['result'];eq(r.hit,True);eq(r.location,locations[family])
    eq(w['before']-armor(unit(w,'v')),5)
    draws=[d['name'] for d in session(w).draws]
    if family in ('punch','kick'):eq(draws.count('physical_location'),1)
    elif family=='swarm':eq(draws.count('swarm_location'),1)
    else:eq(draws.count('hit_location_rolls'),2 if family in ('critproof','FASA-vehicle','advanced-vehicle') else 1)
    if family=='critproof':eq(r.is_critical,False)


@step(r'a normal NARC hit initially selecting a destroyed MECH left arm and live left torso')
def pod_fixture(w):
    from .ammunition import bin_at
    mount(w,'IS.NarcBeacon',L.RARM)
    bin_at(w,L.LTORSO,10)
    acquire_contacts(w)
    u,v=unit(w),unit(w,'v');u.target=v._id;u.pilot.gunnery=0
    v.facing=v.desired_facing=180
    v.sections[L.LARM].armor=v.sections[L.LARM].internal=0


@step(r'attachment resolves')
def attach(w):
    w['result']=call(w,fire_weapon,unit(w),unit(w,'v'),0,1,to_hit_roll=12,location_roll=10)


@step(r'pod location is (\S+) and destroyed arm has no pod')
def attached(w,location):
    eq(w['result'].location,getattr(L,location))
    eq(bool(unit(w,'v').sections[L.LTORSO].specials & 1),True)
    eq(bool(unit(w,'v').sections[L.LARM].specials & 1),False)
