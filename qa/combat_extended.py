"""Additional independent C boundary fixtures for impacts, missiles and clocks."""
from combat_support import *

def cell(o,x=4,y=4):return next(h for h in o['state']['map']['hexes'] if h['at']==[x,y])

def terrain_cases():
    small=['ERSmallLaser','SmallLaser','SmallPulseLaser','X-SmallPulseLaser','ERSmallPulseLaser','HeavySmallLaser','MachineGun','LightMachineGun','HeavyMachineGun','StreakSRM-2','SRM-2']
    ignite=small+['GaussRifle','LightGaussRifle','HeavyGaussRifle','MagshotGaussRifle','NarcBeacon','iNarcBeacon']
    clear=small+[prefix+'AC/'+size for prefix in ('','Ultra','Caseless','Hyper','Light','Rotary') for size in ('2','5')]+['LB2-XAC','LB5-XAC']
    # Catalog names are read from the immutable C catalog, never Python output.
    import re
    names=re.findall(r'\{"([^"]+)"', (ROOT/'btmux/btmux/btech/src/btech/weapons.h').read_text())
    for operation,excluded in [('ignite',ignite),('clear',clear)]:
        for suffix in excluded:
            weapon=next(n for n in names if n[3:]==suffix)
            d=fixture(False);mount(d,'IS.MediumLaser',crits=1,source_name=weapon);d['map']['hexes']=[dict(at=[4,4],terrain='HEAVY_FOREST',elevation=0)]
            seq=[7,12] if operation=='ignite' else [7,6,2]
            d['random']['streams']['terrain_rolls']=seq;d['actions']=[cmd('lock','4','4','I' if operation=='ignite' else 'C'),diag('terrain-hit',weapon=0,x=4,y=4,damage=20,operation='ignite-clear')]
            yield Case(d,lambda o,seq=seq:checks((cell(o)['terrain'],'"'),(o['state']['map']['decorations'],[]),(draws(o,'terrain_rolls'),seq)),label=f'terrain-exclusion-{operation}-{suffix.replace("/","_")}')
    for special,terrain in [(0x80000,'LIGHT_FOREST'),(0,'CLEAR')]:
        for mode,seq in [('I',[7,12]),('C',[7,6,2])]:
            d=fixture(False);mount(d,special=special);d['map']['hexes']=[dict(at=[4,4],terrain=terrain,elevation=0)];d['random']['streams']['terrain_rolls']=seq
            d['actions']=[cmd('lock','4','4',mode),diag('terrain-hit',weapon=0,x=4,y=4,damage=20,operation='ignite-clear')]
            yield Case(d,lambda o,seq=seq,terrain=terrain:checks((draws(o,'terrain_rolls'),seq),(o['state']['map']['decorations'],[]),(cell(o)['terrain'],'`' if terrain=='LIGHT_FOREST' else ' ')),label=f'terrain-early-return-{special}-{terrain}-{mode}')
    for intentional in (0,1):
        for ignite_roll in (3,4,5,6):
            for damage in (7,8):
                d=fixture(False);mount(d);d['map']['hexes']=[dict(at=[4,4],terrain='HEAVY_FOREST',elevation=0)]
                nested=ignite_roll<=(5 if intentional else 3);seq=[7,ignite_roll,8]+([5] if nested else [])
                d['random']['streams']['terrain_rolls']=seq;d['actions']=[diag('terrain-hit',weapon=0,x=4,y=4,damage=damage,hit=intentional,operation='ignite-clear')]
                yield Case(d,lambda o,nested=nested,damage=damage,seq=seq:checks((draws(o,'terrain_rolls'),seq),(cell(o)['terrain'],'&' if nested else '`' if damage==8 else '"'),(draws(o,'terrain_replacement'),[])),label=f'terrain-clear-cutoffs-{intentional}-{ignite_roll}-{damage}')
    d=fixture(False);mount(d);d['units'][0].update(target=-1,status=8|262144|524288);d['map']['hexes']=[dict(at=[4,4],terrain='LIGHT_FOREST',elevation=0)];d['random']['streams']['terrain_rolls']=[7,5]
    d['actions']=[diag('terrain-hit',weapon=0,x=4,y=4,operation='ignite-clear')]
    yield Case(d,lambda o:checks((draws(o,'terrain_rolls'),[7,5]),(len(o['state']['map']['decorations']),1)),label='terrain-ignite-lock-priority')

