# Template catalog workflows 01 - ordinary independent procedures
Feature: Template catalog workflows
  Background:
    Given an isolated template catalog session with pinned inputs and writable scratch storage

  Scenario Outline: Template catalog workflows 01 - ordinary independent procedures
    Given the documented catalog procedure <procedure> has independent file and source expectations
    When it runs through the ordinary public CLI in fresh processes
    Then its complete evidence proves <evidence>
    Examples:
      | procedure | evidence |
      | setup-discover | portable-pinned-setup-list-and-origin |
      | immutable-custom | safe-custom-save-shadow-and-origin-preserving-restore |
      | line-ending-parity | central-LF-CRLF-equivalence-with-rejections |
      | full-catalog | every-raw-candidate-outcome-and-collision |
      | wolverine-jump-combat | real-five-MP-jump-land-fire-and-restore |
      | battlemaster-warhammer | loaded-layouts-motion-front-rear-fire-and-reload |
      | clan-quad | Clan-and-quad-designs-jump-fire-and-reload |
      | other-classes | class-appropriate-motion-fire-and-persistence |
      | jump-boundaries-regressions | shared-C2-boundaries-and-preserved-consumers |
