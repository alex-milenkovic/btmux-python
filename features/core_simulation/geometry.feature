# Core geometry 01 - signed heading normalization; Core geometry 02 - bearing vertical convention; Core geometry 03 - neighbor callback order; Core geometry 04 - arc inclusive boundaries
Feature: Core geometry
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core geometry 01 - signed heading normalization
    Given integer heading <input>
    When AcceptableDegree is evaluated
    Then heading result is <output>
    Examples:
      | input | output |
      | -720 | 360 |
      | -360 | 360 |
      | -361 | 359 |
      | -1 | 359 |
      | 0 | 0 |
      | 360 | 0 |
      | 721 | 1 |

  Scenario Outline: Core geometry 02 - bearing vertical convention
    Given source point zero and target coordinates <point>
    When horizontal and vertical bearings are requested
    Then horizontal bearing is <bearing> and absolute vertical bearing is <vertical>
    Examples:
      | point | bearing | vertical |
      | 0,-1,0 | 0 | 0 |
      | 0,1,0 | 180 | 0 |
      | 0,0,0 | 180 | 0 |
      | 0,0,-1 | 180 | 90 |
      | 0,0,1 | 180 | 90 |

  Scenario Outline: Core geometry 03 - neighbor callback order
    Given an empty 4 by 4 map
    When neighbors of hex <hex> are visited
    Then ordered callback coordinates are <neighbors>
    Examples:
      | hex | neighbors |
      | 0,0 | 1,0;1,1;0,1 |
      | 1,1 | 1,0;2,0;2,1;1,2;0,1;0,0 |
      | 2,1 | 2,0;3,1;3,2;2,2;1,2;1,1 |

  Scenario Outline: Core geometry 04 - arc inclusive boundaries
    Given a non-turret unit with source relative bearing <relative>
    When general weapon arc is classified
    Then arc is <arc>
    Examples:
      | relative | arc |
      | 60 | forward |
      | 61 | left |
      | 120 | left |
      | 121 | rear |
      | 239 | rear |
      | 240 | right |
      | 299 | right |
      | 300 | forward |
