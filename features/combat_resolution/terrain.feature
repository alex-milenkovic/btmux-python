# Combat terrain impacts 01 - ignition thresholds; Combat terrain impacts 02 - clearing and secondary ignition; Combat terrain impacts 03 - mine clearing no-op; Combat terrain impacts 04 - light woods replacement
Feature: Combat terrain impacts
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat terrain impacts 01 - ignition thresholds
    Given light woods and an eligible <weapon>
    When intentional ignition consumes roll <roll>
    Then woods fire is <fire>
    Examples:
      | weapon | roll | fire |
      | Flamer | 3 | absent |
      | Flamer | 4 | present |
      | MediumLaser | 4 | absent |
      | MediumLaser | 5 | present |
      | AC10 | 8 | absent |
      | AC10 | 9 | present |
      | SmallLaser | 12 | absent |
      | flechette-AC10 | 5 | present |

  Scenario Outline: Combat terrain impacts 02 - clearing and secondary ignition
    Given heavy woods and a MediumLaser clearing hit of damage 8
    When clear ignite-roll is <ignite> clear-roll is <clear> and nested ignition-roll is <nested>
    Then terrain result is <result>
    Examples:
      | ignite | clear | nested | result |
      | 5 | 8 | 4 | unchanged |
      | 5 | 8 | 5 | burning-heavy |
      | 6 | 8 | 5 | light-woods |
      | 6 | 9 | 5 | unchanged |

  Scenario Outline: Combat terrain impacts 03 - mine clearing no-op
    Given a mine at a successfully cleared forest hex
    When source possibly-remove-mines is reached
    Then mine count remains <count>
    Examples:
      | count |
      | 1 |

  Scenario Outline: Combat terrain impacts 04 - light woods replacement
    Given light woods and a MediumLaser clearing hit of damage 8
    When intentional clearing uses ignite-roll 6 clear-roll 8 and replacement draw <draw>
    Then terrain is <terrain> and exactly one replacement draw was consumed
    Examples:
      | draw | terrain |
      | 1 | rough |
      | 2 | grassland |
