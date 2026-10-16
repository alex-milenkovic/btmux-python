# Core clocks 01 - independent clocks; Core clocks 02 - heartbeat source idempotence; Core clocks 03 - typed dispatch
Feature: Core clocks
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core clocks 01 - independent clocks
    Given a fresh engine at all clock values zero
    When the clock sequence is <sequence>
    Then wall time is <wall> event tick is <event> and heartbeat tick is <heart>
    Examples:
      | sequence | wall | event | heart |
      | dispatch | 1 | 1 | 0 |
      | heartbeat | 0 | 0 | 1 |
      | dispatch,heartbeat | 1 | 1 | 1 |
      | heartbeat,heartbeat | 0 | 0 | 2 |

  Scenario Outline: Core clocks 02 - heartbeat source idempotence
    Given the heartbeat timer is stopped
    When the timer commands are <commands>
    Then pending heartbeat timer count is <pending>
    Examples:
      | commands | pending |
      | init | 1 |
      | init,init | 1 |
      | stop | 0 |
      | init,stop,stop | 0 |
      | init,stop,init | 1 |

  Scenario Outline: Core clocks 03 - typed dispatch
    Given one registered object of type <kind>
    When one heartbeat fires
    Then the dispatch recipient is <recipient> and heartbeat tick is 1
    Examples:
      | kind | recipient |
      | MECH | mech |
      | AUTO | auto-boundary |
      | MAP | none |
      | OTHER | none |
