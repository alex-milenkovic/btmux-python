# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.advanced.c
#   btech/mech.events.c

"""Advanced combat equipment commands and their source event callbacks."""
from core.randomness import roll as source_roll
from core.events import EventType as E
from entities.mech import MechStatus as S, MechStatus2 as S2, CritStatus, Specials, MoveType, VehicleLocation
from entities.map import ROAD, BRIDGE, BUILDING, WALL, WATER
from systems.combat_commands import command_guard, command_message, CommandMessages, parse_attributes
from core.effects import send_debug
from systems.movement_commands import notify
from systems.sensors import los_broadcast
from systems import ecm

SIGNATURES={
    'stealtharmor':(0x01,S2.STH_ARMOR_ON,E.STEALTH_ARMOR,'Stealth Armor system'),
    'nullsig':(0x10,S2.NULLSIGSYS_ON,E.NSS,'Null Signature System'),
}


def reply(unit,accepted,text,*,caller=None,audience='auto'):
    if audience == 'auto': audience = 2 if accepted else None
    command_message(unit,text,caller=caller,audience=audience)
    return dict(accepted=accepted,text=text)


def signature_working(unit,name):
    return ecm._has_working_ecm_suite(unit) if name=='stealtharmor' else not unit.crit_status & CritStatus.NSS_DESTROYED


def signature_event(event):
    unit=event.data
    name,enabled=event.data2
    if not unit.is_started or not signature_working(unit,name):return
    _,bit,_,label=SIGNATURES[name]
    notify(unit,f'{label} {"engaged" if enabled else "disengaged"}!')
    unit.status2=unit.status2 | bit if enabled else int(unit.status2) & ~int(bit)
    if name=='stealtharmor':ecm.check_ecm(unit)
    ecm.mark_for_los_update(unit)


def signature_command(unit,name):
    tech,bit,event_type,label=SIGNATURES[name]
    if not unit.specials2 & tech:return reply(unit,False,f"Your 'mech isn't equipped with a {label}!",audience=2)
    if not signature_working(unit,name):
        return reply(unit,False,"Your 'mech doesn't have a working Guardian ECM suite!" if name=='stealtharmor' else 'Your Null Signature System is destroyed!',audience=2)
    queue=unit._engine.events
    if queue.has_event_type_data(event_type,unit):
        return reply(unit,False,f'You are already changing the status of your {label}!',audience=2)
    enabled=not bool(unit.status2 & bit)
    result=reply(unit,True,f'Your {label} begins to {"come online" if enabled else "shutdown"}.')
    queue.schedule(30,event_type,signature_event,unit,(name,enabled))
    return result


def stop_digging(unit,*,leave_hole=False):
    unit.digging=False
    unit.tank_crit_status=getattr(unit,'tank_crit_status',0) & ~8
    if leave_hole:
        unit.dug_in=False
        unit.tank_crit_status &= ~4
    engine=getattr(unit,'_engine',None)
    if engine:engine.events.cancel_by_type_and_data(E.DIG,unit)


def dig_event(event):
    unit=event.data
    if not getattr(unit,'tank_crit_status',0) & 8 or not unit.is_started:return
    unit.tank_crit_status=(unit.tank_crit_status & ~8) | 4
    unit.digging=False
    unit.dug_in=True
    notify(unit,'You finish burrowing for cover - only turret weapons are available now.')


def dig(unit,*,caller=None):
    terrain=unit.map.rterrain(unit.x,unit.y)
    guards=((unit.status2 & S2.FORTIFIED,"You are already fortified, there's no need to dig."),
        (abs(unit.speed)>0,'You are moving!'),
        (unit.facing!=unit.desired_facing,'You are turning!'),
        (unit.move_type==MoveType.NONE,'You are stationary!'),
        (unit.dug_in or getattr(unit,'tank_crit_status',0)&4,'You are already dug in!'),
        (unit.digging or getattr(unit,'tank_crit_status',0)&8,'You are already digging in!'),
        (unit.cocoon,'While dropping? I think not.'),
        (terrain in (ROAD,BRIDGE,BUILDING,WALL),'The surface is slightly too hard for you to dig in.'),
        (terrain==WATER,'In water? Who are you kidding?'))
    for condition,message in guards:
        if condition:return reply(unit,False,message,caller=caller)
    unit.digging=True
    unit.tank_crit_status=getattr(unit,'tank_crit_status',0)|8
    unit._engine.events.schedule(20,E.DIG,dig_event,unit)
    return reply(unit,True,'You start digging yourself in a nice hole..')


