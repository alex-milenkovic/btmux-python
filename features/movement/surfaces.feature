# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:45:36.090661277Z","feature_name":"Ice and bridge failure","feature_path":"features/movement/surfaces.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:d90ba2a5659288b37111aae9d739b020ef940a7b55306527250ef14f8701479c","scenarios":[]}
# acceptance-mutation-manifest-end

# Ice and bridge failure 01 - blast thresholds; Ice and bridge failure 02 - other occupants; Ice and bridge failure 03 - trigger chance exemptions
Feature: Ice and bridge failure
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Ice and bridge failure 01 - blast thresholds
    Given target terrain <terrain> stored elevation <elevation> and bridge protection <protected>
    When a weapon of damage <damage> hits the hex with surface draw <draw>
    Then target terrain is <result> and stored elevation is <stored>
    Examples:
      | terrain | elevation | protected | damage | draw | result | stored |
      | ICE | 2 | False | 5 | 5 | WATER | 2 |
      | ICE | 2 | False | 5 | 6 | ICE | 2 |
      | BRIDGE | 3 | False | 10 | 10 | WATER | 1 |
      | BRIDGE | 3 | False | 10 | 11 | BRIDGE | 3 |
      | BRIDGE | 3 | True | 40 | 1 | BRIDGE | 3 |
      | GRASSLAND | 0 | False | 15 | 1 | GRASSLAND | 0 |

  Scenario Outline: Ice and bridge failure 02 - other occupants
    Given ICE at stored depth 2 with another occupant of class <unit> movement <movement> height <z> waterproof <waterproof>
    When the triggering unit breaks through from below
    Then the other occupant has cached terrain WATER fall levels <levels> and destroyed state <destroyed>
    Examples:
      | unit | movement | z | waterproof | levels | destroyed |
      | MECH | BIPED | 0 | False | 2 | False |
      | VEH_GROUND | TRACK | 0 | False | 2 | True |
      | VEH_GROUND | TRACK | 0 | True | 2 | True |
      | VEH_GROUND | HOVER | 0 | False | 0 | False |
      | MECH | BIPED | 2 | False | 0 | False |
      | MECH | BIPED | -1 | False | 0 | False |

  Scenario Outline: Ice and bridge failure 03 - trigger chance exemptions
    Given a unit of class <unit> movement <movement> on depth 2 ICE
    When the drop through ice chance uses die <die>
    Then shared terrain is <terrain> and drop happened is <dropped>
    Examples:
      | unit | movement | die | terrain | dropped |
      | MECH | BIPED | 1 | WATER | True |
      | MECH | BIPED | 2 | ICE | False |
      | VEH_GROUND | HOVER | 1 | ICE | False |
      | VEH_NAVAL | SUB | 1 | ICE | False |
      | BSUIT | BIPED | 1 | ICE | False |
