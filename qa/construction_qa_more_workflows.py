"""Ordinary restoration, class traversal and mixed mode persistence procedures."""
from qa.construction_qa_common import *
from qa.construction_qa_workflows import firing_assertions
from qa.construction_qa_numeric import table
import re

def run(a):
    targets=[{'name':'u','at':[3,3,0]},{'name':'v','at':[3,1,0],'team':2,'facing':180}]
    # Damage through the command interface; restoration through the live editor.
    actions=[T('load','QA50'),T('load','QA50',unit='v'),C('damage-section','CT 5 0 0'),E('repair','CT A 19'),I(),E('restore'),I()]+firing()
    d=a.run('ordinary/03-restore-isolation',document(actions,{'QA50':modern()},units=targets,ordinary=True),'ordinary');r=d['results']
    a.eq('damaged first unit',r[4]['units']['u']['sections'][4]['armor'],19);a.eq('second untouched',r[4]['units']['v']['sections'][4]['armor'],24)
    a.eq('restored armor',r[6]['units']['u']['sections'][4]['armor'],24);a.eq('pilot removed on restore',r[6]['units']['u']['pilot_present'],False)
    baseline=d['state']['templates']['QA50'];a.eq('baseline armor intact',baseline['sections'][4]['armor'],24);a.eq('baseline bin intact',baseline['sections'][3]['criticals'][0]['data'],20);firing_assertions(a,d)
    for reference in ('QA50','qa50','OTHER'):
        u={'name':'u','construction':{'template_ref':'QA50','freq':[42]*16,'freqmodes':[3]*16,'chantitle':['QA']*16},'tics':[[0],[],[],[]]}
        actions=[T('load',reference),I(),R()]
        d=a.run('ordinary/03-reference-'+{'QA50':'exact','qa50':'case','OTHER':'new'}[reference],document(actions,{'QA50':modern(),'OTHER':modern('OTHER')},units=[u]),'ordinary');s=d['state']['units']['u']
        a.eq('TIC exact reference retention',s['tics'],[[0],[],[],[]] if reference=='QA50' else [[],[],[],[]])
        for key,value in [('freq',42),('freqmodes',3),('chantitle','QA')]:
            a.eq('channel '+key,d['results'][-1]['channels'][key],[value if reference=='QA50' else '' if key=='chantitle' else 0]*16)
        a.eq('rd/ud reset target/pilot',[s['target'],s['pilot_present']],[-1,False])
    # Unit-owned scheduled commands vs map-owned operational weather.
    for op in ('load','restore'):
        actions=[T('load','QA50'),dict(op='map_command',name='weather.enable',args={}),dict(op='construction_pilot'),C('startup'),I(),T(op,'QA50'),I()]
        d=a.run('ordinary/03-events-'+op,document(actions,{'QA50':modern()},ordinary=True),'ordinary');before,after=d['results'][-3],d['results'][-1]
        a.eq('map weather survives unit replacement',[e['deadline'] for e in after['events'] if e['kind']=='WEATHER'],[60])
        a.eq('Rloadnew/Rrestore startup distinction',any(e['kind']=='STARTUP' for e in after['events']),op=='restore')
    # Every class, source movement names, real files, ordinary editor and save.
    layout={
      'Mech':('Biped','Left_Arm'),'quad':('Quad','Front_Left_Leg'),'Vehicle':('Track','Front_Side'),'VTOL':('VTOL','Front_Side'),'Naval':('Hull','Front_Side'),
      'AeroFighter':('Fly','Nose'),'Aerodyne_DropShip':('Fly','Nose'),'Spheroid_DropShip':('Fly','Nose'),'Battlesuit':('Biped','Suit_1'),'Mechwarrior':('Biped','Left_Arm')}
    types=table('mech_types');moves=table('move_types')
    for name,(move,section) in layout.items():
        cls='Mech' if name=='quad' else name
        content=field('Type',cls)+field('Move_Type',move)+field('Tons',50)+field('Max_Speed','64.50')+section+'\n'+field('Armor',24)+field('Internals',8)+field('CRIT_1','IS.MediumLaser - - -')
        d=a.run('ordinary/08-'+name,document([T('load','CLASS'),R(),E('savetemp2','SAVED'),T('read','SAVED'),E('resetcrits'),R()],{'CLASS':content}),'ordinary');r=d['results'];out=r[1]
        a.eq('class and movement',[out['type'],out['move']],[types.index(cls),moves.index(move)]);a.eq('class save',r[2]['ok'],True)
        a.eq('default fuel',out['fuel_orig'],{'VTOL':4000,'AeroFighter':2400,'Aerodyne_DropShip':7200,'Spheroid_DropShip':7200}.get(cls,0))
        if cls=='AeroFighter':a.eq('Aero AFT defaults',[s['source_part_id'] for s in r[-1]['slots'][3]],[401 if j in (2,10) else 403 for j in range(12)])
        elif cls!='Mech':a.eq('other class reset clears',sum(bool(s['source_part_id']) for loc in r[-1]['slots'] for s in loc),0)
        fresh=a.run('ordinary/08-'+name+'-fresh',document([T('load','SAVED'),R()]),'ordinary',root=OUT/('ordinary/08-'+name)/'templates');a.eq('fresh saved class',fresh['results'][1]['type'],types.index(cls))
    # Accepted D1 modes set using ordinary commands, then cross process persistence.
    for name,weapon,rear,precision,lbx in [('half-lbx','IS.LB5-XAC',False,False,True),('rear-precision','IS.AC/5',True,True,False),('rear','IS.AC/5',True,False,False),('precision','IS.AC/5',False,True,False),('zero','IS.AC/5',False,False,False)]:
        actions=[T('load','QA50'),E('addweap',weapon+' LT 1 2 3 4'+(' 5' if lbx else '')+(' R' if rear else '')),E('reload',weapon+' RT 1')]
        if lbx:actions += [E('reload',weapon+' RT 1 +'),E('reload',weapon+' RT 1 L'),dict(op='construction_pilot'),C('startup'),A(40),C('lbx','1')]
        if precision:actions += [E('reload',weapon+' RT 1 P'),dict(op='construction_pilot'),C('startup'),A(40),C('precision','1')]
        actions += [E('savetemp2','MODES'),T('read','MODES'),R()]
        d=a.run('ordinary/12-13-'+name,document(actions,{'QA50':modern()},ordinary=True),'ordinary');r=d['results'];save=r[-2].get('text','')
        want='Halfton|LBX/Cluster' if lbx else 'RearMount|Precision' if rear and precision else 'RearMount' if rear else 'Precision' if precision else ' - '
        a.eq('serialized modes',want in save,True)
        units=deepcopy(targets)
        if rear:units[1]['at']=[3,5,0]
        follow=[T('load','MODES'),R()]+firing()
        if rear:follow += [C('lock','3 1 H'),C('fire','1'),I()]
        fresh=a.run('ordinary/12-13-'+name+'-fresh',document(follow,units=units,ordinary=True),'ordinary',root=OUT/('ordinary/12-13-'+name)/'templates')
        read=fresh['results'][1];slot=read['slots'][3 if lbx else 2][0]
        a.eq('loaded fire/ammo masks',[slot['fire'],slot['ammo']],[128,1] if lbx else [32 if rear else 0,65536 if precision else 0])
        if rear:
            # Restrict recycle assertions to the firing sequence's two snapshots.
            copy=deepcopy(fresh);copy['results']=copy['results'][:11];firing_assertions(a,copy,9 if precision else 19)
            a.eq('rear mount rejects forward hex',fresh['results'][-2]['accepted'],False)
        else:firing_assertions(a,fresh,9 if precision or lbx else 19)
