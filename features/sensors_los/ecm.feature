# ECM fields 01 - inclusive ranges; ECM fields 02 - strength thresholds; ECM fields 03 - transition delivery; ECM fields 04 - live pod sections
Feature: ECM fields
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: ECM fields 01 - inclusive ranges
    Given a hostile <suite> ECM emitter at real 3D range <range> from an otherwise unjammed observer
    When the normal ECM update runs
    Then the observer is ECM disturbed <disturbed>
    Examples:
      | suite | range | disturbed |
      | Guardian | 6 | True |
      | Guardian | 6.001 | False |
      | Angel | 6 | True |
      | Personal | 0.5 | True |
      | Personal | 0.501 | False |

  Scenario Outline: ECM fields 02 - strength thresholds
    Given friendly Guardian ECM count <fg> Angel ECM count <fa> and hostile Guardian ECCM count <hc>
    And friendly Guardian ECCM count <fc> and hostile Angel ECM count <ha>
    When the normal ECM update runs
    Then ECM countered is <countered>
    And the observer is ECM disturbed <disturbed>
    Examples:
      | fg | fa | hc | fc | ha | countered | disturbed |
      | 1 | 0 | 1 | 0 | 0 | True | False |
      | 0 | 1 | 1 | 0 | 0 | False | False |
      | 0 | 1 | 2 | 0 | 0 | True | False |
      | 0 | 0 | 0 | 2 | 1 | False | False |
      | 0 | 0 | 0 | 1 | 1 | False | True |

  Scenario Outline: ECM fields 03 - transition delivery
    Given a hostile Guardian emitter initially in range of the observer
    And the observer has functional Beagle equipment and BB sensors with a separate unprotected nonstealth target at range 1
    When the engine performs <updates> ECM updates followed by emitter removal and one update
    Then static notification count is 1 and normal-again notification count is 1
    And ECM disturbed is False and the probe can detect an eligible target
    Examples:
      | updates |
      | 1 |
      | 3 |

  Scenario Outline: ECM fields 04 - live pod sections
    Given one iNARC ECM pod on a MECH section with armor <armor> internal <internal> and destroyed config bit <config>
    And there are no other ECM or ECCM fields
    When the normal ECM update runs
    Then the observer is ECM disturbed <disturbed>
    Examples:
      | armor | internal | config | disturbed |
      | 0 | 10 | False | True |
      | 0 | 0 | False | False |
      | 0 | 10 | True | True |
      | 10 | 0 | False | True |
