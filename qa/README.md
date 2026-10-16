# Behavioral checks and test support

Run these tools from a source checkout. The `tests/` unittest suites and the
35 saved encounters use Python's standard library. For example:

```sh
python -B -m tests.test_gameplay_scenarios
python -B -m tests.test_autopilot_scenarios
python -B -m qa.communications --family channels
```

`qa/` retains independent public-CLI assertions, C oracle builders and clean
fixtures. Results are generated under ignored `tmp/` directories. Some older
drivers are script entrypoints (`python -B qa/core_simulation.py --only clocks`),
while package drivers use `python -B -m qa...`; inspect each driver's `--help`.
Create `tmp/` before using the advanced acceptance workflows.

The advanced `python -m tools.run_acceptance --suite NAME` pipeline expects an
external APS-compatible `gherkin-parser` executable on PATH. It consumes
`gherkin-parser FEATURE OUTPUT_JSON`, then generates and executes Python
bindings. That external developer tool is optional and is not a runtime
dependency or part of the Python distribution. The executable feature files and
bindings remain available under `features/` and `acceptance/`.

Source-based QA requires the separately supplied general C checkout at
`btmux/btmux/btech/src/`; compiled oracles also require a C compiler (`cc`) and
a POSIX environment. Historical fighter checks additionally use the preserved
`references/` snapshot. Catalogue checks require explicit
[catalogue setup](../docs/template-catalog-integration.md); no check should be
interpreted as automatically obtaining these source inputs.

`qa/oracles/build_defensive_bv.py` extracts the original defensive-BV function
body and supplies a small C struct/accessor harness. It accepts `--source-root`
and `--output`; `qa/core_qa_bv_oracle.py` compares its results through the core CLI.
The original C function text and source references are preserved.
