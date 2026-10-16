from . import *
from .recovery import synthetic,slot,ammunition,temp
from systems import enhanced_crits as ec
from systems.combat import fire_weapon
FLAGS={'moderate':ec.WEAP_DAM_MODERATE,'focus':ec.WEAP_DAM_EN_FOCUS,'crystal':ec.WEAP_DAM_EN_CRYSTAL,'ranging':ec.WEAP_DAM_MSL_RANGING,'missile-feed':ec.WEAP_DAM_MSL_AMMO,'barrel':ec.WEAP_DAM_BALL_BARREL,'ballistic-feed':ec.WEAP_DAM_BALL_AMMO}

def fill_run(w,size):
    for s in unit(w).sections[w['section']].criticals[w['slot']:w['slot']+size]:s.type=i2weapon(w['weapon'].index)

@step(r'a MECH (\w+) weapon with six slots and no previously damaged slots')
def severity_fixture(w,kind):synthetic(w,kind,crits=6);fill_run(w,6)

@step(r'an enhanced critical rolls (\d+)')
def severity(w,roll):draw(w,'enhanced_rolls',[int(roll)]);w['notice']=call(w,ec.score_enhanced_weapon_critical_hit,unit(w),session(w).units['enemy'],w['section'],w['slot'])

@step(r'selected slot damage kind is (\S+) and the weapon is destroyed (True|False)')
def severity_result(w,kind,destroyed):
    s=slot(w);eq(bool(s.firemode&F.DESTROYED_MODE),truth(destroyed))
    if kind not in ('destroyed','none-noticeable'):eq(s.weap_damage_flags,FLAGS[kind])
    elif kind=='none-noticeable':eq(s.weap_damage_flags,0)

@step(r'a (\w+) weapon with catalog critical size (\d+) and (\d+) already damaged slots')
def threshold_fixture(w,kind,size,damaged):
    setup(w,kind);synthetic(w,'energy',crits=int(size));fill_run(w,int(size))
    for s in unit(w).sections[4].criticals[:int(damaged)]:s.firemode|=F.DAMAGED_MODE

@step(r'destruction is checked with increment (True|False)')
def threshold(w,inc):w['destroy']=ec.should_destroy_weapon(unit(w),4,0,truth(inc))

@step(r'weapon destruction is required (True|False)')
def threshold_result(w,destroyed):eq(w['destroy'],truth(destroyed))

@step(r'a MECH energy weapon with base damage (\d+) heat (\d+) short range (\d+) and damaged flags ([\w,]+)')
def modifiers(w,damage,heat,short,flags):
    synthetic(w,'energy',damage=int(damage),heat=int(heat),range_short=int(short),crits=6);fill_run(w,6)
    for i,name in enumerate(flags.split(',')):
        s=unit(w).sections[4].criticals[i];s.firemode|=F.DAMAGED_MODE;s.weap_damage_flags=FLAGS[name]
    for s in session(w).units['enemy'].sections:s.armor=s.armor_orig=100

@step(r'a successful ordinary shot is fired at range (\d+) with shot roll twelve')
def modifier_shot(w,distance):w['shot']=call(w,fire_weapon,unit(w),session(w).units['enemy'],0,int(distance),to_hit_roll=12,location_roll=7,engine=session(w).engine)

@step(r'critical BTH addition is (\d+) target damage is (\d+) and firing heat is (\d+)')
def modifier_result(w,bth,damage,heat):eq((w['shot'].critical_bth,w['shot'].damage_dealt,unit(w).weap_heat),tuple(map(int,(bth,damage,heat))))

@step(r'a MECH weapon with one damaged (\S+) slot base damage (\d+) and ten rounds if nonenergy')
def damaged(w,part,damage):
    category=part.split('-')[0];synthetic(w,category,damage=int(damage));s=slot(w);s.firemode|=F.DAMAGED_MODE
    s.weap_damage_flags=FLAGS[{'energy-crystal':'crystal','ballistic-feed':'ballistic-feed','missile-feed':'missile-feed','ballistic-barrel':'barrel'}[part]]
    if category!='energy':ammunition(w)
    w['internal_before']=sum(s.internal for s in unit(w).sections)

@step(r'the pilot fires with shot roll (\d+)')
def damaged_shot(w,roll):w['shot']=call(w,fire_weapon,unit(w),session(w).units['enemy'],0,1,to_hit_roll=int(roll),location_roll=7,engine=session(w).engine)

@step(r'firing outcome is (\w+) shooter internal damage is (\d+) and ammunition spent is (\d+)')
def damaged_result(w,outcome,internal,ammo):
    eq(w['internal_before']-sum(s.internal for s in unit(w).sections),int(internal));eq(10-w['bin'].data if 'bin' in w else 0,int(ammo))
    if outcome=='AMMOCRITJAMMED':eq(ec.part_temp_nuke(slot(w)),7)
    else:eq(w['shot'].shot_aborted,outcome=='exploded')

@step(r'a MECH energy weapon with one damaged slot carrying flag (\w+)')
def detail_fixture(w,flag):mount(w);slot(w).firemode|=F.DAMAGED_MODE;slot(w).weap_damage_flags=FLAGS[flag];w['flag']=flag

@step(r'weaponstatus detail is requested')
def detail(w):w['detail']=ec.show_weapon_damage_and_info(unit(w),4,0)

@step(r'detail damage hit count is (\d+) while actual firing modifier magnitude is one')
def detail_result(w,count):
    key={'moderate':'moderate','focus':'focus','crystal':'crystal'}[w['flag']]
    eq(w['detail']['damage_hits'][{'moderate':0,'focus':1,'crystal':2}[key]],int(count))
    fn={'moderate':lambda:ec.get_crit_added_bth(unit(w),4,0,0),'focus':lambda:ec.get_crit_sub_damage(unit(w),4,0),'crystal':lambda:ec.get_crit_added_heat(unit(w),4,0)}[key]
    eq(fn(),1)
