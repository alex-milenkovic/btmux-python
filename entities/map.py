# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.c
#   btech/map.coding.c
#   btech/mech.maps.c
#   btech/mech.notify.c
#   btech/mech.sensor.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/map.h

"""
Map and terrain — port of the BTMux map layer.

Terrain type characters and elevation semantics from map.h / btmacros.h.
The GameMap class (MAP struct, map.h) and the map-file loader (map_load,
map.c:290) live here.

Coordinate/packing note: the C packs terrain+elevation into one byte per hex
(map.coding.c); per the plan, this port stores them as two parallel arrays.
"""

# --- Terrain type characters (map.h:44-63) ---
GRASSLAND = ' '
HEAVY_FOREST = '"'
LIGHT_FOREST = '`'
WATER = '~'
HIGHWATER = '?'
ROUGH = '%'
MOUNTAINS = '^'
ROAD = '#'
BUILDING = '@'
FIRE = '&'
TFIRE = '>'
SMOKE = ':'
WALL = '='
DESERT = '}'
BRIDGE = '/'
SNOW = '+'
ICE = '-'
UNKNOWN_TERRAIN = '$'

MAX_ELEV = 9  # map.h:43


def base_elev(terrain: str, elev: int) -> int:
    """
    Signed elevation of a hex floor: WATER and ICE store depth, so their
    floor is below zero.  Port of BaseElev (btmacros.h:45).
    """
    if terrain == WATER or terrain == ICE:
        return -elev
    return elev


import os
import re

# --- Map size / name limits (map.h:35-40) ---
MAPX = 1000
MAPY = 1000
MAP_NAME_SIZE = 30
DEFAULT_MAP_WIDTH = 21
DEFAULT_MAP_HEIGHT = 11

# --- Map flags (map.h:71,76) ---
MAPFLAG_UNDERGROUND = 16     # (e) We're underground (map.h:72)
MAPFLAG_FIRES = 8            # (d) We have eternal fires
MAPFLAG_NOBRIDGIFY = 128     # (h) We shouldn't convert roads into bridges
MAPFLAG_NOFRIENDLYFIRE = 256  # (i) Can't shoot friendlies AT ALL (map.h:77)
MAPFLAG_NOPHYSICALS = 512    # (j) No physicals allowed (map.h:78)

