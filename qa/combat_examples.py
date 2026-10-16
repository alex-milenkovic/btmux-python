"""Independent fixtures and assertions for the current APS combat examples."""
from combat_support import *

def ranges(n,p):
    d=fixture(False);mount(d,range_min=0,range_short=3,range_medium=6,range_long=9)
    if n in (1,2):
        d['units'][1]['status2']={'ordinary':0,'stealth':64,'nullsig':128}[p['signature']]
        options=dict(weapon=0,target='v',distance=float(p.get('range',p.get('actual'))))
        if n==2:options['network_range']=float(p['network'])
        d['actions']=[diag('combat-range',**options)]
        return [Case(d,lambda o:checks((o['results'][0]['bracket'],p['bracket']),(o['results'][0]['modifier'],int(p['modifier']))))]
    if n==3:
        d['units'][0]['weapons']=[];mount(d,'IS.Sniper',crits=1,range_long=75)
        d['units'][0].update(artillery=4,fire_adjustment=int(p['adjustment']))
        if p['path']=='indirect-other':
            d['units'][1]['spotting']=int(p['skill'])
            d['actions']=[configure(spotter='v')]
        if p['path']=='underwater':
            d['units'][0]['at']=[3,3,-2];d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-2)]
        d['actions'].append(diag('artillery-bth',weapon=0,distance=20,indirect=p['path'].startswith('indirect')))
        return [Case(d,lambda o:eq(o['results'][-1]['bth'],int(p['bth'])))]
    raise ValueError(('ranges',n))

def modes(n,p):
    d=fixture();word='firemode'
    if n==1:
        for i in range(3):mount(d,'IS.UltraAC/5',index=i,crits=1)
        d['actions']=[cmd('ultra',p['selector'])]
        expected=[] if p['selected']=='none' else list(map(int,p['selected'].split(',')))
        return [Case(d,lambda o:eq([i for i in range(3) if rawslot(o,index=i)['firemode']&1024],expected),mode='normal')]
    if n==2:
        rac=p['weapon']=='RAC';word='firemode' if rac else 'ammomode'
        bits={'none':0,'RAC2':8192,'RAC6':32768,'HAYWIRE':1024,'ECM':2048,'NEMESIS':4096}
        mount(d,'IS.RotaryAC/5' if rac else 'IS.iNarcBeacon',fire=bits[p['initial']] if rac else 0,mode=0 if rac else bits[p['initial']],crits=1)
        d['actions']=[cmd('rac' if rac else 'inarc',*p['text'].split())]
        return [Case(d,lambda o:eq(rawslot(o)[word],bits[p['mode']]),mode='normal')]
    if n==3:
        profile=p['profile'];name={'SRM':'IS.SRM-2','artillery':'IS.Sniper','rocket':'IS.RL-10'}.get(profile,'IS.LRM-5')
        fire=256 if profile=='one-shot-LRM' else 0
        mount(d,name,fire=fire,crits=1)
        d['actions']=[cmd(p['command'],'0')]
        return [Case(d,lambda o:eq(o['results'][0]['accepted'],p['decision']=='accepted'),mode='normal')]
    raise ValueError(('modes',n))

def physicals(n,p):
    d=fixture(False)
    if n==1:
        d['units'][0].update(tonnage=55,heat=int(p['heat']),specials=1)
        d['actions']=[diag('physical-damage',target='v',attack=p['attack'],weight=7 if p['attack']=='claw' else 10,glancing=bool(int(p['glance'])))]
        return [Case(d,lambda o:checks((o['results'][0]['damage_dealt'],int(p['damage'])),(loss(o),int(p['damage']))))]
    if n==3:
        d['units'][1]['at']=[3,4,0]
        d['actions']=[diag('physical-damage',target='v',attack=p['attack'])]
        return [Case(d,lambda o:checks((o['results'][0]['location_hit'],0),(o['results'][0]['is_rear'],False),(draws(o,'physical_location'),[]),(draws(o,'hit_location_rolls'),[]),(state(o,'v')['sections'][0]['armor'],193 if p['attack']=='saw' else 195)))]
    if n==2:
        d['units'][1]['class']=p['target'];d['units'][0]['prefs']=1
        # Exact real coordinate separation bypasses only grid quantization.
        d['units'][1]['at']=[3,3,0]
        d['actions']=[diag('physical-attack',target='v',attack='punch',section='RA',weight=10,bth=2,roll=12)]
        # Real coordinate units are the documented map scale (range 1 = 322.5).
        d['units'][0]['real']=[1024.0750399750987,967.5,0];d['units'][1]['real']=[1024.0750399750987,967.5-float(p['range'])*322.5,0]
        return [Case(d,lambda o:eq(o['results'][0]['success'],p['eligible']=='accepted'))]
    raise ValueError(('physicals',n))

def groups(n,p):
    d=fixture()
    if n in (1,2):
        for i in range(3 if n==1 else 5):mount(d,index=i,crits=1)
        d['units'][0]['tics']=[list(range(3 if n==1 else 5))]
        d['actions']=[cmd('deltic' if n==1 else 'listtic',*(p['text'].split() if n==1 else ['0']))]
        if n==1:return [Case(d,lambda o:eq(state(o)['tics'][0],[] if p['members']=='none' else list(map(int,p['members'].split(',')))),mode='normal')]
        return [Case(d,lambda o:eq([row[0] for row in o['results'][0]['result'][0]],list(map(int,p['order'].split(',')))),mode='normal')]
    if n==3:
        recoil=p['change']=='falls-from-heavy-Gauss-recoil'
        mount(d,'IS.HeavyGaussRifle' if recoil else 'IS.MediumLaser',crits=1,ammo=10 if recoil else None)
        # Source numbering walks sections; the CT interruption weapon must
        # precede both later weapons, independent of fixture insertion order.
        mount(d,loc=5,index=4,crits=1);mount(d,loc=6,index=4,crits=1)
        d['units'][0]['tics']=[[0,1],[2]]
        if recoil:
            d['units'][0]['speed']=1;d['random']['streams'].update(attack_rolls=[12],pilot_rolls=[2]*100)
        else:
            slot(d,4,firemode=8,weap_damage_flags=4);section(d,4,internal=1)
            d['random']['streams']['attack_rolls']=[2]
        d['actions']=[cmd('firetic','0,1')]
        def check(o):
            eq(len(draws(o,'attack_rolls')),1)
            checks((rawslot(o,5,4)['data'],0),(rawslot(o,6,4)['data'],0))
            assert state(o)['fallen'] if recoil else not state(o)['started']
        return [Case(d,check,mode='normal')]
    raise ValueError(('groups',n))

