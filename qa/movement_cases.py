"""Literal feature expectations and UI workflow construction; no engine imports."""
from copy import deepcopy


def command(name, *args, unit='A'):
    return {'op': 'command', 'unit': unit, 'name': name, 'args': [str(v) for v in args]}


def advance(seconds): return {'op': 'advance', 'seconds': int(seconds)}
def inspect(unit='A'): return {'op': 'inspect', 'unit': unit}
def stim(op, **kwargs): return {'op': op, **kwargs}
def flag(value): return {'True': True, 'False': False}[value]
def accepted(row): return row['outcome'] == 'ACCEPTED'
def unit_path(*path, unit='A', action=-1): return ['results', action, 'snapshot', 'units', unit, *path]
def result_path(*path, action=-1): return ['results', action, *path]
def check(path, value, comparison='equal'): return {'path': path, 'value': value, 'comparison': comparison}
def ucheck(key, value, **kwargs): return check(unit_path(key, **kwargs), value)
def timer(name, pending, **kwargs): return check(unit_path('timers', **kwargs), name, 'contains' if pending else 'absent')
def hexagon(x, y, terrain, elevation=0): return {'at': [x, y], 'terrain': terrain, 'elevation': elevation}


def base(unit=None, actions=None):
    return {'units': [unit or {}], 'actions': actions or [], 'random': {}}


def mode_bits(mode): return [] if mode == 'NONE' else [{'SPRINT':'sprinting','EVADE':'evading','DODGE':'dodging'}[mode]]


def modes(index, row):
    d, checks = base(), []
    u = d['units'][0]
    if index == 0:
        u.update({'class': row['unit'], 'states': mode_bits(row['initial'])})
        d['actions'] = [command(row['mode']), advance(row['ticks'])]
        checks = [ucheck('mode', row['active']), ucheck('pending_transition', row['pending'])]
    elif index == 1:
        condition = row['condition']
        states = []
        if condition in ('FORTIFIED', 'FALLEN', 'JUMPING', 'SPRINTING', 'CHARGING', 'WEAPON_RECYCLE', 'LIMB_RECYCLE'):
            states = [condition.lower()]
        elif condition == 'OOD': u['cocoon'] = 11
        elif condition == 'STANDING':
            states = ['fallen']; d['random']['pilot_rolls'] = [12]
            d['actions'].append(command('stand'))
        elif condition in ('TOWING', 'MOUNTED'):
            d['units'].append({'id':'B', 'at':[4,4,0]})
            if condition == 'TOWING': u['load'] = {'tow':'B'}
            else: states = ['mounted']
        elif condition.startswith('IN_WATER'):
            d['map'] = {'hexes':[hexagon(3,3,'WATER',1)]}
            u['at'] = [3,3,-1]
            if condition.endswith('SPRINTING'): states = ['sprinting']
        elif condition.startswith('HIP_DISABLED'):
            states = ['hip_disabled'] + (['evading'] if condition.endswith('EVADING') else [])
        elif condition == 'NO_DODGE_ADVANTAGE': u['advantages'] = ['maneuvering_ace']
        elif condition == 'OTHER_PILOT': u['caller_id'] = 'Other'
        elif condition == 'CHANGING_MODE': d['actions'].append(command('sprint'))
        elif condition in ('LEFT_LEG_DESTROYED', 'QUAD_FRONT_LEG_DESTROYED'):
            loc = 'LLEG' if condition == 'LEFT_LEG_DESTROYED' else 'LARM'
            u['sections'] = [{'location':loc, 'internal':0}]
            if loc == 'LARM': u['movement'] = 'QUAD'
        else: raise ValueError(condition)
        u['states'] = states
        d['actions'].append(command(row['mode']))
        checks = [check(result_path('accepted'), accepted(row))]
        # CHANGING_MODE retains the old event; the rejected request creates none.
        checks.append(check(result_path('new_timers'), ['MOVEMODE'] if flag(row['scheduled']) else []))
    elif index == 2:
        d['actions'] = [command(row['mode'])]
        if row['condition'] == 'SHUTDOWN': d['actions'].append(command('shutdown'))
        elif row['condition'] == 'DESTROYED':
            d['actions'].append(stim('damage',unit='A',attacker='A',section='CTORSO',external=3000,internal=0))
        else:
            # Apply a real weapon-recycle stimulus to exercise this callback.
            d['units'].append({'id':'B','team':2,'at':[3,3,0]})
            if row['condition'] == 'LIMB_RECYCLE':
                d['units']=[{}]
                d['actions'].append(stim('limb_use',unit='A',location='LLEG',seconds=30))
            else:
                d['units'][1]['at']=[3,2,0]
                d['actions']=[stim('scan',unit='A'),advance(2),
                    stim('fire',unit='A',target='B',weapon='IS.MediumLaser',roll=2),command(row['mode'])]
        d['actions'].append(advance(30))
        checks = [ucheck('mode', row['active']), ucheck('pending_transition','NONE')]
        if row['condition']=='LIMB_RECYCLE':
            checks.extend([check(result_path('accepted',action=0),True),
                           check(unit_path('sections','LLEG','recycle',action=1),30)])
        if row['condition']=='WEAPON_RECYCLE':
            checks.extend([check(result_path('weapon_recycle',action=2),0,'greater'),
                           check(result_path('accepted',action=3),True)])
    elif index == 3:
        u.update(states=mode_bits(row['mode']), speed=float(row['speed']))
        d['actions'] = [inspect()]
        checks = [check(result_path('queries','A','movement_heat'),float(row['heat']))]
    return d, checks


