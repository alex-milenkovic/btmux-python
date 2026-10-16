# Damage commands 01 - cluster command truncates remainder; Damage commands 02 - explicit-direction cluster keeps remainder; Damage commands 03 - section command integer flags; Damage commands 04 - raw armor setter validation and no damage side effect; Damage commands 05 - weapon status precedence; Damage commands 06 - location weapon enumeration
Feature: Damage commands
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage commands 01 - cluster command truncates remainder
    Given an intact MECH with enough armor and administrative damage argument <argument>
    When the damage command executes
    Then command accepted is <accepted> and total requested hit damage is <total>
    Examples:
      | argument | accepted | total |
      | 11 5 0 0 | True | 10 |
      | 10 5 1 0 | True | 10 |
      | 0 1 0 0 | False | 0 |
      | 1001 5 0 0 | False | 0 |
      | 5 6 0 0 | False | 0 |
      | 5 0 0 0 | False | 0 |
      | 5 1 x 0 | False | 0 |

  Scenario Outline: Damage commands 02 - explicit-direction cluster keeps remainder
    Given a MECH left arm armor 50 and dodamage direction zero
    When dodamage applies total <total> in clusters <cluster>
    Then left arm armor is <armor> and cluster sizes are <sizes>
    Examples:
      | total | cluster | armor | sizes |
      | 11 | 5 | 39 | 5,5,1 |
      | 10 | 5 | 40 | 5,5 |
      | 1 | 1 | 49 | 1 |

  Scenario Outline: Damage commands 03 - section command integer flags
    Given an intact MECH left torso with front armor 20 rear armor 10
    When damage-section receives argument <argument>
    Then command accepted is <accepted> front armor is <front> and rear armor is <rear>
    Examples:
      | argument | accepted | front | rear |
      | LT 3 0 0 | True | 17 | 10 |
      | LT 3 2 0 | True | 20 | 7 |
      | unknown 3 0 0 | False | 20 | 10 |
      | LT 1001 0 0 | False | 20 | 10 |

  Scenario Outline: Damage commands 04 - raw armor setter validation and no damage side effect
    Given an originally populated MECH left arm with armor 20 internal 10 rear 0
    When setarmorstatus receives type <type> and value text <value>
    Then reply is <reply> front armor is <front> internal is <internal> rear armor is <rear> and no destruction event is emitted
    Examples:
      | type | value | reply | front | internal | rear |
      | 0 | 255 | 1 | 255 | 10 | 0 |
      | 1 | 0 | 1 | 20 | 0 | 0 |
      | 2 | 8 | 1 | 20 | 10 | 8 |
      | 0 | 12junk | 1 | 12 | 10 | 0 |
      | 0 | bad | 1 | 0 | 10 | 0 |
      | 0 | 256 | #-1 INVALID ARMORVALUE | 20 | 10 | 0 |
      | 0 | -1 | #-1 INVALID ARMORVALUE | 20 | 10 | 0 |
      | 3 | 1 | #-1 INVALID ARMORTYPE | 20 | 10 | 0 |

  Scenario Outline: Damage commands 05 - weapon status precedence
    Given one mounted weapon with state <state>
    When weaponstatus is requested
    Then displayed status is <status>
    Examples:
      | state | status |
      | operational | OPERATIONAL |
      | damaged | DAMAGED |
      | disabled-and-damaged | DISABLED |
      | broken-and-disabled | DESTROYED |
      | temporary-destroyed | DESTROYED |
      | temporary-jammed | JAMMED |
      | temporary-shorted | SHORTED |
      | temporary-empty | EMPTY |
      | temporary-dud | DUD |
      | temporary-ammojammed | AMMOJAM |

  Scenario Outline: Damage commands 06 - location weapon enumeration
    Given section zero has two distinct mounted weapons in order laser then autocannon and section one has one missile weapon
    When section <section> weapon count and ordinal <ordinal> type are requested
    Then count is <count> and returned type is <weapon>
    Examples:
      | section | ordinal | count | weapon |
      | 0 | 1 | 1 | autocannon |
      | 0 | 2 | 1 | none |
      | 1 | 1 | 1 | missile |
      | 2 | 1 | 0 | none |
