# Core movement events 01 - fall acceleration and impact boundary; Core movement events 02 - stand callback is authoritative; Core movement events 03 - jump rearm cancellation
Feature: Core movement events
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core movement events 01 - fall acceleration and impact boundary
    Given a stopped nonflying unit at height <height> with fall data <speed>
    When one fall callback runs
    Then remaining height is <remaining> impact levels is <impact> and next fall data is <next>
    Examples:
      | height | speed | remaining | impact | next |
      | 5 | -1 | 3 | 0 | -2 |
      | 2 | -1 | 0 | 3 | none |
      | 3 | -2 | 0 | 6 | none |
      | 4 | 0 | 3 | 0 | -1 |

  Scenario Outline: Core movement events 02 - stand callback is authoritative
    Given a pending stand callback and fallen state <fallen>
    When the callback executes
    Then fallen is zero and LOS invalidation count increases by 1
    Examples:
      | fallen |
      | 0 |
      | 1 |

  Scenario Outline: Core movement events 03 - jump rearm cancellation
    Given a source jump callback whose movement ends jumping <ended>
    When the callback executes
    Then pending jump callbacks is <pending>
    Examples:
      | ended | pending |
      | 0 | 1 |
      | 1 | 0 |
