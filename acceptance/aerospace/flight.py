"""Flight, landing, periodic and exhaust acceptance bindings."""
import math,re
from types import SimpleNamespace
from unittest.mock import patch
from . import step,eq,near,invoke,position,make_unit,events,messages,check,U,M,S,C
from core.events import EventType as E
from physics import aerospace as a
from physics.heights import fuel_check
from entities.mech import MechStatus2 as S2,Specials,VehicleLocation,SectionConfig
from entities.map import BUILDING,ROUGH,LIGHT_FOREST,ROAD,GRASSLAND,FIRE,SMOKE


def fixture(w,text):
    w['fixture']=text;u=w['u'];e=w['engine']
    for token in text.split(';'):
        if token in U.__members__:
            u.unit_type=U[token];u.move_type=M.VTOL if token=='VTOL' else M.BIPED if token=='MECH' else M.FLY
        elif token in ('airborne','landed'):u.clear_status(S.LANDED) if token=='airborne' else u.set_status(S.LANDED)
        elif token=='stopped':u.clear_status(S.STARTED)
        elif token=='started':u.set_status(S.STARTED)
        elif token in ('spin','spinning','already-spinning'):u.set_crit_status(C.SPINNING)
        elif token=='destroyed':u.set_status(S.DESTROYED)
        elif token in ('unconscious','unconscious-pilot'):u.set_status(S.UNCONSCIOUS)
        elif token=='fallen':u.set_status(S.FALLEN)
        elif token=='fortified':u.set_status2(S2.FORTIFIED)
        elif token=='FIRED':u.set_status(S.FIRED)
        elif token=='fusion-free':e.nofusion_vtol_fuel=True
        elif token=='ICE':u.specials|=Specials.ICE_TECH
        elif token=='rotor-destroyed':u.sections[VehicleLocation.ROTOR].internal=0;u.sections[VehicleLocation.ROTOR].armor=0
        elif token=='underground':u.map.flags|=16
        elif token in ('building','rough','grass','road','forest'):
            u.map.set_terrain(u.x,u.y,dict(building=BUILDING,rough=ROUGH,grass=GRASSLAND,road=ROAD,forest=LIGHT_FOREST)[token]);u.terrain=u.map.terrain(u.x,u.y)
        elif token=='vectors-nonzero':u.start_fx=u.start_fy=u.start_fz=10
        elif token=='success':pass
        elif token=='current0' or token=='current-vector0':u.start_fx=u.start_fy=u.start_fz=0
        elif token=='scalar-speed9':u.speed=9
        elif token=='PSR-success':w['streams']['pilot_rolls']=[12]
        elif token=='PSR-fail':w['streams']['pilot_rolls']=[2]
        elif token.startswith('draws'):w['streams'].update(aero_spin_speed=[10],aero_spin_angle=[15],aero_spin_heading=[3])
        else:
            match=re.fullmatch(r'(speed|actual|desired|fuel|maximum|max|Z|vertical|angle|heading|facing|start_fz|start_spin|plus_heat|blzmapmode|argument|draw|now)(-?\d+(?:\.\d+)?)',token)
            if match:
                key,value=match.groups();value=float(value)
                name={'actual':'speed','desired':'desired_speed','maximum':'max_speed','max':'max_speed','Z':'z','vertical':'vertical_speed','angle':'desired_angle','heading':'desired_facing'}.get(key,key)
                if key=='Z':position(u,u.x,u.y,int(value))
                elif key=='blzmapmode':e.blzmapmode=int(value)
                elif key=='now':e.sim_now=int(value)
                elif key=='draw':w['streams']['fuel_check']=[int(value)]
                elif key=='argument':w['argument']=str(int(value))
                else:setattr(u,name,int(value) if name in ('fuel','desired_angle','desired_facing','facing','start_spin') else value)
    return u


