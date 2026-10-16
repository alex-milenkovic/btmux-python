# Repair economy repair event execution 01 queue identity and conflict
# Repair economy repair event execution 02 callback state and estimates
Feature: Repair economy repair event execution

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy repair event execution 01 queue identity and conflict
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | actor7 loc4 pos3 extra2 | pack repair payload | 459316 |
      | actor7 loc4 pos3 extra2 type53 | conflict same loc4 pos3 | true |
      | actor7 loc4 pos3 extra2 type53 | conflict loc4 pos4 | false |
      | actor8 loc4 pos3 extra0 fake type53 | conflict loc4 pos3 | true |
      | two type53 events same unit loc4 pos3 | SomeoneRepairing_s type53 loc4 pos3 | count2 |
      | two armor events same unit loc4 | SomeoneFixingA loc4 | count2 |
      | actor7 loc4 pos3 extra2 type51 | SomeoneScrappingPart loc4 pos3 | true |
      | actor7 loc4 pos3 extra2 type52 | SomeoneScrappingPart loc4 pos3 | false |
      | armor loc12 actor7 | SomeoneFixingA loc4 | false |
      | armor loc12 actor7 | SomeoneFixingA loc12 | true |
      | fake repair delay60 | advance59 then1 | present and unchanged then absent and unchanged |
      | real repairpart delay60 | advance59 then1 | broken then repaired and event absent |

  Scenario Outline: Repair economy repair event execution 02 callback state and estimates
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | replacegun width2 requestedbrand3 | execute callback | both repaired tempnuke0 brand3 |
      | repairgun width2 existingbrand2 | execute callback | both repaired tempnuke0 brand2 |
      | replacegun requestedbrand0 existingbrand2 | execute callback | repaired but brand2 retained |
      | repairpart selected oneshot weapon destroyed expended | execute callback | repaired and oneshot expenditure cleared |
      | repairpart selected ammo destroyed count8 | execute callback | repaired ammo count0 |
      | repairenhcrit middle damaged first tempnuke1 last damaged | execute callback | middle clear first tempnuke0 last still damaged |
      | removegun split second start0 remaining2 | execute callback | second slots0 and1 destroyed |
      | removegun split second start3 remaining2 | execute callback | second run untouched by source upper-bound quirk |
      | all populated internals1 armor0 | completely intact internal query | true |
      | one populated internal0 | completely intact internal query | false |
      | armor packed amount3 first due180 | latest tech event | 540 seconds |
      | internal packed amount2 first due540 | latest tech event | 1080 seconds |
      | armor payload4144 first due180 | latest tech event | 46620 seconds from unmasked payload estimate |
      | source type57 queued | repairs report | suit description followed by reseal description |
      | fake source type53 queued remaining119 | repairs report with lag0 | actor location Failure and 1 minute |
      | fake source type53 queued remaining119 | repairs report with lag50 | time1 minute from truncation before lag |
      | fake source type50 queued | repairs report | scrapping description without Failure suffix |
      | fake source type47 queued | repairs report | Failed armor repair label |
      | no tech events but movement queued | checkstatus | ready |
