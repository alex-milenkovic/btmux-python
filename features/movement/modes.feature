# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:44:35.813094187Z","feature_name":"Movement modes","feature_path":"features/movement/modes.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:41ee6af17f2af25f64a143e508f6ae3354432893be1807fbc07ed26b77ce4bb4","scenarios":[{"index":1,"name":"Movement modes 02 - eligibility differences","scenario_hash":"3bdf9f6585f75942e439ea09a49d756a8e9678a819abcf81ddffca8cfa7455a1","mutation_count":100,"result":{"Total":100,"Killed":100,"Survived":0,"Errors":0},"tested_at":"2026-09-08T00:36:14.098250190Z"}]}
# acceptance-mutation-manifest-end

# Movement modes 01 - delayed toggle; Movement modes 02 - eligibility differences; Movement modes 03 - completion and interruption; Movement modes 04 - mode effects
Feature: Movement modes
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Movement modes 01 - delayed toggle
    Given unit class <unit> with movement mode <initial>
    When the pilot requests <mode>
    And the session advances <ticks> seconds
    Then movement mode is <active> and pending transition is <pending>
    Examples:
      | unit | initial | mode | ticks | active | pending |
      | MECH | NONE | sprint | 29 | NONE | SPRINT_ON |
      | MECH | NONE | sprint | 30 | SPRINT | NONE |
      | BSUIT | NONE | sprint | 14 | NONE | SPRINT_ON |
      | BSUIT | NONE | sprint | 15 | SPRINT | NONE |
      | MW | NONE | evade | 15 | EVADE | NONE |
      | MECH | NONE | evade | 30 | EVADE | NONE |
      | MECH | SPRINT | sprint | 29 | SPRINT | SPRINT_OFF |
      | MECH | SPRINT | sprint | 30 | NONE | NONE |
      | MECH | EVADE | evade | 30 | NONE | NONE |
      | MECH | NONE | dodge | 0 | NONE | DODGE_ON |
      | MECH | NONE | dodge | 1 | DODGE | NONE |
      | MECH | DODGE | dodge | 29 | DODGE | DODGE_OFF |
      | MECH | DODGE | dodge | 30 | NONE | NONE |

  Scenario Outline: Movement modes 02 - eligibility differences
    Given movement condition <condition>
    When the pilot requests <mode>
    Then the command is <outcome> and a new transition is <scheduled>
    Examples:
      | condition | mode | outcome | scheduled |
      | FORTIFIED | sprint | REJECTED | False |
      | OOD | evade | REJECTED | False |
      | FALLEN | dodge | REJECTED | False |
      | STANDING | sprint | REJECTED | False |
      | JUMPING | sprint | REJECTED | False |
      | JUMPING | evade | REJECTED | False |
      | JUMPING | dodge | ACCEPTED | True |
      | TOWING | evade | REJECTED | False |
      | TOWING | sprint | REJECTED | False |
      | TOWING | dodge | ACCEPTED | True |
      | IN_WATER | sprint | REJECTED | False |
      | IN_WATER_SPRINTING | sprint | ACCEPTED | True |
      | HIP_DISABLED | evade | REJECTED | False |
      | HIP_DISABLED_EVADING | evade | ACCEPTED | True |
      | WEAPON_RECYCLE | dodge | ACCEPTED | True |
      | WEAPON_RECYCLE | sprint | REJECTED | False |
      | LIMB_RECYCLE | dodge | REJECTED | False |
      | NO_DODGE_ADVANTAGE | dodge | REJECTED | False |
      | OTHER_PILOT | dodge | REJECTED | False |
      | SPRINTING | evade | REJECTED | False |
      | CHANGING_MODE | sprint | REJECTED | False |
      | CHARGING | evade | REJECTED | False |
      | MOUNTED | sprint | REJECTED | False |
      | LEFT_LEG_DESTROYED | evade | REJECTED | False |
      | QUAD_FRONT_LEG_DESTROYED | sprint | ACCEPTED | True |

  Scenario Outline: Movement modes 03 - completion and interruption
    Given a pending <mode> activation with completion condition <condition>
    When its due event runs
    Then movement mode is <active> and pending transition is NONE
    Examples:
      | mode | condition | active |
      | sprint | SHUTDOWN | NONE |
      | evade | DESTROYED | NONE |
      | dodge | LIMB_RECYCLE | NONE |
      | dodge | WEAPON_RECYCLE | DODGE |

  Scenario Outline: Movement modes 04 - mode effects
    Given active mode <mode> and actual speed <speed> KPH
    When movement heat is evaluated
    Then movement heat contribution is <heat>
    Examples:
      | mode | speed | heat |
      | SPRINT | 10.75 | 3 |
      | EVADE | 10.75 | 3 |
      | SPRINT | 0 | 0 |
      | EVADE | -10.75 | 3 |
      | NONE | 10.75 | 1 |
