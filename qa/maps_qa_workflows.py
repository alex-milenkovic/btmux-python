"""Ordinary map/environment producer workflows; external requests remain separate."""
from maps_environment_qa import case,examples,check,D,M,F,I,A,V,C
from maps_qa_buildings import maps as building_maps
from maps_qa_files import hexcheck
from maps_qa_storage import dynamic


def build():
    # Exact feature identities are tied to independent, expanded procedure scripts.
    labels=[r['workflow'] for r in examples('integration',1)]
    def workflow(label,actions,checks,**kw):
        case('integration',f'example-01-{labels.index(label)}',actions,checks,mode='ordinary',**kw)
    wire='3 2\n%3~2.0\n.0.0.0\n2: 75 -20\n'
    def reload(data,path):
        assert (path/'files/terrain').read_bytes()==wire.encode()
        return ({'map':{'size':[1,1]},'units':[],'actions':[M('load','terrain')],'config':{'periodic_updates':False}},
                [check('state.maps.main.name','terrain'),check('state.maps.main.size',[3,2]),check('state.maps.main.grav',75),check('state.maps.main.temp',-20),check('state.maps.main.flags',2),check('state.maps.main.hexes',[{'at':[x,y],'terrain':'%' if(x,y)==(0,0) else '~' if(x,y)==(1,0) else ' ','elevation':3 if(x,y)==(0,0) else 2 if(x,y)==(1,0) else 0,'underlying':'%' if(x,y)==(0,0) else '~' if(x,y)==(1,0) else ' '} for y in range(2) for x in range(3)])])
    workflow('map-text-reload',[M('resize',3,2),M('addhex',0,0,'%',3),M('addhex',1,0,'~',2),M('conditions',75,-20),M('save','terrain')],
             [check('state.files.terrain.text',wire)],followup=reload)
    # Move A out, fill its interior slot with C; diagnose the source duplicate-add guard.
    boards=[{'name':'main','id':10,'size':[9,9]},{'name':'inside','id':20,'size':[9,9],'flags':6,'grav':120,'temp':-40}]
    crew=[{'name':'a','id':40},{'name':'b','id':41,'at':[4,3,0]},{'name':'c','id':42,'map':'inside'}]
    def membership_reload(data,path):
        assert (path/'files/record').read_bytes()==dynamic([42,41],[1,0],[[0,0],[0,0]])
        return ({'maps':[{'name':'main','id':10,'size':[9,9]}],'units':[{'name':'c','id':42},{'name':'b','id':41}],
                 'config':{'periodic_updates':False},'actions':[F('load_dynamic',count=2)]},
                [check('state.maps.main.roster_ids',[42,41]),check('state.maps.main.slot_flags',[1,0]),check('state.maps.main.slot_los',[[0,0],[0,0]]),check('state.units.c.mapindex',10),check('state.units.c.mapnumber',0),check('state.units.b.mapindex',10),check('state.units.b.mapnumber',1)])
    workflow('membership-transfer',[M('transfer','a',map='inside'),I(),M('transfer','c',map='main'),I(),D('membership_add',unit='c'),I(),F('save_dynamic')],
             [check('results.5.units.c',same_as='results.3.units.c'),check('results.5.maps.main',same_as='results.3.maps.main'),check('results.1.maps.main.roster_ids',[-1,41]),check('results.3.maps.main.roster_ids',[42,41]),check('state.maps.main.roster_ids',[42,41]),check('state.units.c.mapnumber',0),check('state.units.a.mapindex',20),check('state.units.a.status',0x78000000,mask=0x78000000)],maps=boards,units=crew,followup=membership_reload)
    streams={'attack_rolls':[12],'failure_weapon_chance':[4],'terrain_rolls':[12,12],'fire_duration':[120],
             'fire_spread':[9,11,11,12],'fire_wind':[1]*4,'smoke_duration':[90,100,120,150],'fire_dissipation':[3],
             'sensor.detect':[1]*4}
    # The observer-to-target ray crosses smoke at (4,2)/(4,3), but not the fire
    # except at its endpoint. C mech.los.c excludes endpoint FIRE/SMOKE flags.
    scan=C('scan',4,4,unit='w')
    workflow('weapon-forest-fire',[scan,C('lock',4,4,'I'),C('fire',0),I(),scan,A(59),I(),A(1),I(),scan,A(59),I(),A(1),I(),A(90),scan],
             [check('results.0.accepted',True),check('results.2.accepted',True),check('results.3.maps.main.objects.0.deadline',60),check('results.3.units.v.cached_terrain','&'),check('results.4.accepted',True),check('results.6.maps.main.objects',1,where={'kind':'FIRE'},length=True),check('results.8.maps.main.objects',4,where={'kind':'SMOKE'},length=True),check('results.9.accepted',False),check('results.9.text','Coordinates are not in line of sight!'),check('results.11.maps.main.hexes',['&'],where={'at':[4,4]},project='terrain'),check('results.13.maps.main.hexes',['%'],where={'at':[4,4]},project='terrain'),check('results.13.units.v.cached_terrain','%'),check('state.maps.main.objects',[]),check('results.15.accepted',True),check('draws',4,where={'name':'fire_spread'},length=True),check('draws',4,where={'name':'fire_wind'},length=True)],
             map={'size':[12,12],'hexes':[{'at':[4,4],'terrain':'LIGHT_FOREST','elevation':0}]},units=[{'name':'u','at':[4,6,0],'weapons':['IS.Flamer']},{'name':'v','id':41,'at':[4,4,0]},{'name':'w','id':42,'at':[4,1,0]}],random={'streams':streams})
    def smoke_before_fire(data,path):
        names=[draw['name'] for draw in data['draws']]
        assert names[-5:]==['smoke_duration']*4+['fire_duration']
    case('integration','ordinary-wind30-forest-spread',[C('lock',4,4,'I'),C('fire',0),I(),A(29),I(),A(1),I()],
         [check('results.1.accepted',True),check('results.2.maps.main.objects.0.deadline',30),check('results.4.maps.main.objects',1,where={'kind':'FIRE'},length=True),check('state.maps.main.objects',2,where={'kind':'FIRE'},length=True),check('state.maps.main.objects',3,where={'kind':'SMOKE'},length=True),check('state.maps.main.objects',[96],where={'kind':'FIRE','x':4,'y':3},project='datac'),check('state.maps.main.objects',[60],where={'kind':'FIRE','x':4,'y':3},project='deadline'),check('draws',[30],where={'name':'fire_wind'},project='value')],
         mode='ordinary',checker=smoke_before_fire,map={'size':[12,12],'windspeed':30,'hexes':[{'at':[4,4],'terrain':'LIGHT_FOREST','elevation':0},{'at':[4,3],'terrain':'LIGHT_FOREST','elevation':0}]},units=[{'name':'u','at':[4,6,0],'weapons':['IS.Flamer']}],random={'streams':{'attack_rolls':[12],'failure_weapon_chance':[4],'terrain_rolls':[12,12],'fire_duration':[120,60],'fire_spread':[9,2,2,2],'fire_wind':[30],'smoke_duration':[90]*4}})
    workflow('building-hit-repair',[C('lock',2,2,'B'),C('fire',0),C('scan',2,2,'B'),I(),A(119),I(),A(1),I(),A(1079),I(),A(1),I()],
             [check('results.1.accepted',True),check('results.2.building_cf',90),check('results.3.maps.Depot.cf',90),check('results.3.events',[120],where={'kind':'BREGEN'},project='deadline'),check('results.5.maps.Depot.cf',90),check('results.7.maps.Depot.cf',91),check('results.9.maps.Depot.cf',99),check('state.maps.Depot.cf',100),check('state.events',[],where={'kind':'BREGEN'}),check('results.3.units.u.weap_heat',10),check('results.3.units.u.weapons.0.recycle',60),check('state.units.u.messages',contains='You hit the Depot for 10 points of damage.')],
             maps=building_maps(),units=[{'name':'u','id':40,'at':[2,5,0],'weapons':['IS.PPC']}],random={'streams':{'attack_rolls':[12],'failure_weapon_chance':[4]}})
    workflow('building-destroy',[C('lock',2,2,'B'),C('fire',0),I(),A(7200),I()],
             [check('results.1.accepted',True),check('results.2.maps.Depot.cf',0),check('state.maps.Depot.cf',0),check('state.events',[],where={'kind':'BREGEN'}),check('state.events',[],where={'kind':'BREBUILD'}),check('state.units.u.messages',contains='You hit the Depot for 10 points of damage, destroying it!')],
             maps=building_maps(10),units=[{'name':'u','id':40,'at':[2,5,0],'weapons':['IS.AC/20'],'ammo':[{'weapon':'IS.AC/20','rounds':5}]}],random={'streams':{'attack_rolls':[12],'failure_weapon_chance':[4]}})
    maps=[{'name':'main','id':10,'size':[9,9]},{'name':'child','id':20,'size':[9,9],'cf':100,'cfmax':100},{'name':'grandchild','id':30,'size':[9,9],'cf':100,'cfmax':100}]
    attributes={'10':{'BUILDLINKS':'20'},'20':{'BUILDCOORD':'2,2','BUILDENTRANCE':'0 0 0 0','BUILDLINKS':'30'},'30':{'BUILDCOORD':'3,3','BUILDENTRANCE':'0 0 0 0'}}
    workflow('hangar-links',[M('updatelinks'),I(),M('leave','u',map='child'),I()],
             [check('results.0',[2,2,8]),check('results.1.maps.child.onmap',10),check('results.1.maps.grandchild.onmap',20),check('state.units.u.mapindex',10),check('state.units.u.at',[2,2,0]),check('state.maps.child.roster_ids',[]),check('state.units.u.messages',contains='You have left the child.')],
             maps=maps,attributes=attributes,units=[{'name':'u','id':40,'map':'child','at':[4,0,0],'in_character':False}])
    # Incoming damage reaches breach and shared repair; a real weapon mount supplies mirror/readout state.
    u={'name':'u','id':40,'at':[3,3,0],'sections':[{'index':0,'armor':100,'armor_orig':100,'internal':10}],
       'weapons':[{'name':'IS.MediumLaser','section':0,'critical':4}]}
    v={'name':'v','id':41,'at':[3,2,0],'team':2}
    workflow('conditions-breach',[M('conditions',100,20),M('conditions',100,20,1),C('damage-section','LA',1,0,0),I(),C('fire',0,'01'),C('repair','LA',4),C('weaponstatus'),I(),C('fire',0,'01'),I(),M('conditions',99,20),C('damage-section','RA',1,0,0),I()],
             [check('results.3.units.u.sections.0.config',4,mask=4),check('results.4.accepted',False),check('results.5.accepted',True),check('results.7.units.u.sections.0.slots.4.firemode',0,mask=2),check('results.8.accepted',True),check('state.units.u.sections.1.config',0,mask=4),check('draws',3,where={'name':'breach_rolls'},length=True)],
             units=[u,v],random={'streams':{'damage_entry':[7,7,7],'breach_rolls':[10,10,10],'attack_rolls':[12],'failure_weapon_chance':[4],'hit_location_rolls':[7],'tow_rolls':[7]}})
    services=[r['service'] for r in examples('integration',2)]
    def boundary(service,actions,checks,**kw):case('integration',f'example-02-{services.index(service)}',actions,checks,mode='blocked',**kw)
    boundary('occupant-enumeration',[D('hit_building',2,2,-999,10)],[check('state.units.u.external_effects',1,where={'service':'occupant-enumeration','applied':False},length=True)],maps=building_maps(),units=[{'name':'u'}])
    boundary('AUTO-gameplay',[{'op':'clock','name':'heartbeat'}],[check('state.objects.auto.external_effects',[False]*3,project='applied')],objects=[{'name':'auto','id':42,'type':'AUTO','mymech':'u'}],units=[{'name':'u'}])
    boundary('MUX-teleport',[M('updatelinks'),M('leave','u',map='child')],[check('state.units.u.mapindex',10),check('state.units.u.external_effects',1,where={'operation':'loud_teleport','applied':False},length=True)],maps=maps,attributes=attributes,units=[{'name':'u','id':40,'map':'child','in_character':False}])
    # Existing ordinary movement crosses a trigger mine; its MUX script effect is unavailable.
    boundary('mine-trigger-script',[C('speed',64),A(30)],[check('state.units.u.external_effects',1,where={'service':'SendTrigger / did_it / AMINETRIGGER','applied':False},length=True)],
             map={'size':[9,9],'mines':[{'x':3,'y':2,'type':'TRIGGER','strength':5,'extra':1,'creator':40}]},units=[{'name':'u','at':[3,3,0],'max_speed':100}],random={'seed':5489})
