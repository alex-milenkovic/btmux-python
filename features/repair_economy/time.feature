# Repair economy technician time and rolls 01 clock arithmetic
# Repair economy technician time and rolls 02 skill and dice selection
Feature: Repair economy technician time and rolls

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy technician time and rolls 01 clock arithmetic
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | now1000 TECHTIME absent | status and pending | ready and 0 minutes |
      | now1000 TECHTIME 999 | status and pending | ready and 0 minutes |
      | now1000 TECHTIME 1059 | status and pending | pending and 0 minutes |
      | now1000 TECHTIME 1060 | status and pending | pending and 1 minute |
      | now1000 TECHTIME 1059 | append2 minutes | TECHTIME1179 and delay179 seconds |
      | now1000 TECHTIME 900 | append2 minutes | TECHTIME1120 and delay120 seconds |
      | wall elapsed120 tick100 | lag-adjust100 seconds | lag20 and adjusted120 seconds |
      | wall elapsed90 tick100 | lag-adjust100 seconds | lag-10 and adjusted90 seconds |
      | wall elapsed120 tick0 | lag-adjust100 seconds | lag0 and adjusted100 seconds |
      | pending59 seconds base45 minutes success | explicit replacement scheduling | updated TECHTIME plus2700 and due2700 seconds |
      | pending59 seconds base15 minutes success | STARTREPAIR scheduling | updated TECHTIME plus900 and due959 seconds |
      | variable time enabled base60 margin2 mod10 | compute time | 50 minutes |
      | variable time enabled base60 margin0 mod10 | compute time | 60 minutes |
      | variable time enabled base60 margin10 mod10 | compute time | bounded invalid-divisor diagnostic |

  Scenario Outline: Repair economy technician time and rolls 02 skill and dice selection
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | Mech skill8 diff1 dice4,5 IC | general tech roll | margin0 success and technician XP |
      | Ground skill8 diff1 dice4,4 IC | general tech roll | margin-1 failure and no XP |
      | AERO skill7 diff2 dice5,5 IC | general tech roll | margin1 and aerospace technician XP |
      | VTOL skill7 diff2 dice5,5 OOC | general tech roll | margin1 and no XP |
      | BA skill7 diff0 dice3,4 IC | general tech roll | margin0 and BattleMech technician XP |
      | weapon skill8 diff1 aptitude dice1,4,5 | weapon tech roll | margin0 from best two dice |
      | weapon skill8 diff1 normal dice1,4 | weapon tech roll | margin-4 from both dice |
      | catalog weapon width1 fighter physical1 | weapon difficulty and replacement base | difficulty0 and 60 minutes |
      | catalog weapon width6 fighter physical1 | weapon difficulty and replacement base | difficulty2 and 60 minutes |
      | catalog weapon width6 Mech physical6 Clan | weapon difficulty and replacement base | difficulty2 and 180 minutes |
      | catalog weapon width1 Mech physical1 Clan | weapon difficulty and replacement base | difficulty0 and 60 minutes |
