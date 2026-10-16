# Maps weather operations 01 - shared gameplay modifiers; Maps weather operations 02 - clock snowfall; Maps weather operations 03 - clock melt and steam; Maps weather operations 04 - timer ownership; Maps weather operations 05 - persistence and layers; Maps weather operations 06 - clock ice consequences; Maps weather operations 07 - normalized snow control
Feature: Maps weather operations
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps weather operations 01 - shared gameplay modifiers
    Given ordinary weather controls enable conditions <conditions> temperature <temperature> and windspeed <wind>
    And a grounded biped with no hex layers has weapon class <weapon> and ordinary heat dissipation 10
    When sight and actual fire use the same shot setup and an ordinary piloting command and heat tick execute
    Then the sight and firing weather term is <gun> the piloting weather term is <pilot> and minus heat is <minus>
    Examples:
      | conditions | temperature | wind | weapon | gun | pilot | minus |
      | none | 20 | 0 | TAMMO | 0 | 0 | 10 |
      | precipitation | 20 | 0 | TBEAM | 1 | 0 | 9 |
      | heavy_precipitation | 20 | 0 | TBEAM | 0 | 1 | 8 |
      | heavy_precipitation | 0 | 61 | TAMMO | 2 | 1 | 8 |
      | fog,blowing_sand | 20 | 0 | TBEAM | 3 | 0 | 10 |
      | none | 20 | 61 | TAMMO | 2 | 1 | 10 |
      | none | 20 | 60 | TAMMO | 1 | 0 | 10 |
      | none | -31 | 0 | TBEAM | 0 | 0 | 11 |
      | none | 51 | 0 | TBEAM | 0 | 0 | 9 |

  Scenario Outline: Maps weather operations 02 - clock snowfall
    Given a one-cell grass map enables <conditions> at temperature 0 tick 0 with default rates and finite snow draws <draws>
    When the ordinary simulation clock advances to <tick>
    Then snow depth is <depth> snow layer is <layer> and next weather deadline is <deadline>
    Examples:
      | conditions | draws | tick | depth | layer | deadline |
      | precipitation | 10 | 59 | 0 | none | 60 |
      | precipitation | 10 | 60 | 10 | shallow | 120 |
      | precipitation | 10,20 | 120 | 30 | shallow | 180 |
      | heavy_precipitation | 30 | 60 | 30 | shallow | 120 |
      | heavy_precipitation | 30,50 | 120 | 80 | shallow | 180 |
      | none | none | 120 | 0 | none | 180 |

  Scenario Outline: Maps weather operations 03 - clock melt and steam
    Given a one-cell grass map starts with shallow snow depth 500 and enables temperature <temperature> at tick 0 with steam <steam>
    When the simulation reaches tick 60 with optional steam draw <draw>
    Then snow depth is <depth> smoke deadline is <deadline> and the steam draw is <usage>
    Examples:
      | temperature | steam | draw | depth | deadline | usage |
      | 0 | true | 0 | 500 | none | unused |
      | 1 | true | 0 | 490 | 70 | unused |
      | 9 | true | 0 | 410 | 150 | unused |
      | 10 | true | 0 | 400 | 150 | used |
      | 10 | true | 5 | 400 | 155 | used |
      | 10 | false | 0 | 400 | none | unused |

  Scenario Outline: Maps weather operations 04 - timer ownership
    Given a width 5 grass map enables ordinary snowfall at tick 0 with default cadence
    When the ordinary command sequence is <sequence>
    Then the weather event count is <count> and its deadline is <deadline>
    Examples:
      | sequence | count | deadline |
      | identical-set-at-10 | 1 | 60 |
      | heavy-set-at-10 | 1 | 70 |
      | cadence-10-at-10 | 1 | 20 |
      | disable-at-10 | 0 | none |
      | disable-at-10,enable-at-20 | 1 | 80 |
      | reset-at-10 | 0 | none |
      | clear-mechs-at-10 | 1 | 60 |
      | remove-map-at-10 | 0 | none |
      | resize-9x9-at-10 | 1 | 70 |
      | resize-0x0-at-10 | 0 | none |
      | set-mine-at-5,resize-9x9-at-10 | 1 | 60 |
      | invalid-cadence-0-at-10 | 1 | 60 |

  Scenario Outline: Maps weather operations 05 - persistence and layers
    Given the documented ordinary environment snapshot workflow <workflow> starts through public controls
    When it saves loads or resizes through the public interface
    Then the independently observable result is <result>
    Examples:
      | workflow | result |
      | enabled-save-at-10-load-at-100 | weather-deadline-150-and-identical-next-snow-draw |
      | steam-save-at-65-load-at-100 | smoke-expires-105-and-weather-deadline-155 |
      | layers-resize-grow | copied-intersection-and-empty-new-cells |
      | layers-resize-shrink | outside-layers-removed |
      | weather-reset | disabled-empty-layers-retained-temperature-wind-and-smoke |
      | legacy-without-weather | disabled-empty-layers-and-original-temperature-behavior |
      | huge-depth-decimal | exact-9007199254740993-deep-snow-roundtrip |
      | malformed-weather-snapshot | atomic-error-retains-state-and-deadlines |

  Scenario Outline: Maps weather operations 06 - clock ice consequences
    Given an ice hex has stored elevation <elevation> and a same-hex ground vehicle at altitude <altitude> with movement <move>
    And warm weather is enabled at temperature 1 tick 0 with default melt settings
    When the clock processes the weather callback at 60
    Then terrain is water steam is absent and the vehicle consequence is <consequence>
    Examples:
      | elevation | altitude | move | consequence |
      | 2 | 0 | tracked | fall-and-flood-destruction |
      | 2 | 0 | hover | no-fall |
      | 2 | 1 | tracked | no-fall |
      | 0 | 0 | tracked | no-fall |

  Scenario Outline: Maps weather operations 07 - normalized snow control
    Given ordinary layer controls set snow depth <before> and mud on a grass hex
    When the ordinary snow grow command draws <draw> from equal signed bounds <bound>
    Then layer data is <after> and final layers are <layers>
    Examples:
      | before | draw | bound | after | layers |
      | 100 | 200 | -200 | 0 | mud |
      | 100 | 900 | 900 | 1000 | snow |
      | 100 | 901 | 901 | 1001 | deep_snow |
      | 1001 | 1 | -1 | 1000 | snow,mud |
