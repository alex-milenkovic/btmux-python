"""Additional literal obligations in procedures 1–13 beyond the example tables."""
from qa.repair_workflows import *
from qa.repair_events import scheduled

def supplements():
    for label,flag,part,command,field,due in [('FF',0x80000,541,'fixarmor','armor',180),('Endosteel',0x100000,540,'fixinternal','internal',540)]:
        u=unit(specials=flag);u['sections'][4][field]=9
        d=doc(u,stock=stocks((part,0,1)),actions=[cmd(command,'CT'),advance(due-1),inspect(),advance(1),inspect()])
        yield Case('procedures/material-'+label,d).result(ok=True).expect('results.2.units.u.sections.4.'+field,9).expect('state.units.u.sections.4.'+field,10).expect('state.economy.objects.1000.ECONPARTS','').expect('state.repair_jobs',[])
    u=unit();u['sections'][4]['config']=8;setslot(u,4,2,type=HEATSINK,firemode=1);setslot(u,4,3,ammo='IS.SRM-6',data=0,firemode=2)
    yield Case('procedures/fixextra-state',doc(u,actions=[cmd('fixextra')])).result(ok=True).expect('state.units.u.sections.4.config',8,'not_bit').expect('state.units.u.sections.4.slots.2.firemode',0).expect('state.units.u.sections.4.slots.3.firemode',0).expect('state.units.u.sections.4.slots.3.data',15).expect('draws',[])
    d=original();d['actions'] +=[damage('Nose',5),cmd('magic'),inspect()]
    # Magic replays the intact design while retaining existing ordinary damage.
    yield Case('procedures/magic-template',d).result(3,ok=True,result=True).expect('state.units.u.sections.0.armor',19).expect('state.units.u.sections.0.armor_orig',24).expect('state.units.u.si',0)
    d=doc(actions=[scheduled(47,loc=4,pos=3,delay=180),scheduled(48,loc=2,pos=2,delay=540),op('schedule',unit='u',callback='mech_move_event',delay=9999),diag('latest')],characters=[actor(),actor(7)])
    yield Case('procedures/latest-real-max',d).expect('results.3',1080)
    d=doc(actions=[repair('add',object=1000,part=403,brand=0,count=2),repair('add',object=1000,part=403,brand=0,count=3),repair('find',object=1000,part=403)])
    yield Case('procedures/raw-add',d).expect('state.economy.objects.1000.ECONPARTS',stocks((403,0,2),(403,0,3))).expect('results.2',2)
    d=hangar();d['repair_economy']['objects'][0]['ECONPARTS']='';d['characters'][0]['location']=1000
    d['actions']=[cmd('Raddstuff','Ammo_SRM 3'),repair('actor',actor=200,values={'location':10}),cmd('stores'),cmd('loadcargo','Ammo_SRM 2'),inspect(),cmd('unloadcargo','Ammo_SRM 1'),inspect()]
    yield Case('procedures/admin-cargo-conservation',d).expect('results.2.result.rows.0.count',3).expect('results.4.economy.objects.1000.ECONPARTS',stocks((517,0,1))).expect('results.4.economy.objects.10.ECONPARTS',stocks((517,0,2))).expect('state.economy.objects.1000.ECONPARTS',stocks((517,0,2))).expect('state.economy.objects.10.ECONPARTS',stocks((517,0,1))).expect('state.units.u.carried_cargo',1024)
    for mode in ('IC','bay','shutdown'):
        d=hangar()
        if mode=='IC':d['repair_economy']['objects'][0]['in_character']=True
        elif mode=='bay':d['repair_economy']['objects'][0]['MECHSKILLS']='4 4 1'
        else:d['units'][0]['started']=False
        d['actions']=[cmd('stores')]
        yield Case('procedures/stores-'+mode,d).result(ok=False).expect('results.0.error',{'IC':'hangar','bay':'4,4','shutdown':'online'}[mode],'contains').expect('state.economy.objects.1000.ECONPARTS',stocks((517,0,5)))
    u=unit();u.pop('repair');u['core']['cargo_inventory']=[[517,0,2]]
    d=doc(u,actions=[op('diagnose',unit='u',kind='SetCargoWeight',args=[])]);d.pop('repair_economy');d['characters'][0].pop('tech')
    c=Case('procedures/nonpersistent-cargo',d);c.cli='tools.aerospace';c.expect('state.units.u.carried_cargo',2048);yield c
    d=original();d['config']['periodic_updates']=True
    d['actions'] +=[op('editor',editor='e',name='addbomb',args='Bomb_10_Standard F 12'),cmd('startup'),advance(30),cmd('speed','60'),advance(10),cmd('takeoff'),advance(11),inspect(),advance(5),cmd('bomb','list'),cmd('bomb','aim'),cmd('bomb','drop 1'),inspect(),advance(4),inspect()]
    yield Case('procedures/bomb-release-cargo',d).result(ok=True).expect('results.9.units.u.carried_cargo',1020).result(13,ok=True,scheduled=True).expect('results.14.units.u.carried_cargo',0).expect('state.units.u.sections.3.slots.11.type',0).expect('state.units.u.carried_cargo',0)
    for label in ('burn','OOD','own-jump','target-jump','fallen','LOS','different-hex','bridge'):
        d=tow_doc();u,v=d['units']
        if label=='burn':v['repair']['burn_recovery_countdown']=3
        elif label=='OOD':v['cocoon']=1
        elif label=='own-jump':u['status']=0x48
        elif label=='target-jump':v['status']=0x40
        elif label=='fallen':u['fallen']=True
        elif label=='LOS':u['at']=[1,1,0];v['at']=[10,10,0];d['map'].update(mapvis=1,maxvis=1)
        elif label=='different-hex':v['at']=[4,3,0]
        else:u['at'][2]=1;d['map']['hexes']=[dict(at=[3,3],terrain='BRIDGE',elevation=1)]
        d['actions']=[cmd('pickup','01')]
        yield Case('procedures/pickup-'+label,d).result(ok=False).expect('results.0.error',{'burn':'burning','OOD':'OOD','own-jump':'jumping','target-jump':'mid air','fallen':'position','LOS':'line of sight','different-hex':'same hex','bridge':'under the bridge'}[label],'contains').expect('state.units.u.repair.carrying',-1)
    for cables in (False,True):
        d=tow_doc(cables);target=d['units'][-1];target['at'][2]=-1
        d['map']['hexes']=[dict(at=[3,3],terrain='ICE',elevation=1)]
        if cables:
            for u in d['units']:u['at'][2]=-1
        d['random']['streams'].update(hit_location_rolls=[7]*100,crittable_chance=[22]*100,critical_slot=[0]*100)
        d['actions']=[cmd('attachcables','01 02') if cables else cmd('pickup','01'),inspect()]
        c=Case('procedures/ice-'+('cables' if cables else 'pickup'),d).result(ok=True)
        # BreakSurface makes the mirrored surface target fall to water floor -1.
        c.expect('state.units.u.cached_terrain','-' if cables else '~').expect('state.units.v.at.2',-1);yield c
    d=tow_doc();v=d['units'][1];v.update(status=2|4|0x04000000,tank_crit_status=4,swarm_target='v');d['actions']=[cmd('pickup','01'),cmd('speed','60'),inspect()]
    yield Case('procedures/tow-cleared-flags',d).result(ok=True).expect('state.units.v.status',2|4|0x04000000,'not_bit').expect('state.units.v.tank_crit_status',4,'not_bit').expect('state.units.v.repair.swarm_target',-1).expect('state.units.u.desired_speed',20)
    # Both conversion commands preserve unrelated mode bits, including refusal writes.
    u=unit();setslot(u,4,2,ammo='IS.SRM-6',data=2,ammomode=0x80000000)
    d=doc(u,actions=[cmd('reload','CT 3 N')]);d['repair_economy']['objects'].append(dict(id=200,TECHTIME='36000'))
    yield Case('procedures/reload-unrelated-mode',d).result(ok=False).expect('results.0.error','tired','contains').expect('state.units.u.sections.4.slots.2.ammomode',0x80000004).expect('state.units.u.sections.4.slots.2.data',0).expect('draws',[])
