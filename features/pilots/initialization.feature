# Personal initialization 01 - body proportions
# Personal initialization 02 - initialization equipment and ordering
# Personal initialization 03 - speed and full ammo defaults
Feature: Personal initialization
  Background:
    Given a genuine project-local MechWarrior template and source-backed character record

  Scenario Outline: Personal initialization 01 - body proportions
    Given Build5 Reflexes4 Running3 bruise10 lethal10
    When a fresh MW is initialized
    Then section <section> has original and current internal <internal> and zero original armor
    Examples:
      | section | internal |
      | HEAD | 13 |
      | CT | 41 |
      | LT | 29 |
      | RT | 29 |
      | LA | 25 |
      | RA | 25 |
      | LL | 29 |
      | RL | 29 |

  Scenario Outline: Personal initialization 02 - initialization equipment and ordering
    Given equipment field <equipment> and initialization state <state>
    When source initialization runs
    Then visible result is <result>
    Examples:
      | equipment | state | result |
      | 1234 - - | fresh | current-HEAD1-CT2-RA3-RL4 |
      | 12x4 - - | fresh | armor-error-flag-set |
      | 123 - - | fresh | length-error-flag-set |
      | 1234 valid-right invalid-left | fresh | left-error-before-right |
      | 1234 invalid-right valid-left | fresh | left-installed-before-right-error |
      | 1234 valid-right valid-left 3 4 | fresh | right-ammo3-left-ammo4 |
      | 1234 - - | already-initialized | unchanged |
      | 1234 - - | nonMW | unchanged |
      | empty | fresh | no-equipment |

  Scenario Outline: Personal initialization 03 - speed and full ammo defaults
    Given Build <build> Reflexes <reflexes> effective Running <running> and a valid personal weapon without ammo override
    When the MW initializes
    Then maximum speed is <speed> and ammo starts at source full capacity
    Examples:
      | build | reflexes | running | speed |
      | 5 | 4 | 3 | 14.333333 |
      | 1 | 1 | 0 | 2.388889 |
      | 5 | 4 | 0 | 10.75 |
