# Aerospace updates 01 - paid and free fuel
# Aerospace updates 02 - aircraft dispatch timing
# Aerospace updates 03 - spin and bridge effects
# Aerospace updates 04 - preserved fuel callers
Feature: Aerospace updates
  Background:
    Given a registered craft with real pilot heat sensor event and personnel services

  Scenario Outline: Aerospace updates 01 - paid and free fuel
    Given fuel fixture <fixture>
    When one fuel check executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | AERO;fuel1;speed20;max60 | fuel0;continue |
      | AERO;fuel0;speed20;max60;airborne | fuel-1;speeds0;fall-due3;stop |
      | AERO;fuel-1;speed20;max60 | fuel-1;stop;no-new-fall |
      | DS;fuel0;speed20;max60 | fuel-1;backup-notice;continue |
      | DS;fuel-1;speed20;max60 | fuel-1;silent;continue |
      | AERO;fuel5;speed125;max60;Z99 | fuel3;continue |
      | AERO;fuel5;speed125;max60;Z100 | fuel4;continue |
      | AERO;fuel0;speed0;vertical0;draw0 | fuel0;continue;no-fall |
      | AERO;fuel5;speed0;vertical0;draw1 | fuel4;continue |
      | AERO;fuel5;speed10.75;vertical0 | fuel4;no-low-motion-draw |
      | AERO;fuel5;speed0;vertical21.5 | fuel4;no-low-motion-draw |
      | VTOL;fuel0;fusion-free | fuel0;no-draw;continue |
      | VTOL;fuel0;stopped | fuel0;no-draw;continue |
      | VTOL;fuel0;landed;speed20 | fuel-1;speeds0;no-fall;stop |

  Scenario Outline: Aerospace updates 02 - aircraft dispatch timing
    Given aircraft update fixture <fixture>
    When the aircraft dispatcher runs at simulation time <now>
    Then the observation is <observation>
    Examples:
      | fixture | now | observation |
      | destroyed;FIRED | 4 | FIRED-cleared;no-other-updates |
      | started;not-spinning | 0 | pilot-and-heat-only |
      | started;not-spinning | 2 | pilot-and-heat-only |
      | started;not-spinning | 3 | pilot-heat-visibility-ECM-TAG-light |
      | started;not-spinning | 15 | pilot-and-heat-only |
      | stopped;plus_heat0.05 | 3 | heat-ECM-TAG-light;no-pilot-or-visibility |
      | stopped;plus_heat0 | 3 | ECM-TAG-light-only |
      | stopped;unconscious | 3 | pilot-ECM-TAG-light |
      | started;spinning;landed | 15 | pilot-and-heat-only |
      | started;spinning;start_spin0;PSR-success | 15 | modifier7;spin-cleared;remaining-updates |
      | started;spinning;start_spin0;PSR-fail | 16 | modifier7;spin-retained;remaining-updates |
      | started;spinning;start_spin0 | 18 | no-recovery-roll;remaining-updates |

  Scenario Outline: Aerospace updates 03 - spin and bridge effects
    Given effect fixture <fixture>
    When the named production effect executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | control;airborne;now12 | spin-set;start_spin12;notices |
      | control;already-spinning;start_spin5;now12 | unchanged;silent |
      | control;landed | unchanged;silent |
      | control;destroyed | unchanged;silent |
      | bridge;IC;two-ordinary-occupants;wizard | ordinary-occupants-dead-and-afterlife;wizard-retained |
      | bridge;OOC | no-deaths |
      | bridge;destroyed;IC | no-deaths-or-notice |

  Scenario Outline: Aerospace updates 04 - preserved fuel callers
    Given fuel fixture <fixture>
    When ordinary ticks and events execute
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | idle-airborne-AERO;heartbeat;fuel1;draw1 | fuel0 |
      | idle-airborne-VTOL;heartbeat;fuel1;draw1 | fuel0 |
      | idle-airborne-DS;heartbeat;fuel1 | fuel1;no-idle-check |
      | moving-VTOL;fuel0 | movement-stops;fall-event |
      | moving-AERO;fuel0 | aero-chain-stops;fall-event |
      | moving-DS;fuel0 | backup;reduced-wanted-vector;chain-continues |
