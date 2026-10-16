# Repair economy saved repair queues 01 record semantics
# Repair economy saved repair queues 02 all real callback mappings
Feature: Repair economy saved repair queues

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy saved repair queues 01 record semantics
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | real repairpart actor7 loc4 pos3 due120 | save at tick20 | remaining100 positive actor and payload preserved |
      | fake repairpart actor7 loc4 pos3 due120 | save at tick20 | remaining-100 and fake marker preserved |
      | repairpart due20 | save at tick20 | remaining1 |
      | repairpart due10 | save at tick20 | remaining1 |
      | no tech events | save | terminator only and no movement records |
      | real repairpart remaining100 | load at tick500 advance99 then1 | unchanged then repaired at600 |
      | fake repairpart remaining-100 | load at tick500 advance100 | no repair resources or XP and event consumed |
      | real reseal type56 remaining100 | load | no reseal event scheduled |
      | fake reseal type56 remaining-100 | load | fake event scheduled at100 |
      | live repairgun callback saved type53 | load then due | selected part repaired without whole-gun callback |
      | real repairgun type52 saved | load then due | whole gun repaired |
      | unknown real type99 saved | load | record skipped |
      | one valid record then truncated record | load | first retained then bounded end |
      | one valid record then missing-unit record | load | first retained and bounded invalid-reference diagnostic |
      | packed payload outside supported integer domain | load | explicit range error and no fabricated event |

  Scenario Outline: Repair economy saved repair queues 02 all real callback mappings
    Given repair economy state <initial>
    When the repair economy user performs load and execute
    Then the repair economy observation is <expected>

    Examples:
      | initial | expected |
      | source type43 valid saved record | repairpart |
      | source type44 valid saved record | replacegun |
      | source type45 valid saved record | reattach |
      | source type46 valid saved record | reload or unload by extra |
      | source type47 valid saved record | armor point and continuation |
      | source type48 valid saved record | internal point and continuation |
      | source type49 valid saved record | section removal |
      | source type50 valid saved record | part removal |
      | source type51 valid saved record | gun removal |
      | source type52 valid saved record | whole gun repair |
      | source type53 valid saved record | repairpart |
      | source type54 valid saved record | inert bomb mount |
      | source type55 valid saved record | inert bomb unmount |
      | source type57 valid saved record | replace suit |
      | source type58 valid saved record | enhanced critical repair |
