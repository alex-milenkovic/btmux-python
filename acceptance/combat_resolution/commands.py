"""Targeting and preference commands exercise live entities and events."""
from . import step,eq,session,unit,call,dice,position
from .area import advance
from .modes import mount
from entities.mech import MechStatus as S,MechStatus2 as S2,Specials,UnitType as U,MoveType as M
from entities.crittypes import i2ammo
from physics.hexmath import SCALEMAP,find_bearing
from systems import targeting,combat_preferences as prefs


def acquire_contacts(w):
    from systems import sensors
    from core.events import EventType
    from types import SimpleNamespace
    s=session(w)
    dice(w,'sensor.detect',[1]*20)
    call(w,sensors.update_los_info,s.map)
    for peer in s.units.values():
        s.engine.events.cancel_by_type_and_data(EventType.PLOS,peer)
        call(w,targeting.plos_event,SimpleNamespace(data=peer,data2=s.engine))
    for peer in s.units.values():peer.movement_messages.clear()

@step(r'fresh zero preference bits')
def zero(w):unit(w).prefs=0

@step(r'preference (\w+) is set (ON|OFF)')
def preference(w,name,state):
    w['pref_name']=name
    reply=call(w,prefs.mechprefs,unit(w),name+' '+state)
    eq(reply['accepted'],True)

@step(r'underlying preference bit is (\d+) and displayed state is (ON|OFF)')
def preference_result(w,bit,state):
    row=prefs.preference(unit(w),w['pref_name'])
    eq((row['bit'],row['state']),(int(bit),state))

@step(r'a ready tank with intact turret and visible off-axis target lock')
def turret(w):
    u=unit(w)
    u.unit_type=U.VEH_GROUND
    u.move_type=M.TRACK
    u.target=unit(w,'v')._id
    u.facing=0
    u.turret_facing=123
    position(unit(w,'v'),4,3)

@step(r'autoturret is (enabled|disabled) and the normal update runs')
def turret_update(w,state):
    if state=='enabled':eq(call(w,prefs.auto_turret,unit(w))['accepted'],True)
    from core.game_loop import mech_update
    call(w,mech_update,session(w).engine,unit(w))

@step(r'turret facing is (target-bearing|unchanged)')
def turret_result(w,state):
    u,v=unit(w),unit(w,'v')
    eq(u.turret_facing,123 if state=='unchanged' else int(find_bearing(u.fx,u.fy,v.fx,v.fy)-u.facing)%360)

@step(r'a ready Gauss weapon and an ordinary ballistic weapon')
def weapons(w):
    for loc,name in enumerate(('IS.GaussRifle','IS.AC/10')):
        slot=mount(w,name,loc)
        ws=unit(w).weapons[-1]
        ammo=unit(w).sections[3].criticals[loc]
        ammo.type,ammo.data=i2ammo(ws.weapon_idx),10
    unit(w).target=unit(w,'v')._id

@step(r'disableweap selects (Gauss|ballistic)')
def disable(w,name):
    w['number']=0 if name=='Gauss' else 1
    call(w,prefs.disable_weapon,unit(w),str(w['number']))
    from systems.combat import fire_weapon
    w['attack']=call(w,fire_weapon,unit(w),unit(w,'v'),w['number'],1,to_hit_roll=12,engine=session(w).engine)

@step(r'temporary weapon state is (FAIL_DESTROYED|unchanged) and subsequent firing is (rejected|allowed)')
def disable_result(w,state,fire):
    from systems.enhanced_crits import part_temp_nuke,FAIL_DESTROYED
    slot=unit(w).sections[w['number']].criticals[4]
    eq(part_temp_nuke(slot),FAIL_DESTROYED if state=='FAIL_DESTROYED' else 0)
    eq(w['attack'].bth_breakdown is not None,fire=='allowed')

@step(r'a valid visible enemy MECH contact AB and a ready actor')
def contact(w):
    unit(w,'v').contact_id='AB'
    acquire_contacts(w)
    from systems.los import in_line_of_sight
    eq(bool(call(w,in_line_of_sight,unit(w),unit(w,'v'),3,2,1)),True)

@step(r'the actor issues lock with text (.+)')
def lock(w,text):w['lock_result']=call(w,targeting.lock_command,session(w).engine,unit(w),text)

@step(r'target state is (\S+)')
def target_result(w,state):
    u=unit(w)
    if state=='enemy-lock':eq(u.target,unit(w,'v')._id)
    elif state in ('no-lock','rejected-no-lock'):
        eq(u.target,-1)
        eq((u.targ_x,u.targ_y),(-1,-1))
        eq(w['lock_result'][0],state=='no-lock')
    else:
        kind=state.removesuffix('-3-4')
        eq((u.targ_x,u.targ_y),(3,4))
        flag={'coordinates':S.LOCK_TARGET,'ignite':S.LOCK_HEX_IGN,'clear':S.LOCK_HEX_CLR,'hex':S.LOCK_HEX,'building':S.LOCK_BUILDING}[kind]
        eq(bool(u.status & flag),True)

@step(r'a sixth-sense target and attacker mass difference (-?\d+) at range ([\d.]+)')
def sense(w,tons,distance):
    from entities.map import GameMap
    from physics.hexmath import float_to_hex
    s=session(w)
    board=GameMap(40,40)
    board.mapvis,board.maxvis,board.maplight=30,60,2
    board.losinfo={}
    board.grav=100
    board.mechs_on_map=list(s.units.values())
    s.engine.unregister_entity(s.map)
    s.map=board
    s.engine.register_entity(board)
    for peer in s.units.values():peer.map=board
    u,v=unit(w),unit(w,'v')
    u.rtons=(50+int(tons))*1024
    v.rtons=50*1024
    v.specials |= Specials.SS_ABILITY
    # Diagnostic real separation preserves the stated fractional range.
    v.fx=u.fx
    v.fy=u.fy+float(distance)*SCALEMAP
    v.fz=u.fz
    v.x,v.y=float_to_hex(v.fx,v.fy)
    dice(w,'sixth_sense_rolls',[8])
    dice(w,'sixth_sense_delay',[2])

@step(r'a lock succeeds with sixth-sense roll 8 and delay draw 2')
def sense_lock(w):
    acquire_contacts(w)
    eq(call(w,targeting.set_target,session(w).engine,unit(w),unit(w,'v'))[0],True)

@step(r'no warning appears at tick 1 and source warning index (\d+) appears at tick 2')
def sense_result(w,index):
    advance(w,1)
    eq(unit(w,'v').movement_messages,[])
    advance(w,2)
    eq(unit(w,'v').movement_messages,[targeting.SIXTH_SENSE_MESSAGES[int(index)]])

@step(r'a sixth-sense warning due at tick 2')
def pending_warning(w):
    sense(w,'0','2')
    sense_lock(w)

@step(r'target pilot state becomes (conscious-present|unconscious|absent) before tick 2')
def pilot(w,state):
    if state=='unconscious':unit(w,'v').set_status(S.UNCONSCIOUS)
    elif state=='absent':unit(w,'v').pilot=None
    advance(w,2)

@step(r'the warning is (delivered|suppressed)')
def warning_result(w,result):eq(bool(unit(w,'v').movement_messages),result=='delivered')
