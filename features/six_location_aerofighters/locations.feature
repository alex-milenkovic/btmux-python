# Six location fighter hit tables 01 - active profiles
# Six location fighter hit tables 02 - critical proof
# Six location fighter hit tables 03 - normal dispatch
Feature: Six location fighter hit tables
  Background:
    Given a fresh fighter with viable armor equipment and deterministic dice for every table case

  Scenario Outline: Six location fighter hit tables 01 - active profiles
    When legacy and FASA independently select side <side> roll <roll>
    Then both return <location> and the pre-damage effect is <effect>
    Examples:
      | side | roll | location | effect |
      | FRONT | 2 | Cockpit | none |
      | FRONT | 3 | Nose | weapon90 |
      | FRONT | 4 | Fuselage | none |
      | FRONT | 5 | Right_Wing | none |
      | FRONT | 6 | Nose | none |
      | FRONT | 7 | Nose | none |
      | FRONT | 8 | Nose | none |
      | FRONT | 9 | Left_Wing | none |
      | FRONT | 10 | Fuselage | inert-bomb-hook |
      | FRONT | 11 | Nose | weapon90 |
      | FRONT | 12 | Cockpit | none |
      | LEFTSIDE | 2 | Cockpit | none |
      | LEFTSIDE | 3 | Left_Wing | weapon99 |
      | LEFTSIDE | 4 | Engine | sink90 |
      | LEFTSIDE | 5 | Fuselage | inert-bomb-hook |
      | LEFTSIDE | 6 | Left_Wing | none |
      | LEFTSIDE | 7 | Fuselage | none |
      | LEFTSIDE | 8 | Left_Wing | none |
      | LEFTSIDE | 9 | Nose | none |
      | LEFTSIDE | 10 | Engine | sink90 |
      | LEFTSIDE | 11 | Left_Wing | weapon99 |
      | LEFTSIDE | 12 | Engine | deferred99 |
      | RIGHTSIDE | 2 | Cockpit | none |
      | RIGHTSIDE | 3 | Right_Wing | weapon99 |
      | RIGHTSIDE | 4 | Engine | sink90 |
      | RIGHTSIDE | 5 | Fuselage | inert-bomb-hook |
      | RIGHTSIDE | 6 | Right_Wing | none |
      | RIGHTSIDE | 7 | Fuselage | none |
      | RIGHTSIDE | 8 | Right_Wing | none |
      | RIGHTSIDE | 9 | Nose | none |
      | RIGHTSIDE | 10 | Engine | sink90 |
      | RIGHTSIDE | 11 | Right_Wing | weapon99 |
      | RIGHTSIDE | 12 | Engine | deferred99 |
      | BACK | 2 | Engine | deferred90 |
      | BACK | 3 | Fuselage | control |
      | BACK | 4 | Fuselage | sink90 |
      | BACK | 5 | Right_Wing | none |
      | BACK | 6 | Engine | none |
      | BACK | 7 | Fuselage | sink90 |
      | BACK | 8 | Engine | none |
      | BACK | 9 | Left_Wing | none |
      | BACK | 10 | Fuselage | sink90 |
      | BACK | 11 | Fuselage | control |
      | BACK | 12 | Engine | deferred90 |

  Scenario Outline: Six location fighter hit tables 02 - critical proof
    When the critproof table selects side <side> roll <roll>
    Then it returns <location> without table effects or critical chance draws
    Examples:
      | side | roll | location |
      | FRONT | 2 | Cockpit |
      | FRONT | 3 | Nose |
      | FRONT | 4 | Fuselage |
      | FRONT | 5 | Right_Wing |
      | FRONT | 6 | Nose |
      | FRONT | 7 | Nose |
      | FRONT | 8 | Nose |
      | FRONT | 9 | Left_Wing |
      | FRONT | 10 | Fuselage |
      | FRONT | 11 | Nose |
      | FRONT | 12 | Cockpit |
      | LEFTSIDE | 2 | Cockpit |
      | LEFTSIDE | 3 | Left_Wing |
      | LEFTSIDE | 4 | Engine |
      | LEFTSIDE | 5 | Fuselage |
      | LEFTSIDE | 6 | Left_Wing |
      | LEFTSIDE | 7 | Fuselage |
      | LEFTSIDE | 8 | Left_Wing |
      | LEFTSIDE | 9 | Nose |
      | LEFTSIDE | 10 | Engine |
      | LEFTSIDE | 11 | Left_Wing |
      | LEFTSIDE | 12 | Engine |
      | RIGHTSIDE | 2 | Cockpit |
      | RIGHTSIDE | 3 | Right_Wing |
      | RIGHTSIDE | 4 | Engine |
      | RIGHTSIDE | 5 | Fuselage |
      | RIGHTSIDE | 6 | Right_Wing |
      | RIGHTSIDE | 7 | Fuselage |
      | RIGHTSIDE | 8 | Right_Wing |
      | RIGHTSIDE | 9 | Nose |
      | RIGHTSIDE | 10 | Engine |
      | RIGHTSIDE | 11 | Right_Wing |
      | RIGHTSIDE | 12 | Engine |
      | BACK | 2 | Engine |
      | BACK | 3 | Fuselage |
      | BACK | 4 | Fuselage |
      | BACK | 5 | Right_Wing |
      | BACK | 6 | Engine |
      | BACK | 7 | Fuselage |
      | BACK | 8 | Engine |
      | BACK | 9 | Left_Wing |
      | BACK | 10 | Fuselage |
      | BACK | 11 | Fuselage |
      | BACK | 12 | Engine |

  Scenario Outline: Six location fighter hit tables 03 - normal dispatch
    Given the fighter table configuration <configuration>
    When ordinary combat requests a hit location
    Then the selected historical profile is <profile>
    Examples:
      | configuration | profile |
      | FASA-off | legacy |
      | FASA-on | FASA |
      | critproof-with-FASA-on | critproof |
      | critproof-with-FASA-off | critproof |
