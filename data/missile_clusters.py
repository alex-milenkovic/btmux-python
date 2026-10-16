# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/src/btech/weapons.h
# Historical Aerospace sources:
#   src/hcode/btech/weapons.h

"""Weapon-keyed MissileHitTable from the selected C references.

General: checked_in_pipeline_2026_09_15 weapons.h:501-583.
Historical Aerospace: pre-AT2 96f2131. Its MRM-30 data and downstream
incoming-count row selector differ; dictionary insertion order is source order.
"""

MISSILE_CLUSTER_ROWS = {
    'CL.LB10-XAC': (3, 3, 4, 6, 6, 6, 6, 8, 8, 10, 10),
    'CL.LB20-XAC': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'CL.LB2-XAC': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.LB5-XAC': (1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5),
    'CL.LRM-10': (3, 3, 4, 6, 6, 6, 6, 8, 8, 10, 10),
    'CL.LRM-15': (5, 5, 6, 9, 9, 9, 9, 12, 12, 15, 15),
    'CL.LRM-20': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'CL.StreakLRM-5': (1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5),
    'CL.StreakLRM-10': (3, 3, 4, 6, 6, 6, 6, 8, 8, 10, 10),
    'CL.StreakLRM-15': (5, 5, 6, 9, 9, 9, 9, 12, 12, 15, 15),
    'CL.StreakLRM-20': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'CL.LRM-5': (1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5),
    'CL.SRM-2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.SRM-4': (1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4),
    'CL.SRM-6': (2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6),
    'CL.StreakSRM-2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.StreakSRM-4': (1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4),
    'CL.StreakSRM-6': (2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6),
    'CL.ATM-3': (1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3),
    'CL.ATM-6': (2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6),
    'CL.ATM-9': (2, 2, 3, 4, 4, 5, 5, 6, 7, 8, 9),
    'CL.ATM-12': (4, 4, 6, 6, 8, 8, 8, 10, 10, 12, 12),
    'CL.UltraAC/10': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.UltraAC/20': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.UltraAC/2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.UltraAC/5': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.AC/2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.AC/5': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.AC/10': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'CL.AC/20': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.LRM-5': (1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5),
    'IS.LRM-10': (3, 4, 4, 5, 6, 6, 6, 8, 8, 10, 10),
    'IS.LRM-15': (5, 5, 9, 9, 9, 9, 9, 12, 12, 15, 15),
    'IS.LRM-20': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'IS.SRM-2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.SRM-4': (1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4),
    'IS.SRM-6': (2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6),
    'IS.StreakSRM-2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.StreakSRM-4': (1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4),
    'IS.StreakSRM-6': (2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6),
    'IS.LB20-XAC': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'IS.LB10-XAC': (3, 3, 4, 6, 6, 6, 6, 8, 8, 10, 10),
    'IS.LB2-XAC': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.LB5-XAC': (1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5),
    'IS.UltraAC/20': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.UltraAC/10': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.UltraAC/5': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.UltraAC/2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.AC/2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.AC/5': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.AC/10': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.AC/20': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.LightAC/2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.LightAC/5': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.Thunderbolt-5': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'IS.Thunderbolt-10': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'IS.Thunderbolt-15': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'IS.Thunderbolt-20': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'IS.ELRM-10': (3, 4, 4, 5, 6, 6, 6, 7, 7, 10, 10),
    'IS.ELRM-5': (1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5),
    'IS.ELRM-15': (5, 5, 9, 9, 9, 9, 12, 12, 12, 15, 15),
    'IS.ELRM-20': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'IS.LR_DFM-10': (3, 4, 4, 5, 6, 6, 6, 7, 7, 10, 10),
    'IS.LR_DFM-5': (1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5),
    'IS.LR_DFM-15': (5, 5, 9, 9, 9, 9, 12, 12, 12, 15, 15),
    'IS.LR_DFM-20': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'IS.SR_DFM-2': (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2),
    'IS.SR_DFM-4': (1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4),
    'IS.SR_DFM-6': (2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6),
    'IS.NarcBeacon': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'CL.NarcBeacon': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'IS.MRM-10': (2, 3, 4, 5, 6, 6, 6, 8, 8, 10, 10),
    'IS.MRM-20': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'IS.MRM-30': (10, 10, 12, 18, 18, 18, 18, 24, 24, 30, 30),
    'IS.MRM-40': (12, 12, 18, 24, 24, 24, 24, 32, 32, 40, 40),
    'IS.iNarcBeacon': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'IS.RL-10': (3, 4, 4, 5, 6, 6, 6, 8, 8, 10, 10),
    'IS.RL-15': (5, 5, 9, 9, 9, 9, 9, 12, 12, 15, 15),
    'IS.RL-20': (6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20),
    'IS.InfantrySRM': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    'IS.InfantryLRM': (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
}


HISTORICAL_MRM30_ROW = (10,14,16,18,18,18,20,24,28,30,30)
# STREAK bits from the recovered MechWeapons table. Some table candidates
# (the four Clan AC aliases) have no Python catalog entry but still participate.
STREAK_CLUSTER_WEAPONS = frozenset({
    'CL.StreakLRM-5', 'CL.StreakLRM-10', 'CL.StreakLRM-15', 'CL.StreakLRM-20',
    'CL.StreakSRM-2', 'CL.StreakSRM-4', 'CL.StreakSRM-6',
    'IS.StreakSRM-2', 'IS.StreakSRM-4', 'IS.StreakSRM-6',
})


def missile_row(weapon,unit=None,fire_mode=0):
    from entities.mech import FireMode,UnitType
    name=weapon.name
    if fire_mode&FireMode.RAC_MODES:
        count=2 if fire_mode&FireMode.RAC_TWOSHOT_MODE else 4 if fire_mode&FireMode.RAC_FOURSHOT_MODE else 6
        name=f'IS.SRM-{count}'
    if name=='IS.MRM-30' and unit is not None and unit.unit_type in (UnitType.AERO,UnitType.DS,UnitType.SPHEROID_DS):
        return HISTORICAL_MRM30_ROW
    return MISSILE_CLUSTER_ROWS.get(name)


def historical_hit_row(weapon, incoming):
    """Recovered MissileHitTarget selection, after the miss/pod/AMS stages.

    Equal maxima replace earlier rows unless this candidate is the fired
    weapon itself. Do not sort the source table or use a generic rack row.
    """
    from entities.weapon import WeaponFlags
    selected, maximum = None, 0
    streak = bool(weapon.special & WeaponFlags.STREAK)
    for name, row in MISSILE_CLUSTER_ROWS.items():
        count = row[10]
        if count <= incoming and (name in STREAK_CLUSTER_WEAPONS) == streak:
            if count >= maximum and (selected is None or name != weapon.name or count > maximum):
                selected = HISTORICAL_MRM30_ROW if name == 'IS.MRM-30' else row
                maximum = count
    return selected
