"""Required R1-R5 boundary neighbors and shared-consumer interactions."""
import itertools,json
from maps_environment_qa import case,check,D,M,F,I,A,V,C
from maps_qa_files import attempt
from maps_qa_operations import E,W,layer,show,event,basic


def build():
    bad=[{'cadence_ticks':0},{'cadence_ticks':True},{'cadence_ticks':1.5},{'snow_low':21},{'snow_high':-1},{'heavy_snow_low':51},{'melt_per_degree':-1},{'emit':1},{'steam':'true'},{'enabled':1},{'conditions':['rain']},{'conditions':'fog'},{'conditions':[None]},{'temperature':-129},{'temperature':128},{'temperature':True},{'temperature':20.0},{'winddir':32768},{'windspeed':-32769},{'windspeed':False},{'unknown':2}]
    for i,value in enumerate(bad):
        basic(f'atomic-weather-{i}',[W(conditions=['precipitation'],temperature=0),A(10),I(),attempt(W(**value)),I()],[check('results.3.error',not_equal=None),check('results.4.maps',same_as='results.2.maps'),check('results.4.events',same_as='results.2.events'),check('draws',[])])
    bad_layers=[{'x':1,'y':0,'layers':['mud'],'data':1},{'x':0,'y':-1,'layers':['mud'],'data':1},{'x':True,'y':0,'layers':['mud'],'data':1},{'x':0,'y':0,'layers':['bog'],'data':1},{'x':0,'y':0,'layers':['mud'],'data':1.1},{'x':0,'y':0,'layers':['mud'],'data':True}]
    for i,value in enumerate(bad_layers):
        basic(f'atomic-layer-{i}',[W(temperature=0),layer(23,('mud',)),I(),attempt(E('layer.set',**value)),I()],[check('results.3.error',not_equal=None),check('results.4.maps',same_as='results.2.maps'),check('results.4.events',same_as='results.2.events'),check('draws',[])])
    for i,(name,values) in enumerate([('layer.set',{}),('snow.grow',{}),('snow.melt',{}),('weather.show',{'cells':[[0]]}),('weather.show',{'cells':[[True,0]]}),('snow.grow',{'low':True,'high':10}),('snow.melt',{'x':0,'y':0,'depth':1,'steam':1})]):
        basic(f'atomic-command-{i}',[W(temperature=0),I(),attempt(E(name,**values)),I()],[check('results.2.error',not_equal=None),check('results.3.maps',same_as='results.1.maps'),check('results.3.events',same_as='results.1.events'),check('draws',[])])
    for data in (-9,0,1,999,1000,1001,9007199254740993):
        for layers in (('snow','mud','rapids'),('snow','deep_snow','mud'),('mud',)):
            normalized=max(0,data) if 'snow' in layers else data
            expected=set(layers)-{'snow','deep_snow'}
            if 'snow' in layers and normalized:expected.add('snow' if normalized<=1000 else 'deep_snow')
            basic(f'normalize-{data}-'+','.join(layers),[layer(data,layers),show((0,0))],[check('results.1.cells.0.data',normalized),check('results.1.cells.0.layers',sorted(expected)),event(None),check('draws',[])])
    for changed,deadline in ((False,60),(True,70)):
        basic(f'cold-switch-{changed}',[W(conditions=['precipitation'],temperature=0),A(10),W(conditions=['heavy_precipitation'] if changed else ['precipitation']),A(50),show((0,0)),A(10),show((0,0))],[check('results.4.cells.0.data',0 if changed else 10),check('results.6.cells.0.data',30 if changed else 10),event(deadline+60)],random={'streams':{'snow_growth':[30 if changed else 10]}})
    for cadence,rate in ((1,0),(7,12),(60,0)):
        basic(f'custom-cadence-{cadence}-{rate}',[W(conditions=['precipitation'],temperature=0,cadence_ticks=cadence,snow_low=rate,snow_high=rate),A(cadence*2),show((0,0))],[check('results.2.cells.0.data',2*rate),event(cadence*3),check('draws',[rate]*2 if rate else [],project='value')],random={'streams':{'snow_growth':[rate]*2}})
    terrain=[{'at':[0,0],'terrain':'BRIDGE','elevation':0},{'at':[0,1],'terrain':'FIRE','elevation':0},{'at':[1,0],'terrain':'WATER','elevation':0},{'at':[1,1],'terrain':'ICE','elevation':0}]
    basic('cold-x-major-exclusions',[W(conditions=['heavy_precipitation'],temperature=0,heavy_snow_low=1,heavy_snow_high=4),A(60)],[check('state.maps.main.snow_validation_trace',[{'x':0,'y':2,'data':1,'layers':['snow']},{'x':1,'y':2,'data':2,'layers':['snow']},{'x':2,'y':0,'data':3,'layers':['snow']},{'x':2,'y':1,'data':4,'layers':['snow']},{'x':2,'y':2,'data':1,'layers':['snow']}]),check('draws',[1,2,3,4,1],project='value')],map={'id':10,'size':[3,3],'hexes':terrain},random={'streams':{'snow_growth':[1,2,3,4,1]}})
    basic('shallow-deep-clock',[layer(990),W(conditions=['precipitation'],temperature=0),A(60),show((0,0)),A(60),show((0,0))],[check('results.3.cells.0.data',1000),check('results.3.cells.0.layers',['snow']),check('results.5.cells.0.data',1020),check('results.5.cells.0.layers',['deep_snow'])],random={'streams':{'snow_growth':[10,20]}})
    for amount in (1,90,91,100,1001):
        draw=amount//20;duration=amount if amount<=90 else 90+draw
        basic(f'warm-removed-{amount}',[layer(amount,('snow','mud')),W(temperature=100,melt_per_degree=100,emit=False),A(60),E('weather.disable'),I(),A(duration-1),I(),A(1),I()],[check('results.4.maps.main.layers.0.data',0),check('results.4.maps.main.layers.0.layers',['mud']),check('results.4.maps.main.objects.0.deadline',60+duration),check('results.6.maps.main.hexes.0.terrain',':'),check('state.maps.main.hexes.0.terrain',' '),event(None)],random={'streams':{'snow_steam':[draw]}})
    for prefix in ('none','precipitation','heavy_precipitation'):
        basic('warm-no-invented-layers-'+prefix,[W(conditions=[] if prefix=='none' else [prefix],temperature=20),A(120)],[check('state.maps.main.layers',[]),check('state.maps.main.hexes.0.terrain',' '),check('draws',[]),event(180)])
    for first in ('weather','smoke'):
        setup=[W(conditions=['precipitation'],temperature=0,cadence_ticks=10,snow_low=1,snow_high=1),M('addsmoke',0,0,10)]
        if first=='smoke':setup.reverse()
        basic('same-tick-order-'+first,setup+[A(10),E('weather.disable'),A(20),show((0,0))],[check('state.event_trace',['WEATHER','DECORATION'] if first=='weather' else ['DECORATION','WEATHER'],where={'phase':'pre','deadline':10},project='kind'),check('results.5.cells.0.data',1),check('state.maps.main.objects',[]),check('draws',[1],project='value')],random={'streams':{'snow_growth':[1]}})
    lifecycle=[('show-and-identical',[show(),W(conditions=['precipitation']),E('weather.enable')],60),('unregister-enable',[M('unregister'),E('weather.disable'),E('weather.enable')],None),('reregister',[M('unregister'),A(10),M('register')],80),('expand',[M('resize',0,0),A(10),M('resize',1,1)],80),('free',[M('free')],None),('setconditions',[M('conditions',100,-1)],70),('conditions-identical',[M('conditions',100,0)],60)]
    for name,actions,deadline in lifecycle:
        basic('lifecycle-'+name,[W(conditions=['precipitation'],temperature=0),A(10)]+actions,[event(deadline),check('state.maps.main.weather.deadline',deadline)])
    basic('zero-area-enable',[M('resize',0,0),W(conditions=['precipitation'],temperature=0),I(),A(10),M('resize',1,1)],[event(None,'results.2.events'),event(70)])
    basic('visibility-wind-shared',[W(winddir=120,windspeed=30,temperature=0),A(25),I(),V(visibility='30 2 180 61 200 retained message'),A(25),I()],[check('results.2.maps.main.winddir',120),check('results.2.maps.main.windspeed',30),event(60,'results.2.events'),check('state.maps.main.weather.effects',['high_winds']),event(110)],config={'periodic_updates':True},random={'streams':{'visibility_change':[10]*4}})
    for group in (0,1,2):
        actions=[D('decoration',0,0,group,'&' if group==0 else ':' if group==1 else '@',90),W(temperature=50),A(60),I(),E('weather.disable')]
        if group==2:actions += [M('delobj','DECO')]
        else:actions += [A(30)]
        basic(f'ice-overlay-rebase-{group}',actions,[check('results.3.maps.main.hexes.0.terrain','~'),check('results.3.maps.main.objects',[126],where={'kind':('FIRE','SMOKE','DECO')[group]},project='datac'),check('state.maps.main.hexes.0.terrain','~'),check('draws',0,where={'name':'snow_steam'},length=True)],map={'id':10,'size':[1,1],'default':['ICE',2]},random={'streams':{'fire_spread':[2]*4,'smoke_duration':[]}})
    # The shared target is independently base5 plus C weather/layer arithmetic.
    for movement,layers,position in itertools.product(('BIPED','HOVER'),((),('deep_snow','mud','rapids')),('ground','above','jumping','removed','disabled')):
        unit={'name':'u','at':[0,0,1 if position=='above' else 0],'movement':movement,'status':72 if position=='jumping' else 8}
        actions=[layer(1001,layers),W(conditions=['heavy_precipitation'],temperature=20)]
        if position=='removed':actions += [D('membership_remove')]
        if position=='disabled':actions += [E('weather.disable')]
        actions += [dict(op='diagnose',kind='MechPilotSkillRoll_BTH',args=[0])]
        modifier=0 if position!='ground' else 1+(4 if layers and movement!='HOVER' else 0)
        basic(f'pilot-shared-{movement}-{len(layers)}-{position}',actions,[check(f'results.{len(actions)-1}',5+modifier)],units=[unit],mode='diagnostic')
    for weather,throw in itertools.product((False,True),(4,5,6)):
        target=5+int(weather);success=throw>=target
        actions=[W(conditions=['heavy_precipitation'] if weather else [],temperature=20),C('stand','check'),C('stand'),I()]
        basic(f'ordinary-stand-boundary-{weather}-{throw}',actions,[check('results.1.message',f'Your BTH to stand would be: {target}'),check('results.2.accepted',success),check('state.units.u.fallen',not success),check('draws',[throw] if success else [throw,12],where={'name':'pilot_rolls'},project='value')],units=[{'name':'u','at':[0,0,0],'fallen':True}],random={'streams':{'pilot_rolls':[throw,12],'rolls':[12],'fall_directions':[1],'hit_location_rolls':[7],'damage_entry':[7]}})
    snapshots()


