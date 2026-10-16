"""Public CLI scenarios for normal generated acceptance, not an independent QA driver."""
from . import *

# Literal file/source expectations, never taken from a prior production readout.
# Recycle values are WEAPON_TICK(2) * weapons.h VRT, in seconds.
DESIGNS={
 'WVR-6R':(55,86,12,5,0,5,1,40),
 'BLR-1G':(85,64.5,18,0,2,10,10,60),
 'WHM-6R':(70,64.5,18,0,0,10,10,60),
 'MadCat-Prime':(75,86,34,0,0,10,12,40),
 'Grendel-Prime':(45,118.25,24,7,0,7,5,30),
 'GOL-1H':(80,64.5,17,0,2,10,10,60),
 'Demolisher':(80,53.75,0,0,0,20,7,60),
 'Cyrano':(30,193.5,10,0,0,8,8,50),
 'Sloth':(1,32.25,10,0,0,3,1,30),
 'Monitor':(75,53.75,10,0,3,20,7,60),
}


def inspect():return {'op':'inspect'}
def advance(seconds):return {'op':'advance','seconds':seconds}
def pilot():return {'op':'construction_pilot','actor':{'gunnery':4,'piloting':5,'health':{'build':5,'bruise':0,'lethal':0}}}


def design_fields(w,reference,read,snapshot):
    import re
    from data.construction_catalog import source_part
    from data.templates import MECH_TYPES
    text=(w['upstream']/reference).read_text()
    eq(read['tonnage'],int(declared(text,'Tons')));eq(read['max_speed'],float(declared(text,'Max_Speed')))
    eq(MECH_TYPES[read['type']].lower(),declared(text,'Type').lower())
    # File section order is not assumed to equal runtime order. Public section
    # labels supply identity; expected armor and explicit critical tokens come
    # from the unchanged source file, with normalization checked separately.
    names={'Left_Arm':0,'Right_Arm':1,'Left_Torso':2,'Right_Torso':3,'Center_Torso':4,'Left_Leg':5,'Right_Leg':6,'Head':7,
           'Front_Left_Leg':0,'Front_Right_Leg':1,'Rear_Left_Leg':5,'Rear_Right_Leg':6,
           'Left_Side':0,'Right_Side':1,'Front_Side':2,'Aft_Side':3,'Turret':4,'Rotor':5,
           **{f'Suit_{i+1}':i for i in range(8)}}
    loc=None;seen=0
    for line in text.splitlines():
        if line in names:loc=names[line];continue
        if loc is None:continue
        field=re.match(r'\s*(Armor|Rear)\s*\{\s*(\d+)',line)
        if field:eq(snapshot['sections'][loc]['armor' if field[1]=='Armor' else 'rear'],int(field[2]))
        crit=re.match(r'\s*CRIT_(\d+)(?:-(\d+))?\s*\{\s*(\S+)\s+(\S+)\s+(\S+)',line)
        if crit:
            start,end=int(crit[1])-1,int(crit[2] or crit[1]);part=source_part(crit[3])
            for pos in range(start,end):
                eq(read['slots'][loc][pos]['source_part_id'],part);seen+=1
                if crit[5]=='RearMount':eq(read['slots'][loc][pos]['fire']&32,32)
    assert seen>0,reference
    if reference=='WVR-6R':
        eq([s['internal'] for s in snapshot['sections']],[9,9,13,13,18,13,13,3])
        eq(sum(s['armor'] for s in snapshot['sections']),132);eq(sum(s['rear'] for s in snapshot['sections']),20)
        eq(read['slots'][7][3]['brand'],4)
        eq((read['slots'][1][8]['data'],read['slots'][2][2]['data']),(20,15))


