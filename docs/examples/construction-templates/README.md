# Construction CLI examples

From the worktree, create `tmp/`, then run sequentially:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.construction_templates --input docs/examples/construction-templates/01-edit-save.json > ./tmp/construction-example-edit.json
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.construction_templates --input docs/examples/construction-templates/02-load-fire.json > ./tmp/construction-example-fire.json
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.construction_templates --input docs/examples/construction-templates/03-explicit-file.json > ./tmp/construction-example-explicit.json
```

The first process builds and saves `./tmp/construction-example/templates/CUSTOM`.
The second loads that real file, seats a pilot, starts, locks and fires at01.
The third supplies explicit brace-file contents and repeats the shot. Both shots
hit for5, leave19 AC5 rounds, add1 firing heat, and recycle for40 seconds before
becoming ready. Slot readout distinguishes source AC5 ID96/ammo288 from runtime
IDs. Every source random stream is explicit; no acceptance runner is needed.

The other ordinary editor operations and schema are in
[the CLI reference](../../construction-templates-cli.md). The normal APS
integration family executes all11 named ordinary workflow examples and two
mixed-mode integration cases, plus five fresh-process file/fire cases in modes.
The independent QA driver constructs its own inputs and expectations.
