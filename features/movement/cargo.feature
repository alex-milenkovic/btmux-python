# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:43:20.320207165Z","feature_name":"Cargo and enhanced speed","feature_path":"features/movement/cargo.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:ee252b93a27521ee6532c87f8db3598485b1d6475f5a0074d0f1e7b28153991d","scenarios":[{"index":0,"name":"Cargo and enhanced speed 01 - cached speed enhancements","scenario_hash":"b13dbc5b5d514217d287da2a46e3afbbecffb04f5e25ffe88d72ba4caa1fa876","mutation_count":16,"result":{"Total":16,"Killed":16,"Survived":0,"Errors":0},"tested_at":"2026-09-07T21:05:18.505173607Z"}]}
# acceptance-mutation-manifest-end

# Cargo and enhanced speed 01 - cached speed enhancements; Cargo and enhanced speed 02 - overweight and load
Feature: Cargo and enhanced speed
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Cargo and enhanced speed 01 - cached speed enhancements
    Given cached unboosted maximum speed 64.5 KPH and no cargo
    And enabled speed enhancements <enhancements>
    When the effective maximum speed is requested
    Then effective maximum speed is <speed> KPH
    Examples:
      | enhancements | speed |
      | NONE | 64.5 |
      | MASC | 86 |
      | SUPERCHARGER | 86 |
      | SPRINT | 86 |
      | MASC_SUPERCHARGER | 107.5 |
      | MASC_SPRINT | 107.5 |
      | MASC_SUPERCHARGER_SPRINT | 129 |
      | SPRINT_SPEED_DEMON | 96.75 |

  Scenario Outline: Cargo and enhanced speed 02 - overweight and load
    Given nominal mass 50 tons actual mass <actual> tons and effective carried mass <load> tons
    And unboosted maximum speed 64.5 KPH with weight overspeeding disabled
    When the effective maximum speed is requested
    Then effective maximum speed is <speed> KPH
    Examples:
      | actual | load | speed |
      | 50 | 0 | 64.5 |
      | 50 | 25 | 43 |
      | 100 | 0 | 25.8 |
      | 50 | 100 | 21.5 |
      | 50 | 101 | 0 |
