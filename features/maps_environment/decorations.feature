# Maps decorations 01 - smoke deadline and replacement; Maps decorations 02 - fire duration copy; Maps decorations 03 - dissipation terrain
Feature: Maps decorations
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps decorations 01 - smoke deadline and replacement
    Given water elevation 2 at hex 1 1 receives smoke duration 30 at tick 0
    When the next action is <action> and the clock reaches <tick>
    Then raw terrain is <terrain> with underlying water and pending decoration count <pending>
    Examples:
      | action | tick | terrain | pending |
      | none | 29 | smoke | 1 |
      | none | 30 | water | 0 |
      | replace-at-10-duration-40 | 30 | smoke | 1 |
      | replace-at-10-duration-40 | 50 | water | 0 |
      | delete-at-10 | 30 | water | 0 |

  Scenario Outline: Maps decorations 02 - fire duration copy
    Given an isolated light forest receives fire duration <duration> at tick 0 with windspeed <wind>
    When the fire is inspected immediately and its first scheduled event runs
    Then stored initial duration is <duration> first deadline is <first> and next callback is <next> at <deadline>
    Examples:
      | duration | wind | first | next | deadline |
      | 180 | 0 | 60 | spread | 120 |
      | 120 | 0 | 60 | dissipate | 120 |
      | 60 | 0 | 60 | dissipate | 61 |
      | 180 | 50 | 20 | spread | 40 |

  Scenario Outline: Maps decorations 03 - dissipation terrain
    Given a fire object has underlying <underlying> and no surviving spread event
    When its dissipation callback runs with forest roll <roll>
    Then final terrain is <terrain> and the forest draw is <draw>
    Examples:
      | underlying | roll | terrain | draw |
      | light-forest | 1 | grass | consumed |
      | heavy-forest | 2 | grass | consumed |
      | light-forest | 3 | rough | consumed |
      | heavy-forest | 6 | rough | consumed |
      | water | 1 | water | unused |
