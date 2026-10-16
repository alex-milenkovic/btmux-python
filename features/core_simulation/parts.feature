# Core parts 01 - fixed-point rounding tolerance; Core parts 02 - current percentages; Core parts 03 - unit part list mode is ignored
Feature: Core parts
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core parts 01 - fixed-point rounding tolerance
    Given fixed-point weight <weight>
    When half-ton and quarter-ton rounding are requested
    Then rounded weights are <half> and <quarter>
    Examples:
      | weight | half | quarter |
      | 0 | 0 | 0 |
      | 1 | 0 | 0 |
      | 2 | 512 | 256 |
      | 256 | 512 | 256 |
      | 257 | 512 | 256 |
      | 512 | 512 | 512 |
      | 513 | 512 | 512 |
      | 514 | 1024 | 768 |

  Scenario Outline: Core parts 02 - current percentages
    Given original points <original> and remaining points <remaining>
    When remaining percentage is calculated
    Then percentage is <percent>
    Examples:
      | original | remaining | percent |
      | 0 | 0 | 0 |
      | 3 | 2 | 66 |
      | 10 | 11 | 110 |
      | 8 | 1 | 12 |

  Scenario Outline: Core parts 03 - unit part list mode is ignored
    Given the same partially damaged unit with source payload and parts
    When UnitPartsList is requested with mode <mode>
    Then the complete string equals the mode zero result
    Examples:
      | mode |
      | 1 |
      | 2 |
      | -1 |
