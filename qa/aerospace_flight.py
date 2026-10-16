"""QA procedures 1-4: source-derived controls, landing and flight boundaries."""
import math
import re
from aerospace_support import *


def controls():
    for name,row in feature_rows('flight',1):
        fixture=row['fixture'].split(';');kind=fixture[0];unit=craft(kind)
        if 'landed' in fixture:unit['aerospace']['landed']=True
        if 'spinning' in fixture:unit['aerospace']['spinning']=True
        if 'fallen' in fixture:unit['fallen']=True
        arg='' if row['argument']=='empty' else row['argument']
        c=Case(name,document(unit,[cmd('thrust',arg)]))
        number=f32(float(re.match(r'-?[\d.]+',arg)[0])) if arg else None
        error=("You're landed!" if 'landed' in fixture else 'You are unable to control your craft at the moment.' if 'spinning' in fixture else 'Minimum thrust you stay in air with is 6.5 kph.' if kind in ('AERO','DS') and number is not None and number<6.45 else "Your engine's dead, no way to thrust!" if 'fallen' in fixture else "Doh, thrust backwards.. where's your sense of adventure?" if number is not None and number<0 else 'Maximum thrust: 60.00 (6.00 kb/sec2)' if number is not None and number>60 else None)
        c.result(ok=error is None)
        if error:c.result(message=error).final(desired_speed=0)
        else:
            c.final(desired_speed=number or 0)
            if arg:c.expect('state.events',['MOVE',1],'event_count')
        yield c
    for name,row in feature_rows('flight',2):
        kind=row['class'];z=int(row['z']);arg='' if row['argument']=='empty' else row['argument'];command=row['command'].lower()
        unit=craft(kind,at=[10,10,z]);c=Case(name,document(unit,[cmd(command,arg)]))
        n=int(re.match(r'-?\d+',arg)[0]) if re.match(r'-?\d+',arg) else 0
        flag=1 if command=='climb' else -1;angle=flag*n
        if abs(angle)>90:angle=90*flag
        rejected=bool(arg and kind=='SPHEROID_DS' and z<100 and abs(angle)!=90)
        c.result(ok=not rejected).final(**{'aerospace.desired_angle':0 if rejected else angle})
        if rejected:c.result(message='You can go only up / down at <100 z!')
        if not arg:c.result(message='Present angle: 0 degrees.')
        yield c
    for name,row in feature_rows('flight',3):
        f=row['fixture'];kind=f.split(';')[0];z=int(re.search(r'Z(\d+)',f)[1]) if re.search(r'Z(\d+)',f) else 1
        desired=float(re.search(r'desired([\d.]+)',f)[1]);angle=int(re.search(r'angle(-?\d+)',f)[1]) if 'angle' in f else 0
        heading=int(re.search(r'heading(\d+)',f)[1]) if 'heading' in f else 0
        u=craft(kind,at=[10,10,z],aerospace=dict(desired_speed=desired,desired_angle=angle,desired_facing=heading,fuel=-1 if 'fuel-1' in f else 1000,speed=9 if 'scalar-speed9' in f else 0,spinning=';spin;' in f))
        streams={}
        if ';spin;' in f:streams=dict(aero_spin_speed=[10],aero_spin_angle=[15],aero_spin_heading=[3]);desired=60;angle=-90;heading=2
        c=Case(name,document(u,[diag('speed')],random=dict(streams=streams)))
        cap=5*(2.5 if kind=='AERO' else .7)*60/30*(.5 if z<100 else 1)
        magnitude=min(desired*5/(5 if 'fuel-1' in f else 1),cap)
        if desired==0:c.final(speed=9)
        else:
            c.expect('state.units.u.vertical_speed',magnitude*math.sin(math.radians(angle)),'close')
            c.expect('state.units.u.speed',abs(magnitude*math.cos(math.radians(angle))),'close')
        if kind=='SPHEROID_DS':c.final(facing=0)
        elif magnitude<10.75 or angle==-90:c.final(facing=heading)
        if ';spin;' in f:c.final(desired_speed=60,desired_facing=2,**{'aerospace.desired_angle':-90})
        yield c


