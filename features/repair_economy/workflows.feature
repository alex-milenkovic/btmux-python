# Repair economy integrated maintenance workflows 01 public journeys and compatibility
Feature: Repair economy integrated maintenance workflows

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy integrated maintenance workflows 01 public journeys and compatibility
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | Mech damaged internal8 original10 armor7 original10 shared hangar stock | fix internal then armor then inspect manifest | 2 internal and3 armor consumed with real sequential restoration |
      | Mech broken gun stock0 admin in shared hangar | add stock then replacegun then repairs then advance | command sees added stock and repairs at due without second debit |
      | Mech full ammo and empty shared hangar | unload then advance then reload then advance | returned bin commodity funds refill and net stock0 |
      | Mech healthy LA removable part | remove part then advance then remove section then advance | salvage appears only after each real event and can be loaded |
      | partial armor job with2 remaining points | save then fresh process load advance | remaining points restored once without renewed resource charge |
      | fake part replacement pending | save then fresh process load advance | conflict persists until due and part remains broken |
      | local room stock and technician backlog | persist then fresh process load | inventory and absolute TECHTIME retained across process |
      | friendly tow pickup then movement then dropoff | ordinary commands and advance | shared carried unit follows then releases and stops following |
      | original CHP-W5 positive Nose armor damage | load original fixarmor then save template and reload | six named sections original stats preserved and repaired armor visible before design reload |
      | original CHP-W5 zero Engine armor ready weapon | repair diagnostics then combat inspection | thrust0 fall behavior and armor-based destruction retained without SI substitution |
      | existing conscious MW local target | existing pickup command | occupant transfer and health semantics preserved |
      | existing cost fixture | cost readout before and after empty inventory setup | identical FASA cost |
