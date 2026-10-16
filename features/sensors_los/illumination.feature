# Searchlight illumination 01 - switching; Searchlight illumination 02 - source predicate; Searchlight illumination 03 - retention
Feature: Searchlight illumination
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: Searchlight illumination 01 - switching
    Given a functional searchlight initially <initial>
    When the pilot requests slite twice and the engine advances <seconds> seconds
    Then searchlight on is <on> with transition pending <pending>
    And exactly one slite request was accepted
    Examples:
      | initial | seconds | on | pending |
      | False | 4 | False | True |
      | False | 5 | True | False |
      | True | 4 | True | True |
      | True | 5 | False | False |

  Scenario Outline: Searchlight illumination 02 - source predicate
    Given an on searchlight at range <range> and target arc <arc>
    And cached intervening woods are <woods> water hexes <water> and terrain blocked <block>
    When the unit illumination diagnostic evaluates the source
    Then the source qualifies <qualifies>
    Examples:
      | range | arc | woods | water | block | qualifies |
      | 30 | forward | 2 | 0 | False | True |
      | 30.01 | forward | 0 | 0 | False | False |
      | 29 | turret-only | 0 | 0 | False | False |
      | 29 | forward | 3 | 0 | False | False |
      | 29 | forward | 0 | 1 | False | False |
      | 29 | forward | 0 | 0 | True | False |

  Scenario Outline: Searchlight illumination 03 - retention
    Given an already illuminated target with warning preference <warn>
    And <sources> qualifying other light sources remain at range 30
    When the normal end-light update runs twice
    Then the target illuminated flag is <lit> and loss notification count is <messages>
    Examples:
      | warn | sources | lit | messages |
      | True | 1 | True | 0 |
      | True | 0 | False | 1 |
      | False | 0 | False | 0 |
