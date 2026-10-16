# Armor displays 01 - condition boundaries; Armor displays 02 - numeric fields; Armor displays 03 - destroyed field; Armor displays 04 - template grammar; Armor displays 05 - diagram selection
Feature: Armor displays
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Armor displays 01 - condition boundaries
    Given an intact section original armor 99 current armor <current> and front repair <repair>
    When enemy armor is displayed
    Then condition index is <level> and its two-character field is <field>
    Examples:
      | current | repair | level | field |
      | 90 | false | 0 | OO |
      | 89 | false | 1 | oo |
      | 70 | false | 1 | oo |
      | 69 | false | 2 | xx |
      | 45 | false | 2 | xx |
      | 44 | false | 3 | XX |
      | 1 | false | 3 | XX |
      | 0 | false | 4 | ** |
      | 0 | true | 5 | ?? |

  Scenario Outline: Armor displays 02 - numeric fields
    Given armor value <value> requested field width <width> and divide-by-ten <divide>
    When owned armor is displayed for an intact section
    Then its plain field with spaces encoded as underscores is <field> and visible width is <actual>
    Examples:
      | value | width | divide | field | actual |
      | 7 | 3 | false | __7 | 3 |
      | 1234 | 2 | false | 34 | 2 |
      | 11 | 1 | true | 2 | 1 |
      | 10 | 1 | true | 1 | 1 |
      | 7 | 30 | false | ______________________7 | 23 |

  Scenario Outline: Armor displays 03 - destroyed field
    Given section current internal is zero and front armor is zero
    When armor is displayed with SHOW_DEST <show> owner <owner>
    Then its plain two-character field with spaces encoded as underscores is <field>
    Examples:
      | show | owner | field |
      | false | true | __ |
      | false | false | __ |
      | true | true | _0 |
      | true | false | ** |

  Scenario Outline: Armor displays 04 - template grammar
    Given section 0 internal is <internal> and section 1 internal is zero
    When evaluated local custom armor template text is 7 @0A!01B&&
    Then owner plain output with spaces encoded as underscores is <output>
    Examples:
      | internal | output |
      | 1 | _AB& |
      | 0 | ___& |

  Scenario Outline: Armor displays 05 - diagram selection
    Given unit form <form> tonnage <tons> and original turret <turret>
    When status armor is requested
    Then diagram family is <diagram> and every displayed armor field reads the corresponding real section
    Examples:
      | form | tons | turret | diagram |
      | biped | 35 | false | light |
      | biped | 36 | false | medium |
      | biped | 55 | false | medium |
      | biped | 56 | false | heavy |
      | biped | 75 | false | heavy |
      | biped | 76 | false | assault |
      | quad | 50 | false | quad |
      | vehicle | 50 | true | turreted |
      | vehicle | 50 | false | no-turret |
      | VTOL | 30 | false | VTOL |
      | MW | 1 | false | MW |
      | BSUIT | 5 | false | squad |
      | NAVAL-HULL | 50 | true | ship |
      | NAVAL-FOIL | 50 | true | foil |
      | NAVAL-SUB | 50 | true | sub |
      | DS | 1000 | false | aerodyne |
      | SPHEROID_DS | 1000 | false | spheroid |
      | AERO | 90 | false | six-location-fighter |
