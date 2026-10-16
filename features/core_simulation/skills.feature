# Core skills 01 - machine overrides and absent defaults; Core skills 02 - class and weapon skill names; Core skills 03 - piloting guard precedence
Feature: Core skills
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core skills 01 - machine overrides and absent defaults
    Given unit quiet <quiet> skill text <text> and no valid pilot
    When piloting gunnery spotting and artillery skills are resolved
    Then skill tuple is <skills>
    Examples:
      | quiet | text | skills |
      | 0 | 1,2,3,4 | 6,6,8,8 |
      | 1 | 1,2,3,4 | 1,2,3,4 |
      | 1 | 0,-1 | 0,-1,8,8 |
      | 1 | none | 6,6,8,8 |

  Scenario Outline: Core skills 02 - class and weapon skill names
    Given unit <kind> movement <move> terrain <terrain> extended mode <extended> and weapon <weapon>
    When gunnery and piloting skill names are resolved
    Then skill name pair is <names>
    Examples:
      | kind | move | terrain | extended | weapon | names |
      | MECH | QUAD | CLEAR | 0 | laser | Gunnery-Battlemech/Piloting-Battlemech |
      | MECH | QUAD | CLEAR | 1 | laser | Gunnery-Laser/Piloting-Quad |
      | MW | BIPED | WATER | 1 | PC.Blade | Blade/Swimming |
      | MW | BIPED | WATER | 0 | PC.Sword | Blade/Running |
      | MW | BIPED | CLEAR | 1 | PC.Blazer | Support_Weapons/Running |
      | BSUIT | BIPED | CLEAR | 1 | missile | Gunnery-Missile/Piloting-Bsuit |

  Scenario Outline: Core skills 03 - piloting guard precedence
    Given unit fallen <fallen> stopped <stopped> and succeedWhenFallen <succeed>
    When the noXP piloting check runs with otherwise valid state and successful dice
    Then check success is <success> and Roll count is <rolls>
    Examples:
      | fallen | stopped | succeed | success | rolls |
      | 1 | 1 | 1 | 1 | 0 |
      | 1 | 1 | 0 | 0 | 0 |
      | 0 | 1 | 1 | 0 | 0 |
      | 0 | 0 | 1 | 1 | 1 |