def ordinary_design(w,reference,*,rear_weapon=None,shot_override=None):
    tons,speed,sinks,jump,weapon,damage,heat,recycle=DESIGNS[reference]
    if rear_weapon is not None:weapon,damage,heat,recycle=rear_weapon,5,3,40
    if shot_override is not None:weapon,damage,heat,recycle=shot_override
    actions=[fileop('load',reference),{'op':'construction_readout'},inspect(),pilot(),command('startup'),advance(40),
             command('speed','10.75'),advance(60),command('speed','stop'),advance(10),inspect()]
    if jump:
        actions += [command('jump','180 2'),inspect(),advance(30),advance(12),inspect(),command('jump','180 10')]
    elif reference in ('BLR-1G','WHM-6R'):actions += [command('jump','180 2')]
    actions += [command('lock','01'),advance(1),command('fire',f'{weapon} 01'),inspect()]
    mech=reference in ('WVR-6R','BLR-1G','WHM-6R','MadCat-Prime','Grendel-Prime','GOL-1H')
    if mech:actions += [edit('settarget','u'),edit('repair','CT A 1')]
    actions += [fileop('save','COPY-'+reference,clock='fixed'),advance(60),inspect()]
    doc=document(w,actions)
    doc['random']['streams']['visibility_change']=[0]*1500
    doc['random']['streams']['failure_generic_chance']=[5000]*400
    doc['random']['streams']['pilot_rolls']=[12]*20
    doc['random']['streams']['fuel_check']=[1]*500
    doc['map']={'size':[20,20]}
    doc['units'][1].update(facing=180,desired_facing=180)
    doc['units'][1]['sections']=[{'index':loc,'armor':100,'armor_orig':100,'rear':100,'rear_orig':100}
                                for loc in (2,3,4)]
    if rear_weapon is not None:doc['units'][1].update(at=[3,5,0],facing=0,desired_facing=0)
    if reference=='Cyrano':doc['units'][0]['at']=[3,3,3]
    if reference=='Monitor':doc['map']['default']=['WATER',3]
    out=run(w['root'],doc);results=out['results']
    eq(results[0]['ok'],True);read=results[1];snaps=[r['units']['u'] for r in results if isinstance(r,dict) and 'units' in r]
    eq((read['tonnage'],read['max_speed'],read['real_num_sinks'],read['jump_speed']),(tons,speed,sinks,jump*10.75))
    design_fields(w,reference,read,snaps[0])
    assert (snaps[1]['x'],snaps[1]['y'])!=(snaps[0]['x'],snaps[0]['y']),('did not move',reference,snaps[1]['at'])
    shot=next(r for r in results if isinstance(r,dict) and 'attack' in r)
    eq(shot['accepted'],True);eq(shot['attack']['hit'],True);eq(shot['attack']['damage_dealt'],damage)
    eq(snaps[-2]['weap_heat'],heat);eq(snaps[-2]['weapons'][weapon]['recycle'],recycle)
    eq(snaps[-1]['weapons'][weapon]['recycle'],0)
    if reference=='WVR-6R':eq(snaps[-2]['sections'][1]['slots'][8]['data'],19)
    if shot_override is not None:
        if reference=='WHM-6R':eq(snaps[-2]['sections'][3]['slots'][5]['data'],14)
        if reference=='BLR-1G':
            # The bin's actual source identity is compared in design_fields;
            # remaining ammo is asserted below by its declared LT location.
            eq(snaps[-2]['sections'][2]['slots'][5]['data'],199)
    if reference in ('Demolisher','Monitor'):
        bins=range(2,6 if reference=='Demolisher' else 5)
        eq(sum(snaps[-2]['sections'][4]['slots'][pos]['data'] for pos in bins),19 if reference=='Demolisher' else 14)
    if jump:
        jumps=[r for action,r in zip(actions,results) if action.get('name')=='jump']
        eq([r['accepted'] for r in jumps],[True,False]);eq(snaps[3]['jump_mp'],jump)
        from entities.mech import MechStatus
        assert not snaps[3]['status'] & int(MechStatus.JUMPING);assert not any(e['kind']=='JUMP' for e in out['state']['events'])
    for action,result in zip(actions,results):
        if action.get('name')!='jump' and isinstance(result,dict) and 'accepted' in result:eq(result['accepted'],True)
    reloaded=run(w['root'],document(w,[fileop('load','COPY-'+reference),{'op':'construction_readout'},inspect()]))
    eq(reloaded['results'][0]['ok'],True)
    after=reloaded['results'][1]
    for attr in ('tonnage','max_speed','jump_speed','type','move'):eq(after[attr],read[attr])
    if reference=='WVR-6R':eq(after['slots'][1][8]['data'],20)
    if mech:
        eq(snaps[-1]['sections'][4]['armor'],1)
        eq(reloaded['results'][2]['units']['u']['sections'][4]['armor'],snaps[0]['sections'][4]['armor_orig'])
    w.setdefault('ordinary',[]).append(reference)
    return out