def missiles(n,p):
    d=fixture(False)
    if n==1:
        boundary=p['boundary'];swarm=boundary=='ordinary-swarm-hit'
        mount(d,'IS.SRM-6',ammo=20,mode=128 if swarm else 0)
        mount(d,'IS.Anti-MissileSystem',unit=1,ammo=2,heat=1,vrt=4)
        d['units'][1].update(status=8|2048,specials=4)
        d['random']['streams'].update(attack_rolls=[2 if boundary=='ordinary-fire-miss' else 12],ams_rolls=[5],missile_pre_roll=[3]*30,missile_cluster=[12]*10,swarm_rolls=[12]*10)
        if boundary.startswith('ordinary'):d['actions']=[cmd('fire','0')]
        else:d['actions']=[diag('missile-hit',weapon=0,target='v',bth=7,roll=2 if boundary=='direct-missile-miss' else 12,incoming=6)]
        def check(o):
            r=o['results'][0].get('attack',o['results'][0])
            checks((rounds(o,'v'),int(p['ammo'])),(state(o,'v')['weap_heat'],float(p['heat'])),(rawslot(o,name='v')['data'],int(p['recycle'])),(r['ams_shot_down'],int(p['shotdown'])))
            eq(draws(o,'ams_rolls'),[] if boundary.startswith('ordinary') else [5])
        return [Case(d,check,mode='normal' if boundary.startswith('ordinary') else 'diagnostic')]
    if n==2:
        mount(d,'IS.LRM-5');d['random']['streams'].update(missile_pre_roll=[1,2,3],missile_cluster=[int(p['roll'])])
        d['actions']=[diag('missile-index',weapon=0,target='v',glancing=bool(int(p['glance'])))]
        return [Case(d,lambda o:checks((o['results'][0]['index'],int(p['index'])),(draws(o,'missile_pre_roll'),[1,2,3]),(draws(o,'missile_cluster'),[int(p['roll'])])))]
    if n==3:
        condition=p['condition'];d['units'][0]['at']=[3,7,0]
        b=dict(name='B',team=2,at=[3,1,0]);c=dict(name='C',team=2,at=[4,2,0]);d['units'] += [b,c]
        if condition.startswith('enemy-at-'):b['real']=[1024.0750399750987,645-float(condition.split('-')[-1])*322.5,0]
        if condition=='enemy-at-1.9':
            # Source FindRange returns float32. Nominal 1.9 rounds inside the
            # strict boundary; this adjacent coordinate rounds just outside.
            # The accepted generated fixture already uses the same convention.
            b['real'][1]=32.24994
        if condition=='combat-safe':b['status']=8|0x400000
        if condition.startswith('friendly'):b['team']=d['units'][0].get('team',0)
        if condition=='no-LOS':d['map']['hexes']=[dict(at=[3,1],terrain='BUILDING',elevation=9)]
        visited=['v','B'] if condition=='already-visited' else ['v']
        d['actions']=[diag('swarm-next',target='v',visited=visited,enemy_only=condition=='friendly-with-SWARM1')]
        return [Case(d,lambda o:eq(o['results'][0]['target'],p['next']))]
    raise ValueError(('missiles',n))

def artillery(n,p):
    d=fixture(False)
    if n==4:
        d['actions']=[diag('artillery-direction',bearing=int(p['bearing']))]
        return [Case(d,lambda o:eq(o['results'][0]['direction'],p['direction']))]
    if n==1:
        # The clock workflow uses exact grid distances where representable;
        # fractional range also independently checks the public arithmetic.
        distance=float(p['range']);d['map']['size']=[12,120]
        d['units'][0]['at']=[3,110,0];d['units'][0]['artillery']=0
        target_y=110-int(distance)
        mount(d,'IS.Sniper',ammo=20,crits=1,range_long=120)
        d['actions']=[diag('artillery-flight',range=distance),diag('artillery-launch',weapon=0,x=3,y=target_y),inspect(),advance(int(p['before'])),inspect(),advance(int(p['due'])-int(p['before'])),inspect()]
        d['random']['streams']['attack_rolls']=[12]
        return [Case(d,lambda o:checks((o['results'][0]['delay'],int(p['due'])),(len(o['results'][4]['map']['artillery_impacts']),0),(len(o['results'][6]['map']['artillery_impacts']),1)))]
    modes={'SMOKE':32,'MINE':16,'CLUSTER':8}
    mode=8 if n==3 else sum(modes[m] for m in p['mode'].split('+')) if n==5 else 0
    damage=int(p['damage']) if n==3 else 1 if n==5 else 10
    mount(d,'IS.Sniper',ammo=20,mode=mode,damage=damage,crits=1)
    d['units'][1]['at']=[4,4,0]
    d['random']['streams'].update(artillery_cluster=[0]*(4*damage),smoke_duration=[120]*7)
    d['actions']=[diag('artillery-launch',weapon=0,x=4,y=4),inspect()]
    if n==2:
        if p['change']=='moves':d['actions'].append(dict(op='place',unit='u',at=[6,6,0]))
        if p['change']=='changes-lock':d['actions'].append(cmd('lock','7','7','H'))
        if p['change']=='changes-ammo-mode':d['actions'].append(cmd('cluster','0'))
        if p['change']=='is-destroyed':d['actions'].append(diag('destroy-section',section=4))
    d['actions'] += [advance(9),inspect(),advance(1),inspect()]
    def check(o):
        before=o['results'][-3]['map'];after=o['state']['map']
        checks((len(before['projectiles']),1),(len(before['artillery_impacts']),0),(len(after['projectiles']),0),(len(after['artillery_impacts']),1))
        if n==2:
            checks((loss(o),10),(after['artillery_impacts'][0]['x'],4),(after['artillery_impacts'][0]['y'],4))
        if n==3:
            checks((loss(o),int(p['total'])),(len(draws(o,'damage_entry')),damage),(draws(o,'artillery_cluster'),[0]*(4*damage)))
        if n==5:
            checks((len(after['decorations']),int(p['smoke'])),(len(after['mines']),int(p['mines'])),(after['mines'][0]['strength'] if after['mines'] else 0,int(p['strength'])))
    return [Case(d,check)]

