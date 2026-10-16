"""Physics simulation - hex math, movement."""

from .hexmath import (
    SCALEMAP, HEXLEVEL, ZSCALE,
    hex_to_float, float_to_hex,
    find_components, find_bearing, find_range,
    hex_bearing, hex_distance, hex_distance_int,
    normalize_heading, heading_difference, turn_direction,
)

from .movement import (
    MOVE_TICK, MOVE_MOD,
    MP1, MP2, MP3, MP4, MP5, KPH_PER_MP,
    calculate_turn_rate, update_heading,
    calculate_effective_max_speed, calculate_heat_speed_reduction, update_speed,
    move_mech, check_hex_crossing, on_hex_entered,
    update_movement,
    movement_periodic, register_movement_system,
)
