"""Independent character/XP/skill examples expanded from approved rows."""
from qa.pilots.common import *

def run_character():
    a=Audit('character')
    for case,n,r,line in rows('character'):
        actions=[];chars=[character(values={})];expected=[]
        if n==1:
            actions=[ch('set',name=r['name'],amount=int(r['input'])),ch('get',name=r['code']),dg()]
        elif n==2:
            s=r['contents'];mask=int(r['mask']);categories={'health':'2,3','attrs':'5,5,5,5,5','advs':'Lives:1/','skills':'Runni:2/'}
            if s=='absent':categories={}
            elif s.startswith('malformed-health'):categories['health']='bad'
            elif s.startswith('malformed-attributes'):categories['attrs']='bad';categories['skills']='Runni:4/'
            elif s.startswith('duplicate-'):categories['skills']=s.removeprefix('duplicate-')
            elif s.startswith('Running:'):categories['skills']=s
            chars=[character(values={},categories=categories)];actions=[dg(mask=mask)]
        elif n==3:
            mask=2 if r['category']=='skills' else 8
            # Raw array setup via the diagnostic: every other requested value starts zero.
            values={};xp={};last={};s=r['state']
            if s.startswith('Running'):
                v,x,t=map(int,re.fullmatch(r'Running(\d+)-xp(\d+)-last(\d+)',s).groups());values={'Running':v};xp={'Running':x};last={'Running':t}
            elif s.startswith('Lives'):values={'Lives':1,'Toughness':1,'Running':2}
            elif s.startswith('Technician'):values={'Technician-Battlesuit':3}
            chars=[character(values={},categories={'health':'0,0','attrs':'1,1,1,1,1','skills':'','advs':''})]
            actions=[dg('store',mask=mask,values=values,xp=xp,last_use=last),ch('save')]
        elif n==4:
            chars=[character(values={},categories={'skills':f"ShotsHit:{r['old']}/Lives:{r['lives']}/"})]
            actions=[dg('store',mask=2,values={'ShotsHit':int(r['new'])})]
        elif n==5:
            chars=[character(values={**dict.fromkeys(ATTRS,5),'Running':1})]
            actions=[ch('target',name='Running'),dg('store',mask=4,values={'Build':6})]
            op=r['operation']
            if op=='public-set-value':actions.append(ch('set',name='Build',amount=6))
            else:actions.append(dg('store',mask={'store-attributes-only':4,'store-health-only':1,'store-skills':2,'store-advantages':8}[op]))
            actions.append(ch('target',name='Running'))
        elif n==6:
            s=r['request'];authority=r['authority'];chars=[character(wizard=authority=='Wiz',wiz_r=authority=='WizR',values={}),character(102,values={})]
            if s.startswith('status'):
                if s=='status-Toughness2':chars[0]['values']={'Toughness':2}
                if s=='status-Contact7':chars[0]['values']={'Contact':7}
                if s=='status-Exceptional17':chars[0]['values']={'Exceptional_Attribute':17}
                if s=='status-rawRunning0-bonus1':chars[0]['categories']={'health':'0,0','attrs':'5,5,5,5,5','advs':'Lives:1/','skills':'Runni:0,16777216,0/'}
                actions=[ch('status',**({'target':'#102'} if s=='status-other' else {}))]
            elif s.startswith('clear'):actions=[ch('clear',**({'target':'#102'} if s=='clear-other' else {}))]
            elif s.startswith('get'):actions=[ch('get',name='Unknown' if s=='get-unknown-value' else 'Build',**({'target':'missing'} if s=='get-unknown-player' else {}))]
            elif s.startswith('set'):actions=[ch('set',name='Build',flag=1,amount=4)]
            elif s.startswith('list'):actions=[ch('list',name=s.split('-')[1],player=101)]
        else:actions=[ch('duration',amount=int(r['seconds']))]
        out=a.cli(case,doc(actions,characters=chars),identity=dict(outline=n,line=line,values=r));v=out['results'][-1]
        if n==1:a.eq('canonical raw byte',out['results'][1],int(r['value']));a.eq('indexed raw byte',v['values'][int(r['code'])],int(r['value']))
        elif n==2:
            arr=v['values'];s=r['state']
            if s in ('attributes1-lives1-health0-skills0','all-defaults-persisted'):
                expected=[int(t['type']==3) for t in TABLE];expected[5]=1;a.eq('reset complete array',arr,expected)
                a.eq('persisted categories',v['categories'],{'health':'0,0','attrs':'1,1,1,1,1','advs':'Lives:1/','skills':''})
            elif s=='all-zero':a.eq('zero request array',arr,[0]*119)
            elif s=='build0-bruise2-lethal3':a.eq('health-only read',[arr[36],arr[6],arr[7]],[0,2,3])
            elif s.startswith('Running3'):a.eq('ordered duplicate fields',[arr[93],v['xp'][93],v['last_use'][93]],[3,9,40])
            else:a.eq('earlier writes preserved',[arr[93],arr[46]],[2,3 if s.endswith('Blade3') else 0])
        elif n==3:
            text=r['text'] if r['text']!='empty' else '';key='skills' if mask==2 else 'advs'
            a.eq('exact source serialization',out['state']['characters']['101']['categories'][key],text)
            root=OUT/'character'/case/'storage'
            reload=a.cli(case+'-reload',doc([dg(mask=mask)],characters=[]),storage=root,fresh=False,identity=dict(outline=n,line=line,values=r));v=reload['results'][0]
            # Independent source parser for these simple serialized rows.
            values=[0]*119;ex=[0]*119;times=[0]*119;aliases={}
            for t in TABLE:aliases.setdefault(t['short'].lower(),t['code'])
            for entry in text.strip('/').split('/') if text else []:
                name,fields=entry.split(':');idx=aliases[name.lower()];bits=list(map(int,fields.split(',')));values[idx]=bits[0]
                if len(bits)>1:ex[idx]=bits[1];times[idx]=bits[2]
            a.eq('fresh values',v['values'],values);a.eq('fresh packed XP',v['xp'],ex);a.eq('fresh last use',v['last_use'],times)
        elif n==4:a.eq('byte coupling',v['values'][5],int(r['result']))
        elif n==5:a.eq('cached target',out['results'][0],7);a.eq('next target',v,int(r['target']))
        elif n==6:
            result=r['result']
            errors={'authority-error':'authority','power-error':'real power','target-required':'Who do you','invalid-target':'INVALID TARGET','permission-denied':'PERMISSION DENIED','invalid-value':'INVALID VALUE','only-skills-can-have-flag':'ONLY SKILLS'}
            if result in errors:a.error(v,errors[result])
            elif result=='status':a.eq('status name',v['name'],'Bob' if r['request']=='status-other' else 'Alice')
            elif result=='all-source-advantages':a.eq('complete advantage list',v,[t['name'] for t in TABLE if t['type']==2])
            elif result=='all-five':a.eq('all attributes',v,ATTRS)
            elif result=='empty':a.eq('no learned skills',v,[])
            elif result=='advantage-name-shown':a.eq('raw-two status',v['advantages'],['Toughness'])
            elif result=='Contact-value7':a.eq('value advantage',v['advantages'],['Contact: 7'])
            elif result=='Exceptional-Build-and-Charisma':a.eq('mask advantage',v['advantages'],['Exceptional Attribute: Build','Exceptional Attribute: Charisma'])
            else:a.eq('raw-zero skill omitted',v['skills'],['None'])
        else:a.eq('duration',v,r['text'])
    return a.save()

