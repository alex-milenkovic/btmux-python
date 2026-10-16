# Unit transport 01 - cargo and source guards
# Unit transport 02 - unit exit gates and paths
# Unit transport 03 - unit exit state and recycle
Feature: Unit transport
  Background:
    Given a source-valid IC carrier and started allied embarking unit with no recycle and free cargo measured in hundredths of tons

  Scenario Outline: Unit transport 01 - cargo and source guards
    Given embark condition <condition>
    When ordinary unit embark runs
    Then result is <result>
    Examples:
      | condition | result |
      | tons5-free500-max5 | accepted-free0 |
      | tons5-free499-max5 | cargo-error |
      | tons5-free500-max4 | class-tonnage-error |
      | own5-towed3-free800-max5 | both-board-free0-tow-cleared |
      | own5-towed3-free799-max5 | combined-cargo-error |
      | target-speed0.01 | speed-error |
      | own-MMaxSpeed-below-MP1 | overload-error |
      | own-hidden | hidden-error |
      | section-recycle | physical-recycle-error |
      | weapon-recycle | weapon-recycle-error |
      | BA-noncarrier-with-capacity | accepted |
      | MECH-noncarrier | carrier-required |
      | own-carrying-target | towing-target-error |
      | jumping-target | jump-error |

  Scenario Outline: Unit transport 02 - unit exit gates and paths
    Given carried unit condition <condition>
    When ordinary unit disembark runs
    Then result is <result>
    Examples:
      | condition | result |
      | IC-wrong-official-owner | owner-error |
      | IC-wizard | accepted |
      | repairs-pending | repair-error |
      | carrier-speed-walk | accepted |
      | carrier-speed-overwalk | speed-error |
      | carrier-no-map | map-error |
      | BA-ground-carrier-stopped | climbout-no-fall |
      | MECH-ground-carrier-stopped | breakout-fall4 |
      | MECH-ground-carrier-started | ramp |
      | nonflyer-abovefloor | OOD |
      | landed-flyer-abovefloor-carrier-started | ramp-clear-landed |

  Scenario Outline: Unit transport 03 - unit exit state and recycle
    Given carried unit class <class> exits at carrier XYZ with invoking actor inside
    When the ordinary exit completes
    Then immediate startup and cargo credit occur with section recycle <recycle>
    Examples:
      | class | recycle |
      | BA | live-members20 |
      | MECH | all8-60 |
      | MW | all8-60 |
      | ground | all-except5-60 |
      | VTOL | all-except5-60 |
