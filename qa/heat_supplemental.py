"""Independent supplemental C boundary and real event workflows for heat QA."""
from copy import deepcopy
from heat_support import (Case,action,command,maintain,advance,hit,external,
                          weapon,bin_fixture,armed,vehicle,only_front)


def sinks_and_heat():
    for label,unit,enabled,accepted in [
        ('disabled',{},False,0),('stopped',{'started':False},True,1),
        ('mapless',{'map_valid':False},True,1),
        ('nonpilot',{'states':['in_character'],'caller_id':'other'},True,0),
        ('wizard',{'states':['in_character'],'caller_id':'other','wizard':True},True,1),
        ('blinded',{'blinded':True},True,0),('unconscious',{'conscious':False},True,0)]:
        yield Case('extra-sinks/guard-'+label,unit,[command('heatcutoff'),advance(4)],
                   integrated=True,config={'periodic_updates':False,'heatcutoff_enabled':enabled}).accepted(accepted).final(cutoff=bool(accepted)).pending('cutoff_deadline',False)
    yield Case('extra-sinks/toggle-recover',dict(heat_state={'disabled_capacity':4}),
        [command('heatcutoff'),advance(4),command('heatcutoff'),advance(4),advance(10)],
        integrated=True,config={'periodic_updates':True}).accepted(2).final(cutoff=False,disabled_capacity=0)
    for technology,capacity,slots in [('SINGLE',10,1),('DOUBLE',20,3),('CLAN',20,2)]:
        unit=dict(heat_state={'sink_technology':technology,'sink_capacity':capacity,'disabled_capacity':2},
                  sections=[dict(location='LARM',front=0,internal=1,components=[
                    dict(slot=4+i,type='heat_sink',condition='working') for i in range(slots)])])
        c=Case('extra-sinks/loss-'+technology,unit,[hit(1,section='LA'),maintain('heat')],
               random={'critical_rolls':[2],'pilot_rolls':[12]*10})
        loss=1 if technology=='SINGLE' else 2
        yield c.final(active_capacity=capacity-loss,disabled_capacity=0,minus_heat=capacity-loss)
    for condition,minus in [('FUNCTIONAL',11),('DISABLED',10)]:
        yield Case('extra-heat/quad-arm-'+condition,dict(movement='QUAD',at=[2,2,-1],
            heat_state={'weapon_heat':20},sections=[dict(location='LARM',components=[
            dict(slot=4,type='heat_sink',condition='working' if condition=='FUNCTIONAL' else 'disabled')])]),[advance(2)],integrated=True,
            map={'default':['WATER',1]},config={'periodic_updates':True}).final(minus_heat=minus,heat=20-minus)
    sources=[('stealth',{'stealth':True},[],0,10),('null',{'null_signature':True},[],0,10),
             ('both',{'stealth':True,'null_signature':True},[],0,20),
             ('walk',{},[],10.75,1),('run',{},[],54,2),('sprint',{},['sprinting'],54,3),
             ('evade',{},['evading'],54,3),('jumpwalk',{},['jumping'],10.75,4)]
    for label,flags,states,speed,plus in sources:
        yield Case('extra-heat/source-'+label,dict(heat_state=flags,states=['started']+states,
            speed=speed,desired_speed=speed),[maintain('heat')]).final(plus_heat=plus,heat=max(0,plus-10))
    yield Case('extra-heat/fire-combined',dict(heat_state={'engine_heat':5,'stealth':True,'null_signature':True}),
        [maintain('heat')],map={'default':['FIRE',0]}).final(plus_heat=30,heat=20)
    for temperature,minus in [(-31,11),(51,9)]:
        yield Case('extra-heat/water-inferno-'+str(temperature),dict(at=[2,2,-2],events={'inferno':180},
            heat_state={'weapon_heat':20}),[maintain('heat')],map={'default':['WATER',2],
            'special_rules':True,'temperature':temperature}).final(minus_heat=minus,heat=20-minus)
    for old,new,color in [(0,14,'YELLOW'),(14,19,'RED'),(19,14,'YELLOW'),(14,13,'GREEN'),(19,19,None)]:
        c=Case(f'extra-heat/indicator-{old}-{new}',dict(heat_state={'heat':old,'weapon_heat':new+10}),[maintain('heat')])
        c.final(heat=new)
        if color:c.notice('indicator turns '+color)
        else:c.notice('indicator turns',0)
        yield c
    for heat,threshold in [(19,4),(23,6),(28,8)]:
        for roll in (threshold-1,threshold):
            unit=armed(2,heat_state={'heat':heat})
            yield Case(f'extra-heat/ammo-{heat}-{roll}',unit,[maintain('overheat')],clock={'event':30},
                random={'ammo_avoidance':[roll],'shutdown_rolls':[12],'critical_rolls':[2]*5}).final(
                    **{'bins.0.rounds':0 if roll<threshold else 2,'pilot_hits':2 if roll<threshold else 0,
                       'sections.2.internal':80 if roll<threshold else 100})
    for heat,roll,started in [(22,7,False),(22,8,True),(26,9,False),(26,10,True),(30,12,False)]:
        yield Case(f'extra-heat/shutdown-{heat}-{roll}',dict(heat_state={'heat':heat}),[maintain('overheat')],
            clock={'event':30},random={'ammo_avoidance':[12],'shutdown_rolls':[] if heat==30 else [roll]}).final(started=started)
    yield Case('extra-heat/overheat-cadence',dict(heat_state={'heat':14}),
        [maintain('overheat'),maintain('overheat'),action('dispatch',seconds=29),maintain('overheat'),
         action('dispatch',seconds=1),maintain('overheat')],clock={'event':30},
         random={'shutdown_rolls':[12,12]}).expect('consumed.shutdown_rolls',2).final(last_overheat_tick=60)
    yield Case('extra-heat/no-ammo',dict(heat_state={'heat':19}),[maintain('overheat')],clock={'event':30},
        random={'ammo_avoidance':[2],'shutdown_rolls':[12]}).notice('no ammunition').final(started=True)
    for jumping in (False,True):
        yield Case('extra-heat/moving-shutdown-'+str(jumping),dict(speed=21.5,desired_speed=21.5,
            jump_mp=3,states=['started','jumping'] if jumping else ['started'],heat_state={'heat':30}),
            [maintain('overheat'),advance(10)],clock={'event':30},random={'ammo_avoidance':[12],
            'pilot_rolls':[2],'fall_pilot_rolls':[12],'fall_directions':[1],'hit_location_rolls':[7]*10}).final(
                started=False,speed=0,desired_speed=0,jumping=False,fallen=True)
    yield Case('extra-heat/injury-dispatch30',dict(heat_state={'weapon_heat':25,'life_support_destroyed':True}),
        [advance(2)],integrated=True,clock={'event':28,'wall':28},config={'periodic_updates':True},
        random={'shutdown_rolls':[12]}).final(heat=15,pilot_hits=1)


