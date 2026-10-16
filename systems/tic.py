# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.advanced.c
#   btech/mech.tic.c
#   btech/mech.utils.c
#   btech/src/btech/mech.h
#   btech/src/coolmenu.c

"""
TICs (weapon trigger groups) — port of mech.tic.c.

Storage deviation (deliberate): the C keeps each tic as a bitmask of
weapon numbers, "unsigned long tic[NUM_TICS][TICLONGS]" (mech.h:593-596,
mech.h:960).  The port stores `mech.tics: list[set[int]]` — one set of
weapon numbers (0..MAX_WEAPONS_PER_MECH-1) per tic — with identical
semantics: membership, idempotent add, removal, ascending iteration.

Command functions return the C's notify texts as a list[str].
"""

import re

from systems.combat import fire_weapon_number
from systems.combat_commands import read_number, command_guard

# mech.h:593-596: NUM_TICS = 4, MAX_WEAPONS_PER_MECH = 96 (TICLONGS is
# only the C's bitmask word-packing arithmetic — not needed for sets).
NUM_TICS = 4
MAX_WEAPONS_PER_MECH = 96

# listtic row format (mech.tic.c, listtic_fun): "#%2d %3s %-16s %s" ->
# weapon number, short section string, weapon name, "(*)" marker.
TIC_ROW_FORMAT = "#%2d %3s %-16s %s"

# Short mech section names (ShortArmorSectionString), keyed by
# entities.mech.Location index.
SECTION_SHORT_NAMES = ("LA", "RA", "LT", "RT", "CT", "LL", "RL", "H")

# sscanf(buffer, "%d-%d", ...) == 2: first %d already at the (skipws'd)
# start, literal '-' immediately after it, second %d skips whitespace;
# trailing junk is ignored, matching sscanf.
_RANGE_RE = re.compile(r'^([-+]?\d+)-\s*([-+]?\d+)')


def _atoi(value) -> int:
    """C atoi: parse a leading integer, 0 on failure."""
    if isinstance(value, int):
        return value
    m = re.match(r'\s*([-+]?\d+)', str(value))
    return int(m.group(1)) if m else 0


# =============================================================================
# multi_weap_sel (mech.utils.c:2252-2305)
# =============================================================================

def multi_weap_sel(mech, spec, bitbybit: int, foo, messages: list) -> bool:
    """
    Weapon/tic selector: `n`, `n-m`, and comma lists of those.

    Returns explicit selector acceptance; a callback stop is still accepted.
    Port of multi_weap_sel (mech.utils.c:2252-2305).  `foo(mech, low,
    high)` is invoked per selection (per single number when bitbybit is
    odd); a truthy return aborts everything, including the comma tail.
    DOCHECK failures append the C text to `messages` and abort the same
    way (the C returns out of multi_weap_sel before recursing).

    Verbatim C quirks preserved:
    - Reversed ranges are swapped (i1 > i2 -> swap).
    - bitbybit/2 (tic selection): only the HIGH endpoint is checked
      against NUM_TICS, and "There are only %d tics!" prints i2 — the
      offending tic number — NOT the tic count.
    - otherwise (weapon selection): only the HIGH endpoint is validated
      against the mech's real weapon count (FindWeaponNumberOnMech ==
      -1), and the message prints i2 + 1: "Error: the mech doesn't HAVE
      %d weapons!".
    """
    spec = str(spec).lstrip()                        # skipws(buffer)
    head, sep, tail = spec.partition(',')
    m = _RANGE_RE.match(head)
    if m:                                            # sscanf("%d-%d") == 2
        i1, i2 = int(m.group(1)), int(m.group(2))
        if i1 < 0 or i1 >= MAX_WEAPONS_PER_MECH:
            messages.append("Invalid first number in range (%d)" % i1)
            return False
        if i2 < 0 or i2 >= MAX_WEAPONS_PER_MECH:
            messages.append("Invalid second number in range (%d)" % i2)
            return False
        if i1 > i2:
            i1, i2 = i2, i1
    else:
        try:
            i1 = read_number(head)
        except ValueError:
            messages.append("Invalid value: %s" % head)
            return False
        if i1 < 0 or i1 >= MAX_WEAPONS_PER_MECH:
            messages.append("Invalid weapon number: %d" % i1)
            return False
        i2 = i1

    if bitbybit // 2:
        if i2 >= NUM_TICS:
            # Verbatim quirk: prints i2, the offending tic number, NOT
            # the tic count (mech.utils.c:2252-2305).
            messages.append("There are only %d tics!" % i2)
            return False
    else:
        from systems.weapon_modes import find_weapon_number_on_mech
        if find_weapon_number_on_mech(mech, i2)[0] == -1:
            messages.append("Error: the mech doesn't HAVE %d weapons!"
                            % (i2 + 1))
            return False

    if bitbybit % 2:
        for i3 in range(i1, i2 + 1):
            if foo(mech, i3, i3):
                return True
    else:
        if foo(mech, i1, i2):
            return True
    if sep:                                          # recurse on comma tail
        return multi_weap_sel(mech, tail, bitbybit, foo, messages)
    return True


