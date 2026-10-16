"""Normal acceptance workflows executed through the public subprocess CLI."""
import json,subprocess,sys
from pathlib import Path
from copy import deepcopy
from . import step,base,eq
from data.character_values import code
from data.characters import CharacterStore,SKILLS
from entities.mech import FireMode as F,CritStatus as C,MechStatus as S,MechStatus2 as S2

@step(r'an isolated public CLI process with independently derived source inputs and writable scratch storage')
def fresh(w):base(w);w['runs']=[]
@step(r'documented procedure (\S+) has independent source expectations')
def procedure(w,name):w['procedure']=name

def document(w):
    return {'pilots':{'root':str(w['root']/'public-characters'),'radio_draws':[123456,654321,111111]},
        'construction':{'root':str(w['root']/'templates')},'file_root':str(w['root']/'maps'),
        'config':{'periodic_updates':False,'extended_piloting':False,'extended_gunnery':False},
        'random':{'seed':11},'map':{'size':[15,15]},
        'units':[unit('u',10,101),unit('v',20,None)],
        'characters':[character(101,'Alice',10)],'actions':[]}
def character(ident,name,location):
    return {'id':ident,'name':name,'location':location,'wizard':True,'values':{'Build':5,'Reflexes':5,'Intuition':5,'Learn':5,'Charisma':5,'Piloting-Battlemech':8,'Piloting-BSuit':8,'Gunnery-BSuit':8,'Gunnery-Battlemech':8,'Small_Arms':8,'Running':8}}
def unit(name,ident,char):
    return {'name':name,'id':ident,'contact_id':(name.upper()*2)[:2],'team':1,'started':True,'in_character':True,'at':[3,3,0],
        'sections':[{'index':i,'armor':100,'internal':30,'internal_orig':30} for i in range(8)],
        **({'character':char,'personnel':{'official_pilot':char}} if char else {})}
def command(name,*args,unit='u',**options):return {'op':'command','unit':unit,'name':name,'args':list(args),**options}
def inspect():return {'op':'inspect'}
def advance(n):return {'op':'advance','seconds':n}
def char(kind,**values):return {'op':'character','kind':kind,'caller':101,**values}
def configure(**values):return {'op':'configure','unit':'u','values':values}
def run(w,doc):
    index=len(w['runs']);(w['root']/f'workflow-{index}.input.json').write_text(json.dumps(doc,indent=2))
    artifacts=Path('./tmp/pilots-workflows')/w.get('procedure','development')
    artifacts.mkdir(parents=True,exist_ok=True)
    (artifacts/f'{index}.input.json').write_text(json.dumps(doc,indent=2)+'\n')
    result=subprocess.run([sys.executable,'-m','tools.pilots'],input=json.dumps(doc),text=True,capture_output=True)
    eq(result.returncode,0 if result.returncode==0 else ('CLI failure',result.stderr))
    output=json.loads(result.stdout);w['runs'].append(output)
    (artifacts/f'{index}.output.json').write_text(result.stdout)
    (artifacts/f'{index}.stderr.txt').write_text(result.stderr)
    (w['root']/f'workflow-{index}.output.json').write_text(json.dumps(output,indent=2))
    return output

def success(result):
    assert isinstance(result,dict),result
    if 'ok' in result:eq(result['ok'],True)
    elif 'accepted' in result:eq(result['accepted'],True)
    else:assert 'error' not in result,result

def xp(w,skill,ident=101):return CharacterStore(w['root']/'public-characters').retrieve(ident,SKILLS).xp[code(skill)]%16777216

def fire_setup(doc,personal=False):
    doc['units'][0]['weapons']=[{'name':'PC.SMG' if personal else 'IS.MediumLaser','section':0,'critical':4}]
    doc['units'][1]['at']=[3,2,0];doc['units'][1]['team']=2


def character_roundtrip(w):
    d=document(w);d['units']=[]
    d['actions']=[char('set',name='Running',amount=4),char('set',name='Toughness',amount=1),char('save'),char('status')]
    r=run(w,d);eq(r['state']['characters']['101']['categories']['advs'],'Lives:1/Tough:1/')
    assert 'Runni:4/' in r['state']['characters']['101']['categories']['skills']
    d['characters']=[];d['actions']=[char('get',name='Running'),char('get',name='Toughness'),char('skill',name='Running')]
    r=run(w,d);eq(r['results'][:2],[4,1]);eq(r['results'][2]['target'],4)

