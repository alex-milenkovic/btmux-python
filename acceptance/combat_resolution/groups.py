"""TIC selectors and interruptions through actual firing effects."""
from . import step,unit,session,call,dice,eq
from .modes import mount
from .commands import acquire_contacts
from systems import tic
from entities.mech import Location as L,FireMode as F
from entities.crittypes import i2ammo


@step(r'TIC 0 contains weapons 0 1 2')
def membership(w):
    for loc in range(3):mount(w,'IS.MediumLaser',loc)
    call(w,tic.add_tic,unit(w),'0','0-2')


@step(r'deltic text is (.+)')
def delete(w,text):call(w,tic.tic_command,session(w).engine,unit(w),'deltic',text)


@step(r'TIC 0 contains (none|[0-9,]+)')
def members(w,expected):eq(sorted(unit(w).tics[0]),[] if expected=='none' else list(map(int,expected.split(','))))


@step(r'TIC 0 contains valid weapons numbered 0 1 2 3 4')
def listing(w):
    for loc in range(5):mount(w,'IS.MediumLaser',loc)
    call(w,tic.add_tic,unit(w),'0','0-4')


@step(r'listtic 0 is displayed')
def list_rows(w):w['tic_rows']=call(w,tic.list_tic,unit(w),'0')


@step(r'callback row order is ([0-9,]+)')
def row_order(w,expected):
    eq([row[0] for row in w['tic_rows'][0]],list(map(int,expected.split(','))))


@step(r'TIC 0 contains two ready weapons and TIC 1 contains another')
def volley(w):
    # The first mount is configured by the interruption fixture below.
    for loc in (L.CTORSO,L.LLEG,L.RLEG):mount(w,'IS.MediumLaser',loc)
    call(w,tic.add_tic,unit(w),'0','0-1')
    call(w,tic.add_tic,unit(w),'1','2')
    acquire_contacts(w)
    unit(w).target=unit(w,'v')._id


@step(r'firetic 0,1 fires first weapon and actor (falls-from-heavy-Gauss-recoil|shuts-down-from-failure)')
def interrupted_volley(w,change):
    from entities.weapon import get_weapon
    from entities.crittypes import i2weapon
    from systems.enhanced_crits import WEAP_DAM_EN_CRYSTAL
    u=unit(w);ws=u.weapons[0];slot=u.sections[ws.section].criticals[ws.critical]
    if change=='falls-from-heavy-Gauss-recoil':
        weapon=get_weapon('IS.HeavyGaussRifle')
        ws.weapon_idx=weapon.index
        ws.critical=min(4,12-weapon.crits)
        for part in u.sections[ws.section].criticals:part.type=0
        for part in u.sections[ws.section].criticals[ws.critical:ws.critical+weapon.crits]:part.type=i2weapon(weapon.index)
        ammo=u.sections[L.LTORSO].criticals[9]
        ammo.type=i2ammo(weapon.index);ammo.data=10
        u.speed=1
        dice(w,'attack_rolls',[12])
        dice(w,'pilot_rolls',[2]*20)
    else:
        slot.firemode|=F.DAMAGED_MODE
        slot.weap_damage_flags=WEAP_DAM_EN_CRYSTAL
        u.sections[L.CTORSO].internal=1
        dice(w,'attack_rolls',[2])
    w['draw_start']=len(session(w).draws)
    call(w,tic.fire_tic,session(w).engine,u,'0,1')
    eq(u.is_fallen if change=='falls-from-heavy-Gauss-recoil' else not u.is_started,True)


@step(r'no later weapon fires')
def stopped_volley(w):
    eq(sum(d['name']=='attack_rolls' for d in session(w).draws[w['draw_start']:]),1)
    for ws in unit(w).weapons[1:]:eq(unit(w).sections[ws.section].criticals[ws.critical].data,0)