def boosters(n,p):
    d=fixture(False);d['units'][0]['specials']=16
    d['random']['streams']['booster_rolls']=[12 if n in (1,2) else 2]
    if n==1:
        d['units'][0]['desired_speed']=30
        d['actions']=[cmd('masc'),advance(2),cmd('masc'),advance(int(p['tick'])-2)]
        return [Case(d,lambda o:checks((state(o)['desired_speed'],30.0),(state(o)['status']&0x100000,0),(state(o)['masc_counter'],int(p['counter']))),mode='normal')]
    if n==2:
        name='masc' if p['equipment']=='MASC' else 'scharge'
        if name=='scharge':d['units'][0]['specials2']=64
        d['actions']=[cmd(name),advance(1)]
        return [Case(d,lambda o:checks((state(o)['masc_counter'],1),(state(o)['scharge_counter'],0),([e['deadline'] for e in events(o,kind='MASC_FAIL' if name=='masc' else 'SCHARGE_FAIL')],[61])),mode='normal')]
    if n==3:
        d['units'][0].update(speed=float(p['speed']),desired_speed=float(p['speed']),movement='QUAD' if p['chassis']=='quad' else 'BIPED')
        d['actions']=[cmd('masc'),advance(1)]
        def check(o):
            u=state(o)
            checks((u['specials']&16,0),(u['speed'],0.0),(u['max_speed'],0.0),(u['desired_speed'],0.0),
               (sum(bool(u['sections'][i]['slots'][0]['firemode']&1) for i in (0,1,5,6)),int(p['hips'])),(bool(u['status']&128),bool(int(p['fall']))))
        return [Case(d,check,mode='normal')]
    if n==4:
        d['units'][0].update(started=False,masc_counter=int(p['initial']))
        d['pending_events']=[dict(unit='u',callback='booster',data='masc',delay=1)]
        d['actions']=[advance(1)]
        return [Case(d,lambda o:checks((state(o)['masc_counter'],int(p['final'])),(state(o)['specials']&16,16),(events(o,kind='MASC_FAIL'),[]),(draws(o,'booster_rolls'),[2])))]
    raise ValueError(('boosters',n))

def equipment(n,p):
    d=fixture(False);u=d['units'][0]
    if n==1:
        name=p['command'];bit={'stealtharmor':64,'nullsig':128,'slite':32}.get(name)
        if name=='stealtharmor':u.update(specials2=1,equipment=['Guardian'])
        if name=='nullsig':u['specials2']=16
        if name=='fixturret':u.update(**{'class':'GROUND'},tank_crit_status=2)
        if name=='slite':u['equipment']=['searchlight']
        d['actions']=[cmd(name),advance(int(p['before'])),inspect(),advance(int(p['due'])-int(p['before'])),inspect()]
        def check(o):
            eq(o['results'][0]['accepted'],True)
            before=state(o,index=2);after=state(o)
            if bit:checks((bool(before['status2']&bit),False),(bool(after['status2']&bit),True))
            elif name=='dig':checks((before['dug_in'],False),(after['dug_in'],True))
            elif name=='fixturret':checks((before['tank_crit_status']&2,2),(after['tank_crit_status']&2,0))
            else:assert before['status']!=after['status'] or before['status2']!=after['status2'] or before['crit_status']!=after['crit_status'], 'cutoff did not transition'
        return [Case(d,check,mode='normal')]
    if n==2:
        name='stealtharmor' if p['system']=='stealth' else 'nullsig';u['specials2']=1 if name=='stealtharmor' else 16
        if name=='stealtharmor':u['equipment']=['Guardian']
        d['actions']=[cmd(name)]
        if p['condition']=='shutdown':d['actions'].append(cmd('shutdown'))
        elif p['condition']=='Guardian-destroyed':d['actions'].append(diag('slot',section=0,slot=0))
        else:d['actions'].append(configure(crit_status=512))
        d['actions'].append(advance(30))
        return [Case(d,lambda o:checks((state(o)['status2']&(64 if name=='stealtharmor' else 128),0),(events(o,kind='STEALTH_ARMOR' if name=='stealtharmor' else 'NSS'),[])),mode='normal')]
    if n==3:
        number=int(p['number'])
        if number:mount(d,index=0,crits=1)
        mount(d,'IS.RotaryAC/5',index=number,crits=1,ammo=20);slot(d,4,number,temp_failure=6)
        u['gunnery']=4;d['random']['streams']['unjam_rolls']=[int(p['roll'])]
        d['actions']=[cmd('unjamammo',str(number)),advance(59),inspect(),advance(1)]
        return [Case(d,lambda o:checks((state(o,index=2)['sections'][4]['slots'][number]['temp_failure'],6),(rawslot(o,index=number)['temp_failure'],6 if int(p['jam']) else 0),(rounds(o),20-int(p['rounds'])),(draws(o,'unjam_rolls'),[int(p['roll'])])),mode='normal')]
    if n in (4,5):
        if n==4 or int(p['ammo']):mount(d,'IS.AC/5',ammo=2)
        if n==4:d['actions']=[cmd('explode',p['text']),advance(int(p['due'])-1),inspect(),advance(1)]
        else:d['actions']=[diag('combat-callback',name='explode',data=int(p['data']))]
        def check(o):
            u=state(o)
            if n==4:
                assert not state(o,index=2)['destroyed'];assert u['destroyed'];eq(events(o,kind='EXPLODE'),[])
                assert any('great heat' in m for m in u['messages'])
            elif p['result'].startswith('countdown'):
                value=int(p['result'].split('-')[1])
                eq(o['state']['countdowns'],[dict(unit='u',deadline=1,data=value)])
                assert any(f'Self-destruction in {value%256} second' in m for m in u['messages'])
            elif p['result']=='cancelled':checks((u['destroyed'],False),(events(o,kind='EXPLODE'),[]))
            elif p['result']=='reactor':assert u['destroyed'];assert any('great heat' in m for m in u['messages'])
            else:checks((rounds(o),0),(rawslot(o,2,10)['firemode']&1,1));assert any('All your ammo explodes' in m for m in u['messages'])
        return [Case(d,check,mode='normal' if n==4 else 'diagnostic')]
    raise ValueError(('equipment',n))

def pods(n,p):
    d=fixture(False)
    if n==1:
        loc={'CT':4,'LARM':0,'RARM':1}[p['location']];section(d,loc,specials=2)
        if int(p['left']):slot(d,0,2,firemode=1)
        if int(p['right']):slot(d,1,2,firemode=1)
        d['random']['streams']['pod_rolls']=[12];d['actions']=[cmd('removepods',p['location'],'H')]
        arm=0 if p['arm']=='LARM' else 1
        return [Case(d,lambda o:checks((o['results'][0]['arm'],arm),(state(o)['sections'][arm]['recycle'],30),(state(o)['sections'][loc]['specials']&2,0)),mode='normal')]
    if n==2:
        d['units'][0]['tonnage']=55;section(d,4,specials=2);section(d,1,recycle=30)
        for index in (2,1)[:int(p['damage'])]:slot(d,0,index,firemode=1)
        d['random']['streams']['pod_rolls']=[2];d['actions']=[cmd('removepods','CT','H')]
        return [Case(d,lambda o:checks((o['results'][0]['self_damage'],int(p['self'])),(loss(o,'u'),int(p['self'])),(state(o)['sections'][4]['specials']&2,2)),mode='normal')]
    if n==3:
        d['units'][0].update(**{'class':'GROUND'},speed=int(p['speed']),desired_speed=int(p['speed']))
        section(d,2,specials=31);d['actions']=[cmd('removepods'),advance(59),inspect(),advance(1)]
        return [Case(d,lambda o:checks((state(o,index=2)['sections'][2]['specials'],31),(state(o)['sections'][2]['specials'],1)),mode='normal')]
    raise ValueError(('pods',n))

