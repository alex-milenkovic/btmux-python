"""Independent CLI comparisons to the unmodified defensive C function body."""
from pathlib import Path
import json,re,subprocess,sys
from core_simulation_qa import ROOT,OUT,D,case,check as q


def build():
    # This reviewed builder supplies struct accessors, not calculated expectations.
    OUT.mkdir(parents=True,exist_ok=True)
    generated=OUT/'core-bv-oracle.c'
    subprocess.run([sys.executable,str(ROOT/'qa/oracles/build_defensive_bv.py'),'--output',str(generated)],check=True,capture_output=True)
    source=generated.read_text().replace('%.9g','%.17g')
    path=OUT/'qa-defensive-bv-oracle.c';path.write_text(source)
    exe=OUT/'qa-defensive-bv-oracle'
    subprocess.run(['cc','-O0',str(path),'-lm','-o',str(exe)],check=True,capture_output=True)
    header=(ROOT/'btmux/btmux/btech/src/btech/mech.h').read_text()
    def bit(name):
        m=re.search(r'^#define\s+'+name+r'\s+(0x[0-9a-fA-F]+|\d+)\b',header,re.M)
        if not m:raise ValueError(name)
        return int(m[1],0)
    profiles=[]
    for name in ('XL_TECH','XXL_TECH','ICE_TECH','CE_TECH','LE_TECH','REINFI_TECH','COMPI_TECH','MASC_TECH','TRIPLE_MYOMER_TECH'):
        profiles.append((name,bit(name),0,'MECH','BIPED',6,0,[]))
    for name in ('HDGYRO_TECH','XLGYRO_TECH','SUPERCHARGER_TECH','STEALTH_ARMOR_TECH'):
        profiles.append((name,0,bit(name),'MECH','BIPED',6,0,[]))
    profiles += [('combined-boost',bit('MASC_TECH')|bit('TRIPLE_MYOMER_TECH'),bit('SUPERCHARGER_TECH'),'MECH','BIPED',6,0,[])]
    for kind,move in [('VEH_GROUND','TRACK'),('VEH_GROUND','WHEEL'),('VEH_GROUND','HOVER'),('VEH_NAVAL','HULL'),('VEH_NAVAL','FOIL'),('VEH_NAVAL','SUB'),('VTOL','VTOL')]:
        profiles.append(('vehicle-'+move,0,0,kind,move,6,0,[]))
    for mp in (0,2,3,4,5,6,7,9,10,17,18,24,25):
        for jump in (mp,mp+1):profiles.append((f'run{mp}-jump{jump}',0,0,'MECH','BIPED',mp,jump,[]))
    for clan in (0,bit('CLAN_TECH')):
        for engine in (0,bit('XL_TECH'),bit('XXL_TECH')):
            for loc in (0,2,4):
                for caseflag in (0,bit('CASE_TECH')):
                    profiles.append((f'explosive-{clan}-{engine}-{loc}-{caseflag}',clan|engine,0,'MECH','BIPED',6,0,[(loc,caseflag,[193,194,2])]))
    for count in (0,1,2,3):
        profiles.append((f'ecm-probe-{count}',0,0,'MECH','BIPED',6,0,[(4,0,[394+bit('ECM')]*count+[394+bit('BEAGLE_PROBE')]*count)]))
    lines=[];fixtures=[]
    for label,s1,s2,kind,move,mp,jump,raw in profiles:
        # Source catalog indexes0/1 are explicitly represented by metadata on the
        # corresponding local catalog identities. Raw source part numbers agree.
        sections=[dict(index=4,armor=80,armor_orig=80,rear=20,rear_orig=20,internal=50,internal_orig=50)]
        for loc,flag,types in raw:
            sec=next((s for s in sections if s['index']==loc),None)
            if sec is None:sec=dict(index=loc);sections.append(sec)
            sec.update(config=flag,slots=[dict(index=i,type=p,firemode=1,data=0) for i,p in enumerate(types)])
        unit=dict(name='u',profile='sparse',**{'class':kind},movement=move,max_speed=mp*10.75,jump_speed=jump*10.75,specials=s1,specials2=s2,sections=sections,
                  weapons=[dict(name='IS.SmallLaser',section=7,critical=0,metadata=dict(crits=1,special=0x400,bv=32,ammo_bv=11)),dict(name='IS.MediumLaser',section=7,critical=1,metadata=dict(crits=1,special=0x80,bv=320))])
        values=[bit('CLASS_'+kind),bit('MOVE_'+move),50,s1,s2,mp*10.75,jump*10.75]
        for loc in range(8):
            sec=next((s for s in sections if s['index']==loc),{})
            slots=[0]*12
            for slot in sec.get('slots',[]):slots[slot['index']]=slot['type']
            if loc==7:slots[:2]=[1,2]
            values += [sec.get('armor',0)+sec.get('rear',0),sec.get('internal',0),sec.get('config',0)]+slots
        lines.append(' '.join(map(str,values)));fixtures.append((label,unit))
    raw='\n'.join(lines)+'\n';(OUT/'qa-defensive-bv-oracle.input').write_text(raw)
    expected=subprocess.run([str(exe)],input=raw,text=True,capture_output=True,check=True).stdout
    (OUT/'qa-defensive-bv-oracle.stdout').write_text(expected)
    for (label,unit),value in zip(fixtures,expected.splitlines(),strict=True):
        case('bv','c-oracle-'+label,[D('Calculate_Defensive_BV')],[q('results.0.value',float(value),tolerance=1e-5)],units=[unit])
