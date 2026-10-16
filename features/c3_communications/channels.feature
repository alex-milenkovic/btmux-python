# Radio channel configuration 01 - frequency parser
# Radio channel configuration 02 - title storage
# Radio channel configuration 03 - mode parser
# Radio channel configuration 04 - listing color and logging
Feature: Radio channel configuration
  Background:
    Given a registered radio with two channels and relay info scan capabilities

  Scenario Outline: Radio channel configuration 01 - frequency parser
    Given frequency input <input>
    When the frequency setter runs
    Then the observation is <observation>
    Examples:
      | input | observation |
      | a=0 | A-frequency0 |
      | a=999999 | A-frequency999999 |
      | A=123tail | A-frequency123 |
      | b=17 | B-frequency17 |
      | c=17 | channel-error |
      | a=00 | invalid-frequency |
      | a=0x1 | invalid-frequency |
      | a=-1 | negative-error |
      | a=1000000 | frequency-range-error |
      | a17 | missing-equals |
      | a= | invalid-input |
      | blank | invalid-input |
      | a=17-no-map | A-frequency17 |

  Scenario Outline: Radio channel configuration 02 - title storage
    Given title value <value>
    When the title setter writes channel A
    Then stored title and response are <observation>
    Examples:
      | value | observation |
      | Alpha | Alpha-and-set-to-set-to-Alpha |
      | 123456789012345 | all15-stored |
      | 1234567890123456 | first15-stored-full16-echoed |
      | empty | cleared |
      | leading-space-Alpha | Alpha-leading-whitespace-stripped |

  Scenario Outline: Radio channel configuration 03 - mode parser
    Given mode input <input> with capabilities <capabilities>
    When channel A mode is set
    Then the observation is <observation>
    Examples:
      | input | capabilities | observation |
      | empty | all | analog0 |
      | D | all | digital1 |
      | DIUES | all | mode31-flagsIUES |
      | E | all | digital-required-old-mode-retained |
      | I | all | info-requires-digital-old-mode-retained |
      | D | NODIGITAL | capability-error-old-mode-retained |
      | DE | no-relay | capability-error-old-mode-retained |
      | DI | no-info | capability-error-old-mode-retained |
      | S | no-scan | capability-error-old-mode-retained |
      | Drg | all | mode97-color-g |
      | DX | all | mode289-bright-x |
      | D?S | all | digital1-suffix-ignored |
      | ?D | all | analog0 |
      | s | all | scan16 |
      | u | all | mute2 |

  Scenario Outline: Radio channel configuration 04 - listing color and logging
    Given radio display state <state>
    When the source listing color helper or frequency setter runs
    Then the observation is <observation>
    Examples:
      | state | observation |
      | DI-color-r-S | D--S |
      | DI-color-r | D--r |
      | DI | D--I |
      | DU | D-M- |
      | ccode-none | empty |
      | ccode-r | %cr |
      | ccode-bright-X | %ch%c |
      | observer-team1 | %cw |
      | observer-team16 | %cw |
      | observer-team0-after-ccode-r | %cr |
      | set17-two-enemy-matching-nonscan-channels | two-MechFreqs-log-requests |
      | set17-enemy-scan-only | no-log-request |
      | set0-enemy-matching | no-log-request |