def blast(n,p):
    d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1]['at']=[3,3,0]
    options=dict(damage=10,x=3,y=3,safeup=2,safedown=1)
    if n==1:
        d['units'][1]['at'][2]=int(p['height'])
        if p['messages']=='null-target':options['target_message']=None
        if p['messages']=='null-observer':options['observer_message']=None
        d['actions']=[diag('blast',**options)]
        return [Case(d,lambda o:eq(loss(o),int(p['damage'])))]
    if n==2:
        # At coincident source/target centers the source bearing is zero;
        # first facing south makes rear true, which persists to the next unit.
        d['units'][0].update(at=[3,3,0],facing=180)
        d['units'][1]['facing']=0
        d['random']['streams']['physical_location']=[3,3]
        d['actions']=[diag('blast',damage=5,x=3,y=3,table='punch')]
        return [Case(d,lambda o:checks((200-state(o,'v')['sections'][4]['rear'],int(p['rear'])),(200-state(o,'v')['sections'][4]['armor'],int(p['front']))))]
    if n==3:
        d['units'][1]['at']=[3,2,0];d['map']['hexes']=[dict(at=[3,2],terrain='LIGHT_FOREST',elevation=0)]
        options.update(damage=12,neighbors=1)
        if p['messages']=='null':options.update(neighbor_target_message=None,neighbor_observer_message=None)
        d['actions']=[diag('blast',**options)]
        def check(o):
            eq(loss(o),int(p['damage']));assert any(dec['x']==3 and dec['y']==2 and dec['terrain']=='&' for dec in o['state']['map']['decorations'])
        return [Case(d,check)]
    raise ValueError(('blast',n))

def mines(n,p):
    d=fixture(False);reason='step';d['units'][1]['at']=[8,8,0]
    mine=dict(x=3,y=3,type='Standard',strength=int(p['initial']) if n==1 else 4)
    if n==2:
        ice=p['terrain'].startswith('ice');d['map']['hexes']=[dict(at=[3,3],terrain='ICE' if ice else 'WATER',elevation=-2)]
        d['units'][0]['at'][2]=int(p['height']);reason=p['reason']
        if p['terrain']=='ice-trigger':mine.update(type='Trigger',strength=50,extra=0)
    if n==3:
        mine.update(type='Vibra',strength=10,extra=int(p['threshold']))
        if p['placement']=='remote-one-hex':mine['y']=2
    if n==4:
        d['map']['mines']=[dict(x=7,y=i,type='Command',strength=4,extra=channel,creator=i+10) for i,channel in enumerate((7,7,8),3)]
        d['actions']=[cmd('detonatemines',p['channel'])]
        return [Case(d,lambda o:checks((o['results'][0]['count'],int(p['count'])),(len(o['state']['map']['mines']),int(p['remaining']))),mode='normal')]
    d['map']['mines']=[mine];d['actions']=[diag('mine-contact',reason=reason)]
    def check(o):
        left=o['state']['map']['mines']
        if n==1:checks((loss(o,'u'),int(p['damage'])),(len(left),int(p['remaining'])))
        elif n==3:checks((o['results'][0]['count'],int(p['count'])),(len(left),1-int(p['count'])))
        elif p['action']=='script-request':
            eq(len(left),1);effects=state(o)['external_effects'];assert any('AMINETRIGGER' in str(e) and e['applied'] is False for e in effects)
        else:
            eq(o['results'][0]['count'],int(p['action']=='explode'))
            # Ice height zero triggers the object, while the underwater blast
            # remains centered at elevation -2 and excludes its upper edge.
            eq(loss(o,'u'),4 if p['action']=='explode' and p['terrain']=='water' else 0)
    return [Case(d,check,blocked='persistent mine object scripts' if n==2 and p['action']=='script-request' else '')]

def terrain(n,p):
    d=fixture(False);d['map']['hexes']=[dict(at=[4,4],terrain='HEAVY_FOREST' if n in (2,3) else 'LIGHT_FOREST',elevation=0)]
    name='IS.MediumLaser';ammo=0
    if n==1:
        name={'Flamer':'IS.Flamer','MediumLaser':'IS.MediumLaser','AC10':'IS.AC/10','SmallLaser':'IS.SmallLaser','flechette-AC10':'IS.AC/10'}[p['weapon']]
        ammo=16384 if p['weapon']=='flechette-AC10' else 0
        d['random']['streams']['terrain_rolls']=[7,int(p['roll'])]
        mode='I'
    else:
        d['random']['streams']['terrain_rolls']=[7,int(p.get('ignite',6)),int(p.get('clear',8)),int(p.get('nested',5))]
        mode='C'
        if n==4:d['random']['streams']['terrain_replacement']=[int(p['draw'])]
        if n==3:d['map']['mines']=[dict(x=4,y=4,type='Standard',strength=5)]
    mount(d,name,mode=ammo,crits=1)
    d['actions']=[cmd('lock','4','4',mode),diag('terrain-hit',weapon=0,x=4,y=4,damage=8,operation='ignite-clear')]
    def check(o):
        board=o['state']['map'];cell=next(h for h in board['hexes'] if h['at']==[4,4]);burn=bool(board['decorations'])
        if n==1:checks((burn,p['fire']=='present'),(draws(o,'terrain_rolls'),[7,int(p['roll'])]))
        elif n==2:
            expected={'unchanged':'"','burning-heavy':'&','light-woods':"`"}[p['result']]
            eq(cell['terrain'],expected)
        elif n==3:checks((len(board['mines']),int(p['count'])),(cell['terrain'],"`"))
        else:checks((cell['terrain'],'%' if p['terrain']=='rough' else ' '),(draws(o,'terrain_replacement'),[int(p['draw'])]))
    return [Case(d,check)]

SS_MESSAGES=["You feel you'll have your hands full before too long..","You have a bad feeling about this..",
 'You feel a homicidal maniac is about to pounce on you!','You think something is amiss..',
 'You have a slightly bad feeling about this..','You think someone thinks ill of you..',
 'Something makes you somewhat feel uneasy..','Something makes you definitely feel uneasy..',
 'Something makes you feel out of your element..']

