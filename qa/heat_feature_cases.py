"""Translate every accepted example into a public CLI workflow and literal oracle."""
from heat_support import (Case, action, command, maintain, advance, hit, external,
                          weapon, bin_fixture, armed, vehicle, only_front)


def sinks(n, r):
    heat = dict(sink_technology=r.get('technology','SINGLE'),
                sink_capacity=r.get('capacity',10),
                disabled_capacity=r.get('disabled',8 if n==4 else 0),
                weapon_heat=r.get('weapon_heat',0),cutoff=n in (1,4))
    c = Case('', dict(heat_state=heat), [advance(2*r.get('updates',1))],
             integrated=True, config={'periodic_updates':True})
    if n == 3:
        heat['cutoff'] = r['initial']
        c.document['actions'] = [command('heatcutoff') for _ in range(r['requests'])]+[advance(r['seconds'])]
        return c.accepted(1).final(cutoff=r['active']).pending('cutoff_deadline',r['pending'])
    if n == 4:
        c.document['map'] = {'default':['WATER',1]}
        c.document['units'][0]['at'] = [2,2,-1]
        heat['leg_sink_slots'] = 4
    c.final(disabled_capacity=r['remaining_disabled'],heat=r.get('heat',0))
    if 'dissipation' in r: c.final(minus_heat=r['dissipation'])
    return c


def heat(n, r):
    h = dict(sink_capacity=r.get('capacity',10),weapon_heat=20)
    u = dict(heat_state=h)
    c = Case('',u,[advance(r.get('seconds',2))],integrated=n<=3,
             config={'periodic_updates':True})
    if n == 1:
        h.update(heat=r['old_heat'],plus_heat=20)
        c.document['units'][0]['started']=r['started']
        return c.final(heat=r['heat'],weapon_heat=r['retained'])
    if n == 2:
        c.document['map'] = dict(temperature=r['temperature'],special_rules=r['special'])
        if r['jellied']: c.document['units'][0]['events']={'inferno':180}
    elif n == 3:
        h['leg_sink_slots']=r['leg_slots']
        c.document['map']={'default':['WATER',abs(r['z']) or 2]}
        c.document['units'][0].update(at=[2,2,r['z']],fallen=r['fallen'])
    elif n == 4:
        h.update(heat=r['heat'],weapon_heat=0)
        c.document.update(clock={'event':r['tick']},config={'periodic_updates':False},
                          actions=[maintain('overheat')],
                          random={'shutdown_rolls':[r['roll']]})
        return c.final(started=r['started'],last_overheat_tick=r['last_check'])
    elif n == 5:
        h.update(weapon_heat=r['heat']+10,life_support_destroyed=True)
        c.document.update(clock={'event':r['tick']},config={'periodic_updates':False},
                          actions=[maintain('heat')],random={'shutdown_rolls':[12]})
        return c.final(pilot_hits=r['injuries'],heat=r['heat'])
    return c.final(minus_heat=r['dissipation'],heat=r['heat'])


def selector(value):
    return {'WEAPON_A':['0'],'WEAPON_B':['1']}.get(value,value.split())


