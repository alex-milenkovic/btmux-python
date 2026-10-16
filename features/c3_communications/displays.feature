# Communications displays 01 - identity
# Communications displays 02 - movement and arc
# Communications displays 03 - ammunition modes
# Communications displays 04 - fire letters
# Communications displays 05 - flags and report fields
Feature: Communications displays
  Background:
    Given registered source units with real names equipment and raw display output

  Scenario Outline: Communications displays 01 - identity
    Given viewer relation <relation> and NB visibility <visible>
    When Atlas with contact ID AB is identified
    Then identity text is <identity>
    Examples:
      | relation | visible | identity |
      | same-team | True | Atlas [ab] |
      | enemy | True | Atlas [AB] |
      | same-team | False | something [AB] |
      | enemy | False | something [AB] |
      | null-viewer | True | empty |
      | invalid-target | True | empty |
      | self-GetMechID | False | Atlas [AB] |

  Scenario Outline: Communications displays 02 - movement and arc
    Given presentation input <input>
    When the source display label is requested
    Then label is <label>
    Examples:
      | input | label |
      | MOVE_QUAD | QUAD |
      | MOVE_BIPED | BIPED |
      | MOVE_TRACK | TRACKED |
      | MOVE_WHEEL | WHEELED |
      | MOVE_HOVER | HOVER |
      | MOVE_VTOL | VTOL |
      | MOVE_FLY | FLY |
      | MOVE_HULL | HULL |
      | MOVE_SUB | SUBMARINE |
      | MOVE_FOIL | HYDROFOIL |
      | MOVE_NONE | Unknown |
      | MECH-forward-and-right | Forward |
      | MW-right | Right Arm |
      | BSUIT-left | Left Arm |
      | VEH_GROUND-right | Right Side |
      | VTOL-left | Left Side |
      | MECH-rear | Rear |
      | MECH-turret-only | NO |

  Scenario Outline: Communications displays 03 - ammunition modes
    Given ammunition mode <mode>
    When description and slot-wrapper ammo letter are displayed
    Then description token is <description> and letter is <letter>
    Examples:
      | mode | description | letter |
      | none | empty | space |
      | LBX | leading-space:Shotgun | L |
      | ARTEMIS | leading-space:Artemis IV | A |
      | NARC | leading-space:Narc | N |
      | NARC-on-NARC-weapon | leading-space:Explosive | E |
      | INARC_EXPLO | leading-space:iExplosive | X |
      | INARC_HAYWIRE | leading-space:Haywire | Y |
      | INARC_ECM | leading-space:ECM | E |
      | INARC_NEMESIS | leading-space:Nemesis | Z |
      | SWARM | leading-space:Swarm | W |
      | SWARM1 | leading-space:Swarm1 | 1 |
      | INFERNO | leading-space:Inferno | I |
      | CLUSTER | leading-space:Cluster | C |
      | SMOKE | leading-space:Smoke | S |
      | MINE | leading-space:Mine | M |
      | AC_AP | leading-space:Armor Piercing | R |
      | AC_FLECHETTE | leading-space:Flechette | F |
      | AC_INCENDIARY | leading-space:Incendiary | D |
      | AC_PRECISION | leading-space:Precision | P |
      | STINGER | leading-space:Stinger | T |
      | AC_CASELESS | leading-space:Caseless | U |
      | SGUIDED | leading-space:Sguided | G |
      | ATM_ER | leading-space:ExtendedRange | R |
      | ATM_HE | leading-space:HighExplosive | X |
      | MML_LRM | leading-space:LRM | # |
      | LBX+CLUSTER | leading-space:Shotgun | C |
      | INFERNO+SWARM | leading-space:Swarm | I |

  Scenario Outline: Communications displays 04 - fire letters
    Given fire mode <mode>
    When model and real slot wrapper are displayed
    Then letter is <letter>
    Examples:
      | mode | letter |
      | none | space |
      | HOTLOAD | H |
      | ULTRA | U |
      | RFAC | F |
      | GATTLING | G |
      | HEAT | H |
      | RAC_TWO | 2 |
      | RAC_FOUR | 4 |
      | RAC_SIX | 6 |
      | HOTLOAD+ULTRA | H |
      | ULTRA+GATTLING | U |
      | RAC_TWO+RAC_SIX | 2 |

  Scenario Outline: Communications displays 05 - flags and report fields
    Given display state <state>
    When source flags or network report is shown
    Then the observation is <observation>
    Examples:
      | state | observation |
      | fallen-BIPED | FALLEN |
      | fallen-TRACK | TRACK-DESTROYED |
      | fallen-WHEEL | AXLE-DESTROYED |
      | fallen-HOVER | LIFT-FAN-DESTROYED |
      | fallen-VTOL | ROTOR-DESTROYED |
      | fallen-FLY | ENGINE-DESTROYED |
      | fallen-HULL | ENGINE-ROOM-DESTROYED |
      | fallen-SUB | ENGINE-ROOM-DESTROYED |
      | fallen-FOIL | FOIL-DESTROYED |
      | burning-and-jellied | one-ON-FIRE-line |
      | light-on-and-illuminated | SEARCHLIGHT-ON-only |
      | own-level0-ECM-protected-and-disturbed | both-lines-in-source-order |
      | other-level1-ECM-protected | no-private-ECM-line |
      | level0-torso-right-and-left | both-torso-lines |
      | level1-torso-right-shutdown | SHUTDOWN-without-torso |
      | level2-destroyed-shutdown | neither-final-flag |
      | indent3-combat-safe | three-leading-spaces-before-color |
      | network-armor33-of100-internal2-of3 | armor33-internal66 |
      | network-zero-originals | armor0-internal0 |
      | contacts-live-ranges3,8-destroyed-range1 | destroyed1,live8,live3 |
      | contacts-own-something-network-clear | identified-name-and-status |
      | contacts-own-something-network-invisible | something-and-five-blank-statuses |
      | contacts-own-unseen-network-invisible | row-omitted |
      | status3-viewer-spinning-target-stationary | X |
