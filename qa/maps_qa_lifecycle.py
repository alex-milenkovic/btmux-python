"""Source ABI, files, map links, lifetime and downstream member checks."""
import itertools
import json
import re
import struct
import subprocess
from maps_environment_qa import ROOT,OUT,case,check,D,M,F,I,A,V,C
from maps_qa_files import attempt
from maps_qa_oracle import oracle
from maps_qa_storage import dynamic


def abi():
    source=ROOT/'btmux/btmux/btech/src'
    header=(source/'btech/map.h').read_text()
    glue=(source/'include/glue_types.h').read_text()
    declarations=header[header.index('typedef struct mapobj_struct'):header.index('} mapobj;')+9]
    declarations+=header[header.index('typedef struct {\n    XCODE'):header.index('} MAP;')+6]
    path=OUT/'abi-oracle.c'
    path.write_text('typedef long dbref;\n#define NUM_MAPOBJTYPES 10\n#define MAP_NAME_SIZE 30\n'+glue+'\n'+declarations+'\nint qa_abi_sizes[]={sizeof(MAP),sizeof(mapobj),sizeof(void *),sizeof(dbref),sizeof(short),sizeof(long)};\n')
    values={}
    commands=[]
    for profile,bits in (('LP64',64),('ILP32',32)):
        obj=OUT/f'abi-{profile}.o';blob=OUT/f'abi-{profile}.bin'
        for command in (['cc',f'-m{bits}','-c',str(path),'-o',str(obj)],['objcopy','-O','binary','--only-section=.data',str(obj),str(blob)]):
            r=subprocess.run(command,capture_output=True,text=True)
            commands.append({'command':command,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
            if r.returncode:raise RuntimeError(r.stderr)
        values[profile]=list(struct.unpack('<6i',blob.read_bytes()))
    (OUT/'abi-oracle.json').write_text(json.dumps(dict(commands=commands,values=values),indent=2)+'\n')
    return values


def build():
    c=oracle()
    values=abi()
    for profile,(size,obj,pointer,dbref,short,long) in values.items():
        for n in (0,1,3):
            units=[{'name':f'u{i}','id':40+i,'at':[i+1,1,0]} for i in range(n)]
            case('management',f'c-abi-{profile}-{n}',[D('sizes',profile),M('free'),D('sizes',profile)],
                 [check('results.0.sizeof_map',size),check('results.0.sizeof_mapobj',obj),check('results.0.map',size+pointer),check('results.0.mechs',n*(dbref+1+pointer+n*short)),check('results.2.map',size),check('results.2.mechs',0)],units=units)
    directions=((0,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0))
    for axis in range(3):
        for distance in (1,2,3):
            for center in ((4,4),(1,4),(0,4)):
                grid=[[' ']*9 for _ in range(9)]
                x,y=center;grid[y][x]='#'
                for direction in (axis,axis+3):
                    xx,yy=x,y
                    for step in range(1,distance+1):
                        dx,dy=directions[direction];xx+=dx;yy+=dy
                        if xx==0 and dx:yy-=1
                        if 0<=xx<9 and 0<=yy<9:grid[yy][xx]='~' if step==distance else '#'
                raw=''.join(''.join(row) for row in grid)
                expected=list(map(chr,c('bridge',9,9,raw)))
                text='9 9\n'+''.join(''.join((t if t!=' ' else '.')+'0' for t in row)+'\n' for row in grid)
                case('files',f'c-bridge-{axis}-{distance}-{x}-{y}',[F('load_direct')],[check('results.0',0),check('state.maps.main.hexes',expected,project='terrain')],files={'record':{'text':text}})
                if center==(4,4):
                    case('files',f'nobridgify-{axis}-{distance}',[F('load_direct')],[check('state.maps.main.hexes',list(raw),project='terrain')],files={'record':{'text':text+'128: 100 20\n'}})
    longname='abcdefghijklmnopqrstuvwxyz0123456789'
    case('files','filename-thirty-characters',[M('save',longname),M('load',longname)],[check('state.maps.main.name',longname[:30]),check('state.files.'+longname[:30]+'.text','1 1\n.0\n')],map={'size':[1,1]})
    for dims in ((2,2),(1,1),(3,3),(0,0)):
        case('files',f'resize-owned-overlay-{dims[0]}-{dims[1]}',[M('addsmoke',0,0,30),M('resize',*dims),I(),A(30)],
             [check('results.2.maps.main.size',list(dims)),check('results.2.maps.main.objects',[]),check('results.2.events',[],where={'kind':'DECORATION'}),check('state.units.u.at',[1,1,0])]+([check('state.maps.main.hexes.0.terrain',':')] if dims[0] else []),
             map={'size':[2,2]},units=[{'name':'u','at':[1,1,0]}])
    case('files','empty-bits-guard-before-arity',[D('bits','create'),attempt(M('resize'))],[check('results.1.error',contains='Invalid map')])
    for value in (9,10,-4,127):
        case('management',f'addhex-conversion-{value}',[M('addhex','1junk','1junk','%junk',value,'ignored')],[check('state.maps.main.hexes',[min(abs(value),9)],where={'at':[1,1]},project='elevation'),check('state.maps.main.hexes',['%'],where={'at':[1,1]},project='terrain')])
    for count in (0,1,3):
        case('management',f'view-arity-{count}',[attempt(M('view',*([0]*count)))],[check('results.0.error',contains='number')] if count<2 else [check('results.0.value.x',0)])
    for h,w in itertools.product((4,5,24,25),(4,5,40,41)):
        good=5<=h<=24 and 5<=w<=40
        case('management',f'tacsize-boundaries-{h}-{w}',[M('view',5,5,tacsize=f'{h} {w}')],
             [check('results.0.height',min(h if good else 14,9)),check('results.0.width',min(w if good else 21,9)),check('results.0.applied',False)],mode='blocked')
    case('management','list-holes-invalid-records',[F('load_dynamic',count=3),M('list','MECHS','ignored')],
         [check('results.1',contains='2 Mechs On Map'),check('results.1',contains='248 positions open'),check('results.1',contains='3 is first free slot, according to db.')],units=[{'name':'u','id':40}],files={'record':{'hex':dynamic([40,-1,999]).hex()}})
    for arguments in ([],['unknown']):
        case('management','list-refusal-'+str(len(arguments)),[attempt(M('list',*arguments))],[check('results.0.error',contains='Supply' if not arguments else 'Invalid')])
    # Finite recursive links preserve mine bits and replace previous building exits.
    boards=[{'name':'main','id':10,'size':[9,9]},{'name':'child','id':20,'size':[9,9],'cf':100,'cfmax':100},
            {'name':'grandchild','id':30,'size':[9,9],'cf':100,'cfmax':100}]
    attributes={'10':{'BUILDLINKS':'-1 10 999 20'},'20':{'BUILDCOORD':'2,2','BUILDLINKS':'30','BUILDENTRANCE':'0 2 -1 99 ignored'},'30':{'BUILDCOORD':'3,3','BUILDENTRANCE':'0 0 0 0'}}
    case('links','recursive-replace-retains-mines',[D('bits','set',2,2,1),M('updatelinks'),I(),M('updatelinks'),D('bits','query',2,2,1),D('bits','query',2,2,2),D('entrance',0,map='child')],
         [check('results.1',[2,2,7]),check('results.3',[2,2,7]),check('results.4',16),check('results.5',32),check('results.6',{'x':8,'y':4,'direction':'w'}),check('state.maps.main.objects',1,where={'kind':'BUILDING'},length=True)],maps=boards,attributes=attributes)
    cyclic={'10':{'BUILDCOORD':'1,1','BUILDLINKS':'20'},'20':{'BUILDCOORD':'1,1','BUILDLINKS':'10'}}
    case('links','cycle-domain',[M('updatelinks')],[],maps=boards,attributes=cyclic,error='cycle',mode='diagnostic')
    for cf in (0,100):
        copied=[dict(b) for b in boards];copied[1]['cf']=cf
        case('links',f'ordinary-edge-carried-{cf}',[M('updatelinks'),C('speed',64),A(30)],
             [check('state.units.u.mapindex',10 if cf else 20),check('state.units.v.mapindex',10 if cf else 20)],
             maps=copied,attributes=attributes,units=[{'name':'u','id':40,'map':'child','at':[4,0,0],'carrying':41,'in_character':False,'measured_mass':51200},{'name':'v','id':41,'map':'child','at':[4,0,0],'in_character':False,'measured_mass':51200}],random={'seed':5489},mode='ordinary')
    for linked in (True,False):
        actions=[M('linked')]
        if not linked:actions.append(M('delobj','LINKED'))
        actions += [C('speed',64),A(30)]
        def verify_edge(data,path,linked=linked):
            row=data['state']['units']['u']
            assert (row['y']>0 if linked else row['y']==0)
            assert (row['desired_speed']>0 if linked else row['desired_speed']==0)
        case('links',f'ordinary-wrap-{linked}',actions,[check('state.units.u.mapindex',1000)],checker=verify_edge,units=[{'name':'u','at':[4,0,0]}],mode='ordinary')
