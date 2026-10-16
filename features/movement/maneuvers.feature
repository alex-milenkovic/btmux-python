# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:44:17.355946431Z","feature_name":"Prone and bootlegger maneuvers","feature_path":"features/movement/maneuvers.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:9142bee33df028cada77a7b95c7705aa2402cfdff56249863c73ebde3c93249f","scenarios":[]}
# acceptance-mutation-manifest-end

# Prone and bootlegger maneuvers 01 - bootlegger success; Prone and bootlegger maneuvers 02 - controlled drop; Prone and bootlegger maneuvers 03 - thrash targeting
Feature: Prone and bootlegger maneuvers
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Prone and bootlegger maneuvers 01 - bootlegger success
    Given tonnage <tons> speed <speed> MP facing <facing> and a successful piloting roll
    When the pilot requests bootlegger <direction>
    Then piloting modifier is <modifier> facing and desired facing are <heading> and actual speed is <remaining> MP
    And participating legs recycle for 30 seconds
    Examples:
      | tons | speed | facing | direction | modifier | heading | remaining |
      | 35 | 4 | 350 | R | 1 | 80 | 2 |
      | 55 | 8 | 10 | L | 2 | 280 | 4 |
      | 75 | 12 | 270 | R | 4 | 0 | 6 |
      | 80 | 13 | 90 | L | 6 | 0 | 6.5 |

  Scenario Outline: Prone and bootlegger maneuvers 02 - controlled drop
    Given actual speed <speed> KPH and piloting result <roll>
    When the pilot requests prone
    Then the unit is fallen with zero actual and desired speeds and fall levels applied are <levels>
    Examples:
      | speed | roll | levels |
      | 0 | UNUSED | 0 |
      | 21.5 | UNUSED | 0 |
      | 21.6 | PASS | 0 |
      | 21.6 | FAIL | 1 |
      | 43 | FAIL | 1 |
      | 43.1 | FAIL | 2 |
      | -43.1 | FAIL | 2 |

  Scenario Outline: Prone and bootlegger maneuvers 03 - thrash targeting
    Given a prone 50 ton mech and enemy battlesuit range <range> with state <state>
    When the pilot thrashes on GRASSLAND with a successful piloting roll
    Then battlesuit damage total is <damage> and intact limbs recycle for 60 seconds
    Examples:
      | range | state | damage |
      | 1 | GROUND | 16 |
      | 1.01 | GROUND | 0 |
      | 0 | JUMPING | 0 |
      | 0 | OOD | 0 |
      | 0 | FRIENDLY | 0 |
      | 0 | MOUNTED | 16 |
