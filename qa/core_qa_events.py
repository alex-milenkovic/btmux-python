"""CLI cases derived from tick.c, events.c, mech.startup.c and mech.events.c."""
from core_simulation_qa import A,C,D,I,K,S,case,check as q,examples


def events(path, kind, expected, deadlines=False):
    return q(path+'.events', expected, where={'kind':kind}, **({'project':'deadline'} if deadlines else {'length':True}))


def build():
    for n,r in enumerate(examples('clocks',1)):
        case('clocks',f'example-01-{n}',[K(x) for x in r['sequence'].split(',')],
             [q('state.clocks',dict(wall=int(r['wall']),event=int(r['event']),global_tick=int(r['heart'])))])
    for n,r in enumerate(examples('clocks',2)):
        case('clocks',f'example-02-{n}',[K('heartbeat_stop')]+[K('heartbeat_'+x) for x in r['commands'].split(',')],
             [q('state.heartbeat_timer.count',int(r['pending']))])
    for n,r in enumerate(examples('clocks',3)):
        kw = {}
        if r['kind'] in ('AUTO','OTHER'):
            kw['objects']=[dict(name='obj',id=42,type=r['kind'],**({'mymech':'u'} if r['kind']=='AUTO' else {}))]
        if r['kind']=='MECH': kw['units']=[dict(name='u',sections=[dict(index=0,recycle=10)],core={'last_weapon_recycle':-1})]
        checks=[q('state.clocks.global_tick',1)]
        if r['kind']=='MECH': checks.append(q('state.units.u.sections.0.recycle',9))
        if r['kind']=='AUTO': checks.extend([q('state.objects.obj.external_effects',3,length=True),q('state.objects.obj.external_effects',[False]*3,project='applied')])
        case('clocks',f'example-03-{n}',[K('heartbeat')],checks,mode='blocked' if r['kind']=='AUTO' else 'diagnostic',**kw)
    case('clocks','restart-at-nonzero',[K('heartbeat_stop'),K('skip_seconds',seconds=17),K('heartbeat_init'),K('heartbeat_init'),I(),K('heartbeat'),I(),K('heartbeat_stop'),K('heartbeat_stop')],
         [q('results.4.heartbeat_timer',dict(count=1,deadline=18)),q('results.6.heartbeat_timer',dict(count=1,deadline=18)),q('state.heartbeat_timer.count',0),q('state.clocks.global_tick',1)])
    case('clocks','auto-missing-unit',[K('heartbeat')],[q('state.objects.obj.external_effects',[])],objects=[dict(name='obj',id=42,type='AUTO')])
    for ticks,profile,count in [(179,[1],2),(180,[1],3),(179,None,3)]:
        case('clocks',f'auto-profile-{ticks}-{profile is None}',[K('heartbeat')],
             [q('state.objects.obj.external_effects',count,length=True)],
             objects=[dict(name='obj',id=42,type='AUTO',mymech='u',weaplist=profile)],config={'initial_global_tick':ticks},mode='blocked')
    for n,r in enumerate(examples('hooks',1)):
        actions=[D('cancel_events','PLOS'),S('very_fake_func',cancelled=bool(int(r['zombie']))),I()]
        actions += [K('dispatch')] if r['method']=='due' else [D('run_by_type','CUSTOM')]
        case('hooks',f'example-01-{n}',actions,[q('state.event_trace',[] if r['trace']=='none' else ['pre','callback','post'],project='phase'),q('state.event_history',[0]*100),q('state.units.u',same_as='results.2.units.u',omit=['events'])])
    for n,r in enumerate(examples('hooks',2)):
        expected=[] if r['order']=='none' else list(map(int,r['order'].split(',')))
        counts=list(map(int,r['counts'].split(',')))
        checks=[q('results.1',1+len(expected),length=True)]
        for i,t in enumerate(expected):
            checks.extend([q(f'results.1.{i+1}',contains=f'{counts[t]/sum(counts)*100:.3f}%'),q(f'results.1.{i+1}',t,leading_integer=True)])
        case('hooks',f'example-02-{n}',[D('history_input',counts),D('debug_EventTypes','history')],checks)
    for n,r in enumerate(examples('hooks',3)):
        actions=[D('cancel_events','PLOS')]+[S('mech_fall_event',cancelled=i<int(r['cancelled'])) for i in range(3)]+[D('debug_EventTypes',''),I(),I()]
        case('hooks',f'example-03-{n}',actions,[q('results.4',contains=r['total']+' total'),q('results.5',same_as='results.6'),q('state.random.words_consumed',0)])
    for n,r in enumerate(examples('startup',1)):
        case('startup',f'example-01-{n}',[C('startup',*([] if r['argument']=='none' else [r['argument']])),A(int(r['tick']))],
             [q('results.0.accepted',True),q('state.units.u.started',bool(int(r['started']))),q('state.units.u.boot_messages',int(r['messages']),length=True)],
             units=[dict(name='u',**{'class':r['kind']},started=False,pilot=False,actor={'wizard':bool(int(r['wizard']))})],mode='ordinary')
    for n,r in enumerate(examples('startup',2)):
        case('startup',f'example-02-{n}',[C('startup',*([] if r['argument']=='none' else [r['argument']]))],
             [q('results.0.accepted',bool(int(r['scheduled']))),events('state','STARTUP',int(r['scheduled'])),q('state.random.words_consumed',0)],
             units=[dict(name='u',started=False,pilot=False,heat=float(r['heat']),actor={'wizard':bool(int(r['wizard']))})],mode='ordinary')
    for n,r in enumerate(examples('startup',3)):
        case('startup',f'example-03-{n}',[C('startup'),A(int(r['tick']))],
             [q('results.0.accepted',True),q('state.units.u.destroyed',bool(int(r['destroyed']))),events('state','STARTUP',int(r['pending']))],
             units=[dict(name='u',**{'class':r['kind']},started=False,pilot=False,at=[3,3,-2],specials2=0x100000 if int(r['proof']) else 0)],
             map=dict(default=['WATER',2]),mode='ordinary')
    for n,r in enumerate(examples('startup',4)):
        t=int(r['abort'])
        case('startup',f'example-04-{n}',[C('startup'),A(t),C('shutdown'),C('startup'),A(30)],
             [q('results.2.accepted',True),q('results.3.accepted',True),q('state.units.u.started',True),q('state.units.u.boot_messages',t//5+6,length=True),q('state.units.u.last_startup',t+30),events('state','STARTUP',0)],
             units=[dict(name='u',started=False,pilot=False)],mode='ordinary')
    for arg,wiz,accepted,due in [('',False,True,5),(' o',False,False,None),(' OvEr',True,True,1),('override',True,True,1),('override ',False,True,5),('overrides',False,True,5),('x',False,True,5)]:
        case('startup',f'prefix-{arg.encode().hex()}-{wiz}',[C('startup',arg)],
             [q('results.0.accepted',accepted),events('state','STARTUP',[] if due is None else [due],True)],
             units=[dict(name='u',started=False,actor={'wizard':wiz})],mode='ordinary')
    for label,actor,accepted in [('invalid',{'valid':False},False),('dead',{'alive':False},False),('robot',{'alive':False,'robot':True},True),('hardcode',{'alive':False,'hardcode':True},True)]:
        case('startup','actor-'+label,[C('startup')],[q('results.0.accepted',accepted)],units=[dict(name='u',started=False,pilot=False,actor=actor)],mode='ordinary')
    case('startup','six-section-recycle-reset',[C('startup')],[q('state.units.u.sections',[0,0,0,0,9,0,0,9],project='recycle')],
         units=[dict(name='u',started=False,sections=[dict(index=i,recycle=9) for i in range(8)])],mode='ordinary')
    for n,r in enumerate(examples('shutdown',1)):
        speed=float(r['mp'])*10.75
        case('shutdown',f'example-01-{n}',[C('shutdown')],[q('state.units.u.speed',0),q('state.units.u.desired_speed',0),q('state.units.u.messages',int(r['falls']),count_text='Mech fell')],
             units=[dict(name='u',speed=speed,desired_speed=speed)],mode='ordinary')
    for n,r in enumerate(examples('shutdown',2)):
        case('shutdown',f'example-02-{n}',[C('shutdown')],[q('state.units.u.started',bool(int(r['started']))),events('state','FALL',[] if r['due']=='none' else [int(r['due'])],True)],
             units=[dict(name='u',**{'class':r['kind']},at=[3,3,int(r['height'])],status=8|(64 if int(r['jumping']) else 0),actor={'wizard':bool(int(r['wizard']))})],mode='ordinary')
    for n,r in enumerate(examples('shutdown',3)):
        actions=[C('startup')] if r['state']=='starting' else []
        actions += [I(),C('shutdown')]
        unit=dict(name='u',started=r['state'] in ('started','MW-started'),target=8,charge_target=9,masc_counter=3,scharge_counter=4,status2=0x20|1|0x10000)
        if r['state']=='MW-started':unit['class']='MW'
        checks=[q(f'results.{len(actions)-1}.accepted',r['profile']!='refused')]
        for key,value in [('target',-1),('charge_target',-1),('masc_counter',0),('scharge_counter',0)]:
            checks.append(q('state.units.u.'+key,value) if r['profile']=='full' else q('state.units.u.'+key,same_as=f'results.{len(actions)-2}.units.u.'+key))
        case('shutdown',f'example-03-{n}',actions,checks,units=[unit],mode='ordinary')
    for n,r in enumerate(examples('recovery',1)):
        case('recovery',f'example-01-{n}',[D('ProlongUncon',30),A(int(r['now'])),D('ProlongUncon',int(r['length']))],
             [events('state','RECOVERY',[int(r['due'])],True)],config={'periodic_updates':False})
    for n,r in enumerate(examples('recovery',2)):
        case('recovery',f'example-02-{n}',[S('unstun_crew_event',int(t)) for t in r['deadlines'].split(',')]+[A(int(r['now']))],
             [q('state.units.u.tank_crit_status',0x10 if int(r['stunned']) else 0,mask=0x10),q('state.units.u.messages',int(r['messages']),count_text='Your head clears')],
             units=[dict(name='u',**{'class':'VEH_GROUND'},tank_crit_status=0x10)],config={'periodic_updates':False})
    for n,r in enumerate(examples('recovery',3)):
        case('recovery',f'example-03-{n}',[D('callback','mech_crewstun_event')],
             [q('state.units.u.crit_status',0,mask=0x40000000),q('state.units.u.messages',int(r['messages']),count_text='recover from your stunning')],
             units=[dict(name='u',started=r['state']!='stopped',destroyed=r['state']=='destroyed',crit_status=0x40000000)])
    for length in (0,1,30):
        case('recovery',f'fresh-{length}',[D('ProlongUncon',length)], [events('state','RECOVERY',[max(1,length)],True),q('state.units.u.status',8192,mask=8192)])
    case('recovery','cancel-one-crew',[S('unstun_crew_event',5,cancelled=True),S('unstun_crew_event',10),A(10)],
         [q('state.units.u.messages',1,count_text='Your head clears')],units=[dict(name='u',**{'class':'VEH_GROUND'})],config={'periodic_updates':False})
