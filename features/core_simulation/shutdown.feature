# Core shutdown 01 - positive movement threshold; Core shutdown 02 - airborne fall scheduling; Core shutdown 03 - source cleanup and abort separation
Feature: Core shutdown
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core shutdown 01 - positive movement threshold
    Given an eligible grounded started MECH moving at <mp> MP
    When ordinary shutdown executes
    Then fall count is <falls> and both speeds are zero
    Examples:
      | mp | falls |
      | -2 | 0 |
      | 1 | 0 |
      | 1.01 | 1 |
      | 2 | 1 |

  Scenario Outline: Core shutdown 02 - airborne fall scheduling
    Given a started <kind> with jumping <jumping> at <height> above terrain and wizard <wizard>
    When ordinary shutdown executes
    Then started is <started> and fall callback deadline offset is <due>
    Examples:
      | kind | jumping | height | wizard | started | due |
      | MECH | 1 | 5 | 0 | 0 | 3 |
      | VTOL | 0 | 5 | 0 | 0 | 3 |
      | VTOL | 0 | 0 | 0 | 0 | none |
      | VEH_NAVAL | 0 | 5 | 0 | 0 | none |
      | DS | 0 | 5 | 0 | 1 | none |
      | DS | 0 | 5 | 1 | 0 | 3 |

  Scenario Outline: Core shutdown 03 - source cleanup and abort separation
    Given a unit is <state> with pilot and source cleanup fields populated
    When ordinary shutdown executes
    Then observed cleanup profile is <profile>
    Examples:
      | state | profile |
      | started | full |
      | starting | abort-only |
      | MW-started | refused |
      | stopped | refused |
