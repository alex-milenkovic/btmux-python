from entities.mech import MechStatus as S,MoveType
from entities.weapon import WeaponType
from physics import decorations,weather
from . import step,eq,board,unit,invoke,TERRAIN

TERRAIN.update(wall='=',building='@')


@step(r'a 12 by 12 map has a fire at (\d+) 4 and wind direction (\d+)')
def spread_setup(w,x,wind): board(w,12,12); w['x']=int(x); w['map'].winddir=int(wind)


@step(r'the four downwind smoke candidates are calculated')
def coordinates(w): w['coords']=decorations.spread_coordinates(w['map'],w['x'],4,w['map'].winddir)


@step(r'candidate coordinates in source order are (.+)')
def coordinate_result(w,text): eq(w['coords'],[tuple(map(int,xy.split(','))) for xy in text.split(';')])


@step(r'one candidate has threshold (\d+) and the windspeed is (\d+)')
def threshold(w,threshold,wind): w['threshold']=int(threshold); w['map'].windspeed=int(wind)


@step(r'its spread roll is (\d+) and next Number draw would be (\d+)')
def spread_roll(w,roll,number):
    w['streams']={'fire_spread':[int(roll)],'fire_wind':[int(number)]}
    w['eligible']=invoke(w,decorations.spread_eligible,w['map'],w['threshold'])


@step(r'the wind draw is (used|unused) and candidate ignition eligibility is (true|false)')
def spread_result(w,used,eligible):
    eq(any(row[0]=='fire_wind' for row in w['draws']),used=='used'); eq(w['eligible'],eligible=='true')


@step(r'a downwind candidate has underlying (.+) and existing decoration (none|smoke)')
def candidate(w,terrain,deco):
    w['map'].set_terrain(1,1,TERRAIN[terrain])
    if deco=='smoke': decorations.add_smoke(w['engine'],w['map'],1,1,100)


@step(r'smoke is attempted then an eligible fire spread is attempted')
def smoke_then_fire(w):
    invoke(w,decorations.check_smoke,w['engine'],w['map'],[(1,1)])
    invoke(w,decorations.check_fire,w['engine'],w['map'],[(1,1)])


@step(r'final overlay is (none|fire|smoke)')
def overlay(w,value): eq('fire' if w['map'].map_objects[0] else 'smoke' if w['map'].map_objects[1] else 'none',value)


@step(r'symbolic precipitation is (.+) fog and sand are absent temperature is (-?\d+) and windspeed is (\d+)')
def classification(w,precip,temp,wind):
    w['weather']={'none':set(),'ordinary':{'precip'},'heavy':{'heavy_precip'},'ordinary-and-heavy':{'precip','heavy_precip'}}[precip]
    w['temp']=int(temp); w['wind']=int(wind)


@step(r'weather effects are calculated')
def classify(w): w['effects']=weather.calc_effects(weather.validate_conditions(w['weather']),w['temp'],w['wind'])


@step(r'the effect names are (.+)')
def classified(w,effects): eq(w['effects'],set() if effects=='none' else set(effects.replace('-','_').split(',')))


@step(r'a diagnostic weapon type is (TBEAM|TAMMO) and raw effect inputs are (.+)')
def gun(w,weapon,effects):
    w['weapon']=WeaponType[weapon]; w['effects']={key.replace('-','_'):int(value) for key,value in (part.split('=') for part in effects.split(','))}


@step(r'the supplied weather gun arithmetic is evaluated')
def gun_calc(w): w['modifier']=weather.gun_effects(w['effects'],w['weapon'])


@step(r'the modifier is (\d+)')
def modifier(w,expected): eq(w['modifier'],int(expected))


@step(r'a diagnostic unit is (.+) with movement (biped|hover) and layer predicates deep-snow mud and rapids all true')
def pilot(w,position,move):
    u=unit(w); w['map'].add_mech(u)
    u.move_type=MoveType.BIPED if move=='biped' else MoveType.HOVER
    w['map'].layers[0,0]={'deep_snow','mud','rapids'}
    if position=='jumping': u.set_status(S.JUMPING)
    elif position=='above-ground': u.z=1
    elif position=='no-map': u.map=None


@step(r'pilot weather effects are evaluated with heavy rain true and all other weather predicates false')
def pilot_calc(w): w['modifier']=weather.pilot_effects(w['unit'],{'heavy_rain':1})


@step(r'diagnostic minus heat starts at 10 with temperature (-?\d+) weather (.+) and no deep snow')
def heat(w,temp,effects):
    unit(w); w['unit'].minus_heat=10; w['map'].temp=int(temp)
    w['effects']={} if effects=='none' else {effects.replace('-','_'):1}


@step(r'weather heat effects are applied once')
def heat_calc(w): weather.heat_effects(w['map'],w['unit'],w['effects'])


@step(r'minus heat is (\d+)')
def heat_result(w,minus): eq(w['unit'].minus_heat,int(minus))


@step(r'a nonice hex has snow data (\d+) and snow layer (shallow|deep) plus an unrelated layer')
def snow(w,data,layer):
    w['map'].layers[1,1]={'snow' if layer=='shallow' else 'deep_snow','mud'}; w['map'].layer_data[1,1]=int(data)


@step(r'snow is melted by depth (-?\d+) without steam')
def melt(w,depth): weather.melt(w['map'],1,1,int(depth),ice=False)


@step(r'data is (\d+) snow layer is (shallow|deep|none) and unrelated layer remains')
def melted(w,data,layer):
    eq(w['map'].layer_data[1,1],int(data))
    eq(w['map'].layers[1,1],{'mud'}|({'snow' if layer=='shallow' else 'deep_snow'} if layer!='none' else set()))


@step(r'a nonice hex has shallow snow data 500')
def steam_setup(w): snow(w,'500','shallow')


@step(r'depth (\d+) is melted with steam (true|false) and the optional steam draw (\d+)')
def steam(w,depth,steam,draw):
    w['streams']={'snow_steam':[int(draw)]}
    invoke(w,weather.melt,w['map'],1,1,int(depth),steam=steam=='true',ice=False)


@step(r'the smoke duration is (none|\d+) and steam draw usage is (used|unused)')
def steamed(w,duration,usage):
    objects=w['map'].map_objects[1]
    eq(str(objects[0].datas) if objects else 'none',duration); eq(bool(w['draws']),usage=='used')


@step(r'a hex has terrain (.+) data 100 shallow snow and unrelated mud layer')
def growth_setup(w,terrain):
    board(w,1,1); w['map'].set_terrain(0,0,TERRAIN[terrain]); w['map'].layer_data[0,0]=100; w['map'].layers[0,0]={'snow','mud'}


@step(r'growSnow bounds are (-?\d+) (-?\d+) with finite draw (\d+)')
def grow(w,low,high,draw): w['streams']={'snow_growth':[int(draw)]}; invoke(w,weather.grow,w['map'],int(low),int(high))


@step(r'normalized data is (\d+) layers are (.+) and draw is (used|unused)')
def grown(w,data,layers,usage):
    eq(w['map'].layer_data[0,0],int(data)); eq(w['map'].layers[0,0],set(layers.replace('shallow','snow').replace('deep','deep_snow').split(',')))
    eq(bool(w['draws']),usage=='used')