def hulldown(index, row):
    d = base({'movement':row.get('movement','QUAD'), 'speed':float(row.get('speed',0))})
    if index == 0:
        d['actions'] = [command('hulldown')]
        return d, [check(result_path('accepted'),accepted(row)),timer('HULLDOWN',flag(row['scheduled']))]
    workflow = row['workflow']
    if workflow.startswith('RAISE'): d['units'][0]['states'] = ['hulldown']
    d['actions'] = [command('hulldown', *(['-'] if workflow.startswith('RAISE') else []))]
    if workflow.endswith('_STOP'): d['actions'].append(command('hulldown','stop'))
    if workflow.endswith('_SHUTDOWN'): d['actions'].append(command('shutdown'))
    d['actions'].append(advance(row['ticks']))
    return d, [ucheck('hulldown',flag(row['active'])),timer('HULLDOWN',flag(row['pending']))]


def controls(index, row):
    d = base()
    if index == 0:
        d['actions'] = [command('speed',row['request'])]
        checks = [ucheck('desired_speed',float(row['desired'])),ucheck('speed',0)]
    elif index == 1:
        d['actions'] = [command('heading',row['heading']),command('lateral',row['lateral']),advance(6)]
        checks = [ucheck('desired_facing',int(row['desired'])),ucheck('lateral',int(row['offset'])),ucheck('lateral_description',row['description'])]
    elif index == 2:
        d['actions'] = [command('lateral','fl'),advance(2),command('lateral',row['request']),advance(int(row['tick'])-2)]
        checks = [ucheck('lateral',int(row['offset'])),timer('LATERAL',flag(row['pending']))]
    elif index == 3:
        d['units'] = [{'class':'VTOL','movement':'VTOL','at':[3,3,2], 'max_speed':53.75,'desired_speed':32.25}]
        d['actions'] = [command('vertical',row['request'])]
        checks = [check(result_path('accepted'),accepted(row)),ucheck('vertical_speed',float(row['vertical']))]
    else:
        d['map'] = {'size':[10,10]}
        d['units'] = [{'speed':float(row['speed']),'target_hex':[3,7]}]
        d['actions'] = [command('eta')]
        checks = [check(result_path('eta'),row['eta'],'contains')]
    return d, checks


