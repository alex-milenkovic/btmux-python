# Heat sink control 01 - cutoff capacity; Heat sink control 02 - progressive recovery; Heat sink control 03 - delayed command; Heat sink control 04 - submerged switching
Feature: Heat sink control
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Heat sink control 01 - cutoff capacity
    Given a stationary mech with sink technology <technology> capacity <capacity> disabled capacity <disabled> and weapon heat <weapon_heat>
    And heat cutoff is engaged
    When one heat update occurs before the overheat check is due
    Then disabled capacity is <remaining_disabled> dissipation is <dissipation> and current heat is <heat>
    Examples:
      | technology | capacity | disabled | weapon_heat | remaining_disabled | dissipation | heat |
      | SINGLE | 10 | 4 | 16 | 3 | 7 | 9 |
      | SINGLE | 10 | 4 | 15 | 4 | 6 | 9 |
      | SINGLE | 10 | 4 | 15.9 | 4 | 6 | 9.9 |
      | SINGLE | 10 | 4 | 14 | 6 | 4 | 10 |
      | SINGLE | 10 | 4 | 18 | 2 | 8 | 10 |
      | SINGLE | 10 | 1 | 21 | 0 | 10 | 11 |
      | SINGLE | 2 | 0 | 0 | 2 | 0 | 0 |
      | DOUBLE | 20 | 8 | 26 | 4 | 16 | 10 |
      | CLAN | 20 | 8 | 26 | 4 | 16 | 10 |
      | DOUBLE | 20 | 0 | 0 | 4 | 16 | 0 |

  Scenario Outline: Heat sink control 02 - progressive recovery
    Given a stationary mech with sink technology <technology> capacity <capacity> disabled capacity <disabled> and weapon heat 0
    And heat cutoff is disengaged
    When <updates> heat updates occur before the overheat check is due
    Then disabled capacity is <remaining_disabled> and current heat is zero
    Examples:
      | technology | capacity | disabled | updates | remaining_disabled |
      | SINGLE | 10 | 5 | 1 | 3 |
      | SINGLE | 10 | 5 | 2 | 1 |
      | SINGLE | 10 | 5 | 3 | 0 |
      | DOUBLE | 20 | 9 | 1 | 5 |
      | DOUBLE | 20 | 9 | 3 | 0 |
      | CLAN | 20 | 2 | 1 | 0 |

  Scenario Outline: Heat sink control 03 - delayed command
    Given a mech with cutoff initially <initial>
    When the pilot requests heatcutoff <requests> times and advances <seconds> seconds
    Then exactly one cutoff request was accepted
    And cutoff is <active> and a cutoff transition is <pending>
    Examples:
      | initial | requests | seconds | active | pending |
      | False | 1 | 3 | False | True |
      | False | 1 | 4 | True | False |
      | True | 1 | 3 | True | True |
      | True | 1 | 4 | False | False |
      | False | 2 | 4 | True | False |

  Scenario Outline: Heat sink control 04 - submerged switching
    Given a stationary single-sink mech with capacity 10 disabled capacity 8 four functional leg sink slots and weapon heat <weapon_heat>
    And the upright mech is at depth one in water with heat cutoff engaged
    When one heat update occurs before the overheat check is due
    Then disabled capacity is <remaining_disabled> dissipation is <dissipation> and current heat is <heat>
    Examples:
      | weapon_heat | remaining_disabled | dissipation | heat |
      | 14 | 7 | 5 | 9 |
      | 16 | 6 | 6 | 10 |
      | 12 | 10 | 2 | 10 |
