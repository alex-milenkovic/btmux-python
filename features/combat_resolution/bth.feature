# Combat to hit 01 - attacker movement; Combat to hit 02 - target movement; Combat to hit 03 - source-specific additive terms
Feature: Combat to hit
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat to hit 01 - attacker movement
    Given a ready attacker with movement profile <profile>
    When its attack movement modifier is requested
    Then the attack movement modifier is <modifier>
    Examples:
      | profile | modifier |
      | stationary-facing-set | 0 |
      | stationary-turning | 1 |
      | walking-turning | 2 |
      | running-turning | 2 |
      | jumping | 3 |
      | battlesuit-jumping | 0 |
      | intact-quad-prone | 0 |
      | biped-prone | 2 |
      | standing | 2 |
      | stabilizing | 2 |

  Scenario Outline: Combat to hit 02 - target movement
    Given an otherwise mobile target with profile <profile> at range <range>
    When its target movement modifier is requested
    Then target movement modifier is <modifier>
    Examples:
      | profile | range | modifier |
      | ordinary-stationary | 2 | 0 |
      | ordinary-43kph | 2 | 1 |
      | ordinary-43.01kph | 2 | 2 |
      | purifier-stationary | 2 | 3 |
      | purifier-10.75kph | 2 | 2 |
      | purifier-21.5kph | 2 | 1 |
      | purifier-21.51kph | 2 | 0 |
      | prone-stationary | 1 | -2 |
      | prone-stationary | 1.01 | 1 |

  Scenario Outline: Combat to hit 03 - source-specific additive terms
    Given a stable short-range shot with gunnery 4 and all other modifiers zero
    When the isolated BTH condition is <condition>
    Then normal shot BTH is <bth>
    Examples:
      | condition | bth |
      | target-MW | 6 |
      | target-BA | 5 |
      | target-dropship | 1 |
      | pulse | 2 |
      | MRM | 5 |
      | heavy-weapon | 5 |
      | rocket | 5 |
      | AP-ammo | 5 |
      | attacker-haywire | 5 |
      | targetless-hex-ON_TC | 0 |
      | missing-indirect-spotter | 0 |
