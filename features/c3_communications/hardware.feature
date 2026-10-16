# C3 hardware 01 - master grouping
# C3 hardware 02 - queried slot window
# C3 hardware 03 - critical and transfer consumers
Feature: C3 hardware
  Background:
    Given a registered unit with source critical slots and real part functional flags

  Scenario Outline: C3 hardware 01 - master grouping
    Given class <class> and C3 master slots <slots>
    When total and working masters are counted
    Then counts are <total> total and <working> working
    Examples:
      | class | slots | total | working |
      | MECH | LT:0-4-functional | 1 | 1 |
      | MECH | LT:0-3-functional | 0 | 0 |
      | MECH | LT:0-2;RT:0-1-functional | 0 | 0 |
      | MECH | LT:0,2,4,6,8-functional | 1 | 1 |
      | MECH | LT:0-9-functional | 2 | 1 |
      | MECH | LT:0-4;RT:0-4-functional | 2 | 2 |
      | MECH | LT:0-4-slot2-destroyed | 1 | 0 |
      | MECH | LT:0-4-slot2-disabled | 1 | 0 |
      | VEH_GROUND | LT:0-functional | 1 | 1 |
      | VEH_GROUND | LT:0,1-functional | 2 | 1 |
      | VEH_GROUND | LT:0;RT:0-functional | 2 | 2 |

  Scenario Outline: C3 hardware 02 - queried slot window
    Given class <class> and source slot layout <layout>
    When working-master membership checks the queried slot
    Then the membership result is <result>
    Examples:
      | class | layout | result |
      | MECH | only-master-type-at-LT0;all-slots-functional;query4 | True |
      | MECH | only-master-type-at-LT0;slot4-destroyed;query4 | True |
      | MECH | only-master-type-at-LT0;slot3-destroyed;query4 | False |
      | MECH | no-master-types;query4 | False |
      | MECH | masters-at-LT0-and1;all-functional;query4 | False |
      | MECH | only-master-type-at-HEAD4;all-12-slots-functional;query4 | True |
      | MECH | only-master-type-at-HEAD4;allocated-slot7-destroyed;query4 | False |
      | VEH_GROUND | no-master-types;query0 | True |

  Scenario Outline: C3 hardware 03 - critical and transfer consumers
    Given formed network <network> with action <action>
    When ordinary damage or map transfer reaches its source lifecycle boundary
    Then the observation is <observation>
    Examples:
      | network | action | observation |
      | C3-two-separate-working-masters | destroy-one-master-slot | one-working-master-retained-capacity-reduced-on-validation |
      | C3-one-working-master | destroy-last-master | destroyed-flag-TAG-check-and-no-shared-range |
      | C3-slave | destroy-slave | destroyed-flag-and-removed-on-validation |
      | C3i-integer-identity-peers | destroy-C3i-slot | reciprocal-detachment |
      | C3 | cross-map | owner-cleared-old-peers-detached |
      | C3i | cross-map | owner-cleared-old-peers-detached |
