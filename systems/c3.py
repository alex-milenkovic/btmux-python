# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.c3.c
#   btech/mech.c3.misc.c
#   btech/mech.c3i.c

"""C3/C3i membership, replication and source-ordered temporary networks."""
from entities.mech import Specials, CritStatus, UnitType
from systems.targeting import resolve_unit
from systems.ecm import any_ecm_disturbed


def network_name(ordinary):
    return 'c3_network' if ordinary else 'c3i_network'


def network_size(unit, ordinary=True):
    name = network_name(ordinary)
    return getattr(unit, name + '_size', len(getattr(unit, name, [])))


def slots(unit, ordinary=True):
    limit = 11 if ordinary else 5
    values = list(getattr(unit, network_name(ordinary), []))
    if len(values) > limit or network_size(unit, ordinary) > limit:
        raise ValueError('Network exceeds allocated source slots')
    return [getattr(value, '_id', value) for value in values] + [-1] * (limit - len(values))


def write(unit, values, ordinary=True):
    setattr(unit, network_name(ordinary), list(values))
    setattr(unit, network_name(ordinary) + '_size', len(values))


def has_technology(unit, ordinary=True):
    return bool(unit.specials & (Specials.C3_MASTER_TECH | Specials.C3_SLAVE_TECH)
                if ordinary else unit.specials2 & 0x20)


def disabled(unit, ordinary=True):
    return bool(unit.crit_status & (CritStatus.C3_DESTROYED if ordinary else CritStatus.C3I_DESTROYED))


def other(unit, index, ordinary=True, ecm=False, started=False, unconscious=False):
    if index < 0 or index >= network_size(unit, ordinary):
        return None
    ident = slots(unit, ordinary)[index]
    if ident <= 0:
        return None
    peer = resolve_unit(unit, ident)
    if (peer is None or peer.team != unit.team or peer.mapindex != unit.mapindex
            or peer.is_destroyed or not has_technology(peer, ordinary) or disabled(peer, ordinary)):
        return None
    if ecm and any_ecm_disturbed(peer) or started and not peer.is_started or unconscious and peer.is_unconscious:
        return None
    return peer


def temp_member(unit, values, size, index):
    # The C temporary helper accepts index==size, where generated arrays pad -1.
    if index < 0 or index > size:
        return None
    if index >= len(values):
        raise ValueError('Temporary network index exceeds allocated source array')
    ident = getattr(values[index], '_id', values[index])
    peer = resolve_unit(unit, ident) if ident > 0 else None
    return peer if peer is not None and not peer.is_destroyed else None


def masters(unit):
    from systems.criticals import count_working_c3_masters
    value = getattr(unit, 'working_c3_masters', None)
    return count_working_c3_masters(unit) if value is None else value


def maximum(unit, values, joining=None):
    count = masters(unit) + (masters(joining) if joining is not None else 0)
    for ident in values:
        peer = resolve_unit(unit, getattr(ident, '_id', ident))
        if peer is not None:
            count += masters(peer)
    return min(11, 3 * count)


def trim(unit, values):
    limit = maximum(unit, values)
    if limit >= len(values):
        return list(values)
    peers = [resolve_unit(unit, getattr(i, '_id', i)) for i in values]
    leaders = [p._id for p in peers if p is not None and masters(p) > 0]
    followers = [p._id for p in peers if p is not None and masters(p) == 0]
    return leaders + followers[:max(0, limit - len(leaders))]


def temporary(unit, ordinary=True, ecm=True, started=True, unconscious=False):
    values = [peer._id for i in range(max(0, network_size(unit, ordinary)))
              if (peer := other(unit, i, ordinary, ecm, started, unconscious)) is not None]
    return trim(unit, values) if ordinary and values else values


def remove(unit, ident, ordinary=True):
    if not network_size(unit, ordinary):
        return
    size = network_size(unit, ordinary)
    setattr(unit, network_name(ordinary), [-1 if value == ident else value for value in slots(unit, ordinary)])
    setattr(unit, network_name(ordinary) + '_size', size)
    validate(unit, ordinary)


def clear(unit, ordinary=True, propagate=True):
    values = slots(unit, ordinary)
    for i in range(len(values)):
        peer = other(unit, i, ordinary)
        values[i] = -1
        setattr(unit, network_name(ordinary), list(values))
        if propagate and peer is not None:
            remove(peer, unit._id, ordinary)
    write(unit, [], ordinary)