def landing():
    for name,row in feature_rows('landing',1):
        kind=row['class'];desired,speed,vertical=map(float,(row['desired'],row['speed'],row['vertical']))
        u=craft(kind,aerospace=dict(desired_speed=desired,speed=speed,vertical_speed=vertical))
        c=Case(name,document(u,[cmd('land')]))
        lo,hi,down,up={'VTOL':(-15,15,-60,10),'AERO':(32,999,-30,10),'DS':(32,999,-25,10),'SPHEROID_DS':(-40,40,-40,15)}[kind]
        h=math.sqrt(abs(desired*desired-vertical*vertical))
        error="You're moving too fast to land." if h>=hi+1 else "You're moving too slowly to land." if h<lo else 'You are moving too fast to land. ' if int(vertical)>up or vertical<down else None
        c.result(ok=error is None)
        if error:c.result(message=error).final(**{'aerospace.landed':False,'desired_speed':desired,'speed':speed,'vertical_speed':vertical})
        else:c.final(at=[10,10,0],fz=0,speed=0,vertical_speed=0,desired_speed=desired,**{'aerospace.landed':True})
        yield c
    for name,row in feature_rows('landing',2):
        f=row['fixture'];kind=f.split(';')[0];u=craft(kind,aerospace=dict(desired_speed=40 if kind in ('AERO','DS') else 0,speed=40 if kind in ('AERO','DS') else 0));d=document(u,[cmd('land')])
        if 'building' in f:d['maps'][0]['default']=['BUILDING',0]
        if 'rough' in f:d['maps'][0]['default']=['ROUGH',0]
        if 'blzmapmode1' in f:d['aerospace']={'blzmapmode':1}
        if 'Z2' in f:u['at'][2]=2
        if 'actual31.99' in f:u['aerospace']['speed']=31.99;u['aerospace']['start_fz']=1 if 'start_fz1' in f else 0
        if 'stopped' in f:u['started']=False
        if 'fuel0' in f:u['core']['fuel']=0
        if 'fusion-free' in f:d['config']['nofusion_vtol_fuel']=True
        if ';landed;' in f:u['aerospace']['landed']=True
        if ';success;' in f:u['aerospace'].update(desired_speed=10,desired_angle=30,start_fx=1,start_fy=2,start_fz=3)
        errors={'AERO;building':"You can't land on this type of terrain.",'DS;rough;blzmapmode1':"You can't land on this type of terrain.",'VTOL;Z2;floor0':'You are too high to land here.','AERO;actual31.99;desired40;start_fz0':"You're falling, not landing! Pick up some horizontal speed first.",'AERO;actual31.99;desired40;start_fz1':"You're climbing not landing!",'VTOL;fuel0':'You lack fuel to maneuver for landing!','DS;landed;no-takeoff':"You're already landed!"}
        c=Case(name,d).result(ok=f not in errors)
        if f in errors:c.result(message=errors[f])
        else:c.final(**{'aerospace.landed':True,'speed':0,'vertical_speed':0,'start_fx':0,'start_fy':0,'start_fz':0})
        if ';success;' in f:c.final(desired_speed=10,**{'aerospace.desired_angle':30})
        yield c


