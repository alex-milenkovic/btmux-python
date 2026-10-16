"""Independent ordinary gameplay checks for R3, with C-derived arithmetic."""
import itertools
from maps_environment_qa import check,D,M,I,A,C
from maps_qa_operations import W,E,layer,basic


def build():
    # mech.update.c: temperature is gated by SPECIAL; minus precedes balance
    # and weapon heat decays by (minus-internal)/WEAPON_RECYCLE_TIME (30).
    for temp,weather in itertools.product((-31,51),('disabled','clear','rain','heavy')):
        extra=0 if weather in ('disabled','clear') else (-1 if temp>0 or weather=='heavy' else 0)
        if weather=='heavy' and temp>0:extra=-2
        minus=10+(1 if temp<0 else -1)+extra
        conditions=[] if weather in ('disabled','clear') else ['precipitation' if weather=='rain' else 'heavy_precipitation']
        basic(f'heat-temperature-{temp}-{weather}',[W(temperature=temp,conditions=conditions,enabled=weather!='disabled'),A(2)],
              [check('state.units.u.plus_heat',12),check('state.units.u.minus_heat',minus),check('state.units.u.heat',12-minus),check('state.units.u.weap_heat',12-minus/30,tolerance=1e-9)],
              units=[{'name':'u','at':[0,0,0],'heat_state':{'num_sinks':10,'weap_heat':12}}],config={'periodic_updates':True},random={'streams':{'visibility_change':[10]*2}})
    for temp in (-31,51):
        basic(f'heat-legacy-nonspecial-{temp}',[E('weather.enable'),A(2)],
              [check('state.units.u.minus_heat',10),check('state.units.u.plus_heat',12),check('state.units.u.heat',2),check('state.units.u.weap_heat',12-10/30,tolerance=1e-9)],
              map={'id':10,'size':[1,1],'temp':temp,'flags':0},units=[{'name':'u','at':[0,0,0],'heat_state':{'num_sinks':10,'weap_heat':12}}],config={'periodic_updates':True},random={'streams':{'visibility_change':[10]*2}})
    for loc,destroyed in itertools.product((0,6),(False,True)):
        minus=9 if loc==6 and not destroyed else 10
        basic(f'heat-deep-leg-{loc}-{destroyed}',[layer(1001,('deep_snow',)),W(temperature=20),A(2)],
              [check('state.units.u.minus_heat',minus),check('state.units.u.plus_heat',12),check('state.units.u.heat',12-minus),check('state.units.u.weap_heat',12-minus/30,tolerance=1e-9)],
              units=[{'name':'u','at':[0,0,0],'heat_state':{'num_sinks':10,'weap_heat':12},'sections':[{'index':loc,'slots':[{'index':4,'special':'HEAT_SINK','firemode':int(destroyed)}]}]}],config={'periodic_updates':True},random={'streams':{'visibility_change':[10]*2}})
    # No weather modifier at the shared target after ordinary map removal.
    basic('pilot-shared-no-map',[W(conditions=['heavy_precipitation']),D('membership_remove'),dict(op='diagnose',kind='MechPilotSkillRoll_BTH',args=[0])],[check('results.2',5)],units=[{'name':'u','at':[0,0,0]}],mode='diagnostic')
    # Independent source weapon classes and target-neighbor rolls. The clear
    # baseline at range3 is gunnery8, building-4, short0, plus AC/5
    # minimum-range1. Weather is added exactly once to that target.
    weapons=[('IS.AC/5','TAMMO',1),('IS.MediumLaser','TBEAM',3),('IS.SRM-2','TMISSILE',2),('CL.StreakSRM-2','STREAK',2)]
    for (weapon,kind,sandfog),weather in itertools.product(weapons,('high','blizzard','fog-sand-wind','disabled')):
        wind=30 if weather=='fog-sand-wind' else 61
        conditions=['heavy_precipitation'] if weather=='blizzard' else ['fog','blowing_sand'] if weather in ('fog-sand-wind','disabled') else []
        mod=(2 if kind=='TAMMO' else 0) if weather=='high' else (2 if kind=='TAMMO' else 1) if weather=='blizzard' else sandfog+(kind=='TAMMO') if weather=='fog-sand-wind' else 0
        # Raise independent gunnery to8 so every BTH has valid 2d6 neighbors.
        target=4+mod+int(kind=='TAMMO')
        for hit in (False,True):
            throw=target if hit else target-1
            maps=[{'name':'main','id':10,'size':[9,9],'map_objects':[{'kind':'BUILDING','x':2,'y':2,'obj':20}]},{'name':'Depot','id':20,'size':[9,9],'cf':100,'cfmax':100}]
            units=[{'name':'u','at':[2,5,0],'gunnery':8,'weapons':[weapon],'ammo':[] if kind=='TBEAM' else [{'weapon':weapon,'rounds':20}]}]
            def compare(data,path,mod=mod,target=target,throw=throw,hit=hit,kind=kind):
                sight=data['results'][2]['attack'];shot=data['results'][4]['attack']
                assert sight['bth_breakdown']==shot['bth_breakdown']
                assert shot['bth_breakdown']['weather_mod']==mod and shot['bth_breakdown']['total']==target
                assert shot['hit']==hit
                assert [x['value'] for x in data['draws'] if x['name']=='attack_rolls']==[throw,throw]
                before=data['results'][3]['units']['u'];after=data['state']['units']['u']
                assert before['weap_heat']==0 and before['weapons'][0]['recycle']==0
                assert after['weapons'][0]['recycle']>0
                if kind!='TBEAM':
                    ammo=[(i,j) for i,section in enumerate(before['sections']) for j,slot in enumerate(section['slots']) if slot['data']==20]
                    assert len(ammo)==1
                    loc,crit=ammo[0]
                    assert after['sections'][loc]['slots'][crit]['data']==(20 if kind=='STREAK' and not hit else 19)
                assert after['weap_heat']>0 if kind!='STREAK' or hit else after['weap_heat']==0
                assert data['state']['maps']['Depot']['cf']<100 if hit else data['state']['maps']['Depot']['cf']==100
            basic(f'gun-boundary-{kind}-{weather}-{hit}',[W(conditions=conditions,temperature=0,windspeed=wind,enabled=weather!='disabled'),C('lock',2,2,'B'),C('sight',0),I(),C('fire',0)],
                  [check('results.4.accepted',True)],checker=compare,maps=maps,units=units,
                  random={'streams':{'attack_rolls':[throw,throw],'failure_weapon_chance':[4],'missile_cluster':[12],'missile_pre_roll':[6]*3,'terrain_rolls':[2]*4,'rolls':[12]}})
    # Actual wind-controlled ordinary ignition retains FIRESPEED and spread.
    basic('weather-wind-ordinary-forest',[W(windspeed=30),C('lock',4,4,'I'),C('fire',0),I(),A(29),I(),A(1),I()],
          [check('results.2.accepted',True),check('results.3.maps.main.objects.0.deadline',30),check('results.5.maps.main.objects',1,where={'kind':'FIRE'},length=True),check('state.maps.main.objects',2,where={'kind':'FIRE'},length=True),check('state.maps.main.objects',[60],where={'kind':'FIRE','x':4,'y':3},project='deadline'),check('draws',[30],where={'name':'fire_wind'},project='value')],
          map={'id':10,'size':[12,12],'hexes':[{'at':[4,4],'terrain':'LIGHT_FOREST','elevation':0},{'at':[4,3],'terrain':'LIGHT_FOREST','elevation':0}]},units=[{'name':'u','at':[4,6,0],'weapons':['IS.Flamer']}],
          random={'streams':{'attack_rolls':[12],'failure_weapon_chance':[4],'terrain_rolls':[12,12],'fire_duration':[120,60],'fire_spread':[9,2,2,2],'fire_wind':[30],'smoke_duration':[90]*4}})
    # map.winddir's adjusted direction remains unused by C artillery.c;
    # Number direction0/distance2 yields distance2 at wind0, distance7 at60.
    for speed,x in ((0,6),(60,11)):
        basic(f'weather-wind-artillery-{speed}',[W(winddir=180,windspeed=speed),C('lock',4,4,'H'),C('sight',0),C('fire',0),A(10)],
              [check('results.3.accepted',True),check('state.map.artillery_impacts',[x],project='x'),check('state.map.artillery_impacts',[4],project='y'),check('draws',[0],where={'name':'artillery_scatter_direction'},project='value'),check('draws',[2],where={'name':'artillery_scatter_distance'},project='value')],
              map={'id':10,'size':[12,12]},units=[{'name':'u','at':[4,6,0],'class':'VEH_GROUND','movement':'TRACK','artillery':8,'weapons':['IS.Sniper'],'ammo':[{'weapon':'IS.Sniper','rounds':20}]}],
              random={'streams':{'attack_rolls':[2,2],'failure_weapon_chance':[4],'artillery_scatter_direction':[0],'artillery_scatter_distance':[2]}})
    # Warm ice affects only matching z0 nonhover occupants. Other local units
    # witness the source broadcast, while submerged/above occupants survive.
    for altitude in (-2,-1,1):
        basic(f'ice-submerged-above-{altitude}',[W(temperature=1),A(60)],[check('state.units.u.destroyed',False),check('state.units.u.fallen',False),check('state.units.u.cached_terrain','~'),check('draws',[])],
              map={'id':10,'size':[1,1],'default':['ICE',2]},units=[{'name':'u','class':'VEH_GROUND','movement':'TRACK','at':[0,0,altitude]}])
    from maps_qa_storage import dynamic
    from maps_environment_qa import F
    def occupants(data,path):
        before=data['results'][2]['units'];after=data['state']['units']
        # 50 tons /10 *2 levels, halved in water (MechFalls) =5.
        assert sum(s['armor']+s['internal'] for s in before['u']['sections'])-sum(s['armor']+s['internal'] for s in after['u']['sections'])==5
        assert before['v']['sections']==after['v']['sections']
        assert any('goes swimming as ice breaks!' in text for text in after['v']['messages'])
        assert [r['value'] for r in data['draws'] if r['name']=='pilot_rolls']==[12]
    basic('ice-roster-damage-broadcast',[F('load_dynamic',count=4),W(temperature=1),I(),A(60)],
          [check('state.units.u.destroyed',True),check('state.units.u.cached_terrain','~'),check('state.units.v.destroyed',False),check('state.units.v.cached_terrain',' '),check('state.maps.main.roster_ids',[40,41,-1,999])],checker=occupants,
          map={'id':10,'size':[2,1],'hexes':[{'at':[0,0],'terrain':'ICE','elevation':2}]},units=[{'name':'u','id':40,'class':'VEH_GROUND','movement':'TRACK','at':[0,0,0]},{'name':'v','id':41,'at':[1,0,0]}],
          files={'record':{'hex':dynamic([40,41,-1,999]).hex()}},random={'streams':{'sensor.detect':[1]*20,'pilot_rolls':[12],'rolls':[12],'fall_directions':[1],'hit_location_rolls':[7],'damage_entry':[7]}})
    basic('ice-overwrites-removed-snow-steam',[layer(500),W(temperature=1),A(60)],
          [check('state.maps.main.layers.0.data',490),check('state.maps.main.hexes.0.terrain','~'),check('state.maps.main.objects',[]),check('draws',[])],map={'id':10,'size':[1,1],'default':['ICE',2]})
