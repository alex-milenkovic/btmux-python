"""QA procedures 8-9: local bay doors, queue boundaries and physical transfer."""
import re
from aerospace_support import *


def baydoc(actions=None,kind='MECH'):
    u=craft(kind,at=[10,9,0]);ship=craft('DS',name='ship',id=30,contact_id='DS',at=[10,10,0],aerospace=dict(landed=True,bays=['bay','bay2',-1,-1]),sections=[dict(index=5,slots=[dict(index=0,type=421)]),dict(index=4,slots=[dict(index=0,type=421)])])
    d=document(u,actions or [cmd('enterbay')],units=[u,ship],random=dict(streams={'sensor.random':[1]*200,'sensor.detect':[1]*200,'map_contact_id':list(range(26))*10,'fuel_check':[0]*100,'pilot_rolls':[12]*10}))
    d['maps'] += [dict(name='bay',id=2000,size=[10,10],bay=dict(onmap='ship')),dict(name='bay2',id=2001,size=[10,10],bay=dict(onmap='ship'))]
    return d


def bay_configuration():
    for name,row in feature_rows('bays',1):
        f=row['fixture'];d=baydoc();ship=d['units'][1];ship['aerospace']['bays']=[2000,2001,2002,2003] if 'old-four' in f else [-1]*4
        d['maps'] += [dict(name='bay3',id=2002,size=[10,10],bay=dict(onmap='ship')),dict(name='bay4',id=2003,size=[10,10],bay=dict(onmap='ship'))]
        args='bay bay2 bay3 bay4' if f=='four-valid-map-arguments' else '' if f.startswith('no-arguments') else 'bay' if f.startswith('one-valid') else 'bay bay2 bay3 bay4 bay' if f.startswith('five') else 'bay unknown' if f.startswith('valid-map-then') else '10'
        d['actions']=[cmd('createbays',args,unit='ship')];c=Case(name,d).result(ok=not(f.startswith(('five','valid-map-then','non-map'))))
        expected=[2000,2001,2002,2003] if f.startswith(('four','valid-map-then')) else [2000,-1,-1,-1] if f.startswith('one-valid') else [-1]*4
        c.expect('state.units.ship.aerospace.bays',expected)
        yield c
    for name,row in feature_rows('bays',2):
        f=row['fixture'];kind='AERO' if ';AERO' in f else 'VTOL' if ';VTOL' in f else 'MECH';d=baydoc(kind=kind);u,ship=d['units']
        if 'AFT' not in f:ship['sections']=ship['sections'][:1]
        door=ship['sections'][0]['slots'][0]
        if 'aerodoor' in f:door['type']=420
        if 'destroyed' in f:door['firemode']=1
        if 'disabled' in f:door['firemode']=2
        if 'two-doors' in f:ship['sections'][0]['slots'].append(dict(index=1,type=421))
        if f.startswith('DS'):
            x,y=map(int,re.search(r'DS(\d+),(\d+)',f).groups());ship['at']=[x,y,0];ship['facing']=int(re.search(r'facing(\d+)',f)[1]);u['at']=[*map(int,re.search(r'seer(\d+),(\d+)',f).groups()),0]
        d['actions']=[diag('doors',ship='ship',direction=0,reference=2000)]
        c=Case(name,d).result(number=0,direction=-1,adjacent=0,open=not('destroyed' in f or kind=='VTOL' and 'aerodoor' in f))
        # direction query takes a bay ordinal, unlike openness's map reference.
        c.checks=[x for x in c.checks if not x['path'].endswith('.direction')]
        if 'AFT' in f:d['actions'].append(diag('doors',ship='ship',direction=3,reference=2001));c.result(1,number=1,open=True)
        yield c


def entry_gates():
    for name,row in feature_rows('bays',3):
        f=row['fixture'];kind='VTOL' if f.startswith('VTOL') else 'DS' if f.startswith('DS;') else 'MECH';d=baydoc(kind=kind);u,ship=d['units'];index=0
        if 'two-landed' in f:
            other=deepcopy(ship);other.update(name='other',id=31,contact_id='D2');d['units'].append(other)
        if 'no-matching' in f:u['at']=[5,5,0]
        if 'two-arguments' in f:d['actions'][0]['args']='DS DS'
        if 'fuel0' in f:u['core']['fuel']=0;d['config']['nofusion_vtol_fuel']=True
        if 'jumping' in f:u['status']=0x8|0x40
        if 'standing' in f:u['fallen']=True;d['actions'].insert(0,cmd('stand'));index=1
        if 'OOD' in f:u['cocoon']=1
        if 'carrier-tech' in f and 'no-carrier' not in f:u['specials2']=0x80000;ship['sections'][0]['slots'][0]['type']=420
        if 'no-carrier' in f:ship['sections'][0]['slots'][0]['type']=420
        if 'door-destroyed' in f:ship['sections'][0]['slots'][0]['firemode']=1
        if 'relative-speed' in f:u['aerospace']['speed']=float(f.split('relative-speed')[1])
        if 'relative-vertical' in f:u['aerospace']['vertical_speed']=float(f.split('relative-vertical')[1])
        if 'different-Z' in f:u['at'][2]=1
        if 'legless' in f:u['sections']=[dict(index=5,internal=0,armor=0,config=2),dict(index=6,internal=0,armor=0,config=2)]
        if 'lock-denied' in f:d['maps'][1]['bay'].update(enter_lock='false',fail_message='QA locked door')
        if 'pending-other' in f:
            other=deepcopy(u);other.update(name='other',id=11,at=[10,11,0] if 'different-bay' in f else [10,9,0]);d['units'].append(other);d['actions'].insert(0,cmd('enterbay',unit='other'));index=1
        if 'explicit-target' in f:ship['aerospace']['landed']=False;d['actions'][0]['args']='DS'
        success=f in ('valid-MECH-adjacent','MECH;relative-speed10.75','MECH;relative-vertical10','different-bay-pending-other-unit','explicit-target-airborne;matching-door-and-elevation')
        c=Case(name,d).result(index,ok=success)
        pending=int('pending-other' in f)+int(success)
        c.expect('state.events',['ENTER_HANGAR',pending],'event_count').final(map='field')
        if f.startswith('lock-denied'):c.result(index,message='QA locked door')
        yield c


