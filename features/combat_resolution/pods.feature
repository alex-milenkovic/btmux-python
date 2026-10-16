# Combat pod removal 01 - arm choice and success; Combat pod removal 02 - failed swat self damage; Combat pod removal 03 - tank callback keeps ordinary NARC
Feature: Combat pod removal
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat pod removal 01 - arm choice and success
    Given matching homing pods on <location> and available arms with left modifier <left> right modifier <right>
    When pod removal succeeds
    Then selected arm is <arm> and its recycle is 30 and selected pod is cleared
    Examples:
      | location | left | right | arm |
      | CT | 0 | 0 | LARM |
      | CT | 2 | 0 | RARM |
      | LARM | 0 | 0 | RARM |
      | RARM | 0 | 0 | LARM |

  Scenario Outline: Combat pod removal 02 - failed swat self damage
    Given a 55-ton MECH with a CT homing pod and <damage> broken arm actuators
    When pod removal misses using that arm
    Then direct CT self damage is <self> and the pod remains
    Examples:
      | damage | self |
      | 0 | 6 |
      | 1 | 3 |
      | 2 | 1 |

  Scenario Outline: Combat pod removal 03 - tank callback keeps ordinary NARC
    Given a tank carrying ordinary NARC and all four iNARC pod kinds
    When removal starts at signed speed <speed> and completes at tick 60
    Then ordinary NARC remains and all iNARC kinds are removed
    Examples:
      | speed |
      | 0 |
      | -10 |
