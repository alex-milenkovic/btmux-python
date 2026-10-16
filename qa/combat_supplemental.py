"""Source-boundary procedures beyond the sampled combat APS tables."""
from combat_support import *

def interface_cases():
    invalid=[('json','{'),('duplicate-key','{"actions":[],"actions":[]}'),
      ('unknown-action',{'actions':[{'op':'invented'}]}),('unknown-unit',{'actions':[cmd('fire','0',unit='missing')]}),
      ('unknown-command',{'actions':[cmd('not-a-command')]}),('missing-actions',{}),
      ('duplicate-name',dict(units=[{'name':'u'},{'name':'u'}],actions=[])),
      ('duplicate-contact',dict(units=[{'name':'u','contact_id':'AB'},{'name':'v','contact_id':'ab'}],actions=[]))]
    for value in ('NaN','Infinity','-Infinity'):
        invalid.append(('nonfinite-'+value,'{"actions":[],"units":[{"name":"u","speed":'+value+'}]}'))
    for name,value in invalid:yield Case(value,lambda o:None,label='integration-input-'+name,invalid=True)
    for key,value in [('aim',9),('aim_type',99),('real_mass',-1),('gunnery',True),('speed',float('nan')),('speed',float('inf'))]:
        d=fixture();d['units'][0][key]=value
        yield Case(d,lambda o:None,label=f'integration-input-{key}-{value}',invalid=True)
    for name,action in [('negative-time',advance(-1)),('fractional-time',advance(.5)),('bad-diag',diag('unknown')),('unsafe-weapon',diag('combat-bth',weapon=-1,target='v')),('unsafe-part',diag('slot',section=4,slot=12)),('unknown-option',diag('combat-bth',weapon=0,target='v',expected=4))]:
        d=fixture();mount(d);d['actions']=[action]
        yield Case(d,lambda o:None,label='integration-input-'+name,invalid=True)
    for stream,values in [('attack_rolls',[]),('attack_rolls',[13]),('attack_rolls',[True]),('missile_pre_roll',[0,1,2]),('missile_pre_roll',[])]:
        d=fixture();mount(d,'IS.LRM-5',ammo=10);d['random']['streams'][stream]=values;d['actions']=[cmd('fire','0')]
        if stream!='attack_rolls':d['random']['streams']['attack_rolls']=[12]
        yield Case(d,lambda o:None,label=f'integration-input-stream-{stream}-{str(values)}',invalid=True)
    d=fixture();mount(d);slot(d,4,temp_failure=1,data=4);d['actions']=[inspect(),inspect()]
    def pure(o):checks((o['results'][0],o['results'][1]),(o['results'][1],o['state']),(o['draws'],[]))
    yield Case(d,pure,label='integration-inspection-pure',repeat=True)
    d=fixture();mount(d);d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0'),advance(7),inspect()]
    yield Case(d,lambda o:eq(loss(o),5),label='integration-fresh-determinism',repeat=True,mode='normal')

def range_cases():
    # Each boundary is taken from FindBTHByRange, including int(x+.95).
    for water in (False,True):
        for signature,bit in [('ordinary',0),('stealth',64),('nullsig',128)]:
            for boundary,bracket,ordinary in [(0,'SHORT',0),(3,'SHORT',0),(3.049,'SHORT',0),(3.051,'MED',2),(6,'MED',2),(6.049,'MED',2),(6.051,'LONG',4),(9,'LONG',4),(9.049,'LONG',4),(9.051,'EXTREME',8),(12,'EXTREME',8),(12.049,'EXTREME',8),(12.051,'TOFAR',1000)]:
                d=fixture(False);d['units'][1]['status2']=bit
                mount(d,range_min=0,range_short=3,range_medium=6,range_long=9,
                      range_min_water=0,range_short_water=3,range_medium_water=6,range_long_water=9)
                if water:d['units'][0]['at'][2]=-2;d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-2)]
                d['actions']=[diag('combat-range',weapon=0,target='v',distance=boundary)]
                modifier=int(ordinary*1.5) if bit and ordinary<1000 else ordinary
                yield Case(d,lambda o,bracket=bracket,modifier=modifier:checks((o['results'][0]['bracket'],bracket),(o['results'][0]['modifier'],modifier)),label=f'ranges-boundary-{water}-{signature}-{boundary}')
    for water_min,air_min,distance,expected in [(4,1,2,0),(4,4,2,3),(4,1,0,4),(0,4,0,0),(-1,4,0,0)]:
        d=fixture(False);mount(d,range_min=air_min,range_short=5,range_medium=8,range_long=12,range_min_water=water_min,range_short_water=5,range_medium_water=8,range_long_water=12)
        d['units'][0]['at'][2]=-2;d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-2)]
        d['actions']=[diag('combat-range',weapon=0,target='v',distance=distance)]
        yield Case(d,lambda o,expected=expected:eq(o['results'][0]['modifier'],expected),label=f'ranges-water-min-fallthrough-{water_min}-{air_min}-{distance}')
    d=fixture(False);mount(d,range_short_water=0);d['units'][0]['at'][2]=-2;d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-2)]
    d['actions']=[diag('combat-range',weapon=0,target='v',distance=0)]
    yield Case(d,lambda o:checks((o['results'][0]['bracket'],'NOWATER'),(o['results'][0]['modifier'],5000)),label='ranges-water-no-capability')
    for distance,expected in [(.3,0),(.3049,0),(.3051,2),(.6,2),(.6051,4),(.9051,8),(1.2051,1000)]:
        d=fixture(False);mount(d,special=0x80000,range_min=0,range_short=3,range_medium=6,range_long=9)
        d['actions']=[diag('combat-range',weapon=0,target='v',distance=distance)]
        yield Case(d,lambda o,expected=expected:eq(o['results'][0]['modifier'],expected),label=f'ranges-personal-rounding-{distance}')
    for half in (0,1):
        for hot in (False,True):
            for distance in (0,1,2,3):
                d=fixture(False);d['config']['hotloadaddshalfbthmod']=half
                mount(d,'IS.LRM-5',fire=64 if hot else 0,range_min=3)
                expected=(3-distance+(distance!=0)) if not hot else int((4-distance)/2) if half else 0
                d['actions']=[diag('combat-range',weapon=0,target='v',distance=distance)]
                yield Case(d,lambda o,expected=expected:eq(o['results'][0]['modifier'],expected),label=f'ranges-hotload-{half}-{hot}-{distance}')

MODE_ROWS=[('flamerheat','IS.Flamer','firemode',65536),('ultra','IS.UltraAC/5','firemode',1024),
 ('explosive','IS.NarcBeacon','ammomode',4),('lbx','IS.LB10-XAC','ammomode',1),
 ('armorpiercing','IS.AC/10','ammomode',8192),('caseless','IS.AC/10','ammomode',262144),
 ('flechette','IS.AC/10','ammomode',16384),('incendiary','IS.AC/10','ammomode',32768),
 ('precision','IS.AC/10','ammomode',65536),('rapidfire','IS.AC/10','firemode',2048),
 ('stinger','IS.LRM-5','ammomode',131072),('gattling','IS.MachineGun','firemode',4096),
 ('artemis','IS.LRM-5','ammomode',2),('narc','IS.LRM-5','ammomode',4),
 ('swarm','IS.LRM-5','ammomode',128),('sguided','IS.LRM-5','ammomode',524288),
 ('atmrange','IS.LRM-5','ammomode',1048576),('atmexplosive','IS.LRM-5','ammomode',2097152),
 ('swarm1','IS.LRM-5','ammomode',256),('inferno','IS.SRM-4','ammomode',64),
 ('hotload','IS.LRM-5','firemode',64),('cluster','IS.Sniper','ammomode',8),
 ('smoke','IS.SRM-4','ammomode',32),('mine','IS.SRM-4','ammomode',16)]

def mode_cases():
    for command,name,word,bit in MODE_ROWS:
        d=fixture();mount(d,name,fire=16,crits=1)
        if command=='artemis':slot(d,4,1,special='ARTEMIS_IV',data=1)
        d['actions']=[cmd(command,'0'),inspect(),cmd(command,'0'),inspect(),cmd(command,'0,0')]
        def check(o,word=word,bit=bit):
            initial=16 if word=='firemode' else 0
            checks((state(o,index=1)['sections'][4]['slots'][0][word],initial|bit),(rawslot(o)[word],initial),(rawslot(o)['firemode']&16,16))
            assert o['results'][0]['accepted'],o['results'][0]
        yield Case(d,check,label='modes-wrapper-'+command,mode='normal')
    for special in (2,4):
        d=fixture();d['units'][0]['specials']=special;d['actions']=[cmd('ams'),inspect(),cmd('ams')]
        yield Case(d,lambda o:checks((state(o,index=1)['status']&2048,2048),(state(o)['status']&2048,0)),label=f'modes-ams-toggle-{special}',mode='normal')
    for condition in ('stopped','destroyed','unconscious','blind','caller','weapon-busy','section-busy','dead-section','part-disabled','feed-damage','one-shot','rocket'):
        d=fixture();mount(d,'IS.LRM-5',crits=1);u=d['units'][0]
        if condition=='stopped':u['started']=False
        if condition=='destroyed':u['destroyed']=True
        if condition=='unconscious':u['conscious']=False
        if condition=='blind':u['blinded']=True
        if condition=='caller':u.update(caller_is_pilot=False,in_character=True)
        if condition=='weapon-busy':slot(d,4,data=10)
        if condition=='section-busy':section(d,4,recycle=10)
        if condition=='dead-section':section(d,4,armor=0,internal=0,rear=0)
        if condition=='part-disabled':slot(d,4,firemode=2)
        if condition=='feed-damage':slot(d,4,weap_damage_flags=64,firemode=8)
        if condition=='one-shot':slot(d,4,firemode=256)
        if condition=='rocket':d['units'][0]['weapons'][0]['metadata']['special']=65536
        d['actions']=[cmd('hotload','0')]
        # Number lookup checks slot function, not the section's internal value;
        # the mode callback also intentionally continues for physical recycle.
        yield Case(d,lambda o,condition=condition:checks((o['results'][0]['accepted'],condition in ('section-busy','dead-section')),(rawslot(o)['firemode']&64,64 if condition in ('section-busy','dead-section') else 0)),label='modes-guard-'+condition,mode='normal')
    d=fixture();mount(d,crits=1);mount(d,'IS.UltraAC/5',index=1,crits=1);d['actions']=[cmd('ultra','0,1')]
    yield Case(d,lambda o:checks((rawslot(o)['firemode']&1024,0),(rawslot(o,index=1)['firemode']&1024,1024)),label='modes-invalid-capability-continues',mode='normal')

