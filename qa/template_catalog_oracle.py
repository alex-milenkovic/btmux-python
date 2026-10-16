"""Design expectations parsed independently from immutable files and C tables."""
from qa.template_catalog_common import *
from qa.construction_qa_catalog import entries,source_weapons,uncomment
from qa.construction_qa_numeric import table,CROOT
import re,struct
WEAPONS=source_weapons()
NAMES={e['vlong'].lower():e for e in entries()}
UTIL=(CROOT/'mech.utils.c').read_text()
INTTEXT=(CROOT/'mech.consistency.c').read_text().split('static char int_data[][5] = {')[1].split('};')[0]
INTS={int(r[0]):list(map(int,r[1:])) for r in re.findall(r'\{(\d+), (\d+), (\d+), (\d+), (\d+)\}',INTTEXT)}
VRT={name:int(value) for name,value in re.findall(r'#define\s+(VRT_\w+)\s+(\d+)',(CROOT/'weapons.vrt.h').read_text())}
TYPES=table('mech_types');MOVES=table('move_types')
def f32(x):return struct.unpack('f',struct.pack('f',float(x)))[0]
def bits(names,text):
    return sum(1<<i for i,name in enumerate(names) if name.lower() in text.lower().split('|'))
def parse(reference):
    text=(UP/reference).read_bytes().replace(b'\r\n',b'\n').decode()
    fields={m[1].lower():m[2].strip() for m in re.finditer(r'^(\w+)\s+\{([^}]*)\}',text,re.M)}
    cls=next(i for i,n in enumerate(TYPES) if n.lower()==fields['type'].lower())
    move=next(i for i,n in enumerate(MOVES) if n.lower()==fields['move_type'].lower())
    family='quad' if move==8 else 'mech' if cls in (0,6) else 'veh' if cls in (1,2,3) else 'bsuit' if cls==8 else 'ds_spher' if cls==4 else 'ds' if cls==7 else 'aero'
    locs=re.findall(r'"([^"]+)"',re.search(r'char \*'+family+r'_locs\[[^;]*?=\s*\{(.*?)\};',UTIL,re.S)[1])
    sections=[dict(armor=0,rear=0,internal=0) for _ in range(8)]
    slots=[[dict(source_part_id=0,data=0,fire=0,ammo=0,brand=0) for _ in range(12)] for _ in range(8)]
    loc=0;clan_items=False
    for line in text.splitlines():
        if line.replace('_',' ') in locs:loc=locs.index(line.replace('_',' '));continue
        m=re.match(r'\s*(Armor|Rear|Internals)\s*\{\s*(\d+)',line)
        if m:sections[loc][{'Armor':'armor','Rear':'rear','Internals':'internal'}[m[1]]]=int(m[2]);continue
        m=re.match(r'\s*CRIT_(\d+)(?:-(\d+))?\s*\{\s*(.*?)\s*\}',line)
        if not m:continue
        values=m[3].split();entry=NAMES[values[0].lower()];part=entry['source_part_id']
        clan_items|=values[0].lower().startswith('cl.')
        fire=bits(table('crit_fire_modes'),values[2]);ammo=bits(table('crit_ammo_modes'),values[2])
        brand=entry['brand'];data=0
        if part>=193 and part<385:
            data=int(values[1]);cap=int(WEAPONS[part-193][14]);cap=cap//2 if fire&128 else cap
            if data<cap:
                fire|=128
                if data>cap//2:fire&=~128
            if cls not in (6,8):data=int(WEAPONS[part-193][14])//(2 if fire&128 else 1)
        else:
            if part>=394: data=int(values[1]) if values[1].lstrip('-').isdigit() else 0;fire=ammo=0
            if len(values)>3 and values[3].isdigit() and int(values[3]):brand=int(values[3])&15
        for pos in range(int(m[1])-1,int(m[2] or m[1])):slots[loc][pos]=dict(source_part_id=part,data=data,fire=fire,ammo=ammo,brand=brand)
    tons=int(fields['tons']);speed=f32(fields.get('max_speed',0));tech=bits(table('specials'),fields.get('specials',''))
    names=table('internals');jump_id=394+names.index('JumpJet');engine_id=394+names.index('Engine')
    for loc,section in enumerate(slots):
        count=6 if cls==0 and loc>=5 else 12
        if cls!=0 and loc>=6:count=0
        for slot in section[:count]:
            if slot['source_part_id'] and not 193<=slot['source_part_id']<394 and not slot['brand']:slot['brand']=5 if clan_items else 3
    if cls==0:
        ct,side,arm,leg=INTS[tons];arm=leg if move==8 else arm
        for s,n in zip(sections,[arm,arm,side,side,ct,leg,leg,3]):s['internal']=n
    elif cls in (1,2,3):
        for s in sections:
            if s['internal']:s['internal']=max((tons+5)//10,1)
    jets=sum(s['source_part_id']==jump_id for loc,ss in enumerate(slots) for s in ss[:6 if cls==0 and loc>=5 else 12])
    jump=min(jets,int(speed/10.75*2/3))*10.75 if cls==0 else float(fields.get('jump_speed',0))
    comp=int(fields.get('computer',0)) or (5 if clan_items else 2);radio=int(fields.get('radio',0)) or (5 if clan_items else 3)
    mul=[0,.8,1,1.25,1.5,1.75]
    ranges={key:int(fields.get(key,0)) or int(base*mul[radio if key=='radio_range' else comp]) for key,base in [('tac_range',20),('lrs_range',40),('scan_range',20),('radio_range',80)]}
    # Source clears technology claims and derives these from installed criticals.
    derived={}
    counts=Counter(s['source_part_id'] for ss in slots for s in ss)
    for part,flag,threshold in [('FerroFibrous','FerroFibrous_Tech',7 if tech&32 else 14),('EndoSteel','EndoSteel_Tech',7 if tech&32 else 14)]:
        derived[flag]=counts[394+names.index(part)]>=threshold or cls!=0 and counts[394+names.index(part)]>0
    derived['XLEngine_Tech']=cls==0 and any(sum(s['source_part_id']==engine_id for s in slots[i]) in ((1,2,3) if tech&32 else (1,3)) for i in (2,3))
    derived['BeagleProbe']=counts[394+names.index('BeagleProbe')]>0
    derived['Clan']=bool(tech&32)
    derived['ICEEngine_Tech']='ICEEngine_Tech' in fields.get('specials','')
    mounts=[]
    for loc,ss in enumerate(slots):
        pos=0;limit=6 if cls==0 and loc>=5 else 12
        while pos<limit:
            slot=ss[pos];part=slot['source_part_id']
            if not 1<=part<193:pos+=1;continue
            weapon=WEAPONS[part-1];n=int(weapon[13]) if cls==0 else 1
            mounts.append({'name':weapon[0],'section':loc,'critical':pos,'source_id':part,'heat':int(weapon[3]),'damage':int(weapon[4]),'recycle':VRT[weapon[1]]*2,'fire':slot['fire']})
            pos+=n
    return dict(reference=reference,fields=fields,type=cls,move=move,tonnage=tons,max_speed=speed,jump_speed=jump,
                computer=comp,radio=radio,ranges=ranges,sections=sections,slots=slots,mounts=mounts,derived=derived,
                sinks=int(fields.get('heat_sinks',0)) or (0 if 'ICEEngine_Tech' in fields.get('specials','') else 10))

from collections import Counter
def check(a,expected,read,state):
    for key in ('type','move','tonnage','max_speed','jump_speed','computer','radio'):a.eq('source '+key,read[key],expected[key])
    a.eq('source dissipation',read['real_num_sinks'],expected['sinks'])
    for key,value in expected['ranges'].items():a.eq('source electronics '+key,read[key],value)
    for i,sec in enumerate(expected['sections']):
        for key,value in sec.items():
            a.eq(f'section{i} {key}',state['sections'][i][key],value)
            a.eq(f'section{i} {key} original',state['sections'][i][key+'_orig'],value)
    a.eq('all96 source part/data/fire/ammo/brand fields',[[{k:s[k] for k in ('source_part_id','data','fire','ammo','brand')} for s in ss] for ss in read['slots']],expected['slots'])
    a.eq('all source mount identities and grouping',[[w[k] for k in ('name','section','critical')] for w in state['weapons']],[[w[k] for k in ('name','section','critical')] for w in expected['mounts']])
    for slotrow in read['slots']:
        for slot in slotrow:
            if slot['source_part_id']==0 or slot['source_part_id']>=385:
                a.eq('unchanged special numeric namespace',slot['runtime_part_id'],slot['source_part_id'])
    if 'max_suits' in expected['fields']:a.eq('declared suit capacity',read['max_suits'],int(expected['fields']['max_suits']))
    for flag,value in expected['derived'].items():
        bit=1<<table('specials').index(flag);a.eq('source derived '+flag,bool(state['specials']&bit),value)
