"""Unmodified C FASA arithmetic with explicit empty weapon/group inputs.

Inventory consumer totals are separate tests; this oracle isolates tech, size,
armor, sinks, suspension and per-critical arithmetic from inventory helpers.
"""
import re,subprocess
from core_simulation_qa import ROOT,OUT,D,case,check as q
from core_qa_oracles import function


def build():
    src=ROOT/'btmux/btmux/btech/src/btech';header=(src/'mech.h').read_text();source=(src/'mech.utils.c').read_text()
    defs={m[1]:m[0] for m in re.finditer(r'^#define\s+([A-Z][A-Z0-9_]*)\s+[^\n]+',header,re.M)}
    def bit(n):return int(re.search(r'^#define\s+'+n+r'\s+(0x[0-9a-fA-F]+|\d+)\b',header,re.M)[1],0)
    body=''.join(function(source,n) for n in ('round_to_halfton','CalcFasaCost_AddPrice','CalcFasaCost_DoArmMath','CalcFasaCost_DoLegMath'))
    body+=function((src/'mech.consistency.c').read_text(),'susp_factor')+function(source,'CalcFasaCost','unsigned long long int')
    needed=set(re.findall(r'\b[A-Z][A-Z0-9_]+\b',body))|{'WEAPON_BASE_INDEX','AMMO_BASE_INDEX','BOMB_BASE_INDEX','SPECIAL_BASE_INDEX','CARGO_BASE_INDEX'}
    while True:
        new=needed|{v for n in needed if n in defs for v in re.findall(r'\b[A-Z][A-Z0-9_]+\b',defs[n])}
        if new==needed:break
        needed=new
    shim=r'''#include <stdio.h>
#include <math.h>
#define BOUNDED(l,v,h) ((v)<(l)?(l):(v)>(h)?(h):(v))
typedef struct{int type,move,tons,engine,sinks;unsigned specials,specials2;float jump;struct{int armor,rear;unsigned short part[12];}sec[8];}MECH;
struct{int btech_cost_debug;}mudconf;
struct{char*name;int cost,ammo_cost,ammoperton,criticals;}MechWeapons[192];
#define MechTons(m) ((m)->tons)
#define MechType(m) ((m)->type)
#define MechMove(m) ((m)->move)
#define MechSpecials(m) ((m)->specials)
#define MechSpecials2(m) ((m)->specials2)
#define MechEngineSize(m) ((m)->engine)
#define MechRealNumsinks(m) ((m)->sinks)
#define MechJumpSpeed(m) ((m)->jump)
#define GetPartType(m,s,c) ((m)->sec[s].part[c])
#define GetSectOArmor(m,s) ((m)->sec[s].armor)
#define GetSectORArmor(m,s) ((m)->sec[s].rear)
#define IsWeapon(p) ((p)>=WEAPON_BASE_INDEX && (p)<AMMO_BASE_INDEX)
#define IsAmmo(p) ((p)>=AMMO_BASE_INDEX && (p)<BOMB_BASE_INDEX)
#define IsSpecial(p) ((p)>=SPECIAL_BASE_INDEX && (p)<CARGO_BASE_INDEX)
#define IsActuator(p) ((p)>=SPECIAL_BASE_INDEX && (p)<SPECIAL_BASE_INDEX+4)
#define Special2I(p) ((p)-SPECIAL_BASE_INDEX)
#define ClanMech(m) (MechSpecials(m)&CLAN_TECH)
#define MechIsOmniMech(m) (MechSpecials2(m)&OMNIMECH_TECH)
#define is_aero(m) (MechType(m)==CLASS_AERO)
#define IsDS(m) (MechType(m)==CLASS_DS||MechType(m)==CLASS_SPHEROID_DS)
#define IsEnergy(p) 0
#define SendDebug(x) ((void)0)
#define tprintf(...) ""
#define CritsInLoc(m,s) 12
int crit_weight(MECH*m,int p){return 0;}
int FindWeapons(MECH*m,int s,unsigned char*w,unsigned char*d,int*c){return 0;}
int FindAmmunition(MECH*m,unsigned char*w,unsigned short*a,unsigned short*b,unsigned int*mode,int all){return 0;}
long GetPartCost(int p){return 0;}
char*part_name(int p,int b){return "";}
'''
    main=r'''int main(){MECH m;while(scanf("%d%d%d%d%d%u%u%f",&m.type,&m.move,&m.tons,&m.engine,&m.sinks,&m.specials,&m.specials2,&m.jump)==8){for(int s=0;s<8;s++){scanf("%d%d",&m.sec[s].armor,&m.sec[s].rear);for(int c=0;c<12;c++)scanf("%hu",&m.sec[s].part[c]);}printf("%llu\n",CalcFasaCost(&m));}return 0;}'''
    # Macro's C spelling is OMNIMECH_TECH in this reference.
    path=OUT/'cost-oracle.c';exe=OUT/'cost-oracle';path.write_text(shim+'\n'.join(defs[n] for n in sorted(needed|{'OMNIMECH_TECH','CLASS_AERO','CLASS_DS','CLASS_SPHEROID_DS'}) if n in defs)+'\n'+body+main)
    run=subprocess.run(['cc','-O0',str(path),'-lm','-o',str(exe)],capture_output=True,text=True)
    if run.returncode:raise ValueError(run.stderr)
    profiles=[]
    base=dict(name='u',profile='sparse',tonnage=50,max_speed=0,num_sinks=10,core={'engine_rating':200})
    for name in ('ES_TECH','COMPI_TECH','REINFI_TECH','TRIPLE_MYOMER_TECH','CE_TECH','LE_TECH','XL_TECH','XXL_TECH','ICE_TECH','DOUBLE_HEAT_TECH','FF_TECH','HARDA_TECH'):
        profiles.append((name,dict(specials=bit(name))))
    for name in ('SMALLCOCKPIT_TECH','XLGYRO_TECH','CGYRO_TECH','HDGYRO_TECH','COMPACT_HS_TECH','HVY_FF_ARMOR_TECH','LT_FF_ARMOR_TECH','STEALTH_ARMOR_TECH','OMNIMECH_TECH','IMPROVED_JJ_TECH'):
        profiles.append((name,dict(specials2=bit(name))))
    profiles.append(('priority',dict(specials=sum(bit(n) for n in ('ES_TECH','COMPI_TECH','REINFI_TECH','CE_TECH','LE_TECH','XL_TECH','XXL_TECH','ICE_TECH','FF_TECH','HARDA_TECH')),specials2=sum(bit(n) for n in ('XLGYRO_TECH','CGYRO_TECH','HDGYRO_TECH','HVY_FF_ARMOR_TECH','LT_FF_ARMOR_TECH','STEALTH_ARMOR_TECH')))))
    for move,kind in [('TRACK','VEH_GROUND'),('WHEEL','VEH_GROUND'),('HOVER','VEH_GROUND'),('FOIL','VEH_NAVAL'),('HULL','VEH_NAVAL'),('SUB','VEH_NAVAL'),('VTOL','VTOL')]:
        for tons in (10,11,20,21,30,31,40,41,50,51,90,91):profiles.append((f'{move}-{tons}',dict(tonnage=tons,**{'class':kind},movement=move,core={'engine_rating':500})))
    for sinks in (0,9,10,11,19,20,21,501,1001):
        for special,second in ((0,0),(bit('DOUBLE_HEAT_TECH'),0),(bit('ICE_TECH'),0),(0,bit('COMPACT_HS_TECH'))):profiles.append((f'sinks-{sinks}-{special}-{second}',dict(num_sinks=sinks,specials=special,specials2=second)))
    for armor in (0,1,7,8,9,15,16,17,99,100,101):profiles.append((f'armor-{armor}',dict(sections=[dict(index=4,armor=0,armor_orig=armor,rear=0,rear_orig=3)])))
    for jets in (1,2,3,7):
        for improved in (False,True):profiles.append((f'jets-{jets}-{improved}',dict(jump_speed=jets*10.75,specials2=bit('IMPROVED_JJ_TECH') if improved else 0)))
    for special in ('CASE','CASEII','CASE_II','AXE','BEAGLE_PROBE','LIGHT_BAP','ARTEMIS_IV','ANGELECM','C3_MASTER','C3_SLAVE','C3I','ECM','TAG','TARGETING_COMPUTER','MASC','BLOODHOUND_PROBE','SWORD','UPPER_ACTUATOR','LOWER_ACTUATOR','HAND_OR_FOOT_ACTUATOR'):
        for count in (1,3):profiles.append((f'part-{special}-{count}',dict(sections=[dict(index=0,slots=[dict(index=i,type=394+bit(special),firemode=1) for i in range(count)])])))
    for kind in ('MECH','BSUIT'):
        profiles.append(('defined-clan-'+kind,dict(**{'class':kind},specials=bit('CLAN_TECH'),sections=[dict(index=i,slots=[dict(index=0,type=193,data=0)]) for i in range(8)])))
    fixtures=[];rows=[]
    for label,change in profiles:
        u=base|dict(sections=[dict(index=4,armor=0,armor_orig=101,rear=0,rear_orig=7)])|change
        u['core']=u['core']|{'real_num_sinks':u['num_sinks']}
        values=[bit('CLASS_'+u.get('class','MECH')),bit('MOVE_'+u.get('movement','BIPED')),u['tonnage'],u['core']['engine_rating'],u['num_sinks'],u.get('specials',0),u.get('specials2',0),u.get('jump_speed',0)]
        for loc in range(8):
            sec=next((s for s in u['sections'] if s['index']==loc),{});slots=[0]*12
            for slot in sec.get('slots',[]):slots[slot['index']]=slot['type']
            values += [sec.get('armor_orig',0),sec.get('rear_orig',0)]+slots
        rows.append(' '.join(map(str,values)));fixtures.append((label,u))
    raw='\n'.join(rows)+'\n';(OUT/'cost-oracle.input').write_text(raw)
    expected=subprocess.run([str(exe)],input=raw,text=True,capture_output=True,check=True).stdout;(OUT/'cost-oracle.stdout').write_text(expected)
    for (label,u),value in zip(fixtures,expected.splitlines(),strict=True):
        case('cost','c-oracle-'+label,[D('CalcFasaCost')],[q('results.0.value',int(value))],units=[u])
    case('cost','clan-uninitialized-boundary',[D('CalcFasaCost')],[],units=[base|dict(specials=bit('CLAN_TECH'))],error='uninitialized Clan CASE')
