# Status queries 01 - section state; Status queries 02 - armor serialization; Status queries 03 - slot query; Status queries 04 - slot bounds; Status queries 05 - weapon query classification
Feature: Status queries
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Status queries 01 - section state
    Given a named section is destroyed <destroyed> and flooded <flooded>
    When the user queries sectstatus for that section
    Then query text is <text>
    Examples:
      | destroyed | flooded | text |
      | false | false | 1 |
      | true | false | 0 |
      | false | true | -1 |
      | true | true | -1 |

  Scenario Outline: Status queries 02 - armor serialization
    Given a section has current front 7 internal 4 rear 2 and original front 20 internal 10 rear 5
    And every other section has zero current and original front internal and rear values
    When armorstatus query argument is <argument>
    Then query text with field pipes encoded as commas is <text>
    Examples:
      | argument | text |
      | that-section | 7/20,4/10,2/5 |
      | all-only-that-section | 9/25,4/10 |
      | missing-section | #-1 INVALID SECTION |

  Scenario Outline: Status queries 03 - slot query
    Given slot 1 has kind <kind> and state <state>
    When critslot query field <field> is requested
    Then slot query text is <text>
    Examples:
      | kind | state | field | text |
      | weapon | disabled-destroyed | STATUS | Disabled |
      | weapon | destroyed | STATUS | Destroyed |
      | weapon | ready | STATUS | Operational |
      | weapon | ready | MAXAMMO | #-1 NOT AMMO |
      | ammo | ready | MODE | #-1 NOT AMMO OR WEAPON |
      | ammo | half-ton | HALFTON | 1 |

  Scenario Outline: Status queries 04 - slot bounds
    Given a six-location AeroFighter Cockpit
    When critslot NAME is requested for one-based slot <slot>
    Then the result is <result>
    Examples:
      | slot | result |
      | 0 | #-1 INVALID CRITICAL |
      | 5 | part-name |
      | 6 | #-1 INVALID CRITICAL |

  Scenario Outline: Status queries 05 - weapon query classification
    Given a mounted weapon has condition <condition>
    When weaponstatus is queried without a section argument
    Then its final status integer is <status> and all eight source fields are present
    Examples:
      | condition | status |
      | ready | 0 |
      | temporary-failure | 1 |
      | nonfunctional | 2 |
