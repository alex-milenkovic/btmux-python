# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:44:04.435158544Z","feature_name":"Ice evolution","feature_path":"features/movement/ice.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:3dd89ef41d364f164254d4a1457d7670e3fc995ffc21fae07d7d844cb42ecd07","scenarios":[{"index":4,"name":"Ice evolution 05 - melted neighbors affect later cells","scenario_hash":"9c7e0b482105c4813409716b01388e75288d8693bfd72e9d8539eef14ed12938","mutation_count":4,"result":{"Total":4,"Killed":4,"Survived":0,"Errors":0},"tested_at":"2026-09-08T00:35:24.326709840Z"},{"index":2,"name":"Ice evolution 03 - growth preserves depth and path integration","scenario_hash":"fa3680a94160d5ca1b2db75e8ec438d8d70dcfe461dbad41c6434ce758d24369","mutation_count":8,"result":{"Total":8,"Killed":8,"Survived":0,"Errors":0},"tested_at":"2026-09-07T21:11:53.715401823Z"}]}
# acceptance-mutation-manifest-end

# Ice evolution 01 - growth threshold and neighbors; Ice evolution 02 - melt threshold and neighbors; Ice evolution 03 - growth preserves depth and path integration; Ice evolution 04 - new ice remains waterlike during growth; Ice evolution 05 - melted neighbors affect later cells
Feature: Ice evolution
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Ice evolution 01 - growth threshold and neighbors
    Given one WATER candidate with <neighbors> waterlike neighbors and all other hexes GRASSLAND
    And ice percentage <percent> percentage draw <draw> and neighbor die <die>
    When ice growth runs
    Then candidate terrain is <terrain> and changed hex count is <count>
    Examples:
      | neighbors | percent | draw | die | terrain | count |
      | 0 | 50 | 50 | 6 | ICE | 1 |
      | 0 | 50 | 51 | 6 | WATER | 0 |
      | 1 | 100 | 100 | 1 | ICE | 1 |
      | 2 | 100 | 1 | 2 | WATER | 0 |
      | 2 | 100 | 1 | 3 | ICE | 1 |
      | 4 | 100 | 1 | 4 | WATER | 0 |
      | 4 | 100 | 1 | 5 | ICE | 1 |
      | 5 | 100 | 1 | 6 | WATER | 0 |
      | 6 | 100 | 1 | 6 | WATER | 0 |
      | 0 | 0 | 1 | 6 | WATER | 0 |
      | 0 | 101 | 100 | 6 | ICE | 1 |
      | 0 | -1 | 1 | 6 | WATER | 0 |

  Scenario Outline: Ice evolution 02 - melt threshold and neighbors
    Given one ICE candidate with <neighbors> ICE neighbors and all other hexes GRASSLAND
    And ice percentage <percent> percentage draw <draw> and neighbor die <die>
    When ice melting runs
    Then candidate terrain is <terrain> and changed hex count is <count>
    Examples:
      | neighbors | percent | draw | die | terrain | count |
      | 4 | 50 | 1 | 3 | WATER | 1 |
      | 5 | 50 | 1 | 1 | WATER | 1 |
      | 5 | 50 | 1 | 2 | ICE | 0 |
      | 6 | 50 | 1 | 3 | ICE | 0 |
      | 0 | 25 | 25 | 1 | WATER | 1 |
      | 0 | 25 | 26 | 1 | ICE | 0 |

  Scenario Outline: Ice evolution 03 - growth preserves depth and path integration
    Given a WATER hex at stored depth <depth> and no waterlike neighbors
    When ice growth at 100 percent runs and a mech path cost from adjacent GRASSLAND at height 0 is queried
    Then candidate terrain is ICE stored depth is <depth> and mech path cost is <cost>
    Examples:
      | depth | cost |
      | 0 | 1 |
      | 1 | 2 |
      | 2 | 3 |
      | 3 | 0 |

  Scenario Outline: Ice evolution 04 - new ice remains waterlike during growth
    Given WATER at 3 3 and 3 4 and 4 3 on an otherwise empty GRASSLAND map
    And growth percentage 100 with percentage draws 1 and neighbor dice <first> then 2 then 2
    When ice growth runs
    Then terrain at 3 3 is <terrain> and at 3 4 and 4 3 is WATER with changed hex count <count>
    Examples:
      | first | terrain | count |
      | 2 | WATER | 0 |
      | 3 | ICE | 1 |

  Scenario Outline: Ice evolution 05 - melted neighbors affect later cells
    Given an empty square ICE map of side <side> with stored elevation 1
    When melting at 100 percent runs with percentage draws 1
    Then WATER hex count is <count> and ICE hex count is 0
    Examples:
      | side | count |
      | 3 | 9 |
      | 4 | 16 |
