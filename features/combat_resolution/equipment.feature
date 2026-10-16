# Combat advanced equipment 01 - delayed transitions; Combat advanced equipment 02 - signature interrupted completion; Combat advanced equipment 03 - unjam callback; Combat advanced equipment 04 - self destruct encoding; Combat advanced equipment 05 - encoded callback boundary
Feature: Combat advanced equipment
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat advanced equipment 01 - delayed transitions
    Given valid equipment for <command> and no pending actions
    When <command> is requested at tick 0
    Then transition remains pending at <before> and completes at <due>
    Examples:
      | command | before | due |
      | stealtharmor | 29 | 30 |
      | nullsig | 29 | 30 |
      | dig | 19 | 20 |
      | fixturret | 59 | 60 |
      | slite | 4 | 5 |
      | heatcutoff | 3 | 4 |

  Scenario Outline: Combat advanced equipment 02 - signature interrupted completion
    Given <system> activation pending at tick 30
    When condition <condition> is introduced before completion
    Then the system remains inactive and completion does not reschedule
    Examples:
      | system | condition |
      | stealth | shutdown |
      | stealth | Guardian-destroyed |
      | nullsig | shutdown |
      | nullsig | system-destroyed |

  Scenario Outline: Combat advanced equipment 03 - unjam callback
    Given a jammed single-shot RAC numbered <number> with ordinary ammo and gunnery 4 and unjam requested at tick 0
    When tick 60 uses unjam roll <roll>
    Then jam remains <jam> and rounds consumed are <rounds>
    Examples:
      | number | roll | jam | rounds |
      | 0 | 6 | 1 | 0 |
      | 0 | 7 | 0 | 0 |
      | 1 | 6 | 1 | 0 |
      | 1 | 7 | 0 | 1 |

  Scenario Outline: Combat advanced equipment 04 - self destruct encoding
    Given a MECH with ammo and enabled destruction configuration
    When explode text is <text> at tick 0
    Then pilot control is relinquished and terminal source branch at tick <due> is reactor
    Examples:
      | text | due |
      | ammo | 60 |
      | reactor | 120 |

  Scenario Outline: Combat advanced equipment 05 - encoded callback boundary
    Given a started MECH with destructive ammo present <ammo> and self-destruct callback data <data>
    When exactly that callback runs once
    Then callback disposition is <result>
    Examples:
      | ammo | data | result |
      | 1 | 1 | reactor |
      | 0 | 256 | countdown-255 |
      | 1 | 257 | ammo-explosion |
      | 0 | 257 | cancelled |
      | 1 | 258 | countdown-257 |