def result_checks(w,result):
    w['result']=result
    ok,text=result
    check(w,'accepted',ok)
    errors={'too-slow':'too slowly','out-of-fuel':'out of fuel','rotor-dead':"rotor's dead",'engines-dead':'engines are dead','fortified':'fortified','not-landed':"haven't landed",'ceiling':'ceiling','reactor-off':'Reactor is not online','insufficient-access':'Insufficient access','unsupported-type':'vehicle type cannot','already-initiated':'already been initiated',
    'horizontal-too-fast':"You're moving too fast",'horizontal-too-slow':"You're moving too slowly",'vertical-too-fast':'You are moving too fast','terrain-refusal':'type of terrain','too-high':'too high','falling-not-landing':"You're falling",'climbing-not-landing':"You're climbing",'fuel-refusal':'lack fuel','already-landed':'already landed',
    'minimum-thrust-refusal':'Minimum thrust','maximum-thrust-refusal':'Maximum thrust','current-thrust-report':'current thrust','backwards-refusal':'backwards','landed-refusal':"You're landed",'uncontrollable-refusal':'control','engine-dead':"engine's dead",'current-angle-report':'Present angle','vertical-only-refusal':'only up / down', 'Out-of-range':'Out of range','Invalid-number-of-parameters':'Invalid number of parameters'}
    for key,fragment in errors.items():check(w,key,fragment.lower() in text.lower())
    u=w['u']
    check(w,'landed',ok and u.has_status(S.LANDED))
    for value in (0,6.450001,12,60):check(w,'desired'+str(value),abs(u.desired_speed-value)<1e-4)
    check(w,'movement-armed',bool(events(w,E.MOVE)))
    for value in (0,30,-30,90,-90):check(w,'angle'+str(value),u.desired_angle==value)


@step(r'landed class (\w+) and speed ([\d.]+) with launch argument (.+)')
def takeoff_setup(w,kind,speed,arg):
    fixture(w,kind+';speed'+speed+';landed')
    w['argument']='' if arg=='empty' else arg.split(':')[-1]
    if arg.startswith('wizard:'):w['u'].pilot.wizard=True


@step(r'the pilot starts takeoff and advances the launch clock')
def launch(w):
    eq(invoke(w,a.takeoff,w['engine'],w['u'],w['argument'])[0],True)
    w['liftoff']=None
    for i in range(1,303):
        invoke(w,w['engine'].run_ticks,1)
        if not w['u'].has_status(S.LANDED):w['liftoff']=i;break


@step(r'liftoff occurs at (\d+) seconds with flight state (.+)')
def launched(w,delay,state):
    eq(w['liftoff'],int(delay));u=w['u']
    for key,value in re.findall(r'(Z|vertical|desired|angle)(-?\d+)',state):near(getattr(u,dict(Z='z',vertical='vertical_speed',desired='desired_speed',angle='desired_angle')[key]),value)
    eq(len(events(w,E.MOVE)),1)


@step(r'takeoff fixture (.+)')
def takeoff_fixture(w,text):
    fixture(w,text)
    w.setdefault('argument','')
    if 'already-taking-off' in text:invoke(w,a.takeoff,w['engine'],w['u'])


@step(r'takeoff is requested')
def request_takeoff(w):
    result_checks(w,invoke(w,a.takeoff,w['engine'],w['u'],w.get('argument','')))
    check(w,'no-event',not events(w,E.TAKEOFF));check(w,'one-event',len(events(w,E.TAKEOFF))==1)


@step(r'a dropship countdown callback has count (\d+)')
def countdown(w,count):
    w['observer']=make_unit(w,'B')
    w['count']=int(count);w['engine'].schedule_event(1,E.TAKEOFF,a.takeoff_event,data=w['u'],data2=int(count))


@step(r'one callback runs on the real queue')
def callback(w):
    # Wrapping the real effects records arguments while still executing damage/sensors.
    with patch('physics.aerospace.exhaust',wraps=a.exhaust) as blast,patch('systems.sensors.scramble_infra_and_liteamp',wraps=__import__('systems.sensors',fromlist=['scramble_infra_and_liteamp']).scramble_infra_and_liteamp) as scramble:
        invoke(w,w['engine'].run_ticks,1)
    text=messages(w)+messages(w,w['observer']);es=events(w,E.TAKEOFF)
    for n in (74,9,5,4,1,0):check(w,'next'+str(n),len(es)==1 and es[0].data2==n)
    for n in (10,5,2,1):check(w,'countdown'+str(n),f'Launch countdown: {n}.' in text)
    check(w,'no-countdown6','Launch countdown: 6.' not in text)
    check(w,'quarter-glow','unbearable intensity' in text)
    check(w,'engines-ready','almost ready' in text)
    check(w,'plasma','superheated plasma' in text)
    for n in (2,4):check(w,'scramble'+str(n),scramble.call_count==1 and scramble.call_args.args[1]==n)
    check(w,'blast400',blast.call_count==1 and blast.call_args.args[1]==400)
    check(w,'liftoff',not w['u'].has_status(S.LANDED));check(w,'no-takeoff-event',not es)


