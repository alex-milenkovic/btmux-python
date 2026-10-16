from . import *
from systems.combat import apply_damage_with_transfer
from systems.criticals import apply_internal_damage_with_transfer
from systems.damage import check_ap_critical
from entities.mech import SectionConfig, AmmoMode

def hit(w,amount,rear=False,critical=False,internal=False):
    u=unit(w)
    return call(w,apply_damage_with_transfer,u,w['section'],int(amount),rear,session(w).units['enemy'],critical,w.get('weapon'),w.get('ammo_mode',0),session(w).engine,internal=internal,ignore_swarmers=w.get('ignore',False))

@step(r'a (\S+) with hit section (\w+) armor (\d+) rear armor (\d+) and internal (\d+)')
def armor_fixture(w,kind,section,front,rear,internal):
    u=setup(w,kind);w['section']=loc(w,section);s=u.sections[w['section']]
    s.armor=s.armor_orig=int(front);s.rear=s.rear_orig=int(rear);s.internal=s.internal_orig=int(internal)

@step(r'armor technology (\S+) and all incidental critical rolls below eight')
def technology(w,kind):
    unit(w).specials |= {'standard':0,'hardened':Specials.HARDA_TECH,'reinforced-internal':Specials.REINFI_TECH,'composite-internal':Specials.COMPI_TECH}[kind]

@step(r'an ordinary (\d+) point hit arrives with rear flag (True|False)')
def ordinary(w,amount,rear): hit(w,amount,truth(rear))

@step(r'section front armor is (\d+) rear armor is (\d+) and internal is (\d+)')
def armor_left(w,front,rear,internal):
    s=unit(w).sections[w['section']];eq((s.armor,s.rear,s.internal),tuple(map(int,(front,rear,internal))))

@step(r'armor warnings (True|False) original armor (\d+) current armor (\d+) and rear flag (True|False)')
def warnings(w,enabled,original,before,rear):
    w['section']=2;w['rear']=truth(rear);unit(w).armor_warnings=truth(enabled)
    s=unit(w).sections[2];s.armor_orig=s.rear_orig=int(original);s.armor=s.rear=int(before)

@step(r'a (\d+) point hit is applied without penetration criticals')
def warning_hit(w,amount):hit(w,amount,w['rear'])

@step(r'the warning severity is (\w+) and warning count is (\d+)')
def warning_result(w,severity,count):
    notices=getattr(unit(w),'armor_notices',[]);eq(len(notices),int(count));eq(notices[-1]['severity'] if notices else 'none',severity)

@step(r'an AC AP hit with original armor (\d+) armor before (\d+) hit damage (\d+) and weapon (\S+)')
def ap_fixture(w,original,before,damage,weapon):
    w.update(ap_damage=int(damage),ap_name=weapon);s=unit(w).sections[4];s.armor_orig=int(original);s.armor=int(before)

@step(r'the armor critical roll is (\d+)')
def ap_hit(w,roll):
    u=unit(w);s=u.sections[4];overflow=w['ap_damage']-s.armor;s.armor=max(0,-overflow)
    weapon=get_weapon('IS.'+w['ap_name']) or get_weapon('IS.MediumLaser')
    w['ap_count']=check_ap_critical(u,4,weapon,AmmoMode.AC_AP_MODE,False,overflow,roll=int(roll))

@step(r'the AP critical count is (\d+)')
def ap_result(w,count):eq(w['ap_count'],int(count))

@step(r'a MECH torso with one armor point and six independently crittable nonexplosive slots')
def crit_fixture(w):
    s=unit(w).sections[4];s.armor=1;s.internal=100
    for slot in s.criticals[:6]:slot.type=i2special(Special.LIFE_SUPPORT)

@step(r'a two point hit with hit-critical flag True rolls (\d+) for armor and (\d+) for internals')
def armor_internal(w,armor,internal):draw(w,'critical_rolls',[int(armor),int(internal)]);hit(w,2,critical=True)

@step(r'actual critical slot dispatches total (\d+) and two critical rolls are recorded')
def counts(w,count):
    eq(sum(bool(s.firemode & F.DESTROYED_MODE) for s in unit(w).sections[4].criticals),int(count))
    eq(len(unit(w).critical_rolls),2)

