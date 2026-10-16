# Maps visibility 01 - configured refresh; Maps visibility 02 - partial scanf message
Feature: Maps visibility
  Background:
    Given a fresh maps environment session with explicit source defaults
    And a map has initial visibility 10 light 1 and a valid occupant

  Scenario Outline: Maps visibility 01 - configured refresh
    Given A_MAPVIS is <config>
    When map_update executes at event tick 25
    Then visibility is <vis> maximum visibility <maxvis> light <light> wind <wind> speed <speed> and cloudbase <cloud>
    Examples:
      | config | vis | maxvis | light | wind | speed | cloud |
      | 30,2,60,20 | 30 | 60 | 2 | 60 | 20 | 200 |
      | 4,0,120,40,80 | 4 | 24 | 0 | 120 | 40 | 80 |
      | 70,3,0,0,40 | 60 | 60 | 2 | 0 | 0 | 40 |
      | bad | 30 | 60 | 2 | 0 | 0 | 200 |
      | 30,2,0 | 30 | 60 | 2 | 0 | 0 | 200 |

  Scenario Outline: Maps visibility 02 - partial scanf message
    When tick 25 refresh uses A_MAPVIS <config>
    Then the change message is <message> and cloudbase is <cloud>
    Examples:
      | config | message | cloud |
      | 30,2,0,0,changed-weather | absent | 200 |
      | 30,2,0,0,100,abcde | absent | 100 |
      | 30,2,0,0,100,abcdef | abcdef | 100 |
      | 10,1,0,0,100,abcdef | absent | 100 |
