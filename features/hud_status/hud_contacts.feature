# HUD contact exports 01 - contact disclosure; HUD contact exports 02 - sensor and arcs; HUD contact exports 03 - building visibility; HUD contact exports 04 - scan gate; HUD contact exports 05 - scan reductions
Feature: HUD contact exports
  Background:
    Given a fresh HUD display session with ready units and event time zero
    And session key is test

  Scenario Outline: HUD contact exports 01 - contact disclosure
    Given a visible enemy with name Atlas heat 2 status heated and NB <nb>
    When keyed HUD c is requested
    Then its 19-field row name is <name> heat is 2 and status contains +
    And contact rows retain map roster order
    Examples:
      | nb | name |
      | true | Atlas |
      | false | something |

  Scenario Outline: HUD contact exports 02 - sensor and arcs
    Given contact sensor visibility is <sensors> and weapon arcs are <arcs>
    When keyed HUD c is requested
    Then its sensor string is <sensor_text> and arc string is <arc_text>
    Examples:
      | sensors | arcs | sensor_text | arc_text |
      | primary | forward-turret | P | *t |
      | secondary | left-rear | S | lv |
      | both | right | PS | r |
      | none | none | omitted | omitted |

  Scenario Outline: HUD contact exports 03 - building visibility
    Given a linked building with LOS <los> invisible <invisible> hidden <hidden> locked <locked> and safe <safe> CS <cs>
    When keyed HUD cb is requested
    Then the building result is <result>
    Examples:
      | los | invisible | hidden | locked | safe | cs | result |
      | clear | false | false | false | false | false | F |
      | clear | false | false | true | false | false | Ex |
      | clear | false | false | true | false | true | CEX |
      | clear | false | true | false | true | false | FHX |
      | clear | false | true | true | false | false | omitted |
      | clear | true | false | false | false | false | omitted |
      | blocked | false | false | false | false | false | omitted |

  Scenario Outline: HUD contact exports 04 - scan gate
    Given keyed HUD scan fixture range <range> scanner 20 observer <observer> NB <nb> and target form <form>
    When keyed HUD asc and wsc target TT are requested separately
    Then each scan outcome is <outcome> and each request produces <notices> target scan notices
    Examples:
      | range | observer | nb | form | outcome | notices |
      | 20.9 | false | true | mech | list | 1 |
      | 21 | false | true | mech | Out of range | 0 |
      | 21 | true | true | mech | list | 0 |
      | 2 | false | false | mech | Unable to scan target | 0 |
      | 2 | false | true | MW | Unable to scan target | 0 |

  Scenario Outline: HUD contact exports 05 - scan reductions
    Given enemy front armor is <current> of 99 with intact original internal and a ready weapon with recycle data <ticks>
    When keyed HUD asc and wsc target TT are requested separately
    Then the armor front character is <armor> and weapon scan status is <weapon>
    Examples:
      | current | ticks | armor | weapon |
      | 90 | 0 | O | R |
      | 89 | 1 | o | R |
      | 69 | 2 | x | - |
      | 44 | 5 | X | - |
      | 0 | 0 | * | R |
