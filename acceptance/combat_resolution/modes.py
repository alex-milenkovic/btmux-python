"""Text mode selectors and capability predicates use real mounted weapons."""
from . import step,eq,session,unit,call
from entities.mech import WeaponState,FireMode as F,AmmoMode as A
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems import weapon_modes as modes


def mount(w,name,loc=0,mode=0,ammo=0):
    weapon=get_weapon(name)
    weapon=session(w).weapon_overrides.get(weapon.index,weapon)
    u=unit(w)
    from entities.mech import UnitType
    size=weapon.crits if u.unit_type==UnitType.MECH else 1
    first=max(0,min(4,12-size))
    for part in u.sections[loc].criticals[first:first+size]:
        part.type=i2weapon(weapon.index)
        part.firemode=mode
        part.ammomode=ammo
    slot=u.sections[loc].criticals[first]
    u.weapons.append(WeaponState(weapon_idx=weapon.index,section=loc,critical=first))
    return slot

@step(r'three ready Ultra weapons numbered 0 through 2 with no modes')
def ultras(w):
    for loc in range(3):mount(w,'IS.UltraAC/5',loc)

@step(r'ultra mode is requested for selector (.+)')
def select(w,text):call(w,modes.mode_command,unit(w),'ultra',text)

@step(r'Ultra weapons after selection are (.+)')
def selected(w,text):
    actual=[i for i,ws in enumerate(unit(w).weapons) if unit(w).sections[ws.section].criticals[ws.critical].firemode & F.ULTRA_MODE]
    eq(actual,[] if text=='none' else [int(n) for n in text.split(',')])

MODES={'none':0,'RAC2':F.RAC_TWOSHOT_MODE,'RAC6':F.RAC_SIXSHOT_MODE,
       'HAYWIRE':A.INARC_HAYWIRE_MODE,'ECM':A.INARC_ECM_MODE,'NEMESIS':A.INARC_NEMESIS_MODE}

@step(r'a ready (RAC|iNARC) with initial mode (\S+)')
def initial(w,weapon,mode):
    w['mode_command']='rac' if weapon=='RAC' else 'inarc'
    mount(w,'IS.RotaryAC/5' if weapon=='RAC' else 'IS.iNarcBeacon',
          mode=MODES[mode] if weapon=='RAC' else 0,ammo=MODES[mode] if weapon=='iNARC' else 0)

@step(r'mode command text is (.+)')
def command(w,text):call(w,modes.mode_command,unit(w),w['mode_command'],text)

@step(r'selected mode is (\S+)')
def mode_result(w,name):
    slot=unit(w).sections[0].criticals[4]
    eq(slot.firemode if w['mode_command']=='rac' else slot.ammomode,MODES[name])

@step(r'a ready weapon with profile (\S+)')
def profile(w,name):
    catalog={'non-ATM-IDF-non-DAR':'IS.LRM-5','LRM':'IS.LRM-5','SRM':'IS.SRM-6',
             'artillery':'IS.Sniper','rocket':'IS.RL-10',
             'one-shot-LRM':'IS.LRM-5','LRM-no-Artemis-link':'IS.LRM-5'}
    mount(w,catalog[name],mode=F.OS_MODE if name=='one-shot-LRM' else 0)

@step(r'mode command (\w+) is applied')
def capability(w,name):w['mode_result']=call(w,modes.mode_command,unit(w),name,'0')

@step(r'capability decision is (accepted|rejected)')
def decision(w,text):eq(w['mode_result'].success,text=='accepted')
