# Maps objects 01 - ordered object stream; Maps objects 02 - decoration deletion flags; Maps objects 03 - typed coordinate deletion
Feature: Maps objects
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps objects 01 - ordered object stream
    Given a map contains FIRE objects in list order A B and BUILD objects in list order C D
    When the object snapshot operation is <operation>
    Then the result is <result>
    Examples:
      | operation | result |
      | save | 27,FIRE-A,FIRE-B,BUILD-C,BUILD-D,0,39 |
      | save-then-load | FIRE-B,FIRE-A,BUILD-D,BUILD-C |
      | load-bad-start | error-retain-existing |
      | load-bad-end | error-after-record-load |

  Scenario Outline: Maps objects 02 - decoration deletion flags
    Given a timed smoke object covers water and has a pending event
    When that single object is deleted with zap <zap>
    Then raw terrain is <terrain> and its pending event is <event> while MAPO remains set
    Examples:
      | zap | terrain | event |
      | 0 | water | retained |
      | 1 | water | cancelled |
      | 2 | smoke | cancelled |
      | 3 | smoke | cancelled |

  Scenario Outline: Maps objects 03 - typed coordinate deletion
    Given two mine objects and one BLZ object share hex 1 1 and a fourth object is elsewhere
    When delobj receives <selector>
    Then deleted count is <count> with mine recalculation <recalculate>
    Examples:
      | selector | count | recalculate |
      | MINE | 2 | yes |
      | 1,1 | 3 | yes |
      | BLZ,1,1 | 1 | no |
      | FIRE,1,1 | 0 | no |
      | INVALID | 0 | type-error |
