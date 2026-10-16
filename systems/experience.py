# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btechstats.c
#   btech/mech.notify.c

"""Source XP producers; durable character changes and separate channel effects."""
from dataclasses import dataclass
import math
import random
from core.randomness import float32 as f32,draw,roll
from data.characters import divide,integer
from entities.mech import UnitType as U,MoveType as M,MechStatus2
from entities.weapon import WeaponType as T
from systems.characters import attached,gain_xp,skill_target
from systems.notifications import object_name
from systems.piloting import valid_pilot,find_tech_skill_name,find_piloting_skill_name,find_gunnery_skill_name,find_pilot_gunnery,find_pilot_piloting


@dataclass
class Config:
    oldxpsystem: bool=True
    bthmod: bool=False
    missilemod: float=100
    ammomod: float=100
    defaultweapdam: int=5
    xp_modifier: int=100
    defaultweapbv: int=120
    use_pilot_bv: bool=True
    vrtmod: bool=False
    perunit: bool=True
    xpgain_cap: int=10
    noisy_xpgain: bool=False


def config(unit):return getattr(unit._engine,'xp_config',Config())


def award(actor,unit,name,amount,producer,*,now=None,reported_amount=None,channel_text=None,extra_channels=()):
    if actor is None or name is None:return False
    if attached(actor):
        store=actor._character_store;ident=actor._id
    elif producer in ('piloting','perception'):
        store,ident = local_pilot_xp(actor, name)
    else:return False
    before=dict(store.record(ident)['categories'])
    accepted=gain_xp(store,ident,name,integer(amount),now=integer(now if now is not None else getattr(unit._engine,'sim_now',0) if unit else 0))
    applied=bool(accepted and store.record(ident)['categories']!=before)
    request=dict(skill=name,amount=amount,producer=producer,accepted=bool(accepted),applied=applied,player=ident)
    if unit is not None:
        if not hasattr(unit,'xp_requests'):unit.xp_requests=[]
        unit.xp_requests.append(request)
    if accepted:
        from core.effects import emit_channel
        channel='MechTechXP' if producer in ('tech','techweapons') else 'MechPilotXP' if producer=='piloting' else 'MechAttackXP' if producer in ('gun','artillery') else 'MechXP'
        reported=amount if reported_amount is None else reported_amount
        text = f'{actor.name} gained {reported} {name} XP'
        if producer in ('tech','techweapons'):
            label='technician-weapons' if producer=='techweapons' or unit is None else name
            text=f'{actor.name} gained {reported} {label} XP (changing mech #{unit._id if unit else -1})'
        elif producer=='comm':text+=f' (in #{unit._id})'
        elif producer=='spot':text=f'{actor.name} gained spotting XP'
        elif producer=='perception':text=f'{actor.name} gained 1 perception XP'
        elif producer=='artillery':text=f'{actor.name} gained 1 artillery XP'
        elif producer=='computer':text=f'{actor.name} gained {reported} computer XP (mech #{unit._id})'
        owner=unit if unit is not None else store
        emit_channel(owner,channel,channel_text if channel_text is not None else text)
        for extra_channel,extra_text in extra_channels:emit_channel(owner,extra_channel,extra_text)
    return applied


def local_pilot_xp(actor, name):
    """XP-only character adapter for scalar pilots; leave their identity intact.

    Reuses source category storage, thresholds and gain gates. A caller may
    supply a durable CharacterStore as actor._xp_store; otherwise it is local.
    """
    from data.characters import CharacterStore, Stats, ALL, ATTRS, SKILLS
    store = getattr(actor, '_xp_store', None)
    if store is None:
        actor._xp_store = store = CharacterStore()
    ident = getattr(actor, '_id', 1)
    actor._xp_id = ident
    if ident not in store.records:
        store.create(ident, actor.name, is_player=getattr(actor, 'is_player', True))
        store.store(ident, Stats.fresh(), ALL)
    initialized = getattr(actor, '_xp_skills', set())
    if name not in initialized:
        stats = store.retrieve(ident, ATTRS | SKILLS)
        target = getattr(actor, 'skills', {}).get(name, getattr(actor, 'perception' if name == 'Perception' else 'piloting', 6))
        stats.set(name, max(0, min(255, 16 - target)))
        store.store(ident, stats, SKILLS)
        actor._xp_skills = initialized | {name}
    return store, ident


