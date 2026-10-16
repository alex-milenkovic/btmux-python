# Combat blast propagation 01 - strict vertical window; Combat blast propagation 02 - rear flag persists across roster; Combat blast propagation 03 - neighbors and null messages
Feature: Combat blast propagation
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat blast propagation 01 - strict vertical window
    Given a blast with damage 10 safeup 2 safedown 1 and ground-zero 0
    When target height is <height> and messages are <messages>
    Then target blast armor loss is <damage>
    Examples:
      | height | messages | damage |
      | -1 | both | 0 |
      | 0 | both | 10 |
      | 1 | both | 10 |
      | 2 | both | 0 |
      | 0 | null-target | 0 |
      | 0 | null-observer | 0 |

  Scenario Outline: Combat blast propagation 02 - rear flag persists across roster
    Given two MECH targets in roster order with the first facing blast from back and second from front
    When punch-table blast deals 5 damage to each and both location draws select torso
    Then second target loses <rear> rear armor and <front> front armor
    Examples:
      | rear | front |
      | 5 | 0 |

  Scenario Outline: Combat blast propagation 03 - neighbors and null messages
    Given a damage 12 radius-one blast with a target and undecorated woods in a neighboring hex
    When neighbor messages are <messages>
    Then neighbor target armor loss is <damage> and neighbor woods fire is present
    Examples:
      | messages | damage |
      | both | 6 |
      | null | 0 |
