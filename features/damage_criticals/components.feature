# Damage components 01 - sensor ladder; Damage components 02 - direct engine ladder; Damage components 03 - part cleanup and already nonfunctional effects; Damage components 04 - sink loss differs by entry path; Damage components 05 - improved jet grouped loss; Damage components 06 - network and linked equipment consequences
Feature: Damage components
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage components 01 - sensor ladder
    Given a MECH with LRS 31 tactical 21 scan 11 and base to hit 4
    When <hits> distinct functional sensor criticals occur
    Then LRS is <lrs> tactical is <tac> scan is <scan> and base to hit is <bth>
    Examples:
      | hits | lrs | tac | scan | bth |
      | 1 | 15 | 10 | 5 | 6 |
      | 2 | 0 | 0 | 0 | 75 |
      | 3 | 0 | 0 | 0 | 75 |

  Scenario Outline: Damage components 02 - direct engine ladder
    Given a started repairable MECH with engine heat <before> and no other destroyed sections
    When one functional engine critical occurs
    Then engine heat is <after> unit destroyed is <destroyed> and no reactor explosion is triggered
    Examples:
      | before | after | destroyed |
      | 0 | 5 | False |
      | 5 | 10 | False |
      | 10 | 15 | True |
      | 15 | 15 | False |

  Scenario Outline: Damage components 03 - part cleanup and already nonfunctional effects
    Given a special engine slot with condition <condition> brand 3 temporary failure 2 effect flags 4 and data 7
    And engine heat is zero
    When that slot receives a critical
    Then it is destroyed with brand 3 temporary failure zero effect flags zero data 7 and engine heat <heat>
    Examples:
      | condition | heat |
      | functional | 5 |
      | broken | 0 |
      | disabled | 0 |

  Scenario Outline: Damage components 04 - sink loss differs by entry path
    Given a MECH with ten dissipation capacity and a complete <sink> heat sink group
    When sink loss occurs through <path>
    Then remaining dissipation capacity is <capacity> and no second hit on its nonfunctional run repeats that loss
    Examples:
      | sink | path | capacity |
      | single | direct-critical | 9 |
      | IS-double | direct-critical | 8 |
      | Clan-double | direct-critical | 8 |
      | single | hit-location | 8 |
      | IS-double | hit-location | 7 |
      | Clan-double | hit-location | 8 |
      | IS-double | section-destruction | 8 |
      | Clan-double | section-destruction | 8 |

  Scenario Outline: Damage components 05 - improved jet grouped loss
    Given a jumping MECH with <jets> jump MP and one improved two-slot jet group at the hit location
    When a functional slot in that group takes a critical from an attacker
    Then jump MP is <remaining> the paired slot is nonfunctional and a real fall occurs <fall>
    Examples:
      | jets | remaining | fall |
      | 2 | 1 | False |
      | 1 | 0 | True |

  Scenario Outline: Damage components 06 - network and linked equipment consequences
    Given active equipment <equipment> with its linked consumer configured
    When a functional equipment critical occurs
    Then the observable consequence is <consequence>
    Examples:
      | equipment | consequence |
      | C3-slave | C3-destroyed |
      | C3i | network-cleared |
      | TAG | TAG-destroyed-and-source-caller-validated |
      | ECM | ECM-ECCM-and-stealth-off |
      | Angel-ECM | Angel-ECM-ECCM-off |
      | Artemis | linked-ammo-mode-cleared |
      | null-signature | off-and-destroyed |
      | DS-mechdoor | door-and-null-signature-destroyed |
