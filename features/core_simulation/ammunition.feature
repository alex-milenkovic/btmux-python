# Core ammunition 01 - full capacity priority; Core ammunition 02 - grouped current and maximum counts; Core ammunition 03 - empty inventory pruning
Feature: Core ammunition
  Background:
    Given a fresh core simulation session with source defaults

  Scenario Outline: Core ammunition 01 - full capacity priority
    Given ammo base capacity <base> with modes <modes>
    When FullAmmo is requested
    Then full capacity is <capacity>
    Examples:
      | base | modes | capacity |
      | 11 | none | 11 |
      | 11 | HALFTON | 5 |
      | 11 | CASELESS | 22 |
      | 11 | AP+CASELESS | 5 |
      | 11 | MML_LRM | 13 |
      | 13 | MML_LRM | 16 |
      | 11 | HALFTON+MML_LRM | 5 |

  Scenario Outline: Core ammunition 02 - grouped current and maximum counts
    Given same-type same-mode bins of capacity 10 with current rounds 4 and 6 and second nonfunctional <broken>
    When ammunition inventory includes all groups
    Then group current is <current> and maximum is 20
    Examples:
      | broken | current |
      | 0 | 10 |
      | 1 | 4 |

  Scenario Outline: Core ammunition 03 - empty inventory pruning
    Given one ammo group has zero functional rounds and capacity 10
    When ammunition inventory uses returnall <all>
    Then returned group count is <count>
    Examples:
      | all | count |
      | 0 | 0 |
      | 1 | 1 |
