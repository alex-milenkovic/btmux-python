# Radio communication links 01 - relay eligibility
# Radio communication links 02 - path and edge behavior
# Radio communication links 03 - relay information
Feature: Radio communication links
  Background:
    Given source-ordered relay candidates and actual directed radio-range edges

  Scenario Outline: Radio communication links 01 - relay eligibility
    Given relay state <state>
    When an out-of-direct-range digital message seeks its only possible relay
    Then route exists is <exists>
    Examples:
      | state | exists |
      | same-team-started-relay-capable-matching | True |
      | enemy | False |
      | movable-stopped | False |
      | stationary-stopped-intact | True |
      | stationary-destroyed | False |
      | no-relay-capability | False |
      | matching-channel-without-relay-mode | False |
      | wrong-frequency | False |
      | relay-ECM | True |
      | relay-muted | True |
      | relay-mode-without-digital-diagnostic | True |

  Scenario Outline: Radio communication links 02 - path and edge behavior
    Given directed graph fixture <graph>
    When source route discovery executes
    Then the observation is <observation>
    Examples:
      | graph | observation |
      | A-range5-B-distance5-B-range5-C-distance5 | A,B-path-C-recipient |
      | A-range5-B-distance5.01-B-range10-C | no-route |
      | A-range5-B-distance5-B-range1-C-distance5 | no-route |
      | A-range10-B-distance5-B-range1-C-distance5 | A-path-C-direct |
      | A-B-C-D-chain | A,B,C-path-D-recipient |
      | A-B-D-and-A-C-D-equal | A,C-last-equal-route |
      | A-B-C-D-and-A-E-D | A,E-shorter-route |
      | A-B-cycle-no-target-edge | no-route-terminates |
      | A-and-D-only-direct-helper | false-no-relay-candidates |
      | A-B-D-B-two-matching-relay-channels | duplicate-candidates-retained |
      | recursive-A-B-D | source-dep1-path-A-only |

  Scenario Outline: Radio communication links 03 - relay information
    Given receiver mode <mode> and route <route>
    When digital message with title Ops arrives
    Then the observation is <observation>
    Examples:
      | mode | route | observation |
      | D | A-B-C | no-R-path-header-bearing-to-B |
      | DI | A-B-C | R-path-B-bearing-to-A-then-Ops-title |
      | DI | A-B-D-C | R-path-B-then-D-bearing-to-D |
      | DI | A-C-direct | no-R-path-header-bearing-to-A |
