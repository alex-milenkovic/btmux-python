# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.c
#   btech/map.conditions.c

"""Map condition flags and the defined A_MAPVIS scanf conversions."""
from entities.mech import MechStatus as S
from systems.map_management import arguments,readnum,scan_ints,report


def update_conditions(unit,board):
    if unit is None: return
    unit.clear_status(S.CONDITIONS)
    if board is None or not board.flags&2: return
    unit.set_status(S.UNDERSPECIAL)
    if board.temp < -30 or board.temp > 50: unit.set_status(S.UNDERTEMPERATURE)
    if board.grav!=100: unit.set_status(S.UNDERGRAVITY)
    if board.flags&4: unit.set_status(S.UNDERVACUUM)


def alter_conditions(board):
    for unit in board.mechs_on_map: update_conditions(unit,board)


def set_conditions(board,text,actor=1):
    args=arguments(text,4)
    if len(args)<2: raise ValueError('(At least) 2 options required (gravity + temperature)')
    values=[]
    rules=((0,255,'Invalid gravity (must be integer in range of 0 to 255)'),
           (-128,127,'Invalid temperature (must be integer in range of -128 to 127'),
           (0,1,'Invalid vacuum flag (must be integer, 0 or 1)'),
           (0,1,'Invalid underground flag (must be integer, 0 or 1)'))
    for arg,(low,high,message) in zip(args,rules):
        try: value=readnum(arg)
        except ValueError: raise ValueError(message) from None
        if not low<=value<=high: raise ValueError(message)
        values.append(value)
    grav,temp=values[:2]
    flags=board.flags&~6
    if len(values)>2 and values[2]: flags|=4
    if len(values)>3 and values[3]: flags|=16
    if flags&4 or grav!=100 or temp < -30 or temp > 50: flags|=2
    oldtemp=board.temp
    board.flags,board.grav,board.temp=flags,grav,temp
    report(board,'Conditions set!',actor)
    alter_conditions(board)
    if oldtemp!=temp:
        from physics.environment import arm
        arm(board,restart=True)


def visibility_values(text):
    values,pos=scan_ints(text,5)
    if len(values)<4: return 30,2,0,0,200,''
    from entities.map_storage import source_int,signed_value
    values=list(map(source_int,values))
    if len(values)==4: values.append(200); message=''
    else: message=text[pos:].lstrip().split('\n',1)[0]
    return *values[:2],*(signed_value(value,16) for value in values[2:]),message
