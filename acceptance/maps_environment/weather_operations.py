"""Normal generated APS drives the public map/environment command interface."""
from pathlib import Path
from tempfile import TemporaryDirectory
from tools.maps_environment import MapsSession
from core.events import EventType
from entities.mech import MechStatus as S
from . import step,eq


def session(w,width=1,height=1,units=None,streams=None,periodic=False,hexes=None):
    document=dict(maps=[dict(name='outside',id=10,size=[width,height],hexes=hexes or [])],
                  units=units or [],actions=[],config=dict(periodic_updates=periodic,lock_tick=0),
                  random={'seed':5489})
    if streams is not None:document['random']={'streams':streams}
    document['file_root']='./tmp/maps-aps-weather'
    w['session']=MapsSession(document)
    return w['session']


def command(w,name,**args):return w['session'].action(dict(op='map_command',name=name,args=args))
def advance(w,tick):
    s=w['session'];s.action(dict(op='advance',seconds=int(tick)-s.engine.tick))
def conditions(text):return [] if text=='none' else text.split(',')
def deadline(event):return str(event.tick) if event is not None and not event.zombie else 'none'


@step(r'ordinary weather controls enable conditions (.+) temperature (-?\d+) and windspeed (\d+)')
def setup_modifiers(w,names,temp,wind):w['configuration']=dict(conditions=conditions(names),temperature=int(temp),windspeed=int(wind))


@step(r'a grounded biped with no hex layers has weapon class (TAMMO|TBEAM) and ordinary heat dissipation 10')
def setup_weapon(w,weapon):
    weapon='IS.AC/5' if weapon=='TAMMO' else 'IS.MediumLaser'
    session(w,9,9,units=[dict(name='u',id=40,at=[1,3,0],facing=0,weapons=[weapon],ammo=[dict(weapon=weapon,rounds=20,section=2,critical=5)] if weapon=='IS.AC/5' else [],heat_state={'num_sinks':10}),
                           dict(name='pilot',id=41,at=[5,5,0],fallen=True)],periodic=True)
    command(w,'weather.set',**w['configuration'])


@step(r'sight and actual fire use the same shot setup and an ordinary piloting command and heat tick execute')
def gameplay(w):
    s=w['session'];s.action(dict(op='command',name='lock',args=[1,1,'H']))
    before=len(s.draws)
    w['sight']=s.action(dict(op='command',name='sight',args=[0]))
    # Accepted Combat contract: source sight consumes its attack draw.
    eq([row['name'] for row in s.draws[before:]],['attack_rolls'])
    w['fire']=s.action(dict(op='command',name='fire',args=[0]))
    w['stand_check']=s.action(dict(op='command',unit='pilot',name='stand',args=['check']))
    w['stand']=s.action(dict(op='command',unit='pilot',name='stand',args=[]))
    advance(w,2)


@step(r'the sight and firing weather term is (\d+) the piloting weather term is (\d+) and minus heat is (\d+)')
def gameplay_result(w,gun,pilot,minus):
    sight=w['sight']['attack']['bth_breakdown'];fire=w['fire']['attack']['bth_breakdown']
    assert sight is not None and fire is not None,(w['sight'],w['fire'])
    eq(sight['weather_mod'],int(gun));eq(fire['weather_mod'],int(gun));eq(sight['total'],fire['total'])
    assert w['fire']['accepted'],w['fire']
    messages=w['session'].units['pilot'].movement_messages
    assert any(f'Modified Pilot Skill: BTH {5+int(pilot)}\tRoll:' in m for m in messages),messages
    eq(w['session'].units['u'].minus_heat,int(minus))


@step(r'a one-cell grass map enables (.+) at temperature 0 tick 0 with default rates and finite snow draws (.+)')
def snowfall(w,names,draws):
    session(w,streams={'snow_growth':[] if draws=='none' else list(map(int,draws.split(',')))})
    command(w,'weather.set',conditions=conditions(names),temperature=0)


@step(r'the ordinary simulation clock advances to (\d+)')
def clock_to(w,tick):advance(w,tick)


@step(r'snow depth is (\d+) snow layer is (none|shallow|deep) and next weather deadline is (\d+)')
def snow_result(w,depth,layer,next_tick):
    result=command(w,'weather.show',cells=[[0,0]])
    eq(result['cells'][0]['data'],int(depth));eq(result['cells'][0]['layers'],[] if layer=='none' else ['snow' if layer=='shallow' else 'deep_snow'])
    eq(result['deadline'],int(next_tick))


