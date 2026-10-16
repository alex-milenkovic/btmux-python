# Personal combat 01 - damage scale
# Personal combat 02 - location projection
# Personal combat 03 - all armor profiles
# Personal combat 04 - armor luck and domains
# Personal combat 05 - protection intersection
Feature: Personal combat
  Background:
    Given source personal armor metadata with strict finite Number streams and C integer arithmetic

  Scenario Outline: Personal combat 01 - damage scale
    Given target <target> weapon <weapon> and damage <damage>
    When conversion <direction> draws <draws>
    Then damage becomes <result>
    Examples:
      | target | weapon | damage | direction | draws | result |
      | MECH | PC | 250 | to-normal | 50 | 3 |
      | MECH | PC | 250 | to-normal | 51 | 2 |
      | MECH | PC | 200 | to-normal | 1 | 2 |
      | MW | PC | 250 | to-normal | none | 250 |
      | MECH | none | 250 | to-normal | none | 250 |
      | MW | normal | 2 | to-personal | 80,130 | 210 |
      | MW | PC | 2 | to-personal | none | 2 |
      | MECH | normal | 2 | to-personal | none | 2 |
      | MW | none | 0 | to-personal | none | 0 |
      | MW | none | -1 | to-personal | none | 0 |

  Scenario Outline: Personal combat 02 - location projection
    Given personal hit location <location>
    When armor location is resolved
    Then location is <result>
    Examples:
      | location | result |
      | LT | CT |
      | RT | CT |
      | LA | RA |
      | LL | RL |
      | RA | RA |
      | RL | RL |
      | HEAD | HEAD |
      | CT | CT |

  Scenario Outline: Personal combat 03 - all armor profiles
    Given armor location <location> code <code> damage100 and a fully defended PC weapon
    When variation100 weak-point2 half1 and block1 are drawn
    Then resulting damage is <damage>
    Examples:
      | location | code | damage |
      | HEAD | 1 | 85 |
      | HEAD | 2 | 70 |
      | RA | 1 | 90 |
      | RA | 2 | 70 |
      | RL | 1 | 75 |
      | RL | 2 | 50 |
      | CT | 1 | 70 |
      | CT | 2 | 60 |
      | CT | 3 | 50 |
      | CT | 4 | 60 |
      | CT | 5 | 60 |
      | CT | 6 | 50 |
      | CT | 7 | 40 |
      | CT | 8 | 30 |

  Scenario Outline: Personal combat 04 - armor luck and domains
    Given CT armor6 input damage <damage> and source condition <condition>
    When personal armor is applied
    Then resulting damage is <result> and Number call sequence is <calls>
    Examples:
      | damage | condition | result | calls |
      | 100 | normal | 50 | variation-weak-half-block |
      | 100 | double | 140 | variation-weak-double-block |
      | 100 | bypass | 100 | variation-weak-bypass-block |
      | 100 | half | 25 | variation-weak-half-block |
      | -100 | normal | -50 | variation-weak-half-block |
      | 100 | id-minus2 | 50 | weak-half-block |
      | 100 | unknown-armor9 | 100 | variation-weak-half |
      | 100 | armor0 | 100 | variation |
      | 100 | nonMW | 100 | variation |
      | 0 | bypass | undefined-domain | variation-weak-bypass-block |

  Scenario Outline: Personal combat 05 - protection intersection
    Given source armor <armor> against weapon <weapon> with damage100
    When normal variation and luck draws are used
    Then resulting damage is <result> and block draw count is <draws>
    Examples:
      | armor | weapon | result | draws |
      | Helmet | PC_SHAR | 100 | 0 |
      | Helmet | PC_HEAT | 85 | 1 |
      | FlakVest | PC_IMPA | 100 | 0 |
      | FlakVest | PC_SHAR | 70 | 1 |
      | FlakVest | normal | 70 | 1 |
