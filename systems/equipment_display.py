# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/hudinfo.c

"""Weapon, ammunition and critical presentation from authoritative slot state."""
from entities.mech import FireMode as F, AmmoMode as A, CritStatus as C, MechStatus as S
from entities.weapon import WeaponFlags as W, WeaponType as T, get_weapon_by_index
from systems.enhanced_crits import part_temp_nuke
from systems.weapon_inventory import weapon_runs
from systems.combat import part_is_nonfunctional

FIRE_FLAGS=tuple(zip(('RAC_TWOSHOT','RAC_FOURSHOT','RAC_SIXSHOT','WILL_JETTISON','GATTLING','HOTLOAD','RFAC','ON_TC','ULTRA','HEAT'),'246BGHRTUh'))
AMMO_FLAGS=tuple(zip(('SGUIDED','SWARM1','ARTEMIS','CLUSTER','INARC_ECM','AC_FLECHETTE','INARC_HAYWIRE','INFERNO','LBX','MINE','NARC','AC_PRECISION','SWARM','AC_AP','INARC_EXPLO','AC_INCENDIARY','SMOKE','STINGER','AC_CASELESS','ATM_ER','ATM_HE'),'G1ACEFHILMNPSaXesTURX'))


def refresh(unit):
    if unit._engine is not None:
        from core.game_loop import update_recycling
        update_recycling(unit._engine,unit)


def weapon_status(unit,loc,pos):
    slot=unit.sections[loc].criticals[pos]
    if slot.firemode&(F.BROKEN_MODE|F.DESTROYED_MODE):return '*'
    if slot.firemode&F.DISABLED_MODE:return 'D'
    failure=part_temp_nuke(slot)
    if failure in (1,2,3,4,5,6):return {1:'J',2:'S',3:'d',4:'E',5:'*',6:'A'}[failure]
    if slot.firemode&F.IS_JETTISONED_MODE:return 'j'
    return str(slot.data//2) if slot.data else 'R'


def fire_modes(unit,slot,weapon):
    text=''
    for name,char in FIRE_FLAGS:
        flag=getattr(F,name if name=='ON_TC' else name+'_MODE')
        if slot.firemode&flag and (name!='ON_TC' or not unit.crit_status&C.TC_DESTROYED):text+=char
    if slot.firemode&(F.OS_USED|F.ROCKET_FIRED):text+='o'
    elif slot.firemode&F.OS_MODE or weapon.special&W.ROCKET:text+='O'
    for flag,char in [(W.INARC,'I'),(W.NARC,'N'),(W.STREAK,'S')]:
        if weapon.special&flag:text+=char
    if weapon.special&W.AMS:text+='A' if unit.status&S.AMS_ENABLED else 'a'
    return text or '-'


def ammo_modes(mode):
    return ''.join(char for name,char in AMMO_FLAGS if mode&getattr(A,name+'_MODE')) or '-'


def allowed_modes(weapon):
    spec=weapon.special;fire=ammo=damage=''
    if spec&(W.PC_IMPA|W.PC_SHAR|W.PC_HEAT):return None
    if weapon.weapon_type==T.TMISSILE:
        damage='M'
        if spec&W.AMS:damage+='d';fire='Aa'
        elif spec&W.INARC:fire='I';ammo='EHe'
        elif spec&W.NARC:fire='N'
        else:
            if spec&W.IDF:ammo='1ACMNSs';damage+='g';fire='Hi'
            elif spec&W.MRM:damage+='g'
            else:ammo='AIN'
            if spec&W.DFM:damage+='D'
            if spec&W.ELRM:damage+='e'
            if spec&W.STREAK:fire+='S'
    elif weapon.weapon_type==T.TAMMO:
        if spec&W.GAUSS:damage='GH' if spec&W.HVYGAUSS else 'G'
        else:
            damage='BY' if spec&W.HYPER else 'B'
            for flag,letters in [(W.RAC,'246'),(W.GMG,'G'),(W.RFAC,'R'),(W.ULTRA,'U')]:
                if spec&flag:fire+=letters
            if spec&W.RFAC:ammo+='FPai'
            if spec&W.LBX:ammo+='L'
    elif weapon.weapon_type==T.TARTILLERY:damage='Ag';fire='Hi';ammo='CMs'
    elif weapon.weapon_type==T.TBEAM:
        damage='E'
        for flag,char in [(W.HVYW,'h'),(W.PULSE,'p'),(W.A_POD,'a')]:
            if spec&flag:damage+=char
        if spec&W.CHEAT:fire='h'
    if spec&W.NOSPA:ammo=''
    return fire or '-',ammo or '-',damage


def catalog_rows():
    from data.construction_catalog import SOURCE_WEAPON_NAMES
    from entities.construction_weapon_data import WEAPON_ROWS
    from entities.weapon import get_weapon
    for index,name in enumerate(SOURCE_WEAPON_NAMES):
        weapon=get_weapon(name)
        modes=allowed_modes(weapon)
        if modes is None:continue
        yield [index,weapon.name,weapon.range_min,weapon.range_short,weapon.range_medium,weapon.range_long,
               WEAPON_ROWS[index][9],weapon.range_short_water,weapon.range_medium_water,weapon.range_long_water,
               weapon.crits,int(weapon.tonnage*100),weapon.damage,weapon.vrt,*modes,weapon.heat*10]


def catalog_index(runtime_index):
    from data.construction_catalog import source_id
    return source_id(runtime_index+1)-1
