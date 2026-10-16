# Aerospace landing 01 - landing bounds
# Aerospace landing 02 - terrain and state
# Aerospace landing 03 - zone precedence
# Aerospace landing 04 - check and warning presentation
Feature: Aerospace landing
  Background:
    Given a registered craft with source terrain and a flat six-neighbor landing zone

  Scenario Outline: Aerospace landing 01 - landing bounds
    Given airborne class <class> at floor plus one with desired speed <desired> actual speed <speed> and vertical <vertical>
    When land is requested
    Then the landing result is <result>
    Examples:
      | class | desired | speed | vertical | result |
      | VTOL | 0 | 0 | 0 | landed |
      | VTOL | 15.99 | 0 | 0 | landed |
      | VTOL | 16 | 0 | 0 | horizontal-too-fast |
      | VTOL | 10.9 | 0 | 10.9 | landed |
      | VTOL | 11 | 0 | 11 | vertical-too-fast |
      | VTOL | 60 | 0 | -60 | landed |
      | VTOL | 60.1 | 0 | -60.1 | vertical-too-fast |
      | AERO | 32.25 | 32.25 | 0 | landed |
      | AERO | 32 | 32 | 0 | landed |
      | AERO | 31.99 | 32 | 0 | horizontal-too-slow |
      | AERO | 999.9 | 32.25 | 0 | landed |
      | AERO | 1000 | 32.25 | 0 | horizontal-too-fast |
      | DS | 50 | 32.25 | -25 | landed |
      | DS | 50 | 32.25 | -25.1 | vertical-too-fast |
      | SPHEROID_DS | 40.99 | 0 | 0 | landed |
      | SPHEROID_DS | 41 | 0 | 0 | horizontal-too-fast |
      | SPHEROID_DS | 40 | 0 | -40 | landed |

  Scenario Outline: Aerospace landing 02 - terrain and state
    Given landing fixture <fixture>
    When land is requested
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | VTOL;building | landed |
      | AERO;building | terrain-refusal |
      | DS;rough;blzmapmode1 | terrain-refusal |
      | VTOL;Z2;floor0 | too-high |
      | AERO;actual31.99;desired40;start_fz0 | falling-not-landing |
      | AERO;actual31.99;desired40;start_fz1 | climbing-not-landing |
      | AERO;desired40;speed40;stopped | landed |
      | VTOL;fuel0 | fuel-refusal |
      | VTOL;fuel0;fusion-free | landed |
      | DS;landed;no-takeoff | already-landed |
      | VTOL;success;desired10;angle30;vectors-nonzero | Z-floor;FZ-floor;vectors-and-actual-speeds0;desired10;angle30;mine-and-script |

  Scenario Outline: Aerospace landing 03 - zone precedence
    Given zone fixture <fixture>
    When checklz inspects the current hex
    Then the zone result is <result>
    Examples:
      | fixture | result |
      | grass;flat-six;mode0 | good |
      | road;flat-six;mode0 | good |
      | forest;uneven;blocked;mode0 | Improper-terrain |
      | grass;one-neighbor-different;mode0 | Uneven-ground |
      | grass;map-edge;mode0 | Uneven-ground |
      | forest;uneven;mode1 | good |
      | forest;uneven;blocked;mode1 | Blocked-landing-zone |
      | grass;block-team1;unit-team1 | good |
      | grass;block-team0;unit-team1 | Blocked-landing-zone |
      | grass;block-distance-equal-radius | Blocked-landing-zone |
      | grass;block-distance-greater-radius | good |

  Scenario Outline: Aerospace landing 04 - check and warning presentation
    Given zone fixture <fixture>
    When the source check or warning operation executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | checklz;two-coordinates;range-equals-tac | zone-reported |
      | checklz;two-coordinates;range-exceeds-tac | Out-of-range |
      | checklz;observer;range-exceeds-tac | zone-reported |
      | checklz;one-argument | Invalid-number-of-parameters |
      | checklz;stopped | reactor-off |
      | warning;blocked;severity1 | red;CLIMB-UP-NOW |
      | warning;blocked;severity0 | yellow;No-further-descent |
      | warning;blocked;severity-1 | uncolored;Please-do-not-even-consider |
      | warning;valid;severity1 | silent |
