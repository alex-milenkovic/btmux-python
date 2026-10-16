# Construction integration 01 - ordinary workflows; Construction integration 02 - ordinary mixed mode persistence
Feature: Construction integration
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction integration 01 - ordinary workflows
    Given the documented ordinary construction workflow <workflow> has explicit files commands and expected state
    When the workflow runs through a fresh CLI process
    Then its public evidence must show <evidence>
    Examples:
      | workflow | evidence |
      | modern-load-fire | named-file-load-correct-mounts-ammo-damage-heat-and-recycle |
      | edit-save-reload | ordinary-edits-persist-original-layout-and-derived-inventory |
      | restore-isolation | damaged-live-unit-restored-with-immutable-independent-baselines |
      | legacy-load-save | numeric-source-identity-current-armor-and-documented-format-losses |
      | catalog-discovery | sorted-forms-exact-wildcard-cursors-brands-and-source-IDs |
      | validation-weight | internal-correction-damage-preservation-and-design-current-weight |
      | failed-load | source-reset-partial-writes-inspectable-errors-and-no-stale-mounts |
      | multi-class | aero-vehicle-quad-suit-layouts-load-and-edit |
      | cache-directory | one-level-discovery-case-limits-stale-cache-and-invalidation |
      | shared-consumers | Core-repair-aliases-Combat-Streak-and-Maps-weather-bit-regressions |
      | privilege-editor | session-target-permission-guards-and-independent-targets |

  Scenario Outline: Construction integration 02 - ordinary mixed mode persistence
    Given an ordinary editor saves a template with <modes>
    When a fresh process loads the saved file and fires using its loaded ammunition
    Then both source masks persist and the ordinary shot uses <behavior>
    Examples:
      | modes | behavior |
      | Halfton/BAR/LBX/Cluster | half-bin-LBX |
      | RearMount/BAR/Precision | rear-precision |
