"""Source MT/Number/Roll checks through the documented CLI."""
from core_simulation_qa import A,D,I,K,case,check as q,examples


def build():
    for n,r in enumerate(examples('randomness',1)):
        rng={} if r['init']=='default' else {'seed':5489} if r['init']=='seed5489' else {'array_seed':[0x123,0x234,0x345,0x456]}
        index=int(r['index'])
        case('randomness',f'example-01-{n}',[D('genrand_int32')]*(index+1),[q(f'results.{index}',int(r['word'])),q('state.random.words_consumed',index+1)],random=rng)
    for n,r in enumerate(examples('randomness',2)):
        words=[] if r['words']=='none' else [int(w,16) for w in r['words'].split(',')]
        case('randomness',f'example-02-{n}',[D('Number',int(r['low']),int(r['high']))],[q('results.0',int(r['result'])),q('state.random.words_consumed',int(r['used']))],random={'raw32':words})
    for n,r in enumerate(examples('randomness',3)):
        case('randomness',f'example-03-{n}',[K('heartbeat')]*99+[K('dispatch') for _ in range(int(r['tick']))]+[D('MNumber',1,6)],
             [q('results.'+str(99+int(r['tick'])),int(r['result'])),q('state.random.words_consumed',int(r['draws']))],
             map={'current_tick':100},units=[dict(name='u',core=dict(rnd=11,last_rnd_update=0))],random={'raw32':[40]},config={'periodic_updates':False})
    for n,r in enumerate(examples('randomness',4)):
        pairs=[list(map(int,p.split(','))) for p in r['pairs'].split(';')]
        hist=[0]*11
        for pair in pairs:hist[sum(pair)-2]+=1
        case('randomness',f'example-04-{n}',[D('Roll') for p in pairs]+[D('init_stat',123),D('do_show_stat'),I(),I()],
             [q('state.random.histogram',hist),q('state.random.total_rolls',int(r['total'])),q(f'results.{len(pairs)+2}',same_as=f'results.{len(pairs)+3}')],
             random={'raw32':[(d-1)<<29 for pair in pairs for d in pair]})
    for n,r in enumerate(examples('randomness',5)):
        prior=[] if r['prior']=='none' else r['prior'].split(',')
        case('randomness',f'example-05-{n}',[D('genrand_'+g) for g in prior+[r['generator']]],
             [q(f'results.{len(prior)}',float(r['value']),tolerance=1e-15),q('state.random.words_consumed',int(r['used']))],random={'seed':5489})
    for name,div,offset in [('real1',4294967295,0),('real2',4294967296,0),('real3',4294967296,.5)]:
        for word in (0,0xffffffff):
            case('randomness',f'{name}-endpoint-{word}',[D('genrand_'+name)],[q('results.0',(word+offset)/div,tolerance=1e-15),q('state.random.words_consumed',1)],random={'raw32':[word]})
    case('randomness','all-roll-buckets',[D('Roll') for _ in range(11)]+[D('Number',7,7),D('do_show_stat'),D('do_show_stat')],
         [q('results.12',same_as='results.13'),q('state.random.histogram',[1]*11),q('state.random.total_rolls',11),q('state.random.words_consumed',22)],
         random={'raw32':[word for total in range(2,13) for word in ((max(1,total-6)-1)<<29,(min(6,total-1)-1)<<29)]})
    case('randomness','no-roll-statistics',[D('do_show_stat')],[q('results.0',['No rolls to show statistics for!']),q('state.random.words_consumed',0)])
    case('randomness','repeated-rejection',[D('Number',-3,2)],[q('results.0',2),q('state.random.words_consumed',4)],random={'raw32':[0xffffffff,0xe0000000,0xc0000000,0xa0000000]})
    for name,doc,actions,error in [('unordered',{},[D('Number',4,3)],'bound'),('empty-array',{'random':{'array_seed':[]}},[], 'empty'),('exhausted',{'random':{'raw32':[]}},[D('genrand_int32')],'exhaust'),('missing-finite',{'random':{'streams':{}}},[D('Roll')],'stream')]:
        case('randomness','invalid-'+name,actions,[],error=error,**doc)

    case('randomness','reseed-replays-and-retains-roll-history',[D('Roll'),D('init_genrand',5489),D('genrand_int32'),D('init_genrand',5489),D('genrand_int32')],
         [q('results.2',3499211612),q('results.4',3499211612),q('state.random.total_rolls',1)],repeat=True)
    case('randomness','mnumber-independent-units-cross-bounds',[D('MNumber',1,6),D('MNumber',-2,2),dict(op='diagnose',unit='v',kind='MNumber',args=[1,6]),*[K('dispatch')]*6,D('MNumber',1,6),dict(op='diagnose',unit='v',kind='MNumber',args=[1,6]),D('MNumber',7,7)],
         [q('results.0',6),q('results.1',-1),q('results.2',3),q('results.9',3),q('results.10',1),q('results.11',7),q('state.random.words_consumed',2),q('state.units.u.rnd',20),q('state.units.v.rnd',30)],
         maps=[{'name':'main','current_tick':100},{'name':'other','current_tick':200}],units=[dict(name='u',core={'rnd':11,'last_rnd_update':0}),dict(name='v',map='other',core={'rnd':2,'last_rnd_update':0})],config={'periodic_updates':False,'initial_global_tick':99},random={'raw32':[40,60]})

    import struct
    f=lambda x:struct.unpack('f',struct.pack('f',x))[0]
    chances=[1,2,3,4,5,6,5,4,3,2,1]
    rows=['#    Rolls %Current  Optimal Rolls %Optimal  %Hit Chance  %Miss Chance']
    for i,weight in enumerate(chances):
        ideal=f(weight*100/36);current=f(100/11)
        hit=f(f(sum(chances[i:])/36)*100)
        optimal=int(f(f(ideal/100)*11))
        rows.append(f'{i+2:<3d} {1:6d} {current:8.3f} {optimal:14d} {ideal:8.3f} {hit:12.3f} {100-hit:13.3f}')
    rows.append('Total rolls: 11')
    case('randomness','all-statistics-columns',[D('Roll') for _ in range(11)]+[D('do_show_stat')],
         [q('results.11',rows)],random={'raw32':[word for total in range(2,13) for word in ((max(1,total-6)-1)<<29,(min(6,total-1)-1)<<29)]})
