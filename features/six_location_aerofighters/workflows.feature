# Six location fighter workflows 01 - original fighter operations
Feature: Six location fighter workflows
  Background:
    Given independent public CLI sessions using unchanged original templates and the procedures in qa/six_location_aerofighters.py

  Scenario Outline: Six location fighter workflows 01 - original fighter operations
    When public workflow <workflow> runs
    Then the observable result is <result>
    Examples:
      | workflow | result |
      | original-load-save-reload | CHP-W5-six-sections-equipment-and-design-values-preserved |
      | original-takeoff-fly-land | CHP-W5-launches-moves-consumes-fuel-and-lands |
      | original-fire-and-missiles | physical-mount-heat-ammo-recycling-and-six-location-damage-observed |
      | original-combat-damage | depletion-transfer-cockpit-and-engine-outcomes-observed |
      | fighter-bomb-release | six-location-payload-releases-and-impacts-through-shared-events |
      | nonfighter-regression | DS-Union-Cavalry-WVR6R-load-and-scoped-flight-combat-behavior-preserved |