def dump_and_ignition():
    yield Case('extra-dump/replace-after-decrement',armed(6),
        [command('dump','LT','1'),advance(1),command('dump','all'),advance(1),command('dump','stop'),advance(3),
         command('dump','all'),advance(1)],integrated=True).accepted(4).final(**{'bins.0.rounds':3,'dumping':True})
    for selector in [('all',),('LT',),('LT','1')]:
        unit=armed();unit['bins'][0]['condition']='BROKEN'
        yield Case('extra-dump/broken-'+'-'.join(selector),unit,[command('dump',*selector),advance(1)],
            integrated=True).accepted(int(selector==('all',))).final(**{'bins.0.rounds':3,'dumping':False})
    yield Case('extra-dump/restart-does-not-resume',armed(),[command('dump','all'),command('shutdown'),
        advance(1),command('startup'),advance(5)],integrated=True).final(**{'bins.0.rounds':3,'dumping':False})
    for index,args in enumerate([[],['-1'],['99'],['ZZ'],['HEAD'],['LT','0'],['LT','13']]):
        accepted=args in (['LT','0'],['LT','13'])
        yield Case('extra-dump/selector-'+str(index),armed(),[command('dump',*args)]).accepted(int(accepted)).final(dumping=accepted)
    for category in ('ENERGY','HAND'):
        w=weapon();w['category']=category;w['ammo_per_ton']=0
        yield Case('extra-dump/weapon-'+category,dict(equipment=[w]),[command('dump','0')]).accepted(0).final(dumping=False)
    yield Case('extra-dump/movement-guards',armed(jump_mp=3),[command('dump','all'),command('speed','run'),
        command('jump','0','1'),command('speed','walk'),command('dump','stop')],integrated=True).expect(
        'results.1.accepted',False).expect('results.2.accepted',False).expect('results.3.accepted',True).final(dumping=False)
    unit=armed(3);unit['equipment'] += [weapon('B',per_ton=60,section='LA')]
    unit['bins'] += [bin_fixture(3,section='RT',weapon=1)];unit['equipment'][0]['ammo_per_ton']=5
    yield Case('extra-dump/mixed-rates',unit,[command('dump','all'),advance(6)],integrated=True).final(
        **{'bins.0.rounds':2,'bins.1.rounds':0,'dumping':True})
    for scope,condition,expected in [('all','BROKEN',2),('LT','BROKEN',3),('0','BROKEN',2)]:
        unit=armed();unit['bins'][0]['condition']=condition
        if scope=='0':unit['bins'].append(bin_fixture(3,section='RT'))
        yield Case('extra-ignition/condition-'+scope,unit,[command('dump',scope),hit(section='CT',arc='REAR',weapon=0)],
            random={'dump_candidates':[1 if scope=='0' else 0],'fire_rolls':[]}).final(**{'bins.0.rounds':expected})
    yield Case('extra-ignition/second-hit',armed(),[command('dump','all'),hit(section='CT',arc='REAR',weapon=0),
        hit(section='CT',arc='REAR',weapon=0)],random={'dump_candidates':[0],'fire_rolls':[]}).final(
        **{'bins.0.rounds':2,'sections.4.rear':88,'dumping':False}).expect('consumed.dump_candidates',1)
    first=dict(name='u',**armed());other=dict(name='other',**armed())
    yield Case('extra-ignition/independent-unit',units=[first,other],actions=[command('dump','all'),
        command('dump','all',unit='other'),hit(section='CT',arc='REAR',weapon=0)],
        random={'dump_candidates':[0]}).final(dumping=False).expect('final.units.other.dumping',True)
    attacker=dict(name='attacker',at=[2,3,0],facing=0,target_id='u',equipment=[weapon('shot',damage=1)],bins=[bin_fixture(3)])
    yield Case('extra-ignition/actual-fire',units=[dict(name='u',**armed()),attacker],
        actions=[action('scan',unit='attacker'),advance(10),command('dump','all'),command('fire','0',unit='attacker'),advance(40)],integrated=True,
        random={'attack_rolls':[12],'hit_location_rolls':[7],'dump_candidates':[0],'fire_rolls':[]}).expect(
        'results.3.hit',True).expect('results.3.snapshot.units.u.bins.0.rounds',2).final(dumping=False).expect(
        'final.units.attacker.weapons.0.recycle',0).notice('finished recycling')


