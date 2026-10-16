# Display integration 01 - building entry clock; Display integration 02 - building lock threshold; Display integration 03 - entry recheck; Display integration 04 - live display refresh; Display integration 05 - unavailable services; Display integration 06 - fighter compatibility
Feature: Display integration
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Display integration 01 - building entry clock
    Given a ready grounded mech at a real building entrance with an unlocked destination and one towed unit
    When enterbase is issued and <ticks> engine ticks elapse
    Then both units are on <map> and entry completion count is <count>
    Examples:
      | ticks | map | count |
      | 17 | outside | 0 |
      | 18 | inside | 1 |

  Scenario Outline: Display integration 02 - building lock threshold
    Given a locked building with maximum CF 100 current CF <cf> and safe <safe>
    When a ready mech issues enterbase at its entrance
    Then entry scheduling is <scheduled>
    Examples:
      | cf | safe | scheduled |
      | 50 | false | false |
      | 49 | false | true |
      | 49 | true | false |

  Scenario Outline: Display integration 03 - entry recheck
    Given building entry was scheduled and the unit changes to <state> before tick 18
    When the engine reaches tick 18
    Then the unit stays outside with no completed entry
    Examples:
      | state |
      | shutdown |
      | jumping |
      | moved-off-entrance |
      | locked-safe-destination |

  Scenario Outline: Display integration 04 - live display refresh
    Given a unit display fixture with an actual mounted weapon and armor
    When normal workflow <workflow> changes the unit and display commands are repeated
    Then the new display shows <observable> and unrelated state is preserved
    Examples:
      | workflow | observable |
      | weapon-fire-and-recycle | busy-then-ready |
      | real-section-armor-repair | repairing-then-current-value |
      | timed-fire-overlay-expiry | underlay-restored |
      | target-leaves-LOS | contact-removed-target-not-in-LOS |

  Scenario Outline: Display integration 05 - unavailable services
    Given a local display workflow requires unavailable external service <service>
    When the workflow reaches that service
    Then the missing effect is explicitly reported and not counted as implemented behavior
    Examples:
      | service |
      | MUX-expression-lock |
      | MUX-custom-template-expression |
      | autopilot-scan-reply |

  Scenario Outline: Display integration 06 - fighter compatibility
    Given an unchanged six-location fighter template <template> is loaded with distinct section armor
    When armor status critical status HUD oas and as are requested
    Then all six named sections and five Cockpit slots are preserved and no gameplay SI pool is created
    Examples:
      | template |
      | CHP-W5 |
