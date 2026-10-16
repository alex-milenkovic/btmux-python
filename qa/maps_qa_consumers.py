"""Independent downstream and combined persistence procedures from source C."""
import itertools
from maps_environment_qa import case,check,D,M,F,I,A,V,C
from maps_qa_extra import X
from maps_qa_storage import dynamic
from maps_qa_buildings import maps as buildings


def build():
    for movement,layers,raw in itertools.product(('BIPED','HOVER'),range(8),range(16)):
        names=[n for i,n in enumerate(('deep_snow','mud','rapids')) if layers>>i&1]
        effects={n:int(bool(raw>>i&1)) for i,n in enumerate(('heavy_rain','heavy_snow','high_winds','blizzard'))}
        expected=int(bool(raw))+(0 if movement=='HOVER' else bool(layers&1)+bool(layers&2)+2*bool(layers&4))
        case('weather',f'pilot-layer-or-{movement}-{layers}-{raw}',[D('pilot_weather',effects)],
             [check('results.0',expected)],map={'layers':[{'at':[1,1],'layers':names,'data':1001}]},
             units=[{'name':'u','at':[1,1,0],'movement':movement}])
    for movement,loc in itertools.product(('BIPED','QUAD'),(0,6)):
        # DestroyParts leg handling cancels stand even with no attacker; biped arm returns first.
        case('conditions',f'stand-cancel-{movement}-{loc}',[C('stand'),I(),X('destroy-parts',section=loc),I()],
             [check('results.0.accepted',True),check('results.1.events',1,where={'kind':'STAND'},length=True),check('state.events',int(movement=='BIPED' and loc==0),where={'kind':'STAND'},length=True)],
             units=[{'name':'u','status':136,'movement':movement}],random={'streams':{'pilot_rolls':[12]}})
    for double,count in itertools.product((False,True),(1,2,3,4)):
        slots=[{'index':i,'special':'HEAT_SINK'} for i in range(count)]
        case('conditions',f'sink-loss-{double}-{count}',[X('destroy-parts',section=2)],
             [check('state.units.u.sink_capacity',(20 if double else 10)-count+(count//3 if double else 0)),check('state.units.u.num_sinks',10-(count-(count//3 if double else 0))/(2 if double else 1))],
             units=[{'name':'u','num_sinks':10,'specials':8 if double else 0,'sections':[{'index':2,'slots':slots}]}])
    for initial in (0,5,10,15):
        case('conditions',f'engine-heat-{initial}',[X('destroy-parts',section=2)],
             [check('state.units.u.engine_heat',min(15,initial+5)),check('state.units.u.destroyed',initial==10)],
             config={'periodic_updates':False,'stackpole':0},units=[{'name':'u','engine_heat':initial,'sections':[{'index':2,'slots':[{'index':0,'special':'ENGINE'}]}]}])
    case('conditions','last-jet-actual-fall',[X('destroy-parts',section=2,attacker='u')],
         [check('state.units.u.jump_speed',0),check('state.units.u.messages',contains='Losing your last Jump Jet you fall from the sky!!!!!')],
         units=[{'name':'u','at':[3,3,2],'status':64,'jump_speed':1,'jump_mp':4,'sections':[{'index':2,'slots':[{'index':0,'special':'JUMP_JET'}]}]}],random={'seed':5489})
    for underground in (False,True):
        def reactor(data,path,underground=underground):
            u=data['state']['units']['u']
            for loc in (4,2,3,6,5,7):assert u['sections'][loc]['internal']==0
            assert u['at'][2]==0
            requests=u['external_effects']
            assert bool([r for r in requests if 'eject' in str(r).lower()]) != underground
        case('conditions',f'reactor-local-{underground}',[X('reactor-explosion',attacker='u')],
             [check('state.units.u.destroyed',True)],checker=reactor,map={'flags':16 if underground else 0},
             units=[{'name':'u','at':[4,4,0],'in_character':True}],random={'seed':5489},mode='blocked')
    for tower,operation in itertools.product((False,True),('add','remove')):
        units=[{'name':'u','id':40,'status':16384}]
        if tower:units.append({'name':'v','id':41,'carrying':40})
        status=dict(op='configure',values={'status':16384})
        actions=[status,D('membership_remove')] if operation=='remove' else [F('load_dynamic',count=int(tower)),status,D('membership_add')]
        case('dynamic',f'tow-{operation}-{tower}',actions,
             [check('state.units.u.status',0 if tower== (operation=='remove') else 16384,mask=16384)],units=units,
             files={'record':{'hex':dynamic([41] if tower else []).hex()}})
    # A real ordinary step reaches the BUILD bit query installed by link update.
    boards=buildings()
    case('buildings','ordinary-step-visible',[M('updatelinks'),C('speed',32),A(30)],
         [check('state.units.u.messages',contains='The Depot has CF of 100.')],
         maps=boards,attributes={'10':{'BUILDLINKS':'20'},'20':{'BUILDCOORD':'2,2','BUILDENTRANCE':'0 0 0 0'}},units=[{'name':'u','at':[2,3,0]}],mode='ordinary')
    # Combined live fire + damaged BUILD + moved roster: actual files, then a fresh process.
    attributes={'10':{'BUILDLINKS':'20'},'20':{'BUILDCOORD':'2,2','BUILDENTRANCE':'0 0 0 0'}}
    maps=[{'name':'main','id':10,'size':[9,9]}, {'name':'child','id':20,'size':[9,9],'cf':100,'cfmax':100}]
    def reload(data,path,maps=maps):
        for name in ('grid','objects','roster'):assert (path/'files'/name).stat().st_size>0
        doc={'maps':maps,'units':[{'name':'u','id':40,'map':'child'}], 'config':{'periodic_updates':False},
             'actions':[M('load','grid'),F('load_objects','objects'),F('load_dynamic','roster',count=0),A(120)]}
        checks=[check('state.maps.main.roster_ids',[]),check('state.maps.child.roster_ids',[40]),
                check('state.maps.main.objects',1,where={'kind':'BUILDING'},length=True),
                check('state.maps.main.objects',1,where={'kind':'FIRE'},length=True),
                check('state.events',[],where={'kind':'DECORATION'})]
        return doc,checks
    case('integration','combined-two-map-persistence',[M('updatelinks'),M('addfire',4,4,120),D('hit_building',2,2,-999,10),M('transfer','u',map='child'),M('save','grid'),F('save_objects','objects'),F('save_dynamic','roster'),A(120)],
         [check('state.maps.child.cf',91),check('state.maps.main.objects',0,where={'kind':'FIRE'},length=True),check('state.maps.child.roster_ids',[40])],
         maps=maps,attributes=attributes,units=[{'name':'u','id':40,'at':[2,5,0]}],followup=reload,
         random={'streams':{'fire_spread':[2]*4,'smoke_duration':[90]*4,'fire_dissipation':[3],'map_contact_id':[0,0]}},mode='ordinary')

    for name,actions in (('text',[M('save','record')]),('dynamic',[F('save_dynamic')]),('objects-bits',[D('bits','set',1,1,1),F('save_objects')])):
        case('files','actual-short-write-'+name,actions,[],units=[{'name':'u'}],write_limit=8,error='Unable to open' if name=='text' else 'File too large')
    kinds=('FIRE','SMOKE','DECO','MINE','BUILDING','LEAVE','ENTRA','LINKED','TBITS','BLZ')
    for kind in kinds:
        actions=[D('bits','set',1,1,1)] if kind=='TBITS' else [dict(op='map_object',value=dict(kind=kind,x=1,y=1,obj=99,datac=1,datas=7,datai=11))]
        case('objects','all-types-list-'+kind,actions+[M('list','OBJS'),F('save_objects')],
             [check('state.maps.main.objects',1,where={'kind':kind},length=True),check('results.1',contains='--- MAP/HANGAR INFORMATION OBJECT ---')] if kind=='TBITS' else
             [check('state.maps.main.objects',1,where={'kind':kind,'obj':99,'datac':1,'datas':7,'datai':11},length=True)],
             map={'size':[9,9]})
    for before,after in ((0,30),(30,0),(60,-20),(-20,60)):
        first=max(20,60-before);speed=max(20,60-after);duration=300
        next_tick=first+(speed if duration-speed>speed else max(1,duration-speed))
        case('decorations',f'wind-change-{before}-{after}',[M('addfire',4,4,duration),V(windspeed=after),A(first)],
             [check('state.maps.main.objects',[next_tick],where={'kind':'FIRE'},project='deadline'),check('state.maps.main.objects',[duration-speed],where={'kind':'FIRE'},project='datas'),check('draws',0,where={'name':'fire_wind'},length=True)],
             map={'size':[9,9],'windspeed':before},random={'streams':{'fire_spread':[2]*4,'smoke_duration':[90]*4}})
    case('weather','pilot-null-map',[D('membership_remove'),D('pilot_weather',{'heavy_rain':1})],[check('results.1',0)],units=[{'name':'u'}])
    # Debug-fix metadata branches use actual registered units and independent wire IDs.
    records={'40':{'unit':'u','location':1000,'hardcode':True,'type':'MECH'},'41':{'type':'OTHER'},'42':{'type':'MECH'},'43':{'unit':'v','type':'MECH'},'44':{'unit':'w','type':'MECH'}}
    wire=dynamic([41,42,43,44],[8]*4,[[1]*4 for _ in range(4)])
    case('management','debug-fix-all-roster-branches',[F('load_dynamic',count=4),D('membership_state',{'mapindex':20},unit='v'),D('membership_state',{'mapnumber':99},unit='w'),D('debug_fix',records)],
         [check('state.maps.main.roster_ids',[-1,-1,-1,44]),check('state.units.u.mapindex',-1),check('state.maps.main.messages',contains="Error: #41 isn't mech yet is in mapindex. Fixing.."),check('state.maps.main.messages',contains='Error: #42 has no mech data. Removing..'),check('state.maps.main.messages',contains="Error: #43 isn't really here! Removing.."),check('state.maps.main.messages',contains='Error: #44 has invalid mapnumber (mn:99 <-> real:3)..')],
         units=[{'name':'u','id':40},{'name':'v','id':43},{'name':'w','id':44}],files={'record':{'hex':wire.hex()}},mode='diagnostic')
    # Exact Combat B5 producer with the formerly missing local BUILD target supplied.
    maps=[{'name':'main','id':10,'size':[9,9],'hexes':[{'at':[3,1],'terrain':'BUILDING','elevation':0}],
           'map_objects':[{'kind':'BUILDING','x':3,'y':1,'obj':20}]}, {'name':'Depot','id':20,'size':[9,9],'cf':100,'cfmax':100}]
    case('integration','prior-combat-B5-resolved',[C('lock',3,1,'B'),C('fire',0)],
         [check('results.1.accepted',True),check('state.maps.Depot.cf',95),check('state.units.u.external_effects',0,where={'service':'hit_building / persistent building objects'},length=True)],
         maps=maps,units=[{'name':'u','at':[3,3,0],'weapons':['IS.AC/5'],'ammo':[{'weapon':'IS.AC/5','rounds':20}]}],random={'streams':{'attack_rolls':[12],'failure_weapon_chance':[4]}},mode='ordinary')
    maps[0]['map_objects'][0]['y']=2;maps[0]['hexes'][0]['at']=[3,2]
    maps[0]['mines']=[{'x':3,'y':2,'type':'STANDARD','strength':4}]
    case('integration','prior-combat-scan-H-resolved',[C('scan',3,2,'H')],
         [check('results.0.building_cf',100),check('results.0.mines_found',1),check('state.units.u.messages',contains="The Depot's CF is 100.")],
         maps=maps,units=[{'name':'u','at':[3,3,0],'in_character':True,'pilot_details':{'perception':2}}],random={'streams':{'mine_discovery':[9],'perception_rolls':[12]}},mode='ordinary')
    for movement,loc,ood in itertools.product(('BIPED','QUAD'),(0,6),(False,True)):
        falls=not ood and (movement=='QUAD' or loc==6)
        case('conditions',f'limb-fall-OOD-{movement}-{loc}-{ood}',[X('destroy-parts',section=loc,attacker='u')],
             [check('state.units.u.fallen',falls)],
             units=[{'name':'u','cocoon':10 if ood else 0,'movement':movement}],
             random={'streams':{'rolls':[12],'pilot_rolls':[12],'fall_directions':[1],'hit_location_rolls':[7],'damage_entry':[7]}})
    for x,y,radius,inside in ((2,2,0,True),(2,3,0,False),(2,3,1,True),(2,4,1,False),(2,4,2,True),(4,2,1,False),(4,2,2,True),(4,4,2,False),(4,4,3,True)):
        for team in (0,1,2):
            case('links',f'cartesian-BLZ-{x}-{y}-{radius}-{team}',[M('block',2,2,radius,team),D('blocked_lz',x,y)],
                 [check('results.1',inside and team!=2)],units=[{'name':'u','team':2}])
    case('links','ordinary-aerospace-landing-unavailable',[M('block',3,3,2),C('land')],
         [],error='unsupported command: land',
         units=[{'name':'u','class':'AERO','at':[3,3,1]}],mode='blocked')
