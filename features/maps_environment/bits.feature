# Maps bits 01 - corrected packed queries; Maps bits 02 - selective clearing; Maps bits 03 - empty row saving; Maps bits 04 - right edges roundtrip; Maps bits 05 - loaded storage and resize
Feature: Maps bits
  Background:
    Given a fresh maps environment session with explicit source defaults

  Scenario Outline: Maps bits 01 - corrected packed queries
    Given a width 9 map has no allocated bit rows
    When bit <kind> is set at column <x> row 0
    Then the byte index is <index> the query value is <value> and allocated byte count is 3
    Examples:
      | kind | x | index | value |
      | mine | 0 | 0 | 1 |
      | mine | 1 | 0 | 4 |
      | mine | 4 | 1 | 1 |
      | mine | 7 | 1 | 64 |
      | hangar | 0 | 0 | 2 |
      | hangar | 3 | 0 | 128 |
      | hangar | 8 | 2 | 2 |

  Scenario Outline: Maps bits 02 - selective clearing
    Given mine and hangar bits are set at column 1 row 0 on a width 9 map
    When clear_hex_bits uses selector <selector>
    Then mine query is <mine> and hangar query is <hangar>
    Examples:
      | selector | mine | hangar |
      | 0 | 0 | 0 |
      | 1 | 0 | 8 |
      | 2 | 4 | 0 |
      | 3 | 4 | 8 |

  Scenario Outline: Maps bits 03 - empty row saving
    Given a width 9 map has row state <state>
    When the bit record is saved
    Then the type marker is <marker> and allocated bytes afterward are <size>
    Examples:
      | state | marker | size |
      | never-allocated | absent | 0 |
      | allocated-all-zero | absent | 0 |
      | one-nonzero-row | 9 | 3 |
      | two-nonzero-rows | 9 | 6 |

  Scenario Outline: Maps bits 04 - right edges roundtrip
    Given a map of width <width> has both bits set at its last valid column
    When its bit stream is saved and loaded into a fresh map of identical dimensions
    Then byte index is <index> mine query is <mine> hangar query is <hangar> and allocated row bytes are <bytes>
    Examples:
      | width | index | mine | hangar | bytes |
      | 1 | 0 | 1 | 2 | 1 |
      | 2 | 0 | 4 | 8 | 1 |
      | 3 | 0 | 16 | 32 | 1 |
      | 4 | 0 | 64 | 128 | 1 |
      | 5 | 1 | 1 | 2 | 2 |
      | 7 | 1 | 16 | 32 | 2 |
      | 8 | 1 | 64 | 128 | 2 |
      | 9 | 2 | 1 | 2 | 3 |
      | 1000 | 249 | 64 | 128 | 250 |

  Scenario Outline: Maps bits 05 - loaded storage and resize
    Given a width 5 map has an attached bit table with a mine at column 4
    When the storage command sequence is <sequence>
    Then the result is <result>
    Examples:
      | sequence | result |
      | truncated-load | error-and-original-mine-retained |
      | set-column-5 | bounds-error-and-original-mine-retained |
      | resize-9x9 | refused-with-width-5 |
      | clear-all,resize-9x9 | refused-with-width-5 |
      | delete-TBITS,resize-9x9 | success-without-bit-table |