@step(r'a pending launch has transition (.+)')
def transition_setup(w,text):
    w['fixture']=text;u=w['u'];u.pilot.wizard=True;w['argument']='1'
    if text.startswith('AERO'):fixture(w,'AERO;speed32.25')
    if text.startswith('VTOL'):fixture(w,'VTOL')
    if text.startswith('hide'):u.set_crit_status(C.HIDDEN|C.SPINNING)
    eq(invoke(w,a.takeoff,w['engine'],u,'1')[0],True)
    w['hidden_at_start']=not u.has_crit_status(C.HIDDEN)


@step(r'the transition and remaining clock execute')
def transition_run(w):
    u=w['u'];t=w['fixture'];r=(True,'')
    if t.startswith('AERO'):u.speed=32.24
    if t.startswith('VTOL'):u.fuel=0;r=invoke(w,a.land,w['engine'],u)
    if t.startswith('land-before'):r=invoke(w,a.land,w['engine'],u)
    if t.startswith('VTOL'):
        check(w,'landing-fuel-refusal',not r[0] and 'fuel' in r[1]);check(w,'launch-still-pending',bool(events(w,E.TAKEOFF)));return
    invoke(w,w['engine'].run_ticks,2)
    check(w,'too-slow','too slowly' in messages(w));check(w,'still-landed',u.has_status(S.LANDED));check(w,'no-launch-event',not events(w,E.TAKEOFF))
    check(w,'liftoff',not u.has_status(S.LANDED));check(w,'aborted','aborted' in r[1]);check(w,'no-liftoff-or-blast',u.has_status(S.LANDED) and not events(w,E.MOVE))
    check(w,'hidden-cleared-at-start',w['hidden_at_start']);check(w,'spin-cleared-at-liftoff',not u.has_crit_status(C.SPINNING));check(w,'one-move-event',len(events(w,E.MOVE))==1)


@step(r'airborne class (\w+) at floor plus one with desired speed ([\d.]+) actual speed ([\d.]+) and vertical (-?[\d.]+)')
def landing_setup(w,kind,desired,speed,vertical):fixture(w,f'{kind};desired{desired};speed{speed};vertical{vertical};airborne;Z1')


@step(r'landing fixture (.+)')
def landing_fixture(w,text):
    if text.startswith(('AERO','DS')):w['u'].speed=w['u'].desired_speed=40
    fixture(w,text)


@step(r'land is requested')
def land(w):
    u=w['u'];result_checks(w,invoke(w,a.land,w['engine'],u))
    check(w,'Z-floor',u.z==u.elev);check(w,'FZ-floor',u.fz==u.elev*64.5)
    check(w,'vectors-and-actual-speeds0',all(getattr(u,key)==0 for key in ('speed','vertical_speed','start_fx','start_fy','start_fz')))
    check(w,'desired10',u.desired_speed==10);check(w,'angle30',u.desired_angle==30)
    check(w,'mine-and-script',any(v['operation']=='A_AAEROLAND' for v in getattr(u,'external_effects',[])) and u.has_status(S.LANDED))


@step(r'the landing result is (.+)')
def landing_result(w,result):
    from . import observations
    observations(w,result)


