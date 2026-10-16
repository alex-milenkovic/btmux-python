# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_core.c
#   btech/src/btech/autopilot.h

"""Battlesheep controller state. Transient paths and profiles are rebuilt on load."""
from dataclasses import dataclass, field

COMMAND_NAMES = (
    'chasetarget', 'dumbfollow', 'dumbgoto', 'enterbase', 'follow', 'goto',
    'leavebase', 'oldgoto', 'roam', 'wait', 'attackleg', 'autogun', 'chasemode',
    'cmode', 'dropoff', 'embark', 'enterbay', 'jump', 'load', 'pickup', 'report',
    'roammode', 'shutdown', 'speed', 'startup', 'stopgun', 'swarm', 'swarmmode',
    'udisembark', 'unload')
COMMAND_COUNTS = (1,1,2,1,1,2,1,2,1,2,1,1,1,2,0,1,0,1,0,1,0,1,0,1,0,0,1,1,0,0)
COMMANDS = {name: (index, COMMAND_COUNTS[index]) for index, name in enumerate(COMMAND_NAMES)}

AUTOPILOT_AUTOGUN = 1
AUTOPILOT_GUNZOMBIE = 2
AUTOPILOT_PILZOMBIE = 4
AUTOPILOT_ROAM = 8
AUTOPILOT_LSENS = 16
AUTOPILOT_CHASETARG = 32
AUTOPILOT_WAS_CHASE_ON = 64
AUTOPILOT_SWARMCHARGE = 128
AUTOPILOT_ASSIGNED_TARGET = 256


@dataclass
class CommandNode:
    args: list[str] = field(default_factory=list)
    enum_value: int | None = None

    @property
    def argcount(self):
        return len(self.args) - 1

    @property
    def command_enum(self):
        return self.enum_value if self.enum_value is not None else COMMANDS[self.args[0]][0] if self.args else 0


@dataclass
class AStarNode:
    x: int
    y: int
    x_parent: int = -1
    y_parent: int = -1
    g_score: int = 0
    h_score: int = 0
    f_score: int = 0
    hexoffset: int = 0


@dataclass
class WeaponNode:
    weapon_number: int
    weapon_db_number: int
    section: int
    critical: int
    range_scores: list[int] = field(default_factory=lambda: [0] * 30)


@dataclass
class TargetNode:
    target_score: int
    target_dbref: int


class Autopilot:
    xcode_type = 'AUTO'
    hardcode = True
    allocated = True
    gunnery = 6
    piloting = 6
    perception = 6
    robot = True
    is_player = False
    valid_object = True
    # The scalar AUTO struct fields. No object pointers enter persistence.
    state_fields = (
        'location', 'mymechnum', 'mapindex', 'speed', 'ofsx', 'ofsy', 'verbose_level',
        'target', 'target_score', 'target_threshold', 'target_update_tick',
        'chase_target', 'chasetarg_update_tick', 'follow_update_tick', 'flags',
        'mech_max_range', 'roam_type', 'roam_update_tick', 'roam_target_hex_x',
        'roam_target_hex_y', 'roam_anchor_hex_x', 'roam_anchor_hex_y',
        'roam_anchor_distance', 'ahead_ok', 'auto_cmode', 'auto_cdist',
        'auto_goweight', 'auto_fweight', 'auto_nervous', 'b_msc', 'w_msc',
        'b_bsc', 'w_bsc', 'b_dan', 'w_dan', 'last_upd')

    def __init__(self, identity, unit=None):
        self._id = identity
        self.name = 'Autopilot'
        self._engine = None
        for name in self.state_fields:
            setattr(self, name, 0)
        self.location = unit._id if unit is not None else -1
        self.mymechnum = 0
        self.mymech = None
        self.mapindex = 0
        self.speed = 100
        self.commands = []
        self.astar_path = None
        self.weaplist = None
        self.profile = [None] * 30
        self.inbox = []
        self.external_effects = []

    @property
    def mynum(self):
        return self._id

    def get_command_enum(self, position=1):
        from systems.autopilot_core import auto_get_command_enum
        return auto_get_command_enum(self, position)

    def get_command_arg(self, position, argument):
        from systems.autopilot_core import auto_get_command_arg
        return auto_get_command_arg(self, position, argument)

