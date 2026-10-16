# Core startup 01 - six-stage deadlines; Core startup 02 - heat and override guards; Core startup 03 - flood on second stage; Core startup 04 - abort and restart
Feature: Core startup
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core startup 01 - six-stage deadlines
    Given a stopped eligible <kind> requesting startup with <argument> as wizard <wizard>
    When the normal clock reaches <tick>
    Then started is <started> and boot message count is <messages>
    Examples:
      | kind | argument | wizard | tick | started | messages |
      | MECH | none | 0 | 4 | 0 | 0 |
      | MECH | none | 0 | 5 | 0 | 1 |
      | MECH | none | 0 | 29 | 0 | 5 |
      | MECH | none | 0 | 30 | 1 | 6 |
      | BSUIT | none | 0 | 5 | 0 | 5 |
      | BSUIT | none | 0 | 6 | 1 | 6 |
      | MW | none | 0 | 1 | 1 | 1 |
      | MECH | over | 1 | 1 | 1 | 1 |

  Scenario Outline: Core startup 02 - heat and override guards
    Given an otherwise eligible stopped unit with heat <heat>
    When actor wizard <wizard> requests startup argument <argument>
    Then startup scheduling is <scheduled> and random draws consumed is 0
    Examples:
      | heat | wizard | argument | scheduled |
      | 9 | 0 | none | 1 |
      | 14 | 0 | none | 1 |
      | 30 | 0 | none | 1 |
      | 30.1 | 0 | none | 0 |
      | 0 | 0 | over | 0 |
      | 0 | 1 | override | 1 |
      | 0 | 0 | overrideX | 1 |

  Scenario Outline: Core startup 03 - flood on second stage
    Given a stopped <kind> in water with waterproof <proof>
    When normal startup advances to <tick>
    Then destroyed is <destroyed> and remaining startup events is <pending>
    Examples:
      | kind | proof | tick | destroyed | pending |
      | VEH_GROUND | 0 | 5 | 0 | 1 |
      | VEH_GROUND | 0 | 10 | 1 | 0 |
      | VEH_GROUND | 1 | 10 | 0 | 1 |
      | MECH | 0 | 10 | 0 | 1 |
      | BSUIT | 0 | 2 | 1 | 0 |
      | VEH_NAVAL | 0 | 10 | 0 | 1 |

  Scenario Outline: Core startup 04 - abort and restart
    Given normal MECH startup has reached tick <abort>
    When shutdown is followed by a new startup and 30 clock ticks
    Then only the new sequence completes and started is 1
    Examples:
      | abort |
      | 0 |
      | 5 |
      | 29 |
