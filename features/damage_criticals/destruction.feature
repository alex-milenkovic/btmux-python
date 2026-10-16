# Damage destruction 01 - class-specific section loss; Damage destruction 02 - side torso recursion; Damage destruction 03 - VTOL fall is timed; Damage destruction 04 - explosion and cleanup; Damage destruction 05 - non-MECH parts do not use MECH engine ladder; Damage destruction 06 - aero armor exhaustion equality
Feature: Damage destruction
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage destruction 01 - class-specific section loss
    Given a live <unit_class> with populated section <section> containing a weapon and other live sections
    When that section is destroyed by enemy damage
    Then unit destroyed is <destroyed> pending fall is <fall> and the section weapon is unusable
    Examples:
      | unit_class | section | destroyed | fall |
      | MECH | LARM | False | False |
      | MECH | CTORSO | True | False |
      | GROUND | TURRET | False | False |
      | GROUND | LSIDE | True | False |
      | airborne-VTOL | ROTOR | False | True |
      | landed-VTOL | ROTOR | False | False |
      | VTOL | FSIDE | True | False |
      | AERO | COCKPIT | True | False |

  Scenario Outline: Damage destruction 02 - side torso recursion
    Given a <unit_class> with live right-side sections
    When section index three is destroyed
    Then corresponding arm index one is destroyed <arm>
    Examples:
      | unit_class | arm |
      | MECH | True |
      | GROUND | False |

  Scenario Outline: Damage destruction 03 - VTOL fall is timed
    Given an airborne VTOL at height twenty with no usable thrust after rotor destruction
    When time advances to <time> ticks after the critical
    Then height is <height> and the unit is not instantly destroyed
    Examples:
      | time | height |
      | 0 | 20 |
      | 2 | 20 |
      | 3 | 18 |
      | 6 | 15 |

  Scenario: Damage destruction 04 - explosion and cleanup
    Given a started ICE ground vehicle with a target pending movement events active ECM and live original sections
    When a fuel explosion critical occurs
    Then kill reason is FUELTANK all original-live sections are destroyed and speeds are zero
    And target pilot active ECM and obsolete movement events are cleared

  Scenario: Damage destruction 05 - non-MECH parts do not use MECH engine ladder
    Given a ground turret with an engine special slot and engine heat zero
    When the turret section is destroyed
    Then its slot is destroyed engine heat remains zero and the vehicle survives

  Scenario Outline: Damage destruction 06 - aero armor exhaustion equality
    Given a landed AERO wing with armor 5 and other surviving sections
    When ordinary wing damage is <damage>
    Then wing armor is <armor> and wing weapon is unusable <lost>
    Examples:
      | damage | armor | lost |
      | 4 | 1 | False |
      | 5 | 0 | False |
      | 6 | 0 | False |
