# Aerospace bombing 01 - flight time
# Aerospace bombing 02 - release order and timing
# Aerospace bombing 03 - terrain interception
# Aerospace bombing 04 - impact effects
Feature: Aerospace bombing
  Background:
    Given an airborne bomber on a registered map with real timed blast damage

  Scenario Outline: Aerospace bombing 01 - flight time
    Given bomb origin has elevation <z> and vertical start speed <vz> with zero horizontal vector
    When aim computes the ballistic destination
    Then time and displayed suffix are <time> and <suffix> with the original hex retained
    Examples:
      | z | vz | time | suffix |
      | 0 | 0 | 0 | empty |
      | 0.125 | 0 | 0.5 | empty |
      | 0.5 | 0 | 1 | s |
      | 1.125 | 0 | 1.5 | s |
      | 2 | 0 | 2 | empty |
      | 50 | 0 | 10 | empty |
      | 0 | 64.5 | 2 | empty |

  Scenario Outline: Aerospace bombing 02 - release order and timing
    Given drop fixture <fixture>
    When a real drop and the impact clock execute
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | t0;PSR-fail;inbounds | PSR-mod4;no-scatter-draw;slot-cleared;impact-due1 |
      | t1.5;PSR-fail;inbounds | PSR-mod4;no-scatter-draw;impact-due1 |
      | t2;PSR-success;inbounds | PSR-mod4;impact-due2 |
      | t10;PSR-fail;scatter12;direction0;flat-large-map | PSR-mod5;miss6-hex-X;impact-due10 |
      | t10;PSR-fail;scatter1;direction180;flat-large-map | PSR-mod5;miss-minimum1;C-short-truncation |
      | t10;offmap-destination | release-notices;payload-retained;no-cargo-change;no-event |
      | drop-then-move-to-another-map | impact-original-map-and-hex |
      | drop-then-destroy-bomber | impact-still-occurs-once |

  Scenario Outline: Aerospace bombing 03 - terrain interception
    Given flight traversal fixture <fixture>
    When simulate flight examines the path
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | t0.5;high-terrain | unchanged-destination |
      | t4;only-second-sampled-hex-above-trajectory | second-sampled-hex |
      | t4;second-and-third-sampled-hex-above-trajectory | third-sampled-hex |
      | t4;terrain-equals-real-FZ-div64.5 | unchanged-destination |
      | t4;out-of-map-samples-before-inbounds-obstacle | outside-samples-skipped;inbounds-obstacle-selected |

  Scenario Outline: Aerospace bombing 04 - impact effects
    Given bomb <bomb> hits an occupied hex
    When the real scheduled impact executes
    Then blast damage heat and cluster size are <damage> <heat> and <cluster>
    Examples:
      | bomb | damage | heat | cluster |
      | 10_Standard | 130 | 0 | 10 |
      | 10_Inferno | 15 | 30 | 10 |
      | 10_Cluster | 30 | 0 | 2 |
      | 50_Standard | 130 | 0 | 10 |
      | 50_Inferno | 65 | 130 | 10 |
      | 50_Cluster | 130 | 0 | 2 |
      | 100_Standard | 250 | 0 | 10 |
      | 100_Inferno | 125 | 250 | 10 |
      | 100_Cluster | 250 | 0 | 2 |
