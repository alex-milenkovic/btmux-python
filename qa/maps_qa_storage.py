"""Independent storage cases: source packed indices and portable wire contract."""
import struct
from maps_environment_qa import case,examples,check,D,M,F,I

def dynamic(ids,flags=None,los=None):
    n=len(ids);flags=flags if flags is not None else [0]*n;los=los if los is not None else [[0]*n for _ in ids]
    return struct.pack('<'+'i'*n,*ids)+bytes(flags)+b''.join(struct.pack('<'+'H'*n,*r) for r in los)+struct.pack('<I',0x67134269)
def build():
    for i,r in enumerate(examples('bits',1)):
        x=int(r['x']);b=1 if r['kind']=='mine' else 2
        row=[0]*3;row[x//4]=b<<(2*(x%4))
        case('bits',f'example-01-{i}',[D('bits','query',x,0,b),D('bits','set',x,0,b),D('bits','query',x,0,b),D('bits','size')],
             [check('results.0',0),check('results.2',int(r['value'])),check('results.3',3),check('state.maps.main.objects.0.rows.0',row)])
    for i,r in enumerate(examples('bits',2)):
        case('bits',f'example-02-{i}',[D('bits','set',1,0,1),D('bits','set',1,0,2),D('bits','clear',int(r['selector'])),D('bits','query',1,0,1),D('bits','query',1,0,2)],
             [check('results.3',int(r['mine'])),check('results.4',int(r['hangar']))])
    for i,r in enumerate(examples('bits',3)):
        setup=[];rows=[None]*9
        if r['state']!='never-allocated':setup=[D('bits','set',1,0,1)];rows[0]=[4,0,0]
        if r['state']=='allocated-all-zero':setup.append(D('bits','unset',1,0,1));rows[0]=None
        if r['state']=='two-nonzero-rows':setup.append(D('bits','set',1,1,1));rows[1]=[4,0,0]
        wire=b'\x1b'+(b'\x09'+b''.join(struct.pack('<Q',int(v is not None)) for v in rows)+b''.join(bytes(v) for v in rows if v is not None) if any(v is not None for v in rows) else b'')+b'\0\x27'
        case('bits',f'example-03-{i}',setup+[F('save_objects'),D('bits','size')],[check('state.files.record.hex',wire.hex()),check(f'results.{len(setup)+1}',int(r['size']))])
    for x in range(9):
        for b in (1,2):
            v=b<<(2*(x%4));row=[0]*3;row[x//4]=v
            case('bits',f'all-shifts-{x}-{b}',[D('bits','unset',x,2,b),I(),D('bits','set',x,2,b),D('bits','query',x,2,b),D('bits','unset',x,2,b),D('bits','size'),F('save_objects')],
                 [check('results.1.maps.main.objects.0.rows.2',None),check('results.3',v),check('results.5',3),check('state.files.record.hex','1b0027'),check('state.maps.main.objects.0.rows.2',None)])
    for width in (4,8,12):
        case('bits',f'corrected-edge-{width}',[D('bits','set',width-1,0,1),D('bits','query',width-1,0,1)],[check('results.1',64)],map={'size':[width,1]})
        case('bits',f'absent-edge-{width}',[D('bits','query',width-1,0,1)],[check('results.0',0)],map={'size':[width,1]})
    wire=b'\x1b\x09'+struct.pack('<Q',0xFEDCBA9876543210)+bytes([1,2,3])+b'\0\x27'
    case('bits','attached-load',[F('load_objects'),D('bits','query',0,0,1)],
         [check('results.1',1),check('state.maps.main.objects.0.rows',[[1,2,3]]),check('state.maps.main.external_effects',[])],
         map={'size':[9,1]},files={'record':{'hex':wire.hex()}})
    for n in (2,5,9,10,11):
        case('bits',f'short-load-{n}',[F('load_objects')],[],map={'size':[9,1]},files={'record':{'hex':wire[:n].hex()}},error='read-error')
    terrain={'grass':' ','water':'~','rough':'%'}
    for i,r in enumerate(examples('coding',1)):
        pairs=[(terrain[t[:-1]],int(t[-1])) for t in r['requests'].split(',')]
        actions=[D('coding_index',*pair) for pair in pairs];indices=list(map(int,r['indices'].split(',')))
        checks=[check(f'results.{j}',v) for j,v in enumerate(indices)]
        for pair,index in zip(pairs,indices):checks.append(check(f'results.{len(actions)}',list(pair)));actions.append(D('coding_inverse',index))
        case('coding',f'example-01-{i}',actions,checks)
    for i,r in enumerate(examples('coding',2)):
        n=int(r['count']);actions=[D('coding_index',' ',j) for j in range(n)]+[D('coding_initialize'),D('coding_index',' ',0),D('coding_inverse',0)]
        case('coding',f'example-02-{i}',actions,[check(f'results.{n+1}',n),check(f'results.{n+2}', [' ',0] if n==0 else ['\0',0])])
    pairs=[(chr(i//10),i%10) for i in range(255)]
    case('coding','all-255-allocations',[D('coding_index',*v) for v in pairs]+[D('coding_inverse',i) for i in range(255)],
         [check(f'results.{i}',i) for i in range(255)]+[check(f'results.{255+i}',list(v)) for i,v in enumerate(pairs)])
    case('coding','allocation-256-boundary',[D('coding_index',*v) for v in pairs]+[D('coding_index',chr(25),5)],[],error='at most 255',mode='diagnostic')
    for char,elev in (('\x80',0),(' ',10),(' ',-1)):
        case('coding',f'unsafe-{ord(char)}-{elev}',[D('coding_index',char,elev)],[],error='coding requires')
    # Byte-exact dynamic fixtures originate in struct packing of the documented portable conversion.
    for i,r in enumerate(examples('dynamic',1)):
        ids=[] if r['before']=='empty' else list(map(int,r['before'].split(',')))
        identity=int(r['unit']);expected=list(map(int,r['after'].split(',')))
        units=[{'name':'u','id':identity,'map':'park'}]
        maps=[{'name':'main','id':1000,'size':[9,9]},{'name':'park','id':1001,'size':[9,9]}]
        slot=int(r['slot'])
        setup=[F('load_dynamic',count=len(ids)),D('membership_state',{'mapnumber':slot}),D('membership_add')]
        case('dynamic',f'example-01-{i}',setup,[check('state.maps.main.roster_ids',expected),check('state.units.u.mapnumber',slot)],maps=maps,units=units,files={'record':{'hex':dynamic(ids).hex()}})
    for i,r in enumerate(examples('dynamic',2)):
        ids=list(map(int,r['before'].split(',')));actions=[F('load_dynamic',count=len(ids))]
        units=[]
        if r['operation']=='eliminate':actions.append(D('eliminate_empties'))
        else:
            identity=int(r['operation'][6:]);units=[{'name':'u','id':identity}]
            actions += [D('membership_state',{'mapnumber':ids.index(identity)}),D('membership_remove')]
        case('dynamic',f'example-02-{i}',actions,[check('state.maps.main.roster_ids',list(map(int,r['after'].split(','))))],units=units,files={'record':{'hex':dynamic(ids).hex()}})
    for i,r in enumerate(examples('dynamic',3)):
        n=int(r['count']);wire=dynamic([10,20],[3,255],[[1,60000],[42,65535]]) if n else dynamic([])
        label=r['condition'];error=None
        if label.startswith('short'):wire=wire[:{'short-roster':7,'short-flags':9,'short-LOS':13}[label]];error='read-error'
        if label=='wrong-magic':wire=b'\0'*4;error='magic-error'
        if label=='missing-magic':wire=b'';error='read-error'
        checks=[] if error else [check('state.files.saved.hex',wire.hex())]
        case('dynamic',f'example-03-{i}',[F('load_dynamic',count=n),F('save_dynamic','saved')],checks,files={'record':{'hex':wire.hex()}},error=error)
    wire=dynamic([10,-1,30],[8,255,4],[[1,2,3],[4,5,6],[7,8,9]])
    case('dynamic','hole-preserves-directed-los',[F('load_dynamic',count=3),D('membership_add'),F('save_dynamic','saved')],
         [check('state.maps.main.roster_ids',[10,40,30]),check('state.maps.main.slot_flags',[8,1,4]),check('state.maps.main.slot_los',[[1,2,3],[4,5,6],[7,8,9]])],
         units=[{'name':'u','id':40}],files={'record':{'hex':wire.hex()}})
    wire=dynamic([10,20],[128,255],[[1,65535],[456,7]])
    def fresh(data,path):
        return ({'map':{'size':[9,9]},'units':[{'name':'u','id':10},{'name':'v','id':20}], 'config':{'periodic_updates':False},'actions':[F('load_dynamic','saved',count=2),F('save_dynamic','again')]},
                [check('state.maps.main.roster_ids',[10,20]),check('state.maps.main.slot_los',[[1,65535],[456,7]]),check('state.files.again.hex',wire.hex())])
    case('dynamic','fresh-process-directed-restore',[F('load_dynamic',count=2),F('save_dynamic','saved')],[check('state.files.saved.hex',wire.hex())],files={'record':{'hex':wire.hex()}},followup=fresh)
