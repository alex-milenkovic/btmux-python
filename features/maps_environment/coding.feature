# Maps coding 01 - index reuse; Maps coding 02 - initialization retains counter
Feature: Maps coding
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps coding 01 - index reuse
    Given a fresh coding dictionary starts at counter zero
    When the terrain elevation requests are <requests>
    Then returned indices are <indices> and each safe inverse lookup reproduces its pair
    Examples:
      | requests | indices |
      | grass0,grass0 | 0,0 |
      | grass0,water2,grass0 | 0,1,0 |
      | rough3,rough4,water4,rough3 | 0,1,2,0 |

  Scenario Outline: Maps coding 02 - initialization retains counter
    Given a coding dictionary has allocated <count> distinct safe pairs
    When initialization clears the arrays and grass zero is requested
    Then the returned index is <index>
    Examples:
      | count | index |
      | 0 | 0 |
      | 1 | 1 |
      | 3 | 3 |