def tech(actor,unit,reason=1,*,weapons=False,now=None):
    name='Technician-Weapons' if weapons or unit is None else find_tech_skill_name(unit)
    return award(actor,unit,name,max(1,reason),'techweapons' if weapons else 'tech',now=now)


def computer(actor,unit,reason=1):
    if unit is None or not unit.in_character or not getattr(actor,'is_player',False):return False
    return award(actor,unit,'Computer',max(1,reason),'computer',reported_amount=reason)


def comm(actor,unit):
    if unit is None or not valid_pilot(unit) or not unit.in_character or not getattr(actor,'connected',False):return False
    return award(actor,unit,'Comm-Conventional',1,'comm')


def piloting(actor,unit,reason=1,addanyway=False):
    if unit is None or not unit.in_character or not valid_pilot(unit):return False
    name=find_piloting_skill_name(unit)
    if name is None:return False
    if not addanyway:
        if (getattr(unit,'lx',0),getattr(unit,'ly',0))==(unit.x,unit.y):return False
        unit.lx,unit.ly=unit.x,unit.y
    return award(actor,unit,name,max(1,reason),'piloting')


def enemy_gate(actor,unit,target,gun=False):
    return (unit is not None and target is not None and unit.in_character and valid_pilot(unit,gun) is actor and
            unit is not target and not target.is_destroyed and unit.team!=target.team and target.in_character)


def spot(actor,unit,target):
    if not enemy_gate(actor,unit,target):return False
    return award(actor,unit,'Gunnery-Spotting',1,'spot')


def artillery(actor,unit,target):
    if not enemy_gate(actor,unit,target,True):return False
    return award(actor,unit,'Gunnery-Artillery',1,'artillery')


def perception(unit,modifier=0):
    if not unit.in_character or not valid_pilot(unit,True):return False
    actor=unit.pilot
    if actor is None or getattr(actor,'_id',0)<=0:return False
    if not unit.per:
        if attached(actor):unit.per=skill_target(actor._character_store,actor._id,'Perception',2)
        else:
            from systems.piloting import skill_target as scalar_target
            unit.per=scalar_target(actor,'Perception','perception',6)
    if roll('perception_rolls',lambda:random.randint(1,6)+random.randint(1,6))<unit.per+modifier:return False
    award(actor,unit,'Perception',1,'perception');return True


def pilot_bv_factor(gunnery,piloting):
    table=tuple(map(f32,(2.05,1.85,1.65,1.45,1.25,1.15,1.05,.95)))
    base=f32(table[0]+abs(gunnery)*.20) if gunnery<0 else f32(table[7]-gunnery*.10) if gunnery>7 else table[gunnery]
    return f32(base-piloting*.05)


def pilot_bv(unit,weapon):return pilot_bv_factor(find_pilot_gunnery(unit,weapon),find_pilot_piloting(unit))


def movement_value(speed):
    speed=f32(speed)
    return next((i+2 for i,limit in enumerate((2,4,6,9)) if speed<=limit*10.75),6)


def ton_value(unit):return max(1,divide(divide(unit.tonnage,2 if unit.unit_type!=U.MECH else 1),2 if unit.move_type==M.NONE else 1))


BTH=(1,3,6,10,15,21,26,30,33,35)


def old_probability(difficulty):
    if draw('xp_old_gate',1,50,lambda:random.randint(1,50))>difficulty:return 0
    return min(50,max(1,divide(int(difficulty),100)))


