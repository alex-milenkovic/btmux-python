# Ammunition dumping 01 - rate and clock phase; Ammunition dumping 02 - selection; Ammunition dumping 03 - lifecycle; Ammunition dumping 04 - command guards
Feature: Ammunition dumping
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Ammunition dumping 01 - rate and clock phase
    Given a functional bin with <rounds> rounds of ammunition rated <per_ton> rounds per ton
    And the event clock starts at <start_tick>
    When the pilot requests dump selector all
    And the engine advances <seconds> seconds
    Then the bin contains <remaining> rounds and dumping is <pending>
    Examples:
      | rounds | per_ton | start_tick | seconds | remaining | pending |
      | 3 | 5 | 0 | 1 | 3 | True |
      | 3 | 5 | 0 | 6 | 2 | True |
      | 3 | 5 | 5 | 1 | 2 | True |
      | 3 | 20 | 0 | 1 | 2 | True |
      | 3 | 30 | 0 | 1 | 2 | True |
      | 3 | 45 | 0 | 1 | 2 | True |
      | 3 | 60 | 0 | 1 | 1 | True |
      | 3 | 60 | 0 | 2 | 0 | False |
      | 1 | 60 | 0 | 1 | 0 | False |

  Scenario Outline: Ammunition dumping 02 - selection
    Given LT slot 1 holds weapon A ammo LT slot 2 holds weapon B ammo and RT slot 1 holds weapon A ammo
    And every bin contains 3 rounds rated 30 per ton and all bins are functional
    When the pilot requests dump selector <selector>
    And the engine advances 1 second
    Then LT slot 1 contains <left_a> LT slot 2 contains <left_b> and RT slot 1 contains <right_a> rounds
    Examples:
      | selector | left_a | left_b | right_a |
      | all | 2 | 2 | 2 |
      | LT | 2 | 2 | 3 |
      | LT 1 | 2 | 3 | 3 |
      | WEAPON_A | 2 | 3 | 2 |
      | WEAPON_B | 3 | 2 | 3 |
      | LT 13 | 2 | 2 | 3 |

  Scenario Outline: Ammunition dumping 03 - lifecycle
    Given a functional bin with 4 rounds of ammunition rated 30 rounds per ton
    When the pilot performs dump workflow <workflow> before advancing 2 seconds
    Then accepted dump commands number <accepted> the bin contains <remaining> rounds and dumping is <pending>
    Examples:
      | workflow | accepted | remaining | pending |
      | ALL | 1 | 2 | True |
      | ALL_STOP | 2 | 4 | False |
      | ALL_ALL | 1 | 2 | True |
      | BIN_ALL | 2 | 2 | True |
      | ALL_BIN | 1 | 2 | True |
      | ALL_SHUTDOWN | 1 | 4 | False |

  Scenario Outline: Ammunition dumping 04 - command guards
    Given a ready mech with maximum speed 64.5 KPH and ammo condition <condition>
    And desired speed is <speed> KPH and jumping is <jumping>
    When the pilot requests dump selector all
    Then the dump command is <outcome> and dumping is <pending>
    Examples:
      | condition | speed | jumping | outcome | pending |
      | LOADED | 43 | False | ACCEPTED | True |
      | LOADED | 44 | False | REJECTED | False |
      | LOADED | 0 | True | REJECTED | False |
      | EMPTY | 0 | False | REJECTED | False |
      | BROKEN_LOADED | 0 | False | ACCEPTED | True |
