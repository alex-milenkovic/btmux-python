# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btspath.c

"""Directed tile costs from btspath.c; zero means impassable.

Coordinates need not be adjacent. Preserve the C destination ty/width guard,
but safely reject either endpoint outside the map instead of indexing invalid
memory. GameMap's deferred FIRE/SMOKE decoration store limits overlay fidelity.
"""
from typing import Protocol

from entities.map import HEAVY_FOREST, LIGHT_FOREST, MOUNTAINS, ROUGH, WATER


class PathCostMap(Protocol):
    """Read-only terrain view required by pricing; GameMap satisfies it directly.

    Implementations own bounds and signed/real-terrain interpretation. No cell
    storage, map loading, occupants, or mutation API crosses this boundary.
    """

    @property
    def map_width(self) -> int: ...

    def valid(self, x: int, y: int) -> bool: ...

    def base_elevation(self, x: int, y: int) -> int: ...

    def rterrain(self, x: int, y: int) -> str: ...


def _tile_cost(game_map: PathCostMap, fx, fy, tx, ty, mode):
    if (not game_map.valid(fx, fy) or not game_map.valid(tx, ty)
            or ty >= game_map.map_width):
        return 0
    source_floor = game_map.base_elevation(fx, fy)
    destination_floor = game_map.base_elevation(tx, ty)
    difference = abs(source_floor - destination_floor)
    if difference > (2 if mode == 'mech' else 1):
        return 0
    terrain = game_map.rterrain(tx, ty)
    return _destination_cost(terrain, destination_floor, difference, mode)


def _destination_cost(terrain, destination_floor, difference, mode):
    """Price destination terrain after the coordinate and elevation gates."""
    if terrain == WATER:
        if mode == 'hover':
            return 1
        if mode == 'tracked' or destination_floor != 0:
            return 0
    if terrain == HEAVY_FOREST and mode != 'mech':
        return 0
    surcharge = {LIGHT_FOREST: 1, ROUGH: 1, HEAVY_FOREST: 2, MOUNTAINS: 2}
    return 1 + difference + surcharge.get(terrain, 0)


def mech_tile_cost(game_map: PathCostMap, fx: int, fy: int, tx: int, ty: int) -> int:
    """MechTileCost: at most two floor levels; no nonzero-depth water."""
    return _tile_cost(game_map, fx, fy, tx, ty, 'mech')


def hover_tank_tile_cost(game_map: PathCostMap, fx: int, fy: int, tx: int, ty: int) -> int:
    """HoverTankTileCost: at most one floor level, then water costs one."""
    return _tile_cost(game_map, fx, fy, tx, ty, 'hover')


def tracked_tank_tile_cost(game_map: PathCostMap, fx: int, fy: int, tx: int, ty: int) -> int:
    """TrackedTankTileCost: at most one floor level; no water/heavy forest."""
    return _tile_cost(game_map, fx, fy, tx, ty, 'tracked')
