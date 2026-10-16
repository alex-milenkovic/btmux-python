"""Independent typed object, overlay and local link CLI verification."""
import itertools
import struct
from maps_environment_qa import case,examples,check,D,M,F,I,A,V
from maps_qa_files import attempt
from maps_qa_oracle import oracle

REC=struct.Struct('<hhibihq')
def record(kind,x=0,y=0,obj=0,dc=0,ds=0,di=0):return bytes([kind+1])+REC.pack(x,y,obj,0,dc,ds,di)
def build():
    objects=[{'kind':'FIRE','x':2,'y':1,'obj':12,'datac':32},{'kind':'FIRE','x':1,'y':1,'obj':11,'datac':32},
             {'kind':'BUILDING','x':4,'y':1,'obj':14},{'kind':'BUILDING','x':3,'y':1,'obj':13}]
    wire=b'\x1b'+record(0,1,1,11,32)+record(0,2,1,12,32)+record(4,3,1,13)+record(4,4,1,14)+b'\0\x27'
    for i,r in enumerate(examples('objects',1)):
        actions=[F('save_objects')];checks=[check('state.files.record.hex',wire.hex())];files={}
        if r['operation']=='save-then-load':actions.append(F('load_objects'));checks.append(check('state.maps.main.objects',[12,11,14,13],project='obj'))
        elif r['operation'].startswith('load-bad'):
            bad=(b'X'+wire[1:]) if r['operation']=='load-bad-start' else wire[:-1]+b'X'
            files={'bad':{'hex':bad.hex()}};actions.append(attempt(F('load_objects','bad')))
            checks += [check('results.1.error',contains='marker'),check('state.maps.main.objects',[11,12,13,14] if r['operation']=='load-bad-start' else [12,11,14,13],project='obj')]
        case('objects',f'example-01-{i}',actions,checks,map={'size':[9,9],'map_objects':objects},files=files)
    for i,r in enumerate(examples('objects',2)):
        zap=int(r['zap'])
        case('objects',f'example-02-{i}',[M('addsmoke',0,0,30),D('object_delete',1,0,zap)],
             [check('state.maps.main.hexes.0.terrain','~' if r['terrain']=='water' else ':'),check('state.events',int(r['event']=='retained'),length=True),check('state.maps.main.flags',1,mask=1)],
             map={'size':[1,1],'default':['WATER',2]})
    for i,r in enumerate(examples('objects',3)):
        objs=[{'kind':'MINE','x':1,'y':1,'datac':1,'datas':5},{'kind':'MINE','x':1,'y':1,'datac':1,'datas':5},
              {'kind':'BLZ','x':1,'y':1},{'kind':'BLZ','x':2,'y':2}]
        good=r['recalculate']!='type-error'
        case('objects',f'example-03-{i}',[attempt(M('delobj',*r['selector'].split(',')))],
             ([check('results.0.value',int(r['count'])),check('state.maps.main.objects',4-int(r['count']),length=True)] if good else [check('results.0.error',contains='Invalid type'),check('state.maps.main.objects',4,length=True)]),map={'size':[9,9],'map_objects':objs})
    for n in (0,1,2,5,len(wire)-3,len(wire)-1):
        case('objects',f'truncated-stream-{n}',[F('load_objects')],[],files={'record':{'hex':wire[:n].hex()}},error='read-error')
    case('objects','invalid-type',[F('load_objects')],[],files={'record':{'hex':'1bff0027'}},error='invalid object type')
    case('objects','lookup-prepend-and-termination',[D('object_find',1,1,-1),D('object_first',0),D('object_next',0,0),D('object_next',0,1),D('object_find',8,8,-1)],
         [check('results.0.values',[1,1,11,0,32,0,0]),check('results.1',same_as='results.0'),check('results.2.values',[2,1,12,0,32,0,0]),check('results.3',None),check('results.4',None)],map={'size':[9,9],'map_objects':objects})
    for index in range(3):
        case('objects',f'delete-list-position-{index}',[D('object_delete',9,index,1)],
             [check('state.maps.main.objects',[v for j,v in enumerate([3,2,1]) if j!=index],project='obj'),check('state.maps.main.flags',1,mask=1)],
             map={'size':[9,9],'map_objects':[{'kind':'BLZ','obj':v} for v in (1,2,3)]})
    case('objects','MAPO-guard',[V(flags=0),D('object_delete',9,0,1)],
         [check('results.1',False),check('state.maps.main.objects',1,length=True)],map={'size':[9,9],'map_objects':[{'kind':'BLZ'}]})
    case('objects','build-delete-reciprocal',[D('object_delete',4,0,1)],
         [check('state.maps.inside.objects',[]),check('state.maps.inside.onmap',0)],maps=[{'name':'main','id':10,'map_objects':[{'kind':'BUILDING','obj':20}]},{'name':'inside','id':20,'onmap':10,'map_objects':[{'kind':'LEAVE','obj':10}]}])
    for i,r in enumerate(examples('decorations',1)):
        actions=[M('addsmoke',1,1,30)]
        if r['action']!='none':
            actions += [A(10),M('delobj','SMOKE',1,1) if r['action']=='delete-at-10' else M('addsmoke',1,1,40)]
            remaining=int(r['tick'])-10
        else:remaining=int(r['tick'])
        actions.append(A(remaining))
        case('decorations',f'example-01-{i}',actions,[check('state.maps.main.hexes',['~' if r['terrain']=='water' else ':'],where={'at':[1,1]},project='terrain'),check('state.events',int(r['pending']),where={'kind':'DECORATION'},length=True)],
             map={'size':[3,3],'hexes':[{'at':[1,1],'terrain':'WATER','elevation':2}]},random={'streams':{}})
    for i,r in enumerate(examples('decorations',2)):
        first=int(r['first']);duration=int(r['duration'])
        case('decorations',f'example-02-{i}',[M('addfire',0,0,duration),I(),A(first)],
             [check('results.1.maps.main.objects.0.datas',duration),check('results.1.maps.main.objects.0.deadline',first),check('state.maps.main.objects.0.datas',duration-first),check('state.events.0.deadline',int(r['deadline']))],
             map={'size':[1,1],'default':['LIGHT_FOREST',0],'windspeed':int(r['wind'])},random={'streams':{'fire_spread':[2]*4}})
    for i,r in enumerate(examples('decorations',3)):
        names={'light-forest':'LIGHT_FOREST','heavy-forest':'HEAVY_FOREST','water':'WATER'}
        case('decorations',f'example-03-{i}',[M('addfire',0,0,120),D('decoration_callback',0,0,'fire')],
             [check('state.maps.main.hexes.0.terrain',{'grass':' ','rough':'%','water':'~'}[r['terrain']]),check('state.events',[]),check('draws',int(r['draw']=='consumed'),length=True)],
             map={'size':[1,1],'default':[names[r['underlying']],0]},random={'streams':{'fire_dissipation':[int(r['roll'])]}})
    for group,duration in itertools.product(range(3),(-1,0,1,30)):
        terrain='&' if group==0 else ':' if group==1 else '@'
        deadline=max(1,duration) if group==1 and duration else 60 if group==0 and duration else None
        case('decorations',f'typed-duration-{group}-{duration}',[D('decoration',0,0,group,terrain,duration)],
             [check('results.0',deadline),check('state.maps.main.objects.0.datas',duration),check('state.maps.main.objects.0.datac',126),check('state.maps.main.hexes.0.terrain',terrain)],map={'size':[1,1],'default':['WATER',2]})
    for old,new in itertools.product(range(3),repeat=2):
        chars=['&',':','@']
        case('decorations',f'replace-{old}-{new}',[D('decoration',0,0,old,chars[old],30),A(10),D('decoration',0,0,new,chars[new],40),A(20)],
             [check('state.maps.main.objects',1,length=True),check('state.maps.main.objects.0.datac',64 if old==2 else 126),check('state.maps.main.hexes.0.terrain',chars[new]),check('state.events',int(new<2),length=True)],
             map={'size':[1,1],'default':['WATER',2]},random={'streams':{}})
    case('decorations','external-edit-before-delete',[M('addsmoke',0,0,30),M('addhex',0,0,'%',3),M('delobj','SMOKE')],
         [check('state.maps.main.hexes.0.terrain','~'),check('state.maps.main.hexes.0.elevation',3),check('state.events',[])],map={'size':[1,1],'default':['WATER',2]})
    for command in ('addfire','addsmoke'):
        for x,y in ((-1,0),(0,-1),(9,0),(0,9)):
            case('decorations',f'out-of-bounds-{command}-{x}-{y}',[M(command,x,y,30)],[check('state.maps.main.objects',[]),check('state.events',[]),check('results.0',contains=f'({x},{y})')])
    case('decorations','loaded-objects-do-not-rearm',[M('addsmoke',0,0,30),F('save_objects'),F('load_objects'),I(),A(30)],
         [check('results.3.maps.main.objects.0.deadline',None),check('state.maps.main.objects',1,length=True),check('state.maps.main.external_effects.0.service','source orphan decoration'),check('state.maps.main.external_effects.0.applied',False)],map={'size':[1,1]},mode='diagnostic')
    c=oracle()
    directions={'north':0,'east':1,'south':2,'west':3}
    for i,r in enumerate(examples('links',1)):
        value=r['xy'];xy=[None,None] if value=='unset' else [None if v=='unset' else int(v) for v in value.split(',')]
        case('links',f'example-01-{i}',[D('parse_coord',directions[r['direction']],r['input'])],[check('results.0',[r['result']=='success',*xy])],map={'size':[9,7]})
    for width,height,direction,text in itertools.product((1,8,9),(1,6,7),range(4),('0','-1','99','abc','1,x','x,2','99,-2','1 ,2',' +3, -4')):
        expected=c('parse',width,height,direction,text,71,72);expected[0]=bool(expected[0])
        slug=text.replace(' ','s').replace(',','c').replace('+','p')
        case('links',f'c-parse-{width}-{height}-{direction}-{slug}',[D('parse_coord',direction,text,71,72)],[check('results.0',expected)],map={'size':[width,height]})
    for i,r in enumerate(examples('links',2)):
        case('links',f'example-02-{i}',[M('block',1,1,int(r['radius']),int(r['team'])),D('blocked_lz',1,1)],[check('results.1',r['blocked']=='true')],units=[{'name':'u','team':2}])
    for i,r in enumerate(examples('links',3)):
        actions=[]
        for step in r['sequence'].split(','):
            if step=='set':actions.append(M('linked'))
            elif step=='delete-type':actions.append(M('delobj','LINKED'))
        actions.append(D('linked'))
        case('links',f'example-03-{i}',actions,[check(f'results.{len(actions)-1}',r['linked']=='true'),check('state.maps.main.objects',int(r['count']),where={'kind':'LINKED'},length=True)])