def maneuvers(index,row):
    d = base()
    if index == 0:
        d['units'] = [{'tons':int(row['tons']),'speed':float(row['speed'])*10.75,'facing':int(row['facing'])}]
        d['random'] = {'pilot_rolls':[12]}
        d['actions'] = [command('bootlegger',row['direction'])]
        checks = [ucheck('piloting_modifier',int(row['modifier'])),ucheck('facing',int(row['heading'])),
                  ucheck('desired_facing',int(row['heading'])),ucheck('speed',float(row['remaining'])*10.75)]
        for leg in ('LLEG','RLEG'): checks.append(check(unit_path('sections',leg,'recycle'),30))
    elif index == 1:
        d['units'] = [{'speed':float(row['speed'])}]
        if row['roll'] != 'UNUSED': d['random'] = {'pilot_rolls':[12 if row['roll']=='PASS' else 2,12], 'fall_directions':[1]}
        d['actions'] = [command('prone')]
        checks = [ucheck('fallen',True),ucheck('speed',0),ucheck('desired_speed',0),ucheck('last_fall_levels',int(row['levels']))]
        if row['roll']=='UNUSED': checks.append(check(['consumed','pilot_rolls'],0))
        if row['roll']=='PASS': checks.append(check(['consumed','fall_directions'],0))
    else:
        enemy = {'id':'B','class':'BSUIT','team':2,'relative_position':{'to':'A','bearing':0,'range':float(row['range'])}}
        if row['state']=='OOD': enemy['cocoon']=11
        elif row['state']=='FRIENDLY': enemy['team']=1
        elif row['state'] in ('JUMPING','MOUNTED'): enemy['states']=[row['state'].lower()]
        d['units'] = [{'states':['fallen']},enemy]
        d['random'] = {'pilot_rolls':[12]}
        d['actions'] = [command('thrash')]
        checks = [check(result_path('damage_by_unit','B'),int(row['damage']))]
        for limb in ('LLEG','RLEG','LARM','RARM'): checks.append(check(unit_path('sections',limb,'recycle'),60))
        if int(row['damage']): checks.append(check(result_path('damage_clusters'),[5,5,5,1],'clusters'))
    return d,checks


def cargo(index,row):
    d = base(actions=[inspect(),inspect()])
    if index == 0:
        enh = row['enhancements']
        d['units'][0]['states'] = [name for token,name in (('MASC','masc'),('SUPERCHARGER','supercharger'),('SPRINT','sprinting')) if token in enh]
        if 'SPEED_DEMON' in enh: d['units'][0]['advantages']=['speed_demon']
        d['units'][0]['load']={'cache_valid':True}
    else:
        # A MECH without cargo tech multiplies raw carried cargo by two.
        d['units'][0].update(actual_tons=float(row['actual']),load={'cargo_tons':float(row['load'])/2})
    return d,[check(result_path('queries','A','effective_max_speed',action=i),float(row['speed'])) for i in (0,1)]


def neighbors(x,y):
    return [(x,y-1),(x+1,y-(x%2)),(x+1,y+1-(x%2)),(x,y+1),(x-1,y+1-(x%2)),(x-1,y-(x%2))]


def ice_cases(index,row):
    d={'units':[], 'map':{}, 'actions':[], 'random':{}}
    checks=[]
    if index in (0,1):
        center = 'WATER' if index==0 else 'ICE'
        neighbor = 'BRIDGE' if index==0 else 'ICE'
        coordinates = neighbors(3,3)[:int(row['neighbors'])]
        d['map']['hexes']=[hexagon(3,3,center,1)]+[hexagon(x,y,neighbor,1) for x,y in coordinates]
        d['random']['percentage_draws'] = ([int(row['draw'])] if index==0 else
            [int(row['draw']) if xy==(3,3) else 100 for xy in sorted(coordinates+[(3,3)])])
        d['random']['neighbor_d6' if index==0 else 'neighbor_d3']=[int(row['die'])]
        d['actions']=[stim('ice',name='addice' if index==0 else 'delice',args=[row['percent']])]
        checks=[check(result_path('hexes','3,3','terrain'),row['terrain']),check(result_path('changed_hexes'),int(row['count']))]
    elif index==2:
        d['map']['hexes']=[hexagon(3,3,'WATER',int(row['depth']))]
        d['random']['percentage_draws']=[1]
        d['actions']=[stim('ice',name='addice',args=['100']),stim('path_cost',mode='mech',**{'from':[2,3],'to':[3,3]})]
        checks=[check(result_path('cost'),int(row['cost'])),check(result_path('hexes','3,3','terrain'),'ICE'),check(result_path('hexes','3,3','elevation'),int(row['depth']))]
    elif index==3:
        d['map']['hexes']=[hexagon(x,y,'WATER',1) for x,y in ((3,3),(3,4),(4,3))]
        d['random']={'percentage_draws':[1,1,1],'neighbor_d6':[int(row['first']),2,2]}
        d['actions']=[stim('ice',name='addice',args=['100'])]
        checks=[check(result_path('hexes','3,3','terrain'),row['terrain']),check(result_path('changed_hexes'),int(row['count'])),check(['consumed','neighbor_d6'],3)]
        for xy in ('3,4','4,3'): checks.append(check(result_path('hexes',xy,'terrain'),'WATER'))
    else:
        side=int(row['side']); d['map']={'size':[side,side],'default':['ICE',1]}
        d['random']={'percentage_draws':[1]*(side*side),'neighbor_d3':[3]*(side*side)}
        d['actions']=[stim('ice',name='delice',args=['100'])]
        checks=[check(result_path('terrain_counts','WATER'),int(row['count'])),check(result_path('terrain_counts','ICE'),0),check(['consumed','neighbor_d3'],0)]
    return d,checks


