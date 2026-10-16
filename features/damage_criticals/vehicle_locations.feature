# Damage vehicle locations 01 - advanced tables and turret fallback; Damage vehicle locations 02 - critical eligibility boundaries; Damage vehicle locations 03 - dug-in override threshold; Damage vehicle locations 04 - source-specific naval and aero rows
Feature: Damage vehicle locations
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage vehicle locations 01 - advanced tables and turret fallback
    Given advanced <unit_class> locations from <side> with turret internal <turret> and every crittable check failing
    When hit-location rolls two through twelve are evaluated on independent fixtures
    Then ordered locations are <locations> and no output critical is set
    Examples:
      | unit_class | side | turret | locations |
      | GROUND | LEFT | 10 | LSIDE,LSIDE,LSIDE,FSIDE,LSIDE,LSIDE,LSIDE,BSIDE,TURRET,TURRET,TURRET |
      | GROUND | RIGHT | 0 | RSIDE,RSIDE,RSIDE,FSIDE,RSIDE,RSIDE,RSIDE,BSIDE,RSIDE,RSIDE,RSIDE |
      | GROUND | FRONT | 0 | FSIDE,FSIDE,FSIDE,RSIDE,FSIDE,FSIDE,FSIDE,LSIDE,LSIDE,LSIDE,LSIDE |
      | GROUND | BACK | 0 | BSIDE,BSIDE,BSIDE,LSIDE,BSIDE,BSIDE,BSIDE,RSIDE,RSIDE,RSIDE,RSIDE |
      | VTOL | LEFT | 0 | LSIDE,LSIDE,LSIDE,FSIDE,LSIDE,LSIDE,LSIDE,BSIDE,ROTOR,ROTOR,ROTOR |
      | VTOL | FRONT | 0 | FSIDE,FSIDE,FSIDE,RSIDE,FSIDE,FSIDE,FSIDE,LSIDE,ROTOR,ROTOR,ROTOR |

  Scenario Outline: Damage vehicle locations 02 - critical eligibility boundaries
    Given class <unit_class> movement <movement> critproof <proof> vehicle-critical setting <vcrit> original armor <original> and current armor <current>
    When crittable is checked at threshold 60 with bounded chance draw <draw>
    Then eligibility is <eligible>
    Examples:
      | unit_class | movement | proof | vcrit | original | current | draw | eligible |
      | MECH | BIPED | False | 2 | 100 | 59 | 6 | True |
      | MECH | BIPED | False | 2 | 100 | 59 | 5 | False |
      | MECH | BIPED | False | 2 | 100 | 60 | 6 | False |
      | MECH | BIPED | False | 2 | 100 | 100 | 23 | True |
      | MECH | BIPED | False | 2 | 100 | 100 | 22 | False |
      | MECH | BIPED | True | 2 | 0 | 0 | 6 | False |
      | GROUND | NONE | False | 2 | 0 | 0 | 6 | False |
      | GROUND | TRACK | False | 1 | 0 | 0 | 6 | True |
      | GROUND | TRACK | False | 1 | 100 | 20 | 6 | False |

  Scenario Outline: Damage vehicle locations 03 - dug-in override threshold
    Given a dug-in ground vehicle with original turret internal 10 current turret internal <current> and profile <profile>
    When normal front location roll seven and dug-in draw <draw> are supplied
    Then selected location is <location>
    Examples:
      | current | profile | draw | location |
      | 10 | legacy | 41 | FSIDE |
      | 10 | legacy | 42 | TURRET |
      | 0 | legacy | 42 | TURRET |
      | 0 | advanced | 42 | FSIDE |
      | 10 | advanced | 42 | TURRET |

  Scenario Outline: Damage vehicle locations 04 - source-specific naval and aero rows
    Given a <unit_class> under <profile> viewed from <side> with live turret and no successful incidental TAC
    When selected table roll is <roll>
    Then selected location index is <location>
    Examples:
      | unit_class | profile | side | roll | location |
      | NAVAL | legacy | BACK | 7 | 2 |
      | NAVAL | FASA | BACK | 7 | 3 |
      | NAVAL | critproof | LEFT | 7 | 0 |
      | AERO | FASA | FRONT | 10 | 3 |
      | AERO | critproof | FRONT | 10 | 3 |
      | AERO | legacy | BACK | 7 | 3 |
