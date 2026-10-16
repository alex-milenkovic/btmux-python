"""Supplemental source-table, individual mode and advanced-tech UI oracles."""
from hud_displays_common import *
CROOT=ROOT/'btmux/btmux/btech/src/btech'


def uncomment(text):return re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)


def definitions():
    text=(CROOT/'mech.h').read_text()
    return {name:int(value,0) for name,value in re.findall(r'^#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)\b',text,re.M)}


def weapon_rows():
    text=uncomment((CROOT/'weapons.h').read_text()).split('struct weapon_struct MechWeapons[] = {',1)[1].split('};',1)[0]
    vrts={name:int(value) for name,value in re.findall(r'^#define\s+(\w+)\s+(\d+)',(CROOT/'weapons.vrt.h').read_text(),re.M)}
    result=[]
    for index,raw in enumerate(re.findall(r'\{([^{}]+)\}',text)):
        if raw.strip().startswith('NULL'):continue
        fields=[v.strip() for v in raw.split(',')];name=json.loads(fields[0]);flags=set(fields[17].replace(' ','').split('|'));kind=fields[2]
        if flags & {'PC_IMPA','PC_SHAR','PC_HEAT','PCOMBAT'}:continue
        fire,ammo,damage='','',''
        if kind=='TMISSILE':
            damage='M'
            if 'AMS' in flags:damage+='d';fire='Aa'
            elif 'INARC' in flags:fire='I';ammo='EHe'
            elif 'NARC' in flags:fire='N'
            else:
                if 'IDF' in flags:ammo='1ACMNSs';damage+='g';fire='Hi'
                elif 'MRM' in flags:damage+='g'
                else:ammo='AIN'
                for flag,char in [('DFM','D'),('ELRM','e')]:
                    if flag in flags:damage+=char
                if 'STREAK' in flags:fire+='S'
        elif kind=='TAMMO':
            if 'GAUSS' in flags:damage='GH' if 'HVYGAUSS' in flags else 'G'
            else:
                damage='BY' if 'HYPER' in flags else 'B'
                for flag,char in [('RAC','246'),('GMG','G'),('RFAC','R'),('ULTRA','U')]:
                    if flag in flags:fire+=char
                if 'RFAC' in flags:ammo+='FPai'
                if 'LBX' in flags:ammo+='L'
        elif kind=='TARTILLERY':damage='Ag';fire='Hi';ammo='CMs'
        elif kind=='TBEAM':
            damage='E'
            for flag,char in [('HVYW','h'),('PULSE','p'),('A_POD','a')]:
                if flag in flags:damage+=char
            if 'CHEAT' in flags:fire='h'
        if 'NOSPA' in flags:ammo=''
        values=[index,name,*map(int,fields[5:14]),int(fields[15]),int(fields[4]),vrts[fields[1]],fire or '-',ammo or '-',damage,int(fields[3])*10]
        result.append(','.join(map(str,values)))
    return result


def catalog():
    doc=document(actions=[hud('key=test'),hud('wl')]);case=Case('supplement/full-c-weapon-catalog',doc,dict(source='hudinfo.c:513, weapons.h, weapons.vrt.h'))
    expected=weapon_rows();case.expect('results.1.records.*.payload',expected+['Done']);yield case
    defs=definitions()
    fire=[('RAC_TWOSHOT_MODE','2'),('RAC_FOURSHOT_MODE','4'),('RAC_SIXSHOT_MODE','6'),('WILL_JETTISON_MODE','B'),('GATTLING_MODE','G'),('HOTLOAD_MODE','H'),('RFAC_MODE','R'),('ON_TC','T'),('ULTRA_MODE','U'),('HEAT_MODE','h'),('OS_MODE','O'),('OS_USED','o'),('ROCKET_FIRED','o')]
    ammo=[('SGUIDED','G'),('SWARM1','1'),('ARTEMIS','A'),('CLUSTER','C'),('INARC_ECM','E'),('AC_FLECHETTE','F'),('INARC_HAYWIRE','H'),('INFERNO','I'),('LBX','L'),('MINE','M'),('NARC','N'),('AC_PRECISION','P'),('SWARM','S'),('AC_AP','a'),('INARC_EXPLO','X'),('AC_INCENDIARY','e'),('SMOKE','s'),('STINGER','T'),('AC_CASELESS','U'),('ATM_ER','R'),('ATM_HE','X')]
    for group,rows,column in [('firemode',fire,5),('ammomode',[(name+'_MODE',char) for name,char in ammo],6)]:
        for flag,char in rows:
            doc=document(actions=[hud('key=test'),hud('we')]);doc['units'][0]['sections']=[dict(index=0,slots=[dict(index=4,weapon='IS.MediumLaser',**{group:defs[flag]})])]
            yield Case('supplement/'+flag.lower(),doc,dict(diagnostic=True,source='hudinfo.c:281/336, mech.h')).expect(f'results.1.records.0.payload|{column}',char)
    families=[('specials',[('ECM_TECH','E'),('BEAGLE_PROBE_TECH','B'),('LIGHT_BAP_TECH','b'),('MASC_TECH','M'),('AA_TECH','R'),('SLITE_TECH','S'),('TRIPLE_MYOMER_TECH','t'),('C3_SLAVE_TECH','c'),('C3_MASTER_TECH','Tm')]),('specials2',[('ANGEL_ECM_TECH','A'),('NULLSIGSYS_TECH','N'),('BLOODHOUND_PROBE_TECH','b'),('STEALTH_ARMOR_TECH','s'),('C3I_TECH','C'),('TAG_TECH','T')]),('infantry_specials',[('FC_INFILTRATORII_STEALTH_TECH','IP'),('CAN_JETTISON_TECH','J'),('DC_KAGE_STEALTH_TECH','K'),('INF_ANTILEG_TECH','L'),('INF_SWARM_TECH','W'),('FWL_ACHILEUS_STEALTH_TECH','a'),('INF_MOUNT_TECH','f'),('FC_INFILTRATOR_STEALTH_TECH','i'),('MUST_JETTISON_TECH','j'),('CS_PURIFIER_STEALTH_TECH','p')])]
    for group,rows in families:
        for flag,char in rows:
            doc=document(actions=[hud('key=test'),hud('sgi')]);doc['units'][0][group]=defs[flag]
            yield Case('supplement/'+flag.lower(),doc,dict(source='hudinfo.c:668, btmacros.h:851')).expect('results.1.records.0.payload|9',char)