def inherited_locations():
    # These independent C chart vectors were reviewed in the preceding Damage
    # card. Re-execute them against this card's combat CLI and current state.
    import damage_tables
    for old in damage_tables.cases():
        yield Case(old.document,old.check,label='locations-retained-'+old.label,blocked=old.blocked,note=old.note)

def retained_location_dispatch():
    import re,subprocess,json
    import damage_feature_cases,damage_targeting
    def adapt(old,label):
        d=deepcopy(old.document)
        for action in d['actions']:
            if action.get('op')=='command' and action.get('name')=='target':action['name']='lock'
        return Case(d,old.check,label=label,blocked=old.blocked,note=old.note,
                    mode='normal' if any(a.get('name')=='fire' for a in d['actions']) else 'diagnostic')
    for stem in ('locations','vehicle_locations'):
        irpath=OUTPUT/f'retained-damage-{stem}.json'
        subprocess.run(['gherkin-parser',f'features/damage_criticals/{stem}.feature','./'+str(irpath.relative_to(ROOT))],cwd=ROOT,env=ENV,check=True,capture_output=True,text=True)
        for scenario in json.loads(irpath.read_text())['scenarios']:
            n=int(re.search(r' (\d+) - ',scenario['name'])[1])
            for i,params in enumerate(scenario['examples'],1):
                for j,old in enumerate(getattr(damage_feature_cases,stem)(n,params),1):
                    yield adapt(old,f'locations-retained-APS-{stem}-{n:02d}-{i:02d}-{j:02d}')
    for old in damage_targeting.cases():yield adapt(old,'locations-retained-'+old.label)

def targeting_cases():
    from combat_examples import targeting,SS_MESSAGES
    for distance in (0,8.999,9,19.999,20):
        for tons in (-20,-19,0,19,20):
            index=(0 if tons<=-20 else 2 if tons>=20 else 1)+3*(0 if distance<9 else 1 if distance<20 else 2)
            c=targeting(2,dict(range=str(distance),tons=str(tons),index=str(index)))[0]
            c.label=f'targeting-sixth-boundary-{distance}-{tons}';yield c
    for severity,index in [(-1,0),(0,0),(1,1),(2,2),(3,3),(4,4),(5,5),(6,6),(7,7),(8,8),(9,8)]:
        d=fixture(False);d['pending_events']=[dict(unit='v',callback='sixth-sense',data=severity,delay=2)]
        d['actions']=[advance(1),inspect(),advance(1)]
        yield Case(d,lambda o,index=index:checks((sum(m in SS_MESSAGES for m in state(o,'v',1)['messages']),0),(state(o,'v')['messages'][-1],SS_MESSAGES[index])),label=f'targeting-sixth-callback-bound-{severity}')
    for condition in ('roll9','observer','destroyed','no-ability'):
        d=fixture(False);d['units'][0]['target']=-1;v=d['units'][1];v['specials']=262144
        if condition=='observer':d['units'][0]['observer']=True
        if condition=='destroyed':v['destroyed']=True
        if condition=='no-ability':v['specials']=0
        d['random']['streams'].update(sixth_sense_rolls=[9],sixth_sense_delay=[])
        d['actions']=[cmd('lock','01'),advance(3)]
        def check(o,condition=condition):
            checks((draws(o,'sixth_sense_delay'),[]),(draws(o,'sixth_sense_rolls'),[9] if condition=='roll9' else []),(sum(m in SS_MESSAGES for m in state(o,'v')['messages']),0))
        yield Case(d,check,label='targeting-sixth-suppression-'+condition,mode='normal')
    d=fixture(False);d['units'][0]['target']=-1;d['units'][1]['specials']=262144
    d['random']['streams'].update(sixth_sense_rolls=[8,8],sixth_sense_delay=[2,2])
    d['actions']=[cmd('lock','01'),cmd('lock','01'),advance(2)]
    yield Case(d,lambda o:eq(state(o,'v')['messages'].count(SS_MESSAGES[1]),2),label='targeting-sixth-duplicate-warnings',mode='normal')
    for cls,names in [('MECH',[('LA',0),('RA',1),('LT',2),('RT',3),('CT',4),('LL',5),('RL',6),('HEAD',7)]),('GROUND',[('F',2),('L',0),('RS',1),('A',3),('T',4)]),('BA',[('S'+str(i+1),i) for i in range(8)])]:
        for name,index in names:
            d=fixture(False);d['units'][1]['class']=cls;d['actions']=[cmd('target',name),inspect(),cmd('target','-')]
            def check(o,index=index,cls=cls):
                checks((o['results'][0]['accepted'],True),(state(o,index=1)['aim'],index),(state(o,index=1)['aim_type'],{'MECH':0,'GROUND':1,'BA':8}[cls]),(state(o)['aim'],8))
            yield Case(d,check,label=f'targeting-named-section-{cls}-{name}',mode='normal')
    for args in [[],['junk'],['LA','extra']]:
        d=fixture();d['actions']=[inspect(),cmd('target',*args)]
        yield Case(d,lambda o:checks((o['results'][1]['accepted'],False),(state(o)['aim'],state(o,index=0)['aim'])),label='targeting-aim-invalid-'+str(args),mode='normal')
    d=fixture();d['units'][0]['target']=-1;d['actions']=[cmd('target','CT'),cmd('target','-')]
    yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),(o['results'][1]['accepted'],True),(state(o)['aim'],8)),label='targeting-aim-no-lock',mode='normal')
    for args in [[],['1','2','HH'],['1','2','X'],['1','2','H','x'],['12','1'],['1','12'],['-1','1']]:
        d=fixture(False);d['actions']=[inspect(),cmd('lock',*args)]
        def unchanged(o):
            eq(o['results'][1]['accepted'],False)
            for key in ('target','targ_x','targ_y','targ_z','status','fire_adjustment','events'):eq(state(o)[key],state(o,index=0)[key])
        yield Case(d,unchanged,label='targeting-lock-invalid-'+str(args),mode='normal')
    d=fixture(False);d['config']['lock_tick']=5;d['units'][0]['target']=-1
    d['actions']=[cmd('lock','01'),advance(2),cmd('lock','4','4','H'),inspect(),advance(3),inspect(),advance(2)]
    yield Case(d,lambda o:checks(([e['deadline'] for e in events(o,kind='LOCK',index=3)],[7]),([e['deadline'] for e in events(o,kind='LOCK',index=5)],[7]),(events(o,kind='LOCK'),[])),label='targeting-lock-replaces-event',mode='normal')
    d=fixture(False);d['units'].append(dict(name='s',at=[4,3,0],contact_id='SS'));d['actions']=[cmd('spot','SS',unit='s'),cmd('spot','SS'),configure(fire_adjustment=3),cmd('lock','4','4','H',unit='s')]
    yield Case(d,lambda o:eq(state(o)['fire_adjustment'],0),label='targeting-spotter-clears-firer-adjustment',mode='normal')

PREF_ROWS=[('MWSafety',1,True,False),('SLWarn',2,False,False),('AutoFall',4,False,True),
 ('ArmorWarn',8,True,False),('AmmoWarn',16,True,False),('AutoconShutdown',64,False,True),
 ('FFSafety',128,False,False),('BTHDebug',512,False,True)]

