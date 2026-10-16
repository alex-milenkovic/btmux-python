# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-09-08T00:43:46.223147931Z","feature_name":"Hull down","feature_path":"features/movement/hulldown.feature","background_hash":"f1ce2b87b55b08de017271a2248c655eb138b186d438650e4cc17c26d009c7ba","implementation_hash":"sha256:33ae4fbe4cdba53bda52183d6a88a43eec6fa9f689a76338693c8a5ce568559f","scenarios":[]}
# acceptance-mutation-manifest-end

# Hull down 01 - lowering eligibility; Hull down 02 - completion and cancellation
Feature: Hull down
  Background:
    Given a fresh movement session with the standard ready unit and clear map

  Scenario Outline: Hull down 01 - lowering eligibility
    Given unit movement <movement> and actual speed <speed> KPH
    When the pilot requests hulldown
    Then the command is <outcome> and a new transition is <scheduled>
    Examples:
      | movement | speed | outcome | scheduled |
      | QUAD | 0 | ACCEPTED | True |
      | QUAD | 0.5 | ACCEPTED | True |
      | QUAD | 0.51 | REJECTED | False |
      | QUAD | -10.75 | ACCEPTED | True |
      | BIPED | 0 | REJECTED | False |

  Scenario Outline: Hull down 02 - completion and cancellation
    Given a quad with maximum speed 64.5 KPH
    When the pilot performs hull down workflow <workflow> and advances <ticks> seconds
    Then hull down is <active> and changing hull down is <pending>
    Examples:
      | workflow | ticks | active | pending |
      | LOWER | 9 | False | True |
      | LOWER | 10 | True | False |
      | LOWER_STOP | 10 | False | False |
      | RAISE | 9 | True | True |
      | RAISE | 10 | False | False |
      | RAISE_STOP | 10 | True | False |
      | LOWER_SHUTDOWN | 10 | False | False |
