# Stagger maintenance 01 - age boundaries; Stagger maintenance 02 - whole hits; Stagger maintenance 03 - heartbeat consequences; Stagger maintenance 04 - counted history
Feature: Stagger maintenance
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Stagger maintenance 01 - age boundaries
    Given stagger history contains an uncounted hit of 12 and a counted hit of 9 both <age> wall seconds old
    When current stagger totals are inspected then expiry maintenance runs
    Then inspected uncounted damage is <uncounted> counted damage is <counted> and surviving nodes number <nodes>
    Examples:
      | age | uncounted | counted | nodes |
      | 59 | 12 | 9 | 2 |
      | 60 | 12 | 9 | 0 |
      | 61 | 0 | 0 | 0 |

  Scenario Outline: Stagger maintenance 02 - whole hits
    Given chronological recent stagger hits are 12 uncounted 9 counted 15 uncounted and 8 uncounted
    When stagger maintenance action <action> uses level <level>
    Then uncounted damage is <uncounted> counted damage is <counted> and surviving nodes number <nodes>
    Examples:
      | action | level | uncounted | counted | nodes |
      | MARK | 0 | 35 | 9 | 4 |
      | MARK | 1 | 8 | 36 | 4 |
      | MARK | 2 | 0 | 44 | 4 |
      | REMOVE | 1 | 23 | 0 | 2 |
      | REMOVE | 2 | 0 | 0 | 0 |
      | CLEAR_ALL | 0 | 0 | 0 | 0 |

  Scenario Outline: Stagger maintenance 03 - heartbeat consequences
    Given a started upright mech of <tons> tons receives one external hit of <damage> at wall time zero with new stagger mode <mode>
    When the heartbeat reaches wall second <seconds> with piloting roll <roll>
    Then stagger roll count is <checks> the mech is fallen <fallen> and remaining stagger nodes number <nodes>
    Examples:
      | tons | damage | mode | seconds | roll | checks | fallen | nodes |
      | 50 | 20 | 1 | 4 | 12 | 0 | False | 1 |
      | 50 | 19 | 1 | 5 | 12 | 0 | False | 1 |
      | 50 | 20 | 1 | 5 | 12 | 1 | False | 1 |
      | 50 | 20 | 2 | 5 | 12 | 1 | False | 0 |
      | 50 | 20 | 1 | 5 | 2 | 1 | True | 0 |
      | 35 | 20 | 1 | 5 | 5 | 1 | True | 0 |
      | 55 | 20 | 1 | 5 | 5 | 1 | False | 1 |
      | 75 | 20 | 1 | 5 | 4 | 1 | False | 1 |
      | 76 | 20 | 1 | 5 | 3 | 1 | False | 1 |

  Scenario Outline: Stagger maintenance 04 - counted history
    Given a 50 ton mech in new stagger mode 1 has already passed a check for 20 counted damage
    When another <damage> damage arrives and the next five-second heartbeat check occurs
    Then additional stagger roll count is <checks> and the stagger modifier is <modifier>
    Examples:
      | damage | checks | modifier |
      | 0 | 0 | NONE |
      | 19 | 0 | NONE |
      | 20 | 1 | 1 |
      | 40 | 1 | 2 |
