# Experience producers 01 - producer eligibility
# Experience producers 02 - perception caching and gain
# Experience producers 03 - new and old gates
# Experience producers 04 - pilot BV and speed factors
# Experience producers 05 - old movement bins
# Experience producers 06 - new arithmetic controls
# Experience producers 07 - old probability boundary
# Experience producers 08 - damage award routing
Feature: Experience producers
  Background:
    Given a connected in-character pilot and distinct live in-character enemy with valid source skill identities at wall time101 and last skill use0

  Scenario Outline: Experience producers 01 - producer eligibility
    Given producer <producer> with condition <condition> and reason <reason>
    When the source award operation runs
    Then durable gain request is <request>
    Examples:
      | producer | condition | reason | request |
      | tech | MECH | 0 | Technician-Battlemech:1 |
      | tech | no-unit | 3 | Technician-Weapons:3 |
      | techweapons | MECH | 2 | Technician-Weapons:2 |
      | computer | valid | 0 | Computer:1 |
      | computer | no-unit | 2 | none |
      | comm | valid | 0 | Comm-Conventional:1 |
      | comm | disconnected | 0 | none |
      | piloting | changedXY | 3 | Piloting-Battlemech:3 |
      | piloting | sameXY | 3 | none |
      | piloting | sameXY-addanyway | 3 | Piloting-Battlemech:3 |
      | spot | valid | 0 | Gunnery-Spotting:1 |
      | spot | wrong-pilot | 0 | none |
      | artillery | valid-gunpilot | 0 | Gunnery-Artillery:1 |
      | artillery | friendly | 0 | none |

  Scenario Outline: Experience producers 02 - perception caching and gain
    Given stored MechPer <per> character Perception BTH6 and modifier -2
    When source Roll is <roll>
    Then result is <success> stored MechPer is <stored> and requested XP is <xp>
    Examples:
      | per | roll | success | stored | xp |
      | 0 | 5 | False | 8 | 0 |
      | 0 | 6 | True | 8 | 1 |
      | 4 | 2 | True | 4 | 1 |
      | 5 | 2 | False | 5 | 0 |

  Scenario Outline: Experience producers 03 - new and old gates
    Given gun XP system <system> with condition <condition>
    When eligible damage would otherwise earn XP
    Then an award is <outcome>
    Examples:
      | system | condition | outcome |
      | new | BTH13 | rejected |
      | new | BTH2-bthmod-on | rejected |
      | new | BTH2-bthmod-off | accepted |
      | old | BTH2 | rejected |
      | new | NoGunXP | rejected |
      | old | NoGunXP | accepted |
      | new | all-sections-destroyed | rejected |
      | old | all-sections-destroyed | accepted |
      | new | same-team | rejected |
      | old | attacker-tons0 | rejected |
      | new | MECH-shoots-MW | rejected |
      | new | wrong-gunpilot | rejected |
      | new | target-destroyed | rejected |

  Scenario Outline: Experience producers 04 - pilot BV and speed factors
    Given gunnery <gunnery> piloting <piloting>
    When the source pilot BV factor is calculated
    Then factor is <factor>
    Examples:
      | gunnery | piloting | factor |
      | -1 | 0 | 2.25 |
      | 0 | 0 | 2.05 |
      | 4 | 5 | 1.0 |
      | 7 | 0 | 0.95 |
      | 8 | 0 | 0.15 |
      | 10 | 0 | -0.05 |

  Scenario Outline: Experience producers 05 - old movement bins
    Given effective maximum speed is <mp> MP
    When the old experience movement value is calculated
    Then value is <value>
    Examples:
      | mp | value |
      | 2 | 2 |
      | 2.01 | 3 |
      | 4 | 3 |
      | 4.01 | 4 |
      | 6 | 4 |
      | 6.01 | 5 |
      | 9 | 5 |
      | 9.01 | 6 |

  Scenario Outline: Experience producers 06 - new arithmetic controls
    Given equal BV and speeds weaponBV100 defaultBV100 defaultDamage10 damage10 baseMultiplier100 xp_modifier1 cap100 and no BTH or pilot-BV scaling
    When the source configuration is <config>
    Then awarded XP is <xp> and old-random gate draws are 0
    Examples:
      | config | xp |
      | ordinary | 10 |
      | missile-factor0.5 | 5 |
      | ammo-factor2 | 20 |
      | vrt7.5-factor-on | 5 |
      | perunit2 | 20 |
      | cap3 | 3 |

  Scenario Outline: Experience producers 07 - old probability boundary
    Given the final old multiplier times occurrences is <difficulty>
    When Number1to50 is <draw>
    Then awarded XP amount is <award>
    Examples:
      | difficulty | draw | award |
      | 20 | 20 | 1 |
      | 20 | 21 | 0 |
      | 5000 | 50 | 50 |
      | 6000 | 50 | 50 |

  Scenario Outline: Experience producers 08 - damage award routing
    Given a damage entry with <mode> original damage9 before personal conversion
    When the hit is applied through the ordinary shared damage path
    Then source award route is <route>
    Examples:
      | mode | route |
      | weapon | gun-original9 |
      | physical1 | piloting3 |
      | physical2 | none |
      | recursive-transfer | no-second-award |
      | rejected-safety | none |
