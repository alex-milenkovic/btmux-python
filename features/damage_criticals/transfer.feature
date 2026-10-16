# Damage transfer 01 - armor and internal overflow; Damage transfer 02 - existing dead section; Damage transfer 03 - eligibility before side effects; Damage transfer 04 - initial damage accounting; Damage transfer 05 - swarm absorption uses the source roll
Feature: Damage transfer
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage transfer 01 - armor and internal overflow
    Given a MECH left arm with armor 2 internal 3 and left torso with armor 4 internal 20
    And containment <containment> and incidental critical rolls below eight
    When <damage> points strike the arm through the <path> path
    Then left arm is destroyed <arm_destroyed> and left torso armor is <armor_left> internal is <internal_left>
    Examples:
      | containment | damage | path | arm_destroyed | armor_left | internal_left |
      | none | 4 | ordinary | False | 4 | 20 |
      | none | 8 | ordinary | True | 1 | 20 |
      | none | 10 | ordinary | True | 0 | 19 |
      | none | 8 | internal | True | 4 | 15 |
      | CASE | 8 | internal | True | 4 | 20 |
      | Clan | 8 | internal | True | 4 | 20 |
      | CASE-II-only | 8 | internal | True | 4 | 15 |
      | CASE | 10 | ordinary | True | 0 | 19 |

  Scenario Outline: Damage transfer 02 - existing dead section
    Given a MECH with already destroyed left arm and live left torso armor 10 internal 20
    When an ordinary <damage> point hit targets the dead arm
    Then left torso armor is <armor_left> and the destroyed arm dispatches no new criticals
    Examples:
      | damage | armor_left |
      | 3 | 7 |
      | 10 | 0 |

  Scenario Outline: Damage transfer 03 - eligibility before side effects
    Given an intact hidden sprinting MECH with map safety <map_safe> unit safety <unit_safe> and attacker weapons hold <hold>
    When a five point hit is applied to left torso armor 20
    Then armor is <armor_left> hidden is <hidden> sprinting is <sprinting> and hold warning count is <warnings>
    And one damage-entry roll is consumed even when safety prevents the hit
    Examples:
      | map_safe | unit_safe | hold | armor_left | hidden | sprinting | warnings |
      | True | False | False | 20 | True | True | 0 |
      | False | True | False | 20 | True | True | 0 |
      | False | False | False | 15 | False | False | 0 |
      | False | False | True | 15 | False | False | 1 |

  Scenario Outline: Damage transfer 04 - initial damage accounting
    Given a standing MECH with left arm armor 2 internal 3 and left torso armor 20
    When enemy gun damage <damage> crosses the arm with critical rolls below eight
    Then inflicted and taken counters each increase <damage> and stagger records total <damage>
    Examples:
      | damage |
      | 8 |
      | 11 |

  Scenario Outline: Damage transfer 05 - swarm absorption uses the source roll
    Given one live swarming suit on an armored MECH and ignore-swarmers <ignore>
    When a host hit at <section> with rear flag <rear> uses absorption roll <roll>
    Then the damage is routed to the suit <absorbed>
    Examples:
      | ignore | section | rear | roll | absorbed |
      | False | LTORSO | False | 12 | True |
      | False | CTORSO | False | 2 | False |
      | False | CTORSO | True | 12 | True |
      | True | LTORSO | False | 2 | False |
      | False | HEAD | True | 2 | False |