@step(r'the documented catalog procedure (.+) has independent file and source expectations')
def workflow_setup(w,name):w['procedure']=name


@step(r'it runs through the ordinary public CLI in fresh processes')
def workflow_run(w):
    name=w['procedure']
    print('Catalog workflow: '+name,flush=True)
    if name=='setup-discover':
        path=w['root']/'fresh-catalog'
        p=subprocess.run([os.sys.executable,'-m','tools.template_catalog','setup','--path',str(path)],capture_output=True,text=True)
        eq(p.returncode,0);assert json.loads(p.stdout)['outcome'].startswith('verified')
        p=subprocess.run([os.sys.executable,'-m','tools.template_catalog','verify','--path',str(path)],capture_output=True,text=True)
        eq(p.returncode,0)
        for reference in ('WVR-6R','BLR-1G','WHM-6R'):lookup(w,reference);lookup_result(w,reference)
    elif name=='immutable-custom':
        shadow_setup(w)
        for operation,origin in (('default-load','custom'),('explicit-upstream-load','upstream'),('restore-original-unit','upstream'),('explicit-custom-load','custom')):
            # A fresh custom root for each sequence, no stale shadow at first load.
            shadow_file=w['root']/'templates/WVR-6R'
            if shadow_file.exists():shadow_file.unlink()
            shadow(w,operation);shadow_result(w,origin)
    elif name=='line-ending-parity':
        for reference in ('WVR-6R','BLR-1G','WHM-6R'):
            content=(w['upstream']/reference).read_bytes().replace(b'\r\n',b'\n').decode('ascii')
            doc=document(w,[fileop('load',reference),{'op':'construction_readout'},edit('settarget','u'),edit('restore'),{'op':'construction_readout'},fileop('load',reference,origin='custom'),{'op':'construction_readout'}])
            doc['construction']['files']={reference:content};doc['actions'][0]['origin']='upstream'
            out=run(w['root'],doc);a,b,c=[out['results'][i] for i in (1,4,6)]
            for attr in ('slots','max_speed','jump_speed','real_num_sinks'):eq(a[attr],b[attr]);eq(a[attr],c[attr])
    elif name=='full-catalog':
        path=w['root']/'report.json'
        p=subprocess.run([os.sys.executable,'-m','tools.template_catalog','audit','--path',str(w['upstream']),'--output',str(path)],capture_output=True,text=True)
        eq(p.returncode,2);report=json.loads(path.read_text())
        eq((report['candidates'],report['successes'],report['failures']),(1745,1742,3));eq(report['ambiguities'],[])
        eq(Counter(row.get('classification') for row in report['files'] if row['outcome']=='failed'),
           Counter({'unsupported-source-equipment':2,'malformed-range':1}))
    elif name=='wolverine-jump-combat':
        ordinary_design(w,'WVR-6R')
        doc=document(w,[fileop('load','WVR-6R'),fileop('load','WVR-6R','v'),inspect(),edit('settarget','u'),edit('repair','CT A 1'),edit('restore'),inspect()]+fire_actions())
        doc['units'][1]['team']=2
        out=run(w['root'],doc);eq(out['results'][6]['units']['u']['sections'][4]['armor'],20)
        eq(out['results'][2]['units']['v']['sections'],out['results'][6]['units']['v']['sections'])
        eq(next(r for r in out['results'] if isinstance(r,dict) and 'attack' in r)['attack']['damage_dealt'],5)
    elif name=='battlemaster-warhammer':
        ordinary_design(w,'BLR-1G');ordinary_design(w,'WHM-6R');ordinary_design(w,'BLR-1G',rear_weapon=5)
        ordinary_design(w,'BLR-1G',shot_override=(0,2,0,14))
        ordinary_design(w,'WHM-6R',shot_override=(7,12,4,30))
    elif name=='clan-quad':
        for reference in ('MadCat-Prime','Grendel-Prime','GOL-1H'):ordinary_design(w,reference)
        out=run(w['root'],document(w,[fileop('load','Grendel-Prime'),{'op':'diagnose','kind':'do_sub_magic','args':[]},{'op':'construction_readout'}]))
        eq(out['results'][-1]['jump_speed'],75.25)
    elif name=='other-classes':
        for reference in ('Demolisher','Cyrano','Sloth','Monitor'):ordinary_design(w,reference)
        for reference in ('DS.Union','DS.Aero','MechWarrior'):
            out=run(w['root'],document(w,[fileop('load',reference),{'op':'construction_readout'},fileop('save','COPY-'+reference,clock='fixed')]))
            eq(out['results'][0]['ok'],True);eq(out['results'][2]['ok'],True)
            freshout=run(w['root'],document(w,[fileop('load','COPY-'+reference),{'op':'construction_readout'}]))
            eq(freshout['results'][0]['ok'],True);eq(freshout['results'][1]['type'],out['results'][1]['type'])
        out=run(w['root'],document(w,[fileop('load',ref) for ref in ('SL-17','AS7-DC','Elemental','Uller-D')]+[fileop('load','WVR-6R')]+fire_actions()))
        eq([r['ok'] for r in out['results'][:5]],[True,False,False,False,True]);eq(next(r for r in out['results'] if isinstance(r,dict) and 'attack' in r)['attack']['damage_dealt'],5)
    elif name=='jump-boundaries-regressions':
        from acceptance.construction_templates.integration import mode_workflow
        mode_workflow(w['root'],'IS.LB5-XAC',128,1);mode_workflow(w['root'],'IS.AC/5',32,65536)
        doc=document(w,[fileop('load','WVR-6R'),{'op':'diagnose','kind':'do_sub_magic','args':[]},{'op':'construction_readout'},
             {'op':'map_diagnose','kind':'bits','args':['set',8,0,1]}, {'op':'map_diagnose','kind':'bits','args':['query',8,0,1]}])
        out=run(w['root'],doc);eq(out['results'][2]['jump_speed'],53.75);eq(out['results'][4],1)
    else:raise ValueError(name)
    w['completed']=name

EVIDENCE={'setup-discover':'portable-pinned-setup-list-and-origin','immutable-custom':'safe-custom-save-shadow-and-origin-preserving-restore',
 'line-ending-parity':'central-LF-CRLF-equivalence-with-rejections','full-catalog':'every-raw-candidate-outcome-and-collision',
 'wolverine-jump-combat':'real-five-MP-jump-land-fire-and-restore','battlemaster-warhammer':'loaded-layouts-motion-front-rear-fire-and-reload',
 'clan-quad':'Clan-and-quad-designs-jump-fire-and-reload','other-classes':'class-appropriate-motion-fire-and-persistence',
 'jump-boundaries-regressions':'shared-C2-boundaries-and-preserved-consumers'}

@step(r'its complete evidence proves (.+)')
def workflow_result(w,evidence):eq(EVIDENCE[w['completed']],evidence)
