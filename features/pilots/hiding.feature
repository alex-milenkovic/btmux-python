# Hiding and packs 01 - completion deadlines
# Hiding and packs 02 - hide gates and interruption
# Hiding and packs 03 - jettison slot semantics
# Hiding and packs 04 - jettison runtime coherence
Feature: Hiding and packs
  Background:
    Given ordinary battle armor controls on a source map with normal clock and LOS consumers

  Scenario Outline: Hiding and packs 01 - completion deadlines
    Given hiding unit class <class> camouflage <camo> with no detecting enemy and elevation0
    When the accepted hide request advances through one-second callbacks
    Then HIDDEN first becomes true at <time> seconds
    Examples:
      | class | camo | time |
      | MW | False | 21 |
      | MW | True | 11 |
      | BA | False | 61 |
      | BA | True | 31 |
      | VTOL | True | 41 |
      | MECH | True | 51 |

  Scenario Outline: Hiding and packs 02 - hide gates and interruption
    Given hide condition <condition>
    When the hide request or pending callback executes
    Then result is <result>
    Examples:
      | condition | result |
      | MW-speed-MP1 | scheduled |
      | MW-speed-over-MP1 | speed-error |
      | MW-building | terrain-error |
      | BA-building | scheduled |
      | BA-rough | scheduled |
      | BA-swarmtarget1 | scheduled |
      | BA-swarmtarget2 | swarm-error |
      | VTOL-airborne-camo | landed-error |
      | pending-hide | already-hiding-error |
      | enemy-sees-at-callback | cancelled-not-hidden |
      | enemy-clairvoyant-only | ignored-enemy |
      | enemy-shutdown-only | ignored-enemy |
      | elevation1-at-callback | cancelled-not-hidden |
      | ordinary-movement-crosses-hex | pending-hide-cancelled |
      | ordinary-damage-after-hidden | unhidden |

  Scenario Outline: Hiding and packs 03 - jettison slot semantics
    Given CAN_JETTISON <capable> with pending slots <pending> and live members <members>
    When the ordinary jettison command runs
    Then result is <result>
    Examples:
      | capable | pending | members | result |
      | False | 2 | 4 | not-capable-error |
      | True | 0 | 4 | already-jettisoned |
      | True | 2 | 4 | destroy2-clear-broken-disabled-plural |
      | True | 1 | 1 | destroy1-clear-broken-disabled-singular |

  Scenario Outline: Hiding and packs 04 - jettison runtime coherence
    Given a jettisonable weapon in <section> with source pending flags
    When jettison is followed by ordinary fire and another jettison
    Then fire is unavailable and second jettison reports no packs
    Examples:
      | section |
      | live-section0 |
      | destroyed-section7 |