@step(r'zone fixture (.+)')
def zone(w,text):
    fixture(w,text);u=w['u'];b=w['map'];w['zone_text']=text
    from systems.map_links import block_lz
    if 'mode1' in text:w['engine'].blzmapmode=1
    if 'uneven' in text or 'one-neighbor-different' in text:b.set_elevation(10,9,1)
    if 'map-edge' in text:position(u,0,0)
    if any(key in text for key in ('blocked','block-team','block-distance')):
        team=1 if 'block-team1' in text else 0
        if 'unit-team1' in text:u.team=1
        x,y=(10,9) if 'distance' in text else (10,10)
        obj=block_lz(b,f'{x} {y} 1 {team}')
        if 'greater-radius' in text:obj.datai=0
    if 'observer' in text:u.set_crit_status(C.OBSERVATORIC)
    if 'range-' in text:
        from physics.hexmath import hex_to_float,find_range
        u.tac_range=find_range(u.fx,u.fy,*hex_to_float(12,12))
        if 'exceeds' in text:u.tac_range-=.1


@step(r'checklz inspects the current hex')
def zone_run(w):w['zone']=invoke(w,a.improper_lz,w['u'])


@step(r'the zone result is (.+)')
def zone_result(w,text):eq(('good','Improper-terrain','Uneven-ground','Blocked-landing-zone')[w['zone']],text)


@step(r'the source check or warning operation executes')
def warning(w):
    text=w['zone_text'];u=w['u']
    if text.startswith('warning'):
        severity=int(re.search(r'severity(-?\d+)',text)[1]);result=invoke(w,a.land_warning,u,severity) or ''
        check(w,'red',result.startswith('%ch%cr'));check(w,'yellow',result.startswith('%ch%cy'));check(w,'uncolored',result.startswith('WARNING'))
        check(w,'CLIMB-UP-NOW','CLIMB UP NOW!!!' in result);check(w,'No-further-descent','No further descent' in result);check(w,'Please-do-not-even-consider','Please do not even consider' in result);check(w,'silent',not result)
    else:
        arg='12 12' if 'range-' in text else '1' if 'one-argument' in text else ''
        result=invoke(w,a.checklz,u,arg);result_checks(w,result);check(w,'zone-reported',result[0] and 'hex (' in result[1])


@step(r'thrust fixture (.+) and argument (.+)')
def thrust_setup(w,text,arg):fixture(w,text);w['argument']='' if arg=='empty' else arg


@step(r'THRUST executes')
def thrust_run(w):result_checks(w,invoke(w,a.thrust,w['engine'],w['u'],w['argument']))


@step(r'class (\w+) at altitude (\d+) receives (CLIMB|DIVE) with (.+)')
def angle_setup(w,kind,z,cmd,arg):fixture(w,f'{kind};Z{z}');w['argument']='' if arg=='empty' else arg;w['flag']=1 if cmd=='CLIMB' else -1


@step(r'the flight angle command executes')
def angle_run(w):result_checks(w,invoke(w,a.vheading,w['u'],w['argument'],w['flag']))


@step(r'vector fixture (.+)')
def vector_setup(w,text):fixture(w,text)


@step(r'one source speed update runs')
def vector_run(w):
    u=w['u'];invoke(w,a.update_speed,u)
    for value in (12.5,25,3.5,7,5,1):check(w,'vertical'+str(value),abs(u.vertical_speed-value)<1e-4)
    check(w,'zero-delta-preserves-speed9',u.speed==9);check(w,'velocity-east',u.start_fx>0 and abs(u.start_fy)<1e-4);check(w,'facing0',u.facing==0)
    check(w,'speed5',abs(u.speed-5)<1e-4);check(w,'facing123',u.facing==123);check(w,'desired60',u.desired_speed==60);check(w,'angle-90',u.desired_angle==-90);check(w,'heading2',u.desired_facing==2)


@step(r'flight workflow (.+)')
def flight_workflow(w,text):w['fixture']=text


