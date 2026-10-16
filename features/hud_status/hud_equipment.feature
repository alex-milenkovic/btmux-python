# HUD equipment exports 01 - weapon priority; HUD equipment exports 02 - mode ordering; HUD equipment exports 03 - weapon traversal; HUD equipment exports 04 - limb recycling; HUD equipment exports 05 - ammunition groups
Feature: HUD equipment exports
  Background:
    Given a fresh HUD display session with ready units and event time zero
    And session key is test

  Scenario Outline: HUD equipment exports 01 - weapon priority
    Given a mounted weapon has states <states> and recycle data <ticks>
    When keyed HUD we is requested
    Then its weapon status is <status>
    Examples:
      | states | ticks | status |
      | ready | 0 | R |
      | broken-disabled-jammed | 0 | * |
      | disabled-jammed | 0 | D |
      | jammed | 0 | J |
      | shorted | 0 | S |
      | dud | 0 | d |
      | empty | 0 | E |
      | ammojammed | 0 | A |
      | temporarily-destroyed | 0 | * |
      | jettisoned | 5 | j |
      | ready | 5 | 2 |
      | ready | 1 | 0 |

  Scenario Outline: HUD equipment exports 02 - mode ordering
    Given the diagnostic weapon has fire selection <fire> ammo selection <ammo> and intact targeting computer
    When keyed HUD we is requested
    Then fire letters are <fire_text> and ammo letters are <ammo_text>
    Examples:
      | fire | ammo | fire_text | ammo_text |
      | none | none | - | - |
      | RAC2-RAC4-RAC6-HOTLOAD-ULTRA | SWARM1-ARTEMIS-INFERNO | 246HU | 1AI |
      | TC-OS-OSUSED | INARC_EXPLO-ATM_HE | To | XX |
      | AMS-enabled | none | A | - |
      | AMS-disabled | none | a | - |

  Scenario Outline: HUD equipment exports 03 - weapon traversal
    Given weapons are installed in section-slot order <mounts> with the first mount rear-mounted and brands alternating 1 and 2 in traversal order
    When keyed HUD we and wl are requested
    Then WE has <count> sequential zero-based weapon rows with source sections brands and rear suffix
    And WL contains one row per non-personal-combat catalog type with all 18 source fields
    Examples:
      | mounts | count |
      | LARM:4,RARM:0 | 2 |
      | LARM:0,LARM:4,RARM:0 | 3 |

  Scenario Outline: HUD equipment exports 04 - limb recycling
    Given unit form <form> left arm state <state> and recycle data <ticks>
    When keyed HUD li is requested
    Then LI has <rows> rows and first status <status> followed by one Done
    Examples:
      | form | state | ticks | rows | status |
      | biped | intact | 0 | 4 | R |
      | quad | intact | 5 | 4 | 2 |
      | biped | destroyed | 0 | 4 | * |
      | vehicle | intact | 0 | 0 | absent |

  Scenario Outline: HUD equipment exports 05 - ammunition groups
    Given two functional ammo bins of one weapon have modes <modes> rounds 5 and 7 and capacities 20 and 20
    When keyed HUD am is requested
    Then AM contains <rows> groups with current amounts <current> and maximum amounts <maximum>
    Examples:
      | modes | rows | current | maximum |
      | standard-standard | 1 | 12 | 40 |
      | standard-inferno | 2 | 5,7 | 20,20 |
