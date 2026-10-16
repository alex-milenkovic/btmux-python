# Combat ranges 01 - normal range brackets; Combat ranges 02 - C3 uses actual maximum; Combat ranges 03 - artillery BTH
Feature: Combat ranges
  Background:
    Given a fresh combat session with source defaults and event time zero

  Scenario Outline: Combat ranges 01 - normal range brackets
    Given a weapon with air minimum 0 short 3 medium 6 long 9 extreme 12
    When range is <range> and target signature is <signature>
    Then range bracket is <bracket> and range modifier is <modifier>
    Examples:
      | range | signature | bracket | modifier |
      | 0 | ordinary | SHORT | 0 |
      | 3 | ordinary | SHORT | 0 |
      | 3.06 | ordinary | MED | 2 |
      | 6 | ordinary | MED | 2 |
      | 6.06 | ordinary | LONG | 4 |
      | 9.06 | ordinary | EXTREME | 8 |
      | 12.06 | ordinary | TOFAR | 1000 |
      | 4 | stealth | MED | 3 |
      | 7 | nullsig | LONG | 6 |
      | 10 | stealth | EXTREME | 12 |

  Scenario Outline: Combat ranges 02 - C3 uses actual maximum
    Given a weapon with air minimum 0 short 3 medium 6 long 9 extreme 12
    When C3 range diagnostic uses actual <actual> network <network> and signature <signature>
    Then range bracket is <bracket> and range modifier is <modifier>
    Examples:
      | actual | network | signature | bracket | modifier |
      | 9 | 2 | ordinary | SHORT | 0 |
      | 9.06 | 2 | ordinary | TOFAR | 1000 |
      | 8 | 4 | stealth | MED | 3 |
      | 8 | 7 | ordinary | LONG | 4 |

  Scenario Outline: Combat ranges 03 - artillery BTH
    Given artillery skill 4 range 20 maximum 100 and adjustment <adjustment>
    When artillery BTH is requested with <path> and spotter skill <skill>
    Then artillery BTH is <bth>
    Examples:
      | adjustment | path | skill | bth |
      | 0 | direct | 4 | 9 |
      | 0 | indirect-none | 4 | 12 |
      | 0 | indirect-other | 3 | 11 |
      | 0 | indirect-other | 1 | 10 |
      | 2 | indirect-other | 7 | 10 |
      | 0 | underwater | 4 | 5000 |
