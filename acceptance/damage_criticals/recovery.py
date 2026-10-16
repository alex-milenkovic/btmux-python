from . import *
from systems import failures as fail, enhanced_crits as ec
from entities.crittypes import i2ammo
from core.game_loop import wire_standard_systems
from dataclasses import replace
from entities.weapon import register_weapon

def synthetic(w,category,**values):
    base=mount(w,category)
    weapon=register_weapon(replace(base,name='TestDamage.'+str(len(__import__('entities.weapon',fromlist=['WEAPON_INDEX']).WEAPON_INDEX)),**values))
    u=unit(w)
    for s in u.sections[w['section']].criticals:
        if s.type==i2weapon(base.index):s.type=i2weapon(weapon.index)
    u.weapons[-1].weapon_idx=weapon.index;w['weapon']=weapon
    return weapon

def slot(w):return unit(w).sections[w['section']].criticals[w['slot']]
def categories(kind):return {'energy':0,'autocannon':6,'ballistic':6,'missile':12,'flamer':18,'computer':24,'radio':30}[kind]
def temp(name):return {'NONE':0,'JAMMED':1,'SHORTED':2,'DUD':3,'EMPTY':4,'DESTROYED':5,'AMMOJAM':6,'AMMOCRITJAMMED':7}[name]

@step(r'a component category (\w+) and brand level (\d+)')
def brand(w,kind,level):
    if kind=='PCOMBAT':
        from entities.weapon import WeaponFlags
        synthetic(w,'energy',special=WeaponFlags.PC_IMPA)
        w['part_type']=i2weapon(w['weapon'].index);w['level']=int(level);return
    w['part_type']=-1 if kind=='computer' else -2 if kind=='radio' else i2weapon(mount(w,kind).index)
    w['level']=int(level)

@step(r'brand information is requested')
def brand_info(w):w['category']=fail.get_brand_index(w['part_type']);w['brand']=fail.get_part_brand_name(w['part_type'],w['level'])

@step(r'category index is (-?\d+) and displayed brand is (\w+)')
def brand_result(w,index,name):eq(w['category'],int(index));eq(w['brand'] or 'none',name)

@step(r'a parts-enabled energy weapon with brand level (\d+)')
def reliability(w,level):mount(w);slot(w).brand=int(level)

@step(r'weapon failure chance draw is (\d+) reliability draw is (\d+) and outcome draw is one')
def reliability_hit(w,chance,reliability):
    draw(w,'failure_weapon_chance',[int(chance)]);draw(w,'failure_reliability',[int(reliability)]);draw(w,'failure_outcome',[1])
    w['failure']=call(w,fail.check_weapon_failed,unit(w),w['section'],w['slot'])

@step(r'failure type is (\w+)')
def failure_type(w,kind):eq(w['failure'].type,kind)

@step(r'a failing (\w+) weapon with base damage (\d+) heat (\d+) and recycle zero')
def callback_fixture(w,kind,damage,heat):synthetic(w,kind,damage=int(damage),heat=int(heat));w['category']=categories(kind)

@step(r'the final failure-table outcome is (\d+) and any duration draw is twenty')
def callback(w,outcome):
    draw(w,'failure_weapon_recycle',[20]);draw(w,'failure_dud_recycle',[20])
    w['failure']=call(w,fail.apply_failure,unit(w),w['category'],int(outcome),w['section'],w['slot'])

@step(r'failure type is (\w+) modifier is (\d+) temporary state is (\w+) and recycle is (\d+)')
def callback_result(w,kind,modifier,temporary,recycle):eq((w['failure'].type,w['failure'].modifier,ec.part_temp_nuke(slot(w)),slot(w).data),(kind,int(modifier),temp(temporary),int(recycle)))

@step(r'a failing energy weapon with brand one base damage (\d+) and zero recycle')
def reroll_fixture(w,damage):synthetic(w,'energy',damage=int(damage));slot(w).brand=1

@step(r'failure outcome draws are ([\d,]+)')
def reroll(w,outcomes):
    draw(w,'failure_weapon_chance',[9]);draw(w,'failure_reliability',[100]);draw(w,'failure_outcome',list(map(int,outcomes.split(','))))
    w['failure']=call(w,fail.check_weapon_failed,unit(w),w['section'],w['slot'])

@step(r'final failure type is (\w+) and outcome draws consumed is (\d+)')
def reroll_result(w,kind,count):eq(w['failure'].type,kind);eq(sum(d['name']=='failure_outcome' for d in session(w).draws),int(count))

@step(r'a ready weapon with ten rounds and initial target armor (\d+)')
def firing_fixture(w,armor):
    for s in session(w).units['enemy'].sections:s.armor=int(armor)

def ammunition(w,rounds=10):
    s=unit(w).sections[2].criticals[8];s.type=i2ammo(w['weapon'].index);s.data=rounds;w['bin']=s