def dumping(n,r):
    u=armed(r.get('rounds',4 if n==3 else 3))
    c=Case('',u,integrated=True)
    if n==1:
        u['equipment'][0]['ammo_per_ton']=r['per_ton']
        c.document['clock']={'event':r['start_tick']}
        c.document['actions']=[command('dump','all'),advance(r['seconds'])]
    elif n==2:
        u['equipment'].append(weapon('B',section='LA'))
        u['bins'] += [bin_fixture(3,slot=2,weapon=1),bin_fixture(3,section='RT')]
        c.document['actions']=[command('dump',*selector(r['selector'])),advance(1)]
        return c.accepted(1).final(**{'bins.0.rounds':r['left_a'],
                                     'bins.1.rounds':r['left_b'],'bins.2.rounds':r['right_a']})
    elif n==3:
        commands={'ALL':command('dump','all'),'STOP':command('dump','stop'),
                  'BIN':command('dump','LT','1'),'SHUTDOWN':command('shutdown')}
        c.document['actions']=[commands[t] for t in r['workflow'].split('_')]+[advance(2)]
        # Count only dump command acceptances; shutdown is a separate accepted action.
        c.accepted(r['accepted']+(r['workflow']=='ALL_SHUTDOWN'))
    else:
        c.document['units'][0].update(max_speed=64.5,desired_speed=r['speed'],
            states=['started','jumping'] if r['jumping'] else ['started'])
        if r['condition']=='EMPTY':u['bins'][0]['rounds']=0
        if r['condition']=='BROKEN_LOADED':u['bins'][0]['condition']='BROKEN'
        c.document['actions']=[command('dump','all')]
        return c.accepted(int(r['outcome']=='ACCEPTED')).final(dumping=r['pending'])
    return c.final(**{'bins.0.rounds':r['remaining'],'dumping':r['pending']}).pending('dump_deadline',r['pending'])


def ignition(n,r):
    u=armed()
    c=Case('',u,integrated=False,random={'dump_candidates':[r.get('index',0)],'fire_rolls':[]})
    loc=r.get('location','CT')
    c.document['actions']=[command('dump',*selector(r.get('selector','all'))),
        hit(section=loc,arc=r.get('arc','REAR'),weapon=None if r.get('cause')=='INTERNAL_EFFECT' else 0)]
    if n==2:
        w=u['equipment'][0]
        w.update(category=r['category'].replace('_NO_TABLE',''),damage=r['base'],
                 salvo=r['salvo'],table_match=r['category']!='MISSILE_NO_TABLE')
    if n==3:
        u['equipment'].append(weapon('B',damage=5,section='LA'))
        u['bins'].append(bin_fixture(4,section='RT',weapon=1))
        c.final(**{'bins.0.rounds':r['a'],'bins.1.rounds':r['b'],'dumping':False})
    else:
        c.final(**{'bins.0.rounds':r['remaining'],'dumping':r['pending']})
    section={'CT':4,'LT':2,'RT':3,'LLEG':5}[loc]
    rear=r.get('arc','REAR')=='REAR' and section in (2,3,4)
    c.final(**{f'sections.{section}.{"rear" if rear else "front"}':99-r['damage']})
    return c


def fire(n,r):
    c=Case('',vehicle(),integrated=n in (2,3),config={'periodic_updates':False,'advanced_vehicle_fire':True})
    u=c.document['units'][0]
    if n==1:
        u.update({'class':r['class'],'movement':r['movement']})
        c.document.update(actions=[external(False)],random={'fire_rolls':[r['roll']],
                            'fire_damage':[3]*8,'motive_rolls':[8]})
        response=r['response']
        dead=('CTORSO','RLEG','HEAD') if r['class']=='VTOL' else ('LLEG','RLEG','HEAD')
        u['sections']=[dict(location=loc,internal=0) for loc in dead]
        live=(0,1,2,3,5) if r['class']=='VTOL' else (0,1,2,3,4)
        c.count('final.units.u.burning_sides',5 if response=='BURNING' else 0)
        if response in ('BURNING','SECTION_DAMAGE'):
            for loc in live:c.final(**{f'sections.{loc}.front':97})
        else:
            c.final(**{'sections.0.front':100})
        if response=='MOTIVE_HIT':
            c.notice('motive').final(pilot_skill_base=2 if r['movement']=='WHEEL' else 1,
                                     max_speed=53.75 if r['movement']=='WHEEL' else 64.5)
        return c
    if n in (2,3):
        u['sections']=only_front()
        if n==2:
            c.document.update(actions=[external(),advance(r['seconds'])],
                              random={'fire_damage':[r['initial'],r['next']]})
            return c.final(**{'sections.0.front':100-r['damage']}).count('final.units.u.burning_sides',r['pending'])
        u.update(started=r['started'],events={'burns':[{'section':'LSIDE','remaining':60}]})
        c.document.update(actions=[command('extinguish') for _ in range(r['requests'])]+[advance(r['seconds'])],
                          random={'fire_damage':[2,2]})
        return c.accepted(r['accepted']).count('final.units.u.burning_sides',int(r['burning'])).pending('extinguish_deadline',r['pending'])
    u.clear();u.update(name='u',events={'inferno':180},at=[2,2,r['z']],fallen=r['fallen'])
    c.document.update(map={'default':[r['terrain'],abs(r['elevation'])]},
                      actions=[maintain('water_extinguish')])
    c.final(jellied=r['jellied']).pending('inferno_deadline',r['jellied'])
    c.count('final.decorations',int(r['steam']))
    if r['steam']:c.expect('final.decorations.0.deadline',120)
    return c


