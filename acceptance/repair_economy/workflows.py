"""Integrated ordinary-command journeys in fresh public CLI processes."""
from copy import deepcopy
import json,os,subprocess,sys,tempfile
from pathlib import Path
from . import check,source_id,i2weapon,i2ammo,i2special,Special,get_weapon,F,S,Specials


def document(root):
    return dict(pilots=dict(root=root+'/chars'),construction=dict(root=root+'/designs'),file_root=root+'/maps',
        repair_economy=dict(root=root+'/economy',objects=[]),map=dict(id=1000,size=[30,30],mapvis=60,maxvis=100,light=2),
        config=dict(periodic_updates=False),random=dict(seed=1,streams={'tech_rolls':[12]*6,'pilot_rolls':[12]*20,'sensor.perception_xp':[1]*100,'sensor.visual':[1]*100,'sensor.random':[1]*100}),
        units=[dict(name='u',id=10,contact_id='AA',at=[10,10,0],character=101,started=False,in_character=False,measured_mass=51200,repair=dict(stall=True),
            sections=[dict(index=i,internal=10,internal_orig=10,armor=10,armor_orig=10,rear=0,rear_orig=0) for i in range(8)])],
        characters=[dict(id=101,name='Tech',tech=True,location=10,values={'Build':5,'Reflexes':5,'Intuition':5,'Learn':5,'Technician-Battlemech':6,'Technician-Weapons':6,'Technician-Aerospace':6})],actions=[])


def cmd(name,args='',unit='u'):return dict(op='command',unit=unit,name=name,args=args)
def advance(seconds):return dict(op='advance',seconds=seconds)
def inspect():return dict(op='inspect')
def repair(kind,**values):return dict(op='repair',kind=kind,**values)
def slot(loc,pos,**values):return dict(op='section',unit='u',value=dict(index=loc,slots=[dict(index=pos,**values)]))
def stock(d,part,count):d['repair_economy']['objects'].append(dict(id=1000,ECONPARTS=f'[{part},0,{count}]'))
def unit(state):return state['units']['u']
def inv(state,identity=1000):return state['economy']['objects'][str(identity)].get('ECONPARTS','')


