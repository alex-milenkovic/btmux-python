"""Remaining documented UI boundaries identified during the final requirement audit."""
from heat_support import Case,action,command,maintain,advance,hit,weapon,armed,vehicle


def cases():
    for roll in (7,10,12):
        c=Case('audit-fire/entry-'+str(roll),vehicle(),
            [action('enter_hex',unit='u',at=[3,2,0])],integrated=True,
            map={'hexes':[dict(at=[3,2],terrain='FIRE',elevation=0)]},
            config={'periodic_updates':False,'advanced_vehicle_fire':True},
            random={'fire_rolls':[roll],'fire_damage':[3]*8})
        c.expect('consumed.fire_rolls',1).final(**{'sections.0.front':100 if roll==7 else 97})
        yield c.count('final.units.u.burning_sides',8 if roll==12 else 0)
    yield Case('audit-fire/ordinary-entry',vehicle(),[command('speed','walk'),advance(30)],integrated=True,
        map={'default':['FIRE',0],'hexes':[dict(at=[2,2],terrain='GRASSLAND',elevation=0)]},
        config={'periodic_updates':False,'advanced_vehicle_fire':True},random={'fire_rolls':[7]*20}).expect(
        'draws.0.name','fire_rolls').final(real_terrain='&').count('final.units.u.burning_sides',0)
    yield Case('audit-fire/jump-water',dict(jump_mp=3,events={'inferno':180}),
        [command('jump','0','1'),advance(30),advance(180)],integrated=True,
        map={'default':['WATER',2],'hexes':[dict(at=[2,2],terrain='GRASSLAND',elevation=0)]},
        random={'pilot_rolls':[12]*10}).expect('results.0.accepted',True).expect(
        'results.1.snapshot.units.u.jellied',False).final(jumping=False,jellied=False).notice('fires finally die',0)
    for label,changes in [('no-fuel',{'fuel':0}),('fallen',{'fallen':True})]:
        unit={'class':'VTOL','movement':'VTOL','at':[2,2,-1],'vertical_speed':-10.75,**changes}
        yield Case('audit-heights/'+label,unit,[maintain('height')],random={'fall_pilot_rolls':[12],
            'fall_directions':[1],'hit_location_rolls':[7]*20}).final(
            **{'landed':True,'at.2':0,'last_fall_levels':2,'speed':0,'vertical_speed':0}).notice('CRASH!')
    yield Case('audit-heights/aero-orbit-exclusion',{'class':'AERO','movement':'FLY','at':[2,2,300]},
        [maintain('height')]).final(**{'at.2':300,'fz':19350}).notice('cannot achieve orbit',0)
    yield Case('audit-heights/sub-dive',{'class':'VEH_NAVAL','movement':'SUB','at':[2,2,0]},
        [command('vertical','-10.75'),advance(13)],integrated=True,map={'default':['WATER',3]}).accepted(1).notice('unit dives!').final(**{'at.2':-1})
    yield Case('audit-ticks/gravity-no-special',dict(speed=75.25),[maintain('pilot')],clock={'event':30},
        map={'gravity':150},random={'pilot_rolls':[]}).count('results.0.rolls',0)
    yield Case('audit-ticks/gravity-transition',dict(speed=75.25),[command('sprint'),maintain('pilot')],
        clock={'event':30},map={'special_rules':True,'gravity':150},random={'pilot_rolls':[]}).expect(
        'results.0.accepted',True).count('results.1.rolls',0)
    yield Case('audit-ticks/gravity-destroyed-leg',dict(speed=75.25,
        sections=[dict(location='LLEG',internal=0)]),[maintain('pilot')],clock={'event':30},
        map={'special_rules':True,'gravity':150},random={'pilot_rolls':[2],'critical_rolls':[2]}).final(
        **{'sections.5.internal':0,'sections.6.internal':98}).expect('consumed.critical_rolls',1)
    yield Case('audit-ticks/turret-hex',vehicle(auto_turret=True,facing=90,target_hex=[2,1]),[advance(2)],
        integrated=True,config={'periodic_updates':True}).final(turret_facing=270,los=True)
    yield Case('audit-ticks/turret-moving-target',units=[dict(name='u',**vehicle(auto_turret=True,facing=90,target_id='target')),
        dict(name='target',at=[2,1,0],facing=0)],actions=[command('speed','walk',unit='target'),advance(5)],
        integrated=True,config={'periodic_updates':True}).final(turret_facing=270).expect('final.units.target.desired_speed',43.0)
    c=Case('audit-errors/missing-turret-target',vehicle(auto_turret=True,target_id='missing'),[advance(2)],
        config={'periodic_updates':True});c.error='missing';yield c
    for label,unit in [('destroyed-unit',{'states':['started','destroyed']}),
                       ('destroyed-section',{'sections':[dict(location='RARM',internal=0)]})]:
        yield Case('audit-ticks/recycle-'+label,dict(equipment=[weapon(recycle=4)],**unit),
            [action('dispatch',seconds=4),action('heartbeat',wall_seconds=0)]).final(
            **{'weapons.0.recycle':4}).notice('finished recycling',0)
    yield Case('audit-ticks/recycle-fail-destroyed',dict(equipment=[weapon(recycle=4,temporary_failure='DESTROYED')]),
        [action('dispatch',seconds=4),action('heartbeat',wall_seconds=0)]).final(**{'weapons.0.recycle':0,
        'weapons.0.slot_recycle':0,'weapons.0.temporary_failure':0}).notice('operational again')
    yield Case('audit-ticks/recycle-mw',{'class':'MW','equipment':[weapon(recycle=4,slot=1)]},
        [action('dispatch',seconds=4),action('heartbeat',wall_seconds=0)]).final(
        **{'weapons.0.recycle':0}).notice('ready to attack again')
    for kind,remaining in [('MECH',0),('VEH_GROUND',0),('VTOL',0),('MW',4)]:
        yield Case('audit-ticks/physical-recycle-'+kind,{'class':kind,'sections':[dict(location='LARM',recycle=4)]},
            [action('dispatch',seconds=4),action('heartbeat',wall_seconds=0)]).final(**{'sections.0.recycle':remaining})
    for state in ('jumping','running'):
        unit=armed(states=['started','jumping'] if state=='jumping' else ['started'],desired_speed=75.25 if state=='running' else 0)
        yield Case('audit-dump/stop-'+state,unit,[command('dump','stop')]).accepted(0).expect(
            'results.0.message',"You can't dump ammo while "+state+'!')
    for damage in (19,20):
        yield Case('audit-stagger/legacy-threshold-'+str(damage),actions=[hit(damage),maintain('pilot')],
            config={'periodic_updates':False,'new_stagger':0},clock={'event':7},random={'pilot_rolls':[12]}).expect(
            'consumed.pilot_rolls',int(damage==20))
    yield Case('audit-stagger/legacy-dropship',{'class':'DS','movement':'FLY'},[hit(20,section='FRONT'),maintain('pilot')],
        config={'periodic_updates':False,'new_stagger':0},clock={'event':7},random={'pilot_rolls':[]}).final(turn_damage=0)
    yield Case('audit-ticks/fired-rocket',dict(equipment=[weapon(recycle=4,fired_rocket=True)]),
        [action('dispatch',seconds=4),action('heartbeat',wall_seconds=0)]).final(
        **{'weapons.0.recycle':0}).notice('finished recycling',0)
