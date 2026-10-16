# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.tech.do.c

"""Literal technician ammunition compatibility and simple-repair part aliases."""
from entities.mech import AmmoMode as A, Specials as S
from entities.weapon import WeaponFlags as W, WeaponType as T, get_weapon_by_index
from entities.crittypes import is_ammo,ammo2weapon_i,i2special,Special
from data.construction_catalog import source_id

# (letter, mode, required type, required special, forbidden special), tech.do.c.
AMMO_TYPES=(('-',0,None,0,0),('L',A.LBX_MODE,None,W.LBX,0),
    ('A',A.ARTEMIS_MODE,T.TMISSILE,0,W.DAR|W.NARC|W.INARC),
    ('N',A.NARC_MODE,T.TMISSILE,0,W.DAR|W.NARC|W.INARC),
    ('S',A.SWARM_MODE,T.TMISSILE,W.IDF,W.DAR|W.NARC|W.INARC),
    ('1',A.SWARM1_MODE,T.TMISSILE,W.IDF,W.DAR|W.NARC|W.INARC),
    ('I',A.INFERNO_MODE,T.TMISSILE,0,W.IDF|W.DAR|W.NARC|W.INARC),
    ('X',A.INARC_EXPLO_MODE,T.TMISSILE,W.INARC,0),('Y',A.INARC_HAYWIRE_MODE,T.TMISSILE,W.INARC,0),
    ('E',A.INARC_ECM_MODE,T.TMISSILE,W.INARC,0),('Z',A.INARC_NEMESIS_MODE,T.TMISSILE,W.INARC,0),
    ('R',A.AC_AP_MODE,T.TAMMO,W.RFAC,0),('F',A.AC_FLECHETTE_MODE,T.TAMMO,W.RFAC,0),
    ('D',A.AC_INCENDIARY_MODE,T.TAMMO,W.RFAC,0),('P',A.AC_PRECISION_MODE,T.TAMMO,W.RFAC,0),
    ('T',A.STINGER_MODE,T.TMISSILE,W.IDF,W.DAR),('U',A.AC_CASELESS_MODE,T.TAMMO,W.RFAC,0),
    ('G',A.SGUIDED_MODE,T.TMISSILE,W.IDF,W.DAR),('H',A.ATM_HE_MODE,T.TMISSILE,W.IDF,W.DAR),
    ('V',A.ATM_ER_MODE,T.TMISSILE,W.IDF,W.DAR),('#',A.MML_LRM_MODE,T.TMISSILE,W.IDF,W.DAR))


def valid_ammo_mode(unit,loc,pos,letter):
    slot=unit.sections[loc].criticals[pos]
    if not is_ammo(slot.type) or not letter:return -1
    weapon=get_weapon_by_index(ammo2weapon_i(slot.type))
    if weapon is None or weapon.special&W.NOSPA:return -1
    for char,mode,kind,required,forbidden in AMMO_TYPES:
        if str(letter).upper()==char and (kind is None or weapon.weapon_type==kind) and (not required or weapon.special&required) and not weapon.special&forbidden:return int(mode)
    return -1


def find_ammo_type(unit,loc,pos):
    slot=unit.sections[loc].criticals[pos];identity=source_id(slot.type)
    if not is_ammo(slot.type):return identity
    weapon=get_weapon_by_index(ammo2weapon_i(slot.type));name=weapon.name;mode=slot.ammomode
    base=next((value for text,value in (('StreakSRM',6),('StreakLRM',86),('ELRM',87),('LR_DFM',84),('SR_DFM',85),('LRM',4),('SRM',5),('MRM',48)) if text in name),-1)
    if not mode&A.AMMO_MODES:return identity if base<0 else 512+base
    if mode&A.LBX_MODE:
        base=next((value for text,value in (('LB20',3),('LB10',2),('LB5',1),('LB2',0)) if text in name),base)
        return identity if base<0 else 512+base
    if mode&A.AC_MODES:
        for flag,offset in ((A.AC_AP_MODE,60),(A.AC_FLECHETTE_MODE,66),(A.AC_INCENDIARY_MODE,72),(A.AC_PRECISION_MODE,78),(A.AC_CASELESS_MODE,142)):
            if mode&flag:
                for index,text in enumerate(('AC/2','AC/5','AC/10','AC/20','LightAC/2','LightAC/5')):
                    if text in name:base=offset+index
        return identity if base<0 else 512+base
    for flag,value in ((A.INARC_EXPLO_MODE,56),(A.INARC_HAYWIRE_MODE,57),(A.INARC_ECM_MODE,58),(A.INARC_NEMESIS_MODE,59)):
        if mode&flag:return 512+value
    if base<0:return identity
    for flag,offset in ((A.NARC_MODE,3),(A.ARTEMIS_MODE,6),(A.SWARM_MODE,36),(A.SWARM1_MODE,37),(A.INFERNO_MODE,37),(A.STINGER_MODE,137),(A.SGUIDED_MODE,144)):
        if mode&flag:return 512+base+offset
    return 512+base


def repair_alias(unit,part):
    """Source IDs in and out; current simple-repair branch only."""
    if i2special(Special.SHOULDER_OR_HIP)<=part<=i2special(Special.HAND_OR_FOOT_ACTUATOR):return 548
    if part==i2special(Special.ENGINE):
        return next((512+value for flag,value in ((S.XL_TECH,30),(S.ICE_TECH,32),(S.XXL_TECH,43),(S.CE_TECH,44),(S.LE_TECH,49)) if unit.specials&flag),part)
    if part==i2special(Special.HEAT_SINK) and unit.specials&(S.DOUBLE_HEAT_TECH|S.CLAN_TECH):return 543
    return part
