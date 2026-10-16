"""Health, equipment and armor expectations from btechstats.c/pcombat.c."""
from qa.pilots.common import *

def run_health():
    a=Audit('health')
    for case,n,r,line in rows('health'):
        c=character(wizard=False);u=unit(character=101);actions=[];dice=[6,6]*6
        if n==1:
            c['values'].update(Bruise=int(r['bruise']),Pain_Resistance=int(r['pain']));actions=[dict(op='personnel',kind='consciousness_target',unit='u')]
        elif n==2:
            c['values'].update(Bruise=int(r['bruise']),Lethal=int(r['lethal']));actions=[dict(op='personnel',kind=r['kind'],unit='u',amount=int(r['damage']))]
        elif n==3:
            s=r['condition']
            if s=='negative-unit-ID':actions=[dict(op='pilot_diagnose',kind='head',unit='u',source_id=-1,amount=1)]
            elif s.startswith('nonIC'):
                u['in_character']=False;u['pilot_hits']=6 if s.endswith('hits6') else 5;actions=[dict(op='personnel',kind='head',unit='u',amount=0)]
            elif s.startswith('fix'):
                c['values'].update(Build=int(re.search(r'build(\d+)',s)[1]),Bruise=12,Lethal=8);actions=[dict(op='personnel',kind='fix_health',unit='u')]
            else:c['values']['Build']=0;actions=[dict(op='personnel',kind='lethal',unit='u',amount=1)]
        else:
            dice=[1,1];actions=[dict(op='personnel',kind='head',unit='u',amount=1),inspect(),advance(10)]
            s=r['action']
            if s=='nonfatal-injury-at10':actions.append(dict(op='personnel',kind='head',unit='u',amount=1))
            elif s=='explicit-prolong20-at10':actions.append(dict(op='diagnose',kind='ProlongUncon',unit='u',args=[20]))
            else:actions.append(advance(20));dice += [1,1] if s=='failed-recovery-at30' else [6,6]
        out=a.cli(case,doc(actions,characters=[c],units=[u],streams={'character_d6':dice}),identity=dict(outline=n,line=line,values=r));v=out['results'][-1];state=out['state']['units']['u']
        if n==1:a.eq('IC target',v,int(r['target']))
        elif n==2:
            a.eq('durable health',health(out),[int(r['outbruise']),int(r['outlethal'])]);a.eq('hit write order',state['pilot_hits'],int(r['hits']));a.eq('fatal',state['destroyed'],yes(r['fatal']))
            if yes(r['fatal']):a.eq('local occupant alive',out['state']['characters']['101']['alive'],False)
        elif n==3:
            s=r['condition']
            if s=='negative-unit-ID':a.eq('unchanged health',health(out),[0,0]);a.eq('unchanged hits',state['pilot_hits'],0);a.eq('no dice',out['draws'],[])
            elif s.endswith('hits6'):a.true('destroyed',state['destroyed']);a.eq('pilot cleared',state['pilot'],None);a.eq('stopped',[state['speed'],state['desired_speed']],[0,0])
            elif s.endswith('hits5'):a.true('capped target10',any('10' in msg and 'Roll' in msg for msg in state['messages']))
            elif s.startswith('fix'):a.eq('synced hits',state['pilot_hits'],2)
            else:a.eq('BLD zero fatal health',health(out),[10,9]);a.true('fatal',state['destroyed'])
        else:
            due=[] if r['due']=='none' else [int(r['due'])];a.eq('recovery deadline',[e['deadline'] for e in events(out['state'],'RECOVERY')],due)
            a.eq('initial deadline',[e['deadline'] for e in events(out['results'][1],'RECOVERY')],[30]);a.eq('exact consciousness dice',[d['value'] for d in out['draws']],dice)
    return a.save()

def template_load():return dict(op='template',unit='u',kind='load',reference='MechWarrior')

