# Combat complete workflows 01 - new behavior through existing consumers; Combat complete workflows 02 - outside service boundaries
Feature: Combat complete workflows
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat complete workflows 01 - new behavior through existing consumers
    Given the documented end-to-end fixture for <workflow>
    When its user commands and normal event clock run
    Then observable result is <result> with real damage heat and event observations
    Examples:
      | workflow | result |
      | spotted-artillery | delayed-area-impact |
      | movement-mine | contact-damage |
      | jump-DFA | landing-impact-and-recycle |
      | RAC-jam-unjam-fire | jam-cleared-then-shot |
      | stealth-enable-lock-fire | range-and-stable-lock-enforced |
      | TIC-artillery-coordinates | all-selected-shells-queued |
      | pod-ECM-remove | field-recomputed-by-normal-update |

  Scenario Outline: Combat complete workflows 02 - outside service boundaries
    Given a fixture requiring <dependency>
    When the corresponding combat workflow reaches that dependency
    Then unavailable effect is explicitly not applied and workflow remains blocked
    Examples:
      | dependency |
      | persistent-occupant-transfer |
      | persistent-character-XP |
      | mine-object-script |
      | building-object-damage |
      | unavailable-C3-network-formation |
