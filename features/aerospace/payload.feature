# Aerospace payload 01 - catalog
# Aerospace payload 02 - payload display and parser
# Aerospace payload 03 - slot ordering and inert stub
Feature: Aerospace payload
  Background:
    Given a craft whose payload is represented by real critical slots and inventory

  Scenario Outline: Aerospace payload 01 - catalog
    Given bomb index <index>
    When the source payload properties are inspected
    Then name weight type and power are <name> <weight> <type> and <power>
    Examples:
      | index | name | weight | type | power |
      | 0 | 10_Inferno | 10 | 1 | 30 |
      | 1 | 10_Cluster | 10 | 2 | 30 |
      | 2 | 10_Standard | 10 | 0 | 130 |
      | 3 | 50_Inferno | 50 | 1 | 130 |
      | 4 | 50_Cluster | 50 | 2 | 130 |
      | 5 | 50_Standard | 50 | 0 | 130 |
      | 6 | 100_Inferno | 100 | 1 | 250 |
      | 7 | 100_Cluster | 100 | 2 | 250 |
      | 8 | 100_Standard | 100 | 0 | 250 |

  Scenario Outline: Aerospace payload 02 - payload display and parser
    Given bomb command fixture <fixture>
    When BOMB executes with <argument>
    Then the observation is <observation>
    Examples:
      | fixture | argument | observation |
      | landed;stopped;no-bombs | list | No-bombs-installed |
      | landed;stopped;one-bomb | LiSt extra | payload-listed |
      | landed;one-bomb | aim | craft-landed-refusal |
      | airborne;one-bomb | empty | option-required |
      | airborne;one-bomb | drop | which-bomb-refusal |
      | airborne;one-bomb | unknown | invalid-argument |
      | airborne;one-bomb | drop 1 extra | too-many-arguments |
      | airborne;one-bomb | drop 00 | invalid-bomb-number |
      | airborne;one-bomb | drop -1 | negative-bomb-number |
      | airborne;one-bomb | drop 0 | no-bomb-with-number |
      | airborne;no-bombs | drop 0 | No-bombs-installed |
      | airborne;one-bomb | drop 1tail | bomb-released |
      | airborne;unconscious-pilot | list | unconscious-refusal |
      | IC;nonpilot-caller | list | pilot-only-refusal |

  Scenario Outline: Aerospace payload 03 - slot ordering and inert stub
    Given payload fixture <fixture>
    When the payload operation executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | NOSE0-destroyed10-Inferno;NOSE2-live50-Standard;list | two-rows;weights1-and5;Type-header;no-type-row-value |
      | NOSE0-destroyed10-Inferno;NOSE2-live50-Standard;drop1-inbounds | NOSE2-cleared;NOSE0-retained;cargo-recomputed |
      | NOSE0-destroyed10-Inferno;NOSE2-live50-Standard;drop2 | number-refused;slots-retained |
      | live100-Cluster;DestroyBomb | no-change-or-damage |
