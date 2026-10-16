# Spotter links 01 - delayed datalink; Spotter links 02 - coordinate movement gate; Spotter links 03 - watchdog distinction; Spotter links 04 - fire adjustments; Spotter links 05 - indirect target rules
Feature: Spotter links
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: Spotter links 01 - delayed datalink
    Given a shooter with a mounted artillery weapon and no LOS to a friendly self-spotter
    And their real range is <range> and observer radio range is 10
    When the shooter requests that spotter and the engine advances <seconds> seconds
    Then the spot request is <accepted> and the datalink is <linked> with handshake pending <pending>
    Examples:
      | range | seconds | accepted | linked | pending |
      | 19.9 | 11 | True | False | True |
      | 19.9 | 12 | True | True | False |
      | 20 | 13 | True | False | True |
      | 20 | 14 | True | True | False |
      | 20.01 | 14 | False | False | False |

  Scenario Outline: Spotter links 02 - coordinate movement gate
    Given an accepted artillery spot handshake at range 10
    When before expiry shooter X changes <sx> shooter Y changes <sy> observer X changes <ox> and observer Y changes <oy>
    And the engine advances to the handshake deadline
    Then the datalink is <linked> and movement failure notifications total <messages>
    Examples:
      | sx | sy | ox | oy | linked | messages |
      | False | False | False | False | True | 0 |
      | True | False | True | True | True | 0 |
      | True | True | False | False | True | 0 |
      | True | True | True | True | False | 2 |

  Scenario Outline: Spotter links 03 - watchdog distinction
    Given a spot link established by <method>
    When the observer state becomes <state> and the engine advances 10 seconds
    Then the datalink is <linked> and a watchdog is pending <watchdog>
    Examples:
      | method | state | linked | watchdog |
      | ordinary-LOS | beyond-radio-range | True | False |
      | artillery-handshake | at-radio-limit | True | True |
      | artillery-handshake | beyond-radio-range | False | False |
      | artillery-handshake | no-longer-spotting | False | False |
      | artillery-handshake | linked-to-another-spotter | True | True |
      | artillery-handshake | different-map | False | False |

  Scenario Outline: Spotter links 04 - fire adjustments
    Given a self-spotter with two linked shooters at fire adjustments 3 and 5 and an unrelated shooter at 7
    When the self-spotter performs <action>
    Then both linked adjustments are zero and the unrelated adjustment remains 7
    Examples:
      | action |
      | spot-cancel |
      | clear-target |
      | change-hex-target |

  Scenario Outline: Spotter links 05 - indirect target rules
    Given a stationary conscious self-spotter with a visible <target> target and no settling lock
    When the linked shooter sights with a mounted <weapon> weapon
    Then the indirect attempt is <accepted> with observer modifier <modifier> and target selection <selection>
    And ammunition and armor are unchanged
    Examples:
      | target | weapon | accepted | modifier | selection |
      | unit | artillery | False | none | none |
      | occupied-hex | artillery | True | 2 | hex |
      | clear-unit | IDF-missile | True | 1 | unit |
      | empty-hex | IDF-missile | True | 1 | hex |