def gun_amount(unit,target,damage,multiplier,weapon,bth,*,details=None,actor=None):
    cfg=config(unit);mult=f32(multiplier)
    if cfg.oldxpsystem:
        if not 3<=bth<=12:return 0
        if unit.tonnage<=0:
            from core.effects import send_error
            tons=(int(unit.tonnage)+32768)%65536-32768
            send_error(unit,f'AccumulateGunXP: Weird tonnage for IC mech #{unit._id} ({object_name(unit)}): {tons}')
            return 0
        ratio=divide(integer(100*ton_value(target)),ton_value(unit));mult=f32(mult*min(150,max(50,ratio)))
        from physics.cargo import cargo_max_speed
        own,enemy=movement_value(cargo_max_speed(unit)),movement_value(cargo_max_speed(target))
        mult=f32(f32(f32(f32(mult*enemy)*enemy)/own)/own)
        mult=f32(f32(mult*BTH[bth-3])/36);mult=f32(mult*2)
        if cfg.perunit:mult=f32(mult*getattr(unit,'xp_mod',1))
        if details is not None:details['difficulty']=mult
        return old_probability(f32(mult*damage))
    if bth>12:return 0
    mult=f32(mult*cfg.xp_modifier)
    if cfg.bthmod and not 3<=bth<=12:
        if cfg.noisy_xpgain:
            from core.effects import emit_channel
            pilot=actor or valid_pilot(unit,True)
            emit_channel(unit,'MechXP',f'#{getattr(pilot,"_id",-1)} in #{unit._id} 1 noxp #{target._id}')
        return 0
    if cfg.bthmod:mult=f32(f32(f32(2*mult)*BTH[bth-3])/36)
    own_bv,enemy_bv=int(getattr(unit,'mech_bv',0)),int(getattr(target,'mech_bv',0))
    if cfg.use_pilot_bv:
        own_mod,enemy_mod=pilot_bv(unit,weapon),pilot_bv(target,weapon)
        own_bv=int(f32(own_bv*own_mod));enemy_bv=int(f32(enemy_bv*enemy_mod))
        from core.effects import send_debug
        send_debug(unit,f'Using skill modified battle value for mechs {unit._id} and {target._id} with skill mods of {own_mod:2.2f} and {enemy_mod:2.2f}')
    own_speed,enemy_speed=int(unit.max_speed/10.75)+1,int(target.max_speed/10.75)+1
    typemod=f32(cfg.missilemod if weapon.weapon_type==T.TMISSILE else cfg.ammomod if weapon.weapon_type==T.TAMMO else 1)
    damage_mod=damage if cfg.defaultweapdam>1 else 1
    if cfg.defaultweapdam==0 or damage_mod==0:raise ValueError('Unsupported gun XP division by zero')
    vrtmod=f32(math.sqrt(weapon.vrt/30)) if cfg.vrtmod and weapon.vrt<30 else 1
    numerator=(enemy_bv+1)*enemy_speed*cfg.defaultweapbv/cfg.defaultweapdam
    denominator=(own_bv+1)*own_speed*weapon.bv/damage_mod
    if numerator<0 or denominator<=0:raise ValueError('Unsupported gun XP square-root/division domain')
    mult=f32(f32(f32(vrtmod*typemod)*mult)*math.sqrt(numerator)/math.sqrt(denominator))
    if cfg.perunit:mult=f32(mult*getattr(unit,'xp_mod',1))
    if details is not None:details['difficulty']=mult
    return min(cfg.xpgain_cap,max(1,int(f32(f32(mult*damage)/100))))


def gun(actor,unit,target,damage,multiplier,weapon,bth):
    cfg=config(unit)
    if not cfg.oldxpsystem:
        if all(target.is_section_destroyed(i) for i in range(8)) or target.status2 & MechStatus2.NO_GUN_XP:return False
    if not enemy_gate(actor,unit,target,True):return False
    name=find_gunnery_skill_name(unit,weapon)
    if name is None or code_unknown(name):return False
    if target.unit_type==U.MW and unit.unit_type!=U.MW:return False
    details={}
    amount=gun_amount(unit,target,damage,multiplier,weapon,bth,details=details,actor=actor)
    if not amount:return False
    difficulty=details['difficulty']
    text=(f'{actor.name} gained {amount} gun XP from feat of {difficulty:f} % difficulty ({damage} occurences) against {object_name(target)}'
          if cfg.oldxpsystem else
          f'{actor.name} gained {amount} gun XP from feat of {difficulty:f}/100 difficulty ({damage} damage) against {object_name(target)}')
    extra=[('MechXP',f'#{actor._id} in #{unit._id} {damage} damage #{target._id}')] if cfg.noisy_xpgain and not cfg.oldxpsystem else []
    return award(actor,unit,name,amount,'gun',channel_text=text,extra_channels=extra)


def code_unknown(name):
    from data.character_values import code
    return code(name)<0
