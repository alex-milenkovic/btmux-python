"""Ordered lifecycle guards, map transitions and remaining source boundaries."""
import re
from core_simulation_qa import ROOT,D,C,A,I,K,S,case,check as q
from core_qa_events import events


def build():
    source=(ROOT/'btmux/btmux/btech/src/btech/mech.startup.c').read_text()
    for cls,move,table in [('MECH','BIPED','bootmsgs'),('MECH','QUAD','bootmsgs'),('MECH','NONE','bootmsgs'),('BSUIT','BIPED','bsuit_bootmsgs'),('VEH_GROUND','TRACK','track_bootmsgs'),('VEH_GROUND','WHEEL','wheel_bootmsgs'),('VEH_GROUND','HOVER','hover_bootmsgs'),('VTOL','VTOL','vtol_bootmsgs'),('VEH_NAVAL','HULL','naval_bootmsgs'),('VEH_NAVAL','FOIL','naval_bootmsgs'),('VEH_NAVAL','SUB','naval_bootmsgs'),('AERO','FLY','aero_bootmsgs'),('DS','FLY','aero_bootmsgs'),('SPHEROID_DS','FLY','aero_bootmsgs')]:
        values=re.findall(r'"([^"\n]*)"',re.search(r'char \*'+table+r'\[BOOTCOUNT\]\s*=\s*\{(.*?)\};',source,re.S)[1])
        expected=[v.replace('%%','%') for v in values]
        case('startup','exact-boot-messages-'+cls+move,[C('startup'),A(6 if cls=='BSUIT' else 30)],
             [q('state.units.u.boot_messages',expected),q('state.units.u.started',True)],units=[dict(name='u',**{'class':cls},movement=move,started=False)],mode='ordinary')
    case('startup','extinguish-before-repair-heat',[D('queue_event','VEHICLE_EXTINGUISH',40),C('startup')],
         [q('results.1.accepted',False),q('results.1.text',contains='putting out fires'),events('state','STARTUP',0)],units=[dict(name='u',started=False,heat=31,core={'repair_remaining':2})])
    case('startup','missing-map',[dict(op='remove',unit='u'),C('startup')],[q('results.1.accepted',False),events('state','STARTUP',0)],units=[dict(name='u',started=False)])
    case('clocks','registry-order-rearm-before-dispatch',[K('skip_seconds',seconds=17),K('heartbeat')],
         [q('state.heartbeat_trace',[3,7,9,20,1000],project='id'),q('state.heartbeat_trace',['MECH','OTHER','AUTO','MECH','MAP'],project='type'),q('state.heartbeat_trace',[18]*5,project='deadline'),q('state.heartbeat_trace',[4294967295]*5,project='global_tick'),q('state.clocks.global_tick',0)],
         units=[dict(name='u',id=20),dict(name='v',id=3,at=[10,10,0])],objects=[dict(name='auto',id=9,type='AUTO',mymech='u'),dict(name='other',id=7,type='OTHER')],config={'initial_global_tick':4294967295},mode='blocked')
    macro=['TAKEOFF','HIDE','DIG','HULLDOWN','MASC_FAIL'];retained=['RECOVERY','UNSTUN_CREW','CHECK_STAGGER','FALL','STANDFAIL','CREWSTUN','SCHARGE_FAIL','PLOS','LOCK']
    case('shutdown','all-extra-macro-events',[D('cancel_events','PLOS')]+[D('queue_event',kind,100) for kind in macro+retained]+[C('shutdown')],
         [events('state',k,int(k in retained)) for k in macro+retained])
    for destroyed in (False,True):
        case('shutdown','destroyed-conditional-cleanup-'+str(destroyed),[C('shutdown')],
             [q('state.units.u.started',destroyed),q('state.units.u.speed',10 if destroyed else 0),q('state.units.u.desired_speed',10 if destroyed else 0),q('state.units.u.status2',64|128 if destroyed else 0,mask=64|128),q('state.units.u.pilot',None)],units=[dict(name='u',destroyed=destroyed,speed=10,desired_speed=10,status2=64|128)])
    for on in (False,True):
        case('shutdown','light-and-two-torso-notices-'+str(on),[C('shutdown')],[q('state.units.u.messages',int(on),count_text='searchlight shuts off'),q('state.units.u.messages',2,count_text='Torso rotated back'),q('state.units.u.crit_status',0,mask=0x800)],units=[dict(name='u',status=14,status2=32 if on else 0,crit_status=0x800)])
    for kind,move in [('VEH_NAVAL','HULL'),('VEH_GROUND','NONE')]:
        case('shutdown','excluded-freefall-still-tumbles-'+kind,[C('shutdown')],[events('state','FALL',0),q('state.units.u.messages',1,count_text='Mech fell')],units=[dict(name='u',**{'class':kind},movement=move,speed=11,at=[3,3,10])])
    for high in (299,300,301):
        case('shutdown','orbit-strict-'+str(high),[C('shutdown')],[events('state','FALL',int(high<300))],units=[dict(name='u',**{'class':'VTOL'},at=[3,3,high])])
    for at in (5,6):
        for tick in (0,1,2,19,20,21,22):
            case('movement_events',f'dropship-exhaust-window-{at}-{tick}',[K('dispatch')]*tick+[D('callback','aero_move_event')],
                 [q('state.units.u.external_effects',int(at<=5 and tick//2%10==0),where={'operation':'DS_BlastNearbyMechsAndTrees'},length=True),events('state','MOVE',1)],units=[dict(name='u',**{'class':'DS'},at=[3,3,at],core={'free_fuel':True})],config={'periodic_updates':False},mode='blocked')
    for label,cf,entrance,carry in [('rubble',0,True,False),('exit',10,True,False),('carried',10,True,True),('missing-entrance',10,False,False)]:
        maps=[dict(name='bay',id=10,flags=1,cf=cf,leave_target=11),dict(name='field',id=11,default=['GRASSLAND',3],entrances=[dict(target=10,x=5,y=6,name='Bay')] if entrance else [])]
        u=dict(name='u',measured_mass=51200,core={'preferred_contact_id':'ZZ'},carrying=2 if carry else 0)
        units=[u]+([dict(name='v',id=2,core={'preferred_contact_id':'ZY'})] if carry else [])
        checks=[q('state.units.u.map','bay' if not cf else 'field')]
        if cf and entrance:checks += [q('state.units.u.x',5),q('state.units.u.y',6),q('state.units.u.at.2',3),q('state.units.u.external_effects',1,where={'operation':'loud_teleport'},length=True)]
        if carry:checks += [q('state.units.v.map','field'),q('state.units.v.x',5),q('state.units.v.y',6),q('state.units.v.at.2',3)]
        if not entrance:checks += [q('state.units.u.external_effects',1,where={'operation':'find_entrance_by_target'},length=True)]
        case('targets','hangar-'+label,[D('Leave_Hangar')],checks,maps=maps,units=units,mode='blocked' if cf else 'diagnostic')
    case('targets','bay-exit-service',[dict(op='core',values={'x':-1}),D('CheckEdgeOfMap')],
         [q('state.units.u.x',0),q('state.units.u.external_effects',1,where={'operation':'Leave_DS'},length=True)],map={'onmap':55},mode='blocked')
    case('targets','missing-map-reset',[dict(op='remove',unit='u'),D('CheckEdgeOfMap')],[q('state.units.u.mapindex',-1),q('state.units.u.started',False),q('state.units.u.external_effects',1,where={'operation':'CheckEdgeofMap:invalid map'},length=True)],mode='blocked')
    case('recovery','null-crew-callback',[I(),D('callback','mech_crewstun_event',0,True),I()],
         [q('results.0.units.u',same_as='results.2.units.u'),q('state.event_trace',['pre','callback','post'],project='phase'),q('state.random.total_rolls',0)])
    for extended in (False,True):
        for name in ('PC.Sword','PC.Blade','PC.Vibroblade','PC.Blazer','PC.HeavyGyrojetGun','PC.Gun'):
            expected=('Blade' if name in (('PC.Blade','PC.Vibroblade') if extended else ('PC.Sword','PC.Vibroblade')) else 'Support_Weapons' if extended and name in ('PC.Blazer','PC.HeavyGyrojetGun') else 'Small_Arms')
            case('skills',f'pc-exact-name-{extended}-{name}',[D('FindGunnerySkillName',0),D('FindGunnerySkillName',-1)],[q('results',[expected,None if extended else 'Small_Arms'])],units=[dict(name='u',**{'class':'MW'},weapons=[dict(name='IS.SmallLaser',metadata={'source_name':name})])],config={'extended_gunnery':extended})
    for cls,move,started,speed,fuel,free,rotor in [('MECH','BIPED',True,0,0,False,False),('MECH','BIPED',True,1,0,False,False),('MECH','BIPED',True,-1,0,False,False),('MECH','BIPED',False,1,0,False,False),('AERO','FLY',True,-1,10,False,False),('AERO','FLY',True,-2,0,False,False),('AERO','FLY',True,-2,0,True,False),('VTOL','VTOL',True,-2,10,False,True),('VTOL','VTOL',True,-2,10,False,False),('VTOL','VTOL',False,-2,10,True,False)]:
        stop=started and speed>=0;powerless=not started or cls=='MECH' or fuel<=0 and not free or rotor
        velocity=speed+(-1 if speed<=0 and powerless else 1)
        case('movement_events',f'fall-power-{cls}-{started}-{speed}-{fuel}-{free}-{rotor}',[D('callback','mech_fall_event',speed)],
             [q('state.units.u.at.2',10 if stop else 10-abs(velocity)),events('state','FALL',int(not stop)),q('state.events',[] if stop else [velocity],where={'kind':'FALL'},project='data2')],
             units=[dict(name='u',**{'class':cls},movement=move,started=started,at=[3,3,10],fuel=fuel,core={'free_fuel':free},sections=[dict(index=5,armor=0,internal=0)] if rotor else [])])
    for cls,move,landed,vertical,water in [('VTOL','VTOL',True,0,False),('VTOL','VTOL',False,1,False),('VEH_NAVAL','HULL',False,0,False),('VEH_NAVAL','HULL',False,0,True),('VEH_NAVAL','SUB',False,1,True)]:
        case('movement_events',f'move-gates-{cls}-{move}-{landed}-{vertical}-{water}',[D('callback','mech_move_event')],
             [events('state','MOVE',int(not landed and (water or cls=='VTOL')))],
             units=[dict(name='u',**{'class':cls},movement=move,status=9 if landed else 8,at=[3,3,0 if landed else 5 if cls=='VTOL' else -1 if water else 0],speed=0,desired_speed=0 if vertical else 5,vertical_speed=vertical,core={'free_fuel':True})],map={'default':['WATER' if water else 'GRASSLAND',3 if water else 0]})
    for mapless in (False,True):
        case('targets','mark-los-mapless-'+str(mapless),([dict(op='remove',unit='u')] if mapless else [])+[dict(op='core',values={'mapflag':255}),D('MarkForLOSUpdate')],
             [q('state.units.u.mapflag',255 if mapless else 1)])
    for friend in (False,True):
        # Own marker wins after roster markers at the same projected coordinate.
        case('targets','navigate-own-last-'+str(friend),[D('navigate_sketch_mechs',3,3)],
             [q('results.0',1,count_text='*'),q('results.0',0,count_text='x'),q('results.0',0,count_text='X')],
             units=[dict(name='u'),dict(name='v',at=[3,3,0],team=1 if friend else 2)])
    for operation,args,error in [('GetPartWeight',[-1,True],'outside'),('FindWeapons_Advanced',[8],'outside'),('InWeaponArc',[float('nan'),0],'nonfinite'),('MNumber',[3,2],'ordered'),('callback',['mech_fall_event',0,True],'null callback'),('no_such_source',[],'unknown'),('Number',[-2147483648,4294967295],'32')]:
        case('integration','invalid-domain-'+operation,[D(operation,*args)],[],error=error)
    for override in (0,3,10):
        case('repair','engine-sink-override-'+str(override),[D('do_sub_magic')],[q('state.units.u.real_num_sinks',8 if not override else override)],units=[dict(name='u',profile='sparse',num_sinks=10,core={'engine_rating':200,'hs_engine_override':override})])
    case('parts','weight-no-tables',[D('GetPartWeight',p,False) for p in (193,385,394,419,420,512)],
         [q('results',[1024,1020,1024,1024,102,102])])
    case('parts','aero-cargo-mounted-fuel',[D('SetCargoWeight')],
         [q('results.0',8462),q('state.units.u.carried_cargo',8462),q('state.units.u.fuel_max',3000)],
         units=[dict(name='u',**{'class':'AERO'},fuel=1200,core={'fuel_orig':1000,'cargo_inventory':[[385,0,2]]},sections=[dict(index=0,slots=[dict(index=0,special='FUELTANK')])])])

    case('shutdown','tag-and-tow-cleanup',[C('shutdown')],
         [q('state.units.u.relationships.tag_target',0),q('state.units.v.relationships.tagged_by',0),q('state.units.u.relationships.carrying',None),q('state.units.v.status',0,mask=0x4000),q('state.units.v.speed',0),events('state','TAG_RECYCLE',1)],
         units=[dict(name='u',tag_target=2,carrying=2,towed_unit='v'),dict(name='v',id=2,at=[4,3,0],tagged_by=1,status=0x4008,speed=5,desired_speed=5)],mode='ordinary')
    case('shutdown','swarm-detach-cleanup',[C('shutdown')],
         [q('state.units.u.relationships.swarm_target',None),q('state.units.u.messages',1,count_text='You drop'),q('state.units.u.sections.0.recycle',45),q('state.units.u.sections.0.armor',89)],
         units=[dict(name='u',**{'class':'BSUIT'},swarm_target='v',sections=[dict(index=0,armor=100,armor_orig=100,internal=10)]),dict(name='v',id=2,at=[4,3,0])],random={'streams':{'piloting_rolls':[],'suit_fall_location':[0],'damage_entry':[7],'tow_rolls':[7]}},mode='ordinary')
    case('movement_events','power-restored-during-fall',[S('mech_fall_event',3,-1),C('startup','override',actor={'id':1,'wizard':True}),A(1),I(),A(2),I(),A(3)],
         [q('results.3.units.u.started',True),q('results.5.units.u.at.2',10),q('state.units.u.at.2',10),events('state','FALL',0)],
         units=[dict(name='u',**{'class':'VTOL'},at=[3,3,10],started=False,fuel=100,measured_mass=51200)],config={'periodic_updates':False},mode='ordinary')
    for rolling in (False,True):
        case('movement_events','landed-aero-rolling-'+str(rolling),[D('callback','aero_move_event')],
             [events('state','MOVE',int(rolling)),q('state.units.u.at.2',0)],units=[dict(name='u',**{'class':'AERO'},at=[3,3,0],speed=1 if rolling else 0,desired_speed=1 if rolling else 0,fuel=100)])

    for flags in (0,1,2,4):
        for inferno in (False,True):
            case('ammunition',f'destructive-first-tie-disabled-{flags}-{inferno}',[D('FindDestructiveAmmo'),D('FindInfernoAmmo')],
                 [q('results.0.location',2 if flags&1 else 1),q('results.0.slot',11),q('results.0.ammo_count',5),q('results.0.weapon_damage',2),q('results.0.missiles_per_shot',6),q('results.1.location',2)] if inferno else
                 [q('results.0.location',2 if flags&1 else 1),q('results.0.slot',11),q('results.0.ammo_count',5),q('results.0.weapon_damage',2),q('results.0.missiles_per_shot',6),q('results.1',None)],
                 units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.SRM-6',section=4),dict(name='IS.GaussRifle',section=3)],sections=[dict(index=i,slots=[dict(index=11,ammo='IS.SRM-6',data=5,firemode=flags if i==1 else 0,ammomode=64 if inferno and i==2 else 0)]) for i in (1,2)]+[dict(index=0,slots=[dict(index=0,ammo='IS.GaussRifle',data=99,ammomode=64)])])])
    for special,second,broken in ((1024,0,0),(1024,0,0x100000),(0,0x1000,0),(0,0x1000,128),(1024,0x1000,0x100000),(1024,0x1000,0x100080)):
        case('parts',f'heat-factor-ecm-working-{special}-{second}-{broken}',[D('HeatFactor')],
             [q('results.0',-1 if special and not broken&0x100000 or second and not broken&128 else 17)],units=[dict(name='u',specials=special,specials2=second,crit_status=broken,core={'plus_heat':7,'minus_heat':2})])
    for reason in ('legless','jump','ood'):
        case('movement_events','heading-only-'+reason,[D('callback','mech_move_event')],
             [q('state.units.u.at',[3,3,0]),q('state.units.u.speed',10),q('state.units.u.desired_speed',10),q('state.units.u.facing',positive=True),events('state','MOVE',1)],
             units=[dict(name='u',speed=10,desired_speed=10,desired_facing=180,status=8|64 if reason=='jump' else 8,cocoon=1 if reason=='ood' else 0,sections=[dict(index=i,armor=0,internal=0) for i in (5,6)] if reason=='legless' else [])])
    case('targets','roster-hole-first-match',[dict(op='roster-hole'),D('FindMechOnMap','BBsuffix')],
         [q('results.1',2),q('state.maps.main.roster',[1,2,None])],units=[dict(name='u'),dict(name='v',id=2,contact_id='BB',at=[4,3,0])])
    for part in (1,193):
        case('repair','fill-nonammo-zero-capacity-'+str(part),[D('mech_FillPartAmmo',0,0)],
             [q('state.units.u.sections.0.slots.0.data',7),q('state.units.u.sections.0.slots.0.firemode',1)],
             units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.SmallLaser',section=4,metadata={'ammo_per_ton':0})],sections=[dict(index=0,slots=[dict(index=0,type=part,data=7,firemode=1)])])])

    for weight in (.5,1,1.01,5):
        raw=int(weight*100)*1024//100
        amp=20000*(raw//1024)//10;turret=5000*(raw//10)//1024
        case('cost','vehicle-amplifier-turret-'+str(weight),[D('CalcFasaCost')],
             [q('results.0.components',[amp],where={'label':'Power Amplifiers'},project='amount'),q('results.0.components',[turret],where={'label':'Turret'},project='amount'),q('results.0.value',int((95000+amp+turret+1000)*1.5))],
             units=[dict(name='u',profile='sparse',**{'class':'VEH_GROUND'},movement='TRACK',max_speed=0,specials=0x400000,core={'engine_rating':0},weapons=[dict(name='IS.MediumLaser',section=4,metadata={'tonnage':weight,'cost':1000})])])

    for cls in ('MECH','VEH_GROUND'):
        for stall in (0,1):
            template=dict(name='intact',**{'class':cls},core={'engine_rating':200},weapons=[dict(name='IS.SmallLaser',section=0)])
            unit=dict(template,name='u',tank_crit_status=255,core={'engine_rating':1,'template_ref':'intact','stall':stall},sections=[dict(index=0,config=36,slots=[dict(index=0,firemode=1|512|0x100000|0x40000)]),dict(index=1,config=36,slots=[dict(index=0,weapon='IS.SmallLaser',firemode=512|0x100000|0x40000)])])
            case('repair',f'template-stall-masks-{cls}-{stall}',[I(),C('recalculate')],
                 [q('state.units.u.sections.0.config',0 if stall else 4),q('state.units.u.sections.0.slots.0.firemode',1|512|0x100000|0x40000),q('state.units.u.sections.1.slots.0.firemode',0),q('state.units.u.tank_crit_status',0 if cls=='MECH' else 0x33),q('results.0.templates',same_as='state.templates')],units=[unit],templates=[dict(name='intact',unit=template)],mode='ordinary')
    case('repair','detach-repeat-live-section',[C('detach',0),I(),C('detach',0),I()],
         [q('results.1',same_as='results.3'),q('state.units.u.sections.0.internal',0),q('state.units.u.sections.0.armor',0)],mode='ordinary')

    for friend,visible,outside in ((True,True,False),(False,True,False),(True,False,False),(False,False,False),(False,True,True)):
        actions=([dict(op='core',unit='v',values={'x':3,'y':3})] if outside else [])+([] if visible else [dict(op='cache',unit='u',target='v',flags=0)])
        case('targets',f'navigation-marker-{friend}-{visible}-{outside}',actions+[D('navigate_sketch_mechs',3,3)],
             [q('results.'+str(len(actions)),int(visible and not outside),count_text='x' if friend else 'X'),q('results.'+str(len(actions)),0,count_text='*')],
             units=[dict(name='u',at=[1,1,0],team=1),dict(name='v',at=[3,3,0],team=1 if friend else 2,**({'real':[2000,2000,0]} if outside else {}))])

    for complexrepair,material in ((False,542),(True,818)):
        template=dict(name='intact',specials=0x200000,core={'engine_rating':200},sections=[dict(index=loc,slots=[dict(index=i,special='ENGINE') for i in range(6 if loc==4 else 3)]) for loc in (2,3,4)])
        unit=dict(template,name='u',core={'engine_rating':200,'template_ref':'intact'},sections=[dict(index=loc,slots=[dict(index=i,special='ENGINE',firemode=int(loc==4 and i==0)) for i in range(6 if loc==4 else 3)]) for loc in (2,3,4)])
        case('repair','material-consumer-'+str(complexrepair),[D('alias_part',401,4),D('SetPartCost',material,12345),D('GetPartCost',material),D('GetPartCost',material+1),C('repair',4,0),D('alias_part',401,4),C('parts')],
             [q('results.0',material),q('results.2',12345),q('results.3',0),q('results.4.accepted',True),q('results.5',material),q('results.6.accepted',True),q('state.units.u.sections.4.slots.0.firemode',0),q('state.units.u.engine_heat',0)],
             units=[unit],templates=[dict(name='intact',unit=template)],config={'complexrepair':complexrepair})
    for last_friend in (False,True):
        case('targets','navigation-collision-'+str(last_friend),[D('navigate_sketch_mechs',3,3)],
             [q('results.0',1,count_text='x' if last_friend else 'X'),q('results.0',0,count_text='X' if last_friend else 'x')],units=[dict(name='u',at=[1,1,0],team=1),dict(name='v',at=[3,3,0],team=2 if last_friend else 1),dict(name='w',at=[3,3,0],team=1 if last_friend else 2)])
