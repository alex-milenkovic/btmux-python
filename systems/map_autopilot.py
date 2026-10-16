# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.c
#   btech/mech.notify.c

"""Map-entry AUTO title and wake lifecycle; autonomous gameplay stays in services."""
from systems.targeting import resolve_object


def autopilot(board,unit):
    return resolve_object(board,unit.auto) if getattr(unit,'auto',-1)>0 else None


def set_title(board,unit):
    auto=autopilot(board,unit)
    if auto is None:return
    from systems.communications import set_title as channel_title
    from systems.notifications import personal_notify
    from systems.parts import mech_ids
    result=channel_title(unit,f'a={unit.mech_type}/{mech_ids(unit,True)}')
    personal_notify(auto,result.get('message',result.get('error','')))


def wake(board,unit):
    from systems.autopilot import un_zombify_mech
    un_zombify_mech(unit)