# Hex neighbour steps per heading index (mech.utils.c:2766-2773).
DIRS = (
    (0, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
)


def neighbors(board, x, y):
    """Source visit_neighbor_hexes order and odd-column correction."""
    for dx, dy in DIRS:
        nx, ny = x + dx, y + dy
        if x % 2 and not nx % 2:
            ny -= 1
        if board.valid(nx, ny):
            yield nx, ny


def visit_neighbor_hexes(board, x, y, callback):
    for nx, ny in neighbors(board, x, y):
        callback(board, nx, ny)

# Terrain display names.  Port of GetTerrainName_base (mech.maps.c:91-125).
# Oddities preserved: '_' is a Grassland alias; SNOW is absent from the C
# switch, so it names as "Unknown" (and map_load rejects it to GRASSLAND).
_TERRAIN_NAMES = {
    GRASSLAND: "Grassland",
    '_': "Grassland",
    HEAVY_FOREST: "Heavy Forest",
    LIGHT_FOREST: "Light Forest",
    ICE: "Ice",
    BRIDGE: "Bridge",
    HIGHWATER: "Water",
    WATER: "Water",
    ROUGH: "Rough",
    MOUNTAINS: "Mountains",
    ROAD: "Road",
    BUILDING: "Building",
    FIRE: "Fire",
    SMOKE: "Smoke",
    WALL: "Wall",
    DESERT: "Desert",
}


def get_terrain_name_base(terrain: str) -> str:
    """Name of a terrain char, "Unknown" if not valid (mech.maps.c:91-125)."""
    return _TERRAIN_NAMES.get(terrain, "Unknown")


def bounded(low, val, high):
    """Clamp val into [low, high].  Port of the BOUNDED macro."""
    if val < low:
        return low
    if val > high:
        return high
    return val


class GameMap:
    """
    A hex map.  Port of the MAP struct (map.h:159-198).

    Storage deviation (authorized): the C packs terrain+elevation into one
    byte per hex via Coding_GetIndex (map.coding.c:42); this port keeps two
    parallel 2-D arrays (_terrain[y][x] char, _elev[y][x] int) which
    round-trip values verbatim, exactly as the coding layer does.

    Field defaults: XCODE objects are calloc'd in the C, so weather and
    visibility fields default to 0; movemod defaults to 100 (int percent,
    MAPMOVEMOD = movemod / 100.0, btmacros.h:727).

    Local typed objects, dynamic roster records and building values retain
    source state. External persistent object attributes remain adapter inputs.
    """

    xcode_type = "MAP"

    def __init__(self, width: int, height: int, name: str = ""):
        self.map_width = width
        self.map_height = height
        self.name = name
        self.object_name = name  # Database display Name, independent of terrain filename.
        # Two parallel arrays instead of the C's packed byte map (see class doc).
        self._terrain = [[GRASSLAND] * width for _ in range(height)]
        self._elev = [[0] * width for _ in range(height)]
        self.movemod = 100          # int percent (btmacros.h:727)
        self.decorations = {}      # Timed terrain overlays keyed by hex
        self.mines = []
        self.map_objects = [[] for _ in range(10)]
        self.map_objects[3] = self.mines
        self._grid_failed = False
        self._loaded_rows = height
        self._engine = None
        self._id = -1
        self.cf = self.cfmax = self.onmap = self.buildflag = 0
        self.regen_factor = 1
        self.roster_ids = []
        self.mechflags = []
        self.slot_los = []
        self.external_effects = []
        self.map_messages = []
        self.layers = {}
        self.layer_data = {}
        from physics.environment import initialize
        initialize(self)
        self.mine_hexes = set()
        self.projectiles = []
        self.artillery_impacts = []
        self.combat_messages = []
        self.flags = 0
        # calloc defaults (XCODE objects are zeroed in the C)
        self.sensorflags = 0
        self.infrared_profile = "unscaled"
        self.seismic_see_stopped = False
        self.visibility_config = ""
        self.mapvis = 0
        self.maxvis = 0
        self.maplight = 0
        self.winddir = 0
        self.windspeed = 0
        self.cloudbase = 0
        self.temp = 0
        self.grav = 0
        self.mechs_on_map = []      # MAP.mechsOnMap (map.h:188); Mech objects, not dbrefs
        self.losinfo = None         # MAP.LOSinfo (map.h:189) - Workstream D fills

    def valid(self, x: int, y: int) -> bool:
        """In-bounds check for a hex coordinate."""
        return 0 <= x < self.map_width and 0 <= y < self.map_height

    def require_cell(self,x,y):
        if self._grid_failed: raise ValueError('Map grid unavailable after failed load')
        if self._terrain is None: raise ValueError('Map grid has been freed')
        if not self.valid(x,y): raise ValueError('Map coordinates out of range')

    def hex_records(self):
        if self._terrain is None: return []
        height=self._loaded_rows if self._grid_failed else self.map_height
        return [dict(at=[x,y],terrain=self._terrain[y][x],elevation=self._elev[y][x],
                     underlying=None if self._grid_failed else self.rterrain(x,y))
                for y in range(height) for x in range(len(self._terrain[y]))]

    def terrain(self, x: int, y: int) -> str:
        """Raw terrain char of a hex.  GetTerrain (btmacros.h:566)."""
        self.require_cell(x,y)
        return self._terrain[y][x]

    def rterrain(self, x, y):
        if self.terrain(x,y) in (FIRE,SMOKE):
            from entities.map_objects import underlying_terrain
            return underlying_terrain(self,x,y)
        return self.terrain(x,y)

    def legacy_underlying(self, x, y):
        """Read retained dictionary overlays supplied by older fixture adapters."""
        decoration = self.decorations.get((x, y))
        if decoration is not None and self.terrain(x, y) == decoration['terrain']:
            return decoration['underlying']
        return self.terrain(x, y)

    def elevation(self, x: int, y: int) -> int:
        """Unsigned stored elevation 0-9.  GetElevation (btmacros.h:568)."""
        self.require_cell(x,y)
        return self._elev[y][x]

    def base_elevation(self, x: int, y: int) -> int:
        """
        Signed floor elevation of a hex.  Elevation macro (btmacros.h:46-47):
        BaseElev(GetRTerrain, GetElevation).
        """
        return base_elev(self.rterrain(x, y), self.elevation(x, y))

    def water_depth(self, x: int, y: int) -> int:
        """Depth of water/ice hexes (stored elevation), 0 for dry land."""
        t = self.terrain(x, y)
        if t == WATER or t == ICE:
            return self.elevation(x, y)
        return 0

    def set_terrain(self, x: int, y: int, ch: str) -> None:
        """
        Set the terrain char of a hex, keeping elevation.  SetTerrain
        (btmacros.h:571), including the UpdateMechsTerrain(map, x, y, t)
        call (map.c:742-757) that refreshes the cached mech.terrain of
        any mech standing in the hex.
        """
        self._terrain[y][x] = ch
        # UpdateMechsTerrain (map.c:742-757)
        for mech in self.mechs_on_map:
            if mech is None: continue
            if mech.x != x or mech.y != y:
                continue
            if mech.terrain != ch:
                mech.terrain = ch
                # MarkForLOSUpdate(mech) (map.c:754); lazy import —
                # systems.ecm imports entities.map transitively.
                from systems.ecm import mark_for_los_update
                mark_for_los_update(mech)

    def set_elevation(self, x: int, y: int, e: int) -> None:
        """Set the stored elevation of a hex, keeping terrain.  SetElevation (btmacros.h:573)."""
        self._elev[y][x] = e

    @property
    def first_free(self): return len(self.roster_ids)

    @property
    def losinfo(self): return self._losinfo

    @losinfo.setter
    def losinfo(self,values):
        from systems.map_membership import LOSCache
        self._losinfo=None if values is None else LOSCache(self,values)

    def add_mech(self,mech):
        from systems.map_membership import add
        if add(self,mech) and self.valid(mech.x,mech.y):
            mech.terrain=self.terrain(mech.x,mech.y)
            mech.elev=self.elevation(mech.x,mech.y)

    def remove_mech(self,mech):
        from systems.map_membership import remove
        remove(self,mech)
        mech.terrain=''
        mech.elev=0

    @classmethod
    def from_file(cls,path):
        """Fresh-map adapter for the shared source loader and its failure codes."""
        from systems.map_management import load_file
        board=cls(DEFAULT_MAP_WIDTH,DEFAULT_MAP_HEIGHT)
        result=load_file(board,path)
        if result==-1: raise ValueError(f'Bad map file: {path} (return -1)')
        if result==-2: raise ValueError('Error: EOF reached prematurely. (return -2)')
        return board


def water_distance(gamemap: GameMap, x: int, y: int, direction: int,
                   max_dist: int) -> int:
    """
    Distance to water along a heading, or max_dist if blocked/none.
    Port of water_distance (map.c:195-215).  Oddity preserved: the
    `if (!x && dirs[dir][0]) y--;` step (sic - decrements y whenever a
    horizontal move lands on column 0).
    """
    for i in range(1, max_dist):
        x = x + DIRS[direction][0]
        y = y + DIRS[direction][1]
        if not x and DIRS[direction][0]:
            y -= 1
        x2 = bounded(0, x, gamemap.map_width - 1)
        y2 = bounded(0, y, gamemap.map_height - 1)
        if x != x2 or y != y2:
            return max_dist
        t = gamemap.terrain(x, y)
        if t == WATER or t == ICE:
            return i
        if t != BRIDGE and t != ROAD:
            return max_dist
    return max_dist


def eligible_bridge_hex(gamemap: GameMap, x: int, y: int) -> int:
    """
    Whether opposite sides have water within range 3.  Port of
    eligible_bridge_hex (map.c:217-230), including the unreachable
    `(i - j) > 3` continue.
    """
    for k in range(3):
        i = water_distance(gamemap, x, y, k, 4)
        if i < 4:
            j = water_distance(gamemap, x, y, k + 3, 4)
            if j < 4:
                if (i - j) > 3:
                    continue
                return 1
    return 0


def make_bridges(gamemap: GameMap) -> None:
    """
    Convert eligible ROAD hexes over water into BRIDGE.  Port of
    make_bridges (map.c:233-241).  Uses SetTerrainBase semantics (direct
    write, no UpdateMechsTerrain).
    """
    for x in range(gamemap.map_width):
        for y in range(gamemap.map_height):
            if gamemap.terrain(x, y) == ROAD:
                if eligible_bridge_hex(gamemap, x, y):
                    gamemap._terrain[y][x] = BRIDGE   # SetTerrainBase (btmacros.h:572)


# Message hook, same pattern as systems.missile.NOTIFY_HOOK.
NOTIFY_HOOK = None


def _notify(mech, message: str) -> None:
    from systems.movement_commands import notify
    notify(mech, message)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


def map_update(engine, gamemap: GameMap) -> None:
    """
    Periodic map refresh.  Port of map_update (map.c:553-598).

    Every 25th tick (map.c:566) the weather/visibility values are re-read.
    visibility_config supplies the A_MAPVIS text boundary (map.c:569-571).
    Missing/malformed input uses the C's sscanf-failure defaults.
    """
    # Clock stamp for map-scoped readers (MNumber's RANDOM_TICK cache,
    # stagger windows) — the C reads muxevent_tick globally.
    gamemap.current_tick = engine.muxevent_tick

    if not (engine.muxevent_tick % 25):
        oldl = gamemap.maplight
        oldv = gamemap.mapvis
        # sscanf failed / no attr -> defaults (map.c:572-577)
        ma = 30
        ml = 2
        wind = 0
        wspeed = 0
        cloudbase = 200
        changemsg = ""
        from systems.map_conditions import visibility_values
        ma,ml,wind,wspeed,cloudbase,changemsg=visibility_values(gamemap.visibility_config)
        oldwind=(gamemap.winddir,gamemap.windspeed)
        gamemap.winddir = wind                       # map.c:578
        gamemap.windspeed = wspeed                   # map.c:579
        gamemap.mapvis = bounded(0, ma, 60)          # map.c:580
        gamemap.maxvis = bounded(24, ma * 3, 60)     # map.c:581
        gamemap.maplight = bounded(0, ml, 2)         # map.c:582
        gamemap.cloudbase = cloudbase                # map.c:583
        if oldwind!=(wind,wspeed):
            from physics.environment import arm
            arm(gamemap,restart=True)
        if ml != oldl or ma != oldv:                 # map.c:584-594
            for mech in gamemap.mechs_on_map:
                if mech is None:
                    continue
                if ml != oldl:
                    from systems.targeting import sensor_light_availability_check
                    sensor_light_availability_check(mech)
                if len(changemsg) > 5:
                    _notify(mech, changemsg)         # map.c:592-593
    # update_LOSinfo(obj, map) (map.c:596); lazy import — systems.sensors
    # imports entities.map at module level.
    from systems.sensors import update_los_info
    update_los_info(gamemap)
    # Fire/Smoke are event-driven -> nothing related to them done here (map.c:597)
