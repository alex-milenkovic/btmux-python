# Construction saving 01 - location serialization; Construction saving 02 - critical grouping; Construction saving 03 - vehicle exclusions; Construction saving 04 - save uses design and capacity; Construction saving 05 - technology output filters
Feature: Construction saving
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction saving 01 - location serialization
    Given a template section has original armor <armor> internal <internal> rear <rear> and current values1 with config Case
    When modern locations are saved
    Then emitted armor internal rear and config are <out_armor> <out_internal> <out_rear> and <config>
    Examples:
      | armor | internal | rear | out_armor | out_internal | out_rear | config |
      | 10 | 8 | 4 | 10 | 8 | 4 | omitted |
      | 0 | 8 | 0 | omitted | 8 | omitted | omitted |
      | 10 | 0 | 4 | section-omitted | section-omitted | section-omitted | section-omitted |

  Scenario Outline: Construction saving 02 - critical grouping
    Given a source mech has <count> adjacent identical <part> slots with data0 mode0 and brand0
    When dump_item begins at one-based slot1
    Then its run length is <run>
    Examples:
      | count | part | run |
      | 3 | HeatSink | 3 |
      | 12 | HeatSink | 12 |
      | 3 | IS.MediumLaser | 1 |
      | 6 | IS.PPC | 3 |
      | 1 | empty | 1 |

  Scenario Outline: Construction saving 03 - vehicle exclusions
    Given a non-mech section contains part <part>
    When modern locations are saved
    Then the item is <result>
    Examples:
      | part | result |
      | ShoulderOrHip | omitted |
      | UpperActuator | omitted |
      | LowerActuator | omitted |
      | HandOrFootActuator | omitted |
      | Engine | omitted |
      | Gyro | omitted |
      | JumpJet | omitted |
      | HeatSink | emitted |
      | IS.MediumLaser | emitted |

  Scenario Outline: Construction saving 04 - save uses design and capacity
    Given a unit has original front armor20 current front armor7 and an AC5 ammo slot with remaining <remaining> and halfton <half>
    When modern and legacy saves are read
    Then modern armor and rounds are20 and <modern_rounds> while legacy armor and rounds are7 and <legacy_rounds>
    Examples:
      | remaining | half | modern_rounds | legacy_rounds |
      | 3 | 0 | 20 | 3 |
      | 0 | 0 | 20 | 0 |
      | 3 | 1 | 10 | 3 |

  Scenario Outline: Construction saving 05 - technology output filters
    Given a Mech carries only special flag <tech>
    When modern template specials are saved
    Then that flag is <result>
    Examples:
      | tech | result |
      | CL_AMS | omitted |
      | IS_AMS | omitted |
      | SS_Ability | omitted |
      | BeagleProbe | omitted |
      | TripleMyomerTech | omitted |
      | Masc | omitted |
      | ECM | omitted |
      | C3SlaveTech | omitted |
      | C3MasterTech | omitted |
      | ArtemisIV | omitted |
      | EndoSteel_Tech | omitted |
      | FerroFibrous_Tech | omitted |
      | LightBAP | omitted |
      | XLEngine_Tech | omitted |
      | XXL_Tech | omitted |
      | CompactEngine_Tech | omitted |
      | LightEngine_Tech | omitted |
      | AngelECM_Tech | omitted |
      | TargComp_Tech | omitted |
      | Clan | emitted |
      | DoubleHS | emitted |
      | ICEEngine_Tech | emitted |
      | SmallCockpit_Tech | emitted |
      | XLGyro_Tech | emitted |
