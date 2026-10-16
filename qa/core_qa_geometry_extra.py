"""Exact arc decisions and distance boundaries from source formulas."""
from core_simulation_qa import D,I,case,check as q


def build():
    # A vertical target has exact C bearing zero. All source integer boundary
    # decisions below therefore exercise real InWeaponArc without trig tolerance.
    for cls,move,mounts in [('MECH','BIPED',8),('MECH','QUAD',8),('MW','BIPED',8),('BSUIT','BIPED',8),('VEH_GROUND','TRACK',5),('VEH_NAVAL','HULL',5),('VTOL','VTOL',5),('AERO','FLY',4),('DS','FLY',6),('SPHEROID_DS','FLY',6)]:
        for twist in (0,2,4,6):
            for rear in (False,True):
                actions=[];checks=[]
                for facing in (0,29,30,31,59,60,61,119,120,121,239,240,241,299,300,301,329,330,331,359):
                    # Facing is controlled by the existing public unit-state action.
                    actions.append(dict(op='core',unit='u',values={'facing':facing}))
                    def arc(ignore=False):
                        r=(facing+(59 if twist&2 else -59 if twist&4 else 0) * int(cls in ('MECH','MW','BSUIT') and not ignore))%360
                        return (1 if r>=300 or r<=60 else 8 if 120<r<240 else 4 if 240<=r<300 else 2) | (16 if cls in ('VEH_GROUND','VEH_NAVAL','VTOL') and (facing>=330 or facing<=30) else 0)
                    actions.append(D('InWeaponArc',186.19546508789062,-161.25));checks.append(q('results.'+str(len(actions)-1),arc()))
                    for loc in range(mounts):
                        if cls in ('MECH','MW','BSUIT'):want=8 if rear else [3,5,1,1,1,1,1,1][loc]
                        elif cls in ('VEH_GROUND','VEH_NAVAL','VTOL'):want=[2,4,1,8,16][loc]
                        elif cls=='DS':want=[4,2,2,4,8,1][loc]
                        elif cls=='SPHEROID_DS':want=[5,3,10,12,8,1][loc]
                        else:want=[7,10 if rear else 3,12 if rear else 5,8][loc]
                        ignore=cls=='MECH' and (loc in (5,6) or move=='QUAD' and loc in (0,1))
                        actions.append(D('IsInWeaponArc',186.19546508789062,-161.25,loc,0));checks.append(q('results.'+str(len(actions)-1),want&arc(ignore)))
                actions.append(I());checks.append(q('state.units.u.status',8|twist,mask=14))
                case('geometry',f'arc-all-mounts-{cls}-{move}-{twist}-{rear}',actions,checks,
                     units=[dict(name='u',**{'class':cls},movement=move,at=[0,0,0],status=8|twist,sections=[dict(index=i,internal=1,internal_orig=1,slots=[dict(index=0,firemode=32 if rear else 0)]) for i in range(8)])])
    actions=[];checks=[]
    for x in (-32768,-7,-2,-1,0,1,2,7,32767):
        for y in (-7,-1,0,1,7):
            for tc in (-1,0,1):
                xd,yd=abs(x),abs(y);value=yd if not xd else yd-xd//2+tc+xd if xd//2<=yd else xd+tc
                actions.append(D('MyHexDist',0,0,x,y,tc));checks.append(q('results.'+str(len(actions)-1),value))
    case('geometry','myhexdist-short-domain',actions,checks)
    for x,y,z in [(0,0,0),(322.5,0,0),(0,-645,0),(0,0,322.5),(967.5,1290,0),(0,0,-645)]:
        case('geometry',f'ranges-{x}-{y}-{z}',[D('FindXYRange',0,0,x,y),D('FindRange',0,0,0,x,y,z)],
             [q('results.0',(x*x+y*y)**.5/322.5,tolerance=1e-5),q('results.1',(x*x+y*y+z*z)**.5/322.5,tolerance=1e-5)])

    for rear in (False,True):
        for facing,arc in [(0,1),(90,2),(180,8),(270,4)]:
            case('geometry',f'flipped-arms-{rear}-{facing}',[D('IsInWeaponArc',186.19546508789062,-161.25,loc,0) for loc in (0,1,5,6)],
                 [q('results',[(8 if rear else want)&arc for want in (10,12,1,1)]),q('state.units.u.status',1032)],
                 units=[dict(name='u',at=[0,0,0],facing=facing,status=1032,sections=[dict(index=i,slots=[dict(index=0,firemode=32 if rear else 0)]) for i in (0,1,5,6)])])
    for facing in (29,30,31,329,330,331):
        case('geometry','turret-relative-'+str(facing),[D('InWeaponArc',186.19546508789062,-161.25)],
             [q('results.0',1|(16 if facing<=30 or facing>=330 else 0))],units=[dict(name='u',**{'class':'VEH_GROUND'},at=[0,0,0],turret_facing=facing)])