@step(r'ordinary firing encounters brand failure (\S+)')
def firing(w,kind):
    category='missile' if kind.startswith('missile') else 'autocannon';mount(w,category);ammunition(w);slot(w).brand=1
    outcome={'autocannon-dud':2,'autocannon-jam':3,'missile-spike':5,'autocannon-FAIL_NONE-dud':1}[kind]
    draw(w,'failure_weapon_chance',[9]);draw(w,'failure_reliability',[100]);draw(w,'failure_outcome',[outcome]);draw(w,'failure_weapon_recycle',[20]);draw(w,'failure_dud_recycle',[20])
    from systems.combat import fire_weapon
    w['shot']=call(w,fire_weapon,unit(w),session(w).units['enemy'],0,1,to_hit_roll=12,location_roll=7,engine=session(w).engine)

@step(r'rounds remaining are (\d+) target armor is (\d+) and the shot aborted is (True|False)')
def firing_result(w,rounds,armor,aborted):eq(w['bin'].data,int(rounds));eq(session(w).units['enemy'].sections[4].armor,int(armor));eq(w['shot'].shot_aborted,truth(aborted))

@step(r'radio range (\d+) and a radio range-failure reduction of (\d+) scheduled to recover at tick forty')
def radio_fixture(w,initial,reduction):unit(w).radio_range=int(initial);w['category']=30;w['outcome']=3 if int(reduction)==15 else 4

@step(r'an operational radio with range (\d+) whose short recovery is scheduled at tick forty')
def short_fixture(w,initial):unit(w).radio_range=int(initial);w['category']=30;w['outcome']=6

@step(r'initial TAC (\d+) LRS (\d+) SCAN (\d+) and failing scanner channel (\w+) with recovery at tick forty')
def scanner_fixture(w,tac,lrs,scan,channel):
    setup(w,tac_range=int(tac),lrs_range=int(lrs),scan_range=int(scan));w['category']=24;w['outcome']={'TAC':2,'LRS':3,'SCAN':4,'all':5}[channel]

@step(r'the failure occurs and time advances to (\d+)')
def recover(w,time):
    draw(w,'failure_recovery_upper',[40]*3);draw(w,'failure_recovery_delay',[40]*3)
    call(w,fail.apply_failure,unit(w),w['category'],w['outcome']);call(w,session(w).engine.run_ticks,int(time))

@step(r'radio range is (\d+) and operational-again notices number (\d+)')
def radio_result(w,value,count):eq(unit(w).radio_range,int(value));eq(sum('operational again' in s for s in unit(w).movement_messages),int(count))

@step(r'TAC is (\d+) LRS is (\d+) SCAN is (\d+) and recovery notices number (\d+)')
def scanner_result(w,tac,lrs,scan,count):eq((unit(w).tac_range,unit(w).lrs_range,unit(w).scan_range),tuple(map(int,(tac,lrs,scan))));eq(sum('operational again' in s for s in unit(w).movement_messages),int(count))

@step(r'a unit started (True|False) with movement (\w+) target (\d+) and event time (\d+)')
def computer_fixture(w,started,movement,target,time):
    u=unit(w);u.move_type=M[movement];u.target=int(target);u.computer=1
    if not truth(started):u.status&=~S.STARTED
    wire_standard_systems(session(w).engine);call(w,session(w).engine.run_ticks,int(time))

@step(r'computer failure draws select chance (\d+) reliability (\d+) and target-loss outcome one at the next turn boundary')
def computer_draws(w,chance,reliability):draw(w,'failure_generic_chance',[int(chance)]);draw(w,'failure_reliability',[int(reliability)]);draw(w,'failure_outcome',[1]);session(w).units['enemy'].move_type=M.NONE

@step(r'the normal engine advances to tick (\d+)')
def advance_to(w,tick):call(w,session(w).engine.run_ticks,int(tick)-session(w).engine.muxevent_tick)

@step(r'target is (-?\d+) and generic failure checks number (\d+)')
def computer_result(w,target,count):eq(unit(w).target,int(target));eq(sum(d['name']=='failure_generic_chance' for d in session(w).draws),int(count))

@step(r'a failing computer with target (-?\d+)')
def target_fixture(w,target):unit(w).target=int(target)

@step(r'the target-loss failure row is selected')
def target_fail(w):call(w,fail.apply_failure,unit(w),24,1)

@step(r'target is (-?\d+) and failure notices number (\d+)')
def target_result(w,target,count):eq(unit(w).target,int(target));eq(len(unit(w).movement_messages),int(count))

@step(r'a started weapon with temporary DESTROYED state and recycle (\d+)')
def recycle_fixture(w,recycle):mount(w);ec.set_part_temp_nuke(slot(w),5);slot(w).data=int(recycle);wire_standard_systems(session(w).engine)

@step(r'the normal engine performs one recycling tick')
def recycle(w):call(w,session(w).engine.run_ticks,1)

@step(r'temporary state is (\w+) and recycle is zero')
def recycle_result(w,name):eq(ec.part_temp_nuke(slot(w)),temp(name));eq(slot(w).data,0)
