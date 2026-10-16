# LOS geometry and modifiers 01 - eye heights; LOS geometry and modifiers 02 - overlay woods; LOS geometry and modifiers 03 - infrared profiles; LOS geometry and modifiers 04 - cached identification
Feature: LOS geometry and modifiers
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: LOS geometry and modifiers 01 - eye heights
    Given a unit of class <class> posture <posture> movement <movement> at Z 2
    When the LOS height diagnostic is requested
    Then effective unit LOS elevation is <height>
    Examples:
      | class | posture | movement | height |
      | MECH | upright | BIPED | 3.5 |
      | MECH | fallen | BIPED | 2.5 |
      | DS | upright | FLY | 4.5 |
      | SPHEROID_DS | upright | FLY | 6.5 |
      | VEH_GROUND | dug-in | TRACK | 2.1 |
      | DS | upright | NONE | 3.5 |

  Scenario Outline: LOS geometry and modifiers 02 - overlay woods
    Given a target in <terrain> under <overlay> at height <height> above the floor
    And the observer has visual primary visibility at daylight with no intervening woods or partial cover
    When the sensor terrain modifier is inspected
    Then the terrain modifier is <modifier>
    Examples:
      | terrain | overlay | height | modifier |
      | LIGHT_FOREST | none | 0 | 1 |
      | HEAVY_FOREST | SMOKE | 0 | 2 |
      | HEAVY_FOREST | FIRE | 2 | 2 |
      | HEAVY_FOREST | FIRE | 3 | 0 |

  Scenario Outline: LOS geometry and modifiers 03 - infrared profiles
    Given infrared profile <profile> and a hulldown target with partial cover and no woods
    And target heat is <heat> plus heat <plus> and minus heat <minus>
    And the observer has primary infrared visibility
    When the sensor terrain modifier is inspected
    Then the terrain modifier is <modifier>
    Examples:
      | profile | heat | plus | minus | modifier |
      | unscaled | 0 | 0 | 0 | 7 |
      | unscaled | 4 | 0 | 0 | 5 |
      | unscaled | 16 | 0 | 0 | 3 |
      | scaled | 0 | 0 | 0 | 5 |
      | scaled | 0 | 10 | 0 | 4 |
      | scaled | 0 | 10.5 | 0 | 3 |
      | scaled | 0 | 18 | 0 | 2 |
      | scaled | 0 | 25 | 0 | 2 |
      | scaled | 0 | 25.5 | 0 | 1 |
      | scaled | 0 | 20 | 10 | 3 |
      | scaled | 0 | 10 | 20 | 5 |

  Scenario Outline: LOS geometry and modifiers 04 - cached identification
    Given the diagnostic cached contact has primary <primary> secondary <secondary> and terrain block <block>
    When normal and NB line of sight are requested
    Then detected is <detected> and identified is <identified>
    Examples:
      | primary | secondary | block | detected | identified |
      | True | False | False | True | True |
      | False | True | True | True | False |
      | False | False | False | False | False |
