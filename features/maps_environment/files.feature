# Maps files 01 - checked loading; Maps files 02 - terrain text serialization; Maps files 03 - conditional trailer; Maps files 04 - resize intersection
Feature: Maps files
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps files 01 - checked loading
    Given a live 2 by 2 map named old and a map file of kind <kind>
    When the map file is checked before the load command
    Then the check code is <code> and the existing map is <state>
    Examples:
      | kind | code | state |
      | missing | -1 | retained |
      | zero-width | -2 | retained |
      | width-1001 | -2 | retained |
      | short-row | -3 | retained |
      | valid-2x2 | 1 | replaceable |
      | unknown-terrain-2x2 | 1 | replaceable |

  Scenario Outline: Maps files 02 - terrain text serialization
    Given one elevation 3 cell has terrain <terrain> with decoration <deco> and eternal fire flag <eternal>
    When the map is saved as text
    Then its terrain elevation pair is <pair> and live terrain becomes <live>
    Examples:
      | terrain | deco | eternal | pair | live |
      | grass | none | 0 | .3 | grass |
      | fire | fire-on-light-forest | 0 | >3 | fire |
      | fire | none | 1 | &3 | fire |
      | fire | none | 0 | .3 | grass |
      | smoke | smoke-on-water | 0 | ~3 | smoke |
      | smoke | none | 0 | .3 | grass |

  Scenario Outline: Maps files 03 - conditional trailer
    Given a map has flags <flags> gravity 75 and temperature -20
    When it is saved and loaded into a fresh map
    Then a trailer is <trailer> and loaded gravity is <gravity> and temperature is <temperature>
    Examples:
      | flags | trailer | gravity | temperature |
      | 0 | absent | 100 | 20 |
      | 1 | absent | 100 | 20 |
      | 2 | present | 75 | -20 |
      | 129 | present | 75 | -20 |

  Scenario Outline: Maps files 04 - resize intersection
    Given a 2 by 2 map has rough elevation 3 at 1 1 and bit table <bits>
    When resize requests dimensions <width> <height>
    Then the resize outcome is <outcome> with original corner <corner> and new cells grass zero
    Examples:
      | bits | width | height | outcome | corner |
      | absent | 3 | 3 | success | retained |
      | absent | 1 | 1 | success | removed |
      | absent | 0 | 0 | success | removed |
      | present-empty | 3 | 3 | refused | retained |
      | absent | 1001 | 2 | refused | retained |