def fires():
    unit=vehicle(sections=only_front())
    yield Case('extra-fire/duplicate-inferno',unit,[external(),external(),advance(60),advance(60)],integrated=True,
        config={'periodic_updates':False,'advanced_vehicle_fire':True},random={'fire_damage':[3,2,1]}).final(
        **{'sections.0.front':94}).count('final.units.u.burning_sides',0).expect('consumed.fire_damage',3).notice('finally goes out')
    for startup,natural in [(False,False),(True,False),(False,True)]:
        u=vehicle(started=False,sections=only_front(),events={'burns':[{'section':'LSIDE','remaining':60}]})
        acts=[command('extinguish')]+([command('startup')] if startup else [])+[advance(120),advance(60)]
        yield Case(f'extra-fire/extinguish-{startup}-{natural}',u,acts,integrated=True,
            random={'fire_damage':[1] if natural else [2,2,2]}).count('final.units.u.burning_sides',0).pending(
            'extinguish_deadline',False).notice('dowse',0 if natural else 1)
    for alias,slot in [('FRONT',2),('REAR',3)]:
        yield Case('extra-fire/alias-'+alias,vehicle(events={'burns':[{'section':alias,'remaining':1}]}),
            [advance(1)],random={'fire_damage':[1]}).final(**{f'sections.{slot}.front':99}).count('final.units.u.burning_sides',0)
    for roll,destroyed in [(8,False),(9,True)]:
        yield Case('extra-fire/legacy-'+str(roll),vehicle(),[external(False)],random={'fire_rolls':[roll]}).final(destroyed=destroyed)
    for terrain,depth in [('WATER',2),('ICE',2),('BRIDGE',2)]:
        c=Case('extra-fire/steam-expiry-'+terrain,dict(events={'inferno':180}),
            [action('enter_hex',unit='u',at=[3,2,-2 if terrain!='BRIDGE' else -1]),advance(119),advance(1),advance(60)],
            integrated=True,map={'hexes':[dict(at=[3,2],terrain=terrain,elevation=depth)]},random={'pilot_rolls':[12]*10})
        c.expect('results.0.snapshot.units.u.jellied',False).expect('results.1.snapshot.decorations.0.deadline',120)
        yield c.count('final.decorations',0).pending('inferno_deadline',False).notice('fires finally die',0)
    yield Case('extra-fire/settled-water-Z0',dict(events={'inferno':180}),
        [action('enter_hex',unit='u',at=[3,2,0])],integrated=True,
        map={'hexes':[dict(at=[3,2],terrain='WATER',elevation=2)]}).final(**{'at.2':-2,'jellied':False}).count('final.decorations',1)
    yield Case('extra-fire/prone-water',dict(at=[2,2,-1],events={'inferno':180}),
        [command('prone'),advance(180)],integrated=True,map={'default':['WATER',1]}).accepted(1).final(
        fallen=True,jellied=False).count('final.decorations',0).notice('fires finally die',0)
    yield Case('extra-fire/actual-water-move',dict(events={'inferno':180}),[command('speed','walk'),advance(30)],
        integrated=True,map={'default':['WATER',2],'hexes':[dict(at=[2,2],terrain='GRASSLAND',elevation=0)]},
        random={'pilot_rolls':[12]*20}).final(jellied=False).count('final.decorations',1)


