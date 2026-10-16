# Damage mobility 01 - arm actuator precedence; Damage mobility 02 - global leg normalization; Damage mobility 03 - hip belongs to its own leg; Damage mobility 04 - gyro live stages; Damage mobility 05 - signed speed correction
Feature: Damage mobility
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage mobility 01 - arm actuator precedence
    Given an intact biped arm with destroyed actuator set <actuators>
    When damaged-location normalization runs twice
    Then arm weapon BTH is <bth> after each run
    Examples:
      | actuators | bth |
      | hand | 0 |
      | upper | 1 |
      | upper,lower | 2 |
      | shoulder,upper,lower | 4 |

  Scenario Outline: Damage mobility 02 - global leg normalization
    Given a <chassis> with template max speed 64.5 and <lost> destroyed legs without other criticals
    When complete actuator normalization runs twice
    Then max speed is <speed> pilot skill base is <psr> and fallen is <fallen> after each run
    Examples:
      | chassis | lost | speed | psr | fallen |
      | biped | 0 | 64.5 | 0 | False |
      | biped | 1 | 10.75 | 5 | False |
      | biped | 2 | 0 | 10 | True |
      | quad | 1 | 53.75 | 2 | False |
      | quad | 2 | 10.75 | 7 | False |
      | quad | 3 | 0 | 2 | True |
      | quad | 4 | 0 | 2 | True |

  Scenario Outline: Damage mobility 03 - hip belongs to its own leg
    Given a biped with template max speed 64.5 a destroyed left hip and right leg actuator state <right>
    When complete actuator normalization runs twice
    Then max speed is <speed> and pilot skill base is <psr> after each run
    Examples:
      | right | speed | psr |
      | intact | 32.25 | 2 |
      | upper-destroyed | 21.5 | 3 |
      | hip-destroyed | 0 | 4 |

  Scenario Outline: Damage mobility 04 - gyro live stages
    Given a standing MECH with gyro <gyro> and all requested piloting rolls passing
    When <hits> distinct gyro slots take criticals from an attacker
    Then hardened damage is <hard> gyro damaged is <damaged> gyro destroyed is <destroyed> and actual fallen state is <fallen>
    Examples:
      | gyro | hits | hard | damaged | destroyed | fallen |
      | standard | 1 | False | True | False | False |
      | standard | 2 | False | True | True | True |
      | hardened | 1 | True | False | False | False |
      | hardened | 2 | True | True | False | False |
      | hardened | 3 | True | True | True | True |

  Scenario Outline: Damage mobility 05 - signed speed correction
    Given cargo-adjusted maximum 30 current speed <current> and desired speed <desired>
    When damage speed correction runs
    Then current speed is <actual> and desired speed is <wanted>
    Examples:
      | current | desired | actual | wanted |
      | 40 | 40 | 30 | 30 |
      | -40 | -40 | -20 | -20 |
      | 40 | -40 | -20 | -20 |
      | 15 | -10 | 15 | -10 |
