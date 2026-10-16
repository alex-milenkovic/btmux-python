"""UI fixtures and independent assertions for every sensors_los example row."""
from sensors_support import *


def controls(n,r):
    d=document();a=d['actions'];diagnostic=False
    if n==1:
        a += [adv(2),cmd('target','TT'),config(targ_x=4,targ_y=5),inspect(),cmd('sensor',*r['request'].split()),adv(r['seconds'])]
        diagnostic=True
        def check(o):
            s=state(o);before=state(o,index=3)
            equal(s['sensors'],r['current']);equal(s['wanted'],None if r['wanted']=='none' else r['wanted'])
            equal(s['target'],-1 if r['target']=='cleared' else state(o,'t')['id'])
            equal((s['hex_target'],s['lock_modes']),(before['hex_target'],before['lock_modes']))
    elif n==2:
        a += [cmd('sensor','I','E'),adv(3),cmd('sensor',*r['request'].split()),adv(r['time']-3)]
        def check(o):
            s=state(o);equal(s['sensors'],r['current']);equal(s['wanted'],None if r['wanted']=='none' else r['wanted'])
            equal(events(s,'SCHANGE'),[] if r['deadline']=='none' else [r['deadline']])
    elif n==3:
        d['map'].update(light=0);d['units'][0]['sensors']=list(r['pair'])
        a += [dict(op='conditions',weather=f"30 {r['light']} 0 0 0"),adv(25)]
        def check(o): equal(state(o)['sensors'],r['current']);equal(events(state(o),'SCHANGE'),[])
    else:
        d['map']['light']=0;d['units'][0].update(sensors=list(r['pair']),equipment=equipment(r['pair']))
        a += [cmd('sensor',*(['info'] if r['style']=='verbose' else []))]
        def check(o):
            text=o['results'][0]['message'];assert r['name'] in text,text
            if r['arc']=='fullvision': assert 'degree scanning' not in text,text
            else: assert str(r['arc'])+' degree scanning' in text,text
            equal('Blocked by:' in text,r['details']=='present')
    return Case(d,check,diagnostic=diagnostic)


def detection(n,r):
    d=document();a=d['actions'];diagnostic=n>=3
    if n==1:
        f=r['workflow']
        if f=='map-maintenance-only': a += [diag('map-maintenance')];diagnostic=True
        else:
            if f.startswith('repeated'): a += [dict(op='register'),dict(op='register')]
            a += [adv(2)]
            if f.startswith('acquire-then'): a += [cmd('shutdown'),adv(2)]
            if f.startswith('acquire-lock'): a += [cmd('target','TT'),dict(op='conditions',sensorflags=1),adv(2)]
        def check(o):
            s=state(o);equal(bool(s['contacts']['t']&1),r['seen']);equal(s['num_seen'],r['count']);equal(len(events(s,'PLOS')),r['chains'])
            if 'disable' in f: equal(s['target'],-1);equal(events(s,'LOCK'),[])
    elif n==2:
        d['units'][0]['brief']=4*r['mode'];d['units'][1]['team']=1 if r['relation']=='friend' else 2
        a += [adv(2)]
        def check(o):
            texts=[m for m in state(o)['messages'] if 'Seen:' in m or 'You notice' in m]
            equal('short' if texts and 'Seen:' in texts[0] else 'long' if texts else 'none',r['style']);equal(any('%cr' in m for m in texts),r['warning'])
    elif n==3:
        d['units'][0].update(sensors=[r['sensor']]*2,equipment=equipment(r['sensor']));d['map']['sensorflags']=r['mask']
        a += [diag('eligibility')]
        def check(o): equal(o['results'][0]['eligible'],r['eligible'])
    else:
        d['config']={'periodic_updates':False};d['map']['light']=0;d['units'][0]['sensors']=[r['primary'],'V']
        a += [cache(),dict(op='flash',source='t',duration=4),config(conscious=r['conscious']),adv(r['seconds'])]
        def check(o): equal(state(o)['blinded'],r['blinded']);equal(messages(state(o),'Your sight recovers.'),r['messages'])
    return Case(d,check,diagnostic=diagnostic)


