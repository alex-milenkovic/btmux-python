from . import step,base,eq,draws,numbers,values
from entities.mech import UnitType as U,Location as L,CritStatus
from entities.weapon import get_weapon,WeaponFlags as W
from systems import personal_damage as p
LOC={'LA':0,'RA':1,'LT':2,'RT':3,'CT':4,'LL':5,'RL':6,'HEAD':7}

@step(r'source personal armor metadata with strict finite Number streams and C integer arithmetic')
def fresh(w):base(w)

@step(r'target (\w+) weapon (\w+) and damage (-?\d+)')
def conversion(w,target,weapon,damage):
    w['unit'].unit_type=U[target];w['weapon']=get_weapon('PC.SMG') if weapon=='PC' else get_weapon('IS.MediumLaser') if weapon=='normal' else None;w['amount']=int(damage)

@step(r'conversion (to-normal|to-personal) draws (.+)')
def convert(w,kind,dice):w['result']=draws(w,numbers(dice),p.personal_to_damage if kind=='to-normal' else p.damage_to_personal,w['unit'],w['weapon'],w['amount'])

@step(r'damage becomes (-?\d+)')
def damage(w,n):eq(w['result'],int(n))

@step(r'personal hit location (\w+)')
def location(w,name):w['loc']=LOC[name]

@step(r'armor location is resolved')
def project(w):w['result']=p.personal_location(w['loc'])

@step(r'location is (\w+)')
def projected(w,name):eq(w['result'],LOC[name])

@step(r'armor location (\w+) code (\d+) damage100 and a fully defended PC weapon')
def armor(w,loc,code):
    w['unit'].unit_type=U.MW;w['loc']=LOC[loc];w['unit'].sections[w['loc']].armor=int(code)
    # A non-PC cause is defended by every profile, with identical source block math.
    # PC_HEAT|PC_SHAR|PC_IMPA intersects all 14 defenses.
    from types import SimpleNamespace
    w['weapon']=SimpleNamespace(special=p.PCOMBAT)

@step(r'variation100 weak-point2 half1 and block1 are drawn')
def armor_run(w):w['result']=draws(w,[100,2,1,1],p.personal_armor_effect,w['unit'],w['weapon'],w['loc'],100)

@step(r'resulting damage is (-?\d+)')
def damage_result(w,n):eq(w['result'],int(n))

@step(r'CT armor6 input damage (-?\d+) and source condition (.+)')
def luck(w,damage,condition):
    w['unit'].unit_type=U.MW;w['unit'].sections[4].armor=6;w['amount']=int(damage);w['condition']=condition

@step(r'personal armor is applied')
def luck_run(w):
    condition=w['condition'];unit=w['unit'];dice=[100,2,1,1];ident=-1
    if condition in ('double','bypass'):dice=[100,1,1 if condition=='double' else 2,1]
    if condition=='half':dice=[100,2,2,1]
    if condition=='id-minus2':dice=dice[1:];ident=-2
    if condition=='unknown-armor9':unit.sections[4].armor=9;dice=dice[:-1]
    if condition=='armor0':unit.sections[4].armor=0;dice=[100]
    if condition=='nonMW':unit.unit_type=U.MECH;dice=[100]
    try:w['result']=draws(w,dice,p.personal_armor_effect,unit,None,4,w['amount'],id=ident)
    except ValueError as error:
        assert 'division by zero' in str(error);w['result']='undefined-domain'

@step(r'resulting damage is (.+) and Number call sequence is (.+)')
def luck_result(w,expected,calls):
    eq(w['result'],expected if expected=='undefined-domain' else int(expected))
    mapped=[{'personal_variation':'variation','personal_weak_point':'weak','personal_double_or_bypass':w['condition'],'personal_half':'half','personal_block':'block'}[n] for n in w['calls']]
    eq('-'.join(mapped),calls)

@step(r'source armor (\w+) against weapon (\w+) with damage100')
def protection(w,armor,weapon):
    w['unit'].unit_type=U.MW;w['loc']=7 if armor=='Helmet' else 4;w['unit'].sections[w['loc']].armor=1
    from types import SimpleNamespace
    w['weapon']=SimpleNamespace(special=getattr(W,weapon)) if weapon!='normal' else None

