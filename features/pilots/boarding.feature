# Pilot boarding 01 - contents flags and disposal
# Pilot boarding 02 - MW embark gates
# Pilot boarding 03 - pickup outcomes
# Pilot boarding 04 - discard clock
Feature: Pilot boarding
  Background:
    Given source-valid co-located units with ordered local occupants and empty enter locks

  Scenario Outline: Pilot boarding 01 - contents flags and disposal
    Given transfer flag <flag> origin quiet <quiet> with one ordinary occupant and one wizard
    When contents transfer and IC shell disposal execute
    Then count is <count> ordinary slave is <slave> XP loss is <loss> and teleport is <mode>
    Examples:
      | flag | quiet | count | slave | loss | mode |
      | 0 | False | 1 | False | False | hush |
      | 1 | False | 2 | False | False | hush |
      | 3 | False | 2 | True | False | hush |
      | 5 | False | 2 | False | False | loud |
      | 9 | False | 2 | False | True | hush |
      | 9 | True | 2 | False | False | hush |

  Scenario Outline: Pilot boarding 02 - MW embark gates
    Given MW embark condition <condition>
    When the ordinary embark command executes
    Then result is <result>
    Examples:
      | condition | result |
      | same-team-speed15 | accepted-transfer-all |
      | same-team-speed15.01 | speed-error |
      | other-team-empty-lock | locked-error |
      | other-team-explicit-passing-lock | accepted-transfer-all |
      | failing-lock | FAIL-and-AFAIL |
      | height-plus1 | accepted-transfer-all |
      | height-plus2 | height-error |
      | different-hex | samehex-error |
      | target-OOD | landing-error |
      | ground-unfixable | wreck-error |
      | MECH-no-head | head-error |
      | MECH-destroyed-cockpit | cockpit-missing-error |
      | MECH-disabled-cockpit | cockpit-stuck-error |

  Scenario Outline: Pilot boarding 03 - pickup outcomes
    Given pickup target team <team> pickup_action <action> and picker <picker>
    When ordinary pickup passes its source position and LOS gates
    Then result is <result>
    Examples:
      | team | action | picker | result |
      | friendly | 0 | MECH | all-contents-hush |
      | enemy | 0 | MECH | all-contents-nonwiz-slave-hush |
      | enemy | 1 | MECH | all-contents-loud-no-slave |
      | friendly | 1 | VTOL | all-contents-loud |
      | friendly | 0 | BA | pickup-class-error |
      | friendly | 0 | BA-salvage | all-contents-hush |

  Scenario Outline: Pilot boarding 04 - discard clock
    Given shell state <state> after a successful occupant transfer
    When the normal clock advances to <time>
    Then the shell is <result>
    Examples:
      | state | time | result |
      | IC | 9 | still-present-empty |
      | IC | 10 | leave-hook-then-used-store-dark-zombie-no-hardcode |
      | nonIC | 10 | not-scheduled |
