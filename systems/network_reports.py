# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.c3.misc.c
#   btech/mech.notify.c
#   btech/mech.utils.c

"""Source C3 reports and communications presentation helpers."""
from entities.mech import AmmoMode as A, FireMode as F, MechStatus as S, MechStatus2 as S2, CritStatus as C, MoveType as M, UnitType as U, Location as L
from systems.observation import weapon_arc, status_chars
from systems.notifications import MBUF_SIZE
from physics.hexmath import virtual_facing

AMMO_DESCRIPTIONS = (
    ('LBX','Shotgun'), ('ARTEMIS','Artemis IV'), ('NARC','Narc'),
    ('INARC_EXPLO','iExplosive'), ('INARC_HAYWIRE','Haywire'), ('INARC_ECM','ECM'),
    ('INARC_NEMESIS','Nemesis'), ('SWARM','Swarm'), ('SWARM1','Swarm1'),
    ('INFERNO','Inferno'), ('CLUSTER','Cluster'), ('SMOKE','Smoke'), ('MINE','Mine'),
    ('AC_AP','Armor Piercing'), ('AC_FLECHETTE','Flechette'), ('AC_INCENDIARY','Incendiary'),
    ('AC_PRECISION','Precision'), ('STINGER','Stinger'), ('AC_CASELESS','Caseless'),
    ('SGUIDED','Sguided'), ('ATM_ER','ExtendedRange'), ('ATM_HE','HighExplosive'), ('MML_LRM','LRM'))
AMMO_LETTERS = tuple(zip(
    ('CLUSTER','SMOKE','MINE','LBX','ARTEMIS','NARC','INARC_EXPLO','INARC_HAYWIRE','INARC_ECM','INARC_NEMESIS','INFERNO','SWARM','SWARM1','AC_AP','AC_FLECHETTE','AC_INCENDIARY','AC_PRECISION','STINGER','AC_CASELESS','SGUIDED','ATM_ER','ATM_HE','MML_LRM'),
    'CSMLANXYEZIW1RF DPTUGRX#'.replace(' ', '')))


def ammo_description(weapon, mode):
    from entities.weapon import WeaponFlags
    for name, description in AMMO_DESCRIPTIONS:
        if mode & getattr(A, name + '_MODE'):
            if name == 'NARC' and weapon.special & WeaponFlags.NARC:
                description = 'Explosive'
            return ' ' + description
    return ''


def ammo_letter(weapon, mode):
    from entities.weapon import WeaponFlags
    if not mode & A.AMMO_MODES:
        return ' '
    for name, letter in AMMO_LETTERS:
        if mode & getattr(A, name + '_MODE'):
            return 'E' if name == 'NARC' and weapon.special & WeaponFlags.NARC else letter
    return ' '


def fire_letter(mode):
    if not mode & F.FIRE_MODES:
        return ' '
    for name, letter in (('HOTLOAD','H'),('ULTRA','U'),('RFAC','F'),('GATTLING','G'),('HEAT','H'),('RAC_TWOSHOT','2'),('RAC_FOURSHOT','4'),('RAC_SIXSHOT','6')):
        if mode & getattr(F, name + '_MODE'):
            return letter
    return ' '


def slot_ammo_letter(unit, section, slot):
    from entities.weapon import get_weapon_by_index
    critical = unit.sections[section].criticals[slot]
    weapon = get_weapon_by_index(critical.type - 1)
    if weapon is None:
        raise ValueError('Source ammo-mode wrapper requires a weapon slot')
    return ammo_letter(weapon, critical.ammomode)


def slot_fire_letter(unit, section, slot):
    return fire_letter(unit.sections[section].criticals[slot].firemode)


def move_type(move):
    return {M.QUAD:'QUAD',M.BIPED:'BIPED',M.TRACK:'TRACKED',M.WHEEL:'WHEELED',
            M.HOVER:'HOVER',M.VTOL:'VTOL',M.FLY:'FLY',M.HULL:'HULL',M.SUB:'SUBMARINE',M.FOIL:'HYDROFOIL'}.get(move,'Unknown')


def arc_label(unit, arc):
    from physics.hexmath import FORWARDARC,RSIDEARC,LSIDEARC,REARARC
    side = 'Arm' if unit.unit_type in (U.MECH,U.MW,U.BSUIT) else 'Side'
    return next((name for flag,name in ((FORWARDARC,'Forward'),(RSIDEARC,'Right '+side),(LSIDEARC,'Left '+side),(REARARC,'Rear')) if arc & flag),'NO')


def event(unit, name):
    from core.events import EventType
    engine = getattr(unit, '_engine', None)
    return engine is not None and engine.has_event(getattr(EventType,name), unit)


def status_char(viewer, target, column):
    return status_chars(viewer, target)[column - 1] if 1 <= column <= 5 else ' '


