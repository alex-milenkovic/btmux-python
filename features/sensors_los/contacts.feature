# Contact readout 01 - packed preferences; Contact readout 02 - filters; Contact readout 03 - ordering; Contact readout 04 - status masking
Feature: Contact readout
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: Contact readout 01 - packed preferences
    Given contact brief value <initial>
    When the pilot issues brief <request>
    Then the command is <accepted> and brief value is <value>
    Examples:
      | initial | request | accepted | value |
      | 5 | A 3 | True | 13 |
      | 13 | C 2 | True | 14 |
      | 14 | A 6 | True | 26 |
      | 14 | A 7 | False | 14 |
      | 14 | C 4 | False | 14 |

  Scenario Outline: Contact readout 02 - filters
    Given identified contacts friend f enemy e shutdown enemy s destroyed enemy d and locked shutdown enemy t
    And contact brevity is 2 with no buildings
    When the pilot requests contacts with filter <filter>
    Then the included unit IDs as an unordered set are <ids>
    Examples:
      | filter | ids |
      | no-argument | d,e,f,s,t |
      | a | f |
      | e | e |
      | es | e,s,t |
      | t | t |
      | !dst | e,f |
      | !d | e,f,s,t |

  Scenario Outline: Contact readout 03 - ordering
    Given visible live contacts near at range 2 far at range 8 and destroyed wreck at range 1 in that roster order
    When the pilot requests contact brevity <brevity>
    Then displayed contact order is <order> and ordinary heading is <heading>
    Examples:
      | brevity | order | heading |
      | 0 | near,far,wreck | True |
      | 1 | wreck,far,near | True |
      | 3 | wreck,far,near | False |

  Scenario Outline: Contact readout 04 - status masking
    Given a same-team contact with primary visibility and terrain block <block>
    And the contact is heated jellied burning and has active ECM and attached NARC
    When a brief contact list is requested
    Then the name is <name> apparent friend is <friend> and five status characters are <status>
    Examples:
      | block | name | friend | status |
      | False | real-name | True | ___+n |
      | True | something | False | _____ |
