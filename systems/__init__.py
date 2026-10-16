"""Game systems - heat, combat."""

from systems.combat import (
    # Enums
    HitGroup,
    # Data structures
    AttackResult,
    BTHBreakdown,
    WeaponSlot,
    # Constants
    DEFAULT_GUNNERY,
    DEFAULT_PILOTING,
    BTH_PULSE_BONUS,
    BTH_HEAT_THRESHOLDS,
    # Dice rolling
    roll_1d6,
    roll_2d6,
    roll_dice,
    # BTH calculation
    calculate_bth,
    calculate_overheat_modifier,
    calculate_attacker_movement_modifier,
    calculate_target_movement_modifier,
    calculate_weapon_bth_modifier,
    # Hit location
    determine_hit_group,
    get_hit_location,
    get_punch_location,
    get_kick_location,
    MECH_HIT_LOCATIONS,
    PUNCH_HIT_LOCATIONS,
    KICK_HIT_LOCATIONS,
    TRANSFER_LOCATIONS,
    # Damage
    apply_damage_to_location,
    apply_damage_with_transfer,
    # Critical hits
    check_for_critical,
    roll_critical_hits,
    # Attack resolution
    resolve_attack,
    can_attack,
    estimate_hit_chance,
    # Weapon fire pipeline
    WEAPON_TICK,
    find_ammo_in_section,
    find_ammo_for_weapon,
    fire_weapon,
)

from systems.heat import (
    # Constants
    HEAT_TICK,
    TURN,
    WEAPON_RECYCLE_TIME,
    HEAT_WALKING,
    HEAT_RUNNING,
    HEAT_SPRINTING,
    HEAT_JUMP_MINIMUM,
    HEAT_FIRE_HEX,
    HEAT_STEALTH_ARMOR,
    HEAT_NULL_SIG,
    DEFAULT_HEAT_SINKS,
    MAX_LEG_SINKS_BONUS,
    INFERNO_SINK_PENALTY,
    SHUTDOWN_THRESHOLDS,
    AMMO_EXPLOSION_THRESHOLDS,
    AMMO_EXPLOSION_INFERNO_THRESHOLDS,
    PILOT_DAMAGE_THRESHOLD_1,
    PILOT_DAMAGE_THRESHOLD_2,
    HEAT_LEVEL_GREEN,
    HEAT_LEVEL_YELLOW,
    KPH_PER_MP,
    MP_PER_KPH,
    # Data structures
    HeatResult,
    # Utility functions
    roll_2d6,
    get_heat_indicator,
    is_running,
    # Heat calculation functions
    calculate_movement_heat,
    calculate_environment_heat,
    calculate_engine_heat,
    calculate_plus_heat,
    calculate_minus_heat,
    decay_weapon_heat,
    update_heat,
    # Overheat functions
    check_ammo_explosion,
    check_shutdown,
    check_pilot_damage,
    check_overheat,
    apply_shutdown,
    full_heat_update,
    # Game loop integration
    heat_periodic,
    register_heat_system,
)

__all__ = [
    # Combat - Enums
    'HitGroup',
    # Combat - Data structures
    'AttackResult',
    'BTHBreakdown',
    'WeaponSlot',
    # Combat - Constants
    'DEFAULT_GUNNERY',
    'DEFAULT_PILOTING',
    'BTH_PULSE_BONUS',
    'BTH_HEAT_THRESHOLDS',
    # Combat - Dice rolling
    'roll_1d6',
    'roll_dice',
    # Combat - BTH calculation
    'calculate_bth',
    'calculate_overheat_modifier',
    'calculate_attacker_movement_modifier',
    'calculate_target_movement_modifier',
    'calculate_weapon_bth_modifier',
    # Combat - Hit location
    'determine_hit_group',
    'get_hit_location',
    'get_punch_location',
    'get_kick_location',
    'MECH_HIT_LOCATIONS',
    'PUNCH_HIT_LOCATIONS',
    'KICK_HIT_LOCATIONS',
    'TRANSFER_LOCATIONS',
    # Combat - Damage
    'apply_damage_to_location',
    'apply_damage_with_transfer',
    # Combat - Critical hits
    'check_for_critical',
    'roll_critical_hits',
    # Combat - Attack resolution
    'resolve_attack',
    'can_attack',
    'estimate_hit_chance',
    # Combat - Weapon fire pipeline
    'WEAPON_TICK',
    'find_ammo_in_section',
    'find_ammo_for_weapon',
    'fire_weapon',
    # Heat - Constants
    'HEAT_TICK',
    'TURN',
    'WEAPON_RECYCLE_TIME',
    'HEAT_WALKING',
    'HEAT_RUNNING',
    'HEAT_SPRINTING',
    'HEAT_JUMP_MINIMUM',
    'HEAT_FIRE_HEX',
    'HEAT_STEALTH_ARMOR',
    'HEAT_NULL_SIG',
    'DEFAULT_HEAT_SINKS',
    'MAX_LEG_SINKS_BONUS',
    'INFERNO_SINK_PENALTY',
    'SHUTDOWN_THRESHOLDS',
    'AMMO_EXPLOSION_THRESHOLDS',
    'AMMO_EXPLOSION_INFERNO_THRESHOLDS',
    'PILOT_DAMAGE_THRESHOLD_1',
    'PILOT_DAMAGE_THRESHOLD_2',
    'HEAT_LEVEL_GREEN',
    'HEAT_LEVEL_YELLOW',
    'KPH_PER_MP',
    'MP_PER_KPH',
    # Data structures
    'HeatResult',
    # Utility functions
    'roll_2d6',
    'get_heat_indicator',
    'is_running',
    # Heat calculation functions
    'calculate_movement_heat',
    'calculate_environment_heat',
    'calculate_engine_heat',
    'calculate_plus_heat',
    'calculate_minus_heat',
    'decay_weapon_heat',
    'update_heat',
    # Overheat functions
    'check_ammo_explosion',
    'check_shutdown',
    'check_pilot_damage',
    'check_overheat',
    'apply_shutdown',
    'full_heat_update',
    # Game loop integration
    'heat_periodic',
    'register_heat_system',
]
