"""QA-owned ordinary workflows. No acceptance or engine imports."""
from qa.pilots.common import *
from qa.pilots.battle import ba,cfg,probe

def T(kind,reference='',unit='u',**kw):return dict(op='template',kind=kind,reference=reference,unit=unit,**kw)
def attach(unit='u',player=101):return dict(op='personnel',kind='attach',unit=unit,player=player)
def shoot(index=0,unit='u',target='VV'):return command('fire',unit=unit,args=f'{index} {target}')
def skill_get(name,flag=0,player=101):return ch('get',name=name,flag=flag,target=f'#{player}')
def unit_state(o,name='u'):return o['state']['units'][name]
def ammo(u):return sum(s['data'] for sec in u['sections'] for s in sec['slots'] if 193<=s['type']<385)
def game(actions,*,units=None,characters=None,catalog=False,streams=None,periodic=True):
    defaults={'sensor.perception_xp':[1]*1000,'sensor.detect':[1]*1000,'visibility_change':[0]*1000,
      'failure_generic_chance':[5000]*1000,'failure_weapon_chance':[1]*1000,'attack_rolls':[12]*100,
      'hit_location_rolls':[7]*100,'damage_entry':[7]*200,'pilot_rolls':[12]*100,'character_d6':[6]*100,
      'xp_old_gate':[1]*100,'critical_rolls':[2]*100,'critical_slot':[0]*100,'fall_directions':[1]*100,
      'breach_rolls':[12]*100,'fuel_check':[1]*1000,'missile_pre_roll':[6]*100,'missile_cluster':[12]*100,
      'personal_variation':[100]*100,'personal_weak_point':[2]*100,'personal_half':[1]*100,
      'personal_block':[1]*100,'personal_to_normal':[1]*100,'personal_conversion':[100]*200,
      'swarm_location':[7]*100,'suit_choice':[0]*100,'suit_ejection':[100]*100,'physical_location':[1]*100,'sensor.flash':[100]*100,
      **(streams or {})}
    d=doc(actions,characters=characters,units=units or [unit(character=101),unit('v',20,at=[3,1,0],facing=180)],streams=defaults)
    d['config']['periodic_updates']=periodic;d['construction']={'catalog':catalog};d['pilots']={'radio_draws':[1234567]*10}
    return d

def record(a,name,d,**kw):return a.cli(name,d,mode='ordinary',**kw)
def commands_ok(a,d,o,except_names=()):
    for action,result in zip(d['actions'],o['results']):
        if action.get('op')=='command' and action.get('name') not in except_names:
            a.eq('command '+action['name'],result.get('accepted',result.get('ok')),True)

