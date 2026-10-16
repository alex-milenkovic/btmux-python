"""Remaining lifecycle, skill and shared-utility boundary procedures."""
from core_simulation_qa import A,C,D,I,K,S,case,check as q
from core_qa_events import events
from core_qa_workflows import finite


def build():
    for lag in (0,5,19,20,30):
        case('clocks',f'dispatch-clamp-{lag}',[K('dispatch'),K('skip_seconds',seconds=lag),K('heartbeat'),C('skills'),K('dispatch')],
             [q('state.clocks',dict(wall=lag+2,event=1+min(20,lag+1),global_tick=1)),q('results.3.accepted',True)])
    for flags,wanted in [(1|2|16,131072),(2|16,65536),(16,262144)]:
        for entering in (False,True):
            case('movement_events',f'mode-priority-{flags}-{entering}',[D('callback','mech_movemode_event',flags|(4 if entering else 8))],
                 [q('state.units.u.status2',wanted if entering else 458752&~wanted,mask=458752)],units=[dict(name='u',status2=0 if entering else 458752)])
    case('movement_events','dodge-refusal-before-speed-cap',[D('callback','mech_movemode_event',20)],
         [q('state.units.u.desired_speed',100),q('state.units.u.status2',0,mask=262144)],units=[dict(name='u',speed=100,desired_speed=100,sections=[dict(index=0,recycle=1)])])
    case('movement_events','reverse-sprint-stops-desired',[D('callback','mech_movemode_event',6)],
         [q('state.units.u.desired_speed',0),q('state.units.u.status2',65536,mask=65536)],units=[dict(name='u',speed=-10,desired_speed=-20)])
    for status in (0,8|32):
        case('movement_events','mode-stopped-destroyed-'+str(status),[D('callback','mech_movemode_event',5)],[q('state.units.u.status2',0,mask=458752)],units=[dict(name='u',status=status,status2=458752)])
    for cls in ('AERO','DS'):
        for started in (False,True):
            case('movement_events',f'flight-boundary-{cls}-{started}',[D('callback','aero_move_event')],
                 [events('state','MOVE',1),q('state.units.u.start_fz',2),q('state.units.u.external_effects',positive=True,where={'operation':'aero move_mech','applied':False},length=True)],units=[dict(name='u',**{'class':cls},at=[3,3,20],status=128|(8 if started else 0),core={'free_fuel':True,'start_fz':3})],mode='blocked')
    for cls,move,g,p,t in [('MECH','BIPED','Gunnery-Battlemech','Piloting-Battlemech','Technician-Battlemech'),('BSUIT','BIPED','Gunnery-BSuit','Piloting-BSuit','Technician-Battlemech'),('VEH_GROUND','TRACK','Gunnery-Conventional','Drive','Technician-Mechanic'),('VEH_NAVAL','HULL','Gunnery-Conventional','Drive','Technician-Mechanic'),('VTOL','VTOL','Gunnery-Aerospace','Piloting-Aerospace','Technician-Aerospace'),('AERO','FLY','Gunnery-Aerospace','Piloting-Aerospace','Technician-Aerospace'),('DS','FLY','Gunnery-Spacecraft','Piloting-Spacecraft','Technician-Aerospace'),('SPHEROID_DS','FLY','Gunnery-Spacecraft','Piloting-Spacecraft','Technician-Aerospace'),('MW','BIPED','Small_Arms','Running',None)]:
        case('skills','all-class-selectors-'+cls,[D('FindGunnerySkillName',-1),D('FindPilotingSkillName'),D('FindTechSkillName'),D('FindTechSkill')],
             [q('results',[g,p,t,18 if cls=='MW' else 7])],units=[dict(name='u',**{'class':cls},movement=move,actor={'technician':7})],config={'extended_gunnery':False,'extended_piloting':False})
    for move,label in [('BIPED','Biped'),('QUAD','Quad'),('TRACK','Tracked'),('HOVER','Hover'),('WHEEL','Wheeled'),('NONE',None)]:
        case('skills','extended-move-'+move,[D('FindPilotingSkillName'),D('FindSPilotPiloting')],[q('results.0',None if label is None else 'Piloting-'+label),q('results.1',3 if move=='QUAD' else 6 if move=='NONE' else 5)],
             units=[dict(name='u',movement=move)],config={'extended_piloting':True})
    for weapon_type,label in [(0,'Gunnery-Laser'),(1,'Gunnery-Missile'),(2,'Gunnery-Artillery'),(3,'Gunnery-Ballistic'),(4,None)]:
        case('skills','extended-weapon-type-'+str(weapon_type),[D('FindGunnerySkillName',0),D('FindGunnerySkillName',-1)],
             [q('results',[label,None])],units=[dict(name='u',weapons=[dict(name='IS.SmallLaser',metadata={'weapon_type':weapon_type})])],config={'extended_gunnery':True})
    for valid in (False,True):
        case('skills','separate-gunner-'+str(valid),[D('FindPilotPiloting'),D('FindPilotGunnery',0),D('FindPilotSpotting'),D('FindPilotArtyGun')],
             [q('results',[5,2 if valid else 6,7,3 if valid else 8])],units=[dict(name='u',pilot_details={'spotting':7},gunner={'gunnery':2,'artillery':3,'valid':valid})])
    for quiet in (False,True):
        case('skills','quiet-versus-local-pilot-'+str(quiet),[D('FindPilotPiloting'),D('FindPilotGunnery',0),D('FindPilotSpotting'),D('FindPilotArtyGun')],
             [q('results',[1,2,3,4] if quiet else [5,4,8,8])],units=[dict(name='u',core={'quiet':quiet,'mechskills':'1 2 3 4'})])
    for quad in (False,True):
        case('skills','bth-small-cockpit-remote-'+str(quad),[D('MechPilotSkillRoll_BTH',3)],
             [q('results.0',17 if not quad else 15)],units=[dict(name='u',movement='QUAD' if quad else 'BIPED',in_character=True,specials2=0x2000000,core={'pilot_skill_base':2},pilot_details={'location':999})])
    for amount in (2,3,7,9,12):
        case('skills',f'xp-exact-cap-{amount}',[D('MadePilotSkillRoll_Advanced',amount-5)],
             [q('state.units.u.xp_requests',[] if amount<=2 else [max(1,min(amount-7,max(2,1+amount-5)))],project='amount')],
             random={'streams':{'pilot_rolls':[12]}},mode='diagnostic' if amount<=2 else 'blocked')
    for mask in (0,64,128):
        case('parts','heat-factor-signatures-'+str(mask),[D('HeatFactor')],[q('results.0',-1 if mask else 17)],units=[dict(name='u',status2=mask,core={'plus_heat':7,'minus_heat':2})])
    for ice in (False,True):
        case('parts','heat-factor-vehicle-'+str(ice),[D('HeatFactor')],[q('results.0',-1 if ice else 21)],units=[dict(name='u',**{'class':'VEH_GROUND'},specials=0x400000 if ice else 0)])
    case('parts','source-list-separators',[D('UnitPartsList',0),D('UnitPartsList',-1)],
         [q('results',['ARMOR:5|INTERNAL:3|IS.SmallLaser:1|#-1 INVALID PART NUMBER:1|Engine:1||Actuator:1']*2)],
         units=[dict(name='u',profile='sparse',sections=[dict(index=0,armor=5,internal=3,slots=[dict(index=0,type=1,firemode=1),dict(index=1,type=1,firemode=4),dict(index=2,special='ENGINE'),dict(index=3,special='UPPER_ACTUATOR'),dict(index=4,special='ENDO_STEEL'),dict(index=5,type=193)])])])
    for quad in (False,True):
        case('ammunition','leg-sinks-'+str(quad),[D('FindLegHeatSinks')],[q('results.0',2 if quad else 1)],units=[dict(name='u',movement='QUAD' if quad else 'BIPED',sections=[dict(index=i,slots=[dict(index=5,special='HEAT_SINK',firemode=1 if i in (0,5) else 0)]) for i in (0,1,5,6)])])
    case('cost','zero-part-cost-is-source-noop',[D('SetPartCost',0,99),D('GetPartCost',0)],[q('results',[None,0]),q('state.costs',{})])
    for phase in range(6):
        case('startup','callback-stage-changed-'+str(phase),[S('mech_startup_event',1,data=phase),K('dispatch')],
             [q('state.units.u.boot_messages',1,length=True),q('state.units.u.started',phase==5),events('state','STARTUP',int(phase<5))],units=[dict(name='u',started=False)])
    for label,unit,text in [('already',dict(started=True),'already started'),('MW',{'class':'MW','started':True},'up and about'),('towed',dict(status=0x4000|32),'being towed'),('destroyed',dict(destroyed=True),'destroyed'),('repair',dict(core={'repair_remaining':1},heat=31),'under repairs')]:
        unit=dict(name='u',**unit);unit.setdefault('started',False)
        case('startup','ordered-guard-'+label,[C('startup')],[q('results.0.accepted',False),q('results.0.text',contains=text)],units=[unit],mode='ordinary')
    for owner,wizard,accepted in [('actor',False,True),('pilot',False,False),('pilot',True,True)]:
        case('startup','ownership-'+owner+str(wizard),[C('startup')],[q('results.0.accepted',accepted)],units=[dict(name='u',started=False,in_character=True,actor={'wizard':wizard},pilot_owner=owner)],mode='ordinary')
    case('startup','health-and-completion-fields',[C('startup'),A(30)],
         [q('state.units.u.pilot_hits',2),q('state.units.u.pilot_status',2),q('state.units.u.specials',0x40000,mask=0x40000),q('state.units.u.comm',3),q('state.units.u.per',4),q('state.units.u.comm_last',0),q('state.units.u.last_startup',30),q('state.units.u.carried_cargo',2048)],
         units=[dict(name='u',started=False,pilot=False,measured_mass=51200,actor={'health':{'build':5,'bruise':12,'lethal':8},'skills':{'Sixth_Sense':1,'Comm-Conventional':3,'Perception':4}},core={'cargo_inventory':[[193,0,2]],'comm_last':99})],mode='ordinary')
    retained=['RECOVERY','UNSTUN_CREW','CHECK_STAGGER','FALL','STANDFAIL']
    stopped=['STARTUP','MOVEMODE','JUMP','MOVE','AERO_MOVE','STAND','JUMPSTABIL']
    callbacks={'RECOVERY':'mech_recovery_event','UNSTUN_CREW':'unstun_crew_event','CHECK_STAGGER':'check_stagger_event','FALL':'mech_fall_event','STANDFAIL':'mech_standfail_event','MOVEMODE':'mech_movemode_event','JUMP':'mech_jump_event','MOVE':'mech_move_event','AERO_MOVE':'aero_move_event','STAND':'mech_stand_event','JUMPSTABIL':'mech_jumpstabil_event'}
    # A pending STARTUP would deliberately select abort-only, so seed the other
    # macro events for a normal shutdown and test startup abort separately.
    actions=[S(callbacks[k],100) for k in retained+stopped[1:]]+[C('shutdown')]
    case('shutdown','macro-event-retention-and-bits',actions,
         [events('state',k,int(k in retained)) for k in retained+stopped]+[q('state.units.u.status',0,mask=8|2|4|0x100000),q('state.units.u.status2',0,mask=0x733e3),q('state.units.u.crit_status',0,mask=0x8800),q('state.units.u.pilot',None),q('state.units.u.charge_target',-1),q('state.units.u.sections.0.specials',0,mask=32)],
         units=[dict(name='u',status=8|2|4|0x100000,status2=0x733e3,crit_status=0x8800,charge_target=8,sections=[dict(index=0,specials=32)],core={'digging':True})])
