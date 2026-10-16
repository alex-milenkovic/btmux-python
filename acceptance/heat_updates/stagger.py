"""Stagger list boundaries and heartbeat consequences."""
from .context import *
from systems import stagger as rules
from core.game_loop import mech_heartbeat
from entities.mech import Location
from systems.combat import apply_damage_with_transfer


@step(r'stagger history contains an uncounted hit of 12 and a counted hit of 9 both (\d+) wall seconds old')
def history(w,age):
    w['engine'].sim_now=int(age)
    w['unit'].stagger_damage_list=[dict(amount=12,counted=False,occurred_at=0),dict(amount=9,counted=True,occurred_at=0)]


@step(r'current stagger totals are inspected then expiry maintenance runs')
def inspect(w):
    now=w['engine'].sim_now
    w['uncounted']=rules.current_damage(w['unit'],now);w['counted']=rules.current_damage(w['unit'],now,True)
    rules.clear_expired(w['unit'],now)


@step(r'inspected uncounted damage is (\d+) counted damage is (\d+) and surviving nodes number (\d+)')
def inspected(w,uncounted,counted,nodes):
    equal((w['uncounted'],w['counted'],len(w['unit'].stagger_damage_list)),(int(uncounted),int(counted),int(nodes)))


@step(r'chronological recent stagger hits are 12 uncounted 9 counted 15 uncounted and 8 uncounted')
def whole(w):
    w['unit'].stagger_damage_list=[dict(amount=n,counted=c,occurred_at=0) for n,c in ((12,False),(9,True),(15,False),(8,False))]


@step(r'stagger maintenance action (MARK|REMOVE|CLEAR_ALL) uses level (\d+)')
def action(w,action,level):
    if action=='CLEAR_ALL':rules.clear_all(w['unit'])
    else:{'MARK':rules.mark_damage,'REMOVE':rules.remove_damage}[action](w['unit'],int(level))


@step(r'uncounted damage is (\d+) counted damage is (\d+) and surviving nodes number (\d+)')
def totals(w,uncounted,counted,nodes):
    equal(rules.current_damage(w['unit'],0),int(uncounted));equal(rules.current_damage(w['unit'],0,True),int(counted));equal(len(w['unit'].stagger_damage_list),int(nodes))


@step(r'a started upright mech of (\d+) tons receives one external hit of (\d+) at wall time zero with new stagger mode (1|2)')
def hit(w,tons,damage,mode):
    w['unit'].tonnage=int(tons);w['engine'].new_stagger=int(mode)
    w['unit'].sections[Location.CTORSO].armor=1000
    invoke(w,apply_damage_with_transfer,w['unit'],Location.CTORSO,int(damage),engine=w['engine'])


@step(r'the heartbeat reaches wall second (\d+) with piloting roll (\d+)')
def heartbeat(w,seconds,roll):
    w['engine'].sim_now=int(seconds);w['dice']['pilot_rolls']=int(roll)
    invoke(w,mech_heartbeat,w['engine'],w['unit'])


@step(r'stagger roll count is (\d+) the mech is fallen '+B+r' and remaining stagger nodes number (\d+)')
def result(w,count,fallen,nodes):
    equal(len(w['rolls']),int(count));equal(w['unit'].is_fallen,boolean(fallen));equal(len(w['unit'].stagger_damage_list),int(nodes))


@step(r'a 50 ton mech in new stagger mode 1 has already passed a check for 20 counted damage')
def prior(w):
    hit(w,50,20,1);heartbeat(w,5,12);w['rolls'].clear()


@step(r'another (\d+) damage arrives and the next five-second heartbeat check occurs')
def another(w,damage):
    invoke(w,apply_damage_with_transfer,w['unit'],Location.CTORSO,int(damage),engine=w['engine'])
    heartbeat(w,10,12)


@step(r'additional stagger roll count is (\d+) and the stagger modifier is (NONE|-?\d+)')
def more(w,count,modifier):
    equal(len(w['rolls']),int(count));equal(w['rolls'][-1]['modifier'] if w['rolls'] else 'NONE',int(modifier) if modifier!='NONE' else modifier)
