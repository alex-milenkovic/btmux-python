# Repair economy access and parsing 01 command gates
# Repair economy access and parsing 02 parser boundaries
Feature: Repair economy access and parsing

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy access and parsing 01 command gates
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | Tech false and Wiz true | fixinternal CT | refuse clearance before dice or writes |
      | Tech true startup true stall true | fixinternal CT | refuse startup |
      | Tech true started true stall true | fixinternal CT | refuse started |
      | Tech true shutdown nonDS stall false | fixinternal CT | refuse stall |
      | Tech true shutdown DS stall false | fixinternal Nose | pass shared C gate |
      | Tech true Wiz true started true stall false | fixinternal CT | pass shared C gate |
      | Tech true shutdown limitedrepairs 0 stall false | reload CT 1 | pass shared D gate |
      | Tech true shutdown limitedrepairs 1 stall false | reload CT 1 | refuse stall |
      | Tech true shutdown pending minutes 599 | replacepart CT 1 | pass fatigue gate |
      | Tech true Wiz true pending minutes 600 | replacepart CT 1 | refuse fatigue |
      | IC true Wiz false Tech true | toggletype CT 1 - | refuse IC wizard gate |
      | IC false Wiz false Tech false | toggletype CT 1 - | fill valid ammo immediately |
      | Tech true pending minutes 600 stall true | fixextra | immediate existing restoration without dice |
      | Tech true pending minutes 600 stall true template missing | magic | explicit template dependency without invented restoration |

  Scenario Outline: Repair economy access and parsing 02 parser boundaries
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | Mech CT with twelve slots | parsepart CT 1 | location4 position0 |
      | Mech CT with twelve slots | parsepart CT 12 | location4 position11 |
      | Mech CT with twelve slots | parsepart CT 13 | error -2 |
      | Mech CT with twelve slots | parsepart CT 0 | error -2 |
      | Mech CT with twelve slots | parsepart BAD 1 | error -1 |
      | Mech CT with twelve slots | parsepart CT 2junk | location4 position1 |
      | rear-aware armor parser | parsepart CT rear | location12 |
      | rear-aware armor parser | parsepart LT R | location10 |
      | optional-extra part parser | parsepart CT 2 cluster | extra c |
      | optional-extra part parser | parsepart CT 2 | extra zero |
      | AERO Cockpit with five slots | parsepart Cockpit 5 | location4 position4 |
      | AERO Cockpit with five slots | parsepart Cockpit 6 | error -2 |
      | first global gun destroyed | parsegun 0 | locate destroyed mount |
      | first global gun recycling | parsegun 0 | locate recycling mount |
      | Mech CT weapon begins slot3 width2 | validgun CT 4 | false |
      | Mech CT weapon begins slot3 width2 | validgun CT 3 | true |
      | brand-enabled CT slot3 weapon | parsegun CT 13 Brand | error -4 |
      | brand-enabled CT slot3 weapon | parsegun CT 3 MissingBrand | error -2 |
      | brand-enabled CT slot3 weapon | parsegun CT 3 OtherPartBrand | error -3 |
