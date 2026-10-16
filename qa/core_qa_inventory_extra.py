"""Critical-run, split location, lookup and ammunition boundary procedures."""
from core_simulation_qa import D,C,I,case,check as q


def build():
    for sect,candidates,marker in [(0,[2],443),(1,[3],444),(2,[4,0,5],443),(3,[4,1,6],444)]:
        for skip in range(len(candidates)+1):
            locations=candidates[skip:]
            case('weapons',f'split-order-{sect}-{skip}',[D('GetSplitData',sect,3)],[q('results.0',[locations[0],2,marker] if locations else None)],units=[dict(name='u',profile='sparse',sections=[dict(index=i,slots=[dict(index=2,type=marker,data=3),dict(index=4,type=marker,data=3)]) for i in locations])])
    for cls in ('MECH','VEH_GROUND'):
        for marker in (443,444):
            case('weapons',f'reverse-split-{cls}-{marker}',[D('ReverseSplitCritLoc',i,0) for i in range(8)],
                 [q('results',[2,3,0,1,3 if marker==444 else 2,2,3,-1] if cls=='MECH' else [-1]*8)],units=[dict(name='u',**{'class':cls},sections=[dict(index=i,slots=[dict(index=0,type=marker)]) for i in range(8)])])
    for move,limit in [('BIPED',12),('QUAD',6)]:
        for index in (5,6,11):
            case('weapons',f'split-limit-{move}-{index}',[D('FindSplitCrits',0,443,2)],[q('results.0',index if index<limit else -1)],units=[dict(name='u',movement=move,sections=[dict(index=0,slots=[dict(index=index,type=443,data=2)])])])
    case('weapons','firstcrit-separated-repeated',[D('FindFirstWeaponCrit',0,n,0,1,2) for n in (-1,3,4,7,8,11)],
         [q('results',[3,3,3,7,7,7])],units=[dict(name='u',profile='sparse',sections=[dict(index=0,slots=[dict(index=i,type=1) for i in (3,4,7,8)])])])
    for size,slots,expected in [(1,[0,1,3,7],[0,1,3,7]),(2,[0,1,2,3,6,7],[0,2,6]),(3,[0,1,2,4,5,6],[0,4]),(9,[0,1,2],[0])]:
        case('weapons',f'critical-grouping-{size}',[D('FindWeapons_Advanced',0)],[q('results.0',expected,project='critical')],units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.SmallLaser',section=4,metadata={'crits':size})],sections=[dict(index=0,slots=[dict(index=i,type=1) for i in slots])])])
    for cls in ('MECH','VEH_GROUND','BSUIT'):
        case('weapons','nonmech-run-size-'+cls,[D('FindWeapons_Advanced',0)],
             [q('results.0',[0] if cls=='MECH' else [0,1,2],project='critical')],units=[dict(name='u',profile='sparse',**{'class':cls},weapons=[dict(name='IS.SmallLaser',section=4,metadata={'crits':3})],sections=[dict(index=0,slots=[dict(index=i,type=1) for i in (0,1,2)])])])
    for size in (2,3,4,5,6):
        for dead in range(size+1):
            for disabled in (False,True):
                case('weapons',f'partial-threshold-{size}-{dead}-{disabled}',[D('WeaponIsNonfunctional',0,0)],[q('results.0',1 if disabled and dead<size else 2 if dead>=size//2 else -dead)],units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.SmallLaser',section=0,metadata={'crits':size})],sections=[dict(index=0,slots=[dict(index=i,firemode=1 if i<dead else 2 if disabled and i==dead else 4) for i in range(size)])])])
    for mask in (0,1,2,3):
        for earlier_weapon in (False,True):
            case('weapons',f'busy-source-order-{mask}-{earlier_weapon}',[D('MechFullNoRecycle',mask)],
                 [q('results.0',1 if mask&1 and earlier_weapon else 2 if mask&2 else 1 if mask&1 else 0)],units=[dict(name='u',weapons=[dict(name='IS.MediumLaser',section=0 if earlier_weapon else 1)],sections=[dict(index=0,recycle=2),dict(index=0 if earlier_weapon else 1,slots=[dict(index=0,data=3)])])])
    # A numeric catalog identity is obtained through the UI; metadata fixtures use
    # index zero (SmallLaser) deliberately to isolate ammo scanning from lookup.
    for destroyed in (0,1,2,4,8):
        case('ammunition','twelve-slot-count-'+str(destroyed),[D('FindRoundsForWeapon',0),D('CountAmmoForWeapon',0)],
             [q('results',[7 if destroyed&7 else 10]*2)],units=[dict(name='u',weapons=[dict(name='IS.SmallLaser',section=4,metadata={'ammo_per_ton':20})],sections=[dict(index=7,slots=[dict(index=11,type=193,data=7),dict(index=10,type=193,data=3,firemode=destroyed)])])])
    for sinks in (0,1,5,6,10):
        for reverse in (False,True):
            heats=[1,9] if reverse else [9,1];order=list(reversed(heats));capacity=sinks+4;acc=0;expected=50
            for heat in order:expected+=50 if acc+heat>capacity else 101;acc+=heat
            case('bv',f'offense-equal-bv-heat-order-{sinks}-{reverse}',[D('Calculate_Offensive_BV')],[q('results.0.value',expected)],units=[dict(name='u',profile='sparse',num_sinks=sinks,weapons=[dict(name=n,section=i,fire_mode=1,metadata={'crits':1,'bv':101,'heat':heats[i]}) for i,n in enumerate(('IS.SmallLaser','IS.MediumLaser'))])])
    case('bv','offense-ams-omission-no-todo-bonus',[D('Calculate_Offensive_BV')],[q('results.0.value',131)],units=[dict(name='u',profile='sparse',specials2=65536|0x1000000,weapons=[dict(name='IS.SmallLaser',section=0,metadata={'crits':1,'bv':500,'heat':90,'special':0x400}),dict(name='IS.MediumLaser',section=1,fire_mode=32|256,metadata={'crits':1,'bv':81,'heat':1})])])
    for mode in range(4):
        for text in ('2-0,1,1','0,99','2-0suffix,1','0-9,1'):
            if text=='0,99':wanted=[[0,0]]
            elif text=='0-9,1':wanted=[]
            else:wanted=([[0,0],[1,1],[2,2]] if mode%2 else [[0,2]])+([[1,1],[1,1]] if text=='2-0,1,1' else [[1,1]])
            case('weapons',f'multi-mode-{mode}-{text.encode().hex()}',[D('multi_weap_sel',text,mode)],
                 [q('results.0.calls',wanted),q('results.0.messages',int(text in ('0,99','0-9,1')),length=True)],units=[dict(name='u',weapons=[dict(name='IS.SmallLaser',section=i) for i in range(3)])])
        case('weapons',f'multi-stop-prior-effects-{mode}',[D('multi_weap_sel','0-2,1,2',mode,2)],
             [q('results.0.calls',[[0,0],[1,1]] if mode%2 else [[0,2],[1,1]])],units=[dict(name='u',weapons=[dict(name='IS.SmallLaser',section=i) for i in range(3)])])
    for whine in (False,True):
        for silence in (False,True):
            def check_notice(data,wanted=int(whine and not silence)):
                before=data['results'][1]['units']['u']['external_effects'];after=data['state']['units']['u']['external_effects']
                assert len(after)-len(before)==wanted,(before,after,wanted)
            case('weapons',f'malformed-whine-silence-{whine}-{silence}',[dict(op='section',value=dict(index=0,slots=[dict(index=0,type=1)])),I(),D('FindWeapons_Advanced',0,whine,silence)],
                 [q('results.2',None)],checker=check_notice,
                 units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.SmallLaser',section=4,metadata={'crits':3})])])
    for current in (0,1,20):
        for flags in (0,1,2,4,128):
            for artemis in (False,True):
                ammo=0 if not current or flags&7 else 45 if flags&128 else 180 if artemis else 90
                case('cost',f'inventory-consumer-{current}-{flags}-{artemis}',[D('CalcFasaCost')],
                     [q('results.0.value',int((470000+1000+ammo)*1.5))],units=[dict(name='u',profile='sparse',max_speed=0,core={'engine_rating':0},weapons=[dict(name='IS.SmallLaser',section=0,fire_mode=1,metadata={'crits':2,'cost':1000,'ammo_cost':90,'ammo_per_ton':20})],sections=[dict(index=7,slots=[dict(index=11,type=193,data=current,firemode=flags,ammomode=2 if artemis else 0)])])])