def clocks_and_heights():
    for mode in (1,2):
        yield Case('extra-stagger/normal-'+str(mode),actions=[hit(25),advance(5),advance(55)],integrated=True,
            config={'periodic_updates':True,'new_stagger':mode},random={'pilot_rolls':[12]}).expect(
            'consumed.pilot_rolls',1).count('final.units.u.stagger',0).expect('results.1.snapshot.units.u.counted_damage',25 if mode==1 else 0)
    yield Case('extra-stagger/exact60',actions=[hit(20),action('heartbeat',wall_seconds=60)],
        random={'pilot_rolls':[12]}).expect('consumed.pilot_rolls',1).count('final.units.u.stagger',0)
    yield Case('extra-stagger/event-backlog',actions=[hit(20),action('dispatch',seconds=4),action('inspect'),action('inspect')]).final(
        uncounted_damage=20).expect('consumed.pilot_rolls',0).expect('final.clock.wall',4)
    for posture in ('fallen','jumping'):
        yield Case('extra-stagger/prune-'+posture,dict(states=[posture],history=[dict(amount=20,wall=0,counted=False)]),
            [action('heartbeat',wall_seconds=60)],random={'pilot_rolls':[]}).count('final.units.u.stagger',0)
    yield Case('extra-stagger/stopped',dict(started=False),[hit(20),action('heartbeat',wall_seconds=5)],
        random={'pilot_rolls':[12],'fall_pilot_rolls':[12],'fall_directions':[1],'hit_location_rolls':[7]*10}).final(
        fallen=True).expect('results.1.rolls.0.modifier',999).count('final.units.u.stagger',0)
    for posture in ('upright','jumping','fallen','ood'):
        unit={'states':[posture] if posture in ('jumping','fallen') else []}
        if posture=='ood':unit['cocoon']=10
        yield Case('extra-stagger/legacy-'+posture,unit,[hit(20),maintain('pilot'),maintain('pilot')],
            config={'periodic_updates':False,'new_stagger':0},random={'pilot_rolls':[12]},clock={'event':7}).final(turn_damage=0).expect(
            'consumed.pilot_rolls',int(posture=='upright'))
    for conscious,checks in [(True,0),(False,1)]:
        yield Case('extra-ticks/stopped-'+str(conscious),dict(started=False,conscious=conscious),[advance(2)],
            integrated=True,clock={'wall':28,'event':28},config={'periodic_updates':True},
            random={'pilot_rolls':[12]}).expect('consumed.pilot_rolls',checks)
    for speed in (64.5,-75.25):
        yield Case('extra-ticks/gravity-boundary-'+str(speed),dict(speed=speed),[maintain('pilot')],
            map={'special_rules':True,'gravity':150},clock={'event':30},random={'pilot_rolls':[]}).count('results.0.rolls',0)
    for label,z,direction,seconds,finalz in [('surface',-1,'10.75',13,0),('bottom',-1,'-10.75',24,-2)]:
        yield Case('extra-heights/sub-'+label,{'class':'VEH_NAVAL','movement':'SUB','at':[2,2,z]},
            [command('vertical',direction),advance(seconds)],integrated=True,map={'default':['WATER',3]}).accepted(1).final(
                **{'at.2':finalz,'vertical_speed':0,'fz':0 if label=='surface' else -180.6})
    yield Case('extra-heights/vtol-orbit',{'class':'VTOL','movement':'VTOL','at':[2,2,299]},
        [command('vertical','10.75'),advance(12)],integrated=True).accepted(1).final(**{'at.2':299,'fz':19285.5,'vertical_speed':0})
    for terrain in ('GRASSLAND','ROAD','BUILDING'):
        yield Case('extra-heights/landing-'+terrain,{'class':'VTOL','movement':'VTOL','at':[2,2,-1],
            'vertical_speed':-10.75,'desired_speed':10.75},[maintain('height')],map={'default':[terrain,0]}).final(
            **{'at.2':0,'landed':True,'vertical_speed':0}).expect('final.units.u.unavailable','landing mines and object scripts','contains')
    yield Case('extra-heights/naval-grounding',{'class':'VEH_NAVAL','movement':'SUB','at':[2,2,-1],
        'speed':10.75,'desired_speed':10.75,'facing':90},[action('enter_hex',unit='u',at=[3,2,0])],integrated=True).final(
        speed=0,desired_speed=0,vertical_speed=0,facing=0,desired_facing=0)
    yield Case('extra-ticks/independent-notice',units=[{'name':'u'},{'name':'other'}],clock={'event':10},
        actions=[maintain('dropship_notice'),action('maintain',unit='other',kind='dropship_notice')]).expect(
        'results.0.emitted',True).expect('results.1.emitted',True)
    yield Case('extra-ticks/unavailable-delegates',actions=[advance(30)],integrated=True,config={'periodic_updates':True}).expect(
        'final.units.u.unavailable','CheckGenericFail','contains').expect('final.units.u.unavailable','checkTAG','contains').expect(
        'final.units.u.unavailable','end_lite_check','contains')
    yield Case('extra-ticks/aircraft-delegate',{'class':'AERO','movement':'FLY',
        'heat_state':{'weapon_heat':20}},[advance(2)],integrated=True,
        config={'periodic_updates':True}).final(heat=10,minus_heat=10)


