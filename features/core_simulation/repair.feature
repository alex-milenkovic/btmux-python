# Core repair 01 - reattach versus replace flooded section; Core repair 02 - part modifier boundaries; Core repair 03 - standard jet recomputation source cap; Core repair 04 - reseal preserves broken and damaged flags
Feature: Core repair
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core repair 01 - reattach versus replace flooded section
    Given a destroyed flooded section with original internal 10
    When repair operation <operation> is applied
    Then internal is 10 destroyed is zero and flooded is <flooded>
    Examples:
      | operation | flooded |
      | reattach | 0 |
      | replace-suit | 1 |

  Scenario Outline: Core repair 02 - part modifier boundaries
    Given source engine rating <rating> and nominal tons <tons>
    When gyro engine and ordinary repair modifiers are requested
    Then modifier tuple is <mods>
    Examples:
      | rating | tons | mods |
      | 100 | 10 | 0,4,0 |
      | 101 | 11 | 1,5,1 |
      | 400 | 100 | 3,19,9 |
      | 500 | 110 | 3,19,9 |

  Scenario Outline: Core repair 03 - standard jet recomputation source cap
    Given a MECH with maximum speed 6 MP and <slots> jump-jet slots and improved jets <improved>
    When do_sub_magic recomputes movement
    Then jump capacity is <mp> MP
    Examples:
      | slots | improved | mp |
      | 4 | 0 | 4 |
      | 4 | 1 | 2 |
      | 16 | 1 | 6 |

  Scenario Outline: Core repair 04 - reseal preserves broken and damaged flags
    Given a live flooded section containing a disabled part additionally marked <flag>
    When ReSeal runs
    Then disabled is zero and retained extra flag is <retained>
    Examples:
      | flag | retained |
      | none | none |
      | BROKEN | BROKEN |
      | DAMAGED | DAMAGED |