def los(n,r):
    d=document();d['config']={'periodic_updates':False};a=d['actions']
    if n==1:
        d['units'][0].update(at=[2,1,2],**{'class':r['class'],'movement':r['movement'],'fallen':r['posture']=='fallen'})
        if r['posture']=='dug-in': a += [config(tank_crit_status=4)]
        a += [diag('height',None)]
        def check(o): near(o['results'][-1]['height'],r['height'])
    elif n==2:
        d['units'][1]['at']=[2,2,r['height']]
        d['map']['hexes']=[dict(at=[2,2],terrain=r['terrain'],elevation=0,**({'overlay':r['overlay']} if r['overlay']!='none' else {}))]
        a += [cache(2),diag('terrain-modifier')]
        def check(o): near(o['results'][-1]['modifier'],r['modifier'])
    elif n==3:
        d['config']['infrared_profile']=r['profile'];d['units'][0]['sensors']=['I','I']
        d['units'][1].update(hulldown=True,heat=r['heat'],plus_heat=r['plus'],minus_heat=r['minus'])
        a += [cache(4098),diag('terrain-modifier')]
        def check(o): near(o['results'][-1]['modifier'],r['modifier'])
    else:
        a += [cache((2 if r['primary'] else 0)|(4 if r['secondary'] else 0)|(32768 if r['block'] else 0)),diag('los')]
        def check(o): equal(o['results'][-1],dict(detected=r['detected'],identified=r['identified']))
    return Case(d,check,diagnostic=True)


def ecm_cases(n,r):
    d=document();a=d['actions'];diagnostic=n==4
    if n==1:
        d['units'][1].update(real=at_range(r['range']),equipment=[r['suite']])
        a += [cmd({'Guardian':'ecm','Angel':'angelecm','Personal':'perecm'}[r['suite']],unit='t'),adv(2)]
        def check(o): equal(o['results'][0]['ok'],True);equal(state(o)['disturbed'],r['disturbed'])
    elif n==2:
        d['units']= [actor()]
        for column,team,equip,command in [('fg',1,'Guardian','ecm'),('fa',1,'Angel','angelecm'),('hc',2,'Guardian','eccm'),('fc',1,'Guardian','eccm'),('ha',2,'Angel','angelecm')]:
            for j in range(r[column]):
                name=f'{column}{j}';d['units'].append(actor(name,contact_id=f'{len(d["units"]):02}',team=team,at=[2,2,0],equipment=[equip]));a += [cmd(command,unit=name)]
        a += [adv(2)]
        def check(o): equal(state(o)['countered'],r['countered']);equal(state(o)['disturbed'],r['disturbed'])
    elif n==3:
        d['units'][0].update(equipment=['Beagle'],sensors=['B','B']);d['units'][1]['equipment']=['Guardian']
        d['units'].append(actor('probe',contact_id='PP',at=[2,2,0]))
        a += [cmd('ecm',unit='t'),adv(r['updates']*2),diag('eligibility','probe'),dict(op='remove',unit='t'),adv(2),diag('eligibility','probe')]
        def check(o):
            equal(o['results'][2]['eligible'],0);equal(o['results'][5]['eligible'],3);equal(state(o)['disturbed'],False)
            equal(messages(state(o),'static!'),1);equal(messages(state(o),'back to normal'),1)
    else:
        d['units'][0]['sections']=[dict(index=0,armor=r['armor'],internal=r['internal'],specials=8,config=2 if r['config'] else 0)]
        a += [diag('ecm')]
        def check(o): equal(state(o)['disturbed'],r['disturbed'])
    return Case(d,check,diagnostic=diagnostic)


def illumination(n,r):
    d=document();a=d['actions']
    if n==1:
        d['units'][0].update(equipment=['searchlight'],status2=32 if r['initial'] else 0)
        a += [cmd('slite'),cmd('slite'),adv(r['seconds'])]
        def check(o):
            equal(sum(v.get('ok',False) for v in o['results']),1);equal(state(o)['searchlight'],r['on']);equal(bool(events(state(o),'SLITE_CHANGE')),r['pending'])
    elif n==2:
        d['config']={'periodic_updates':False};d['units'][0].update(equipment=['searchlight'],status2=32)
        if r['arc']=='turret-only': d['units'][0].update(**{'class':'VEH_GROUND','movement':'TRACK'},facing=0,turret_facing=180)
        d['units'][1]['real']=at_range(r['range'])
        a += [cache(r['woods']*32+r['water']*512+(32768 if r['block'] else 0)),diag('illumination')]
        def check(o): equal(o['results'][-1]['qualifies'],bool(r['qualifies']))
    else:
        d['config']={'periodic_updates':False};d['units'][0]['status2']=32 if r['sources'] else 0
        d['units'][1].update(real=at_range(30),crit_status=2048,sl_warn=r['warn'])
        a += [cache(),diag('end-light',None,'t'),diag('end-light',None,'t')]
        def check(o): equal(state(o,'t')['lit'],r['lit']);equal(messages(state(o,'t'),'no longer being illuminated'),r['messages'])
    return Case(d,check,diagnostic=n>1)


