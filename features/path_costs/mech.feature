# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:46:20.725697834Z","feature_name":"Mech path costs","feature_path":"features/path_costs/mech.feature","background_hash":"5bf732482e542abb4705414822a26b14435301de5198f52cc5c19bbaed0542c1","implementation_hash":"sha256:868ec3dd40bf99b65f02dcb7f7d149cc37858964545af1011b9beb1cdf99c4c5","scenarios":[{"index":0,"name":"Mech path costs 01 - terrain charges","scenario_hash":"246795d804724db87d410c72187ddea4a29a36857598c349c4f4780cafa87461","mutation_count":51,"result":{"Total":51,"Killed":51,"Survived":0,"Errors":0},"tested_at":"2026-09-07T14:46:23.101105342Z"}]}
# acceptance-mutation-manifest-end

# Mech path costs 01 - terrain charges; Mech path costs 02 - signed heights and water
Feature: Mech path costs
  Background:
    Given a fresh 4 by 4 path-cost map with source at 0 0 and destination at 1 0

  Scenario Outline: Mech path costs 01 - terrain charges
    Given source terrain GRASSLAND with stored elevation 0
    And destination terrain <terrain> with stored elevation <elevation>
    When the mech path cost is requested
    Then the path cost is <cost>
    Examples:
      | terrain      | elevation | cost |
      | GRASSLAND    | 0         | 1    |
      | GRASSLAND    | 2         | 3    |
      | LIGHT_FOREST | 0         | 2    |
      | LIGHT_FOREST | 2         | 4    |
      | ROUGH        | 0         | 2    |
      | HEAVY_FOREST | 0         | 3    |
      | HEAVY_FOREST | 2         | 5    |
      | MOUNTAINS    | 0         | 3    |
      | MOUNTAINS    | 1         | 4    |
      | ROAD         | 1         | 2    |
      | BUILDING     | 0         | 1    |
      | WALL         | 0         | 1    |
      | DESERT       | 0         | 1    |
      | BRIDGE       | 2         | 3    |
      | SNOW         | 0         | 1    |
      | HIGHWATER    | 1         | 2    |
      | UNKNOWN_TERRAIN | 0      | 1    |

  Scenario Outline: Mech path costs 02 - signed heights and water
    Given source terrain <source> with stored elevation <source_elevation>
    And destination terrain <terrain> with stored elevation <elevation>
    When the mech path cost is requested
    Then the path cost is <cost>
    Examples:
      | source       | source_elevation | terrain   | elevation | cost |
      | GRASSLAND    | 0                | GRASSLAND | 1         | 2    |
      | GRASSLAND    | 0                | GRASSLAND | 3         | 0    |
      | GRASSLAND    | 2                | GRASSLAND | 0         | 3    |
      | GRASSLAND    | 3                | GRASSLAND | 0         | 0    |
      | MOUNTAINS    | 1                | GRASSLAND | 1         | 1    |
      | GRASSLAND    | 0                | WATER     | 0         | 1    |
      | GRASSLAND    | 2                | WATER     | 0         | 3    |
      | GRASSLAND    | 3                | WATER     | 0         | 0    |
      | GRASSLAND    | 0                | WATER     | 1         | 0    |
      | WATER        | 1                | WATER     | 1         | 0    |
      | WATER        | 2                | GRASSLAND | 0         | 3    |
      | WATER        | 1                | GRASSLAND | 1         | 3    |
      | GRASSLAND    | 1                | ICE       | 1         | 3    |
      | GRASSLAND    | 1                | ICE       | 2         | 0    |
      | ICE          | 2                | ICE       | 1         | 2    |
