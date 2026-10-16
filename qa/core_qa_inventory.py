"""Source critical inventories, ammunition, repair and skill checks via CLI."""
from core_simulation_qa import D,C,I,case,check as q,examples


def build():
    for n,r in enumerate(examples('weapons',1)):
        name='IS.SmallLaser' if r['category']=='beam' else 'IS.LRM-5'
        checks=[q('results.0.0',int(r['code']))] if r['code']!='catalog' else [q('results.0.0',same_as='results.1')]
        case('weapons',f'example-01-{n}',[D('FindWeaponNumberOnMech',0,bool(int(r['sight']))),D('FindWeaponIndex',0)],checks,
             units=[dict(name='u',profile='sparse',weapons=[dict(name=name,section=0)],sections=[dict(index=0,recycle=int(r['physical']),slots=[dict(index=0,data=int(r['data']),firemode=int(r['destroyed']))])])])
    for n,r in enumerate(examples('weapons',2)):
        slots=[dict(index=i,weapon='IS.PPC') for i in range(int(r['actual']))]
        checks=[q('results.0',None)] if r['count']=='-1' else [q('results.0',int(r['count']),length=True)]
        case('weapons',f'example-02-{n}',[D('FindWeapons_Advanced',0)],checks,units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.PPC',section=1,metadata={'crits':int(r['required'])})],sections=[dict(index=0,slots=slots)])])
    for n,r in enumerate(examples('weapons',3)):
        slots=[dict(index=i,firemode=1 if i<int(r['destroyed']) else 2) for i in range(int(r['destroyed'])+int(r['disabled']))]
        case('weapons',f'example-03-{n}',[D('WeaponIsNonfunctional',0,0)],[q('results.0',int(r['code']))],
             units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.SmallLaser',section=0,metadata={'crits':int(r['size'])})],sections=[dict(index=0,slots=slots)])])
    for n,r in enumerate(examples('weapons',4)):
        case('weapons',f'example-04-{n}',[D('FindWeaponFromIndex',0)],[q('results.0',[bool(int(r['found'])),0,3])],
             units=[dict(name='u',profile='sparse',weapons=[dict(name='IS.SmallLaser',section=0,critical=3)],sections=[dict(index=0,slots=[dict(index=0,type=0,firemode=int(r['state']=='empty-destroyed'))])])])
    for n,r in enumerate(examples('ammunition',1)):
        names=r['modes'].split('+');fire=128 if 'HALFTON' in names else 0
        ammo=sum({'AP':0x2000,'CASELESS':0x40000,'MML_LRM':0x400000}.get(x,0) for x in names)
        case('ammunition',f'example-01-{n}',[D('ammo_capacity',int(r['base']),fire,ammo)],[q('results.0',int(r['capacity']))])
    for n,r in enumerate(examples('ammunition',2)):
        case('ammunition',f'example-02-{n}',[D('FindAmmunition',True)],[q('results.0.0.current',int(r['current'])),q('results.0.0.maximum',20)],
             units=[dict(name='u',ammo=[dict(weapon='IS.AC/10',rounds=4,section=0,critical=0),dict(weapon='IS.AC/10',rounds=6,section=0,critical=1)],sections=[dict(index=0,slots=[dict(index=1,firemode=4 if int(r['broken']) else 0)])])])
    for n,r in enumerate(examples('ammunition',3)):
        case('ammunition',f'example-03-{n}',[D('FindAmmunition',bool(int(r['all'])))],[q('results.0',int(r['count']),length=True)],units=[dict(name='u',ammo=[dict(weapon='IS.AC/10',rounds=0)])])
    for n,r in enumerate(examples('repair',1)):
        case('repair',f'example-01-{n}',[C('reattach' if r['operation']=='reattach' else 'replacesuit',0)],[q('state.units.u.sections.0.internal',10),q('state.units.u.sections.0.config',8*int(r['flooded']))],
             units=[dict(name='u',sections=[dict(index=0,config=10,internal=0,internal_orig=10,armor=0)])])
    for n,r in enumerate(examples('repair',2)):
        case('repair',f'example-02-{n}',[D('GetPartMod',p) for p in (402,401,0)],[q('results',list(map(int,r['mods'].split(','))))],units=[dict(name='u',tonnage=int(r['tons']),core={'engine_rating':int(r['rating'])})])
    for n,r in enumerate(examples('repair',3)):
        sections=[dict(index=i,slots=[dict(index=j,special='JUMP_JET') for j in range(min(12,int(r['slots'])-i*12))]) for i in range((int(r['slots'])+11)//12)]
        case('repair',f'example-03-{n}',[D('do_sub_magic')],[q('state.units.u.jump_speed',int(r['mp'])*10.75)],units=[dict(name='u',max_speed=64.5,specials2=128*int(r['improved']),sections=sections)])
    for n,r in enumerate(examples('repair',4)):
        flag={'none':0,'BROKEN':4,'DAMAGED':8}[r['flag']]
        case('repair',f'example-04-{n}',[C('reseal',0)],[q('state.units.u.sections.0.config',0),q('state.units.u.sections.0.slots.0.firemode',flag)],units=[dict(name='u',weapons=[dict(name='IS.SmallLaser',section=0)],sections=[dict(index=0,config=8,slots=[dict(index=0,firemode=flag|2)])])])
    for n,r in enumerate(examples('skills',1)):
        case('skills',f'example-01-{n}',[D('FindPilotPiloting'),D('FindPilotGunnery',0),D('FindPilotSpotting'),D('FindPilotArtyGun')],
             [q('results',list(map(int,r['skills'].split(','))))],units=[dict(name='u',pilot=False,core={'quiet':bool(int(r['quiet'])),'mechskills':'' if r['text']=='none' else r['text'].replace(',',' ')})])
    for n,r in enumerate(examples('skills',2)):
        # Source metadata can represent the exact PC name exceptions without inventing a weapon outcome.
        source_name={'laser':'IS.SmallLaser','missile':'IS.LRM-5'}.get(r['weapon'],r['weapon'])
        metadata={'source_name':source_name,'weapon_type':1 if r['weapon']=='missile' else 0}
        case('skills',f'example-02-{n}',[D('FindGunnerySkillName',0),D('FindPilotingSkillName')],[q('results',r['names'].split('/'))],
             units=[dict(name='u',**{'class':r['kind']},movement=r['move'],weapons=[dict(name='IS.SmallLaser',metadata=metadata)])],
             map=dict(default=[r['terrain'],0]),config=dict(extended_gunnery=bool(int(r['extended'])),extended_piloting=bool(int(r['extended']))))
    for n,r in enumerate(examples('skills',3)):
        case('skills',f'example-03-{n}',[D('MadePilotSkillRoll_NoXP',0,bool(int(r['succeed'])))],[q('results.0.success',bool(int(r['success']))),q('state.random.total_rolls',int(r['rolls'])),q('state.units.u.xp_requests',[])],
             units=[dict(name='u',fallen=bool(int(r['fallen'])),started=not int(r['stopped']))],random={'streams':{'pilot_rolls':[12]}})
    for text,values in [('-2 +3 0 -4 trailing',[-2,3,0,-4]),('1 2oops 3 4',[1,2,8,8]),('junk 1 2 3',[6,6,8,8]),('1',[1,6,8,8]),('1 2 3 4 5',[1,2,3,4])]:
        case('skills','signed-columns-'+text.encode().hex(),[D('FindPilotPiloting'),D('FindPilotGunnery',0),D('FindPilotSpotting'),D('FindPilotArtyGun')],[q('results',values)],units=[dict(name='u',pilot=False,core={'quiet':True,'mechskills':text})])
    case('skills','high-bth-still-rolls',[D('MadePilotSkillRoll_NoXP',100)],[q('results.0.success',False),q('state.random.total_rolls',1)],random={'streams':{'pilot_rolls':[12]}})
    for bth in (2,3,7,9):
        case('skills',f'xp-{bth}',[D('MadePilotSkillRoll_Advanced',bth-5)], [q('results.0.success',True),q('state.units.u.xp_requests',int(bth>2),length=True)],random={'streams':{'pilot_rolls':[12]}},mode='blocked' if bth>2 else 'diagnostic')