def snapshots():
    # Mutate only external file bytes, then ask the real loader to validate them.
    invalid=[('version',2),('version',True),('conditions',['unknown']),('layers',['unknown']),('data','+1'),('data','01'),('data','-0'),('data',1),('x',1),('x',True),('width',1001),('remaining',0),('remaining',1.5),('callback','unknown'),('duplicate-event',None),('missing-event',None)]
    for name,value in invalid:
        def fresh(data,path,name=name,value=value):
            saved=json.loads((path/'files/snapshot').read_text());m=saved['maps'][0]
            if name=='version':saved[name]=value
            elif name=='conditions':m['weather'][name]=value
            elif name in ('layers','data','x'):m['weather']['cells'][0][name]=value
            elif name=='width':m[name]=value
            elif name in ('remaining','callback'):saved['events'][0][name]=value
            elif name=='duplicate-event':saved['events']*=2
            else:saved['events']=[]
            (path/'files/invalid').write_text(json.dumps(saved))
            return ({'map':{'id':10,'size':[1,1]},'units':[],'config':{'periodic_updates':False},'random':{'streams':{}},'actions':[W(temperature=0),layer(42,('mud',)),A(10),I(),attempt(E('environment.load',file='invalid')),I()]},[check('results.4.error',not_equal=None),check('results.5.maps',same_as='results.3.maps'),check('results.5.events',same_as='results.3.events'),check('draws',[])])
        basic('invalid-snapshot-'+name+'-'+str(value),[layer(12),W(temperature=0),E('environment.save',file='snapshot',maps=[10])],[event(60)],followup=fresh)
    for direct,text,success in ((False,'1 1\n%3\n',True),(False,'bad\n',False),(True,'1 2\n.0\n',False)):
        operation=F('load_direct','terrain') if direct else M('load','terrain')
        actions=[layer(10),W(temperature=0),A(10),attempt(operation),I(),A(60)]
        checks=[event(None if direct or success else 60,'results.4.events')]
        if success:checks += [check('results.4.maps.main.weather.enabled',False),check('results.4.maps.main.layers',[])]
        elif direct:checks += [check('results.4.maps.main.partial_grid',True),check('results.4.maps.main.layers',[])]
        else:checks += [check('results.4.maps.main.layers.0.data',10),event(120)]
        basic(f'text-reload-{direct}-{success}',actions,checks,files={'terrain':{'text':text}})
    for second in (1,2):
        basic(f'second-open-weather-{second}',[W(temperature=0),A(10),M('load','terrain',player=second,fail_second_open=True),I()],[event(60),check('state.maps.main.weather.enabled',True)],files={'terrain':{'text':'1 1\n.0\n'}})
    from maps_qa_storage import dynamic
    maps=[{'name':'main','id':10,'size':[5,2],'map_objects':[{'kind':'BUILDING','x':4,'y':0,'obj':20}]},{'name':'Depot','id':20,'size':[1,1],'cf':90,'cfmax':100}]
    units=[{'name':'u','id':40,'at':[4,1,0]},{'name':'v','id':41,'map':'Depot','at':[0,0,0]}]
    def fresh(data,path):
        saved=json.loads((path/'files/snapshot').read_text())
        assert [(e['callback'],e['remaining']) for e in saved['events']]==[('weather',50),('spread_fire',50),('regen',110)]
        assert bytes.fromhex(saved['maps'][0]['dynamic'])==dynamic([40,-1],[5,6],[[11,12],[13,14]])
        return ({'maps':maps,'units':units,'config':{'periodic_updates':False},'random':{'streams':{'snow_growth':[1]*18,'fire_spread':[2]*4,'smoke_duration':[90]}},'actions':[A(100),E('environment.load',file='snapshot'),I(),D('bits','query',4,0,1),D('bits','query',4,0,2),A(110),I()]},[check('results.2.maps.main.objects',[2,3],where={'kind':'SMOKE'},project='x'),check('results.2.maps.main.slot_flags',[5,6]),check('results.2.maps.main.slot_los',[[11,12],[13,14]]),check('results.2.units.u.mapindex',10),check('results.2.units.v.mapindex',20),check('results.3',1),check('results.4',2),event(150,'results.2.events'),check('results.2.events',[210],where={'kind':'BREGEN'},project='deadline'),check('state.maps.Depot.cf',91),check('state.maps.main.objects',[],where={'kind':'FIRE'}),check('draws',[1]*18,where={'name':'snow_growth'},project='value')])
    basic('snapshot-maps-CF-bits-roster',[W(conditions=['precipitation'],temperature=0,snow_low=1,snow_high=1),M('addfire',0,0,120),M('addsmoke',2,0,0),M('addsmoke',3,0,0),D('bits','set',4,0,1),D('bits','set',4,0,2),D('start_regen',map='Depot'),F('load_dynamic',count=2),A(10),I(),E('environment.save',file='snapshot',maps=[10,20]),I()],[check('results.11.maps',same_as='results.9.maps'),check('results.11.events',same_as='results.9.events')],maps=maps,map=None,units=units,files={'record':{'hex':dynamic([40,-1],[5,6],[[11,12],[13,14]]).hex()}},followup=fresh,random={'streams':{'sensor.detect':[1]*8}})
