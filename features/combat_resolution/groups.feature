# Combat trigger groups 01 - membership editing; Combat trigger groups 02 - two-column listing; Combat trigger groups 03 - abort remaining volley
Feature: Combat trigger groups
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat trigger groups 01 - membership editing
    Given TIC 0 contains weapons 0 1 2
    When deltic text is <text>
    Then TIC 0 contains <members>
    Examples:
      | text | members |
      | 0 1 | 0,2 |
      | 0 2-1 | 0 |
      | 0 | none |

  Scenario Outline: Combat trigger groups 02 - two-column listing
    Given TIC 0 contains valid weapons numbered 0 1 2 3 4
    When listtic 0 is displayed
    Then callback row order is <order>
    Examples:
      | order |
      | 0,3,1,4,2 |

  Scenario Outline: Combat trigger groups 03 - abort remaining volley
    Given TIC 0 contains two ready weapons and TIC 1 contains another
    When firetic 0,1 fires first weapon and actor <change>
    Then no later weapon fires
    Examples:
      | change |
      | falls-from-heavy-Gauss-recoil |
      | shuts-down-from-failure |
