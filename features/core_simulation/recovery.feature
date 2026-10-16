# Core recovery 01 - extend remaining recovery deadline; Core recovery 02 - crew stun callback multiplicity; Core recovery 03 - mech stun callback guards
Feature: Core recovery
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core recovery 01 - extend remaining recovery deadline
    Given a recovery callback is due at tick 30
    When at event tick <now> unconsciousness is prolonged by <length>
    Then one recovery event remains due at <due>
    Examples:
      | now | length | due |
      | 0 | 10 | 40 |
      | 10 | 5 | 35 |
      | 29 | 30 | 60 |

  Scenario Outline: Core recovery 02 - crew stun callback multiplicity
    Given tank crew stun callbacks are scheduled at <deadlines>
    When event time reaches <now>
    Then tank crew stunned is <stunned> and recovery notices is <messages>
    Examples:
      | deadlines | now | stunned | messages |
      | 5,10 | 5 | 1 | 0 |
      | 5,10 | 10 | 0 | 1 |
      | 5,5 | 5 | 0 | 1 |
      | 5 | 5 | 0 | 1 |

  Scenario Outline: Core recovery 03 - mech stun callback guards
    Given a MECH with stunned bit set and state <state>
    When the crewstun callback runs
    Then stunned bit is zero and recovery notice count is <messages>
    Examples:
      | state | messages |
      | started | 1 |
      | stopped | 0 |
      | destroyed | 0 |
