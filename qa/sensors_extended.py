"""Consumer integration and additional source-boundary UI checks."""
from sensors_support import *


def cases():
    from sensors_supplemental import case,contains
    # Match SensorInf's defined indexes, including the stale wanted alphabet.
    for pair,request,expected in [('VI',None,'vi'),('VI',['V','I'],'vi'),('VV',['V','I'],'vvIS'),('VV',['H','H'],None)]:
        d=document([actor(sensors=list(pair),equipment=['Bloodhound'])],([cmd('sensor',*request)] if request else [])+[diag('legacy-sensor-info',None)])
        yield case('controls','legacy-precise-'+pair+str(request),d,lambda o,expected=expected:equal(o['results'][-1]['legacy'],expected) if expected else None,True,invalid=expected is None)
    for cls,movement in [('MW','BIPED'),('BSUIT','BIPED'),('VEH_NAVAL','HULL'),('VEH_GROUND','HOVER')]:
        d=document([actor(**{'class':cls,'movement':movement})],[cmd('sensor','S','S')])
        yield case('controls','seismic-class-'+cls,d,lambda o:equal(o['results'][0]['ok'],False))
    d=document(actions=[dict(op='remove',unit='u'),cmd('sensor','I','E')])
    yield case('controls','mapless-request',d,lambda o:equal(o['results'][-1]['ok'],False))
    # Metadata callback eligibility for every registration, using inputs not answers.
    for sn,blocked in [('V',32768),('L',512),('I',8192),('E',16),('S',16),('R',32768),('B',32768),('A',32768),('H',32768)]:
        for mask in (0,1<<('VLIESRBH'.index('B' if sn=='A' else sn))):
            target=actor('t',speed=11,at=[2,2,3] if sn=='R' else [2,2,0])
            d=document([actor(sensors=[sn,sn],equipment=equipment(sn)),target],[cache(8),diag('eligibility'),cache(8|blocked),diag('eligibility')]);d['config']={'periodic_updates':False};d['map'].update(sensorflags=mask,light=0)
            blocked_eligible=sn in 'SBAH'
            def check(o,mask=mask,blocked_eligible=blocked_eligible): equal(o['results'][1]['eligible'],0 if mask else 3);equal(o['results'][3]['eligible'],0 if mask or not blocked_eligible else 3)
            yield case('detection','callbacks-'+sn+'-'+str(mask),d,check,True)
    for distance in (5,5.001):
        d=document([actor(),actor('t',real=at_range(distance),hidden=True)],[adv(3)]);d['random']={'streams':{'sensor.detect':[1]*100}}
        yield case('detection','hidden-'+str(distance),d,lambda o,distance=distance:equal(bool(state(o)['contacts']['t']&1),distance<=5))
    for draw in (8414,8415):
        # VV at range 3: callback int(100-3/3)=99, forward/Per6=85%; strict <8415.
        d=document([actor(),actor('t',real=at_range(3))],[adv(2)]);d['random']={'streams':{'sensor.detect':[draw]*100}}
        yield case('detection','strict-draw-'+str(draw),d,lambda o,draw=draw:equal(bool(state(o)['contacts']['t']&1),draw<8415))
    # Actual motion crosses a smoke-obscured LOS, then reverses out of it.
    d=document(actions=[adv(2),cmd('target','TT'),cmd('heading',180,unit='t'),cmd('speed',32.25,unit='t'),adv(45),inspect(),cmd('speed',-32.25,unit='t'),adv(47),cmd('speed',0,unit='t'),adv(2),inspect()])
    d['map']['hexes']=[dict(at=[2,3],terrain='CLEAR',elevation=0,overlay='SMOKE',duration=100)]
    d['random']={'streams':{'sensor.detect':[1]*500}}
    def moved(o):
        before=state(o,index=5);after=state(o)
        equal(bool(before['contacts']['t']&1),False);equal(before['target'],-1);equal(bool(after['contacts']['t']&1),True)
        assert messages(after,'have lost')>=1 and messages(after,'You notice')>=2
        assert state(o,'t',5)['at']!=[2,2,0]
    yield case('detection','movement-loss-reacquire',d,moved)
    # Underwater ordering, smoke endpoints and two-sided traces.
    for z,expected in [(-1,False),(-2,True)]:
        d=document([actor(),actor('t',at=[2,1,z])],[diag('trace')]);d['map']['hexes']=[dict(at=[2,1],terrain='WATER',elevation=3)]
        yield case('los','same-hex-water-'+str(z),d,lambda o,expected=expected:equal(bool(o['results'][0]['flags']&32768),expected),True)
    for at in ([2,1],[2,4]):
        d=document([actor(),actor('t',at=[2,4,0])],[diag('trace')]);d['map']['hexes']=[dict(at=at,terrain='LIGHT_FOREST',elevation=0,overlay='SMOKE')]
        yield case('los','endpoint-'+str(at),d,lambda o:equal(o['results'][0]['flags'],8),True)
    # Probe-only contact is visible but cannot be identified/scanned/TAGged.
    d=document([actor(sensors=['B','B'],equipment=['Beagle','TAG'],weapons=['IS.MediumLaser']),actor('t',at=[2,4,0],markings='hidden')],[adv(2),cmd('contacts'),cmd('scan','TT'),cmd('view','TT'),cmd('tag','TT'),cmd('target','TT'),cmd('sight',0)])
    d['map']['hexes']=[dict(at=[2,2],terrain='CLEAR',elevation=9)];d['random']={'streams':{'sensor.detect':[1]*100}}
    def probe(o):
        equal(o['results'][1]['contacts'][0]['name'],'something')
        for i in (2,3,4): equal(o['results'][i]['ok'],False)
        equal(o['results'][5]['ok'],True)
        # Firing follows its own terrain/BTH gate rather than assuming NB visibility.
        assert 'attack' in o['results'][6]
    yield case('los','probe-disclosure-consumers',d,probe)
    # ECM section liveness is type sensitive and ignores config-only destruction.
    for cls,armor,internal,expected in [('AERO',0,10,False),('AERO',1,0,True),('DS',0,0,True),('SPHEROID_DS',0,0,True)]:
        d=document([actor(**{'class':cls,'movement':'FLY'},sections=[dict(index=0,armor=armor,internal=internal,specials=8)])],[diag('ecm',None)]);d['config']={'periodic_updates':False}
        yield case('ecm',f'section-{cls}-{armor}-{internal}',d,lambda o,expected=expected:equal(state(o)['disturbed'],expected),True)
    for sn in 'EBAH':
        d=document([actor(sensors=[sn,sn],equipment=equipment(sn)),actor('t'),actor('b',team=2,equipment=['Guardian'])],[cmd('ecm',unit='b'),adv(2),diag('eligibility'),cmd('shutdown',unit='b'),adv(2),diag('eligibility')])
        yield case('ecm','sensor-recovery-'+sn,d,lambda o:(equal(o['results'][2]['eligible'],0),equal(o['results'][5]['eligible'],3)))
    # Semiguided sight before and after stable TAG, then real fire after break.
    for ammo in (0,524288):
        d=document([actor(weapons=[dict(name='IS.LRM-10',ammo_mode=ammo)],ammo=[dict(weapon='IS.LRM-10',rounds=5,ammo_mode=ammo)]),actor('b',equipment=['TAG'],at=[3,1,0]),actor('t',at=[2,8,0])],
            [adv(2),cmd('target','TT'),cmd('tag','TT',unit='b'),config('t',speed=75.25),inspect(),cmd('sight',0),adv(30),config('t',speed=75.25),cmd('sight',0),cmd('tag','-',unit='b'),cmd('sight',0),cmd('fire',0)])
        d['random']={'streams':{'sensor.detect':[1]*1000,'attack_rolls':[12],'fire_rolls':[12],'hit_location_rolls':[7]*100}}
        def guided(o,ammo=ammo):
            for i in (5,8): equal(o['results'][i]['attack']['bth_breakdown']['target_move'],0 if ammo else 3)
            for i in (10,11): equal(o['results'][i]['attack']['bth_breakdown']['target_move'],3)
            equal(state(o)['ammo'][0]['rounds'],4)
            before=state(o,'t',4);after=state(o,'t')
            assert sum(after['armor']+after['rear_armor'])<sum(before['armor']+before['rear_armor'])
        yield case('tag','semiguided-fire-'+str(ammo),d,guided,True)
    # Retargeting keeps the old TaggedBy exactly as in C until reciprocal checks.
    d=document([actor(equipment=['TAG']),actor('t'),actor('b',team=2,at=[3,1,0])],[adv(2),cmd('tag','TT'),adv(30),cmd('tag','BB'),inspect()])
    yield case('tag','retarget-stale-old-owner',d,lambda o:(equal(state(o,'t')['tagged_by'],state(o)['id']),equal(state(o,'b')['tagged_by'],state(o)['id']),equal(state(o)['tag_target'],state(o,'b')['id'])))
    # External service limitations are verified/reported independently of local success.
    d=document([actor(weapons=['IS.ThumperCannon'],ammo=[dict(weapon='IS.ThumperCannon',rounds=3)]),actor('t',team=1)],
        [cmd('spot','TT',unit='t'),adv(2),cmd('spot','TT'),cmd('target',2,4,unit='t'),inspect(),cmd('sight',0),cmd('fire',0)])
    def artillery(o):
        equal(o['results'][5]['ok'],True);equal(o['results'][6]['ok'],False);contains(o['results'][6]['message'],'unavailable');equal(state(o)['ammo'],state(o,index=4)['ammo']);equal(state(o)['armor'],state(o,index=4)['armor'])
    yield case('spotting','artillery-impact-blocked',d,artillery,blocked='D3: artillery flight, scatter and area impact dispatcher is unavailable; sight and links pass separately.')
    d=document([actor(in_character=True),actor('t',in_character=True,real=at_range(5))],[adv(3)]);d['random']={'streams':{'sensor.detect':[1]*100}}
    yield case('detection','persistent-XP-blocked',d,lambda o:equal(bool(state(o)['contacts']['t']&1),True),blocked='D1: no persistent character skill/XP ledger or MadePerceptionRoll/AccumulateSpotXP/AccumulateArtyXP service exists.')
    d=document(actions=[adv(2),cmd('scan','TT')])
    yield case('scanning','autopilot-blocked',d,lambda o:equal(o['results'][1]['ok'],True),blocked='D2: no UnZombifyMech or auto_reply service exists; enemy acquisition wake and scan autonomous reply are unavailable.')
    # Status priority pairs. Raw words deliberately isolate display predicates.
    for label,values,initial,col,expected in [
        ('tow-before-carry',{'status':8|0x4000,'carrying':1},{},0,'T'),
        ('carry-before-mode',{'carrying':1,'status2':65536},{},0,'t'),
        ('sprint-before-evade',{'status2':196608},{},0,'M'),
        ('destroy-before-light',{}, {'destroyed':True,'status2':32,'crit_status':2048},1,'D'),
        ('on-before-lit',{}, {'status2':32,'crit_status':2048},1,'L'),
        ('fallen-before-hull',{}, {'fallen':True,'hulldown':True},2,'F'),
        ('heat-before-gel',{}, {'heat':1,'crit_status':4194304},3,'+'),
        ('eccm-before-ecm',{}, {'status2':3},4,'P'),
        ('ecm-before-protected',{}, {'status2':9},4,'E'),
        ('protected-before-disturbed',{}, {'status2':12},4,'p')]:
        d=document([actor(),actor('t',**initial)],([config('t',**values)] if values else [])+[diag('status')]);d['config']={'periodic_updates':False}
        yield case('contacts','priority-'+label,d,lambda o,col=col,expected=expected:equal(o['results'][-1]['status'][col],expected),True)
    for preference in ('','e','a'):
        d=document([actor(),actor('t'),actor('b',team=1)],[adv(2),config(contact_options=preference),cmd('contacts','+')])
        expected=['t'] if preference=='e' else ['b'] if preference=='a' else ['b','t']
        yield case('contacts','configured-options-'+str(preference),d,lambda o,expected=expected:equal(sorted(x['name'] for x in o['results'][-1]['contacts']),expected),True)
    # Unit scanner gates refer to the target class; observers do not notify.
    d=document([actor(),actor('t',**{'class':'MW'})],[adv(2),cmd('scan','TT')])
    yield case('scanning','MW-target',d,lambda o:equal(o['results'][-1]['ok'],False))
    d=document([actor(observer=True),actor('t')],[adv(2),cmd('scan','TT')])
    yield case('scanning','observer-no-notice',d,lambda o:(equal(o['results'][-1]['ok'],True),equal(messages(state(o,'t'),'being scanned'),0)))
    d=document([actor(target=999999)],[cmd('view')])
    yield case('scanning','invalid-default-view',d,lambda o:(equal(o['results'][0]['ok'],False),equal(state(o)['target'],-1)))
    for args in ([],['TT','W'],[2,2]):
        d=document([actor(),actor('t',weapons=['IS.LRM-10'])],[adv(2),cmd('target','TT'),cmd('scan',*args)])
        yield case('scanning','argument-form-'+str(args),d,lambda o:equal(o['results'][-1]['ok'],True))
    # Manually listed odd/even halo cells; no production expected-value calculation.
    odd={(3,3),(3,2),(4,2),(4,3),(3,4),(2,3),(2,2)}
    even={(2,3),(2,2),(3,3),(3,4),(2,4),(1,4),(1,3)}
    d=document([actor(),actor('t',at=[3,3,0],crit_status=4194304),actor('b',at=[2,3,0],crit_status=4194304)],
        [dict(op='map',origin=[1,1],size=[4,4]),dict(op='remove',unit='t'),dict(op='map',origin=[1,1],size=[4,4]),dict(op='remove',unit='b'),dict(op='map',origin=[1,1],size=[4,4])])
    def halos(o):
        for i,expected in [(0,odd|even),(2,even),(4,set())]:
            equal({(1+j%4,1+j//4) for j,flag in enumerate(o['results'][i]['flags']) if flag&8},expected)
    yield case('visibility','overlapping-odd-even-halos',d,halos)
    for distance in (59.999,60.):
        # Rectangle cell (2,61) minus source y gives the exact source range.
        real=at_range(60-distance)
        d=document([actor(equipment=['searchlight'],status2=32,real=real)],[dict(op='map',origin=[2,61],size=[1,1])]);d['map']['mapvis']=60
        yield case('visibility','light-range-'+str(distance),d,lambda o,distance=distance:equal(bool(o['results'][0]['flags'][0]&8),distance<60))
    d=document([actor(equipment=['C3master']),actor('t')],[adv(2),cmd('tag','TT'),dict(op='equipment_hit',equipment='C3master')])
    yield case('tag','C3-critical-blocked',d,lambda o:(equal(o['results'][-1]['effect_applied'],False),contains(o['results'][-1]['message'],'unavailable')),blocked='D5: C3 working/total master accounting and countWorkingC3MastersOnMech are absent, preventing its conditional critical-to-TAG integration.')
    d=document([actor(equipment=['C3master'],crit_status=524288),actor('t')],[adv(2),cmd('tag','TT')])
    yield case('tag','C3-destroyed-predicate',d,lambda o:(equal(o['results'][-1]['ok'],False),contains(o['results'][-1]['message'],'destroyed')),True)
    for quiet in (False,True):
        d=document([actor(),actor('t',hidden=True)],[dict(op='pending-hide',unit='t',seconds=10),cmd('losemit','waves',unit='t') if quiet else adv(2),inspect()])
        yield case('detection','hide-cancel-'+str(quiet),d,lambda o:(equal(events(state(o,'t'),'HIDE'),[]),equal(bool(state(o,'t')['crit_status']&8),True)),True)
    d=document([actor(sensors=['I','I']),actor('t',real=at_range(10))],[diag('reactor-explosion',None,unit='t'),inspect(),adv(4)])
    d['config']={'periodic_updates':False};d['random']={'streams':{'sensor.detect':[1]*100}}
    yield case('detection','reactor-flash-producer',d,lambda o:(equal(state(o,index=1)['blinded'],True),equal(state(o)['blinded'],False),equal(messages(state(o),'Your sight recovers.'),1)),True)
    d=document([actor(weapons=[dict(name='IS.LRM-10',ammo_mode=524288)],ammo=[dict(weapon='IS.LRM-10',rounds=5,ammo_mode=524288)]),actor('b',equipment=['TAG']),actor('t',at=[2,8,0])],
        [adv(2),cmd('target','TT'),cmd('tag','TT',unit='b'),config('t',speed=75.25),cmd('fire',0)])
    d['random']={'streams':{'sensor.detect':[1]*100,'attack_rolls':[12],'hit_location_rolls':[7]*100}}
    yield case('tag','semiguided-fire-before-stable',d,lambda o:(equal(o['results'][-1]['attack']['bth_breakdown']['target_move'],0),equal(o['results'][-1]['attack']['hit'],True),equal(messages(state(o,'b'),'stable lock'),0),equal(state(o)['ammo'][0]['rounds'],4)),True)
    for disturbed,damage in [(False,8),(True,6)]:
        d=document([actor(weapons=[dict(name='IS.LRM-10',ammo_mode=2)],ammo=[dict(weapon='IS.LRM-10',rounds=5,ammo_mode=2)]),actor('t',at=[2,8,0],equipment=['Guardian'])],
            [cache(),cmd('target','TT')]+([cmd('ecm',unit='t'),diag('ecm',None,unit='t')] if disturbed else [])+[cmd('fire',0)])
        d['config']={'periodic_updates':False};d['random']={'seed':0,'streams':{'attack_rolls':[12],'hit_location_rolls':[7]*100}}
        yield case('ecm','missile-guidance-'+str(disturbed),d,lambda o,damage=damage:(equal(o['results'][-1]['attack']['damage_dealt'],damage),equal(state(o)['ammo'][0]['rounds'],4)),True)
