# Combat targeting 01 - aim and lock parsing; Combat targeting 02 - sixth sense severity; Combat targeting 03 - delayed warning gates
Feature: Combat targeting
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat targeting 01 - aim and lock parsing
    Given a valid visible enemy MECH contact AB and a ready actor
    When the actor issues lock with text <text>
    Then target state is <state>
    Examples:
      | text | state |
      | AB | enemy-lock |
      | - | no-lock |
      | 3junk 4 | coordinates-3-4 |
      | 3 4 I | ignite-3-4 |
      | 3 4 C | clear-3-4 |
      | 3 4 H | hex-3-4 |
      | 3 4 B | building-3-4 |
      | 3 4 wrong | rejected-no-lock |

  Scenario Outline: Combat targeting 02 - sixth sense severity
    Given a sixth-sense target and attacker mass difference <tons> at range <range>
    When a lock succeeds with sixth-sense roll 8 and delay draw 2
    Then no warning appears at tick 1 and source warning index <index> appears at tick 2
    Examples:
      | tons | range | index |
      | -20 | 8 | 0 |
      | -19 | 8 | 1 |
      | 20 | 8 | 2 |
      | -20 | 9 | 3 |
      | 0 | 19.9 | 4 |
      | 20 | 20 | 8 |

  Scenario Outline: Combat targeting 03 - delayed warning gates
    Given a sixth-sense warning due at tick 2
    When target pilot state becomes <state> before tick 2
    Then the warning is <result>
    Examples:
      | state | result |
      | conscious-present | delivered |
      | unconscious | suppressed |
      | absent | suppressed |