@step(r'a one-cell grass map starts with shallow snow depth 500 and enables temperature (-?\d+) at tick 0 with steam (true|false)')
def melting(w,temp,steam):
    session(w)
    command(w,'layer.set',x=0,y=0,layers=['snow'],data=500)
    command(w,'weather.set',temperature=int(temp),steam=steam=='true')


@step(r'the simulation reaches tick 60 with optional steam draw (\d+)')
def melt_clock(w,draw):
    # Finite named streams are ordinary simulator inputs, never expected state.
    s=w['session'];s.strict_streams=True;s.streams={'snow_steam':[int(draw)]}
    advance(w,60)


@step(r'snow depth is (\d+) smoke deadline is (none|\d+) and the steam draw is (used|unused)')
def melt_result(w,depth,next_tick,usage):
    s=w['session'];eq(s.map.layer_data[0,0],int(depth))
    eq(deadline(s.map.map_objects[1][0].event) if s.map.map_objects[1] else 'none',next_tick)
    eq(any(d['name']=='snow_steam' for d in s.draws),usage=='used')


@step(r'a width 5 grass map enables ordinary snowfall at tick 0 with default cadence')
def timer_setup(w):session(w,5,1);command(w,'weather.set',conditions=['precipitation'],temperature=0)


@step(r'the ordinary command sequence is (.+)')
def timer_sequence(w,sequence):
    if sequence.startswith('set-mine'):
        advance(w,5)
        # Empty-unit administrative map bit operation uses the shared map API.
        from entities.map_objects import bits_for
        bits_for(w['session'].map).set(4,0,1)
    advance(w,10)
    if sequence=='identical-set-at-10':command(w,'weather.set',conditions=['precipitation'])
    elif sequence=='heavy-set-at-10':command(w,'weather.set',conditions=['heavy_precipitation'])
    elif sequence=='cadence-10-at-10':command(w,'weather.set',cadence_ticks=10)
    elif sequence.startswith('disable'):
        command(w,'weather.disable')
        if ',' in sequence:advance(w,20);command(w,'weather.enable')
    elif sequence=='reset-at-10':command(w,'weather.reset')
    elif sequence=='clear-mechs-at-10':w['session'].action(dict(op='map_command',name='clear'))
    elif sequence=='remove-map-at-10':w['session'].action(dict(op='map_command',name='unregister'))
    elif 'resize' in sequence:
        result=w['session'].action(dict(op='map_attempt',action=dict(op='map_command',name='resize',args='0 0' if '0x0' in sequence else '9 9')))
        if sequence.startswith('set-mine'):assert result['error']
        else:eq(result['error'],None)
    elif sequence=='invalid-cadence-0-at-10':
        result=w['session'].action(dict(op='map_attempt',action=dict(op='map_command',name='weather.set',args=dict(cadence_ticks=0))))
        assert result['error']
    else:raise ValueError(sequence)


@step(r'the weather event count is (\d+) and its deadline is (none|\d+)')
def timer_result(w,count,next_tick):
    s=w['session'];eq(s.engine.events.count_type(EventType.WEATHER),int(count));eq(deadline(s.map.weather_event),next_tick)


@step(r'the documented ordinary environment snapshot workflow (.+) starts through public controls')
def snapshot_setup(w,workflow):
    w['weather_workflow']=workflow;session(w,2,2)
    command(w,'layer.set',x=0,y=0,layers=['snow'],data=500)
    command(w,'weather.set',conditions=['precipitation'],temperature=0)
    if workflow=='huge-depth-decimal':command(w,'layer.set',x=0,y=0,layers=['deep_snow'],data=9007199254740993)
    if workflow.startswith('steam-'):command(w,'weather.set',temperature=1,conditions=[])
    if workflow=='weather-reset':
        command(w,'weather.set',temperature=21,winddir=90,windspeed=30)
        w['session'].action(dict(op='map_command',name='addsmoke',args='0 0 120'))


@step(r'it saves loads or resizes through the public interface')
def snapshot_operation(w):
    import json
    kind=w['weather_workflow'];s=w['session']
    if kind.startswith('layers-resize'):
        command(w,'layer.set',x=1,y=1,layers=['mud'],data=4)
        s.action(dict(op='map_command',name='resize',args='3 3' if kind.endswith('grow') else '1 1'))
    elif kind=='weather-reset':command(w,'weather.reset')
    else:
        if kind.startswith('enabled-save'):advance(w,10)
        if kind.startswith('steam-save'):advance(w,65)
        command(w,'environment.save',file='weather-snapshot.json',maps=[10])
        saved=s.path('weather-snapshot.json').read_text()
        if kind=='malformed-weather-snapshot':
            malformed=json.loads(saved);malformed['maps'][0]['weather']['conditions']=['bad']
            s.path('weather-snapshot.json').write_text(json.dumps(malformed));w['old_event']=s.map.weather_event
            w['load_error']=s.action(dict(op='map_attempt',action=dict(op='map_command',name='environment.load',args=dict(file='weather-snapshot.json'))))
        else:
            if kind=='legacy-without-weather':
                legacy=json.loads(saved);del legacy['maps'][0]['weather'];legacy['events']=[];saved=json.dumps(legacy)
            w['original_session']=s;session(w,2,2)
            w['session'].path('weather-snapshot.json').write_text(saved)
            if kind.startswith(('enabled-save','steam-save')):advance(w,100)
            command(w,'environment.load',file='weather-snapshot.json')


