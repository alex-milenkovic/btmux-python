# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.advanced.c

"""Combat preferences and equipment switches from mech.advanced.c."""
from entities.mech import UnitType,MechStatus2 as S2,VehicleLocation as V
from entities.weapon import WeaponFlags,get_weapon_by_index
from systems.combat_commands import command_guard
from systems.movement_commands import notify

# bit, inverted presentation, negative presentation, live compatibility field
PREFERENCES={
    'MWSafety':(1,True,False,None),
    'SLWarn':(2,False,False,'sl_warn'),
    'AutoFall':(4,False,True,None),
    'ArmorWarn':(8,True,False,'armor_warnings'),
    'AmmoWarn':(16,True,False,'ammo_warnings'),
    'AutoconShutdown':(64,False,True,'autocon_shutdown'),
    'FFSafety':(128,False,False,None),
    'BTHDebug':(512,False,True,None),
}


PREFERENCE_MESSAGES = {
    'MWSafety':'MechWarrior Safeties flipped',
    'SLWarn':'The warning when lit by searchlight is now',
    'AutoFall':'Suicidal jumps off cliffs toggled',
    'ArmorWarn':'Low-armor warnings turned',
    'AmmoWarn':'Warning when running out of Ammunition switched',
    'AutoconShutdown':'Autocon on shutdown units turned',
    'FFSafety':'Friendly Fire Safeties flipped',
    'BTHDebug':'BTH Debugging is now',
}


def result(unit,accepted,text,*,caller=None,audience=2,**values):
    from systems.combat_commands import command_message
    command_message(unit,text,caller=caller,audience=audience)
    return dict(accepted=accepted,text=text,**values)


def preference(unit,name,*,owner=None):
    if unit is None:
        from core.effects import send_error
        if owner is not None:
            send_error(owner,'Invalid target_mech in display_mechpref!')
        else:
            import logging
            logging.getLogger('MechErrors').error('Invalid target_mech in display_mechpref!')
        return dict(name=name,bit=0,state=None,text='Unknown error; contact a Wizard.')
    bit,inverted,negative,field=PREFERENCES[name]
    raw=bool(unit.prefs & bit)
    enabled=raw != inverted
    state='ON' if enabled else 'OFF'
    color='%cr' if enabled==negative else '%cg'
    return dict(name=name,bit=int(raw),state=state,text=f'        {name:<40}%ch{color}{state}%cn')


def sync_preference(unit,name):
    bit,inverted,negative,field=PREFERENCES[name]
    if field:
        setattr(unit,field,bool(unit.prefs & bit)!=inverted)


def mechprefs(unit,text,**actor):
    from systems.combat_commands import parse_attributes
    caller=actor.get('caller')
    def reply(ok,text,**values):
        return result(unit,ok,text,caller=caller,audience=None,**values)
    error=command_guard(unit,started=False,map_required=False,**actor)
    if error:return reply(False,error)
    args=parse_attributes(text,2)
    if not args:
        from systems.status_display import menu_lines
        from systems.combat_commands import command_message
        rows=[preference(unit,name) for name in PREFERENCES]
        lines=menu_lines('Mech Preferences',[row['text'] for row in rows])
        for line in lines:command_message(unit,line,caller=caller)
        return dict(accepted=True,text='\n'.join(lines),preferences=rows)
    name=next((n for n in PREFERENCES if n.lower()==args[0].lower()),None)
    if name is None:return reply(False,'Unknown MechPreference: '+args[0])
    bit,inverted,negative,field=PREFERENCES[name]
    if len(args)>1:
        if args[1].upper() not in ('ON','OFF'):
            return reply(False,'Only accept ON or OFF as valid extra parameter for mechprefs pref')
        enabled=(args[1].upper()=='ON') != inverted
        unit.prefs=unit.prefs | bit if enabled else unit.prefs & ~bit
    else:
        unit.prefs ^= bit
    sync_preference(unit,name)
    row=preference(unit,name)
    state=row['text'][48:]
    return reply(True,PREFERENCE_MESSAGES[name]+' '+state,preference=row)


def safety(unit,text,*,caller=None,wizard=False):
    if unit.unit_type==UnitType.MW:
        return result(unit,False,'Your weapons dont have safeties.',caller=caller,audience=None)
    if text.lower()=='on':unit.prefs &= ~1
    elif text.lower()=='off':unit.prefs |= 1
    row=preference(unit,'MWSafety')
    state='%ch'+('%crOFF' if unit.prefs & 1 else '%cgON')+'%cn'
    changed=text.lower() in ('on','off')
    return result(unit,True,('Safeties flipped '+state+'.') if changed else 'Weapon safeties are '+state,
                  audience=2 if changed else 0,preference=row)


def auto_turret(unit,**actor):
    caller=actor.get('caller')
    error=command_guard(unit,started=False,**actor)
    if error:return result(unit,False,error,caller=caller,audience=None)
    if not unit.sections[V.TURRET].internal:
        return result(unit,False,'You have no turret to autoturn!',caller=caller,audience=None)
    answer=result(unit,True,'Automatic turret turning is now '+('OFF' if unit.status2 & S2.AUTOTURN_TURRET else 'ON'))
    unit.status2 ^= S2.AUTOTURN_TURRET
    return answer


def disable_weapon(unit,text,**actor):
    from systems.tic import multi_weap_sel
    from systems.enhanced_crits import set_part_temp_nuke,FAIL_DESTROYED
    from systems.weapon_modes import find_weapon_number_on_mech
    from systems.combat_commands import CommandMessages,parse_attributes
    from entities.crittypes import weapon2i
    messages=CommandMessages(unit=unit,caller=actor.get('caller'))
    error=command_guard(unit,**actor)
    if error:
        messages.append(error)
        return dict(accepted=False,text=str(error),weapons=[])
    args=parse_attributes(text,1)
    if not args:
        messages.append('Please specify a weapon number.')
        return dict(accepted=False,text=messages[0],weapons=[])
    changed=[]
    def disable(mech,index,high):
        code,section,critical=find_weapon_number_on_mech(mech,index,sight=True)
        if code==-1:
            messages.append("The weapons system chirps: 'Illegal Weapon Number!'")
            return 0
        if code==-2:
            messages.append("The weapons system chirps: 'That Weapon has been destroyed!'")
            return 0
        slot=mech.sections[section].criticals[critical]
        if not get_weapon_by_index(weapon2i(slot.type)).special & WeaponFlags.GAUSS:
            messages.append('You can only disable Gauss weapons.')
        elif slot.data>0:
            messages.append("The weapon system chirps: 'That weapon is still recharging!'")
        else:
            set_part_temp_nuke(slot,FAIL_DESTROYED)
            messages.unit(f'You power down weapon {index}.')
            changed.append(index)
        return 0
    accepted=multi_weap_sel(unit,args[0],1,disable,messages)
    return dict(accepted=accepted,text='\n'.join(messages),weapons=changed)