def targeting(n,p):
    d=fixture(False);d['units'][0]['target']=-1;d['units'][1]['contact_id']='AB'
    if n==1:
        d['actions']=[cmd('lock',*p['text'].split())]
        def check(o):
            u=state(o);label=p['state']
            if label=='enemy-lock':eq(u['target'],2)
            elif label.endswith('no-lock'):eq(u['target'],-1);eq(o['results'][0]['accepted'],label=='no-lock')
            else:
                checks((u['targ_x'],3),(u['targ_y'],4),(u['target'],-1))
                mask={'coordinates':0x8000,'ignite':0x40000,'clear':0x80000,'hex':0x20000,'building':0x10000}[label.split('-')[0]]
                eq(u['status']&0xf8000,mask)
        return [Case(d,check,mode='normal')]
    if n==2:
        d['map']['size']=[12,50];d['map']['mapvis']=60;d['map']['maxvis']=60
        distance=float(p['range']);d['units'][0].update(at=[3,30,0],real_mass=50+int(p['tons']),scan_range=100)
        d['units'][1].update(at=[3,30-int(distance),0],specials=0x40000,real=[1024.0750399750987,9675-distance*322.5,0])
        # This procedure isolates Sixth Sense after a visible target is acquired.
        # Keep that prerequisite independent of the simulation's seeded RNG.
        d['random']['streams'].update(**{'sensor.detect':[1]*20},sixth_sense_rolls=[8],sixth_sense_delay=[2])
        d['actions']=[cmd('lock','AB'),advance(1),inspect(),advance(1)]
        def check(o):
            eq(o['results'][0]['accepted'],True)
            before=state(o,'v',2)['messages'];after=state(o,'v')['messages']
            checks((any(m in SS_MESSAGES for m in before),False),(sum(m==SS_MESSAGES[int(p['index'])] for m in after),1),(draws(o,'sixth_sense_delay'),[2]))
        return [Case(d,check,mode='normal')]
    if n==3:
        d['pending_events']=[dict(unit='v',callback='sixth-sense',data=1,delay=2)]
        if p['state']=='unconscious':d['units'][1]['conscious']=False
        if p['state']=='absent':d['units'][1]['pilot']=False
        d['actions']=[advance(1),inspect(),advance(1)]
        return [Case(d,lambda o:checks((SS_MESSAGES[1] in state(o,'v',1)['messages'],False),(SS_MESSAGES[1] in state(o,'v')['messages'],p['result']=='delivered')))]
    raise ValueError(('targeting',n))

def bth(n,p):
    d=fixture(False);mount(d);options=dict(weapon=0,target='v',distance=float(p.get('range',2)))
    if n==1:
        profile=p['profile'];u=d['units'][0]
        if 'turning' in profile:u['desired_facing']=20
        if 'walking' in profile:u['speed']=10.75
        if 'running' in profile:u['speed']=53.75
        if 'jumping' in profile:u['status']=8|64
        if profile=='battlesuit-jumping':u['class']='BA'
        if 'prone' in profile:u['fallen']=True
        if 'quad' in profile:u['movement']='QUAD'
        if profile=='standing':u['fallen']=True;d['actions']=[cmd('stand')]
        if profile=='stabilizing':d['pending_events']=[dict(unit='u',callback='jump-stabil',delay=12)]
        key='attacker_move'
    elif n==2:
        profile=p['profile'];v=d['units'][1]
        if 'prone' in profile:v['fallen']=True
        if 'purifier' in profile:v['infantry_specials']=8
        if profile.endswith('kph'):v['speed']=float(profile.split('-')[1][:-3])
        key='target_move'
    elif n==3:
        c=p['condition'];weapon=d['units'][0]['weapons'][0];key='total'
        if c.startswith('target-'):d['units'][1]['class']={'target-MW':'MW','target-BA':'BA','target-dropship':'DS'}[c]
        if c in ('pulse','MRM','heavy-weapon','rocket'):weapon['metadata']={'special':{'pulse':1,'MRM':32768,'heavy-weapon':0x2000000,'rocket':65536}[c]}
        if c=='AP-ammo':weapon['ammo_mode']=8192
        if c=='attacker-haywire':section(d,4,specials=4)
        if c=='targetless-hex-ON_TC':options.pop('target');weapon['fire_mode']=16;d['units'][0]['target']=-1;d['actions']=[cmd('lock','3','2','H')]
        if c=='missing-indirect-spotter':options['indirect_fire']=0
    else:raise ValueError(('bth',n))
    d['actions'].append(diag('combat-bth',**options))
    return [Case(d,lambda o:eq(o['results'][-1][key],int(p['bth'] if n==3 else p['modifier'])))]

def preferences(n,p):
    d=fixture()
    if n==1:
        d['actions']=[cmd('mechprefs',p['name'],p['setting'])]
        return [Case(d,lambda o:checks((o['results'][0]['preference']['bit'],int(p['bit'])),(o['results'][0]['preference']['state'],p['setting'])),mode='normal')]
    if n==2:
        d['units'][0].update(**{'class':'GROUND'},turret_facing=90)
        if p['state']=='enabled':d['actions']=[cmd('autoturret')]
        d['actions'].append(advance(2))
        return [Case(d,lambda o:eq(state(o)['turret_facing'],0 if p['result']=='target-bearing' else 90),mode='normal')]
    if n==3:
        mount(d,'IS.GaussRifle',ammo=10,crits=1);mount(d,'IS.AC/5',index=1,crits=1)
        d['units'][0]['ammo'].append(dict(weapon='IS.AC/5',rounds=10,section=2,critical=11))
        number=0 if p['weapon']=='Gauss' else 1
        d['random']['streams']['attack_rolls']=[12]
        d['actions']=[cmd('disableweap',str(number)),cmd('fire',str(number))]
        return [Case(d,lambda o:checks((rawslot(o,index=number)['temp_failure'],5 if number==0 else 0),(o['results'][1]['accepted'],p['fire']=='allowed')),mode='normal')]
    raise ValueError(('preferences',n))

