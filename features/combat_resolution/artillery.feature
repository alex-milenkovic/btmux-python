# Combat artillery 01 - flight deadline; Combat artillery 02 - captured launch state; Combat artillery 03 - cluster total; Combat artillery 04 - compass message boundary; Combat artillery 05 - combined impact mode priority
Feature: Combat artillery
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat artillery 01 - flight deadline
    Given artillery launch at tick 0 over hex range <range>
    When the event clock advances to <before> then <due>
    Then impact count is zero before and one at due
    Examples:
      | range | before | due |
      | 0 | 9 | 10 |
      | 49 | 9 | 10 |
      | 54.9 | 9 | 10 |
      | 55 | 10 | 11 |
      | 100 | 19 | 20 |

  Scenario Outline: Combat artillery 02 - captured launch state
    Given a normal artillery shell launched at target hex 4 4
    When before impact the shooter <change>
    Then exactly one impact uses captured target 4 4 and original ammo mode
    Examples:
      | change |
      | moves |
      | changes-lock |
      | changes-ammo-mode |
      | is-destroyed |

  Scenario Outline: Combat artillery 03 - cluster total
    Given an in-bounds shell of nominal damage <damage> with ammo bits CLUSTER and every cluster offset draw zero
    When the artillery impact event runs
    Then center delivered damage is <total> in chunks no larger than 2
    Examples:
      | damage | total |
      | 1 | 2 |
      | 5 | 10 |
      | 10 | 20 |

  Scenario Outline: Combat artillery 04 - compass message boundary
    Given a projectile bearing diagnostic of <bearing> degrees
    When its flight direction is described
    Then description is <direction>
    Examples:
      | bearing | direction |
      | 0 | north |
      | 30 | north |
      | 31 | northeast |
      | 300 | northwest |
      | 359 | northwest |

  Scenario Outline: Combat artillery 05 - combined impact mode priority
    Given an in-bounds shell of nominal damage 1 with ammo bits <mode> and every cluster offset draw zero
    When the successful shell impact event runs on an undecorated map
    Then smoke hex count is <smoke> mine count is <mines> and center mine strength is <strength>
    Examples:
      | mode | smoke | mines | strength |
      | SMOKE | 7 | 0 | 0 |
      | SMOKE+MINE | 1 | 0 | 0 |
      | CLUSTER+SMOKE | 1 | 0 | 0 |
      | CLUSTER+MINE | 0 | 1 | 2 |
      | CLUSTER+SMOKE+MINE | 1 | 0 | 0 |
