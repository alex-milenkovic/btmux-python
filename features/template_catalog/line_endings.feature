# Template catalog line endings 01 - real design parity; Template catalog line endings 02 - preserve parser behavior
Feature: Template catalog line endings
  Background:
    Given an isolated template catalog session with pinned inputs and writable scratch storage

  Scenario Outline: Template catalog line endings 01 - real design parity
    Given unchanged CRLF design <reference> and its LF scratch equivalent
    When each is loaded through ordinary production template loading
    Then both succeed with equal finalized design fields and jump capability <mp>
    Examples:
      | reference | mp |
      | WVR-6R | 5 |
      | BLR-1G | 0 |
      | WHM-6R | 0 |
      | Grendel-Prime | 7 |

  Scenario Outline: Template catalog line endings 02 - preserve parser behavior
    Given a template fixture <fixture> encoded with <ending>
    When the central template parser reads it
    Then its outcome is <outcome> with source ordered writes and unchanged input bytes
    Examples:
      | fixture | ending | outcome |
      | valid-multiline | LF | normalized-multiline |
      | valid-multiline | CRLF | normalized-multiline |
      | valid-multiline | mixed | normalized-multiline |
      | unknown-section | LF | section-error |
      | unknown-section | CRLF | section-error |
      | unknown-mode | CRLF | mode-error |
      | CRIT13 | CRLF | bounds-error |
      | interior-carriage-return-section | LF | section-error |
      | unterminated-final-section | none | source-last-byte-deletion |
