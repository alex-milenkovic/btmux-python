# Construction weights 01 - suspension lookup; Construction weights 02 - engine order and rounding; Construction weights 03 - per critical construction mass; Construction weights 04 - simple mech totals; Construction weights 05 - ammo pile truncation; Construction weights 06 - weight cache; Construction weights 07 - vehicle totals; Construction weights 08 - armor contribution rounding
Feature: Construction weights
  Background:
    Given a fresh construction session with explicit source defaults

  Scenario Outline: Construction weights 01 - suspension lookup
    Given a vehicle of <tons> tons moving by <move>
    When its suspension factor is requested
    Then the factor is <factor>
    Examples:
      | tons | move | factor |
      | 10 | Track | 0 |
      | 10 | Wheel | 20 |
      | 10 | Hull | 30 |
      | 10 | Sub | 30 |
      | 10 | Hover | 40 |
      | 11 | Hover | 85 |
      | 20 | Hover | 85 |
      | 21 | Hover | 130 |
      | 30 | Hover | 130 |
      | 31 | Hover | 175 |
      | 40 | Hover | 175 |
      | 41 | Hover | 235 |
      | 10 | VTOL | 50 |
      | 11 | VTOL | 95 |
      | 20 | VTOL | 95 |
      | 21 | VTOL | 140 |
      | 10 | Foil | 60 |
      | 11 | Foil | 105 |
      | 30 | Foil | 150 |
      | 40 | Foil | 195 |
      | 50 | Foil | 255 |
      | 60 | Foil | 300 |
      | 70 | Foil | 345 |
      | 80 | Foil | 390 |
      | 90 | Foil | 435 |
      | 91 | Foil | 480 |
      | 10 | Fly | 0 |

  Scenario Outline: Construction weights 02 - engine order and rounding
    Given a <unit> moving by <move> has stored engine rating <rating> and engine tech <tech>
    When construction engine weight is calculated
    Then calculated weight in1024ths is <weight>
    Examples:
      | unit | move | rating | tech | weight |
      | Mech | Biped | 200 | standard | 8704 |
      | Mech | Biped | 200 | XL | 4608 |
      | Mech | Biped | 200 | XXL | 3072 |
      | Mech | Biped | 200 | Light | 6656 |
      | Mech | Biped | 200 | Compact | 13312 |
      | Mech | Biped | 200 | ICE+XL | 17408 |
      | Mech | Biped | 201 | standard | 0 |
      | Vehicle | Track | 200 | standard | 13312 |
      | Vehicle | Wheel | 220 | standard | 13312 |
      | Vehicle | Track | 200 | XL | 6656 |
      | Vehicle | Track | 200 | ICE | 17408 |
      | Mech | Biped | 500 | standard | 473600 |
      | Mech | Biped | 0 | standard | 0 |

  Scenario Outline: Construction weights 03 - per critical construction mass
    Given a <unit> of <tons> tons has tech <tech>
    When construction crit weight is requested for <part>
    Then calculated weight in1024ths is <weight>
    Examples:
      | unit | tons | tech | part | weight |
      | Mech | 50 | standard | HeatSink | 1024 |
      | Mech | 50 | DoubleHS | HeatSink | 341 |
      | Mech | 50 | Clan | HeatSink | 512 |
      | Vehicle | 50 | Clan | HeatSink | 1024 |
      | Mech | 55 | standard | JumpJet | 512 |
      | Mech | 56 | standard | JumpJet | 1024 |
      | Mech | 85 | standard | JumpJet | 1024 |
      | Mech | 86 | standard | JumpJet | 2048 |
      | Mech | 50 | standard | Sword | 640 |
      | Mech | 50 | standard | BloodhoundProbe | 682 |
      | Vehicle | 50 | standard | BloodhoundProbe | 2048 |
      | Mech | 50 | standard | C3i | 1280 |
      | Vehicle | 50 | standard | C3i | 2560 |
      | Mech | 50 | standard | Ecm | 768 |
      | Mech | 50 | Clan | Ecm | 1024 |
      | Vehicle | 50 | standard | Ecm | 1536 |
      | Mech | 50 | standard | Case | 512 |
      | Mech | 50 | standard | Engine | 0 |
      | Mech | 50 | standard | Ammo_IS.AC/5 | 512 |

  Scenario Outline: Construction weights 04 - simple mech totals
    Given a 50-ton mech has engine200 original internal100 current internal100 no armor no equipment and ten original sinks
    And its cockpit gyro structure and cargo are <cockpit> <gyro> <structure> and <cargo>
    When design weight is requested
    Then calculated weight in1024ths is <weight>
    Examples:
      | cockpit | gyro | structure | cargo | weight |
      | standard | standard | standard | 0 | 18944 |
      | small | standard | standard | 0 | 17920 |
      | standard | XL | standard | 0 | 17920 |
      | standard | Hardened | standard | 0 | 20992 |
      | standard | Compact | standard | 0 | 19968 |
      | standard | standard | EndoSteel | 0 | 16384 |
      | standard | standard | Reinforced | 0 | 24064 |
      | standard | standard | standard | 500 | 19968 |

  Scenario Outline: Construction weights 05 - ammo pile truncation
    Given a mech with no other items has <bins> identical AC5 ammo bins of <rounds> rounds each and mode <mode> in a surviving section
    When its ammo-only design contribution and current ammo weight are requested
    Then the values in1024ths are <design> and <current>
    Examples:
      | bins | rounds | mode | design | current |
      | 1 | 20 | normal | 1024 | 1024 |
      | 1 | 10 | halfton | 512 | 512 |
      | 1 | 10 | AP | 512 | 512 |
      | 1 | 40 | caseless | 0 | 2048 |
      | 2 | 40 | caseless | 0 | 4096 |
      | 1 | 0 | normal | 1024 | 0 |

  Scenario Outline: Construction weights 06 - weight cache
    Given a <destroyed> unit of50 tons has cache flag <valid> cached value <cached> and computed weight <computed> with dynspeed <dynamic>
    When get_weight is called
    Then the weight is <result> and computation count is <calls>
    Examples:
      | destroyed | valid | cached | computed | dynamic | result | calls |
      | alive | 1 | 1234 | 1 | 1 | 1234 | 0 |
      | alive | 0 | 1234 | 1 | 1 | 51200 | 1 |
      | destroyed | 0 | 1234 | 1 | 1 | 1 | 1 |
      | destroyed | 0 | 1234 | 20000 | 0 | 51200 | 1 |
      | alive | 0 | 0 | 20000 | 1 | 20000 | 1 |

  Scenario Outline: Construction weights 07 - vehicle totals
    Given a <unit> of <tons> tons moving by <move> has engine rating <rating> original internal <original> current internal <current> in front only with zero armor items and real sinks
    When weight uses interactive <interactive>
    Then calculated weight in1024ths is <weight>
    Examples:
      | unit | tons | move | rating | original | current | interactive | weight |
      | Vehicle | 50 | Track | 200 | 5 | 5 | 0 | 20992 |
      | Vehicle | 50 | Wheel | 220 | 5 | 5 | 0 | 20992 |
      | Vehicle | 50 | Hover | 235 | 5 | 5 | 0 | 23040 |
      | Naval | 50 | Hull | 230 | 5 | 5 | 0 | 26112 |
      | VTOL | 10 | VTOL | 100 | 1 | 1 | 0 | 5120 |
      | Vehicle | 50 | Track | 200 | 5 | 0 | 0 | 5120 |
      | Vehicle | 50 | Track | 200 | 5 | 0 | -1 | 1 |

  Scenario Outline: Construction weights 08 - armor contribution rounding
    Given a Mech with <armor> total original armor and armor technology <tech>
    When its design armor weight contribution is calculated
    Then calculated weight in1024ths is <weight>
    Examples:
      | armor | tech | weight |
      | 16 | standard | 1024 |
      | 17 | standard | 1536 |
      | 17 | IS-FF | 1024 |
      | 17 | Clan-FF | 1024 |
      | 17 | heavy-FF | 1024 |
      | 17 | light-FF | 1024 |
      | 17 | hardened | 2560 |
      | 1 | standard | 512 |
      | 0 | standard | 0 |
