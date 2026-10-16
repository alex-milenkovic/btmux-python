# Combat weapon modes 01 - group selector grammar; Combat weapon modes 02 - sticky and first-character selection; Combat weapon modes 03 - source capability predicates
Feature: Combat weapon modes
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat weapon modes 01 - group selector grammar
    Given three ready Ultra weapons numbered 0 through 2 with no modes
    When ultra mode is requested for selector <selector>
    Then Ultra weapons after selection are <selected>
    Examples:
      | selector | selected |
      | 0 | 0 |
      | 00 | none |
      | +0 | none |
      | 1junk | 1 |
      | 2-0 | 0,1,2 |
      | 0,0 | none |
      | 0,2 | 0,2 |
      | 0,99,1 | 0 |

  Scenario Outline: Combat weapon modes 02 - sticky and first-character selection
    Given a ready <weapon> with initial mode <initial>
    When mode command text is <text>
    Then selected mode is <mode>
    Examples:
      | weapon | initial | text | mode |
      | RAC | none | 0 2foo | RAC2 |
      | RAC | RAC2 | 0 2 | RAC2 |
      | RAC | RAC6 | 0 bad | none |
      | iNARC | none | 0 Yfoo | HAYWIRE |
      | iNARC | HAYWIRE | 0 Y | HAYWIRE |
      | iNARC | ECM | 0 | none |
      | iNARC | none | 0 Z | NEMESIS |

  Scenario Outline: Combat weapon modes 03 - source capability predicates
    Given a ready weapon with profile <profile>
    When mode command <command> is applied
    Then capability decision is <decision>
    Examples:
      | profile | command | decision |
      | non-ATM-IDF-non-DAR | atmrange | accepted |
      | LRM | inferno | accepted |
      | SRM | smoke | accepted |
      | artillery | smoke | rejected |
      | artillery | cluster | accepted |
      | rocket | inferno | rejected |
      | one-shot-LRM | hotload | rejected |
      | LRM-no-Artemis-link | artemis | rejected |
