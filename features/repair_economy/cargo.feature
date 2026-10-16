# Repair economy cargo transfer and mass 01 load unload restrictions
# Repair economy cargo transfer and mass 02 weight and speed coupling
Feature: Repair economy cargo transfer and mass

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy cargo transfer and mass 01 load unload restrictions
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | started pilot CargoTech in unit in OOC hangar at bay speed0 store5 | loadcargo item 3 | unit plus3 store minus3 |
      | shutdown pilot CargoTech in unit in OOC hangar at bay store5 | loadcargo item 3 | refuse shared started gate |
      | started pilot without CargoTech valid hangar | loadcargo item 3 | refuse CargoTech |
      | started pilot valid hangar speed0.1 | loadcargo item 3 | refuse movement |
      | started pilot valid hangar speed-0.1 | loadcargo item 3 | refuse movement |
      | started pilot valid hangar wrong bay third coordinate flag1 | loadcargo item 3 | refuse and reveal required coordinates |
      | started pilot valid hangar wrong bay third coordinate flag0 | loadcargo item 3 | refuse without coordinates |
      | started pilot IC hangar | loadcargo item 3 | refuse IC hangar |
      | shutdown pilot CargoTech moving IC hangar wrong bay cargo5 | unloadcargo item 3 | unit minus3 store plus3 |
      | pilot outside unit | unloadcargo item 3 | refuse actor location |
      | unit outside its map room | unloadcargo item 3 | refuse hangar relationship |
      | store itemA2 itemB5 selector both count4 | loadcargo selector 4 | transfer A2 B4 independently |
      | store21 matching items each1 | loadcargo selector 1 | all21 transfer without admin match cap |
      | bay attribute one numeric token | loadcargo item 1 | no bay-coordinate restriction |
      | valid load guards selector matches no items | loadcargo missing 1 | nothing matching and correct-speed refresh still occurs |

  Scenario Outline: Repair economy cargo transfer and mass 02 weight and speed coupling
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | unit inventory two one-ton parts brands1 and2 | refresh cargo weight | mass2 tons regardless brands and LOAD_OK cleared |
      | flying unit mounted fuel tank1 stored tank2 | refresh cargo weight | max fuel original plus6000 |
      | flying unit destroyed mounted fuel tank1 | refresh cargo weight | max fuel original plus2000 |
      | nonflying unit mounted fuel tank1 no stored tanks | refresh cargo weight | no mounted tank capacity addition |
      | flying unit bomb in backing section7 slot11 destroyed | refresh cargo weight | bomb mass included |
      | stored bomb commodity count2 | refresh cargo weight | source bomb weight times8 mass units |
      | flying unit fuel original100 current150 no tanks | refresh cargo weight | excess50 raw mass added |
      | flying unit fuel original100 current90 no tanks | refresh cargo weight | no excess-fuel mass |
      | old cargo maximum60 new cargo maximum40 speed55 desired55 | correct speed once then twice | first speeds55 second speeds40 |
      | old cargo maximum60 desired-50 actual-50 | correct speed | actual-40 desired-40 using reverse two-thirds |
