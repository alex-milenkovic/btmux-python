"""Boundary and lifecycle workflows from the supplemental QA procedures."""
from copy import deepcopy
from sensors_support import *
from sensors_feature_cases import artillery_document


def case(stem,label,d,check,diagnostic=False,invalid=False,blocked=''):
    return Case(d,check,stem+'/supplement-'+label,diagnostic,invalid,blocked)


def cases():
    # Controls: command gates, nine metadata rows, negative equipment and light.
    for pair in ('VV','LL','II','EE','SS','RR','BB','AA','HH'):
        d=document([actor(sensors=list(pair),equipment=equipment(pair))],[cmd('sensor','info')]);d['map']['light']=0
        names={'V':'Vislight','L':'Light-amplification','I':'Infrared','E':'Electromagnetic','S':'Seismic','R':'Radar','B':'Beagle','A':'Light Beagle','H':'Bloodhound'}
        def check(o,pair=pair): assert names[pair[0]] in o['results'][0]['message'];equal(o['results'][0]['ok'],True)
        yield case('controls','all-sensors-'+pair,d,check)
    for name,fixture,args,ok in [('stopped',{'started':False},['I','E'],True),('MW-display',{'class':'MW'},[],False),('MW-change',{'class':'MW'},['I','E'],False),('unknown',{},['Q','Q'],False),('excess',{},['I','E','V'],False)]+[(s+'-missing',{},[s,s],False) for s in 'RBAH']+[(s+'-null-signature',{'specials':131072},[s,s],False) for s in 'LIES']:
        d=document([actor(**fixture)],[cmd('sensor',*args)]);d['map']['light']=0
        def check(o,ok=ok): equal(o['results'][0]['ok'],ok);equal(state(o)['wanted'],None)
        yield case('controls','gate-'+name,d,check)
    for light in (0,1,2):
        d=document([actor()],[cmd('sensor','L','L')]);d['map']['light']=light
        yield case('controls',f'light-{light}',d,lambda o,light=light:equal(o['results'][0]['ok'],light<2))
    d=document(actions=[cmd('sensor','I','E'),cmd('shutdown'),adv(10)])
    yield case('controls','shutdown-expiry',d,lambda o:(equal(state(o)['sensors'],'VV'),equal(state(o)['wanted'],None)))
    d=document(actions=[adv(20),cmd('sensor','L','L'),dict(op='conditions',weather='30 2 0 0 200'),adv(10)]);d['map']['light']=0
    yield case('controls','no-expiry-revalidation',d,lambda o:equal(state(o)['sensors'],'LL'))
    for pair,expected in [('VV','vv'),('II','ii')]:
        d=document([actor(sensors=list(pair))],[diag('legacy-sensor-info',None)]);d['config']={'periodic_updates':False}
        # Legacy format checked literally against SensorInf and source sprintf.
        yield case('controls','legacy-'+pair,d,lambda o,expected=expected:equal(o['results'][0]['legacy'],expected),True)
    for value,expected in [(0,''),(2147483657,'0,3,31')]:
        d=document(actions=[diag('flags',None,value=value)])
        yield case('controls',f'flags-{value}',d,lambda o,expected=expected:equal(o['results'][0]['flags'],expected),True)
    d=document(actions=[diag('sensor-description',None,index=99)])
    yield case('controls','invalid-description',d,lambda o:equal(o['results'][0]['description'],'None'),True)
    for kind,weather,expected in [('defaults','bad',[30,60,2]),('clamp','90 9 7 8 123 Weather changed',[60,60,2]),('low','-2 -1 7 8',[0,24,0]),('dark','10 0 2 3',[10,30,0])]:
        d=document(actions=[dict(op='conditions',weather=weather),adv(25)])
        yield case('controls','weather-'+kind,d,lambda o,expected=expected:equal([o['state']['map'][k] for k in ('mapvis','maxvis','light')],expected))
    # Detection: quiet/gain/loss boundaries, preferences, stopped viewers/targets.
    for mode in range(7):
        for friend in (False,True):
            for gain in (False,True):
                d=document([actor(brief=4*mode),actor('t',team=1 if friend else 2)], [cache(),diag('notice',los=-1 if gain else 15,seeanew=1,gain=gain)])
                enabled=mode in (0,1,4) or (not friend and mode in (2,3,5))
                def check(o,enabled=enabled,gain=gain):
                    m=state(o)['messages'];equal(len(m),int(enabled))
                    if enabled: assert ('Seen:' in m[0] or 'You notice' in m[0]) if gain else ('Lost:' in m[0] or 'have lost' in m[0])
                yield case('detection',f'notice-{mode}-{friend}-{gain}',d,check,True)
    for gain in (False,True):
        for seeanew in range(4):
            d=document(actions=[cache(),diag('notice',los=0,seeanew=seeanew,gain=gain)])
            yield case('detection',f'quiet-boundary-{gain}-{seeanew}',d,lambda o,gain=gain,seeanew=seeanew:equal(bool(state(o)['messages']),seeanew<(2 if gain else 3)),True)
    for flag,pref,observer,expected in [(0,False,False,False),(8388608,False,False,True),(0,True,False,True),(8388608,True,True,False)]:
        d=document([actor(status=8|flag,autocon_shutdown=pref,observer=observer),actor('t',started=False)],[cache(),diag('notice',los=-1,seeanew=1,gain=True)])
        yield case('detection',f'shutdown-notice-{flag}-{pref}-{observer}',d,lambda o,expected=expected:equal(bool(state(o)['messages']),expected),True)
    for perception,expected in [(2,100),(6,85),(12,65)]:
        d=document([actor(perception=perception),actor('t')],[diag('sensor-chance')])
        yield case('detection',f'perception-{perception}',d,lambda o,expected=expected:equal(o['results'][0]['driver'],expected),True)
    for lock in (0,8):
        d=document(actions=[adv(2),cmd('target','TT'),dict(op='conditions',sensorflags=1),adv(2),inspect()]);d['config']={'lock_tick':lock}
        yield case('detection',f'loss-lock-{lock}',d,lambda o:(equal(state(o)['target'],-1),equal(state(o)['lock_modes'],0),equal(events(state(o),'LOCK'),[])))
    d=document(actions=[adv(2),cmd('shutdown'),adv(2),cmd('startup'),adv(35),inspect()])
    yield case('detection','restart-chain',d,lambda o:(equal(state(o)['started'],True),equal(len(events(state(o),'PLOS')),1)))
    d=document(actions=[dict(op='remove',unit='u'),adv(3)])
    yield case('detection','mapless-chain',d,lambda o:equal(events(state(o),'PLOS'),[]))
    for speed in (0,10.75,10.751):
        for enabled in (False,True):
            d=document([actor(sensors=['S','S']),actor('t',speed=speed)],[diag('eligibility')]);d['config']={'seismic_see_stopped':enabled,'periodic_updates':False}
            yield case('detection',f'seismic-{enabled}-{speed}',d,lambda o,enabled=enabled,speed=speed:equal(o['results'][0]['eligible'],3 if enabled or speed>10.75 else 0),True)
    for draw in (50,51):
        d=document([actor(sensors=['I','V']),actor('t')],[cache(),dict(op='flash',source='t',duration=4,chance=50),inspect(),adv(1),dict(op='flash',source='t',duration=9,chance=0),adv(3)])
        d['config']={'periodic_updates':False};d['random']={'streams':{'sensor.flash':[draw]}}
        def check(o,draw=draw):
            equal(state(o,index=2)['blinded'],draw==50)
            equal(state(o)['blinded'],draw!=50)
            equal(len([v for v in o['draws'] if v['name']=='sensor.flash']),1)
        yield case('detection','flash-boundary-'+str(draw),d,check,True)
    for fixture in ({'sensors':['V','I']},{'sensors':['I','V'],'conscious':False},{'sensors':['I','V'],'blinded':True}):
        d=document([actor(**fixture),actor('t')],[cache(),dict(op='flash',source='t',duration=4,chance=50)]);d['config']={'periodic_updates':False};d['random']={'streams':{'sensor.flash':[]}}
        yield case('detection','flash-excluded-'+str(list(fixture.values())),d,lambda o:equal(o['draws'],[]),True)
    d=document([actor(),actor('t'),actor('b',started=False)],[cmd('losemit','waves'),cmd('contacts',unit='t')])
    def broadcast(o):
        equal(messages(state(o),'waves'),0);equal(messages(state(o,'b'),'waves'),0);equal(messages(state(o,'t'),'waves'),1)
        equal(messages(state(o,'t'),'Seen:')+messages(state(o,'t'),'You notice'),0)
    yield case('detection','quiet-broadcast',d,broadcast)
    # Geometry and callbacks; independent flag/height expectations.
    for terrain,overlay,flag in [('LIGHT_FOREST',None,32),('HEAVY_FOREST','SMOKE',64|16384),('HEAVY_FOREST','FIRE',64|8192),('CLEAR',None,0)]:
        d=document([actor(),actor('t',at=[2,4,0])],[diag('trace')]);d['map']['hexes']=[dict(at=[2,2],terrain=terrain,elevation=0,**({'overlay':overlay} if overlay else {}))]
        def check(o,flag=flag): equal(o['results'][0]['trace'],[[2,2],[2,3],[2,4]]);equal(o['results'][0]['flags'],8|flag)
        yield case('los',f'trace-{terrain}-{overlay}',d,check,True)
    for reverse in (False,True):
        d=document([actor(at=[4,3,0] if reverse else [2,3,0]),actor('t',at=[2,3,0] if reverse else [4,3,0])],[diag('trace')])
        yield case('los',f'tied-horizontal-{reverse}',d,lambda o,reverse=reverse:equal(o['results'][0]['trace'],[[3,4],[2,3] if reverse else [4,3]]),True)
    for posture,expected in [(False,4096),(True,0)]:
        d=document([actor(),actor('t',at=[2,4,0],fallen=posture)],[diag('trace')]);d['map']['hexes']=[dict(at=[2,3],terrain='CLEAR',elevation=1)]
        yield case('los',f'partial-{posture}',d,lambda o,expected=expected:equal(o['results'][0]['flags']&4096,expected),True)
    for terrain,elevation,blocked in [('CLEAR',9,True),('BRIDGE',9,False)]:
        d=document([actor(),actor('t',at=[2,4,0])],[diag('trace')]);d['map']['hexes']=[dict(at=[2,2],terrain=terrain,elevation=elevation)]
        yield case('los',f'ridge-{terrain}',d,lambda o,blocked=blocked:equal(bool(o['results'][0]['flags']&32768),blocked),True)
    d=document([actor(),actor('t',at=[2,1,0])],[diag('trace')])
    yield case('los','same-hex',d,lambda o:equal(o['results'][0]['flags'],8),True)
    d=document([actor(at=[2,1,11]),actor('t',at=[2,4,11])],[diag('trace')]);d['map']['hexes']=[dict(at=[2,2],terrain='CLEAR',elevation=9)]
    yield case('los','high-altitude-bypass',d,lambda o:equal(o['results'][0]['flags'],8),True)
    for pair,flags,expected in [('VI',2,0),('VI',4,3),('VI',6,0),('VV',0,10000)]:
        d=document([actor(sensors=list(pair)),actor('t')],[cache(flags),diag('terrain-modifier')])
        yield case('los',f'selection-{pair}-{flags}',d,lambda o,expected=expected:equal(o['results'][-1]['modifier'],expected),True)
    d=document([actor(started=False),actor('t',started=False)],[adv(11),diag('random-window',None,low=0,high=1),diag('random-window',None,low=0,high=2),adv(1),diag('random-window',None,low=0,high=1),diag('random-window',None,unit='t',low=0,high=2)]);d['config']={'periodic_updates':False};d['random']={'streams':{'sensor.random':[7,8,5]}}
    yield case('los','event-random-window',d,lambda o:(equal([o['results'][i]['value'] for i in (1,2,4,5)],[1,1,0,2]),equal([v['value'] for v in o['draws']],[7,8,5])),True)
    # ECM commands, critical dispatch, vertical boundary, disturbance-kind latch.
    for command,equip,other,mask in [('ecm','Guardian','eccm',3),('angelecm','Angel','angeleccm',768),('perecm','Personal','pereccm',12288)]:
        d=document([actor(equipment=[equip])],[cmd(command),inspect(),cmd(other),inspect(),cmd(other),inspect(),cmd(command),cmd('shutdown'),adv(2)])
        def check(o,mask=mask):
            equal(state(o,index=1)['status2']&mask,mask//3);equal(state(o,index=3)['status2']&mask,mask//3*2);equal(state(o,index=5)['status2']&mask,0);equal(state(o)['status2']&mask,0)
        yield case('ecm','toggle-'+equip,d,check)
        for fixture in ({},{'pilot':False},{'started':False}):
            unit=actor(**fixture)
            if fixture: unit['equipment']=[equip]
            d=document([unit],[cmd(command)])
            yield case('ecm','gate-'+equip+'-'+str(fixture),d,lambda o:equal(o['results'][0]['ok'],False))
    for distance in (6,6.001):
        d=document([actor(),actor('t',equipment=['Guardian'],at=[2,1,0],real=[X2,Y1,distance*SCALE])],[cmd('ecm',unit='t'),diag('ecm')]);d['config']={'periodic_updates':False}
        yield case('ecm','vertical-'+str(distance),d,lambda o,distance=distance:equal(state(o)['disturbed'],distance==6),True)
    for equip,pair,expected in [('Guardian','VV','VV'),('Angel','VV','VV'),('Beagle','BB','VV'),('LightBeagle','AA','VV'),('Bloodhound','HH','HH')]:
        d=document([actor(equipment=[equip],sensors=list(pair))],[dict(op='equipment_hit',equipment=equip),cmd('sensor')])
        yield case('ecm','critical-'+equip,d,lambda o,expected=expected:equal(state(o)['sensors'],expected))
    d=document([actor(),actor('t',equipment=['Guardian','Angel'])],[cmd('ecm',unit='t'),adv(2),inspect(),cmd('ecm',unit='t'),cmd('angelecm',unit='t'),adv(2),inspect(),cmd('angelecm',unit='t'),adv(2),cmd('angelecm',unit='t'),adv(2),inspect()])
    def latch(o):
        equal(state(o,index=2)['status2']&2052,4);equal(state(o,index=6)['status2']&2052,4);equal(state(o)['status2']&2052,2048)
    yield case('ecm','kind-latch',d,latch)
    # Searchlights: real warmup/shutdown/two-source sweeps and strict new range.
    for interruption in ('shutdown','destroyed-light'):
        d=document([actor(equipment=['searchlight'])],[cmd('slite'),cmd('shutdown') if interruption=='shutdown' else config(crit_status=1024),adv(6)])
        yield case('illumination',interruption+'-warmup',d,lambda o:equal(state(o)['searchlight'],False),interruption!='shutdown')
    for distance,expected in [(29,True),(30,False)]:
        d=document([actor(equipment=['searchlight']),actor('t',real=at_range(distance),sl_warn=True)],[cmd('slite'),adv(8),inspect(),cmd('slite'),adv(8)])
        d['map'].update(mapvis=10,light=0);d['random']={'streams':{'sensor.detect':[1]*500}}
        def check(o,expected=expected):
            equal(state(o,'t',2)['lit'],expected);equal(state(o,'t')['lit'],False)
            equal(messages(state(o,'t'),'being illuminated!'),int(expected))
        yield case('illumination','normal-range-'+str(distance),d,check)
    d=document([actor(equipment=['searchlight']),actor('b',at=[2,1,0],equipment=['searchlight']),actor('t',real=at_range(29),sl_warn=True)],[cmd('slite'),cmd('slite',unit='b'),adv(8),dict(op='remove',unit='u'),adv(2),inspect(),dict(op='remove',unit='b'),adv(2)])
    yield case('illumination','two-sources',d,lambda o:(equal(state(o,'t',5)['lit'],True),equal(state(o,'t')['lit'],False),equal(messages(state(o,'t'),'no longer being illuminated'),1)))
    # TAG production damage, shutdown, cancellation precedence and fire consumer.
    for equip in ('TAG',):
        d=document([actor(equipment=[equip]),actor('t')],[adv(2),cmd('tag','TT'),dict(op='equipment_hit',equipment=equip),adv(30),cmd('tag','-')])
        yield case('tag','destroyed-'+equip,d,lambda o:(equal(o['results'][1]['ok'],True),equal(messages(state(o),'stable lock'),0),equal(o['results'][-1]['ok'],False)))
    d=document([actor(equipment=['TAG']),actor('t')],[adv(2),cmd('tag','TT'),adv(5),cmd('shutdown'),adv(30)])
    yield case('tag','shutdown-before-stable',d,lambda o:(equal(state(o)['tag_target'],0),equal(state(o,'t')['tagged_by'],0),equal(messages(state(o),'stable lock'),0)))
    for args in ([],['ZZ'],['AA'],['TT','extra'],['-']):
        d=document([actor(equipment=['TAG']),actor('t',team=1)],[adv(2),cmd('tag',*args)])
        yield case('tag','invalid-'+str(args),d,lambda o:equal(o['results'][-1]['ok'],False))
    # Spotting handshakes: preserve adjustments, duplicate source events, returns.
    d=artillery_document();d['units'][0]['fire_adjustment']=3;d['actions'] += [cmd('spot','TT'),adv(12)]
    yield case('spotting','duplicate-handshake',d,lambda o:(equal(state(o)['spotter'],state(o,'t')['id']),equal(state(o)['fire_adjustment'],3),equal(len(events(state(o),'SPOT_CHECK')),2)))
    d=artillery_document();d['actions'] += [move(11),move(10),adv(12)]
    yield case('spotting','return-position',d,lambda o:equal(state(o)['spotter'],state(o,'t')['id']))
    for fixture in ({'weapons':['IS.LRM-10'],'recycle':3},{'class':'MW'},{'started':False},{'pilot':False},{'status2':65536}):
        d=document([actor(**fixture)],[cmd('spot','AA')])
        yield case('spotting','self-gate-'+str(fixture),d,lambda o:equal(o['results'][0]['ok'],False))
    d=document([actor(status2=65536)],[cmd('spot','AA')]);d['config']={'movement_modes':False}
    yield case('spotting','movement-mode-config',d,lambda o:equal(o['results'][0]['ok'],True))
    # Contacts: all packed values, HUD, unknown options, roster holes and masks.
    for brief in range(4):
        d=document([actor(brief=brief),actor('t')],[dict(op='roster-hole'),adv(2),cmd('contacts','h')])
        yield case('contacts','hud-'+str(brief),d,lambda o:(equal(o['results'][-1]['hud'],True),equal(len(o['results'][-1]['contacts']),1),contains(o['results'][-1]['message'],'#HUDINFO:CON#End Contact List')))
    d=document(actions=[adv(2),cmd('contacts','z')])
    yield case('contacts','unknown-option',d,lambda o:contains(o['results'][-1]['message'],'Ignoring z'))
    d=document([actor(brief=1),actor('t')],[adv(2),cmd('contacts')])
    yield case('contacts','building-dependency',d,lambda o:contains(' '.join(o['results'][-1]['blocked']),'Building'),blocked='D4: visible/invisible/hidden building records, access locks, CF and +20000 ordering require the absent building service.')
    # Scanning safety, notification, metadata, supported coordinate grammars.
    for args in (['-1','0'],['200','0'],['0','200'],['x','y','z','w']):
        d=document(actions=[cmd('scan',*args)])
        yield case('scanning','reject-'+str(args),d,lambda o:equal(o['results'][0]['ok'],False))
    for fixture,expected in [({'class':'MW'},True),({'observer':True,'scan_range':1},True)]:
        d=document([actor(**fixture),actor('t',real=at_range(8))],[adv(2),cmd('scan','TT')]);d['random']={'streams':{'sensor.detect':[1]*100}}
        yield case('scanning','gate-'+str(fixture),d,lambda o,expected=expected:equal(o['results'][-1]['ok'],expected))
    for name,args in [('bearing',[]),('bearing',[2,4]),('bearing',[2,1,2,4]),('range',[]),('range',[2,4]),('range',[2,1,2,4]),('vector',[]),('vector',[2,4,0]),('vector',[2,1,0,2,4,4])]:
        d=document(actions=[adv(2),cmd('target','TT'),cmd(name,*args)])
        yield case('scanning','navigation-'+name+'-'+str(args),d,lambda o:equal(o['results'][-1]['ok'],True))
    for branch in ('B','H'):
        d=document(actions=[cmd('scan',2,2,branch)])
        yield case('scanning','dependency-'+branch,d,lambda o:(equal(o['results'][0]['ok'],False),contains(o['results'][0]['message'],'unavailable')),blocked='D4: building access/records or mine discovery service unavailable; this branch is not translated.')
    # Map supplements with manual straight-strip expectations and real expiry.
    for facing,pair,expected in [(0,'VV',[7,1,1,1,1]),(0,'VL',[1]*5),(180,'LL',[7,7,1,1,1]),(0,'IV',[7]*5)]:
        d=document([actor(facing=facing,sensors=list(pair))],[dict(op='map',origin=[2,2],size=[1,5])]);d['map'].update(mapvis=3,light=1)
        yield case('visibility','rear-union-'+str(facing)+pair,d,lambda o,expected=expected:equal(o['results'][0]['flags'],expected))
    d=document([actor()],[dict(op='map',origin=[2,2],size=[1,5]),adv(4),dict(op='map',origin=[2,2],size=[1,5])]);d['map'].update(mapvis=3,light=0,hexes=[dict(at=[2,5],terrain='LIGHT_FOREST',elevation=0,overlay='FIRE',duration=4)])
    yield case('visibility','fire-expiry-underlay',d,lambda o:(equal(o['results'][0]['flags'],[7,7,15,15,15]),equal(o['results'][2]['flags'],[7,7,1,1,1])))
    for origin,size in [([-1,0],[1,1]),([0,-1],[1,1]),([0,0],[-1,1]),([7,79],[2,1])]:
        d=document([actor()],[dict(op='map',origin=origin,size=size)])
        yield case('visibility','invalid-'+str(origin)+str(size),d,lambda o:None,invalid=True)
    d=document([actor(),actor('b',sensors=['R','R'],equipment=['Radar'])],[dict(op='map',origin=[2,2],size=[1,5]),dict(op='map',unit='b',origin=[2,2],size=[1,5]),dict(op='map',origin=[2,2],size=[1,5])]);d['map']['mapvis']=3
    yield case('visibility','alternating-observers',d,lambda o:(equal(o['results'][0],o['results'][2]),equal(o['results'][1]['flags'],[1]*5)))
    # Schema validation and read-only inspection are verified through the executable.
    for label,d in [('unknown-action',{'actions':[{'op':'fake'}]}),('unknown-field',{'actions':[],'answer':True}),('bad-enum',{'units':[{'name':'u','class':'FAKE'}],'actions':[]}),('bad-action-field',{'actions':[{'op':'inspect','answer':True}]}),('dice-exhaustion',document([actor(started=False)],[diag('random-window',None)])),('offmap-unit',document([actor(at=[999,1,0])]))]:
        if label=='dice-exhaustion': d['random']={'streams':{'sensor.random':[]}}
        yield case('controls','schema-'+label,d,lambda o:None,invalid=True)
    for index,value in enumerate(([], '', 0, False, None)):
        d=document(actions=[dict(op='diagnose',kind='map-maintenance',options=value)])
        yield case('controls','schema-diagnostic-options-'+str(index),d,lambda o:None,invalid=True)
    d=document(actions=[inspect(),inspect()])
    yield case('controls','inspect-purity',d,lambda o:(equal(o['results'][0],o['results'][1]),equal(o['results'][1],o['state']),equal(o['draws'],[])))
    from sensors_extended import cases as extended
    yield from extended()


def contains(text,part): assert part in text,(part,text)
def assert_legacy(o): assert isinstance(o['results'][0]['legacy'],str) and o['results'][0]['legacy']