def run_workflows():
    a=Audit('workflows')
    for case,_,r,line in rows('workflows'):
        name=r['procedure'];identity=dict(outline=1,line=line,values=r)
        if name=='character-roundtrip':
            chars=[character(values={},wiz_r=True),character(102,wizard=False,values={})]
            actions=[]
            for field,amount in [('Build',5),('Reflexes',4),('Intuition',3),('Learn',2),('Charisma',1),('Running',3),('Blade',2),('Toughness',1),('Contact',7),('Lives',4)]:actions.append(ch('set',name=field,amount=amount))
            actions.extend([ch('set',name='Running',flag=3,amount=101),ch('status'),ch('status',target='#102'),ch('save')])
            out=record(a,name,doc(actions,characters=chars),identity=identity);categories=out['state']['characters']['101']['categories']
            a.eq('attribute source text',categories['attrs'],'5,4,3,2,1');a.eq('advantage order',categories['advs'],'Lives:4/Conta:7/Tough:1/');a.eq('XP serialization',categories['skills'],'Blade:2/Runni:3,33554533,0/')
            root=OUT/'workflows'/name/'storage'
            out=record(a,name+'-reload',doc([skill_get('rUnNi'),skill_get('GunBat'),ch('status'),ch('status',target='#102'),ch('clear',target='#101'),ch('status')],characters=[]),storage=root,fresh=False)
            a.eq('alias effective skill',out['results'][0],5);a.eq('second character unchanged',out['results'][3]['attributes'],dict.fromkeys(ATTRS,1));a.eq('clear lazy defaults',out['results'][5]['attributes'],dict.fromkeys(ATTRS,1))
        elif name=='skills-and-rolls':
            actions=[T('load','WVR-6R'),attach(),command('startup'),advance(40),inspect(),ch('target',name='Gunnery-Battlemech'),command('sight',args='0 VV'),shoot(),inspect(),ch('set',name='Reflexes',amount=6),ch('target',name='Gunnery-Battlemech'),advance(40),command('sight',args='0 VV'),shoot(),inspect()]
            # Stand through the actual command on a separately fallen ordinary unit.
            u=unit(character=101);v=unit('v',20,at=[3,1,0],facing=180)
            d=game(actions,units=[u,v],catalog=True);out=record(a,name,d,identity=identity);commands_ok(a,d,out)
            a.eq('changed BTH',[out['results'][5],out['results'][10]],[4,3]);a.eq('both real shots',[out['results'][i]['attack']['hit'] for i in (7,13)],[True,True]);a.eq('next actual sight BTH changes',out['results'][6]['attack']['bth']-out['results'][12]['attack']['bth'],1)
            a.eq('two rounds spent',ammo(out['results'][4]['units']['u'])-ammo(unit_state(out)),2)
            d=game([command('stand'),advance(20),inspect()],units=[unit(character=101,fallen=True)],characters=[character()]);stand=record(a,name+'-stand',d);commands_ok(a,d,stand);a.eq('stood',unit_state(stand)['fallen'],False);a.true('real PSR histogram',stand['state']['random']['total_rolls']>0)
        elif name=='xp-progression':
            u=unit(character=101,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)]);v=unit('v',20,at=[3,1,0],facing=180)
            actions=[ch('set',name='Gunnery-Battlemech',flag=3,amount=3000),ch('target',name='Gunnery-Battlemech'),shoot(),skill_get('Gunnery-Battlemech',2),ch('target',name='Gunnery-Battlemech'),ch('save'),inspect()]
            d=game(actions,units=[u,v],periodic=False);d['pilots']['xp']={'oldxpsystem':False,'use_pilot_bv':False};out=record(a,name,d,identity=identity);commands_ok(a,d,out)
            a.eq('before BTH',out['results'][1],4);a.true('real hit advances XP',out['results'][3]>3000);a.eq('next BTH after crossing',out['results'][4],3);a.eq('one actual gain',len(unit_state(out)['xp_requests']),1)
            root=OUT/'workflows'/name/'storage';again=record(a,name+'-reload',doc([skill_get('Gunnery-Battlemech',2),ch('target',name='Gunnery-Battlemech')],characters=[]),storage=root,fresh=False);a.eq('durable XP fresh process',again['results'][0],out['results'][3]);a.eq('durable next target',again['results'][1],3)
            d=game([dict(op='clock',name='skip_seconds',seconds=101),command('speed',args='walk'),advance(300),inspect()],units=[unit(character=101,max_speed=64.5,at=[3,13,0])]);o=record(a,name+'-motion',d);commands_ok(a,d,o);a.true('crossed hex',unit_state(o)['at'][:2]!=[3,3]);a.true('ordinary piloting XP',any(q['producer']=='piloting' and q['applied'] for q in unit_state(o)['xp_requests']))
        elif name=='conscious-injuries':
            shooter=unit(character=101,weapons=[dict(name='IS.MediumLaser',section=0,critical=4),dict(name='IS.MediumLaser',section=1,critical=4)])
            victim=unit('v',20,at=[3,1,0],facing=180,character=102)
            chars=[character(values={**dict.fromkeys(ATTRS,5),'Gunnery-Battlemech':8}),character(102,wizard=False)]
            for failure in (False,True):
                actions=[shoot(0),inspect(),advance(10),shoot(1),inspect(),advance(20),inspect()]
                if failure:actions.extend([advance(30),inspect()])
                d=game(actions,units=[shooter,victim],characters=chars,periodic=False,streams={'hit_location_rolls':[12,12],'character_d6':[1,1]+([1,1,6,6] if failure else [6,6])})
                o=record(a,name+('-rearm' if failure else ''),d,identity=identity if not failure else None);commands_ok(a,d,o)
                a.eq('real head shots',[o['results'][i]['attack']['location'] for i in (0,3)],[7,7]);a.eq('initial injury recovery',[e['deadline'] for e in events(o['results'][1],'RECOVERY')],[30]);a.eq('repeat injury keeps recovery',[e['deadline'] for e in events(o['results'][4],'RECOVERY')],[30]);a.eq('hits accumulate',o['results'][4]['units']['v']['pilot_hits'],2)
                a.eq('rearm or recovered',[e['deadline'] for e in events(o['results'][6],'RECOVERY')],[60] if failure else []);a.eq('eventually recovered',events(o['state'],'RECOVERY'),[]);a.eq('durable bruise',health(o,102),[20,0])
        elif name=='personal-equipment':
            c=character(values={**dict.fromkeys(ATTRS,5),'Running':3,'Reflexes':4,'Small_Arms':8,'Bruise':10,'Lethal':10},pcequip='1234 PC.SMG PC.LaserRifle 3 4')
            u=unit(character=101,started=False);v=unit('v',20,cls='MW',at=[3,2,0],facing=180,character=102)
            c2=character(102,wizard=False,values={**dict.fromkeys(ATTRS,5),'Build':20})
            actions=[T('load','MechWarrior'),attach(),dict(op='personnel',kind='initialize',unit='u'),inspect(),dict(op='register',unit='u'),advance(2),shoot(0),inspect()]
            d=game(actions,units=[u,v],characters=[c,c2],catalog=True,periodic=True);o=record(a,name,d,identity=identity);a.true('ordinary personal shot',o['results'][6].get('accepted'));s=o['results'][3]['units']['u'];a.eq('all8 body values',[x['internal'] for x in s['sections']],[25,25,29,29,41,29,29,13]);a.eq('equipment ammo',[s['sections'][1]['slots'][1]['data'],s['sections'][0]['slots'][1]['data']],[3,4]);a.eq('actual ammo consumed',ammo(s)-ammo(unit_state(o)),1)
        elif name=='manual-ejection':
            c=character(wizard=False,values={**dict.fromkeys(ATTRS,5),'Running':4,'Small_Arms':8},pcequip='0000 PC.SMG -')
            actions=[T('load','WVR-6R'),attach(),dict(op='personnel',kind='configure',unit='u',values={'official_pilot':101}),command('eject'),inspect(),advance(2),shoot(0,unit='mw1001'),command('speed',unit='mw1001',args='walk'),advance(90),inspect()]
            d=game(actions,characters=[c],catalog=True);o=record(a,name,d,identity=identity);commands_ok(a,d,o);a.true('original destroyed',unit_state(o)['destroyed']);a.true('cockpit used',unit_state(o)['sections'][7]['slots'][2]['firemode']&1);mw=unit_state(o,'mw1001');a.eq('actor now controls MW',o['state']['characters']['101']['location'],1001);a.true('MW crossed hex',mw['at'][:2]!=[3,3]);a.true('MW fired',o['results'][6]['attack']['hit'])
        elif name=='pilot-exit-entry':
            c=character(wizard=False);p=character(102,wizard=False,location=10)
            u=unit(character=101,speed=25,personnel={'official_pilot':101});v=unit('v',20,team=1)
            actions=[command('disembark',actor=102),inspect(),advance(2),command('embark',unit='mw1001',args='VV',actor=102),advance(10),inspect()]
            d=game(actions,units=[u,v],characters=[c,p],catalog=True,periodic=True);o=record(a,name,d,identity=identity);commands_ok(a,d,o);a.eq('passenger boarded ally',o['state']['characters']['102']['location'],20);a.eq('pilot stays',o['state']['characters']['101']['location'],10);a.eq('shell disposed',unit_state(o,'mw1001')['personnel']['hardcode'],False)
            u=unit(character=101,started=False,at=[3,3,2],speed=21.5)
            d=game([command('disembark'),inspect(),advance(3),inspect()],units=[u],characters=[c],catalog=True,periodic=False);o=record(a,name+'-fall',d);commands_ok(a,d,o);a.eq('actual scheduled fall',[(e['data2'],e['deadline']) for e in events(o['results'][1],'FALL')],[(-5,3)]);a.eq('fall landed',unit_state(o,'mw1001')['at'][2],0)
        elif name=='pickup-and-discard':
            chars=[character(wizard=False),character(102,wizard=False,location=20,lock='secret'),character(103,wizard=True,location=20)]
            u=unit(character=101);v=unit('v',20,cls='MW');actions=[command('pickup',args='VV'),inspect(),advance(9),inspect(),advance(1),inspect()]
            d=game(actions,units=[u,v],characters=chars,periodic=False);d['pilots']['pickup_action']=0;o=record(a,name,d,identity=identity);commands_ok(a,d,o);a.eq('ordered captured contents',o['state']['personnel']['contents']['10'],[101,102,103]);a.eq('nonwizard enslaved',o['state']['characters']['102']['slave'],True);a.eq('lock cleared',o['state']['characters']['102']['lock'],'');a.eq('wizard not enslaved',o['state']['characters']['103'].get('slave',False),False);a.eq('shell present9',o['results'][3]['units']['v']['personnel']['hardcode'],True);a.eq('discard10',unit_state(o,'v')['personnel']['hardcode'],False)
        elif name=='carrier-roundtrip':
            u=unit(character=101,tonnage=5,measured_mass=5120,max_speed=64.5,carrying=30,personnel={'official_pilot':101});v=unit('v',20,team=1,specials2=0x80000,max_speed=64.5,construction={'car_max_ton':5,'cargo_space':800});tow=unit('tow',30,team=1,contact_id='TO',tonnage=3,measured_mass=3072)
            acts=[command('embark',args='VV'),inspect(),command('udisembark'),inspect(),command('speed',args='walk'),advance(30),inspect()]
            d=game(acts,units=[u,v,tow]);o=record(a,name,d,identity=identity);commands_ok(a,d,o);board=o['results'][1];a.eq('towee ordered before own',board['personnel']['contents']['20'],[30,10]);a.eq('all capacity used',board['units']['v']['construction']['cargo_space'],0);a.eq('own exit capacity credit',unit_state(o,'v')['construction']['cargo_space'],500);a.true('startup on exit',o['results'][3]['units']['u']['started']);a.true('ordinary movement after exit',unit_state(o)['at'][:2]!=[3,3])
        elif name=='swarm-and-host':
            c=character(values={**dict.fromkeys(ATTRS,5),'Piloting-BSuit':8,'Gunnery-BSuit':8});u=ba(8,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)]);v=unit('v',20)
            actions=[command('swarm',args='VV'),inspect(),command('speed',unit='v',args='walk'),advance(20),inspect(),shoot(0),command('swarm',args='-'),inspect()]
            d=game(actions,characters=[c],units=[u,v]);o=record(a,name,d,identity=identity);commands_ok(a,d,o);m=o['results'][4];a.eq('rider XY mirrors host',m['units']['u']['at'][:2],m['units']['v']['at'][:2]);a.eq('rider Z offset',m['units']['u']['at'][2],m['units']['v']['at'][2]+1);a.true('host moved',m['units']['v']['at'][:2]!=[3,3]);a.true('host-only firing',o['results'][5]['attack']['hit']);a.eq('intentional detach',unit_state(o)['relationships']['swarm_target'],None)
        elif name=='leg-attacks':
            c=character(values={**dict.fromkeys(ATTRS,5),'Piloting-BSuit':8});u=ba(8);v=unit('v',20,movement='QUAD',weapons=[dict(name='IS.MediumLaser',section=1,critical=4)]);v['sections'][6]['internal']=0
            actions=[command('attackleg',args='VV'),inspect()]
            d=game(actions,characters=[c],units=[u,v],periodic=False,streams={'leg_location':[0,2],'leg_critical':[12]});o=record(a,name,d,identity=identity);commands_ok(a,d,o);a.eq('reroll absent leg actual selection',o['results'][0]['location'],1);a.eq('actual leg destroyed',unit_state(o,'v')['sections'][1]['internal'],0);a.eq('weapon lost with leg',unit_state(o,'v')['weapons'][0]['status'],'DESTROYED');a.eq('critical12 fallthrough report',o['results'][0]['effect'],'destroy-leg-then-critical3')
        elif name=='hiding-and-jettison':
            c=character();u=ba(8);u['infantry_specials']|=0x200;u['sections'][7]['slots']=[dict(index=4,weapon='PC.SMG',firemode=0x20000)]
            # Enemy is outside LOS during concealment, then ordinary LOS is queried
            # from its actual position after completed hiding.
            v=unit('v',20,started=False)
            actions=[command('hide'),advance(60),inspect(),advance(1),inspect(),command('jettison'),command('fire',args='0 VV'),command('jettison')]
            d=game(actions,characters=[c],units=[u,v],periodic=False);d['map']['default']=['ROUGH',0];o=record(a,name,d,identity=identity);commands_ok(a,d,o,except_names=('fire',));a.eq('hidden only61',bool(o['results'][2]['units']['u']['crit_status']&8),False);a.true('hidden61',o['results'][4]['units']['u']['crit_status']&8);a.eq('section7 destroyed pack',unit_state(o)['sections'][7]['slots'][4]['firemode'],0x60001);a.eq('real fire unavailable',o['results'][6]['accepted'],False)
        elif name=='automatic-escape':
            c=character(wizard=False,pcequip='0000 PC.SMG -');attacker=unit('v',20,at=[3,1,0],facing=180,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
            for armor in (False,True):
                u=unit(character=101,engine_heat=10,tonnage=50)
                if armor:
                    u['class']='BA'
                    for i,s in enumerate(u['sections']):s.update(armor=0,internal=1 if i==7 else 0,internal_orig=1 if i==7 else 0)
                else:u['sections'][2].update(armor=0,internal=1,slots=[dict(index=0,special='ENGINE')])
                acts=[shoot(0,unit='v',target='UU'),inspect(),advance(90),inspect(),command('speed',unit='mw1001',args='walk'),advance(90),inspect()]
                # BA live-list hit lookup selects the only living member. The
                # fusion fixture destroys a real side-torso engine slot by fire.
                streams={'hit_location_rolls':[8]+[7]*100 if not armor else [7]*100,'suit_choice':[0]*20,'suit_ejection':[25],'stackpole_rolls':[12]}
                d=game(acts,characters=[c],units=[u,attacker],catalog=True,streams=streams);o=record(a,name+('-suit' if armor else ''),d,identity=identity if not armor else None)
                shot=o['results'][0];a.true('ordinary weapon hit',shot['attack']['hit']);a.true('source destroyed',unit_state(o)['destroyed']);a.true('MW actually created','mw1001' in o['state']['units'])
                if 'mw1001' in o['state']['units']:
                    a.eq('initial escape altitude',o['results'][1]['units']['mw1001']['at'][2],0 if armor else 150);a.eq('escaped actor moved',o['state']['characters']['101']['location'],1001);a.eq('landed through clock',unit_state(o,'mw1001')['at'][2],0);a.eq('MW movement accepted',o['results'][4].get('accepted'),True)
        else:
            acts=[T('load','WVR-6R'),attach(),command('startup'),advance(40),inspect(),command('speed',args='10.75'),advance(40),command('speed',args='stop'),advance(10),command('jump',args='180 5'),advance(80),inspect(),shoot(0),inspect(),command('repair',args='4 0'),T('save','QA-Wolverine',clock='QA'),T('load','MechWarrior',unit='v'),inspect()]
            d=game(acts,catalog=True);o=record(a,name,d,identity=identity);commands_ok(a,d,o);a.eq('five MP retained',unit_state(o)['jump_mp'],5);a.eq('jump ended',bool(unit_state(o)['status']&0x40),False);a.true('actual catalog shot',o['results'][12]['attack']['hit']);a.eq('real MW loaded',o['results'][16]['ok'],True)
            root=OUT/'workflows'/name/'storage';o=record(a,name+'-reload',game([T('load','QA-Wolverine'),inspect()],catalog=True,periodic=False,characters=[]),storage=root,fresh=False);a.eq('fresh saved catalog load',o['results'][0]['ok'],True);a.eq('full design ammo',unit_state(o)['sections'][1]['slots'][8]['data'],20)
        a.save()
    return a.save()
