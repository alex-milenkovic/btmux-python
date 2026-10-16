# Construction editor 01 - target guards; Construction editor 02 - type selection; Construction editor 03 - movement selection; Construction editor 04 - scalar conversion; Construction editor 05 - radio clamping; Construction editor 06 - armor writes and repairs; Construction editor 07 - cargo space
Feature: Construction editor
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction editor 01 - target guards
    Given an editor has template privilege <privilege> allocated data <allocated> and target <target>
    When resetcrits is requested
    Then its outcome is <outcome>
    Examples:
      | privilege | allocated | target | outcome |
      | 0 | 1 | valid | permission-denied |
      | 1 | 0 | valid | three-data-errors |
      | 1 | 1 | unset | set-target-first |
      | 1 | 1 | missing | three-data-errors |
      | 1 | 1 | valid | defaults-set |

  Scenario Outline: Construction editor 02 - type selection
    Given an editor targets a unit whose movement is Track
    When settype receives <text>
    Then type and movement become <unit> and <move>
    Examples:
      | text | unit | move |
      | M | Mech | Biped |
      | Q | Mech | Quad |
      | G | Vehicle | Track |
      | V | VTOL | VTOL |
      | N | Naval | Track |
      | A | AeroFighter | Fly |
      | D | Aerodyne_DropShip | Fly |
      | S | Spheroid_DropShip | Fly |
      | B | Battlesuit | Biped |

  Scenario Outline: Construction editor 03 - movement selection
    Given an editor targets a unit whose movement is Track
    When setmove receives <text>
    Then movement is <move> and notification count is <messages>
    Examples:
      | text | move | messages |
      | Track | Track | 1 |
      | Wheel | Wheel | 1 |
      | Hover | Hover | 1 |
      | Hull | Hull | 1 |
      | VTOL | VTOL | 1 |
      | Quad | Quad | 1 |
      | Biped | Biped | 1 |
      | Sub | Sub | 1 |
      | FLY | None | 2 |
      | FOIL | None | 2 |
      | Frog | None | 1 |
      | Huh | Hull | 1 |
      | Haze | Track | 0 |
      | None | None | 1 |

  Scenario Outline: Construction editor 04 - scalar conversion
    When editor operation <operation> receives <arguments>
    Then its stored value is <stored>
    Examples:
      | operation | arguments | stored |
      | setspeed | 6 | 64.5 |
      | setspeed | 2.5 | 26.875 |
      | setjumpspeed | 3 | 32.25 |
      | setjumpspeed | -1 | -10.75 |
      | settons | 50suffix | 50 |
      | settons | junk | 0 |
      | setheatsinks | 12 | 12 |
      | setlrsrange | 40 | 40 |
      | settacrange | 20 | 20 |
      | setscanrange | 25 | 25 |
      | setradiorange | 80 | 80 |

  Scenario Outline: Construction editor 05 - radio clamping
    Given an editor targets a Clan unit
    When setradio receives <value>
    Then radio level type and range are <level> <type> and <range>
    Examples:
      | value | level | type | range |
      | 0 | 1 | 2 | 64 |
      | 1 | 1 | 2 | 64 |
      | 2 | 2 | 4 | 80 |
      | 3 | 3 | 5 | 100 |
      | 4 | 4 | 24 | 120 |
      | 9 | 5 | 27 | 140 |

  Scenario Outline: Construction editor 06 - armor writes and repairs
    Given a mech center torso has original and current armor20 internal16 rear5
    When editor operation <operation> receives <arguments>
    Then current armor internal rear and original armor internal rear are <a> <i> <r> and <oa> <oi> <orr>
    Examples:
      | operation | arguments | a | i | r | oa | oi | orr |
      | setarmor | CT~30~18~6 | 30 | 18 | 6 | 30 | 18 | 6 |
      | setarmor | CT~-1~18~6 | 20 | 18 | 6 | 20 | 18 | 6 |
      | setarmor | CT~30~-1~6 | 30 | 16 | 6 | 30 | 16 | 6 |
      | setarmor | CT | 20 | 16 | 5 | 20 | 16 | 5 |
      | repair | CT~A~9 | 9 | 16 | 5 | 20 | 16 | 5 |
      | repair | CT~I~4 | 20 | 4 | 5 | 20 | 16 | 5 |
      | repair | CT~R~2 | 20 | 16 | 2 | 20 | 16 | 5 |
      | repair | CT~A | 0 | 16 | 5 | 20 | 16 | 5 |

  Scenario Outline: Construction editor 07 - cargo space
    Given an editor targets a unit with cargospace0 maxton1
    When setcargospace receives <cargo> and <maximum>
    Then accepted is <accepted> stored cargo is <stored> and maxton is <maxton>
    Examples:
      | cargo | maximum | accepted | stored | maxton |
      | 1 | 0 | 1 | 50 | 1 |
      | 2 | 50 | 1 | 100 | 50 |
      | 5000 | 101 | 1 | 250000 | 100 |
      | 5001 | 5 | 0 | 0 | 1 |
      | -1 | 5 | 0 | 0 | 1 |