def show_flags(unit, spaces=0, level=0):
    from systems import ecm, swarm
    from systems.targeting import resolve_unit
    if not 0 <= spaces < MBUF_SIZE:
        raise ValueError('Indent exceeds source message buffer')
    rows = []
    def emit(condition, text):
        if condition:
            if spaces + len(text) >= MBUF_SIZE:
                raise ValueError('Flag text exceeds source message buffer')
            rows.append(' ' * spaces + text)
    emit(unit.status & S.COMBAT_SAFE, '%cb%chCOMBAT SAFE%cn')
    emit(unit.status2 & S2.FORTIFIED, '%ch%cgFORTIFIED%cn')
    emit(unit.status2 & S2.WEAPONS_HOLD, '%ch%crWEAPONS HOLD%cn')
    fallen = {M.BIPED:'FALLEN',M.QUAD:'FALLEN',M.TRACK:'TRACK DESTROYED',M.WHEEL:'AXLE DESTROYED',M.HOVER:'LIFT FAN DESTROYED',M.VTOL:'ROTOR DESTROYED',M.FLY:'ENGINE DESTROYED',M.HULL:'ENGINE ROOM DESTROYED',M.SUB:'ENGINE ROOM DESTROYED',M.FOIL:'FOIL DESTROYED'}
    if unit.is_fallen:
        # Source leaves the previous buffer unchanged for MOVE_NONE.
        emit(True, '%cr%ch' + fallen[unit.move_type] + '%cn' if unit.move_type in fallen else (rows[-1][spaces:] if rows else ''))
    emit(unit.status & S.HULLDOWN, '%cg%chHULLDOWN%cn')
    emit(getattr(unit,'tank_crit_status',0) & 4, '%cg%chDUG IN%cn')
    emit(getattr(unit,'tank_crit_status',0) & 8, '%cgDIGGING IN%cn')
    emit(unit.stagger_damage // 20 > 0, '%cr%chSTAGGERING%cn')
    emit(unit.crit_status & C.SLITE_DEST, '%cr%chSEARCHLIGHT DESTROYED%cn')
    if unit.status2 & S2.SLITE_ON:
        emit(True, '%cg%chSEARCHLIGHT ON%cn')
    else:
        emit(unit.crit_status & C.SLITE_LIT, '%cg%chILLUMINATED%cn')
    emit(event(unit,'VEHICLE_BURN') or unit.crit_status & C.JELLIED, '%cr%chON FIRE%cn')
    emit(unit.crit_status & C.HIDDEN, '%ch%cgHIDDEN%c')
    emit(swarm.is_swarmed(unit), '%cr%chSWARMED BY ENEMY SUITS%cn')
    emit(swarm.is_mounted(unit), '%cr%chMOUNTED BY FRIENDLY SUITS%cn')
    ident = getattr(unit.swarm_target, '_id', unit.swarm_target) or -1
    host = resolve_unit(unit, ident) if ident > 0 else None
    if host is not None:
        emit(True, '%cg%chMOUNTED ON FRIENDLY UNIT%cn' if host.team == unit.team else '%cg%chSWARMING ENEMY UNIT%cn')
    for flag,name in ((S2.DODGING,'DODGING'),(S2.EVADING,'EVADING'),(S2.SPRINTING,'SPRINTING')):
        emit(unit.status2 & flag, '%ch%cr' + name + '%c')
    emit(event(unit,'MOVEMODE'), '%ch%cyCHANGING MOVEMENT MODE%c')
    emit(event(unit,'SIDESLIP'), '%ch%cySIDESLIPPING%c')
    emit(getattr(unit,'tank_crit_status',0) & 16 or unit.crit_status & C.MECH_STUNNED, '%ch%crSTUNNED%c')
    if level == 0:
        for condition,text in (
            (ecm.ecm_protected(unit),'%cg%chPROTECTED BY ECM%cn'),
            (ecm.angel_ecm_protected(unit),'%cg%chPROTECTED BY ANGEL ECM%cn'),
            (ecm.ecm_disturbed(unit),'%cy%chAFFECTED BY ECM%cn'),
            (ecm.angel_ecm_disturbed(unit),'%cy%chAFFECTED BY ANGEL ECM%cn'),
            (ecm.ecm_countered(unit),'%cy%chCOUNTERED BY ECCM%cn'),
            (unit.status2 & S2.STH_ARMOR_ON,'%cg%chSTEALTH ARMOR ACTIVE%cn'),
            (unit.status2 & S2.NULLSIGSYS_ON,'%cg%chNULL SIGNATURE SYSTEM ACTIVE%cn')):
            emit(condition,text)
        for flag,name in ((1,'NARC'),(2,'INARC HOMING'),(4,'INARC HAYWIRE'),(8,'INARC ECM')):
            emit(ecm.check_all_sections(unit,flag),'%cy%ch' + name + ' POD ATTACHED%cn')
        emit(event(unit,'VEHICLE_EXTINGUISH'),'%cy%chEXTINGUISHING FIRE%cn')
        emit(unit.status2 & S2.AUTOTURN_TURRET,'%cg%chTURRET AUTO-TURN ENGAGED%cn')
        emit(unit.sections[L.RARM].specials & 32,'%cg%chCARRYING CLUB - RIGHT ARM%cn')
        emit(unit.sections[L.LARM].specials & 32,'%cg%chCARRYING CLUB - LEFT ARM%cn')
    if level <= 1:
        emit(unit.is_destroyed,'DESTROYED')
        emit(not unit.is_started,'SHUTDOWN')
    if level <= 0:
        emit(unit.status & S.TORSO_RIGHT,'Torso is 60 degrees right')
        emit(unit.status & S.TORSO_LEFT,'Torso is 60 degrees left')
    return rows


def remaining_percent(unit, armor=True):
    from core.randomness import float32
    keys = ('armor','rear') if armor else ('internal',)
    current = original = 0.0
    for section in unit.sections:
        for key in keys:
            current = float32(current + getattr(section,key,0))
            original = float32(original + getattr(section,key + '_orig',0))
    return int(float32(float32(current / original) * 100)) if original else 0


def network_data(unit, ordinary=True):
    from systems.c3 import temporary
    from systems.targeting import resolve_unit, fa_mech_range
    from physics.hexmath import find_bearing
    kind = 'C3' if ordinary else 'C3i'
    rows = [kind + ' Network Status:']
    for ident in temporary(unit, ordinary):
        peer = resolve_unit(unit, ident)
        bearing = int(find_bearing(unit.fx,unit.fy,peer.fx,peer.fy))
        rows.append((f'%ch%cy[{peer.contact_id.lower()}]{move_type(peer.move_type)[0]} {peer.name[:12]:<12} '
                     f'x:{peer.x:3d} y:{peer.y:3d} z:{peer.z:3d} r:{fa_mech_range(unit,peer):4.1f} '
                     f'b:{bearing:3d} s:{peer.speed:5.1f} h:{virtual_facing(peer):3d} a: {remaining_percent(peer):3d} i: {remaining_percent(peer,False):3d}%cn')[:99])
    return rows + ['End ' + kind + ' Network Status']


def targets(unit, ordinary=True):
    from systems.c3 import temporary, seen_by_network, range_with_network
    from systems.targeting import fa_mech_range
    from systems.los import in_line_of_sight, in_line_of_sight_nb, MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS
    from physics.hexmath import find_bearing, in_weapon_arc
    kind = 'C3' if ordinary else 'C3i'
    peers = temporary(unit, ordinary)
    rows, distances = [], []
    network_seen = 0
    for target in unit.map.mechs_on_map:
        if target is None or target is unit:
            continue
        distance = fa_mech_range(unit,target)
        visible = in_line_of_sight(unit,target,target.x,target.y,distance)
        identified = bool(in_line_of_sight_nb(unit,target,target.x,target.y,0))
        own_seen = (1 if identified else 2) if visible else 0
        if own_seen != 1:
            network_seen = seen_by_network(unit,target,ordinary)
        if not own_seen and not network_seen:
            continue
        show = own_seen == 1 or network_seen == 1
        shared, _ = range_with_network(unit,target,distance,peers)
        friend = unit.team == target.team and identified
        selected = target._id == unit.target
        prefix = '%ch%cr' if selected else '%ch%cy' if show and not friend else ''
        suffix = '%c' if selected or not friend else ''
        contact = target.contact_id.lower() if friend or not show else target.contact_id
        name = target.name if show else 'something'
        statuses = status_chars(unit,target) if show else ' ' * 5
        bearing = int(find_bearing(unit.fx,unit.fy,target.fx,target.fy))
        flags = ('P' if visible & MECHLOSFLAG_SEESP else ' ') + ('S' if visible & MECHLOSFLAG_SEESS else ' ')
        arc = weapon_arc(in_weapon_arc(unit,target.fx,target.fy))
        rows.append((f'{prefix}{flags}{arc}[{contact}]{move_type(target.move_type)[0]} {name[:11]:<11} '
                     f'x:{target.x:3d} y:{target.y:3d} z:{target.z:3d} r:{distance:4.1f} c:{shared:4.1f} '
                     f'b:{bearing:3d} s:{target.speed:5.1f} h:{virtual_facing(target):3d} S:{statuses}{suffix}')[:99])
        distances.append(distance + (10000 if target.is_destroyed else 0))
    indexes = list(range(len(rows)))
    for i in range(len(rows)-1):
        for j in range(i+1,len(rows)):
            if distances[indexes[j]] > distances[indexes[i]]:
                indexes[i],indexes[j] = indexes[j],indexes[i]
    return [kind + ' Contacts:'] + [rows[i] for i in indexes] + ['End ' + kind + ' Contact List']
