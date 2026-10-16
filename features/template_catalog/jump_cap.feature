# Template catalog jump cap 01 - corrected shared calculation; Template catalog jump cap 02 - slot counting and shared callers
Feature: Template catalog jump cap
  Background:
    Given an isolated template catalog session with pinned inputs and writable scratch storage

  Scenario Outline: Template catalog jump cap 01 - corrected shared calculation
    Given a Mech has maximum speed <speed> KPH and <slots> installed JumpJet slots with improved flag <improved>
    When shared sub_magic recomputes mobility
    Then persistent jump capacity is <mp> MP and jump speed is <jump> KPH
    Examples:
      | speed | slots | improved | mp | jump |
      | 64.5 | 0 | 0 | 0 | 0 |
      | 64.5 | 4 | 0 | 4 | 43 |
      | 64.5 | 8 | 0 | 4 | 43 |
      | 86 | 5 | 0 | 5 | 53.75 |
      | 86 | 8 | 0 | 5 | 53.75 |
      | 64.49 | 8 | 0 | 3 | 32.25 |
      | 64.51 | 8 | 0 | 4 | 43 |
      | 0 | 4 | 0 | 0 | 0 |
      | 64.5 | 4 | 1 | 2 | 21.5 |
      | 64.5 | 5 | 1 | 2 | 21.5 |
      | 64.5 | 16 | 1 | 6 | 64.5 |
      | 86 | 18 | 1 | 8 | 86 |
      | 64.49 | 16 | 1 | 5 | 53.75 |

  Scenario Outline: Template catalog jump cap 02 - slot counting and shared callers
    Given four standard JumpJet slots at maximum64.5 KPH with slot condition <condition>
    When recomputation runs through <caller>
    Then jump capacity is4 MP and the established sink calculation is unchanged
    Examples:
      | condition | caller |
      | intact | modern-load |
      | destroyed | sub-magic |
      | disabled | sub-magic |
      | intact | repair-replay |