# =============================================================================
# addtic (mech.tic.c: addtic_sub / addtic_sub_func)
# =============================================================================

def add_tic(mech, ticnum, spec, *, caller=None) -> list:
    """
    addtic <tic> <weapons> — port of addtic_sub/addtic_sub_func
    (mech.tic.c).  Set-adds are idempotent, matching the C bit-set.
    """
    messages = TicMessages(mech,caller)
    tn = _atoi(ticnum)
    if not (0 <= tn < NUM_TICS):
        messages.reject("Invalid tic number!")
        return messages

    def _add(m, low, high):
        for i in range(low, high + 1):
            m.tics[tn].add(i)
        if low != high:
            messages.append("Weapons #%d - #%d added to TIC %d!"
                            % (low, high, tn))
        else:
            messages.append("Weapon #%d added to TIC %d!" % (low, tn))
        return 0

    messages.accepted = multi_weap_sel(mech, spec, 0, _add, messages)
    return messages


# =============================================================================
# deltic (mech.tic.c: deltic_sub / deltic_sub_func)
# =============================================================================

def del_tic(mech, *args, caller=None) -> list:
    """
    deltic — port of deltic_sub/deltic_sub_func (mech.tic.c).

    Verbatim quirk: ONE argument falls through to cleartic with that
    argument — `deltic 2` clears ALL of tic 2 (the C hands cleartic_sub
    the original buffer).
    """
    argc = len(args)
    if argc < 1 or argc > 2:
        return TicMessages(mech,caller,["Invalid number of arguments to the function!"],accepted=False)
    if argc == 1:
        return clear_tic(mech, args[0], caller=caller)
    tn = _atoi(args[0])
    if not (0 <= tn < NUM_TICS):
        return TicMessages(mech,caller,["Invalid tic number!"],accepted=False)
    messages = TicMessages(mech,caller)

    def _del(m, low, high):
        for i in range(low, high + 1):
            m.tics[tn].discard(i)
        if low != high:
            messages.append("Weapons #%d - #%d removed from TIC %d!"
                            % (low, high, tn))
        else:
            messages.append("Weapon #%d removed from TIC %d!" % (low, tn))
        return 0

    messages.accepted = multi_weap_sel(mech, args[1], 0, _del, messages)
    return messages


# =============================================================================
# cleartic (mech.tic.c: cleartic_sub / cleartic_sub_func)
# =============================================================================

def clear_tic(mech, spec, *, caller=None) -> list:
    """
    cleartic <ticspec> — port of cleartic_sub/cleartic_sub_func
    (mech.tic.c).  Tic selector, so ranges and comma lists of TIC numbers
    are allowed (the bitbybit=2 path of multi_weap_sel).
    """
    messages = TicMessages(mech,caller)
    # mech_parseattributes argc check (mech.tic.c cleartic_sub):
    # DOCHECK(argc != 1, ...)
    if len(str(spec).split()) != 1:
        messages.reject("Invalid number of arguments to function")
        return messages

    def _clear(m, low, high):
        for i in range(low, high + 1):
            m.tics[i].clear()
            messages.append("TIC #%d cleared!" % i)
        return 0

    messages.accepted = multi_weap_sel(mech, spec, 2, _clear, messages)
    return messages


# =============================================================================
# firetic (mech.tic.c: mech_firetic / firetic_sub / firetic_sub_func)
# =============================================================================

def fire_tic(engine, mech, ticnum_spec='', *fire_args, caller=None, wizard=False):
    from entities.mech import MechStatus2
    from systems.movement_commands import notify
    messages = TicMessages(mech,caller)
    error = command_guard(mech,caller=caller,wizard=wizard)
    if error:
        messages.reject(error);return messages
    if mech.status2 & MechStatus2.WEAPONS_HOLD:
        messages.reject('Currently in weapons hold. Unable to fire weapons.');return messages
    if not str(ticnum_spec):
        messages.reject('Not enough arguments to function');return messages
    tn = _atoi(ticnum_spec)
    if not 0 <= tn < NUM_TICS:
        messages.reject('TIC out of range!');return messages
    temp_args = (str(ticnum_spec),) + tuple(fire_args)
    def fire(m,low,high):
        fallen = m.is_fallen
        for i in range(low,high+1):
            messages.append(f'Firing weapons in tic #{i}!')
            count = 0
            for number in sorted(m.tics[i]):
                result = fire_weapon_number(engine,m,number,raw_args=temp_args,caller=caller,wizard=wizard,_guarded=True)
                list.extend(messages,getattr(result,'messages',[]))
                if fallen != m.is_fallen:
                    if m.is_started:
                        text='That fall causes you to stop your fire!'
                        notify(m,text);list.append(messages,text)
                    return 1
                if not m.is_started:return 1
                count += 1
            if not count:messages.append('*Click* (the tic contained no weapons)')
        return 0
    messages.accepted = multi_weap_sel(mech,ticnum_spec,2,fire,messages)
    return messages