def surfaces(index,row):
    d=base()
    if index==0:
        d['map']={'hexes':[hexagon(4,3,row['terrain'],int(row['elevation']))], 'bridge_protection':flag(row['protected'])}
        d['random']={'surface_draws':[int(row['draw'])]}
        d['actions']=[stim('hit_hex',attacker='A',at=[4,3],weapon_damage=int(row['damage']))]
        checks=[check(result_path('hexes','4,3','terrain'),row['result']),check(result_path('hexes','4,3','elevation'),int(row['stored']))]
    elif index==1:
        d['map']={'hexes':[hexagon(3,3,'ICE',2)]}
        d['units']=[{'at':[3,3,-1]}, {'id':'B','class':row['unit'],'movement':row['movement'],'at':[3,3,int(row['z'])], 'states':['waterproof'] if flag(row['waterproof']) else []}]
        d['random']={'pilot_rolls':[12], 'fall_directions':[1]}
        d['actions']=[stim('surface',unit='A',name='break_up')]
        checks=[ucheck('terrain','WATER',unit='B'),ucheck('last_fall_levels',int(row['levels']),unit='B'),ucheck('destroyed',flag(row['destroyed']),unit='B')]
    else:
        d['map']={'hexes':[hexagon(3,3,'ICE',2)]}
        d['units']=[{'class':row['unit'],'movement':row['movement']}]
        d['random']={'ice_d6':[int(row['die'])],'pilot_rolls':[12],'fall_directions':[1]}
        d['actions']=[stim('surface',unit='A',name='drop_chance')]
        checks=[check(result_path('hexes','3,3','terrain'),row['terrain']),check(result_path('dropped'),flag(row['dropped']))]
    return d,checks


def orbital(index,row):
    d=base({'jump_mp':0},[])
    d['random']={'pilot_rolls':[12,12],'fall_directions':[1]}
    checks=[]
    if index==0:
        d['actions']=[command('ood',3,3,row['height']),advance(row['ticks'])]
        checks=[check(unit_path('at',2),int(row['z'])),ucheck('cocoon',int(row['cocoon'])),timer('OOD',flag(row['pending']))]
    elif index==1:
        d['units'][0]['jump_mp']=float(row['jump'])
        d['actions']=[command('ood',3,3,20),stim('cocoon_hit',unit='A',attacker='A',damage=int(row['damage']))]
        checks=[ucheck('cocoon',int(row['cocoon'])),timer('OOD',flag(row['ood'])),timer('FALL',flag(row['fall']))]
    elif index==2:
        d['map']={'hexes':[hexagon(3,3,row['terrain'],0)]}
        rescued=int(row['cocoon'])==-1
        d['units'][0]['jump_mp']=1 if rescued else 0
        d['actions']=[command('ood',3,3,1 if rescued else 0)]
        if int(row['cocoon']) in (1,-1): d['actions'].append(stim('cocoon_hit',unit='A',attacker='A',damage=11 if rescued else 10))
        d['actions'].append(advance(1))
        d['random']['pilot_rolls']=[int(row['roll']),12]
        checks=[ucheck('required_roll',int(row['target'])),ucheck('last_fall_levels',int(row['levels']))]
    elif index==3:
        d['units'][0].update(jump_mp=1, sections=[{'location':'CTORSO','front':20,'original_front':20}])
        d['actions']=[command('ood',3,3,20)]
        if int(row['initial'])<0: d['actions'].append(stim('cocoon_hit',unit='A',attacker='A',damage=11))
        d['random']['interception_rolls']=[int(row['roll'])]
        d['actions'].append(stim('damage',unit='A',attacker='A',section='CTORSO',external=5,internal=0))
        checks=[ucheck('cocoon',int(row['cocoon'])),check(unit_path('sections','CTORSO','front'),int(row['armor']))]
    else:
        d['actions']=[command('ood',3,3,7),stim('cocoon_hit',unit='A',attacker='A',damage=11),advance(row['ticks'])]
        checks=[check(unit_path('at',2),int(row['height'])),timer('FALL',flag(row['pending'])),timer('OOD',False),ucheck('last_fall_levels',int(row['levels']))]
        if int(row['levels']): checks.append(check(result_path('damage_by_unit','A'),55))
    return d,checks


