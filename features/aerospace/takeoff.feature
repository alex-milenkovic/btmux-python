# Aerospace takeoff 01 - launch clocks
# Aerospace takeoff 02 - launch refusals
# Aerospace takeoff 03 - countdown effects
# Aerospace takeoff 04 - abort and recheck
Feature: Aerospace takeoff
  Background:
    Given a registered craft on a clear level landing zone with real event scheduling

  Scenario Outline: Aerospace takeoff 01 - launch clocks
    Given landed class <class> and speed <speed> with launch argument <argument>
    When the pilot starts takeoff and advances the launch clock
    Then liftoff occurs at <delay> seconds with flight state <state>
    Examples:
      | class | speed | argument | delay | state |
      | VTOL | 0 | empty | 1 | Z1;vertical60;desired0 |
      | AERO | 32.25 | empty | 11 | Z1;angle90;desired40 |
      | DS | 0 | empty | 301 | Z1;angle90;desired40 |
      | SPHEROID_DS | 0 | empty | 301 | Z1;angle90;desired40 |
      | AERO | 32.25 | wizard:2 | 3 | Z1;angle90;desired40 |
      | DS | 0 | wizard:-2 | 1 | Z1;angle90;desired40 |
      | AERO | 32.25 | 0 | 11 | Z1;angle90;desired40 |

  Scenario Outline: Aerospace takeoff 02 - launch refusals
    Given takeoff fixture <fixture>
    When takeoff is requested
    Then the observation is <observation>
    Examples:
      | fixture | observation |
      | AERO;speed32.24 | too-slow;no-event |
      | AERO;speed32.25;fuel0 | out-of-fuel;no-event |
      | VTOL;fuel0;fusion-free | accepted |
      | VTOL;fuel0;fusion-free;ICE | out-of-fuel;no-event |
      | VTOL;rotor-destroyed | rotor-dead;no-event |
      | DS;fallen | engines-dead;no-event |
      | DS;maximum10.75 | engines-dead;no-event |
      | DS;fortified | fortified;no-event |
      | DS;airborne | not-landed;no-event |
      | DS;underground | ceiling;no-event |
      | DS;stopped | reactor-off;no-event |
      | DS;argument2;nonwizard | insufficient-access;no-event |
      | MECH | unsupported-type;no-event |
      | DS;already-taking-off | already-initiated;one-event |

  Scenario Outline: Aerospace takeoff 03 - countdown effects
    Given a dropship countdown callback has count <count>
    When one callback runs on the real queue
    Then the observation is <observation>
    Examples:
      | count | observation |
      | 75 | quarter-glow;next74 |
      | 10 | countdown10;engines-ready;next9 |
      | 6 | no-countdown6;scramble2;next5 |
      | 5 | countdown5;next4 |
      | 2 | countdown2;plasma;scramble4;next1 |
      | 1 | countdown1;blast400;next0 |
      | 0 | liftoff;no-takeoff-event |

  Scenario Outline: Aerospace takeoff 04 - abort and recheck
    Given a pending launch has transition <transition>
    When the transition and remaining clock execute
    Then the observation is <observation>
    Examples:
      | transition | observation |
      | AERO-speed-falls-below32.25-before-count0 | too-slow;still-landed;no-launch-event |
      | DS-speed0-at-count0 | liftoff |
      | land-before-first-callback | aborted;no-liftoff-or-blast |
      | VTOL-fuel0-before-land-abort | landing-fuel-refusal;launch-still-pending |
      | hide-and-spin-then-launch | hidden-cleared-at-start;spin-cleared-at-liftoff;one-move-event |
