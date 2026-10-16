# C3 shared targeting 01 - best contributor
# C3 shared targeting 02 - hex and early return
# C3 shared targeting 03 - network visibility fold
# C3 shared targeting 04 - normal firing consumers
Feature: C3 shared targeting
  Background:
    Given a started shooter and command-created eligible network using current LOS and geometry

  Scenario Outline: C3 shared targeting 01 - best contributor
    Given real range <real> and ordered peer observations <peers>
    When C3 shared range is queried
    Then range and source are <result>
    Examples:
      | real | peers | result |
      | 12 | B:3-visible;C:5-visible | 3,B |
      | 12 | B:3-visible;C:3-visible | 3,B |
      | 12 | B:12-visible | 12,0 |
      | 12 | B:3-invisible | 12,0 |
      | 12 | B:3-visible-unconscious | 3,B |
      | 12 | B:3-visible-stopped | 12,0 |
      | 12 | B:3-visible-AngelECM | 12,0 |
      | 12 | target:0-visible | 12,0 |
      | 12 | B:3-something | 3,B |
      | 5 | B:8-visible | 5,0 |

  Scenario Outline: C3 shared targeting 02 - hex and early return
    Given range request state <state>
    When the source range function executes
    Then the observation is <observation>
    Examples:
      | state | observation |
      | hex-X0-Y4 | real-range-no-source |
      | hex-X4-Y0 | real-range-no-source |
      | hex-X4-Y4-height3 | targetZ3-and-elevated-NB-peer-range |
      | owner-C3-destroyed-ref77 | real-range-ref77-stored-unchanged |
      | owner-C3i-destroyed-ref77 | real-range-ref77-reciprocal-clear |
      | owner-ECM-ref77 | real-range-ref77-stored-unchanged |
      | empty-working-network-ref77 | real-range-ref0 |

  Scenario Outline: C3 shared targeting 03 - network visibility fold
    Given ordered peer LOS and NB results <views>
    When network visibility is requested
    Then visibility code is <code>
    Examples:
      | views | code |
      | none | 0 |
      | something | 2 |
      | something,invisible | 0 |
      | invisible,something | 2 |
      | something,clear,invisible | 1 |
      | clear,invisible | 1 |
      | target-self | 0 |
      | unconscious-clear | 1 |

  Scenario Outline: C3 shared targeting 04 - normal firing consumers
    Given combat condition <condition>
    When ordinary sight and fire consume the formed network
    Then the observation is <observation>
    Examples:
      | condition | observation |
      | real12-peer3-IS.MediumLaser | TOFAR-no-network-extension |
      | real8-peer2-IS.MediumLaser | SHORT-network-bracket-and-peer-reference |
      | real8-peer4-IS.MediumLaser | MED-network-bracket-and-peer-reference |
      | real8-peer2-then-peer-shutdown | LONG-bracket-after-shutdown-membership-retained |
      | real8-peer2-then-owner-ECM | LONG-bracket-while-disturbed |
      | both-technologies-C3-peer4-C3i-peer2 | C3-peer4-selected |
      | own-fractional-minimum-LRM | accepted-combat-minimum-bypass-retained |
