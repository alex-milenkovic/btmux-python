# Core integration 01 - real consumer paths; Core integration 02 - outside services remain explicit
Feature: Core integration
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core integration 01 - real consumer paths
    Given normal workflow <workflow>
    When the documented commands and clock steps execute
    Then real outcome <outcome> is observed with no duplicate effects
    Examples:
      | workflow | outcome |
      | startup-lock-fire-shutdown | delayed-ready-shot-stopped |
      | knockout-extend-recover | one-late-recovery |
      | stun-twice | one-final-clear |
      | damage-stagger-fall | actual-fall-damage |
      | repair-refill-fire | repaired-mount-spends-bin |
      | seeded-fire-pilot-statistics | shared-stream-and-roll-count |

  Scenario Outline: Core integration 02 - outside services remain explicit
    Given required service <service> is unavailable
    When workflow <workflow> reaches that boundary
    Then the unavailable operation is reported with applied false and available local effects remain
    Examples:
      | service | workflow |
      | persistent-character | startup-player-init |
      | MUX-channels-and-hooks | channel-kill |
      | persistent-XP | successful-pilot-roll |
      | autopilot-gameplay | AUTO-heartbeat |
      | persistent-map-objects | hangar-exit |