@step(r'normal variation and luck draws are used')
def protection_run(w):
    profile=next(r for r in p.ARMORS if r[:2]==(w['loc'],1))
    defended=w['weapon'] is None or bool(profile[2]&w['weapon'].special)
    w['result']=draws(w,[100,2,1]+([1] if defended else []),p.personal_armor_effect,w['unit'],w['weapon'],w['loc'],100)

@step(r'resulting damage is (-?\d+) and block draw count is (\d+)')
def protection_result(w,n,count):eq(w['result'],int(n));eq(w['calls'].count('personal_block'),int(count))

_DIRECTORY=None
@step(r'a genuine project-local MechWarrior template and source-backed character record')
def initialize_background(w):
    global _DIRECTORY
    base(w)
    from data.template_catalog import CatalogDirectory
    from data.template_dependency import resolve_catalog
    if _DIRECTORY is None:_DIRECTORY=CatalogDirectory(w['root']/'templates',resolve_catalog(True))
    w['directory']=_DIRECTORY
    assert _DIRECTORY.loadnew(w['unit'],'MechWarrior',wrapper=True)

@step(r'Build5 Reflexes4 Running3 bruise10 lethal10')
def body(w):values(w,Build=5,Reflexes=4,Running=3,Bruise=10,Lethal=10)

@step(r'a fresh MW is initialized')
def initialize(w):p.initialize_pc(w['store'].actor(101),w['unit'],w['directory'].catalog)

@step(r'section (\w+) has original and current internal (\d+) and zero original armor')
def section(w,loc,n):
    s=w['unit'].sections[LOC[loc]];eq((s.internal_orig,s.internal,s.armor_orig),(int(n),int(n),0))

@step(r'equipment field (.+) and initialization state (.+)')
def equipment(w,text,state):
    w['equipment']=text;w['initstate']=state
    text=text.replace('valid-right','PC.SMG').replace('valid-left','PC.LaserRifle') if 'invalid' not in text else text.replace(' invalid',' MISSING').replace('valid-right','PC.SMG').replace('valid-left','PC.LaserRifle')
    # Invalid labels remain guaranteed absent catalog names after substitution.
    if text=='empty':text=''
    w['store'].records[101]['pcequip']=text
    if state=='already-initialized':w['unit'].set_crit_status(CritStatus.PC_INITIALIZED)
    if state=='nonMW':w['unit'].unit_type=U.MECH
    from copy import deepcopy
    w['before']=deepcopy(w['unit'].sections)

@step(r'source initialization runs')
def equipment_run(w):
    try:initialize(w);w['error']=None
    except ValueError as error:w['error']=str(error)

@step(r'visible result is (.+)')
def equipment_result(w,expected):
    unit=w['unit'];left=unit.sections[0].criticals;right=unit.sections[1].criticals
    if expected=='unchanged':eq(unit.sections,w['before']);return
    assert unit.has_crit_status(CritStatus.PC_INITIALIZED)
    if expected=='current-HEAD1-CT2-RA3-RL4':eq([unit.sections[i].armor for i in (7,4,1,6)],[1,2,3,4])
    elif expected=='armor-error-flag-set':assert 'Invalid armor char' in w['error']
    elif expected=='length-error-flag-set':assert 'Invalid armor string' in w['error']
    elif expected=='left-error-before-right':assert w['error'];eq(right[0].type,0);eq(left[0].type,0)
    elif expected=='left-installed-before-right-error':assert w['error'];eq(left[0].type,get_weapon('PC.LaserRifle').index+1);eq(right[0].type,0)
    elif expected=='right-ammo3-left-ammo4':eq((right[1].data,left[1].data),(3,4))
    elif expected=='no-equipment':eq([s.armor for s in unit.sections],[0]*8);eq(sum(s.type for sec in unit.sections for s in sec.criticals),0)
    else:raise AssertionError(expected)

@step(r'Build (\d+) Reflexes (\d+) effective Running (\d+) and a valid personal weapon without ammo override')
def speed(w,build,reflexes,running):
    values(w,Build=int(build),Reflexes=int(reflexes),Running=int(running));w['store'].records[101]['pcequip']='0000 PC.SMG -'

@step(r'the MW initializes')
def speed_run(w):initialize(w)

@step(r'maximum speed is ([0-9.]+) and ammo starts at source full capacity')
def speed_result(w,speed):
    assert abs(w['unit'].max_speed-float(speed))<0.000002
    eq(w['unit'].sections[1].criticals[1].data,get_weapon('PC.SMG').ammo_per_ton)
