"""Ammunition compatibility, commodity selection and live bin maintenance."""
import re
from . import check,command,stock,advance,A,F,Special,i2special,i2ammo,i2weapon,get_weapon,WEAPON_CATALOG,source_id
from entities.weapon import WeaponFlags as W,WeaponType as T
from systems.repair_materials import valid_ammo_mode,find_ammo_type


def run(w,initial,operation):
    u=w['u'];slot=u.sections[4].criticals[0];inv=w['inventory']
    if operation=='find commodity':
        names={'StreakSRM6':'IS.StreakSRM-6','StreakLRM10':'CL.StreakLRM-10','ELRM15':'IS.ELRM-15','LR_DFM5':'IS.LR_DFM-5','SR_DFM2':'IS.SR_DFM-2','LRM15':'IS.LRM-15','SRM6':'IS.SRM-6','MRM20':'IS.MRM-20','ordinary':'IS.AC/10','LB20':'IS.LB20-XAC','LB10':'IS.LB10-XAC','LB5':'IS.LB5-XAC','LB2':'IS.LB2-XAC','AC10':'IS.AC/10','LightAC5':'IS.LightAC/5','iNarc':'IS.iNarcBeacon'}
        slot.type=i2special(Special.ENGINE) if initial.startswith('nonammo') else i2ammo(get_weapon(names[initial.split()[0]]).index)
        flags={'LBX':A.LBX_MODE,'AP':A.AC_AP_MODE,'PRECISION':A.AC_PRECISION_MODE,'CASELESS':A.AC_CASELESS_MODE,'explosive':A.INARC_EXPLO_MODE,'haywire':A.INARC_HAYWIRE_MODE,'Narc':A.NARC_MODE,'Artemis':A.ARTEMIS_MODE,'Swarm1':A.SWARM1_MODE,'ATM_HE':A.ATM_HE_MODE}
        for word,flag in flags.items():
            if word in initial.split():slot.ammomode|=flag
        result=find_ammo_type(u,4,0)
        values={'SSRM base cargo':518,'SLRM base cargo':598,'ELRM base cargo':599,'LR_DFM base cargo':596,'SR_DFM base cargo':597,'LRM base cargo':516,'SRM base cargo':517,'MRM base cargo':560,'encoded ammo identity':source_id(slot.type),'LBX20 cargo':515,'LBX10 cargo':514,'LBX5 cargo':513,'LBX2 cargo':512,'AC10 precision cargo':592,'LightAC5 caseless cargo':659,'explosive commodity':568,'LRM Narc commodity':519,'LRM Swarm1 commodity':553,'Engine identity':i2special(Special.ENGINE)}
        for label,value in values.items():check(w,label,result==value)
        return True
    name=operation.split()[0]
    if name in ('reload','unload','toggletype'):
        weapon=get_weapon('CL.ATM-6');slot.type=i2ammo(weapon.index)
        slot.data=10 if initial.startswith('full') else 0 if initial.startswith('empty') else 2 if initial.startswith('OOC') else 8
        # Artemis is accepted by the literal source table even on ATM.
        slot.ammomode=0x40000000  # Explicit bit outside the source ammo mask.
        unrelated=slot.ammomode
        if initial.startswith('OOC'):w['actor'].tech=False
        if 'pending600' in initial:inv.put(7,'TECHTIME','36000')
        identity=find_ammo_type(u,4,0);stock(w,identity,1 if 'stock1' in initial else 0)
        w['streams']['tech_rolls']=[2 if 'roll fail' in initial else 12]
        arg='CT 1'+(' A' if 'alternative' in operation else '')
        command(w,name,arg);event=w['result'];err=w['error'];atcommand=slot.data;count=inv.find(1000,identity)
        check(w,'refuse full and keep normal mode','full' in err and slot.data==10 and slot.ammomode==unrelated)
        check(w,'refuse fatigue after emptying and mode change','tired' in err and slot.data==0 and bool(slot.ammomode&A.ARTEMIS_MODE))
        check(w,'refuse stock after emptying and mode change','stock' in err and slot.data==0 and bool(slot.ammomode&A.ARTEMIS_MODE))
        check(w,'refuse empty without dice','empty' in err and not w['draws'])
        check(w,'ammo10 and only ammo mode bits replaced',not err and slot.data==10 and int(slot.ammomode)==0x40000002)
        match=re.search(r'advance(\d+)',operation)
        if match and event:advance(w,int(match[1])-1);early=slot.data;advance(w,1)
        else:early=slot.data
        check(w,'stock0 at command ammo10 only at600',count==0 and atcommand==early==8 and slot.data==10 and event.tick==600)
        check(w,'stock0 ammo8 and no refill',count==0 and slot.data==8 and bool(event) and event.repair_fake and not w['jobs'].events())
        check(w,'ammo0 and returned commodity1',slot.data==0 and inv.find(1000,identity)==1 and bool(event) and not event.repair_fake)
        check(w,'ammo0 and returned commodity0',slot.data==0 and inv.find(1000,identity)==0 and bool(event) and not event.repair_fake)
        return True
    if not initial.endswith(('ammo','ammo not ATM','ammo not MML','weapon','specials')):return False
    if 'NOSPA' in initial:weapon=get_weapon('IS.StreakSRM-2')
    elif 'LBX' in initial:weapon=get_weapon('IS.LB10-XAC')
    elif 'INARC' in initial:weapon=get_weapon('IS.iNarcBeacon')
    elif 'DAR' in initial:weapon=get_weapon('IS.ArrowIVSystem')
    elif 'TAMMO without' in initial:weapon=get_weapon('IS.MachineGun')
    elif 'RFAC' in initial:weapon=get_weapon('IS.AC/10')
    elif 'missile' in initial:weapon=get_weapon('IS.SRM-6' if 'without IDF' in initial or 'ordinary' in initial else 'IS.LRM-15')
    else:weapon=get_weapon('IS.AC/10')
    slot.type=(i2weapon if initial.startswith('nonammo') else i2ammo)(weapon.index)
    result=valid_ammo_mode(u,4,0,operation.split()[-1]);check(w,'invalid',result==-1);check(w,'valid zero mask',result==0)
    for flag in ('LBX_MODE','ARTEMIS_MODE','NARC_MODE','SWARM_MODE','SWARM1_MODE','INFERNO_MODE','INARC_EXPLO_MODE','INARC_HAYWIRE_MODE','INARC_ECM_MODE','INARC_NEMESIS_MODE','AC_AP_MODE','AC_FLECHETTE_MODE','AC_INCENDIARY_MODE','AC_PRECISION_MODE','AC_CASELESS_MODE','STINGER_MODE','SGUIDED_MODE','ATM_HE_MODE','ATM_ER_MODE','MML_LRM_MODE'):check(w,'valid '+flag,result==getattr(A,flag))
    return True
