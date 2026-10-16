"""Fresh public-process original fighter workflows; owned by normal APS."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from . import step, eq
from acceptance.aerospace.workflows import command, advance, inspect, slot, configure, diagnostic
from data.template_dependency import resolve_catalog
from entities.crittypes import i2bomb


def document(root, reference='CHP-W5'):
    """Copy unchanged upstream bytes into an isolated writable file adapter."""
    text=(resolve_catalog(True)/reference).read_bytes().decode('ascii')
    return dict(construction=dict(root=root+'/designs',files={reference:text}),
        pilots=dict(root=root+'/people'),file_root=root+'/maps',
        config=dict(periodic_updates=False,extended_gunnery=True,extended_piloting=True),random=dict(seed=1,streams={
            'pilot_rolls':[12]*100,'attack_rolls':[12]*20,
            'hit_location_rolls':[7]*100,'missile_cluster':[12]*20,
            'critical_rolls':[7]*100,'crittable_chance':[22]*100,
            'damage_entry':[7]*100,'tow_rolls':[7]*100,
            'fuel_check':[0]*100,'failure_weapon_chance':[1]*100,
            'missile_pre_roll':[1]*20,'character_d6':[6]*100,'fire_rolls':[7]*100}),
        maps=[dict(name='main',id=1000,size=[100,100],mapvis=60,maxvis=100,light=2)],
        units=[dict(name='u',id=10,contact_id='AA',at=[50,50,0],character=110,in_character=False)],
        characters=[dict(id=110,name='pilot',location=10,connected=True,
            values={'Build':5,'Reflexes':4,'Intuition':3,'Learn':2,'Charisma':1,
                'Piloting-Aerospace':6,'Piloting-Spacecraft':6,'Piloting-Biped':6,
                'Piloting-VTOL':6,'Gunnery-Laser':7,'Gunnery-Missile':7})],
        actions=[dict(op='template',unit='u',kind='load',reference=reference),
                 dict(op='personnel',unit='u',kind='attach',player=110)])


def run(document):
    process=subprocess.run([sys.executable,'-m','tools.aerospace'],
        input=json.dumps(document),text=True,capture_output=True,
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    assert process.returncode==0,process.stderr
    output=json.loads(process.stdout)
    for action,result in zip(document['actions'],output['results']):
        assert not isinstance(result,dict) or ('error' not in result and result.get('ok',True)
            and result.get('accepted',True)),(action,result)
    return output


def damage(section,amount,unit='u',**options):
    return dict(op='diagnose',unit=unit,kind='damage',
                options=dict(section=section,amount=amount,**options))


def peer(d,reference='CHP-W5'):
    d['construction']['files'][reference]=(resolve_catalog(True)/reference).read_bytes().decode('ascii')
    d['units'].append(dict(name='v',id=11,contact_id='BB',at=[50,49,0],team=2,in_character=False))
    d['actions'] += [dict(op='template',unit='v',kind='load',reference=reference),
                     dict(op='core',unit='v',values=dict(facing=180))]


def build(root,name):
    d=document(root);a=d['actions'];marks={}
    def mark(label):marks[label]=len(a);a.append(inspect())
    mark('loaded')
    if name=='original-load-save-reload':
        a += [dict(op='template',unit='u',kind='save',reference='saved',clock=0),
              dict(op='template',kind='read',reference='saved')]
    elif name=='original-takeoff-fly-land':
        a += [command('startup'),advance(30)];mark('started')
        a += [command('speed','60'),advance(10),command('takeoff'),advance(12)]
        mark('launched');a += [command('climb','0'),command('thrust','40'),advance(6)]
        mark('flown');a += [command('land')]
    elif name=='original-fire-and-missiles':
        peer(d);a += [command('startup'),advance(30),dict(op='cache',unit='u',target='v',flags=3)]
        mark('ready');a += [command('fire','0 BB')];mark('laser')
        a += [command('fire','2 BB')]
    elif name=='original-combat-damage':
        a += [damage('Left_Wing',20)];mark('depleted')
        a += [damage('Left_Wing',5)];mark('transferred')
        a += [dict(op='place',unit='u',at=[50,50,10]),damage('Engine',20)]
        mark('engine');a += [damage('Cockpit',16)]
    elif name=='fighter-bomb-release':
        peer(d);a += [dict(op='place',unit='v',at=[50,50,0]),command('startup'),advance(30),
            dict(op='place',unit='u',at=[50,50,2]),configure(landed=False),
            slot(3,11,type=i2bomb(2)),dict(op='diagnose',unit='u',kind='SetCargoWeight')]
        mark('armed');a += [command('bomb','drop 1')];mark('released');a += [advance(2)]
    else:raise AssertionError(name)
    return d,marks


@step(r'public workflow (\S+) runs')
def execute(w,name):
    w['workflow']=name
    with tempfile.TemporaryDirectory(dir='./tmp',prefix='fighter-aps-') as root:
        if name=='nonfighter-regression':
            outputs={}
            for reference in ('DS.Union','Cavalry','WVR-6R'):
                d=document(root+'/'+reference,reference)
                d['actions'] += [command('startup'),advance(30)]
                if reference=='Cavalry':
                    d['actions'] += [command('takeoff'),advance(1),command('vertical','0'),command('land')]
                elif reference=='DS.Union':
                    d['actions'] += [command('takeoff'),advance(301)]
                else:
                    peer(d,'WVR-6R');d['actions'] += [dict(op='cache',unit='u',target='v',flags=3),command('fire','0 BB')]
                outputs[reference]=run(d)
                Path('./tmp/six-nonfighter-'+reference+'.json').write_text(json.dumps(outputs[reference]))
            w['outputs']=outputs
        else:
            d,marks=build(root,name);output=run(d)
            w.update(output=output,marks={key:output['results'][index] for key,index in marks.items()})
            if name=='original-load-save-reload':
                second=document(root+'/reload','CHP-W5')
                second['construction']['files']={'CHP-W5':output['results'][-1]['text']}
                w['reload']=run(second)
            Path('./tmp/six-fighter-'+name+'.json').write_text(json.dumps(output))


def unit(state):return state['units']['u']
def event(state,kind):return any(e['kind']==kind for e in state['events'])


@step(r'the observable result is (\S+)')
def verify(w,result):
    name=w['workflow']
    if name=='nonfighter-regression':
        for reference,output in w['outputs'].items():
            u=unit(output['state']);assert u['started'] and not u['destroyed']
            if reference=='DS.Union':assert not u['aerospace']['landed'] and u['at'][2]>0
            elif reference=='Cavalry':assert u['aerospace']['landed']
            else:assert output['state']['units']['v']['damage_taken']>0
        return
    o=w['output'];state=o['state'];u=unit(state);m=w['marks'];loaded=unit(m['loaded'])
    eq(loaded['si'],0);assert not loaded['destroyed']
    eq([s['armor'] for s in loaded['sections'][:6]],[24,15,15,30,16,20])
    if name=='original-load-save-reload':
        reload=unit(w['reload']['state'])
        for key in ('sections','weapons','max_speed','sink_capacity','fuel','si'):
            eq(reload[key],loaded[key])
    elif name=='original-takeoff-fly-land':
        assert unit(m['started'])['started']
        assert not unit(m['launched'])['aerospace']['landed']
        assert unit(m['flown'])['at'][:2]!=unit(m['launched'])['at'][:2]
        assert unit(m['flown'])['fuel']<loaded['fuel']
        assert u['aerospace']['landed'] and u['at'][2]==0 and not u['destroyed']
    elif name=='original-fire-and-missiles':
        before=unit(m['ready']);laser=unit(m['laser'])
        assert laser['weap_heat']>before['weap_heat'] and u['weap_heat']>laser['weap_heat']
        assert u['sections'][0]['slots'][0]['data']>0 and u['sections'][0]['slots'][2]['data']>0
        assert u['sections'][3]['slots'][0]['data']<before['sections'][3]['slots'][0]['data']
        assert m['laser']['units']['v']['damage_taken']>0
        assert state['units']['v']['damage_taken']>m['laser']['units']['v']['damage_taken']
        assert state['units']['v']['sections'][0]['armor']<24
        eq(state['units']['v']['si'],0)
    elif name=='original-combat-damage':
        eq(unit(m['depleted'])['sections'][1]['armor'],0)
        eq(unit(m['depleted'])['sections'][3]['armor'],30)
        eq(unit(m['transferred'])['sections'][3]['armor'],25)
        engine=unit(m['engine']);assert engine['fallen'] and event(m['engine'],'FALL')
        eq([engine[k] for k in ('speed','max_speed','vertical_speed')],[0,0,0])
        assert u['destroyed'];eq([s['internal'] for s in u['sections'][:6]],[10]*6)
    else:
        assert unit(m['armed'])['aerospace']['payload']
        eq(unit(m['released'])['aerospace']['payload'],[])
        assert unit(m['released'])['carried_cargo']<unit(m['armed'])['carried_cargo']
        assert event(m['released'],'ARTILLERY_HIT') and not event(state,'ARTILLERY_HIT')
        assert state['units']['v']['damage_taken']>0
