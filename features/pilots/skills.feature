# Character skills 01 - attribute pair targets
# Character skills 02 - dice families
# Character skills 03 - success and margin
# Character skills 04 - opposed margins
# Character skills 05 - attribute saves and advantages
# Character skills 06 - exact boolean advantages
Feature: Character skills
  Background:
    Given source character attributes Build5 Reflexes4 Intuition3 Learn2 Charisma1 unless overridden

  Scenario Outline: Character skills 01 - attribute pair targets
    Given skill <skill> with raw level 2 and packed bonus 1
    When target calculation uses XP <xp> and modifier <modifier>
    Then BTH is <target>
    Examples:
      | skill | xp | modifier | target |
      | Running | True | 2 | 8 |
      | Small_Arms | True | 2 | 10 |
      | Computer | True | 2 | 12 |
      | Negotiation | True | 2 | 13 |
      | Running | False | 2 | 7 |
      | Build | True | 9 | 18 |
      | Unknown | True | 9 | 18 |

  Scenario Outline: Character skills 02 - dice families
    Given Number dice <dice>
    When the character rolls <kind>
    Then result is <result> with <draws> Number calls and zero Roll statistics
    Examples:
      | dice | kind | result | draws |
      | 1,3,6 | saving | 9 | 3 |
      | 1,3,6 | unskilled | 4 | 3 |
      | 6,6,6 | unskilled | 12 | 3 |
      | 2,5 | skilled | 7 | 2 |
      | 1,2,3,4 | d6-4 | 10 | 4 |
      | none | d6-0 | 0 | 0 |
      | none | d6-minus1 | 0 | 0 |

  Scenario Outline: Character skills 03 - success and margin
    Given effective skill <level> with target <target> and dice <dice>
    When named skill success and margin are each evaluated in fresh identical state
    Then success is <success> and margin is <margin>
    Examples:
      | level | target | dice | success | margin |
      | 0 | 10 | 2,5,6 | False | -3 |
      | 1 | 7 | 2,5 | True | 0 |
      | 1 | 8 | 2,5 | False | -1 |
      | -1 | 18 | 6,6 | False | -6 |

  Scenario Outline: Character skills 04 - opposed margins
    Given first margin <first> and second margin <second> from sequential source rolls
    When the two characters contest the skill
    Then the winner is <winner>
    Examples:
      | first | second | winner |
      | 1 | 0 | first |
      | -1 | 0 | second |
      | 2 | 2 | tie |

  Scenario Outline: Character skills 05 - attribute saves and advantages
    Given attribute value <value> and a skilled roll of 7
    When attribute saving target and success are computed
    Then target is <target> and success is <success>
    Examples:
      | value | target | success |
      | 0 | 18 | False |
      | 5 | 8 | False |
      | 6 | 6 | True |
      | 9 | 0 | True |
      | 10 | 0 | True |
      | -1 | -1 | -1 |

  Scenario Outline: Character skills 06 - exact boolean advantages
    Given Toughness has value <value>
    When the named Boolean advantage is queried
    Then it is <present>
    Examples:
      | value | present |
      | 0 | False |
      | 1 | True |
      | 2 | False |
      | 255 | False |
