# Damage hit locations 01 - MECH FASA tables; Damage hit locations 02 - physical tables; Damage hit locations 03 - swarm chart; Damage hit locations 04 - live member helper and table fallthrough; Damage hit locations 05 - normal target selection priority; Damage hit locations 06 - NARC skips destroyed structure; Damage hit locations 07 - exile head stun lifecycle
Feature: Damage hit locations
  Background:
    Given a fresh damage session with source defaults and event time zero

  Scenario Outline: Damage hit locations 01 - MECH FASA tables
    Given a MECH using FASA hit locations from <side> with exile stun disabled
    When hit-location rolls two through twelve are evaluated on independent fixtures
    Then ordered locations are <locations> and only roll two marks a critical
    Examples:
      | side | locations |
      | FRONT | CTORSO,RARM,RARM,RLEG,RTORSO,CTORSO,LTORSO,LLEG,LARM,LARM,HEAD |
      | BACK | CTORSO,RARM,RARM,RLEG,RTORSO,CTORSO,LTORSO,LLEG,LARM,LARM,HEAD |
      | LEFT | LTORSO,LLEG,LARM,LARM,LLEG,LTORSO,CTORSO,RTORSO,RARM,RLEG,HEAD |
      | RIGHT | RTORSO,RLEG,RARM,RARM,RLEG,RTORSO,CTORSO,LTORSO,LARM,LLEG,HEAD |

  Scenario Outline: Damage hit locations 02 - physical tables
    Given a <chassis> target viewed from <side>
    When <attack> location rolls one through six are evaluated
    Then ordered locations are <locations>
    Examples:
      | chassis | side | attack | locations |
      | biped | FRONT | punch | LARM,LTORSO,CTORSO,RTORSO,RARM,HEAD |
      | biped | LEFT | punch | LTORSO,LTORSO,CTORSO,LARM,LARM,HEAD |
      | biped | RIGHT | punch | RTORSO,RTORSO,CTORSO,RARM,RARM,HEAD |
      | quad | FRONT | punch | LARM,LTORSO,CTORSO,RTORSO,RARM,HEAD |
      | quad | BACK | punch | LLEG,LTORSO,CTORSO,RTORSO,RLEG,HEAD |
      | quad | LEFT | punch | LTORSO,LTORSO,CTORSO,LARM,LLEG,HEAD |
      | quad | RIGHT | punch | RTORSO,RTORSO,CTORSO,RARM,RLEG,HEAD |
      | biped | FRONT | kick | RLEG,RLEG,RLEG,LLEG,LLEG,LLEG |
      | biped | LEFT | kick | LLEG,LLEG,LLEG,LLEG,LLEG,LLEG |
      | biped | RIGHT | kick | RLEG,RLEG,RLEG,RLEG,RLEG,RLEG |
      | quad | FRONT | kick | RARM,RARM,RARM,LARM,LARM,LARM |
      | quad | BACK | kick | RLEG,RLEG,RLEG,LLEG,LLEG,LLEG |
      | quad | LEFT | kick | LARM,LARM,LARM,LLEG,LLEG,LLEG |
      | quad | RIGHT | kick | RARM,RARM,RARM,RLEG,RLEG,RLEG |

  Scenario Outline: Damage hit locations 03 - swarm chart
    Given a BA unit swarming a MECH without partial cover
    When the swarm location roll is <roll>
    Then the hit location is <location> rear flag is <rear> and critical flag is True
    Examples:
      | roll | location | rear |
      | 2 | HEAD | False |
      | 3 | CTORSO | True |
      | 4 | RTORSO | True |
      | 5 | RTORSO | False |
      | 6 | RARM | False |
      | 7 | CTORSO | False |
      | 8 | LARM | False |
      | 9 | LTORSO | False |
      | 10 | LTORSO | True |
      | 11 | CTORSO | True |
      | 12 | HEAD | False |

  Scenario Outline: Damage hit locations 04 - live member helper and table fallthrough
    Given a BA unit with live member indices <members>
    When the live-member helper uses choice zero and the FASA front table uses roll seven
    Then helper location is <helper_location> and FASA location index is <table_location>
    Examples:
      | members | helper_location | table_location |
      | 1,4 | 1 | 4 |
      | 2 | 2 | 4 |
      | none | -1 | 0 |

  Scenario Outline: Damage hit locations 05 - normal target selection priority
    Given an attacker of class <attacker> and target MECH with cover <cover> swarmed <swarmed> and attacker height difference <height>
    When a front hit uses physical location roll one and normal location roll seven
    Then selected location is <location> and selected table is <table>
    Examples:
      | attacker | cover | swarmed | height | location | table |
      | MW | False | False | 0 | RLEG | kick |
      | MW | True | False | 0 | LARM | punch |
      | MW | False | False | 1 | CTORSO | normal |
      | BSUIT | False | True | 0 | CTORSO | swarm |
      | BSUIT | True | True | 0 | LARM | punch |

  Scenario Outline: Damage hit locations 06 - NARC skips destroyed structure
    Given a rear NARC hit initially selects <location> on class <unit_class> with dead sections <dead>
    When the pod resolves its attachment location
    Then attachment location is <attached> and rear marker is <rear>
    Examples:
      | location | unit_class | dead | attached | rear |
      | LARM | MECH | LARM | LTORSO | True |
      | LARM | MECH | LARM,LTORSO | CTORSO | True |
      | LARM | MECH | LARM,LTORSO,CTORSO | none | False |
      | FSIDE | GROUND | none | BSIDE | False |

  Scenario Outline: Damage hit locations 07 - exile head stun lifecycle
    Given a started MECH moving above walking speed and exile mode <mode>
    When a front head hit rerolls punch location <roll> and time advances <time> ticks
    Then replacement location is <location> and MECH stunned is <stunned>
    Examples:
      | mode | roll | time | location | stunned |
      | 1 | 1 | 0 | LARM | True |
      | 1 | 1 | 9 | LARM | True |
      | 1 | 1 | 10 | LARM | False |
      | 1 | 6 | 0 | HEAD | False |
      | 2 | 1 | 0 | LARM | False |
