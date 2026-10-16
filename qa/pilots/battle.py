"""Eight-section actions and source clock/LOS boundaries through public controls."""
from qa.pilots.common import *

def ba(count=4,**kw):
    u=unit(cls='BA',character=101,infantry_specials=7,**kw)
    for i,s in enumerate(u['sections']):s.update(armor=100 if i<count else 0,internal=30 if i<count else 0,internal_orig=30 if i<count else 0)
    return u

def cfg(values,unit='u'):return dict(op='configure',unit=unit,values=values)
def probe(kind,**kw):return dict(op='pilot_diagnose',kind=kind,unit='u',**kw)

def run_swarm():
    a=Audit('swarm')
    for case,n,r,line in rows('swarm'):
        c=character(values={**dict.fromkeys(ATTRS,5),'Piloting-BSuit':4});u=ba();v=unit('v',20);units=[u,v];actions=[];streams={'pilot_rolls':[12]*10,'leg_location':[0]*10,'leg_critical':[7],'damage_entry':[7]*100,'critical_rolls':[2]*20,'enhanced_rolls':[12]*20,'critical_slot':[0]*60,'character_d6':[6]*20,'suit_fall_location':[7],'fall_directions':[1]*20,'hit_location_rolls':[7]*100};mode='diagnostic'
        if n==1:
            s=r['state']
            if s.startswith('only-'):
                u=ba(0);u['sections'][7].update(internal=1);units[0]=u
            elif s.startswith('section0'):
                u=ba(1);u['sections'][0].update(internal=1,config=2);units[0]=u
            elif s=='Clan':u['specials']=32
            if 'attached' in s or s=='zero-ID-entry':
                u['swarm_target']='v';u['team']=1;v['team']=1 if s=='friendly-only-attached' else 2
                if s=='enemy-then-friendly-attached':units.append(unit('friend',30,cls='BA',contact_id='FR',team=2,swarm_target='v'))
                actions=[probe('swarm-query',target='v',**({'source_id':0} if s=='zero-ID-entry' else {}))]
            elif s.startswith('host-'):
                v['at']=[3,4,2];actions=[dict(op='hex',value={'at':[3,4],'terrain':'GRASSLAND','elevation':1}),dict(op='place',unit='v',at=[3,4,2]),probe('mirror',target='v')]
            else:actions=[probe('swarm-query',**({'no_map':True} if s=='no-map' else {}))]
        elif n in (2,4):
            u=ba(int(r['members']),hidden=yes(r['hidden']));units[0]=u
            if r.get('team')=='friendly':v['team']=1
            if 'fallen' in r['target']:v['fallen']=True
            if 'immobile' in r['target']:v['started']=False
            actions=[probe('modifier',target='v',leg=n==4)]
            # Nonzero member command fixtures independently check real caller output.
            if int(r['members'])>0 and n==2:actions.append(command('swarm',args='VV'))
        elif n==3:
            mode='ordinary';s=r['condition'];args='VV';cmd='attackleg' if r['action']=='leg' else 'swarm'
            if s.startswith('range'):
                range_value=1 if s=='range1' else .999;u['real']=[1000,1000,0];v['real']=[1000,1000+322.5*range_value,0]
            if s=='stale-default':u['target']=9999;args=''
            if s=='two-arguments':args='VV XX'
            if s.startswith('friendly'):v['team']=1
            if s=='friendly-no-mount-tech':u['infantry_specials']=1
            if 'pending-jettison' in s:u['infantry_specials']|=0x100;u['sections'][7]['slots']=[dict(index=11,firemode=0x20000)]
            if s in ('swarmers-on-target-only','swarmers-on-attacker'):
                units.append(unit('third',30,cls='BA',contact_id='TH',swarm_target='v' if s.endswith('only') else 'u'))
            if s=='busy-functional-weapon-on-live-section7':u['sections'][7].update(armor=1,internal=1,slots=[dict(index=0,weapon='PC.SMG',data=3)])
            if s=='section7-recycle-live':u['sections'][7].update(armor=1,internal=1,recycle=3)
            if s=='attacker-legless':u['class']='MECH'
            if s=='quad-no-live-legs':
                v['movement']='QUAD'
                for i in (0,1,5,6):v['sections'][i]['internal']=0
            actions=[command(cmd,args=args)]
        elif n==5:
            mode='ordinary';streams['leg_critical']=[int(r['roll'])];u=ba(8);units[0]=u
            # A real three-slot weapon makes each critical dispatch observable.
            v['weapons']=[dict(name='IS.AC/5',section=5,critical=0)]
            streams['critical_slot']=[0]*60
            actions=[command('attackleg',args='VV')]
        else:
            s=r['outcome'];u=ba(8);units[0]=u
            if s.startswith('swarm-') or s=='leg-failure-hidden':
                if s.endswith('hidden') and not s.endswith('pendinghide'):u['hidden']=True
                if 'failure' in s:streams['pilot_rolls']=[2];c['values']['Piloting-BSuit']=0
                if s.endswith('pendinghide'):actions=[dict(op='pending-hide',unit='u',seconds=99)]
                actions.append(command('attackleg' if s.startswith('leg') else 'swarm',args='VV'));mode='ordinary'
            else:
                u['swarm_target']='v'
                if s=='stop-unresolved-target':actions=[cfg({'swarm_target':9999})]
                if s=='host-shutdown':actions.append(command('shutdown',unit='v'));mode='ordinary'
                elif s=='host-destroyed':actions.append(dict(op='diagnose',kind='destroy-section',unit='v',options={'section':4}));streams['suit_ejection']=[100]
                else:
                    if 'fail' in s:streams['pilot_rolls']=[2];c['values']['Piloting-BSuit']=0
                    actions.append(probe('detach',intentional=s=='stop-intentional'))
        d=doc(actions,characters=[c],units=units,streams=streams)
        out=a.cli(case,d,mode=mode,identity=dict(outline=n,line=line,values=r));result=out['results'][-1];state=out['state'];own=state['units']['u'];host=state['units']['v']
        if n==1:
            expected=r['result']
            if expected=='members1':a.eq('all-eight member count',result['members'],1)
            elif expected=='Point-point':a.eq('Clan name',[result['name'],result['lower_name']],['Point','point'])
            elif expected=='Squad-squad':a.eq('IS name',[result['name'],result['lower_name']],['Squad','squad'])
            elif expected.startswith('mirror'):a.eq('mirror coordinates/elevation',[result[k] for k in ('x','y','z','elev')],[3,4,3,2])
            else:
                e={'swarmed0-mounted0-count0-firstnone':[False,False,0,None],'swarmed1-mounted1-count2-firstenemy':[True,True,2,10],'swarmed0-mounted1-count1':[False,True,1,10],'ignored':[False,False,0,None]}[expected]
                a.eq('ordered swarm queries',[result[k] for k in ('swarmed','mounted','count','first')],e)
        elif n in (2,4):
            a.eq('source modifier',out['results'][0],int(r['modifier']))
            if len(actions)>1:a.eq('ordinary caller modifier',result.get('modifier'),int(r['modifier']))
        elif n==3:
            expected=r['result'];errors={'range-error':'out of range','argument-error':'Invalid arguments','mount-tech-error':'mounting','jettison-error':'jettisons','crowded-error':'no room','weapon-busy-error':'weapons recycling','section-busy-error':'Suit 8','legless-error':'no legs','friendly-error':'friendly','unsupported-nontermination':'nontermination'}
            if expected in errors:a.error(result,errors[expected])
            elif expected=='default-cleared-minus1':a.eq('invalid default cleared',own['target'],-1)
            else:a.true('action attempted',result.get('ok'))
        elif n==5:
            a.eq('critical branch',result.get('effect'),r['effect']);a.eq('recycle30',[s['recycle'] for s in own['sections']],[30]*8)
            if r['roll']=='7':a.eq('real leg armor damage',host['sections'][5]['armor'],96)
            elif r['roll']=='12':a.eq('leg gone',host['sections'][5]['internal'],0);a.true('mobility fall',host['fallen'])
            else:a.true('actual slot damaged',any(s['firemode']&1 for s in host['sections'][5]['slots']))
            draws=[x['name'] for x in out['draws']];a.true('leg selection before pilot roll',draws.index('leg_location')<draws.index('pilot_rolls')<draws.index('leg_critical'))
        else:
            s=r['outcome']
            if s=='stop-unresolved-target':a.eq('unresolved ID unchanged',own['relationships']['swarm_target'],9999)
            elif s=='host-shutdown':a.eq('host shutdown retains riders',own['relationships']['swarm_target'],'v')
            else:
                attached=s in ('swarm-success-hidden','swarm-attempt-unhidden-pendinghide')
                a.eq('attachment',own['relationships']['swarm_target'],'v' if attached else None)
                recycle=45 if 'fail-draw7' in s else 30 if s in ('leg-failure-hidden','stop-PSR4-success') else 20
                a.eq('surviving member recycle',[sec['recycle'] for sec in own['sections'] if sec['internal']],[recycle]*sum(bool(sec['internal']) for sec in own['sections']))
                if s=='swarm-success-hidden':a.eq('facing/speeds',[own['facing'],own['speed'],own['desired_speed']],[270,0,0]);a.true('both flags',own['status2']&0x200000 and host['status2']&0x100000)
                if s=='leg-failure-hidden':a.true('hidden retained',own['crit_status']&8)
                if s.endswith('pendinghide'):a.eq('pending hide retained',len(events(state,'HIDE')),1)
                if s=='host-destroyed':a.eq('no detachment PSR',[x for x in out['draws'] if x['name']=='pilot_rolls'],[])
                if 'fail-draw7' in s:a.eq('section7 actual damage',own['sections'][7]['armor'],89)
    return a.save()