def skills_and_rolls(w):
    d=document(w);fire_setup(d);d['actions']=[char('target',name='Gunnery-Battlemech'),command('sight','0','VV'),command('fire','0','VV'),
        {'op':'diagnose','kind':'MadePilotSkillRoll','unit':'u','args':[0]},inspect()]
    r=run(w,d);eq(r['results'][0],0);shot=r['results'][2]['attack'];assert shot.get('hit'),shot
    eq(shot['bth'],r['results'][1]['attack']['bth']);eq(r['state']['units']['u']['shots_fired'],1)
    eq(r['results'][3]['success'],True);eq(r['results'][3]['target'],0)
    assert r['state']['units']['v']['damage_taken']>0
    names=[x['name'] for x in r['draws']];eq(names.count('attack_rolls'),2);eq(names.count('pilot_rolls'),1)
    eq(r['state']['random']['total_rolls'],sum(r['state']['random']['histogram']))

def xp_progression(w):
    d=document(w);fire_setup(d);d['pilots']['xp']={'oldxpsystem':False,'xp_modifier':100,'defaultweapdam':5,'defaultweapbv':120,'use_pilot_bv':False,'xpgain_cap':10}
    d['actions']=[char('threshold',args='Gunnery-Battlemech 1'),command('fire','0','VV'),char('save'),inspect()]
    r=run(w,d);assert r['results'][1].get('attack',{}).get('hit'),r['results'][1]
    requests=r['state']['units']['u']['xp_requests'];assert any(q['producer']=='gun' and q['applied'] for q in requests),requests
    amount=xp(w,'Gunnery-Battlemech');assert amount>0
    d['characters']=[];d['actions']=[char('get',name='Gunnery-Battlemech',flag=2)];eq(run(w,d)['results'][0],amount)

def conscious_injuries(w):
    d=document(w);d['units']=d['units'][:1];d['characters'][0]['wizard']=False
    d['random']={'streams':{'character_d6':[1,1,6,6,6,6,6,6]}}
    d['actions']=[{'op':'personnel','kind':'head','unit':'u','amount':1},inspect(),
        {'op':'personnel','kind':'head','unit':'u','amount':1},inspect(),advance(30),inspect(),
        {'op':'personnel','kind':'lethal','unit':'u','amount':30},{'op':'personnel','kind':'lethal','unit':'u','amount':2},inspect()]
    r=run(w,d);first,again,recovered,dead=(r['results'][i] for i in (1,3,5,8))
    eq(not bool(first['units']['u']['status']&int(S.UNCONSCIOUS)),False);eq(not bool(again['units']['u']['status']&int(S.UNCONSCIOUS)),False)
    a=[e['deadline'] for e in first['events'] if e['kind']=='RECOVERY'];b=[e['deadline'] for e in again['events'] if e['kind']=='RECOVERY'];eq(a,b)
    eq(not bool(recovered['units']['u']['status']&int(S.UNCONSCIOUS)),True);eq(dead['units']['u']['destroyed'],True)
    eq(dead['characters']['101']['alive'],False)
    d=document(w);d['characters']=[character(103,'NonIC',10)];d['units']=d['units'][:1];d['units'][0]['character']=103;d['units'][0]['in_character']=False
    d['random']={'streams':{'character_d6':[6,6]}};d['actions']=[{'op':'personnel','kind':'head','unit':'u','amount':1},inspect()]
    r=run(w,d);eq(r['state']['units']['u']['pilot_hits'],1)

def manual_ejection(w):
    d=document(w);d['construction']['catalog']=True;d['units']=d['units'][:1];d['actions']=[command('eject'),inspect(),command('speed','walk',unit='mw1001'),advance(2),inspect()]
    r=run(w,d);success(r['results'][0]);ident=r['results'][0]['unit'];state=r['state'];mw=state['units']['mw'+str(ident)]
    eq(state['characters']['101']['location'],ident);eq(mw['personnel']['official_pilot'],101)
    eq(mw['template_ref'],'MechWarrior');eq(state['units']['u']['destroyed'],True)
    assert state['units']['u']['sections'][7]['slots'][2]['firemode']&int(F.DESTROYED_MODE)
    eq(state['personnel']['radio'],[{'raw':123456,'channel':123456}]);success(r['results'][2]);assert mw['speed']>0