def preference_cases():
    d=fixture(False);d['actions']=[cmd('mechprefs')]
    def display(o):
        rows=o['results'][0]['preferences'];eq(len(rows),8)
        for row,(name,bit,invert,negative) in zip(rows,PREF_ROWS):
            checks((row['name'],name),(row['bit'],0),(row['state'],'ON' if invert else 'OFF'))
            assert ('%cr' if invert==negative else '%cg') in row['text'],row
    yield Case(d,display,label='preferences-all-zero-display',mode='normal')
    for name,bit,invert,negative in PREF_ROWS:
        d=fixture(False);d['units'][0]['prefs']=2048
        d['actions']=[cmd('mechprefs',name.lower()),inspect(),cmd('mechprefs',name,'oN'),cmd('mechprefs',name,'ON'),inspect(),cmd('mechprefs',name,'OFF'),cmd('mechprefs',name,'off')]
        def check(o,bit=bit,invert=invert):
            checks((state(o,index=1)['prefs'],2048|bit),(state(o,index=4)['prefs'],2048 if invert else 2048|bit),(state(o)['prefs'],2048|bit if invert else 2048))
        yield Case(d,check,label='preferences-toggle-explicit-'+name,mode='normal')
    for args in [('unknown',),('AmmoWarn','maybe')]:
        d=fixture(False);d['actions']=[cmd('mechprefs',*args)]
        yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),(state(o)['prefs'],0)),label='preferences-invalid-'+str(args),mode='normal')
    for condition in ('stopped','destroyed','unconscious','blind','caller'):
        d=fixture(False);u=d['units'][0]
        if condition=='stopped':u['started']=False
        if condition=='destroyed':u['destroyed']=True
        if condition=='unconscious':u['conscious']=False
        if condition=='blind':u['blinded']=True
        if condition=='caller':u.update(caller_is_pilot=False,in_character=True)
        d['actions']=[cmd('mechprefs','AmmoWarn','OFF')]
        yield Case(d,lambda o,condition=condition:checks((o['results'][0]['accepted'],condition in ('stopped','destroyed')),(state(o)['prefs'],16 if condition in ('stopped','destroyed') else 0)),label='preferences-common-'+condition,mode='normal')
        d=deepcopy(d);d['actions']=[cmd('safety','OFF'),cmd('safety','query'),cmd('safety','ON')]
        yield Case(d,lambda o:checks((o['results'][0]['accepted'],True),(o['results'][1]['preference']['state'],'OFF'),(state(o)['prefs'],0)),label='preferences-safety-no-common-'+condition,mode='normal')
    d=fixture(False);d['units'][0]['class']='MW';d['actions']=[cmd('safety','OFF')]
    yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),(state(o)['prefs'],0)),label='preferences-safety-mw-rejected',mode='normal')
    for target,enabled in [('MW',False),('MW',True),('friendly',False),('friendly',True)]:
        d=fixture();mount(d);d['random']['streams']['attack_rolls']=[12]
        if target=='MW':d['units'][1]['class']='MW'
        else:d['units'][1]['team']=0
        pref='MWSafety' if target=='MW' else 'FFSafety'
        d['actions']=[cmd('mechprefs',pref,'ON' if enabled else 'OFF'),cmd('fire','0')]
        yield Case(d,lambda o,enabled=enabled,target=target:checks((o['results'][1]['accepted'],not enabled),(loss(o),0 if enabled else 400 if target=='MW' else 5),(draws(o,'attack_rolls'),[] if enabled else [12])),label=f'preferences-live-safety-{target}-{enabled}',mode='normal')
    d=fixture();mount(d);d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('mechprefs','BTHDebug','ON'),cmd('fire','0')]
    def debug(o):
        eq(o['results'][1]['attack']['bth'],4)
        assert any('BTH' in text for text in state(o)['messages']),state(o)['messages']
    yield Case(d,debug,label='preferences-debug-live-fire',mode='normal')
    for command in ('autoturret','disableweap'):
        d=fixture(False);d['units'][0]['class']='GROUND';section(d,4,internal=0)
        if command=='disableweap':mount(d)
        d['actions']=[cmd(command,*(['0'] if command=='disableweap' else []))]
        yield Case(d,lambda o:eq(o['results'][0]['accepted'],False),label='preferences-'+command+'-ineligible',mode='normal')

def group_cases():
    d=fixture(False);mount(d);d['actions']=[cmd('addtic','0','0'),cmd('addtic','0','0'),inspect(),cmd('cleartic','0'),cmd('listtic','0'),cmd('firetic','0')]
    yield Case(d,lambda o:checks((state(o,index=2)['tics'][0],[0]),(state(o)['tics'][0],[]),(o['results'][4]['text'],'No weapons in tic.'),(o['results'][5]['text'],'Firing weapons in tic #0!\n*Click* (the tic contained no weapons)')),label='groups-add-clear-empty',mode='normal')
    for command,args in [('addtic',['4','0']),('addtic',['-1','0']),('addtic',['0','96']),('addtic',['0','-1']),('addtic',['0','96,0']),('addtic',['0','0-96']),('deltic',['4','0']),('cleartic',['4']),('firetic',['4']),('listtic',['4']),('firetic',['-1']),('listtic',['-1'])]:
        d=fixture(False);mount(d);d['actions']=[cmd(command,*args)]
        yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),(state(o)['tics'],[[],[],[],[]]),(draws(o,'attack_rolls'),[])),label='groups-invalid-'+command+'-'+str(args),mode='normal')
    for command in ('addtic','deltic','cleartic','listtic','firetic'):
        for condition in ('stopped','destroyed','unconscious','blind','caller','hold'):
            d=fixture(False);mount(d);u=d['units'][0]
            if condition=='stopped':u['started']=False
            if condition=='destroyed':u['destroyed']=True
            if condition=='unconscious':u['conscious']=False
            if condition=='blind':u['blinded']=True
            if condition=='caller':u.update(caller_is_pilot=False,in_character=True)
            if condition=='hold':u['status2']=8388608
            d['actions']=[cmd(command,'0',*(['0'] if command=='addtic' else []))]
            allowed=(condition in ('stopped','destroyed','caller','hold') and command!='firetic')
            yield Case(d,lambda o,allowed=allowed:eq(o['results'][0]['accepted'],allowed),label=f'groups-common-{command}-{condition}',mode='normal')
    for cls,movement,loc,label in [('MECH','BIPED',0,'LA'),('MECH','QUAD',0,'FLL'),('GROUND','TRACK',0,'LS'),('GROUND','TRACK',2,'FS'),('VTOL','VTOL',5,'R'),('AERO','FLY',0,'N'),('DS','FLY',0,'RW'),('BA','BIPED',0,'S1')]:
        d=fixture(False);d['units'][0].update(**{'class':cls,'movement':movement},tics=[[0]])
        mount(d,loc=loc,index=4,crits=1);slot(d,loc,4,firemode=1)
        d['actions']=[cmd('listtic','0')]
        yield Case(d,lambda o,label=label:checks((o['results'][0]['result'][0][0][1],label),(o['results'][0]['result'][0][0][3],'(*)')),label=f'groups-list-class-{cls}-{movement}-{loc}',mode='normal')
    for members,remaining in [([40,41],[]),([0,40,41],[0])]:
        d=fixture(False)
        if 0 in members:mount(d)
        d['units'][0]['tics']=[members];d['actions']=[cmd('listtic','0')]
        def check(o,remaining=remaining):
            eq(state(o)['tics'][0],remaining)
            eq(o['results'][0]['result'][0][-2:],['Unknown - error of some sort occured']*2)
        yield Case(d,check,label='groups-list-stale-'+str(members),mode='normal',note='Exact C menu format probe and callback sequence.')
    for explicit in ('01','3 2'):
        d=fixture();mount(d,crits=1);mount(d,loc=3,crits=1);slot(d,4,data=5);d['units'][0]['tics']=[[0,1]]
        if explicit!='01':d['actions']=[cmd('lock','3','2','H')]
        d['random']['streams']['attack_rolls']=[12];d['actions'] += [cmd('firetic','0',*explicit.split())]
        yield Case(d,lambda o:checks((len(draws(o,'attack_rolls')),1),(loss(o),5),(rawslot(o,3)['data'],40),(rawslot(o,4)['data'],5)),label='groups-refused-member-continues-'+explicit,mode='normal')

