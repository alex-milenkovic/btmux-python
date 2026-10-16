"""Executable ordinary procedures 1–4, 7–9, 11–13 from construction QA."""
from qa.construction_qa_common import *
import re

def firing_assertions(a,d,expected_ammo=19,damage=5):
    hits=[r for r in d['results'] if isinstance(r,dict) and 'attack' in r]
    a.eq('ordinary fire accepted',bool(hits) and hits[-1]['accepted'],True)
    if hits:a.eq('real damage',hits[-1]['attack']['damage_dealt'],damage)
    snapshots=[r for r in d['results'] if isinstance(r,dict) and 'units' in r]
    if len(snapshots)>=2:
        shot=snapshots[-2]['units']['u'];end=snapshots[-1]['units']['u']
        a.eq('live ammunition after shot',shot['sections'][3]['slots'][0]['data'],expected_ammo)
        ac=next(w for w in shot['weapons'] if 'AC' in w['name']);last=next(w for w in end['weapons'] if 'AC' in w['name'])
        a.eq('recycle starts',ac['recycle'],40);a.eq('recycle completes',last['recycle'],0)
        a.eq('AC5 firing heat',shot['weap_heat'],1.0)

def run(a):
    targets=[{'name':'u','at':[3,3,0]},{'name':'v','at':[3,1,0],'team':2}]
    for cls,move in [('Mech','Biped'),('Vehicle','Track')]:
        d=a.run('ordinary/01-'+cls,document([T('lookup','qa50'),T('load','qa50'),R()]+firing(),{'QA50':modern(unit=cls,move=move)},units=targets,ordinary=True),'ordinary')
        a.eq('case-insensitive discovery',d['results'][0]['path'],'QA50');a.eq('loaded',d['results'][1]['ok'],True)
        r=d['results'][2];s=d['state']['units']['u']
        for k,v in [('tonnage',50),('max_speed',64.5),('computer',2),('radio',3),('radio_type',5),('scan_range',20),('tac_range',20),('lrs_range',40),('radio_range',100)]:a.eq(k,r[k],v)
        a.eq('engine rating',s['engine_rating'],200)
        a.eq('source/runtime namespace',[r['slots'][2][0][k] for k in ('source_part_id','runtime_part_id')],[96,20])
        a.eq('full AC5 critical run',sum(x['source_part_id']==96 for x in r['slots'][2]),4 if cls=='Mech' else 1)
        a.eq('current and original armor',[[z['armor'],z['armor_orig']] for z in s['sections'][:5]],[[24,24]]*5)
        firing_assertions(a,d)
    actions=[T('load','QA50'),E('settons','50'),E('setspeed','6'),E('setradio','4'),E('setarmor','CT 31 16 6'),E('addweap','IS.MediumLaser RT 2'),R(),E('addspecial','empty RT 2'),E('addspecial','HeatSink RT 3 7'),E('addspecial','empty RT 3'),E('reload','IS.AC/5 RT 1'),E('repair','CT A 7'),E('savetemp2','SAVED',clock='fixed',caller='Independent QA',caller_id=71),E('savetemp','OLD'),T('read','SAVED'),T('read','OLD'),R()]
    d=a.run('ordinary/02-edit-save',document(actions,{'QA50':modern()},ordinary=True),'ordinary');r=d['results']
    a.eq('all editor operations succeeded',[x.get('ok') for x in r[1:6]],[True]*5)
    a.eq('added live weapon count',len(r[6]['payload'].split('|')),3)
    saved=r[-3]['text'];old=r[-2]['text']
    a.eq('fixed caller comment','Saved by: Independent QA(#71) at fixed' in saved,True)
    a.eq('one-based AC run',bool(re.search(r'CRIT_1-4\s+\{ IS.AC/5',saved)),True)
    a.eq('modern original CT',bool(re.search(r'Center_Torso\s+Armor\s+\{ 31 \}',saved)),True)
    a.eq('legacy current CT',old.splitlines()[1+4*13].split()[:3],['7','16','6'])
    d=a.run('ordinary/02-fresh-reload',document([T('load','SAVED'),R()]+firing(),units=targets,ordinary=True),'ordinary',root=OUT/'ordinary/02-edit-save/templates')
    a.eq('saved radio reload',d['results'][1]['radio_range'],120);a.eq('saved CT layout',d['state']['units']['u']['sections'][4]['armor'],31);firing_assertions(a,d)
    for special,radio in [(32768,77),(16384,None),(8192,90),(4196,80),(32,55),(33,55)]:
        text=legacy(special,radio,triples={(0,4):(79,0,0),(2,0):(96,7,32),(3,0):(288,3,128)})
        name=f'ordinary/04-legacy-{special}';d=a.run(name,document([T('load','LEGACY'),R(),T('save','OLD',legacy=True),T('read','OLD')],{'LEGACY':text}),'ordinary')
        r=d['results'][1];u=d['state']['units']['u'];a.eq('legacy masks',u['specials'],special & ~(32768|16384|8192|4196));a.eq('legacy radio',u['radio_range'],radio if radio is not None else 80)
        a.eq('legacy source IDs',[(r['slots'][loc][pos]['source_part_id'],r['slots'][loc][pos]['runtime_part_id']) for loc,pos in [(0,4),(2,0),(3,0)]],[(79,2),(96,20),(288,212)])
        a.eq('config4 cleared',[s['config']&4 for s in u['sections']],[0]*8)
        a.eq('legacy fields',len(d['results'][-1]['text'].split()),8+8*(4+12*3)+3)
        a.eq('speed formatting','64.50 0.00' in d['results'][-1]['text'].splitlines()[0],True)
        reloaded=a.run(name+'-fresh',document([T('load','OLD'),R()]),'ordinary',root=OUT/name/'templates')
        a.eq('legacy preserved critical data',reloaded['results'][1]['slots'][3][0]['data'],3)
        a.eq('legacy absent ammo mask',reloaded['results'][1]['slots'][3][0]['ammo'],0)
    for bad,text in [('missing',None),('modern','Tons { 55 }\nLeft_Torso\nCRIT_1 { IS.MediumLaser - - 3 }\nCRIT_13 { HeatSink - - 3 }\n'),('legacy','55 20 40 20 10 64.50 0.00 0\n20 8 0 0\n79 7 0\n')]:
        files={'QA50':modern()}
        if text is not None:files['BAD']=text
        actions=[T('load','QA50'),T('load','BAD'),I(),R(),T('load','QA50')]+firing()
        d=a.run('ordinary/07-failed-'+bad,document(actions,files,units=targets,ordinary=True),'ordinary');r=d['results']
        a.eq('failed load',r[1]['ok'],False);u=r[2]['units']['u']
        a.eq('preserved live identity and position',[u['id'],u['map'],u['at']],[1,'main',[3,3,0]])
        a.eq('pilot removed',u['pilot_present'],False);a.eq('old AC absent',any(w['name']=='IS.AC/5' for w in u['weapons']),False)
        a.eq('partial tonnage',r[3]['tonnage'],0 if bad=='missing' else 55);firing_assertions(a,d)
    # Source cache behavior: ordinary file actions, no private directory API.
    actions=[T('list'),T('write','NEW',text=modern('NEW')),T('lookup','NEW'),T('save','SAVE'),T('lookup','NEW'),T('delete','NEW'),T('lookup','NEW'),T('lookup','nested/DEEP'),T('lookup','HIDDEN'),T('reset'),T('list')]
    d=a.run('ordinary/09-cache',document(actions,{'ROOT':modern('ROOT'),'Custom/CHILD':modern('CHILD'),'nested/DEEP':modern('DEEP'),'.hidden/HIDDEN':modern('HIDDEN'),'Custom/nested/DEEPER':modern('DEEPER')}),'ordinary');r=d['results']
    a.eq('miss does not rescan',r[2]['path'],None);a.eq('save invalidates cache',r[4]['path'],'NEW');a.eq('deleted hit rescans',r[6]['path'],None);a.eq('explicit slash lookup',r[7]['path'],'nested/DEEP');a.eq('hidden not scanned',r[8]['path'],None)
    # Privilege guard ordering and editor isolation.
    editors=[{'name':'a','id':70,'target':'u'},{'name':'b','id':71,'target':'v'},{'name':'null','id':72,'allocated':False},{'name':'unset','id':73},{'name':'missing','id':74,'target':999}]
    actions=[E('settons','99',editor='null',privilege=False),E('settons','99',editor='null'),E('resetcrits',editor='unset'),E('resetcrits',editor='missing'),E('settons','55',editor='a'),E('settons','65',editor='b'),E('settarget','v',editor='a'),E('setradio','4',editor='a'),E('settons','',editor='b'),E('settarget','u extra',editor='b'),R('u'),R('v')]
    d=a.run('ordinary/11-privilege',document(actions,units=targets,editors=editors),'ordinary');r=d['results']
    a.eq('privilege first',r[0]['messages'],["I'm sorry Dave, can't do that."]);a.eq('allocation guard',r[1]['messages'],['There is a problem with that item.','The data is not properly allocated.','Please notify a director of this.'])
    a.eq('unset target',r[2]['messages'],['You must set a target first!']);a.eq('missing target guard',r[3]['messages'],r[1]['messages'])
    a.eq('independent unit edits',[r[-2]['tonnage'],r[-1]['tonnage']],[55,65]);a.eq('retarget persists',d['state']['construction']['editors']['b']['target'],'v')
