"""Derived and immediate technologies, independently read from source tables."""
from qa.construction_qa_common import *
from qa.construction_qa_numeric import blank,table,tech

def U():return dict(op='diagnose',kind='update_specials',args=[])
def run(a):
    parts=table('internals');first=table('specials');second=table('specials2')
    flag_names={'FF':'FerroFibrous_Tech','ES':'EndoSteel_Tech','MASC':'Masc','BAP':'BeagleProbe','ECM':'ECM','Angel':'AngelECM_Tech','Bloodhound':'BloodhoundProbe_Tech','TC':'TargComp_Tech','TSM':'TripleMyomerTech'}
    def mask(flag):
        flag=flag_names.get(flag,flag)
        return ('specials',1<<first.index(flag)) if flag in first else ('specials2',1<<second.index(flag))
    for outline in (1,2,3,4):
        for line,r in examples('technology',outline):
            u=blank(r.get('unit','Mech'));actions=[]
            if outline==1:
                tech(u,'Clan' if r['base']=='Clan' else 'standard');count=int(r['count']);coords=[(loc,j) for loc in (2,3,4,0,1) for j in range(12)]
                for loc,j in coords[:count]:u['sections'][loc]['slots'][j].update(type=394+parts.index(r['part']),firemode=1 if r['condition']=='destroyed' else 0)
                actions=[U(),I()]
            elif outline==2:actions=[E(r['operation'],r['text'].replace('~',' ')),I()]
            elif outline==3:
                u['specials']=1|16|1024;u['infantry_specials']=1
                for loc in range(8):
                    u['sections'][loc]['config']=1
                    for j,p in enumerate(('CASE','TripleStrengthMyomer','Masc','Ecm')):u['sections'][loc]['slots'][j].update(type=394+parts.index(p),data=7)
                actions=[E('deltech',r['text']),I()]
            else:
                layout=r['layout'];u['specials']=1024 if r['ecm']=='1' else 0
                if 'NSS' in layout:
                    for loc in range(7):
                        if loc==0 and 'and-LA' in layout:continue
                        u['sections'][loc]['slots'][0]['type']=394+parts.index('NullSig_Device')
                else:
                    for loc in (0,1,2,3,5,6):
                        if loc==0 and 'and-LA' in layout:continue
                        for j in (0,1):u['sections'][loc]['slots'][j]['type']=394+parts.index('StealthArmor')
                    if 'with-ECM-slot' in layout:u['sections'][4]['slots'][0]['type']=415
                actions=[U(),I()]
            d=a.run(f'technology/{outline}-{line}',document(actions[:-1]+[R(),actions[-1]],units=[u]));state=d['results'][-1]['units']['u']
            if outline==1:
                field,b=mask(r['flag']);a.eq('derived threshold',bool(state[field]&b),r['enabled']=='1')
            elif outline==2:
                want={'Clan-set':(32,0,0),'Angel-set':(0,4096,0),'swarm-set':(0,0,1)}.get(r['outcome'],(0,0,0));a.eq('strict tech parser',[state['specials'],state['specials2'],d['results'][-2]['infantry_specials']],list(want))
                # Infantry flags are exposed in the brief tech output as well.
                if r['outcome']=='swarm-set':a.eq('infantry command succeeded',d['results'][0]['ok'],True)
            elif outline==3:
                wanted=sum(mask(p)[1] for p in r['tech'].split('+')) if r['tech']!='none' else 0;a.eq('remaining tech',state['specials'],wanted)
                a.eq('residual data retained',[[s['data'] for s in sec['slots'][:4]] for sec in state['sections']],[[7]*4]*8)
            else:a.eq('distributed tech',[bool(state['specials2']&16),bool(state['specials2']&1)],[r['nss']=='1',r['stealth']=='1'])
    effects={'CASE':('config',1),'TripleStrengthMyomer':('specials',1),'Masc':('specials',16),'C3Master':('specials',128),'C3Slave':('specials',256),'ArtemisIV':('specials',512),'Ecm':('specials',1024),'BeagleProbe':('specials',2048),'Light_BAP':('specials',32768),'TAG':('specials2',32768),'AngelEcm':('specials2',4096),'C3i':('specials2',32),'BloodhoundProbe':('specials2',2048),'TargetingComputer':('specials2',16777216)}
    inputs=[(line,r) for line,r in examples('equipment',4)]
    inputs += [(1000+i,dict(unit='Mech',part=p,section='LT',data='7',stored='7',effect='source-immediate')) for i,p in enumerate(effects)]
    for line,r in inputs:
        u=blank(r['unit']);loc=0 if r['section']=='LS' else 2;u['sections'][loc]['slots'][0].update(firemode=7,ammomode=3)
        d=a.run(f'equipment/4-{line}',document([E('addspecial',f"{r['part']} {r['section']} 1 {r['data']}"),R(),I()],units=[u]));res,out,state=d['results'];slot=out['slots'][loc][0]
        a.eq('special data/modes',[slot['data'],slot['fire'],slot['ammo']],[int(r['stored']),7,3]);a.eq('special identity',slot['source_part_id'],0 if r['part']=='empty' else 394+parts.index(r['part']))
        if r['part'] in effects:
            field,b=effects[r['part']];actual=state['units']['u']['sections'][3 if r['unit']=='Vehicle' else loc]['config'] if field=='config' else state['units']['u'][field];a.eq('immediate flag',bool(actual&b),True)
    # Engine inference uses per-section counts, including the retained zero-CT compact quirk.
    for clan in (False,True):
        for ct,side in ((0,0),(3,0),(4,0),(6,1),(6,2),(6,3),(6,4)):
            u=blank();u['specials']=32 if clan else 0
            for loc,count in ((4,ct),(2,side)):
                for j in range(count):u['sections'][loc]['slots'][j]['type']=401
            d=a.run(f'technology/engine-{clan}-{ct}-{side}',document([U(),I()],units=[u]));want=(1<<26 if ct<4 else 0)|(1<<25 if side>3 else (1<<21 if clan else 1<<24) if side==2 else 1<<21 if side else 0)
            a.eq('source engine inference',d['results'][-1]['units']['u']['specials']&((1<<21)|(1<<24)|(1<<25)|(1<<26)),want)
    # Suit thresholds use live members; zero live members deliberately enables all five.
    suit_parts=['PurifierArmor','KageStealthUnit','AchileusStealthUnit','InfiltratorStealthUnit','InfiltratorIIStealthUnit']
    source=(CROOT/'mech.h').read_text()
    import re
    bits=[int(re.search(r'^#define\s+'+n+r'\s+(0x[\da-fA-F]+|\d+)',source,re.M)[1],0) for n in ('CS_PURIFIER_STEALTH_TECH','DC_KAGE_STEALTH_TECH','FWL_ACHILEUS_STEALTH_TECH','FC_INFILTRATOR_STEALTH_TECH','FC_INFILTRATORII_STEALTH_TECH')]
    # Resolve exact source spellings from the table, not production catalog output.
    suit_parts=[next(p for p in parts if p.lower().replace('_','').startswith(n)) for n in ('purifier','kage','achileus','infiltratorstealth','infiltratoriistealth')]
    for live in (0,1,2):
        for broken in (False,True):
            u=blank('Battlesuit')
            for i in range(live):u['sections'][i].update(internal=1,internal_orig=1)
            for j,p in enumerate(suit_parts):u['sections'][0]['slots'][j].update(type=394+parts.index(p),firemode=int(broken))
            d=a.run(f'technology/suits-{live}-{broken}',document([U(),R()],units=[u]));want=sum(bits) if live==0 or live==1 and not broken else bits[0] if live==1 else 0
            a.eq('live suit/source threshold',d['results'][-1]['infantry_specials']&sum(bits),want)
    # TC enables eligible beam/ballistic weapons; losing TC leaves existing ON_TC.
    u=blank();u['sections'][2]['slots'][0]['type']=394+parts.index('TargetingComputer')
    for loc,name in ((0,'IS.MediumLaser'),(1,'IS.SRM-2'),(3,'IS.Flamer')):
        u['sections'][loc]['slots'][0].pop('type');u['sections'][loc]['slots'][0]['weapon']=name
    d=a.run('technology/TC-retention',document([U(),R(),E('addspecial','empty LT 1'),U(),R()],units=[u]));r=d['results'];on=int(re.search(r'^#define\s+ON_TC\s+(0x[\da-fA-F]+|\d+)',source,re.M)[1],0)
    a.eq('TC eligible selection',[r[1]['slots'][i][0]['fire']&on for i in (0,1,3)],[on,0,0]);a.eq('TC removal retains flag',r[-1]['slots'][0][0]['fire']&on,on)
    for count,broken in ((4,0),(5,0),(10,0),(10,1),(10,6)):
        u=blank()
        for j in range(count):u['sections'][2]['slots'][j].update(type=394+parts.index('C3Master'),firemode=int(j<broken))
        d=a.run(f'technology/C3-{count}-{broken}',document([U(),I()],units=[u]));s=d['results'][-1]['units']['u']
        a.eq('C3 total',s['total_c3_masters'],count//5);a.eq('C3 working',s['working_c3_masters'],int(count>=5 and broken==0))
