# Maps snow 01 - melt layer boundaries; Maps snow 02 - steam delay; Maps snow 03 - growth and reconstructed validation
Feature: Maps snow
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps snow 01 - melt layer boundaries
    Given a nonice hex has snow data <data> and snow layer <layer> plus an unrelated layer
    When snow is melted by depth <depth> without steam
    Then data is <after> snow layer is <result> and unrelated layer remains
    Examples:
      | data | layer | depth | after | result |
      | 1100 | deep | 99 | 1001 | deep |
      | 1100 | deep | 100 | 1000 | shallow |
      | 1000 | shallow | 1000 | 0 | none |
      | 50 | shallow | 100 | 0 | none |
      | 50 | shallow | 0 | 50 | shallow |
      | 50 | shallow | -1 | 50 | shallow |

  Scenario Outline: Maps snow 02 - steam delay
    Given a nonice hex has shallow snow data 500
    When depth <depth> is melted with steam <steam> and the optional steam draw <draw>
    Then the smoke duration is <duration> and steam draw usage is <usage>
    Examples:
      | depth | steam | draw | duration | usage |
      | 50 | true | 0 | 50 | unused |
      | 90 | true | 0 | 90 | unused |
      | 100 | true | 0 | 90 | used |
      | 100 | true | 5 | 95 | used |
      | 100 | false | 0 | none | unused |

  Scenario Outline: Maps snow 03 - growth and reconstructed validation
    Given a hex has terrain <terrain> data 100 shallow snow and unrelated mud layer
    When growSnow bounds are <low> <high> with finite draw <draw>
    Then normalized data is <data> layers are <layers> and draw is <usage>
    Examples:
      | terrain | low | high | draw | data | layers | usage |
      | grass | 10 | 10 | 10 | 110 | shallow | used |
      | grass | -10 | 20 | 15 | 85 | shallow,mud | used |
      | water | 10 | 10 | 10 | 100 | shallow,mud | unused |
      | ice | 10 | 10 | 10 | 100 | shallow,mud | unused |
      | fire | 10 | 10 | 10 | 100 | shallow,mud | unused |
      | bridge | 10 | 10 | 10 | 100 | shallow,mud | unused |
      | grass | 0 | 0 | 0 | 100 | shallow,mud | unused |
      | grass | -200 | -200 | 200 | 0 | mud | used |
      | grass | 900 | 900 | 900 | 1000 | shallow | used |
      | grass | 901 | 901 | 901 | 1001 | deep | used |
