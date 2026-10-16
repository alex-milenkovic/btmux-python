"""Additional command/branch QA cases; all execution uses public subprocesses."""
from copy import deepcopy
import json
import sys
from movement_cases import *


def cases():
    d=base({'speed':43},[command('dodge'),command('bootlegger','R'),advance(1)])
    d['random']={'pilot_rolls':[12]}
    yield 'dodge-bootlegger-callback',d,[check(result_path('accepted',action=1),True),
        check(unit_path('sections','LLEG','recycle',action=1),30),ucheck('mode','NONE'),ucheck('pending_transition','NONE')]
    d=base(actions=[stim('scan',unit='A'),advance(2),command('dodge'),
        stim('punch',unit='A',target='B',arm='R',roll=12,location_roll=3),advance(1)])
    d['units'].append({'id':'B','team':2,'relative_position':{'to':'A','bearing':0,'range':0.5}})
    yield 'pending-dodge-refuses-punch',d,[check(result_path('accepted',action=2),True),
        check(result_path('attacks',0,'success',action=3),False),
        check(result_path('messages',action=3),'movement mode','text'),
        check(unit_path('sections','RARM','recycle',action=3),0),ucheck('mode','DODGE')]
    # Timer deadlines and callback feedback use the real queue.
    yield 'sprint-deadline',base(actions=[command('sprint'),advance(29),inspect(),advance(1)]),[
        ucheck('mode','NONE',action=2),check(unit_path('timers','MOVEMODE',action=2),1),ucheck('mode','SPRINT'),
        check(result_path('messages'),'enabled','text')]
    yield 'reverse-sprint',base({'speed':-10.75,'desired_speed':-10.75},[command('sprint'),advance(30)]),[
        ucheck('speed',-10.75),ucheck('desired_speed',0),ucheck('mode','SPRINT')]
    d=base({'states':['sprinting'],'desired_speed':100},[command('sprint'),advance(30)])
    yield 'exit-speed-cap',d,[ucheck('mode','NONE'),ucheck('desired_speed',64.5)]
    for active in (False,True):
        for internal in (False,True):
            d=base({'states':['sprinting'] if active else []},[])
            if not active:d['actions'].append(command('sprint'))
            d['actions'].append(stim('damage',unit='A',attacker='A',section='LARM',external=0 if internal else 1,internal=1 if internal else 0))
            yield f'damage-{active}-{internal}',d,[ucheck('mode','NONE'),ucheck('pending_transition','SPRINT_OFF' if active else 'NONE')]
    # Hull-down locks throughout lower/attained/raise workflows.
    for phase in ('lowering','lowered','raising'):
        for name,args in (('heading',[90]),('speed',['walk']),('jump',[0,1]),('stand',[])):
            actions=[command('hulldown')]
            if phase!='lowering':actions.append(advance(10))
            if phase=='raising':actions.append(command('hulldown','-'))
            actions.append(command(name,*args))
            yield f'hulldown-{phase}-{name}',base({'movement':'QUAD'},actions),[check(result_path('accepted'),False)]
    for name,args in (('hulldown',['bad']),('hulldown',['stop']),('land',[]),('jump',[0,100]),('jump',[0,0]),('eta',['3'])):
        yield f'rejected-{name}-{args}',base(actions=[command(name,*args)]),[check(result_path('accepted'),False)]
    yield 'hulldown-repeat',base({'movement':'QUAD'},[command('hulldown'),command('hulldown')]),[
        check(result_path('accepted'),False),check(unit_path('timers','HULLDOWN'),10)]
    # Queries and source text conversion; no ticks run.
    yield 'control-queries',base(actions=[command('heading'),command('speed'),command('turnmode')]),[
        check(result_path('message',action=0),'heading','contains'),check(result_path('message',action=1),'speed','contains'),check(['results',-1,'snapshot','tick'],0)]
    yield 'heading-atoi',base(actions=[command('heading',' -721junk')]),[ucheck('desired_facing',359)]
    yield 'speed-atof',base(actions=[command('speed',' 1.25e1junk')]),[ucheck('desired_speed',12.5)]
    yield 'arity',base(actions=[command('heading','1','2'),command('sprint','extra')]),[
        check(result_path('accepted',action=0),False),check(result_path('accepted'),False),ucheck('pending_transition','NONE')]
    for state in ('fallen','fortified','no_move','hulldown'):
        yield 'speed-guard-'+state,base({'states':[state]},[command('speed','walk')]),[check(result_path('accepted'),False),ucheck('desired_speed',0)]
    for state in ('dumping','unjamming','crew_stunned','tail_rotor_destroyed'):
        yield 'run-guard-'+state,base({'states':[state]},[command('speed','run')]),[check(result_path('accepted'),False)]
    for desired,expected in ((0.1,True),(0.11,False)):
        yield 'dig-clear-'+str(desired),base({'states':['digging']},[command('speed',desired)]),[ucheck('digging',expected)]
    yield 'torso-opposite',base(actions=[command('torso','L'),command('torso','R'),command('torso','R')]),[
        ucheck('torso_left',True,action=0),ucheck('torso_left',False,action=1),ucheck('torso_right',False,action=1),ucheck('torso_right',True)]
    yield 'mw-torso',base({'class':'MW'},[command('torso','L')]),[check(result_path('accepted'),True),ucheck('torso_left',True)]
    for setting in ('jammed','locked','damaged','working'):
        u={'class':'VEH_GROUND','movement':'TRACK','turret':{}}
        if setting in ('jammed','locked'):u['turret'][setting]=True
        if setting=='damaged':u['sections']=[{'location':'CTORSO','internal':0}]
        yield 'turret-'+setting,base(u,[command('turret',90)]),[check(result_path('accepted'),setting=='working')]
    for state in ('landed','fallen'):
        yield 'vertical-'+state,base({'class':'VTOL','movement':'VTOL','states':[state]},[command('vertical',1)]),[check(result_path('accepted'),False)]
    yield 'vertical-no-fuel',base({'class':'VTOL','movement':'VTOL','fuel':0},[command('vertical',1)]),[check(result_path('accepted'),False)]
    yield 'vertical-query',base({'class':'VTOL','movement':'VTOL'},[command('vertical')]),[check(result_path('accepted'),True)]
    yield 'vertical-atof',base({'class':'VTOL','movement':'VTOL','at':[3,3,3]},[command('vertical','junk')]),[ucheck('vertical_speed',0)]
    # Explicitly configured no periodic heat for isolated hot-TSM and speed arithmetic.
    for gravity,expected in ((50,129.0),(100,64.5),(150,43.0)):
        d=base(actions=[inspect(),inspect()]);d['map']={'gravity':gravity,'special_rules':True}
        yield 'cargo-gravity-'+str(gravity),d,[check(result_path('queries','A','effective_max_speed'),expected)]
    d=base({'states':['hot_tsm']},[inspect(),inspect()]);d['config']={'periodic_updates':False}
    yield 'hot-tsm',d,[check(result_path('queries','A','effective_max_speed'),86.0)]
    d=base({'load':{'tow':'B'}},[inspect(),inspect()]);d['units'].append({'id':'B','tons':25,'at':[4,4,0]})
    yield 'tow-speed',d,[check(result_path('queries','A','effective_max_speed'),32.25)]
    # Live ice evolution -> all three previously completed path-cost functions.
    d={'units':[], 'map':{'hexes':[hexagon(3,3,'WATER',1)]},'random':{'percentage_draws':[1,1]},
       'actions':[stim('ice',name='addice',args=['100'])]}
    for mode in ('mech','hover','tracked'):d['actions'].append(stim('path_cost',mode=mode,**{'from':[2,3],'to':[3,3]}))
    d['actions'].append(stim('ice',name='delice',args=['100']))
    for mode in ('mech','hover','tracked'):d['actions'].append(stim('path_cost',mode=mode,**{'from':[2,3],'to':[3,3]}))
    yield 'live-ice-costs',d,[check(result_path('cost',action=i),v) for i,v in ((1,2),(2,2),(3,2),(5,0),(6,1),(7,0))]
    for size,point,expected in (([2,4],[1,2],0),([4,2],[3,1],1)):
        d={'units':[],'map':{'size':size},'actions':[stim('path_cost',mode=m,**{'from':[0,0],'to':point}) for m in ('mech','hover','tracked')]}
        yield 'path-legacy-'+str(size[0]),d,[check(result_path('cost',action=i),expected) for i in range(3)]
    for center in ((2,3),(0,0)):
        d={'units':[],'map':{'hexes':[hexagon(*center,'WATER',1)]},'random':{'percentage_draws':[1]},'actions':[stim('ice',name='addice',args=['100'])]}
        yield 'ice-even-edge-'+str(center[0]),d,[check(result_path('changed_hexes'),1)]
    for args in ([],['1','2'],['junk'],['1.5']):
        yield 'ice-command-error-'+str(args),base(actions=[stim('ice',name='addice',args=args)]),[check(result_path('accepted'),False)]
    d=base({'at':[3,3,-1]},[stim('surface',unit='A',name='break_up')]);d['map']={'hexes':[hexagon(3,3,'ICE',0)]}
    d['units'][0]['at']=[3,3,0];d['units'].append({'id':'B','at':[3,3,0]})
    yield 'zero-depth-occupants',d,[ucheck('last_fall_levels',0,unit='B'),ucheck('terrain','WATER',unit='B'),check(['consumed','pilot_rolls'],0)]
    d=base({'at':[3,3,0]},[stim('surface',unit='A',name='break_up')]);d['map']={'hexes':[hexagon(3,3,'BRIDGE',1)]}
    d['units'].extend([{'id':'B','at':[3,3,1],'class':'VEH_GROUND','movement':'HOVER'},{'id':'C','at':[4,3,0]}]);d['random']={'pilot_rolls':[12],'fall_directions':[1]}
    yield 'bridge-occupants',d,[ucheck('last_fall_levels',2,unit='B'),ucheck('terrain','GRASSLAND',unit='C'),ucheck('last_fall_levels',0,unit='C')]
    for movement_type,waterproof,levels,destroyed in (('FOIL',False,0,False),('TRACK',True,2,False)):
        d=base({'class':'VEH_NAVAL' if movement_type=='FOIL' else 'VEH_GROUND','movement':movement_type,'states':['waterproof'] if waterproof else []},[stim('surface',unit='A',name='drop_down')])
        d['map']={'hexes':[hexagon(3,3,'ICE',2)]};d['random']={'pilot_rolls':[12],'fall_directions':[1]}
        yield 'trigger-'+movement_type,d,[ucheck('last_fall_levels',levels),ucheck('destroyed',destroyed)]
    d=base(actions=[command('jump',180,1),advance(20)]);d['map']={'hexes':[hexagon(3,4,'ICE',2)]};d['random']={'ice_d6':[1],'pilot_rolls':[12],'fall_directions':[1]}
    yield 'jump-ice-landing',d,[check(result_path('hexes','3,4','terrain'),'WATER'),ucheck('last_fall_levels',2),ucheck('jumping',False)]
    yield 'ood-default-height',base(actions=[command('ood',3,3)]),[check(unit_path('at',2),300),ucheck('cocoon',11)]
    yield 'ood-repeat',base(actions=[command('ood',3,3,7),command('ood',4,4,8)]),[check(result_path('accepted'),False),ucheck('at',[3,3,7])]
    yield 'ood-relocates-before-prone-rejection',base({'states':['fallen']},[command('ood',4,4,7)]),[check(result_path('accepted'),False),ucheck('at',[4,4,0]),timer('OOD',False)]
    d=base({'states':['combat_safe']},[command('ood',3,3,0),advance(1)])
    yield 'ood-safe-no-roll',d,[check(['consumed','pilot_rolls'],0),ucheck('cocoon',0),ucheck('fallen',False)]
    for cls,expected in (('MW',4),('BSUIT',4)):
        d=base({'class':cls},[command('ood',3,3,0),advance(1)]);d['random']={'pilot_rolls':[12]}
        yield 'ood-'+cls,d,[ucheck('required_roll',expected),ucheck('cocoon',0)]
    yield 'ood-flying',base({'class':'VTOL','movement':'VTOL','states':['landed']},[command('ood',3,3,20)]),[ucheck('cocoon',0),timer('OOD',False),ucheck('desired_speed',32.25)]
    for protected in (False,True):
        d=base({'class':'VEH_GROUND','movement':'TRACK','states':['waterproof'] if protected else []},[command('ood',3,3,0),advance(1)])
        d['map']={'hexes':[hexagon(3,3,'WATER',1)]};d['random']={'pilot_rolls':[12]}
        yield 'ood-waterproof-'+str(protected),d,[ucheck('destroyed',not protected)]
    yield 'no-queued-ood-from-fixture',base({'cocoon':11},[advance(1)]),[ucheck('cocoon',11),timer('OOD',False)]
    # Flood hardware uses real disable consequences, not an expected-result fixture.
    d=base({'at':[3,3,-1],'sections':[{'location':'LLEG','front':0,'components':[{'slot':4,'type':'heat_sink','condition':'working'}]}]},[stim('flood',unit='A'),stim('flood',unit='A')]);d['map']={'hexes':[hexagon(3,3,'WATER',1)]}
    d['random']={'pilot_rolls':[12,12],'fall_directions':[1]}
    yield 'flood-disables-idempotently',d,[check(unit_path('sections','LLEG','components',4,'condition'),'disabled'),ucheck('num_sinks',9)]
    for state in ('waterproof','combat_safe'):
        d=base({'states':[state],'at':[3,3,-1],'sections':[{'location':'LLEG','front':0}]},[stim('flood',unit='A')]);d['map']={'hexes':[hexagon(3,3,'WATER',1)]}
        yield 'flood-exempt-'+state,d,[check(unit_path('sections','LLEG','flooded'),False)]
    d=base({'at':[3,3,-2],'sections':[{'location':'HEAD','front':0}]},[stim('flood',unit='A')]);d['map']={'hexes':[hexagon(3,3,'WATER',2)]}
    yield 'head-flood',d,[ucheck('destroyed',True)]
    d=base({'states':['fallen']},[command('stand','careful'),advance(29),inspect(),advance(1)]);d['random']={'pilot_rolls':[2,12],'fall_directions':[1]}
    yield 'careful-failure-recovery',d,[check(unit_path('timers','STANDFAIL',action=2),1),timer('STANDFAIL',False),ucheck('fallen',True)]
    for careful,delay in ((False,4),(True,8)):
        d=base({'class':'MW','states':['fallen']},[command('stand',*(['careful'] if careful else [])),advance(delay)])
        yield 'mw-stand-'+str(careful),d,[check(unit_path('timers','STAND',action=0),delay),timer('STAND',False),check(['consumed','pilot_rolls'],0)]
    for mode,bth in (('NONE',5),('DODGE',7)):
        d=base({'id':'A','facing':0},[stim('scan',unit='A'),advance(2),stim('punch',unit='A',target='B',arm='R',roll=2,location_roll=3)])
        d['units'].append({'id':'B','team':2,'relative_position':{'to':'A','bearing':0,'range':0.5},'states':mode_bits(mode)})
        yield 'physical-bth-'+mode,d,[check(result_path('attacks',0,'bth'),bth),check(result_path('attacks',0,'success'),True)]
    for mode,bth in (('NONE',6),('EVADE',7),('SPRINT',2)):
        d=base({'id':'A','facing':0},[stim('scan',unit='A'),advance(2),stim('fire',unit='A',target='B',weapon='IS.MediumLaser',roll=2)])
        d['units'].append({'id':'B','team':2,'at':[3,2,0],'states':mode_bits(mode)})
        yield 'weapon-bth-'+mode,d,[check(result_path('attack','bth'),bth),check(result_path('attack','roll'),2)]
    d=base({'at':[3,4,0],'speed':64.5},[command('speed','run'),advance(10)])
    d['map']={'hexes':[hexagon(3,3,'ICE',2)]};d['random']={'ice_d6':[1],'pilot_rolls':[12,12],'fall_directions':[1]}
    yield 'ordinary-movement-ice',d,[check(result_path('hexes','3,3','terrain'),'WATER'),ucheck('fallen',True),ucheck('last_fall_levels',2)]
    for mode,speed,expected in (('NONE',64.5,67.725),('SPRINT',86,86.0)):
        d=base({'class':'VEH_GROUND','movement':'TRACK','speed':speed,'states':mode_bits(mode)},[command('speed','run'),advance(1)])
        d['map']={'default':['ROAD',0]}
        yield 'road-bonus-'+mode,d,[ucheck('speed',expected)]
    # Without speed_demon or maneuvering_ace, both modes halve turning.
    for mode,expected in (('NONE',9),('SPRINT',4),('EVADE',4)):
        d=base({'states':mode_bits(mode),'advantages':[]},[command('heading',180),advance(1)])
        yield 'heading-mode-penalty-'+mode,d,[ucheck('facing',expected)]
    d=base({'class':'VTOL','movement':'VTOL','at':[3,3,2]},[command('vertical',43),advance(3)])
    yield 'vertical-with-zero-horizontal',d,[ucheck('speed',0),check(unit_path('at',2),3)]
    d={'units':[],'map':{'hexes':[hexagon(2,3,'WATER',1),hexagon(2,2,'BRIDGE',1),hexagon(3,3,'BRIDGE',1)]},
       'random':{'percentage_draws':[1],'neighbor_d6':[3]},'actions':[stim('ice',name='addice',args=['100'])]}
    yield 'ice-even-neighbors',d,[check(result_path('changed_hexes'),1),check(result_path('hexes','2,3','terrain'),'ICE')]
    d=base({'at':[3,3,-1],'sections':[{'location':'LLEG','front':0,'components':[{'slot':5,'type':'ammo','weapon':'IS.AC/5','rounds':10,'condition':'working'}]}]},[stim('flood',unit='A')])
    d['map']={'hexes':[hexagon(3,3,'WATER',1)]};d['random']={'pilot_rolls':[12,12],'fall_directions':[1]}
    yield 'flood-empties-ammo',d,[check(unit_path('sections','LLEG','components',5,'condition'),'disabled'),check(unit_path('sections','LLEG','components',5,'data'),0)]

    for state,target,levels in (('unconscious',5,12),('blinded',5,12),('stopped',15,52)):
        d=base({'states':[] if state=='stopped' else [state]},[command('ood',3,3,0)])
        if state=='stopped':d['actions'].append(command('shutdown'))
        d['actions'].append(advance(1));d['random']={'pilot_rolls':[12,12],'fall_directions':[1]}
        checks=[ucheck('required_roll',target),ucheck('last_fall_levels',levels),ucheck('cocoon',0)]
        if state=='stopped':
            # Shutdown triggers the fall immediately.
            immediate=['results',1,'snapshot','units','A']
            checks=[check(immediate+['last_fall_levels'],0),check(immediate+['cocoon'],0),
                    check(immediate+['fallen'],True),check(immediate+['speed'],0),
                    check(immediate+['desired_speed'],0),ucheck('started',False),
                    ucheck('cocoon',0),ucheck('required_roll',None),ucheck('last_fall_levels',0),
                    timer('OOD',False),check(['consumed','pilot_rolls'],1)]
        yield 'ood-pilot-'+state,d,checks
    for dropship in (False,True):
        d=base(actions=[command('jump',0,1),advance(20)])
        d['units'].extend([{'id':'B','class':'DS' if dropship else 'MECH','at':[3,2,0],
                           'cocoon':-1,'states':['landed'] if dropship else []},
                          {'id':'C','at':[3,2,0],'cocoon':11}, {'id':'D','at':[3,2,0]}])
        yield 'ood-stacking-'+str(dropship),d,[ucheck('jumping',False),
            check(result_path('damage_by_unit','A'),12 if dropship else 0),
            check(result_path('damage_by_unit','B'),2 if dropship else 0),
            check(result_path('damage_by_unit','C'),0)]


