"""Connection and own-unit feature examples exercised through JSON CLI."""
from hud_displays_common import *


def sessions():
    for name,n,row,meta in examples('session'):
        doc=document();case=Case(name,doc,meta)
        if n in (1,2):
            initial=row.get('initial','test');request=row['request'];request='' if request=='no-argument' else request
            if initial!='unset':doc['actions'].append(hud('key='+initial))
            index=len(doc['actions']);doc['actions'].append(hud(request))
            key=row.get('key',initial);key='' if key=='unset' else key
            if row['class']=='unframed':case.expect(f'results.{index}.wire',row['payload']+'\r\n')
            else:record(case,index,row['class'],row.get('type','E'),row['payload'],key)
            doc['actions'].append(hud('gs'));after=index+1
            case.expect(f'results.{after}.ok',bool(key)).expect(f'results.{after}.wire',f'#HUD:{key or "???"}:','contains')
        elif n==3:
            state=row['state'];u=doc['units'][0]
            if state=='no-unit':doc['sessions'][0]=dict(name='pilot')
            elif state=='shutdown':u['started']=False
            elif state=='destroyed':u['destroyed']=True
            elif state=='unconscious':u['conscious']=False
            elif state=='blinded':u['blinded']=True
            doc['actions']=[hud('key=test'),hud(row['request'])]
            expected=row['result']
            if expected.endswith('-list'):
                case.expect('results.1.ok',True).expect('results.1.records.-1.type','D').expect('results.1.records.-1.payload','Done')
            elif expected=='general-status':case.expect('results.1.records.0.class','GS').expect('results.1.ok',True)
            else:record(case,1,row['request'].upper(),'E',expected)
        else:
            # A itself lives inside B and carries C; hardcode/zombie control eligibility.
            placement=row['placement']
            doc['units']=[dict(name='u',id=10,contact_id='AA',personnel=dict(location=20,hardcode=placement=='all')),
                dict(name='B',id=20,contact_id='BB',personnel=dict(zombie=placement=='no-self-zombie-location',hardcode=placement!='none')),
                dict(name='C',id=30,contact_id='CC',personnel=dict(location=10,hardcode=placement!='none'))]
            doc['sessions']=[dict(name='pilot',player=10),dict(name='second',player=10)]
            doc['actions']=[hud('key=test'),hud('key=other','second'),hud('gs'),hud('key=new'),hud('gs','second')]
            if row['selected']=='no-unit-error':case.expect('results.2.ok',False).expect('results.2.records.0.payload','Not in a BattleTech unit')
            else:case.expect('results.2.records.0.payload|0',row['selected']*2)
            case.expect('results.4.wire','#HUD:other:','contains').expect('results.3.wire','#HUD:new:KEY:R# Key set\r\n')
        yield case


def state():
    for name,n,row,meta in examples('hud_state'):
        doc=document(actions=[hud('key=test')]);u=doc['units'][0];case=Case(name,doc,meta)
        if n==1:
            u.update(speed=float(row['speed']),desired_speed=float(row['desired']),plus_heat=float(row['plus']),minus_heat=float(row['minus']),vertical_speed=float(row['vertical']))
            doc['actions'].append(hud('gs'))
            for index,key in [(6,'speed_text'),(7,'desired_text'),(8,'plus_text'),(9,'minus_text'),(11,'vertical_text'),(12,'vertical_text')]:case.expect(f'results.1.records.0.payload|{index}',row[key])
            case.expect('results.1.records.0.payload',r'^(?:[^,]*,){19}-$','regex')
        elif n==2:
            u.update(formed(row['form']));u['turret_facing']=int(row['offset']);u['core']=dict(going_x=4,going_y=5)
            # Authoritative mech.h status word, including STARTED=8.
            u['status']=8 | (4 if row['torso']=='left' else 2 if row['torso']=='right' else 0) | (64 if row['jump']!='none' else 0)
            doc['actions'].append(hud('gs'));case.expect('results.1.records.0.payload|15',row['field'])
            for index,value in zip((17,18),row['destination'].split(',')):case.expect(f'results.1.records.0.payload|{index}',value)
        elif n==3:
            u['sections']=[dict(index=0,armor_orig=int(row['of']),rear_orig=int(row['orr']),internal_orig=int(row['oi']),armor=int(row['cf']),rear=int(row['cr']),internal=int(row['ci']))]
            doc['actions'] += [hud('oas'),hud('as')]
            for index,key in [(1,'original'),(2,'current')]:
                if row[key]=='omitted':case.expect(f'results.{index}.wire','LA,','excludes')
                else:case.expect(f'results.{index}.records.0.payload','LA,'+row[key])
        elif n==4:
            if row['light']=='no-map':doc['actions'].append(action('map_diagnose',unit='u',kind='membership_remove'))
            else:doc['map'].update(light=int(row['light']),mapvis=30,gravity=100,temperature=25,flags=32 if row['flags']=='dark' else 32|4|16 if row['flags']!='none' else 0)
            start=len(doc['actions']);doc['actions'] += [hud('con'),hud('co')]
            for index,cls in [(start,'CON'),(start+1,'CO')]:record(case,index,cls,'R',row['payload'])
        else:
            u.update(formed(row['form']));u['core']=dict(template_ref='QA-DESIGN',max_speed=60,real_num_sinks=17,fuel_orig=123)
            u['display']=dict(template_name='QA Design')
            doc['actions'].append(hud('sgi'));case.expect('results.1.records.0.payload|0',row['code']).expect('results.1.records.0.payload|1','QA-DESIGN').expect('results.1.records.0.payload|2','QA Design').expect('results.1.records.0.payload|8','17')
        yield case
