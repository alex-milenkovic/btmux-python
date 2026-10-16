# Core targets 01 - unit-target failure does not use hex fallback; Core targets 02 - map ID matching; Core targets 03 - LOS invalidation replaces map flags
Feature: Core targets
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core targets 01 - unit-target failure does not use hex fallback
    Given stored target <target> and valid hex coordinates with target Z 3
    When FindTargetXY is requested
    Then target resolution is <result>
    Examples:
      | target | result |
      | minus1 | hex-z3 |
      | missing-unit | none |
      | registered-unit | unit-xyz |

  Scenario Outline: Core targets 02 - map ID matching
    Given roster IDs AB followed by Ab with distinct identities
    When target ID text <text> is resolved
    Then selected roster ordinal is <ordinal>
    Examples:
      | text | ordinal |
      | ab | 0 |
      | ABsuffix | 0 |
      | zz | -1 |

  Scenario Outline: Core targets 03 - LOS invalidation replaces map flags
    Given unit map flag is <flags> and map moves is 4
    When MarkForLOSUpdate runs
    Then unit map flag is 1 and map moves is 5
    Examples:
      | flags |
      | 0 |
      | 2 |
      | 7 |
