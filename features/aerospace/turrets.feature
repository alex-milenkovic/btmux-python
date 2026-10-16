# Aerospace turrets 01 - turret lifecycle
# Aerospace turrets 02 - active command guards
# Aerospace turrets 03 - all active delegates
# Aerospace turrets 04 - context isolation
# Aerospace turrets 05 - inactive TIC bodies
Feature: Aerospace turrets
  Background:
    Given an OOC dropship with two real turret rooms distinct connected gunners and a separate parent pilot

  Scenario Outline: Aerospace turrets 01 - turret lifecycle
    Given turret fixture <fixture>
    When the lifecycle command executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | allocate;key40;preexisting-gunner7;targz9 | id40;targetXY-minus1;gunner7;targz9 |
      | free-selector | no-body-effect |
      | initialize;old-gunner-connected-same-room | must-leave-or-disconnect |
      | initialize;old-gunner-disconnected | new-gunner;room-notice |
      | initialize;old-gunner-other-room | new-gunner;room-notice |
      | initialize;same-gunner | grap-firmer-notice;unchanged |
      | deinitialize;registered-gunner | gunner-minus1;room-notice |
      | deinitialize;other-caller | not-gunner-refusal |
      | initialize;invalid-parent | unknown-parent-refusal |

  Scenario Outline: Aerospace turrets 02 - active command guards
    Given turret fixture <fixture>
    When RANGE executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | parent-not-mech | unknown-parent-refusal |
      | gunner-minus1 | not-initialized-refusal |
      | caller-not-gunner | not-registered-gunner-refusal |
      | gunner-is-parent-pilot | pilot-and-gun-refusal |
      | authorized-gunner;valid-target | real-range;parent-context-restored |

  Scenario Outline: Aerospace turrets 03 - all active delegates
    Given an authorized turret has its own target distinct from the parent
    When turret command <command> executes through the real command service
    Then the observation is <observation>
    Examples:
      | command | observation |
      | BEARING | turret-target-bearing |
      | ETA | turret-target-ETA |
      | FINDCENTER | parent-position-center;no-overrides |
      | FIRE | real-shot-and-recycle-on-parent-mount |
      | LOCK | turret-target-updated;parent-target-retained |
      | LRS | actual-long-range-map |
      | NAVIGATE | actual-surrounding-hex-map |
      | RANGE | turret-target-range |
      | SIGHT | actual-gunner-BTH;no-shot |
      | TACTICAL | actual-tactical-map |
      | CONTACTS | actual-parent-sensor-contacts |
      | CRITSTATUS | actual-parent-critical-slots |
      | REPORT | turret-target-report |
      | SCAN | turret-target-scan |
      | STATUS | actual-parent-status-and-weapons |
      | WEAPONSPECS | actual-parent-weapon-specifications |

  Scenario Outline: Aerospace turrets 04 - context isolation
    Given turret fixture <fixture>
    When the turret action returns
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | turretA-lock-BB;parent-lock-AA | A-target-BB;parent-AA;no-LOCK-event |
      | turretA-hex-lock;parent-unit-lock | A-XYZ-and-lockmode-updated;parent-entire-context-restored |
      | turretA-fire;IC-wizard-gunner-skill2;parent-pilot-skill7 | BTH-uses-gunner2;real-effects-persist;parent-status-restored |
      | turretA-fire-invalid-target | refusal;both-overrides0;parent-context-restored |
      | turretA-fire-then-turretB-same-mount | second-shot-recycle-refusal;B-lock-retained |
      | turretA-fire-then-parent-fire-after-recycle | parent-uses-own-lock-and-pilot;no-leaked-override |
      | turret-arcs-exclude-target;parent-unusable-arcs-set | arc-control-refusal |
      | fire;parent-and-turret-room-occupants | source-audiences-receive-once;real-shot-count1 |
      | IC-nonwizard-gunner-fire | pilot-only-refusal;parent-and-overrides-restored |
      | diagnostic-delegate-error | exception-reported;overrides-cleared;parent-context-restored |

  Scenario Outline: Aerospace turrets 05 - inactive TIC bodies
    Given uninitialized turret with parent missing receives <command>
    When the registered inactive command executes
    Then the observation is silent with no state or shot change
    Examples:
      | command |
      | ADDTIC |
      | DELTIC |
      | LISTTIC |
      | CLEARTIC |
      | FIRETIC |
