import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from entities.mech import MechStatus as S,FireMode as F,SectionConfig as C
from entities.map_objects import MapObject,add_object
from systems import buildings,map_links
from physics.weather import grow
from tools.maps_environment import MapsSession
from . import step,eq,board,unit,invoke


@step(r'the named ordinary workflow (.+) starts from its documented fresh fixture')
def workflow(w,name):
    w['workflow']=name
    w['document']=json.loads((Path('examples/maps_environment')/(name+'.json')).read_text())


@step(r'only its setup commands gameplay commands and clock advances are executed')
def execute(w):
    with TemporaryDirectory(dir='./tmp') as directory:
        document=dict(w['document'],file_root=directory)
        s=MapsSession(document); w['session']=s
        w['results']=[s.action(action) for action in document['actions']]
        w['snapshots']=[result for action,result in zip(document['actions'],w['results']) if action['op']=='inspect']
        w['final']=s.snapshot()


@step(r'the independently observable result is (.+)')
def outcome(w,result):
    if 'weather_workflow' in w:
        from .weather_operations import snapshot_result
        return snapshot_result(w,result)
    s=w['session']; state=w['final']; snapshots=w['snapshots']; u=s.units['u']
    if result=='hexes-and-source-trailer-rules':
        eq((s.map.terrain(1,1),s.map.elevation(1,1)),('%',3))
        eq((s.map.flags,s.map.grav,s.map.temp),(2,75,-20))
        assert state['files']['terrain']['text'].endswith('2: 75 -20\n')
    elif result=='unique-local-membership-and-conditions':
        eq(s.maps['outside'].roster_ids,[]); eq(s.maps['inside'].roster_ids,[40]); eq(u.mapindex,20)
        eq(u.status&S.CONDITIONS,S.CONDITIONS); eq(u.mapnumber,0)
    elif result=='timed-spread-smoke-and-restoration':
        eq(w['results'][1]['accepted'],True)
        first,middle,last=snapshots
        eq(first['maps']['outside']['hexes'][10]['terrain'],'&')
        assert any(obj['kind']=='SMOKE' for obj in middle['maps']['outside']['objects'])
        eq(last['maps']['outside']['objects'],[])
        eq(last['maps']['outside']['hexes'][10]['terrain'],'%')
        assert any(draw['name']=='fire_spread' for draw in s.draws)
    elif result=='CF-damage-regeneration-and-scan':
        eq(w['results'][2]['building_cf'],95); eq(snapshots[0]['maps']['inside']['cf'],95)
        eq(s.maps['inside'].cf,96)
        eq([e['deadline'] for e in state['events'] if e['kind']=='BREGEN'],[240])
    elif result=='CF-zero-no-auto-rebuild':
        eq(w['results'][2]['building_cf'],0); eq(s.maps['inside'].cf,0)
        assert not any(e['kind'] in ('BREGEN','BREBUILD') for e in state['events'])
    elif result=='real-local-exit-resolution':
        eq(w['results'][0],[1,1,4]); eq(u.map,s.maps['outside']); eq((u.x,u.y),(1,1))
        eq(s.maps['inside'].roster_ids,[])
        assert 'You have left the inside.' in u.movement_messages
        assert any(e['operation']=='loud_teleport' and not e['applied'] for e in u.external_effects)
    elif result=='applied-local-disable-and-repair':
        eq(u.sections[0].config&C.SECTION_BREACHED,C.SECTION_BREACHED)
        before=snapshots[0]['units']['u']
        assert any(draw['name']=='breach_rolls' and draw['value']>=10 for draw in s.draws)
        eq(u.sections[0].criticals[4].firemode&F.DISABLED_MODE,0)
        assert u.sections[0].criticals[0].firemode&F.DISABLED_MODE
        eq(w['results'][-2]['accepted'],True)
    else: raise ValueError(result)


@step(r'a diagnostic attempt requires unavailable service (.+)')
def unavailable(w,service): w['service']=service


@step(r'the dependency has no supplied implementation or approved source mapping')
def dependency(w):
    service=w['service']; u=unit(w); b=w['map']; b.add_mech(u)
    if service in ('MUX-teleport','occupant-enumeration'):
        inside=board(w); inside._id=2000; inside.cf=inside.cfmax=100; inside.name='Depot'
        w['map']=b; add_object(b,4,MapObject(x=1,y=1,obj=2000)); add_object(inside,5,MapObject(obj=b._id))
        if service=='MUX-teleport':
            from systems.map_transitions import transfer,leave_hangar
            u.in_character=False; invoke(w,transfer,u,inside); invoke(w,leave_hangar,inside,u)
        else: invoke(w,buildings.hit_building,u,1,1,-1,10)
        w['effects']=u.external_effects
    elif service=='mine-trigger-script':
        from systems.mines import Mine,MineType,make_mine_explode
        invoke(w,make_mine_explode,u,b,Mine(0,0,MineType.TRIGGER,5,1,40),0,0,'step')
        w['effects']=u.external_effects
    elif service=='AUTO-gameplay':
        document={'units':[{'name':'u'}],'objects':[{'name':'auto','id':42,'type':'AUTO','mymech':'u'}], 'actions':[]}
        s=MapsSession(document); s.action({'op':'clock','name':'heartbeat'})
        w['effects']=s.objects['auto'].external_effects
    elif service=='validateSnowDepth':
        board(w,1,1); invoke(w,grow,w['map'],1,1); w['effects']=w['map'].external_effects
    elif service=='weather-macro-values':
        from physics.weather import mapping_status
        w['effects']=[mapping_status()]
    else: raise ValueError(service)


@step(r'it is reported blocked with applied false and no fabricated success')
def blocked(w):
    effects=w['effects']; assert effects,effects
    assert all(effect['applied'] is False for effect in effects),effects
    needles={'MUX-teleport':'loud_teleport','occupant-enumeration':'occupant-enumeration','AUTO-gameplay':'auto',
             'mine-trigger-script':'trigger','weather-macro-values':'macro','validateSnowDepth':'validateSnowDepth'}
    assert any(needles[w['service']].lower() in str(effect).lower() for effect in effects),effects
