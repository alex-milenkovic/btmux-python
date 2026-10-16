# Tactical display 01 - terrain cells; Tactical display 02 - cliff thresholds; Tactical display 03 - restricted modes; Tactical display 04 - window preferences; Tactical display 05 - mine visibility; Tactical display 06 - dropship footprint
Feature: Tactical display
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Tactical display 01 - terrain cells
    Given a clear tactical cell has terrain <terrain> elevation <elev> and underlying <underlay>
    When tactical mode <mode> renders without color or units in that cell
    Then the two top glyphs and two bottom glyphs are <top> and <bottom>
    Examples:
      | terrain | elev | underlay | mode | top | bottom |
      | grass | 0 | grass | default | spaces | __ |
      | water | 2 | water | default | ~~ | ~2 |
      | bridge | 0 | bridge | default | ## | ++ |
      | highwater | 0 | water | default | ~~ | ++ |
      | fire | 0 | road | u | && | ## |
      | smoke | 3 | forest | u | :: | `3 |

  Scenario Outline: Tactical display 02 - cliff thresholds
    Given neighboring displayed hexes have elevation difference <difference>
    When tactical mode <mode> is requested on a non-dark map
    Then their shared lower edge is marked as a cliff <cliff>
    Examples:
      | difference | mode | cliff |
      | 2 | c | false |
      | 3 | c | true |
      | 1 | t | false |
      | 2 | t | true |

  Scenario Outline: Tactical display 03 - restricted modes
    Given map is dark <dark>
    When tactical mode <mode> is requested
    Then command outcome is <outcome>
    Examples:
      | dark | mode | outcome |
      | true | c | You can't see that much here! |
      | true | t | You can't see that much here! |
      | true | b | You can't see that much here! |
      | true | l | map |
      | false | z | Invalid tactical map flag. |

  Scenario Outline: Tactical display 04 - window preferences
    Given a 100 by 100 map scanner range <range> and TACSIZE <preference>
    When tactical is requested
    Then the hex window height is <height> width is <width> and preference warnings total <warnings>
    Examples:
      | range | preference | height | width | warnings |
      | 30 | unset | 14 | 21 | 0 |
      | 30 | 5 40 | 5 | 40 | 0 |
      | 30 | 4 40 | 14 | 21 | 1 |
      | 3 | 24 40 | 6 | 6 | 0 |

  Scenario Outline: Tactical display 05 - mine visibility
    Given first mine in a displayed hex is <kind> with hex NB <nb>
    When tactical mine mode is requested
    Then the bottom mine marker is <marker>
    Examples:
      | kind | nb | marker |
      | ordinary | true | <> |
      | trigger | true | blank |
      | ordinary | false | blank |
      | none | true | blank |

  Scenario Outline: Tactical display 06 - dropship footprint
    Given a visible non-carrier DropShip is <state> with six adjacent hexes and one bay door
    When tactical is requested
    Then the dropship occupies <footprint> hexes and a footprint door marker is <door>
    Examples:
      | state | footprint | door |
      | landed | 7 | @ |
      | shutdown | 7 | @ |
      | airborne-below-orbit | 1 | absent |
