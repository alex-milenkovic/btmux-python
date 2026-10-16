# Display scanning 01 - scan versus report; Display scanning 02 - selected report sections; Display scanning 03 - hex services; Display scanning 04 - vector sign; Display scanning 05 - range presentation; Display scanning 06 - sight and view
Feature: Display scanning
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Display scanning 01 - scan versus report
    Given scanner range 20 and NB-visible target TT at range <range>
    When pilot command <command> is issued for TT
    Then report outcome is <outcome> and scan notices total <notices>
    Examples:
      | range | command | outcome | notices |
      | 20.9 | scan | success | 1 |
      | 21 | scan | out-of-range | 0 |
      | 21 | report | success | 0 |

  Scenario Outline: Display scanning 02 - selected report sections
    Given a visible target with front armor 44 of 99 and mounted weapon recycle 4
    When scan option <option> is requested by observer <observer>
    Then report sections are <sections> and armor representation is <armor>
    Examples:
      | option | observer | sections | armor |
      | A | false | base,armor | XX |
      | I | false | base,info | absent |
      | W | false | base,weapons | absent |
      | all | true | base,armor,info,weapons | 44 |

  Scenario Outline: Display scanning 03 - hex services
    Given the targeted hex has <objects> with clear NB LOS and usable scanner
    When scan coordinates option <option> is issued
    Then building query occurs and mine query occurs <mine> without treating empty content as unavailable
    Examples:
      | objects | option | mine |
      | building-and-mine | B | false |
      | building-and-mine | H | true |
      | mine-only | H | true |
      | empty | H | true |

  Scenario Outline: Display scanning 04 - vector sign
    Given observer at 2 2 elevation 0
    When vector coordinates 2 2 <z> are requested
    Then range text is <range> and vertical mark is <mark>
    Examples:
      | z | range | mark |
      | 5 | 1.0 | +90 |
      | -5 | 1.0 | -90 |
      | 3 | 0.6 | +90 |

  Scenario Outline: Display scanning 05 - range presentation
    Given observer at 2 2 elevation 0 and destination 2 5 elevation 4 with dark map <dark>
    When range coordinates 2 5 is requested
    Then displayed range is <range> and separate ground-range text is <ground>
    Examples:
      | dark | range | ground |
      | false | 3.1 | 3.0 |
      | true | 3.0 | absent |

  Scenario Outline: Display scanning 06 - sight and view
    Given visible locked target TT with markings <markings> and one ready loaded weapon
    When view TT then sight weapon 0 are requested
    Then view text is <text> and sight reports the actual firing solution
    And ammo heat target armor and weapon recycle are unchanged
    Examples:
      | markings | text |
      | red-chevron | red-chevron |
      | empty | That target has no markings. |
