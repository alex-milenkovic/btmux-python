# Aerospace bays 01 - bay configuration
# Aerospace bays 02 - door mapping
# Aerospace bays 03 - entry gates
# Aerospace bays 04 - callback rechecks
# Aerospace bays 05 - bay exit
Feature: Aerospace bays
  Background:
    Given real dropship door criticals bay maps occupants and map transitions

  Scenario Outline: Aerospace bays 01 - bay configuration
    Given bay setup fixture <fixture>
    When createbays executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | four-valid-map-arguments | four-bays;each-parent-set |
      | no-arguments;old-four-bays | all-slots-minus1;old-map-parents-retained |
      | one-valid-map-argument;old-four-bays | first-assigned;trailing-minus1 |
      | five-map-arguments | invalid-count;unchanged |
      | valid-map-then-invalid;old-four-bays | first-assigned-and-parent-set;remaining-old-slots-retained |
      | non-map-first-argument | argument-not-map;unchanged |

  Scenario Outline: Aerospace bays 02 - door mapping
    Given door fixture <fixture>
    When bay number direction adjacency and openness are queried
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | NOSE-door;AFT-door | nose-bay0;aft-bay1;other-dirs-minus1 |
      | NOSE-two-doors;AFT-door | nose-bay0;aft-bay1 |
      | NOSE-destroyed-mechdoor;AFT-live-mechdoor | nose-bay0-closed;aft-bay1-open |
      | NOSE-disabled-mechdoor;MECH | bay0-open |
      | NOSE-aerodoor;AERO | bay0-open |
      | NOSE-aerodoor;VTOL | bay0-closed |
      | DS10,10;facing0;NOSE-door;seer10,9 | adjacent-bay0 |
      | DS11,10;facing60;NOSE-door;seer12,9 | adjacent-bay0 |
      | DS10,10;facing29;NOSE-door;seer10,9 | adjacent-bay0 |
      | DS10,10;facing30;NOSE-door;seer11,10 | adjacent-bay0 |

  Scenario Outline: Aerospace bays 03 - entry gates
    Given entry fixture <fixture>
    When enterbay executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | valid-MECH-adjacent | entry-due12 |
      | no-argument;two-landed-matching-DS | ambiguous;no-event |
      | no-argument;no-matching-DS | no-bay;no-event |
      | two-arguments | invalid-count;no-event |
      | VTOL;fuel0;fusion-free | fuel-refusal |
      | MECH;jumping | mid-jump-refusal |
      | MECH;standing | stand-first-refusal |
      | MECH;OOD | mid-flight-refusal |
      | DS;carrier-tech;matching-aerodoor | too-large |
      | DS;no-carrier-tech | craft-cannot-enter |
      | MECH;door-destroyed | door-jammed |
      | MECH;relative-speed10.75 | entry-due12 |
      | MECH;relative-speed10.76 | speed-difference-refusal |
      | MECH;relative-vertical10 | entry-due12 |
      | MECH;relative-vertical10.1 | vertical-difference-refusal |
      | MECH;different-Z | elevation-refusal |
      | biped;legless | without-legs-refusal |
      | lock-denied;FAIL-custom | custom-failure;no-event |
      | same-bay-pending-other-unit | door-busy |
      | different-bay-pending-other-unit | entry-due12 |
      | explicit-target-airborne;matching-door-and-elevation | entry-due12 |

  Scenario Outline: Aerospace bays 04 - callback rechecks
    Given a queued entry changes by <transition>
    When the clock reaches 12 seconds
    Then the observation is <observation>
    Examples:
      | transition | observation |
      | none;carried-unit-present | unit-and-cargo-in-bay-at5,5;locations-and-membership-updated |
      | unit-shuts-down | no-transfer |
      | unit-unconscious | no-transfer |
      | unit-speed12;maximum60 | no-transfer |
      | unit-speed11.99;maximum60 | transfer |
      | unit-speed1;maximum10 | transfer |
      | door-destroyed-after-request | transfer |
      | lock-denied-after-request | transfer |
      | unit-moves-to-other-bay-neighbor | transfer-to-current-bay |
      | unit-moves-away | no-transfer |
      | MW-enters-OOC-bay | contents-moved;shell-disposal-due10 |
      | enemy-swarmer-attached | swarmer-detached-before-transfer |

  Scenario Outline: Aerospace bays 05 - bay exit
    Given exit fixture <fixture>
    When the unit crosses the bay map edge
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | landed-DS;ground-unit;NOSE-door;DS10,10;facing0 | parent-map10,9;Z-and-elev-from-parent;ground-FZ-retained |
      | landed-DS;ground-unit;NOSE-door;DS11,10;facing60 | parent-map12,9 |
      | landed-DS;NOSE-door;DS0,0;facing0 | placement-clamped0,0 |
      | airborne-DS;ground-unit | ship-airborne-refusal |
      | airborne-DS;VTOL;matching-mechdoor;carried-unit | flyer-Z-parent-plus1;cargo-Z-parent;move-event-stopped |
      | door-destroyed | door-jammed |
      | parent-zombie | imprudent-refusal |
      | parent-missing | invalid-parent-refusal |
      | IC;pilot-outside-unit | transfer;intruder-alarm;real-shutdown |
      | formed-C3-network;successful-exit | old-peers-detached;owner-network-cleared |
