# Combat mines 01 - strength decay and persistence; Combat mines 02 - reason and height gates; Combat mines 03 - vibra equality; Combat mines 04 - channel detonates matching mines
Feature: Combat mines
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat mines 01 - strength decay and persistence
    Given a standard mine of strength <initial> at a ground target hex
    When a step triggers it
    Then strength used is <damage> and mine remains <remaining>
    Examples:
      | initial | damage | remaining |
      | 4 | 4 | 0 |
      | 5 | 5 | 1 |
      | 7 | 7 | 1 |
      | 8 | 5 | 1 |
      | 12 | 8 | 1 |

  Scenario Outline: Combat mines 02 - reason and height gates
    Given a mine-covered hex with elevation -2 and target height <height>
    When a <terrain> unit enters with mine reason <reason>
    Then trigger action is <action>
    Examples:
      | height | terrain | reason | action |
      | -1 | water | step | none |
      | -2 | water | step | explode |
      | 0 | ice | step | explode |
      | 1 | ice | step | none |
      | 0 | ice-trigger | fall | none |
      | 0 | ice-trigger | land | script-request |

  Scenario Outline: Combat mines 03 - vibra equality
    Given a 50-ton unit and vibra threshold <threshold>
    When the mine is <placement> relative to the unit
    Then vibra explosion count is <count>
    Examples:
      | threshold | placement | count |
      | 50 | same-hex | 1 |
      | 51 | same-hex | 0 |
      | 50 | remote-one-hex | 0 |
      | 40 | remote-one-hex | 1 |
      | 41 | remote-one-hex | 0 |

  Scenario Outline: Combat mines 04 - channel detonates matching mines
    Given command mines with channels 7 7 8 and different creators
    When channel <channel> is detonated
    Then detonation count is <count> and remaining mine count is <remaining>
    Examples:
      | channel | count | remaining |
      | 7 | 2 | 1 |
      | 8 | 1 | 2 |
      | 9 | 0 | 3 |
