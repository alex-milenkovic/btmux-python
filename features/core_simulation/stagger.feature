# Core stagger 01 - new and legacy tonnage modifiers; Core stagger 02 - new stagger counted history; Core stagger 03 - legacy event terminal state
Feature: Core stagger
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core stagger 01 - new and legacy tonnage modifiers
    Given a started unit of tons <tons> at stagger level <level>
    When new weighted new unweighted and legacy modifiers are inspected
    Then modifier triple is <mods>
    Examples:
      | tons | level | mods |
      | 35 | 1 | 1,0,2 |
      | 36 | 1 | 0,0,1 |
      | 55 | 2 | 1,1,2 |
      | 56 | 2 | 0,1,1 |
      | 75 | 3 | 1,2,2 |
      | 76 | 3 | 0,2,1 |

  Scenario Outline: Core stagger 02 - new stagger counted history
    Given uncounted damage 20 and counted damage 20 in the active window
    When mode <mode> stagger check runs at its deadline with a successful pilot roll
    Then observed stagger level is <level> and retained history points is <points>
    Examples:
      | mode | level | points |
      | 1 | 2 | 40 |
      | 2 | 1 | 20 |

  Scenario Outline: Core stagger 03 - legacy event terminal state
    Given a legacy stagger callback with state <state> and damage <damage>
    When the callback executes with successful rolls if needed
    Then stagger damage is <remaining> and pilot rolls consumed is <draws>
    Examples:
      | state | damage | remaining | draws |
      | upright | 20 | -10 | 1 |
      | jumping | 20 | 20 | 0 |
      | fallen | 20 | 20 | 0 |
      | upright | 19 | 19 | 0 |
