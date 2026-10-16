"""Direct loss quirks, deferred criticals, components and missile sequencing."""
from six_support import *

def direct_effects():
    for name,row in rows('criticals',4):
        f=row['fixture'];u=fighter();actions=[];c=None
        for s in u['sections'][:6]:s.update(armor=80,armor_orig=100)
        if any(k in f for k in ('weapon','mount','lasers','same-type')):
            count=1 if f.startswith('one-global') else 2
            u['weapons']=[dict(name='IS.MediumLaser',section=0,critical=i) for i in range(count)]
            flags0=1 if f.startswith('first-of') else 0;flags1=1 if f.startswith('second-global-mount-destroyed') else 0
            u['sections'][0]['slots']=[dict(index=0,firemode=flags0),dict(index=1,firemode=flags1,data=5 if 'recycling' in f else 0)]
            actions=[dd('location',profile='legacy',side='FRONT',roll=3)]
            d=session(u,actions);c=Case(name,d)
            lost=count==2 and not f.startswith('second-global')
            c.expect('state.units.u.sections.0.slots.0.firemode',1 if lost or flags0 else 0).expect('state.units.u.sections.0.slots.1.firemode',flags1)
            drawcheck(c,'fighter_weapon_choice',[0] if count==2 else [],0,0)
        elif f.startswith('sink90'):
            if 'no-local' not in f:u['sections'][5]['slots']=[dict(index=0,special='HEAT_SINK',firemode=1 if 'destroyed' in f else 0),dict(index=1,special='HEAT_SINK')]
            d=session(u,[dd('location',profile='legacy',side='LEFTSIDE',roll=4)]);c=Case(name,d).final(real_num_sinks=25 if 'no-local' in f else 23)
            c.expect('state.units.u.sections.5.slots.0.firemode',0 if 'no-local' in f else 1).expect('state.units.u.sections.5.slots.1.firemode',0)
        elif f.startswith('rear'):
            spinning='already-spinning' in f;landed='landed' in f;destroyed='destroyed' in f
            u.update(destroyed=destroyed);u['aerospace'].update(landed=landed,spinning=spinning,start_spin=2 if spinning else 0)
            d=session(u,[op('clock',name='skip_seconds',seconds=7),dd('location',profile='legacy',side='BACK',roll=11 if '11' in f else 3)])
            c=Case(name,d).final(**{'aerospace.spinning':spinning or not(landed or destroyed),'aerospace.start_spin':2 if spinning else 0 if landed or destroyed else 7})
        else:
            u['sections'][3]['slots']=[dict(index=11,type=387)];u['core']['carried_cargo']=1020
            c=Case(name,session(u,[dd('location',profile='legacy',side='FRONT',roll=10)])).expect('state.units.u.sections.3.slots.11.type',387).final(carried_cargo=1020).expect('state.events',['ARTILLERY_HIT',0],'event_count')
        drawcheck(c,'critical_rolls',[]);yield c

def deferred():
    for name,row in rows('criticals',5):
        roll,count=int(row['roll']),int(row['count']);u=fighter();u['sections'][5].update(armor=18,armor_orig=20,slots=[dict(index=i,special='HEAT_SINK') for i in range(3)])
        d=session(u,[dd('location',profile='legacy',side='BACK',roll=2),damage(5,1,rear=True,critical=True)])
        d['random']['streams'].update(crittable_chance=[6],critical_rolls=[roll])
        c=Case(name,d).expect('results.0',[5,True]).expect('state.units.u.sections.5.armor',17).final(real_num_sinks=25-count)
        for i in range(3):c.expect(f'state.units.u.sections.5.slots.{i}.firemode',int(i<count))
        drawcheck(c,'crittable_chance',[6],1,11);drawcheck(c,'critical_slot',[0]*count);yield c

