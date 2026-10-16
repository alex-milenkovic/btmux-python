# Pilot subsystem workflows 01 - ordinary independent procedures
Feature: Pilot subsystem workflows
  Background:
    Given an isolated public CLI process with independently derived source inputs and writable scratch storage

  Scenario Outline: Pilot subsystem workflows 01 - ordinary independent procedures
    Given documented procedure <procedure> has independent source expectations
    When the complete ordinary workflow executes through public commands and clocks
    Then evidence proves <evidence>
    Examples:
      | procedure | evidence |
      | character-roundtrip | durable-skills-advantages-source-text-fresh-reload |
      | skills-and-rolls | named-BTH-actual-fire-PSR-dice-accounting |
      | xp-progression | ordinary-awards-threshold-change-persistence |
      | conscious-injuries | IC-nonIC-damage-initial-recovery-death |
      | personal-equipment | real-MW-initialization-armor-and-firing |
      | manual-ejection | created-MW-control-cockpit-consumption-source-death |
      | pilot-exit-entry | passenger-ground-airborne-disembark-embark |
      | pickup-and-discard | real-occupant-transfer-capture-clock-disposal |
      | carrier-roundtrip | capacity-tow-shutdown-exit-startup-fall |
      | swarm-and-host | ordinary-swarm-host-motion-fire-detach |
      | leg-attacks | source-limb-choice-critical-fallthrough-damage |
      | hiding-and-jettison | clock-LOS-cancel-packs-real-fire |
      | automatic-escape | reactor-and-last-member-real-MW-escape |
      | shared-regressions | accepted-Core-Damage-Construction-Catalog-Maps-consumers |
