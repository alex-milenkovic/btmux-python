# Combat boosters 01 - activation and regeneration; Combat boosters 02 - movement profile counters; Combat boosters 03 - MASC failure damage; Combat boosters 04 - stopped callback still increments
Feature: Combat boosters
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat boosters 01 - activation and regeneration
    Given MASC tech with desired speed 30 and counter 0
    When MASC turns on and first failure roll is 12 then turns off at tick 2
    Then desired speed is 30 MASC is off and counter at tick <tick> is <counter>
    Examples:
      | tick | counter |
      | 61 | 1 |
      | 62 | 0 |
      | 122 | 0 |

  Scenario Outline: Combat boosters 02 - movement profile counters
    Given both booster counters zero and <equipment> enabled with a failure event due now
    When booster failure roll is 12
    Then MASC counter is 1 supercharger counter is 0 and next event is due in 60
    Examples:
      | equipment |
      | MASC |
      | supercharger |

  Scenario Outline: Combat boosters 03 - MASC failure damage
    Given a <chassis> with MASC enabled and speed <speed>
    When first MASC failure roll is 2
    Then MASC tech is lost all speeds are zero damaged hip slots are <hips> and fall occurs <fall>
    Examples:
      | chassis | speed | hips | fall |
      | biped | 10.75 | 2 | 0 |
      | biped | 10.76 | 2 | 1 |
      | quad | 0 | 4 | 0 |

  Scenario Outline: Combat boosters 04 - stopped callback still increments
    Given a stopped MASC unit with counter <initial> and an already pending failure event
    When that event runs with roll 2
    Then counter is <final> MASC tech remains and no next failure event exists
    Examples:
      | initial | final |
      | 0 | 1 |
      | 2 | 3 |