def run_cli(d,allow_failures=False):
    p=subprocess.run([sys.executable,'-m','tools.repair_economy'],input=json.dumps(d),text=True,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    assert p.returncode==0,p.stderr
    output=json.loads(p.stdout)
    if not allow_failures:
        for action,result in zip(d['actions'],output['results']):
            assert not isinstance(result,dict) or (result.get('ok',True) and result.get('accepted',True) and not result.get('error')),(action,result)
    return output


def run(w,initial,operation):
    operations=('fix internal then armor then inspect manifest','add stock then replacegun then repairs then advance','unload then advance then reload then advance','remove part then advance then remove section then advance','save then fresh process load advance','persist then fresh process load','ordinary commands and advance','load original fixarmor then save template and reload','repair diagnostics then combat inspection','existing pickup command','cost readout before and after empty inventory setup')
    if operation not in operations:return False
    with tempfile.TemporaryDirectory(dir='./tmp',prefix='repair-journey-') as root:
        d=document(root);a=d['actions'];section=d['units'][0]['sections'][4]
        if operation==operations[0]:
            section.update(internal=8,armor=7)
            d['repair_economy']['objects']=[dict(id=1000,ECONPARTS='[546,0,2],[547,0,3]')]
            a.extend([cmd('fixinternal','CT'),advance(1079),inspect(),advance(1),inspect(),cmd('fixarmor','CT'),advance(540),repair('actor',actor=101,values=dict(location=1000)),cmd('manifest')])
            o=run_cli(d);before=o['results'][2];middle=o['results'][4];end=o['state']
            check(w,'2 internal and3 armor consumed with real sequential restoration',unit(before)['sections'][4]['internal']==9 and unit(middle)['sections'][4]['internal']==10 and unit(middle)['sections'][4]['armor']==7 and unit(end)['sections'][4]['armor']==10 and inv(end)=='' and o['results'][-1]['result']['rows']==[])
        elif operation==operations[1]:
            weapon=get_weapon('IS.LargeLaser');part=source_id(i2weapon(weapon.index))
            section['slots']=[dict(index=i,type=i2weapon(weapon.index),firemode=int(F.BROKEN_MODE)) for i in (0,1)]
            a.extend([repair('actor',actor=101,values=dict(location=1000)),cmd('Raddstuff',weapon.name+' 1'),repair('actor',actor=101,values=dict(location=10)),cmd('replacegun','CT 1'),cmd('repairs'),inspect(),advance(7199),inspect(),advance(1)])
            o=run_cli(d);queued=o['results'][5];early=o['results'][7];end=o['state']
            check(w,'command sees added stock and repairs at due without second debit',inv(queued)==inv(end)=='' and len(queued['repair_jobs'])==1 and o['results'][4]['result'][0]['type']==44 and unit(early)['sections'][4]['slots'][0]['firemode']&int(F.BROKEN_MODE) and all(not s['firemode']&int(F.BROKEN_MODE) for s in unit(end)['sections'][4]['slots'][:2]))
        elif operation==operations[2]:
            section['slots']=[dict(index=0,type=i2ammo(get_weapon('CL.ATM-6').index),data=10)]
            a.extend([cmd('unload','CT 1'),inspect(),advance(600),inspect(),cmd('reload','CT 1'),inspect(),advance(600)])
            o=run_cli(d);end=o['state']
            check(w,'returned bin commodity funds refill and net stock0',inv(o['results'][1])=='' and bool(inv(o['results'][3])) and inv(o['results'][5])==inv(end)=='' and unit(o['results'][3])['sections'][4]['slots'][0]['data']==0 and unit(end)['sections'][4]['slots'][0]['data']==10)
        elif operation==operations[3]:
            part=i2special(Special.CASE);d['units'][0]['sections'][0]['slots']=[dict(index=4,type=part)]
            d['units'][0]['specials']=int(Specials.CARGO_TECH)
            a.extend([cmd('removepart','LA 5'),inspect(),advance(2400),inspect(),cmd('removesection','LA'),inspect(),advance(7200),inspect(),cmd('startup'),advance(30),cmd('loadcargo','Internal 1')])
            o=run_cli(d);end=o['state']
            check(w,'salvage appears only after each real event and can be loaded',inv(o['results'][1])=='' and f'[{part},0,1]' in inv(o['results'][3]) and inv(o['results'][3])==inv(o['results'][5]) and '[546,0,10]' in inv(o['results'][7]) and '[546,0,1]' in inv(end,10))
        elif operation==operations[4]:
            fake=initial.startswith('fake')
            if fake:
                part=i2special(Special.CASE);section['slots']=[dict(index=0,type=part,firemode=int(F.BROKEN_MODE))];stock(d,part,2);d['random']['streams']['tech_rolls']=[2,12]
                a.extend([cmd('replacepart','CT 1'),repair('save')]);remaining=4020
            else:
                section['armor']=7;stock(d,547,3);a.extend([cmd('fixarmor','CT'),advance(180),repair('save')]);remaining=360
            first=run_cli(d);fresh=deepcopy(d);fresh['characters']=[];fresh['repair_economy']['objects']=[]
            if not fake:fresh['units'][0]['sections'][4]['armor']=8
            fresh['actions']=[repair('load'),inspect(),advance(remaining-1),inspect(),advance(1),inspect(),advance(60)]
            second=run_cli(fresh);loaded=second['results'][1];early=second['results'][3];atdue=second['results'][5];end=second['state']
            check(w,'remaining points restored once without renewed resource charge',not fake and unit(early)['sections'][4]['armor']==9 and unit(atdue)['sections'][4]['armor']==unit(end)['sections'][4]['armor']==10 and not end['repair_jobs'] and inv(first['state'])==inv(end)=='' and second['draws']==[])
            check(w,'conflict persists until due and part remains broken',fake and len(loaded['repair_jobs'])==len(early['repair_jobs'])==1 and not atdue['repair_jobs'] and bool(unit(end)['sections'][4]['slots'][0]['firemode']&int(F.BROKEN_MODE)) and inv(first['state'])==inv(end) and second['draws']==[])
            o=second
        elif operation==operations[5]:
            d['repair_economy']['objects']=[dict(id=1000,ECONPARTS='[546,0,8]'),dict(id=101,TECHTIME='7200')];a.append(repair('persist'))
            first=run_cli(d);d['characters']=[];d['repair_economy']['objects']=[];d['actions']=[repair('objects')];o=run_cli(d)
            check(w,'inventory and absolute TECHTIME retained across process',inv(o['state'])=='[546,0,8]' and o['state']['economy']['objects']['101']['TECHTIME']=='7200' and o['state']['characters']['101']['tech'])
        elif operation==operations[6] or operation==operations[9]:
            mw=operation==operations[9];d['units'][0].update(started=True,in_character=True,team=1)
            for loc in (0,1):d['units'][0]['sections'][loc]['slots']=[dict(index=0,type=i2special(Special.SHOULDER_OR_HIP)),dict(index=3,type=i2special(Special.HAND_OR_FOOT_ACTUATOR))]
            peer=dict(name='v',id=11,contact_id='BB',at=[10,10,0],started=False,in_character=True,team=1,measured_mass=51200)
            if mw:
                peer.update({'class':'MW','character':102});d['characters'].append(dict(id=102,name='Walker',location=11,values={'Bruise':2}))
            d['units'].append(peer)
            a.extend([dict(op='cache',unit='u',target='v',flags=3),cmd('pickup','BB'),inspect()])
            if mw:a.insert(1,inspect())
            else:a.extend([cmd('speed','10'),advance(5),inspect(),cmd('dropoff'),inspect(),advance(5)])
            o=run_cli(d);end=o['state']
            if mw:check(w,'occupant transfer and health semantics preserved',end['characters']['102']['location']==10 and end['characters']['102']['categories']['health']==o['results'][1]['characters']['102']['categories']['health'] and unit(end)['repair']['carrying']<=0)
            else:
                moved=o['results'][5];released=o['results'][7]
                check(w,'shared carried unit follows then releases and stops following',unit(moved)['at']==moved['units']['v']['at'] and unit(moved)['fx']==moved['units']['v']['fx'] and (unit(end)['fx'],unit(end)['fy'])!=(end['units']['v']['fx'],end['units']['v']['fy']) and (end['units']['v']['fx'],end['units']['v']['fy'])==(released['units']['v']['fx'],released['units']['v']['fy']) and unit(end)['repair']['carrying']==-1)
        elif operation in operations[7:9]:
            from acceptance.six_location_aerofighters.workflows import document as original
            d=original(root);a=d['actions'];d['characters'][0]['tech']=True;d['characters'][0]['values']['Technician-Aerospace']=6
            d['units'][0]['repair']=dict(stall=True);d['repair_economy']=dict(root=root+'/economy',objects=[dict(id=1000,ECONPARTS='[547,0,5]')]);d['random']['streams']['tech_rolls']=[12]
            a.append(inspect());loaded_index=len(a)-1
            if operation==operations[7]:
                a.extend([dict(op='section',unit='u',value=dict(index=0,armor=19)),cmd('fixarmor','Nose'),advance(900),inspect(),dict(op='template',unit='u',kind='save',reference='saved',clock=0),dict(op='template',kind='read',reference='saved')])
                o=run_cli(d);loaded=o['results'][loaded_index];repaired=o['results'][-3];text=o['results'][-1]['text']
                d2=original(root+'/reload');d2['construction']['files']={'CHP-W5':text};d2['repair_economy']=dict(root=root+'/reload/economy');d2['characters'][0]['tech']=True
                other=run_cli(d2)
                same=all(unit(other['state'])[k]==unit(loaded)[k] for k in ('sections','weapons','max_speed','sink_capacity','fuel','si'))
                check(w,'six named sections original stats preserved and repaired armor visible before design reload',same and unit(repaired)['sections'][0]['armor']==24 and [s['armor'] for s in unit(loaded)['sections'][:6]]==[24,15,15,30,16,20])
            else:
                a.extend([dict(op='place',unit='u',at=[50,50,10]),dict(op='diagnose',unit='u',kind='damage',options=dict(section='Engine',amount=20)),dict(op='repair_diagnose',unit='u',kind='damage_table'),cmd('weaponstatus'),inspect()])
                o=run_cli(d);end=o['state'];fighter=unit(end)
                check(w,'thrust0 fall behavior and armor-based destruction retained without SI substitution',fighter['max_speed']==fighter['speed']==0 and fighter['fallen'] and fighter['sections'][5]['armor']==0 and fighter['si']==0 and any(e['kind']=='FALL' for e in end['events']) and fighter['weapons'])
        else:
            a.extend([dict(op='diagnose',kind='CalcFasaCost',args=[]),repair('configure_object',values=dict(id=10,ECONPARTS='')),dict(op='diagnose',kind='CalcFasaCost',args=[])])
            o=run_cli(d);check(w,'identical FASA cost',o['results'][0]==o['results'][2] and o['results'][0]['value']>0)
        w['result']={'checks':w['checks'],'results_count':len(o['results'])}
        Path('./tmp/repair-last-workflow.json').write_text(json.dumps(o))
    return True