def unjam_turret_event(event):
    unit=event.data
    if unit.is_destroyed or unit.is_unconscious or not unit.sections[VehicleLocation.TURRET].internal or not unit.is_started:return
    if getattr(unit,'tank_crit_status',0)&1:
        notify(unit,'You are unable to unjam the turret!')
        return
    unit.tank_crit_status=getattr(unit,'tank_crit_status',0)&~2
    notify(unit,'You manage to unjam your turret!')


def command(unit,name,*,caller=None,wizard=False):
    error=command_guard(unit,map_required=name not in ('fliparms','masc','scharge'),caller=caller,wizard=wizard)
    if error:return reply(unit,False,error,caller=caller)
    if name in ('masc','scharge'):return booster_command(unit,name,caller=caller)
    if name in SIGNATURES:return signature_command(unit,name)
    if name=='dig':return dig(unit,caller=caller)
    if name=='fixturret':
        flags=getattr(unit,'tank_crit_status',0)
        if flags&1:return reply(unit,False,'Your turret is locked! You need a repairbay to fix it!',caller=caller)
        if not flags&2:return reply(unit,False,'Your turret is not jammed!',caller=caller)
        unit._engine.events.schedule(60,E.UNJAM_TURRET,unjam_turret_event,unit)
        return reply(unit,True,'You start to repair your jammed turret.')
    if name=='fliparms':
        if unit.is_fallen:return reply(unit,False,"You're using your arms to support yourself. Try flipping something else.",caller=caller)
        if not unit.specials & Specials.FLIPABLE_ARMS:return reply(unit,False,'You cannot flip the arms in this mech',caller=caller)
        result=reply(unit,True,f'Arms have been flipped to {"FORWARD" if unit.has_status(S.FLIPPED_ARMS) else "BACKWARD"} position')
        unit.status ^= S.FLIPPED_ARMS
        return result
    raise ValueError('unknown equipment command')


