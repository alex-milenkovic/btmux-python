from types import SimpleNamespace
from . import step,base,eq,truth,values,draws
from core.game_loop import GameEngine
from core.randomness import use_source
from data.characters import SKILLS
from data.character_values import code,XP_MAX
from entities.mech import Mech,UnitType as U,MechStatus as S,MechStatus2 as S2
from entities.weapon import get_weapon,WeaponType as T
from systems import experience as x

@step(r'a connected in-character pilot and distinct live in-character enemy with valid source skill identities at wall time101 and last skill use0')
def fresh(w):
    base(w);w['engine']=GameEngine();w['engine'].sim_now=101
    w['engine'].extended_gunnery=w['engine'].extended_piloting=False
    w['unit']=Mech.create_test_mech();w['enemy']=Mech.create_test_mech()
    for i,u in enumerate((w['unit'],w['enemy']),10):
        u._id=i;u._engine=w['engine'];u.status=S.STARTED;u.in_character=True;u.team=i;u.mech_bv=100;u.max_speed=43
    w['store'].records[101]['location']=10;w['actor']=w['store'].actor(101);w['unit'].pilot=w['actor']
    values(w,Build=5,Reflexes=5,Intuition=5,Learn=5,Charisma=5)
    from systems.characters import set_value
    set_value(w['store'],101,'Gunnery-Battlemech',4)
    w['weapon']=get_weapon('IS.MediumLaser')

def raw(w,name):return w['store'].retrieve(101,SKILLS).xp[code(name)]%XP_MAX

@step(r'producer (\S+) with condition (\S+) and reason (\d+)')
def producer(w,p,condition,reason):w.update(producer=p,condition=condition,reason=int(reason))

@step(r'the source award operation runs')
def run(w):
    unit,actor,enemy=w['unit'],w['actor'],w['enemy'];condition=w['condition'];p=w['producer']
    if condition=='no-unit':unit=None
    if condition=='disconnected':actor.connected=False
    if condition=='changedXY':unit.x=2
    if condition=='wrong-pilot':w['store'].create(102,'Other');actor=w['store'].actor(102)
    if condition=='friendly':enemy.team=unit.team
    if p in ('spot','artillery'):w['result']=getattr(x,p)(actor,unit,enemy)
    elif p=='comm':w['result']=x.comm(actor,unit)
    elif p=='piloting':w['result']=x.piloting(actor,unit,w['reason'],condition.endswith('addanyway'))
    elif p=='techweapons':w['result']=x.tech(actor,unit,w['reason'],weapons=True)
    else:w['result']=getattr(x,p)(actor,unit,w['reason'],**({'now':101} if p=='tech' else {}))

@step(r'durable gain request is (\S+)')
def request(w,expected):
    s=w['store'].retrieve(101,SKILLS)
    actual={i:n%XP_MAX for i,n in enumerate(s.xp) if n%XP_MAX}
    if expected=='none':eq(actual,{});return
    name,amount=expected.split(':');eq(actual,{code(name):int(amount)})

@step(r'stored MechPer (\d+) character Perception BTH6 and modifier -2')
def per(w,n):
    from systems.characters import set_value
    set_value(w['store'],101,'Perception',2);w['unit'].per=int(n)

@step(r'source Roll is (\d+)')
def per_roll(w,n):w['result']=draws(w,[int(n)],x.perception,w['unit'],-2)

@step(r'result is (True|False) stored MechPer is (\d+) and requested XP is (\d+)')
def per_result(w,result,stored,xp):eq((w['result'],w['unit'].per,raw(w,'Perception')),(truth(result),int(stored),int(xp)))

@step(r'gun XP system (new|old) with condition (\S+)')
def gun_condition(w,system,condition):
    w['engine'].xp_config=x.Config(oldxpsystem=system=='old');w['bth']=8;u,t=w['unit'],w['enemy']
    if condition.startswith('BTH'):w['bth']=int(condition.split('-')[0][3:]);w['engine'].xp_config.bthmod=condition.endswith('-on')
    elif condition=='NoGunXP':t.status2|=S2.NO_GUN_XP
    elif condition=='all-sections-destroyed':
        for s in t.sections:s.internal=s.armor=0
    elif condition=='same-team':t.team=u.team
    elif condition=='attacker-tons0':u.tonnage=0
    elif condition=='MECH-shoots-MW':t.unit_type=U.MW
    elif condition=='wrong-gunpilot':w['store'].create(102,'Other');w['actor']=w['store'].actor(102)
    elif condition=='target-destroyed':t.status|=S.DESTROYED
    else:raise AssertionError(condition)

