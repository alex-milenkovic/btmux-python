# Six location fighter weapons 01 - location arcs
# Six location fighter weapons 02 - recycling with depleted armor
# Six location fighter weapons 03 - aimed fighter shots
# Six location fighter weapons 04 - targeting computer masks
# Six location fighter weapons 05 - failed targeting computer gate
# Six location fighter weapons 06 - cockpit aiming penalty
Feature: Six location fighter weapons
  Background:
    Given a source-compatible fighter with functional physical weapon slots and ordinary firing prerequisites satisfied

  Scenario Outline: Six location fighter weapons 01 - location arcs
    Given a weapon in <section> mounted <mount>
    When front left right and rear arcs are checked independently
    Then allowed arcs are <arcs>
    Examples:
      | section | mount | arcs |
      | Nose | normal | front-left-right |
      | Fuselage | normal | front-left-right-rear |
      | Left_Wing | normal | front-left |
      | Left_Wing | rear | left-rear |
      | Right_Wing | normal | front-right |
      | Right_Wing | rear | right-rear |
      | Engine | normal | rear |
      | Cockpit | normal | none |

  Scenario Outline: Six location fighter weapons 02 - recycling with depleted armor
    Given the weapon lifecycle fixture <fixture>
    When firing and scheduled recycling execute
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | armor0-functional-ready-valid-arc | fire-accepted-recycle-started |
      | armor0-functional-recycle5-advance5 | recycle-remains5 |
      | armor-positive-functional-recycle5-advance5 | recycle-finishes |
      | armor0-destroyed-weapon | fire-refused |

  Scenario Outline: Six location fighter weapons 03 - aimed fighter shots
    Given an immobile fighter aimed location <location>
    When the successful aimed-shot location helper runs from BACK
    Then it returns <index> with rear true and no critical request
    Examples:
      | location | index |
      | Nose | 0 |
      | Left_Wing | 1 |
      | Right_Wing | 2 |
      | Fuselage | 3 |
      | Cockpit | 4 |
      | Engine | 5 |

  Scenario Outline: Six location fighter weapons 04 - targeting computer masks
    Given matching fighter aim type location <aim> side <side> and successful TC roll 3
    When the TC location helper runs with fallback roll 7
    Then the returned location is <location> through <path>
    Examples:
      | aim | side | location | path |
      | Nose | FRONT | Nose | fighter |
      | Cockpit | FRONT | Cockpit | fighter |
      | Engine | BACK | Engine | fighter |
      | Fuselage | BACK | Fuselage | fighter |
      | Left_Wing | RIGHTSIDE | Left_Wing | vehicle-fallthrough |
      | Right_Wing | LEFTSIDE | Right_Wing | vehicle-fallthrough |
      | Cockpit | BACK | Cockpit | vehicle-fallthrough |
      | Nose | BACK | Nose | vehicle-fallthrough |
      | Engine | FRONT | Nose | normal-table |
      | Fuselage | FRONT | Nose | normal-table |

  Scenario Outline: Six location fighter weapons 05 - failed targeting computer gate
    Given TC gate case <fixture>
    When a FRONT hit uses fallback roll 7
    Then it hits Nose with random observation <draws>
    Examples:
      | fixture | draws |
      | matching-type-roll2 | tc-d6-consumed |
      | mismatched-type | no-tc-d6 |

  Scenario Outline: Six location fighter weapons 06 - cockpit aiming penalty
    Given a <weapon> aimed at fighter section <aim> against a <mobility> target with targeting computer <tc>
    When the ordinary to-hit calculation evaluates aiming
    Then the aim modifier is <modifier>
    Examples:
      | weapon | aim | mobility | tc | modifier |
      | Laser | Cockpit | immobile | off | 7 |
      | Laser | Cockpit | mobile | off | 25 |
      | Laser | Cockpit | immobile | on | 7 |
      | Laser | Cockpit | mobile | on | 25 |
      | Missile | Cockpit | mobile | off | 0 |
      | Laser | Engine | mobile | off | 0 |
      | Laser | Fuselage | immobile | off | 0 |
      | Laser | Engine | mobile | on | 3 |
      | Laser | Engine | immobile | on | -1 |
