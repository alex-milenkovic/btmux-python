# HUD state exports 01 - general scalar fields; HUD state exports 02 - position and torso; HUD state exports 03 - armor originals; HUD state exports 04 - conditions; HUD state exports 05 - type codes
Feature: HUD state exports
  Background:
    Given a fresh HUD display session with ready units and event time zero
    And session key is test

  Scenario Outline: HUD state exports 01 - general scalar fields
    Given unit speed <speed> desired speed <desired> plus heat <plus> minus heat <minus> and vertical speed <vertical>
    When the user requests keyed HUD gs
    Then GS speed fields are <speed_text> and <desired_text> heat fields are <plus_text> and <minus_text> and both vertical fields are <vertical_text>
    And GS has 20 fields with the final target field a dash
    Examples:
      | speed | desired | plus | minus | vertical | speed_text | desired_text | plus_text | minus_text | vertical_text |
      | 12.345 | 20 | 2.19 | 1.99 | -3.5 | 12.35 | 20.00 | 21 | 19 | -3.50 |
      | -1.234 | 0 | 0 | 0 | 0 | -1.23 | 0.00 | 0 | 0 | 0.00 |

  Scenario Outline: HUD state exports 02 - position and torso
    Given unit form <form> with turret offset <offset> torso <torso> and jump state <jump>
    When the user requests keyed HUD gs
    Then the torso field is <field> and jump destination fields are <destination>
    Examples:
      | form | offset | torso | jump | field | destination |
      | biped | 0 | left | none | -60 | -,- |
      | biped | 0 | right | 4,5 | 60 | 4,5 |
      | quad | 0 | none | none | - | -,- |
      | turreted-vehicle | 90 | none | none | -90 | -,- |

  Scenario Outline: HUD state exports 03 - armor originals
    Given a section has original front <of> rear <orr> internal <oi> and current front <cf> rear <cr> internal <ci>
    When keyed HUD oas and as are requested
    Then the section original row is <original> and current row is <current>
    Examples:
      | of | orr | oi | cf | cr | ci | original | current |
      | 20 | 5 | 10 | 7 | 2 | 4 | 20,5,10 | 7,2,4 |
      | 20 | 0 | 10 | 0 | 0 | 0 | 20,0,10 | 0,0,0 |
      | 0 | 0 | 0 | 0 | 0 | 0 | omitted | omitted |

  Scenario Outline: HUD state exports 04 - conditions
    Given map light <light> visibility 30 gravity 100 temperature 25 and flags <flags>
    When keyed HUD con and co are requested
    Then both condition payloads are <payload> with their respective CON and CO classes
    Examples:
      | light | flags | payload |
      | 0 | none | N,30,100,25,- |
      | 1 | vacuum-underground-dark | T,30,100,25,VUD |
      | 2 | dark | D,30,100,25,D |
      | no-map | none | ?,?,?,?,? |

  Scenario Outline: HUD state exports 05 - type codes
    Given the unit class and movement are <form>
    When keyed HUD sgi is requested
    Then its type field is <code> and all remaining template fields come from the loaded design
    Examples:
      | form | code |
      | MECH-BIPED | B |
      | MECH-QUAD | Q |
      | VEHICLE-TRACK | T |
      | VEHICLE-WHEEL | W |
      | VEHICLE-HOVER | H |
      | NAVAL-HULL | N |
      | NAVAL-FOIL | Y |
      | NAVAL-SUB | U |
      | VTOL | V |
      | AERO | F |
      | DS | A |
      | SPHEROID_DS | D |
      | MW | I |
      | BSUIT | S |
      | INSTALLATION | i |
