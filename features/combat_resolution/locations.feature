# Combat hit location integration 01 - actual source selectors; Combat hit location integration 02 - pod transfer over destroyed location
Feature: Combat hit location integration
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat hit location integration 01 - actual source selectors
    Given a real firing fixture with selector condition <condition>
    When an otherwise successful shot uses location draw <roll>
    Then location family is <family>
    Examples:
      | condition | roll | family |
      | upright-MECH-partial-cover | 1 | punch |
      | MW-shooter-at-MECH-target-height | 1 | kick |
      | BA-shooter-swarming-MECH-target | 7 | swarm |
      | ordinary-MECH | 7 | normal |
      | critproof-MECH | 2 | critproof |
      | FASA-ground | 7 | FASA-vehicle |
      | advanced-ground | 7 | advanced-vehicle |

  Scenario Outline: Combat hit location integration 02 - pod transfer over destroyed location
    Given a normal NARC hit initially selecting a destroyed MECH left arm and live left torso
    When attachment resolves
    Then pod location is <location> and destroyed arm has no pod
    Examples:
      | location |
      | LTORSO |
