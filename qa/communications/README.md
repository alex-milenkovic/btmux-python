# Independent communications QA

Run from the repository worktree with scratch under its `tmp/`:

```sh
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/tmp" python3 -m qa.communications
```

Use repeated `--family` flags to select a bounded rerun. `QA_COMMS_CASE` selects
an exact `01-01` row or a workflow procedure name. The runner returns nonzero
when assertions fail. Source constants are parsed from the shared C header;
there are no production or acceptance imports. Each case invokes the public
`python -m tools.communications --input ...` UI in a fresh process. Explicit
finite draw streams have no successful fallback.

Inputs, stdout, stderr, exit status, assertion identities and SHA256 values live
in `tmp/qa-c3-communications/`. Reruns archive previous raw input/output in each
case's `history/` directory. Workflow setup does not prepopulate peer lists,
recipient lists, computed ranges/routes, XP or desired LOS. Explicit cache,
invalid-object and source helper diagnostics are labeled separately in the
behavioral row families. The master correction TAG fixture is diagnostic; its
critical shots and downstream capacity/targeting checks are ordinary commands.

`master_correction` retains the original real-shot reproductions and now checks
post-loss fire/report use after the slot is destroyed and working masters are recounted.
`supplements` maps the additional flag, status, color, buffer, report, route,
scanner, XP, passenger and repair checks to their named procedures.

Normal APS workflow dispatch uses a separate `tmp/qa-c3-aps/` root, selected by
`QA_COMMS_OUTPUT`. Both runs execute the same QA workflow oracle; independence
is from production/acceptance assertions, not from each other.
