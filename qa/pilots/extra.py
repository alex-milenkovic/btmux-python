"""Additional ordinary paths required by the fourteen QA procedures."""
from qa.pilots.workflows import *


def run_extra():
    a=Audit('extra')
    # Real successful head shots distinguish exact-one Toughness/Pain resistance.
    for advantage in ('Toughness','Pain_Resistance'):
        for value in (1,2):
            u=unit(character=101,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
            v=unit('v',20,at=[3,1,0],facing=180,character=102)
            c=character(102,wizard=False,values={**dict.fromkeys(ATTRS,5),advantage:value})
            d=game([shoot(),inspect()],units=[u,v],characters=[character(),c],periodic=False,
                   streams={'hit_location_rolls':[12],'character_d6':[1,1,6]})
            o=record(a,'head-'+advantage+str(value),d)
            a.true('ordinary head hit',o['results'][0]['attack']['hit'])
            a.eq('persisted injury',health(o,102),[10,0])
            # With Pain1 BTH2 succeeds on2; Pain2 uses BTH3. Toughness
            # uses the best two of three dice only when its value is one.
            a.eq('exact-one consciousness',bool(events(o['state'],'RECOVERY')),value==2)
    for initial,expected,dead in [([45,0],[50,5],False),([45,45],[50,49],True)]:
        c=character(102,wizard=False,values={**dict.fromkeys(ATTRS,5),'Bruise':initial[0],'Lethal':initial[1]})
        u=unit(character=101,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
        v=unit('v',20,at=[3,1,0],facing=180,character=102)
        o=record(a,'head-overflow-'+str(initial[1]),game([shoot(),inspect()],units=[u,v],characters=[character(),c],periodic=False,streams={'hit_location_rolls':[12]}))
        a.eq('real head overflow',health(o,102),expected)
        a.eq('death controls actor',o['state']['characters']['102']['alive'],not dead)
        a.eq('no postfatal pilot increment',unit_state(o,'v')['pilot_hits'],0 if dead else 1)
    for condition in ('miss','rejected','friendly','destroyed','MW'):
        u=unit(character=101,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
        v=unit('v',20,at=[3,1,0],facing=180)
        if condition=='friendly':v['team']=1
        if condition=='destroyed':v['destroyed']=True
        if condition=='MW':v['class']='MW'
        actions=[dict(op='clock',name='skip_seconds',seconds=101),shoot(99 if condition=='rejected' else 0),inspect()]
        o=record(a,'gun-exclusion-'+condition,game(actions,units=[u,v],periodic=False,streams={'attack_rolls':[2 if condition=='miss' else 12]}))
        a.eq('no spurious gun gain',unit_state(o)['xp_requests'],[])
    # The supported ordinary indirect-fire caller awards both Spot and Arty
    # before dispatching the real missile attack, as mech.spot.c specifies.
    u=unit(character=101,at=[3,12,0],weapons=[dict(name='IS.LRM-10',section=0,critical=4)],
           sections=[dict(index=0,armor=100,internal=30,slots=[dict(index=8,ammo='IS.LRM-10',data=12)])])
    s=unit('spotter',30,character=103,team=1,contact_id='SS',at=[3,5,0])
    v=unit('v',20,at=[3,2,0],facing=180)
    actions=[dict(op='clock',name='skip_seconds',seconds=101),command('spot',unit='spotter',args='SS'),command('lock',unit='spotter',args='VV'),command('spot',args='SS'),command('fire',args='0'),inspect()]
    d=game(actions,units=[u,s,v],characters=[character(values={**dict.fromkeys(ATTRS,5),'Gunnery-Battlemech':8}),character(103,location=30,values={**dict.fromkeys(ATTRS,5),'Gunnery-Spotting':8})],periodic=False)
    o=record(a,'ordinary-indirect-awards',d);commands_ok(a,d,o)
    a.true('spotter actual gain',any(q['producer']=='spot' and q['applied'] for q in unit_state(o,'spotter')['xp_requests']))
    a.true('attacker actual artillery gain',any(q['producer']=='artillery' and q['applied'] for q in unit_state(o)['xp_requests']))
    a.true('real missile shot',o['results'][4]['attack']['hit'])
    # Startup owns cached perception; close-range PLOS invokes the real producer.
    for roll in (2,12):
        c=character(values={**dict.fromkeys(ATTRS,5),'Perception':2})
        u=unit(character=101,started=False);v=unit('v',20,at=[3,2,0])
        d=game([dict(op='clock',name='skip_seconds',seconds=101),command('startup'),advance(40),inspect()],units=[u,v],characters=[c],streams={'sensor.perception_xp':[0]*1000,'perception_rolls':[roll]*1000})
        o=record(a,'sensor-perception-'+str(roll),d);commands_ok(a,d,o)
        gains=[q for q in unit_state(o)['xp_requests'] if q['producer']=='perception']
        a.eq('real perception success gain',any(q['applied'] for q in gains),roll==12)
        a.eq('startup cached perception retained',unit_state(o)['per'],6)
    u=ba(8);u['infantry_specials']|=0x100|0x200
    u['sections'][7]['slots']=[dict(index=4,weapon='PC.SMG',firemode=0x20000)]
    d=game([command('swarm',args='VV'),command('jettison'),command('swarm',args='VV'),inspect()],units=[u,unit('v',20)],periodic=False)
    o=record(a,'jettison-then-swarm',d)
    a.error(o['results'][0],'jettisons');a.eq('real pack release',o['results'][1]['count'],1)
    a.true('ordinary swarm after release',o['results'][2].get('success'))
    u=ba(8,at=[3,10,0]);v=unit('v',20,character=102,at=[3,3,0],facing=180)
    friend=unit('friend',30,team=1,contact_id='FF',at=[3,11,0],weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
    visibility=dict(op='pilot_diagnose',kind='visibility',unit='v',target='u')
    acts=[visibility,command('shutdown',unit='v'),command('hide'),advance(61),
          command('startup',unit='v'),advance(30),visibility,
          shoot(unit='friend',target='UU'),advance(2),visibility,inspect()]
    d=game(acts,units=[u,v,friend],characters=[character(),character(102,wizard=False)],streams={'tow_rolls':[12]*20});d['map']['default']=['ROUGH',0]
    o=a.cli('real-hide-LOS-and-damage',d,mode='ordinary actions; diagnostic LOS readout')
    commands_ok(a,d,o)
    a.eq('real enemy LOS before/hidden/revealed',[o['results'][i]['visible'] for i in (0,6,9)],[True,False,True])
    a.true('actual revealing hit',o['results'][7]['attack']['hit'])
    a.eq('real damage clears hiding',bool(unit_state(o)['crit_status']&8),False)
    u=ba(8)
    u['sections'][7].update(armor=0,internal=0,recycle=3,
        slots=[dict(index=4,weapon='PC.SMG',data=3)])
    o=record(a,'destroyed-section7-skips-both-guards',game(
        [command('swarm',args='VV'),inspect()],units=[u,unit('v',20)],periodic=False))
    a.true('ordinary swarm skips destroyed busy section',o['results'][0].get('success'))
    a.eq('dead member recycle untouched',unit_state(o)['sections'][7]['recycle'],3)
    return a.save()
