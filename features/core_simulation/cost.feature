# Core cost 01 - source sparse MECH total; Core cost 02 - unsupported classes; Core cost 03 - actuator cost components; Core cost 04 - cost tables preserve large values
Feature: Core cost
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core cost 01 - source sparse MECH total
    Given a non-Clan standard 50-ton cost fixture with engine <engine> no armor actuators weapons or parts and ten single sinks
    When FASA cost is calculated
    Then cost is <cost>
    Examples:
      | engine | cost |
      | 0 | 705000 |
      | 200 | 2604999 |

  Scenario Outline: Core cost 02 - unsupported classes
    Given a unit of type <kind>
    When FASA cost is calculated
    Then cost is 0
    Examples:
      | kind |
      | AERO |
      | DS |
      | SPHEROID_DS |
      | MW |

  Scenario Outline: Core cost 03 - actuator cost components
    Given a 50-ton unit with one upper one lower and one terminal actuator plus shoulder or hip
    When location math is applied for <kind>
    Then added price is <price>
    Examples:
      | kind | price |
      | arm | 11500 |
      | leg | 17500 |

  Scenario Outline: Core cost 04 - cost tables preserve large values
    Given a valid source part category <category>
    When its cost is set to 9007199254740993
    Then reading the same part returns exactly 9007199254740993
    Examples:
      | category |
      | weapon |
      | ammo |
      | special |
      | bomb |
      | cargo |
