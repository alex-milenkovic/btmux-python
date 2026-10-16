# Pilot health 01 - IC consciousness thresholds
# Pilot health 02 - head and lethal health writes
# Pilot health 03 - damage gates and synchronization
# Pilot health 04 - recovery and repeat injury
Feature: Pilot health
  Background:
    Given an attached pilot with Build5 and ordinary simulation recovery events

  Scenario Outline: Pilot health 01 - IC consciousness thresholds
    Given bruise <bruise> and pain resistance <pain>
    When IC consciousness target is read
    Then target is <target>
    Examples:
      | bruise | pain | target |
      | 0 | 0 | 3 |
      | 10 | 0 | 3 |
      | 11 | 0 | 5 |
      | 20 | 0 | 5 |
      | 21 | 0 | 7 |
      | 30 | 0 | 7 |
      | 31 | 0 | 10 |
      | 40 | 0 | 10 |
      | 41 | 0 | 11 |
      | 51 | 0 | 11 |
      | 52 | 0 | 0 |
      | 10 | 1 | 2 |
      | 10 | 2 | 3 |

  Scenario Outline: Pilot health 02 - head and lethal health writes
    Given bruise <bruise> lethal <lethal> and initial pilot hits0
    When IC <kind> damage <damage> is applied with surviving consciousness rolls
    Then stored bruise is <outbruise> lethal is <outlethal> hits are <hits> and fatal is <fatal>
    Examples:
      | bruise | lethal | kind | damage | outbruise | outlethal | hits | fatal |
      | 0 | 0 | head | 1 | 10 | 0 | 1 | False |
      | 45 | 0 | head | 1 | 50 | 5 | 1 | False |
      | 45 | 45 | head | 1 | 50 | 49 | 0 | True |
      | 0 | 0 | lethal | 1 | 45 | 10 | 1 | False |
      | 0 | 0 | lethal | 20 | 45 | 40 | 20 | False |
      | 0 | 40 | lethal | 1 | 50 | 49 | 0 | True |

  Scenario Outline: Pilot health 03 - damage gates and synchronization
    Given pilot damage condition <condition>
    When damage or health synchronization occurs
    Then result is <result>
    Examples:
      | condition | result |
      | negative-unit-ID | no-health-hits-or-dice |
      | nonIC-initial-hits6 | destroy-once-clear-pilot-stop |
      | nonIC-hits5 | target10 |
      | fix-build5-bruise12-lethal8 | hits2 |
      | fix-build0-bruise12-lethal8 | hits2 |
      | fix-build51-bruise12-lethal8 | hits2 |
      | lethal-build0-damage1 | bruise10-lethal9-fatal |

  Scenario Outline: Pilot health 04 - recovery and repeat injury
    Given initial unconsciousness at time0 with recovery due30
    When <action> occurs
    Then next recovery is <due> and additional initial dice are 0
    Examples:
      | action | due |
      | nonfatal-injury-at10 | 30 |
      | failed-recovery-at30 | 60 |
      | explicit-prolong20-at10 | 50 |
      | successful-recovery-at30 | none |