@step(r'a (?:standing )?MECH (?:left arm|with left arm) (?:with )?armor (\d+) internal (\d+) and left torso (?:with )?armor (\d+)(?: internal (\d+))?')
def transfer_fixture(w,armor,internal,torso,tinternal):
    u=unit(w);w['section']=0
    u.sections[0].armor=int(armor);u.sections[0].internal=int(internal)
    u.sections[2].armor=int(torso);u.sections[2].internal=int(tinternal or 20)

@step(r'containment (\S+) and incidental critical rolls below eight')
def containment(w,name):
    u=unit(w)
    if name=='CASE':u.sections[0].config|=SectionConfig.CASE_TECH
    elif name=='Clan':u.specials|=Specials.CLAN_TECH
    elif name=='CASE-II-only':u.sections[0].config|=SectionConfig.CASEII_TECH
    else:eq(name,'none')

@step(r'(\d+) points strike the arm through the (ordinary|internal) path')
def transfer_hit(w,amount,path):hit(w,amount,internal=path=='internal')

@step(r'left arm is destroyed (True|False) and left torso armor is (\d+) internal is (\d+)')
def transfer_result(w,dead,armor,internal):
    u=unit(w);eq(u.sections[0].internal==0,truth(dead));eq((u.sections[2].armor,u.sections[2].internal),(int(armor),int(internal)))

@step(r'a MECH with already destroyed left arm and live left torso armor (\d+) internal (\d+)')
def dead_arm(w,armor,internal):transfer_fixture(w,'0','0',armor,internal)

@step(r'an ordinary (\d+) point hit targets the dead arm')
def dead_hit(w,amount):hit(w,amount)

@step(r'left torso armor is (\d+) and the destroyed arm dispatches no new criticals')
def dead_result(w,armor):eq(unit(w).sections[2].armor,int(armor));eq(getattr(unit(w),'critical_rolls',[]),[])

@step(r'an intact hidden sprinting MECH with map safety (True|False) unit safety (True|False) and attacker weapons hold (True|False)')
def safety(w,mapped,safe,hold):
    u=unit(w);u.crit_status|=C.HIDDEN;u.status2|=S2.SPRINTING
    session(w).map.buildflag=2 if truth(mapped) else 0
    if truth(safe):u.status|=S.COMBAT_SAFE
    if truth(hold):session(w).units['enemy'].status2|=S2.WEAPONS_HOLD
    w['section']=2

@step(r'a five point hit is applied to left torso armor (\d+)')
def safe_hit(w,armor):unit(w).sections[2].armor=int(armor);hit(w,5)

@step(r'armor is (\d+) hidden is (True|False) sprinting is (True|False) and hold warning count is (\d+)')
def safety_result(w,armor,hidden,sprint,count):
    u=unit(w);eq(u.sections[2].armor,int(armor));eq(bool(u.crit_status&C.HIDDEN),truth(hidden));eq(bool(u.status2&S2.SPRINTING),truth(sprint))
    eq(sum('weapons hold' in msg for msg in session(w).units['enemy'].movement_messages),int(count))

@step(r'one damage-entry roll is consumed even when safety prevents the hit')
def entry(w):eq(sum(d['name']=='damage_entry' for d in session(w).draws),1)

@step(r'enemy gun damage (\d+) crosses the arm with critical rolls below eight')
def accounted_hit(w,amount):hit(w,amount)

@step(r'inflicted and taken counters each increase (\d+) and stagger records total (\d+)')
def accounting(w,amount,stagger):
    eq(unit(w).damage_taken,int(amount));eq(session(w).units['enemy'].damage_inflicted,int(amount));eq(sum(n['amount'] for n in unit(w).stagger_damage_list),int(stagger))

@step(r'one live swarming suit on an armored MECH and ignore-swarmers (True|False)')
def swarm_fixture(w,ignore):
    w['ignore']=truth(ignore)
    suit=session(w).add_unit({'name':'suit','class':'BSUIT'})
    suit.swarm_target=unit(w)
    for i,s in enumerate(suit.sections):s.internal=10 if i==0 else 0
    w['suit']=suit
    draw(w,'live_suit',[0]*10)

@step(r'a host hit at (\w+) with rear flag (True|False) uses absorption roll (\d+)')
def swarm_hit(w,section,rear,roll):
    w['section']=loc(w,section);draw(w,'damage_entry',[int(roll),7,7]);hit(w,3,truth(rear))

@step(r'the damage is routed to the suit (True|False)')
def swarm_result(w,absorbed):eq(w['suit'].damage_taken>0,truth(absorbed))