@step(r'ordinary controls and the movement clock execute')
def flight_workflow_run(w):
    from systems import movement_commands as mc
    from physics import movement
    from physics.heights import check_vtol_height
    u=w['u'];e=w['engine'];text=w['fixture'];position(u,10,10,100)
    if 'speed-command' in text:
        r=mc.speed(e,u,'20');check(w,'use-thrust-refusal',not r[0] and 'thrust' in r[1]);return
    if 'heading-command' in text:
        u.set_crit_status(C.SPINNING);r=mc.heading(e,u,'90');check(w,'uncontrollable-refusal',not r[0]);return
    if text.startswith('spheroid'):
        u.unit_type=U.SPHEROID_DS;u.desired_angle=90;u.desired_speed=20
        invoke(w,mc.heading,e,u,'90');invoke(w,e.run_ticks,1)
        check(w,'heading-turns-independently-of-velocity',u.facing!=0 and abs(u.start_fx)<1e-4 and abs(u.start_fy)<1e-4);return
    if 'thrust20' in text:
        before=(u.fx,u.fy,u.fz,u.fuel)
        invoke(w,a.thrust,e,u,'20');invoke(w,a.vheading,u,'30');invoke(w,e.run_ticks,3)
        check(w,'real-XYZ-changes',(u.fx,u.fy,u.fz)!=before[:3]);check(w,'fuel-used',u.fuel<before[3]);check(w,'one-move-chain',len(events(w,E.MOVE))==1);return
    if 'fallen' in text:
        u.set_status(S.FALLEN);u.clear_status(S.STARTED);u.start_fz=0;before=u.fz
        invoke(w,mc.maybe_move,e,u);invoke(w,e.run_ticks,1)
        check(w,'start_fz-decrements1-before-displacement',u.start_fz==-1 and u.fz==before-.5);return
    if 'descend' in text:
        old,new=map(int,re.search(r'descend(\d+)-to(\d+)',text).groups())
        u.unit_type=U.DS;position(u,10,10,old);u.start_fz=(new-old)*64.5*2;u.start_fx=1;u.start_fy=1
        u.map.set_terrain(10,10,ROUGH);u.terrain=ROUGH
        invoke(w,movement.move_mech,u)
        msg=messages(w)
        check(w,'angle90',u.desired_angle==90);check(w,'horizontal-vectors0',u.start_fx==u.start_fy==0);check(w,'warning-1','Please do not even consider' in msg)
        check(w,'yellow-warning','%ch%cyWARNING' in msg);check(w,'red-warning','%ch%crWARNING' in msg)
        check(w,'red-warning-only','%ch%crWARNING' in msg and '%ch%cyWARNING' not in msg and 'Please do not even consider' not in msg)
        check(w,'no-cross100-reset',u.desired_angle==0 and u.start_fx==1);return
    if 'ground-penetration' in text:
        position(u,10,10,-1);u.vertical_speed=-40;u.desired_speed=0;u.map.set_terrain(10,10,ROUGH);u.terrain=ROUGH
        invoke(w,check_vtol_height,u)
        check(w,'crash','CRASH!' in messages(w));check(w,'fall-damage',u.damage_taken>0);check(w,'landed',u.has_status(S.LANDED));return
    if 'cross-map-boundary' in text:
        u.map.linked=True;position(u,29,10,100);u.start_fx=500
        invoke(w,movement.update_movement,u,source_callback=True,flight_vectors=True)
        check(w,'normal-map-membership-and-position-updated',u.map.valid(u.x,u.y) and u in u.map.mechs_on_map and u.mapindex==u.map._id and u.x<29);return
    raise AssertionError(text)


@step(r'fuel fixture (.+)')
def fuel_fixture(w,text):fixture(w,text)


@step(r'one fuel check executes')
def fuel_run(w):
    u=w['u'];stop=invoke(w,fuel_check,u)
    for n in (-1,0,3,4):check(w,'fuel'+str(n),u.fuel==n)
    check(w,'continue',not stop);check(w,'stop',stop);check(w,'speeds0',u.speed==u.desired_speed==u.vertical_speed==0)
    check(w,'fall-due3',len(events(w,E.FALL))==1 and events(w,E.FALL)[0].tick==3)
    for key in ('no-new-fall','no-fall'):check(w,key,not events(w,E.FALL))
    check(w,'backup-notice','backup power' in messages(w));check(w,'silent',not messages(w))
    check(w,'no-low-motion-draw',not any(n=='fuel_check' for n,*_ in w['draws']));check(w,'no-draw',not w['draws'])


@step(r'aircraft update fixture (.+)')
def update_fixture(w,text):fixture(w,text)