def errors():
    invalid=[('operation',{'actions':[{'op':'unknown'}]},'unknown'),
             ('field',{'units':[{'unknown':True}],'actions':[]},'unknown'),
             ('enum',{'units':[{'class':'INVALID'}],'actions':[]},'INVALID'),
             ('capacity',{'units':[{'heat_state':{'sink_capacity':2,'disabled_capacity':3}}],'actions':[]},'outside'),
             ('json','{','error:'),('duplicate','{"actions":[],"actions":[]}','duplicate'),
             ('dice',{'random':{'pilot_rolls':[13]},'actions':[]},'outside'),
             ('exhaustion',{'units':[{'heat_state':{'heat':14}}],'clock':{'event':30},
              'random':{'shutdown_rolls':[]},'actions':[maintain('overheat')]},'exhausted'),
             ('profile',{'config':{'mw3stats':True},'actions':[]},'unsupported'),
             ('zero-rate',{'units':[{'equipment':[weapon(per_ton=0)]}],'actions':[]},'positive')]
    for label,document,error in invalid:
        c=Case('extra-errors/'+label);c.document=document;c.error=error;yield c
        yield Case('extra-errors/recovery-'+label,dict(heat_state={'heat':100,'plus_heat':20,'weapon_heat':20}),
            [advance(2)],integrated=True,config={'periodic_updates':True}).final(heat=10,weapon_heat=19.666666667,started=True,pilot_hits=0)


