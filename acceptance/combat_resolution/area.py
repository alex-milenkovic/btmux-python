"""Artillery, blast, mine and terrain acceptance bindings."""
from dataclasses import replace
from . import step,eq,session,unit,call,dice,armor,position
from core.events import EventType
from entities.mech import AmmoMode as A, MechStatus as S, Location as L
from entities.map import LIGHT_FOREST,HEAVY_FOREST,ROUGH,GRASSLAND,FIRE,SMOKE,ICE,WATER
from entities.weapon import get_weapon
from physics.hexmath import hex_to_float
from systems import artillery,mines,damage,terrain_combat as terrain


def shot(w,mode=0,nominal=None):
    weapon=get_weapon('IS.Sniper')
    if nominal is not None:
        session(w).weapon_overrides[weapon.index]=replace(weapon,damage=nominal)
    w['shot']=artillery.ArtilleryShot(3,3,4,4,weapon.index,mode,True,unit(w)._id,session(w).map)
    position(unit(w,'v'),4,4)
    w['before']=armor(unit(w,'v'))

def impact(w):
    call(w,artillery.artillery_hit,session(w).engine,w['shot'])

def advance(w,tick):
    session(w).engine.events.set_tick(int(tick))
    call(w,session(w).engine.events.run_events)

@step(r'artillery launch at tick 0 over hex range ([\d.]+)')
def flight(w,distance):
    shot(w,A.MINE_MODE)
    session(w).engine.events.schedule(artillery.flight_time(float(distance)),EventType.ARTILLERY_HIT,
        artillery.artillery_hit_event,w['shot'],session(w).engine)

@step(r'the event clock advances to (\d+) then (\d+)')
def deadline(w,before,due):
    advance(w,before)
    w['early_impacts']=len(session(w).map.artillery_impacts)
    advance(w,due)

@step(r'impact count is zero before and one at due')
def deadline_result(w):eq((w['early_impacts'],len(session(w).map.artillery_impacts)),(0,1))

@step(r'a normal artillery shell launched at target hex 4 4')
def launch(w):
    shot(w)
    w['shot']=call(w,artillery.artillery_shoot,session(w).engine,unit(w),4,4,w['shot'].weapon_index,0,True)

@step(r'before impact the shooter (moves|changes-lock|changes-ammo-mode|is-destroyed)')
def change(w,kind):
    u=unit(w)
    if kind=='moves':position(u,7,7)
    elif kind=='changes-lock':u.targ_x=u.targ_y=8
    elif kind=='changes-ammo-mode':u.sections[4].criticals[0].ammomode=A.SMOKE_MODE
    else:call(w,damage.destroy_mech,u,u,engine=session(w).engine)
    advance(w,10)

@step(r'exactly one impact uses captured target 4 4 and original ammo mode')
def captured(w):
    impacts=session(w).map.artillery_impacts
    eq(len(impacts),1)
    eq((impacts[0]['x'],impacts[0]['y'],impacts[0]['mode']),(4,4,0))

@step(r'an in-bounds shell of nominal damage (\d+) with ammo bits (.+) and every cluster offset draw zero')
def cluster(w,nominal,modes):
    mode=0
    for name in modes.split('+'):mode |= A[name+'_MODE']
    shot(w,mode,int(nominal))
    dice(w,'artillery_cluster',[0]*(int(nominal)*4))
    dice(w,'smoke_duration',[90]*20)

@step(r'the (?:successful shell |artillery )impact event runs(?: on an undecorated map)?')
def hit(w):impact(w)

