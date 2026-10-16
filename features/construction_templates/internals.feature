# Construction internals 01 - mech table; Construction internals 02 - preserving damage; Construction internals 03 - vehicle boundaries
Feature: Construction internals
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction internals 01 - mech table
    Given a <move> mech of <tons> tons has zero original and current internals everywhere
    When internal consistency runs
    Then center side arm leg and head internals become <ct> <side> <arm> <leg> and 3 in both current and original state
    Examples:
      | move | tons | ct | side | arm | leg |
      | Biped | 10 | 4 | 3 | 1 | 2 |
      | Quad | 10 | 4 | 3 | 2 | 2 |
      | Biped | 15 | 5 | 4 | 2 | 3 |
      | Quad | 15 | 5 | 4 | 3 | 3 |
      | Biped | 20 | 6 | 5 | 3 | 4 |
      | Quad | 20 | 6 | 5 | 4 | 4 |
      | Biped | 25 | 8 | 6 | 4 | 6 |
      | Quad | 25 | 8 | 6 | 6 | 6 |
      | Biped | 30 | 10 | 7 | 5 | 7 |
      | Quad | 30 | 10 | 7 | 7 | 7 |
      | Biped | 35 | 11 | 8 | 6 | 8 |
      | Quad | 35 | 11 | 8 | 8 | 8 |
      | Biped | 40 | 12 | 10 | 6 | 10 |
      | Quad | 40 | 12 | 10 | 10 | 10 |
      | Biped | 45 | 14 | 11 | 7 | 11 |
      | Quad | 45 | 14 | 11 | 11 | 11 |
      | Biped | 50 | 16 | 12 | 8 | 12 |
      | Quad | 50 | 16 | 12 | 12 | 12 |
      | Biped | 55 | 18 | 13 | 9 | 13 |
      | Quad | 55 | 18 | 13 | 13 | 13 |
      | Biped | 60 | 20 | 14 | 10 | 14 |
      | Quad | 60 | 20 | 14 | 14 | 14 |
      | Biped | 65 | 21 | 15 | 10 | 15 |
      | Quad | 65 | 21 | 15 | 15 | 15 |
      | Biped | 70 | 22 | 15 | 11 | 15 |
      | Quad | 70 | 22 | 15 | 15 | 15 |
      | Biped | 75 | 23 | 16 | 12 | 16 |
      | Quad | 75 | 23 | 16 | 16 | 16 |
      | Biped | 80 | 25 | 17 | 13 | 17 |
      | Quad | 80 | 25 | 17 | 17 | 17 |
      | Biped | 85 | 27 | 18 | 14 | 18 |
      | Quad | 85 | 27 | 18 | 18 | 18 |
      | Biped | 90 | 29 | 19 | 15 | 19 |
      | Quad | 90 | 29 | 19 | 19 | 19 |
      | Biped | 95 | 30 | 20 | 16 | 20 |
      | Quad | 95 | 30 | 20 | 20 | 20 |
      | Biped | 100 | 31 | 21 | 17 | 21 |
      | Quad | 100 | 31 | 21 | 21 | 21 |

  Scenario Outline: Construction internals 02 - preserving damage
    Given a 50-ton biped left arm has original internal <original> and current internal <current>
    When internal consistency runs
    Then left arm original and current internal are 8 and <after_current>
    Examples:
      | original | current | after_current |
      | 8 | 2 | 2 |
      | 7 | 2 | 8 |
      | 0 | 0 | 8 |

  Scenario Outline: Construction internals 03 - vehicle boundaries
    Given a <unit> of <tons> tons has front original internal <original> and current internal 0
    When internal consistency runs
    Then front original and current internals are <after_original> and <after_current>
    Examples:
      | unit | tons | original | after_original | after_current |
      | Vehicle | 4 | 2 | 1 | 1 |
      | Vehicle | 5 | 2 | 1 | 1 |
      | Vehicle | 14 | 2 | 1 | 1 |
      | Vehicle | 15 | 1 | 2 | 2 |
      | VTOL | 50 | 1 | 5 | 5 |
      | Naval | 100 | 1 | 10 | 10 |
      | Vehicle | 50 | 0 | 0 | 0 |
      | Vehicle | 50 | 5 | 5 | 0 |
      | AeroFighter | 50 | 1 | 1 | 0 |
      | Mech | 51 | 1 | 1 | 0 |