@step(r'eligible damage would otherwise earn XP')
def gun_run(w):
    w['calls']=[]
    def source(name,lo,hi,fallback):eq(name,'xp_old_gate');w['calls'].append(name);return 1
    with use_source(source):w['result']=x.gun(w['actor'],w['unit'],w['enemy'],10,100,w['weapon'],w['bth'])

@step(r'an award is (accepted|rejected)')
def gun_result(w,outcome):eq(w['result'],outcome=='accepted');eq(raw(w,'Gunnery-Battlemech')>0,outcome=='accepted')

@step(r'gunnery (-?\d+) piloting (\d+)')
def bv(w,gun,pil):w['bv']=(int(gun),int(pil))
@step(r'the source pilot BV factor is calculated')
def bv_run(w):w['result']=x.pilot_bv_factor(*w['bv'])
@step(r'factor is (-?[\d.]+)')
def bv_result(w,n):assert abs(w['result']-float(n))<.000001,(w['result'],n)
@step(r'effective maximum speed is ([\d.]+) MP')
def speed(w,n):w['speed']=float(n)*10.75
@step(r'the old experience movement value is calculated')
def speed_run(w):w['result']=x.movement_value(w['speed'])
@step(r'value is (\d+)')
def speed_result(w,n):eq(w['result'],int(n))

@step(r'equal BV and speeds weaponBV100 defaultBV100 defaultDamage10 damage10 baseMultiplier100 xp_modifier1 cap100 and no BTH or pilot-BV scaling')
def arithmetic(w):
    w['engine'].xp_config=x.Config(oldxpsystem=False,xp_modifier=1,defaultweapbv=100,defaultweapdam=10,use_pilot_bv=False,xpgain_cap=100,missilemod=1,ammomod=1)
    w['weapon']=SimpleNamespace(index=w['weapon'].index,weapon_type=T.TBEAM,bv=100,vrt=30)
@step(r'the source configuration is (\S+)')
def arithmetic_run(w,config):
    c=w['engine'].xp_config;weapon=w['weapon']
    if config=='missile-factor0.5':weapon.weapon_type=T.TMISSILE;c.missilemod=.5
    elif config=='ammo-factor2':weapon.weapon_type=T.TAMMO;c.ammomod=2
    elif config=='vrt7.5-factor-on':weapon.vrt=7.5;c.vrtmod=True
    elif config=='perunit2':w['unit'].xp_mod=2
    elif config=='cap3':c.xpgain_cap=3
    else:eq(config,'ordinary')
    w['result']=draws(w,[],x.gun_amount,w['unit'],w['enemy'],10,100,weapon,8)
@step(r'awarded XP is (\d+) and old-random gate draws are 0')
def arithmetic_result(w,n):eq(w['result'],int(n));eq(w['calls'],[])
@step(r'the final old multiplier times occurrences is (\d+)')
def difficulty(w,n):w['difficulty']=int(n)
@step(r'Number1to50 is (\d+)')
def probability(w,n):w['result']=draws(w,[int(n)],x.old_probability,w['difficulty'])
@step(r'awarded XP amount is (\d+)')
def probability_result(w,n):eq(w['result'],int(n));eq(w['calls'],['xp_old_gate'])

@step(r'a damage entry with (\S+) original damage9 before personal conversion')
def damage(w,mode):
    w['damage_mode']=mode;w['engine'].xp_config=x.Config(oldxpsystem=False)
    for s in w['enemy'].sections:s.armor=1000;s.internal=1000
    if mode=='rejected-safety':w['enemy'].status|=S.COMBAT_SAFE
    if mode=='recursive-transfer':w['enemy'].sections[0].internal=0
@step(r'the hit is applied through the ordinary shared damage path')
def damage_run(w):
    from systems.combat import apply_damage_with_transfer
    from unittest.mock import patch
    mode=w['damage_mode'];real=x.gun
    with patch('systems.experience.gun',wraps=real) as spy,use_source(lambda name,lo,hi,fallback:hi):
        apply_damage_with_transfer(w['enemy'],0,9,attacker=w['unit'],weapon=w['weapon'],bth=8,physical=int(mode[-1]) if mode.startswith('physical') else 0)
        w['gun_calls']=list(spy.call_args_list)
@step(r'source award route is (\S+)')
def damage_result(w,route):
    calls=w['gun_calls'];requests=getattr(w['unit'],'xp_requests',[])
    if route=='none':eq(calls,[]);eq(requests,[])
    elif route=='piloting3':eq(calls,[]);eq(raw(w,'Piloting-Battlemech'),3)
    else:
        eq(len(calls),1);eq(calls[0].args[3],9);eq(len(requests),1);assert raw(w,'Gunnery-Battlemech')>0
