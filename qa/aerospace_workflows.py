"""Independent ordinary workflows and supplemental source integration cases."""
from aerospace_support import *
from aerospace_bombing import bomber,slot,impacts
from aerospace_bays import baydoc
from aerospace_turrets import turretdoc,turret_command


def finite():
    return {'fuel_check':[1]*800,'failure_generic_chance':[5000]*100,'failure_weapon_chance':[1]*100,'visibility_change':[1]*800,'sensor.random':[1]*1000,'sensor.detect':[1]*1000,'sensor.perception_xp':[1]*1000,'pilot_rolls':[12]*50,'character_d6':[6]*100,'hit_location_rolls':[7]*600,'damage_entry':[7]*600,'tow_rolls':[12]*600,'fall_directions':[1]*50,'fall_pilot_rolls':[12]*50,'fire_duration':[120]*100,'fire_rolls':[2]*100,'attack_rolls':[12]*50,'map_contact_id':list(range(26))*50,'critical_rolls':[2]*100}


def loaded(reference,actions):
    d=document(craft(at=[10,10,0]),[op('template',kind='load',unit='u',reference=reference),op('construction_pilot',unit='u',actor=dict(piloting=0,gunnery=2)),op('register',unit='u'),core(fuel=1000,fuel_orig=1000,cargo_inventory=[]),cmd('startup'),advance(30),*actions],random=dict(streams=finite()))
    d['construction']={'files':{reference:(ROOT/'btmux-mechs'/reference).read_text()}}
    return d


def bridge_document(destroyed=False,ic=True):
    u=craft('DS',at=[10,10,0],in_character=ic,destroyed=destroyed,character=501,aerospace=dict(landed=True))
    chars=[dict(id=ident,name='Crew'+str(ident),location=10,wizard=ident==503,values=dict(Build=5)) for ident in (501,502,503)]
    return document(u,[diag('bridge')],characters=chars,pilots=dict(afterlife=999),random=dict(streams=finite()))


def bridge_cases():
    for name,row in list(feature_rows('updates',3))[4:]:
        f=row['fixture'];active='OOC' not in f and 'destroyed' not in f;d=bridge_document('destroyed' in f,'OOC' not in f)
        c=Case(name,d)
        for ident in (501,502):c.expect(f'state.characters.{ident}.alive',not active).expect(f'state.characters.{ident}.location',999 if active else 10)
        c.expect('state.characters.503.alive',True).expect('state.characters.503.location',10)
        yield c


def captured_impacts():
    base=next(impacts())
    for name,row in list(feature_rows('bombing',2))[6:]:
        d=deepcopy(base.doc);actions=d['actions'];d['maps'].append(dict(name='away',id=1001,size=[30,30]))
        if 'move' in row['fixture']:actions.insert(2,op('map_command',map='away',name='transfer',args='u'));d['random']['streams']['map_contact_id']=[0,1]
        else:actions.insert(2,op('configure',unit='u',values=dict(destroyed=True)))
        c=Case(name,d).result(ok=True,scheduled=True).expect('state.units.target.damage_taken',130).expect('state.events',['ARTILLERY_HIT',0],'event_count')
        if 'move' in row['fixture']:c.final(map='away')
        else:c.final(destroyed=True)
        yield c