def tag(n,r):
    d=document();a=d['actions'];d['units'][0]['equipment']=['TAG'];diagnostic=False
    if n==1:
        d['units'][1]['real']=at_range(r['range']);d['random']={'streams':{'sensor.detect':[1]*500}}
        a += [adv(2),cmd('tag','TT'),adv(r['seconds'])]
        def check(o):
            s=state(o);equal(o['results'][1]['ok'],r['accepted']);equal(s['tag_target']==state(o,'t')['id'] and state(o,'t')['tagged_by']==s['id'],r['linked'])
            equal(messages(s,'stable lock'),r['stable']);equal(bool(events(s,'TAG_RECYCLE')),r['recycling'])
    elif n==2:
        a += [adv(2),cmd('tag','TT'),adv(r['cancel_time']),cmd('tag','-'),adv(r['time']-r['cancel_time'])]
        def check(o):
            s=state(o);equal(o['results'][3]['ok'],r['accepted']);equal(s['tag_target']==state(o,'t')['id'],r['linked']);equal(bool(events(s,'TAG_RECYCLE')),r['recycling']);equal(messages(s,'finished recycling'),r['ready'])
    elif n==3:
        d['units'].append(actor('b',equipment=['TAG'],at=[3,1,0]));d['random']={'streams':{'sensor.detect':[1]*1000}}
        a += [adv(2),cmd('tag','TT'),adv(30)]
        change=r['change']
        if change.startswith('range-to-'): a += [move(float(change[9:]))]
        elif change=='block-NB-LOS': a += [cache(32770)];diagnostic=True
        elif change=='b-overwrites-tag': a += [cmd('tag','TT',unit='b')]
        else: a += [dict(op='remove',unit='t')]
        a += [diag('tag')]
        def check(o):
            s=state(o);t=state(o,'t');equal(s['tag_target']>0,r['linked']);equal(bool(events(s,'TAG_RECYCLE')),r['cooldown'])
            owner='absent' if not t['mapped'] else 'original' if t['tagged_by']==s['id'] else 'b' if t['tagged_by']==state(o,'b')['id'] else 'none';equal(owner,r['owner'])
    else:
        diagnostic=True;d['config']={'periodic_updates':False}
        relation=r['tagger'];units=[actor()]
        if relation in ('other-friendly','hostile'): units += [actor('b',team=1 if relation=='other-friendly' else 2)]
        ref={'other-friendly':'b','hostile':'b','self':'u','dangling-positive-ID':999999,'none':0}[relation]
        units += [actor('t',speed=r['speed'],started=r['started'],tagged_by=ref)]
        units[0]['weapons']=[dict(name='IS.LRM-10',ammo_mode=524288 if r['ammo']=='semiguided' else 0)];d['units']=units
        a += [cache(),cmd('target','TT'),cmd('sight',0)]
        def check(o): equal(o['results'][-1]['attack']['bth_breakdown']['target_move'],r['applied'])
    return Case(d,check,diagnostic=diagnostic)


def artillery_document(distance=10,radio=80):
    d=document();d['units'][0]['weapons']=['IS.ThumperCannon'];d['units'][1].update(team=1,real=at_range(distance),radio_range=radio)
    d['map']['hexes']=[dict(at=[2,5],terrain='CLEAR',elevation=9)]
    d['actions']=[cmd('spot','TT',unit='t'),adv(2),cmd('spot','TT')]
    return d


