"""Remaining lifecycle, persistence, and cache branches through public commands."""
from qa.construction_qa_common import *
from qa.construction_qa_numeric import blank

def run(a):
    for line,r in examples('lifecycle',3):
        actions=[T('list')];change=r['change']
        if change=='add-AS7-K-after-scan':actions+=[T('write','AS7-K',text=modern('AS7-K'))]
        elif change=='save-AS7-K-invalidates-cache':actions+=[T('save','AS7-K')]
        elif change=='delete-hit-and-retry':actions+=[T('delete','AS7-D')]
        actions+=[T('lookup',r['query'])]
        d=a.run(f'lifecycle/3-{line}',document(actions,{r['path']:modern('AS7-D')}),'ordinary')
        a.eq('source directory outcome',d['results'][-1]['path'],r['path'] if r['outcome'].endswith('hit') and change=='none' else 'AS7-K' if change=='save-AS7-K-invalidates-cache' else None)
    for n in (24,25,34,35):
        ref='A'*n;d=a.run(f'ordinary/09-length-{n}',document([T('list'),T('lookup',ref),T('lookup','./'+ref)],{ref:modern(ref)}),'ordinary')
        a.eq('cache truncation',d['results'][0]['entries'][0]['reference'],ref[:34]);a.eq('cache readable hit',d['results'][1]['path'],ref);a.eq('explicit path bypass',d['results'][2]['path'],ref)
    base='COLLISION'+'x'*15;refs=[base+'A',base+'B','Custom/'+base+'a']
    d=a.run('ordinary/09-collisions',document([T('lookup',base.lower())],{r:modern(r) for r in refs}),'ordinary');a.eq('stable source equivalence class',d['results'][0]['ambiguities'],refs);a.eq('stable winner',d['results'][0]['path'],refs[0])
    actions=[D('load_reference','QA50'),T('load','QA50'),E('setarmor','CT 1 1'),D('load_reference','QA50'),D('load_reference','MISSING'),T('write','QA50',text=modern().replace('Armor { 24 }','Armor { 31 }')),D('load_reference','QA50')]
    d=a.run('diagnostic/09-reference-cache',document(actions,{'QA50':modern()}));r=d['results'];a.eq('cached baseline independent',r[0],r[3]);a.eq('failed reference null',r[4],None);a.eq('failed reference reset',r[6]['sections'][4]['armor'],31)
    for direct in (False,True):
        u=blank('Spheroid_DropShip','Fly');d=a.run('legacy/class4-'+str(direct),document([D('load_legacy','OLD') if direct else T('load','OLD'),I()],{'OLD':legacy(cls=4,move=7)},units=[u]));armor=[s['armor'] for s in d['results'][-1]['units']['u']['sections']]
        a.eq('preload class4 permutation',armor,[20,21,22,25,23,24,26,27] if direct else list(range(20,28)))
    for kind,text in [('header','50 20'),('section','50 20 40 20 10 64.50 0.00 0\n20 8'),('part',legacy(triples={(0,1):(9999,0,0)}))]:
        d=a.run('legacy/partial-'+kind,document([D('load_legacy','BAD'),R()],{'BAD':text}));a.eq('legacy failure',d['results'][0]['ok'],False);a.eq('legacy partial tonnage',d['results'][1]['tonnage'],50 if kind!='header' else 50)
    for line,r in examples('weights',6):
        u=blank('AeroFighter','Fly');u.update(destroyed=r['destroyed']=='destroyed',crit_status=8192*int(r['valid']));u['construction']={'rtons':int(r['cached'])}
        args=[] if r['computed']=='1' else [int(r['computed'])]
        d=a.run(f'weights/6-{line}',document([dict(op='configure',values={'crit_status':8192*int(r['valid'])}),D('weight_cache',*args)],units=[u],construction={'dynspeed':r['dynamic']=='1'}));a.eq('cache value',d['results'][-1]['value'],int(r['result']));a.eq('recompute calls',d['results'][-1]['calls'],int(r['calls']))
    # Real ordinary mutations exercise the actual current-mass calculation and cache.
    actions=[T('load','QA50'),R(),E('repair','CT A 8'),R(),E('repair','CT A 24'),R(),E('reload','IS.AC/5 RT 1 +'),R()]
    d=a.run('ordinary/06-mass-invalidation',document(actions,{'QA50':modern()},ordinary=True),'ordinary');r=d['results'];initial=r[1]['current_weight'];a.eq('damage loses sixteen armor',r[3]['current_weight'],initial-1024);a.eq('repair restores mass',r[5]['current_weight'],initial);a.eq('half ammunition loses half ton',r[7]['current_weight'],initial-512);a.eq('design armor unaffected',r[3]['design_weight'],r[1]['design_weight'])
    # Save error paths leave the editor available for a subsequent successful save.
    d=a.run('ordinary/02-save-errors',document([T('load','QA50'),E('savetemp2','bad/name'),E('savetemp2','occupied'),E('settons','1'),E('savetemp2','HEAVY'),T('read','HEAVY')],{'QA50':modern(),'occupied/child':'x'}),'ordinary');r=d['results'];a.eq('slash rejected',r[1]['ok'],False);a.eq('directory I/O rejected',r[2]['ok'],False);a.eq('overweight still saved',r[4]['ok'],True);a.eq('overweight warning',any('Overweight' in m for m in d['state']['units']['u']['construction']['messages']),True)
    units=[{'name':'u','at':[3,3,0]},{'name':'v','at':[3,1,0],'team':2,'facing':180}]
    actions=[T('load','QA50'),T('load','QA50',unit='v'),dict(op='construction_pilot'),C('startup'),A(40),C('damage-section','LT 1 0 1'),C('damage-section','CT 1 0 1'),I(),E('repair','LT C 1'),E('repair','CT C 1'),I(),E('restore'),I()]
    doc=document(actions,{'QA50':modern()},units=units,ordinary=True);doc['random']['streams'].update(critical_rolls=[8,8],critical_slot=[0,0],enhanced_rolls=[12]*20,pilot_rolls=[12]*20)
    d=a.run('ordinary/03-weapon-engine-repair',doc,'ordinary');r=d['results'];damaged=r[7]['units']['u'];repaired=r[10]['units']['u'];restored=r[12]['units']['u']
    a.eq('ordinary engine hit',damaged['engine_heat'],5);a.eq('ordinary weapon damage',damaged['sections'][2]['slots'][0]['firemode']&1,1)
    a.eq('editor repairs engine',repaired['engine_heat'],0);a.eq('editor repairs weapon',repaired['sections'][2]['slots'][0]['firemode']&1,0);a.eq('live weapon restored',next(w['usable'] for w in repaired['weapons'] if w['name']=='IS.AC/5'),True)
    a.eq('baseline and other unit intact',[d['state']['templates']['QA50']['sections'][4]['armor'],r[10]['units']['v']['sections'][4]['armor']],[24,24]);a.eq('restore original ranges',[restored['engine_rating'],restored['scan_range'],restored['radio_range']],[200,20,100])
    for line,r in examples('lifecycle',1):
        u={'name':'u','construction':{'template_ref':'AS7-D','freq':[42]*16,'freqmodes':[3]*16,'chantitle':['QA']*16},'tics':[[0],[],[],[]],'heat':20,'target':9}
        d=a.run(f'lifecycle/1-{line}',document([T('load',r['reference']),R(),I()],{'AS7-D':modern('AS7-D'),'AS7-K':modern('AS7-K')},units=[u]),'ordinary');read=d['results'][1];s=d['results'][2]['units']['u'];retain=r['retention']=='retained'
        a.eq('channel retention',read['channels']['freq'],[42 if retain else 0]*16);a.eq('TIC retention',s['tics'],[[0],[],[],[]] if retain else [[],[],[],[]]);a.eq('reset heat target pilot',[s['heat'],s['target'],s['pilot_present']],[0,-1,False])
    for line,r in examples('lifecycle',2):
        actions=[T('load','QA50'),dict(op='construction_pilot'),C('startup')]
        if r['file']=='missing-reference':actions += [dict(op='construction_value',values={'template_ref':''})]
        operation=T('load','MISSING' if r['file']=='missing' else 'QA50') if r['operation']=='loadnew' else E('restore')
        d=a.run(f'lifecycle/2-{line}',document(actions+[operation,I()],{'QA50':modern()},ordinary=True),'ordinary');res=d['results'][-2];state=d['results'][-1]
        a.eq('lifecycle result',res['ok'],r['result']=='success');a.eq('startup cleanup policy',any(e['kind']=='STARTUP' for e in state['events']),r['events']!='all-unit-events-cancelled')
    missing=OUT/'ordinary/09-missing-root/never-created'
    assert not missing.exists()
    d=a.run('ordinary/09-missing-root',document([T('list'),T('lookup','ABSENT'),T('save','SAVE'),I()],construction={'create_root':False}),'ordinary',root=missing)
    a.eq('missing-root empty discovery',d['results'][0]['entries'],[]);a.eq('missing-root fallback',d['results'][1]['path'],None);a.eq('missing-root save error',d['results'][2]['ok'],False)
    bad=[D('parse_bits','unknown','fire','RearMount'),D('parse_bits','strict','unknown','RearMount'),D('parse_bits','strict','fire'),D('read_desc'),D('section_index',7),D('short_section',8),D('load_fields'),D('load_reference'),D('weight_cache',1,2)]
    d=a.run('diagnostic/affordance-errors',document(bad+[E('settons','55'),R()]));a.eq('new diagnostic errors remain structured',[r.get('ok') for r in d['results'][:len(bad)]],[False]*len(bad));a.eq('session remains usable',d['results'][-1]['tonnage'],55)
    d=a.run('ordinary/06-fired-current-mass',document([T('load','QA50'),R()]+firing()+[R()],{'QA50':modern()},units=[{'name':'u','at':[3,3,0]},{'name':'v','at':[3,1,0],'team':2,'facing':180}],ordinary=True),'ordinary')
    a.eq('live fired mass uses actual remaining ammo',d['results'][-1]['current_weight'],d['results'][1]['current_weight']-52)
    a.eq('design ammo still full capacity',d['results'][-1]['design_weight'],d['results'][1]['design_weight'])
