# Aerospace flight 01 - thrust
# Aerospace flight 02 - vertical headings
# Aerospace flight 03 - vector acceleration
# Aerospace flight 04 - heading and motion callers
Feature: Aerospace flight
  Background:
    Given an airborne registered craft with maximum 60 and source float vector arithmetic

  Scenario Outline: Aerospace flight 01 - thrust
    Given thrust fixture <fixture> and argument <argument>
    When THRUST executes
    Then the observation is <observation>
    Examples:
      | fixture | argument | observation |
      | AERO | 6.45 | minimum-thrust-refusal |
      | AERO | 6.450001 | desired6.450001;movement-armed |
      | AERO | 6.44 | minimum-thrust-refusal |
      | AERO | 60 | desired60;movement-armed |
      | AERO | 60.01 | maximum-thrust-refusal |
      | DS | empty | current-thrust-report |
      | SPHEROID_DS | 0 | desired0;movement-armed |
      | SPHEROID_DS | -1 | backwards-refusal |
      | AERO;landed | 20 | landed-refusal |
      | AERO;spinning | 20 | uncontrollable-refusal |
      | DS;fallen | 20 | engine-dead |
      | SPHEROID_DS | 12tail | desired12;movement-armed |

  Scenario Outline: Aerospace flight 02 - vertical headings
    Given class <class> at altitude <z> receives <command> with <argument>
    When the flight angle command executes
    Then the observation is <observation>
    Examples:
      | class | z | command | argument | observation |
      | AERO | 20 | CLIMB | 30 | angle30 |
      | AERO | 20 | DIVE | 30 | angle-30 |
      | AERO | 20 | CLIMB | -30 | angle-30 |
      | AERO | 20 | CLIMB | -100 | angle90 |
      | AERO | 20 | DIVE | -100 | angle-90 |
      | AERO | 20 | DIVE | empty | current-angle-report |
      | AERO | 20 | CLIMB | text | angle0 |
      | SPHEROID_DS | 99 | CLIMB | 89 | vertical-only-refusal |
      | SPHEROID_DS | 99 | DIVE | 90 | angle-90 |
      | SPHEROID_DS | 100 | CLIMB | 0 | angle0 |

  Scenario Outline: Aerospace flight 03 - vector acceleration
    Given vector fixture <fixture>
    When one source speed update runs
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | AERO;Z99;desired60;angle90;current0 | vertical12.5 |
      | AERO;Z100;desired60;angle90;current0 | vertical25 |
      | DS;Z99;desired60;angle90;current0 | vertical3.5 |
      | DS;Z100;desired60;angle90;current0 | vertical7 |
      | AERO;Z100;desired1;angle90;current0 | vertical5 |
      | DS;Z100;fuel-1;desired1;angle90;current0 | vertical1 |
      | AERO;Z100;desired0;current-vector0;scalar-speed9 | zero-delta-preserves-speed9 |
      | SPHEROID_DS;Z100;desired60;angle0;heading90;facing0 | velocity-east;facing0 |
      | AERO;Z100;desired1;angle0;heading123;current0 | speed5;facing123 |
      | AERO;spin;desired59;angle-85;heading359;draws10,15,3 | desired60;angle-90;heading2 |

  Scenario Outline: Aerospace flight 04 - heading and motion callers
    Given flight workflow <fixture>
    When ordinary controls and the movement clock execute
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | airborne-AERO;speed-command20 | use-thrust-refusal |
      | airborne-AERO;spin;heading-command90 | uncontrollable-refusal |
      | spheroid;heading90;advance | heading-turns-independently-of-velocity |
      | AERO;thrust20;climb30;advance | real-XYZ-changes;fuel-used;one-move-chain |
      | AERO;fallen;airborne;one-event | start_fz-decrements1-before-displacement |
      | DS;descend100-to99;bad-zone | angle90;horizontal-vectors0;warning-1 |
      | DS;descend50-to49;bad-zone | yellow-warning |
      | DS;descend10-to9;bad-zone | red-warning |
      | DS;descend100-to9;bad-zone | red-warning-only;no-cross100-reset |
      | AERO;ground-penetration;invalid-landing | crash;fall-damage;landed |
      | AERO;cross-map-boundary | normal-map-membership-and-position-updated |
