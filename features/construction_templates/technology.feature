# Construction technology 01 - technology thresholds; Construction technology 02 - editor tech parsing; Construction technology 03 - editor tech deletion; Construction technology 04 - distributed technology
Feature: Construction technology
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction technology 01 - technology thresholds
    Given a <unit> of50 tons with tech <base> has <count> slots of <part> with condition <condition>
    When update_specials runs
    Then the derived <flag> flag is <enabled>
    Examples:
      | unit | base | count | part | condition | flag | enabled |
      | Mech | standard | 13 | FerroFibrous | intact | FF | 0 |
      | Mech | standard | 14 | FerroFibrous | destroyed | FF | 1 |
      | Mech | Clan | 7 | EndoSteel | intact | ES | 1 |
      | Vehicle | standard | 1 | FerroFibrous | intact | FF | 1 |
      | Mech | standard | 1 | Masc | intact | MASC | 0 |
      | Mech | standard | 2 | Masc | intact | MASC | 1 |
      | Mech | standard | 2 | Masc | destroyed | MASC | 0 |
      | Mech | standard | 1 | BeagleProbe | destroyed | BAP | 0 |
      | Mech | standard | 1 | Ecm | destroyed | ECM | 1 |
      | Mech | standard | 2 | AngelEcm | intact | Angel | 1 |
      | Mech | standard | 1 | AngelEcm | intact | Angel | 0 |
      | Mech | standard | 3 | BloodhoundProbe | destroyed | Bloodhound | 1 |
      | Mech | standard | 1 | TargetingComputer | intact | TC | 1 |
      | Mech | standard | 1 | TargetingComputer | destroyed | TC | 0 |
      | Mech | standard | 6 | TripleStrengthMyomer | destroyed | TSM | 1 |

  Scenario Outline: Construction technology 02 - editor tech parsing
    Given an editor targets a <unit> with zero tech flags
    When editor operation <operation> receives <text>
    Then outcome is <outcome>
    Examples:
      | unit | operation | text | outcome |
      | Mech | addtech | Clan | Clan-set |
      | Mech | addtech | AngelECM_Tech | Angel-set |
      | Mech | addtech | Clan~AngelECM_Tech | invalid-no-change |
      | Mech | addtech | - | nothing-set |
      | Mech | addinftech | Swarm_Attack_Tech | invalid-unit |
      | Battlesuit | addinftech | Swarm_Attack_Tech | swarm-set |
      | Battlesuit | addinftech | unknown | invalid-no-change |

  Scenario Outline: Construction technology 03 - editor tech deletion
    Given a mech has CASE TSM MASC ECM and infantry Swarm with corresponding slots storing data7
    When editor operation deltech receives <text>
    Then the remaining first-table tech and infantry tech are <tech> and Swarm while removed slots retain data7
    Examples:
      | text | tech |
      | all | none |
      | Case | TSM+MASC+ECM |
      | TripleMyomerTech | MASC+ECM |
      | Masc | TSM+ECM |
      | ECM | TSM+MASC |
      | unknown | TSM+MASC+ECM |

  Scenario Outline: Construction technology 04 - distributed technology
    Given a mech has <layout> special criticals with ECM flag <ecm>
    When update_specials recomputes derived technology
    Then NSS and stealth armor are <nss> and <stealth>
    Examples:
      | layout | ecm | nss | stealth |
      | one-NSS-every-location-except-head | 0 | 1 | 0 |
      | one-NSS-every-location-except-head-and-LA | 0 | 0 | 0 |
      | two-Stealth-every-location-except-head-and-CT-with-ECM-slot | 0 | 0 | 1 |
      | two-Stealth-every-location-except-head-and-CT | 1 | 0 | 0 |
      | two-Stealth-every-location-except-head-CT-and-LA-with-ECM-slot | 0 | 0 | 0 |
