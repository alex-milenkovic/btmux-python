# Repair economy ammunition economy 01 literal mode compatibility
# Repair economy ammunition economy 02 commodity priorities
# Repair economy ammunition economy 03 reload unload and early writes
Feature: Repair economy ammunition economy

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy ammunition economy 01 literal mode compatibility
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | NOSPA ammo | normal - | invalid |
      | ordinary ammo without specials | normal - | valid zero mask |
      | nonammo weapon | cluster L | invalid |
      | LBX ammo | cluster l | valid LBX_MODE |
      | missile DAR ammo | artemis A | invalid |
      | missile ordinary ammo | artemis A | valid ARTEMIS_MODE |
      | missile INARC ammo | narc N | invalid |
      | missile ordinary ammo | narc N | valid NARC_MODE |
      | missile IDF ammo | swarm S | valid SWARM_MODE |
      | missile without IDF ammo | swarm S | invalid |
      | missile IDF ammo | swarm1 1 | valid SWARM1_MODE |
      | missile IDF ammo | inferno I | invalid |
      | missile without IDF ammo | inferno I | valid INFERNO_MODE |
      | missile INARC ammo | explosive X | valid INARC_EXPLO_MODE |
      | missile INARC ammo | haywire Y | valid INARC_HAYWIRE_MODE |
      | missile INARC ammo | ecm E | valid INARC_ECM_MODE |
      | missile INARC ammo | nemesis Z | valid INARC_NEMESIS_MODE |
      | TAMMO RFAC ammo | armor piercing R | valid AC_AP_MODE |
      | TAMMO RFAC ammo | flechette F | valid AC_FLECHETTE_MODE |
      | TAMMO RFAC ammo | incendiary D | valid AC_INCENDIARY_MODE |
      | TAMMO RFAC ammo | precision P | valid AC_PRECISION_MODE |
      | TAMMO RFAC ammo | caseless U | valid AC_CASELESS_MODE |
      | TAMMO without RFAC ammo | precision P | invalid |
      | missile IDF ammo | stinger T | valid STINGER_MODE |
      | missile IDF ammo | semiguided G | valid SGUIDED_MODE |
      | missile IDF ammo not ATM | high explosive H | valid ATM_HE_MODE |
      | missile IDF ammo not ATM | extended range V | valid ATM_ER_MODE |
      | missile IDF ammo not MML | LRM mode # | valid MML_LRM_MODE |
      | missile IDF DAR ammo | LRM mode # | invalid |
      | ordinary ammo | unknown Q | invalid |

  Scenario Outline: Repair economy ammunition economy 02 commodity priorities
    Given repair economy state <initial>
    When the repair economy user performs find commodity
    Then the repair economy observation is <expected>

    Examples:
      | initial | expected |
      | StreakSRM6 normal | SSRM base cargo |
      | StreakLRM10 normal | SLRM base cargo |
      | ELRM15 normal | ELRM base cargo |
      | LR_DFM5 normal | LR_DFM base cargo |
      | SR_DFM2 normal | SR_DFM base cargo |
      | LRM15 normal | LRM base cargo |
      | SRM6 normal | SRM base cargo |
      | MRM20 normal | MRM base cargo |
      | ordinary nonmissile ammo normal | encoded ammo identity |
      | LB20 ammo LBX | LBX20 cargo |
      | LB10 ammo LBX | LBX10 cargo |
      | LB5 ammo LBX | LBX5 cargo |
      | LB2 ammo LBX | LBX2 cargo |
      | AC10 AP and PRECISION | AC10 precision cargo |
      | LightAC5 CASELESS | LightAC5 caseless cargo |
      | iNarc explosive and haywire | explosive commodity |
      | LRM15 Narc and Artemis | LRM Narc commodity |
      | LRM15 Swarm1 | LRM Swarm1 commodity |
      | LRM15 ATM_HE | LRM base cargo |
      | nonammo Engine | Engine identity |

  Scenario Outline: Repair economy ammunition economy 03 reload unload and early writes
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | partial bin8 of10 ammo stock1 roll success | reload and advance600 | stock0 at command ammo10 only at600 |
      | partial bin8 of10 ammo stock1 roll fail | reload and advance900 | stock0 ammo8 and no refill |
      | full bin10 of10 mode normal | reload with valid alternative | refuse full and keep normal mode |
      | partial bin8 of10 pending600 minutes | reload with valid alternative | refuse fatigue after emptying and mode change |
      | partial bin8 of10 replacement ammo stock0 | reload with valid alternative | refuse stock after emptying and mode change |
      | full bin10 of10 roll success | unload and advance600 | ammo0 and returned commodity1 |
      | partial bin8 of10 roll success | unload and advance600 | ammo0 and returned commodity0 |
      | full bin10 of10 roll fail | unload and advance900 | ammo0 and returned commodity1 |
      | empty bin0 of10 | unload | refuse empty without dice |
      | OOC nonTech ammo2 of10 unrelated mode retained | toggletype valid alternative | ammo10 and only ammo mode bits replaced |
