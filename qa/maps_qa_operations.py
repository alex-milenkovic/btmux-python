"""Independent public-control verification of approved B1/B2 and R1-R5.

Numeric expectations come from map.weather.c, mech.ice.c and the approved
reconstruction. This module imports QA helpers only and drives real CLI processes.
"""
import json,struct
from maps_environment_qa import case,examples,check,D,M,F,I,A,V,C
from maps_qa_files import attempt
from maps_qa_storage import dynamic


def E(name,map=None,**values):
    action=dict(op='map_command',name=name,args=values)
    if map is not None:action['map']=map
    return action

def layer(data,layers=('snow',),x=0,y=0):return E('layer.set',x=x,y=y,layers=list(layers),data=data)
def W(**values):return E('weather.set',**values)
def show(*cells):return E('weather.show',cells=[list(p) for p in cells])
def event(deadline,path='state.events'):
    return check(path,[] if deadline is None else [deadline],where={'kind':'WEATHER'},project='deadline')
def basic(name,actions,checks,**kwargs):
    kwargs.setdefault('map',{'id':10,'size':[1,1]})
    kwargs.setdefault('random',{'streams':{}})
    case('weather_operations',name,actions,checks,mode=kwargs.pop('mode','ordinary'),**kwargs)
def row(n,i,actions,checks,**kwargs):basic(f'example-{n:02d}-{i}',actions,checks,**kwargs)
def build():
    for i,r in enumerate(examples('bits',4)):
        width=int(r['width']);x=width-1;b=int(r['mine'])+int(r['hangar'])
        values=[0]*int(r['bytes']);values[int(r['index'])]=b
        wire=b'\x1b\x09'+struct.pack('<Q',1)+bytes(values)+b'\0\x27'
        def reload(data,path,width=width,x=x,r=r,wire=wire):
            assert (path/'files/record').read_bytes()==wire
            return ({'map':{'size':[1,1]},'units':[],'config':{'periodic_updates':False},'actions':[M('resize',width,1),F('load_objects'),D('bits','query',x,0,1),D('bits','query',x,0,2),D('bits','size')]},
                    [check('results.2',int(r['mine'])),check('results.3',int(r['hangar'])),check('results.4',int(r['bytes'])),check('state.map.mine_hexes',[[x,0]])])
        case('bits',f'example-04-{i}',[M('resize',width,1),D('bits','set',x,0,1),D('bits','set',x,0,2),F('save_objects')],[check('state.files.record.hex',wire.hex())],map={'size':[1,1]},followup=reload)
    for i,r in enumerate(examples('bits',5)):
        actions=[D('bits','set',4,0,1),I()];checks=[]
        if r['sequence']=='truncated-load':actions += [attempt(F('load_objects')),D('bits','query',4,0,1)];checks=[check('results.2.error',contains='read-error'),check('results.3',1)]
        elif r['sequence']=='set-column-5':actions += [attempt(D('bits','set',5,0,1)),D('bits','query',4,0,1)];checks=[check('results.2.error',contains='out of range'),check('results.3',1)]
        else:
            if r['sequence'].startswith('clear-all'):actions += [D('bits','clear',0)]
            if r['sequence'].startswith('delete-TBITS'):actions += [M('delobj','TBITS')]
            actions += [attempt(M('resize',9,9))]
            ok=r['sequence'].startswith('delete-TBITS')
            checks=[check('state.maps.main.size',[9,9] if ok else [5,1]),check(f'results.{len(actions)-1}.error',None) if ok else check(f'results.{len(actions)-1}.error',contains='Invalid map')]
        case('bits',f'example-05-{i}',actions,checks,map={'size':[5,1]},files={'record':{'hex':'1b090100000000000000'}})
    for i,r in enumerate(examples('weather_operations',1)):
        weapon='IS.AC/5' if r['weapon']=='TAMMO' else 'IS.MediumLaser'
        gun,pilot,minus=(int(r[k]) for k in ('gun','pilot','minus'))
        maps=[{'name':'main','id':10,'size':[9,9],'map_objects':[{'kind':'BUILDING','x':2,'y':2,'obj':20}]},{'name':'Depot','id':20,'size':[9,9],'cf':100,'cfmax':100}]
        units=[{'name':'u','id':40,'at':[2,5,0],'weapons':[weapon],'ammo':[{'weapon':weapon,'rounds':20}] if r['weapon']=='TAMMO' else [],'heat_state':{'num_sinks':10}}, {'name':'pilot','id':41,'at':[6,6,0],'fallen':True}]
        actions=[C('lock',2,2,'B'),C('sight',0),I(),W(conditions=[] if r['conditions']=='none' else r['conditions'].split(','),temperature=int(r['temperature']),windspeed=int(r['wind'])),C('sight',0),I(),C('fire',0),I(),C('stand','check',unit='pilot'),C('stand',unit='pilot'),A(2),I()]
        def gameplay(data,path,gun=gun,pilot=pilot):
            results=data['results'];baseline=results[1]['attack']['bth_breakdown'];sight=results[4]['attack']['bth_breakdown'];shot=results[6]['attack']['bth_breakdown']
            assert sight==shot
            assert sight['weather_mod']==gun and sight['total']==baseline['total']+gun
            before=results[2]['units']['u'];after=results[5]['units']['u']
            for key in ('weap_heat','weapons'):assert before[key]==after[key]
            assert results[2]['maps']['Depot']['cf']==results[5]['maps']['Depot']['cf']==100
            assert [x['value'] for x in data['draws'] if x['name']=='attack_rolls']==[12,12,12]
            assert results[8]['accepted'] and results[9]['accepted']
            assert results[8]['message']==f'Your BTH to stand would be: {5+pilot}'
        row(1,i,actions,[check('results.6.accepted',True),check('results.7.maps.Depot.cf',95),check('state.units.u.minus_heat',minus)],maps=maps,map=None,units=units,checker=gameplay,config={'periodic_updates':True,'lock_tick':0},random={'streams':{'attack_rolls':[12]*3,'failure_weapon_chance':[4],'pilot_rolls':[12]*3,'sensor.detect':[1]*10,'visibility_change':[10]*10}})
    for i,r in enumerate(examples('weather_operations',2)):
        names=[] if r['conditions']=='none' else [r['conditions']];depth=int(r['depth'])
        draws=[] if r['draws']=='none' else list(map(int,r['draws'].split(',')))
        row(2,i,[W(conditions=names,temperature=0),A(int(r['tick'])),show((0,0))],[check('results.2.cells.0.data',depth),check('results.2.cells.0.layers',[] if not depth else ['snow']),event(int(r['deadline']))],random={'streams':{'snow_growth':draws}})
    for i,r in enumerate(examples('weather_operations',3)):
        deadline=None if r['deadline']=='none' else int(r['deadline'])
        row(3,i,[layer(500),W(temperature=int(r['temperature']),steam=r['steam']=='true'),A(60),show((0,0))],[check('results.3.cells.0.data',int(r['depth'])),check('state.maps.main.objects',[] if deadline is None else [deadline],where={'kind':'SMOKE'},project='deadline'),check('draws',int(r['usage']=='used'),where={'name':'snow_steam'},length=True),event(120)],random={'streams':{'snow_steam':[int(r['draw'])]}})
    for i,r in enumerate(examples('weather_operations',4)):
        sequence=r['sequence'];actions=[W(conditions=['precipitation'],temperature=0)]
        if sequence.startswith('set-mine'):actions += [A(5),D('bits','set',4,0,1),A(5)]
        else:actions += [A(10)]
        commands={'identical-set-at-10':[W(conditions=['precipitation'])],'heavy-set-at-10':[W(conditions=['heavy_precipitation'])],'cadence-10-at-10':[W(cadence_ticks=10)],'disable-at-10':[E('weather.disable')],'disable-at-10,enable-at-20':[E('weather.disable'),A(10),E('weather.enable')],'reset-at-10':[E('weather.reset')],'clear-mechs-at-10':[M('clear')],'remove-map-at-10':[M('unregister')],'resize-9x9-at-10':[M('resize',9,9)],'resize-0x0-at-10':[M('resize',0,0)],'set-mine-at-5,resize-9x9-at-10':[attempt(M('resize',9,9))],'invalid-cadence-0-at-10':[attempt(W(cadence_ticks=0))]}
        actions+=commands[sequence];deadline=None if r['deadline']=='none' else int(r['deadline'])
        row(4,i,actions,[event(deadline),check('state.maps.main.weather.deadline',deadline)],map={'id':10,'size':[5,1]})
    for i,r in enumerate(examples('weather_operations',6)):
        destroyed=r['consequence']=='fall-and-flood-destruction'
        row(6,i,[W(temperature=1),A(60)],[check('state.maps.main.hexes.0.terrain','~'),check('state.maps.main.hexes.0.elevation',int(r['elevation'])),check('state.units.u.destroyed',destroyed),check('state.units.u.cached_terrain','~'),check('state.maps.main.objects',[]),check('draws',0,where={'name':'snow_steam'},length=True)],map={'id':10,'size':[1,1],'default':['ICE',int(r['elevation'])]},units=[{'name':'u','id':40,'class':'VEH_GROUND','movement':'TRACK' if r['move']=='tracked' else 'HOVER','at':[0,0,int(r['altitude'])]}],random={'streams':{'pilot_rolls':[12],'rolls':[12],'fall_directions':[1],'hit_location_rolls':[7],'damage_entry':[7]}})
    for i,r in enumerate(examples('weather_operations',7)):
        row(7,i,[layer(int(r['before']),('snow','mud')),E('snow.grow',low=int(r['bound']),high=int(r['bound'])),show((0,0))],[check('results.2.cells.0.data',int(r['after'])),check('results.2.cells.0.layers',sorted(r['layers'].split(','))),check('draws',[int(r['draw'])],where={'name':'snow_growth'},project='value')],random={'streams':{'snow_growth':[int(r['draw'])]}})
    persistence()
    from maps_qa_operation_edges import build as edges
    edges()
    from maps_qa_operation_consumers import build as consumers
    consumers()