def snapshot_result(w,result):
    s=w['session'];kind=w['weather_workflow']
    if kind.startswith('enabled-save'):
        eq(s.map.weather_event.tick,150)
        s.strict_streams=True;s.streams={'snow_growth':[10,11,12,13]}
        original=w['original_session'];original.strict_streams=True;original.streams={'snow_growth':[10,11,12,13]}
        original.action(dict(op='advance',seconds=50));advance(w,150)
        eq(s.map.layer_data,original.map.layer_data);eq(s.draws,original.draws)
    elif kind.startswith('steam-save'):
        eq(s.map.weather_event.tick,155);eq(s.map.map_objects[1][0].event.tick,105)
        advance(w,104);eq(s.map.terrain(0,0),':');advance(w,105);eq(s.map.terrain(0,0),' ')
    elif kind=='layers-resize-grow':
        eq((s.map.map_width,s.map.map_height),(3,3));eq(s.map.layer_data,{(0,0):500,(1,1):4});eq(s.map.layers.get((2,2),set()),set())
    elif kind=='layers-resize-shrink':eq(s.map.layer_data,{(0,0):500})
    elif kind=='weather-reset':
        eq(s.map.weather_enabled,False);eq(s.map.layers,{});eq((s.map.temp,s.map.winddir,s.map.windspeed),(21,90,30));eq(s.map.map_objects[1][0].event.tick,120)
    elif kind=='legacy-without-weather':eq(s.map.weather_enabled,False);eq(s.map.layers,{});eq(s.map.temp,0)
    elif kind=='huge-depth-decimal':eq(s.map.layer_data[0,0],9007199254740993);eq(s.map.layers[0,0],{'deep_snow'})
    elif kind=='malformed-weather-snapshot':
        assert w['load_error']['error'];assert s.map.weather_event is w['old_event'];eq(s.map.weather_event.zombie,False)
    else:raise ValueError(result)


@step(r'an ice hex has stored elevation (\d+) and a same-hex ground vehicle at altitude (\d+) with movement (tracked|hover)')
def ice_setup(w,elev,altitude,move):
    session(w,units=[dict(name='u',id=40,at=[0,0,int(altitude)],**{'class':'VEH_GROUND'},movement='TRACK' if move=='tracked' else 'HOVER')],
            hexes=[dict(at=[0,0],terrain='ICE',elevation=int(elev))])


@step(r'warm weather is enabled at temperature 1 tick 0 with default melt settings')
def warm(w):command(w,'weather.set',temperature=1)


@step(r'the clock processes the weather callback at 60')
def ice_clock(w):advance(w,60)


@step(r'terrain is water steam is absent and the vehicle consequence is (fall-and-flood-destruction|no-fall)')
def ice_result(w,consequence):
    s=w['session'];eq(s.map.terrain(0,0),'~');eq(s.map.map_objects[1],[])
    eq(s.units['u'].is_destroyed,consequence=='fall-and-flood-destruction')
    if consequence.startswith('fall'):assert s.units['u'].last_fall_levels>0
    else:eq(getattr(s.units['u'],'last_fall_levels',0),0)


@step(r'ordinary layer controls set snow depth (\d+) and mud on a grass hex')
def normalized_setup(w,before):session(w);command(w,'layer.set',x=0,y=0,layers=['snow','mud'],data=int(before))


@step(r'the ordinary snow grow command draws (\d+) from equal signed bounds (-?\d+)')
def normalized_grow(w,draw,bound):
    s=w['session'];s.strict_streams=True;s.streams={'snow_growth':[int(draw)]}
    command(w,'snow.grow',low=int(bound),high=int(bound))


@step(r'layer data is (\d+) and final layers are (.+)')
def normalized_result(w,after,layers):
    result=command(w,'weather.show',cells=[[0,0]])['cells'][0]
    eq(result['data'],int(after));eq(set(result['layers']),set(layers.split(',')))
