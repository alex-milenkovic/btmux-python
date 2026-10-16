# Construction loading 01 - basename and field normalization; Construction loading 02 - ordered fuel fields; Construction loading 03 - default electronics; Construction loading 04 - ammo capacity normalization; Construction loading 05 - invalid values with defined source behavior; Construction loading 06 - critical range copies
Feature: Construction loading
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction loading 01 - basename and field normalization
    Given a zeroed unit loads a modern file named <filename> containing Reference <reference> Unit_Era <era> and Unit_TRO <tro>
    When loading succeeds
    Then stored reference era and TRO are <stored> <out_era> and <out_tro>
    Examples:
      | filename | reference | era | tro | stored | out_era | out_tro |
      | AS7-D | AS7-D | 3050 | TRO3050 | AS7-D | 3050 | TRO3050 |
      | AS7-D | wrong | X | Y | AS7-D | Undefined | Undefined |
      | abcdefghijklmnopqrstuvwxy | ignored | empty | empty | abcdefghijklmnopqrstuvwx | Undefined | Undefined |

  Scenario Outline: Construction loading 02 - ordered fuel fields
    Given a zeroed unit loads a modern template containing <sequence>
    When loading finishes
    Then current and original fuel both equal <fuel>
    Examples:
      | sequence | fuel |
      | Type:AeroFighter | 2400 |
      | Fuel:100,Type:AeroFighter | 2400 |
      | Type:AeroFighter,Fuel:100 | 100 |
      | Type:VTOL | 4000 |
      | Type:Mech | 0 |

  Scenario Outline: Construction loading 03 - default electronics
    Given a zeroed non-mech template has source Clan flag <clan_flag> and item <item> with computer <computer> radio <radio> and scan <scan>
    When modern load finalization runs
    Then computer radio scan tac lrs radio_range and radio_type are <c> <r> <s> <t> <l> <rr> and <rt>
    Examples:
      | clan_flag | item | computer | radio | scan | c | r | s | t | l | rr | rt |
      | 0 | IS.MediumLaser | 0 | 0 | 0 | 2 | 3 | 20 | 20 | 40 | 100 | 5 |
      | 1 | IS.MediumLaser | 0 | 0 | 0 | 2 | 3 | 20 | 20 | 40 | 100 | 5 |
      | 0 | CL.ERLargeLaser | 0 | 0 | 0 | 5 | 5 | 35 | 35 | 70 | 140 | 27 |
      | 0 | CL.ERLargeLaser | 2 | 3 | 7 | 2 | 3 | 7 | 20 | 40 | 100 | 21 |

  Scenario Outline: Construction loading 04 - ammo capacity normalization
    Given a modern <unit> template has an AC5 ammo slot with quantity <quantity> and mode <mode>
    When that slot is loaded
    Then rounds are <rounds> and halfton is <half>
    Examples:
      | unit | quantity | mode | rounds | half |
      | Mech | 20 | - | 20 | 0 |
      | Mech | 10 | - | 10 | 1 |
      | Mech | 5 | - | 10 | 1 |
      | Mech | 15 | - | 20 | 0 |
      | Mech | 30 | - | 20 | 0 |
      | Mech | 0 | - | 10 | 1 |
      | Battlesuit | 5 | - | 5 | 1 |
      | Mechwarrior | 15 | - | 15 | 0 |
      | Mech | 10 | AP | 10 | 0 |

  Scenario Outline: Construction loading 05 - invalid values with defined source behavior
    Given a zeroed unit loads modern field <field> with value <value>
    When that field is applied
    Then the field outcome is <outcome>
    Examples:
      | field | value | outcome |
      | Specials | unknown | unchanged-no-error |
      | Specials | Clan~AngelECM_Tech | both-flags-set |
      | InfantrySpecials | unknown | unchanged-no-error |
      | Config | Case~Destroyed | zero |
      | Type | unknown | error |
      | Move_Type | unknown | error |
      | Tons | 50suffix | 50 |
      | Tons | nonsense | 0 |
      | CRIT_13 | HeatSink~-~-~- | safe-bounds-error |

  Scenario Outline: Construction loading 06 - critical range copies
    Given a modern file defines <range> as HeatSink data7 brand3 with parts enabled
    When the critical range loads
    Then one-based slots holding HeatSink data7 brand3 are <slots>
    Examples:
      | range | slots |
      | CRIT_1 | 1 |
      | CRIT_1-3 | 1,2,3 |
      | CRIT_12 | 12 |
      | CRIT_4-5 | 4,5 |
