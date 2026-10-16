# Radio transmission 01 - send parsing and gates
# Radio transmission 02 - recipient selection
# Radio transmission 03 - scanner retuning
# Radio transmission 04 - scramble arithmetic
# Radio transmission 05 - CommXP and outside calls
# Radio transmission 06 - direct radio differences
Feature: Radio transmission
  Background:
    Given local occupants and live map membership with a documented source radio random stream

  Scenario Outline: Radio transmission 01 - send parsing and gates
    Given sendchannel request <request>
    When the ordinary command executes
    Then the observation is <observation>
    Examples:
      | request | observation |
      | a=hello | channel0-send-and-mine-check |
      | b=hello | channel1-send-and-mine-check |
      | A=hello | format-error |
      | Y=hello | format-error |
      | Z=hello | channel0-send-and-mine-check |
      | 1=hello | channel0-send-and-mine-check |
      | a ignored hello | channel0-send-hello-and-mine-check |
      | leading-space-a=hello | channel0-send-equals-hello-from-empty-first-token |
      | a=empty | format-error |
      | a=hello-stopped | send-allowed |
      | a=hello-destroyed | gear-inoperative |
      | a=hello-radio-range0 | gear-inoperative |
      | a=hello-crew-stunned | stunned-error |
      | a=byte10 | control-character-error-no-mine-check |
      | a=hello-IC-frequency0 | ZeroFrequencies-channel-and-send |

  Scenario Outline: Radio transmission 02 - recipient selection
    Given transmission condition <condition>
    When channel A sends hello
    Then the observation is <observation>
    Examples:
      | condition | observation |
      | matching-two-receiver-channels | first-eligible-channel-only |
      | first-matching-muted-second-matching | second-channel-only |
      | enemy-matching-analog | delivered |
      | matching-stopped-receiver | delivered |
      | matching-unconscious-receiver | inbox-suppressed |
      | matching-blinded-receiver | inbox-suppressed |
      | matching-destroyed-receiver | skipped |
      | matching-receiver-ID2 | skipped |
      | matching-receiver-radio0 | no-normal-delivery |
      | sender-digital-receiver-analog | delivered |
      | sender-digital-receiver-NODIGITAL | not-delivered |
      | sender-digital-range80-radio80 | delivered |
      | sender-digital-range80.9-radio80 | delivered-integer-range80 |
      | sender-digital-range81-radio80-no-relay | not-delivered |
      | sender-digital-receiver-radio1-range50-sender80 | delivered |
      | sender-digital-receiver-AngelECM | not-delivered |
      | sender-digital-self-ECM | self-echo |
      | observer-unmatched-frequency-range999-ECM | observer-message-once |
      | observer-all-channels-muted | no-observer-message |

  Scenario Outline: Radio transmission 03 - scanner retuning
    Given analog message length <length> frequency <frequency> scanner <scanner> and draws <draws>
    When an unmatched receiver scans
    Then the observation is <observation>
    Examples:
      | length | frequency | scanner | draws | observation |
      | 20 | 1000 | 900 | 21 | unchanged-no-detection |
      | 20 | 1000 | 900 | 20,20 | frequency920-somewhat |
      | 80 | 1000 | 900 | 80,60 | frequency960-precisely |
      | 100 | 1000 | 1100 | 80,99 | frequency1001-exactly |
      | 20 | 1000 | 999 | 1,1 | frequency1000-exactly-no-message-this-send |
      | 20 | 0 | 900 | none | no-scan |
      | 20 | 1000 | digital-sender-scanner900 | none | no-scan |
      | 20 | 1000 | out-of-range-ECM-scanner900 | 20,20 | frequency920-somewhat |

  Scenario Outline: Radio transmission 04 - scramble arithmetic
    Given message <message> and scramble state <state> with draws <draws>
    When source scrambling executes
    Then text and XP marker are <observation>
    Examples:
      | message | state | draws | observation |
      | A B | analog-range80-send80-recv80 | none | A B;xp0 |
      | A B | analog-range81-send80-recv80-bth4 | percent100-roll9-for-each-byte-twice | A!B;xp1 |
      | A | analog-range100-send50-recv100-bth4 | percent51-roll8-sign1-delta3 | greater-than-symbol;xp1 |
      | A | analog-range100-send50-recv100-bth4 | percent50 | A;xp1 |
      | A | analog-range100-send50-recv100-bth4 | percent51-roll9 | A;xp1 |
      | A | digital-range100-send50-recv1 | none | A;xp0 |
      | A | analog-ECM-range0 | none | A;xp0 |
      | A | digital-ECM-range1-bth4 | chance30-percent31-roll8-sign2-delta1 | B;xp1 |
      | space | analog-ECM-range1-bth4 | chance50-percent1 | exclamation;xp1 |

  Scenario Outline: Radio transmission 05 - CommXP and outside calls
    Given radio workflow <workflow>
    When ordinary transmission and time progression execute
    Then the observation is <observation>
    Examples:
      | workflow | observation |
      | scrambled-IC-last0-tick60 | no-XP-last0 |
      | scrambled-IC-last0-tick61 | CommXP-award-last61 |
      | scrambled-IC-last61-tick121 | no-new-XP-last61 |
      | scrambled-IC-last61-tick122 | CommXP-award-last122 |
      | scrambled-OOC-last0-tick61 | no-XP-last0 |
      | clear-IC-last0-tick61 | no-XP-last0 |
      | channel-matching-command-mine | actual-detonation-and-mine-state-change |
      | channel-unmatched-command-mine | mine-retained |
      | missing-autopilot-object | autopilot-reset-minus1 |
      | wrong-location-autopilot | executed-AI-channel |
      | valid-unported-autopilot-parser | unapplied-parser-request |
      | radio-range-recovery | subsequent-send-uses-restored-range |

  Scenario Outline: Radio transmission 06 - direct radio differences
    Given direct radio condition <condition>
    When radio AB=hello executes
    Then the observation is <observation>
    Examples:
      | condition | observation |
      | visible-enemy-radio0-ECM | sender-and-target-delivery |
      | visible-target-stopped | sender-only-delivery-no-AUTO-reply |
      | sender-stopped | reactor-error |
      | sender-observer | observer-error |
      | no-LOS | target-LOS-error |
      | wrong-separator | format-error |
      | one-letter-target | format-error |
      | three-letter-target | format-error |
      | sender-crew-stunned | send-allowed |
