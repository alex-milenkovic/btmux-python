"""QA procedure 10: real gunner rooms, delegates and restoration."""
from aerospace_support import *


def turret_command(name,args='',turret='A',actor=201):return op('turret',turret=turret,actor=actor,name=name,args=args)

def turretdoc(actions=None):
    u=craft('DS',at=[10,10,0],aerospace=dict(landed=True),target='a',pilot_details=dict(gunnery=7),weapons=[dict(name='IS.MediumLaser',section=5,critical=0),dict(name='IS.MediumLaser',section=5,critical=1)])
    targets=[craft('MECH',name=name,id=identity,contact_id=contact,at=at,sections=[dict(index=j,armor=255,armor_orig=255,internal=100,internal_orig=100,rear=255,rear_orig=255) for j in range(8)]) for name,identity,contact,at in [('a',20,'AA',[10,8,0]),('b',21,'BB',[10,9,0])]]
    d=document(u,actions or [turret_command('range')],units=[*targets,u],characters=[dict(id=i,name='Gunner'+str(i),location=room,connected=True,values={'Reflexes':5,'Intuition':5,'Gunnery-Spacecraft':6}) for i,room in [(201,40),(202,41)]],turrets=[dict(name='A',id=40,parent='u',gunner=201,arcs=1,target='b'),dict(name='B',id=41,parent='u',gunner=202,arcs=1,target='a')],random=dict(streams={'sensor.random':[1]*200,'sensor.detect':[1]*200,'sensor.perception_xp':[1]*200,'attack_rolls':[12]*10,'hit_location_rolls':[7]*10,'damage_entry':[7]*10,'tow_rolls':[12]*10,'failure_weapon_chance':[1]*10,'failure_generic_chance':[5000]*10}))
    d['config']['extended_gunnery']=False
    return d


def restored(case):
    return case.final(target=20,status=9).expect('state.overrides',dict(pilot=0,arc=0))


def lifecycle():
    for name,row in feature_rows('turrets',1):
        f=row['fixture'];d=turretdoc();t=d['turrets'][0];old=d['characters'][0];actor=202
        if f.startswith('allocate'):
            t.update(gunner=7,targ_z=9,target=20,targ_x=3,targ_y=4);d['actions']=[op('turret_diagnose',turret='A',selector=1)];c=Case(name,d).expect('state.turrets.A.gunner',7).expect('state.turrets.A.targ_z',9).expect('state.turrets.A.target',-1).expect('state.turrets.A.targ_x',-1).expect('state.turrets.A.targ_y',-1)
        elif f=='free-selector':
            d['actions']=[op('turret_diagnose',turret='A',selector=0)];c=Case(name,d).expect('state.turrets.A.target',21).expect('state.turrets.A.gunner',201)
        else:
            d['characters'][1]['location']=40
            if 'disconnected' in f:old['connected']=False
            if 'other-room' in f:old['location']=41
            if 'same-gunner' in f or 'registered-gunner' in f:actor=201
            if 'invalid-parent' in f:t['parent']=999
            command='deinitialize' if f.startswith('deinitialize') else 'initialize';d['actions']=[turret_command(command,actor=actor)]
            accepted='disconnected' in f or 'other-room' in f or 'registered-gunner' in f
            c=Case(name,d).result(ok=accepted).expect('state.turrets.A.gunner',-1 if 'registered-gunner' in f else 202 if accepted else 201)
        yield c
    for name,row in feature_rows('turrets',2):
        f=row['fixture'];d=turretdoc()
        if f=='parent-not-mech':d['turrets'][0]['parent']=999
        if f=='gunner-minus1':d['turrets'][0]['gunner']=-1
        if f=='caller-not-gunner':d['actions'][0]['actor']=202
        if f=='gunner-is-parent-pilot':d['units'][2]['character']=201
        c=Case(name,d).result(ok=f.startswith('authorized'))
        if f.startswith('authorized'):restored(c)
        yield c
    for name,row in feature_rows('turrets',5):
        d=turretdoc([turret_command(row['command'])]);d['turrets'][0].update(parent=999,gunner=-1)
        yield Case(name,d).result(ok=True,messages=[]).final(shots_fired=0).expect('state.turrets.A.gunner',-1)