def run_initialization():
    a=Audit('initialization')
    for case,n,r,line in rows('initialization'):
        c=character(values={**dict.fromkeys(ATTRS,5),'Reflexes':4,'Running':3,'Bruise':10,'Lethal':10});u=unit(cls='MW',character=101)
        equipment='';state='fresh'
        if n==2:equipment=r['equipment'];state=r['state']
        if n==3:
            c['values'].update(Build=int(r['build']),Reflexes=int(r['reflexes']),Running=int(r['running']),Bruise=0,Lethal=0);equipment='0000 PC.SMG -'
        equipment=' '.join({'valid-right':'PC.SMG','valid-left':'PC.LaserRifle','invalid-right':'NotARegisteredPart','invalid-left':'NotARegisteredPart'}.get(x,x) for x in equipment.split())
        c['pcequip']='' if equipment=='empty' else equipment
        # Genuine loader, then attach the persisted actor after loader pilot reset.
        actions=[dict(op='template',unit='u',kind='load',reference='MechWarrior'),dict(op='personnel',kind='attach',unit='u',player=101)]
        if state=='nonMW':actions=[dict(op='template',unit='u',kind='load',reference='WVR-6R'),dict(op='personnel',kind='attach',unit='u',player=101)]
        if state=='already-initialized':actions.append(dict(op='personnel',kind='initialize',unit='u'))
        actions.extend([inspect(),dict(op='personnel',kind='initialize',unit='u'),inspect()])
        d=doc(actions,characters=[c],units=[u]);d['construction']={'catalog':True}
        out=a.cli(case,d,identity=dict(outline=n,line=line,values=r));before=out['results'][-3]['units']['u'];v=out['state']['units']['u'];sections=v['sections'];res=out['results'][-2]
        if n==1:
            s=sections[LOC[r['section']]];a.eq('section proportions',[s['internal'],s['internal_orig'],s['armor_orig']],[int(r['internal']),int(r['internal']),0])
        elif n==3:
            a.near('float32 speed',v['max_speed'],float(r['speed']));a.eq('source SMG full ammo',sections[1]['slots'][1]['data'],50)
        elif state!='fresh':a.eq('initializer no-op',sections,before['sections']);a.eq('speed unchanged',v['max_speed'],before['max_speed'])
        else:
            expected=r['result']
            if 'error' in expected:
                a.error(res,'Invalid PC weapon' if 'left-error' in expected or 'right-error' in expected else 'Invalid armor')
                a.true('initialized flag set',v['crit_status'] & 0x00800000)
                if expected=='left-error-before-right':a.eq('right not installed',sections[1]['slots'][0]['type'],before['sections'][1]['slots'][0]['type'])
                if expected=='left-installed-before-right-error':a.true('left installed',sections[0]['slots'][0]['type']>0)
            elif expected=='current-HEAD1-CT2-RA3-RL4':a.eq('armor codes',[sections[x]['armor'] for x in (7,4,1,6)],[1,2,3,4])
            elif expected=='right-ammo3-left-ammo4':a.eq('ordered ammo',[sections[1]['slots'][1]['data'],sections[0]['slots'][1]['data']],[3,4])
            else:a.eq('no armor equipment',[s['armor'] for s in sections],[0]*8)
        a.eq('no original armor codes',[s['armor_orig'] for s in sections],[0]*8 if state!='nonMW' else [s['armor_orig'] for s in before['sections']])
    return a.save()

def run_personal():
    a=Audit('personal')
    for case,n,r,line in rows('personal'):
        u=unit(cls='MW');actions=[];streams={};weapon=None;loc=4;amount=100;id=-1
        if n==1:
            u['class']=r['target'];weapon={'PC':'PC.SMG','normal':'IS.MediumLaser','none':None}[r['weapon']];kind=r['direction'].replace('-','_');amount=int(r['damage']);stream='personal_to_normal' if kind=='to_normal' else 'personal_conversion';streams={stream:nums(r['draws'])}
        elif n==2:kind='location';loc=LOC[r['location']]
        else:
            kind='armor';streams={'personal_variation':[100],'personal_weak_point':[2],'personal_half':[1],'personal_block':[1]}
            armor=6
            if n==3:
                loc=LOC[r['location']];armor=int(r['code']);weapon='PC.Sword' if (loc,armor) in ((1,1),(6,1),(4,1),(4,4)) else 'PC.LaserRifle'
            elif n==4:
                amount=int(r['damage']);s=r['condition']
                if s in ('double','bypass'):streams['personal_weak_point']=[1];streams['personal_double_or_bypass']=[1 if s=='double' else 2]
                if s=='half':streams['personal_half']=[2]
                if s=='id-minus2':id=-2
                if s=='unknown-armor9':armor=9
                if s=='armor0':armor=0
                if s=='nonMW':u['class']='MECH'
            else:
                loc=7 if r['armor']=='Helmet' else 4;armor=1;weapon={'PC_SHAR':'PC.Sword','PC_HEAT':'PC.LaserRifle','PC_IMPA':'PC.SMG','normal':'IS.MediumLaser'}[r['weapon']]
            u['sections'][loc]['armor']=armor
        action=dict(op='personal',kind=kind,unit='u',location=loc,amount=amount,id=id)
        if weapon:action['weapon']=weapon
        out=a.cli(case,doc([action],characters=[],units=[u],streams=streams),identity=dict(outline=n,line=line,values=r));v=out['results'][0]
        if n==2:a.eq('location projection',v,LOC[r['result']])
        elif n==3:a.eq('source armor profile',v,int(r['damage']))
        elif r['result']=='undefined-domain':a.error(v,'division by zero')
        else:a.eq('personal damage',v,int(r['result']))
        drawn=[d['name'] for d in out['draws']]
        if n==1:a.eq('conversion draws',[d['value'] for d in out['draws']],nums(r['draws']))
        if n==4:
            names={'variation':'personal_variation','weak':'personal_weak_point','half':'personal_half','double':'personal_double_or_bypass','bypass':'personal_double_or_bypass','block':'personal_block'}
            a.eq('draw order',drawn,[names[x] for x in r['calls'].split('-')])
        if n==5:a.eq('block call count',drawn.count('personal_block'),int(r['draws']))
        if n>=3:a.eq('armor codes do not deplete',out['state']['units']['u']['sections'][loc]['armor'],armor)
    return a.save()