@step(r'center delivered damage is (\d+) in chunks no larger than 2')
def cluster_result(w,total):
    eq(w['before']-armor(unit(w,'v')),int(total))
    calls=[d for d in session(w).draws if d['name']=='physical_location']
    eq(len(calls),int(total)//2)

@step(r'a projectile bearing diagnostic of (\d+) degrees')
def bearing(w,value):w['bearing']=int(value)

@step(r'its flight direction is described')
def direction(w):w['direction']=artillery.artillery_direction(w['bearing'])

@step(r'description is (\w+)')
def direction_result(w,name):eq(w['direction'],name)

@step(r'smoke hex count is (\d+) mine count is (\d+) and center mine strength is (\d+)')
def modes_result(w,smoke,count,strength):
    board=session(w).map
    eq(sum(d['terrain']==SMOKE for d in board.decorations.values()),int(smoke))
    eq(len(board.mines),int(count))
    eq(next((m.strength for m in board.mines if (m.x,m.y)==(4,4)),0),int(strength))

def blast(w,**kwargs):
    defaults=dict(game_map=session(w).map,dam=10,singlehitsize=5,heatdam=0,
        tx=3,ty=3,tomsg='hit',otmsg='hit',tomsg1=None,otmsg1=None,table=damage.TABLE_PUNCH,
        safeup=2,safedown=1,isunderwater=False,engine=session(w).engine)
    defaults.update(kwargs)
    return call(w,damage.blast_hit_hexes,**defaults)

@step(r'a blast with damage 10 safeup 2 safedown 1 and ground-zero 0')
def blast_fixture(w):w['before']=armor(unit(w))

@step(r'target height is (-?\d+) and messages are (both|null-target|null-observer)')
def vertical(w,height,messages):
    unit(w).z=int(height)
    blast(w,tomsg=None if messages=='null-target' else 'hit',otmsg=None if messages=='null-observer' else 'hit')

@step(r'target blast armor loss is (\d+)')
def blast_result(w,value):eq(w['before']-armor(unit(w)),int(value))

@step(r'two MECH targets in roster order with the first facing blast from back and second from front')
def roster(w):
    for u in session(w).units.values():position(u,3,3)
    unit(w).facing=180
    unit(w,'v').facing=0
    w['rear_before']=unit(w,'v').sections[L.CTORSO].rear
    w['front_before']=unit(w,'v').sections[L.CTORSO].armor

@step(r'punch-table blast deals 5 damage to each and both location draws select torso')
def roster_blast(w):
    fx,fy=hex_to_float(3,3)
    tx,ty=hex_to_float(3,2)
    call(w,damage.blast_hit_hexf,session(w).map,5,5,0,fx,fy,tx,ty,'hit','hit',damage.TABLE_PUNCH,2,1,False,engine=session(w).engine)

@step(r'second target loses (\d+) rear armor and (\d+) front armor')
def rear_result(w,rear,front):
    s=unit(w,'v').sections[L.CTORSO]
    eq((w['rear_before']-s.rear,w['front_before']-s.armor),(int(rear),int(front)))

@step(r'a damage 12 radius-one blast with a target and undecorated woods in a neighboring hex')
def neighbor(w):
    position(unit(w,'v'),3,4)
    session(w).map.set_terrain(3,4,LIGHT_FOREST)
    w['before']=armor(unit(w,'v'))
    dice(w,'fire_duration',[60])

@step(r'neighbor messages are (both|null)')
def neighbor_hit(w,messages):blast(w,dam=12,doneighbors=1,tomsg1='hit' if messages=='both' else None,otmsg1='hit' if messages=='both' else None)

@step(r'neighbor target armor loss is (\d+) and neighbor woods fire is present')
def neighbor_result(w,value):
    eq(w['before']-armor(unit(w,'v')),int(value))
    eq(session(w).map.terrain(3,4),FIRE)

@step(r'a standard mine of strength (\d+) at a ground target hex')
def mine_fixture(w,value):
    mines.add_mine(session(w).map,3,3,int(value))
    w['before']=armor(unit(w))

@step(r'a step triggers it')
def step_mine(w):call(w,mines.possible_mine_poof,unit(w),'step')

@step(r'strength used is (\d+) and mine remains (\d+)')
def mine_result(w,strength,remaining):
    eq(w['before']-armor(unit(w)),int(strength))
    eq(len(session(w).map.mines),int(remaining))

@step(r'a mine-covered hex with elevation -2 and target height (-?\d+)')
def mine_height(w,height):
    session(w).map.set_elevation(3,3,2)
    unit(w).z=int(height)

@step(r'a (water|ice|ice-trigger) unit enters with mine reason (step|fall|land)')
def contact(w,kind,reason):
    session(w).map.set_terrain(3,3,WATER if kind=='water' else ICE)
    mines.map_add_mine(session(w).map,'3 3 '+('Trigger 1 0' if kind=='ice-trigger' else 'Standard 5'))
    count=call(w,mines.possible_mine_poof,unit(w),reason)
    w['contact_action']='none' if count==0 else 'script-request' if kind=='ice-trigger' else 'explode'

@step(r'trigger action is (none|explode|script-request)')
def contact_result(w,action):
    eq(w['contact_action'],action)
    if action=='script-request':eq(unit(w).external_effects[-1]['applied'],False)

@step(r'a 50-ton unit and vibra threshold (\d+)')
def vibra(w,threshold):
    unit(w).rtons=50*1024
    w['threshold']=int(threshold)

@step(r'the mine is (same-hex|remote-one-hex) relative to the unit')
def vibra_placement(w,placement):
    # Vertical neighbors have exactly one real hex of separation; diagonal
    # coordinates carry floating-point error on this engine's real grid.
    y=3 if placement=='same-hex' else 4
    mines.map_add_mine(session(w).map,f'3 {y} Vibra 5 {w["threshold"]}')
    w['count']=call(w,mines.possible_mine_poof,unit(w),'step')

@step(r'vibra explosion count is (\d+)')
def vibra_count(w,value):eq(w['count'],int(value))

@step(r'command mines with channels 7 7 8 and different creators')
def channels(w):
    for x,channel in ((5,7),(6,7),(7,8)):
        mines.map_add_mine(session(w).map,f'{x} 5 Command 5 {channel}',creator=x)

@step(r'channel (\d+) is detonated')
def detonate(w,channel):w['count']=call(w,mines.explode_mines,unit(w),int(channel))

@step(r'detonation count is (\d+) and remaining mine count is (\d+)')
def channel_result(w,count,remaining):eq((w['count'],len(session(w).map.mines)),(int(count),int(remaining)))

@step(r'light woods and an eligible (\S+)')
def forest_weapon(w,name):
    session(w).map.set_terrain(4,4,LIGHT_FOREST)
    w['ammo_mode']=A.AC_FLECHETTE_MODE if name.startswith('flechette-') else 0
    w['weapon']=get_weapon('IS.'+name.removeprefix('flechette-').replace('AC10','AC/10'))

@step(r'intentional ignition consumes roll (\d+)')
def ignition(w,value):
    dice(w,'terrain_rolls',[int(value)])
    dice(w,'fire_duration',[60])
    call(w,terrain.possibly_ignite,unit(w),w['weapon'].index,w['ammo_mode'],4,4,True)

@step(r'woods fire is (absent|present)')
def fire_result(w,value):eq(session(w).map.terrain(4,4)==FIRE,value=='present')

@step(r'(heavy|light) woods and a MediumLaser clearing hit of damage 8')
def clear_fixture(w,kind):session(w).map.set_terrain(4,4,HEAVY_FOREST if kind=='heavy' else LIGHT_FOREST)

@step(r'clear ignite-roll is (\d+) clear-roll is (\d+) and nested ignition-roll is (\d+)')
def clearing(w,ignite,clear,nested):
    dice(w,'terrain_rolls',[int(ignite),int(clear),int(nested)])
    dice(w,'fire_duration',[60])
    call(w,terrain.possibly_clear,unit(w),get_weapon('IS.MediumLaser').index,0,8,4,4,True)

@step(r'terrain result is (unchanged|burning-heavy|light-woods)')
def clear_result(w,value):
    eq(session(w).map.terrain(4,4),{'unchanged':HEAVY_FOREST,'burning-heavy':FIRE,'light-woods':LIGHT_FOREST}[value])

@step(r'a mine at a successfully cleared forest hex')
def cleared_mine(w):
    clear_fixture(w,'heavy')
    mines.add_mine(session(w).map,4,4,5)
    clearing(w,'6','8','5')
    eq(session(w).map.terrain(4,4),LIGHT_FOREST)

@step(r'source possibly-remove-mines is reached')
def no_clear(w):call(w,mines.possibly_remove_mines,unit(w),4,4)

@step(r'mine count remains (\d+)')
def mine_count(w,value):eq(len(session(w).map.mines),int(value))

@step(r'intentional clearing uses ignite-roll 6 clear-roll 8 and replacement draw (\d+)')
def replacement(w,value):
    dice(w,'terrain_replacement',[int(value)])
    clearing(w,'6','8','5')

@step(r'terrain is (rough|grassland) and exactly one replacement draw was consumed')
def replacement_result(w,value):
    eq(session(w).map.terrain(4,4),ROUGH if value=='rough' else GRASSLAND)
    eq(len([d for d in session(w).draws if d['name']=='terrain_replacement']),1)
