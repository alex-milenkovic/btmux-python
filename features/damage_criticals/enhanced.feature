# Damage enhanced weapons 01 - severity boundaries; Damage enhanced weapons 02 - strict damaged slot threshold; Damage enhanced weapons 03 - firing consumes enhanced modifiers; Damage enhanced weapons 04 - damaged firing failure; Damage enhanced weapons 05 - legacy detail differs from consumer counts
Feature: Damage enhanced weapons
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage enhanced weapons 01 - severity boundaries
    Given a MECH <weapon_type> weapon with six slots and no previously damaged slots
    When an enhanced critical rolls <roll>
    Then selected slot damage kind is <kind> and the weapon is destroyed <destroyed>
    Examples:
      | weapon_type | roll | kind | destroyed |
      | energy | 2 | none-noticeable | False |
      | energy | 4 | moderate | False |
      | energy | 6 | focus | False |
      | energy | 8 | crystal | False |
      | energy | 9 | destroyed | True |
      | missile | 6 | ranging | False |
      | missile | 8 | missile-feed | False |
      | ballistic | 6 | barrel | False |
      | ballistic | 8 | ballistic-feed | False |

  Scenario Outline: Damage enhanced weapons 02 - strict damaged slot threshold
    Given a <unit_class> weapon with catalog critical size 4 and <damaged> already damaged slots
    When destruction is checked with increment <increment>
    Then weapon destruction is required <destroy>
    Examples:
      | unit_class | damaged | increment | destroy |
      | MECH | 1 | True | False |
      | MECH | 2 | True | True |
      | MECH | 2 | False | False |
      | GROUND | 0 | False | True |

  Scenario Outline: Damage enhanced weapons 03 - firing consumes enhanced modifiers
    Given a MECH energy weapon with base damage 10 heat 5 short range 3 and damaged flags <flags>
    When a successful ordinary shot is fired at range <range> with shot roll twelve
    Then critical BTH addition is <bth> target damage is <damage> and firing heat is <heat>
    Examples:
      | flags | range | bth | damage | heat |
      | moderate | 3 | 1 | 10 | 5 |
      | focus | 3 | 0 | 9 | 5 |
      | focus | 4 | 1 | 9 | 5 |
      | crystal | 3 | 0 | 10 | 6 |
      | moderate,focus,crystal | 4 | 2 | 9 | 6 |

  Scenario Outline: Damage enhanced weapons 04 - damaged firing failure
    Given a MECH weapon with one damaged <part> slot base damage 5 and ten rounds if nonenergy
    When the pilot fires with shot roll <roll>
    Then firing outcome is <outcome> shooter internal damage is <internal> and ammunition spent is <ammo>
    Examples:
      | part | roll | outcome | internal | ammo |
      | energy-crystal | 2 | exploded | 5 | 0 |
      | energy-crystal | 3 | ordinary | 0 | 0 |
      | ballistic-feed | 2 | exploded | 5 | 1 |
      | missile-feed | 2 | exploded | 5 | 1 |
      | ballistic-barrel | 2 | AMMOCRITJAMMED | 0 | 0 |

  Scenario Outline: Damage enhanced weapons 05 - legacy detail differs from consumer counts
    Given a MECH energy weapon with one damaged slot carrying flag <flag>
    When weaponstatus detail is requested
    Then detail damage hit count is <display_count> while actual firing modifier magnitude is one
    Examples:
      | flag | display_count |
      | moderate | 1 |
      | focus | 2 |
      | crystal | 4 |
