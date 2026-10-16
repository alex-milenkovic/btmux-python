# Repair economy armor and structure maintenance 01 point scheduling
# Repair economy armor and structure maintenance 02 structural jobs and resources
# Repair economy armor and structure maintenance 03 repairability and material aliases
Feature: Repair economy armor and structure maintenance

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy armor and structure maintenance 01 point scheduling
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | front armor7 original10 full internals stock3 success | fixarmor and advance179 then1 then180 then180 | armor7 then8 then9 then10 and stock0 |
      | internal7 original10 stock3 success | fixinternal and advance539 then1 then540 then540 | internal7 then8 then9 then10 and stock0 |
      | rear armor4 original6 full internals stock2 success | fixarmor CT r and advance180 then180 | rear5 then6 front unchanged encodedloc12 |
      | front armor11 original10 full internals | fixarmor | refuse no repair need after source clamp |
      | front armor5 original10 internal9 original10 | fixarmor | refuse internals first |
      | front armor5 original10 stock5 initial fail recovery pass percentdraw5 | fixarmor | amount2 time9 minutes first due360 then540 total and stock0 |
      | internal5 original10 stock5 initial fail recovery fail percentdraw44 | fixinternal | amount2 time27 minutes first due1080 then1620 total and stock0 |
      | front armor9 original10 stock1 initial fail recovery pass percentdraw44 | fixarmor and advance1 | armor10 no finish message and no remaining event |
      | internal9 original10 stock1 initial fail recovery fail percentdraw5 | fixinternal and advance1 | internal10 no finish message and no remaining event |

  Scenario Outline: Repair economy armor and structure maintenance 02 structural jobs and resources
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | destroyed Mech LA LT present originalinternal10 stocks10 each success | reattach and advance14400 | LA internal10 unflooded and both stocks0 |
      | destroyed Mech LA originalinternal10 with LT destroyed | reattach | refuse path without dice or debit |
      | destroyed Mech CT originalinternal10 | reattach | refuse unfixable |
      | live Mech LA flooded originalinternal10 stocks10 each success | reseal and advance3600 | unflooded disabled parts repaired and both stocks0 |
      | live Mech LA not flooded | reseal | refuse not flooded |
      | live flooded LA originalinternal10 internalstock10 electronics9 | reseal | refuse and retain both full stocks |
      | live flooded LA originalinternal10 stocks10 each fail then recovery pass | reseal and advance5400 | real reseal and stocks0 |
      | live flooded LA originalinternal10 stocks10 each both fail percent50 | reseal and advance5400 | still flooded and refund5 each |
      | BA three live one destroyed target stock10,2,2,10 success | replacesuit and advance7200 | member restored and all four resources0 |
      | BA no live members and stock10,2,2,10 | replacesuit | refuse all dead without debit |
      | BA three live one destroyed fourth resource9 | replacesuit | refuse and retain every resource |
      | BA three live one destroyed full stock both fail percent50 | replacesuit and advance10800 | member stays destroyed refunds5 internal1 sensor1 life5 electronics |
      | nonBA destroyed location | replacesuit | refuse wrong unit type |
      | BA destroyed location | reattach | refuse suits need replacement |
      | destroyed Mech LA originalinternal10 stocks10 each first fail recovery pass | reattach and advance21600 | restored and stocks0 |
      | destroyed Mech LA originalinternal10 stocks10 each both fail | reattach and advance21600 | not restored and stocks0 |
      | AERO Nose armor0 internal0 original10 | reattach event | internal1 armor0 and still armor-destroyed |
      | AERO Nose armor5 original10 internal10 original10 stock5 success | fixarmor and advance900 | armor10 with internals10 and SI unchanged |

  Scenario Outline: Repair economy armor and structure maintenance 03 repairability and material aliases
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | Mech CT destroyed originalinternal10 | unit fixability | false |
      | Mech LA destroyed originalinternal10 CT intact | unit fixability | true |
      | VTOL rotor5 destroyed populated | unit fixability | true |
      | VTOL front destroyed populated | unit fixability | false |
      | ground turret4 destroyed populated | unit fixability | true |
      | ground front destroyed populated | unit fixability | false |
      | AERO Fuselage armor0 populated | unit fixability | true |
      | Mech CT unpopulated originalinternal0 | unit fixability | true |
      | FF and Hardened armor technologies | proper armor | FF cargo |
      | Stealth and HeavyFF armor technologies | proper armor | Stealth cargo |
      | HeavyFF and LightFF armor technologies | proper armor | HeavyFF cargo |
      | Purifier stealth infantry technology | proper armor | Purifier cargo |
      | Endosteel and Reinforced internal technologies | proper internal | Endosteel cargo |
      | Reinforced and Composite internal technologies | proper internal | Reinforced cargo |
      | Composite internal technology | proper internal | Composite cargo |
      | shoulder actuator | alias part | standard actuator cargo |
      | Engine XL and ICE technology | alias part | XL engine cargo |
      | Engine ICE and XXL technology | alias part | ICE engine cargo |
      | Engine XXL and Compact technology | alias part | XXL engine cargo |
      | Engine Compact and Light technology | alias part | Compact engine cargo |
      | Engine Light technology | alias part | Light engine cargo |
      | HeatSink with double technology | alias part | double heat sink cargo |
