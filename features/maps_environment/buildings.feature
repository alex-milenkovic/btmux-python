# Maps buildings 01 - damage and regeneration; Maps buildings 02 - regen callback; Maps buildings 03 - rebuild callback is diagnostic; Maps buildings 04 - safety protection; Maps buildings 05 - step and scan visibility
Feature: Maps buildings
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps buildings 01 - damage and regeneration
    Given a building has CF <cf> maximum 100 and no timers
    When it takes explicit damage <damage> at tick 0
    Then CF becomes <remaining> and newly scheduled regen deadline is <deadline>
    Examples:
      | cf | damage | remaining | deadline |
      | 100 | 10 | 90 | 120 |
      | 90 | 10 | 80 | none |
      | 100 | 100 | 0 | none |
      | 100 | 150 | 0 | none |
      | 0 | 10 | 0 | none |

  Scenario Outline: Maps buildings 02 - regen callback
    Given a building with CF <cf> maximum 100 and regen factor <factor> has a regen event due at 120
    When the event runs at tick 120
    Then CF is <after> and next regen deadline is <deadline>
    Examples:
      | cf | factor | after | deadline |
      | 98 | 1 | 99 | 240 |
      | 99 | 1 | 100 | none |
      | 98 | 5 | 100 | none |
      | 0 | 1 | 0 | none |
      | 90 | 0 | 90 | 240 |
      | 90 | -1 | 89 | 240 |

  Scenario Outline: Maps buildings 03 - rebuild callback is diagnostic
    Given a building has CF <cf> maximum <maximum> and no timers
    When the rebuild callback is invoked diagnostically
    Then CF is <after> and no timer is scheduled
    Examples:
      | cf | maximum | after |
      | 0 | 100 | 1 |
      | 0 | 0 | 0 |
      | 1 | 100 | 1 |
      | 40 | 100 | 40 |

  Scenario Outline: Maps buildings 04 - safety protection
    Given a building at CF 100 has exterior flags <exterior> and interior flags <interior>
    When a unit hits it with explicit damage 10
    Then CF is <cf> and scratches-paint notification is <scratch>
    Examples:
      | exterior | interior | cf | scratch |
      | 0 | 0 | 90 | absent |
      | 2 | 0 | 100 | present |
      | 0 | 1 | 100 | present |
      | 1 | 0 | 90 | absent |
      | 0 | 2 | 90 | absent |

  Scenario Outline: Maps buildings 05 - step and scan visibility
    Given a same-elevation unit stands on a valid hangar for a building with flags <flags> and CF 75
    When the query <query> uses a successful perception roll if required
    Then the building CF is <visible>
    Examples:
      | flags | query | visible |
      | 0 | step | shown |
      | 4 | step | hidden |
      | 16 | step | shown |
      | 0 | scan | shown |
      | 4 | scan | shown |
      | 16 | scan | hidden |
