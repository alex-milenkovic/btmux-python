from . import *
from systems.map_display import sketch,palette
from entities.map import GameMap
from entities.map_objects import add_object,MapObject
from physics.hexmath import hex_to_float

@step(r'a clear 100 by 100 map with viewer at 50 50 and LRS range 30')
def large(w):u(w).set_hex_position(50,50,0);u(w).lrs_range=30
@step(r'keyed HUD tactical height (\d+) is requested')
def hud_height(w,height):hud(w,'t '+height)
@step(r'start bounds are (\S+) and there are (\d+) terrain rows of 70 cells')
def bounds(w,bounds,count):eq(','.join(records(w,'S')[0][:4]),bounds);eq(len(records(w)),int(count));eq(set(len(r[1]) for r in records(w)),{140} if int(count) else set())
@step(r'every row has its y coordinate followed by paired terrain and elevation glyphs')
def pairs(w):
    start=records(w,'S')[0]
    for i,row in enumerate(records(w)):eq(row[0],str(int(start[1])+i));eq(row[1],'.0'*70)
@step(r'tactical outcome is (.+)')
def hud_outcome(w,text):
    if text=='map-list':eq(records(w,'D'),[['Done']]);eq(len(records(w,'S')),1)
    else:eq(w['result']['records'][0]['payload'],text)
@step(r'a map cell terrain is grass elevation 3 with visibility (\S+)')
def cell_visibility(w,visibility):
    u(w).map.set_elevation(3,3,3);u(w).display_los_cells=[dict(x=3,y=3,flags={'both':7,'terrain-only':3,'elevation-only':5,'neither':1}[visibility])]
@step(r'keyed HUD tactical LOS mode renders the cell')
def hud_los(w):hud(w,'t 10 0 0 l')
@step(r'its terrain-elevation pair is (\S+)')
def hud_pair(w,pair):
    sx=int(records(w,'S')[0][0]);row=next(r for r in records(w) if r[0]=='3');eq(row[1][(3-sx)*2:(3-sx)*2+2],pair)
@step(r'HUD mapinfo configuration (\d+) and map in-character (\S+)')
def identity_setup(w,config,ic):w['s'].engine.hudinfo_show_mapinfo=int(config);u(w).map.in_character=truth(ic)
@step(r'keyed HUD tactical is requested')
def hud_map(w):hud(w,'t 5')
@step(r'map ID and name are (\S+) and dimensions remain disclosed')
def identity(w,text):
    row=records(w,'S')[0];eq(row[4:6],[str(u(w).map._id),u(w).map.name] if text=='actual' else ['-1','-1']);eq(row[7:9],['100','100'])
@step(r'a clear tactical cell has terrain (\S+) elevation (\d+) and underlying (\S+)')
def terrain_setup(w,terrain,elev,underlay):
    names={'grass':'GRASSLAND','forest':'LIGHT_FOREST','water':'WATER','bridge':'BRIDGE','highwater':'HIGHWATER','fire':'FIRE','smoke':'SMOKE','road':'ROAD'}
    w['s'].hexagon(dict(at=[4,4],terrain=names[underlay] if terrain in ('fire','smoke') else names[terrain],elevation=int(elev),**(dict(overlay=names[terrain],duration=10) if terrain in ('fire','smoke') else {})))
@step(r'tactical mode (\S+) renders without color or units in that cell')
def terrain_request(w,mode):command(w,'tactical',blank(mode).replace('default',''))
@step(r'the two top glyphs and two bottom glyphs are (\S+) and (\S+)')
def glyphs(w,top,bottom):
    cell=next(c for c in w['result']['cells'] if (c['x'],c['y'])==(4,4));y,x=cell['offset'];eq(w['result']['rows'][y][x:x+2],'  ' if top=='spaces' else top);eq(w['result']['rows'][y+1][x:x+2],bottom)
@step(r'neighboring displayed hexes have elevation difference (\d+)')
def neighbors(w,difference):u(w).map.set_elevation(4,4,int(difference));w['cliff_cell']=(4,4)
@step(r'tactical mode (\S+) is requested on a non-dark map')
def cliff_request(w,mode):command(w,'tactical',mode)
@step(r'their shared lower edge is marked as a cliff (\S+)')
def cliff(w,expected):
    cell=next(c for c in w['result']['cells'] if (c['x'],c['y'])==w['cliff_cell']);y,x=cell['offset'];eq(w['result']['rows'][y+1][x:x+2]==',,',truth(expected))
@step(r'map is dark (\S+)')
def dark(w,value):u(w).map.dark=truth(value)
@step(r'tactical mode (\S+) is requested')
def mode(w,value):command(w,'tactical',value)
@step(r'command outcome is (.+)')
def result(w,text):
    if text=='map':eq(w['result']['ok'],True);assert w['result']['rows']
    else:eq(w['result']['message'],text);eq(w['result']['ok'],False)
@step(r'a 100 by 100 map scanner range (\d+) and TACSIZE (.+)')
def tacsize(w,distance,pref):u(w).tac_range=int(distance);u(w).tacsize=blank(pref)
@step(r'tactical is requested')
def tactical(w):command(w,'tactical')
@step(r'the hex window height is (\d+) width is (\d+) and preference warnings total (\d+)')
def window(w,height,width,warnings):eq(w['result']['window'][2:],[int(width),int(height)]);eq(len(w['result']['warnings']),int(warnings))
@step(r'first mine in a displayed hex is (\S+) with hex NB (\S+)')
def mine(w,kind,nb):
    from systems.mines import Mine,MineType
    if kind!='none':u(w).map.map_objects[3].append(Mine(4,4,MineType.TRIGGER if kind=='trigger' else MineType.STANDARD,5,0,1))
    if kind=='trigger':u(w).map.map_objects[3].append(Mine(4,4,MineType.STANDARD,5,0,1))
    if not truth(nb):u(w).map.set_elevation(3,3,9)
    w['mine_nb']=truth(nb)
