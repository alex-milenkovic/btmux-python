# Combat missiles 01 - AMS at distinct call boundaries; Combat missiles 02 - glancing missile index; Combat missiles 03 - swarm next target
Feature: Combat missiles
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat missiles 01 - AMS at distinct call boundaries
    Given a target with enabled ready IS AMS heat 0 ammo 2 and recycle value 4
    When boundary <boundary> resolves a salvo of 6 with AMS draw 5
    Then AMS ammo is <ammo> heat is <heat> recycle is <recycle> and returned shotdown is <shotdown>
    Examples:
      | boundary | ammo | heat | recycle | shotdown |
      | ordinary-fire-miss | 2 | 0 | 0 | 0 |
      | direct-missile-miss | 0 | 1 | 4 | 0 |
      | direct-missile-hit | 0 | 1 | 4 | 5 |
      | ordinary-swarm-hit | 2 | 0 | 0 | 0 |

  Scenario Outline: Combat missiles 02 - glancing missile index
    Given ordinary unguided missiles with initial d6 draws 1 2 3
    When fresh cluster roll is <roll> and glancing is <glance>
    Then missile hit-table index is <index>
    Examples:
      | roll | glance | index |
      | 2 | 0 | 0 |
      | 2 | 1 | -1 |
      | 5 | 1 | -1 |
      | 6 | 1 | 0 |
      | 12 | 1 | 6 |

  Scenario Outline: Combat missiles 03 - swarm next target
    Given a swarm leaving target A with candidates in roster order B then C
    When B has condition <condition> and C is an eligible enemy within one hex
    Then next swarm target is <next>
    Examples:
      | condition | next |
      | enemy-at-1.8 | B |
      | enemy-at-1.9 | C |
      | already-visited | C |
      | combat-safe | C |
      | friendly-with-SWARM1 | C |
      | friendly-with-SWARM | B |
      | no-LOS | C |
