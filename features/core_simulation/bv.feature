# Core bv 01 - new defensive movement components; Core bv 02 - new offensive heat capacity; Core bv 03 - legacy cache boundary
Feature: Core bv
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core bv 01 - new defensive movement components
    Given a MECH with current armor 100 internal 50 tons 50 standard engine and no parts or jump
    When defensive BV uses running MP <mp>
    Then defensive BV is <bv>
    Examples:
      | mp | bv |
      | 2 | 350 |
      | 3 | 385 |
      | 5 | 420 |
      | 7 | 455 |
      | 10 | 490 |
      | 18 | 525 |
      | 25 | 560 |

  Scenario Outline: Core bv 02 - new offensive heat capacity
    Given a 50-ton MECH with no jump and <sinks> active sinks and weapons of BV 101 and 80 each heat 5
    When new offensive BV is calculated
    Then offensive BV is <bv>
    Examples:
      | sinks | bv |
      | 0 | 140 |
      | 1 | 191 |
      | 6 | 231 |

  Scenario Outline: Core bv 03 - legacy cache boundary
    Given legacy BV cache value 777 last checked at tick 0 and a zero-speed empty 50-ton unit with skills 4 and 5
    When CalculateBV receives both skill sentinels 100 at tick <tick>
    Then result is <result> and BVLast is <last>
    Examples:
      | tick | result | last |
      | 29 | 777 | 0 |
      | 30 | 50 | 30 |