def extended():
    for heat,threshold in [(10,4),(14,6),(19,8),(23,10),(28,12)]:
        for roll in (threshold-1,threshold):
            unit=armed(4,heat_state={'heat':heat});unit['equipment'][0].update(category='MISSILE',damage=2)
            unit['bins'][0]['inferno']=True
            boom=roll<threshold
            yield Case(f'extra-inferno/threshold-{heat}-{roll}',unit,[maintain('overheat')],clock={'event':30},
                config={'periodic_updates':False,'inferno_penalty':True},random={'ammo_avoidance':[roll],
                'shutdown_rolls':[12],'critical_rolls':[2]*5}).final(**{'bins.0.rounds':0 if boom else 4,
                'pilot_hits':2 if boom else 0,'sections.2.internal':96 if boom else 100,'weapon_heat':30 if boom else 0})
    yield Case('extra-inferno/extension',dict(events={'inferno':60}),[advance(20),external(heat=5),advance(69),advance(1)],
        integrated=True).expect('results.1.snapshot.units.u.inferno_deadline',90).expect('results.2.snapshot.units.u.jellied',True).final(jellied=False)
    yield Case('extra-inferno/pain-resistance',armed(2,pain_resistance=True,heat_state={'heat':19}),
        [maintain('overheat')],clock={'event':30},random={'ammo_avoidance':[2],'shutdown_rolls':[12],'critical_rolls':[2]}).final(pilot_hits=1)
    yield Case('extra-inferno/bsuit-routing',dict({'class':'BSUIT'},**armed(2,heat_state={'heat':19})),
        [maintain('overheat')],clock={'event':30},random={'ammo_avoidance':[2],'shutdown_rolls':[12],'critical_rolls':[2]}).final(
        **{'pilot_hits':0,'sections.2.front':80,'sections.2.internal':100})
    yield Case('extra-heat/searchlight-shutdown',dict(searchlight=True,heat_state={'heat':30}),[maintain('overheat')],
        clock={'event':30},random={'ammo_avoidance':[12]}).final(started=False,searchlight=False)
    yield Case('extra-heat/critical-cleanup',armed(2,heat_state={'heat':19}),[maintain('overheat')],clock={'event':30},
        random={'ammo_avoidance':[2],'shutdown_rolls':[12],'critical_rolls':[2]}).final(
        **{'bins.0.rounds':0,'bins.0.temporary_failure':0,'bins.0.condition':1})
    # Independent sides: one expires on 1 while another rearms after 2.
    u=vehicle(events={'burns':[dict(section='LSIDE',remaining=60),dict(section='RSIDE',remaining=60)]})
    yield Case('extra-fire/multiple-sides',u,[advance(60),advance(60)],integrated=True,
        random={'fire_damage':[1,2,1]}).expect('results.0.snapshot.units.u.burning_sides',{'1':120}).count(
        'final.units.u.burning_sides',0).final(**{'sections.0.front':99,'sections.1.front':97})
    u=vehicle(events={'burns':[dict(section='LSIDE',remaining=60)]},sections=[dict(location='LARM',front=0,internal=1)])
    other=vehicle(events={'burns':[dict(section='RSIDE',remaining=60)]})
    yield Case('extra-fire/destroyed-side-isolation',units=[dict(name='u',**u),dict(name='other',**other)],
        actions=[hit(1,section='LSIDE'),advance(60)],integrated=True,
        random={'critical_rolls':[2],'fire_damage':[2,2]}).final(**{'sections.0.internal':0}).count('final.units.u.burning_sides',0).count(
        'final.units.other.burning_sides',1)
    for terrain in ('GRASSLAND','ROAD','BUILDING'):
        yield Case('extra-heights/vertical-land-'+terrain,{'class':'VTOL','movement':'VTOL','at':[2,2,1],
            'desired_speed':0},[command('vertical','-10.75'),advance(25)],integrated=True,map={'default':[terrain,0]}).final(
            **{'at.2':0,'landed':True,'vertical_speed':0,'last_fall_levels':None})
    yield Case('extra-heights/landed-suppression',{'class':'VTOL','movement':'VTOL','at':[2,2,300],'states':['landed']},
        [maintain('height')]).final(**{'at.2':300})
    for terrain in ('FIRE','GRASSLAND'):
        yield Case('extra-ticks/already-destroyed-'+terrain,{'class':'MW','states':['destroyed']},
            [action('enter_hex',unit='u',at=[3,2,0])],map={'default':[terrain,0]}).final(destroyed=True,kill_reason=None)
    yield Case('extra-ticks/turret-target-precedence',units=[dict(name='u',**vehicle(auto_turret=True,facing=90,
        target_id='target',target_hex=[3,2])),dict(name='target',relative_position={'to':'u','bearing':0,'range':1})],
        actions=[advance(2)],integrated=True,config={'periodic_updates':True}).final(turret_facing=270)
    yield Case('extra-ticks/turret-flag-off',vehicle(turret={'present':True,'facing':17},target_hex=[2,1]),
        [advance(2)],integrated=True,config={'periodic_updates':True}).final(turret_facing=17)
    for failure in ('DESTROYED','NONE'):
        w=weapon(recycle=4,temporary_failure=failure)
        yield Case('extra-ticks/recycle-stopped-'+failure,dict(equipment=[w],started=False),
            [action('dispatch',seconds=4),action('heartbeat',wall_seconds=0)]).final(**{'weapons.0.recycle':4})
    yield Case('extra-ticks/recycle-rollback',dict(equipment=[weapon(recycle=4)]),
        [action('heartbeat',wall_seconds=0),action('dispatch',seconds=1),action('heartbeat',wall_seconds=0)],
        clock={'event':-2}).final(**{'weapons.0.recycle':3,'weapons.0.slot_recycle':3})
    yield Case('extra-stagger/transferred-hit',dict(sections=[dict(location='LARM',front=0,internal=2)]),
        [hit(25,section='LA'),maintain('stagger_totals')],clock={'wall':17},random={'critical_rolls':[2]*5}).final(
        uncounted_damage=25).count('final.units.u.stagger',1).expect('final.units.u.stagger.0.wall',17)
    c=Case('extra-errors/unknown-inspected-unit',actions=[action('inspect',unit='missing')]);c.error='missing';yield c


def cases():
    for group in (sinks_and_heat,dump_and_ignition,fires,clocks_and_heights,errors,extended):
        yield from group()
