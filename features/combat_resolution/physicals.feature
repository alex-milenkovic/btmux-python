# Combat physical attacks 01 - damage order; Combat physical attacks 02 - strict physical range; Combat physical attacks 03 - source location fallthrough
Feature: Combat physical attacks
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat physical attacks 01 - damage order
    Given a 55-ton attacker with intact actuators and heat <heat> and TSM installed
    When physical damage diagnostic resolves <attack> with glance <glance>
    Then direct damage is <damage>
    Examples:
      | heat | attack | glance | damage |
      | 8 | punch | 0 | 5 |
      | 9 | punch | 0 | 10 |
      | 9 | punch | 1 | 5 |
      | 9 | saw | 0 | 7 |
      | 9 | saw | 1 | 4 |
      | 8 | sword | 0 | 7 |
      | 9 | sword | 0 | 14 |
      | 8 | claw | 0 | 7 |

  Scenario Outline: Combat physical attacks 02 - strict physical range
    Given a ready legal physical attack against <target>
    When distance is <range>
    Then range eligibility is <eligible>
    Examples:
      | target | range | eligible |
      | MECH | 0.99 | accepted |
      | MECH | 1 | rejected |
      | BA | 0.49 | accepted |
      | BA | 0.5 | rejected |
      | MW | 0.5 | rejected |

  Scenario Outline: Combat physical attacks 03 - source location fallthrough
    Given a ready attacker and armored target behind it
    When physical damage diagnostic resolves <attack> with glance 0
    Then hit location is 0 rear is false and location draws consumed are 0
    Examples:
      | attack |
      | saw |
      | claw |