def run_skills():
    a=Audit('skills')
    for case,n,r,line in rows('skills'):
        vals=dict(zip(ATTRS,[5,4,3,2,1]));chars=[character(values=vals)];actions=[];dice=[]
        if n==1:
            if r['skill'] in INDEX and TABLE[INDEX[r['skill']]]['type']==1:
                chars[0]['values'][r['skill']]=2
                actions.append(dg('store',mask=2,xp={r['skill']:XP_MAX}))
            actions.append(ch('target',name=r['skill'],use_xp=yes(r['xp']),modifier=int(r['modifier'])))
        elif n==2:
            dice=nums(r['dice']);kind=r['kind'];actions=[ch('dice',name=kind if not kind.startswith('d6-') else 'd6',count=int(kind[3:].replace('minus','-')) if kind.startswith('d6-') else 2)]
        elif n==3:
            lv=int(r['level']);name='Unknown' if lv==-1 else 'Running';chars[0]['values']={**dict.fromkeys(ATTRS,4 if lv==0 else 5),'Running':max(0,lv)}
            base=18-2*(4 if lv==0 else 5)-max(lv,0);mod=int(r['target'])-base
            dice=nums(r['dice'])*2;actions=[ch('skill',name=name,modifier=mod),ch('margin',name=name,modifier=mod)]
        elif n==4:
            chars=[character(values={**dict.fromkeys(ATTRS,5),'Running':1}),character(102,values={**dict.fromkeys(ATTRS,5),'Running':1})]
            dice=[3,4+int(r['first']),3,4+int(r['second'])];actions=[ch('opposed',name='Running',other=102)]
        elif n==5:
            chars[0]['values']['Build']=max(0,int(r['value']));actions=[ch('attribute',name='Unknown' if r['value']=='-1' else 'Build')];dice=[] if r['value']=='-1' else [2,5]
        else:chars[0]['values']['Toughness']=int(r['value']);actions=[ch('advantage',name='Toughness')]
        out=a.cli(case,doc(actions,characters=chars,streams={'character_d6':dice}),identity=dict(outline=n,line=line,values=r));v=out['results'][-1]
        if n==1:a.eq('source BTH',v,int(r['target']))
        elif n==2:a.eq('dice result',v,int(r['result']))
        elif n==3:a.eq('success',out['results'][0]['success'],yes(r['success']));a.eq('target',out['results'][0]['target'],int(r['target']));a.eq('margin',v,int(r['margin']))
        elif n==4:a.eq('winner',v,{'first':101,'second':102,'tie':0}[r['winner']])
        elif n==5:a.eq('attribute result',v,dict(target=int(r['target']),success=-1 if r['success']=='-1' else yes(r['success'])))
        else:a.eq('exact-one advantage',v,yes(r['present']))
        a.eq('Number values in order',[d['value'] for d in out['draws']],dice);a.eq('Roll histogram unchanged',out['state']['random']['total_rolls'],0)
    return a.save()

