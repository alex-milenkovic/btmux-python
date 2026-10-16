# Vehicle fire 01 - advanced table; Vehicle fire 02 - continuing side burn; Vehicle fire 03 - extinguish lifecycle; Vehicle fire 04 - inferno water expiry
Feature: Vehicle fire
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Vehicle fire 01 - advanced table
    Given advanced vehicle fire is enabled for class <class> movement <movement>
    When external non-inferno heat reaches the vehicle with fire roll <roll> and section damage dice 3
    Then the fire response is <response>
    Examples:
      | class | movement | roll | response |
      | VEH_GROUND | TRACK | 7 | NONE |
      | VEH_GROUND | TRACK | 8 | MOTIVE_HIT |
      | VEH_GROUND | TRACK | 9 | MOTIVE_HIT |
      | VEH_GROUND | TRACK | 10 | SECTION_DAMAGE |
      | VEH_GROUND | TRACK | 11 | SECTION_DAMAGE |
      | VEH_GROUND | TRACK | 12 | BURNING |
      | VEH_GROUND | WHEEL | 6 | MOTIVE_HIT |
      | VEH_GROUND | HOVER | 6 | SECTION_DAMAGE |
      | VEH_GROUND | HOVER | 8 | BURNING |
      | VTOL | VTOL | 6 | NONE |
      | VTOL | VTOL | 8 | SECTION_DAMAGE |

  Scenario Outline: Vehicle fire 02 - continuing side burn
    Given a tracked ground vehicle with advanced vehicle fire enabled and exactly one live side having 100 front armor and 100 internal
    When inferno starts a side burn with initial die <initial> and the next burn die is <next>
    And the engine advances <seconds> seconds
    Then that side has lost <damage> armor and pending side burns number <pending>
    Examples:
      | initial | next | seconds | damage | pending |
      | 1 | 3 | 59 | 1 | 1 |
      | 1 | 3 | 60 | 4 | 1 |
      | 3 | 1 | 60 | 4 | 0 |
      | 3 | 6 | 60 | 9 | 1 |

  Scenario Outline: Vehicle fire 03 - extinguish lifecycle
    Given a vehicle with one persistent side fire sufficient armor and started state <started>
    When the pilot requests extinguish <requests> times and advances <seconds> seconds
    Then accepted extinguish commands number <accepted> burning is <burning> and extinguishing is <pending>
    Examples:
      | started | requests | seconds | accepted | burning | pending |
      | True | 1 | 0 | 0 | True | False |
      | False | 1 | 119 | 1 | True | True |
      | False | 1 | 120 | 1 | False | False |
      | False | 2 | 120 | 1 | False | False |

  Scenario Outline: Vehicle fire 04 - inferno water expiry
    Given a jellied mech with a live inferno expiry in 180 seconds
    When it enters terrain <terrain> with signed elevation <elevation> Z <z> and fallen state <fallen>
    Then jellied is <jellied> and a 120 second steam decoration is <steam>
    And a pending inferno expiry is <jellied>
    Examples:
      | terrain | elevation | z | fallen | jellied | steam |
      | WATER | -1 | -1 | False | True | False |
      | WATER | -1 | -1 | True | False | True |
      | WATER | -2 | -2 | False | False | True |
      | ICE | -2 | -2 | False | False | True |
      | BRIDGE | 2 | -1 | False | False | True |
      | WATER | -2 | 0 | False | True | False |
      | HIGHWATER | 2 | -2 | False | True | False |
