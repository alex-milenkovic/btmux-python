# Combat death from above 01 - successful impact clustering; Combat death from above 02 - miss has no second fall packet; Combat death from above 03 - declined DFA allows landing
Feature: Combat death from above
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat death from above 01 - successful impact clustering
    Given an airborne attacker of nominal tons <nominal> actual tons <actual> and upright MECH target
    When landing DFA hits and both follow-up piloting rolls succeed
    Then target punch-table damage is <target> self kick-table damage is <self> and all six sections recycle for 30
    Examples:
      | nominal | actual | target | self |
      | 50 | 50 | 15 | 10 |
      | 55 | 55 | 17 | 11 |
      | 55 | 60 | 19 | 11 |
      | 60 | 55 | 16 | 12 |

  Scenario Outline: Combat death from above 02 - miss has no second fall packet
    Given a 55-ton attacker landing a DFA over ground elevation <floor>
    When DFA misses and injury piloting succeeds
    Then target damage is 0 self back-table damage is 11 attacker is prone and Z is <floor>
    Examples:
      | floor |
      | 0 |
      | -1 |

  Scenario Outline: Combat death from above 03 - declined DFA allows landing
    Given an attacker completing a DFA jump with condition <condition>
    When the landing callback runs
    Then DFA does not roll or damage and ordinary landing runs
    Examples:
      | condition |
      | target-on-different-map |
      | target-jumping |
      | arm-weapon-recycling |
      | leg-physical-recycling |
      | BTH-over-12 |
