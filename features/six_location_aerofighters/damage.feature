# Six location fighter damage 01 - normal armor exhaustion
# Six location fighter damage 02 - already empty routing
# Six location fighter damage 03 - damage entry distinctions
# Six location fighter damage 04 - engine depletion
# Six location fighter damage 05 - retained equipment
Feature: Six location fighter damage
  Background:
    Given a fresh fighter with six sections internal and original internal 10 no environmental damage or critical request unless the case overrides it

  Scenario Outline: Six location fighter damage 01 - normal armor exhaustion
    Given section <section> armor <armor> and Fuselage armor <fuselage>
    When an ordinary nonrear hit deals <damage> to that section
    Then section armor Fuselage armor and craft result are <after> <fuselage_after> and <result>
    Examples:
      | section | armor | fuselage | damage | after | fuselage_after | result |
      | Nose | 3 | 30 | 8 | 0 | 30 | alive |
      | Left_Wing | 3 | 30 | 8 | 0 | 30 | alive |
      | Right_Wing | 3 | 30 | 8 | 0 | 30 | alive |
      | Fuselage | 3 | 3 | 8 | 0 | 0 | alive |
      | Cockpit | 3 | 30 | 3 | 0 | 30 | destroyed |
      | Engine | 3 | 30 | 3 | 0 | 30 | thrust-lost |
      | Nose | 24 | 30 | 5 | 19 | 30 | alive |
      | Cockpit | 16 | 30 | 1 | 15 | 30 | shared-head-injury |

  Scenario Outline: Six location fighter damage 02 - already empty routing
    Given section <section> armor zero and Fuselage armor <fuselage>
    When an ordinary nonrear hit deals <damage> to that section
    Then Fuselage armor is <after> and the craft result is <result>
    Examples:
      | section | fuselage | damage | after | result |
      | Nose | 30 | 8 | 22 | alive |
      | Left_Wing | 30 | 8 | 22 | alive |
      | Right_Wing | 30 | 8 | 22 | alive |
      | Engine | 30 | 8 | 22 | no-new-engine-depletion-effect |
      | Cockpit | 30 | 8 | 22 | no-cockpit-injury |
      | Fuselage | 0 | 1 | 0 | destroyed |
      | Left_Wing | 0 | 1 | 0 | destroyed |
      | Nose | 3 | 8 | 0 | alive |

  Scenario Outline: Six location fighter damage 03 - damage entry distinctions
    Given the fighter damage boundary <fixture>
    When the specified damage entry runs
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | Right_Wing15-Fuselage30-rear-hit5 | source-rear-remap-Fuselage25-Right_Wing15 |
      | Left_Wing15-Fuselage30-rear-hit5 | Left_Wing10-Fuselage30 |
      | Nose3-Fuselage30-explicit-transfer-hit8 | Nose0-Fuselage25 |
      | Fuselage3-explicit-transfer-hit8 | destroyed |
      | Nose3-Fuselage30-internal-only8-transfer-disabled | Nose0-Fuselage30-internals10 |
      | Nose3-Fuselage30-internal-only8-transfer-enabled | Nose0-Fuselage25-internals10 |
      | Nose3-Fuselage30-internal-only8-CASE | Nose0-Fuselage30-internals10 |
      | empty-Fuselage-SI50-hit1 | destroyed-SI-not-a-health-pool |
      | all-positive-armor-SI0 | alive-before-damage |
      | Engine0-Fuselage30-deferred-critical-hit1-count8 | Fuselage29-critical-in-Fuselage-no-Engine-effect |

  Scenario Outline: Six location fighter damage 04 - engine depletion
    Given Engine armor 3 with flight state <flight>
    When ordinary damage 3 exhausts Engine armor
    Then the observable engine outcome is <outcome>
    Examples:
      | flight | outcome |
      | airborne | speed-maxspeed-vertical-zero-fall-scheduled |
      | landed | speed-maxspeed-vertical-zero-no-new-airborne-fall-event |

  Scenario Outline: Six location fighter damage 05 - retained equipment
    Given a ready fighter weapon in <section> with armor 3
    When ordinary damage 8 exhausts that armor
    Then internals remain 10 and the individual weapon remains functional
    Examples:
      | section |
      | Nose |
      | Left_Wing |
      | Right_Wing |
      | Fuselage |