def personal_equipment(w):
    d=document(w);d['construction']['catalog']=True;d['config']['periodic_updates']=True
    d['units'][1]['class']='MW';d['units'][1]['team']=2;d['units'][1]['at']=[3,2,0]
    d['characters'][0]['pcequip']='1234 PC.SMG PC.LaserRifle 10 10'
    d['actions']=[command('eject'),advance(3),inspect(),command('fire','0','VV',unit='mw1001'),inspect()]
    r=run(w,d);success(r['results'][0]);before=r['results'][2]['units']['mw1001'];after=r['state']['units']['mw1001']
    assert before['crit_status']&int(C.PC_INITIALIZED)
    assert any(s['internal']>0 for s in before['sections']);success(r['results'][3]);eq(after['shots_fired'],1)
    assert r['results'][3]['attack']['hit'],r['results'][3]
    assert any(draw['name']=='personal_variation' for draw in r['draws']),r['draws']

WORKFLOWS={'character-roundtrip':character_roundtrip,'skills-and-rolls':skills_and_rolls,'xp-progression':xp_progression,
    'conscious-injuries':conscious_injuries,'manual-ejection':manual_ejection,'personal-equipment':personal_equipment}
@step(r'the complete ordinary workflow executes through public commands and clocks')
def execute(w):WORKFLOWS[w['procedure']](w);w['verified']=True
@step(r'evidence proves (\S+)')
def evidence(w,expected):eq(w['verified'],True);assert w['runs'];w['evidence']=expected

def pilot_exit_entry(w):
    d=document(w);d['construction']['catalog']=True;d['units'][0]['started']=False
    # Map1000 is the highest allocated local object; creation allocates1001.
    d['config']['periodic_updates']=True
    d['actions']=[command('disembark'),inspect(),advance(3),
        command('embark','VV',unit='mw1001'),inspect()]
    r=run(w,d);success(r['results'][0]);eq(r['results'][0]['unit'],1001)
    eq(r['results'][1]['characters']['101']['location'],1001);success(r['results'][3])
    eq(r['state']['characters']['101']['location'],20);eq(r['state']['units']['u']['destroyed'],False)
    d=document(w);d['construction']['catalog']=True;d['pilots']['root']=str(w['root']/'passenger-characters');d['characters'].append(character(102,'Bob',10));d['units'][0]['at']=[3,3,2]
    d['actions']=[command('disembark',actor=102),inspect()]
    r=run(w,d);success(r['results'][0]);mw='mw'+str(r['results'][0]['unit']);eq(r['state']['units'][mw]['at'][2],2)
    assert any(e['kind']=='FALL' and e['data2']==-4 and e['deadline']==3 for e in r['state']['events'])

def pickup_and_discard(w):
    d=document(w);d['pilots']['pickup_action']=0;d['units'][1]['class']='MW';d['units'][1]['team']=2
    d['characters'].append(character(102,'Stray',20));d['characters'][1]['wizard']=False
    d['characters'].append(character(103,'Wizard',20));d['actions']=[command('pickup','VV'),inspect(),advance(9),inspect(),advance(1),inspect()]
    r=run(w,d);success(r['results'][0]);a,b,c=(r['results'][i] for i in (1,3,5))
    eq(a['characters']['102']['location'],10);eq(a['characters']['102']['slave'],True);eq(a['characters']['103'].get('slave',False),False)
    eq(b['units']['v']['personnel']['hardcode'],True);eq(c['units']['v']['personnel']['hardcode'],False)
    eq(c['units']['v']['personnel']['location'],901);eq(c['units']['v']['personnel']['dark'],True)
    eq([e['kind'] for e in c['personnel']['trace'] if e['kind'] in ('leave','discard')],['leave','discard'])

