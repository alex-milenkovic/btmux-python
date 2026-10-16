# Construction sections 01 - default critical filling; Construction sections 02 - source section names; Construction sections 03 - short labels; Construction sections 04 - allocation guard
Feature: Construction sections
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction sections 01 - default critical filling
    Given a <unit> unit with all12 slots in section <section> containing junk type data firemode and ammomode
    When default critical filling runs for that section
    Then nonempty slot types are <layout> and every data firemode and ammomode is zero
    Examples:
      | unit | section | layout |
      | Mech | Head | 1:LifeSupport,2:Sensors,3:Cockpit,5:Sensors,6:LifeSupport |
      | Mech | Center_Torso | 1:Engine,2:Engine,3:Engine,4:Gyro,5:Gyro,6:Gyro,7:Gyro,8:Engine,9:Engine,10:Engine |
      | Mech | Left_Arm | 1:ShoulderOrHip,2:UpperActuator,3:LowerActuator,4:HandOrFootActuator |
      | Mech | Left_Torso | empty |
      | AeroFighter | Aft_Side | 1:HeatSink,2:HeatSink,3:Engine,4:HeatSink,5:HeatSink,6:HeatSink,7:HeatSink,8:HeatSink,9:HeatSink,10:HeatSink,11:Engine,12:HeatSink |
      | AeroFighter | Nose | empty |
      | Vehicle | Front_Side | empty |

  Scenario Outline: Construction sections 02 - source section names
    Given a <unit> unit moving by <move>
    When source section text <text> is resolved
    Then the zero-based location is <location>
    Examples:
      | unit | move | text | location |
      | Mech | Biped | Left_Arm | 0 |
      | Mech | Biped | la | 0 |
      | Mech | Biped | L | 5 |
      | Mech | Biped | R | 6 |
      | Mech | Biped | CT | 4 |
      | Mech | Biped | H | 7 |
      | Mech | Biped | empty | -1 |
      | Mech | Quad | Front_Left_Leg | 0 |
      | Mech | Quad | FL | 0 |
      | Mech | Quad | RL | 5 |
      | Battlesuit | Biped | Suit_8 | 7 |
      | Battlesuit | Biped | S8 | 7 |
      | AeroFighter | Fly | RW | 2 |
      | Aerodyne_DropShip | Fly | N | 5 |
      | Spheroid_DropShip | Fly | FR | 0 |
      | Vehicle | Track | F | 2 |
      | VTOL | VTOL | RO | 5 |
      | Mech | Biped | nonsense | -1 |

  Scenario Outline: Construction sections 03 - short labels
    Given a <unit> unit moving by <move>
    When location <location> is formatted as a short armor label
    Then the label is <label>
    Examples:
      | unit | move | location | label |
      | Mech | Biped | 0 | LA |
      | Mech | Quad | 0 | FLL |
      | Mech | Quad | 6 | RRL |
      | Battlesuit | Biped | 7 | S8 |
      | Aerodyne_DropShip | Fly | 2 | LRW |
      | Spheroid_DropShip | Fly | 0 | FRS |
      | VTOL | VTOL | 5 | R |
      | Vehicle | Track | 3 | AS |

  Scenario Outline: Construction sections 04 - allocation guard
    Given construction data is <state>
    When CheckData is requested
    Then success is <success> and notification count is <messages>
    Examples:
      | state | success | messages |
      | allocated | 1 | 0 |
      | null | 0 | 3 |
