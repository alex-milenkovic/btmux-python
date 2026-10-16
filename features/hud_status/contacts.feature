# Display contacts 01 - filter and order; Display contacts 02 - compact priority; Display contacts 03 - identity mask; Display contacts 04 - saved filters
Feature: Display contacts
  Background:
    Given a fresh HUD display session with ready units and event time zero

  Scenario Outline: Display contacts 01 - filter and order
    Given contacts near friendly range 2 far enemy range 8 wreck enemy range 1 and an accessible building range 3
    When contacts brevity <brief> filter <filter> is requested
    Then the displayed ordered names are <names> and ordinary framing is <framing>
    Examples:
      | brief | filter | names | framing |
      | 0 | no-argument | near,far,wreck | true |
      | 1 | no-argument | building,wreck,far,near | true |
      | 2 | no-argument | wreck,far,near | true |
      | 3 | no-argument | wreck,far,near | false |
      | 1 | !db | far,near | true |
      | 2 | a | near | true |
      | 2 | e | far | true |

  Scenario Outline: Display contacts 02 - compact priority
    Given target diagnostic status combination <states> and viewer spinning <spin>
    When identified brief contacts are requested
    Then the five status columns with blanks encoded as underscores are <chars>
    Examples:
      | states | spin | chars |
      | started-swarming-towed-carrying-destroyed-light-jumping-fallen-heat-inferno-NARC-enemy | false | WDJ+N |
      | started-lit-hulldown-ECM-ECCM | false | _lH_P |
      | offline-staggering-starting | false | ___G_ |
      | offline-starting | false | ___s_ |
      | started | true | __X__ |
      | started-target-spinning | false | _____ |

  Scenario Outline: Display contacts 03 - identity mask
    Given a same-team contact named LongVisibleName with two-character ID AB heat 2 and NB <nb>
    When brief legacy HUD contacts h is requested
    Then legacy row relation is <relation> displayed ID is <id> name field with trailing padding removed is <name> and compact status with blanks encoded as underscores is <status>
    And the row contains primary secondary arc and movement columns in source order
    Examples:
      | nb | relation | id | name | status |
      | true | F | ab | LongVisibleN | ___+_ |
      | false | E | AB | something | _____ |

  Scenario Outline: Display contacts 04 - saved filters
    Given saved contact options are <saved> and a ready enemy plus a wreck are visible
    And contact brevity is zero and roster order is enemy then wreck
    When contacts plus is requested
    Then included names are <names> and ignored option warnings are <warnings>
    Examples:
      | saved | names | warnings |
      | unset | enemy | 0 |
      | e | enemy | 0 |
      | ed | enemy,wreck | 0 |
      | ez | enemy | 1 |
