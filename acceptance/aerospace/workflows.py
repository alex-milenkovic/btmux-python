"""Normal acceptance subprocess workflows through the public CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from . import step,eq
from entities.mech import MechStatus as S,CritStatus as C
from entities.crittypes import i2bomb
from systems.dropships import MECHDOOR


def command(name,args='',unit='u'):
    return dict(op='command',unit=unit,name=name,args=args)


def configure(**values):return dict(op='aero_configure',unit='u',values=values)
def advance(n):return dict(op='advance',seconds=n)
def diagnostic(kind,**values):return dict(op='aero_diagnose',unit='u',kind=kind,**values)
def inspect():return dict(op='inspect')
def slot(section,index,**values):return dict(op='section',unit='u',value=dict(index=section,slots=[dict(index=index,**values)]))


def document(root,reference='DS.Union'):
    # Copy genuine design bytes to the isolated writable template adapter root.
    from data.template_dependency import resolve_catalog
    catalog=resolve_catalog(True)
    text=(catalog/reference).read_bytes().decode('ascii')
    d=dict(construction=dict(root=root+'/designs',files={reference:text}),pilots=dict(root=root+'/people'),
           file_root=root+'/maps',config=dict(periodic_updates=False,extended_gunnery=True,extended_piloting=True),random=dict(seed=1),
           maps=[dict(name='main',id=1000,size=[30,30],mapvis=60,maxvis=100,light=2)],
           units=[dict(name='u',id=10,contact_id='AA',at=[10,10,0],character=110,in_character=False)],
           characters=[dict(id=110,name='pilot',location=10,connected=True,wizard=True,
              values={'Build':5,'Reflexes':4,'Intuition':3,'Learn':2,'Charisma':1,'Piloting-Spacecraft':6,'Piloting-Aerospace':6,'Piloting-Biped':6,'Piloting-VTOL':6,'Gunnery-Laser':7})],
           actions=[dict(op='template',unit='u',kind='load',reference=reference),
              dict(op='personnel',unit='u',kind='attach',player=110),
              dict(op='communications_diagnose',unit='u',kind='configure',values=dict(status=int(S.STARTED))),
              configure(fuel=1000,max_speed=60,tac_range=15,lrs_range=30),dict(op='core',unit='u',values=dict(cargo_inventory=[]))])
    return d


def build(root,name):
    reference='WVR-6R' if name=='bay-entry-and-content-transfer' else 'Cavalry' if name in ('landing-and-zones','bridge-and-preservation','bay-exit-and-placement') else 'DS.Union'
    d=document(root,reference);a=d['actions'];marks={}
    def mark(label):marks[label]=len(a);a.append(inspect())
    def peer(name='v',**extra):
        record=dict(name=name,id=11+len(d['units']),contact_id=chr(65+len(d['units']))+'Z',at=[10,10,0],team=2,in_character=False)
        record['sections']=[dict(index=i,armor=255,armor_orig=255,internal=255,internal_orig=255) for i in range(8)]
        record.update(extra);d['units'].append(record)
    if name=='launch-abort-relaunch':
        a += [configure(landed=True),dict(op='communications_diagnose',kind='configure',unit='u',values=dict(crit_status=int(C.HIDDEN))),command('takeoff','2')]
        mark('queued');a += [command('land'),advance(3)];mark('aborted')
        a += [command('takeoff','2'),advance(2)];mark('last');a += [advance(1)];mark('launched');a += [advance(2)]
    elif name=='landing-and-zones':
        a += [dict(op='place',unit='u',at=[10,10,1]),dict(op='hex',value=dict(at=[10,10],terrain='ROUGH',elevation=0)),command('checklz'),command('land')]
        mark('blocked');a += [dict(op='hex',value=dict(at=[10,10],terrain='GRASSLAND',elevation=0)),command('addmine','10 10 standard 4'),command('checklz'),command('land')]
    elif name=='flight-and-backup':
        a += [dict(op='place',unit='u',at=[10,10,100]),command('thrust','20'),command('climb','30'),advance(2)]
        mark('moving');a += [configure(fuel=1,speed=20),diagnostic('fuel')];mark('empty');a += [diagnostic('fuel')];mark('backup')
        a += [configure(start_fx=0,start_fy=0,start_fz=0,desired_speed=1,desired_angle=90),diagnostic('speed')]
    elif name=='aircraft-periodic-updates':
        d['random']['streams']={'pilot_rolls':[12]*10,'visibility_change':[17]*20,'failure_generic_chance':[5000]*40}
        a += [dict(op='place',unit='u',at=[10,10,100]),dict(op='core',unit='u',values=dict(weap_heat=15)),diagnostic('update')]
        mark('window');a += [diagnostic('control'),advance(15),diagnostic('update')]
    elif name in ('bomb-list-aim-drop','bomb-scatter-and-terrain'):
        peer();a += [dict(op='place',unit='u',at=[10,10,2]),slot(7,11,type=i2bomb(2)),dict(op='diagnose',unit='u',kind='SetCargoWeight'),command('bomb','list'),command('bomb','aim')]
        d['random']['streams']={'pilot_rolls':[12] if name=='bomb-list-aim-drop' else [2,12],'bomb_scatter_distance':[6],'bomb_scatter_direction':[0],'hit_location_rolls':[7]*50,'critical_rolls':[7]*50,'crittable_chance':[1]*50,'damage_entry':[7]*100,'tow_rolls':[7]*100}
        if name=='bomb-list-aim-drop':
            mark('loaded');a += [command('bomb','drop 1')];mark('released');a += [advance(1)];mark('before-hit');a += [advance(1)]
        else:
            a += [command('bomb','drop 1')];mark('scatter')
            a += [slot(7,11,type=i2bomb(2)),configure(start_fx=100000),command('bomb','drop 1')];mark('offmap')
            a += [configure(start_fx=0,fz=0),dict(op='hex',value=dict(at=[11,10],terrain='GRASSLAND',elevation=9)),dict(op='hex',value=dict(at=[12,10],terrain='GRASSLAND',elevation=9)),diagnostic('simulate_flight',x=13,y=10,time=4)]
    elif name=='dropship-exhaust':
        peer(at=[10,11,0],sensors=['I','L'])
        a += [configure(landed=True),dict(op='hex',value=dict(at=[10,11],terrain='LIGHT_FOREST',elevation=0)),command('takeoff','6'),advance(1)]
        mark('flash');a += [advance(5)]
    elif name in ('bay-entry-and-content-transfer','bay-exit-and-placement'):
        d['maps'].append(dict(name='bay',id=1001,size=[10,10],bay=dict(onmap='ship',in_character=True)))
        peer('ship',id=20,class_='DS')
        ship=d['units'][-1];ship.pop('class_');ship.update({'class':'DS','movement':'FLY','contact_id':'DD','at':[10,10,0],'aerospace':dict(landed=True,bays=['bay',-1,-1,-1]),'sections':[dict(index=5,slots=[dict(index=0,type=MECHDOOR)])]})
        peer('cargo',id=21,at=[10,9,0]);a += [dict(op='place',unit='u',at=[10,9,0]),configure(carrying=21),command('enterbay'),advance(11)]
        mark('pending');a += [advance(1)];mark('entered')
        if name=='bay-entry-and-content-transfer':
            peer('second',id=22,at=[10,9,0]);a.insert(marks['pending'],command('enterbay',unit='second'))
            marks={key:(value+1 if value>=marks['pending'] else value) for key,value in marks.items()}
            peer('mw',id=24,at=[10,9,0],character=114,in_character=True,**{'class':'MW','movement':'BIPED'})
            d['characters'].append(dict(id=114,name='walking pilot',location=24,connected=True))
            a += [dict(op='bay_configure',map='bay',values=dict(in_character=False)),command('enterbay',unit='mw'),advance(12)]
        else:
            peer('master',id=23,team=0,map='bay',at=[5,5,0],communications=dict(specials=128,working_c3_masters=1))
            a += [dict(op='communications_diagnose',kind='configure',unit='u',values=dict(specials=256)),
                  dict(op='communications_diagnose',kind='add',unit='master',target='u'),
                  dict(op='communications_diagnose',kind='replicate',unit='master',target='u')]
            mark('network')
            a += [dict(op='place',unit='ship',at=[11,10,2]),dict(op='core',unit='ship',values=dict(facing=60)),configure(x=-1),diagnostic('edge')]
    elif name=='turret-control-and-fire':
        peer();d['units'][-1]['at']=[10,9,0]
        for ident in (200,201):d['characters'].append(dict(id=ident,name='gunner'+str(ident),location=40+ident-200,connected=True,values={'Build':5,'Reflexes':4,'Intuition':3,'Learn':2,'Gunnery-Laser':7}))
        d['turrets']=[dict(name='A',id=40,parent='u',arcs=1),dict(name='B',id=41,parent='u',arcs=1)]
        d['random']['streams']={'attack_rolls':[12]*10,'failure_weapon_chance':[1]*40,'hit_location_rolls':[7]*50,'critical_rolls':[7]*50,'crittable_chance':[1]*50,'damage_entry':[7]*100,'tow_rolls':[7]*100}
        # Install a real shared nose mount, retaining the loaded ship's other systems.
        a += [slot(5,0,weapon='IS.MediumLaser'),dict(op='cache',unit='u',target='v',flags=3)]
        for turret,actor in (('A',200),('B',201)):
            for cmd,args in (('initialize',''),('lock','BZ')):a.append(dict(op='turret',turret=turret,actor=actor,name=cmd,args=args))
        mark('locks');a += [dict(op='turret',turret='A',actor=200,name='fire',args='0')];mark('shot')
        a += [dict(op='turret',turret='B',actor=201,name='fire',args='0'),dict(op='turret',turret='B',actor=201,name='range')]
    elif name=='bridge-and-preservation':
        d['units'][0]['in_character']=True
        d['characters'][0]['wizard']=False
        for ident in (200,201):d['characters'].append(dict(id=ident,name='crew'+str(ident),location=10,connected=True,wizard=ident==201))
        a += [dict(op='place',unit='u',at=[10,10,1]),command('land')];mark('landed')
        a += [configure(fuel=1,landed=False,speed=20),diagnostic('fuel')];mark('empty');a += [diagnostic('fuel')];mark('fall')
        a += [diagnostic('bridge')]
    else:raise AssertionError(name)
    return d,marks


@step(r'independent workflow (\S+) from the aerospace QA suite')
def fixture(w,name):w['workflow']=name


@step(r'QA executes the public interface in a fresh subprocess')
def execute(w):
    # Each workflow runs through a fresh public CLI process.
    with tempfile.TemporaryDirectory(dir='./tmp',prefix='aero-acceptance-') as root:
        d,marks=build(root,w['workflow'])
        result=subprocess.run([sys.executable,'-m','tools.aerospace'],input=json.dumps(d),text=True,capture_output=True,
                              env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        assert result.returncode==0,result.stderr
        output=json.loads(result.stdout)
        eq(output['results'][0]['ok'],True)
        for row in output['results']:
            assert not (isinstance(row,dict) and 'error' in row),(w['workflow'],row)
        w.update(output=output,marks={key:output['results'][index] for key,index in marks.items()})
        Path('./tmp/aerospace-workflow-'+w['workflow']+'.json').write_text(json.dumps(output))


def craft(state):return state['units']['u']
def has_event(state,name):return any(e['kind']==name for e in state['events'])


@step(r'the observable result is (\S+)')
def verify(w,result):
    o=w['output'];state=o['state'];u=craft(state);m=w['marks'];name=w['workflow']
    if name=='launch-abort-relaunch':
        assert has_event(m['queued'],'TAKEOFF') and not craft(m['queued'])['crit_status']&int(C.HIDDEN)
        assert not has_event(m['aborted'],'TAKEOFF') and craft(m['aborted'])['aerospace']['landed']
        assert craft(m['last'])['aerospace']['landed'] and not craft(m['launched'])['aerospace']['landed']
        assert u['at'][2]>=1 and has_event(state,'MOVE')
    elif name=='landing-and-zones':
        assert not craft(m['blocked'])['aerospace']['landed']
        assert u['aerospace']['landed'] and u['at'][2]==0 and u['damage_taken']>0
        assert any('A_AAEROLAND' in str(e) for e in u['external_effects'])
    elif name=='flight-and-backup':
        assert craft(m['moving'])['aerospace']['start_fz']>0 and craft(m['moving'])['aerospace']['fy']!=3386.25
        eq(craft(m['empty'])['fuel'],0);eq(craft(m['backup'])['fuel'],-1)
        assert not has_event(m['empty'],'FALL');eq(u['aerospace']['start_fz'],1)
    elif name=='aircraft-periodic-updates':
        assert craft(m['window'])['weap_heat']==12 and 'aero_update' not in u['missing_services']
        assert not u['aerospace']['spinning'] and any('recover control' in s for s in u['messages'])
        assert any(d['name']=='visibility_change' for d in o['draws'])
    elif name=='bomb-list-aim-drop':
        eq(len(craft(m['loaded'])['aerospace']['payload']),1);eq(craft(m['released'])['aerospace']['payload'],[])
        assert craft(m['loaded'])['carried_cargo']>craft(m['released'])['carried_cargo']
        assert has_event(m['released'],'ARTILLERY_HIT') and m['before-hit']['units']['v']['damage_taken']==0
        assert state['units']['v']['damage_taken']>0 and not has_event(state,'ARTILLERY_HIT')
    elif name=='bomb-scatter-and-terrain':
        shot=next(e for e in m['scatter']['events'] if e['kind']=='ARTILLERY_HIT');eq(shot['bomb']['x'],13)
        eq(len(craft(m['offmap'])['aerospace']['payload']),1)
        eq(sum(e['kind']=='ARTILLERY_HIT' for e in m['offmap']['events']),1)
        eq(o['results'][-1],[12,10])
    elif name=='dropship-exhaust':
        assert m['flash']['units']['v']['status']&int(S.BLINDED)
        assert state['units']['v']['damage_taken']>0 and state['units']['v']['crit_status']&int(C.JELLIED)
        assert any('trees' in msg.lower() for inbox in state['inboxes'].values() for msg in inbox)
    elif name.startswith('bay-'):
        eq(craft(m['pending'])['map'],'main');assert has_event(m['pending'],'ENTER_HANGAR')
        for key in ('u','cargo'):eq(m['entered']['units'][key]['map'],'bay');eq(m['entered']['units'][key]['at'][:2],[5,5])
        if name=='bay-entry-and-content-transfer':
            assert any('Someone else' in str(row) for row in o['results'])
            assert all(i in state['personnel']['contents']['1001'] for i in (10,21,114))
            assert has_event(state,'NUKEMECH')
        else:
            eq(u['map'],'main');eq(u['at'],[12,9,3]);eq(state['units']['cargo']['at'],[12,9,2])
            assert 10 in m['network']['units']['master']['communications']['c3']['peers']
            assert 10 not in state['units']['master']['communications']['c3']['peers']
    elif name=='turret-control-and-fire':
        eq(state['overrides'],dict(pilot=0,arc=0));eq(u['target'],-1)
        eq(state['turrets']['A']['target'],state['turrets']['B']['target'])
        assert m['shot']['units']['v']['damage_taken']>0
        assert any('recharg' in str(row) for row in o['results'])
        assert all(sum('You fire ' in msg for msg in state['inboxes'][str(i)])==1 for i in (110,200,201))
    else:
        assert craft(m['landed'])['aerospace']['landed'];eq(craft(m['empty'])['fuel'],0)
        eq(craft(m['fall'])['fuel'],-1);assert has_event(m['fall'],'FALL')
        assert 200 not in state['personnel']['contents'].get('10',[]) and 201 in state['personnel']['contents']['10']
