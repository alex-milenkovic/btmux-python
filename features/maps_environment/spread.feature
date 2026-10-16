# Maps spread 01 - wind parity coordinates; Maps spread 02 - short circuit fire draws; Maps spread 03 - smoke then forest ignition
Feature: Maps spread
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps spread 01 - wind parity coordinates
    Given a 12 by 12 map has a fire at <x> 4 and wind direction <wind>
    When the four downwind smoke candidates are calculated
    Then candidate coordinates in source order are <coordinates>
    Examples:
      | x | wind | coordinates |
      | 4 | 0 | 4,3;3,4;5,4;4,2 |
      | 5 | 0 | 5,3;6,3;4,3;5,2 |
      | 4 | 29 | 4,3;3,4;5,4;4,2 |
      | 4 | 30 | 5,4;4,3;5,5;6,3 |
      | 5 | 180 | 5,5;6,4;4,4;5,6 |
      | 4 | 359 | 4,3;3,4;5,4;4,2 |

  Scenario Outline: Maps spread 02 - short circuit fire draws
    Given one candidate has threshold <threshold> and the windspeed is <wind>
    When its spread roll is <roll> and next Number draw would be <number>
    Then the wind draw is <consumed> and candidate ignition eligibility is <eligible>
    Examples:
      | threshold | wind | roll | number | consumed | eligible |
      | 9 | 30 | 8 | 1 | unused | false |
      | 9 | 30 | 9 | 30 | used | true |
      | 9 | 30 | 9 | 31 | used | false |
      | 11 | 60 | 10 | 1 | unused | false |
      | 11 | 60 | 11 | 60 | used | true |
      | 12 | 0 | 12 | 1 | used | false |

  Scenario Outline: Maps spread 03 - smoke then forest ignition
    Given a downwind candidate has underlying <underlying> and existing decoration <decoration>
    When smoke is attempted then an eligible fire spread is attempted
    Then final overlay is <overlay>
    Examples:
      | underlying | decoration | overlay |
      | light-forest | none | fire |
      | heavy-forest | smoke | fire |
      | grass | none | smoke |
      | wall | none | none |
      | building | none | none |
      | water | smoke | smoke |
