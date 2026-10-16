# Map terrain visibility 01 - clear strip; Map terrain visibility 02 - fire illumination; Map terrain visibility 03 - terrain horizons; Map terrain visibility 04 - rectangle bounds
Feature: Map terrain visibility
  Background:
    Given a fresh sensor session with ready units and event time zero
    And an upright observer at hex 2 1 Z 0 facing south on a clear map

  Scenario Outline: Map terrain visibility 01 - clear strip
    Given selected sensors <pair> map visibility <visibility> light <light> and clairvoyance <clairvoyant>
    When the pilot renders rectangle origin 2 2 width 1 height 5
    Then row-major visibility flags are <flags>
    Examples:
      | pair | visibility | light | clairvoyant | flags |
      | VV | 3 | 2 | False | 7,7,1,1,1 |
      | LL | 3 | 0 | False | 7,7,7,7,7 |
      | RR | 30 | 2 | False | 1,1,1,1,1 |
      | BB | 30 | 2 | True | 7,7,7,7,7 |
      | IV | 3 | 2 | False | 7,7,7,7,7 |

  Scenario Outline: Map terrain visibility 02 - fire illumination
    Given visual sensors map visibility 3 and light 0
    And a <source> light source at hex 2 5
    When the pilot renders rectangle origin 2 2 width 1 height 5
    Then row-major visibility flags are <flags>
    Examples:
      | source | flags |
      | none | 7,7,1,1,1 |
      | fire-decoration | 7,7,15,15,15 |
      | jellied-unit | 7,7,15,15,15 |

  Scenario Outline: Map terrain visibility 03 - terrain horizons
    Given sensors <pair> visibility 30 light 0 and hex 2 2 containing <terrain> at floor <floor>
    When the pilot renders rectangle origin 2 2 width 1 height 3
    Then row-major visibility flags are <flags>
    Examples:
      | pair | terrain | floor | flags |
      | VV | CLEAR | 3 | 7,1,1 |
      | VV | LIGHT_FOREST | 0 | 7,7,7 |
      | EE | MOUNTAINS | 0 | 7,1,1 |
      | LL | WATER | -1 | 7,1,1 |
      | VV | WATER | -1 | 7,7,7 |

  Scenario Outline: Map terrain visibility 04 - rectangle bounds
    Given a clear 80 by 60 map
    When the pilot renders rectangle origin 0 0 width <width> height <height>
    Then the render is <accepted> and cell count is <count>
    Examples:
      | width | height | accepted | count |
      | 70 | 45 | True | 3150 |
      | 71 | 45 | False | 0 |
      | 70 | 46 | False | 0 |
      | 0 | 10 | False | 0 |
