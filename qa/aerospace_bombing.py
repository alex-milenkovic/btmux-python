"""QA procedures 5-7: physical payload and source ballistic/impact observations."""
import math
import re
from aerospace_support import *

BOMBS=[('10_Inferno',10,1,30),('10_Cluster',10,2,30),('10_Standard',10,0,130),('50_Inferno',50,1,130),('50_Cluster',50,2,130),('50_Standard',50,0,130),('100_Inferno',100,1,250),('100_Cluster',100,2,250),('100_Standard',100,0,250)]

def slot(index=2,position=0,**kw):return dict(index=position,type=385+index,**kw)
def bomber(index=2,**kw):return craft(sections=[dict(index=5,slots=[slot(index)])],**kw)
def streams(**kw):return dict(streams=dict(pilot_rolls=[12],**kw))

def payload():
    for name,row in feature_rows('payload',1):
        i=int(row['index']);label,weight,kind,power=BOMBS[i]
        c=Case(name,document(bomber(i),[cmd('bomb','list')])).result(ok=True)
        for key,value in dict(name=label,weight=weight,type=kind,power=power).items():c.expect('results.0.rows.0.'+key,value)
        c.expect('results.0.rows',1,'length').expect('results.0.lines.2',('Inferno','Cluster','Standard')[i%3],'excludes')
        yield c
    for name,row in feature_rows('payload',2):
        f=row['fixture'];arg='' if row['argument']=='empty' else row['argument'];u=bomber()
        if 'no-bombs' in f:u['sections']=[]
        if 'landed' in f:u['aerospace']['landed']=True
        if 'stopped' in f:u['started']=False
        if 'unconscious' in f:u['conscious']=False
        if 'IC;' in f:u.update(in_character=True,actor=dict(id=99,location=10))
        errors={'aim':'The craft is landed!','':'(At least) one option required.','drop':'The BOMB commands needs to know WHICH bomb to drop!','unknown':'Invalid argument to BOMB!','drop 1 extra':'Too many arguments!','drop 00':'Invalid bomb number!','drop -1':'Negative bomb number? Gimme a break.','drop 0':'No bombs installed.' if 'no-bombs' in f else 'No bomb with such number installed! (See BOMB LIST)'}
        c=Case(name,document(u,[cmd('bomb',arg)],random=streams()))
        if arg in errors:c.result(ok=False,error=errors[arg])
        elif 'unconscious' in f:c.result(ok=False).text('results.0.error','conscious')
        elif 'IC;' in f:c.result(ok=False).text('results.0.error','pilot')
        elif 'list' in arg.lower():c.result(ok=True).expect('results.0.rows',0 if 'no-bombs' in f else 1,'length')
        else:c.result(ok=True,scheduled=True).final(**{'sections.5.slots.0.type':0})
        yield c
    for name,row in feature_rows('payload',3):
        f=row['fixture'];u=bomber();u['sections']=[dict(index=5,slots=[slot(0,firemode=1),slot(5,position=2,data=7,brand=2,ammomode=8)])]
        if 'DestroyBomb' in f:u['sections']=[dict(index=5,slots=[slot(7)])];actions=[diag('destroy_bomb',direction=5)]
        else:actions=[cmd('bomb','list' if ';list' in f else 'drop 2' if ';drop2' in f else 'drop 1')]
        c=Case(name,document(u,actions,random=streams()))
        if ';list' in f:c.result(ok=True).expect('results.0.rows',2,'length').expect('results.0.rows.0.destroyed',True).expect('results.0.rows.1.weight',50)
        elif ';drop1' in f:c.result(ok=True,scheduled=True).final(**{'sections.5.slots.0.type':385,'sections.5.slots.2.type':0,'sections.5.slots.2.data':7,'sections.5.slots.2.brand':2,'sections.5.slots.2.ammomode':8})
        elif ';drop2' in f:c.result(ok=False).final(**{'sections.5.slots.0.type':385,'sections.5.slots.2.type':390})
        else:c.final(damage_taken=0,**{'sections.5.slots.0.type':392})
        yield c


