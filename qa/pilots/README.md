# Independent pilot QA

Run from the assigned worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" TMPDIR="$PWD/tmp" python3 -m qa.pilots
```

`--family` selects a feature family, `workflows`, `extra`, or `references`.
For debugging only, `QA_PILOTS_CASE` selects an outline/example identity or
workflow name. A filtered run replaces that family's report; run the full family
again before publishing evidence.

The driver imports only Python's standard library and QA-owned modules. It reads
the approved feature rows and authoritative C definitions independently, expands
source fixtures, and launches `python3 -m tools.pilots --input …` in a fresh
subprocess for every case. Persistence cases reuse only their on-disk store in
a second process. No production, acceptance, or workflow assertion imports are used.
The separate normal APS pipeline and scoped unit runner are not this suite.

Each process saves input, stdout, stderr, exit status, assertions and SHA-256
hashes under `tmp/qa-pilots/<family>/<case>/`; family reports sit alongside those
directories. Row identity includes the original line, outline and every parameter.
A reload may share its parent row identity; completion checks compare the exact
set of approved identities, not the number of subprocesses. `extra` contains
ordinary consumer paths supplementing the fourteen specified procedures.

Ordinary commands, initializer diagnostics and source arithmetic probes are
identified in the audit and process records. Fixture construction, finite random
streams, template registration and diagnostic source inputs are explicit. No
fixture accepts a desired computed result as an input.
