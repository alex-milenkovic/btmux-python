# C3 membership 01 - capacity boundary
# C3 membership 02 - join gates
# C3 membership 03 - replication order
# C3 membership 04 - stored validation and temporary use
# C3 membership 05 - source arrays and trim
# C3 membership 06 - network messages
Feature: C3 membership
  Background:
    Given registered same-team units on a real map with no initial networks

  Scenario Outline: C3 membership 01 - capacity boundary
    Given network kind <kind> has <masters> working masters and target peer count <peers>
    When another eligible unit tries to join
    Then the join is <result>
    Examples:
      | kind | masters | peers | result |
      | C3 | 0 | 0 | capacity-refusal |
      | C3 | 1 | 0 | accepted |
      | C3 | 1 | 2 | accepted |
      | C3 | 1 | 3 | capacity-refusal |
      | C3 | 2 | 5 | accepted |
      | C3 | 2 | 6 | capacity-refusal |
      | C3 | 4 | 10 | accepted |
      | C3 | 4 | 11 | capacity-refusal |
      | C3i | 0 | 4 | accepted |
      | C3i | 0 | 5 | capacity-refusal |

  Scenario Outline: C3 membership 02 - join gates
    Given network kind <kind> and join condition <condition>
    When the pilot issues the network join command
    Then the observation is <observation>
    Examples:
      | kind | condition | observation |
      | C3 | two-arguments | argument-error |
      | C3i | empty-argument | argument-error |
      | C3 | no-own-technology | technology-error |
      | C3i | own-system-destroyed | system-error |
      | C3 | own-AngelECM | operational-error |
      | C3i | already-connected | already-connected-error |
      | C3 | target-no-LOS | targetID-error |
      | C3i | enemy-target | unfriendly-error |
      | C3 | self-target | self-error |
      | C3i | destroyed-target | target-destroyed-error |
      | C3 | stopped-target | target-not-started-error |
      | C3i | target-only-C3 | target-technology-error |
      | C3i | intact-target-under-ECM | join-stored-target-temporarily-unusable |
      | C3i | destroyed-target-system | confirmation-then-source-validation-clears-connection |
      | C3 | disconnected-leave | not-connected-message |
      | C3i | connected-leave | reciprocal-clear-and-disconnect-message |

  Scenario Outline: C3 membership 03 - replication order
    Given network kind <kind> and sequence <sequence>
    When the joins and removals execute in that order
    Then stored peer order is <order>
    Examples:
      | kind | sequence | order |
      | C3 | B-joins-master-A;C-joins-A | A:B,C;B:A,C;C:A,B |
      | C3i | B-joins-A;C-joins-B | A:B,C;B:A,C;C:B,A |
      | C3 | B-joins-master-A;C-joins-A;B-leaves | A:C;B:empty;C:A |
      | C3i | B-joins-A;C-joins-A;C-leaves | A:B;B:A;C:empty |

  Scenario Outline: C3 membership 04 - stored validation and temporary use
    Given stored C3i peer state <state>
    When validation and targeting and messaging build their eligible lists
    Then stored targeting messaging inclusion is <inclusion>
    Examples:
      | state | inclusion |
      | healthy | True,True,True |
      | stopped | True,False,False |
      | unconscious | True,True,False |
      | blinded | True,True,True |
      | ECM-disturbed | True,False,False |
      | Angel-disturbed | True,False,False |
      | destroyed | False,False,False |
      | wrong-team | False,False,False |
      | wrong-map | False,False,False |
      | missing | False,False,False |
      | zero-ID | False,False,False |
      | no-tech | False,False,False |
      | system-destroyed | False,False,False |

  Scenario Outline: C3 membership 05 - source arrays and trim
    Given diagnostic source network <state>
    When the named storage operation runs
    Then the observation is <observation>
    Examples:
      | state | observation |
      | C3i-size-negative;validate | owner-cleared-peer-entries-retained-negative-prefix |
      | C3i-size2;slots-B,-1,C;validate | B-only-C-outside-prefix |
      | C3i-size3;slots-B,-1,C;validate | B,C-compacted |
      | C3i-size2;slots-B,B;validate | duplicates-retained |
      | C3i-size1;slots-B;free-B | minus1 |
      | C3i-size5;slots-B,C,D,E,F;free-G | minus2 |
      | C3i-size1;slots-B;free-C | index1 |
      | C3i-size2;slots-B,C;clear-local | owner-empty-peers-unchanged |
      | C3i-size2;slots-B,C;clear-B | C-only |
      | C3-owner-master0;peers-S1,M1,S2,S3,S4;trim | M1,S1,S2 |
      | C3-owner-master1;peers-S1,S2;trim | S1,S2 |
      | C3-owner-master0;peers-S1,S2;temporary-trim | temporary-empty-stored-S1,S2 |
      | C3i-size1;slots-B,-1;temp-index1 | null-padding-readable |
      | C3i-size1;slots-B,-1;other-index1 | null-outside-prefix |

  Scenario Outline: C3 membership 06 - network messages
    Given message condition <condition>
    When the ordinary network message command runs
    Then the observation is <observation>
    Examples:
      | condition | observation |
      | C3-leading-spaces-hello | stripped-hello-peer-C3-identity-and-self-You |
      | C3i-leading-spaces-hello | stripped-hello-peer-C3i-identity-and-self-You |
      | C3-empty-stored-network | no-other-units-error |
      | C3i-nonempty-network-blank-message | what-to-send-error |
      | C3i-only-stopped-peers | self-echo-no-peer-delivery |
      | C3i-only-unconscious-peers | self-echo-no-peer-delivery |
      | C3-owner-slave-master-peer-ECM | self-echo-no-peers-after-temporary-trim |