def carrier_roundtrip(w):
    d=document(w);u,v=d['units'];u['tonnage']=5;u['measured_mass']=5*1024;u['carrying']=30;u['towed_unit']='tow'
    v['specials2']=0x80000;v['construction']={'car_max_ton':5,'cargo_space':800}
    tow=unit('tow',30,None);tow['tonnage']=3;tow['measured_mass']=3*1024;d['units'].append(tow)
    d['actions']=[command('embark','VV'),inspect(),command('udisembark'),inspect()]
    r=run(w,d);success(r['results'][0]);success(r['results'][2]);boarded,exited=r['results'][1],r['state']
    eq(boarded['personnel']['contents']['20'],[30,10]);eq(boarded['units']['u']['started'],False);eq(boarded['units']['u']['relationships']['carrying'],None)
    eq(exited['units']['u']['started'],True);eq(exited['units']['u']['at'],[3,3,0]);eq(exited['units']['v']['construction']['cargo_space'],500)
    eq([s['recycle'] for s in exited['units']['u']['sections']],[60]*8)
    d=document(w);d['pilots']['root']=str(w['root']/'breakout-characters');u,v=d['units'];u['tonnage']=5;u['measured_mass']=5*1024
    v['specials2']=0x80000;v['construction']={'car_max_ton':5,'cargo_space':500}
    d['actions']=[command('embark','VV'),command('shutdown',unit='v'),command('udisembark'),inspect()]
    r=run(w,d);success(r['results'][2]);eq(r['results'][2]['path'],'breakout');eq(r['state']['units']['u']['last_fall_levels'],4)

def ba_document(w):
    d=document(w);u,v=d['units'];u['class']='BA';u['infantry_specials']=7
    for s in u['sections']:
        if s['index']>=4:s['internal']=s['internal_orig']=s['armor']=0
    v['team']=2;return d

def swarm_and_host(w):
    d=ba_document(w);d['config']['periodic_updates']=True;d['units'][0]['weapons']=[{'name':'IS.MediumLaser','section':0,'critical':4}]
    d['actions']=[command('swarm','VV'),inspect(),command('speed','walk',unit='v'),advance(20),inspect(),
        command('fire','0','VV'),command('swarm','-'),inspect()]
    r=run(w,d);success(r['results'][0]);eq(r['results'][0]['success'],True)
    attached,moved,final=(r['results'][i] for i in (1,4,7));eq(attached['units']['u']['relationships']['swarm_target'],'v')
    eq(moved['units']['u']['at'][:2],moved['units']['v']['at'][:2]);eq(moved['units']['u']['at'][2],moved['units']['v']['at'][2]+1)
    success(r['results'][5]);success(r['results'][6]);eq(final['units']['u']['relationships']['swarm_target'],None)
    eq([s['recycle'] for s in final['units']['u']['sections'] if s['internal']],[20]*4)

def leg_attacks(w):
    for roll,effect in ((7,'damage4-with-critical-flag'),(8,'critical1'),(10,'critical2'),(12,'destroy-leg-then-critical3')):
        d=ba_document(w);d['pilots']['root']=str(w['root']/f'leg-{roll}-characters')
        d['random']={'streams':{'sensor.perception_xp':[5]*50,'leg_location':[1], 'pilot_rolls':[12]*30,
            'leg_critical':[roll],'damage_entry':[2]*30,'critical_rolls':[2]*30,'critical_slot':[0]*30,
            'critical_slots':[0]*30,'location_rolls':[7]*30,'hit_location_rolls':[7]*30,'fall_locations':[7]*30,'fall_directions':[1]*30,'character_d6':[6]*100}}
        d['actions']=[command('attackleg','VV'),inspect()]
        r=run(w,d);success(r['results'][0]);eq(r['results'][0]['effect'],effect)
        eq([s['recycle'] for s in r['state']['units']['u']['sections'] if s['internal']],[30]*4)
        if roll==7:eq(r['state']['units']['v']['damage_taken'],4)
        if roll==12:eq(r['state']['units']['v']['sections'][6]['internal'],0);eq(r['state']['units']['v']['fallen'],True)

