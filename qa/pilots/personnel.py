"""Independent transfer and ejection commands, source boundary fixtures."""
from qa.pilots.common import *

def transfer_state():
    chars=[character(wizard=False,lock='secret',values={},categories={'health':'0,0','attrs':'5,5,5,5,5','advs':'Lives:1/','skills':'GunBat:4,1000,0/'}),character(102,wizard=True,location=10,values={})]
    return chars

def run_boarding():
    a=Audit('boarding')
    for case,n,r,line in rows('boarding'):
        chars=transfer_state();u=unit(cls='MW',character=101);v=unit('v',20,team=1);units=[u,v];actions=[];options={}
        if n==1:
            u['core']={'quiet':yes(r['quiet'])};actions=[dict(op='personnel',kind='transfer',origin=10,destination=20,flags=int(r['flag'])),dict(op='personnel',kind='discard',unit='u')]
        elif n==2:
            s=r['condition'];v['speed']=15 if s=='same-team-speed15' else 15.01 if s=='same-team-speed15.01' else 0
            if s.startswith('other-team'):v['team']=2
            if s=='other-team-explicit-passing-lock':v['personnel']={'enter_lock':'source-external-lock','lock_result':True}
            if s=='failing-lock':v['personnel']={'enter_lock':'source-external-lock','lock_result':False}
            if s=='height-plus1':u['at'][2]=1
            if s=='height-plus2':u['at'][2]=2
            if s=='different-hex':v['at'][0]=4
            if s=='target-OOD':v['cocoon']=10
            if s=='ground-unfixable':v['class']='GROUND';v['sections'][0].update(armor=0,internal=0)
            if s=='MECH-no-head':v['sections'][7]['internal']=0
            if s=='MECH-destroyed-cockpit':v['sections'][7]['slots']=[{'index':2,'firemode':1}]
            if s=='MECH-disabled-cockpit':v['sections'][7]['slots']=[{'index':2,'firemode':2}]
            actions=[command('embark',args='VV')]
        elif n==3:
            u['class']='BA' if r['picker'].startswith('BA') else r['picker'];v['class']='MW';v['team']=1 if r['team']=='friendly' else 2
            for c in chars:c['location']=20
            if r['picker']=='BA-salvage':u['specials']=0x1000
            options['pickup_action']=int(r['action']);actions=[command('pickup',args='VV')]
        else:
            u['in_character']=r['state']=='IC';actions=[dict(op='personnel',kind='transfer',origin=10,destination=20,flags=1),dict(op='personnel',kind='discard',unit='u'),advance(int(r['time']))]
        d=doc(actions,characters=chars,units=units);d['pilots']=options
        out=a.cli(case,d,mode='ordinary' if n in (2,3) else 'diagnostic',identity=dict(outline=n,line=line,values=r));result=out['results'][0];state=out['state'];records=state['characters'];trace=state['personnel']['trace']
        if n==1:
            a.eq('actual count',result,int(r['count']));a.eq('ordinary moved',records['101']['location'],20);a.eq('wizard policy',records['102']['location'],20 if int(r['flag'])&1 else 10);a.eq('slave flag',records['101'].get('slave',False),yes(r['slave']));a.eq('wizard not enslaved',records['102'].get('slave',False),False)
            a.eq('XP loss',records['101']['categories']['skills'],'GunBat:4,666,0/' if yes(r['loss']) else 'GunBat:4,1000,0/')
            a.eq('discard deadline',[e['deadline'] for e in events(state,'NUKEMECH')],[10])
            a.true('transfer mode',any(t.get('kind')=='move' and t.get('loud')==(r['mode']=='loud') for t in trace))
        elif n==2:
            target=r['result'];errors={'speed-error':'too fast','locked-error':'Locked','FAIL-and-AFAIL':'locked','height-error':'too high','samehex-error':'same hex','landing-error':'land','wreck-error':'twisted metal','head-error':'head go','cockpit-missing-error':'stole the cockpit','cockpit-stuck-error':"door won't budge"}
            if target=='accepted-transfer-all':a.true('embark accepted',result.get('ok'));a.eq('all contents',[records[str(i)]['location'] for i in (101,102)],[20,20]);a.eq('discard scheduled',len(events(state,'NUKEMECH')),1)
            else:a.error(result,errors[target]);a.eq('occupants unmoved',[records[str(i)]['location'] for i in (101,102)],[10,10])
        elif n==3:
            if r['result']=='pickup-class-error':a.error(result,"can't pick up")
            else:
                a.true('pickup accepted',result.get('ok'));a.eq('picked up all',[records[str(i)]['location'] for i in (101,102)],[10,10]);a.eq('ordinary captive',records['101'].get('slave',False),r['team']=='enemy' and r['action']=='0');a.eq('wizard not captive',records['102'].get('slave',False),False);a.eq('no tow',state['units']['u']['relationships']['carrying'],None)
        else:
            ustate=state['units']['u']['personnel']
            if r['result'].startswith('leave-hook'):
                a.eq('discard flags',[ustate[k] for k in ('hardcode','going','dark','zombie')],[False,True,True,True]);a.eq('store location',ustate['location'],901);a.true('leave hook requested',any('LEAVE' in str(x) for x in trace))
            else:a.eq('hardcode retained',ustate['hardcode'],True)
            a.eq('empty original',state['personnel']['contents'].get('10',[]),[])
    return a.save()

