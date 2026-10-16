# Combat firing 01 - command rejection and concealment; Combat firing 02 - target safety on all paths; Combat firing 03 - sight and impossible shots
Feature: Combat firing
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat firing 01 - command rejection and concealment
    Given a hidden ready attacker with a loaded weapon and visible locked enemy
    When fire is attempted with condition <condition>
    Then firing is rejected and hidden state is <hidden> and shot resources are unchanged
    Examples:
      | condition | hidden |
      | weapons-hold | retained |
      | sprinting | cleared |
      | invalid-weapon | cleared |
      | weapon-recycling | cleared |
      | carrying-club-in-mount | cleared |
      | dug-in-nonturret | cleared |
      | AMS-weapon | cleared |
      | ammo-unjam-pending | cleared |

  Scenario Outline: Combat firing 02 - target safety on all paths
    Given a ready shooter and target selected by <path>
    When target safety condition is <condition> and fire is attempted
    Then shot disposition is <result>
    Examples:
      | path | condition | result |
      | default | friendly-with-FFSafety | rejected |
      | explicit-contact | friendly-with-map-safety | rejected |
      | hex-occupant | stealth-without-stable-lock | rejected |
      | default | own-swarmer | rejected |
      | explicit-contact | enemy-with-no-lock | fired |
      | default | MW-with-safety | rejected |
      | default | friendly-coolant | fired |

  Scenario Outline: Combat firing 03 - sight and impossible shots
    Given a ready non-artillery shot with source BTH <bth> and attack roll 7
    When the action is <action>
    Then attack draws consumed are 1 and resources spent are <spent>
    Examples:
      | bth | action | spent |
      | 7 | sight | 0 |
      | 13 | sight | 0 |
      | 13 | fire-unit | 0 |
      | 13 | fire-hex | 0 |
      | 7 | fire-unit | 1 |
