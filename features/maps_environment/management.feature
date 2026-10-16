# Maps management 01 - hex editing and cache; Maps management 02 - map view dimensions; Maps management 03 - map creation and emission
Feature: Maps management
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps management 01 - hex editing and cache
    Given a 3 by 3 map has a unit at 1 1 with cached grass elevation 0 and another at 2 2
    When addhex receives <arguments>
    Then the outcome is <outcome> with terrain <terrain> elevation <elevation> and cached unit elevation 0
    Examples:
      | arguments | outcome | terrain | elevation |
      | 1,1,.,-4 | success | grass | 4 |
      | 1,1,%,20 | success | rough | 9 |
      | 3,1,%,2 | out-of-range | grass | 0 |
      | 1,1,% | arity-error | grass | 0 |

  Scenario Outline: Maps management 02 - map view dimensions
    Given a 30 by 30 map has player TACSIZE <tacsize>
    When view is requested at -3 99
    Then the renderer request has center 0 29 dimensions <height> <width> and warning <warning>
    Examples:
      | tacsize | height | width | warning |
      | absent | 14 | 21 | none |
      | 5,5 | 5 | 5 | none |
      | 24,40 | 24 | 30 | none |
      | 4,20 | 14 | 21 | invalid-tacsize |
      | 20,41 | 14 | 21 | invalid-tacsize |

  Scenario Outline: Maps management 03 - map creation and emission
    Given an allocated empty map has identity 41
    When mapemit receives <text>
    Then the map remains 21 by 11 grass zero with regen factor 1 and the emission is <result>
    Examples:
      | text | result |
      | SPACES | empty-error |
      | SPACEShello | hello |
      | helloSPACES | helloSPACES |