def bth_cases():
    def emit(d,label,**terms):
        if not d['actions'] or d['actions'][-1].get('kind')!='combat-bth':d['actions'].append(diag('combat-bth',weapon=0,target='v',distance=2))
        def check(o):
            row=o['results'][-1]
            for name,value in terms.items():eq(row[name],value)
        return Case(d,check,label='bth-term-'+label)
    for present in (False,True):
        for term in ('base','section','water','stabilizer','AP','haywire','homing','pulse','MRM','heavy','rocket','selfspot'):
            d=fixture(False);mount(d);u,v=d['units'];expected=0;key='other_mods'
            if term=='base':u['base_to_hit']=3 if present else 0;expected=3*present
            if term=='section':section(d,4,basetohit=2 if present else 0);key='section_mod';expected=2*present
            if term=='water':
                d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-2)];u['at'][2]=-1 if present else 0;expected=int(present)
            if term=='stabilizer':u['speed']=10.75;section(d,4,config=32 if present else 0);key='attacker_move';expected=2 if present else 1
            if term=='AP':u['weapons'][0]['ammo_mode']=8192 if present else 0;key='ammo_mode_mod';expected=int(present)
            if term=='haywire':section(d,4,specials=4 if present else 0);key='pod_mod';expected=int(present)
            if term=='homing':u['weapons'][0]['ammo_mode']=4;section(d,4,unit=1,specials=2 if present else 1);key='pod_mod';expected=-int(present)
            if term in ('pulse','MRM','heavy','rocket'):
                u['weapons'][0]['metadata']={'special':{'pulse':1,'MRM':32768,'heavy':33554432,'rocket':65536}[term] if present else 0};key='weapon_mod';expected=(-2 if term=='pulse' else 1)*present
            if term=='selfspot':u['spotter']='u' if present else -1;key='spotting_mod';expected=int(present)
            yield emit(d,f'{term}-{present}',**{key:expected})
    for heat,expected in [(0,0),(7,0),(8,1),(12,1),(13,2),(16,2),(17,3),(23,3),(24,4)]:
        d=fixture(False);mount(d);d['units'][0]['heat']=heat;yield emit(d,f'heat-{heat}',heat_mod=expected)
    for bits,modifiers in [(0,[0,0,0,0]),(32,[1,2,3,0]),(16,[0,1,2,0]),(64,[0,1,2,0]),(128,[1,1,2,0])]:
        for distance,modifier in zip((2,5,8,11),modifiers):
            d=fixture(False);mount(d,range_min=0,range_short=3,range_medium=6,range_long=9);d['units'][1]['infantry_specials']=bits
            d['actions']=[diag('combat-bth',weapon=0,target='v',distance=distance)]
            yield emit(d,f'infantry-{bits}-{distance}',other_mods=modifier)
    for tc in (0,1,2):
        for distance in (6,6.051):
            d=fixture(False);mount(d);d['actions']=[configure(targcomp=tc),diag('combat-bth',weapon=0,target='v',distance=distance)]
            expected=0 if not tc else -1 if (tc==1)==(distance==6) else 1
            yield emit(d,f'tc-range-{tc}-{distance}',targcomp_mod=expected)
    for tech in (0,65536):
        for flying in (False,True):
            d=fixture(False);mount(d);d['units'][0]['specials']=tech;v=d['units'][1];v.update(**{'class':'VTOL'})
            if flying:v['at'][2]=1
            d['actions']=[configure(targcomp=4)]
            yield emit(d,f'AA-{tech}-{flying}',targcomp_mod=(-3 if tech else -2) if flying else 1)
    for mode in (0,131072):
        for cls,z,cocoon,speed,expected in [('VTOL',1,0,0,-3),('VTOL',0,0,1,1),('MECH',0,1,0,-1),('MECH',0,0,0,0)]:
            d=fixture(False);mount(d,mode=mode);v=d['units'][1];v.update(**{'class':cls,'speed':speed,'cocoon':cocoon});v['at'][2]=z
            yield emit(d,f'stinger-{mode}-{cls}-{z}-{cocoon}',other_mods=(expected if mode else int(cls=='VTOL' and bool(speed)))-2*int(cocoon>0))
    for mode in (0,1):
        for cls in ('MECH','VTOL'):
            d=fixture(False);mount(d,mode=mode);d['units'][1]['class']=cls
            yield emit(d,f'LBX-{mode}-{cls}',ammo_mode_mod=(-3 if cls=='VTOL' else -1) if mode else 0)
    for aim in (4,7,8):
        for stopped in (False,True):
            for tc in (False,True):
                d=fixture(False);mount(d,fire=16 if tc else 0);d['units'][0].update(aim=aim,target=2);d['units'][1]['started']=not stopped
                expected=(7 if stopped else 25) if aim==7 else (-1 if stopped or aim==8 else 3) if tc else 0
                yield emit(d,f'aim-{aim}-{stopped}-{tc}',aim_mod=expected)
    for mode in (0,65536):
        for stopped in (False,True):
            d=fixture(False);mount(d,mode=mode);d['units'][1]['started']=not stopped
            yield emit(d,f'precision-negative-{mode}-{stopped}',target_move=-4 if stopped and not mode else 0)
    for tagger in ('self','enemy','friendly','dangling','none'):
        for stopped in (False,True):
            d=fixture(False);mount(d,'IS.LRM-5',mode=524288,range_min=0);u,v=d['units'];v.update(speed=64.5,started=not stopped)
            d['units'].append(dict(name='s',at=[4,3,0],team=2 if tagger=='enemy' else 0))
            d['actions']=[configure(unit='v',tagged_by={'self':'u','enemy':'s','friendly':'s','dangling':999,'none':-1}[tagger])]
            modifier=-2 if stopped else 2
            if tagger=='dangling':modifier=0
            if tagger=='friendly':modifier=min(0,modifier)
            yield emit(d,f'semiguided-{tagger}-{stopped}',target_move=modifier)
    for extended in (0,1):
        for speed,expected in [(9*10.75,3),(9*10.75+.01,3),(10*10.75,4),(14*10.75-.01,4),(14*10.75,5)]:
            d=fixture(False);mount(d);d['config']['extendedmovemod']=extended;d['units'][1]['speed']=speed
            if not extended and speed>9*10.75:expected=4
            yield emit(d,f'extended-{extended}-{speed}',target_move=expected)
    for heat in (8,9):
        d=fixture(False);mount(d);d['units'][0].update(specials=1,heat=heat,speed=48,max_speed=64.5)
        yield emit(d,f'TSM-hot-walk-{heat}',attacker_move=1 if heat==9 else 2)
    for whose in ('u','v'):
        for height in (-1,0,1):
            d=fixture(False);mount(d);d['units'][1]['at'][2]=height
            # btmacros.h:407 ignores MechDugIn's argument and uses local mech.
            d['units'][0 if whose=='u' else 1]['tank_crit_status']=4
            yield emit(d,f'dug-{whose}-targetZ{height}',other_mods=3 if whose=='u' and height>=0 else 0)
    for who in ('u','v'):
        d=fixture(False);mount(d);d['units'][0 if who=='u' else 1].update(**{'class':'AERO'},at=[3,3 if who=='u' else 2,1])
        yield emit(d,f'aero-strafing-{who}',other_mods=2 if who=='u' else 0)
    for mode,fallen,expected in [(0,False,0),(65536,False,-4),(131072,False,1),(131072,True,0)]:
        d=fixture(False);mount(d);d['units'][1].update(status2=mode,fallen=fallen)
        yield emit(d,f'target-mode-{mode}-{fallen}',other_mods=expected)
    d=fixture(False);mount(d,'IS.LRM-5',range_min=3);d['actions']=[diag('combat-bth',weapon=0,target='v',distance=2)]
    yield emit(d,'minimum-retains-TOFAR',range_bracket='TOFAR',range_mod=2)
    # One additive calculation: base4 + water1 + stabilizer2 + pulse(-2)
    # + precision-adjusted targetMove0 + light woods1 + BA1 = 7.
    d=fixture(False);mount(d,mode=65536,special=1,range_short_water=3,range_medium_water=6,range_long_water=9)
    d['units'][0].update(at=[3,3,-1],speed=10.75);section(d,4,config=32)
    d['units'][1].update(**{'class':'BA'},speed=43)
    d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-1),dict(at=[3,2],terrain='LIGHT_FOREST',elevation=0)]
    yield emit(d,'additive-water-stabilizer-pulse-precision-terrain-BA',total=7,other_mods=2,attacker_move=2,weapon_mod=-2,target_move=0,terrain_mod=1)

def mine_cases():
    for typ,number in [('Standard',1),('Inferno',2),('Command',3),('Vibra',4),('Trigger',5)]:
        for extra in (None,80):
            d=fixture(False);args=['0','0',typ,'12']+([] if extra is None else [str(extra)])
            d['actions']=[cmd('addmine',*args)]
            def check(o,number=number,extra=extra):
                row=o['state']['map']['mines'][0]
                checks((row['type'],number),(row['strength'],12),(row['extra'],extra or 0),(row['creator'],1))
                assert all(0<=x<12 and 0<=y<12 for x,y in o['state']['map']['mine_hexes'])
            yield Case(d,check,label=f'mines-create-{typ}-{extra}',mode='normal')
    for text,accepted,x,strength in [('0 0 standard 4',True,0,4),('00 0 Standard 4',False,0,0),('+0 0 Standard 4',False,0,0),('1junk 0 Standard 4junk',True,1,4),('1 0 Missing 4',False,0,0),('12 0 Standard 4',False,0,0),('-1 0 Standard 4',False,0,0),('0 0 Standard',False,0,0),('0 0 Standard 4 0 extra',False,0,0)]:
        d=fixture(False);d['actions']=[cmd('addmine',*text.split())]
        def check(o,accepted=accepted,x=x,strength=strength):
            eq(o['results'][0]['accepted'],accepted);eq(len(o['state']['map']['mines']),int(accepted))
            if accepted:checks((o['state']['map']['mines'][0]['x'],x),(o['state']['map']['mines'][0]['strength'],strength))
        yield Case(d,check,label='mines-parser-'+text,mode='normal')
    d=fixture(False);d['actions']=[cmd('addmine','3','3','Standard','4'),cmd('addmine','3','3','Command','8',unit='v')]
    yield Case(d,lambda o:eq([(r['type'],r['creator']) for r in o['state']['map']['mines']],[(1,1),(3,2)]),label='mines-duplicate-different-creator',mode='normal')
    # Integer diamond for vibra; source Euclidean hex distance rounds for
    # trigger coverage. The radius1 corner covers the three neighboring hexes.
    for typ,extra,expected in [('Standard',0,[[0,0]]),('Inferno',0,[[0,0]]),('Command',0,[[0,0]]),('Vibra',80,[[0,0],[0,1],[0,2],[1,0],[1,1],[1,2],[2,0],[2,1]]),('Trigger',1,[[0,0],[0,1],[1,0],[1,1]])]:
        d=fixture(False);d['actions']=[cmd('addmine','0','0',typ,'12',str(extra))]
        yield Case(d,lambda o,expected=expected:eq(o['state']['map']['mine_hexes'],expected),label='mines-coverage-'+typ,mode='normal')
    for typ in ('Standard','Inferno','Vibra','Command'):
        for old in (4,5,7,8,12):
            d=fixture(False);d['units'][1]['at']=[3,2,0];d['map']['mines']=[dict(x=3,y=3,type=typ,strength=old,extra=0)]
            strength=int(old*2/3) if old>=8 and typ in ('Standard','Inferno') else old
            d['actions']=[cmd('detonatemines','0') if typ=='Command' else diag('mine-contact',reason='fall')]
            target_damage=int(strength/3) if typ=='Inferno' else strength
            neighbor=int(strength/2) if typ in ('Vibra','Command') else 0
            persistent=typ in ('Standard','Inferno') and old>=5
            def check(o,target_damage=target_damage,neighbor=neighbor,persistent=persistent,strength=strength,typ=typ):
                checks((loss(o,'u'),target_damage),(loss(o),neighbor),(len(o['state']['map']['mines']),int(persistent)))
                if persistent:eq(o['state']['map']['mines'][0]['strength'],strength)
                if typ=='Inferno':checks((state(o)['crit_status']&4194304,4194304),([e['deadline'] for e in events(o,kind='CUSTOM')],[strength*6]))
            yield Case(d,check,label=f'mines-contact-{typ}-{old}',mode='normal' if typ=='Command' else 'diagnostic')
    d=fixture(False);d['units'][1]['at']=[8,8,0];d['map']['mines']=[dict(x=3,y=3,type='Standard',strength=4) for _ in range(3)]
    d['actions']=[diag('mine-contact',reason='land')]
    yield Case(d,lambda o:checks((loss(o,'u'),12),(len(o['state']['map']['mines']),0),(o['results'][0]['count'],3)),label='mines-safe-adjacent-removal')
    for has_object in (False,True):
        for distance,draw,perception,found in [(3,2,12,False),(3,3,12,True),(3,3,2,False),(3.99,3,12,True)]:
            d=fixture(False);d['map']['mines']=[dict(x=3 if has_object else 4,y=3,type='Trigger',strength=50,extra=2)]
            d['random']['streams'].update(mine_discovery=[draw],perception_rolls=[perception])
            d['actions']=[diag('mine-discovery',range=distance,x=3,y=3)]
            def check(o,has_object=has_object,found=found,draw=draw,distance=distance,perception=perception):
                checks((o['results'][0]['found'],has_object and found),(draws(o,'mine_discovery'),[draw] if has_object else []),(draws(o,'perception_rolls'),[perception] if has_object and draw>=int(distance) else []))
            yield Case(d,check,label=f'mines-discovery-{has_object}-{distance}-{draw}-{perception}')
    d=fixture();d['map']['mines']=[dict(x=3,y=2,type='Standard',strength=4)];d['random']['streams'].update(mine_discovery=[9],perception_rolls=[12])
    d['actions']=[cmd('scan','3','2','H')]
    yield Case(d,lambda o:checks((draws(o,'mine_discovery'),[9]),(draws(o,'perception_rolls'),[12]),('Small bomblets' in str(state(o)['messages']),True)),label='mines-real-scan-H',mode='normal')

