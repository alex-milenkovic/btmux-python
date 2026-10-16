# Maps dynamic 01 - roster slot reuse; Maps dynamic 02 - tail removal and cleanup; Maps dynamic 03 - stream validation
Feature: Maps dynamic
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps dynamic 01 - roster slot reuse
    Given a map has roster <before> and a valid unit with ID <unit>
    When the unit is added to the map
    Then the resulting roster is <after>
    And the assigned slot is <slot>
    Examples:
      | before | unit | after | slot |
      | 10,20 | 20 | 10,20 | 1 |
      | 10,-1,30 | 40 | 10,40,30 | 1 |
      | 10,20 | 30 | 10,20,30 | 2 |
      | empty | 10 | 10 | 0 |

  Scenario Outline: Maps dynamic 02 - tail removal and cleanup
    Given a map has roster <before> with consistent unit slots
    When the operation is <operation>
    Then the resulting roster is <after>
    Examples:
      | before | operation | after |
      | 10,20,30 | remove20 | 10,-1,30 |
      | 10,-1,30 | remove30 | 10,-1 |
      | 10,-1,-1 | eliminate | 10 |
      | -1,-1 | eliminate | -1,-1 |
      | 10,-1,30,-1 | eliminate | 10,-1,30 |

  Scenario Outline: Maps dynamic 03 - stream validation
    Given a dynamic snapshot uses count <count> with stream condition <condition>
    When the snapshot is loaded through the documented persistence interface
    Then the result is <result>
    Examples:
      | count | condition | result |
      | 0 | magic-only | empty-arrays |
      | 2 | valid-distinct-directed-LOS | exact-roundtrip |
      | 2 | short-roster | read-error |
      | 2 | short-flags | read-error |
      | 2 | short-LOS | read-error |
      | 0 | wrong-magic | magic-error |
      | 0 | missing-magic | read-error |
