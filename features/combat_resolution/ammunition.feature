# Combat ammunition 01 - preferred-bin fallback; Combat ammunition 02 - burst shortages; Combat ammunition 03 - one-use weapon lifecycle; Combat ammunition 04 - warning threshold
Feature: Combat ammunition
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat ammunition 01 - preferred-bin fallback
    Given a weapon mounted in CT with ordinary ammo CT 4 LT 3 RT 2
    When preferred ammo source is <source> with LT bin condition <condition> and one shot fires
    Then the spent bin is <bin>
    Examples:
      | source | condition | bin |
      | LT | working | LT |
      | LT | empty | CT |
      | LT | destroyed | CT |
      | - | working | CT |

  Scenario Outline: Combat ammunition 02 - burst shortages
    Given a ready <weapon> with <ammo> ordinary rounds and requested burst <burst>
    When a nonjamming shot fires with gattling draw 6
    Then actual shot count is <shots> and ammo remaining is <remaining>
    Examples:
      | weapon | ammo | burst | shots | remaining |
      | RAC | 5 | 6 | 1 | 4 |
      | RAC | 6 | 6 | 6 | 0 |
      | RAC | 3 | 4 | 1 | 2 |
      | RAC | 1 | 2 | 1 | 0 |
      | gattling | 8 | 6 | 2 | 2 |
      | gattling | 2 | 6 | 1 | 0 |
      | Ultra | 1 | 2 | 1 | 0 |
      | Ultra | 2 | 2 | 2 | 0 |

  Scenario Outline: Combat ammunition 03 - one-use weapon lifecycle
    Given an unfired <weapon> with no ammo bins
    When it fires then recycles and fire is requested again
    Then first shot fires and second shot is rejected with spent marker <marker>
    Examples:
      | weapon | marker |
      | pure-rocket | all-run-ROCKET_FIRED |
      | one-shot | OS_USED |

  Scenario Outline: Combat ammunition 04 - warning threshold
    Given a started nonzero-index weapon with warning threshold 5 and AmmoWarn enabled
    When ammunition count is <count> and expenditure-check offset is <offset>
    Then warning severity is <severity> and weapon-check state is set
    Examples:
      | count | offset | severity |
      | 5 | 0 | red |
      | 10 | 0 | yellow |
      | 6 | 1 | red |
      | 5 | 2 | red |
      | 7 | 1 | none |