def validate(unit, ordinary=True):
    if not has_technology(unit, ordinary) or unit.is_destroyed or disabled(unit, ordinary) or network_size(unit, ordinary) < 0:
        clear(unit, ordinary)
        return
    values = temporary(unit, ordinary, False, False, False)
    write(unit, values, ordinary)


def free_position(unit, joining, ordinary=True):
    validate(unit, ordinary)
    for i, ident in enumerate(slots(unit, ordinary)):
        if ident <= 0:
            return i
        if ident == joining._id:
            return -1
    return -2


def replicate(source, destination, ordinary=True):
    values = [source._id] + [i for i in slots(source, ordinary) if i != destination._id]
    if len(values) > (11 if ordinary else 5):
        raise ValueError('Replication exceeds allocated source network array')
    clear(destination, ordinary, False)
    write(destination, values, ordinary)
    validate(destination, ordinary)


def add(unit, joining, ordinary=True):
    from systems.notifications import mech_notify, identity, MECHALL
    index = free_position(unit, joining, ordinary)
    if index < 0:
        return
    values = slots(unit, ordinary)
    values[index] = joining._id
    size = network_size(unit, ordinary) + 1
    setattr(unit, network_name(ordinary), values)
    setattr(unit, network_name(ordinary) + '_size', size)
    kind = 'C3' if ordinary else 'C3i'
    mech_notify(unit, MECHALL, f'{identity(unit, joining)} connects to your {kind} network.')
    for i in range(len(values)):
        peer = other(unit, i, ordinary)
        if peer is None:
            continue
        if peer is not joining and other(unit, i, ordinary, True, True, True) is not None:
            mech_notify(peer, MECHALL, f'{identity(peer, joining)} connects to your {kind} network.')
        replicate(unit, peer, ordinary)
    validate(unit, ordinary)


def send_message(unit, message, ordinary=True):
    from systems.notifications import mech_notify, unit_identity, MECHALL, LBUF_SIZE
    kind = 'C3' if ordinary else 'C3i'
    sender = unit_identity(unit)
    members = temporary(unit, ordinary, True, True, True)
    for index in range(len(members)):
        peer = temp_member(unit, members, len(members), index)
        if peer is None or not getattr(peer, 'valid', True) or not getattr(peer, 'valid_object', True):
            continue
        mech_notify(peer, MECHALL, f'%ch{kind}/{sender}: {message}%cn'[:LBUF_SIZE - 1])
    mech_notify(unit, MECHALL, f'%ch{kind}/You: {message}%cn'[:LBUF_SIZE - 1])


def command(unit, actor, action, argument='', ordinary=True):
    from systems.communications import common_checks, MECH_USUALO
    from systems.notifications import mech_notify, identity, MECHALL, personal_notify
    from systems.targeting import contact_target
    from systems.los import in_line_of_sight
    kind = 'C3' if ordinary else 'C3i'
    def fail(error):
        if error:
            personal_notify(actor, error)
        return dict(ok=False, error=error)
    error = common_checks(unit, actor, MECH_USUALO)
    if error is not None:
        return fail(error)
    from systems.combat_commands import parse_attributes
    args = parse_attributes(argument, 2)
    if action == 'join' and len(args) != 1:
        return fail('Invalid number of arguments to function!')
    if not has_technology(unit, ordinary):
        return fail(f'This unit is not equipped with {kind}!')
    if disabled(unit, ordinary):
        return fail(f'Your {kind} system is destroyed!')
    if any_ecm_disturbed(unit):
        return fail(f'Your {kind} system is not currently operational!')
    validate(unit, ordinary)
    if action == 'join':
        if args[0] == '-':
            message = (f'You disconnect from the {kind} network.' if network_size(unit, ordinary)
                       else f'You are not connected to a {kind} network!')
            clear(unit, ordinary)
            mech_notify(unit, MECHALL, message)
            return dict(ok=True, message=message)
        if network_size(unit, ordinary):
            return fail(f'You are already in a {kind} network!')
        target = contact_target(unit, args[0])
        if target is None or target._id <= 0 or not in_line_of_sight(unit, target, target.x, target.y, 0):
            return fail('That is not a valid targetID. Try again.')
        if target.team != unit.team:
            return fail(f"You can't use the {kind} network of unfriendly units!")
        if target is unit:
            return fail("You can't connect to yourself!")
        if target.is_destroyed:
            return fail('That unit is destroyed!')
        if not target.is_started:
            return fail('That unit is not started!')
        if not has_technology(target, ordinary):
            return fail(f'That unit does not appear to be equipped with {kind}!')
        validate(target, ordinary)
        capacity = maximum(unit, slots(target, ordinary)[:network_size(target, ordinary)], target) if ordinary else 5
        if network_size(target, ordinary) + 1 > capacity:
            return fail(f"That unit's {kind} network is operating at maximum capacity!")
        mech_notify(unit, MECHALL, f"You connect to {identity(unit, target)}'s {kind} network.")
        add(target, unit, ordinary)
        return dict(ok=True)
    if not network_size(unit, ordinary):
        return fail(f'There are no other units in your {kind} network!')
    if action == 'message':
        message = argument.lstrip()
        if not message:
            return fail(f'What do you want to send on the {kind} Network?')
        send_message(unit, message, ordinary)
        return dict(ok=True)
    from systems.network_reports import targets, network_data
    rows = (targets if action == 'targets' else network_data)(unit, ordinary)
    for row in rows:
        personal_notify(actor, row)
    return dict(ok=True, rows=rows)


