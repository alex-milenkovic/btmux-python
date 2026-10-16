# Character experience 01 - strict thresholds and packed values
# Character experience 02 - threshold scaling
# Character experience 03 - gain cooldown and overrides
# Character experience 04 - loss and wrap
# Character experience 05 - administrative value modes
# Character experience 06 - threshold and leaderboard controls
Feature: Character experience
  Background:
    Given a source character with Gunnery-Battlemech raw BTH4 threshold3000 and XP_MAX16777216

  Scenario Outline: Character experience 01 - strict thresholds and packed values
    Given raw XP <raw>
    When the source bonus is recomputed and next level queried
    Then bonus is <bonus> packed XP is <packed> and cumulative next threshold is <next>
    Examples:
      | raw | bonus | packed | next |
      | 0 | 0 | 0 | 3001 |
      | 3000 | 0 | 3000 | 3001 |
      | 3001 | 1 | 16780217 | 12001 |
      | 12000 | 1 | 16789216 | 12001 |
      | 12001 | 2 | 33566433 | 39001 |
      | 39000 | 2 | 33593432 | 39001 |
      | 39001 | 3 | 50370649 | 120001 |

  Scenario Outline: Character experience 02 - threshold scaling
    Given raw BTH <bth> and configured threshold <threshold>
    When XP is <xp> and bonus is recomputed
    Then bonus is <bonus> and first cumulative threshold is <first>
    Examples:
      | bth | threshold | xp | bonus | first |
      | 5 | 3000 | 1000 | 0 | 1001 |
      | 5 | 3000 | 1001 | 1 | 1001 |
      | 3 | 3000 | 9001 | 1 | 9001 |
      | 18 | 50 | 1 | 0 | 2 |
      | 18 | 50 | 2 | 1 | 2 |
      | 4 | 0 | 5000 | 0 | -1 |

  Scenario Outline: Character experience 03 - gain cooldown and overrides
    Given last use 100 with <kind> skill and current time <now>
    When XP gain 1 requests override <override>
    Then accepted is <accepted> and last use becomes <last>
    Examples:
      | kind | now | override | accepted | last |
      | ordinary | 130 | False | False | 100 |
      | ordinary | 131 | False | True | 131 |
      | SK_XP | 100 | False | True | 100 |
      | ordinary | 100 | True | True | 100 |
      | ordinary-disconnected | 131 | False | True | 131 |

  Scenario Outline: Character experience 04 - loss and wrap
    Given packed XP <packed>
    When XP is changed with <operation>
    Then packed XP becomes <result>
    Examples:
      | packed | operation | result |
      | 16780217 | lower-500 | 1500 |
      | -1 | lower-500 | 0 |
      | 0 | lower-500 | 0 |
      | 16777215 | gain-forced-1 | 0 |
      | 3001 | lower-1000 | 16780217 |

  Scenario Outline: Character experience 05 - administrative value modes
    Given Gunnery-Battlemech BTH4 raw level4 raw XP3001 and bonus1
    When the administrator requests <operation>
    Then the visible result is <result>
    Examples:
      | operation | result |
      | get-flag0 | 5 |
      | get-flag1 | 3 |
      | get-flag2 | 3001 |
      | get-flag3 | 4 |
      | get-flag4 | 12001 |
      | set-flag3-XP3000 | rawXP3000-bonus0 |
      | set-flag2-XP1 | rawXP3002-bonus1 |
      | set-flag1-BTH10 | rawLevel0 |

  Scenario Outline: Character experience 06 - threshold and leaderboard controls
    Given configuration request <request>
    When the ordinary XP control executes
    Then the visible result is <result>
    Examples:
      | request | result |
      | threshold-empty | invalid-arguments |
      | threshold-Running-minus1 | negative-error |
      | threshold-Build-5 | not-skill |
      | threshold-Running-0 | threshold0 |
      | getthreshold-unknown | -1 |
      | top-nonplayers-and-wizards | excluded |
      | top-A100-B100-C200 | order-C-B-A-percent50-25-25-total400 |
      | top-17-players | top16-percent-against17 |