@step(r'the aircraft dispatcher runs at simulation time (\d+)')
def update_run(w,now):
    from core.game_loop import mech_update
    import systems.stability as stability,systems.heat as heat,systems.ecm as ecm,systems.targeting as targeting,systems.sensors as sensors
    from contextlib import ExitStack
    trace=[];w['engine'].sim_now=int(now);u=w['u']
    with ExitStack() as stack:
        for module,name,label in ((stability,'update_pilot_skill_rolls','pilot'),(heat,'update_from_environment','heat'),(ecm,'check_ecm','ECM'),(targeting,'check_tag','TAG'),(sensors,'end_lite_check','light')):
            fn=getattr(module,name)
            def call(*args,_fn=fn,_label=label,**kwargs):trace.append(_label);return _fn(*args,**kwargs)
            stack.enter_context(patch.object(module,name,side_effect=call))
        invoke(w,mech_update,w['engine'],u)
    if any(name=='visibility_change' for name,*_ in w['draws']):trace.insert(trace.index('ECM'),'visibility')
    check(w,'FIRED-cleared',not u.has_status(S.FIRED));check(w,'no-other-updates',not trace)
    expected={'pilot-and-heat-only':['pilot','heat'],'pilot-heat-visibility-ECM-TAG-light':['pilot','heat','visibility','ECM','TAG','light'],'heat-ECM-TAG-light':['heat','ECM','TAG','light'],'ECM-TAG-light-only':['ECM','TAG','light'],'pilot-ECM-TAG-light':['pilot','ECM','TAG','light']}
    for label,values in expected.items():check(w,label,trace==values)
    check(w,'no-pilot-or-visibility','pilot' not in trace and 'visibility' not in trace)
    check(w,'modifier7',getattr(u,'last_piloting_modifier',None)==7)
    check(w,'spin-cleared',not u.has_crit_status(C.SPINNING));check(w,'spin-retained',u.has_crit_status(C.SPINNING))
    check(w,'remaining-updates',trace[-3:]==['ECM','TAG','light']);check(w,'no-recovery-roll',not any(name=='pilot_rolls' for name,*_ in w['draws']))


@step(r'effect fixture (.+)')
def effect_setup(w,text):
    fixture(w,text)
    if text.startswith('bridge'):
        u=w['u'];u.in_character='IC' in text
        for ident in (200,201,202):
            w['store'].create(ident,'crew'+str(ident),location=u._id,connected=True,wizard=ident==202)
            w['personnel'].add(w['store'].actor(ident),u._id)
    w['before']=(w['u'].crit_status,w['u'].start_spin)


@step(r'the named production effect executes')
def effect_run(w):
    u=w['u']
    if w['fixture'].startswith('control'):
        invoke(w,a.control_effect,u)
        check(w,'spin-set',u.has_crit_status(C.SPINNING));check(w,'start_spin12',u.start_spin==12);check(w,'notices','lose control' in messages(w))
        check(w,'unchanged',(u.crit_status,u.start_spin)==w['before']);check(w,'silent',not messages(w))
    else:
        from systems.hit_locations import bridge_hit
        invoke(w,bridge_hit,u);world=w['personnel'];crew=[world.objects[i] for i in (200,201)]
        check(w,'ordinary-occupants-dead-and-afterlife',all(not p.alive and p.location==world.afterlife for p in crew))
        check(w,'wizard-retained',world.objects[202].location==u._id and world.objects[202].alive)
        check(w,'no-deaths',all(p.alive for p in crew));check(w,'no-deaths-or-notice',all(p.alive for p in crew) and not messages(w))


@step(r'ordinary ticks and events execute')
def fuel_callers(w):
    from core.game_loop import mech_heartbeat
    from systems.movement_commands import maybe_move
    u=w['u'];text=w['fixture']
    kind=re.search(r'(AERO|VTOL|DS)',text)[1];fixture(w,kind+';airborne');position(u,10,10,100)
    if text.startswith('idle'):
        invoke(w,mech_heartbeat,w['engine'],u)
        check(w,'fuel0',u.fuel==0);check(w,'fuel1',u.fuel==1);check(w,'no-idle-check',not w['draws'])
    else:
        u.desired_speed=20;u.speed=20
        invoke(w,maybe_move,w['engine'],u);invoke(w,w['engine'].run_ticks,1)
        check(w,'movement-stops',not events(w,E.MOVE));check(w,'aero-chain-stops',not events(w,E.MOVE));check(w,'fall-event',bool(events(w,E.FALL)))
        check(w,'backup','backup power' in messages(w));check(w,'chain-continues',len(events(w,E.MOVE))==1)
        # A small request reaches the backup target in one high-altitude DS update.
        u.desired_speed=1;u.desired_angle=90;u.start_fx=u.start_fy=u.start_fz=0
        invoke(w,a.update_speed,u);check(w,'reduced-wanted-vector',abs(u.start_fz-1)<1e-4)


