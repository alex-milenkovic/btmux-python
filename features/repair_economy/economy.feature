# Repair economy object inventory storage 01 raw storage mutations
# Repair economy object inventory storage 02 cleanup listing and admin
Feature: Repair economy object inventory storage

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy object inventory storage 01 raw storage mutations
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | [idA,0,2],[idB,0,3] | find idA brand0 | count2 without write |
      | [idA,0,2],[idA,0,5] | find idA brand0 | count2 not7 |
      | [idA,0,2],[idB,0,3] | change idA brand0 plus4 | [idB,0,3],[idA,0,6] |
      | [idA,0,2],[idA,0,5] | change idA brand0 plus1 | [idA,0,5],[idA,0,3] |
      | [idA,0,2],[idB,0,3] | change idA brand0 minus2 | [idB,0,3] |
      | [idA,0,2],[idB,0,3] | change idA brand0 minus9 | [idB,0,3] |
      | [idB,0,3] | change idA brand0 minus1 | identical raw storage without attribute write |
      | [idA,0,2],[idB,0,3] | set idA brand0 to2 | identical raw storage without attribute write |
      | [idA,0,2],[idB,0,3] | set idA brand0 to5 | [idB,0,3],[idA,0,5] |
      | invalid object | change idA brand0 plus3 | no write |
      | brand2 same catalog short name as brand0 | change idA brand2 plus3 | normalized brand0 count3 |
      | brand2 distinct catalog short name | change idA brand2 plus3 | retained brand2 count3 |
      | raw actuator count2 | change actuator plus1 | actuator removed and standard actuator cargo plus3 |
      | raw actuator count2 | find standard actuator cargo | count0 without alias lookup |
      | [idA,0,2 missing closing bracket | remove idA brand0 | raw text unchanged |
      | [idA,0,2],[idB,0,3] | remove idB brand0 | [idA,0,2] |
      | [idA,0,2],[idB,0,3] | remove idA brand0 | [idB,0,3] |

  Scenario Outline: Repair economy object inventory storage 02 cleanup listing and admin
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | duplicate idA counts2 and5 | manifest | aggregated count7 |
      | idA raw counts2 and-5 | manifest | displayed count-3 |
      | idA count2 one-ton item | manifest | count2 weight2 tons |
      | raw valid positive duplicate crap negative and invalid catalog entries | Rfixstuff | aggregate valid positives only and canonical order |
      | actor room has inventory and unit differs | manifest | actor-room inventory |
      | selector matches short family and different long family | Raddstuff selector 3 | short family only gains3 each |
      | admin selector matches20 parts | Raddstuff selector 3 | all20 gain3 |
      | admin nonGOD selector matches21 parts | Raddstuff selector 3 | refuse before any stock mutation |
      | admin GOD selector matches21 parts | Raddstuff selector 3 | all21 gain3 |
      | admin count50001 | Raddstuff selector 50001 | each match gains50000 |
      | admin count0 | Raddstuff selector 0 | refuse positive-count requirement |
      | admin count3junk | Rremovestuff selector 3junk | remove3 by atoi prefix |
      | admin nonempty room inventory | Rresetstuff | room storage empty and log request |
      | empty room inventory | manifest | empty footer |
