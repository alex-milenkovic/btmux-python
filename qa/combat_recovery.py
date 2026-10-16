"""Independent combat eligibility, targeting and damage regression procedures.

Oracles: mech.bth.c, mech.combat.c, mech.advanced.c, mech.c3.misc.c and
mech.enhanced.criticals.c. All effects are observed through the documented CLI.
"""
from combat_support import *


def bth_cases():
    for skill in (2,4,6):
        for indirect in (2,1000):
            d=fixture(False);mount(d,range_min=0);d['units'][1]['spotting']=skill
            d['actions']=[diag('combat-bth',weapon=0,target='v',distance=2,spotter='v',indirect_fire=indirect)]
            yield Case(d,lambda o,skill=skill,indirect=indirect:checks(
                (o['results'][0]['spotting_mod'],skill-4 if indirect<1000 else 0),
                (o['results'][0]['idf_terrain_mod'],2 if indirect<1000 else 0)),
                label=f'bth-recovery-indirect-{skill}-{indirect}')
    for cls,expected in [('MW',2),('BA',1),('DS',-3),('MECH',0)]:
        d=fixture(False);mount(d);d['units'][1]['class']=cls
        d['actions']=[diag('combat-bth',weapon=0,target='v',distance=2)]
        yield Case(d,lambda o,expected=expected:eq(o['results'][0]['other_mods'],expected),label='bth-recovery-class-exclusion-'+cls)
    for flags in (0,2,32,1,3):
        for distance,bracket in [(2.5,'TOFAR'),(4,'SHORT'),(7,'LONG')]:
            d=fixture(False);mount(d,range_min=3,range_short=4,range_medium=6,range_long=9)
            slot(d,4,weap_damage_flags=flags)
            d['actions']=[diag('combat-bth',weapon=0,target='v',distance=distance)]
            expected=int(bool(flags&1))+int(bool(flags&(2|32)) and bracket!='SHORT')
            yield Case(d,lambda o,expected=expected,bracket=bracket:checks(
                (o['results'][0]['critical_bth'],expected),(o['results'][0]['range_bracket'],bracket)),
                label=f'bth-recovery-enhanced-bracket-{flags}-{distance}')
    for water in (False,True):
        for pc in (False,True):
            for tc in (1,2):
                for far in (False,True):
                    d=fixture(False);mount(d,range_min=0,range_short=3,range_medium=6,range_long=9,
                        range_min_water=0,range_short_water=1,range_medium_water=2,range_long_water=3,special=0x80000 if pc else 0)
                    if water:d['units'][0]['at'][2]=-2;d['map']['hexes']=[dict(at=[3,3],terrain='WATER',elevation=-2)]
                    boundary=2 if water else 6;distance=(boundary+(.051 if far else 0))/(10 if pc else 1)
                    d['actions']=[configure(targcomp=tc),diag('combat-bth',weapon=0,target='v',distance=distance)]
                    expected=-1 if (tc==2)==far else 1
                    yield Case(d,lambda o,expected=expected:eq(o['results'][-1]['targcomp_mod'],expected),label=f'bth-recovery-TC-water{water}-pc{pc}-{tc}-{far}')
    for mode in ('stable','locking','hipshot','side-lock','multi-side','multi-locking','override'):
        d=fixture();mount(d);d['random']['streams']['attack_rolls']=[12]
        d['config']['lock_tick']=8
        if mode=='hipshot':d['units'][0]['target']=-1
        if mode in ('side-lock','multi-side'):
            d['units'].append(dict(name='w',at=[4,3,0],team=2));d['units'][0]['target']=3
        if mode in ('locking','multi-locking','override'):
            d['units'][0]['target']=-1;d['actions']=[cmd('lock','01')]
        if mode.startswith('multi'):d['actions'].append(configure(targcomp=3))
        if mode=='override':d['config']['arc_override']=1
        d['actions'].append(cmd('sight','0','01'))
        unstable={'stable':0,'locking':1,'hipshot':2,'side-lock':2,'multi-side':2,'multi-locking':0,'override':0}[mode]
        def check(o,unstable=unstable,mode=mode):
            eq(o['results'][-1]['accepted'],True)
            b=o['results'][-1]['attack']['bth_breakdown']
            checks((b['unstable_lock_mod'],unstable),(b['targcomp_mod'],int(mode=='multi-side')),(draws(o,'attack_rolls'),[12]))
        yield Case(d,check,label='bth-recovery-lock-'+mode,mode='normal')
    for cocoon in (-1,0,1):
        d=fixture(False);mount(d);d['units'][1]['cocoon']=cocoon
        d['actions']=[diag('combat-bth',weapon=0,target='v',distance=2)]
        yield Case(d,lambda o,cocoon=cocoon:eq(o['results'][0]['other_mods'],-2*int(cocoon>0)),label=f'bth-recovery-OOD-{cocoon}')
    for woods in ('LIGHT_FOREST','HEAVY_FOREST'):
        for enabled in (0,1):
            d=fixture(False);mount(d);d['config']['moddamagewithwoods']=enabled
            d['map']['hexes']=[dict(at=[3,2],terrain=woods,elevation=0)]
            d['actions']=[diag('combat-bth',weapon=0,target='v',distance=2)]
            bonus=(1-enabled)*(1 if woods=='LIGHT_FOREST' else 2)
            # The CLI groups this source bonus with terrain/light modifiers.
            yield Case(d,lambda o,bonus=bonus:eq(o['results'][0]['terrain_mod'],bonus),label=f'bth-recovery-woods-{woods}-{enabled}')


