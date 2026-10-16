# Template catalog audit 01 - pinned inventory accounting; Template catalog audit 02 - complete failure reporting; Template catalog audit 03 - source compatibility limitations
Feature: Template catalog audit
  Background:
    Given an isolated template catalog session with pinned inputs and writable scratch storage

  Scenario Outline: Template catalog audit 01 - pinned inventory accounting
    When the actual pinned catalog is inventoried without parsing filters
    Then declared type <unit_type> has <count> candidates
    Examples:
      | unit_type | count |
      | Mech | 1303 |
      | Vehicle | 235 |
      | AeroFighter | 120 |
      | VTOL | 34 |
      | Battlesuit | 22 |
      | Spheroid_DropShip | 22 |
      | Naval | 7 |
      | Aerodyne_Dropship | 1 |
      | Mechwarrior | 1 |

  Scenario Outline: Template catalog audit 02 - complete failure reporting
    Given a disposable catalog audit fixture contains <fixture>
    When its real per-file audit runs in fresh state
    Then candidates successes failures and ambiguity groups are <candidates> <successes> <failures> and <ambiguities> with outcome <outcome>
    Examples:
      | fixture | candidates | successes | failures | ambiguities | outcome |
      | one-valid | 1 | 1 | 0 | 0 | complete-success |
      | valid-invalid-valid | 3 | 2 | 1 | 0 | complete-with-failures |
      | same-key-two-valid-files | 2 | 2 | 0 | 1 | complete-success |
      | same-key-valid-invalid | 2 | 1 | 1 | 1 | complete-with-failures |
      | unknown-type-and-valid | 2 | 1 | 1 | 0 | complete-with-failures |
      | valid-plus-git-metadata | 1 | 1 | 0 | 0 | complete-success |
      | nested-valid-not-discoverable | 1 | 1 | 0 | 0 | complete-success |

  Scenario Outline: Template catalog audit 03 - source compatibility limitations
    When unchanged design <reference> is attempted through the corrected production loader
    Then failure is classified as <classification> with cause <cause>
    Examples:
      | reference | classification | cause |
      | AS7-DC | unsupported-source-equipment | CL.MediumLaser |
      | Elemental | unsupported-source-equipment | CL.SmallLaser |
      | Uller-D | malformed-range | CRIT_8-0 |