def run_ejection():
    a=Audit('ejection')
    for case,n,r,line in rows('ejection'):
        c=character(wizard=False);u=unit(character=101,personnel={'official_pilot':101});chars=[c];actions=[];options={'radio_draws':[1234567]};config={};catalog=True
        if n==1:
            s=r['condition']
            if s=='ground-landed-owner':u['class']='GROUND'
            if s=='VTOL-airborne':u['class']='VTOL';u['at'][2]=3
            if s=='dropship':u['class']='DS'
            if s=='BA':u['class']='BA'
            if s=='nonIC-unit':u['in_character']=False
            if s=='nonIC-map':u['personnel']['location_ic']=False
            if s=='MUX-IC-off':options['in_character']=False
            if s=='started-other-pilot':chars.append(character(102,location=10,wizard=False));actions=[command('eject',actor=102)]
            if s=='stopped-wrong-owner':u['started']=False;u['personnel']['official_pilot']=102
            if s=='nonfunctional-cockpit':u['sections'][7]['slots']=[dict(index=2,firemode=1)]
            if s=='missing-template':c['mwtemplate']='NoSuchPilotTemplate'
            if not actions:actions=[command('eject')]
        elif n==2:
            u['started']=yes(r['started']);u['speed']=float(r['speed']);actor=101
            if r['caller']=='passenger':chars.append(character(102,location=10,wizard=False));actor=102
            actions=[command('disembark',actor=actor)]
        elif n==3:
            u['started']=False;u['at'][2]=int(r['z']);u['speed']=float(r['speed']);u['vertical_speed']=float(r['vertical']);actions=[command('disembark')]
        else:
            # Source destruction helpers, with ordinary producer exercised separately
            # by QA workflow 13. These are explicitly diagnostic edge fixtures.
            s=r['condition']
            if s.startswith('last-BA'):
                u['class']='BA'
                for i in range(8):u['sections'][i].update(armor=0,internal=1 if i==7 else 0,internal_orig=1 if i==7 else 0)
                actions=[dict(op='diagnose',kind='destroy-section',unit='u',options={'section':7})]
            else:actions=[dict(op='diagnose',kind='reactor-explosion',unit='u')]
            if s=='player-zero':u.pop('character');u['pilot_details']={'id':0}
            if s=='location-nonIC':u['personnel']['location_ic']=False
            if s=='missing-template':c['mwtemplate']='NoSuchPilotTemplate'
        d=doc(actions,characters=chars,units=[u]);d['pilots']=options;d['construction']={'catalog':catalog};d['random']={'seed':17}
        if n==3 and r['ground']=='-2':d['map']['default']=['WATER',2]
        if n==4 and r['condition'].startswith('last-BA'):d['random']={'streams':{'suit_ejection':[25 if '25' in r['condition'] else 26]}}
        out=a.cli(case,d,mode='ordinary' if n<4 else 'diagnostic',identity=dict(outline=n,line=line,values=r));result=out['results'][0];state=out['state'];created=[v for k,v in state['units'].items() if k!='u']
        if n==1:
            errors={'landed-error':'landed','dropship-error':'Dropships','no-seat-error':'no ejection seat','unit-IC-error':"unit isn't",'location-IC-error':"location isn't",'MUX-IC-error':"MUX isn't",'seat-error':"pilot's seat",'official-pilot-error':'official pilot','used-cockpit-error':'already used'}
            s=r['result']
            if s in errors:a.error(result,errors[s]);a.eq('no creation',created,[])
            elif s.startswith('creation-'):a.eq('no orphan',created,[]);a.eq('actor unmoved',state['characters']['101']['location'],10);a.eq('source survives',state['units']['u']['destroyed'],False)
            else:
                a.eq('one MW',len(created),1);a.true('source destroyed',state['units']['u']['destroyed']);a.eq('actor transferred',state['characters']['101']['location'],created[0]['id']);a.eq('radio separate',[x['channel'] for x in state['personnel']['radio']],[234567]);a.eq('source head consumed',bool(state['units']['u']['sections'][7]['slots'][2]['firemode']&1),r['condition'].startswith('MECH'))
        elif n==2:
            if r['result']=='accepted':a.eq('one MW',len(created),1);a.eq('original retained',state['units']['u']['destroyed'],False)
            else:a.error(result,'running' if r['result']=='rejected-running' else 'too fast');a.eq('no MW',created,[])
        elif n==3:
            a.eq('one MW',len(created),1)
            if created:
                a.eq('source Z',created[0]['at'][2],int(r['z']));falls=events(state,'FALL');a.eq('fall data',[e['data2'] for e in falls],[] if r['data']=='none' else [int(r['data'])]);a.eq('fall delay',[e['deadline'] for e in falls],[] if r['data']=='none' else [int(r['delay'])])
        else:
            should=r['condition'] in ('surface-reactor-valid-pilot','last-BA-escape-roll25');a.eq('MW count',len(created),int(should))
            if should:
                a.eq('pilot transferred',state['characters']['101']['location'],created[0]['id']);a.eq('OOD distinction',created[0]['at'][2],150 if r['condition'].startswith('surface') else 0)
    return a.save()