def blast_cases():
    for angle,arc in [(59,'front'),(60,'right'),(61,'right'),(119,'right'),(120,'right'),(121,'back'),(239,'back'),(240,'left'),(241,'left'),(299,'left'),(300,'left'),(301,'front')]:
        d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1].update(at=[3,3,0],facing=(360-angle)%360)
        d['actions']=[diag('blast',x=3,y=3,damage=7,cluster=5,source_real=[1024.0750399750987,935.25])]
        loc={'front':4,'right':3,'back':4,'left':2}[arc]
        def check(o,loc=loc,arc=arc):
            eq(loss(o),7);eq(state(o,'v')['sections'][loc]['rear' if arc=='back' else 'armor'],193)
            eq(len(draws(o,'damage_entry')),2)
        yield Case(d,check,label=f'blast-arc-{angle}')
    for distance,expected in [(0,11),(.999,11),(1,5),(1.999,5),(2,3),(3,2)]:
        d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1]['at']=[3,3,0]
        d['actions']=[diag('blast',x=3,y=3,damage=11,source_real=[1024.0750399750987,967.5-distance*322.5])]
        yield Case(d,lambda o,expected=expected:eq(loss(o),expected),label=f'blast-source-distance-{distance}')
    for damage in (-2,-1,0,1,2):
        d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1]['at']=[3,3,0]
        d['map']['hexes']=[dict(at=[3,2],terrain='LIGHT_FOREST',elevation=0)]
        d['actions']=[diag('blast',x=3,y=3,damage=damage,neighbors=1,neighbor_target_message=None,neighbor_observer_message=None)]
        yield Case(d,lambda o,damage=damage:checks((loss(o),max(0,damage)),(bool(o['state']['map']['decorations']),abs(damage)>=2)),label=f'blast-signed-neighbor-{damage}')
    for x,y in [(-1,-1),(-1,3),(12,3),(3,12)]:
        d=fixture(False);d['actions']=[diag('blast',damage=100,x=x,y=y)]
        yield Case(d,lambda o:checks((loss(o),0),(loss(o,'u'),0),(draws(o,'damage_entry'),[])),label=f'blast-outside-{x}-{y}')
    for underwater in (False,True):
        for z in (-3,-2,-1,0,1,2):
            d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1]['at']=[3,3,z]
            d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-2)]
            d['actions']=[diag('blast',damage=5,x=3,y=3,underwater=underwater,safeup=2,safedown=1)]
            ground=-2 if underwater else 0;expected=5 if ground-1<z<ground+2 else 0
            yield Case(d,lambda o,expected=expected:eq(loss(o),expected),label=f'blast-water-window-{underwater}-{z}')
    for radius in (0,1,2):
        for corner in (False,True):
            d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1]['at']=[0 if corner else 3,1 if corner else 2,0]
            d['actions']=[diag('blast',damage=12,x=0 if corner else 3,y=0 if corner else 3,neighbors=radius)]
            yield Case(d,lambda o,radius=radius:eq(loss(o),6 if radius else 0),label=f'blast-radius-corner-{radius}-{corner}')
    for cls,heat,roll,exploded in [('MECH',0,2,False),('MECH',2,2,False),('GROUND',0,8,False),('GROUND',0,9,True),('GROUND',2,8,False),('GROUND',2,9,True),('VTOL',2,9,True)]:
        d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1].update(**{'class':cls},at=[3,3,0])
        d['random']['streams']['fire_rolls']=[roll];d['actions']=[diag('blast',damage=0,heat=heat,x=3,y=3)]
        def check(o,cls=cls,heat=heat,roll=roll,exploded=exploded):
            checks((state(o,'v')['destroyed'],exploded),(draws(o,'fire_rolls'),[] if cls=='MECH' else [roll]))
            if cls=='MECH':eq(state(o,'v')['crit_status']&4194304,4194304 if heat else 0)
        yield Case(d,check,label=f'blast-heat-class-{cls}-{heat}-{roll}')

def firing_cases():
    for sight in (False,True):
        for condition in ('ready','hidden','weapon-recycle','limb-recycle','temporary','stunned','destroyed-part','club','ba-busy','sprint','selfspot','weapons-hold','mounted','dug','ams','crew-stun','unjam-turret','unjam-ammo','remove-pods','nonidf-spotter'):
            d=fixture(False);mount(d,'IS.AC/5',ammo=20,range_min=0,crits=1);u=d['units'][0]
            d['random']['streams']['attack_rolls']=[12]
            if condition=='hidden':u['hidden']=True
            if condition=='weapon-recycle':slot(d,4,data=9)
            if condition=='limb-recycle':section(d,4,recycle=9)
            if condition=='temporary':slot(d,4,temp_failure=1,data=9)
            if condition=='stunned':u['crit_status']=1073741824
            if condition=='destroyed-part':slot(d,4,firemode=1)
            if condition=='club':section(d,4,specials=32)
            if condition=='ba-busy':u['class']='BA';section(d,1,recycle=9)
            if condition=='sprint':u['status2']=65536
            if condition=='selfspot':u['spotter']='u'
            if condition=='weapons-hold':u['status2']=8388608
            if condition=='mounted':u['status2']=1048576
            if condition=='dug':u['tank_crit_status']=4;u['weapons'][0]['section']=2
            if condition=='ams':u['weapons'][0]['name']='IS.Anti-MissileSystem';u['ammo'][0]['weapon']='IS.Anti-MissileSystem'
            if condition=='crew-stun':u['class']='GROUND';d['actions']=[diag('effect',name='crew_stunned')]
            if condition in ('unjam-turret','unjam-ammo','remove-pods'):d['pending_events']=[dict(unit='u',callback=condition,data=0,delay=60)]
            if condition=='nonidf-spotter':d['actions']=[configure(spotter='v')]
            d['actions'] += [cmd('sight' if sight else 'fire','0')]
            allowed=condition in ('ready','hidden') or sight and condition in ('weapon-recycle','limb-recycle','temporary','stunned','club','weapons-hold')
            def check(o,allowed=allowed,sight=sight,condition=condition):
                eq(o['results'][-1]['accepted'],allowed)
                checks((rounds(o),19 if allowed and not sight else 20),(state(o)['weap_heat'],1.0 if allowed and not sight else 0.0),(draws(o,'attack_rolls'),[12] if allowed else []))
                if condition=='hidden':eq(bool(state(o)['crit_status']&8),sight)
                if not allowed:eq(state(o)['shots_fired'],0)
            yield Case(d,check,label=f'firing-gate-{condition}-sight{sight}',mode='normal')
    for loc in (0,1,4,5,6):
        for bad in ('none','left','right','both'):
            d=fixture(False);mount(d,loc=loc,index=4,crits=1);d['units'][0]['fallen']=True
            if bad in ('left','both'):section(d,0,recycle=10)
            if bad in ('right','both'):section(d,1,recycle=10)
            d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0')]
            allowed=loc not in (5,6) and (bad=='none' or loc==4 and bad!='both')
            yield Case(d,lambda o,allowed=allowed:checks((o['results'][0]['accepted'],allowed),(draws(o,'attack_rolls'),[12] if allowed else [])),label=f'firing-prone-prop-{loc}-{bad}',mode='normal')
    for dead in (0,1,2,3):
        for loc in (4,5):
            d=fixture(False);mount(d,loc=loc,index=4,crits=1);d['units'][0].update(fallen=True,movement='QUAD')
            for index in (0,1,6)[:dead]:section(d,index,armor=0,rear=0,internal=0)
            d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0')]
            allowed=dead<3 and (dead==0 or loc==4 and dead<2)
            yield Case(d,lambda o,allowed=allowed:eq(o['results'][0]['accepted'],allowed),label=f'firing-prone-quad-{dead}-{loc}',mode='normal')
    for first,second,text in [('stunned','recycle','stunned'),('temporary','recycle','unusable'),('sprint','selfspot','movement mode'),('selfspot','invalid','spotting')]:
        d=fixture(False);mount(d,crits=1);u=d['units'][0];slot(d,4,data=10)
        if first=='stunned':u['crit_status']=1073741824
        if first=='temporary':slot(d,4,temp_failure=1)
        if first=='sprint':u['status2']=65536
        if first in ('selfspot','sprint'):u['spotter']='u'
        d['actions']=[cmd('fire','99' if second=='invalid' else '0')]
        yield Case(d,lambda o,text=text:checks((text in o['results'][0]['text'],True),(draws(o,'attack_rolls'),[])),label=f'firing-precedence-{first}-{second}',mode='normal')
    for sight in (False,True):
        d=fixture(False);mount(d,crits=1);d['actions']=[cmd('lock','3','2','H'),cmd('sight' if sight else 'fire','0','4','1')];d['random']['streams']['attack_rolls']=[12]
        yield Case(d,lambda o,sight=sight:checks((o['results'][-1]['attack']['target_id'],None if sight else 2),(loss(o),0 if sight else 5)),label=f'firing-explicit-coordinates-stored-occupant-sight{sight}',mode='normal')