def run_experience():
    a=Audit('experience');skill='Gunnery-Battlemech';idx=INDEX[skill]
    for case,n,r,line in rows('experience'):
        chars=[character()];actions=[]
        if n==1:actions=[dg('store',mask=2,xp={skill:int(r['raw'])}),dg('pack',mask=6,name=skill),ch('next',name=skill),dg()]
        elif n==2:
            bth=int(r['bth']);chars[0]['values'].update({**dict.fromkeys(ATTRS,0 if bth==18 else 5),skill:0 if bth==18 else 8-bth})
            actions=[ch('threshold',args=f"{skill} {r['threshold']}"),ch('next',name=skill),dg('store',mask=2,xp={skill:int(r['xp'])}),dg('pack',mask=6,name=skill),dg()]
        elif n==3:
            skill2=skill if r['kind']=='SK_XP' else 'Blade';chars[0]['connected']=r['kind']!='ordinary-disconnected'
            actions=[dg('store',mask=2,values={skill2:1},xp={skill2:1},last_use={skill2:100}),dict(op='clock',name='skip_seconds',seconds=int(r['now'])),ch('gain',name=skill2,amount=1,override=yes(r['override'])),dg()]
        elif n==4:
            actions=[dg('store',mask=2,xp={skill:int(r['packed'])})]
            op=r['operation'];actions.append(ch('lower',promillage=int(op.split('-')[1])) if op.startswith('lower') else ch('gain',name=skill,amount=1,override=True));actions.append(dg())
        elif n==5:
            actions=[dg('store',mask=2,xp={skill:XP_MAX+3001})];op=r['operation']
            if op.startswith('get'):actions.append(ch('get',name=skill,flag=int(op[-1])))
            else:actions.extend([ch('set',name=skill,flag=int(op[8]),amount=int(re.search(r'(?:XP|BTH)(\d+)',op)[1])),dg()])
        else:
            s=r['request']
            if s.startswith('threshold'):
                args={'threshold-empty':'','threshold-Running-minus1':'Running -1','threshold-Build-5':'Build 5','threshold-Running-0':'Running 0'}[s];actions=[ch('threshold',args=args)]
            elif s.startswith('getthreshold'):actions=[ch('getthreshold',name='Unknown')]
            else:
                chars=[]
                amounts=[100,100,200] if s=='top-A100-B100-C200' else [100]*17 if s=='top-17-players' else [100,200,300]
                for i,x in enumerate(amounts):
                    chars.append(character(101+i,name=chr(65+i),wizard=s=='top-nonplayers-and-wizards' and i==1,is_player=not(s=='top-nonplayers-and-wizards' and i==2),values={},categories={'health':'0,0','attrs':'5,5,5,5,5','skills':f'GunBat:4,{x},0/','advs':'Lives:1/'}))
                actions=[ch('top',name=skill)]
        out=a.cli(case,doc(actions,characters=chars),identity=dict(outline=n,line=line,values=r));v=out['results'][-1]
        if n==1:a.eq('packed',v['xp'][idx],int(r['packed']));a.eq('bonus',v['xp'][idx]//XP_MAX,int(r['bonus']));a.eq('cumulative next',out['results'][2],int(r['next']))
        elif n==2:a.eq('bonus',v['xp'][idx]//XP_MAX,int(r['bonus']));a.eq('first cumulative threshold',out['results'][1],int(r['first']))
        elif n==3:a.eq('accepted',bool(out['results'][2]),yes(r['accepted']));a.eq('last use',v['last_use'][INDEX[skill2]],int(r['last']))
        elif n==4:a.eq('packed after change',v['xp'][idx],int(r['result']))
        elif n==5:
            result=r['result']
            if result.lstrip('-').isdigit():a.eq('getter',v,int(result))
            elif result=='rawLevel0':a.eq('raw level',v['values'][idx],0)
            else:
                raw,bonus=map(int,re.fullmatch(r'rawXP(\d+)-bonus(\d+)',result).groups());a.eq('raw and bonus',v['xp'][idx],bonus*XP_MAX+raw)
        else:
            s=r['result'];errors={'invalid-arguments':'Invalid arguments','negative-error':'Threshold needs','not-skill':"isn't any skill"}
            if s in errors:a.error(v,errors[s])
            elif s=='threshold0':a.eq('disabled threshold',v,0)
            elif s=='-1':a.eq('missing threshold',v,-1)
            elif s=='excluded':a.eq('eligible rows',[x['id'] for x in v['rows']],[101])
            elif s.startswith('order'):a.eq('tie order',[x['name'] for x in v['rows']],['C','B','A']);a.eq('percentages',[x['percent'] for x in v['rows']],[50,25,25]);a.eq('total',v['total'],400)
            else:a.eq('top16 count',len(v['rows']),16);a.eq('grand total',v['total'],1700);a.near('denominator all17',v['rows'][0]['percent'],100/17)
    return a.save()
