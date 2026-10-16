# Battle armor actions 01 - member and map helpers
# Battle armor actions 02 - swarm modifiers
# Battle armor actions 03 - action guards and target edges
# Battle armor actions 04 - leg modifiers
# Battle armor actions 05 - leg outcomes and fallthrough
# Battle armor actions 06 - swarm attempt and stop effects
Feature: Battle armor actions
  Background:
    Given eight-section battle armor using shared source piloting damage and map membership

  Scenario Outline: Battle armor actions 01 - member and map helpers
    Given source state <state>
    When members or swarm map queries execute
    Then result is <result>
    Examples:
      | state | result |
      | only-section7-internal1 | members1 |
      | section0-internal1-destroyedflag | members1 |
      | no-map | swarmed0-mounted0-count0-firstnone |
      | enemy-then-friendly-attached | swarmed1-mounted1-count2-firstenemy |
      | friendly-only-attached | swarmed0-mounted1-count1 |
      | zero-ID-entry | ignored |
      | Clan | Point-point |
      | IS | Squad-squad |
      | host-XY3,4-Z2-elev1 | mirror-XY3,4-Z3-elev2 |

  Scenario Outline: Battle armor actions 02 - swarm modifiers
    Given member count <members> team <team> attacker hidden <hidden> target <target>
    When the swarm attempt computes its modifier
    Then modifier is <modifier>
    Examples:
      | members | team | hidden | target | modifier |
      | 1 | enemy | False | stationary-upright | 5 |
      | 3 | enemy | False | stationary-upright | 5 |
      | 4 | enemy | False | stationary-upright | 2 |
      | 0 | enemy | False | stationary-upright | 2 |
      | 4 | friendly | False | stationary-upright | -2 |
      | 4 | enemy | True | immobile-fallen | -6 |
      | 4 | enemy | False | fallen | -2 |
      | 4 | enemy | True | fallen | -2 |

  Scenario Outline: Battle armor actions 03 - action guards and target edges
    Given requested action <action> with source condition <condition>
    When the ordinary command runs
    Then result is <result>
    Examples:
      | action | condition | result |
      | swarm | range1 | range-error |
      | swarm | range0.999 | attempt |
      | swarm | stale-default | default-cleared-minus1 |
      | swarm | two-arguments | argument-error |
      | swarm | friendly-no-mount-tech | mount-tech-error |
      | swarm | enemy-pending-jettison | jettison-error |
      | swarm | friendly-pending-jettison-mount-tech | attempt |
      | swarm | swarmers-on-target-only | attempt-source-attacker-count |
      | swarm | swarmers-on-attacker | crowded-error |
      | swarm | busy-functional-weapon-on-live-section7 | weapon-busy-error |
      | swarm | section7-recycle-live | section-busy-error |
      | leg | attacker-legless | legless-error |
      | leg | friendly | friendly-error |
      | leg | quad-no-live-legs | unsupported-nontermination |

  Scenario Outline: Battle armor actions 04 - leg modifiers
    Given member count <members> hidden <hidden> target <target>
    When attackleg computes its modifier
    Then modifier is <modifier>
    Examples:
      | members | hidden | target | modifier |
      | 1 | False | stationary | 7 |
      | 2 | False | stationary | 5 |
      | 3 | False | stationary | 2 |
      | 4 | False | stationary | -1 |
      | 0 | False | stationary | -1 |
      | 4 | True | immobile-fallen | -7 |
      | 4 | False | fallen | -3 |

  Scenario Outline: Battle armor actions 05 - leg outcomes and fallthrough
    Given a successful leg attack with selected live leg and source critical Roll <roll>
    When the action resolves
    Then effect is <effect> and attack recycle is 30
    Examples:
      | roll | effect |
      | 7 | damage4-with-critical-flag |
      | 8 | critical1 |
      | 9 | critical1 |
      | 10 | critical2 |
      | 11 | critical2 |
      | 12 | destroy-leg-then-critical3 |

  Scenario Outline: Battle armor actions 06 - swarm attempt and stop effects
    Given action outcome <outcome>
    When source post-action effects complete
    Then result is <result>
    Examples:
      | outcome | result |
      | swarm-success-hidden | attached-both-flags-facing270-speeds0-unhidden-lock-stopped-recycle20 |
      | swarm-failure-hidden | unattached-unhidden-recycle20 |
      | leg-failure-hidden | hidden-retained-recycle30 |
      | stop-intentional | unattached-speed0-recycle20 |
      | stop-PSR4-success | unattached-speed0-recycle30 |
      | stop-PSR4-fail-draw7 | damage11-section7-then-survivors45 |
      | stop-unresolved-target | unchanged |
      | host-destroyed | intentional20-no-detachment-PSR |
      | host-shutdown | riders-remain-attached |
      | swarm-attempt-unhidden-pendinghide | pendinghide-retained-recycle20 |