def callbacks():
    for name,row in feature_rows('bays',4):
        f=row['transition'];kind='MW' if f.startswith('MW') else 'MECH';d=baydoc(kind=kind);u,ship=d['units'];actions=d['actions'];destination='bay'
        if kind=='MW':
            u.update(in_character=True,character=501);d['characters']=[dict(id=501,name='Passenger',location=10)]
        if 'carried-unit' in f:
            car=craft('MECH',name='cargo',id=12,at=[10,9,0]);d['units'].append(car);u['aerospace']['carrying']=12
        if 'shuts-down' in f:actions.append(cmd('shutdown'))
        if 'unconscious' in f:actions.append(op('configure',unit='u',values=dict(conscious=False)))
        if 'speed' in f:
            speed=float(re.search(r'speed([\d.]+)',f)[1]);maximum=float(re.search(r'maximum([\d.]+)',f)[1]);actions.append(configure(speed=speed,max_speed=maximum))
        if 'door-destroyed' in f:actions.append(op('section',unit='ship',value=dict(index=5,slots=[dict(index=0,firemode=1)])))
        if 'lock-denied' in f:actions.append(op('bay_configure',map='bay',values=dict(enter_lock='false')))
        if 'other-bay' in f:actions.append(op('place',unit='u',at=[10,11,0]));destination='bay2'
        if 'moves-away' in f:actions.append(op('place',unit='u',at=[5,5,0]))
        if 'swarmer' in f:
            swarmer=craft('BSUIT',name='swarm',id=13,at=[10,9,0],swarm_target='u');swarmer['movement']='BIPED';d['units'].append(swarmer)
        actions += [advance(11),inspect(),advance(1)]
        no_transfer=f in ('unit-shuts-down','unit-unconscious','unit-speed12;maximum60','unit-moves-away')
        c=Case(name,d).result(ok=True).expect(f'results.{len(actions)-2}.units.u.map','field')
        if kind!='MW':c.final(map='field' if no_transfer else destination)
        if not no_transfer and kind!='MW':c.final(at=[5,5,0]).expect('state.units.u.personnel.location',2001 if destination=='bay2' else 2000)
        if 'carried-unit' in f:c.expect('state.units.cargo.map','bay').expect('state.units.cargo.at',[5,5,0])
        if 'swarmer' in f:c.expect('state.units.swarm.relationships.swarm_target',None)
        if kind=='MW':c.expect('state.events',['NUKEMECH',1],'event_count').expect('state.characters.501.location',2000).expect('state.personnel.contents.10',[]).expect('state.events',dict(kind='NUKEMECH',deadline=22),'has_record')
        yield c


def exits():
    for name,row in feature_rows('bays',5):
        f=row['fixture'];kind='VTOL' if ';VTOL;' in f else 'MECH';d=baydoc(kind=kind);u,ship=d['units'];u.update(map='bay',at=[0,0,0]);u['aerospace']['fz']=129
        d['actions']=[configure(x=-1),diag('edge')]
        if 'DS11' in f:ship['at']=[11,10,0];ship['facing']=60
        if 'DS0,0' in f:ship['at']=[0,0,0]
        if 'airborne' in f:ship['aerospace']['landed']=False;ship['at'][2]=20
        if 'carried-unit' in f:u['aerospace']['carrying']=12;d['units'].append(craft('MECH',name='cargo',id=12,map='bay',at=[0,0,0]))
        if 'door-destroyed' in f:ship['sections'][0]['slots'][0]['firemode']=1
        if 'zombie' in f:ship['aerospace']['zombie']=True
        if 'missing' in f:d['maps'][1]['bay']['onmap']=99
        if 'pilot-outside' in f:u.update(in_character=True,pilot_details=dict(location=99))
        if 'C3-network' in f:
            peer=craft('MECH',name='peer',id=12,map='bay',at=[3,3,0],specials2=0x20,sections=[dict(index=0,slots=[dict(index=0,type=430)])]);u['specials2']=0x20;u['sections']=[dict(index=0,slots=[dict(index=0,type=430)])];d['units'].append(peer);d['actions'][0:0]=[cmd('c3i','02'),inspect()]
        rejected=any(s in f for s in ('ground-unit','door-destroyed','zombie','missing')) and ('airborne' in f or any(s in f for s in ('door-destroyed','zombie','missing')))
        c=Case(name,d).final(map='bay' if rejected else 'field')
        if 'C3-network' in f:
            c.result(ok=True).expect('results.1.units.u.communications.c3i.size',1).expect('state.units.u.communications.c3i.size',0).expect('state.units.peer.communications.c3i.size',0)
        if not rejected:
            x,y=([12,9] if 'DS11' in f else [0,0] if 'DS0,0' in f else [10,9]);z=21 if kind=='VTOL' else 0
            c.final(at=[x,y,z],fz=64.5*z if kind=='VTOL' else 129)
            if 'carried-unit' in f:c.expect('state.units.cargo.at',[10,9,20])
            if 'pilot-outside' in f:c.final(started=False)
        yield c
