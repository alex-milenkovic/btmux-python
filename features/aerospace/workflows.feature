# Aerospace workflows 01 - end to end
Feature: Aerospace workflows
  Background:
    Given the documented aerospace CLI with genuine templates real maps and ordinary commands

  Scenario Outline: Aerospace workflows 01 - end to end
    Given independent workflow <workflow> from the aerospace QA suite
    When QA executes the public interface in a fresh subprocess
    Then the observable result is <result>
    Examples:
      | workflow | result |
      | launch-abort-relaunch | correct-event-boundaries-cover-and-live-flight |
      | landing-and-zones | real-zone-gates-and-successful-landing-mine |
      | flight-and-backup | real-vectors-displacement-and-delayed-fuel-consequences |
      | aircraft-periodic-updates | aircraft-heat-spin-and-sensor-window |
      | bomb-list-aim-drop | real-payload-removal-cargo-change-and-delayed-damage |
      | bomb-scatter-and-terrain | source-scatter-last-interception-and-offmap-retention |
      | dropship-exhaust | actual-forest-damage-heat-and-sensor-scramble |
      | bay-entry-and-content-transfer | door-busy-delay-cargo-and-personnel-transfer |
      | bay-exit-and-placement | real-edge-transfer-parity-flight-and-C3-cleanup |
      | turret-control-and-fire | two-gunners-independent-locks-real-shots-and-restoration |
      | bridge-and-preservation | real-bridge-casualties-and-scoped-fuel-VTOL-regressions |
