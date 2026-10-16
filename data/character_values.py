# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btechstats.c
#   btech/src/btech/btechstats.h

"""Ordered btechstats.h character values and source short-name collision policy.

Translated from BTMux, copyright 1996 Markus Stenberg, 1998-2002 Thomas
Wouters, 2000-2002 Cord Awtry, 1999-2005 Kevin Stevens.
"""
from dataclasses import dataclass

VALUE, SKILL, ADVANTAGE, ATTRIBUTE = range(4)
ATHLETIC, MENTAL, PHYSICAL, SOCIAL, SK_XP = 1, 2, 4, 8, 0x4000
XP_MAX = 16777216

@dataclass(frozen=True)
class CharacterValue:
    name: str
    type: int
    flags: int
    threshold: int
    short: str

VALUES = tuple(CharacterValue(*row) for row in (
    ('XP', 0, 0, 0, 'XP'),
    ('MaxXP', 0, 0, 0, 'MaxXPP'),
    ('Type', 0, 0, 0, 'Type'),
    ('Level', 0, 0, 0, 'Level'),
    ('Package', 0, 0, 0, 'Packa'),
    ('Lives', 0, 0, 0, 'Lives'),
    ('Bruise', 0, 0, 0, 'Bruis'),
    ('Lethal', 0, 0, 0, 'Letha'),
    ('Unused1', 0, 0, 0, 'Unuse'),
    ('ShotsFired', 0, 0, 0, 'ShoFir'),
    ('ShotsMissed', 0, 0, 0, 'ShoMis'),
    ('ShotsHit', 0, 0, 0, 'ShoHit'),
    ('DamageTaken', 0, 0, 0, 'DamTak'),
    ('DamageGiven', 0, 0, 0, 'DamGiv'),
    ('Ambidextrous', 2, 1, 0, 'Ambid'),
    ('Bloodname', 2, 1, 0, 'Blood'),
    ('Combat_Sense', 2, 1, 0, 'ComSen'),
    ('Contact', 2, 0, 0, 'Conta'),
    ('Dropship', 2, 0, 0, 'Drops'),
    ('EI_Implant', 2, 1, 0, 'EI_I_IImp'),
    ('Exceptional_Attribute', 2, 2, 0, 'ExcAtt'),
    ('Extra_Edge', 2, 0, 0, 'ExtEdg'),
    ('Land_Grant', 2, 0, 0, 'LanGra'),
    ('Reputation', 2, 1, 0, 'Reput'),
    ('Sixth_Sense', 2, 1, 0, 'SixSen'),
    ('Title', 2, 0, 0, 'Title'),
    ('Toughness', 2, 1, 0, 'Tough'),
    ('Wealth', 2, 0, 0, 'Wealt'),
    ('Well-Connected', 2, 0, 0, 'WelCon'),
    ('Well_Equipped', 2, 0, 0, 'WelEqu'),
    ('Dodge_Maneuver', 2, 1, 0, 'DodMan'),
    ('Maneuvering_Ace', 2, 1, 0, 'ManAce'),
    ('Melee_Specialist', 2, 1, 0, 'MelSpe'),
    ('Pain_Resistance', 2, 1, 0, 'PaiRes'),
    ('Speed_Demon', 2, 1, 0, 'SpeDem'),
    ('Tech_Aptitude', 2, 1, 0, 'TecApt'),
    ('Build', 3, 0, 0, 'Build'),
    ('Reflexes', 3, 0, 0, 'Refle'),
    ('Intuition', 3, 0, 0, 'Intui'),
    ('Learn', 3, 0, 0, 'Learn'),
    ('Charisma', 3, 0, 0, 'Chari'),
    ('Acrobatics', 1, 1, 50, 'Acrob'),
    ('Administration', 1, 2, 50, 'Admin'),
    ('Alternate_Identity', 1, 2, 50, 'AltIde'),
    ('Appraisal', 1, 2, 50, 'Appra'),
    ('Archery', 1, 1, 50, 'Arche'),
    ('Blade', 1, 2049, 50, 'Blade'),
    ('Bureaucracy', 1, 2056, 50, 'Burea'),
    ('Climbing', 1, 1, 50, 'Climb'),
    ('Comm-Conventional', 1, 1538, 150, 'ComCon'),
    ('Comm-Hyperpulse', 1, 1538, 50, 'ComHyp'),
    ('Computer', 1, 1538, 50, 'Compu'),
    ('Cryptography', 1, 1538, 50, 'Crypt'),
    ('Demolitions', 1, 2, 50, 'Demol'),
    ('Disguise', 1, 8194, 50, 'Disgu'),
    ('Drive', 1, 20, 3000, 'Drive'),
    ('Drive-Naval', 1, 4, 3000, 'DriNav'),
    ('Engineering', 1, 1538, 50, 'Engin'),
    ('Escape_Artist', 1, 8196, 50, 'EscArt'),
    ('Forgery', 1, 2, 50, 'Forge'),
    ('Gambling', 1, 2, 50, 'Gambl'),
    ('Gunnery-Aerospace', 1, 16452, 1000, 'GunAer'),
    ('Gunnery-Artillery', 1, 16516, 500, 'GunArt'),
    ('Gunnery-Battlemech', 1, 16420, 3000, 'GunBat'),
    ('Gunnery-BSuit', 1, 16388, 500, 'GunBSuSui'),
    ('Gunnery-Conventional', 1, 16404, 3000, 'GunCon'),
    ('Gunnery-Spacecraft', 1, 16644, 50, 'GunSpa'),
    ('Gunnery-Spotting', 1, 132, 50, 'GunSpo'),
    ('Gunnery-Ballistic', 1, 16388, 2500, 'GunBal'),
    ('Gunnery-Flamer', 1, 16388, 500, 'GunFla'),
    ('Gunnery-Laser', 1, 16388, 2500, 'GunLas'),
    ('Gunnery-Missile', 1, 16388, 2500, 'GunMis'),
    ('Impersonation', 1, 8, 50, 'Imper'),
    ('Interrogation', 1, 8200, 50, 'Inter'),
    ('Jump_Pack', 1, 1, 50, 'JumPac'),
    ('Leadership', 1, 4104, 50, 'Leade'),
    ('Medtech', 1, 2050, 300, 'Medte'),
    ('Navigation', 1, 2, 25, 'Navig'),
    ('Negotiation', 1, 8, 25, 'Negot'),
    ('Perception', 1, 8194, 150, 'Perce'),
    ('Piloting-Aerospace', 1, 16452, 2500, 'PilAer'),
    ('Piloting-Battlemech', 1, 16420, 3000, 'PilBat'),
    ('Piloting-BSuit', 1, 16385, 3000, 'PilBSuSui'),
    ('Piloting-Spacecraft', 1, 16644, 50, 'PilSpa'),
    ('Piloting-Biped', 1, 16420, 3000, 'PilBip'),
    ('Piloting-Hover', 1, 16404, 3000, 'PilHov'),
    ('Piloting-Naval', 1, 16404, 3000, 'PilNav'),
    ('Piloting-Quad', 1, 16420, 3000, 'PilQua'),
    ('Piloting-Tracked', 1, 16404, 3000, 'PilTra'),
    ('Piloting-Wheeled', 1, 16404, 3000, 'PilWhe'),
    ('Protocol', 1, 8, 50, 'Proto'),
    ('Quickdraw', 1, 4, 50, 'Quick'),
    ('Research', 1, 1538, 100, 'Resea'),
    ('Running', 1, 16385, 100, 'Runni'),
    ('Riding', 1, 1, 50, 'Ridin'),
    ('Scrounge', 1, 1544, 50, 'Scrou'),
    ('Security_Systems', 1, 8194, 50, 'SecSys'),
    ('Seduction', 1, 8, 50, 'Seduc'),
    ('Small_Arms', 1, 2052, 50, 'SmaArm'),
    ('Stealth', 1, 8196, 50, 'Steal'),
    ('Strategy', 1, 4098, 50, 'Strat'),
    ('Streetwise', 1, 8, 50, 'Stree'),
    ('Support_Weapons', 1, 2052, 50, 'SupWea'),
    ('Survival', 1, 2, 50, 'Survi'),
    ('Swimming', 1, 1, 50, 'Swimm'),
    ('Tactics', 1, 4098, 50, 'Tacti'),
    ('Technician-Aerospace', 1, 17410, 50, 'TecAer'),
    ('Technician-Battlemech', 1, 16898, 600, 'TecBat'),
    ('Technician-Battlesuit', 1, 16386, 300, 'TecBat'),
    ('Technician-Electronics', 1, 17922, 50, 'TecEle'),
    ('Technician-Mechanic', 1, 17410, 400, 'TecMec'),
    ('Technician-Weapons', 1, 17922, 300, 'TecWea'),
    ('Technician-Spacecraft', 1, 16386, 300, 'TecSpa'),
    ('Throwing_Weapons', 1, 4, 50, 'ThrWea'),
    ('Tinker', 1, 1538, 50, 'Tinke'),
    ('Tracking', 1, 8194, 50, 'Track'),
    ('Training', 1, 8, 50, 'Train'),
    ('Unarmed_Combat', 1, 2049, 50, 'UnaCom'),
    ('Zero-G_Operations', 1, 4, 50, 'ZerG_OOpe'),
))
FULL_NAMES = {row.name.lower(): i for i,row in enumerate(VALUES)}
SHORT_NAMES = {}
for i,row in enumerate(VALUES):
    SHORT_NAMES.setdefault(row.short.lower(), i)  # rbtab hashadd keeps first.

def code(name):
    if isinstance(name,int):
        if name >= len(VALUES): raise ValueError('Character value index out of bounds')
        return name
    key=name.lower()
    return FULL_NAMES.get(key,SHORT_NAMES.get(key,-1))
