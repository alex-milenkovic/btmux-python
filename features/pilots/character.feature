# Character records 01 - names and unsigned values
# Character records 02 - initialization and category retrieval
# Character records 03 - source generic serialization
# Character records 04 - code eleven coupling
# Character records 05 - cache invalidation
# Character records 06 - public permissions and lists
# Character records 07 - duration rendering
Feature: Character records
  Background:
    Given an isolated character registry using the complete source value table and production storage

  Scenario Outline: Character records 01 - names and unsigned values
    Given character value <name> is assigned <input>
    When the value is retrieved by its canonical name
    Then its code is <code> and stored value is <value>
    Examples:
      | name | input | code | value |
      | Build | 5 | 36 | 5 |
      | bUiLd | 257 | 36 | 1 |
      | BuilD | -1 | 36 | 255 |
      | Refle | 4 | 37 | 4 |
      | GunBat | 3 | 63 | 3 |
      | TecBat | 3 | 107 | 3 |
      | Tough | 2 | 26 | 2 |

  Scenario Outline: Character records 02 - initialization and category retrieval
    Given the stored categories contain <contents>
    When retrieval requests <mask>
    Then the resulting category state is <state>
    Examples:
      | contents | mask | state |
      | absent | 15 | attributes1-lives1-health0-skills0 |
      | valid-build5-health2,3 | 1 | build0-bruise2-lethal3 |
      | malformed-health-existing-build5 | 15 | all-defaults-persisted |
      | malformed-attributes-existing-skill4 | 15 | all-defaults-persisted |
      | valid-all | 0 | all-zero |
      | duplicate-Running:2,9,40/Running:3,0,0/ | 2 | Running3-xp9-last40 |
      | Running:2/Unknown:9/Blade:3/ | 2 | Running2-Blade3 |
      | Running:2/bad/Blade:3/ | 2 | Running2-Blade0 |

  Scenario Outline: Character records 03 - source generic serialization
    Given raw stored state <state>
    When the <category> category is serialized and retrieved from fresh state
    Then exact text is <text> and resulting state is <result>
    Examples:
      | state | category | text | result |
      | Running2-xp0-last40 | skills | Runni:2/ | Running2-xp0-last0 |
      | Running2-xp16777317-last40 | skills | Runni:2,16777317,40/ | Running2-xp16777317-last40 |
      | Running0-xp0-last40 | skills | empty | Running0-xp0-last0 |
      | Lives1-Toughness1-Running2 | advantages | Lives:1/Tough:1/ | Lives1-Toughness1-Running0 |
      | Lives1-Toughness1-Running2 | skills | Runni:2/ | Lives0-Toughness0-Running2 |
      | all-zero | advantages | empty | all-zero |
      | Technician-Battlesuit3-xp0 | skills | TecBat:3/ | Technician-Battlemech3-Battlesuit0 |

  Scenario Outline: Character records 04 - code eleven coupling
    Given Lives is <lives> and raw ShotsHit is <old>
    When raw ShotsHit is set to <new> in the current stats structure
    Then Lives is <result>
    Examples:
      | lives | old | new | result |
      | 1 | 0 | 3 | 4 |
      | 4 | 3 | 0 | 1 |
      | 255 | 0 | 2 | 1 |
      | 1 | 2 | 0 | 255 |

  Scenario Outline: Character records 05 - cache invalidation
    Given a cached Running BTH of 7 and changed Build yielding a fresh BTH of 6
    When the operation is <operation>
    Then the next Running BTH is <target>
    Examples:
      | operation | target |
      | store-attributes-only | 7 |
      | store-health-only | 7 |
      | store-skills | 6 |
      | store-advantages | 6 |
      | public-set-value | 6 |

  Scenario Outline: Character records 06 - public permissions and lists
    Given character request <request> with <authority>
    When the ordinary character control runs
    Then the visible result is <result>
    Examples:
      | request | authority | result |
      | status-self | ordinary | status |
      | status-other | ordinary | authority-error |
      | status-other | WizR | status |
      | clear-other | ordinary | power-error |
      | clear-missing-argument | WizR | target-required |
      | get-unknown-player | ordinary | invalid-target |
      | get-Build | ordinary | permission-denied |
      | get-unknown-value | Wiz | invalid-value |
      | set-Build-flag1 | Wiz | only-skills-can-have-flag |
      | list-advantages-zero-target | ordinary | all-source-advantages |
      | list-skills-zero-target | ordinary | empty |
      | list-attributes-zero-target | ordinary | all-five |
      | list-unknown-category | ordinary | invalid-value |
      | status-Toughness2 | ordinary | advantage-name-shown |
      | status-Contact7 | ordinary | Contact-value7 |
      | status-Exceptional17 | ordinary | Exceptional-Build-and-Charisma |
      | status-rawRunning0-bonus1 | ordinary | no-listed-skills |

  Scenario Outline: Character records 07 - duration rendering
    Given an uptime of <seconds> seconds
    When its public duration is requested
    Then the rendered duration is <text>
    Examples:
      | seconds | text |
      | 0 | #-1 INVALID VALUE |
      | 1 | 1 second |
      | 61 | 1 minute and 1 second |
      | 3661 | 1 hour, 1 minute and 1 second |
