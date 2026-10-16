# HUD tactical export 01 - window bounds; HUD tactical export 02 - syntax; HUD tactical export 03 - independent visibility; HUD tactical export 04 - map identity
Feature: HUD tactical export
  Background:
    Given a fresh HUD display session with ready units and event time zero
    And session key is test

  Scenario Outline: HUD tactical export 01 - window bounds
    Given a clear 100 by 100 map with viewer at 50 50 and LRS range 30
    When keyed HUD tactical height <height> is requested
    Then start bounds are <bounds> and there are <rows> terrain rows of 70 cells
    And every row has its y coordinate followed by paired terrain and elevation glyphs
    Examples:
      | height | bounds | rows |
      | 1 | 15,50,84,49 | 0 |
      | 2 | 15,49,84,50 | 2 |
      | 5 | 15,48,84,51 | 4 |
      | 40 | 15,30,84,69 | 40 |

  Scenario Outline: HUD tactical export 02 - syntax
    When keyed HUD text <request> is submitted
    Then tactical outcome is <outcome>
    Examples:
      | request | outcome |
      | t 0 | Invalid 1st argument |
      | t 41 | Invalid 1st argument |
      | t 5 90 | Invalid arguments |
      | t 5 90 1 x | Invalid fourth argument |
      | t 5 90 1 l | map-list |

  Scenario Outline: HUD tactical export 03 - independent visibility
    Given a map cell terrain is grass elevation 3 with visibility <visibility>
    When keyed HUD tactical LOS mode renders the cell
    Then its terrain-elevation pair is <pair>
    Examples:
      | visibility | pair |
      | both | .3 |
      | terrain-only | .? |
      | elevation-only | ?3 |
      | neither | ?? |

  Scenario Outline: HUD tactical export 04 - map identity
    Given HUD mapinfo configuration <config> and map in-character <ic>
    When keyed HUD tactical is requested
    Then map ID and name are <identity> and dimensions remain disclosed
    Examples:
      | config | ic | identity |
      | 0 | false | -1,-1 |
      | 1 | true | -1,-1 |
      | 1 | false | actual |
      | 2 | true | actual |