def stagger(n,r):
    c=Case('')
    u=c.document['units'][0]
    if n==1:
        u['history']=[dict(amount=12,wall=0,counted=False),dict(amount=9,wall=0,counted=True)]
        c.document.update(clock={'wall':r['age']},actions=[maintain('stagger_totals'),maintain('stagger_expiry')])
        c.expect('results.0.uncounted',r['uncounted']).expect('results.0.counted',r['counted'])
    elif n==2:
        u['history']=[dict(amount=a,wall=0,counted=b) for a,b in [(12,False),(9,True),(15,False),(8,False)]]
        c.document['actions']=[action('stagger',unit='u',action=r['action'],level=r['level'])]
        c.final(uncounted_damage=r['uncounted'],counted_damage=r['counted'])
    elif n==3:
        u.update(tons=r['tons'],actual_tons=r['tons'])
        c.document.update(config={'periodic_updates':False,'new_stagger':r['mode']},
                          random={'pilot_rolls':[r['roll']],'fall_pilot_rolls':[12], 'fall_directions':[1],
                                  'hit_location_rolls':[7]*30},
                          actions=[hit(r['damage']),action('heartbeat',wall_seconds=r['seconds'])])
        c.expect('results.1.rolls',r['checks'],'primary_rolls').final(fallen=r['fallen'])
    else:
        u.update(history=[dict(amount=20,wall=0,counted=True)],last_stagger_check=5)
        c.document.update(clock={'wall':6},random={'pilot_rolls':[12]},
                          actions=[hit(r['damage']),action('heartbeat',wall_seconds=4)])
        c.count('results.1.rolls',r['checks'])
        if r['modifier']!='NONE':c.expect('results.1.rolls.0.modifier',r['modifier'])
        return c
    return c.count('final.units.u.stagger',r['nodes'])


def heights(n,r):
    u={'class':'VEH_NAVAL' if n<=2 else 'VTOL','movement':'SUB' if n<=2 else 'VTOL',
       'fuel':100,'at':[2,2,r.get('z',0)],'vertical_speed':r.get('vertical',-10.75)}
    terrain=r.get('terrain','WATER')
    elevation=abs(r['bottom']) if n==1 else 3 if n==4 or (n==2 and terrain in ('WATER','ICE','BRIDGE')) else 1 if terrain=='WATER' else 0
    c=Case('',u,[maintain('height')],map={'default':[terrain,elevation]},random={'pilot_rolls':[12]*10,'hit_location_rolls':[7]*20,'fall_directions':[1]})
    if n==1:
        c.document['units'][0]['fz']=r['fz']
        return c.final(**{'at.2':r['final_z'],'fz':r['final_fz'],'vertical_speed':r['vertical']})
    if n==2:
        c.document['units'][0].update(fz=1,vertical_speed=10.75,speed=21.5,desired_speed=32.25,facing=90,desired_facing=90)
        return c.final(fz=r['fz'],speed=r['speed'],desired_speed=r['desired'],facing=r['facing'],desired_facing=r['facing'],vertical_speed=0)
    if n==3:
        c.final(**{'destroyed':r['destroyed'],'at.2':r['final_z'],'vertical_speed':r['final_vertical']})
        if r['z']>=300:c.final(fz=19285.5)
        if r['destroyed']:c.final(kill_reason='FLOOD')
        return c
    c.document['units'][0].update(vertical_speed=-21.5,desired_speed=21.5)
    c.final(**{'landed':r['landed'],'at.2':r['final_z']})
    c.notice('CRASH!',int(r['crash']))
    if r['crash']:c.final(fz=193.5,speed=0,vertical_speed=0)
    return c


