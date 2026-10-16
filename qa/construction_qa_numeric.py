"""Independent specification examples and literal C arithmetic tables."""
from qa.construction_qa_common import *
import re
CLASSES={'Mech':'MECH','Vehicle':'GROUND','Naval':'NAVAL','VTOL':'VTOL','AeroFighter':'AERO','Aerodyne_DropShip':'DS','Spheroid_DropShip':'SPHEROID_DS','Battlesuit':'BSUIT','Mechwarrior':'MW'}
MOVES={s:s.upper() for s in ['Biped','Track','Wheel','Hover','VTOL','Hull','Foil','Fly','Quad','Sub','None']}
SOURCE=(CROOT/'template.c').read_text()
def table(name):return re.findall(r'"([^"\n]*)"',re.search(r'char \*'+name+r'\[\]\s*=\s*\{(.*?)\};',SOURCE,re.S)[1])
SPECIALS=table('specials');SPECIALS2=table('specials2');INTERNALS=table('internals')

def blank(cls='Mech',move='Biped',tons=50):
    return dict(name='u',**{'class':CLASSES[cls]},movement=MOVES[move],tonnage=tons,core={'engine_rating':200,'original_sinks':10,'real_num_sinks':0},sections=[dict(index=i,armor=0,armor_orig=0,rear=0,rear_orig=0,internal=0,internal_orig=0,slots=[dict(index=j,type=0) for j in range(12)]) for i in range(8)])
def tech(unit,names):
    first=second=0
    aliases={'XL':'XLEngine_Tech','XXL':'XXL_Tech','Light':'LightEngine_Tech','Compact':'CompactEngine_Tech','ICE':'ICEEngine_Tech','EndoSteel':'EndoSteel_Tech','Reinforced':'ReinforcedInternal_Tech','IS-FF':'FerroFibrous_Tech','Clan-FF':'Clan+FerroFibrous_Tech','heavy-FF':'HvyFerroFibrous_Tech','light-FF':'LtFerroFibrous_Tech','hardened':'HardenedArmor_Tech'}
    names='+'.join(aliases.get(n,n) for n in names.split('+'))
    for name in names.split('+'):
        if name in SPECIALS:first|=1<<SPECIALS.index(name)
        elif name in SPECIALS2:second|=1<<SPECIALS2.index(name)
        elif name not in ('standard','none'):raise ValueError(name)
    unit['specials']=first;unit['specials2']=second;return unit

def run(a):
    for outline in (1,2,3):
        for line,row in examples('internals',outline):
            u=blank(row.get('unit','Mech'),row.get('move','Biped'),int(row.get('tons',50)))
            if outline==1:
                arm,side,ct,leg=(int(row[x]) for x in ('arm','side','ct','leg'));want=[arm,arm,side,side,ct,leg,leg,3]
            else:
                loc=0 if outline==2 else 2;u['sections'][loc].update(internal_orig=int(row['original']),internal=int(row.get('current',0)))
                want=[8,int(row['after_current'])] if outline==2 else [int(row['after_original']),int(row['after_current'])]
            d=a.run(f'internals/{outline}-{line}',document([dict(op='construction_validate'),I()],units=[u]),'ordinary');secs=d['results'][-1]['units']['u']['sections']
            if outline==1:
                a.eq('table originals',[s['internal_orig'] for s in secs],want);a.eq('table current',[s['internal'] for s in secs],want)
            else:a.eq('defined damage preservation',[secs[loc]['internal_orig'],secs[loc]['internal']],want)
    for outline in (1,2,3,4,5,7,8):
        for line,r in examples('weights',outline):
            u=blank(r.get('unit','Mech'),r.get('move','Biped'),int(r.get('tons',50)))
            tech(u,r.get('tech','standard'))
            if outline==1:actions=[D('suspension')];want=int(r['factor'])
            elif outline==2:
                u['core']['engine_rating']=int(r['rating'])
                if not int(r['rating']):u['max_speed']=0
                actions=[D('engine_weight')];want=int(r['weight'])
            elif outline==3:
                part=r['part'];partid=212 if part=='Ammo_IS.AC/5' else 394+next(i for i,s in enumerate(INTERNALS) if s.lower()==part.lower())
                actions=[D('crit_weight',partid)];want=int(r['weight'])
            else:
                if outline in (4,5,8):
                    for i,n in enumerate([10,10,10,10,20,15,15,10]):u['sections'][i].update(internal=n,internal_orig=n)
                if outline==4:
                    tech(u,r['structure']);u['construction']={'cargo_space':int(r['cargo'])}
                    if r['cockpit']=='small':u['specials2']|=1<<SPECIALS2.index('SmallCockpit_Tech')
                    gyro={'XL':'XLGyro_Tech','Hardened':'HDGyro_Tech','Compact':'CompactGyro_Tech'}.get(r['gyro'])
                    if gyro:u['specials2']|=1<<SPECIALS2.index(gyro)
                elif outline==5:
                    for j in range(int(r['bins'])):u['sections'][2]['slots'][j].update(type=212,data=int(r['rounds']),firemode=128 if r['mode']=='halfton' else 0,ammomode={'AP':8192,'caseless':262144}.get(r['mode'],0))
                elif outline==7:
                    u['core']['engine_rating']=int(r['rating']);u['sections'][2].update(internal_orig=int(r['original']),internal=int(r['current']))
                elif outline==8:u['sections'][0].update(armor=int(r['armor']),armor_orig=int(r['armor']))
                actions=[dict(op='construction_validate',correct=False,interactive=int(r.get('interactive',0))),D('ammo_weight')]
                want=int(r.get('weight',r.get('design',0)))
            d=a.run(f'weights/{outline}-{line}',document(actions,units=[u]),'diagnostic' if outline<=3 else 'ordinary');actual=d['results'][0]
            if outline==5:a.eq('remaining ammo',d['results'][1],int(r['current']));actual=actual['terms'].get('equipment',0)
            elif outline==8:actual=actual['terms'].get('armor',0)
            elif outline in (4,7):actual=actual['total']
            a.eq('source expected mass/factor',actual,want)
