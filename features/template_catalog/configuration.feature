# Template catalog configuration 01 - path precedence; Template catalog configuration 02 - verification without mutation; Template catalog configuration 03 - ordinary list and lookup
Feature: Template catalog configuration
  Background:
    Given an isolated template catalog session with pinned inputs and writable scratch storage

  Scenario Outline: Template catalog configuration 01 - path precedence
    Given catalog option <option> and environment <environment> with all named roots at the pinned revision
    When ordinary catalog configuration resolves its read root
    Then the selected root is <selected>
    Examples:
      | option | environment | selected |
      | true | none | project-relative |
      | true | environment-root | environment-root |
      | explicit-root | environment-root | explicit-root |
      | false | environment-root | disabled |
      | omitted | environment-root | disabled |

  Scenario Outline: Template catalog configuration 02 - verification without mutation
    Given the configured catalog has <state>
    When setup verification is requested
    Then the outcome is <outcome> and every preexisting input byte is unchanged
    Examples:
      | state | outcome |
      | matching-LF | verified |
      | matching-CRLF | verified-EOL-only |
      | wrong-revision | revision-error |
      | content-drift | drift-error |
      | missing | missing-error |

  Scenario Outline: Template catalog configuration 03 - ordinary list and lookup
    When an ordinary list and reference lookup requests <reference> from the pinned upstream catalog
    Then the chosen design is <chosen> with upstream provenance
    Examples:
      | reference | chosen |
      | WVR-6R | WVR-6R |
      | wvr-6r | WVR-6R |
      | BLR-1G | BLR-1G |
      | WHM-6R | WHM-6R |
