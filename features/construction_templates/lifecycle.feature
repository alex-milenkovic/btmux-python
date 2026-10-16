# Construction lifecycle 01 - clear and same reference; Construction lifecycle 02 - failure and wrapper cleanup; Construction lifecycle 03 - cache depth and invalidation; Construction lifecycle 04 - legacy header and omissions
Feature: Construction lifecycle
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction lifecycle 01 - clear and same reference
    Given a unit reference is AS7-D with nonzero heat damage statuses targets TICs radio frequencies and channel titles
    When mech_loadnew requests <reference> with a valid modern file
    Then TICs frequencies and titles are <retention> while runtime reset and live identity preservation succeed
    Examples:
      | reference | retention |
      | AS7-D | retained |
      | as7-d | cleared |
      | AS7-K | cleared |

  Scenario Outline: Construction lifecycle 02 - failure and wrapper cleanup
    Given a unit with queued events and cached LOS requests <operation> using a <file> reference
    When the operation completes
    Then its result and event policy are <result> and <events>
    Examples:
      | operation | file | result | events |
      | loadnew | valid | success | all-unit-events-cancelled |
      | restore | valid | success | no-extra-wrapper-cancellation |
      | loadnew | missing | failure-after-clear | only-clear-mech-burning-cleanup |
      | restore | missing-reference | failure-before-clear | unchanged |

  Scenario Outline: Construction lifecycle 03 - cache depth and invalidation
    Given a template root contains <path> and its cache is built
    When lookup <query> uses <change>
    Then the outcome is <outcome>
    Examples:
      | path | query | change | outcome |
      | AS7-D | as7-d | none | root-hit |
      | Custom/AS7-D | as7-d | none | subdir-hit |
      | Custom/nested/AS7-D | AS7-D | none | cache-miss |
      | Custom/nested/AS7-D | Custom/nested/AS7-D | none | explicit-path-hit |
      | .hidden/AS7-D | AS7-D | none | cache-miss |
      | AS7-D | AS7-K | add-AS7-K-after-scan | cache-miss |
      | AS7-D | AS7-K | save-AS7-K-invalidates-cache | root-hit |
      | AS7-D | AS7-D | delete-hit-and-retry | not-found |

  Scenario Outline: Construction lifecycle 04 - legacy header and omissions
    Given a complete numeric legacy template header has specials <specials> and optional radio <radio>
    When legacy load is requested
    Then specials and radio range are <out_specials> and <out_radio>
    Examples:
      | specials | radio | out_specials | out_radio |
      | 32768 | 77 | 0 | 77 |
      | 16384 | absent | 0 | 80 |
      | 8192 | 90 | 0 | 90 |
      | 4196 | 80 | 0 | 80 |
      | 32 | 55 | 0 | 55 |
      | 33 | 55 | 1 | 55 |
