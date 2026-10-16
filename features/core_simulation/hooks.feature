# Core hooks 01 - no-op hooks around live callbacks; Core hooks 02 - history ordering; Core hooks 03 - pending view excludes cancelled events
Feature: Core hooks
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core hooks 01 - no-op hooks around live callbacks
    Given a queued event marked zombie <zombie>
    When it is executed by <method>
    Then hook and callback trace is <trace> and history count remains 0
    Examples:
      | zombie | method | trace |
      | 0 | due | pre,callback,post |
      | 1 | due | none |
      | 0 | type | pre,callback,post |
      | 1 | type | none |

  Scenario Outline: Core hooks 02 - history ordering
    Given history counts for source types 0 1 and 2 are <counts>
    When nonempty event history is requested
    Then displayed nonzero type order is <order>
    Examples:
      | counts | order |
      | 2,2,1 | 2,0,1 |
      | 0,3,1 | 2,1 |
      | 0,0,0 | none |

  Scenario Outline: Core hooks 03 - pending view excludes cancelled events
    Given three events of one source type with <cancelled> cancelled
    When blank event summary is requested
    Then pending total is <total> and roll state is unchanged
    Examples:
      | cancelled | total |
      | 0 | 3 |
      | 1 | 2 |
      | 3 | 0 |
