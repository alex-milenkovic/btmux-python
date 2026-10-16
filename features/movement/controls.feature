# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:43:36.961834932Z","feature_name":"Movement controls","feature_path":"features/movement/controls.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:a46a01688d96a6ee4545b158f6726b41cba6151d087ce90f11fd87f1ec8790ff","scenarios":[]}
# acceptance-mutation-manifest-end

# Movement controls 01 - speed aliases and clamping; Movement controls 02 - heading and lateral state; Movement controls 03 - replace pending lateral; Movement controls 04 - vertical envelope; Movement controls 05 - ETA display
Feature: Movement controls
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Movement controls 01 - speed aliases and clamping
    Given maximum speed 64.5 KPH and requested speed text <request>
    When the pilot uses the speed command
    Then desired speed is <desired> KPH and actual speed remains 0 KPH
    Examples:
      | request | desired |
      | walk | 43 |
      | run | 64.5 |
      | cruise | 43 |
      | flank | 64.5 |
      | stop | 0 |
      | back | -43 |
      | 100 | 64.5 |
      | -100 | -43 |
      | 12.5 | 12.5 |
      | nonsense | 0 |

  Scenario Outline: Movement controls 02 - heading and lateral state
    When the pilot requests heading <heading> and lateral <lateral> then advances 6 seconds
    Then desired facing is <desired> and lateral offset is <offset> with description <description>
    Examples:
      | heading | lateral | desired | offset | description |
      | 370 | fl | 10 | 300 | Front/Left |
      | -10 | fr | 350 | 60 | Front/Right |
      | 90 | rl | 90 | 240 | Rear/Left |
      | 180 | rr | 180 | 120 | Rear/Right |
      | 360 | - | 0 | 0 | None |

  Scenario Outline: Movement controls 03 - replace pending lateral
    Given lateral offset 0 degrees and a pending fl request made at second 0
    When at second 2 the pilot requests lateral <request> and advances to second <tick>
    Then lateral offset is <offset> and changing lateral is <pending>
    Examples:
      | request | tick | offset | pending |
      | - | 8 | 0 | False |
      | fr | 6 | 0 | True |
      | fr | 8 | 60 | False |
      | fl | 6 | 0 | True |
      | fl | 8 | 300 | False |

  Scenario Outline: Movement controls 04 - vertical envelope
    Given an airborne VTOL with maximum speed 53.75 KPH and desired horizontal speed 32.25 KPH
    When the pilot requests vertical speed <request> KPH
    Then the command is <outcome> and vertical speed is <vertical> KPH
    Examples:
      | request | outcome | vertical |
      | 43 | ACCEPTED | 43 |
      | -43 | ACCEPTED | -43 |
      | 43.01 | REJECTED | 0 |
      | -43.01 | REJECTED | 0 |

  Scenario Outline: Movement controls 05 - ETA display
    Given a hex target 4 hex ranges away and actual speed <speed> KPH
    When the pilot requests ETA for the default hex target
    Then ETA display contains <eta>
    Examples:
      | speed | eta |
      | 43 | 00:01 |
      | -43 | 00:01 |
      | 0 | Never, mech not moving. |
      | 0.09 | Never, mech not moving. |