def persistence():
    for i,r in enumerate(examples('weather_operations',5)):
        label=r['workflow']
        if label=='enabled-save-at-10-load-at-100':
            def fresh(data,path):
                saved=json.loads((path/'files/snapshot').read_text())
                assert saved['events']==[{'callback':'weather','map':10,'remaining':50}]
                return ({'map':{'id':10,'size':[1,1]},'units':[],'config':{'periodic_updates':False},'random':{'streams':{'snow_growth':[10]}},'actions':[A(100),E('environment.load',file='snapshot'),I(),A(49),show((0,0)),A(1),show((0,0))]},[event(150,'results.2.events'),check('results.4.cells.0.data',0),check('results.6.cells.0.data',10),event(210),check('draws',[10],project='value')])
            row(5,i,[W(conditions=['precipitation'],temperature=0),A(10),E('environment.save',file='snapshot',maps=[10]),A(50),show((0,0))],[check('results.4.cells.0.data',10),event(120),check('draws',[10],project='value')],followup=fresh,random={'streams':{'snow_growth':[10]}})
        elif label=='steam-save-at-65-load-at-100':
            def fresh(data,path):
                saved=json.loads((path/'files/snapshot').read_text())
                assert sorted((e['callback'],e['remaining']) for e in saved['events'])==[('expire_smoke',5),('weather',55)]
                return ({'map':{'id':10,'size':[1,1]},'units':[],'config':{'periodic_updates':False},'random':{'streams':{}},'actions':[A(100),E('environment.load',file='snapshot'),A(4),I(),A(1),I()]},[check('results.3.maps.main.hexes.0.terrain',':'),check('state.maps.main.hexes.0.terrain',' '),event(155),check('state.events',[],where={'kind':'DECORATION'}),check('draws',[])])
            row(5,i,[layer(500),W(temperature=1),A(65),E('environment.save',file='snapshot',maps=[10]),A(5)], [check('state.maps.main.hexes.0.terrain',' '),event(120)],followup=fresh)
        elif label.startswith('layers-resize'):
            grow=label.endswith('grow');actions=[layer(17,('mud',)),layer(1001,('deep_snow',),1,1),M('resize',3 if grow else 1,3 if grow else 1),show((0,0),(2,2)) if grow else show((0,0))]
            checks=[check('results.3.cells.0.data',17),check('state.maps.main.size',[3,3] if grow else [1,1]),check('state.maps.main.layers',2 if grow else 1,length=True)]
            if grow:checks += [check('results.3.cells.1.data',0),check('results.3.cells.1.layers',[])]
            row(5,i,actions,checks,map={'id':10,'size':[2,2]})
        elif label=='weather-reset':
            row(5,i,[layer(1001),W(temperature=51,winddir=120,windspeed=30),M('addsmoke',0,0,90),A(10),E('weather.reset'),show((0,0)),A(80)],[event(None),check('results.5.cells.0.layers',[]),check('results.5.cells.0.data',0),check('results.5.temperature',51),check('results.5.windspeed',30),check('results.5.deadline',None),check('state.maps.main.objects',[])])
        else:
            def fresh(data,path,label=label):
                saved=json.loads((path/'files/snapshot').read_text())
                if label=='legacy-without-weather':
                    saved['maps'][0].pop('weather');saved['events']=[]
                if label=='malformed-weather-snapshot':saved['maps'][0]['weather']['cells'][0]['x']=1
                (path/'files/reload').write_text(json.dumps(saved))
                actions=[W(temperature=0),layer(42,('mud',)),I(),attempt(E('environment.load',file='reload')),I(),show((0,0))]
                checks=([check('results.4.maps',same_as='results.2.maps'),check('results.4.events',same_as='results.2.events'),check('results.3.error',contains='out of range')] if label=='malformed-weather-snapshot' else [check('results.5.cells.0.data',9007199254740993 if label=='huge-depth-decimal' else 0),check('results.5.cells.0.layers',['deep_snow'] if label=='huge-depth-decimal' else []),check('results.5.enabled',False)])
                if label=='huge-depth-decimal':assert saved['maps'][0]['weather']['cells'][0]['data']=='9007199254740993'
                return ({'map':{'id':10,'size':[1,1]},'units':[],'config':{'periodic_updates':False},'random':{'streams':{}},'actions':actions},checks)
            row(5,i,[layer(9007199254740993,('deep_snow',)),E('environment.save',file='snapshot',maps=[10])],[check('state.maps.main.layers.0.data',9007199254740993)],followup=fresh)
