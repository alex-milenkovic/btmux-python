# Maps links 01 - entrance coordinate parsing; Maps links 02 - landing zone boundaries; Maps links 03 - linked state
Feature: Maps links
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps links 01 - entrance coordinate parsing
    Given a map has width 9 and height 7
    When direction <direction> uses coordinate input <input>
    Then parse outcome is <result> and coordinates are <xy>
    Examples:
      | direction | input | result | xy |
      | north | 0 | success | 4,0 |
      | east | 2 | success | 6,3 |
      | south | 2 | success | 4,4 |
      | west | 99 | success | 8,3 |
      | north | -1 | failure | unset |
      | north | 99,-2 | success | 99,-2 |
      | west | abc | success | 0,3 |
      | south | 1,x | failure | 1,unset |

  Scenario Outline: Maps links 02 - landing zone boundaries
    Given a block at the tested landing hex has radius <radius> and exempt team <team>
    When a team 2 unit tests landing at that same hex
    Then blocked is <blocked>
    Examples:
      | radius | team | blocked |
      | 0 | 0 | true |
      | 0 | 2 | false |
      | 0 | 3 | true |
      | -1 | 0 | false |
      | 3 | 0 | true |

  Scenario Outline: Maps links 03 - linked state
    Given a valid map starts without LINKED objects
    When the linked command sequence is <sequence>
    Then the linked query is <linked> and LINKED count is <count>
    Examples:
      | sequence | linked | count |
      | query | false | 0 |
      | set | true | 1 |
      | set,set | true | 2 |
      | set,delete-type | false | 0 |
