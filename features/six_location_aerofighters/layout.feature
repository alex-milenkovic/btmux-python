# Six location fighter layout 01 - original sections
# Six location fighter layout 02 - installed equipment
# Six location fighter layout 03 - builder defaults
# Six location fighter layout 04 - section addressing
# Six location fighter layout 05 - modern design round trip
Feature: Six location fighter layout
  Background:
    Given the historical fighter template and construction fixture described in docs/six-location-aerofighters-cli.md

  Scenario Outline: Six location fighter layout 01 - original sections
    When unchanged CHP-W5 is loaded
    Then section <index> is <name> with armor <armor> internal bookkeeping 10 and slot limit <slots>
    Examples:
      | index | name | armor | slots |
      | 0 | Nose | 24 | 12 |
      | 1 | Left_Wing | 15 | 12 |
      | 2 | Right_Wing | 15 | 12 |
      | 3 | Fuselage | 30 | 12 |
      | 4 | Cockpit | 16 | 5 |
      | 5 | Engine | 20 | 12 |

  Scenario Outline: Six location fighter layout 02 - installed equipment
    When unchanged CHP-W5 is loaded
    Then the physical equipment observation is <observation>
    Examples:
      | observation |
      | Nose-five-single-slot-weapons |
      | each-wing-large-lasers-at-slots-1-and-3-slot-2-empty |
      | Fuselage-four-LRM15-ammo-bins-of-8-and-one-SRM6-bin-of-15 |
      | Cockpit-LifeSupport-Sensors-Cockpit-Sensors-LifeSupport |
      | Engine-two-small-lasers-no-default-engine-or-sink-components |
      | six-sections-armor-total120-internals-total60-SI0-alive |
      | Fly-90tons-MaxSpeed86-Fuel750-HeatSinks25 |

  Scenario Outline: Six location fighter layout 03 - builder defaults
    When resetcrits is applied to a fighter
    Then section <section> has default contents <contents>
    Examples:
      | section | contents |
      | Nose | empty |
      | Left_Wing | empty |
      | Right_Wing | empty |
      | Fuselage | empty |
      | Cockpit | LifeSupport-Sensors-Cockpit-Sensors-LifeSupport |
      | Engine | Engine-at-3-and-11-HeatSink-at-other-ten-slots |

  Scenario Outline: Six location fighter layout 04 - section addressing
    When the fighter editor operation is <operation>
    Then the result is <result>
    Examples:
      | operation | result |
      | display-Fuselage | section3 |
      | display-Cockpit | section4-five-slots |
      | display-Engine | section5-twelve-slots |
      | add-special-Cockpit-slot5 | accepted |
      | add-special-Cockpit-slot6 | rejected-no-write |
      | add-weapon-Engine-slot12 | one-slot-accepted |
      | add-weapon-Engine-slot13 | rejected-no-write |

  Scenario Outline: Six location fighter layout 05 - modern design round trip
    Given loaded CHP-W5 with modification <modification>
    When modern save writes a new reference and a fresh unit loads that file
    Then the observation is <observation>
    Examples:
      | modification | observation |
      | none | all-six-design-sections-and-installed-equipment-preserved |
      | Nose-current-armor19 | Nose-armor24-internals10-on-reload |
      | Fuselage-current-armor0 | Fuselage-armor30-internals10-on-reload |
      | LRM-bin-current-ammo3 | LRM-bin-full-capacity-on-reload |
      | wing-slot3-rear-mounted | rear-mount-and-slot-gap-preserved |
