# Damage armor 01 - class and armor arithmetic; Damage armor 02 - warning transitions; Damage armor 03 - armor piercing threshold and penalties; Damage armor 04 - critical through armor versus internal roll
Feature: Damage armor
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage armor 01 - class and armor arithmetic
    Given a <unit_class> with hit section <section> armor 20 rear armor 8 and internal 30
    And armor technology <technology> and all incidental critical rolls below eight
    When an ordinary <damage> point hit arrives with rear flag <rear>
    Then section front armor is <front_left> rear armor is <rear_left> and internal is <internal_left>
    Examples:
      | unit_class | section | technology | damage | rear | front_left | rear_left | internal_left |
      | MECH | LTORSO | standard | 7 | False | 13 | 8 | 30 |
      | MECH | LTORSO | standard | 7 | True | 20 | 1 | 30 |
      | MECH | LTORSO | hardened | 7 | True | 20 | 4 | 30 |
      | MECH | LTORSO | standard | 23 | False | 0 | 8 | 27 |
      | MECH | LTORSO | reinforced-internal | 23 | False | 0 | 8 | 28 |
      | MECH | LTORSO | composite-internal | 23 | False | 0 | 8 | 24 |
      | MECH | LARM | standard | 7 | True | 13 | 8 | 30 |
      | GROUND | LSIDE | standard | 7 | True | 13 | 8 | 30 |

  Scenario Outline: Damage armor 02 - warning transitions
    Given armor warnings <enabled> original armor 40 current armor <before> and rear flag <rear>
    When a 1 point hit is applied without penetration criticals
    Then the warning severity is <severity> and warning count is <notices>
    Examples:
      | enabled | before | rear | severity | notices |
      | True | 21 | False | none | 0 |
      | True | 20 | False | low | 1 |
      | True | 11 | False | none | 0 |
      | True | 10 | False | critical | 1 |
      | True | 1 | False | breached | 1 |
      | True | 19 | False | none | 0 |
      | True | 20 | True | low | 1 |
      | False | 20 | True | none | 0 |

  Scenario Outline: Damage armor 03 - armor piercing threshold and penalties
    Given an AC AP hit with original armor 100 armor before <before> hit damage <damage> and weapon <weapon>
    When the armor critical roll is <roll>
    Then the AP critical count is <criticals>
    Examples:
      | before | damage | weapon | roll | criticals |
      | 55 | 5 | AC/20 | 12 | 0 |
      | 54 | 5 | AC/20 | 9 | 1 |
      | 54 | 5 | AC/10 | 10 | 1 |
      | 54 | 5 | AC/5 | 11 | 1 |
      | 54 | 5 | AC/2 | 12 | 1 |
      | 54 | 5 | LightAC/2 | 11 | 0 |
      | 54 | 5 | LightAC/5 | 12 | 1 |
      | 54 | 5 | AC/20 | 11 | 2 |
      | 54 | 55 | AC/20 | 12 | 0 |
      | 54 | 5 | other | 12 | 0 |

  Scenario Outline: Damage armor 04 - critical through armor versus internal roll
    Given a MECH torso with one armor point and six independently crittable nonexplosive slots
    When a two point hit with hit-critical flag True rolls <armor_roll> for armor and <internal_roll> for internals
    Then actual critical slot dispatches total <criticals> and two critical rolls are recorded
    Examples:
      | armor_roll | internal_roll | criticals |
      | 7 | 8 | 1 |
      | 8 | 12 | 1 |
      | 10 | 12 | 2 |
      | 12 | 12 | 3 |
      | 7 | 7 | 0 |
