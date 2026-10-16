# Repair economy pickup dropoff and cables 01 pickup guards and transitions
# Repair economy pickup dropoff and cables 02 cable asymmetries
# Repair economy pickup dropoff and cables 03 release consequences
Feature: Repair economy pickup dropoff and cables

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy pickup dropoff and cables 01 pickup guards and transitions
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | Mech tower functional arms and enemy intact shutdown team2 | pickup target | refuse intact enemy |
      | Mech tower functional arms and enemy started | pickup target | refuse started enemy |
      | Mech tower functional arms and friendly shutdown target | pickup target | carrying relation TOWED fallen centered shutdown and mirrored position |
      | Mech quad tower | pickup nonMW | refuse quad |
      | Mech tower left arm destroyed right functional | pickup nonMW | refuse missing arm |
      | Mech tower both arms present left shoulder and hand functional right broken | pickup nonMW | accept equipment gate |
      | Mech tower both arms present no arm has both shoulder and hand | pickup nonMW | refuse functional actuator gate |
      | nonMech tower no SALVAGE_TECH | pickup nonMW | refuse salvage equipment |
      | nonMech tower SALVAGE_TECH | pickup friendly target | accept equipment gate |
      | Mech tower speed1 vertical-1 | pickup friendly target | accept speed boundary |
      | Mech tower speed1.01 | pickup friendly target | refuse speed boundary |
      | Mech tower z3 targetz0 samehex | pickup friendly target | accept upper height boundary |
      | Mech tower z4 targetz0 samehex | pickup friendly target | refuse height |
      | Mech tower z-2 targetz0 samehex | pickup friendly target | accept lower height boundary |
      | Mech tower z-3 targetz0 samehex | pickup friendly target | refuse height |
      | Mech tower carrying unit already with valid friendly MW target | pickup MW | existing MW pickup branch before carrying rejection |
      | Mech tower enemy shutdown target team0 | pickup target | no intact enemy refusal |
      | valid target hidden | pickup target | refuse hidden |
      | valid target OOC not towable | pickup target | refuse OOC |
      | valid target already carrying another unit | pickup target | prior load dropped through shared release then new tow attached |

  Scenario Outline: Repair economy pickup dropoff and cables 02 cable asymmetries
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | actor friendly to IC Mech tower and enemy intact shutdown load | attachcables tower load | attach permitted without intact enemy rejection |
      | actor friendly to IC ground tower SALVAGE_TECH | attachcables tower load | refuse dedicated salvage tower |
      | actor friendly to OOC towable tower | attachcables tower load | refuse tower not IC |
      | actor friendly to IC tower speed0.01 | attachcables tower load | refuse exact stationary gate |
      | actor friendly to IC tower and OOC towable load | attachcables tower load | attach permitted |
      | actor friendly to IC tower and enemy started load | attachcables tower load | refuse started enemy |
      | actor enemy to IC tower | attachcables tower load | refuse tower team |
      | actor OOD | attachcables tower load | refuse actor OOD |
      | actor samehex different elevation from tower | attachcables tower load | refuse elevation |
      | valid actor tower and load with different real coordinates samehex | attachcables tower load | tow attached without mirror-position branch |
      | nonpilot GOD actor | detachcables tower | shared usual gate still applies |
      | enemy actor passing usual guards samehex moving tower carries load | detachcables tower | detach allowed without team or stationary gate |
      | valid tower carrying missing object | detachcables tower | relation cleared before missing-object return |
      | valid tower on elevated terrain load aloft | detachcables tower | load integer z set to tower floor no fall and FZ unchanged |

  Scenario Outline: Repair economy pickup dropoff and cables 03 release consequences
    Given repair economy state <initial>
    When the repair economy user performs dropoff
    Then the repair economy observation is <expected>

    Examples:
      | initial | expected |
      | tower with load z3 own floor0 | relation clear TOWED clear speeds0 FALL due3 payload-1 |
      | same load z2 own floor0 tower floor1 | z1 and no fall event |
      | load z0 tower on ICE | z0 and no fall event |
      | load fallen shutdown | remains fallen shutdown after release |
      | tower carrying missing object | relation clear and no target mutation |
      | tower carrying no unit | refusal no carrying unit |
