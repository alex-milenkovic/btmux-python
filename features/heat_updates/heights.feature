# Height maintenance 01 - submarine bottom; Height maintenance 02 - surface and grounding; Height maintenance 03 - VTOL water and orbit; Height maintenance 04 - VTOL terrain collision
Feature: Height maintenance
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Height maintenance 01 - submarine bottom
    Given a submarine in water with lower elevation <bottom> at Z <z> and FZ <fz> diving at 10.75 KPH
    When the movement height-maintenance boundary is reached
    Then submarine Z is <final_z> FZ is <final_fz> and vertical speed is <vertical>
    Examples:
      | bottom | z | fz | final_z | final_fz | vertical |
      | -3 | -2 | -129 | -2 | -129 | -10.75 |
      | -3 | -3 | -193.5 | -2 | -180.6 | 0 |
      | -3 | -4 | -258 | -2 | -180.6 | 0 |
      | -1 | -1 | -64.5 | 0 | -51.6 | 0 |

  Scenario Outline: Height maintenance 02 - surface and grounding
    Given a naval unit on <terrain> with previous Z -1 current Z 0 FZ 1 vertical speed 10.75 speed 21.5 desired speed 32.25 and both facings 90
    When the movement height-maintenance boundary is reached
    Then vertical speed is zero
    And FZ is <fz> actual speed is <speed> desired speed is <desired> and both facings are <facing>
    Examples:
      | terrain | fz | speed | desired | facing |
      | WATER | 0 | 21.5 | 32.25 | 90 |
      | ICE | 0 | 21.5 | 32.25 | 90 |
      | BRIDGE | 0 | 21.5 | 32.25 | 90 |
      | GRASSLAND | 1 | 0 | 0 | 0 |
      | HIGHWATER | 1 | 0 | 0 | 0 |

  Scenario Outline: Height maintenance 03 - VTOL water and orbit
    Given an airborne VTOL on <terrain> at Z <z> with FZ equal to Z times 64.5 and vertical speed <vertical>
    When the movement height-maintenance boundary is reached
    Then destroyed is <destroyed> final Z is <final_z> and final vertical speed is <final_vertical>
    Examples:
      | terrain | z | vertical | destroyed | final_z | final_vertical |
      | WATER | -1 | -10.75 | True | -1 | 0 |
      | WATER | 0 | -10.75 | False | 0 | -10.75 |
      | GRASSLAND | 299 | 10.75 | False | 299 | 10.75 |
      | GRASSLAND | 300 | 10.75 | False | 299 | 0 |
      | GRASSLAND | 301 | 10.75 | False | 299 | 0 |

  Scenario Outline: Height maintenance 04 - VTOL terrain collision
    Given an airborne VTOL at Z <z> over <terrain> with signed elevation 3 vertical speed -21.5 desired speed 21.5 and a landing site that the real landing rules reject
    When the movement height-maintenance boundary is reached
    Then a crash occurred <crash> landed is <landed> and final Z is <final_z>
    Examples:
      | z | terrain | crash | landed | final_z |
      | 3 | MOUNTAINS | False | False | 3 |
      | 2 | MOUNTAINS | True | True | 3 |
      | 2 | BRIDGE | True | True | 3 |
      | 1 | BRIDGE | False | False | 1 |