# =============================================================================
# listtic (mech.tic.c: listtic_sub / listtic_fun)
# =============================================================================

def list_tic(mech, ticnum, *, caller=None) -> tuple:
    """
    listtic <tic> — port of listtic_sub/listtic_fun (mech.tic.c).

    Returns (rows, messages).  Rows are (weapon_number, section_short,
    weapon_name, marker) tuples in the C two-column callback order;
    stale or missing display entries are source error strings.
    Fields map onto the C row format "#%2d %3s %-16s %s"
    (TIC_ROW_FORMAT): the weapon name drops its 3-char tech prefix
    (&MechWeapons[t].name[3]) and marker is "(*)" when the part is
    nonfunctional (PartIsNonfunctional).

    Side effect (verbatim, listtic_fun's -1 branch): weapon numbers that
    no longer resolve on the mech (FindWeaponNumberOnMech == -1) are
    PRUNED from the tic while listing.
    """
    from entities.weapon import get_weapon_by_index
    from systems.combat import part_is_nonfunctional
    from systems.damage_commands import section_names

    messages = TicMessages(mech,caller)
    # listtic_sub: DOCHECK(argc != 1, "Invalid number of arguments!")
    if len(str(ticnum).split()) != 1:
        messages.reject("Invalid number of arguments!")
        return [], messages
    tn = _atoi(ticnum)
    if not (0 <= tn < NUM_TICS):
        messages.reject("TIC out of range!")
        return [], messages

    from systems.weapon_inventory import sync_weapon_states
    sync_weapon_states(mech)

    # The menu captures membership count before calling the formatter. Its
    # initial format probe invokes row zero too (coolmenu.c:347-369), so a
    # stale number can disappear before the first displayed row.
    count = len(mech.tics[tn])
    error = "Unknown - error of some sort occured"

    def display_row(index):
        if not count:
            return "No weapons in tic."
        offset = index // 2 + ((count + 1) // 2 if index % 2 else 0)
        members = sorted(mech.tics[tn])
        if offset >= len(members):
            return error
        weapnum = members[offset]
        if weapnum >= len(mech.weapons):
            mech.tics[tn].discard(weapnum)
            return error
        ws = mech.weapons[weapnum]
        weapon = get_weapon_by_index(ws.weapon_idx)
        name = weapon.name[3:] if weapon else "???"
        names = section_names(mech)
        from systems.damage_commands import short_section
        short = (short_section(mech,ws.section)
                 if 0 <= ws.section < len(names) else "?")
        marker = "(*)" if part_is_nonfunctional(mech, ws.section, ws.critical) else ""
        return weapnum, short, name, marker

    display_row(0)  # Source format probe; its text is not displayed.
    rows = [display_row(i) for i in range(max(1, count))]
    from core.effects import notify_actor
    from systems.parts import mech_ids
    actor = mech.pilot if caller is None else caller
    notify_actor(mech,actor,f'TIC #{tn} listing for {mech_ids(mech)}')
    for row in rows:
        if isinstance(row,str):messages.append(row)
        else:notify_actor(mech,actor,TIC_ROW_FORMAT % row)
    return rows if count else [], messages


class TicMessages(list):
    """Source personal notifications emitted at each selector callback."""
    def __init__(self,mech,caller=None,initial=(),*,accepted=True):
        super().__init__()
        self.mech,self.caller = mech,mech.pilot if caller is None else caller
        self.accepted = accepted
        self.extend(initial)
    def append(self,text):
        from core.effects import notify_actor
        if not getattr(text,'notified',False):notify_actor(self.mech,self.caller,text)
        super().append(text)
    def extend(self,items):
        for item in items:self.append(item)
    def reject(self,text):
        self.accepted = False
        self.append(text)


def tic_command(engine,mech,name,text,*,caller=None,wizard=False):
    args = text.split()
    if name == 'firetic':return fire_tic(engine,mech,*args,caller=caller,wizard=wizard)
    error = command_guard(mech,started=False,map_required=False,pilot_only=False,caller=caller,wizard=wizard)
    if error:return TicMessages(mech,caller,[error],accepted=False)
    if name == 'addtic':
        return add_tic(mech,*args,caller=caller) if len(args)==2 else TicMessages(mech,caller,['Invalid number of arguments to function!'],accepted=False)
    if name == 'deltic':return del_tic(mech,*args,caller=caller)
    if name == 'cleartic':return clear_tic(mech,text,caller=caller)
    if name == 'listtic':return list_tic(mech,text,caller=caller)
    raise ValueError('Unknown TIC command')
