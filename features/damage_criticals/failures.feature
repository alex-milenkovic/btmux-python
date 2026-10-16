# Damage equipment failures 01 - brand category and names; Damage equipment failures 02 - weapon reliability gates; Damage equipment failures 03 - weapon callback effects; Damage equipment failures 04 - six rerolls once; Damage equipment failures 05 - live firing ammo consumption
Feature: Damage equipment failures
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage equipment failures 01 - brand category and names
    Given a component category <category> and brand level <level>
    When brand information is requested
    Then category index is <index> and displayed brand is <brand>
    Examples:
      | category | level | index | brand |
      | energy | 1 | 0 | Lords |
      | energy | 2 | 0 | Hesperus |
      | autocannon | 3 | 6 | Oriente |
      | missile | 5 | 12 | Telos |
      | flamer | 1 | 18 | Pynes |
      | computer | 4 | 24 | Ares |
      | radio | 5 | 30 | Iriad |
      | energy | 0 | 0 | none |
      | PCOMBAT | 1 | -1 | none |

  Scenario Outline: Damage equipment failures 02 - weapon reliability gates
    Given a parts-enabled energy weapon with brand level <level>
    When weapon failure chance draw is <chance> reliability draw is <reliability> and outcome draw is one
    Then failure type is <failure>
    Examples:
      | level | chance | reliability | failure |
      | 1 | 8 | 100 | NONE |
      | 1 | 9 | 80 | NONE |
      | 1 | 9 | 81 | DAMAGE |
      | 2 | 10 | 81 | DAMAGE |
      | 3 | 10 | 90 | NONE |
      | 3 | 10 | 91 | DAMAGE |
      | 0 | 10 | 100 | NONE |

  Scenario Outline: Damage equipment failures 03 - weapon callback effects
    Given a failing <category> weapon with base damage 20 heat 10 and recycle zero
    When the final failure-table outcome is <outcome> and any duration draw is twenty
    Then failure type is <failure> modifier is <modifier> temporary state is <temporary> and recycle is <recycle>
    Examples:
      | category | outcome | failure | modifier | temporary | recycle |
      | energy | 1 | DAMAGE | 3 | NONE | 0 |
      | energy | 2 | DAMAGE | 6 | NONE | 0 |
      | energy | 3 | DAMAGE | 9 | NONE | 0 |
      | energy | 4 | HEAT | 3 | NONE | 0 |
      | energy | 5 | POWER_SPIKE | 0 | SHORTED | 20 |
      | energy | 6 | POWER_SPIKE | 0 | DESTROYED | 0 |
      | autocannon | 2 | WEAPON_DUD | 0 | DUD | 50 |
      | autocannon | 3 | WEAPON_JAMMED | 0 | JAMMED | 20 |
      | autocannon | 4 | HEAT | 2 | NONE | 0 |
      | autocannon | 5 | HEAT | 4 | NONE | 0 |
      | autocannon | 6 | WEAPON_DUD | 0 | DESTROYED | 50 |
      | missile | 1 | WEAPON_JAMMED | 0 | JAMMED | 20 |
      | missile | 2 | CRAZY_MISSILES | 20 | NONE | 0 |
      | missile | 3 | CRAZY_MISSILES | 40 | NONE | 0 |
      | missile | 4 | CRAZY_MISSILES | 100 | NONE | 0 |
      | missile | 5 | POWER_SPIKE | 0 | SHORTED | 20 |
      | missile | 6 | POWER_SPIKE | 0 | DESTROYED | 0 |
      | flamer | 1 | WEAPON_JAMMED | 0 | JAMMED | 20 |
      | flamer | 2 | POWER_SPIKE | 0 | SHORTED | 20 |
      | flamer | 3 | HEAT | 10 | NONE | 0 |
      | flamer | 4 | POWER_SPIKE | 0 | SHORTED | 20 |
      | flamer | 5 | WEAPON_JAMMED | 0 | JAMMED | 20 |
      | flamer | 6 | POWER_SPIKE | 0 | DESTROYED | 0 |

  Scenario Outline: Damage equipment failures 04 - six rerolls once
    Given a failing energy weapon with brand one base damage 20 and zero recycle
    When failure outcome draws are <draws>
    Then final failure type is <failure> and outcome draws consumed is <count>
    Examples:
      | draws | failure | count |
      | 1 | DAMAGE | 1 |
      | 6,1 | DAMAGE | 2 |
      | 6,6 | POWER_SPIKE | 2 |

  Scenario Outline: Damage equipment failures 05 - live firing ammo consumption
    Given a ready weapon with ten rounds and initial target armor 100
    When ordinary firing encounters brand failure <failure>
    Then rounds remaining are <rounds> target armor is <armor> and the shot aborted is <aborted>
    Examples:
      | failure | rounds | armor | aborted |
      | autocannon-dud | 9 | 100 | True |
      | autocannon-jam | 9 | 100 | True |
      | missile-spike | 10 | 100 | True |
      | autocannon-FAIL_NONE-dud | 9 | 95 | False |