def components():
    for name,row in rows('criticals',6):
        f=row['fixture'];u=fighter();loc=4 if f.startswith('Cockpit') else 5;kind='LIFE_SUPPORT' if 'LifeSupport' in f else 'SENSORS' if 'Sensors' in f else 'COCKPIT' if 'Cockpit-IC' in f else 'ENGINE' if f.startswith('Engine-component') else 'HEAT_SINK'
        u['sections'][loc]['slots']=[] if f=='no-eligible-slots' else [dict(index=0,special=kind)]
        if 'Sensors' in f:u.update(lrs_range=80,tac_range=40,scan_range=20,base_to_hit=0,crit_status=2 if 'second' in f else 0)
        if 'engineheat' in f:u['engine_heat']=int(f.rsplit('engineheat',1)[1])
        if f.startswith('eligible-slot'):u['sections'][loc]['slots'] += [dict(index=1,special='HEAT_SINK',firemode=1),dict(index=2,special='HEAT_SINK',firemode=8)]
        if f=='no-eligible-slots':u['sections'][3]['slots']=[dict(index=0,special='HEAT_SINK')]
        if f=='critproof':u['specials']=0x40000000
        if f=='combat-safe':u['status']=0x400000|8
        d=session(u,[dd('critical',section=loc,count=1)])
        if f=='vcrit0':d['config']['vcrit']=0
        if kind=='COCKPIT':
            u.update(character=110,in_character=True);d['characters']=[dict(id=110,name='Pilot',location=10,connected=True,values=dict(Build=5))];d['pilots']=dict(afterlife=999)
        c=Case(name,d);guard=f in ('no-eligible-slots','combat-safe','critproof','vcrit0')
        if guard:
            c.expect('results.0',[]);drawcheck(c,'critical_slot',[])
            if f=='no-eligible-slots':c.expect('state.units.u.sections.3.slots.0.firemode',0).final(real_num_sinks=25)
        else:
            c.expect(f'state.units.u.sections.{loc}.slots.0.firemode',1)
            if kind=='LIFE_SUPPORT':c.expect('state.units.u.crit_status',64,'bit_set')
            if kind=='SENSORS':
                second='second' in f;c.final(lrs_range=0 if second else 40,tac_range=0 if second else 20,scan_range=0 if second else 10,base_to_hit=75 if second else 2)
            if kind=='COCKPIT':c.final(destroyed=True,pilot_present=False).expect('state.characters.110.alive',False).expect('state.characters.110.location',999)
            if kind=='ENGINE':
                heat=int(f.rsplit('engineheat',1)[1])+5;c.final(engine_heat=heat,destroyed=heat==15)
                if heat<15:c.final(max_speed=60)
            if kind=='HEAT_SINK':c.final(real_num_sinks=24)
            if f.startswith('eligible-slot'):c.expect('state.units.u.sections.5.slots.2.firemode',8);drawcheck(c,'critical_slot',[0],0,0)
        yield c

def missile_cases():
    for name,row in rows('criticals',7):
        lrm=row['family'].startswith('LRM');weapon='IS.LRM-15' if lrm else 'IS.SRM-2'
        u=fighter(contact_id='AA',team=2,weapons=[dict(name='IS.MediumLaser',section=0)])
        gun=fighter(pilot_details=dict(gunnery=0),name='gun',id=20,contact_id='BB',at=[10,9,10],facing=180,weapons=[dict(name=weapon,section=0)])
        gun['sections'][3]['slots']=[dict(index=0,ammo=weapon,data=8 if lrm else 50)]
        d=session(u,[cmd('fire','0 AA',unit='gun')],units=[u,gun]);d['random']['streams'].update(hit_location_rolls=[3]*10,crittable_chance=[22,5])
        c=Case(name,d).result(accepted=True).expect('results.0.attack.hit',True).expect('state.units.u.sections.0.armor',9 if lrm else 20).expect('state.units.gun.sections.3.slots.0.data',7 if lrm else 49)
        drawcheck(c,'crittable_chance',[22] if lrm else [22,5]);drawcheck(c,'fighter_weapon_choice',[])
        c.expect('draws',dict(name='crittable_chance',value=22,low=1,high=71),'has_record')
        if not lrm:c.expect('draws',dict(name='crittable_chance',value=5,low=1,high=11),'has_record')
        # Each group executes within one real shot, with armor chance draws
        # interleaved only at the eligible pre-hit armor (24; then SRM22).
        sequence=[('attack_rolls',12),('failure_weapon_chance',1)]+[('missile_pre_roll',1)]*3+[('missile_cluster',12)]
        for i in range(3 if lrm else 2):
            sequence.append(('hit_location_rolls',3))
            if i==0:sequence.append(('crittable_chance',22))
            elif not lrm:sequence.append(('crittable_chance',5))
            sequence.append(('damage_entry',7))
        c.expect('draws',len(sequence),'length').expect('results.0.attack.damage_dealt',15 if lrm else 4)
        for i,(stream,value) in enumerate(sequence):c.expect(f'draws.{i}.name',stream).expect(f'draws.{i}.value',value)
        yield c
