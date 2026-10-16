# Construction catalog 01 - mech reference prefix; Construction catalog 02 - unbranded forms; Construction catalog 03 - brand generation and fallback; Construction catalog 04 - exact lookups and cursors; Construction catalog 05 - packed names; Construction catalog 06 - helper literal arithmetic; Construction catalog 07 - catalog user errors
Feature: Construction catalog
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction catalog 01 - mech reference prefix
    When reference <reference> is identified with the source ordered table
    Then its inferred name is <name>
    Examples:
      | reference | name |
      | AS7-D | Atlas |
      | as7-D | none |
      | MAD-3R | Marauder |
      | Mad-Prime | MadCat |
      | CHP-W5 | Champion |
      | HCT-3F | Hatchetman |
      | Thor | Thor- |
      | Tho-A | Thor |
      | CRK5003-1 | Crockett |
      | CRK_5003-2 | Katana |
      | CRK5003-2 | none |
      | F-100A | Riever |
      | F-10A | Cheetah |
      | BEN1-A | none |
      | unknown | none |

  Scenario Outline: Construction catalog 02 - unbranded forms
    Given source catalog parts policy is 1 with Clan support
    When the unbranded part <part> is formatted
    Then short long and very-long forms are <short> <long> and <vlong>
    Examples:
      | part | short | long | vlong |
      | IS.MediumLaser | ML | MediumLaser | IS.MediumLaser |
      | CL.ERLargeLaser | CLERLL | ERLargeLaser | CL.ERLargeLaser |
      | Ammo_IS.AC/5 | A_AC5 | Ammo_AC/5 | Ammo_IS.AC/5 |
      | HeatSink | HS | HeatSink | HeatSink |
      | ShoulderOrHip | SOH | ShoulderOrHip | ShoulderOrHip |
      | Bomb_10_Standard | B_10_S | Bomb_10_Standard | Bomb_10_Standard |
      | empty | none | none | none |
      | Ammo_IS.MediumLaser | none | none | none |

  Scenario Outline: Construction catalog 03 - brand generation and fallback
    Given source catalog parts policy is <parts> with Clan support
    When part <part> requests brand <brand>
    Then a generated branded entry is <entry> and get_parts_vlong_name returns <name>
    Examples:
      | parts | part | brand | entry | name |
      | 1 | IS.MediumLaser | 1 | 1 | Lords.IS.MediumLaser |
      | 1 | IS.MediumLaser | 3 | 1 | Martell.IS.MediumLaser |
      | 1 | CL.ERLargeLaser | 3 | 0 | CL.ERLargeLaser |
      | 0 | IS.MediumLaser | 3 | 0 | IS.MediumLaser |
      | 1 | HeatSink | 3 | 0 | HeatSink |
      | 1 | Ammo_IS.AC/5 | 2 | 0 | Ammo_IS.AC/5 |

  Scenario Outline: Construction catalog 04 - exact lookups and cursors
    Given the catalog is initialized and the lookup cursor is <cursor>
    When <form> lookup requests <query>
    Then lookup success is <success> and the matched base part is <part>
    Examples:
      | cursor | form | query | success | part |
      | -1 | vlong | is.mediumlaser | 1 | IS.MediumLaser |
      | -1 | vlong | IS.* | 0 | none |
      | 0 | vlong | IS.MediumLaser | 0 | none |
      | -1 | short | ml | 1 | IS.MediumLaser |
      | 0 | short | ML | 0 | none |
      | -1 | short | M* | 0 | none |
      | -1 | long | MediumLas?r | 1 | IS.MediumLaser |
      | -1 | vlong | HeatSink | 1 | HeatSink |

  Scenario Outline: Construction catalog 05 - packed names
    Given the source catalog is initialized
    When packed part <id> is requested with name selector <selector>
    Then catalog text is <text>
    Examples:
      | id | selector | text |
      | 403 | v | HeatSink |
      | 403 | S | HS |
      | 1427 | v | INVALID_PART_NUMBER |
      | -1 | v | INVALID_PART_NUMBER |
      | 6144 | v | INVALID_PART_NUMBER |
      | 403 | x | INVALID_NAME_TYPE |
      | 0 | v | INVALID_PART_NUMBER |

  Scenario Outline: Construction catalog 06 - helper literal arithmetic
    When source helper <helper> resolves <text>
    Then its numeric result is <value>
    Examples:
      | helper | text | value |
      | WeaponIFromString | CL.A-Pod | 1 |
      | WeaponIFromString | CL.StreakSRM-2 | 2 |
      | AmmoIFromString | Ammo_CL.StreakSRM-2 | 102 |
      | AmmoIFromString | CL.StreakSRM-2 | -1 |
      | FindSpecialItemCodeFromString | HeatSink | 9 |
      | FindSpecialItemCodeFromString | IS.MediumLaser | -1 |
      | WeaponIndexFromString | HeatSink | -1 |
      | WeaponIndexFromString | CL.StreakSRM-2 | 1 |

  Scenario Outline: Construction catalog 07 - catalog user errors
    Given caller wizard is <wizard>
    When catalog command <command> receives <argument>
    Then the result is <result>
    Examples:
      | wizard | command | argument | result |
      | 0 | btpartmatch | HeatSink | PERMISSION_DENIED |
      | 0 | btpartname | 403/v | PERMISSION_DENIED |
      | 1 | btpartmatch | no-such-part | INVALID_PARTNAME |
      | 1 | btpartname | abc/v | INVALID_PART_NUMBER |
      | 1 | btpartname | 403suffix/v | HeatSink |
      | 1 | btpartname | 403/long | HeatSink |
