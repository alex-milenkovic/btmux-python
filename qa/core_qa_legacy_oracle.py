"""Independent legacy BV oracle: unmodified C body and data-only accessors."""
import re,subprocess
from core_simulation_qa import ROOT,OUT,D,case,check as q
from core_qa_oracles import function


def build():
    src=ROOT/'btmux/btmux/btech/src/btech';h=(src/'mech.h').read_text();s=(src/'mech.utils.c').read_text()
    defs={m[1]:m[0] for m in re.finditer(r'^#define\s+([A-Z][A-Z0-9_]*)\s+[^\n]+',h,re.M)}
    def bit(n):return int(re.search(r'^#define\s+'+n+r'\s+(0x[0-9a-fA-F]+|\d+)\b',h,re.M)[1],0)
    body=function(re.sub(r'^\s+(int CalculateBV\()',r'\1',s,flags=re.M),'CalculateBV')
    table=s[s.index('#define HIGH_SKILL'):s.index('void Calc_AddOffBV')]
    # Include only the original table and clamp macro, excluding other functions.
    table=table[:table.index('void')] if 'void' in table else table
    shim=r'''#include <stdio.h>
#include <math.h>
#define MAX(a,b) ((a)>(b)?(a):(b))
struct slot{int type,data,firemode,ammomode;};
struct section{int armor,rear,internal,config;struct slot crit[12];};
typedef struct{int type,move,tons,sinks,si,bv,last,pil,gun;unsigned specials,specials2,infantry;float speed,jump;struct section sec[8];}MECH;
struct{char*name;int criticals,battlevalue,heat,vrt,ammoperton,type;unsigned special;}MechWeapons[192];
int muxevent_tick;
#define MechType(m) ((m)->type)
#define MechMove(m) ((m)->move)
#define MechTons(m) ((m)->tons)
#define MechSpecials(m) ((m)->specials)
#define MechSpecials2(m) ((m)->specials2)
#define MechInfantrySpecials(m) ((m)->infantry)
#define MechBV(m) ((m)->bv)
#define MechBVLast(m) ((m)->last)
#define MMaxSpeed(m) ((m)->speed)
#define MechJumpSpeed(m) ((m)->jump)
#define MechActiveNumsinks(m) ((m)->sinks)
#define WalkingSpeed(v) ((float)2.0*(v)/3.0)
#define GetSectArmor(m,i) ((m)->sec[i].armor)
#define GetSectRArmor(m,i) ((m)->sec[i].rear)
#define GetSectInt(m,i) ((m)->sec[i].internal)
#define MechSections(m) ((m)->sec)
#define GetPartType(m,i,j) ((m)->sec[i].crit[j].type)
#define GetPartData(m,i,j) ((m)->sec[i].crit[j].data)
#define GetPartFireMode(m,i,j) ((m)->sec[i].crit[j].firemode)
#define GetPartAmmoMode(m,i,j) ((m)->sec[i].crit[j].ammomode)
#define PartIsNonfunctional(m,i,j) (GetPartFireMode(m,i,j)&7)
#define CritsInLoc(m,i) ((m)->type==CLASS_MECH?((i)>=5?6:12):12)
#define IsWeapon(p) ((p)>=1&&(p)<193)
#define IsAmmo(p) ((p)>=193&&(p)<385)
#define Weapon2I(p) ((p)-1)
#define Ammo2WeaponI(p) ((p)-193)
#define IsDS(m) ((m)->type==CLASS_DS||(m)->type==CLASS_SPHEROID_DS)
#define is_aero(m) (IsDS(m)||(m)->type==CLASS_AERO)
#define AeroSI(m) ((m)->si)
#define FindPilotPiloting(m) ((m)->pil)
#define FindAverageGunnery(m) ((m)->gun)
#define FindArtemisForWeapon(m,i,j) (GetPartType(m,i,(j)+1)==414)
'''
    needed=set(re.findall(r'\b[A-Z][A-Z0-9_]+\b',body+shim))
    while True:
        new=needed|{v for n in needed if n in defs for v in re.findall(r'\b[A-Z][A-Z0-9_]+\b',defs[n])}
        if new==needed:break
        needed=new
    main=r'''int main(){MECH m;int gs,ps;while(scanf("%d%d%d%d%d%d%d%u%u%u%f%f%d%d%d",&m.type,&m.move,&m.tons,&m.sinks,&m.si,&m.pil,&m.gun,&m.specials,&m.specials2,&m.infantry,&m.speed,&m.jump,&gs,&ps,&muxevent_tick)==15){m.bv=777;m.last=0;for(int k=0;k<2;k++)scanf("%d%d%d%d%d%d%u",&MechWeapons[k].criticals,&MechWeapons[k].battlevalue,&MechWeapons[k].heat,&MechWeapons[k].vrt,&MechWeapons[k].ammoperton,&MechWeapons[k].type,&MechWeapons[k].special);for(int i=0;i<8;i++){scanf("%d%d%d%d",&m.sec[i].armor,&m.sec[i].rear,&m.sec[i].internal,&m.sec[i].config);for(int j=0;j<12;j++)scanf("%d%d%d%d",&m.sec[i].crit[j].type,&m.sec[i].crit[j].data,&m.sec[i].crit[j].firemode,&m.sec[i].crit[j].ammomode);}int value=CalculateBV(&m,gs,ps);printf("%d %d\n",value,m.last);}return 0;}'''
    path=OUT/'legacy-bv-oracle.c';exe=OUT/'legacy-bv-oracle';path.write_text(shim+'\n'.join(defs[n] for n in sorted(needed) if n in defs)+'\n'+table+body+main)
    run=subprocess.run(['cc','-O0',str(path),'-lm','-o',str(exe)],text=True,capture_output=True)
    if run.returncode:raise ValueError(run.stderr)
    profiles=[('base',{})]
    for n in ('HARDA_TECH','COMPI_TECH','REINFI_TECH','XL_TECH','XXL_TECH','LE_TECH','ICE_TECH','CLAN_TECH','ECM_TECH','BEAGLE_PROBE_TECH','MASC_TECH','TRIPLE_MYOMER_TECH'):profiles.append((n,{'specials':bit(n)}))
    for n in ('NULLSIGSYS_TECH','STEALTH_ARMOR_TECH','SUPERCHARGER_TECH','OMNIMECH_TECH'):profiles.append((n,{'specials2':bit(n)}))
    for n in (8,16,32,64,120):profiles.append(('infantry-'+str(n),{'infantry_specials':n}))
    for mp in (0,2,3,4,5,6,7,9,10,13,14,18,19,24,25):profiles.append(('speed-'+str(mp),{'max_speed':mp*10.75}))
    for kind,move in [('VEH_GROUND','TRACK'),('VEH_GROUND','WHEEL'),('VEH_GROUND','HOVER'),('VTOL','VTOL'),('VEH_NAVAL','HULL'),('VEH_NAVAL','FOIL'),('VEH_NAVAL','SUB'),('AERO','FLY'),('DS','FLY'),('SPHEROID_DS','FLY')]:profiles.append((kind+move,{'class':kind,'movement':move}))
    for gs in (-1,0,4,7,8,100):
        for ps in (-1,0,5,7,8,100):profiles.append((f'skills-{gs}-{ps}',{'gs':gs,'ps':ps}))
    for tick in (29,30):profiles.append(('cache-'+str(tick),{'gs':100,'ps':100,'tick':tick}))
    for loc in (0,2,4):
        for flag in (0,1,2,4,8,32):
            for caseflag in (0,bit('CASE_TECH')):profiles.append((f'weapon-{loc}-{flag}-{caseflag}',{'loc':loc,'fire':flag,'case':caseflag}))
    for ammo in (0,1,7,20):
        for mode in (0,bit('AC_AP_MODE'),bit('AC_PRECISION_MODE'),bit('SWARM_MODE'),bit('SWARM1_MODE'),bit('STINGER_MODE')):profiles.append((f'ammo-{ammo}-{mode}',{'ammo':ammo,'ammomode':mode}))
    for name,cflag,pflag in [('AMS',bit('AMS'),0x400),('GAUSS',bit('GAUSS'),0x80),('ULTRA',bit('ULTRA'),4),('STREAK',bit('STREAK'),8)]:
        for vrt in (10,20,30,40):profiles.append((name+str(vrt),{'cflag':cflag,'pflag':pflag,'vrt':vrt}))
    for sinks in (0,1,2,4,10,20,100):
        for jump in (0,1,3,4):profiles.append((f'heat-{sinks}-{jump}',{'sinks':sinks,'jump_speed':jump*10.75}))
    fixtures=[];rows=[]
    for label,change in profiles:
        v=dict(gs=4,ps=5,tick=30,loc=0,fire=0,case=0,ammo=7,ammomode=0,cflag=0,pflag=0,vrt=20,sinks=10)|change
        u=dict(name='u',profile='sparse',tonnage=50,max_speed=64.5,jump_speed=0,si=40,gunnery=2,piloting=6,core={'bv':777,'bv_last':0,'real_num_sinks':v['sinks']})
        for k in ('class','movement','specials','specials2','infantry_specials','max_speed','jump_speed'):
            if k in v:u[k]=v[k]
        u['weapons']=[dict(name='IS.SmallLaser',section=v['loc'],critical=0,metadata={'crits':1,'bv':101,'heat':5,'vrt':v['vrt'],'ammo_per_ton':20,'weapon_type':1,'special':v['pflag']}),dict(name='IS.MediumLaser',section=3,critical=0,metadata={'crits':1,'bv':80,'heat':3,'vrt':30,'ammo_per_ton':20,'weapon_type':0,'special':0})]
        sections=[dict(index=i,armor=11 if i==4 else 1,rear=3 if i in (0,2,4) else 0,internal=7 if i==4 else 1,config=v['case'] if i==v['loc'] else 0,slots=[]) for i in range(8)]
        sections[v['loc']]['slots']=[dict(index=0,firemode=v['fire']),dict(index=1,type=414,data=1),dict(index=2,type=193,data=v['ammo'],ammomode=v['ammomode'])]
        u['sections']=sections
        values=[bit('CLASS_'+u.get('class','MECH')),bit('MOVE_'+u.get('movement','BIPED')),50,v['sinks'],40,6,2,u.get('specials',0),u.get('specials2',0),u.get('infantry_specials',0),u['max_speed'],u['jump_speed'],v['gs'],v['ps'],v['tick'],1,101,5,v['vrt'],20,1,v['cflag'],1,80,3,30,20,0,0]
        for sec in sections:
            slots=[[0,0,0,0] for _ in range(12)];i=sec['index']
            if i==v['loc']:slots[:3]=[[1,0,v['fire'],0],[414,1,0,0],[193,v['ammo'],0,v['ammomode']]]
            if i==3:slots[0]=[2,0,0,0]
            values += [sec['armor'],sec['rear'],sec['internal'],sec['config']]+[x for slot in slots for x in slot]
        rows.append(' '.join(map(str,values)));fixtures.append((label,u,v))
    raw='\n'.join(rows)+'\n';(OUT/'legacy-bv-oracle.input').write_text(raw)
    out=subprocess.run([str(exe)],input=raw,text=True,capture_output=True,check=True).stdout;(OUT/'legacy-bv-oracle.stdout').write_text(out)
    for (label,u,v),line in zip(fixtures,out.splitlines(),strict=True):
        value,last=map(int,line.split());case('bv','legacy-c-oracle-'+label,[D('CalculateBV',v['gs'],v['ps'],v['tick'])],[q('results.0.value',value),q('state.units.u.bv_last',last),q('state.units.u.bv',777)],units=[u],config={'extended_gunnery':False,'extended_piloting':False})
