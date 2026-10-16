# Construction modes 01 - approved mixed mode loading; Construction modes 02 - strict helpers remain strict; Construction modes 03 - saved modes drive real firing
Feature: Construction modes
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction modes 01 - approved mixed mode loading
    Given a modern template has <kind> slot with mode field <text>
    When the approved union mode loader runs
    Then fire mask is <fire> ammo mask is <ammo> and outcome is <outcome>
    Examples:
      | kind | text | fire | ammo | outcome |
      | weapon | RearMount/BAR/Precision | 32 | 65536 | success |
      | ammo | Halfton/BAR/LBX/Cluster | 128 | 1 | success |
      | weapon | RearMount | 32 | 0 | success |
      | ammo | LBX/Cluster | 0 | 1 | success |
      | weapon | - | 0 | 0 | success |
      | ammo | - | 0 | 0 | success |
      | weapon | rearMOUNT/BAR/precision | 32 | 65536 | success |
      | ammo | Halfton/BAR/Halfton/BAR/LBX/Cluster | 128 | 1 | success |
      | weapon | unknown | unchanged | unchanged | error |
      | ammo | unknown | unchanged | unchanged | error |
      | weapon | RearMount/BAR/unknown | unchanged | unchanged | error |
      | ammo | LBX/Cluster/BAR/unknown | unchanged | unchanged | error |
      | ammo | Halfton/BAR/ | unchanged | unchanged | error |

  Scenario Outline: Construction modes 02 - strict helpers remain strict
    When the standalone <table> mode parser receives <text>
    Then its result is <result>
    Examples:
      | table | text | result |
      | fire | RearMount/BAR/Precision | -1 |
      | ammo | RearMount/BAR/Precision | -1 |
      | fire | Halfton/BAR/LBX/Cluster | -1 |
      | ammo | Halfton/BAR/LBX/Cluster | -1 |
      | fire | RearMount | 32 |
      | ammo | Precision | 65536 |

  Scenario Outline: Construction modes 03 - saved modes drive real firing
    Given an ordinary editor configures weapon <weapon> and its ammo with saved fire mask <fire> and ammo mask <ammo> in the source-appropriate weapon or ammo slot
    When a modern save is loaded into a fresh unit and a legal ordinary shot is fired
    Then the saved and loaded masks agree and the shot consumes one round with <behavior>
    Examples:
      | weapon | fire | ammo | behavior |
      | IS.LB5-XAC | 128 | 1 | half-bin-and-LBX-cluster-resolution |
      | IS.AC/5 | 32 | 65536 | rear-arc-and-precision-ammunition |
      | IS.AC/5 | 32 | 0 | rear-arc-standard-ammunition |
      | IS.AC/5 | 0 | 65536 | forward-arc-precision-ammunition |
      | IS.AC/5 | 0 | 0 | forward-arc-standard-ammunition |
