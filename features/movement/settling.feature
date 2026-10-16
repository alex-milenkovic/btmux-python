# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:45:17.537681134Z","feature_name":"Falling flooding and settling","feature_path":"features/movement/settling.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:f441cfbb68adbf2bde71e09343fa201f77d66238bcb53ff0edfad8bc9764911d","scenarios":[{"index":2,"name":"Falling flooding and settling 03 - jump and stand completion","scenario_hash":"d7a0443f61e3dbf813e64a63728e4087cca29cf54a36b586aa56284992a45238","mutation_count":12,"result":{"Total":12,"Killed":12,"Survived":0,"Errors":0},"tested_at":"2026-09-08T00:36:58.559224126Z"}]}
# acceptance-mutation-manifest-end

# Falling flooding and settling 01 - fall damage and facing; Falling flooding and settling 02 - section flooding; Falling flooding and settling 03 - jump and stand completion
Feature: Falling flooding and settling
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Falling flooding and settling 01 - fall damage and facing
    Given tonnage <tons> terrain <terrain> gravity <gravity> percent and facing 350 degrees
    When a fall of <levels> levels uses direction die <direction> and a successful pilot injury roll
    Then total fall damage is <damage> and facing and desired facing are <facing>
    Examples:
      | tons | terrain | gravity | levels | direction | damage | facing |
      | 50 | GRASSLAND | 100 | 1 | 1 | 5 | 350 |
      | 50 | GRASSLAND | 100 | 2 | 2 | 11 | 50 |
      | 50 | WATER | 100 | 2 | 4 | 5 | 170 |
      | 50 | HIGHWATER | 100 | 2 | 6 | 5 | 290 |
      | 50 | GRASSLAND | 50 | 2 | 3 | 5 | 110 |
      | 50 | GRASSLAND | 150 | 2 | 5 | 11 | 230 |
      | 50 | GRASSLAND | 100 | 0 | 1 | 0 | 350 |
      | 35 | GRASSLAND | 100 | 1 | 1 | 4 | 350 |

  Scenario Outline: Falling flooding and settling 02 - section flooding
    Given a MECH with movement <movement> posture <posture> in WATER at depth <depth>
    And section <section> front armor <front> rear armor <rear> and original rear armor <original>
    When flooding is evaluated
    Then that section is flooded <flooded>
    Examples:
      | movement | posture | depth | section | front | rear | original | flooded |
      | BIPED | UPRIGHT | 1 | LLEG | 0 | 0 | 0 | True |
      | BIPED | UPRIGHT | 1 | LARM | 0 | 0 | 0 | False |
      | QUAD | UPRIGHT | 1 | LARM | 0 | 0 | 0 | True |
      | BIPED | FALLEN | 1 | CTORSO | 10 | 0 | 5 | True |
      | BIPED | UPRIGHT | 2 | CTORSO | 10 | 0 | 5 | True |
      | BIPED | UPRIGHT | 2 | CTORSO | 10 | 0 | 0 | False |
      | BIPED | UPRIGHT | 2 | CTORSO | 0 | 5 | 5 | True |
      | BIPED | UPRIGHT | 0 | LLEG | 0 | 0 | 0 | False |

  Scenario Outline: Falling flooding and settling 03 - jump and stand completion
    Given movement workflow <workflow>
    When the workflow runs to completion using successful required pilot rolls
    Then observable state is <result>
    Examples:
      | workflow | result |
      | INTACT_JUMP | LANDED_WITHOUT_LANDING_ROLL |
      | EARLY_LAND | JUMP_CANCELLED_AND_STABILIZING |
      | QUAD_STAND | STANDING_WITHOUT_ROLL |
      | STAND_CHECK | BTH_REPORTED_NO_STATE_CHANGE |
      | STAND_BTH_13 | REFUSED_WITH_ANYWAY_HINT |
      | STAND_CAREFUL | MINUS_TWO_ROLL_DOUBLE_TIME |
