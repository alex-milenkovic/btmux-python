# Long range and navigation 01 - movement glyphs; Long range and navigation 02 - elevation rendering; Long range and navigation 03 - visibility rendering; Long range and navigation 04 - height preference; Long range and navigation 05 - navigation geometry; Long range and navigation 06 - colors
Feature: Long range and navigation
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Long range and navigation 01 - movement glyphs
    Given a visible other unit has movement <movement> and apparent friendship <friend>
    When LRS m is requested
    Then its plain glyph is <glyph>
    Examples:
      | movement | friend | glyph |
      | biped | true | b |
      | quad | false | Q |
      | fly | false | B |
      | track | true | t |
      | wheel | false | W |
      | hover | true | h |
      | VTOL | false | V |
      | hull | true | n |
      | sub | false | S |
      | foil | true | f |

  Scenario Outline: Long range and navigation 02 - elevation rendering
    Given an empty visible grass hex at elevation <elevation>
    When LRS mode <mode> is requested
    Then its plain glyph is <glyph>
    Examples:
      | elevation | mode | glyph |
      | 0 | e | space |
      | 0 | c | 0 |
      | 3 | e | 3 |

  Scenario Outline: Long range and navigation 03 - visibility rendering
    Given a displayed cell is <visibility>
    When LRS l and tactical l are requested
    Then the cell uses unknown-state glyph <glyph>
    Examples:
      | visibility | glyph |
      | unvisited | X |
      | visited-no-terrain | ? |

  Scenario Outline: Long range and navigation 04 - height preference
    Given a large map and LRS range <range> with LRSHEIGHT <preference>
    When LRS t is requested
    Then its hex height is <height> with <warnings> preference warnings
    Examples:
      | range | preference | height | warnings |
      | 30 | unset | 11 | 0 |
      | 30 | 10 | 11 | 0 |
      | 30 | 40 | 41 | 0 |
      | 30 | 9 | 11 | 1 |
      | 3 | 20 | 7 | 0 |

  Scenario Outline: Long range and navigation 05 - navigation geometry
    Given the observer is at hex <position> and visible same-hex contacts have distinct real offsets
    When navigate and findcenter are requested
    Then navigate has 13 lines and a 5 by 5 hexagonal local view with compass and live movement fields
    And off-map hexes are <outside> and self wins a coincident subhex marker
    Examples:
      | position | outside |
      | 0,0 | blank |
      | 5,5 | absent |

  Scenario Outline: Long range and navigation 06 - colors
    Given display color preference <palette>
    When two consecutive colored maps are requested then a different player requests the default palette
    Then each original render emits <warnings> preference diagnostic lines and the default-player render emits zero
    And color does not leak between lines or players
    Examples:
      | palette | warnings |
      | B | 0 |
      | n | 0 |
      | invalid? | 2 |
      | 1234567890123456789012 | 2 |
