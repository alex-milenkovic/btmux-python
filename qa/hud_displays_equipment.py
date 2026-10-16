"""Slot, catalog and query examples with independently declared raw C flags."""
from hud_displays_common import *


def slot_state(state,ticks=0):
    values=dict(index=0,weapon='IS.MediumLaser',data=int(ticks))
    values['firemode']=(4 if 'broken'in state else 0)|(2 if 'disabled'in state else 0)|(1 if state in ('destroyed','nonfunctional','destroyed-weapon') else 0)
    if state=='jettisoned':values['firemode']|=0x40000
    if state=='rocket-fired':values['firemode']|=0x100000
    for label,code in [('ammojammed',6),('temporarily-destroyed',5),('jammed',1),('shorted',2),('dud',3),('empty',4),('temporary-failure',1)]:
        if label in state:values['temp_failure']=code;break
    return values


def equipment():
    for name,n,row,meta in examples('hud_equipment'):
        doc=document(actions=[hud('key=test')]);u=doc['units'][0];case=Case(name,doc,meta)
        if n==1:
            u['sections']=[dict(index=0,slots=[slot_state(row['states'],row['ticks'])])]
            doc['actions'].append(hud('we'));case.expect('results.1.records.0.payload|4',row['status'])
        elif n==2:
            fire={'none':0,'RAC2-RAC4-RAC6-HOTLOAD-ULTRA':0x2000|0x4000|0x8000|0x40|0x400,'TC-OS-OSUSED':0x10|0x100|0x200,'AMS-enabled':0,'AMS-disabled':0}[row['fire']]
            ammo={'none':0,'SWARM1-ARTEMIS-INFERNO':0x100|2|0x40,'INARC_EXPLO-ATM_HE':0x200|0x200000}[row['ammo']]
            weapon='IS.Anti-MissileSystem' if row['fire'].startswith('AMS') else 'IS.MediumLaser'
            u['sections']=[dict(index=0,slots=[dict(index=0,weapon=weapon,firemode=fire,ammomode=ammo)])]
            if row['fire']=='AMS-enabled':u['status']=8|0x800
            doc['actions'].append(hud('we'));case.expect('results.1.records.0.payload|5',row['fire_text']).expect('results.1.records.0.payload|6',row['ammo_text'])
        elif n==3:
            sections={};mounts=row['mounts'].split(',')
            for index,item in enumerate(mounts):
                loc,pos=item.split(':');loc={'LARM':0,'RARM':1}[loc]
                sections.setdefault(loc,dict(index=loc,slots=[]))['slots'].append(dict(index=int(pos),weapon='IS.MediumLaser',firemode=32 if index==0 else 0,brand=1+index%2))
            u['sections']=list(reversed(list(sections.values())))
            doc['actions'] += [hud('we'),hud('wl')]
            case.expect('results.1.records',int(row['count'])+1,'length')
            for i,mount in enumerate(mounts):
                case.expect(f'results.1.records.{i}.payload|0',str(i)).expect(f'results.1.records.{i}.payload|2',str(1+i%2)).expect(f'results.1.records.{i}.payload|3',('LA' if mount.startswith('LARM') else 'RA')+('r' if i==0 else ''))
            case.expect('results.2.records.-1.payload','Done').expect('results.2.wire',r'(?m)^#HUD:test:WL:L# (?:[^,\r\n]*,){17}[^,\r\n]*\r$','regex')
            # Full catalog/source comparisons are provided by the supplemental catalog oracle.
        elif n==4:
            u.update(formed(row['form']));u['sections']=[dict(index=0,recycle=int(row['ticks']),armor=0 if row['state']=='destroyed' else 10,internal=0 if row['state']=='destroyed' else 10,config=2 if row['state']=='destroyed' else 0)]
            doc['actions'].append(hud('li'));case.expect('results.1.records',int(row['rows'])+1,'length')
            if row['status']!='absent':case.expect('results.1.records.0.payload|1',row['status'])
        else:
            u['sections']=[dict(index=2,slots=[dict(index=0,ammo='IS.AC/5',data=5),dict(index=1,ammo='IS.AC/5',data=7,ammomode=0 if row['modes']=='standard-standard' else 64)])]
            doc['actions'].append(hud('am'));case.expect('results.1.records',int(row['rows'])+1,'length')
            for i,(current,maximum) in enumerate(zip(row['current'].split(','),row['maximum'].split(','))):
                case.expect(f'results.1.records.{i}.payload|3',current).expect(f'results.1.records.{i}.payload|4',maximum)
        case.expect('results.1.records.-1.type','D')
        yield case


def queries():
    for name,n,row,meta in examples('queries'):
        doc=document();u=doc['units'][0];case=Case(name,doc,meta)
        query=dict(op='status_query',unit='u',section='LA')
        if n==1:
            u['sections']=[dict(index=0,armor=0 if row['destroyed']=='true' else 10,internal=0 if row['destroyed']=='true' else 10,config=(2 if row['destroyed']=='true' else 0)|(8 if row['flooded']=='true' else 0))]
            query['kind']='sectstatus';case.expect('results.0.text',row['text'])
        elif n==2:
            u['profile']='sparse';u['sections']=[dict(index=0,armor=7,armor_orig=20,internal=4,internal_orig=10,rear=2,rear_orig=5)]
            query.update(kind='armorstatus',section={'that-section':'LA','all-only-that-section':'all','missing-section':'nonsense'}[row['argument']])
            case.expect('results.0.text',row['text'].replace(',','|'))
        elif n==3:
            slot=slot_state(row['state'])
            if row['kind']=='ammo':slot.pop('weapon');slot['ammo']='IS.AC/5'
            if row['state']=='half-ton':slot['firemode']=128
            u['sections']=[dict(index=0,slots=[slot])];query.update(kind='critslot',slot=1,flag=row['field'])
            case.expect('results.0.text',row['text'])
        elif n==4:
            u.update(formed('AERO'));u['sections']=[dict(index=4,internal_orig=10,internal=10,slots=[dict(index=4,special='LIFE_SUPPORT')])]
            query.update(kind='critslot',section='Cockpit',slot=int(row['slot']),flag='NAME')
            if row['result']=='part-name':case.expect('results.0.ok',True).expect('results.0.text','Life','contains')
            else:case.expect('results.0.text',row['result'])
        else:
            u['sections']=[dict(index=0,slots=[slot_state(row['condition'])])]
            query.pop('section');query['kind']='weaponstatus'
            case.expect('results.0.text',r'^(?:[^|]*\|){7}'+row['status']+'$','regex')
        doc['actions']=[query];yield case
