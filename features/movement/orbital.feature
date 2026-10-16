# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:44:54.855814688Z","feature_name":"Orbital drop","feature_path":"features/movement/orbital.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:4e66cf8f6988e25bad3a3381f46a6b85d53020002d11e60978b48383805bf812","scenarios":[{"index":4,"name":"Orbital drop 05 - breached cocoon reaches free fall impact","scenario_hash":"bfb316ce68b91ce61505ee27d9f364aaedf3c951f0a1e25a6a18d81cc25fc817","mutation_count":12,"result":{"Total":12,"Killed":12,"Survived":0,"Errors":0},"tested_at":"2026-09-08T00:36:36.144707120Z"}]}
# acceptance-mutation-manifest-end

# Orbital drop 01 - descent and touchdown; Orbital drop 02 - cocoon breach; Orbital drop 03 - touchdown roll margin; Orbital drop 04 - damage interception; Orbital drop 05 - breached cocoon reaches free fall impact
Feature: Orbital drop
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Orbital drop 01 - descent and touchdown
    Given a ready 50 ton mech at height <height> over GRASSLAND with pilot roll 12
    When orbital drop is initiated at its current coordinates and advances <ticks> seconds
    Then height is <z> cocoon is <cocoon> and orbital descent is <pending>
    Examples:
      | height | ticks | z | cocoon | pending |
      | 300 | 0 | 300 | 11 | True |
      | 7 | 1 | 5 | 11 | True |
      | 7 | 2 | 3 | 11 | True |
      | 7 | 3 | 1 | 11 | True |
      | 7 | 4 | 0 | 0 | False |
      | 2 | 1 | 0 | 0 | False |
      | 0 | 1 | 0 | 0 | False |

  Scenario Outline: Orbital drop 02 - cocoon breach
    Given an orbital dropping mech at height 20 with cocoon 11 and jump capability <jump> MP
    When its cocoon takes <damage> damage
    Then cocoon is <cocoon> orbital descent is <ood> and free fall is <fall>
    Examples:
      | jump | damage | cocoon | ood | fall |
      | 0 | 10 | 1 | True | False |
      | 0 | 11 | 0 | False | True |
      | 0 | 20 | 0 | False | True |
      | 1 | 11 | -1 | True | False |
      | 0.99 | 11 | 0 | False | True |

  Scenario Outline: Orbital drop 03 - touchdown roll margin
    Given an orbital dropping MECH ready to touch down with piloting target 5 before terrain and cocoon modifiers
    And touchdown terrain <terrain> cocoon <cocoon> and pilot roll <roll>
    When the touchdown event runs
    Then required roll is <target> and fall levels applied are <levels>
    Examples:
      | terrain | cocoon | roll | target | levels |
      | GRASSLAND | 11 | 5 | 5 | 0 |
      | GRASSLAND | 11 | 4 | 5 | 4 |
      | ROAD | 1 | 4 | 5 | 2 |
      | WATER | 11 | 6 | 7 | 4 |
      | ROUGH | 11 | 7 | 8 | 4 |
      | GRASSLAND | -1 | 8 | 9 | 4 |
      | HIGHWATER | 11 | 6 | 7 | 4 |

  Scenario Outline: Orbital drop 04 - damage interception
    Given an orbital dropping mech with cocoon <initial> and intact torso armor 20
    When external torso damage 5 is resolved with interception roll <roll>
    Then cocoon is <cocoon> and torso armor is <armor>
    Examples:
      | initial | roll | cocoon | armor |
      | 11 | 8 | 11 | 15 |
      | 11 | 9 | 6 | 20 |
      | -1 | 9 | -1 | 15 |

  Scenario Outline: Orbital drop 05 - breached cocoon reaches free fall impact
    Given an orbital dropping 50 ton mech at height 7 with no jump jets and cocoon 11
    When its cocoon takes 11 damage and the session advances <ticks> seconds
    Then height is <height> free fall is <pending> and impact fall levels are <levels>
    Examples:
      | ticks | height | pending | levels |
      | 3 | 5 | True | 0 |
      | 6 | 2 | True | 0 |
      | 9 | 0 | False | 10 |
