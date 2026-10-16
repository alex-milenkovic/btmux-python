# Construction helpers 01 - strict versus lenient bits; Construction helpers 02 - read description bytes; Construction helpers 03 - computer conversion; Construction helpers 04 - fuel by class
Feature: Construction helpers
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction helpers 01 - strict versus lenient bits
    Given a bit table with Alpha Beta and Gamma in that order
    When the <parser> bit parser reads <text>
    Then its integer result is <value>
    Examples:
      | parser | text | value |
      | strict | Alpha | 1 |
      | strict | Alpha~Beta | 3 |
      | strict | Alpha~ | -1 |
      | strict | - | 0 |
      | strict | empty | 0 |
      | strict | unknown | -1 |
      | lenient | Alpha~unknown~Gamma | 5 |
      | delimited | Alpha/BAR/Gamma | 5 |
      | delimited | Alpha/BAR//BAR/Beta | 3 |
      | delimited | Alpha/BAR/ | -1 |
      | delimited | Alpha~/BAR/Beta | -1 |

  Scenario Outline: Construction helpers 02 - read description bytes
    When read_desc reads same-line data <text> with an empty remaining stream
    Then the returned bytes are <value>
    Examples:
      | text | value |
      | {~Name~} | Name |
      | {~Name} | Nam |
      | {~50~} | 50 |
      | {~50} | 5 |
      | no-brace | empty |

  Scenario Outline: Construction helpers 03 - computer conversion
    Given a unit with computer0 radio3 scan <scan> tac9 lrs9 and radio range9
    When legacy computer conversion runs
    Then computer scan tac lrs and radio range are <computer> <out_scan> <tac> <lrs> and <radio>
    Examples:
      | scan | computer | out_scan | tac | lrs | radio |
      | 20 | 2 | 20 | 20 | 40 | 100 |
      | 25 | 3 | 25 | 25 | 50 | 100 |
      | 30 | 4 | 30 | 30 | 60 | 100 |
      | 19 | 0 | 19 | 9 | 9 | 9 |

  Scenario Outline: Construction helpers 04 - fuel by class
    Given unit type <unit>
    When default fuel is requested
    Then fuel is <fuel>
    Examples:
      | unit | fuel |
      | VTOL | 4000 |
      | AeroFighter | 2400 |
      | Aerodyne_DropShip | 7200 |
      | Spheroid_DropShip | 7200 |
      | Mech | 0 |
      | Vehicle | 0 |
      | Battlesuit | 0 |
