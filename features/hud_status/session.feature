# HUD session 01 - handshake; HUD session 02 - dispatch; HUD session 03 - eligibility; HUD session 04 - session ownership
Feature: HUD session
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: HUD session 01 - handshake
    Given session key is <initial>
    When the user submits HUD text <request>
    Then the HUD reply class is <class> type is <type> and payload is <payload>
    And the session key becomes <key>
    Examples:
      | initial | request | class | type | payload | key |
      | unset | no-argument | unframed | unframed | #HUD hudinfo version 0.8 | unset |
      | unset | gs | ??? | E | No session key set | unset |
      | unset | key=abc19 | KEY | R | Key set | abc19 |
      | abc19 | key= | KEY | R | Key set | unset |
      | abc19 | key=bad-key | KEY | E | Invalid key | abc19 |
      | abc19 | key=123456789012345678901 | KEY | E | Invalid key | abc19 |
      | unset | key=12345678901234567890 | KEY | R | Key set | 12345678901234567890 |

  Scenario Outline: HUD session 02 - dispatch
    Given session key is test
    When the user submits HUD text <request>
    Then the HUD reply class is <class> type is E and payload is <payload>
    And no successful HUD list terminator is emitted
    Examples:
      | request | class | payload |
      | GS | ??? | GS: subcommand not found |
      | bad! | ??? | Invalid subcommand |
      | gs extra | GS | Command takes no arguments |
      | asc | ASC | Not enough arguments |
      | t | T | Not enough arguments |

  Scenario Outline: HUD session 03 - eligibility
    Given session key is test and the associated unit state is <state>
    When the user submits HUD text <request>
    Then the HUD result is <result>
    Examples:
      | state | request | result |
      | no-unit | wl | catalog-list |
      | no-unit | gs | Not in a BattleTech unit |
      | shutdown | gs | general-status |
      | destroyed | we | weapon-list |
      | unconscious | gs | You are unconscious....zzzzzzz |
      | blinded | oas | You are unconscious....zzzzzzz |
      | destroyed | c | You are destroyed! |
      | shutdown | c | Reactor is not online |

  Scenario Outline: HUD session 04 - session ownership
    Given local player placement <placement> with eligible self A location B and carried unit C as applicable
    When an independent keyed session requests HUD gs
    Then the selected unit is <selected>
    And changing that session key does not change another session key
    Examples:
      | placement | selected |
      | all | A |
      | no-self | B |
      | no-self-zombie-location | C |
      | none | no-unit-error |