def exhaust_consumers():
    for name,row in feature_rows('exhaust',2):
        f=row['fixture'];u=craft('DS',at=[10,10,0],aerospace=dict(landed=True));target=craft('MECH',name='target',id=20,at=[10,10,0],sections=[dict(index=j,armor=255,armor_orig=255,rear=255,rear_orig=255,internal=100,internal_orig=100) for j in range(8)]);d=document(u,units=[u,target],random=dict(streams=finite()));actions=[]
        if 'count1;' in f:actions=[diag('takeoff_event',count=1),advance(1)];damage=400
        elif 'event-tick' in f:
            z=6 if 'plus6' in f else 5;tick=22 if 'tick22' in f else 20;u.update(started=False,at=[10,10,z]);u['aerospace']['landed']=False
            actions=[advance(tick-1),diag('move'),advance(1)];damage=8 if z==5 and tick==20 else 0
        elif 'aborted' in f:actions=[cmd('takeoff'),cmd('land'),advance(301)];damage=0
        else:
            count=6 if 'count6' in f else 2;target['sensors']=['I','I'] if count==6 else ['L','L'];target['at']=[10,9,0];actions=[diag('takeoff_event',count=count),advance(1)];damage=0
        d['actions']=actions;c=Case(name,d).expect('state.units.target.damage_taken',damage).final(**{'at.2':u['at'][2]})
        if damage:
            c.expect('draws',['hit_location_rolls',(damage+4)//5],'draw_count').expect('state.events',dict(kind='CUSTOM',unit='target',deadline=(1 if 'count1;' in f else 20)+(damage//2)*6),'has_record')
        if 'observer' in f:c.expect('state.units.target.status',0x200000,'bit_set').expect('state.events',dict(kind='BLINDREC',unit='target',deadline=3 if 'count6' in f else 5),'has_record')
        yield c


def workflows():
    for name,row in feature_rows('workflows',1):
        label=row['workflow']
        if label=='launch-abort-relaunch':
            u=craft(at=[10,10,0],aerospace=dict(landed=True),started=False)
            actions=[cmd('startup'),advance(30),cmd('speed','40'),advance(15),cmd('takeoff'),advance(2),cmd('land'),advance(11),inspect(),cmd('takeoff'),advance(10),inspect(),advance(1),inspect(),advance(4)]
            d=document(u,actions,random=dict(streams=finite()));c=Case(name,d).result(4,ok=True).result(6,ok=True).expect('results.8.units.u.aerospace.landed',True).expect('results.11.units.u.aerospace.landed',True).expect('results.13.units.u.aerospace.landed',False).final(**{'aerospace.landed':False}).expect('state.units.u.start_fz',0,'greater')
        elif label=='landing-and-zones':
            u=craft('VTOL',at=[10,10,1]);actions=[cmd('addmine','10 10 STANDARD 5'),cmd('checklz'),cmd('land')];d=document(u,actions,random=dict(streams=finite()));c=Case(name,d).result(2,ok=True).final(**{'aerospace.landed':True}).expect('state.units.u.damage_taken',0,'greater').expect('state.map.mines',1,'length').expect('state.map.mines.0.strength',5)
        elif label=='flight-and-backup':
            d=loaded('DS.Aero',[cmd('takeoff'),advance(301),cmd('climb','90'),cmd('thrust','20'),advance(5),inspect(),configure(fuel=1),advance(1),inspect(),advance(1),inspect(),advance(1)])
            c=Case(name,d).result(ok=True).result(6,ok=True).expect('results.11.units.u.fz',64.5,'greater').expect('results.14.units.u.fuel',0).final(fuel=-1).expect('state.events',['MOVE',1],'event_count')
        elif label=='aircraft-periodic-updates':
            u=craft(at=[10,10,100],core=dict(weap_heat=30),aerospace=dict(landed=False));d=document(u,[advance(2),inspect(),advance(2),inspect(),diag('control'),advance(11),inspect(),advance(1)],random=dict(streams=finite()));d['config']['periodic_updates']=True;u['piloting']=0
            c=Case(name,d).expect('results.1.units.u.heat',20).expect('results.1.units.u.vis_mod',50).expect('results.3.units.u.vis_mod',51).final(**{'aerospace.spinning':False})
        elif label=='bomb-list-aim-drop':
            u=bomber(5,at=[10,10,0],aerospace=dict(landed=True,speed=32.25),measured_mass=51200,core=dict(carried_cargo=5100));d=document(u,[cmd('bomb','list'),cmd('takeoff'),advance(11),advance(10),cmd('bomb','aim'),cmd('bomb','drop 1'),inspect(),advance(20)],random=dict(streams=finite()));c=Case(name,d).result(ok=True).result(4,ok=True).result(5,ok=True,scheduled=True).expect('results.6.units.u.sections.5.slots.0.type',0).expect('results.6.units.u.carried_cargo',0).expect('state.events',['ARTILLERY_HIT',0],'event_count')
        elif label=='bomb-scatter-and-terrain':
            u=bomber(at=[10,10,8],aerospace=dict(start_fy=322.5,fz=516));draws=finite();draws.update(pilot_rolls=[2],bomb_scatter_distance=[2],bomb_scatter_direction=[0]);d=document(u,[op('map_command',name='addhex',args='10 12 . 9'),op('map_command',name='addhex',args='11 13 . 9'),cmd('bomb','aim'),cmd('bomb','drop 1'),advance(4)],random=dict(streams=draws));c=Case(name,d).result(2,x=10,y=14,time=4).result(3,ok=True,scheduled=True).final(**{'sections.5.slots.0.type':0})
        elif label=='dropship-exhaust':
            d=loaded('DS.Union',[op('map_command',name='addhex',args='10 11 ` 0'),op('map_command',name='addhex',args='10 14 ` 0'),cmd('takeoff'),advance(299),inspect(),advance(1),inspect(),advance(1)])
            c=Case(name,d).result(ok=True).result(8,ok=True).expect('results.10.units.u.aerospace.landed',True).expect('results.12.units.u.aerospace.landed',True).final(**{'aerospace.landed':False}).expect('state.maps.field.hexes.340.underlying','%').expect('state.maps.field.hexes.430.terrain','&')
        elif label=='bay-entry-and-content-transfer':
            d=baydoc();u=d['units'][0];u['at']=[10,10,0];u['aerospace']['carrying']=12;d['units'].append(craft('MECH',name='cargo',id=12,at=[10,10,0]));d['random']['streams']=finite();d['actions']=[cmd('speed','10.75'),advance(33),cmd('speed','0'),advance(3),inspect(),cmd('enterbay'),advance(11),inspect(),advance(1)]
            c=Case(name,d).result(5,ok=True).expect('results.7.units.u.map','field').final(map='bay',at=[5,5,0]).expect('state.units.cargo.map','bay')
        elif label=='bay-exit-and-placement':
            d=baydoc();d['units'][0].update(map='bay',at=[5,0,0]);d['random']['streams']=finite();d['actions']=[cmd('speed','10.75'),advance(35)];c=Case(name,d).result(ok=True).final(map='field').expect('state.units.u.personnel.location',1000)
        elif label=='turret-control-and-fire':
            d=turretdoc([turret_command('initialize'),turret_command('initialize',turret='B',actor=202),turret_command('lock','BB'),turret_command('lock','AA',turret='B',actor=202),turret_command('fire','0'),turret_command('fire','0',turret='B',actor=202),turret_command('fire','1',turret='B',actor=202),advance(40),cmd('fire','0')]);d['turrets'][0]['gunner']=-1;d['turrets'][1]['gunner']=-1;d['random']['streams']=finite()
            c=Case(name,d).result(ok=True).result(1,ok=True).result(4,ok=True).result(5,ok=False).result(6,ok=True).final(shots_fired=3,target=20).expect('state.turrets.A.target',21).expect('state.turrets.B.target',20).expect('state.overrides',dict(pilot=0,arc=0))
        else:
            d=bridge_document();ship=d['units'][0];attacker=craft('MECH',name='attacker',id=20,at=[10,9,0],facing=180,weapons=[dict(name='IS.MediumLaser',section=1,critical=4)],target='u');d['units'].append(attacker);d['random']['streams'].update(hit_location_rolls=[2],crittable_chance=[23]);d['actions']=[cmd('fire','0',unit='attacker')]
            c=Case(name,d).expect('results.0.attack.hit',True).expect('state.characters.501.alive',False).expect('state.characters.502.alive',False).expect('state.characters.503.alive',True).expect('state.characters.501.location',999)
        yield c


def template_workflows():
    d=loaded('Cavalry',[cmd('takeoff'),advance(1),inspect(),cmd('vertical','0'),cmd('land')])
    yield Case('procedures/catalog-VTOL',d).result(ok=True).result(6,ok=True).expect('results.8.units.u.vertical_speed',60).result(9,ok=True).result(10,ok=True).final(template_ref='Cavalry',real_mass=24.75,**{'aerospace.landed':True})
    d=baydoc();prefix=loaded('WVR-6R',[])['actions'];d['actions']=prefix+[cmd('enterbay'),advance(12)]
    d['construction']={'files':{'WVR-6R':(ROOT/'btmux-mechs/WVR-6R').read_text()}};d['random']['streams']=finite()
    yield Case('procedures/catalog-MECH-bay',d).result(ok=True).result(6,ok=True).final(template_ref='WVR-6R',map='bay',at=[5,5,0],real_mass=55)


def friday_workflows():
    template=(ROOT/'qa/fixtures/aerospace/Friday').read_text()
    prefix=[op('template',kind='load',unit='u',reference='Friday'),inspect(),op('construction_pilot',unit='u',actor=dict(piloting=0,gunnery=2)),op('register',unit='u'),core(cargo_inventory=[]),cmd('startup'),advance(30),cmd('speed','40'),advance(15),cmd('takeoff'),advance(11),inspect()]
    flight=[cmd('thrust','40'),cmd('climb','0'),cmd('heading','90'),cmd('dive','0'),advance(4),inspect(),cmd('land'),inspect()]
    d=document(craft(at=[10,10,0]),prefix+flight,construction=dict(files={'Friday':template}),random=dict(streams=finite()))
    c=Case('procedures/Friday-flight-land',d).result(ok=True).expect('results.1.units.u.si',20).expect('results.1.units.u.fuel',1000).expect('results.1.units.u.max_speed',64.5).expect('results.1.units.u.engine_rating',200)
    c.expect('results.11.units.u.aerospace.landed',False).expect('results.11.units.u.desired_speed',43).expect('results.11.units.u.carried_cargo',3060).result(12,ok=True).result(13,ok=True).result(14,ok=True).result(15,ok=True).result(18,ok=True).final(template_ref='Friday',si=20,**{'aerospace.landed':True}).expect('results.17.units.u.fuel',1000,'less').expect('results.17.units.u.start_fx',0,'greater')
    c.expect('results.1.units.u.real_num_sinks',10).expect('results.1.units.u.sink_capacity',10).expect('results.1.units.u.sections.3.slots.2.type',401).expect('results.1.units.u.sections.3.slots.10.type',401)
    effective=64.5*51200/(51200+3060)
    cap=f32(f32(f32(1.25*5)*effective)/30)
    c.expect('results.17.units.u.start_fx',4*cap,'close')
    for loc,armor in enumerate((40,30,30,20)):
        c.expect(f'results.1.units.u.sections.{loc}.armor',armor).expect(f'results.1.units.u.sections.{loc}.internal',10)
    yield c
    d=document(craft(at=[10,10,0]),prefix+[advance(20),cmd('bomb','list'),cmd('bomb','aim'),cmd('bomb','drop 1'),inspect(),advance(30)],construction=dict(files={'Friday':template}),random=dict(streams=finite()))
    c=Case('procedures/Friday-bombing',d).result(ok=True).result(13,ok=True).expect('results.13.rows',3,'length').result(14,ok=True).result(15,ok=True,scheduled=True).expect('results.16.units.u.sections.0.slots.4.type',0).expect('results.16.units.u.carried_cargo',2040).final(template_ref='Friday',si=20).expect('state.events',['ARTILLERY_HIT',0],'event_count')
    yield c


def remaining_transfers():
    d=baydoc();u=d['units'][0];u.update(specials2=0x20,sections=[dict(index=0,slots=[dict(index=0,type=430)])]);d['units'].append(craft('MECH',name='peer',id=12,at=[10,8,0],specials2=0x20,sections=[dict(index=0,slots=[dict(index=0,type=430)])]));d['random']['streams']=finite()
    d['actions']=[cmd('c3i','02'),inspect(),cmd('enterbay'),advance(12)]
    yield Case('procedures/C3i-entry',d).result(ok=True).expect('results.1.units.u.communications.c3i.size',1).result(2,ok=True).final(map='bay').expect('state.units.u.communications.c3i.size',0).expect('state.units.peer.communications.c3i.size',0)
    from aerospace_bays import callbacks
    d=deepcopy(next(c.doc for c in callbacks() if any(u.get('class')=='MW' for u in c.doc['units'])));d['actions'].append(advance(10))
    yield Case('procedures/MW-disposal',d).expect('state.characters.501.location',2000).expect('state.personnel.trace',dict(kind='discard',id=10),'has_record').expect('state.events',['NUKEMECH',0],'event_count')
    d=deepcopy(next(friday_workflows()).doc);d['actions']=d['actions'][:10]+[advance(2),cmd('land'),advance(11),inspect(),cmd('takeoff'),advance(10),inspect(),advance(1)]
    yield Case('procedures/Friday-abort-relaunch',d).result(ok=True).result(11,ok=True).expect('results.13.units.u.aerospace.landed',True).result(14,ok=True).expect('results.16.units.u.aerospace.landed',True).final(template_ref='Friday',si=20,**{'aerospace.landed':False}).expect('state.events',['MOVE',1],'event_count')


def preservation_boundaries():
    # Procedure 2/11: independent UI counterparts to the preserved height tests.
    d=document(craft('VTOL',at=[10,10,0]),[cmd('vertical','-10.75'),advance(1)],random=dict(streams=finite()));d['maps'][0]['default']=['WATER',2]
    yield Case('procedures/VTOL-water-surface',d).result(ok=True).final(destroyed=False,vertical_speed=-10.75,**{'at.2':0})
    d=document(craft('VTOL',at=[10,10,300]),[cmd('vertical','10.75'),advance(1)],random=dict(streams=finite()))
    yield Case('procedures/VTOL-orbit-ceiling',d).result(ok=True).final(destroyed=False,vertical_speed=0,fz=299*64.5,**{'at.2':299})
    # Procedure 9: DSBearMod rounds exactly at30, and AERO uses an aero door.
    for facing,at in [(29,[10,9,0]),(30,[11,10,0])]:
        d=baydoc();d['units'][0].update(map='bay',at=[0,0,0]);d['units'][1]['facing']=facing;d['actions']=[configure(x=-1),diag('edge')]
        yield Case('procedures/bay-facing-'+str(facing),d).final(map='field',at=at)
    d=baydoc(kind='AERO');d['units'][0].update(map='bay',at=[0,0,0]);ship=d['units'][1];ship['at'][2]=20;ship['aerospace']['landed']=False;ship['sections'][0]['slots'][0]['type']=420;d['actions']=[configure(x=-1),diag('edge')]
    yield Case('procedures/bay-AERO-exit',d).final(map='field',at=[10,9,21],fz=21*64.5,**{'aerospace.landed':False}).expect('state.events',['MOVE',0],'event_count')


def aircraft_services():
    # A real TAG command establishes the relationship; invalidate its peer and
    # leave stale illumination/ECM flags for the scheduled update to recompute.
    u=craft(at=[10,10,100],specials2=0x8000,sections=[dict(index=0,slots=[dict(index=0,type=423)])])
    target=craft('MECH',name='target',id=20,contact_id='BB',team=2,at=[10,9,100])
    actions=[cmd('tag','BB'),op('configure',unit='target',values=dict(tagged_by=0)),op('configure',unit='u',values=dict(status2=4,crit_status=0x800)),inspect(),advance(2),inspect(),advance(2),inspect()]
    d=document(u,actions,units=[u,target],random=dict(streams=finite()));d['config']['periodic_updates']=True
    c=Case('procedures/aircraft-service-state',d).result(ok=True)
    for index,active in [(3,False),(5,False),(7,True)]:
        for field,value in {'relationships.tag_target':'target' if index==3 else 0,'crit_status':0 if active else 0x800,'status2':0 if active else 4}.items():
            c.expect(f'results.{index}.units.u.{field}',value)
    # Normal PLOS runs at+1 and independently invalidates TAG before HEAT_TICK2.
    c.expect('state.events',['TAG_RECYCLE',2],'event_count')
    yield c
    for now in (2,3):
        isolated=deepcopy(d);isolated['config']['periodic_updates']=False
        isolated['actions']=actions[:4]+[op('clock',name='skip_seconds',seconds=now),diag('update'),inspect()]
        c=Case('procedures/aircraft-service-window-'+str(now),isolated).result(ok=True)
        c.expect('results.3.units.u.relationships.tag_target','target')
        c.final(**{'relationships.tag_target':'target' if now==2 else 0,'crit_status':0x800 if now==2 else 0,'status2':4 if now==2 else 0})
        c.expect('state.events',['TAG_RECYCLE',1 if now==2 else 2],'event_count')
        yield c


def spheroid_descent():
    from aerospace_flight import motion
    for case in motion():
        if any(c['path']=='state.units.u.messages' and 'WARNING:' in str(c['value']) for c in case.checks):
            d=deepcopy(case.doc);d['units'][0]['class']='SPHEROID_DS'
            c=Case('procedures/spheroid-descent-'+case.name.rsplit('/',1)[1],d);c.checks=deepcopy(case.checks)
            yield c


def exhaust_observer():
    d=loaded('DS.Union',[cmd('takeoff'),advance(225),inspect(),advance(1),inspect(),advance(65),inspect(),advance(10)])
    d['units'].append(craft('MECH',name='observer',id=20,at=[10,18,0]))
    c=Case('procedures/catalog-DS-observer',d).result(ok=True).result(6,ok=True)
    glow="'s engines start to glow with unbearable intensity.."
    # Compare actual delivered room/unit notices, including their exact source
    # suffix, while allowing the template service to supply the contact prefix.
    c.expect('results.8.units.observer.messages',glow,'no_text_suffix')
    c.expect('results.10.units.observer.messages',glow,'text_suffix')
    c.expect('results.12.units.observer.messages',"'s engines are almost ready to lift off!",'text_suffix')
    c.final(**{'aerospace.landed':False}).expect('state.units.observer.destroyed',False).expect('state.units.observer.damage_taken',0)
    yield c
