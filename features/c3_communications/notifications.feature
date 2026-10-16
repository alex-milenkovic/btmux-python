# Communications audiences 01 - notification gates
# Communications audiences 02 - map and limited broadcasts
# Communications audiences 03 - LOS and hex expansion
# Communications audiences 04 - real fire broadcasts
# Communications audiences 05 - common command checks
Feature: Communications audiences
  Background:
    Given real registered units local personnel locations and per-recipient inboxes

  Scenario Outline: Communications audiences 01 - notification gates
    Given notification type <type> and state <state>
    When the message hello is emitted
    Then the observation is <observation>
    Examples:
      | type | state | observation |
      | ALL | healthy-stopped-pilot-and-passenger | both-occupants |
      | STARTED | healthy-stopped-pilot-and-passenger | none |
      | PILOT | healthy-stopped-pilot-inside | pilot-only |
      | PILOT | pilot-outside-passenger-inside | passenger-only-fallback |
      | PILOT | destroyed-pilot-inside | pilot-only |
      | ALL | destroyed-started | none |
      | STARTED | destroyed-started | occupants |
      | ALL | unconscious | none |
      | PILOT | blinded | none |
      | STARTED | negative-ID | none |
      | ALL | arc-override-two-turrets | unit-and-both-turret-contents |
      | ALL | no-arc-override-two-turrets | unit-contents-only |
      | PRINTF | formatted-value17 | same-gates-and-hello17 |

  Scenario Outline: Communications audiences 02 - map and limited broadcasts
    Given broadcast fixture <fixture>
    When map or range broadcast executes
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | map-A-started-B-stopped | A-only-inbox |
      | mech-source-A-target-B-observers-C,D | C,D-inboxes |
      | mech-source-A-no-target-observers-B,C | B,C-inboxes |
      | 2D-radius5-unit-distance5-Z10 | count1-and-delivery |
      | 3D-radius5-unit-XY0-Z6-scaled | count0 |
      | 2D-radius5-unit-distance5.01 | count0 |
      | 3D-radius5-unit-distance5-unconscious | count1-no-delivery |
      | 2D-radius5-stopped-and-started-inside | count2-one-delivery |
      | debug-C3-default | no-output-or-external-request |

  Scenario Outline: Communications audiences 03 - LOS and hex expansion
    Given broadcast state <state>
    When the source broadcast executes
    Then the observation is <observation>
    Examples:
      | state | observation |
      | single-visible-AtlasAB-same-team-message-moves | Atlas [ab] moves |
      | single-visible-AtlasAB-enemy-message-apostrophe-s-arm | Atlas [AB]'s arm |
      | single-ordinary-visible-NB-unseen | something [AB] moves |
      | single-unseen | no-delivery |
      | pair-only-attacker-visible | attacker-ID-and-someone |
      | pair-only-target-visible | Someone-and-target-ID |
      | pair-neither-visible | no-delivery |
      | pair-both-visible | both-observer-specific-IDs |
      | hex-own-dollar-h | your hex |
      | hex-other3,4-dollar-h | 3,4 |
      | hex-own-dollar-H | %ch%crYOUR HEX%cn |
      | hex-other3,4-dollar-H | %ch%cy3,4%cn |
      | hex-unknown-dollar-q-terminal-dollar | unknown-dollar-q-retained-terminal-dollar-removed |
      | hex-height3 | sight-uses-Elevation-times-ZSCALE |

  Scenario Outline: Communications audiences 04 - real fire broadcasts
    Given ordinary firing fixture <fixture>
    When one shot resolves
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | unit-hit-both-visible | observer-hits-text-hit-counter-plus1 |
      | unit-miss-defender-only-visible | Something-misses-target-ID |
      | unit-shot-attacker-only-visible | attacker-fires-at-something |
      | unit-shot-neither-visible | no-observer-message |
      | hex-shot-both-visible | attacker-fires-at-hex-no-shot-counter |
      | hex-shot-defender-only-visible | Something-fires-at-hex |
      | unit-hit-unconscious-observer | no-observer-inbox-hit-counter-plus1 |

  Scenario Outline: Communications audiences 05 - common command checks
    Given flag-controlled common check state <state>
    When the source command eligibility check runs
    Then the observation is <observation>
    Examples:
      | state | observation |
      | null-unit | rejected |
      | destroyed-and-stopped-USUALO | destroyed-error |
      | stopped-and-blinded-USUALO | reactor-error |
      | blinded-and-unconscious-USUALO | blinded-error |
      | unconscious-started-pilot-USUAL | unconscious-error |
      | unconscious-started-passenger-USUAL | eligible |
      | unconscious-stopped-passenger-USUALS | unconscious-error |
      | IC-nonwizard-nonpilot-USUALO | pilot-only-error |
      | IC-wizard-nonpilot-USUALO | eligible |
      | OOC-nonpilot-USUALO | eligible |
      | negative-map-USUAL | no-map-error |
      | unresolved-nonnegative-map-USUAL | invalid-map-shutdown-reset-minus1 |
      | last-use99-no-check-flags | eligible-last-use0 |
