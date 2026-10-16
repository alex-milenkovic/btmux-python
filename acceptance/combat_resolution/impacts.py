"""Impact ordering, glancing, and heat effects through real firing and damage."""
from dataclasses import replace
from . import step,unit,session,call,dice,eq,armor
from .modes import mount
from .commands import acquire_contacts
from .ammunition import bin_at
from entities.weapon import get_weapon
from entities.mech import Location as L,FireMode as F,AmmoMode as A,UnitType as U
from systems.combat import fire_weapon,resolve_attack,calculate_bth


@step(r'a ready loaded weapon with mode (\S+) and attack BTH 2')
def risky(w,mode):
    names={'HOTLOAD':'IS.LRM-5','CASELESS':'IS.AC/5','RFAC':'IS.AC/5','ULTRA':'IS.UltraAC/5'}
    modes={'HOTLOAD':F.HOTLOAD_MODE,'CASELESS':0,'RFAC':F.RFAC_MODE,'ULTRA':F.ULTRA_MODE,
           'RAC2':F.RAC_TWOSHOT_MODE,'RAC4':F.RAC_FOURSHOT_MODE,'RAC6':F.RAC_SIXSHOT_MODE}
    w['weapon']=get_weapon(names.get(mode,'IS.RotaryAC/5'))
    ammo=A.AC_CASELESS_MODE if mode=='CASELESS' else 0
    w['slot']=mount(w,w['weapon'].name,L.LARM,mode=modes[mode],ammo=ammo)
    w['bin']=bin_at(w,L.LTORSO,30)
    w['bin'].ammomode=ammo
    acquire_contacts(w)
    u,v=unit(w),unit(w,'v')
    u.target=v._id
    original=call(w,calculate_bth,u,v,w['weapon'],1,u.pilot.gunnery,L.LARM,w_fire_mode=modes[mode],w_ammo_mode=ammo)
    u.pilot.gunnery+=2-original.total


@step(r'attack roll is (\d+) and caseless explosion roll is (\d+)')
def risky_fire(w,roll,secondary):
    dice(w,'caseless_rolls',[int(secondary)])
    w['result']=call(w,fire_weapon,unit(w),unit(w,'v'),0,1,to_hit_roll=int(roll),cluster_roll=12,location_roll=7)
    eq(w['result'].bth,2)


@step(r'weapon outcome is (\S+) and ordinary tail resources are (unspent|spent)')
def risky_result(w,outcome,tail):
    r=w['result'];u=unit(w)
    if outcome=='AMMOJAMMED':eq(w['slot'].brand>>4,6)
    elif outcome.startswith('destroyed'):
        eq(bool(w['slot'].firemode&F.DESTROYED_MODE),True)
        if outcome.endswith('ammo-spent'):
            eq(w['bin'].data,28 if w['slot'].firemode&F.RFAC_MODE else 29)
            assert u.sections[L.LARM].internal<100
    else:eq(r.shot_aborted,False)
    if tail=='unspent':
        eq(u.weap_heat,0)
        eq(u.shots_fired,0)
    else:
        assert u.weap_heat>0
        eq(u.shots_fired,1)
        eq(w['bin'].data,29)


@step(r'a base 9 damage single-hit weapon with BTH 7 and no armor modifiers')
def glancing(w):
    w['weapon']=replace(get_weapon('IS.MediumLaser'),damage=9)
    acquire_contacts(w)
    unit(w).target=unit(w,'v')._id


@step(r'glancing configuration is (\d+) and attack roll is (\d+)')
def glance(w,mode,roll):
    session(w).engine.glancing_blows=int(mode)
    w['result']=call(w,resolve_attack,unit(w),unit(w,'v'),w['weapon'],1,7,to_hit_roll=int(roll),location_roll=7)


@step(r'applied weapon damage is (\d+)')
def glance_result(w,damage):eq(w['result'].damage_dealt,int(damage))


@step(r'a target with weapon heat 10 and ample armor')
def heat_target(w):
    unit(w,'v').weap_heat=10
    w['armor']=armor(unit(w,'v'))
    acquire_contacts(w)


@step(r'impact kind is (\S+) with base damage 5 and plasma draw 4')
def heat_impact(w,kind):
    names={'flamer-heat':'IS.Flamer','coolant':'IS.CoolantGun','IS-plasma-MECH-base10':'IS.PlasmaRifle',
           'IS-plasma-ground-base10':'IS.PlasmaRifle','CL-plasma-MECH-base10':'CL.PlasmaRifle'}
    weapon=replace(get_weapon(names[kind]),damage=10 if 'plasma' in kind else 5)
    if 'ground' in kind:unit(w,'v').unit_type=U.VEH_GROUND
    dice(w,'plasma_heat',[4])
    w['result']=call(w,resolve_attack,unit(w),unit(w,'v'),weapon,1,4,to_hit_roll=12,location_roll=7,
                     w_fire_mode=F.HEAT_MODE if kind=='flamer-heat' else 0)


@step(r'target heat is (\d+) and armor loss is (\d+)')
def heat_result(w,heat,loss):
    eq(unit(w,'v').weap_heat,int(heat))
    eq(w['armor']-armor(unit(w,'v')),int(loss))