def range_cases():
    for half in (0,1):
        for ammo in (0,64):
            for distance in (0,2.5,6,6.1):
                d=fixture(False);mount(d,'IS.LRM-5',mode=ammo,range_min=6,range_short=7,range_medium=8,range_long=9)
                d['config']['hotloadaddshalfbthmod']=half
                d['actions']=[diag('combat-range',weapon=0,target='v',distance=distance,network_range=1),
                              diag('combat-bth',weapon=0,target='v',distance=distance)]
                direct=0 if distance>6 else int(7-distance) if ammo else int((7-distance)/2) if half else 0
                normal=int(7-distance) if distance<=6 else 0
                yield Case(d,lambda o,direct=direct,normal=normal:checks(
                    (o['results'][0]['modifier'],direct),(o['results'][1]['range_mod'],normal)),
                    label=f'ranges-recovery-C3-inverted-{half}-{ammo}-{distance}')
    for mode in (0,131072):
        for distance,ordinary in [(12,8),(12.051,1000),(19,1000),(19.051,1000)]:
            d=fixture(False);mount(d,mode=mode,range_min=0,range_short=3,range_medium=6,range_long=9)
            d['actions']=[diag('combat-range',weapon=0,target='v',distance=distance)]
            expected=8 if mode and distance<=19 else ordinary
            yield Case(d,lambda o,expected=expected:eq(o['results'][0]['modifier'],expected),label=f'ranges-recovery-stinger-{mode}-{distance}')
    for empty in (False,True):
        for reverse in (False,True):
            d=fixture(False);mount(d,range_min=0,range_short=3,range_medium=6,range_long=9)
            names=['p','q'][::(-1 if reverse else 1)]
            d['units'][0].update(at=[3,10,0],specials=128,working_c3_masters=1,c3_network=[] if empty else names)
            d['units'] += [dict(name=n,at=[3,3,0],specials=256) for n in ('p','q')]
            d['random']['streams']['sensor.detect']=[1]*30
            d['actions']=[diag('combat-bth',weapon=0,target='v',distance=8)]
            yield Case(d,lambda o,empty=empty,reverse=reverse:checks((o['results'][0]['c3_ref'],-1 if empty else 4 if reverse else 3),
                (o['results'][0]['range_mod'],4 if empty else 0)),label=f'ranges-recovery-network-empty{empty}-reversed{reverse}')
    for weapon in ('IS.MediumLaser','IS.Sniper'):
        d=fixture();mount(d,weapon,ammo=10 if weapon=='IS.Sniper' else None,crits=1)
        d['units'][1]['at']=[8,8,0];d['random']['streams']['attack_rolls']=[12,12]
        d['actions']=[cmd('lock','3','1','H'),cmd('sight','0'),cmd('fire','0')]
        def check(o):
            sight,fire=o['results'][1:]
            checks((sight['accepted'],True),(fire['accepted'],True),(sight['attack']['bth'],fire['attack']['bth']),
                   (draws(o,'attack_rolls'),[12,12]),(state(o)['shots_fired'],0),(rawslot(o)['data']>0,True))
        yield Case(d,check,label='ranges-recovery-sight-fire-'+weapon,mode='normal')


def other_cases():
    for mask,short,long in [(0,'reg','at'),(65536,'bld','at the building at'),(196608,'hex','at the hex'),(720896,'clr','at the hex, trying to clear it'),(983040,'ign','at the hex, trying to ignite it')]:
        d=fixture();mount(d);d['units'][0].update(target=-1,status=8|mask)
        d['units'][1]['at']=[8,8,0];d['random']['streams']['attack_rolls']=[12]
        d['actions']=[cmd('fire','0','3','1')]
        def check(o,short=short,long=long):
            checks((o['results'][0]['accepted'],True),(o['results'][0]['attack']['hex_target_label'],short),
                   (f'MediumLaser {long} (3,1)' in o['results'][0]['text'],True))
        yield Case(d,check,label=f'targeting-recovery-combined-label-{short}',mode='normal')
    for values,selected in [([0,0],None),([10,10],0),([9,10],1),([2147483647,1],0)]:
        d=fixture(False);d['units'][0]['class']='GROUND';mount(d,loc=2,crits=1);mount(d,loc=3,crits=1)
        d['random']['streams']['vehicle_weapon_weight']=values;d['actions']=[diag('main-weapon-jam')]
        yield Case(d,lambda o,values=values,selected=selected:checks(
            (draws(o,'vehicle_weapon_weight'),values),([rawslot(o,loc)['temp_failure'] for loc in (2,3)],
                [5 if selected==i else 0 for i in (0,1)])),label='preferences-recovery-main-weapon-'+str(values))
    # Independently retain both representable sides of the strict SWARM radius.
    for y,expected in [(32.25,'B'),(32.24994,'C')]:
        d=fixture(False);d['units'][0]['at']=[3,7,0]
        d['units'] += [dict(name='B',at=[3,1,0],team=2,real=[1024.0750399750987,y,0]),dict(name='C',at=[4,2,0],team=2)]
        d['actions']=[diag('swarm-next',target='v',visited=['v'])]
        yield Case(d,lambda o,expected=expected:eq(o['results'][0]['target'],expected),label=f'missiles-recovery-float-boundary-{y}',note='Independent compiled C FindRange probe; strict comparison to double literal 1.9.')
    for token in ('stop','stop override'):
        d=fixture();d['config']['explode_stop']=1;d['units'][0]['caller_wizard']=True
        d['actions']=[cmd('explode','reactor'),cmd('explode',*token.split()),inspect()]
        yield Case(d,lambda o,token=token:checks((o['results'][1]['accepted'],token=='stop'),
            (len(events(o,kind='EXPLODE')),int(token!='stop'))),label='equipment-recovery-exact-stop-'+token,mode='normal')


def cases():
    yield from bth_cases()
    yield from range_cases()
    yield from other_cases()