def hiding_and_jettison(w):
    d=ba_document(w);d['units'][1]['started']=False;d['map']['hexes']=[{'at':[3,3],'terrain':'ROUGH','elevation':0}]
    d['units'][0]['infantry_specials']|=0x200
    d['units'][0]['weapons']=[{'name':'PC.SMG','section':0,'critical':4,'fire_mode':int(F.WILL_JETTISON_MODE)}]
    d['actions']=[command('hide'),advance(60),inspect(),advance(1),inspect(),command('jettison'),command('fire','0','VV'),command('jettison'),inspect()]
    r=run(w,d);success(r['results'][0]);eq(bool(r['results'][2]['units']['u']['crit_status']&int(C.HIDDEN)),False)
    eq(bool(r['results'][4]['units']['u']['crit_status']&int(C.HIDDEN)),True)
    eq(r['results'][5]['count'],1);eq(r['results'][6]['accepted'],False);eq(r['results'][7]['count'],0)
    d=ba_document(w);d['pilots']['root']=str(w['root']/'cancel-characters');d['map']['hexes']=[{'at':[3,3],'terrain':'ROUGH','elevation':0}]
    d['actions']=[command('hide'),advance(1),inspect()]
    r=run(w,d);success(r['results'][0]);eq(bool(r['state']['units']['u']['crit_status']&int(C.HIDDEN)),False)
    eq([e for e in r['state']['events'] if e['kind']=='HIDE'],[])

def automatic_escape(w):
    d=document(w);d['construction']['catalog']=True;d['units']=d['units'][:1];d['actions']=[{'op':'diagnose','unit':'u','kind':'reactor-explosion','options':{'attacker':'u'}},inspect()]
    r=run(w,d);state=r['state'];mw=next(name for name in state['units'] if name.startswith('mw'))
    eq(state['units'][mw]['at'][2],150);eq(state['characters']['101']['alive'],True);eq(state['units']['u']['sections'][7]['internal'],0)
    d=ba_document(w);d['construction']['catalog']=True;d['pilots']['root']=str(w['root']/'last-suit-characters');d['units']=d['units'][:1]
    for s in d['units'][0]['sections']:s['internal']=s['internal_orig']=1 if s['index']==7 else 0
    d['random']={'streams':{'suit_ejection':[25]}}
    d['actions']=[{'op':'diagnose','unit':'u','kind':'destroy-section','options':{'section':7}},inspect()]
    r=run(w,d);mw=next(name for name in r['state']['units'] if name.startswith('mw'));eq(r['state']['units'][mw]['at'][2],0)
    assert not any(e['kind']=='OOD' for e in r['state']['units'][mw]['events']);eq(r['state']['characters']['101']['alive'],True)

def shared_regressions(w):
    d=document(w);d['construction']['catalog']=True;d['actions']=[{'op':'template','kind':'load','unit':'u','reference':'WVR-6R'},
        {'op':'construction_readout','unit':'u'},{'op':'template','kind':'save','unit':'u','reference':'LocalWolverine'},
        {'op':'template','kind':'load','unit':'v','reference':'LocalWolverine'},inspect()]
    r=run(w,d);success(r['results'][0]);success(r['results'][2]);success(r['results'][3]);eq(r['state']['units']['u']['jump_mp'],5)
    eq(r['state']['units']['v']['jump_mp'],5);assert r['state']['maps']
    d=document(w);d['characters']=[];fire_setup(d)
    d['actions']=[{'op':'map_command','name':'weather.set','args':{'conditions':['blowing_sand'],'temperature':20,'enabled':True}},
        {'op':'map_command','name':'weather.show','args':{}},command('sight','0','VV'),command('fire','0','VV')]
    r=run(w,d);sight=r['results'][2]['attack'];shot=r['results'][3]['attack']
    eq(sight['bth_breakdown']['weather_mod'],2);eq(shot['bth_breakdown']['weather_mod'],2);eq(sight['bth'],shot['bth'])
    eq([x['name'] for x in r['draws']].count('attack_rolls'),2)

WORKFLOWS.update({'pilot-exit-entry':pilot_exit_entry,'pickup-and-discard':pickup_and_discard,'carrier-roundtrip':carrier_roundtrip,
    'swarm-and-host':swarm_and_host,'leg-attacks':leg_attacks,'hiding-and-jettison':hiding_and_jettison,
    'automatic-escape':automatic_escape,'shared-regressions':shared_regressions})
