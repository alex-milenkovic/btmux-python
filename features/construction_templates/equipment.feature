# Construction equipment 01 - weapon placement; Construction equipment 02 - reload and restock; Construction equipment 03 - fire mode transitions; Construction equipment 04 - special insertion
Feature: Construction equipment
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction equipment 01 - weapon placement
    Given an editor targets an intact mech left torso with each critical data7
    When addweap receives <arguments>
    Then outcome is <outcome> and changed slots are <slots> with data7 retained
    Examples:
      | arguments | outcome | slots |
      | IS.MediumLaser~LT~1 | added | 1 |
      | IS.MediumLaser~LT~1~R~T~O | added-rear-TC-OS | 1 |
      | IS.PPC~LT~1~2 | not-enough | empty |
      | IS.PPC~LT~1~2~3 | added | 1,2,3 |
      | IS.MediumLaser~LT~1~2 | too-many | empty |
      | IS.AC/20~LT~1~2 | split-needs8 | 1,2 |
      | IS.PPC~LT~1~2~13 | bad-slot-after-writes | 1,2 |

  Scenario Outline: Construction equipment 02 - reload and restock
    Given a mech slot contains an AC5 ammo bin with rounds2 fire mode <fire> and ammo mode <ammo>
    When editor <operation> applies <flag>
    Then first-critical fire mode and ammo mode are <out_fire> and <out_ammo>
    And ammunition rounds are <rounds>
    Examples:
      | fire | ammo | operation | flag | out_fire | out_ammo | rounds |
      | none | AP | reload | - | none | none | 20 |
      | Halfton | AP | reload | L | Halfton | AP+LBX | 10 |
      | none | none | reload | + | Halfton | none | 10 |
      | none | none | reload | R | none | AP | 10 |
      | none | none | reload | U | none | Caseless | 40 |
      | Halfton | AP | restock | none | Halfton | AP | 10 |
      | none | Smoke | restock | none | none | Smoke | 20 |

  Scenario Outline: Construction equipment 03 - fire mode transitions
    Given an ammo-using weapon starts with fire mode <fire> and ammo mode AP
    When mechrep firemode selects <flag>
    Then first-critical fire mode and ammo mode are <out_fire> and <out_ammo>
    Examples:
      | fire | flag | out_fire | out_ammo |
      | RearMount | P | none | Precision |
      | OneShot | L | OneShot | LBX |
      | Halfton | L | Halfton | AP+LBX |
      | OneShot | - | none | none |
      | none | Z | none | none |
      | none | + | none | none |
      | none | J | Jettison | none |
      | none | # | none | MML_LRM |

  Scenario Outline: Construction equipment 04 - special insertion
    Given an editor targets a <unit> and the chosen slot has fire7 ammo3
    When addspecial places <part> in <section> slot1 with data <data>
    Then stored data is <stored> and immediate consequence is <effect> with fire7 ammo3 retained
    Examples:
      | unit | part | section | data | stored | effect |
      | Mech | empty | LT | 5 | 5 | type-empty |
      | Mech | HeatSink | LT | 7 | 7 | type-HeatSink |
      | Mech | SplitCrit_Left | LT | 4 | 3 | split-reference |
      | Vehicle | CASE | LS | 0 | 0 | aft-CASE |
      | Mech | CASE | LT | 0 | 0 | local-CASE |
      | Mech | ArtemisIV | LT | 3 | 3 | Artemis-tech |
      | Mech | TargetingComputer | LT | 0 | 0 | TC-tech |
      | Mech | AngelEcm | LT | 0 | 0 | Angel-tech |