@step(r'blast damage (\d+) reaches forest at hex distance (\d+) with decoration (.+)')
def forest_setup(w,damage,distance,decoration):
    from physics.decorations import add_decoration
    w.update(damage=int(damage),forest=(10,10+int(distance)))
    w['map'].set_terrain(*w['forest'],LIGHT_FOREST)
    if decoration=='existing-smoke':invoke(w,add_decoration,w['engine'],w['map'],*w['forest'],SMOKE,100)
    w['forest_before']=(w['map'].terrain(*w['forest']),dict(w['map'].decorations))


@step(r'the source exhaust effect executes')
def exhaust_run(w):invoke(w,a.exhaust,w['u'],w['damage'])


@step(r'the forest becomes (.+)')
def forest_assert(w,text):
    terrain=w['map'].terrain(*w['forest'])
    if text=='unchanged':eq(terrain,w['forest_before'][0])
    elif text=='ROUGH':eq(terrain,ROUGH)
    else:eq(terrain,FIRE);eq(w['map'].rterrain(*w['forest']),LIGHT_FOREST)


@step(r'exhaust fixture (.+)')
def exhaust_setup(w,text):
    w['fixture']=text;u=w['u'];u.unit_type=U.DS
    if 'recipient' in text:
        peer=make_unit(w,'B');w['recipient']=peer
        for sec in peer.sections:sec.armor=sec.armor_orig=2000;sec.internal=sec.internal_orig=2000
    if 'observer' in text:
        peer=make_unit(w,'B');peer.sensor=[2,2] if 'infrared' in text else [1,1];w['recipient']=peer
    if 'airborne' in text:
        u.clear_status(S.LANDED);position(u,10,10,5 if 'plus5' in text else 6);u.clear_status(S.STARTED)
        w['engine'].events.set_tick(19 if 'tick20' in text else 21)
    else:u.set_status(S.LANDED)


@step(r'countdown or movement reaches the exhaust boundary')
def exhaust_boundary(w):
    from physics.movement import aero_move_event
    from systems import damage,sensors
    u=w['u'];text=w['fixture'];z=u.z
    with patch.object(damage,'blast_hit_hexes_f',wraps=damage.blast_hit_hexes_f) as blast,patch.object(sensors,'scramble_infra_and_liteamp',wraps=sensors.scramble_infra_and_liteamp) as scramble:
        if 'airborne' in text:w['engine'].schedule_event(1,E.MOVE,aero_move_event,data=u)
        else:
            count=int(re.search(r'count(\d+)',text)[1]) if 'count' in text else 6
            w['engine'].schedule_event(1,E.TAKEOFF,a.takeoff_event,data=u,data2=count)
            if 'aborted' in text:invoke(w,a.land,w['engine'],u)
        invoke(w,w['engine'].run_ticks,1)
    for value in (400,8):check(w,'actual-blast'+str(value),blast.call_count==1 and blast.call_args.args[1]==value and (w.get('recipient') is None or w['recipient'].damage_taken>0))
    check(w,'clusters5',blast.call_count==1 and blast.call_args.args[2]==5)
    for value in (200,4):check(w,'heat'+str(value),blast.call_count==1 and blast.call_args.args[3]==value)
    check(w,'emitter-Z-restored',u.z==z);check(w,'no-exhaust',not blast.called)
    for value in (2,4):check(w,'real-sensor-scramble'+str(value),scramble.call_count==1 and scramble.call_args.args[1]==value and w['recipient'].has_status(S.BLINDED))
    check(w,'no-scramble-or-blast',not scramble.called and not blast.called)
