# Per-tick updates 01 - turn cadence; Per-tick updates 02 - gravity injury; Per-tick updates 03 - stationary turret; Per-tick updates 04 - recycle completion; Per-tick updates 05 - fire terrain; Per-tick updates 06 - dropship notice throttle
Feature: Per-tick updates
  Background:
    Given a fresh heat session with standard ready units and independent clocks

  Scenario Outline: Per-tick updates 01 - turn cadence
    Given a running mech with gyro damage and posture <posture>
    When pilot maintenance runs at event tick <tick> with a successful piloting roll
    Then stability roll count is <checks>
    Examples:
      | posture | tick | checks |
      | UPRIGHT | 28 | 0 |
      | UPRIGHT | 29 | 1 |
      | UPRIGHT | 30 | 1 |
      | UPRIGHT | 31 | 0 |
      | FALLEN | 30 | 0 |
      | JUMPING | 30 | 0 |
      | OOD | 30 | 0 |

  Scenario Outline: Per-tick updates 02 - gravity injury
    Given an upright mech in special gravity with movement <movement> actual speed <speed> and base maximum speed 64.5 KPH
    When the turn-boundary gravity piloting check fails
    Then each intact leg takes <damage> internal damage and injured limbs number <limbs>
    And no gravity-induced fall occurs
    Examples:
      | movement | speed | damage | limbs |
      | BIPED | 65 | 1 | 2 |
      | BIPED | 75.25 | 2 | 2 |
      | QUAD | 75.25 | 2 | 4 |

  Scenario Outline: Per-tick updates 03 - stationary turret
    Given a stationary vehicle with automatic turret flag enabled hull facing <hull> turret facing 17 and a target at absolute bearing <bearing>
    And its turret eligibility state is <state>
    When the standard dispatcher advances 2 seconds without a movement event
    Then relative turret facing is <turret> and turret tracking marks LOS <los>
    Examples:
      | hull | bearing | state | turret | los |
      | 90 | 0 | READY | 270 | True |
      | 350 | 10 | READY | 20 | True |
      | 90 | 0 | JAMMED | 17 | False |
      | 90 | 0 | LOCKED | 17 | False |
      | 90 | 0 | DESTROYED_TURRET | 17 | False |
      | 90 | 0 | STOPPED | 17 | False |
      | 90 | 0 | UNCONSCIOUS | 17 | False |
      | 90 | 0 | BLINDED | 17 | False |

  Scenario Outline: Per-tick updates 04 - recycle completion
    Given a functional weapon with recycle 4 and temporary failure <failure>
    When event time advances <seconds> seconds and one heartbeat runs
    Then weapon and first-slot recycle are <remaining> temporary failure is <after> and completion notice is <notice>
    Examples:
      | failure | seconds | remaining | after | notice |
      | NONE | 0 | 4 | NONE | NONE |
      | NONE | 3 | 1 | NONE | NONE |
      | NONE | 4 | 0 | NONE | READY |
      | TEMPORARY | 3 | 1 | TEMPORARY | NONE |
      | TEMPORARY | 4 | 0 | NONE | OPERATIONAL |
      | TEMPORARY | 10 | 0 | NONE | OPERATIONAL |

  Scenario Outline: Per-tick updates 05 - fire terrain
    Given a live unit of class <class> movement <movement> enters cached FIRE terrain
    When movement reaches the fiery-death check
    Then the unit is destroyed <destroyed> with reason <reason>
    Examples:
      | class | movement | destroyed | reason |
      | MW | BIPED | True | HEAT |
      | MECH | BIPED | False | NONE |
      | VEH_GROUND | TRACK | False | NONE |
      | VTOL | VTOL | False | NONE |

  Scenario Outline: Per-tick updates 06 - dropship notice throttle
    Given a dropship last announced at event tick <last>
    When a throttled dropship descent notice is requested at event tick <now>
    Then the notice is emitted <emitted> and last notice tick is <stored>
    Examples:
      | last | now | emitted | stored |
      | 0 | 9 | False | 0 |
      | 0 | 10 | True | 10 |
      | 10 | 19 | False | 10 |
      | 10 | 20 | True | 20 |
      | 20 | 10 | True | 10 |
