# Combat weapon impacts 01 - risky firing before tail; Combat weapon impacts 02 - glancing threshold; Combat weapon impacts 03 - heat-only and plasma
Feature: Combat weapon impacts
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat weapon impacts 01 - risky firing before tail
    Given a ready loaded weapon with mode <mode> and attack BTH 2
    When attack roll is <roll> and caseless explosion roll is <secondary>
    Then weapon outcome is <outcome> and ordinary tail resources are <tail>
    Examples:
      | mode | roll | secondary | outcome | tail |
      | HOTLOAD | 2 | 7 | AMMOJAMMED | unspent |
      | HOTLOAD | 3 | 7 | AMMOJAMMED | unspent |
      | HOTLOAD | 4 | 7 | fired | spent |
      | CASELESS | 3 | 7 | AMMOJAMMED | unspent |
      | CASELESS | 3 | 8 | destroyed-internal-ammo-spent | unspent |
      | RFAC | 2 | 7 | destroyed-internal-ammo-spent | unspent |
      | RFAC | 4 | 7 | AMMOJAMMED | unspent |
      | RAC2 | 2 | 7 | AMMOJAMMED | unspent |
      | RAC4 | 3 | 7 | AMMOJAMMED | unspent |
      | RAC6 | 4 | 7 | AMMOJAMMED | unspent |
      | ULTRA | 2 | 7 | destroyed | unspent |

  Scenario Outline: Combat weapon impacts 02 - glancing threshold
    Given a base 9 damage single-hit weapon with BTH 7 and no armor modifiers
    When glancing configuration is <mode> and attack roll is <roll>
    Then applied weapon damage is <damage>
    Examples:
      | mode | roll | damage |
      | 0 | 6 | 0 |
      | 0 | 7 | 9 |
      | 1 | 6 | 0 |
      | 1 | 7 | 5 |
      | 1 | 8 | 9 |
      | 2 | 5 | 0 |
      | 2 | 6 | 5 |
      | 2 | 7 | 9 |

  Scenario Outline: Combat weapon impacts 03 - heat-only and plasma
    Given a target with weapon heat 10 and ample armor
    When impact kind is <kind> with base damage 5 and plasma draw 4
    Then target heat is <heat> and armor loss is <armor>
    Examples:
      | kind | heat | armor |
      | flamer-heat | 15 | 0 |
      | coolant | 5 | 0 |
      | IS-plasma-MECH-base10 | 14 | 10 |
      | IS-plasma-ground-base10 | 10 | 10 |
      | CL-plasma-MECH-base10 | 10 | 10 |
