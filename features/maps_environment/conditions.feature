# Maps conditions 01 - special flags; Maps conditions 02 - condition validation; Maps conditions 03 - breach roll gates
Feature: Maps conditions
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps conditions 01 - special flags
    Given a map starts with flags <before>
    When setconditions receives <arguments>
    Then map flags are <after> gravity is <gravity> and temperature is <temperature>
    Examples:
      | before | arguments | after | gravity | temperature |
      | 0 | 100,20 | 0 | 100 | 20 |
      | 0 | 100,-30 | 0 | 100 | -30 |
      | 0 | 100,-31 | 2 | 100 | -31 |
      | 0 | 100,50 | 0 | 100 | 50 |
      | 0 | 100,51 | 2 | 100 | 51 |
      | 0 | 99,20 | 2 | 99 | 20 |
      | 0 | 100,20,1 | 6 | 100 | 20 |
      | 6 | 100,20 | 0 | 100 | 20 |
      | 16 | 100,20,0,0 | 16 | 100 | 20 |
      | 0 | 100,20,0,1 | 16 | 100 | 20 |

  Scenario Outline: Maps conditions 02 - condition validation
    Given a map starts with flags 16 gravity 100 and temperature 20
    When setconditions receives <arguments>
    Then the outcome is <result> and invalid requests preserve all existing values
    Examples:
      | arguments | result |
      | 0,-128 | success |
      | 255,127,1,1 | success |
      | -1,20 | gravity-error |
      | 256,20 | gravity-error |
      | 100,-129 | temperature-error |
      | 100,128 | temperature-error |
      | 100,20,2 | vacuum-error |
      | 100,20,0,2 | underground-error |
      | 100 | arity-error |

  Scenario Outline: Maps conditions 03 - breach roll gates
    Given an intact unbreached arm belongs to a unit with special <special> and vacuum <vacuum>
    When possibly breach is attempted with next roll <roll>
    Then roll consumption is <consumption> and breached is <breached>
    Examples:
      | special | vacuum | roll | consumption | breached |
      | 0 | 0 | 12 | unused | false |
      | 1 | 0 | 12 | used | false |
      | 1 | 1 | 9 | used | false |
      | 1 | 1 | 10 | used | true |
      | 1 | 1 | 12 | used | true |