def errors_suite(run,output,errors,records):
    import hashlib
    root=output.parents[1]
    valid={'actions':[command('sprint'),advance(30)]}
    bad=[('invalid-json','{'),('malformed-section',{'units':[{'sections':[None]}],'actions':[]}),('missing-actions',{}),('missing-action-field',{'actions':[{'op':'command','unit':'A','name':'speed'}]}),
         ('limb-without-dodge',{'actions':[stim('limb_use',unit='A',location='LLEG',seconds=30)]}),
         ('limb-nonlimb',{'actions':[command('dodge'),stim('limb_use',unit='A',location='HEAD',seconds=30)]}),
         ('limb-invalid-seconds',{'actions':[command('dodge'),stim('limb_use',unit='A',location='LLEG',seconds=0)]}),
         ('unknown-op',{'actions':[{'op':'oops'}]}),('unknown-command',{'actions':[command('oops')]}),
         ('unknown-terrain',{'map':{'default':['BOG',0]},'actions':[]}),('missing-unit',{'actions':[command('speed','walk',unit='Z')]}),
         ('negative-advance',{'actions':[advance(-1)]}),('invalid-dice',{'random':{'pilot_rolls':[13]},'actions':[]}),
         ('unused-invalid-dice',{'random':{'ice_d6':[0]},'actions':[]}),('exhausted-dice',{'random':{},'units':[{'states':['fallen']}],'actions':[command('stand')]}),
         ('unknown-fixture',{'units':[{'magic':4}],'actions':[]}),('invalid-lateral',{'units':[{'lateral':30}],'actions':[]}),
         ('nonfinite', '{"units":[{"speed":NaN}],"actions":[]}'),('overflow-number','{"units":[{"speed":1e400}],"actions":[]}'),
         ('duplicate-json','{"actions":[],"actions":[]}'),('bad-bool',{'map':{'special_rules':'false'},'actions':[]}),
         ('duplicate-unit',{'units':[{'id':'A'},{'id':'A'}],'actions':[]}),('relative-cycle',{'units':[{'id':'A','relative_position':{'to':'A','bearing':0,'range':1}}],'actions':[]}),
         ('relative-missing',{'units':[{'relative_position':{'to':'Z','bearing':0,'range':1}}],'actions':[]}),
         ('relative-offmap',{'units':[{'id':'A'},{'id':'B','relative_position':{'to':'A','bearing':0,'range':100}}],'actions':[]}),
         ('rear-on-arm',{'units':[{'sections':[{'location':'LARM','original_rear':1}]}],'actions':[]}),
         ('unknown-config',{'config':{'magic':True},'actions':[]}),('unavailable-profile',{'config':{'overspeeding':True},'actions':[]}),
         ('below-ice',{'map':{'default':['ICE',2]},'units':[{'at':[3,3,-3]}],'actions':[]})]
    for label,document in bad:
        path=output/'errors'/f'{label}.json';path.parent.mkdir(exist_ok=True)
        path.write_text(document if isinstance(document,str) else json.dumps(document))
        result=run([sys.executable,'-m','tools.movement','--script',str(path)])
        ok=result['status']!=0 and not result['stdout'] and 'error:' in result['stderr'] and 'Traceback' not in result['stderr']
        (path.with_suffix('.result.json')).write_text(json.dumps(result,indent=2))
        records.append({'label':'errors/'+label,'passed':ok})
        if not ok:errors.append({'label':'errors/'+label,'error':str(result)})
    path=output/'repeatability.json';path.write_text(json.dumps(valid))
    first=run([sys.executable,'-m','tools.movement','--script',str(path)])
    second=run([sys.executable,'-m','tools.movement','--script',str(path)])
    ok=first['status']==second['status']==0 and first['stdout']==second['stdout'] and not first['stderr'] and not second['stderr']
    (output/'repeatability.result.json').write_text(json.dumps({'first':first,'second':second},indent=2))
    records.append({'label':'repeatability','passed':ok})
    if not ok:errors.append({'label':'repeatability','error':'identical fresh processes differ'})
    help_result=run([sys.executable,'-m','tools.movement','--help'])
    ok=help_result['status']==0 and not help_result['stderr'] and all(term in help_result['stdout'] for term in ('KPH','FIFO','D1-D7','--script','path_cost'))
    (output/'help.result.json').write_text(json.dumps(help_result,indent=2))
    records.append({'label':'help','passed':ok})
    if not ok:errors.append({'label':'help','error':'missing contract documentation'})