def ammunition(n,p):
    d=fixture();d['random']['streams'].update(attack_rolls=[12]*3,missile_pre_roll=[3]*20,missile_cluster=[12]*4)
    if n==1:
        mount(d,'IS.AC/5',crits=1)
        for loc,amount in ((4,4),(2,3),(3,2)):slot(d,loc,10,ammo='IS.AC/5',data=amount)
        if p['condition']=='empty':slot(d,2,10,data=0)
        if p['condition']=='destroyed':slot(d,2,10,firemode=1)
        d['actions']=[cmd('usebin','0',p['source']),inspect(),cmd('fire','0')]
        selected={'CT':4,'LT':2}[p['bin']]
        def check(o):
            eq(o['results'][2]['accepted'],True)
            for loc in (4,2,3):eq(state(o,index=1)['sections'][loc]['slots'][10]['data']-rawslot(o,loc,10)['data'],int(loc==selected))
        return [Case(d,check,mode='normal')]
    if n==2:
        weapon=p['weapon'];burst=int(p['burst']);shots=int(p['shots'])
        name={'RAC':'IS.RotaryAC/5','gattling':'IS.MachineGun','Ultra':'IS.UltraAC/5'}[weapon]
        fire={2:8192,4:16384,6:32768}[burst] if weapon=='RAC' else 4096 if weapon=='gattling' else 1024
        mount(d,name,fire=fire,ammo=int(p['ammo']),crits=1)
        d['random']['streams']['gattling_shots']=[6];d['actions']=[cmd('fire','0')]
        expected_damage=shots if weapon=='gattling' else shots*5
        return [Case(d,lambda o:checks((rounds(o),int(p['remaining'])),(loss(o),expected_damage)),mode='normal')]
    if n==3:
        rocket=p['weapon']=='pure-rocket';mount(d,'IS.RL-10' if rocket else 'IS.LRM-5',fire=0 if rocket else 256,crits=2,**({'special':65536} if rocket else {}))
        d['actions']=[cmd('fire','0'),advance(60),cmd('fire','0')]
        def check(o):
            checks((o['results'][0]['accepted'],True),(o['results'][2]['accepted'],False))
            if rocket:
                for i in range(2):eq(rawslot(o,index=i)['firemode']&0x100000,0x100000)
            else:eq(rawslot(o)['firemode']&512,512)
        return [Case(d,check,mode='normal')]
    if n==4:
        d['config']['periodic_updates']=False;d['units'][0]['crit_status']=8192
        mount(d,'IS.AC/5',ammo=int(p['count']),crits=1,ammo_per_ton=20)
        d['actions']=[diag('ammunition-check',weapon=0,offset=int(p['offset']))]
        return [Case(d,lambda o:checks((o['results'][0]['severity'],None if p['severity']=='none' else p['severity']),(state(o)['crit_status']&8192,0)))]
    raise ValueError(('ammunition',n))

def impacts(n,p):
    d=fixture(False);u=d['units'][0]
    if n==1:
        mode=p['mode'];fire={'HOTLOAD':64,'RFAC':2048,'RAC2':8192,'RAC4':16384,'RAC6':32768,'ULTRA':1024}.get(mode,0)
        name='IS.LRM-5' if mode=='HOTLOAD' else 'IS.UltraAC/5' if mode=='ULTRA' else 'IS.RotaryAC/5' if mode.startswith('RAC') else 'IS.AC/5'
        mount(d,name,fire=fire,mode=262144 if mode=='CASELESS' else 0,ammo=30,crits=1,range_min=0)
        u['gunnery']=2
        d['random']['streams'].update(attack_rolls=[int(p['roll'])],caseless_rolls=[int(p['secondary'])],missile_pre_roll=[3]*3,missile_cluster=[12])
        d['actions']=[cmd('fire','0')]
        def check(o):
            slot=rawslot(o);result=o['results'][0]['attack'];outcome=p['outcome']
            if outcome=='AMMOJAMMED':eq(slot['temp_failure'],6)
            elif outcome.startswith('destroyed'):eq(slot['firemode']&1,1)
            else:eq(o['results'][0]['accepted'],True)
            if p['tail']=='unspent':checks((state(o)['weap_heat'],0.0),(slot['data'],0))
            else:assert state(o)['weap_heat']>0 and slot['data']>0
            expected=28 if mode=='RFAC' and outcome.endswith('ammo-spent') else 29 if outcome.endswith('ammo-spent') or outcome=='fired' else 30
            eq(rounds(o),expected)
        return [Case(d,check,mode='normal')]
    if n==2:
        mount(d,damage=9);u['gunnery']=7;d['config']['glancing_blows']=int(p['mode'])
        d['actions']=[diag('combat-attack',weapon=0,target='v',roll=int(p['roll']))]
        return [Case(d,lambda o:checks((o['results'][0]['bth'],7),(loss(o),int(p['damage']))))]
    if n==3:
        kind=p['kind'];name='IS.Flamer' if kind=='flamer-heat' else 'IS.CoolantGun' if kind=='coolant' else 'CL.PlasmaRifle' if kind.startswith('CL') else 'IS.PlasmaRifle'
        mount(d,name,fire=65536 if kind=='flamer-heat' else 0,damage=10 if 'plasma' in kind else 5,crits=1)
        d['units'][1]['weap_heat']=10
        if 'ground' in kind:d['units'][1]['class']='GROUND'
        d['random']['streams']['plasma_heat']=[4]
        d['actions']=[diag('combat-attack',weapon=0,target='v',roll=12)]
        return [Case(d,lambda o:checks((state(o,'v')['weap_heat'],float(p['heat'])),(loss(o),int(p['armor'])),(len(draws(o,'plasma_heat')),1 if kind=='IS-plasma-MECH-base10' else 0)))]
    raise ValueError(('impacts',n))

