# Combat preferences 01 - preference polarity; Combat preferences 02 - automatic turret consumer; Combat preferences 03 - powered down Gauss
Feature: Combat preferences
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat preferences 01 - preference polarity
    Given fresh zero preference bits
    When preference <name> is set <setting>
    Then underlying preference bit is <bit> and displayed state is <setting>
    Examples:
      | name | setting | bit |
      | MWSafety | ON | 0 |
      | MWSafety | OFF | 1 |
      | ArmorWarn | ON | 0 |
      | AmmoWarn | OFF | 1 |
      | FFSafety | ON | 1 |
      | SLWarn | ON | 1 |
      | AutoFall | ON | 1 |
      | AutoconShutdown | OFF | 0 |
      | BTHDebug | ON | 1 |

  Scenario Outline: Combat preferences 02 - automatic turret consumer
    Given a ready tank with intact turret and visible off-axis target lock
    When autoturret is <state> and the normal update runs
    Then turret facing is <result>
    Examples:
      | state | result |
      | enabled | target-bearing |
      | disabled | unchanged |

  Scenario Outline: Combat preferences 03 - powered down Gauss
    Given a ready Gauss weapon and an ordinary ballistic weapon
    When disableweap selects <weapon>
    Then temporary weapon state is <state> and subsequent firing is <fire>
    Examples:
      | weapon | state | fire |
      | Gauss | FAIL_DESTROYED | rejected |
      | ballistic | unchanged | allowed |