def launches():
    # N callbacks print N..1; the following callback performs liftoff.
    for kind,count in [('VTOL',0),('AERO',10),('DS',300),('SPHEROID_DS',300)]:
        u=craft(kind,at=[10,10,0],aerospace=dict(landed=True,speed=32.25 if kind=='AERO' else 0))
        d=document(u,[cmd('takeoff'),inspect(),advance(count) if count else inspect(),inspect(),advance(1),inspect()])
        # No random movement before the launch boundary; PLOS has no peers.
        c=Case('procedures/launch-'+kind,d).result(ok=True)
        c.expect('results.1.events',['TAKEOFF',1],'event_count')
        c.expect('results.3.units.u.aerospace.landed',True).final(**{'aerospace.landed':False,'at':[10,10,1],'start_fx':0,'start_fy':0,'start_fz':0})
        if kind=='VTOL':c.final(vertical_speed=60,desired_speed=0)
        else:c.final(desired_speed=40,**{'aerospace.desired_angle':90})
        yield c
    u=craft(at=[10,10,0],aerospace=dict(landed=True,speed=32.25))
    yield Case('procedures/abort-relaunch',document(u,[cmd('takeoff'),advance(2),cmd('land'),advance(11),inspect(),cmd('takeoff'),advance(10),inspect(),advance(1)])).result(ok=True).expect('results.4.units.u.aerospace.landed',True).expect('results.7.units.u.aerospace.landed',True).final(**{'aerospace.landed':False})


def takeoff_examples():
    for name,row in feature_rows('takeoff',1):
        kind=row['class'];arg=row['argument'];u=craft(kind,at=[10,10,0],aerospace=dict(landed=True,speed=float(row['speed'])))
        count={'AERO':10,'VTOL':0,'DS':300,'SPHEROID_DS':300}[kind]
        if arg.startswith('wizard:'):arg=arg.split(':')[1];u['pilot_details']={'wizard':True};count=int(arg)
        elif arg=='empty':arg=''
        c=Case(name,document(u,[cmd('takeoff',arg),advance(max(0,count)),inspect(),advance(1)]))
        c.result(ok=True).expect('results.2.units.u.aerospace.landed',True).final(**{'aerospace.landed':False,'at':[10,10,1],'desired_speed':0 if kind=='VTOL' else 40})
        yield c
    for name,row in feature_rows('takeoff',2):
        f=row['fixture'];kind=f.split(';')[0];u=craft(kind,at=[10,10,0],aerospace=dict(landed=True,speed=32.25 if kind=='AERO' else 0));d=document(u,[cmd('takeoff')])
        if 'speed32.24' in f:u['aerospace']['speed']=32.24
        if 'fuel0' in f:u['core']['fuel']=0
        if 'fusion-free' in f:d['config']['nofusion_vtol_fuel']=True
        if ';ICE' in f:u['specials']=0x400000
        if 'rotor-destroyed' in f:u['sections']=[dict(index=5,internal=0,armor=0,config=2)]
        if 'fallen' in f:u['fallen']=True
        if 'maximum10.75' in f:u['core']['max_speed']=10.75
        if 'fortified' in f:u['status2']=0x00400000
        if 'airborne' in f:u['aerospace']['landed']=False
        if 'underground' in f:d['maps'][0]['flags']=16
        if 'stopped' in f:u['started']=False
        if 'argument2' in f:d['actions'][0]['args']='2'
        if 'already-taking-off' in f:d['actions'].insert(0,cmd('takeoff'))
        c=Case(name,d);index=len(d['actions'])-1
        success=f=='VTOL;fuel0;fusion-free'
        c.result(index,ok=success).expect('state.events',['TAKEOFF',int(success or 'already-taking-off' in f)],'event_count')
        yield c
    for name,row in feature_rows('takeoff',3):
        count=int(row['count']);u=craft('DS',at=[10,10,0],aerospace=dict(landed=True));c=Case(name,document(u,[diag('takeoff_event',count=count),advance(1)]))
        c.expect('state.events',['TAKEOFF',int(count>0)],'event_count').final(**{'aerospace.landed':count>0})
        if count in (1,2,5,10):c.text('state.units.u.messages',f'Launch countdown: {count}.')
        elif count:c.expect('state.units.u.messages',f'Launch countdown: {count}.','excludes')
        yield c
    for name,row in feature_rows('takeoff',4):
        transition=row['transition'];kind='VTOL' if transition.startswith('VTOL') else 'DS' if transition.startswith('DS') else 'AERO';u=craft(kind,at=[10,10,0],aerospace=dict(landed=True,speed=32.25 if kind=='AERO' else 0));actions=[cmd('takeoff')]
        if transition.startswith('AERO-speed'):actions += [configure(speed=32.24),advance(11)];landed=True
        elif transition.startswith('DS-speed'):actions += [advance(301)];landed=False
        elif transition=='land-before-first-callback':actions += [cmd('land'),advance(15)];landed=True
        elif transition.startswith('VTOL-fuel'):actions += [configure(fuel=0),cmd('land')];landed=True
        else:u['hidden']=True;u['aerospace']['spinning']=True;actions += [inspect(),advance(11)];landed=False
        c=Case(name,document(u,actions)).result(ok=True).final(**{'aerospace.landed':landed})
        if transition.startswith('VTOL-fuel'):c.result(2,ok=False).expect('state.events',['TAKEOFF',1],'event_count')
        elif not landed:c.expect('state.events',['MOVE',1],'event_count').final(**{'aerospace.spinning':False})
        else:c.expect('state.events',['TAKEOFF',0],'event_count')
        yield c