def run_carriers():
    a=Audit('carriers')
    for case,n,r,line in rows('carriers'):
        c=character(wizard=False);u=unit(character=101,tonnage=5,measured_mass=5120,max_speed=64.5,personnel={'official_pilot':101});v=unit('v',20,team=1,specials2=0x80000,max_speed=64.5,construction={'car_max_ton':5,'cargo_space':500});units=[u,v];actions=[];mode='ordinary'
        if n==1:
            s=r['condition']
            if '499' in s:v['construction']['cargo_space']=499
            if 'max4' in s:v['construction']['car_max_ton']=4
            if s.startswith('own5-towed3'):
                v['construction']['cargo_space']=800 if '800' in s else 799
                units.append(unit('tow',30,contact_id='TO',team=1,tonnage=3,measured_mass=3072));u['carrying']=30
            if s=='target-speed0.01':v['speed']=.01
            if s=='own-MMaxSpeed-below-MP1':u['max_speed']=10
            if s=='own-hidden':u['hidden']=True
            if s=='section-recycle':u['sections'][0]['recycle']=1
            if s=='weapon-recycle':u['weapons']=[{'name':'IS.MediumLaser','section':0,'critical':4}];u['sections'][0]['slots']=[{'index':4,'data':1}]
            if 'noncarrier' in s:v['specials2']=0
            if s.startswith('BA-'):u['class']='BA'
            if s=='own-carrying-target':u['carrying']=20
            if s=='jumping-target':v['status']=0x8|0x40
            actions=[command('embark',args='VV')]
        else:
            # Actual carried membership is fixture input; exit is the real command.
            u['personnel']['location']=20;v['construction']['cargo_space']=0
            if n==2:
                s=r['condition']
                if s=='IC-wrong-official-owner':u['personnel']['official_pilot']=102
                if s=='IC-wizard':c['wizard']=True;u['personnel']['official_pilot']=102
                if s=='repairs-pending':u['core']={'repair_remaining':10}
                if s=='carrier-speed-walk':v['speed']=43
                if s=='carrier-speed-overwalk':v['speed']=43.01
                if s=='carrier-no-map':actions.append(dict(op='core',unit='v',values={'mapindex':-1}))
                if s.startswith('BA'):u['class']='BA';v['started']=False
                if s=='MECH-ground-carrier-stopped':v['started']=False
                if s in ('nonflyer-abovefloor','landed-flyer-abovefloor-carrier-started'):v['at'][2]=3
                if s.startswith('landed-flyer'):u['class']='VTOL'
            else:u['class']='GROUND' if r['class']=='ground' else r['class']
            actions.extend([dict(op='remove',unit='u'),dict(op='core',unit='u',values={'mapindex':-1}),command('udisembark')])
        d=doc(actions,characters=[c],units=units);d['random']={'seed':7}
        out=a.cli(case,d,mode=mode,identity=dict(outline=n,line=line,values=r));result=out['results'][-1];state=out['state'];own=state['units']['u'];carrier=state['units']['v'];expected=r.get('result','')
        errors={'cargo-error':'cargospace for you','class-tonnage-error':'too large','combined-cargo-error':'you and your towed','speed-error':'too fast' if n==1 else 'faster than walk','overload-error':'overloaded','hidden-error':'hidden','physical-recycle-error':'recovering','weapon-recycle-error':'weapons recycling','carrier-required':"can't handle",'towing-target-error':'what your towing','jump-error':'jumping','owner-error':"isn't your mech",'repair-error':'repairs','map-error':'not on a map'}
        if expected in errors:a.error(result,errors[expected])
        elif n==1:
            a.true('board accepted',result.get('ok'));a.eq('unit now carried',own['personnel']['location'],20);a.eq('off-map',own['mapindex'],-1);a.eq('preserved XY',own['at'][:2],u['at'][:2]);a.eq('shutdown',own['started'],False);a.eq('capacity debited',carrier['construction']['cargo_space'],0)
            if expected.startswith('both'):
                a.eq('tow cleared',own['relationships']['carrying'],None);a.eq('towee carried',state['units']['tow']['personnel']['location'],20);a.eq('towee before own',state['personnel']['contents']['20'],[30,10])
        else:
            a.true('exit accepted',result.get('ok'));a.eq('cargo credited',carrier['construction']['cargo_space'],500);a.true('immediate startup',own['started']);a.eq('pilot identity',own['pilot']['id'],101)
            if n==3:
                expected=[20]*8 if r['class']=='BA' else [60 if i!=5 or r['class'] in ('MECH','MW') else 0 for i in range(8)]
                a.eq('all source section recycles',[s['recycle'] for s in own['sections']],expected)
            elif expected=='breakout-fall4':a.eq('fall level',own['last_fall_levels'],4)
            elif expected=='OOD':a.true('drop event',any(e['kind']=='OOD' for e in own['events']))
            elif expected=='ramp-clear-landed':a.eq('landed cleared',bool(own['status']&0x1),False)
    return a.save()
