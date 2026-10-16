# Unit status displays 01 - selection; Unit status displays 02 - owner weapon status; Unit status displays 03 - ammo colors; Unit status displays 04 - critical display; Unit status displays 05 - weapon specs unique; Unit status displays 06 - physical display threshold; Unit status displays 07 - heat bar shift; Unit status displays 08 - empty owner ammunition
Feature: Unit status displays
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Unit status displays 01 - selection
    When pilot status argument <argument> is requested
    Then selected status components are <components>
    Examples:
      | argument | components |
      | no-argument | generic,armor,info,heat,weapons |
      | A | generic,armor |
      | Info | generic,info,heat |
      | Weapons | generic,weapons |
      | H | heat |
      | S A W | short,target |
      | N | compact-template |
      | R | template-generic,armor,info,heat,weapons |

  Scenario Outline: Unit status displays 02 - owner weapon status
    Given a mounted weapon has state <state> and recycle data <ticks>
    When status weapons is requested
    Then weapon status text is <text>
    Examples:
      | state | ticks | text |
      | ready | 0 | Ready |
      | ready | 1 | 1 |
      | ready | 5 | 3 |
      | broken-disabled | 0 | ***** |
      | disabled | 0 | DISABLE |
      | jammed | 0 | JAMMED |
      | shorted | 0 | SHORTED |
      | ammojammed | 0 | AMMOJAM |
      | dud | 0 | DUD |
      | empty | 0 | EMPTY |
      | damaged-slot | 0 | DAMAGED |
      | rocket-fired | 0 | Empty |

  Scenario Outline: Unit status displays 03 - ammo colors
    Given functional ammo group capacity 100 and current amount <amount>
    When status weapons is requested
    Then that ammo amount uses color <color> even when it is a leftover row
    Examples:
      | amount | color |
      | 50 | bright-green |
      | 49 | bright-yellow |
      | 25 | bright-yellow |
      | 24 | bright-red |

  Scenario: Unit status displays 08 - empty owner ammunition
    Given functional ammo group capacity 100 and current amount 0
    When status weapons is requested
    Then the empty ammunition group is omitted and the direct amount color is bright-red

  Scenario Outline: Unit status displays 04 - critical display
    Given a biped arm with twelve legal critical slots and slot 1 state <state>
    When critstatus LARM is requested
    Then displayed slot order is 1,7,2,8,3,9,4,10,5,11,6,12 and slot 1 suffix is <suffix>
    Examples:
      | state | suffix |
      | destroyed-weapon | Destroyed |
      | disabled-weapon | Disabled |
      | damaged-weapon | Damaged |
      | ready-weapon | absent |

  Scenario Outline: Unit status displays 05 - weapon specs unique
    Given section traversal contains weapon types <types>
    When weaponspecs is requested
    Then weapon specification row types are <result> in first-seen order
    Examples:
      | types | result |
      | MediumLaser,MediumLaser,SRM6 | MediumLaser,SRM6 |
      | SRM6,MediumLaser,SRM6 | SRM6,MediumLaser |
      | none | You have no weapons! |

  Scenario Outline: Unit status displays 06 - physical display threshold
    Given a 60 ton mech has <slots> installed sword criticals including destroyed ones
    When status weapons is requested
    Then a sword readiness entry is present <present> without changing attack eligibility thresholds
    Examples:
      | slots | present |
      | 3 | false |
      | 4 | true |

  Scenario Outline: Unit status displays 07 - heat bar shift
    Given heat production 5 and dissipation <minus>
    When status H is requested
    Then the heat scale starts at <start> and left indicator is <indicator>
    Examples:
      | minus | start | indicator |
      | 27 | 0 | space |
      | 28 | 1 | < |
      | 32 | 5 | < |