def firing(n,p):
    d=fixture(False);u=d['units'][0];v=d['units'][1]
    mount(d,'IS.AC/5',ammo=20,crits=1,range_min=0);d['random']['streams']['attack_rolls']=[12]
    if n==1:
        u['hidden']=True;condition=p['condition'];number='0'
        if condition=='weapons-hold':u['status2']=0x800000
        if condition=='sprinting':u['status2']=0x10000
        if condition=='invalid-weapon':number='99'
        if condition=='weapon-recycling':slot(d,4,data=10)
        if condition=='carrying-club-in-mount':section(d,4,specials=32)
        if condition=='dug-in-nonturret':u['dug_in']=True;u['weapons'][0]['section']=2
        if condition=='AMS-weapon':u['weapons'][0].update(name='IS.Anti-MissileSystem');u['ammo'][0]['weapon']='IS.Anti-MissileSystem'
        if condition=='ammo-unjam-pending':d['pending_events']=[dict(unit='u',callback='unjam-ammo',data=0,delay=60)]
        d['actions']=[inspect(),cmd('fire',number)]
        return [Case(d,lambda o:checks((o['results'][1]['accepted'],False),(bool(state(o)['crit_status']&8),p['hidden']=='retained'),(rounds(o),20),(state(o)['weap_heat'],0.0),(rawslot(o,2 if condition=='dug-in-nonturret' else 4)['data'],10 if condition=='weapon-recycling' else 0)),mode='normal')]
    if n==2:
        c=p['condition'];path=p['path'];args=['0']
        if c.startswith('friendly'):v['team']=u.get('team',0)
        if c=='friendly-with-FFSafety':u['prefs']=128
        if c=='friendly-with-map-safety':d['map']['flags']=256
        if c=='stealth-without-stable-lock':v['status2']=64
        if c=='own-swarmer':v.update(**{'class':'BA'},swarm_target='u')
        if c=='enemy-with-no-lock':u['target']=-1
        if c=='MW-with-safety':v['class']='MW'
        if c=='friendly-coolant':u['weapons'][0]['name']='IS.CoolantGun';u['ammo'][0]['weapon']='IS.CoolantGun'
        if path=='explicit-contact':args.append('01')
        if path=='hex-occupant':d['actions']=[cmd('lock','3','2')]
        d['actions'].append(cmd('fire',*args))
        return [Case(d,lambda o:eq(o['results'][-1]['accepted'],p['result']=='fired'),mode='normal')]
    if n==3:
        bth=int(p['bth']);action=p['action'];u['gunnery']=bth+(4 if action=='fire-hex' else 0)
        d['random']['streams']['attack_rolls']=[7]
        if action=='fire-hex':d['actions']=[cmd('lock','4','1','H')]
        d['actions'].append(cmd('sight' if action=='sight' else 'fire','0'))
        def check(o):
            attack=o['results'][-1]['attack'];spent=int(p['spent'])
            checks((attack['bth'],bth),(draws(o,'attack_rolls'),[7]),(rounds(o),20-spent),(rawslot(o)['data'],40*spent),(state(o)['weap_heat'],float(spent)))
        return [Case(d,check,mode='normal')]
    raise ValueError(('firing',n))

def locations(n,p):
    d=fixture(False);u=d['units'][0];v=d['units'][1]
    if n==1:
        c=p['condition'];mount(d);d['random']['streams']['attack_rolls']=[12]
        if c=='upright-MECH-partial-cover':
            v['at']=[3,1,0];d['map']['hexes']=[dict(at=[3,2],terrain='CLEAR',elevation=1)]
        if c=='MW-shooter-at-MECH-target-height':u['class']='MW'
        if c=='BA-shooter-swarming-MECH-target':u.update(**{'class':'BA'},swarm_target='v')
        if c=='critproof-MECH':v['specials']=0x40000000
        if c in ('FASA-ground','advanced-ground'):
            v['class']='GROUND';d['config']['fasacrit' if c=='FASA-ground' else 'fasaadvvhlcrit']=1
        source='physical_location' if p['family'] in ('punch','kick') else 'swarm_location' if p['family']=='swarm' else 'hit_location_rolls'
        d['random']['streams'][source]=[int(p['roll'])]*5
        d['random']['streams']['crittable_chance']=[1]*10
        d['actions']=[cmd('fire','0')]
        expected={'punch':0,'kick':6,'swarm':4,'normal':4,'critproof':4,'FASA-vehicle':2,'advanced-vehicle':2}[p['family']]
        def check(o):
            result=o['results'][-1]['attack'];eq(result['location'],expected)
            eq(loss(o),5);assert draws(o,source)
            eq(state(o,'v')['sections'][expected]['armor'],195)
        return [Case(d,check,mode='normal')]
    if n==2:
        mount(d,'IS.NarcBeacon',ammo=10,crits=1);section(d,0,unit=1,armor=0,internal=0,rear=0)
        d['random']['streams'].update(attack_rolls=[12],hit_location_rolls=[10])
        d['actions']=[cmd('fire','0')]
        return [Case(d,lambda o:checks((state(o,'v')['sections'][0]['specials']&1,0),(state(o,'v')['sections'][2]['specials']&1,1)),mode='normal')]
    raise ValueError(('locations',n))

def dfa(n,p):
    d=fixture();u=d['units'][0]
    u.update(jump_mp=3,jump_speed=32.25,piloting=4)
    d['random']['streams']['dfa_rolls']=[2 if n==2 else 12]
    if n==1:u.update(tonnage=int(p['nominal']),real_mass=int(p['actual']))
    if n==2:
        u.update(tonnage=55,real_mass=55)
        if int(p['floor'])<0:
            d['map']['hexes']=[dict(at=[3,2],terrain='WATER',elevation=-1)];d['units'][1]['at'][2]=-1
    d['actions']=[cmd('jump'),advance(1)]
    if n==3:
        c=p['condition']
        if c=='target-on-different-map':d['actions'].append(dict(op='remove',unit='v'))
        if c=='target-jumping':d['actions'].append(configure(unit='v',status=8|64))
        if c=='arm-weapon-recycling':
            mount(d,loc=0,index=4,crits=1)
            d['actions'].append(dict(op='section',value=dict(index=0,slots=[dict(index=4,data=60)])))
        if c=='leg-physical-recycling':d['actions'].append(dict(op='section',value=dict(index=5,recycle=60)))
        if c=='BTH-over-12':d['actions'].append(configure(piloting=10))
    d['actions'] += [advance(17),inspect(),advance(1),inspect(),advance(1),inspect()]
    def check(o):
        eq(o['results'][0]['accepted'],True)
        landed=next((r for r in o['results'] if isinstance(r,dict) and 'units' in r and not r['units']['u']['status']&64),None)
        assert landed,'jump failed to finish'
        a=landed['units']['u'];v=landed['units']['v']
        eq(a['dfa_target'],-1);assert not any(e['kind']=='JUMP' for e in a['events'])
        if n==3:
            checks((loss(o),0),(draws(o,'dfa_rolls'),[]));assert any('finish your jump' in m for m in a['messages'])
        else:
            result=a['last_dfa_result'];expected=int(p['target']) if n==1 else 0;selfdamage=int(p['self']) if n==1 else 11
            checks((result['damage_dealt'],expected),(result['attacker_damage'],selfdamage),(loss(o),expected),(loss(o,'u'),selfdamage))
            # The ordinary periodic consumer runs later in this same tick.
            for loc in (0,1,2,3,5,6):eq(a['sections'][loc]['recycle'],29)
            if n==2:checks((a['fallen'],True),(a['at'][2],int(p['floor'])))
    cases=[Case(d,check,mode='normal')]
    if n in (1,2):
        callback=deepcopy(d);callback['config']['periodic_updates']=False
        callback['units'][0]['status']=8|64|256
        callback['actions']=[diag('dfa',target='v',roll=2 if n==2 else 12)]
        def initial(o):
            for loc in (0,1,2,3,5,6):eq(state(o)['sections'][loc]['recycle'],30)
        cases.append(Case(callback,initial,note='Exact callback recycle before the ordinary tick consumer.'))
    return cases

