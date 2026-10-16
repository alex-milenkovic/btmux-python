"""Geometry, part arithmetic and cost/BV diagnostics via CLI."""
import math
from core_simulation_qa import D,C,I,case,check as q,examples


def build():
    for n,r in enumerate(examples('geometry',1)):
        case('geometry',f'example-01-{n}',[D('AcceptableDegree',int(r['input']))],[q('results.0',int(r['output']))])
    for n,r in enumerate(examples('geometry',2)):
        x,y,z=map(float,r['point'].split(','))
        case('geometry',f'example-02-{n}',[D('FindBearing',0,0,x,y),D('FindZBearing',0,0,0,x,y,z)], [q('results',[int(r['bearing']),int(r['vertical'])])])
    for n,r in enumerate(examples('geometry',3)):
        case('geometry',f'example-03-{n}',[D('visit_neighbor_hexes',*map(int,r['hex'].split(',')))],[q('results.0',[list(map(int,p.split(','))) for p in r['neighbors'].split(';')])],map={'size':[4,4]},units=[dict(name='u',at=[1,1,0])])
    for n,r in enumerate(examples('geometry',4)):
        relative=int(r['relative'])
        # Use the source float32 center of hex(0,0), and an exactly vertical target.
        case('geometry',f'example-04-{n}',[D('InWeaponArc',186.19546508789062,-161.25)],
             [q('results.0',{'forward':1,'rear':8,'left':2,'right':4}[r['arc']])],
             units=[dict(name='u',at=[0,0,0],facing=relative)])
    for n,r in enumerate(examples('parts',1)):
        case('parts',f'example-01-{n}',[D('round_to_halfton',int(r['weight'])),D('round_to_quarterton',int(r['weight']))],[q('results',[int(r['half']),int(r['quarter'])])])
    for weight in (-1025,-1024,-1023,-514,-513,-512,-511,-257,-256,-255,-2,-1,255,258,511,515,1023):
        expected=[]
        for size in (512,256):
            remainder=weight-int(weight/size)*size
            expected.append(weight if remainder==0 else weight-remainder if remainder<2 else weight+size-remainder)
        case('parts','signed-round-'+str(weight),[D('round_to_halfton',weight),D('round_to_quarterton',weight)],[q('results',expected)])
    for n,r in enumerate(examples('parts',2)):
        section=dict(index=4,armor=int(r['remaining']),armor_orig=int(r['original']),internal=int(r['remaining']),internal_orig=int(r['original']))
        case('parts',f'example-02-{n}',[D('getRemainingArmorPercent'),D('getRemainingInternalPercent')],[q('results',[int(r['percent'])]*2)],units=[dict(name='u',profile='sparse',sections=[section])])
    for n,r in enumerate(examples('parts',3)):
        case('parts',f'example-03-{n}',[D('UnitPartsList',0),D('UnitPartsList',int(r['mode']))],[q('results.0',same_as='results.1')],
             units=[dict(name='u',weapons=['IS.SmallLaser'],ammo=[dict(weapon='IS.AC/5',rounds=3)],sections=[dict(index=4,armor=2)])])
    for name,label in [('MECH','mech'),('VEH_GROUND','tank'),('VTOL','VTOL'),('VEH_NAVAL','vessel'),('SPHEROID_DS','aerofighter'),('AERO','DropShip'),('MW',None),('DS',None),('BSUIT',None)]:
        case('parts','type-'+name,[D('mechtypename')],[q('results.0',label)],units=[dict(name='u',**{'class':name})])
    for kind,move,sizes in [('MECH','BIPED',[12]*5+[6]*3),('MECH','QUAD',[6,6,12,12,12,6,6,6]),('MW','BIPED',[2]*8),('VEH_GROUND','TRACK',[12]*8)]:
        case('parts','crit-count-'+kind+move,[D('CritsInLoc',i) for i in range(8)],[q('results',sizes)],units=[dict(name='u',**{'class':kind},movement=move)])
    case('parts','labels-and-matching',[D('MechIDS'),D('MechIDS',True),D('MyToUpper','aBc'),D('listmatch',['Alpha','alpha','Beta'],'ALPHA'),D('listmatch',['Alpha'],'Al')],
         [q('results',['AB','ab','ABc',0,-1])],units=[dict(name='u',contact_id='AB')])
    for n,r in enumerate(examples('cost',1)):
        case('cost',f'example-01-{n}',[C('cost')],[q('results.0.result.value',int(r['cost']))],units=[dict(name='u',profile='sparse',max_speed=0,core={'engine_rating':int(r['engine'])})])
    for n,r in enumerate(examples('cost',2)):
        case('cost',f'example-02-{n}',[C('cost')],[q('results.0.result.value',0)],units=[dict(name='u',**{'class':r['kind']})])
    for n,r in enumerate(examples('cost',3)):
        case('cost',f'example-03-{n}',[D('CalcFasaCost_DoArmMath' if r['kind']=='arm' else 'CalcFasaCost_DoLegMath',0 if r['kind']=='arm' else 5)],[q('results.0.value',int(r['price']))])
    for operation in ('AddDefBV','SubDefBV','AddOffBV'):
        values=[0,-5,5]
        case('bv','debug-operation-'+operation,[D('Calc_'+operation,100,'signed',v) for v in values],
             [q('results', [100-v if operation=='SubDefBV' else 100+v for v in values],project='value'),
              q('state.units.u.debug_messages',[f'{operation} {"signed":>25}{"-" if operation=="SubDefBV" else " "}{v:8.2f}' for v in values])],config={'cost_debug':True})
    for n,r in enumerate(examples('cost',4)):
        part={'weapon':1,'ammo':197,'special':394,'bomb':389,'cargo':512}[r['category']]
        case('cost',f'example-04-{n}',[D('SetPartCost',part,9007199254740993),D('GetPartCost',part)],[q('results.1',9007199254740993)])
    case('cost','five-tables-isolation',[D('SetPartCost',p,i+123) for i,p in enumerate([1,197,394,389,512])]+[D('GetPartCost',p) for p in [1,197,394,389,512]],
         [q('results.'+str(5+i),i+123) for i in range(5)])
    case('cost','unreachable-generic-price',[D('CalcFasaCost'),D('SetPartCost',512,123456789),D('CalcFasaCost')],[q('results.0.value',same_as='results.2.value')],units=[dict(name='u',profile='sparse',sections=[dict(index=4,slots=[dict(index=0,type=512)])])])
    for n,r in enumerate(examples('bv',1)):
        case('bv',f'example-01-{n}',[D('Calculate_Defensive_BV')],[q('results.0.value',float(r['bv']),tolerance=1e-5)],
             units=[dict(name='u',profile='sparse',max_speed=int(r['mp'])*10.75,sections=[dict(index=4,armor=100,armor_orig=100,internal=50,internal_orig=50)])])
    for n,r in enumerate(examples('bv',2)):
        case('bv',f'example-02-{n}',[D('Calculate_Offensive_BV')],[q('results.0.value',int(r['bv']))],units=[dict(name='u',profile='sparse',num_sinks=int(r['sinks']),
             weapons=[dict(name='IS.SmallLaser',section=0,metadata=dict(crits=1,heat=5,bv=101)),dict(name='IS.MediumLaser',section=1,metadata=dict(crits=1,heat=5,bv=80))])])
    for n,r in enumerate(examples('bv',3)):
        case('bv',f'example-03-{n}',[D('CalculateBV',100,100,int(r['tick']))],[q('results.0.value',int(r['result'])),q('state.units.u.bv_last',int(r['last'])),q('state.units.u.bv',777)],units=[dict(name='u',profile='sparse',max_speed=0,core={'bv':777,'bv_last':0})])
