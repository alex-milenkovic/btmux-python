# Template catalog storage 01 - custom mutation routing; Template catalog storage 02 - collision origin and restore
Feature: Template catalog storage
  Background:
    Given an isolated template catalog session with pinned inputs and writable scratch storage

  Scenario Outline: Template catalog storage 01 - custom mutation routing
    Given upstream WVR-6R is loaded and the requested custom root has <root_state>
    When ordinary mutation <operation> is attempted
    Then its outcome is <outcome> and the upstream byte manifest is unchanged
    Examples:
      | root_state | operation | outcome |
      | separate | save-CUSTOM | custom-written |
      | separate | editor-save-CUSTOM | custom-written |
      | separate | write-CUSTOM | custom-written |
      | upstream-overlap | save-WVR-6R | rejected |
      | symlink-into-upstream | write-WVR-6R | rejected |
      | separate | delete-explicit-upstream-WVR-6R | rejected |
      | upstream-overlap | fixture-write-WVR-6R | rejected |

  Scenario Outline: Template catalog storage 02 - collision origin and restore
    Given a catalog-loaded WVR-6R and a later distinct custom WVR-6R shadow
    When <operation> selects that reference
    Then its source is <origin> and the two listed candidates retain distinct provenance
    Examples:
      | operation | origin |
      | default-load | custom |
      | explicit-upstream-load | upstream |
      | restore-original-unit | upstream |
      | explicit-custom-load | custom |