def spotting(n,r):
    diagnostic=False
    if n in (1,2,3):
        d=artillery_document(r['range'] if n==1 else 10,10 if n in (1,3) else 80);a=d['actions'];deadline=2*((int(r['range']) if n==1 else 10)//10+5)
        if n==1:
            a += [adv(r['seconds'])]
            def check(o): equal(o['results'][2]['ok'],r['accepted']);equal(state(o)['spotter']==state(o,'t')['id'],r['linked']);equal(bool(events(state(o),'SPOT_LOCK')),r['pending'])
        elif n==2:
            for name,x,y,distance in [('u',r['sx'],r['sy'],0),('t',r['ox'],r['oy'],10)]:
                real=at_range(distance);real[0]+=int(x);real[1]+=int(y)
                a += [dict(op='place',unit=name,at=[2,1+distance,0],real=real)]
            a += [adv(deadline)]
            def check(o): equal(state(o)['spotter']==state(o,'t')['id'],r['linked']);equal(sum(messages(s,'not established due to movement') for s in o['state']['units'].values()),r['messages'])
        else:
            if r['method']=='ordinary-LOS':
                d=document();a=d['actions'];d['units'][1].update(team=1,radio_range=10)
                a += [cmd('spot','TT',unit='t'),adv(2),cmd('spot','TT')]
            else: a += [adv(deadline)]
            change=r['state']
            if change=='at-radio-limit': a += [move(20)]
            elif change=='beyond-radio-range': a += [move(20.01)]
            elif change=='no-longer-spotting': a += [cmd('spot','-',unit='t')]
            elif change=='linked-to-another-spotter':
                # Set a real friend as spotter through commands, then relink the observer.
                d['units'].append(actor('b',at=[2,2,0]));a += [cmd('spot','BB',unit='b'),move(1),adv(2),cmd('spot','BB',unit='t')]
            else: a += [dict(op='remove',unit='t')]
            a += [adv(10)]
            def check(o): equal(state(o)['spotter']==state(o,'t')['id'],r['linked']);equal(bool(events(state(o),'SPOT_CHECK')),r['watchdog'])
    elif n==4:
        d=document([actor(),actor('t',team=1),actor('linked',contact_id='LL',team=1),actor('other',contact_id='OO',team=1,fire_adjustment=7)])
        a=d['actions'];a += [cmd('spot','AA'),adv(2),cmd('spot','AA',unit='t'),cmd('spot','AA',unit='linked'),config('t',fire_adjustment=3),config('linked',fire_adjustment=5)]
        # Adjustment is the preexisting accumulated correction, supplied diagnostically.
        diagnostic=True
        a += [cmd('spot','-') if r['action']=='spot-cancel' else cmd('target','-') if r['action']=='clear-target' else cmd('target',4,4)]
        def check(o): equal(state(o,'t')['fire_adjustment'],0);equal(state(o,'linked')['fire_adjustment'],0);equal(state(o,'other')['fire_adjustment'],7)
    else:
        d=document([actor(weapons=['IS.ThumperCannon' if r['weapon']=='artillery' else 'IS.LRM-10']),actor('t',team=1),actor('enemy',contact_id='EE',team=2,at=[2,3,0])]);a=d['actions']
        a += [cmd('spot','TT',unit='t'),adv(2),cmd('spot','TT')]
        if r['target'] in ('unit','clear-unit'): a += [cmd('target','EE',unit='t')]
        else:
            if r['target']=='empty-hex': a += [dict(op='remove',unit='enemy')]
            a += [cmd('target',2,3,unit='t')]
        a += [inspect(),cmd('sight',0)]
        def check(o):
            result=o['results'][-1];equal(result['ok'],r['accepted']);attack=result['attack']
            if r['modifier']=='none': equal(attack['bth_breakdown'],None)
            else: equal(attack['observer_modifier'],r['modifier']);equal(attack['target_id'] is not None,r['selection']=='unit')
            before=o['results'][-2]['units'];equal(state(o,'enemy')['armor'],before['enemy']['armor']);equal(state(o)['ammo'],before['u']['ammo']);equal(state(o)['weapons'],before['u']['weapons'])
    return Case(d,check,diagnostic=diagnostic)


def contacts(n,r):
    d=document();a=d['actions'];diagnostic=n==4
    if n==1:
        d['units'][0]['brief']=r['initial'];a += [cmd('brief',*r['request'].split()),cmd('brief')]
        def check(o): equal(o['results'][0]['ok'],r['accepted']);equal(state(o)['brief'],r['value'])
    elif n==2:
        d['units']=[actor(brief=2)]+[actor(name,contact_id=name.upper()*2,team=1 if name=='f' else 2,started=name in ('f','e'),destroyed=name=='d',at=[2,2,0]) for name in ('f','e','s','d','t')]
        a += [adv(2),cmd('target','TT'),cmd('contacts',*([] if r['filter']=='no-argument' else [r['filter']]))]
        def check(o): equal(sorted(x['name'] for x in o['results'][-1]['contacts']),sorted(r['ids'].split(',')))
    elif n==3:
        d['units']=[actor(brief=r['brevity'])]+[actor(name,contact_id=code,real=at_range(dist),destroyed=name=='wreck') for name,code,dist in [('near','NN',2),('far','FF',8),('wreck','WW',1)]]
        d['random']={'streams':{'sensor.detect':[1]*100}};a += [adv(2),cmd('contacts')]
        def check(o): equal([x['name'] for x in o['results'][-1]['contacts']],r['order'].split(','));equal(o['results'][-1]['heading'],r['heading'])
    else:
        d['units'][0]['brief']=2;d['units'][1].update(team=1,heat=5,crit_status=4194304,status2=1,sections=[dict(index=0,specials=1)])
        d['map']['hexes']=[dict(at=[2,2],terrain='FIRE',elevation=0)]
        a += [cache(2|(32768 if r['block'] else 0)),cmd('contacts')]
        def check(o):
            row=o['results'][-1]['contacts'][0];equal(row['name'],'t' if r['name']=='real-name' else r['name']);equal(row['friend'],r['friend']);equal(row['status'],r['status'].replace('_',' '))
    return Case(d,check,diagnostic=diagnostic)


def scanning(n,r):
    d=document();a=d['actions'];diagnostic=n==3 and not r['nb']
    if n==1:
        d['units'][0]['scan_range']=r['scan_range'];d['units'][1]['real']=at_range(r['range']);d['random']={'streams':{'sensor.detect':[1]*100}}
        a += [adv(2),cmd(r['command'],'TT')]
        def check(o): equal(o['results'][-1]['ok'],r['accepted']);equal(messages(state(o,'t'),'being scanned'),r['notices'])
    elif n==2:
        d['units'][1]['weapons']=['IS.LRM-10'];a += [adv(2),cmd('target','TT'),cmd('scan',*([] if r['option']=='all' else [r['option']]))]
        def check(o):
            result=o['results'][-1]
            for k in ('armor','info','weapons'): equal(k in result,r[k])
            assert 'position' in result['report'] and 'movement' in result['report']
    elif n==3:
        d['units'][1]['markings']='' if r['markings']=='empty' else r['markings']
        a += [adv(2)] if r['nb'] else [cache(32770)]
        a += [cmd('view','TT')]
        def check(o):
            text=o['results'][-1]['message']
            if r['outcome']=='not-seen-well-enough': equal(o['results'][-1]['ok'],False);assert 'seen well enough' in text
            else: equal(text,'That target has no markings.' if r['outcome']=='no-markings' else r['outcome'])
    else:
        d['units'][0]['at']=[2,2,0];d['map'].update(dark=r['dark'],hexes=[dict(at=[2,5],terrain='CLEAR',elevation=4)])
        a += [cmd('range',2,5)]
        def check(o): equal(round(o['results'][-1]['range'],1),r['range']);equal(round(o['results'][-1]['ground_range'],1),3.)
    return Case(d,check,diagnostic=diagnostic)


def visibility(n,r):
    d=document([actor()]);a=d['actions'];size=[1,5]
    if n==1:
        d['units'][0].update(sensors=list(r['pair']),equipment=equipment(r['pair']),clairvoyant=r['clairvoyant']);d['map'].update(mapvis=r['visibility'],light=r['light'])
    elif n==2:
        d['map'].update(mapvis=3,light=0)
        if r['source']=='fire-decoration': d['map']['hexes']=[dict(at=[2,5],terrain='CLEAR',elevation=0,overlay='FIRE')]
        elif r['source']=='jellied-unit': d['units'].append(actor('t',at=[2,5,0],crit_status=4194304))
    elif n==3:
        d['units'][0]['sensors']=list(r['pair']);d['map'].update(mapvis=30,light=0,hexes=[dict(at=[2,2],terrain=r['terrain'],elevation=r['floor'])]);size=[1,3]
    else: d['map']['size']=[80,60];size=[r['width'],r['height']]
    a += [dict(op='map',origin=[0,0] if n==4 else [2,2],size=size)]
    def check(o):
        if n==4:
            if r['accepted']: equal(len(o['results'][0]['flags']),r['count'])
        else:
            equal(o['results'][0]['flags'],[int(v) for v in r['flags'].split(',')])
            for flag,cell in zip(o['results'][0]['flags'],o['results'][0]['cells']):
                if not flag&2: equal(cell['terrain'],None)
                if not flag&4: equal(cell['elevation'],None)
    return Case(d,check,invalid=n==4 and not r['accepted'])


BUILDERS=dict(controls=controls,detection=detection,los=los,ecm=ecm_cases,illumination=illumination,tag=tag,spotting=spotting,contacts=contacts,scanning=scanning,visibility=visibility)
