# Damage failure recovery 01 - radio decrement and additive recovery; Damage failure recovery 02 - radio short; Damage failure recovery 03 - scanner encoded recovery; Damage failure recovery 04 - computer turn-boundary integration; Damage failure recovery 05 - target prerequisite; Damage failure recovery 06 - temporary destroyed state follows the actual recycler
Feature: Damage failure recovery
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage failure recovery 01 - radio decrement and additive recovery
    Given radio range <initial_range> and a radio range-failure reduction of <reduction> scheduled to recover at tick forty
    When the failure occurs and time advances to <time>
    Then radio range is <range> and operational-again notices number 0
    Examples:
      | initial_range | reduction | time | range |
      | 20 | 15 | 39 | 5 |
      | 20 | 15 | 40 | 20 |
      | 10 | 30 | 39 | 1 |
      | 10 | 30 | 40 | 10 |
      | 1 | 15 | 40 | 1 |

  Scenario Outline: Damage failure recovery 02 - radio short
    Given an operational radio with range 30 whose short recovery is scheduled at tick forty
    When the failure occurs and time advances to <time>
    Then radio range is <range> and operational-again notices number <notices>
    Examples:
      | time | range | notices |
      | 39 | 0 | 0 |
      | 40 | 30 | 1 |
      | 41 | 30 | 1 |

  Scenario Outline: Damage failure recovery 03 - scanner encoded recovery
    Given initial TAC 20 LRS 30 SCAN 40 and failing scanner channel <channel> with recovery at tick forty
    When the failure occurs and time advances to <time>
    Then TAC is <tac> LRS is <lrs> SCAN is <scan> and recovery notices number <notices>
    Examples:
      | channel | time | tac | lrs | scan | notices |
      | TAC | 39 | 0 | 30 | 40 | 0 |
      | TAC | 40 | 20 | 30 | 40 | 1 |
      | LRS | 39 | 20 | 0 | 40 | 0 |
      | LRS | 40 | 20 | 286 | 40 | 1 |
      | SCAN | 39 | 20 | 30 | 0 | 0 |
      | SCAN | 40 | 20 | 30 | 552 | 1 |
      | all | 39 | 0 | 0 | 0 | 0 |
      | all | 40 | 20 | 286 | 552 | 3 |

  Scenario Outline: Damage failure recovery 04 - computer turn-boundary integration
    Given a unit started <started> with movement <movement> target 7 and event time 28
    And computer failure draws select chance 42 reliability 100 and target-loss outcome one at the next turn boundary
    When the normal engine advances to tick 30
    Then target is <target> and generic failure checks number <checks>
    Examples:
      | started | movement | target | checks |
      | True | BIPED | -1 | 1 |
      | False | BIPED | 7 | 0 |
      | True | NONE | 7 | 0 |

  Scenario Outline: Damage failure recovery 05 - target prerequisite
    Given a failing computer with target <target>
    When the target-loss failure row is selected
    Then target is <after> and failure notices number <notices>
    Examples:
      | target | after | notices |
      | 0 | 0 | 0 |
      | -1 | -1 | 0 |
      | 7 | -1 | 1 |

  Scenario Outline: Damage failure recovery 06 - temporary destroyed state follows the actual recycler
    Given a started weapon with temporary DESTROYED state and recycle <recycle>
    When the normal engine performs one recycling tick
    Then temporary state is <state> and recycle is zero
    Examples:
      | recycle | state |
      | 50 | NONE |
      | 0 | DESTROYED |
