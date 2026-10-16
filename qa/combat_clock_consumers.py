"""Ordinary-clock complements to isolated arithmetic and callback procedures."""
from combat_support import *

def cases():
    import combat_extended,combat_examples
    for old in combat_extended.booster_cases():
        if old.label not in ('boosters-toggle-clock-masc-0','boosters-toggle-clock-scharge-0','boosters-supercharger-engine-draw-1'):continue
        old.document['config']['periodic_updates']=True
        old.label=old.label.replace('boosters-','boosters-normal-')
        yield old
    old=combat_examples.boosters(3,dict(speed='0',chassis='biped',hips='2',fall='0'))[0]
    old.document['config']['periodic_updates']=True;old.label='boosters-normal-MASC-hip-failure'
    yield old
    d=fixture();mount(d);d['random']['streams']['attack_rolls']=[12,12,12]
    d['actions']=[cmd('sight','0'),cmd('fire','0'),inspect(),advance(40),cmd('fire','0')]
    yield Case(d,lambda o:checks((o['results'][0]['accepted'],True),(o['results'][1]['accepted'],True),(o['results'][-1]['accepted'],True),(loss(o),10),(state(o,index=2)['weap_heat'],3.0),(state(o)['shots_fired'],2)),label='firing-normal-recycle-and-refire',mode='normal')
    d=fixture();mount(d);d['units'][1]['at']=[8,8,0];d['map']['hexes']=[dict(at=[3,2],terrain='LIGHT_FOREST',elevation=0)]
    d['random']['streams'].update(attack_rolls=[12],terrain_rolls=[7,6,5],terrain_replacement=[1]);d['actions']=[cmd('lock','3','2','C'),cmd('fire','0'),advance(40)]
    yield Case(d,lambda o:checks((o['results'][1]['accepted'],True),(next(h['terrain'] for h in o['state']['map']['hexes'] if h['at']==[3,2]),'%'),(rawslot(o)['data'],0),(draws(o,'terrain_rolls'),[7,6,5])),label='terrain-normal-clear-and-recycle',mode='normal')