def settling(index,row):
    d=base()
    if index==0:
        terrain=row['terrain']; depth=1 if terrain=='WATER' else 0
        d['map']={'hexes':[hexagon(3,3,terrain,depth)], 'gravity':int(row['gravity']),'special_rules':True}
        d['units']=[{'tons':int(row['tons']),'facing':350,'at':[3,3,-depth]}]
        d['random']={'pilot_rolls':[12],'fall_directions':[int(row['direction'])]}
        d['actions']=[stim('fall',unit='A',levels=int(row['levels']))]
        checks=[check(result_path('fall','damage_taken'),int(row['damage'])),ucheck('facing',int(row['facing'])),ucheck('desired_facing',int(row['facing']))]
    elif index==1:
        d['map']={'hexes':[hexagon(3,3,'WATER',int(row['depth']))]}
        d['units']=[{'movement':row['movement'],'at':[3,3,-int(row['depth'])], 'states':['fallen'] if row['posture']=='FALLEN' else [],
            'sections':[{'location':row['section'],'front':int(row['front']),'rear':int(row['rear']), 'original_rear':int(row['original'])}]}]
        d['random']={'pilot_rolls':[12,12], 'fall_directions':[1]}
        d['actions']=[stim('flood',unit='A'),stim('flood',unit='A')]
        checks=[check(unit_path('sections',row['section'],'flooded'),flag(row['flooded'])),check(result_path('damage_by_unit','A'),0)]
    else:
        w=row['workflow']
        if w in ('INTACT_JUMP','EARLY_LAND'):
            d['actions']=[command('jump',0,1)]
            if w=='EARLY_LAND':
                d['random']={'pilot_rolls':[12]}; d['actions'].append(command('land'))
                checks=[ucheck('jumping',False),timer('JUMPSTABIL',True),check(['consumed','pilot_rolls'],1)]
            else:
                d['actions'].append(advance(20))
                checks=[ucheck('jumping',False),check(['consumed','pilot_rolls'],0)]
        else:
            d['units'][0]['states']=['fallen']
            if w=='QUAD_STAND': d['units'][0]['movement']='QUAD'
            if w=='STAND_BTH_13': d['units'][0]['pilot_skill']=13
            if w=='STAND_CAREFUL': d['random']={'pilot_rolls':[12]}
            arg={'STAND_CHECK':['check'],'STAND_CAREFUL':['careful']}.get(w,[])
            d['actions']=[command('stand',*arg)]
            if w=='QUAD_STAND':
                d['actions'].append(advance(10)); checks=[ucheck('fallen',False),timer('STAND',False),check(['consumed','pilot_rolls'],0)]
            elif w=='STAND_CHECK': checks=[ucheck('fallen',True),timer('STAND',False),check(result_path('message'),'BTH','contains')]
            elif w=='STAND_BTH_13': checks=[check(result_path('accepted'),False),check(result_path('message'),'anyway','contains')]
            else: checks=[check(result_path('pilot_rolls',0,'target'),3),check(unit_path('timers','STAND'),20)]
    return d,checks


FACTORIES={'modes':modes,'hulldown':hulldown,'controls':controls,'maneuvers':maneuvers,
           'cargo':cargo,'ice':ice_cases,'surfaces':surfaces,'orbital':orbital,'settling':settling}
