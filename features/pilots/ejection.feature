# Pilot ejection 01 - manual command gates
# Pilot ejection 02 - disembark command boundaries
# Pilot ejection 03 - airborne exit arithmetic
# Pilot ejection 04 - automatic ejection integration
Feature: Pilot ejection
  Background:
    Given a valid source-backed local pilot in an IC map with a loadable MechWarrior template

  Scenario Outline: Pilot ejection 01 - manual command gates
    Given a manual eject request with <condition>
    When the ordinary eject command runs
    Then result is <result>
    Examples:
      | condition | result |
      | MECH-started-owner | success-cockpit-consumed-source-destroyed |
      | ground-landed-owner | success-source-destroyed |
      | VTOL-airborne | landed-error |
      | dropship | dropship-error |
      | BA | no-seat-error |
      | nonIC-unit | unit-IC-error |
      | nonIC-map | location-IC-error |
      | MUX-IC-off | MUX-IC-error |
      | started-other-pilot | seat-error |
      | stopped-wrong-owner | official-pilot-error |
      | nonfunctional-cockpit | used-cockpit-error |
      | missing-template | creation-rolled-back-player-unmoved |

  Scenario Outline: Pilot ejection 02 - disembark command boundaries
    Given a disembark request with started <started> caller <caller> and speed <speed>
    When the ordinary disembark command runs
    Then it is <result>
    Examples:
      | started | caller | speed | result |
      | True | pilot | 0 | rejected-running |
      | True | passenger | 25 | accepted |
      | False | pilot | 25 | accepted |
      | False | pilot | 25.01 | rejected-speed |
      | False | pilot | -25 | accepted |
      | False | pilot | -25.01 | rejected-speed |

  Scenario Outline: Pilot ejection 03 - airborne exit arithmetic
    Given source Z <z> ground elevation <ground> speed <speed> and vertical speed <vertical>
    When the pilot disembarks
    Then new MW Z is <z> and fall event data is <data> due after <delay> seconds
    Examples:
      | z | ground | speed | vertical | data | delay |
      | 1 | 0 | 0 | 0 | none | 0 |
      | 2 | 0 | 0 | 0 | -4 | 3 |
      | 2 | 0 | 21.5 | 0 | -5 | 3 |
      | 2 | 0 | 0 | -10.75 | -3 | 3 |
      | 0 | -2 | 0 | 0 | none | 0 |

  Scenario Outline: Pilot ejection 04 - automatic ejection integration
    Given automatic ejection condition <condition>
    When the ordinary destruction producer invokes autoejection
    Then result is <result>
    Examples:
      | condition | result |
      | surface-reactor-valid-pilot | MW-before-head-destruction-OOD150 |
      | last-BA-escape-roll25 | MW-climbout-no-OOD |
      | last-BA-escape-roll26 | no-MW-contents-death |
      | player-zero | no-creation |
      | location-nonIC | no-creation |
      | missing-template | error-no-orphan-no-fake-success |
