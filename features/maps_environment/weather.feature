# Maps weather 01 - symbolic weather classification; Maps weather 02 - source gun arithmetic; Maps weather 03 - pilot arithmetic; Maps weather 04 - minus heat arithmetic
Feature: Maps weather
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps weather 01 - symbolic weather classification
    Given symbolic precipitation is <precip> fog and sand are absent temperature is <temp> and windspeed is <wind>
    When weather effects are calculated
    Then the effect names are <effects>
    Examples:
      | precip | temp | wind | effects |
      | none | 20 | 29 | none |
      | none | 20 | 30 | winds |
      | none | 20 | 60 | winds |
      | none | 20 | 61 | high-winds |
      | ordinary | 0 | 0 | snow |
      | ordinary | 1 | 0 | rain |
      | heavy | 0 | 60 | winds,heavy-snow |
      | heavy | 0 | 61 | blizzard |
      | heavy | 1 | 61 | high-winds,heavy-rain |
      | ordinary-and-heavy | 0 | 0 | heavy-snow |

  Scenario Outline: Maps weather 02 - source gun arithmetic
    Given a diagnostic weapon type is <weapon> and raw effect inputs are <effects>
    When the supplied weather gun arithmetic is evaluated
    Then the modifier is <modifier>
    Examples:
      | weapon | effects | modifier |
      | TBEAM | rain=1 | 1 |
      | TBEAM | heavy-rain=1 | 0 |
      | TAMMO | blizzard=1 | 2 |
      | TBEAM | blizzard=1 | 1 |
      | TBEAM | fog=1,sand=1 | 3 |
      | TAMMO | sand=1,winds=1 | 2 |
      | TAMMO | high-winds=1 | 2 |
      | TAMMO | high-winds=2 | 0 |

  Scenario Outline: Maps weather 03 - pilot arithmetic
    Given a diagnostic unit is <position> with movement <move> and layer predicates deep-snow mud and rapids all true
    When pilot weather effects are evaluated with heavy rain true and all other weather predicates false
    Then the modifier is <modifier>
    Examples:
      | position | move | modifier |
      | grounded | biped | 5 |
      | grounded | hover | 1 |
      | jumping | biped | 0 |
      | above-ground | biped | 0 |
      | no-map | biped | 0 |

  Scenario Outline: Maps weather 04 - minus heat arithmetic
    Given diagnostic minus heat starts at 10 with temperature <temp> weather <effects> and no deep snow
    When weather heat effects are applied once
    Then minus heat is <minus>
    Examples:
      | temp | effects | minus |
      | 20 | heavy-rain | 8 |
      | 20 | rain | 9 |
      | 20 | blizzard | 8 |
      | 20 | heavy-snow | 9 |
      | -30 | none | 10 |
      | -31 | none | 11 |
      | -40 | none | 11 |
      | -41 | none | 12 |
      | 50 | none | 10 |
      | 51 | none | 9 |
      | 61 | none | 8 |
