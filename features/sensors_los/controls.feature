# Sensor controls 01 - delayed selection; Sensor controls 02 - replace pending; Sensor controls 03 - light availability; Sensor controls 04 - capability readout
Feature: Sensor controls
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: Sensor controls 01 - delayed selection
    Given visual sensors and a unit target lock with retained hex coordinates
    When the pilot requests sensors <request>
    And the engine advances <seconds> seconds
    Then current sensors are <current> wanted sensors are <wanted> and the unit target is <target>
    And the hex coordinates and lock mode bits are unchanged
    Examples:
      | request | seconds | current | wanted | target |
      | I E | 9 | VV | IE | retained |
      | I E | 10 | IE | none | cleared |
      | i e | 10 | IE | none | cleared |
      | V V | 10 | VV | none | retained |

  Scenario Outline: Sensor controls 02 - replace pending
    Given a sensor change from VV to IE requested at time zero
    When the engine advances 3 seconds
    And the pilot requests sensors <request>
    And the engine advances to time <time>
    Then current sensors are <current> wanted sensors are <wanted> and the sensor deadline is <deadline>
    Examples:
      | request | time | current | wanted | deadline |
      | E E | 10 | VV | EE | 13 |
      | E E | 13 | EE | none | none |
      | V V | 10 | IE | none | none |
      | Q Q | 10 | IE | none | none |

  Scenario Outline: Sensor controls 03 - light availability
    Given current sensors <pair> and map light 0
    When configured map light <light> is read by the normal time 25 map update
    Then current sensors are <current> with no sensor change event created
    Examples:
      | pair | light | current |
      | LL | 2 | VL |
      | LI | 2 | VI |
      | IL | 2 | IV |
      | LL | 1 | LL |
      | II | 2 | II |

  Scenario Outline: Sensor controls 04 - capability readout
    Given current sensors <pair> and map light 0
    And all equipment required by that sensor pair is installed
    When the pilot requests sensor readout <style>
    Then the sensor name includes <name> and scanning description is <arc>
    And blocker details are <details>
    Examples:
      | pair | style | name | arc | details |
      | VV | concise | Vislight | 360 | absent |
      | VL | verbose | Vislight | 120 | present |
      | II | verbose | Infrared | fullvision | present |
      | AA | concise | Light Beagle ActiveProbe | fullvision | absent |
      | HH | verbose | Bloodhound ActiveProbe | fullvision | present |
