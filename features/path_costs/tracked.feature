# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:46:32.490780598Z","feature_name":"Tracked path costs","feature_path":"features/path_costs/tracked.feature","background_hash":"5bf732482e542abb4705414822a26b14435301de5198f52cc5c19bbaed0542c1","implementation_hash":"sha256:6094acc734c0ce872249937a00e95c3b36848a88ade982880388b5c7b10d2248","scenarios":[{"index":0,"name":"Tracked path costs 01 - terrain charges","scenario_hash":"3c1d5c2a9162c3e4e97e1951a91e5650aaf3e1bd087c86de47d671c9841bdf00","mutation_count":51,"result":{"Total":51,"Killed":51,"Survived":0,"Errors":0},"tested_at":"2026-09-07T14:46:40.673122535Z"}]}
# acceptance-mutation-manifest-end

# Tracked path costs 01 - terrain charges; Tracked path costs 02 - signed heights and water
Feature: Tracked path costs
  Background:
    Given a fresh 4 by 4 path-cost map with source at 0 0 and destination at 1 0

  Scenario Outline: Tracked path costs 01 - terrain charges
    Given source terrain GRASSLAND with stored elevation 0
    And destination terrain <terrain> with stored elevation <elevation>
    When the tracked path cost is requested
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

  Scenario Outline: Tracked path costs 02 - signed heights and water
    Given source terrain <source> with stored elevation <source_elevation>
    And destination terrain <terrain> with stored elevation <elevation>
    When the tracked path cost is requested
    Then the path cost is <cost>
    Examples:
      | source       | source_elevation | terrain      | elevation | cost |
      | GRASSLAND    | 0                | GRASSLAND    | 2         | 0    |
      | GRASSLAND    | 1                | GRASSLAND    | 0         | 2    |
      | GRASSLAND    | 2                | GRASSLAND    | 0         | 0    |
      | HEAVY_FOREST | 1                | GRASSLAND    | 1         | 1    |
      | GRASSLAND    | 0                | WATER        | 0         | 0    |
      | GRASSLAND    | 0                | WATER        | 1         | 0    |
      | WATER        | 3                | WATER        | 3         | 0    |
      | WATER        | 1                | GRASSLAND    | 0         | 2    |
      | WATER        | 1                | GRASSLAND    | 1         | 0    |
      | GRASSLAND    | 0                | ICE          | 1         | 2    |
      | GRASSLAND    | 1                | ICE          | 1         | 0    |
      | ICE          | 2                | ICE          | 1         | 2    |
      | GRASSLAND    | 1                | HEAVY_FOREST | 0         | 0    |