def zones():
    for name,row in feature_rows('landing',3):
        f=row['fixture'];u=craft(team=1);d=document(u,[]);actions=[];terrain='LIGHT_FOREST' if 'forest' in f else 'ROAD' if 'road' in f else 'GRASSLAND'
        d['maps'][0]['default']=[terrain,0]
        if 'uneven' in f or 'neighbor-different' in f:actions.append(op('map_command',name='addhex',args='10 9 g 1'))
        if 'map-edge' in f:u['at']=[0,0,1]
        if 'mode1' in f:d['aerospace']={'blzmapmode':1}
        blocked='blocked' in f or 'block-' in f
        if blocked:
            distance=2 if 'greater-radius' in f else 1 if 'distance-equal' in f else 0
            actions.append(op('map_command',name='block',args=f'10 {10+distance} {1 if distance else 0} {1 if "block-team1" in f else 0}'))
        actions.append(cmd('checklz'));d['actions']=actions
        result=1 if terrain=='LIGHT_FOREST' and 'mode1' not in f else 2 if ('uneven' in f or 'neighbor-different' in f or 'map-edge' in f) and 'mode1' not in f else 3 if blocked and 'block-team1' not in f and 'greater-radius' not in f else 0
        fragment=['looks good enough','Improper terrain','Uneven ground','Blocked landing zone'][result]
        yield Case(name,d).result(len(actions)-1,ok=True).text(f'results.{len(actions)-1}.message',fragment)
    for name,row in feature_rows('landing',4):
        f=row['fixture'];u=craft();actions=[]
        if 'warning' in f:
            severity=int(re.search(r'severity(-?\d+)',f)[1]);blocked='blocked' in f
            if blocked:actions.append(op('map_command',name='block',args='10 10 0'))
            actions.append(diag('warning',severity=severity));c=Case(name,document(u,actions))
            if blocked:
                color='%ch%cr' if severity==1 else '%ch%cy' if severity==0 else '';text='CLIMB UP NOW!!!' if severity==1 else 'No further descent is advisable.' if severity==0 else 'Please do not even consider landing here.'
                c.text('state.units.u.messages',f'{color}WARNING: Blocked landing zone - {text}%cn')
            else:c.final(messages=[])
        else:
            arg='10 11' if 'coordinates' in f or 'observer' in f else '10' if 'one-argument' in f else ''
            u['aerospace']['tac_range']=0 if 'exceeds-tac' in f else 1
            if 'observer' in f:u['observer']=True
            if 'stopped' in f:u['started']=False
            error='Invalid number of parameters!' if 'one-argument' in f else 'Out of range!' if 'exceeds-tac' in f and 'observer' not in f else None
            c=Case(name,document(u,[cmd('checklz',arg)])).result(ok=not(error or 'stopped' in f))
            if error:c.result(message=error)
        yield c


