# Core weapons 01 - physical recycle and sight; Core weapons 02 - weapon run validation; Core weapons 03 - functional status thresholds; Core weapons 04 - lookup ordinal differs from critical
Feature: Core weapons
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core weapons 01 - physical recycle and sight
    Given a MECH weapon of category <category> with weapon data <data> section recycle <physical> and destroyed <destroyed>
    When weapon lookup uses sight <sight>
    Then lookup result code is <code>
    Examples:
      | category | data | physical | destroyed | sight | code |
      | beam | 1 | 0 | 0 | 0 | -4 |
      | missile | 1 | 0 | 0 | 0 | -3 |
      | beam | 0 | 1 | 0 | 0 | -5 |
      | beam | 1 | 1 | 0 | 1 | catalog |
      | beam | 0 | 0 | 1 | 1 | -2 |

  Scenario Outline: Core weapons 02 - weapon run validation
    Given a MECH catalog weapon requiring <required> crits and a contiguous run of <actual> matching slots
    When FindWeapons_Advanced inspects that section
    Then weapon count or failure is <count>
    Examples:
      | required | actual | count |
      | 3 | 3 | 1 |
      | 3 | 6 | 2 |
      | 3 | 2 | -1 |
      | 9 | 2 | 1 |

  Scenario Outline: Core weapons 03 - functional status thresholds
    Given a weapon run of <size> with destroyed slots <destroyed> and disabled slots <disabled>
    When WeaponIsNonfunctional is inspected
    Then functional status code is <code>
    Examples:
      | size | destroyed | disabled | code |
      | 1 | 0 | 0 | 0 |
      | 1 | 1 | 0 | 2 |
      | 6 | 1 | 0 | -1 |
      | 6 | 2 | 0 | -2 |
      | 6 | 3 | 0 | 2 |
      | 6 | 0 | 1 | 1 |
      | 3 | 1 | 0 | 2 |

  Scenario Outline: Core weapons 04 - lookup ordinal differs from critical
    Given the first weapon run begins at critical 3 and ordinal slot 0 is <state> while weapon critical 3 is ready
    When FindWeaponFromIndex searches that weapon type
    Then found result is <found> and returned critical is 3
    Examples:
      | state | found |
      | empty-ready | 1 |
      | empty-destroyed | 0 |
