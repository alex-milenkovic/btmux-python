# Core randomness 01 - source MT vectors; Core randomness 02 - Number rejection and equal endpoints; Core randomness 03 - MNumber uses event windows; Core randomness 04 - Roll statistics and init preservation; Core randomness 05 - mixed generator word consumption
Feature: Core randomness
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core randomness 01 - source MT vectors
    Given a fresh MT stream initialized by <init>
    When zero-based word <index> is drawn
    Then unsigned32 word is <word>
    Examples:
      | init | index | word |
      | seed5489 | 0 | 3499211612 |
      | seed5489 | 1 | 581869302 |
      | seed5489 | 623 | 4020325887 |
      | seed5489 | 624 | 4178893912 |
      | seed5489 | 625 | 610818241 |
      | default | 0 | 3499211612 |
      | array123-234-345-456 | 0 | 1067595299 |
      | array123-234-345-456 | 4 | 4228976476 |

  Scenario Outline: Core randomness 02 - Number rejection and equal endpoints
    Given raw32 words <words>
    When Number is called with low <low> and high <high>
    Then result is <result> and raw words consumed is <used>
    Examples:
      | words | low | high | result | used |
      | none | 7 | 7 | 0 | 0 |
      | FFFFFFFF,80000000 | 1 | 6 | 5 | 2 |
      | 00000000 | -2 | 2 | -2 | 1 |
      | FFFFFFFF | 0 | 4294967295 | 4294967295 | 1 |
      | 80000000 | 0 | 1 | 1 | 1 |

  Scenario Outline: Core randomness 03 - MNumber uses event windows
    Given cached random 11 last window 0 and next int31 input 20
    When MNumber from 1 to 6 runs at event tick <tick> with map tick 100 and heartbeat tick 99
    Then result is <result> and int31 draw count is <draws>
    Examples:
      | tick | result | draws |
      | 0 | 6 | 0 |
      | 5 | 6 | 0 |
      | 6 | 3 | 1 |
      | 11 | 3 | 1 |

  Scenario Outline: Core randomness 04 - Roll statistics and init preservation
    Given source Roll die pairs <pairs>
    When all pairs are rolled and init_stat reseeds without another roll
    Then total rolls is <total> and nonzero histogram is <hist>
    Examples:
      | pairs | total | hist |
      | 1,1 | 1 | 2:1 |
      | 6,6;1,6 | 2 | 7:1,12:1 |
      | 3,4;4,3;6,1 | 3 | 7:3 |

  Scenario Outline: Core randomness 05 - mixed generator word consumption
    Given MT seed 5489 and prior calls <prior>
    When generator <generator> is called
    Then output is <value> and total raw32 words consumed is <used>
    Examples:
      | prior | generator | value | used |
      | none | int31 | 1749605806 | 1 |
      | int31 | real1 | 0.13547700413863104 | 2 |
      | int31,real1 | real2 | 0.90579193411394954 | 3 |
      | int31,real1,real2 | real3 | 0.83500858990009874 | 4 |
      | int31,real1,real2,real3 | res53 | 0.12698681629350606 | 6 |