def run_hiding():
    a=Audit('hiding')
    for case,n,r,line in rows('hiding'):
        c=character(wizard=False);u=ba();units=[u];actions=[];terrain='ROUGH';streams={'damage_entry':[7]*100};config={}
        if n==1:
            u['class']=r['class'];u['specials2']=0x40000 if yes(r['camo']) else 0
            actions=[command('hide'),advance(int(r['time'])-1),inspect(),advance(1),inspect()]
        elif n==2:
            s=r['condition']
            if s.startswith('MW'):u['class']='MW'
            if s=='MW-speed-MP1':u['speed']=10.75
            if s=='MW-speed-over-MP1':u['speed']=10.751
            if 'building' in s:terrain='BUILDING'
            if s=='VTOL-airborne-camo':u['class']='VTOL';u['at'][2]=1;u['specials2']=0x40000
            if 'swarmtarget' in s:actions.append(cfg({'swarm_target':int(s[-1])}))
            if s=='pending-hide':actions.append(command('hide'))
            if s.startswith('enemy-'):
                v=unit('v',20);units.append(v)
                if 'clairvoyant' in s:v['clairvoyant']=True
                if 'shutdown' in s:v['started']=False
            actions.append(command('hide'))
            if s.startswith('enemy-') or s=='elevation1-at-callback':
                if s.startswith('elevation'):actions.append(dict(op='place',unit='u',at=[3,3,1]))
                actions.append(advance(1))
            if s=='ordinary-movement-crosses-hex':actions.extend([command('speed',args='walk'),advance(20)]);config['periodic_updates']=True
            if s=='ordinary-damage-after-hidden':actions.extend([advance(61),dict(op='diagnose',kind='damage',unit='u',options={'amount':1,'section':0})])
        else:
            capable=n==4 or yes(r['capable']);count=1 if n==4 else int(r['pending']);members_count=4 if n==4 else int(r['members']);u=ba(members_count);units=[u];u['infantry_specials']=0x200 if capable else 0
            loc=7 if n==4 and r['section']=='destroyed-section7' else 0
            u['sections'][loc]['slots']=[dict(index=4+i,weapon='PC.SMG',firemode=0x20000|2|4|8) for i in range(count)]
            actions=[command('jettison')]
            if n==4:actions.extend([command('fire',args='0 UU'),command('jettison')])
        d=doc(actions,characters=[c],units=units,streams=streams);d['map']['default']=[terrain,0];d['config'].update(config)
        if config:d['random']={'seed':8}
        out=a.cli(case,d,mode='ordinary' if not(n==2 and r['condition']=='ordinary-damage-after-hidden') else 'diagnostic',identity=dict(outline=n,line=line,values=r));state=out['state'];own=state['units']['u'];result=out['results'][0]
        if n==1:
            a.true('hide scheduled',result.get('ok'));a.eq('not hidden before deadline',bool(out['results'][2]['units']['u']['crit_status']&8),False);a.true('hidden at deadline',own['crit_status']&8);a.eq('completed event',events(state,'HIDE'),[])
        elif n==2:
            expected=r['result'];errors={'speed-error':'complete stop','terrain-error':"isn't going to work",'swarm-error':'Not while','landed-error':'landed','already-hiding-error':'already'}
            actual=next((x for x in reversed(out['results']) if isinstance(x,dict) and 'ok' in x),{})
            if expected in errors:a.error(actual,errors[expected])
            elif expected in ('scheduled','ignored-enemy'):a.eq('pending hide',len(events(state,'HIDE')),1)
            else:a.eq('no pending hide',len(events(state,'HIDE')),0);a.eq('not hidden',bool(own['crit_status']&8),False)
        else:
            if n==3 and not yes(r['capable']):a.error(result,'no backpack')
            else:
                a.eq('slot count',result.get('count'),count)
                for i in range(count):a.eq('jettison preserves unrelated bits',own['sections'][loc]['slots'][4+i]['firemode'],0x20000|0x40000|1|8)
                if n==4:a.eq('repeat count',out['results'][2].get('count'),0);a.eq('fire unavailable',out['results'][1].get('accepted'),False)
    return a.save()
