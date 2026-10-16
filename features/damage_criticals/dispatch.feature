# Damage critical dispatch 01 - eligibility gates; Damage critical dispatch 02 - advanced critical charts; Damage critical dispatch 03 - legacy chart choices; Damage critical dispatch 04 - candidate rebuild and filler exclusion; Damage critical dispatch 05 - do not truncate requested criticals at death
Feature: Damage critical dispatch
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage critical dispatch 01 - eligibility gates
    Given class <unit_class> with combat safe <safe> critproof <proof> and vehicle-critical setting <vcrit>
    When one torso critical is requested with MW gate draw <draw> and a functional special slot
    Then slot dispatch count is <count>
    Examples:
      | unit_class | safe | proof | vcrit | draw | count |
      | MECH | True | False | 2 | 2 | 0 |
      | MECH | False | True | 2 | 2 | 0 |
      | MECH | False | False | 0 | 2 | 1 |
      | MW | False | False | 2 | 1 | 0 |
      | MW | False | False | 2 | 2 | 1 |
      | MW | False | False | 0 | 2 | 0 |
      | DS | False | False | 2 | 2 | 0 |

  Scenario Outline: Damage critical dispatch 02 - advanced critical charts
    Given a movable <unit_class> hit in <location> with advanced critical dispatch enabled
    When rolls six through twelve are independently requested through critical dispatch
    Then the selected source effects are <effects> and each selected effect executes its production consequence
    Examples:
      | unit_class | location | effects |
      | GROUND | FSIDE | driver,weapon-jam,stabilizer,sensor,commander,weapon-destroyed,crew-killed |
      | GROUND | LSIDE | cargo,weapon-jam,crew-stun,stabilizer,weapon-destroyed,engine,fuel |
      | GROUND | BSIDE | weapon-jam,cargo,stabilizer,weapon-destroyed,engine,ammo,fuel |
      | GROUND | TURRET | stabilizer,turret-jam,weapon-jam,turret-lock,weapon-destroyed,turret-off,ammo |
      | VTOL | FSIDE | copilot,weapon-jam,stabilizer,sensor,pilot,weapon-destroyed,crew-killed |
      | VTOL | LSIDE | weapon-jam,cargo,stabilizer,weapon-destroyed,engine,ammo,fuel |
      | VTOL | BSIDE | cargo,weapon-jam,stabilizer,weapon-destroyed,sensor,engine,fuel |
      | VTOL | ROTOR | rotor-damage,rotor-damage,rotor-damage,tail-rotor,tail-rotor,rotor-destroyed,rotor-destroyed |

  Scenario Outline: Damage critical dispatch 03 - legacy chart choices
    Given a movable <unit_class> with advanced critical dispatch disabled and profile <profile>
    When six independent critical resolutions choose legacy outcomes zero through five after any preliminary gate
    Then the selected source effects are <effects>
    Examples:
      | unit_class | profile | effects |
      | GROUND | FASA | head-injury,main-jam,engine,crew-killed,fuel,powerplant |
      | GROUND | legacy | head-injury,main-jam,engine,crew-killed,fuel,powerplant |
      | VTOL | legacy | cockpit,main-jam,engine,cockpit,fuel,powerplant |

  Scenario Outline: Damage critical dispatch 04 - candidate rebuild and filler exclusion
    Given a torso with candidate kinds <slots> in that order and all remaining slots empty
    When <requested> criticals repeatedly select eligible index zero
    Then destroyed slot indices are <destroyed> and no critical transfers to another section
    Examples:
      | slots | requested | destroyed |
      | CASE,LIFE_SUPPORT,TARGETING_COMPUTER | 2 | 1,2 |
      | MASC,SUPERCHARGER,ENDO_STEEL | 3 | none |
      | disabled-LIFE_SUPPORT,LIFE_SUPPORT | 2 | 0,1 |
      | damaged-weapon,LIFE_SUPPORT | 1 | 1 |

  Scenario: Damage critical dispatch 05 - do not truncate requested criticals at death
    Given an intact MECH head containing a cockpit and life support as the only eligible slots
    When two criticals repeatedly select eligible index zero
    Then cockpit and life support slots are destroyed and both critical requests are consumed
