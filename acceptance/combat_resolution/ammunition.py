"""Ammunition APS exercises firing plus shared checks and expenditure."""
from dataclasses import replace
from . import step,unit,session,call,dice,eq
from .modes import mount
from .equipment import advance
from entities.mech import Location as L,FireMode as F,CritStatus
from entities.crittypes import i2ammo
from entities.weapon import get_weapon,get_weapon_by_index,WeaponFlags as W
from systems import combat_ammunition as ammo
from systems.combat import fire_weapon


def bin_at(w,loc,rounds,pos=11):
    slot=unit(w).sections[loc].criticals[pos]
    slot.type=i2ammo(unit(w).weapons[0].weapon_idx)
    slot.data=rounds
    return slot


def fire(w):
    return call(w,fire_weapon,unit(w),unit(w,'v'),0,1,to_hit_roll=12,cluster_roll=12,location_roll=7)


@step(r'a weapon mounted in CT with ordinary ammo CT 4 LT 3 RT 2')
def preferred_fixture(w):
    mount(w,'IS.AC/10',L.CTORSO)
    w['bins']={name:bin_at(w,loc,count) for name,loc,count in (('CT',L.CTORSO,4),('LT',L.LTORSO,3),('RT',L.RTORSO,2))}


@step(r'preferred ammo source is (LT|-) with LT bin condition (working|empty|destroyed) and one shot fires')
def preferred_fire(w,source,condition):
    eq(call(w,ammo.usebin,unit(w),'0 '+source)['accepted'],True)
    if condition=='empty':w['bins']['LT'].data=0
    if condition=='destroyed':w['bins']['LT'].firemode|=F.DESTROYED_MODE
    before={name:slot.data for name,slot in w['bins'].items()}
    eq(fire(w).hit,True)
    w['spent']=[name for name,slot in w['bins'].items() if slot.data<before[name]]


@step(r'the spent bin is (CT|LT|RT)')
def preferred_result(w,name):eq(w['spent'],[name])


@step(r'a ready (RAC|gattling|Ultra) with (\d+) ordinary rounds and requested burst (\d+)')
def burst_fixture(w,name,rounds,burst):
    weapon={'RAC':'IS.RotaryAC/5','gattling':'IS.MachineGun','Ultra':'IS.UltraAC/5'}[name]
    mode={'RAC':{2:F.RAC_TWOSHOT_MODE,4:F.RAC_FOURSHOT_MODE,6:F.RAC_SIXSHOT_MODE}[int(burst)],'gattling':F.GATTLING_MODE,'Ultra':F.ULTRA_MODE}[name]
    mount(w,weapon,L.CTORSO,mode=mode)
    w['burst_name']=name
    w['burst_bin']=bin_at(w,L.LTORSO,int(rounds))


@step(r'a nonjamming shot fires with gattling draw 6')
def burst_fire(w):
    dice(w,'gattling_shots',[6])
    w['burst_result']=fire(w)
    eq(w['burst_result'].hit,True)


@step(r'actual shot count is (\d+) and ammo remaining is (\d+)')
def burst_result(w,shots,remaining):
    result=w['burst_result']
    weapon=get_weapon_by_index(unit(w).weapons[0].weapon_idx)
    actual=result.damage_dealt if w['burst_name']=='gattling' else result.damage_dealt/weapon.damage
    eq(actual,int(shots))
    eq(w['burst_bin'].data,int(remaining))


@step(r'an unfired (pure-rocket|one-shot) with no ammo bins')
def one_use_fixture(w,name):
    weapon=get_weapon('IS.RL-10' if name=='pure-rocket' else 'IS.SRM-2')
    if name=='pure-rocket':session(w).weapon_overrides[weapon.index]=replace(weapon,special=W.ROCKET,crits=2)
    else:session(w).weapon_overrides[weapon.index]=replace(weapon,crits=1)
    slot=mount(w,weapon.name,L.CTORSO,mode=F.OS_MODE if name=='one-shot' else 0)
    if name=='pure-rocket':unit(w).sections[L.CTORSO].criticals[5].type=slot.type


@step(r'it fires then recycles and fire is requested again')
def one_use_fire(w):
    w['first']=fire(w)
    weapon=get_weapon_by_index(unit(w).weapons[0].weapon_idx)
    advance(w,2*weapon.vrt+2)
    w['second']=fire(w)


@step(r'first shot fires and second shot is rejected with spent marker (all-run-ROCKET_FIRED|OS_USED)')
def one_use_result(w,marker):
    eq(w['first'].hit,True)
    eq(w['second'].bth_breakdown,None)
    eq(any('already been used' in m for m in w['second'].messages),True)
    slots=unit(w).sections[L.CTORSO].criticals
    bit=F.OS_USED if marker=='OS_USED' else F.ROCKET_FIRED
    for pos in ([4] if marker=='OS_USED' else [4,5]):eq(bool(slots[pos].firemode&bit),True)


@step(r'a started nonzero-index weapon with warning threshold 5 and AmmoWarn enabled')
def warning_fixture(w):
    mount(w,'IS.AC/5',L.CTORSO)
    weapon=get_weapon_by_index(unit(w).weapons[0].weapon_idx)
    session(w).weapon_overrides[weapon.index]=replace(weapon,ammo_per_ton=20)
    w['warning_bin']=bin_at(w,L.LTORSO,1)
    unit(w).prefs=0
    unit(w).crit_status|=CritStatus.OWEIGHT_OK


@step(r'ammunition count is (\d+) and expenditure-check offset is (\d+)')
def warning_check(w,count,offset):
    w['warning_bin'].data=int(count)
    w['severity']=call(w,ammo.expenditure_check,unit(w),unit(w).weapons[0].weapon_idx,int(offset))


@step(r'warning severity is (red|yellow|none) and weapon-check state is set')
def warning_result(w,severity):
    eq(w['severity'],None if severity=='none' else severity)
    eq(bool(unit(w).crit_status&CritStatus.OWEIGHT_OK),False)