def explode_event(event):
    """The original byte encoding deliberately leaves command ammo untagged."""
    from systems.heat import find_destructive_ammo
    from systems.damage import reactor_explosion,destroy_section
    from systems.piloting import head_hit_mw_damage
    from entities.mech import UnitType
    unit,extra=event.data,event.data2
    if unit.is_destroyed or not unit.is_started:return 'cancelled'
    if extra>256 and find_destructive_ammo(unit) is None:return 'cancelled'
    extra-=1
    remainder=extra-(abs(extra)//256)*(1 if extra>=0 else -1)*256
    if remainder:
        notify(unit,f'Self-destruction in {remainder} second{"s" if extra>1 else ""}..')
        unit._engine.events.schedule(1,E.EXPLODE,explode_event,unit,extra)
        return f'countdown-{extra}'
    send_debug(unit,f'#{unit._id} explodes.')
    if unit.unit_type==UnitType.BSUIT:
        notify(unit,"Your batttle suit triggers it's self-destruction sequence.. you faint.. (and die)")
        los_broadcast(unit,'suddenly explodes!')
        head_hit_mw_damage(unit,unit,4)
        for loc in range(8):destroy_section(unit,unit,loc,unit._engine,los=-1)
        unit.z+=6
        return 'battlesuit'
    if unit.unit_type!=UnitType.MECH:
        notify(unit,'Your life flashes before your eyes as your vehicle immolates itself... you faint.. (and die)')
        los_broadcast(unit,'suddenly explodes!')
        destroy_section(unit,unit,3,unit._engine,los=-1)
        head_hit_mw_damage(unit,unit,4)
        unit.z+=6
        return 'vehicle'
    if extra>=256:
        from systems.criticals import ammo_explosion
        send_debug(unit,f'#{unit._id} explodes [ammo]')
        notify(unit,'All your ammo explodes!')
        while (ammo:=find_destructive_ammo(unit)) is not None:
            ammo_explosion(unit,ammo.location,ammo.ammo_count,ammo.weapon_damage,
                ammo.missiles_per_shot,ammo.is_inferno,ammo.is_gauss,attacker=unit,engine=unit._engine,slot=ammo.slot)
        return 'ammo-explosion'
    send_debug(unit,f'#{unit._id} explodes [reactor]')
    los_broadcast(unit,'suddenly explodes!')
    notify(unit,'Suddenly you feel great heat overcoming your senses.. you faint.. (and die)')
    reactor_explosion(unit,unit,unit._engine)
    return 'reactor'


def explode(unit,text,*,caller=None,wizard=False):
    from systems.physical import sect_has_busy_weap,sect_is_destroyed
    from systems.heat import find_destructive_ammo
    from entities.mech import UnitType
    error=command_guard(unit,caller=caller,wizard=wizard)
    if error:return reply(unit,False,error,caller=caller)
    override='override' in text and wizard
    args=parse_attributes(text,2)
    if not args:return reply(unit,False,'Invalid number of arguments!',caller=caller)
    actor=unit.pilot if caller is None else caller
    actor_id=getattr(actor,'dbref',getattr(actor,'_id',actor if isinstance(actor,int) else -1))
    # strtok terminates the first token but leaves skipped leading bytes in
    # buffer; C compares that original buffer, not the returned args[0].
    leading=text[:len(text)-len(text.lstrip(' \t'))]
    verb=(leading+args[0]).lower()
    if not override:
        for loc,section in enumerate(unit.sections):
            if not sect_is_destroyed(unit,loc) and sect_has_busy_weap(unit,loc):
                return reply(unit,False,'You have weapons recycling!',caller=caller)
            if section.recycle:return reply(unit,False,'You are still recovering from your last attack.',caller=caller)
    engine=unit._engine
    pending=engine.events.has_event_type_data(E.EXPLODE,unit)
    if verb=='stop':
        if not override and not getattr(engine,'explode_stop',0):return reply(unit,False,"It's too late to turn back now!",caller=caller)
        if not pending:return reply(unit,False,"Your mech isn't undergoing a self-destruct sequence!",caller=caller)
        engine.events.cancel_by_type_and_data(E.EXPLODE,unit)
        result=reply(unit,True,'Self-destruction sequence aborted.')
        send_debug(unit,f'#{actor_id} in #{unit._id} stopped the self-destruction sequence.')
        los_broadcast(unit,'regains control over itself.')
        return result
    if pending:return reply(unit,False,'Your mech is already undergoing a self-destruct sequence!',caller=caller)
    ammo=verb=='ammo'
    if not override:
        if not getattr(engine,'explode_ammo' if ammo else 'explode_reactor',1):return reply(unit,False,"You can't bring yourself to do it!",caller=caller)
        if ammo and unit.has_status(S.EXPLODE_SAFE):return reply(unit,False,"That's not a possibility here.",caller=caller)
        if not ammo and unit.unit_type!=UnitType.MECH:return reply(unit,False,"Only mechs can do the 'big boom' effect.",caller=caller)
        if not ammo and unit.specials & Specials.ICE_TECH:return reply(unit,False,'You need a fusion reactor.',caller=caller)
    if ammo and find_destructive_ammo(unit) is None:return reply(unit,False,"There is no 'damaging' ammo on your 'mech!",caller=caller)
    send_debug(unit,f'#{actor_id} in #{unit._id} initiates the {"ammo" if ammo else "reactor"} explosion sequence.')
    los_broadcast(unit,'starts billowing smoke!' if ammo else 'loses reactions containment!')
    delay=getattr(engine,'explode_time',120)
    if ammo:delay=int(delay/2)
    if override:delay=3
    engine.events.schedule(1,E.EXPLODE,explode_event,unit,delay)
    result=reply(unit,True,'Self-destruction sequence engaged ; please stand by.')
    notify(unit,f'{"The ammunition will explode" if ammo else "The reactor will blow up"} in {delay} seconds.')
    unit.pilot=None
    return result


BOOSTERS={
    'masc':('specials',Specials.MASC_TECH,S.MASC_ENABLED,E.MASC_FAIL,E.MASC_REGEN,'MASC'),
    'scharge':('specials2',0x40,S.SCHARGE_ENABLED,E.SCHARGE_FAIL,E.SCHARGE_REGEN,'Supercharger'),
}


def booster_command(unit,name,*,caller=None):
    from physics.cargo import cargo_max_speed
    attr,tech,bit,failure,regen,label=BOOSTERS[name]
    if not getattr(unit,attr)&tech:return reply(unit,False,"Your toy ain't prepared for what you're askin' it!",caller=caller)
    queue=unit._engine.events
    if unit.status&bit:
        result=reply(unit,True,f'{label} has been turned off.')
        unit.status &= ~bit
        unit.desired_speed *= 3/4
        queue.cancel_by_type_and_data(failure,unit)
        queue.schedule(60,regen,booster_regen,unit,name)
        return result
    if cargo_max_speed(unit)<10.75:
        return reply(unit,False,"You can't move. How is MASC going to work?" if name=='masc' else "How much can you Supercharge if you can't move?",caller=caller)
    result=reply(unit,True,f'{label} has been turned on.')
    unit.status |= bit
    queue.cancel_by_type_and_data(regen,unit)
    unit.desired_speed *= 4/3
    queue.schedule(1,failure,booster_event,unit,name)
    return result


def booster_regen(event):
    unit,name=event.data,event.data2
    attr=name+'_counter'
    value=getattr(unit,attr,0)
    if value>0:
        setattr(unit,attr,value-1)
        unit._engine.events.schedule(60,BOOSTERS[name][4],booster_regen,unit,name)


def booster_event(event):
    from systems.artillery import number
    from core.randomness import draw
    from systems.combat import roll_2d6
    from systems.criticals import _destroy_part
    from entities.mech import Location as L,UnitType,FireMode
    from entities.crittypes import i2special,Special
    unit,name=event.data,event.data2
    attr,tech,bit,failure,_,label=BOOSTERS[name]
    counter=getattr(unit,'masc_counter',0)
    unit.masc_counter=counter+1
    # BT_MOVEMENT_MODES uses MASCCounter for *both* systems. The MASC
    # surcharge test reads status2, while its roll penalty reads status.
    other=bool(unit.status2 & int(S.SCHARGE_ENABLED)) if name=='masc' else bool(unit.status&S.MASC_ENABLED)
    needed=2*(counter+1)+other+2*bool(unit.status2&S2.SPRINTING)
    rolled=source_roll('booster_rolls', roll_2d6)
    if not unit.is_started or not getattr(unit,attr)&tech:return
    if unit.status & (S.SCHARGE_ENABLED if name=='masc' else S.MASC_ENABLED):rolled-=1
    if needed<10 and getattr(unit.pilot,'wizard',False):rolled=number('booster_wizard',needed+1,12)
    notify(unit,f'{label}: BTH {needed+1}{"+" if name=="masc" else ""}, Roll: {rolled}')
    if rolled>needed:
        unit._engine.events.schedule(60,failure,booster_event,unit,name)
        return
    setattr(unit,attr,getattr(unit,attr)&~tech)
    unit.status &= ~bit
    if name=='masc':
        if abs(unit.speed)>10.75:
            from physics.jump import mech_falls
            notify(unit,'Your leg actuators freeze suddenly, and you fall!')
            los_broadcast(unit,'stops and falls in mid-step!')
            mech_falls(unit,1,notify_fall=False)
        else:
            notify(unit,'Your leg actuators freeze suddenly!')
            if unit.speed>0:los_broadcast(unit,'stops suddenly!')
        locations=[L.RLEG,L.LLEG]
        if unit.move_type==MoveType.QUAD:locations += [L.RARM,L.LARM]
        for loc in locations:_destroy_part(unit.sections[loc].criticals[0])
        for loc in (L.RLEG,L.LLEG):unit.sections[loc].basetohit+=2
        unit.crit_status |= CritStatus.HIP_DAMAGED|CritStatus.HIP_DESTROYED
        from systems.vehicle_combat import set_max_speed
        set_max_speed(unit,0)
        return
    notify(unit,'Your supercharger overloads and explodes!')
    if unit.unit_type==UnitType.MECH:
        slots=unit.sections[L.CTORSO].criticals
        for slot in slots:
            if slot.type==i2special(Special.SUPERCHARGER) and not slot.firemode & FireMode.DESTROYED_MODE:_destroy_part(slot)
        count=number('supercharger_crits',1,4)
        for slot in slots:
            if count and slot.type==i2special(Special.ENGINE) and not slot.firemode & FireMode.DESTROYED_MODE:
                _destroy_part(slot)
                if not unit.is_destroyed and unit.is_started:los_broadcast(unit,"'s center torso spews black smoke!")
                if unit.engine_heat<10:
                    unit.engine_heat+=5
                    notify(unit,"Your engine shielding takes a hit!  It's getting hotter in here!!")
                elif unit.engine_heat<15:
                    from systems.damage import destroy_mech,KILL_TYPE_SCHARGE
                    unit.engine_heat=15
                    notify(unit,'Your engine is destroyed!!')
                    destroy_mech(unit,unit,showboom=True,reason=KILL_TYPE_SCHARGE)
                count-=1
    elif unit.unit_type in (UnitType.VTOL,UnitType.VEH_GROUND):
        los_broadcast(unit,' coughs thick black smoke from its exhaust.')
        from systems.vehicle_combat import set_max_speed
        set_max_speed(unit,int(int(unit.max_speed)*.5))


def unjam_ammo(unit,text,*,caller=None,wizard=False):
    from systems.tic import multi_weap_sel
    from systems.weapon_modes import find_weapon_number_on_mech
    from systems.enhanced_crits import part_temp_nuke,FAIL_AMMOJAMMED
    from systems.physical import sect_has_busy_weap
    from physics.cargo import cargo_max_speed
    error=command_guard(unit,map_required=False,caller=caller,wizard=wizard)
    if error:return reply(unit,False,error,caller=caller)
    args=parse_attributes(text,1)
    if not args:return reply(unit,False,'Please specify a weapon number.',caller=caller)
    messages=CommandMessages(unit=unit,caller=caller)
    started=False
    def selected(mech,index,high):
        nonlocal started
        code,loc,pos=find_weapon_number_on_mech(mech,index)
        if code==-1:messages.append("The weapons system chirps: 'Illegal Weapon Number!'");return 0
        if code==-2:messages.append("The weapons system chirps: 'That Weapon has been destroyed!'");return 0
        if part_temp_nuke(mech.sections[loc].criticals[pos])!=FAIL_AMMOJAMMED:
            messages.append('The ammo feed mechanism for that weapon is not jammed.');return 0
        if mech.is_jumping:messages.append("You can't unjam the ammo feed while jumping!");return 0
        if mech.desired_speed>cargo_max_speed(mech)*2/3+0.1:
            messages.append("You can't unjam the ammo feed while running!");return 0
        from systems.parts import armor_string
        for location in range(len(mech.sections)):
            if sect_has_busy_weap(mech,location):
                messages.unit(f'You have weapons recycling on your {armor_string(mech,location)}.');return 0
        if mech._engine.events.has_event_type_data(E.UNJAM_AMMO,mech):
            messages.append('You are already unjamming a weapon!');return 0
        mech._engine.events.schedule(60,E.UNJAM_AMMO,unjam_ammo_event,mech,index)
        mech.unjamming=True
        messages.unit(f'You begin to shake the jammed ammo loose on weapon #{index}')
        started=True
        return 0
    accepted=multi_weap_sel(unit,args[0],1,selected,messages)
    return dict(accepted=accepted,started=started,text='\n'.join(messages))


def unjam_ammo_event(event):
    from systems.weapon_modes import find_weapon_number_on_mech
    from systems.enhanced_crits import set_part_temp_nuke
    from systems import combat_ammunition as ammo
    from systems.piloting import find_pilot_gunnery,make_piloting_roll
    from systems.combat import roll_2d6
    from core.randomness import draw
    from entities.weapon import get_weapon_by_index,WeaponFlags
    unit,index=event.data,event.data2
    unit.unjamming=False
    if unit.is_unconscious or not unit.is_started:return
    code,loc,pos=find_weapon_number_on_mech(unit,index)
    if code in (-1,-2):return
    from systems.weapon_inventory import sync_weapon_states
    ws=sync_weapon_states(unit)[index]
    slot=unit.sections[loc].criticals[pos]
    plan=ammo.find_and_check(unit,ws)
    weapon=get_weapon_by_index(ws.weapon_idx)
    from data.construction_catalog import source_id
    from entities.crittypes import i2weapon
    from systems.status_display import catalog
    from systems.notifications import mech_printf, MECHALL
    name = catalog().names(source_id(i2weapon(ws.weapon_idx)), 0)[1]
    if not plan.accepted:
        set_part_temp_nuke(slot,0)
        mech_printf(unit, MECHALL, 'You finish bouncing around and realize you no longer have ammo for your %s!', name)
        return
    if weapon.special&WeaponFlags.RAC:
        rolled=source_roll('unjam_rolls', roll_2d6)
        needed=find_pilot_gunnery(unit,weapon)+3
        command_message(unit,'You make a roll to unjam the weapon!',audience=0)
        command_message(unit,f'Modified Gunnery Skill: BTH {needed}\tRoll: {rolled}',audience=0)
        success=rolled>=needed
    else:success=make_piloting_roll(unit,0).success
    if not success:
        notify(unit,"Your attempt to remove the jammed slug fails. You'll need to try again to clear it.")
        return
    from entities.source_weapon_numbers import source_weapon
    source_weapon(index)  # Reject unavailable source metadata before changing the jam.
    set_part_temp_nuke(slot,0)
    mech_printf(unit, MECHALL, 'You manage to clear the jam on your %s!', name)
    los_broadcast(unit,'ejects a mangled shell!')
    ammo.decrement(unit,index,ws,plan,source_number=True)


def arm_bth_modifier(unit,arm):
    from systems.physical import okay_crit_sect
    from entities.crittypes import Special
    return sum(penalty for slot,kind,penalty in ((1,Special.UPPER_ACTUATOR,2),
        (2,Special.LOWER_ACTUATOR,2),(3,Special.HAND_OR_FOOT_ACTUATOR,1))
        if not okay_crit_sect(unit,arm,slot,kind))


def show_pods(unit,**actor):
    from systems.missile import check_all_sections
    from systems.damage import section_destroyed
    from systems.parts import armor_string, check_section_for_special
    caller=actor.get('caller')
    error=command_guard(unit,**actor)
    if error:return reply(unit,False,error,caller=caller)
    if not check_all_sections(unit,0x1f):return reply(unit,True,'There are no NARC or iNARC pods attached to this unit.',caller=caller,audience=None)
    rows=[]
    messages=CommandMessages(unit=unit,caller=caller)
    messages.append('=========================Attached NARC and iNARC Pods========================')
    messages.append('-- Location ---||- NARC -||- iHoming -||- iHaywire -||- iECM -||- iNemesis --')
    for loc,section in enumerate(unit.sections):
        if section.internal_orig>0:
            name=armor_string(unit,loc)
            destroyed=section_destroyed(unit,loc)
            bits=[bool(check_section_for_special(unit,bit,loc)) for bit in (1,2,4,8,16)]
            rows.append(dict(location=loc,name=name,destroyed=destroyed,**dict(zip(('narc','homing','haywire','ecm','nemesis'),bits))))
            if destroyed:messages.append(f' {name[:13]:<14}||********||***********||************||********||************* ')
            else:
                narc,homing,haywire,ecm_bit,nemesis=('X' if bit else '.' for bit in bits)
                messages.append(f' {name[:13]:<14}||....{narc}...||.....{homing}.....||......{haywire}.....||....{ecm_bit}...||......{nemesis}...... ')
    return dict(accepted=True,text='\n'.join(messages),pods=rows)


def remove_pods_mech(unit,text,**actor):
    from entities.mech import Location as L
    from entities.crittypes import Special
    from systems.damage_commands import armor_section_from_string
    from systems.physical import sect_has_busy_weap,okay_crit_sect,set_recycle_limb,PHYSICAL_RECYCLE_TIME
    from systems.piloting import find_pilot_piloting
    from systems.combat import roll_2d6,apply_damage_with_transfer
    from systems.parts import armor_string as _aim_section_name
    from core.randomness import draw
    caller=actor.get('caller')
    error=command_guard(unit,**actor)
    if error:return reply(unit,False,error,caller=caller)
    if unit.move_type==MoveType.QUAD:return reply(unit,False,'Quads can not knock of iNARC pods!',caller=caller)
    args=parse_attributes(text,2)
    if len(args)!=2:return reply(unit,False,'Invalid number of arguments!',caller=caller)
    loc=armor_section_from_string(unit,args[0])
    if loc<0 or not unit.sections[loc].internal_orig:return reply(unit,False,'Invalid section!',caller=caller)
    if not unit.sections[loc].internal:return reply(unit,False,'That section is destroyed!',caller=caller)
    bit,label={'Y':(4,'Haywire'),'E':(8,'ECM')}.get(args[1][0].upper(),(2,'Homing'))
    if not unit.sections[loc].specials&bit:return reply(unit,False,f'There are no iNarc {label} pods attached to your {_aim_section_name(unit,loc)}!',caller=caller)
    if not unit.sections[L.LARM].internal and not unit.sections[L.RARM].internal:
        return reply(unit,False,'You need at least one functioning arm to remove iNarc pods!',caller=caller)
    if loc in (L.LARM,L.RARM):
        arm=L.RARM if loc==L.LARM else L.LARM
        name=_aim_section_name(unit,arm)
        target_name='Left Arm' if loc==L.LARM else 'right arm'
        if not unit.sections[arm].internal:return reply(unit,False,f'Your {name} needs to be intact to take iNarc pods off your {target_name}!',caller=caller)
        if sect_has_busy_weap(unit,arm):return reply(unit,False,f'You have weapons recycling on your {name}.',caller=caller)
        if unit.sections[arm].recycle:return reply(unit,False,f'Your {name} is still recovering from your last attack.',caller=caller)
    else:
        candidates=[arm for arm in (L.LARM,L.RARM) if unit.sections[arm].internal and
                    not unit.sections[arm].recycle and not sect_has_busy_weap(unit,arm)]
        if not candidates:return reply(unit,False,'You need at least one arm that is not recycling and does not have weapons recycling in it!',caller=caller)
        arm=min(candidates,key=lambda a:arm_bth_modifier(unit,a))
    bth=arm_bth_modifier(unit,arm)+find_pilot_piloting(unit)+4
    roll=source_roll('pod_rolls', roll_2d6)
    notify(unit,f'You try to swat at the iNarc pods attached to your {_aim_section_name(unit,loc)} with your {_aim_section_name(unit,arm)}.  BTH:  {bth},\tRoll:  {roll}')
    damage=0
    if roll<bth:
        notify(unit,'Uh oh. You miss the pod and hit yourself!')
        los_broadcast(unit,'tries to swat off an iNarc pod, but misses and hits itself!')
        damage=int((unit.tonnage+5)/10)
        for slot,kind in ((2,Special.LOWER_ACTUATOR),(1,Special.UPPER_ACTUATOR)):
            if not okay_crit_sect(unit,arm,slot,kind):damage=int(damage/2)
        apply_damage_with_transfer(unit,loc,damage,attacker=unit,los=1,attack_pilot=unit.pilot if unit.pilot is not None else -1)
    else:
        unit.sections[loc].specials&=~bit
        notify(unit,f'You knock a {label} pod off your {_aim_section_name(unit,loc)}!')
        los_broadcast(unit,'knocks an iNarc pod off itself.')
    set_recycle_limb(unit,arm,PHYSICAL_RECYCLE_TIME)
    return dict(accepted=True,arm=int(arm),bth=bth,roll=roll,self_damage=damage,removed=roll>=bth)


def remove_pods_event(event):
    unit=event.data
    if unit.is_destroyed:return
    notify(unit,'You remove all the iNARC pods from your unit.')
    los_broadcast(unit,"'s crew climbs out and knocks off all the attached iNarc pods!")
    for section in unit.sections:
        if section.internal_orig:section.specials&=~0x1e


def remove_pods_tank(unit,**actor):
    from entities.mech import UnitType as U
    from systems.missile import check_all_sections
    caller=actor.get('caller')
    error=command_guard(unit,started=False,**actor)
    if error:return reply(unit,False,error,caller=caller)
    if unit.desired_speed>0 or unit.speed>0:return reply(unit,False,'You can not be moving when attempting to remove iNarc pods!',caller=caller)
    if unit.unit_type==U.VTOL and not unit.status&S.LANDED:return reply(unit,False,'You must land before attempting to remove iNarc pods!',caller=caller)
    queue=unit._engine.events
    if queue.has_event_type_data(E.UNSTUN_CREW,unit):return reply(unit,False,"You're too stunned to remove iNarc pods!",caller=caller)
    for kind,label in ((E.UNJAM_TURRET,'your turret'),(E.UNJAM_AMMO,'a weapon')):
        if queue.has_event_type_data(kind,unit):return reply(unit,False,f"You're too busy unjamming {label} to remove iNarc pods!",caller=caller)
    if not check_all_sections(unit,0x1e):return reply(unit,False,'There are no iNarc pods attached to this unit.',audience=2)
    result=reply(unit,True,'You begin to systematically remove all the iNarc pods from your unit.')
    queue.schedule(60,E.REMOVE_PODS,remove_pods_event,unit)
    return result
