# Maps integration 01 - ordinary environment workflows; Maps integration 02 - explicit unresolved dependencies
Feature: Maps integration
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps integration 01 - ordinary environment workflows
    Given the named ordinary workflow <workflow> starts from its documented fresh fixture
    When only its setup commands gameplay commands and clock advances are executed
    Then the independently observable result is <result>
    Examples:
      | workflow | result |
      | map-text-reload | hexes-and-source-trailer-rules |
      | membership-transfer | unique-local-membership-and-conditions |
      | weapon-forest-fire | timed-spread-smoke-and-restoration |
      | building-hit-repair | CF-damage-regeneration-and-scan |
      | building-destroy | CF-zero-no-auto-rebuild |
      | hangar-links | real-local-exit-resolution |
      | conditions-breach | applied-local-disable-and-repair |

  Scenario Outline: Maps integration 02 - explicit unresolved dependencies
    Given a diagnostic attempt requires unavailable service <service>
    When the dependency has no supplied implementation or approved source mapping
    Then it is reported blocked with applied false and no fabricated success
    Examples:
      | service |
      | MUX-teleport |
      | occupant-enumeration |
      | AUTO-gameplay |
      | mine-trigger-script |