def impact_cases():
    import combat_examples
    for mode,threshold in [('HOTLOAD',3),('RFAC',4),('RAC2',2),('RAC4',3),('RAC6',4),('ULTRA',2),('CASELESS',3)]:
        for rolled in (threshold,threshold+1):
            if mode=='ULTRA' and rolled==2:outcome='destroyed';tail='unspent'
            elif rolled<=threshold:outcome='AMMOJAMMED';tail='unspent'
            else:outcome='fired';tail='spent'
            p=dict(mode=mode,roll=str(rolled),secondary='7',outcome=outcome,tail=tail)
            case=combat_examples.impacts(1,p)[0];case.label=f'impacts-risk-boundary-{mode}-{rolled}'
            # A successful multi-shot consumes its actual mode count.
            if outcome=='fired':
                count={'RFAC':2,'RAC2':2,'RAC4':4,'RAC6':6,'ULTRA':2}.get(mode,1)
                case.check=lambda o,count=count:checks((o['results'][0]['accepted'],True),(rounds(o),30-count),(rawslot(o)['temp_failure'],0))
            yield case
    for name,base,bands in [('IS.HeavyGaussRifle',25,[25,20,20,10]),('IS.SnubNosedPPC',10,[10,8,8,5])]:
        for distance,expected in zip((3,3.1,6,6.1),bands):
            d=fixture(False);mount(d,name,ammo=10 if 'Gauss' in name else None,crits=1,range_min=0,range_short=3,range_medium=6,range_long=9,damage=base);d['units'][0]['gunnery']=0
            d['actions']=[diag('combat-attack',weapon=0,target='v',distance=distance,roll=12)]
            yield Case(d,lambda o,expected=expected:eq(loss(o),expected),label=f'impacts-range-shaping-{name}-{distance}')
    for wet in (False,True):
        for distance,expected in [(1,10),(1.01,9),(6,9),(6.1,8),(9,8),(9.1,4)]:
            d=fixture(False);mount(d,damage=9,range_short=3,range_medium=6,range_long=9,range_short_water=3,range_medium_water=6,range_long_water=9);d['config']['moddamagewithrange']=1;d['units'][0]['gunnery']=0
            if wet:d['units'][0]['at'][2]=-2;d['units'][1]['at'][2]=-2;d['map']['hexes']=[dict(at=[3,y],terrain='WATER',elevation=-2) for y in (2,3)]
            d['actions']=[diag('combat-attack',weapon=0,target='v',distance=distance,roll=12)]
            yield Case(d,lambda o,expected=expected:eq(loss(o),expected),label=f'impacts-energy-water{wet}-range{distance}')
    for terrain,base,expected in [('LIGHT_FOREST',5,3),('HEAVY_FOREST',5,1),('HEAVY_FOREST',3,1)]:
        d=fixture(False);mount(d,damage=base);d['config']['moddamagewithwoods']=1;d['map']['hexes']=[dict(at=[3,2],terrain=terrain,elevation=0)]
        d['random']['streams']['terrain_rolls']=[7,6,base];d['random']['streams']['terrain_replacement']=[2]
        d['actions']=[diag('combat-attack',weapon=0,target='v',roll=12)]
        yield Case(d,lambda o,expected=expected,terrain=terrain:checks((loss(o),expected),(cell(o,3,2)['terrain'],'`' if terrain=='HEAVY_FOREST' else ' ')),label=f'impacts-woods-preabsorption-{terrain}-{base}')
    for shots in range(1,7):
        for stock in (3,20):
            d=fixture(False);mount(d,'IS.MachineGun',fire=4096,ammo=stock,crits=1);d['random']['streams'].update(attack_rolls=[12],gattling_shots=[shots]);d['actions']=[cmd('fire','0')]
            yield Case(d,lambda o,shots=shots,stock=stock:checks((loss(o),min(shots,stock//3)),(rounds(o),stock-3*min(shots,stock//3)),(state(o)['weap_heat'],float(min(shots,stock//3)))),label=f'impacts-gattling-draw{shots}-stock{stock}',mode='normal')
    for jets in (0,10.75):
        d=fixture(False);mount(d);d['units'][0].update(cocoon=1,jump_speed=jets,at=[3,3,2]);d['actions']=[diag('combat-attack',weapon=0,target='v',roll=12)]
        yield Case(d,lambda o,jets=jets:checks((state(o)['cocoon'],-1 if jets else 0),(len(events(o,kind='FALL')),0 if jets else 1),(loss(o),5)),label=f'impacts-OOD-cocoon-jets{jets}')

def missile_cases():
    for kind in ('ordinary','hotload','Streak'):
        for glance in (False,True):
            d=fixture(False);mount(d,'IS.StreakSRM-6' if kind=='Streak' else 'IS.LRM-5',fire=64 if kind=='hotload' else 0,crits=1)
            d['random']['streams'].update(missile_pre_roll=[6,5,1],missile_cluster=[4]);d['actions']=[diag('missile-index',weapon=0,target='v',glancing=glance)]
            expected=10 if kind=='Streak' else (0 if glance else 4) if kind=='hotload' else -1 if glance else 2
            yield Case(d,lambda o,expected=expected,kind=kind:checks((o['results'][0]['index'],expected),(draws(o,'missile_pre_roll'),[6,5,1]),(draws(o,'missile_cluster'),[] if kind=='hotload' else [4])),label=f'missiles-three-dice-{kind}-{glance}')
    for mode in (0,2,4,6):
        for field in ('none','targetECM','targetAngel','attackerECM','attackerAngel'):
            d=fixture(False);mount(d,'IS.LRM-5',mode=mode,crits=1);section(d,4,unit=1,specials=3)
            if field.startswith('target'):d['units'][1]['status2']=8 if field=='targetECM' else 1024
            if field.startswith('attacker'):d['units'][0]['status2']=4 if field=='attackerECM' else 2048
            d['random']['streams'].update(missile_pre_roll=[3]*3,missile_cluster=[7]);d['actions']=[diag('missile-index',weapon=0,target='v')]
            yield Case(d,lambda o,mode=mode,field=field:eq(o['results'][0]['index'],7 if mode and field=='none' else 5),label=f'missiles-guidance-mask{mode}-{field}')
    for mode,pod in [(0,2),(512,0),(1024,4),(2048,8),(4096,2)]:
        d=fixture(False);mount(d,'IS.iNarcBeacon',ammo=5,mode=mode,crits=1);d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0')]
        yield Case(d,lambda o,pod=pod:checks((state(o,'v')['sections'][4]['specials'],pod),(loss(o),6 if pod==0 else 0),(rounds(o),4)),label=f'missiles-inarc-choice-{mode}',mode='normal')
    for visited,enemy,expected in [([],False,'u'),(['u'],False,'far'),(['u','far'],False,'near'),(['u'],True,'near')]:
        d=fixture(False);d['units'][0]['at']=[3,3,0];d['units'][1]['at']=[3,2,0]
        d['units'] += [dict(name='far',at=[4,3,0],team=0),dict(name='near',at=[3,1,0],team=2)]
        d['actions']=[diag('swarm-next',target='v',visited=['v']+visited,enemy_only=enemy)]
        yield Case(d,lambda o,expected=expected:eq(o['results'][0]['target'],expected),label=f'missiles-swarm-roster-{len(visited)}-{enemy}')

def booster_cases():
    for name,tech,bit in [('masc','specials',1048576),('scharge','specials2',33554432)]:
        for speed in (-30,0,30):
            d=fixture(False);d['units'][0].update(desired_speed=speed,**{tech:16 if name=='masc' else 64});d['random']['streams']['booster_rolls']=[12]*3
            d['actions']=[cmd(name),inspect(),cmd(name),inspect(),cmd(name),advance(1),inspect(),advance(60),inspect(),advance(60)]
            def check(o,speed=speed,name=name,bit=bit):
                checks((state(o,index=1)['desired_speed'],speed*4/3),(state(o,index=3)['desired_speed'],float(speed)),(state(o)['masc_counter'],3),(state(o)['scharge_counter'],0),(bool(state(o)['status']&bit),True),(draws(o,'booster_rolls'),[12]*3))
                eq([e['deadline'] for e in events(o,kind='MASC_FAIL' if name=='masc' else 'SCHARGE_FAIL')],[181])
            yield Case(d,check,label=f'boosters-toggle-clock-{name}-{speed}',mode='normal')
        for condition in ('missing-tech','immobile','stopped'):
            d=fixture(False);d['units'][0][tech]=16 if name=='masc' else 64
            if condition=='missing-tech':d['units'][0][tech]=0
            if condition=='immobile':d['units'][0]['max_speed']=0
            if condition=='stopped':d['units'][0]['started']=False
            d['actions']=[cmd(name)]
            yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),([e for e in events(o) if e['kind'].startswith(('MASC','SCHARGE'))],[])),label=f'boosters-command-{name}-{condition}',mode='normal')
        for missing in (False,True):
            d=fixture(False);d['units'][0].update(started=missing,**{tech:0 if missing else 16 if name=='masc' else 64})
            d['random']['streams']['booster_rolls']=[2];d['pending_events']=[dict(unit='u',callback='booster',data=name,delay=1)];d['actions']=[advance(1)]
            yield Case(d,lambda o:checks((state(o)['masc_counter'],1),(draws(o,'booster_rolls'),[2]),([e for e in events(o) if e['kind'].startswith(('MASC','SCHARGE'))],[])),label=f'boosters-callback-{name}-missingtech{missing}')
    for cls in ('GROUND','VTOL'):
        for speed in (65,65.9,10.75):
            d=fixture(False);d['units'][0].update(**{'class':cls},specials2=64,max_speed=speed);d['random']['streams']['booster_rolls']=[2];d['actions']=[cmd('scharge'),advance(1)]
            yield Case(d,lambda o,speed=speed:checks((state(o)['max_speed'],float(int(int(speed)*.5))),(state(o)['specials2']&64,0)),label=f'boosters-supercharger-integer-speed-{cls}-{speed}',mode='normal')
    for count in range(1,5):
        d=fixture(False);d['units'][0]['specials2']=64
        for i,part in enumerate(['SUPERCHARGER']+['ENGINE']*4):slot(d,4,i,special=part)
        d['random']['streams'].update(booster_rolls=[2],supercharger_crits=[count]);d['actions']=[cmd('scharge'),advance(1)]
        yield Case(d,lambda o,count=count:checks((state(o)['engine_heat'],min(15,count*5)),(state(o)['destroyed'],count>=3),(sum(bool(rawslot(o,index=i)['firemode']&1) for i in range(5)),count+1)),label=f'boosters-supercharger-engine-draw-{count}',mode='normal')

def all_cases():
    yield from terrain_cases()
    yield from impact_cases()
    yield from missile_cases()
    yield from booster_cases()
