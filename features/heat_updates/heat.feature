# Integrated heat 01 - retained weapon heat; Integrated heat 02 - temperature order; Integrated heat 03 - water sinks; Integrated heat 04 - low-band shutdown; Integrated heat 05 - injury delivery
Feature: Integrated heat
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Integrated heat 01 - retained weapon heat
    Given a stationary mech with capacity 10 no disabled sinks old heat <old_heat> weapon heat 20 and started state <started>
    And previous plus heat is 20 with no engine or environment heat
    When the standard dispatcher advances <seconds> seconds
    Then current heat is <heat> and retained weapon heat is <retained>
    Examples:
      | old_heat | started | seconds | heat | retained |
      | 0 | True | 2 | 10 | 19.66666603088379 |
      | 100 | True | 2 | 10 | 19.66666603088379 |
      | 100 | False | 2 | 10 | 19.66666603088379 |
      | 0 | True | 4 | 9.666666030883789 | 19.333332061767578 |

  Scenario Outline: Integrated heat 02 - temperature order
    Given a stationary mech with active capacity <capacity> weapon heat 20 jellied state <jellied> and special-map rules <special>
    And map temperature is <temperature> Celsius with no water bonus
    When one heat update occurs before the overheat check is due
    Then dissipation is <dissipation> and current heat is <heat>
    Examples:
      | capacity | jellied | special | temperature | dissipation | heat |
      | 10 | False | True | -30 | 10 | 10 |
      | 10 | False | True | -31 | 11 | 9 |
      | 10 | False | True | -41 | 12 | 8 |
      | 10 | False | True | 50 | 10 | 10 |
      | 10 | False | True | 51 | 9 | 11 |
      | 10 | False | True | 61 | 8 | 12 |
      | 10 | False | False | 61 | 10 | 10 |
      | 4 | True | True | -31 | 1 | 19 |
      | 4 | True | True | 51 | -1 | 21 |

  Scenario Outline: Integrated heat 03 - water sinks
    Given a mech with active capacity <capacity> functional submerged leg sink slots <leg_slots> and weapon heat 20
    And the mech is in water at Z <z> and fallen state <fallen>
    When one heat update occurs before the overheat check is due
    Then dissipation is <dissipation> and current heat is <heat>
    Examples:
      | capacity | leg_slots | z | fallen | dissipation | heat |
      | 10 | 0 | -1 | False | 10 | 10 |
      | 10 | 2 | -1 | False | 12 | 8 |
      | 10 | 6 | -1 | False | 14 | 6 |
      | 10 | 0 | -2 | False | 16 | 4 |
      | 10 | 0 | -1 | True | 16 | 4 |
      | 2 | 2 | -1 | False | 4 | 16 |
      | 10 | 4 | 0 | False | 10 | 10 |

  Scenario Outline: Integrated heat 04 - low-band shutdown
    Given a stationary started mech without ammo at current heat <heat> and last overheat check tick 0
    When the due overheat evaluation runs at event tick <tick> with shutdown roll <roll>
    Then the mech remains started <started> and last overheat check tick is <last_check>
    Examples:
      | heat | tick | roll | started | last_check |
      | 9.9 | 30 | 12 | True | 0 |
      | 10 | 29 | 12 | True | 0 |
      | 10 | 30 | 12 | True | 30 |
      | 13.9 | 30 | 12 | True | 30 |
      | 14 | 30 | 3 | False | 30 |
      | 14 | 30 | 4 | True | 30 |
      | 18 | 30 | 5 | False | 30 |
      | 18 | 30 | 6 | True | 30 |

  Scenario Outline: Integrated heat 05 - injury delivery
    Given a mech with destroyed life support and no prior pilot injuries
    When a heat update produces heat <heat> at event tick <tick>
    Then the pilot has <injuries> applied heat injuries
    Examples:
      | heat | tick | injuries |
      | 14.9 | 30 | 0 |
      | 15 | 30 | 1 |
      | 25 | 30 | 1 |
      | 25.1 | 30 | 2 |
      | 26 | 28 | 0 |
