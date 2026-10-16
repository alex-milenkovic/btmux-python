# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:46:08.941800818Z","feature_name":"Hover path costs","feature_path":"features/path_costs/hover.feature","background_hash":"5bf732482e542abb4705414822a26b14435301de5198f52cc5c19bbaed0542c1","implementation_hash":"sha256:f70dc36586d19c9181dfe78af7624a9d6a8aedd4f5f92fb90db08037bbb36737","scenarios":[{"index":0,"name":"Hover path costs 01 - terrain charges","scenario_hash":"5a93516a35029f5e48659ed9d484de451a451a6096b7b70cde258e337c224f67","mutation_count":51,"result":{"Total":51,"Killed":51,"Survived":0,"Errors":0},"tested_at":"2026-09-07T14:45:40.208923231Z"}]}
# acceptance-mutation-manifest-end

# Hover path costs 01 - terrain charges; Hover path costs 02 - signed heights and water
Feature: Hover path costs
  Background:
    Given a fresh 4 by 4 path-cost map with source at 0 0 and destination at 1 0

  Scenario Outline: Hover path costs 01 - terrain charges
    Given source terrain GRASSLAND with stored elevation 0
    And destination terrain <terrain> with stored elevation <elevation>
    When the hover path cost is requested
    Then the path cost is <cost>
    Examples:
      | terrain      | elevation | cost |
      | GRASSLAND    | 0         | 1    |
      | GRASSLAND    | 1         | 2    |
      | LIGHT_FOREST | 0         | 2    |
      | LIGHT_FOREST | 1         | 3    |
      | ROUGH        | 0         | 2    |
      | ROUGH        | 1         | 3    |
      | HEAVY_FOREST | 0         | 0    |
      | MOUNTAINS    | 0         | 3    |
      | MOUNTAINS    | 1         | 4    |
      | ROAD         | 1         | 2    |
      | BUILDING     | 0         | 1    |
      | WALL         | 0         | 1    |
      | DESERT       | 0         | 1    |
      | BRIDGE       | 1         | 2    |
      | SNOW         | 0         | 1    |
      | HIGHWATER    | 1         | 2    |
      | UNKNOWN_TERRAIN | 0      | 1    |

  Scenario Outline: Hover path costs 02 - signed heights and water
    Given source terrain <source> with stored elevation <source_elevation>
    And destination terrain <terrain> with stored elevation <elevation>
    When the hover path cost is requested
    Then the path cost is <cost>
    Examples:
      | source       | source_elevation | terrain      | elevation | cost |
      | GRASSLAND    | 0                | GRASSLAND    | 2         | 0    |
      | GRASSLAND    | 1                | GRASSLAND    | 0         | 2    |
      | GRASSLAND    | 2                | GRASSLAND    | 0         | 0    |
      | HEAVY_FOREST | 1                | GRASSLAND    | 1         | 1    |
      | GRASSLAND    | 0                | WATER        | 0         | 1    |
      | GRASSLAND    | 0                | WATER        | 1         | 1    |
      | GRASSLAND    | 0                | WATER        | 2         | 0    |
      | GRASSLAND    | 1                | WATER        | 1         | 0    |
      | WATER        | 3                | WATER        | 3         | 1    |
      | WATER        | 3                | WATER        | 2         | 1    |
      | WATER        | 3                | WATER        | 1         | 0    |
      | WATER        | 1                | GRASSLAND    | 0         | 2    |
      | WATER        | 1                | GRASSLAND    | 1         | 0    |
      | GRASSLAND    | 0                | ICE          | 1         | 2    |
      | GRASSLAND    | 1                | ICE          | 1         | 0    |
      | ICE          | 2                | ICE          | 1         | 2    |
      | GRASSLAND    | 1                | HEAVY_FOREST | 0         | 0    |
