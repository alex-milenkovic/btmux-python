"""Independent text-file, administration, condition and visibility cases."""
from maps_environment_qa import case,examples,check,D,M,F,I,A,V,C

def attempt(action):return {'op':'map_attempt','action':action}
def hexcheck(path,x,y,terrain,elev):
    return check(path,[{'at':[x,y],'terrain':terrain,'elevation':elev,'underlying':terrain}],where={'at':[x,y]})

def build():
    for i,r in enumerate(examples('files',1)):
        texts={'zero-width':'0 2\n','width-1001':'1001 1\n','short-row':'2 2\n.0.0\n','valid-2x2':'2 2\n~1%2\n.0.0\n','unknown-terrain-2x2':'2 2\n$0.0\n.0.0\n'}
        files={} if r['kind']=='missing' else {'record':{'text':texts[r['kind']]}}
        code=int(r['code'])
        case('files',f'example-01-{i}',[I(),M('check','record'),I(),M('load','record'),I()],
             [check('results.1',code),check('results.2.maps.main.hexes',same_as='results.0.maps.main.hexes')]+([check('results.4.maps.main.hexes',same_as='results.0.maps.main.hexes')] if code<0 else [check('results.4.maps.main.size',[2,2])]),
             map={'size':[2,2]},files=files,mode='ordinary')
    terrain={'grass':'CLEAR','fire':'FIRE','smoke':'SMOKE'};values={'grass':' ','fire':'&','smoke':':'}
    for i,r in enumerate(examples('files',2)):
        objs=[]
        if r['deco']!='none':objs=[{'kind':'FIRE' if r['terrain']=='fire' else 'SMOKE','datac':96 if r['terrain']=='fire' else 126}]
        case('files',f'example-02-{i}',[M('save','record')],[check('state.files.record.text',f"1 1\n{r['pair']}\n"+('8: 100 20\n' if r['eternal']=='1' else '')),check('state.maps.main.hexes.0.terrain',values[r['live']])],
             map={'size':[1,1],'default':[terrain[r['terrain']],3],'flags':8 if r['eternal']=='1' else 0,'map_objects':objs})
    for i,r in enumerate(examples('files',3)):
        flags=int(r['flags']);wire='1 1\n.0\n'+(f'{flags&~1}: 75 -20\n' if flags&~1 else '')
        def fresh(data,path,r=r):
            return ({'map':{'size':[2,2]},'units':[],'actions':[M('load','record')],'config':{'periodic_updates':False}},
                    [check('state.maps.main.grav',int(r['gravity'])),check('state.maps.main.temp',int(r['temperature'])),check('state.maps.main.size',[1,1])])
        case('files',f'example-03-{i}',[M('save','record')],[check('state.files.record.text',wire)],map={'size':[1,1],'flags':flags,'grav':75,'temp':-20},followup=fresh)
    for i,r in enumerate(examples('files',4)):
        setup=[D('bits','create')] if r['bits']=='present-empty' else []
        w,h=int(r['width']),int(r['height']);ok=r['outcome']=='success'
        checks=[check('state.maps.main.size',[w,h] if ok else [2,2])]
        if ok:
            if w>1:checks += [hexcheck('state.maps.main.hexes',1,1,'%',3),hexcheck('state.maps.main.hexes',w-1,h-1,' ',0)]
            checks.append(check(f'results.{len(setup)}.error',None))
        else:checks.append(check(f'results.{len(setup)}.error',contains='Invalid map' if r['bits']=='present-empty' else 'out of range'))
        case('files',f'example-04-{i}',setup+[attempt(M('resize',w,h))],checks,map={'size':[2,2],'hexes':[{'at':[1,1],'terrain':'ROUGH','elevation':3}]})
    # scanf/fgets boundaries independently specified as bytes, with direct and checked side effects.
    texts=[('one','1 1\n.0\n',1),('zero-h','1 0\n',-2),('negative','-1 1\n',-2),('over-h','1 1001\n',-2),
           ('nonnumeric','bad\n',-2),('one-int','1\n',-2),('short','2 1\n.0\n',-3),('newline-count','1 1\n.\n',1),
           ('whitespace-header',' 1\t1\n \n\t.0\n',1),('extra-row','1 1\n.0\n~2\n',1),('extra-cell','1 1\n.0~2\n',1),
           ('width1000','1000 1\n'+'.0'*1000+'\n',1),('height1000','1 1000\n'+'.0\n'*1000,1)]
    for name,text,expected in texts:
        case('files','check-'+name,[M('check','record')],[check('results.0',expected)],files={'record':{'text':text}})
    for name,text in [('partial','2 2\n~2%3\n'),('invalid-dim','0 0\n')]:
        case('files','direct-'+name,[M('addsmoke',1,1,30),I(),F('load_direct'),I()],
             [check('results.2',-2),check('state.maps.main.partial_grid',True),check('state.maps.main.size',[9,9]),check('state.maps.main.objects',[]),check('state.events',[])],files={'record':{'text':text}})
    text='7 1\n>0:1.2\'3$4+5&6\n128:100-20\n'
    case('files','remap-and-compact-trailer',[F('load_direct')],[check('results.0',0),check('state.maps.main.flags',128),check('state.maps.main.grav',100),check('state.maps.main.temp',-20),check('state.maps.main.hexes',[' ',' ',' ','`',' ',' ','&'],project='terrain')],files={'record':{'text':text}})
    for player in (1,2):
        case('files',f'second-open-race-{player}',[M('addsmoke',1,1,30),M('load','record',player=player,fail_second_open=True)],
             [check('results.1',-1),check('state.maps.main.size',[9,9]),check('state.maps.main.objects',int(player==1),length=True),check('state.maps.main.roster_ids',[40] if player==1 else [])],
             units=[{'name':'u','id':40}],files={'record':{'text':'1 1\n.0\n'}})
    case('files','load-preserves-cache',[M('load','record')],[check('state.units.u.cached_terrain',' '),check('state.units.u.cached_elevation',0),check('state.maps.main.hexes.0.terrain','~')],
         map={'size':[1,1]},units=[{'name':'u','at':[0,0,0]}],files={'record':{'text':'1 1\n~2\n'}})
    for flags,trailer in ((16,''),(16,'0: 75 -20\n'),(128,'128: 100 20\n')):
        case('files',f'inherited-flags-{flags}-{bool(trailer)}',[F('load_direct')],[check('state.maps.main.flags',int(trailer.split(':')[0]) if trailer else flags|8)],map={'size':[1,1],'flags':flags},files={'record':{'text':'1 1\n&0\n'+trailer}})
    for i,r in enumerate(examples('management',1)):
        args=r['arguments'].split(',');ok=r['outcome']=='success'
        case('management',f'example-01-{i}',[attempt(M('addhex',*args))],[check('state.units.u.cached_elevation',0),check('state.units.v.cached_terrain',' '),hexcheck('state.maps.main.hexes',1,1,'%' if r['terrain']=='rough' else ' ',int(r['elevation']))]+([check('results.0.error',None)] if ok else [check('results.0.error',contains='out of range' if r['outcome']=='out-of-range' else 'number')]),
             map={'size':[3,3]},units=[{'name':'u','at':[1,1,0]},{'name':'v','at':[2,2,0]}])
    for i,r in enumerate(examples('management',2)):
        tac='' if r['tacsize']=='absent' else r['tacsize'].replace(',',' ')
        case('management',f'example-02-{i}',[M('view',-3,99,tacsize=tac)],
             [check('results.0',{'service':'MakeMapText','applied':False,'x':0,'y':29,'width':int(r['width']),'height':int(r['height']),'mode':3}),check('state.maps.main.messages',0 if r['warning']=='none' else 1,length=True)],map={'size':[30,30]},mode='blocked')
    for i,r in enumerate(examples('management',3)):
        text=r['text'].replace('SPACES','   ')
        actions=[D('initialize',41,True),attempt(M('mapemit',text))]
        checks=[check('results.0.id',41),check('results.0.size',[21,11]),check('results.0.regen_factor',1)]
        if r['result']=='empty-error':checks.append(check('results.1.error',contains='What do you want'))
        else:checks.append(check('state.units.u.messages',contains=r['result'].replace('SPACES','   ')))
        case('management',f'example-03-{i}',actions,checks,units=[{'name':'u'}])
    for allocate in (False,True):
        case('management',f'source-initialize-{allocate}',[D('initialize',41,allocate)],
             [check('results.0.id',41),check('results.0.movemod',0),check('results.0.grav',0),check('results.0.temp',0),check('results.0.name','Default Map' if allocate else '')])
    for cmd in ('clear','free'):
        case('management','live-'+cmd,[M('addsmoke',1,1,30),M(cmd),I(),A(30)],
             [check('results.2.maps.main.roster_ids',[]),check('results.2.units.u.mapindex',-1),check('results.2.units.u.at',[0,0,0]),check('results.2.maps.main.grid_allocated',cmd=='clear'),check('results.2.maps.main.objects',int(cmd=='clear'),length=True),check('state.events',[])],units=[{'name':'u','at':[2,2,0]}])
    # Integer bounds and atomic rejection: map_attempt permits post-error inspection.
    for i,r in enumerate(examples('conditions',1)):
        case('conditions',f'example-01-{i}',[M('conditions',*r['arguments'].split(','))],
             [check('state.maps.main.flags',int(r['after'])),check('state.maps.main.grav',int(r['gravity'])),check('state.maps.main.temp',int(r['temperature']))],map={'size':[9,9],'flags':int(r['before'])},units=[{'name':'u'}])
    for i,r in enumerate(examples('conditions',2)):
        good=r['result']=='success';checks=[check('results.0.error',None)] if good else [check('state.maps.main.flags',16),check('state.maps.main.grav',100),check('state.maps.main.temp',20),check('results.0.error',contains='required' if r['result']=='arity-error' else 'Invalid')]
        case('conditions',f'example-02-{i}',[attempt(M('conditions',*r['arguments'].split(',')))],checks,map={'size':[9,9],'flags':16})
    for i,r in enumerate(examples('conditions',3)):
        special=int(r['special']);vac=int(r['vacuum']);flags=2*special+4*vac
        # Source special without vacuum still Rolls; gravity supplies the live special flag.
        case('conditions',f'example-03-{i}',[C('damage-section','LA',1,0,0)],
             [check('draws',int(r['consumption']=='used'),where={'name':'breach_rolls'},length=True),check('state.units.u.sections.0.config',4 if r['breached']=='true' else 0,mask=4)],
             map={'size':[9,9],'flags':flags,'grav':99 if special else 100},units=[{'name':'u','sections':[{'index':0,'armor':100,'internal':10}]}],random={'streams':{'breach_rolls':[int(r['roll'])],'damage_entry':[2]}})
    for i,r in enumerate(examples('visibility',1)):
        case('visibility',f'example-01-{i}',[A(25)],
             [check('state.maps.main.'+k,int(r[v])) for k,v in [('mapvis','vis'),('maxvis','maxvis'),('light','light'),('winddir','wind'),('windspeed','speed'),('cloudbase','cloud')]],
             map={'size':[9,9],'mapvis':10,'light':1,'visibility':r['config'].replace(',',' ')},units=[{'name':'u'}],config={'periodic_updates':True},random={'seed':5489})
    for i,r in enumerate(examples('visibility',2)):
        def messages(data,path,r=r):
            assert ('abcdef' in data['state']['units']['u']['messages'])==(r['message']=='abcdef')
        case('visibility',f'example-02-{i}',[A(25)],[check('state.maps.main.cloudbase',int(r['cloud']))],checker=messages,
             map={'size':[9,9],'mapvis':10,'light':1,'visibility':r['config'].replace(',',' ')},units=[{'name':'u'}],config={'periodic_updates':True},random={'seed':5489})
