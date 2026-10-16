# Repair economy salvage and failure callbacks 01 salvage commands
# Repair economy salvage and failure callbacks 02 legacy failure helpers
# Repair economy salvage and failure callbacks 03 inert source bodies
Feature: Repair economy salvage and failure callbacks

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy salvage and failure callbacks 01 salvage commands
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | intact gun width2 weapon success | removegun and advance4800 | gun destroyed at4800 and salvage1 |
      | intact gun width2 first fail recovery pass | removegun and advance4800 | gun destroyed at4800 and salvage1 |
      | intact gun width2 both weapon rolls fail | removegun and advance4800 | gun intact and salvage0 with normal-time fake |
      | intact removable part first fail recovery pass | removepart and advance2400 | part destroyed salvage1 |
      | intact removable part both rolls fail | removepart and advance3600 | part intact salvage0 |
      | structural Endosteel slot | removepart | refuse structural material |
      | weapon slot | removepart | refuse use weapon removal |
      | Mech LT with LA intact | removesection | refuse outside-in path |
      | Mech CT with HD intact and sides destroyed | removesection | refuse head prerequisite |
      | live LA internal10 frontarmor20 reararmor8 success | removesection and advance7200 | detached salvage10 internal20 armor5 electronics |
      | live LA internal10 frontarmor20 reararmor8 fail | removesection and advance10800 | detached salvage6 internal13 armor3 electronics |
      | scheduled normal remove-section now internal6 frontarmor8 | execute event | salvage6 internal8 armor3 electronics from due state |
      | selected part pending repair type53 | removepart | refuse same part repair |
      | section pending repairgun type52 only | CanScrapLoc | true under narrow source filter |
      | section pending replacepart type43 | CanScrapLoc | false |
      | section pending reload type46 | CanScrapLoc | false |

  Scenario Outline: Repair economy salvage and failure callbacks 02 legacy failure helpers
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | old replacement helper initial stock0 recovery pass | replaceg_fail | refund1 and return-1 |
      | old replacement helper initial stock0 | replacep_fail | refund0 return-1 and no dice |
      | destroyed gun width5 second intact | repairg_fail | second destroyed and return-1 |
      | destroyed gun width4 second intact | repairp_fail | second intact and return-1 |
      | damaged enhanced critical | repairenhcrit_fail | unchanged and return-1 |
      | partially full bin | reload_fail | unchanged and return-1 |
      | old reattach originalinternal10 recovery fail percent50 | reattach_fail | refund5 internal5 electronics return-1 |
      | old reattach originalinternal10 recovery pass | reattach_fail | refund0 return0 |
      | old reseal originalinternal10 recovery fail percent50 | reseal_fail | refund5 internal5 electronics return-1 |
      | suit original resources10,2,2,10 recovery fail percent5 | replacesuit_fail | refund1 internal1 sensor0 life0 electronics return-1 |

  Scenario Outline: Repair economy salvage and failure callbacks 03 inert source bodies
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | nonempty inventory and damaged unit | replacep_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | replaceg_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | reload_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | fixinternal_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | fixarmor_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | reattach_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | reseal_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | replacesuit_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | repairg_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | repairenhcrit_succ | return0 with no state dice or queue changes |
      | nonempty inventory and damaged unit | repairp_succ | return0 with no state dice or queue changes |
      | mounted bomb and cargo | mountbomb event | no state inventory or notification changes |
      | mounted bomb and cargo | umountbomb event | no state inventory or notification changes |
