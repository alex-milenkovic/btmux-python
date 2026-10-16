"""Normal APS public-process workflows; no imports from the independent QA suite."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from . import step,eq


def command(name,args='',unit='u'):return {'op':'command','unit':unit,'name':name,'args':args}
def edit(name,args='',editor='e'):return {'op':'editor','editor':editor,'name':name,'args':args}
def fileop(kind,reference='',unit='u',**extras):return {'op':'template','kind':kind,'reference':reference,'unit':unit,**extras}


def streams():
    return {'visibility_change':[0]*300,'failure_generic_chance':[5000]*100,'attack_rolls':[12]*4,
        'failure_weapon_chance':[1]*10,'hit_location_rolls':[7]*20,'damage_entry':[7]*20,'tow_rolls':[12]*20,
        'missile_pre_roll':[6]*20,'missile_cluster':[12]*10}


def base(root,actions,files=None,rear=False):
    return {'construction':{'root':str(Path(root)/'templates'),'files':files or {}},'file_root':str(Path(root)/'maps'),
        'units':[{'name':'u','at':[3,3,0]},{'name':'v','at':[3,5 if rear else 1,0],'team':2}],
        'config':{'periodic_updates':True,'lock_tick':0},'random':{'streams':streams()},'actions':actions}


def run(root,document):
    count=len(list(Path(root).glob('input-*.json')))
    input_path=Path(root)/f'input-{count}.json';input_path.write_text(json.dumps(document))
    process=subprocess.run([sys.executable,'-m','tools.construction_templates','--input',str(input_path)],capture_output=True,text=True)
    (Path(root)/f'output-{count}.json').write_text(process.stdout)
    (Path(root)/f'error-{count}.txt').write_text(process.stderr)
    assert process.returncode==0,process.stderr
    return json.loads(process.stdout)


def modern_text():
    # Explicit fixture from source default criticals, 50-ton internal table and AC5 data.
    text='Name { Test Chassis }\nReference { CUSTOM }\nType { Mech }\nMove_Type { Biped }\nTons { 50 }\nMax_Speed { 64.50 }\nHeat_Sinks { 10 }\n'
    sections=(('Left_Arm',8),('Right_Arm',8),('Left_Torso',12),('Right_Torso',12),('Center_Torso',16),('Left_Leg',12),('Right_Leg',12),('Head',3))
    for i,(name,internal) in enumerate(sections):
        text+=f'{name}\nArmor {{ 30 }}\nInternals {{ {internal} }}\n'
        defaults={}
        if i in (0,1,5,6):defaults={1:'ShoulderOrHip',2:'UpperActuator',3:'LowerActuator',4:'HandOrFootActuator'}
        if i==4:defaults={1:'Engine',2:'Engine',3:'Engine',4:'Gyro',5:'Gyro',6:'Gyro',7:'Gyro',8:'Engine',9:'Engine',10:'Engine'}
        if i==7:defaults={1:'LifeSupport',2:'Sensors',3:'Cockpit',5:'Sensors',6:'LifeSupport'}
        for pos,part in defaults.items():text+=f'CRIT_{pos} {{ {part} - - 3 }}\n'
        if i==2:text+='CRIT_1-4 { IS.AC/5 - - 3 }\n'
        if i==3:text+='CRIT_1 { Ammo_IS.AC/5 20 - - }\n'
    return text


def fire_actions():
    return [{'op':'construction_pilot','unit':'u','actor':{'gunnery':4,'piloting':5,'health':{'build':5,'bruise':0,'lethal':0}}},
       command('startup'),{'op':'advance','seconds':40},command('lock','01'),{'op':'advance','seconds':1},
       command('fire','0 01'),{'op':'inspect'},{'op':'advance','seconds':40},{'op':'inspect'}]


def assert_shot(output,rounds=19,lbx=False):
    results=output['results'];shot=next(r for r in results if isinstance(r,dict) and 'attack' in r)
    eq(shot['accepted'],True);eq(shot['attack']['hit'],True);eq(shot['attack']['damage_dealt'],5)
    snapshots=[r for r in results if isinstance(r,dict) and 'units' in r]
    before=snapshots[-2]['units']['u'];after=snapshots[-1]['units']['u']
    eq(before['sections'][3]['slots'][0]['data'],rounds);eq(before['weap_heat'],1.0)
    eq(before['weapons'][0]['recycle'],40);eq(after['weapons'][0]['recycle'],0)
    eq(snapshots[-2]['units']['v']['damage_taken'],5)
    if lbx:assert '5 pellets' in shot['text'];eq(len([d for d in output['draws'] if d['name']=='missile_cluster']),1)
    else:eq(len([d for d in output['draws'] if d['name']=='missile_cluster']),0)


def mode_workflow(root,weapon,fire,ammo):
    lbx=weapon=='IS.LB5-XAC';rear=bool(fire&32)
    actions=[edit('settarget','u'),edit('resetcrits'),edit('setspeed','6')]
    actions += [edit('setarmor',f'{loc} 30 {value}') for loc,value in zip(('LA','RA','LT','RT','CT','LL','RL','H'),(8,8,12,12,16,12,12,3))]
    slots='1 2 3 4 5' if lbx else '1 2 3 4'
    actions+=[edit('addweap',f'{weapon} LT {slots}'+(' R' if rear else ''))]
    actions+=[edit('reload',f'{weapon} RT 1'+(' +' if lbx else ' P' if ammo else ''))]
    if lbx:actions+=[edit('reload',f'{weapon} RT 1 L'),command('lbx','0')]
    elif ammo:actions+=[command('precision','0')]
    actions += [{'op':'construction_readout'},edit('savetemp2','CUSTOM')]
    first=run(root,base(root,actions,rear=rear))
    for result in first['results']:
        if isinstance(result,dict) and 'ok' in result:eq(result['ok'],True)
        if isinstance(result,dict) and 'accepted' in result:eq(result['accepted'],True)
    before=first['results'][-2]
    second=run(root,base(root,[fileop('load','CUSTOM'),{'op':'construction_readout'}]+fire_actions(),rear=rear))
    eq(second['results'][0]['ok'],True);loaded=second['results'][1]
    for loc in (2,3):
        eq((before['slots'][loc][0]['fire'],before['slots'][loc][0]['ammo']),
           (loaded['slots'][loc][0]['fire'],loaded['slots'][loc][0]['ammo']))
    eq((loaded['slots'][3 if lbx else 2][0]['fire'],loaded['slots'][3 if lbx else 2][0]['ammo']),(fire,ammo))
    assert_shot(second,9 if lbx or ammo else 19,lbx)
    saved=first['state']['construction']['files']['CUSTOM']
    if lbx:assert 'Halfton|LBX/Cluster' in saved
    elif rear and ammo:assert 'RearMount|Precision' in saved
    return first,second


@step(r'an ordinary editor configures weapon (.+) and its ammo with saved fire mask (\d+) and ammo mask (\d+) in the source-appropriate weapon or ammo slot')
def mode_setup(w,weapon,fire,ammo):w['mode_case']=(weapon,int(fire),int(ammo))


@step(r'a modern save is loaded into a fresh unit and a legal ordinary shot is fired')
def mode_run(w):
    with TemporaryDirectory(dir='./tmp') as root:w['outputs']=mode_workflow(root,*w['mode_case'])


@step(r'the saved and loaded masks agree and the shot consumes one round with (.+)')
def mode_result(w,behavior):
    eq(behavior,{('IS.LB5-XAC',128,1):'half-bin-and-LBX-cluster-resolution',('IS.AC/5',32,65536):'rear-arc-and-precision-ammunition',
        ('IS.AC/5',32,0):'rear-arc-standard-ammunition',('IS.AC/5',0,65536):'forward-arc-precision-ammunition',
        ('IS.AC/5',0,0):'forward-arc-standard-ammunition'}[w['mode_case']])


@step(r'an ordinary editor saves a template with (.+)')
def mixed_setup(w,modes):
    w['mixed']=modes
    w['mode_case']={'Halfton/BAR/LBX/Cluster':('IS.LB5-XAC',128,1),'RearMount/BAR/Precision':('IS.AC/5',32,65536)}[modes]


@step(r'a fresh process loads the saved file and fires using its loaded ammunition')
def mixed_run(w):mode_run(w)


@step(r'both source masks persist and the ordinary shot uses (.+)')
def mixed_result(w,behavior):eq(behavior,'half-bin-LBX' if w['mode_case'][0]=='IS.LB5-XAC' else 'rear-precision')


@step(r'the documented ordinary construction workflow (.+) has explicit files commands and expected state')
def workflow_setup(w,name):w['workflow']=name


@step(r'the workflow runs through a fresh CLI process')
def workflow_run(w):
    with TemporaryDirectory(dir='./tmp') as root:
        name=w['workflow'];template={'CUSTOM':modern_text()}
        if name=='modern-load-fire':
            out=run(root,base(root,[fileop('list'),fileop('load','CUSTOM'),{'op':'construction_readout'}]+fire_actions(),template))
            eq(out['results'][0]['entries'],[{'reference':'CUSTOM','directory':''}])
            read=out['results'][2];eq(read['slots'][2][0]['source_part_id'],96);eq(read['slots'][3][0]['source_part_id'],288)
            eq(read['real_num_sinks'],10);eq(read['radio_range'],100);assert_shot(out)
        elif name=='edit-save-reload':mode_workflow(root,'IS.AC/5',0,0)
        elif name=='restore-isolation':
            actions=[fileop('load','CUSTOM'),fileop('load','CUSTOM','v'),{'op':'inspect'},
                edit('settarget','u'),edit('repair','CT A 4'),{'op':'inspect'},edit('restore'),{'op':'inspect'}]
            out=run(root,base(root,actions,template));original,damaged,restored=[r for r in out['results'] if isinstance(r,dict) and 'units' in r]
            eq(damaged['units']['u']['sections'][4]['armor'],4);eq(restored['units']['u']['sections'][4]['armor'],30)
            eq(original['templates'],damaged['templates']);eq(original['units']['v']['sections'],restored['units']['v']['sections'])
        elif name=='legacy-load-save':
            legacy='50 20 40 20 10 64.50 0 0\n'+''.join('20 5 0 4\n'+'79 0 32\n'+'0 0 0\n'*11 for _ in range(8))+'0 0\n77\n'
            out=run(root,base(root,[fileop('load','OLD'),{'op':'construction_readout'},fileop('save','COPY',legacy=True)],{'OLD':legacy}))
            eq(out['results'][0]['ok'],True);eq(out['results'][1]['slots'][0][0]['source_part_id'],79)
            saved=out['state']['construction']['files']['COPY'];eq(saved.splitlines()[2],'79 0 32')
            fresh=run(root,base(root,[fileop('load','COPY'),{'op':'construction_readout'}]));eq(fresh['results'][1]['slots'][0][0]['source_part_id'],79)
        elif name=='catalog-discovery':
            actions=[{'op':'catalog','kind':'list','form':form} for form in ('short','long','vlong')]
            actions += [{'op':'catalog','kind':'match','form':'long','text':'MediumLas?r'},
              {'op':'catalog','kind':'partmatch','text':'HeatSink'}, {'op':'catalog','kind':'names','text':'IS.MediumLaser','brand':3}]
            out=run(root,base(root,actions))
            for form,rows in zip(('short','long','vlong'),out['results'][:3]):eq([r[form] for r in rows],sorted(r[form] for r in rows));assert len(rows)>1000
            eq(out['results'][3]['source_part_id'],79);eq(out['results'][4],'403 403 ');eq(out['results'][5]['vlong'],'Martell.IS.MediumLaser')
        elif name=='validation-weight':
            actions=[edit('settarget','u'),edit('setarmor','LA 20 8'),edit('repair','LA I 2'),{'op':'construction_validate'},{'op':'inspect'},
               edit('setarmor','LA 20 7'),{'op':'construction_validate'},{'op':'inspect'}]
            out=run(root,base(root,actions));eq(out['results'][4]['units']['u']['sections'][0]['internal'],2);eq(out['results'][7]['units']['u']['sections'][0]['internal'],8)
            assert out['results'][3]['total']>0
        elif name=='failed-load':
            actions=[edit('settarget','u'),edit('addweap','IS.MediumLaser LT 1'),fileop('load','MISSING'),{'op':'inspect'},
              fileop('load','BROKEN'),{'op':'inspect'},fileop('load','CUSTOM')]+fire_actions()
            out=run(root,base(root,actions,template|{'BROKEN':'Type { Mech }\nTons { 42 }\nLeft_Arm\nCRIT_13 { HeatSink - - - }\n'}))
            eq(out['results'][2]['ok'],False);eq(out['results'][3]['units']['u']['weapons'],[])
            eq(out['results'][4]['ok'],False);eq(out['results'][5]['units']['u']['weapons'],[])
            assert_shot(out)
        elif name=='multi-class':
            for kind,move in (('Mech','Quad'),('Vehicle','Track'),('VTOL','VTOL'),('Naval','Hull'),('AeroFighter','Fly'),('Aerodyne_DropShip','Fly'),('Spheroid_DropShip','Fly'),('Battlesuit','Biped'),('Mechwarrior','Biped')):
                content=f'Type {{ {kind} }}\nMove_Type {{ {move} }}\nTons {{ 50 }}\n'
                out=run(root,base(root,[fileop('load','CLASS'),edit('settarget','u'),edit('resetcrits'),fileop('save','SAVED'),{'op':'inspect'}],{'CLASS':content}))
                eq(out['results'][0]['ok'],True);eq(out['results'][2]['ok'],True);eq(out['results'][3]['ok'],True)
                slots=out['state']['units']['u']['sections'][3]['slots']
                if kind=='AeroFighter':eq([s['type'] for s in slots],[403,403,401,403,403,403,403,403,403,403,401,403])
        elif name=='cache-directory':
            actions=[fileop('list'),fileop('lookup','as7-d'),fileop('write','NEW',text='Tons { 50 }\n'),fileop('lookup','NEW'),
              edit('settarget','u'),edit('savetemp2','SAVED'),fileop('lookup','NEW'),fileop('lookup','Custom/nested/X')]
            out=run(root,base(root,actions,{'Custom/AS7-D':modern_text(),'Custom/nested/X':modern_text()}))
            eq(out['results'][1]['path'],'Custom/AS7-D');eq(out['results'][3]['path'],None);eq(out['results'][6]['path'],'NEW');eq(out['results'][7]['path'],'Custom/nested/X')
        elif name=='privilege-editor':
            actions=[edit('resetcrits'),dict(edit('resetcrits'),privilege=False),edit('settarget','u'),edit('settarget','v','other'),
               edit('settons','60'),edit('settons','80','other'),{'op':'construction_readout','unit':'u'},{'op':'construction_readout','unit':'v'}]
            doc=base(root,actions);doc['editors']=[{'name':'e','id':70},{'name':'other','id':71}]
            out=run(root,doc);eq(out['results'][0]['messages'],['You must set a target first!']);eq(out['results'][1]['messages'],["I'm sorry Dave, can't do that."])
            eq((out['results'][6]['tonnage'],out['results'][7]['tonnage']),(60,80))
        elif name=='shared-consumers':
            actions=[fileop('load','CUSTOM'),{'op':'diagnose','kind':'ProperMyomer','args':[]},
                {'op':'diagnose','kind':'ProperInternal','args':[]},
                {'op':'map_diagnose','kind':'bits','args':['set',8,0,1]},
                {'op':'map_diagnose','kind':'bits','args':['query',8,0,1]},
                {'op':'map_command','name':'weather.set','args':{'temperature':20,'windspeed':61}}]+fire_actions()
            doc=base(root,actions,template);doc['config']['complexrepair']=True
            out=run(root,doc);eq(out['results'][1],683);eq(out['results'][2],703);eq(out['results'][4],1);assert_shot(out)
            shot=next(r for r in out['results'] if isinstance(r,dict) and 'attack' in r)
            eq(shot['attack']['bth_breakdown']['weather_mod'],2)
            streak=modern_text().replace('CRIT_1-4 { IS.AC/5 - - 3 }','CRIT_1 { CL.StreakSRM-2 - - 0 }').replace('Ammo_IS.AC/5 20','Ammo_CL.StreakSRM-2 50')
            doc=base(root,[fileop('load','STREAK')]+fire_actions(),{'STREAK':streak})
            doc['random']['streams']['missile_cluster']=[2]
            out=run(root,doc)
            shot=next(r for r in out['results'] if isinstance(r,dict) and 'attack' in r)
            eq(shot['accepted'],True);eq(shot['attack']['damage_dealt'],4)
            # Ordinary unit hits consume the source cluster draw before Streak
            # replaces its result with max; building hits have a different guard.
            eq([d['value'] for d in out['draws'] if d['name']=='missile_cluster'],[2])
            snap=next(r for r in out['results'] if isinstance(r,dict) and 'units' in r)
            eq(snap['units']['u']['sections'][3]['slots'][0]['data'],49)
        else:raise ValueError(name)
        w['completed_workflow']=name


EVIDENCE={'modern-load-fire':'named-file-load-correct-mounts-ammo-damage-heat-and-recycle',
 'edit-save-reload':'ordinary-edits-persist-original-layout-and-derived-inventory',
 'restore-isolation':'damaged-live-unit-restored-with-immutable-independent-baselines',
 'legacy-load-save':'numeric-source-identity-current-armor-and-documented-format-losses',
 'catalog-discovery':'sorted-forms-exact-wildcard-cursors-brands-and-source-IDs',
 'validation-weight':'internal-correction-damage-preservation-and-design-current-weight',
 'failed-load':'source-reset-partial-writes-inspectable-errors-and-no-stale-mounts',
 'multi-class':'aero-vehicle-quad-suit-layouts-load-and-edit',
 'cache-directory':'one-level-discovery-case-limits-stale-cache-and-invalidation',
 'shared-consumers':'Core-repair-aliases-Combat-Streak-and-Maps-weather-bit-regressions',
 'privilege-editor':'session-target-permission-guards-and-independent-targets'}


@step(r'its public evidence must show (.+)')
def workflow_result(w,evidence):eq(evidence,EVIDENCE[w['completed_workflow']])
