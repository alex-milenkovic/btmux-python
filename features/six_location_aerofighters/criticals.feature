# Six location fighter criticals 01 - armor gates
# Six location fighter criticals 02 - gate precedence
# Six location fighter criticals 03 - disabled critical gates
# Six location fighter criticals 04 - direct effects
# Six location fighter criticals 05 - deferred critical counts
# Six location fighter criticals 06 - component behavior
# Six location fighter criticals 07 - sequential missile groups
Feature: Six location fighter criticals
  Background:
    Given a fighter using historical critical rules with vcrit 2 moving type Fly and a conscious pilot unless the case overrides it

  Scenario Outline: Six location fighter criticals 01 - armor gates
    Given armor <armor> original armor <original> threshold <threshold> and chance <chance>
    When the fighter critical gate runs
    Then gate <result> consumes <draw>
    Examples:
      | armor | original | threshold | chance | result | draw |
      | 89 | 100 | 90 | 6 | true | none |
      | 90 | 100 | 90 | 6 | true | 1..11 |
      | 90 | 100 | 90 | 5 | false | 1..11 |
      | 94 | 100 | 90 | 6 | true | 1..11 |
      | 95 | 100 | 90 | 6 | false | none |
      | 99 | 100 | 90 | 6 | false | none |
      | 100 | 100 | 90 | 23 | true | 1..71 |
      | 100 | 100 | 90 | 22 | false | 1..71 |
      | 98 | 100 | 99 | 6 | true | none |
      | 99 | 100 | 99 | 6 | true | 1..11 |
      | 99 | 100 | 99 | 5 | false | 1..11 |
      | 100 | 100 | 99 | 23 | true | 1..71 |
      | 24 | 24 | 90 | 22 | false | 1..71 |
      | 23 | 24 | 90 | 6 | false | none |
      | 22 | 24 | 90 | 6 | true | 1..11 |
      | 21 | 24 | 90 | 5 | true | none |
      | 0 | 0 | 90 | 6 | true | none |

  Scenario Outline: Six location fighter criticals 02 - gate precedence
    Given fighter gate overrides <overrides>
    When the critical gate runs on zero original armor
    Then the gate is <result> without random draws
    Examples:
      | overrides | result |
      | critproof | false |
      | Move_NONE | false |
      | vcrit0 | true |
      | vcrit1 | true |

  Scenario Outline: Six location fighter criticals 03 - disabled critical gates
    Given positive original armor and <overrides>
    When the fighter critical gate runs
    Then the gate is false without random draws
    Examples:
      | overrides |
      | critproof |
      | Move_NONE |
      | vcrit0 |
      | vcrit1 |

  Scenario Outline: Six location fighter criticals 04 - direct effects
    Given the direct fighter effect case <fixture>
    When the source table or named helper executes
    Then the equipment or control observation is <observation>
    Examples:
      | fixture | observation |
      | one-global-weapon-only-weapon-loss | no-candidate-no-selection-draw |
      | two-Nose-medium-lasers-select-ordinal1 | global-mount0-destroyed-global-mount1-retained |
      | second-global-mount-recycling-selected | no-destruction |
      | second-global-mount-destroyed-selected | no-destruction |
      | first-of-same-type-destroyed-second-ready-selected | first-redestroyed-second-retained |
      | sink90-with-aggregate25-no-local-sink | sinks25-no-slot-change |
      | sink90-with-two-local-single-sinks | first-sink-destroyed-capacity-minus2 |
      | sink90-first-sink-destroyed-second-live | first-redestroyed-capacity-minus2-second-live |
      | rear3-airborne | spinning-start-time-set |
      | rear11-landed | no-spin |
      | rear3-already-spinning | start-time-preserved |
      | rear11-destroyed | no-spin |
      | front10-live-bomb | payload-retained-no-explosion |

  Scenario Outline: Six location fighter criticals 05 - deferred critical counts
    Given Engine armor 18 original 20 and rear roll 2 with chance 6 passing threshold 90
    When armor damage 1 runs with critical count roll <roll>
    Then requested Engine slot criticals are <count> after armor becomes 17
    Examples:
      | roll | count |
      | 2 | 0 |
      | 7 | 0 |
      | 8 | 1 |
      | 9 | 1 |
      | 10 | 2 |
      | 11 | 2 |
      | 12 | 3 |

  Scenario Outline: Six location fighter criticals 06 - component behavior
    Given the fighter component case <fixture>
    When its shared critical path resolves
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | Cockpit-LifeSupport | life-support-destroyed |
      | Cockpit-Sensors-first-ranges80-40-20-BTH0 | ranges40-20-10-BTH2 |
      | Cockpit-Sensors-second | ranges0-0-0-BTH75 |
      | Cockpit-Cockpit-IC-pilot | craft-destroyed-pilot-cleared-local-contents-killed |
      | single-HeatSink-capacity25 | capacity24-slot-destroyed |
      | Engine-component-engineheat0 | engineheat5-no-thrust-zeroing |
      | Engine-component-engineheat5 | engineheat10-no-thrust-zeroing |
      | Engine-component-engineheat10 | engineheat15-craft-destroyed |
      | no-eligible-slots | no-draw-no-critical-transfer |
      | eligible-slot-with-destroyed-and-damaged-neighbors | only-eligible-slot-selected |
      | combat-safe | no-slot-effect |
      | critproof | no-slot-effect |
      | vcrit0 | no-slot-effect |

  Scenario Outline: Six location fighter criticals 07 - sequential missile groups
    Given CHP-W5 Nose armor 24 with only global mount zero installed and full-armor chance miss
    When all <family> damage groups hit Nose roll 3 in sequence
    Then pre-hit armors are <before> final armor is <after> and gate draw domains are <draws>
    Examples:
      | family | before | after | draws |
      | LRM15-three-groups-of5 | 24-19-14 | 9 | 1..71-only |
      | SRM-two-groups-of2 | 24-22 | 20 | 1..71-then-1..11 |
