# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:45:53.338853037Z","feature_name":"Path cost coordinates","feature_path":"features/path_costs/coordinates.feature","background_hash":"a9e4b298c98505d56a4421bb1e3a0897a7415a19cb4de011dea8d230a9948c10","implementation_hash":"sha256:b95866163556b3fca40d500f5155893d6295170aaccb37a90a9debfcad070dcd","scenarios":[]}
# acceptance-mutation-manifest-end

# Path cost coordinates 01 - legacy destination guard; Path cost coordinates 02 - safe coordinate domain
Feature: Path cost coordinates
  Background:
    Given all map hexes are GRASSLAND with stored elevation 0

  Scenario Outline: Path cost coordinates 01 - legacy destination guard
    Given map dimensions <width> by <height>
    And source coordinates 0 0 and destination coordinates <tx> <ty>
    When all three path costs are requested
    Then each path cost is <cost>
    Examples:
      | width | height | tx | ty | cost |
      | 4     | 4      | 3  | 3  | 1    |
      | 4     | 4      | -1 | 0  | 0    |
      | 4     | 4      | 0  | -1 | 0    |
      | 4     | 4      | 0  | 4  | 0    |
      | 2     | 4      | 1  | 1  | 1    |
      | 2     | 4      | 1  | 2  | 0    |
      | 2     | 4      | 0  | 3  | 0    |
      | 4     | 2      | 3  | 1  | 1    |
      | 4     | 2      | 0  | 2  | 0    |
      | 4     | 4      | 0  | 0  | 1    |

  Scenario Outline: Path cost coordinates 02 - safe coordinate domain
    Given map dimensions <width> by <height>
    And source coordinates <fx> <fy> and destination coordinates <tx> <ty>
    When all three path costs are requested
    Then each path cost is <cost>
    Examples:
      | width | height | fx | fy | tx | ty | cost |
      | 4     | 4      | 0  | 0  | 4  | 0  | 0    |
      | 4     | 4      | 0  | 0  | 5  | 1  | 0    |
      | 4     | 4      | -1 | 0  | 1  | 0  | 0    |
      | 4     | 4      | 0  | -1 | 1  | 0  | 0    |
      | 4     | 4      | 4  | 0  | 1  | 0  | 0    |
      | 4     | 4      | 0  | 4  | 1  | 0  | 0    |
      | 4     | 4      | 1  | 2  | 2  | 1  | 1    |
      | 4     | 4      | 0  | 3  | 3  | 0  | 1    |
      | 2     | 4      | 0  | 3  | 1  | 1  | 1    |
