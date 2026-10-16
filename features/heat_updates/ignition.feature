# Dumping ammo ignition 01 - rear hit routing; Dumping ammo ignition 02 - one-round damage; Dumping ammo ignition 03 - selected stream
Feature: Dumping ammo ignition
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Dumping ammo ignition 01 - rear hit routing
    Given a mech dumping a bin of 3 rounds each causing 10 damage
    And all armor and internal values are sufficient to survive both hits
    When a 1 point hit strikes <location> from <arc> with cause <cause>
    Then extra rear armor damage is <damage> ammo remaining is <remaining> and dumping is <pending>
    Examples:
      | location | arc | cause | pending | remaining | damage |
      | CT | REAR | WEAPON | False | 2 | 10 |
      | LT | REAR | WEAPON | False | 2 | 10 |
      | RT | REAR | WEAPON | False | 2 | 10 |
      | CT | FRONT | WEAPON | True | 3 | 0 |
      | LLEG | REAR | WEAPON | True | 3 | 0 |
      | CT | REAR | INTERNAL_EFFECT | True | 3 | 0 |

  Scenario Outline: Dumping ammo ignition 02 - one-round damage
    Given the only dumping bin has 3 rounds for weapon category <category> base damage <base> and maximum salvo <salvo>
    When a weapon hit ignites that dumping stream at a surviving rear torso
    Then extra rear armor damage is <damage> ammo remaining is <remaining> and dumping is <pending>
    Examples:
      | category | base | salvo | damage | remaining | pending |
      | BALLISTIC | 10 | 1 | 10 | 2 | False |
      | MISSILE | 2 | 6 | 12 | 2 | False |
      | ARTILLERY | 5 | 4 | 20 | 2 | False |
      | MISSILE_NO_TABLE | 2 | 1 | 2 | 2 | False |
      | BALLISTIC | 0 | 1 | 0 | 3 | True |

  Scenario Outline: Dumping ammo ignition 03 - selected stream
    Given LT slot 1 has 3 rounds of A doing 10 damage and RT slot 1 has 4 rounds of B doing 5 damage
    When dump selector <selector> is requested and a rear torso weapon hit selects candidate <index>
    Then A has <a> rounds B has <b> rounds and extra rear armor damage is <damage>
    And no dumping event remains
    Examples:
      | selector | index | a | b | damage |
      | all | 0 | 3 | 3 | 5 |
      | all | 1 | 2 | 4 | 10 |
      | LT | 0 | 2 | 4 | 10 |
      | WEAPON_A | 0 | 2 | 4 | 10 |
      | RT 1 | 0 | 3 | 3 | 5 |