def charge(n,p):
    d=fixture(False);u=d['units'][0];v=d['units'][1]
    u.update(speed=float(p.get('speed',10.75)),real_mass=50,piloting=0)
    v.update(real_mass=65 if n==3 else 50,tonnage=65 if n==3 else 50,piloting=0)
    if n==1:
        d['actions']=[diag('charge',target='v',roll=12)]
        return [Case(d,lambda o:checks((loss(o),int(p['damage'])),(loss(o,'u'),5)))]
    if n==2:
        d['config']['periodic_updates']=True;u['speed']=0
        d['random']['streams']['charge_rolls']=[12,12]
        d['actions']=[cmd('charge',*(['01'] if p['selection']=='explicit-contact' else [])),cmd('speed','64.5'),advance(20)]
        def check(o):
            eq(o['results'][0]['accepted'],True);a=state(o)
            assert a.get('last_charge_result',{}).get('attacker_hit'),a.get('last_charge_result')
            checks((a['speed'],0.0),(a['charge_target'],-1),(len(draws(o,'charge_rolls')),1));assert loss(o)>0
        return [Case(d,check,mode='normal')]
    if n==3:
        u['charge_target']='v';v.update(charge_target='u',speed=10.75)
        d['actions']=[diag('charge',target='v',roll=12,target_roll=12)]
        return [Case(d,lambda o:checks((loss(o),11+int(p['secondself'])),(loss(o,'u'),7+int(p['firstself']))))]
    raise ValueError(('charge',n))

def integration(n,p):
    d=fixture();u=d['units'][0];v=d['units'][1]
    if n==2:
        dep=p['dependency']
        if dep in ('persistent-occupant-transfer','persistent-character-XP'):
            u['in_character']=True
            d['actions']=[cmd('damage-section','HD','1000','0','0')]
        elif dep=='mine-object-script':
            d['map']['mines']=[dict(x=3,y=2,type='Trigger',strength=20,extra=0)]
            v['at']=[8,8,0];d['actions']=[cmd('speed','64.5'),advance(20)]
        elif dep=='building-object-damage':
            mount(d,'IS.AC/5',ammo=20,crits=1);d['map']['hexes']=[dict(at=[3,1],terrain='BUILDING',elevation=0)]
            d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('lock','3','1','B'),cmd('fire','0')]
        else:d['actions']=[cmd('c3connect')]
        def check(o):
            effects=[e for row in o['state']['units'].values() for e in row['external_effects']]
            needle={'persistent-occupant-transfer':'occupant','persistent-character-XP':'XP','mine-object-script':'AMINETRIGGER','building-object-damage':'building','unavailable-C3-network-formation':'C3'}[dep]
            assert any(needle.lower() in str(e).lower() and e['applied'] is False for e in effects),effects
        return [Case(d,check,mode='normal',blocked=dep)]
    workflow=p['workflow']
    if workflow=='jump-DFA':return dfa(1,dict(nominal='55',actual='60',target='19',self='11'))[:1]
    if workflow=='movement-mine':
        d['map']['mines']=[dict(x=3,y=2,type='Standard',strength=4)];v['at']=[8,8,0]
        d['actions']=[cmd('speed','64.5'),advance(20)]
        return [Case(d,lambda o:checks((loss(o,'u'),4),(len(o['state']['map']['mines']),0)),mode='normal')]
    if workflow=='RAC-jam-unjam-fire':
        mount(d,'IS.RotaryAC/5',ammo=20,crits=1,fire=8192);u['gunnery']=2
        d['random']['streams'].update(attack_rolls=[2,12],unjam_rolls=[12],missile_cluster=[12])
        d['actions']=[cmd('fire','0'),inspect(),cmd('rac','0','1'),cmd('unjamammo','0'),advance(60),inspect(),cmd('fire','0')]
        def check(o):
            checks((state(o,index=1)['sections'][4]['slots'][0]['temp_failure'],6),(state(o,index=5)['sections'][4]['slots'][0]['temp_failure'],0),(o['results'][-1]['accepted'],True),(rounds(o),18))
        return [Case(d,check,mode='normal')]
    if workflow=='stealth-enable-lock-fire':
        mount(d,'IS.AC/5',ammo=20,crits=1);v.update(specials2=1,equipment=['Guardian']);u['target']=-1
        d['random']['streams']['attack_rolls']=[12]
        d['actions']=[cmd('stealtharmor',unit='v'),advance(30),cmd('fire','0','01'),cmd('lock','01'),advance(10),cmd('fire','0')]
        return [Case(d,lambda o:checks((state(o,'v')['status2']&64,64),(o['results'][2]['accepted'],False),(o['results'][-1]['accepted'],True),(rounds(o),19)),mode='normal')]
    if workflow=='pod-ECM-remove':
        v['class']='GROUND';section(d,2,unit=1,specials=8)
        d['actions']=[advance(2),inspect(),cmd('removepods',unit='v'),advance(60),inspect()]
        return [Case(d,lambda o:checks((bool(state(o,'v',1)['status2']&4),True),(state(o,'v')['sections'][2]['specials']&8,0),(bool(state(o,'v')['status2']&4),False)),mode='normal')]
    if workflow in ('spotted-artillery','TIC-artillery-coordinates'):
        u['artillery']=0;mount(d,'IS.Sniper',ammo=20,crits=1);v['at']=[3,1,0]
        d['random']['streams']['attack_rolls']=[12,12]
        if workflow=='TIC-artillery-coordinates':
            mount(d,'IS.Sniper',index=1,crits=1);u['tics']=[[0,1]]
            d['actions']=[cmd('firetic','0','3','1')]
        else:
            d['units'].append(dict(name='s',at=[4,3,0],team=0,spotting=4))
            d['actions']=[cmd('spot','02',unit='s'),cmd('lock','3','1','H',unit='s'),cmd('lock','-'),cmd('spot','02'),cmd('fire','0')]
        d['actions'] += [inspect(),advance(9),inspect(),advance(1)]
        def check(o):
            before=o['results'][-4]['map'];near=o['results'][-2]['map'];final=o['state']['map'];count=2 if workflow.startswith('TIC') else 1
            checks((len(before['projectiles']),count),(len(near['artillery_impacts']),0),(len(final['projectiles']),0),(len(final['artillery_impacts']),count))
            assert loss(o)>0
        return [Case(d,check,mode='normal')]
    raise ValueError(('integration',n,p))

def supplemental():
    from combat_supplemental import all_cases
    return all_cases()
