# Scanner commands 01 - range gates; Scanner commands 02 - report options; Scanner commands 03 - markings; Scanner commands 04 - dark map range
Feature: Scanner commands
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: Scanner commands 01 - range gates
    Given a scanner range <scan_range> and an identified ordinary unit at real range <range>
    When the pilot issues <command> for the target ID
    Then the command is <accepted> and the target receives <notices> scan notifications
    Examples:
      | scan_range | range | command | accepted | notices |
      | 20 | 20.9 | scan | True | 1 |
      | 20 | 21 | scan | False | 0 |
      | 20 | 21 | report | True | 0 |
      | 0 | 1 | scan | False | 0 |
      | 0 | 1 | report | False | 0 |

  Scenario Outline: Scanner commands 02 - report options
    Given an identified target with real armor and mounted weapon state within scanner range
    When the pilot requests scan option <option>
    Then armor details are <armor> information extras are <info> and weapon details are <weapons>
    And the base position and movement report is present
    Examples:
      | option | armor | info | weapons |
      | all | True | True | True |
      | A | True | False | False |
      | I | False | True | False |
      | W | False | False | True |

  Scenario Outline: Scanner commands 03 - markings
    Given a target with markings <markings> and NB visibility <nb>
    When the pilot views its contact ID
    Then the view outcome is <outcome>
    Examples:
      | markings | nb | outcome |
      | red-chevron | True | red-chevron |
      | empty | True | no-markings |
      | red-chevron | False | not-seen-well-enough |

  Scenario Outline: Scanner commands 04 - dark map range
    Given an observer at hex 2 2 Z 0 and destination hex 2 5 at floor 4
    And the map is dark <dark>
    When the pilot requests coordinate range
    Then displayed 3D range rounded to one decimal is <range> and displayed ground range is 3.0
    Examples:
      | dark | range |
      | False | 3.1 |
      | True | 3.0 |