def delegates():
    for name,row in feature_rows('turrets',3):
        command=row['command'].lower();args={'fire':'0','sight':'0','lock':'BB','lrs':'m'}.get(command,'')
        d=turretdoc([turret_command(command,args)])
        if command=='eta':d['turrets'][0].update(target=-1,targ_x=10,targ_y=9)
        c=restored(Case(name,d))
        c.result(ok=True)
        if command=='fire':c.final(shots_fired=1,weap_heat=3).expect('state.units.b.damage_taken',5).expect('state.units.u.weapons.0.recycle',0,'greater')
        elif command=='sight':c.final(shots_fired=0,weap_heat=0).expect('results.0.attack.bth_breakdown.base',2)
        elif command=='lock':c.expect('state.turrets.A.target',21).expect('state.events',['LOCK',0],'event_count')
        elif command=='range':c.expect('results.0.range',1,'close')
        elif command=='bearing':c.expect('results.0.bearing',0)
        elif command=='findcenter':c.result(x=10,y=10,z=0).expect('results.0.range',0,'close')
        elif command in ('lrs','navigate','tactical'):
            width,height={'lrs':(30,20),'navigate':(5,5),'tactical':(21,14)}[command]
            c.expect('results.0.rows',height,'length').expect('results.0.rows.0',width,'length').expect('results.0.cells',width*height,'length')
            c.expect('results.0.cells',dict(x=10,y=9,terrain=' ',elevation=0,unit=21),'has_record')
        elif command=='contacts':
            c.expect('results.0.contacts',2,'length').expect('results.0.contacts',dict(id=21,contact_id='BB',locked_by_me=True),'has_record')
        elif command in ('scan','report'):
            c.expect('results.0.report.contact_id','BB').expect('results.0.report.position',[10,9,0]).expect('results.0.report.range',1)
            if command=='scan':c.expect('results.0.armor',8,'length').expect('results.0.armor.0.armor',255)
        elif command=='critstatus':c.expect('results.0.sections',8,'length').expect('results.0.sections.5.slots.0.name','IS.MediumLaser')
        elif command in ('status','weaponspecs'):
            c.expect('results.0.weapons',2,'length').expect('results.0.weapons.0.spec.damage',5).expect('results.0.weapons.0.spec.heat',3)
            if command=='status':c.expect('results.0.unit.type','DS').expect('results.0.unit.position',[10,10,0])
        yield c


def contexts():
    for name,row in feature_rows('turrets',4):
        f=row['fixture'];d=turretdoc();actions=[]
        if 'hex-lock' in f:actions=[turret_command('lock','10 9')]
        elif 'lock-BB' in f:actions=[turret_command('lock','BB')]
        elif 'invalid-target' in f:actions=[turret_command('fire','0 ZZ')]
        elif 'delegate-error' in f:actions=[turret_command('qa-invalid-delegate')]
        else:actions=[turret_command('fire','0')]
        if 'IC-' in f:
            d['units'][2]['in_character']=True
            if 'IC-wizard-' in f:d['characters'][0]['wizard']=True
        if 'arcs-exclude' in f:d['units'][2]['core']['unusable_arcs']=1;d['turrets'][0]['arcs']=8
        if 'turretB-same' in f:actions.append(turret_command('fire','0',turret='B',actor=202))
        if 'parent-fire' in f:actions += [advance(40),cmd('fire','0')]
        if 'room-occupants' in f:d['characters'].append(dict(id=301,name='BridgeCrew',location=10,connected=True))
        if 'IC-wizard' in f:
            d['units'][1].update(in_character=True,team=2,at=[10,6,0]);d['random']['streams']['xp_old_gate']=[1]
        d['actions']=actions;c=restored(Case(name,d))
        if 'room-occupants' in f:
            for ident in (201,202,301):c.expect(f'state.inboxes.{ident}',1,'length').expect(f'state.inboxes.{ident}.0','You fire MediumLaser at ','contains')
        if 'IC-wizard' in f:c.expect('state.units.u.xp_requests',dict(player=201,producer='gun',applied=True),'has_record')
        if 'parent-fire' in f:
            c.checks=[check for check in c.checks if check['path']!='state.units.u.status']
            c.final(status=0x1000009).expect('results.2.attack.target_id',20).expect('results.2.attack.bth_breakdown.base',7)
        if 'delegate-error' in f:c.result(ok=False).text('results.0.error','Unknown turret command')
        elif 'invalid-target' in f or 'IC-nonwizard' in f or 'arcs-exclude' in f:c.result(ok=False).final(shots_fired=0)
        elif 'lock' in f:c.result(ok=True).final(shots_fired=0)
        else:
            c.result(ok=True).final(shots_fired=2 if 'parent-fire' in f else 1)
            if 'turretB-same' in f:c.result(1,ok=False).expect('state.turrets.B.target',20)
        yield c


def supplemental_turrets():
    d=turretdoc([turret_command('sight','0')]);d['units'][2]['core'].update(quiet=True,mechskills='5 3')
    yield restored(Case('procedures/turret-machine-skill',d)).result(ok=True).expect('results.0.attack.bth_breakdown.base',3).final(shots_fired=0)
    d=turretdoc([turret_command('fire','0')]);d['turrets'][0]['arcs']=8;d['units'][2]['core']['unusable_arcs']=0
    yield restored(Case('procedures/turret-zero-parent-arcs',d)).result(ok=True).final(shots_fired=1)
    d=turretdoc([turret_command('fire','0')]);d['units'][2]['weapons'][0]['section']=4
    yield restored(Case('procedures/turret-physical-mount-arc',d)).result(ok=False).final(shots_fired=0)
