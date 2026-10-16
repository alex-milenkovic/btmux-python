# Aerospace exhaust 01 - forest response
# Aerospace exhaust 02 - blast consumers
Feature: Aerospace exhaust
  Background:
    Given a dropship with actual nearby recipients and map decorations

  Scenario Outline: Aerospace exhaust 01 - forest response
    Given blast damage <damage> reaches forest at hex distance <distance> with decoration <decoration>
    When the source exhaust effect executes
    Then the forest becomes <terrain>
    Examples:
      | damage | distance | decoration | terrain |
      | 400 | 1 | none | ROUGH |
      | 400 | 3 | none | ROUGH |
      | 400 | 4 | none | FIRE-over-forest |
      | 400 | 5 | none | FIRE-over-forest |
      | 400 | 6 | none | unchanged |
      | 100 | 1 | none | FIRE-over-forest |
      | 8 | 3 | none | FIRE-over-forest |
      | 8 | 4 | none | unchanged |
      | 400 | 1 | existing-smoke | unchanged |

  Scenario Outline: Aerospace exhaust 02 - blast consumers
    Given exhaust fixture <fixture>
    When countdown or movement reaches the exhaust boundary
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | takeoff-count1;damageable-ground-recipient | actual-blast400;clusters5;heat200;emitter-Z-restored |
      | airborne-DS;Z-floor-plus5;event-tick20 | actual-blast8;clusters5;heat4;emitter-Z-restored |
      | airborne-DS;Z-floor-plus6;event-tick20 | no-exhaust |
      | airborne-DS;Z-floor-plus5;event-tick22 | no-exhaust |
      | takeoff-count6;infrared-observer | real-sensor-scramble2 |
      | takeoff-count2;liteamp-observer | real-sensor-scramble4 |
      | takeoff-aborted-before-count6 | no-scramble-or-blast |