def fuel_and_updates():
    for name,row in feature_rows('updates',1):
        f=row['fixture'];kind=f.split(';')[0];fuel=int(re.search(r'fuel(-?\d+)',f)[1]);speed=float(re.search(r'speed([\d.]+)',f)[1]) if 'speed' in f else 0;vertical=float(re.search(r'vertical([\d.]+)',f)[1]) if 'vertical' in f else 0;z=100 if 'Z100' in f else 99
        u=craft(kind,at=[10,10,z],started='stopped' not in f,aerospace=dict(fuel=fuel,speed=speed,vertical_speed=vertical,landed='landed' in f));d=document(u,[diag('fuel')])
        if 'fusion-free' in f:d['config']['nofusion_vtol_fuel']=True
        free='stopped' in f or 'fusion-free' in f or 'draw0' in f
        if 'draw' in f:d['random']['streams']['fuel_check']=[0 if 'draw0' in f else 1]
        cost=int(speed/60) if speed>60 and z<100 else 1
        after=fuel if free or fuel<0 else max(0,fuel-cost) if fuel>0 else -1
        stop=not free and fuel<=0 and kind not in ('DS','SPHEROID_DS')
        c=Case(name,d).result(stop=stop,fuel=after).final(fuel=after)
        c.expect('state.events',['FALL',int(stop and fuel==0 and 'landed' not in f)],'event_count')
        if stop and fuel==0:c.final(speed=0,desired_speed=0)
        yield c
    for name,row in feature_rows('updates',2):
        f=row['fixture'];now=int(row['now']);spinning=';spinning' in f;started=not f.startswith('stopped');destroyed='destroyed' in f;landed='landed' in f
        u=craft(started=started,destroyed=destroyed,conscious='unconscious' not in f,aerospace=dict(spinning=spinning,landed=landed),core=dict(weap_heat=20,plus_heat=.05 if 'plus_heat0.05' in f else 0))
        if destroyed:u['status']=0x01000000|0x20
        active=not destroyed and (now//3%5!=0 or spinning and not landed)
        rolls=dict(visibility_change=[7] if active and started else [],pilot_rolls=[12 if 'success' in f else 2] if spinning and not landed and now//3%5==0 else [],failure_generic_chance=[5000],fall_directions=[1],fall_pilot_rolls=[12],hit_location_rolls=[7]*10,damage_entry=[7]*10,tow_rolls=[12]*10)
        # Explicit pilot skill zero makes modifier7 attainable by the success dice.
        u['piloting']=0
        actions=[op('clock',name='skip_seconds',seconds=now),diag('update')]
        c=Case(name,document(u,actions,random=dict(streams=rolls)))
        c.final(vis_mod=57 if active and started else 50,**{'aerospace.spinning':spinning and 'success' not in f})
        c.final(heat=10 if not destroyed and (started or 'plus_heat0.05' in f) else 0)
        c.expect('state.units.u.missing_services','aero_update','excludes')
        yield c


def motion():
    for name,row in feature_rows('flight',4):
        f=row['fixture'];kind='SPHEROID_DS' if f.startswith('spheroid') else 'DS' if f.startswith('DS') else 'AERO';u=craft(kind,at=[10,10,100]);d=document(u);actions=[]
        d['random']['streams'].update(fuel_check=[1]*40,sensor={'unused':0} if False else [])
        del d['random']['streams']['sensor']
        if 'speed-command' in f:actions=[cmd('speed','20')];c=Case(name,d).result(ok=False)
        elif 'heading-command' in f:u['aerospace']['spinning']=True;actions=[cmd('heading','90')];c=Case(name,d).result(ok=False)
        elif kind=='SPHEROID_DS':
            u['aerospace']['start_fx']=20;actions=[cmd('heading','90'),advance(1)];c=Case(name,d).expect('state.units.u.facing',0,'greater')
        elif 'thrust20' in f:
            actions=[cmd('thrust','20'),cmd('climb','30'),advance(2)];c=Case(name,d).result(ok=True).result(1,ok=True).expect('state.units.u.fz',6450,'greater').expect('state.units.u.fy',3386.25,'less').expect('state.events',['MOVE',1],'event_count').expect('state.units.u.fuel',1000,'less')
        elif 'fallen' in f:
            u.update(started=False,fallen=True);u['aerospace']['start_fz']=0;actions=[diag('move'),advance(1)];c=Case(name,d).final(start_fz=-1).expect('state.units.u.fz',6449.5,'close')
        elif 'descend' in f:
            old,new=map(int,re.search(r'descend(\d+)-to(\d+)',f).groups());u.update(started=False,at=[10,10,old]);u['aerospace'].update(start_fx=20,start_fz=(new-old)*129)
            actions=[op('map_command',name='block',args='10 10 1'),diag('move'),advance(1)];c=Case(name,d).final(**{'at.2':new})
            severity=1 if new<10 else 0 if new<50 else -1
            advice='CLIMB UP NOW!!!' if severity==1 else 'No further descent is advisable.' if severity==0 else 'Please do not even consider landing here.'
            color='%ch%cr' if severity==1 else '%ch%cy' if severity==0 else ''
            c.text('state.units.u.messages',f'{color}WARNING: Blocked landing zone - {advice}%cn')
            c.final(start_fx=0 if old==100 and new==99 else 20,**{'aerospace.desired_angle':90 if new==99 else 0})
        elif 'ground-penetration' in f:
            u.update(started=False,at=[10,10,1]);u['aerospace']['start_fz']=-258;actions=[diag('move'),advance(1)];d['random']['streams'].update(fall_directions=[1],fall_pilot_rolls=[12],character_d6=[6]*20,hit_location_rolls=[7]*20,damage_entry=[7]*20,tow_rolls=[12]*20)
            c=Case(name,d).final(**{'aerospace.landed':True,'at.2':0}).expect('state.units.u.damage_taken',0,'greater')
        else:
            u.update(started=False,at=[29,10,100]);u['aerospace']['start_fx']=1000;d['maps'][0]['linked']=True;actions=[diag('move'),advance(1)];c=Case(name,d).expect('state.units.u.at.0',29,'less')
        d['actions']=actions
        yield c


def control_effects():
    for name,row in list(feature_rows('updates',3))[:4]:
        f=row['fixture'];u=craft(destroyed='destroyed' in f,aerospace=dict(landed='landed' in f,spinning='already-spinning' in f,start_spin=5 if 'start_spin5' in f else 0));actions=[op('clock',name='skip_seconds',seconds=12),diag('control')]
        active=not any(word in f for word in ('destroyed','landed','already-spinning'))
        c=Case(name,document(u,actions)).final(**{'aerospace.spinning':active or 'already-spinning' in f,'aerospace.start_spin':12 if active else 5 if 'start_spin5' in f else 0})
        if active:c.text('state.units.u.messages','You lose control of your craft!')
        else:c.final(messages=[])
        yield c
    for name,row in feature_rows('updates',4):
        f=row['fixture'];kind='VTOL' if 'VTOL' in f else 'DS' if 'DS' in f else 'AERO';moving=f.startswith('moving');u=craft(kind,at=[10,10,100],aerospace=dict(fuel=0 if moving else 1,speed=20 if moving else 0,desired_speed=20 if moving else 0));actions=[diag('move'),advance(1)] if moving else [op('clock',name='heartbeat')]
        d=document(u,actions,random=dict(streams={'fuel_check':[1]*10}));c=Case(name,d)
        if moving:c.final(fuel=-1).expect('state.events',['FALL',int(kind!='DS')],'event_count').expect('state.events',['MOVE',int(kind=='DS')],'event_count')
        else:c.final(fuel=1 if kind=='DS' else 0)
        yield c