def ticks(n,r):
    c=Case('')
    u=c.document['units'][0]
    if n==1:
        u.update(speed=54,desired_speed=54,max_speed=64.5,states=['started','gyro_damaged'])
        if r['posture'] in ('FALLEN','JUMPING'):u['states'].append(r['posture'].lower())
        if r['posture']=='OOD':u['cocoon']=10
        c.document.update(clock={'event':r['tick']},random={'pilot_rolls':[12]},actions=[maintain('pilot')])
        return c.count('results.0.rolls',r['checks'])
    if n==2:
        u.update(movement=r['movement'],speed=r['speed'],max_speed=64.5)
        c.document.update(map={'special_rules':True,'gravity':150},clock={'event':30},
                          random={'pilot_rolls':[2],'critical_rolls':[2]*4},actions=[maintain('pilot')])
        return c.expect('final.units.u.sections',[r['damage']]*r['limbs'],'damage_deltas').final(fallen=False)
    if n==3:
        u.update(vehicle(facing=r['hull'],desired_facing=r['hull'],auto_turret=True,
                         turret={'present':r['state']!='DESTROYED_TURRET','facing':17,
                                 'jammed':r['state']=='JAMMED','locked':r['state']=='LOCKED'},
                         target_id='target',started=r['state']!='STOPPED',
                         conscious=r['state']!='UNCONSCIOUS',blinded=r['state']=='BLINDED'))
        c.document['units'].append(dict(name='target',relative_position={'to':'u','bearing':r['bearing'],'range':1}))
        c.document.update(config={'periodic_updates':True},actions=[advance(2)])
        c.integrated=True
        return c.final(turret_facing=r['turret'],los=r['los'])
    if n==4:
        w=weapon();w.update(category='ENERGY',recycle=4,temporary_failure=r['failure'])
        u['equipment']=[w]
        c.document['actions']=[action('dispatch',seconds=r['seconds']),action('heartbeat',wall_seconds=0),action('heartbeat',wall_seconds=0)]
        c.final(**{'weapons.0.recycle':r['remaining'],'weapons.0.slot_recycle':r['remaining'],
                   'weapons.0.temporary_failure':0 if r['after']=='NONE' else 1})
        c.notice('finished recycling',int(r['notice']=='READY')).notice('operational',int(r['notice']=='OPERATIONAL'))
        return c
    if n==5:
        u.update({'class':r['class'],'movement':r['movement']})
        c.document.update(map={'default':['FIRE',0]},actions=[action('enter_hex',unit='u',at=[3,2,0])],random={'fire_rolls':[2]})
        return c.final(destroyed=r['destroyed'],kill_reason=None if r['reason']=='NONE' else r['reason'])
    u.update({'class':'DS','movement':'FLY','last_dropship_notice':r['last']})
    c.document.update(clock={'event':r['now']},actions=[maintain('dropship_notice')])
    return c.expect('results.0.emitted',r['emitted']).final(last_dropship_notice=r['stored'])


BUILDERS = dict(sinks=sinks,heat=heat,dumping=dumping,ignition=ignition,
                fire=fire,stagger=stagger,heights=heights,ticks=ticks)