def ammunition_cases():
    for condition in ('normal','energy','weapon-busy','dead-source','original-zero','bad-source','reset','duplicate','missing','extra','bad-number'):
        d=fixture(False);mount(d,'IS.MediumLaser' if condition=='energy' else 'IS.AC/5',ammo=None if condition=='energy' else 20,crits=1)
        if condition=='weapon-busy':slot(d,4,data=3)
        if condition=='dead-source':section(d,3,internal=0)
        if condition=='original-zero':section(d,3,internal_orig=0)
        args=['00' if condition=='bad-number' else '0','bad' if condition=='bad-source' else 'RT']
        if condition=='missing':args=['0']
        if condition=='extra':args.append('extra')
        if condition in ('reset','duplicate'):d['actions']=[cmd('usebin','0','RT')]
        if condition=='reset':args=['0','-']
        d['actions'].append(cmd('usebin',*args))
        allowed=condition in ('normal','reset')
        yield Case(d,lambda o,allowed=allowed,condition=condition:checks((o['results'][-1]['accepted'],allowed),(rawslot(o)['desired_ammo_loc'],3 if condition in ('normal','duplicate') else -1)),label='ammunition-usebin-'+condition,mode='normal')
    for bad in ('empty','disabled','wrong-mode'):
        d=fixture();mount(d,'IS.AC/5',ammo=3,crits=1);slot(d,3,10,ammo='IS.AC/5',data=0 if bad=='empty' else 2,firemode=2 if bad=='disabled' else 0,ammomode=8192 if bad=='wrong-mode' else 0)
        d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('usebin','0','RT'),cmd('fire','0')]
        yield Case(d,lambda o,bad=bad:checks((rawslot(o,2,10)['data'],2),(rawslot(o,3,10)['data'],0 if bad=='empty' else 2)),label='ammunition-preferred-fallback-'+bad,mode='normal')
    d=fixture();mount(d,'IS.AC/5',ammo=1,crits=1);slot(d,3,10,ammo='IS.AC/5',data=1)
    d['random']['streams']['attack_rolls']=[12,12];d['actions']=[cmd('fire','0'),advance(40),cmd('fire','0'),advance(40),cmd('fire','0')]
    yield Case(d,lambda o:checks((rounds(o),0),(o['results'][-1]['accepted'],False),(draws(o,'attack_rolls'),[12,12]),(loss(o),10)),label='ammunition-multiple-bin-exact-depletion',mode='normal')
    d=fixture();mount(d,'IS.UltraAC/5',ammo=1,fire=1024|16|32,crits=1)
    d['units'][1]['at']=[3,4,0];d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0')]
    yield Case(d,lambda o:checks((rawslot(o)['firemode'],0),(rounds(o),0),(loss(o),5)),label='ammunition-ultra-shortage-clears-whole-word',mode='normal')
    for flag in (65536,65536|16):
        d=fixture();mount(d,'IS.RL-10',special=flag,crits=2);d['random']['streams'].update(attack_rolls=[12],missile_pre_roll=[3,3,3],missile_cluster=[12]);d['actions']=[cmd('fire','0')]
        yield Case(d,lambda o,flag=flag:checks((o['results'][0]['accepted'],flag==65536),(bool(rawslot(o)['firemode']&1048576),flag==65536)),label=f'ammunition-rocket-special-equality-{flag}',mode='normal')
    # expenditure_check C uses an integer slots accumulator; each caseless
    # half is truncated separately, rather than summing fractions first.
    for mode,fire,slots in [(0,0,2),(0,128,1),(8192,0,1),(65536,0,1),(262144,0,0)]:
        for capacity in (4,40,240):
            threshold=max(3,min(30,int(slots*capacity/8)))
            for count,severity in [(threshold,'red'),(threshold*2,'yellow'),(threshold+1,None)]:
                d=fixture(False);mount(d,'IS.AC/5',ammo=count,crits=1,ammo_per_ton=capacity);slot(d,2,10,ammomode=mode,firemode=fire)
                d['units'][0]['crit_status']=8192;d['actions']=[diag('ammunition-check',weapon=0,offset=0)]
                yield Case(d,lambda o,severity=severity:checks((o['results'][0]['severity'],severity),(state(o)['crit_status']&8192,0)),label=f'ammunition-warning-mod-{mode}-{fire}-{capacity}-{count}')
    for condition in ('stopped','warnings-off'):
        d=fixture(False);mount(d,'IS.AC/5',ammo=5,ammo_per_ton=20,crits=1);d['units'][0]['crit_status']=8192
        if condition=='stopped':d['units'][0]['started']=False
        else:d['units'][0]['prefs']=16
        d['actions']=[diag('ammunition-check',weapon=0,offset=0)]
        yield Case(d,lambda o:checks((o['results'][0]['severity'],None),(state(o)['crit_status']&8192,0)),label='ammunition-warning-suppressed-'+condition)
    d=fixture();mount(d,'IS.AC/5',ammo=10,crits=1);slot(d,3,10,ammo='IS.AC/5',data=10,ammomode=8192)
    d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('armorpiercing','0'),cmd('fire','0')]
    yield Case(d,lambda o:checks((rawslot(o,2,10)['data'],10),(rawslot(o,3,10)['data'],9),(o['results'][1]['attack']['bth_breakdown']['ammo_mode_mod'],1)),label='ammunition-mode-selects-real-bin',mode='normal')

def more_mode_cases():
    for command in ('hotload','ultra'):
        for args in [[],['0','extra','extra'],['00'],['+0'],['1junk'],['1-0'],['96'],['0,0']]:
            d=fixture();name={'hotload':'IS.LRM-5','ultra':'IS.UltraAC/5','rac':'IS.RotaryAC/5','inarc':'IS.iNarcBeacon'}[command]
            mount(d,name,crits=1);mount(d,name,index=1,crits=1)
            if command in ('rac','inarc') and args:args=args+['2' if command=='rac' else 'Y']
            d['actions']=[cmd(command,*args)]
            # Fixed wrappers parse the whole provided selector; RAC/iNARC
            # require two tokens. Explicit complete arity matrices live in APS.
            if command in ('rac','inarc'):continue
            expected=[1] if args==['1junk'] else [0,1] if args==['1-0'] else [0] if args==['0','extra','extra'] else []
            bit=64 if command=='hotload' else 1024
            yield Case(d,lambda o,bit=bit,expected=expected:eq([i for i in (0,1) if rawslot(o,index=i)['firemode']&bit],expected),label='modes-extra-selector-'+command+'-'+str(args),mode='normal')
    for where,index,destroyed,accepted in [(4,1,False,True),(7,0,False,True),(7,5,False,True),(7,6,False,False),(4,1,True,False)]:
        d=fixture();mount(d,'IS.LRM-5',crits=1);slot(d,where,index,special='ARTEMIS_IV',data=1,firemode=1 if destroyed else 0);d['actions']=[cmd('artemis','0')]
        yield Case(d,lambda o,accepted=accepted:eq(o['results'][0]['accepted'],accepted),label=f'modes-artemis-association-{where}-{index}-{destroyed}',mode='normal')
    for condition in ('stopped','unconscious','blind','caller'):
        d=fixture();mount(d,'IS.RotaryAC/5',crits=1);u=d['units'][0]
        if condition=='stopped':u['started']=False
        if condition=='unconscious':u['conscious']=False
        if condition=='blind':u['blinded']=True
        if condition=='caller':u.update(caller_is_pilot=False,in_character=True)
        d['actions']=[cmd('rac','0','2')]
        yield Case(d,lambda o:checks((o['results'][0]['accepted'],True),(rawslot(o)['firemode'],8192)),label='modes-RAC-no-common-'+condition,mode='normal')