def part_of_working_master(unit, section, slot):
    from systems.criticals import crits_in_loc
    from systems.combat import part_is_nonfunctional
    from entities.crittypes import i2special, Special
    size = 5 if unit.unit_type == UnitType.MECH else 1
    start, working, index = max(0, slot - (size - 1)), 0, 0
    criticals = unit.sections[section].criticals
    if not 0 <= slot < len(criticals):
        raise ValueError('Query exceeds allocated source critical array')
    while index < crits_in_loc(unit, section):
        if criticals[index].type == i2special(Special.C3_MASTER):
            if index < start:
                index += size
                continue
            if index + size > len(criticals):
                raise ValueError('C3 window exceeds allocated source critical array')
            working += sum(not part_is_nonfunctional(unit, section, i)
                           for i in range(index, index + size) if i != slot)
        index += 1
    return working == size - 1


def debug(message):
    """DEBUG_C3=0: the source default has no observable action."""


def range_with_network(unit, target, actual, values):
    from systems.los import in_line_of_sight, in_line_of_sight_nb
    from systems.targeting import fa_mech_range, find_range
    from physics.hexmath import hex_to_float, ZSCALE
    from core.randomness import float32
    best, reference = float32(actual), 0
    for i in range(len(values)):
        peer = temp_member(unit, values, len(values), i)
        if peer is None or peer is target:
            continue
        if target is not None:
            distance = fa_mech_range(peer, target)
            visible = in_line_of_sight(peer, target, target.x, target.y, distance)
        elif unit.targ_x > 0 and unit.targ_y > 0 and unit.map is not None:
            unit.targ_z = unit.map.base_elevation(unit.targ_x, unit.targ_y)
            x, y = hex_to_float(unit.targ_x, unit.targ_y)
            distance = find_range(peer.fx, peer.fy, peer.fz, x, y, unit.targ_z * ZSCALE)
            visible = in_line_of_sight_nb(peer, None, unit.targ_x, unit.targ_y, distance)
        else:
            continue
        if visible and distance < best:
            best, reference = distance, peer._id
    return best, reference


def range_query(unit, target, actual, ordinary=True, reference=-1):
    from core.randomness import float32
    actual = float32(actual)
    if disabled(unit, ordinary):
        if not ordinary:
            validate(unit, False)
        return actual, reference
    if any_ecm_disturbed(unit):
        return actual, reference
    return range_with_network(unit, target, actual, temporary(unit, ordinary))


def seen_by_network(unit, target, ordinary=True):
    from systems.los import in_line_of_sight, in_line_of_sight_nb
    from systems.targeting import fa_mech_range
    result = 0
    for ident in temporary(unit, ordinary):
        peer = resolve_unit(unit, ident)
        if peer is None or peer is target:
            continue
        distance = fa_mech_range(peer, target)
        result = in_line_of_sight(peer, target, target.x, target.y, distance)
        if result:
            if in_line_of_sight_nb(peer, target, target.x, target.y, distance):
                return 1
            result = 2
    return result
