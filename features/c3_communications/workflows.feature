# C3 communications workflows 01 - independent end to end procedures
Feature: C3 communications workflows
  Background:
    Given the documented public CLI with real commands clocks templates and local character inboxes

  Scenario Outline: C3 communications workflows 01 - independent end to end procedures
    Given procedure <procedure> from the QA specification
    When QA executes the user-visible workflow in a fresh process
    Then required observable outcome is <outcome>
    Examples:
      | procedure | outcome |
      | c3-formation-and-fire | joined-network-changes-real-shot-range |
      | c3i-membership-and-loss | six-unit-capacity-and-real-critical-detachment |
      | network-availability | ECM-shutdown-and-unconscious-distinguished |
      | network-reports-and-messages | ordered-masked-reports-and-recipient-inboxes |
      | channel-configuration | parsed-settings-list-and-transmission-agree |
      | radio-relay | multihop-digital-delivery-and-route-bearing |
      | analog-scan-and-XP | retuning-scrambling-and-real-CommXP |
      | channel-mines-and-recovery | actual-mine-detonation-and-restored-radio |
      | notification-audiences | occupant-pilot-turret-and-suppression-cases |
      | visibility-broadcasts | ordinary-fire-and-movement-observer-delivery |
      | map-transfer-and-pilot-radio | detached-networks-and-emergency-MW-channel |
      | presentation-and-boundaries | all-source-display-modes-and-explicit-external-effects |