def pod_cases():
    for mask in (0,1,2,4,8,16,31):
        d=fixture(False);section(d,4,specials=mask);section(d,0,internal=0,armor=0);section(d,1,internal_orig=0);d['actions']=[cmd('shownarcpods')]
        def check(o,mask=mask):
            r=o['results'][0];eq(r['accepted'],True)
            if not mask:assert 'no NARC' in r['text'];return
            rows={r['location']:r for r in r['pods']};eq(len(rows),7);eq(rows[0]['destroyed'],True);assert 1 not in rows
            for key,bit in [('narc',1),('homing',2),('haywire',4),('ecm',8),('nemesis',16)]:eq(rows[4][key],bool(mask&bit))
        yield Case(d,check,label=f'pods-display-{mask}',mode='normal')
    for token,bit in [('H',2),('Y',4),('E',8),('Z',2),('junk',2)]:
        d=fixture(False);section(d,4,specials=31);d['random']['streams']['pod_rolls']=[12];d['actions']=[cmd('removepods','CT',token)]
        yield Case(d,lambda o,bit=bit:checks((state(o)['sections'][4]['specials'],31&~bit),(o['results'][0]['arm'],0),(state(o)['sections'][0]['recycle'],30)),label='pods-type-choice-'+token,mode='normal')
    for upper,lower,hand in [(0,0,0),(1,0,0),(0,1,0),(0,0,1),(1,1,1)]:
        for roll in (2,12):
            d=fixture(False);section(d,1,specials=2);d['units'][0].update(tonnage=55,piloting=3)
            for index,bad in [(1,upper),(2,lower),(3,hand)]:
                if bad:slot(d,0,index,firemode=1)
            d['random']['streams']['pod_rolls']=[roll];d['actions']=[cmd('removepods','RA','H')]
            bth=7+2*upper+2*lower+hand;damage=0 if roll>=bth else int(int(6/(2 if lower else 1))/(2 if upper else 1))
            yield Case(d,lambda o,bth=bth,damage=damage,roll=roll:checks((o['results'][0]['bth'],bth),(o['results'][0]['self_damage'],damage),(state(o)['sections'][1]['specials'],0 if roll>=bth else 2),(loss(o,'u'),damage),(state(o)['sections'][0]['recycle'],30)),label=f'pods-actuator-{upper}-{lower}-{hand}-{roll}',mode='normal')
    for condition in ('quad','no-arms','both-busy','opposite-dead','opposite-weapon-busy','invalid','dead-location','no-pod'):
        d=fixture(False);section(d,1,specials=2);u=d['units'][0]
        if condition=='quad':u['movement']='QUAD'
        if condition=='no-arms':section(d,0,internal=0);section(d,1,internal=0)
        if condition=='both-busy':section(d,0,recycle=10);section(d,1,recycle=10)
        if condition=='opposite-dead':section(d,0,internal=0)
        if condition=='opposite-weapon-busy':mount(d,loc=0,index=4,crits=1);slot(d,0,4,data=10)
        if condition=='dead-location':section(d,1,internal=0)
        if condition=='no-pod':section(d,1,specials=1)
        d['actions']=[cmd('removepods','bad' if condition=='invalid' else 'RA','H')]
        yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),(draws(o,'pod_rolls'),[])),label='pods-guard-'+condition,mode='normal')
    for condition in ('moving','desired-moving','airborne','crew','turret','ammo','empty'):
        d=fixture(False);u=d['units'][0];u['class']='GROUND';section(d,2,specials=31)
        if condition=='moving':u['speed']=1
        if condition=='desired-moving':u['desired_speed']=1
        if condition=='airborne':u['class']='VTOL';u['at'][2]=1
        if condition=='crew':d['actions']=[diag('effect',name='crew_stunned')]
        if condition in ('turret','ammo'):d['pending_events']=[dict(unit='u',callback='unjam-'+condition,data=0,delay=60)]
        if condition=='empty':section(d,2,specials=1)
        d['actions'].append(cmd('removepods'))
        yield Case(d,lambda o:checks((o['results'][-1]['accepted'],False),(events(o,kind='REMOVE_PODS'),[])),label='pods-tank-guard-'+condition,mode='normal')
    for condition in ('normal','shutdown','moving','destroyed','duplicate'):
        d=fixture(False);u=d['units'][0];u['class']='GROUND';section(d,2,specials=31);section(d,0,internal_orig=0,specials=31)
        d['actions']=[cmd('removepods')]
        if condition=='shutdown':d['actions'].append(cmd('shutdown'))
        if condition=='moving':d['actions'].append(configure(speed=30,desired_speed=30))
        if condition=='destroyed':d['actions'].append(configure(destroyed=True))
        if condition=='duplicate':d['actions'].append(cmd('removepods'))
        d['actions'] += [advance(59),inspect(),advance(1)]
        yield Case(d,lambda o,condition=condition:checks((state(o,index=-2)['sections'][2]['specials'],31),(state(o)['sections'][2]['specials'],31 if condition=='destroyed' else 1),(state(o)['sections'][0]['specials'],31),(sum('You remove all' in m for m in state(o)['messages']),0 if condition=='destroyed' else 2 if condition=='duplicate' else 1)),label='pods-tank-callback-'+condition,mode='normal')
    d=fixture();mount(d);section(d,4,specials=4);d['random']['streams']['pod_rolls']=[12]
    d['actions']=[diag('combat-bth',weapon=0,target='v'),cmd('removepods','CT','Y'),diag('combat-bth',weapon=0,target='v')]
    yield Case(d,lambda o:checks((o['results'][0]['pod_mod'],1),(o['results'][2]['pod_mod'],0)),label='pods-haywire-real-consumer',mode='normal')

def artillery_cases():
    for weapon,word in [('IS.Sniper','round'),('IS.ArrowIVSystem','round'),('CL.ArrowIVSystem','round')]:
        d=fixture(False);mount(d,weapon,ammo=20,crits=1);d['actions']=[cmd('lock','3','1','H'),cmd('fire','0')];d['random']['streams']['attack_rolls']=[12]
        yield Case(d,lambda o,word=word:checks((len(o['state']['map']['projectiles']),1),(any('shoots a '+word in m for m in state(o,'v')['messages']),True)),label='artillery-launch-noun-'+weapon,mode='normal')
    for wind,direction,dist,xy in [(0,0,2,(6,4)),(0,90,2,(4,6)),(0,180,2,(2,4)),(0,270,2,(3,2)),(0,359,2,(5,3)),(60,0,2,(11,4)),(60,90,2,(4,11)),(60,180,2,(0,4))]:
        d=fixture(False);mount(d,'IS.Sniper',damage=1,crits=1);d['map'].update(windspeed=wind,winddir=180)
        d['random']['streams'].update(artillery_scatter_direction=[direction],artillery_scatter_distance=[dist]);d['actions']=[diag('artillery-launch',weapon=0,x=4,y=4,hit=False),advance(10)]
        yield Case(d,lambda o,xy=xy:checks(((o['state']['map']['artillery_impacts'][0]['x'],o['state']['map']['artillery_impacts'][0]['y']),xy),(len(o['state']['map']['projectiles']),0)),label=f'artillery-scatter-{wind}-{direction}')
    for remove in ('map','shooter'):
        d=fixture(False);mount(d,'IS.Sniper',crits=1);d['actions']=[diag('artillery-launch',weapon=0,x=3,y=2),diag('map-unregister') if remove=='map' else dict(op='remove',unit='u'),advance(10),advance(10)]
        yield Case(d,lambda o,remove=remove:checks((len(o['state']['map']['projectiles']),0),(len(o['state']['map']['artillery_impacts']),int(remove=='shooter')),(loss(o),10 if remove=='shooter' else 0)),label='artillery-invalidated-'+remove)
    d=fixture(False);mount(d,'IS.Sniper',damage=2,mode=8|16,crits=1)
    # First bomblet retries after x=-2/y=-2. Accepted (1,0), then (0,1)
    # accumulate and apply in X-major order, each at strength2.
    seq=[-2,0,-2,0, 0,1,0,0, 0,0,0,1]
    d['random']['streams']['artillery_cluster']=seq;d['actions']=[diag('artillery-launch',weapon=0,x=0,y=0),advance(10)]
    yield Case(d,lambda o:checks((draws(o,'artillery_cluster'),seq),([(m['x'],m['y'],m['strength']) for m in o['state']['map']['mines']],[(0,1,2),(1,0,2)])),label='artillery-cluster-edge-retry-x-major')
    for mode in (0,32,16):
        d=fixture(False);mount(d,'IS.Sniper',damage=10,mode=mode,crits=1);d['units'][0]['at']=[9,9,0]
        positions=[(3,3),(2,2),(2,3),(3,2),(3,4),(4,2),(4,3)]
        d['units']=[d['units'][0]]+[dict(name=f't{i}',at=[x,y,0],team=2,sections=[sec(k) for k in range(8)]) for i,(x,y) in enumerate(positions)]
        d['random']['streams']['smoke_duration']=[120]*7;d['actions']=[diag('artillery-launch',weapon=0,x=3,y=3),advance(10)]
        def check(o,mode=mode):
            eq([loss(o,f't{i}') for i in range(7)],[10]+[5]*6 if mode==0 else [0]*7)
            eq(len(o['state']['map']['decorations']),7 if mode==32 else 0);eq(len(o['state']['map']['mines']),int(mode==16))
        yield Case(d,check,label=f'artillery-seven-hex-packets-{mode}')
    for condition in ('friendly','enemy','stopped-shooter','stopped-observer','retargeted','hit','spotter','nonseeing-spotter'):
        d=fixture(False);mount(d,'IS.Sniper',damage=1,crits=1);d['units'][1].update(at=[4,4,0],team=0 if condition!='enemy' else 2)
        d['actions']=[cmd('lock','4','4','H')]
        if condition.endswith('spotter'):
            d['units'].append(dict(name='s',at=[4,3,0],sensors=['V','V'],scan_range=40))
            d['actions'] += [cmd('spot','02',unit='s'),cmd('lock','4','4','H',unit='s'),cmd('spot','02')]
            if condition=='nonseeing-spotter':d['actions'] += [dict(op='place',unit='s',at=[4,1,0]),dict(op='hex',value=dict(at=[4,2],terrain='BUILDING',elevation=9))]
        d['random']['streams'].update(artillery_scatter_direction=[0],artillery_scatter_distance=[2])
        d['actions'].append(diag('artillery-launch',weapon=0,x=4,y=4,hit=condition=='hit'))
        if condition=='stopped-shooter':d['actions'].append(cmd('shutdown'))
        if condition=='stopped-observer':d['actions'].append(cmd('shutdown',unit='v'))
        if condition=='retargeted':d['actions'].append(cmd('lock','5','5','H'))
        d['actions'].append(advance(10))
        yield Case(d,lambda o,condition=condition:eq(state(o)['fire_adjustment'],int(condition in ('friendly','spotter'))),label='artillery-original-target-adjustment-'+condition)

