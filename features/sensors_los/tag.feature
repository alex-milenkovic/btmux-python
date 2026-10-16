# TAG designation 01 - range and stabilization; TAG designation 02 - stop and cooldown; TAG designation 03 - relationship ownership; TAG designation 04 - semiguided movement
Feature: TAG designation
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: TAG designation 01 - range and stabilization
    Given a functional TAG unit and an identified enemy at range <range>
    When the pilot tags that enemy and the engine advances <seconds> seconds
    Then the TAG command is <accepted> reciprocal relationship is <linked> and stable message count is <stable>
    And the TAG system is recycling <recycling>
    Examples:
      | range | seconds | accepted | linked | stable | recycling |
      | 15 | 29 | True | True | 0 | True |
      | 15 | 30 | True | True | 1 | False |
      | 15.01 | 30 | False | False | 0 | False |

  Scenario Outline: TAG designation 02 - stop and cooldown
    Given a TAG relationship started at time zero with its original target
    When at time <cancel_time> the pilot requests tag cancellation
    And the engine advances to time <time>
    Then cancellation is <accepted> reciprocal relationship is <linked> and the TAG system is recycling <recycling>
    And ready message count is <ready>
    Examples:
      | cancel_time | time | accepted | linked | recycling | ready |
      | 29 | 29 | False | True | True | 0 |
      | 30 | 59 | True | False | True | 0 |
      | 30 | 60 | True | False | False | 1 |

  Scenario Outline: TAG designation 03 - relationship ownership
    Given a stable TAG relationship to target t and another tagger b
    When the target change is <change> and normal TAG validation runs
    Then the original tagger remains linked <linked> and target tagged-by is <owner>
    And the original tagger has a cooldown pending <cooldown>
    Examples:
      | change | linked | owner | cooldown |
      | range-to-15 | True | original | False |
      | range-to-15.01 | False | none | True |
      | block-NB-LOS | False | none | True |
      | b-overwrites-tag | False | b | True |
      | target-removed | False | absent | True |

  Scenario Outline: TAG designation 04 - semiguided movement
    Given a target speed <speed> started <started> and tagged-by relation <tagger>
    When the shooter sights with ammunition <ammo>
    Then the applied target movement modifier is <applied>
    Examples:
      | speed | started | tagger | ammo | applied |
      | 75.25 | True | other-friendly | semiguided | 0 |
      | 0 | False | other-friendly | semiguided | -4 |
      | 75.25 | True | self | semiguided | 3 |
      | 75.25 | True | hostile | semiguided | 3 |
      | 75.25 | True | dangling-positive-ID | semiguided | 0 |
      | 75.25 | True | none | semiguided | 3 |
      | 75.25 | True | other-friendly | ordinary | 3 |
