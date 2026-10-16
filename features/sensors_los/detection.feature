# Contact acquisition 01 - normal lifecycle; Contact acquisition 02 - autocontacts; Contact acquisition 03 - map sensor mask; Contact acquisition 04 - blind recovery
Feature: Contact acquisition
  Background:
    Given a fresh sensor session with ready units and event time zero

  Scenario Outline: Contact acquisition 01 - normal lifecycle
    Given a started observer and an enemy one hex ahead with no cached contact
    When the visibility workflow is <workflow>
    Then the enemy contact is <seen> and enemy count is <count>
    And the observer has <chains> pending acquisition chains
    Examples:
      | workflow | seen | count | chains |
      | map-maintenance-only | False | 0 | 1 |
      | normal-advance-two | True | 1 | 1 |
      | repeated-live-registration-and-advance | True | 1 | 1 |
      | acquire-then-shutdown-and-advance | True | 1 | 0 |
      | acquire-lock-disable-visual-and-advance | False | 0 | 1 |

  Scenario Outline: Contact acquisition 02 - autocontacts
    Given autocontact mode <mode> and a new <relation> contact with clear NB visibility
    When an ordinary acquisition sweep notices the contact
    Then the acquisition notification style is <style> and warning is <warning>
    Examples:
      | mode | relation | style | warning |
      | 0 | enemy | long | True |
      | 1 | friend | short | False |
      | 2 | friend | none | False |
      | 2 | enemy | long | True |
      | 3 | enemy | short | True |
      | 4 | enemy | short | False |
      | 5 | friend | none | False |
      | 6 | enemy | none | False |

  Scenario Outline: Contact acquisition 03 - map sensor mask
    Given equal sensors <sensor> with valid equipment and an eligible target at range 1
    And the configured sensor disable mask is <mask>
    When sensor eligibility is inspected through the diagnostic command
    Then the eligible sensor mask is <eligible>
    Examples:
      | sensor | mask | eligible |
      | V | 0 | 3 |
      | V | 1 | 0 |
      | I | 4 | 0 |
      | B | 64 | 0 |
      | A | 64 | 0 |
      | A | 128 | 3 |
      | H | 128 | 0 |
      | H | 256 | 3 |

  Scenario Outline: Contact acquisition 04 - blind recovery
    Given an observer with primary sensor <primary> secondary V and clear LOS to a flash source
    When a guaranteed flash of duration 4 occurs
    And the engine advances <seconds> seconds with recovery consciousness <conscious>
    Then blinded is <blinded> and recovery message count is <messages>
    Examples:
      | primary | seconds | conscious | blinded | messages |
      | I | 3 | True | True | 0 |
      | I | 4 | True | False | 1 |
      | L | 4 | False | False | 0 |
      | V | 3 | True | False | 0 |