@step(r'tactical mine mode is requested')
def mine_request(w):command(w,'tactical','m')
@step(r'the bottom mine marker is (\S+)')
def marker(w,marker):
    cell=next(c for c in w['result']['cells'] if (c['x'],c['y'])==(4,4));y,x=cell['offset'];eq(w['result']['rows'][y+1][x:x+2],'  ' if marker=='blank' else marker)
@step(r'a visible non-carrier DropShip is (\S+) with six adjacent hexes and one bay door')
def ds_setup(w,state):
    form(t(w),'DS');t(w).set_hex_position(5,5,0);t(w).specials2&=~0x80000;t(w).sections[5].criticals[0].type=i2special(Special.DS_MECHDOOR)
    if state=='landed':t(w).status|=S.LANDED
    if state=='shutdown':t(w).status&=~S.STARTED
    visible(w)
@step(r'the dropship occupies (\d+) hexes and a footprint door marker is (\S+)')
def ds(w,count,door):
    rows=w['result']['rows'];occupied=0
    for cell in w['result']['cells']:
        y,x=cell['offset'];top=rows[y][x:x+2];bottom=rows[y+1][x:x+2]
        if top=='TT' or any(c in top+bottom for c in '@=X'):occupied+=1
    eq(occupied,int(count));eq(any('@' in line for line in rows),door=='@')
@step(r'a visible other unit has movement (\S+) and apparent friendship (\S+)')
def movement(w,name,friend):
    t(w).move_type=getattr(M,name.upper());t(w).team=u(w).team if truth(friend) else u(w).team+1;visible(w)
@step(r'LRS (\w) is requested')
def lrs(w,mode):command(w,'lrs',mode)
@step(r'its plain glyph is (\S+)')
def glyph(w,value):
    xy=w.get('glyph_cell',(t(w).x,t(w).y));eq(next(c['glyph'] for c in w['result']['cells'] if (c['x'],c['y'])==xy),' ' if value=='space' else value)
@step(r'an empty visible grass hex at elevation (\d+)')
def elevation(w,value):u(w).map.set_elevation(4,4,int(value));w['glyph_cell']=(4,4)
@step(r'LRS mode (\w) is requested')
def elevation_request(w,mode):command(w,'lrs',mode)
@step(r'a displayed cell is (\S+)')
def unknown(w,value):u(w).display_los_cells=[dict(x=4,y=4,flags=0 if value=='unvisited' else 1)]
@step(r'LRS l and tactical l are requested')
def unknown_request(w):w['lrs']=command(w,'lrs','l');w['tac']=command(w,'tactical','l')
@step(r'the cell uses unknown-state glyph (\S+)')
def unknown_glyph(w,value):
    eq(next(c['glyph'] for c in w['lrs']['cells'] if (c['x'],c['y'])==(4,4)),value)
    cell=next(c for c in w['tac']['cells'] if (c['x'],c['y'])==(4,4));y,x=cell['offset'];eq(w['tac']['rows'][y][x],value)
@step(r'a large map and LRS range (\d+) with LRSHEIGHT (\S+)')
def height_setup(w,distance,pref):u(w).lrs_range=int(distance);u(w).lrsheight=blank(pref)
@step(r'its hex height is (\d+) with (\d+) preference warnings')
def height(w,height,warnings):eq(w['result']['window'][3]-w['result']['window'][1],int(height));eq(len(w['result']['warnings']),int(warnings))
@step(r'the observer is at hex (\S+) and visible same-hex contacts have distinct real offsets')
def navigate_setup(w,position):
    x,y=map(int,position.split(','));u(w).set_hex_position(x,y,0);t(w).set_hex_position(x,y,0);t(w).fx+=10;visible(w)
@step(r'navigate and findcenter are requested')
def navigate(w):w['nav']=command(w,'navigate');w['center']=command(w,'findcenter')
@step(r'navigate has 13 lines and a 5 by 5 hexagonal local view with compass and live movement fields')
def navigation(w):eq(len(w['nav']['rows']),13);eq(w['nav']['window'][2:],[5,5]);assert 'Speed:' in w['nav']['message'];eq(w['center']['range'],0.0)
@step(r'off-map hexes are (\S+) and self wins a coincident subhex marker')
def offmap(w,expected):
    eq(any(v<0 for v in w['nav']['window'][:2]),expected=='blank')
    t(w).fx,t(w).fy=u(w).fx,u(w).fy;result=command(w,'navigate');assert '*' in result['message']
@step(r'display color preference (\S+)')
def colors(w,value):u(w).mapcolor=value;u(w).ansimap=True
@step(r'two consecutive colored maps are requested then a different player requests the default palette')
def colored(w):
    from systems.map_display import DEFAULT_PALETTE
    w['colors']=[command(w,'tactical'),command(w,'tactical')]
    t(w).ansimap=True
    action=dict(op='command',unit='target',name='tactical',args=[])
    w['default']=w['s'].action(action)
    t(w).mapcolor=DEFAULT_PALETTE;w['explicit_default']=w['s'].action(action)
@step(r'each original render emits (\d+) preference diagnostic lines and the default-player render emits zero')
def warnings(w,count):eq([len(r['warnings']) for r in w['colors']],[int(count)]*2);eq(w['default']['warnings'],[])
@step(r'color does not leak between lines or players')
def isolation(w):eq(w['colors'][0]['rows'],w['colors'][1]['rows']);eq(w['default']['rows'],w['explicit_default']['rows'])
