# Combat charge resolution 01 - one-sided charge formula; Combat charge resolution 02 - real movement contact; Combat charge resolution 03 - mutual damage asymmetry
Feature: Combat charge resolution
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat charge resolution 01 - one-sided charge formula
    Given a 50-ton actual-mass attacker at speed <speed> and stationary 50-ton enemy
    When old-charge damage is computed without melee advantage
    Then target damage is <damage> and self damage is 5
    Examples:
      | speed | damage |
      | 10.75 | 6 |
      | 21.5 | 12 |
      | 32.25 | 17 |

  Scenario Outline: Combat charge resolution 02 - real movement contact
    Given a valid charge selection by <selection> and a target in the next traversed hex
    When movement reaches charge contact with a successful attack and piloting rolls
    Then charge damage occurs once and attacker speed and charge target clear
    Examples:
      | selection |
      | default-lock |
      | explicit-contact |

  Scenario Outline: Combat charge resolution 03 - mutual damage asymmetry
    Given mutually charging actual masses 50 and 65 with both speeds one MP facing each other
    When both old-charge rolls hit and all piloting checks succeed
    Then first attack damage is 11 second attack damage is 7 and each side self damage is <firstself> and <secondself>
    Examples:
      | firstself | secondself |
      | 7 | 7 |
