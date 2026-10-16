# Damage vehicle effects 01 - temporary weapon criticals; Damage vehicle effects 02 - turret progression; Damage vehicle effects 03 - ammunition total and fallback; Damage vehicle effects 04 - rotor damage threshold; Damage vehicle effects 05 - crew stun overlap; Damage vehicle effects 06 - VTOL direct engine source branches; Damage vehicle effects 07 - cruise limit only changes desired speed; Damage vehicle effects 08 - main weapon weighted selection; Damage vehicle effects 09 - motive chart
Feature: Damage vehicle effects
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage vehicle effects 01 - temporary weapon criticals
    Given a ground vehicle with one working <weapon_type> weapon and ten rounds of ammunition where applicable
    When a weapon-jam critical draws recycle duration <duration>
    Then its temporary failure is <failure> firing is refused and recycle remaining is <duration>
    When the normal started engine advances <duration> ticks
    Then the weapon becomes operational and its ammunition has not been consumed by the critical
    Examples:
      | weapon_type | duration | failure |
      | ballistic | 60 | JAMMED |
      | energy | 120 | SHORTED |
      | missile | 90 | SHORTED |

  Scenario Outline: Damage vehicle effects 02 - turret progression
    Given an intact ground turret with jammed <jammed> and locked <locked>
    When a turret jam critical occurs
    Then turret jammed is <new_jammed> locked is <new_locked> and turning is refused
    Examples:
      | jammed | locked | new_jammed | new_locked |
      | False | False | True | False |
      | True | False | False | True |
      | False | True | False | True |

  Scenario Outline: Damage vehicle effects 03 - ammunition total and fallback
    Given a ground vehicle rear section with 100 internal and bins containing <rounds> rounds at five damage each plus a Gauss bin
    When the ammunition critical occurs with critical rolls below eight
    Then rear internal is <internal> eligible bin rounds are zero Gauss rounds are unchanged and fallback weapon destruction is <fallback>
    Examples:
      | rounds | internal | fallback |
      | 3 | 85 | False |
      | 0 | 100 | True |

  Scenario Outline: Damage vehicle effects 04 - rotor damage threshold
    Given an airborne VTOL with maximum speed <speed> and intact rotors
    When one rotor-damage critical occurs
    Then maximum speed is <remaining> rotor destroyed is <destroyed> and pending FALL events number <events>
    Examples:
      | speed | remaining | destroyed | events |
      | 21.5 | 10.75 | False | 0 |
      | 10.75 | 0 | True | 1 |
      | 5 | 0 | True | 1 |

  Scenario Outline: Damage vehicle effects 05 - crew stun overlap
    Given a vehicle stunned at tick zero and again at tick 30 with standard event dispatch
    When time advances to tick <time>
    Then crew stunned is <stunned> and ordinary firing is permitted <can_fire>
    Examples:
      | time | stunned | can_fire |
      | 59 | True | False |
      | 60 | True | False |
      | 89 | True | False |
      | 90 | False | True |

  Scenario Outline: Damage vehicle effects 06 - VTOL direct engine source branches
    Given an airborne VTOL at height five over <terrain> and a piloting roll that <roll>
    When the direct vehicle-engine critical occurs
    Then safe landing is <landed> and immediate MechFalls dispatch is <falls>
    Examples:
      | terrain | roll | landed | falls |
      | GRASSLAND | passes | True | False |
      | GRASSLAND | fails | False | False |
      | ROAD | passes | True | False |
      | BUILDING | passes | True | False |
      | ROUGH | passes | False | True |

  Scenario Outline: Damage vehicle effects 07 - cruise limit only changes desired speed
    Given a ground vehicle with maximum speed 64.5 current speed 60 and desired speed <desired>
    When the crew-stun critical applies its cruise limit
    Then current speed remains 60 and desired speed is <wanted>
    Examples:
      | desired | wanted |
      | 60 | 42.5666666667 |
      | 40 | 40 |
      | -50 | -50 |

  Scenario Outline: Damage vehicle effects 08 - main weapon weighted selection
    Given two functional weapons in different sections with enumeration weights <weights>
    When the main weapon jam operation executes
    Then selected weapon ordinal is <selected> and no recovery timer is scheduled
    Examples:
      | weights | selected |
      | 5,9 | 2 |
      | 9,5 | 1 |
      | 9,9 | 1 |
      | 0,0 | none |

  Scenario Outline: Damage vehicle effects 09 - motive chart
    Given a moving <movement> vehicle with maximum speed 64.5 and no motive damage
    When motive roll <roll> is applied without an extra modifier
    Then maximum speed is <speed> piloting penalty is <penalty> and immobilized is <immobile>
    Examples:
      | movement | roll | speed | penalty | immobile |
      | TRACK | 7 | 64.5 | 0 | False |
      | TRACK | 8 | 64.5 | 1 | False |
      | TRACK | 10 | 53.75 | 2 | False |
      | TRACK | 12 | 0 | 0 | True |
      | WHEEL | 6 | 64.5 | 1 | False |
      | HOVER | 6 | 53.75 | 2 | False |
      | FOIL | 8 | 0 | 0 | True |