def equipment_cases():
    for name,tech,bit,event in [('nullsig',16,128,'NSS'),('stealtharmor',1,64,'STEALTH_ARMOR')]:
        for initial in (False,True):
            for condition in ('normal','duplicate','stopped','destroyed-system','no-tech'):
                d=fixture();u=d['units'][0];u.update(specials2=tech if condition!='no-tech' else 0,status2=bit if initial else 0)
                if name=='stealtharmor':u['equipment']=['Guardian']
                d['actions']=[cmd(name)]
                if condition=='duplicate':d['actions'].append(cmd(name))
                if condition=='stopped':d['actions'].append(cmd('shutdown'))
                if condition=='destroyed-system':d['actions'].append(configure(crit_status=512 if name=='nullsig' else 1048576))
                d['actions'] += [advance(29),inspect(),advance(1)]
                def check(o,initial=initial,condition=condition,bit=bit,event=event):
                    # btmacros.h Shutdown clears both signature bits immediately.
                    if condition=='stopped':initial=False
                    checks((o['results'][0]['accepted'],condition!='no-tech'),(bool(state(o,index=-2)['status2']&bit),initial),(bool(state(o)['status2']&bit),not initial if condition in ('normal','duplicate') else initial),(events(o,kind=event),[]))
                    if condition=='duplicate':eq(o['results'][1]['accepted'],False)
                yield Case(d,check,label=f'equipment-signature-{name}-{initial}-{condition}',mode='normal')
    for terrain in ('CLEAR','LIGHT_FOREST','ROAD','BRIDGE','BUILDING','WALL','WATER'):
        d=fixture(False);d['units'][0]['class']='GROUND';d['map']['hexes']=[dict(at=[3,3],terrain=terrain,elevation=0)]
        d['actions']=[cmd('dig'),advance(20)]
        yield Case(d,lambda o,terrain=terrain:checks((o['results'][0]['accepted'],terrain in ('CLEAR','LIGHT_FOREST')),(bool(state(o)['tank_crit_status']&4),terrain in ('CLEAR','LIGHT_FOREST'))),label='equipment-dig-terrain-'+terrain,mode='normal')
    for condition in ('moving','reverse','turning','none','fortified','OOD','already-dug','already-digging'):
        d=fixture(False);u=d['units'][0];u['class']='GROUND'
        if condition in ('moving','reverse'):u['speed']=1 if condition=='moving' else -1
        if condition=='turning':u['desired_facing']=1
        if condition=='none':u['movement']='NONE'
        if condition=='fortified':u['status2']=4194304
        if condition=='OOD':u['cocoon']=1
        if condition=='already-dug':u['tank_crit_status']=4
        if condition=='already-digging':u['tank_crit_status']=8
        d['actions']=[cmd('dig')]
        yield Case(d,lambda o:eq(o['results'][0]['accepted'],False),label='equipment-dig-guard-'+condition,mode='normal')
    for action in ('move','shutdown','turret-shot','hull-shot'):
        d=fixture();u=d['units'][0];u['class']='GROUND';mount(d,loc=4 if action=='turret-shot' else 2,crits=1)
        d['actions']=[cmd('dig')]
        if action=='move':d['actions'] += [cmd('speed','32.25'),advance(20)]
        elif action=='shutdown':d['actions'] += [cmd('shutdown'),advance(20)]
        else:d['random']['streams']['attack_rolls']=[12];d['actions'] += [advance(20),cmd('fire','0')]
        def check(o,action=action):
            eq(state(o)['dug_in'],action.endswith('shot'))
            if action.endswith('shot'):eq(o['results'][-1]['accepted'],action=='turret-shot')
        yield Case(d,check,label='equipment-dig-consumer-'+action,mode='normal')
    for condition in ('normal','duplicate','destroyed','unconscious','no-turret','stopped','locked'):
        d=fixture(False);u=d['units'][0];u.update(**{'class':'GROUND'},tank_crit_status=2);d['actions']=[cmd('fixturret')]
        if condition=='duplicate':d['actions'].append(cmd('fixturret'))
        if condition in ('destroyed','unconscious','stopped'):d['actions'].append(configure(**{'destroyed':True} if condition=='destroyed' else {'conscious':False} if condition=='unconscious' else {'started':False}))
        if condition=='locked':d['actions'].append(configure(tank_crit_status=3))
        if condition=='no-turret':d['actions'].append(dict(op='section',unit='u',value=dict(index=4,internal=0)))
        d['actions'] += [advance(59),inspect(),advance(1)]
        yield Case(d,lambda o,condition=condition:checks((state(o,index=-2)['tank_crit_status']&2,2),(state(o)['tank_crit_status']&2,0 if condition in ('normal','duplicate') else 2),(sum('manage to unjam' in m for m in state(o)['messages']),2 if condition=='duplicate' else int(condition=='normal'))),label='equipment-turret-callback-'+condition,mode='normal')
    for condition in ('jumping','desired-run','any-section-busy','duplicate','no-ammo','destroyed-weapon','stopped','unconscious','non-RAC'):
        d=fixture(False);name='IS.AC/5' if condition=='non-RAC' else 'IS.RotaryAC/5';mount(d,name,ammo=20,crits=1);slot(d,4,temp_failure=6)
        d['random']['streams'].update(unjam_rolls=[12],pilot_rolls=[12]*100)
        if condition=='jumping':d['units'][0]['status']=8|64
        if condition=='desired-run':d['units'][0]['desired_speed']=64.5
        if condition=='any-section-busy':mount(d,loc=7,index=4,crits=1);slot(d,7,4,data=5)
        d['actions']=[cmd('unjamammo','0')]
        if condition=='duplicate':d['actions'].append(cmd('unjamammo','0'))
        if condition=='no-ammo':d['actions'].append(dict(op='section',unit='u',value=dict(index=2,slots=[dict(index=10,data=0)])))
        if condition=='destroyed-weapon':d['actions'].append(dict(op='section',unit='u',value=dict(index=4,slots=[dict(index=0,firemode=1)])))
        if condition in ('stopped','unconscious'):d['actions'].append(configure(**{'started':False} if condition=='stopped' else {'conscious':False}))
        d['actions'].append(advance(60));cleared=condition in ('duplicate','no-ammo','non-RAC')
        yield Case(d,lambda o,condition=condition,cleared=cleared:checks((o['results'][0]['accepted'],condition not in ('jumping','desired-run','any-section-busy')),(rawslot(o)['temp_failure'],0 if cleared else 6)),label='equipment-unjam-branch-'+condition,mode='normal')
    for stop_enabled,busy in [(0,False),(1,False),(1,True)]:
        d=fixture(False);d['config']['explode_stop']=stop_enabled;mount(d,'IS.AC/5',ammo=2,crits=1)
        d['pending_events']=[dict(unit='u',callback='explode',data=60,delay=1)]
        if busy:slot(d,4,data=10)
        d['actions']=[cmd('explode','stop')]
        yield Case(d,lambda o,stop_enabled=stop_enabled,busy=busy:checks((o['results'][0]['accepted'],bool(stop_enabled and not busy)),(len(events(o,kind='EXPLODE')),0 if stop_enabled and not busy else 1)),label=f'equipment-explode-stop-{stop_enabled}-{busy}',mode='normal')
    for armor in (False,True):
        d=fixture();d['units'][0]['specials']=64;mount(d,loc=0,index=4,crits=1);d['units'][1]['at']=[3,4,0];d['random']['streams']['attack_rolls']=[12]
        d['actions']=[cmd('fire','0'),cmd('fliparms'),cmd('fire','0')]
        if armor:d['units'][0]['fallen']=True
        yield Case(d,lambda o,armor=armor:checks((o['results'][0]['accepted'],False),(o['results'][1]['accepted'],not armor),(o['results'][2]['accepted'],not armor)),label=f'equipment-flipped-arm-live-arc-prone{armor}',mode='normal')

def all_cases():
    from combat_recovery import cases as recovery
    yield from recovery()
    from combat_clock_consumers import cases as clocks
    yield from clocks()
    from combat_extended import all_cases as extended
    yield from extended()
    from combat_physical_procedures import all_cases as physical
    yield from physical()
    from combat_consumers import cases as consumers
    yield from consumers()
    from combat_remaining import cases as remaining
    yield from remaining()
    from combat_sequences import cases as sequences
    yield from sequences()
    yield from equipment_cases()
    yield from artillery_cases()
    yield from pod_cases()
    yield from ammunition_cases()
    yield from more_mode_cases()
    yield from firing_cases()
    yield from blast_cases()
    yield from mine_cases()
    yield from bth_cases()
    yield from group_cases()
    yield from preference_cases()
    yield from targeting_cases()
    yield from interface_cases()
    yield from range_cases()
    yield from mode_cases()
    yield from inherited_locations()
    yield from retained_location_dispatch()