def ballistics():
    for name,row in feature_rows('bombing',1):
        z=float(row['z']);vz=float(row['vz']);t=f32(f32(vz/64.5)+math.sqrt(f32(f32(f32(vz/64.5)**2)+f32(2*f32(z)))))
        u=bomber(at=[10,10,int(z)],aerospace=dict(fz=64.5*z,start_fz=vz))
        suffix='' if t>=2 or t<1 else 's'
        yield Case(name,document(u,[cmd('bomb','aim')])).result(ok=True,time=t,x=10,y=10,message=f'Estimated bomb flight time {t:.1f} second{suffix}, estimated landing hex 10,10.')
    for name,row in list(feature_rows('bombing',2))[:6]:
        f=row['fixture'];t=float(re.match(r't([\d.]+)',f)[1]);u=bomber(at=[10,10,int(t*t/2)],aerospace=dict(fz=64.5*t*t/2))
        draws=dict(pilot_rolls=[2 if 'fail' in f else 12]);x,y=10,10
        if 'scatter12' in f:draws.update(bomb_scatter_distance=[12],bomb_scatter_direction=[0]);x=16
        if 'scatter1' in f:
            draws.update(bomb_scatter_distance=[1],bomb_scatter_direction=[180]);angle=f32(180*.0174533);x,y=int(10+math.cos(angle)),int(10+math.sin(angle))
        if 'offmap' in f:u['aerospace']['start_fx']=1000
        c=Case(name,document(u,[cmd('bomb','drop 1')],random=dict(streams=draws))).result(ok=True,modifier=4+int(t)//10,scheduled='offmap' not in f)
        if 'offmap' not in f:c.result(x=x,y=y,due=max(1,int(t))).final(**{'sections.5.slots.0.type':0})
        else:c.final(**{'sections.5.slots.0.type':387,'carried_cargo':0}).expect('state.events',['ARTILLERY_HIT',0],'event_count')
        c.expect('draws',1+(2 if 'scatter' in f else 0),'length')
        yield c


def impacts():
    for name,row in feature_rows('bombing',4):
        i=next(i for i,b in enumerate(BOMBS) if b[0]==row['bomb']);label,weight,kind,power=BOMBS[i];damage=power//2 if kind==1 else power
        u=bomber(i,at=[10,10,8],aerospace=dict(fz=516))
        target=craft('MECH',name='target',id=20,at=[10,10,0],sections=[dict(index=j,armor=255,armor_orig=255,internal=100,internal_orig=100,rear=255,rear_orig=255) for j in range(8)])
        nearby=deepcopy(target);nearby.update(name='near',id=21,at=[10,11,0])
        high=deepcopy(target);high.update(name='high',id=22,at=[10,10,4])
        actions=[cmd('bomb','drop 1'),inspect(),advance(3),inspect(),advance(1)]
        d=document(u,actions,units=[u,target,nearby,high],random=streams(**{'hit_location_rolls':[7]*300,'damage_entry':[7]*300,'tow_rolls':[12]*300,'sensor.random':[1]*100,'fuel_check':[0]*10}))
        c=Case(name,d).result(ok=True,scheduled=True,due=4).expect('results.3.units.target.damage_taken',0)
        c.expect('state.units.target.damage_taken',damage).expect('state.units.near.damage_taken',damage//2).expect('state.units.high.damage_taken',0)
        c.expect('state.events',['ARTILLERY_HIT',0],'event_count')
        cluster=2 if kind==2 else 10
        c.expect('draws',['hit_location_rolls',math.ceil(damage/cluster)+math.ceil((damage//2)/cluster)],'draw_count')
        if kind==1:
            for recipient,heat in [('target',power),('near',power//2)]:
                c.expect('state.events',dict(kind='CUSTOM',unit=recipient,deadline=4+heat*6),'has_record')
        yield c


def terrain():
    for name,row in feature_rows('bombing',3):
        f=row['fixture'];u=bomber(at=[10,10,8],aerospace=dict(fz=516));d=document(u);actions=[]
        t=.5 if 't0.5' in f else 4;x,y=10,14;expected=[x,y]
        if 't0.5' in f:actions=[op('map_command',name='addhex',args='10 11 . 9')]
        elif 'only-second' in f:actions=[op('map_command',name='addhex',args='10 12 . 9')];expected=[10,12]
        elif 'second-and-third' in f:actions=[op('map_command',name='addhex',args='10 12 . 9'),op('map_command',name='addhex',args='10 13 . 9')];expected=[10,13]
        elif 'equals' in f:u['aerospace']['fz']=131;actions=[op('map_command',name='addhex',args='10 12 . 2')]
        else:u['aerospace']['fy']=-483.75;y=3;actions=[op('map_command',name='addhex',args='10 2 . 9')];expected=[10,2]
        actions.append(diag('simulate_flight',x=x,y=y,time=t));d['actions']=actions
        yield Case(name,d).expect(f'results.{len(actions)-1}',expected)


def forests():
    for name,row in feature_rows('exhaust',1):
        damage=int(row['damage']);distance=int(row['distance']);decorated=row['decoration']!='none';u=craft('DS',at=[10,10,0]);actions=[op('map_command',name='addhex',args=f'10 {10+distance} ` 0')]
        if decorated:actions.append(op('map_command',name='addsmoke',args=f'10 {10+distance} 100'))
        actions += [diag('exhaust',damage=damage),op('map_command',name='view',args=f'10 {10+distance}')]
        d=document(u,actions,random=dict(streams={'fire_duration':[120]*100}));c=Case(name,d).final(**{'at.2':0})
        # Grid snapshots use raw source terrain characters; decorators remain separate.
        radius=5 if damage>100 else 3;rough=distance<=radius and not decorated and damage//max(1,distance)>100
        c.expect(f'state.maps.field.hexes.{(10+distance)*30+10}.underlying','%' if rough else '`')
        c.expect(f'state.maps.field.hexes.{(10+distance)*30+10}.terrain',':' if decorated else '%' if rough else '&' if distance<=radius else '`')
        yield c
