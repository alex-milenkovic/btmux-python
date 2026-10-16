"""Command-line adapter for strict JSON heat and per-tick workflows."""

import argparse
import json
from pathlib import Path
from tools.heat_updates_session import Session
from tools.heat_updates_dice import Dice  # Retain the existing public import.


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a heat/per-tick JSON workflow. Required: actions. Optional: map, units, config, clock, random. Defaults: clear 8x8 map, ready 50-ton unit u at 2,2,0, capacity 10; wall/event/heartbeat zero; standard dispatch and heartbeat enabled. See docs/heat-updates-cli.md for all strict fields, commands, diagnostic maintenance, finite named dice streams, clock semantics, runnable examples and unavailable dependencies. Profiles: movement modes on, MW3 off; advanced vehicle fire off; new stagger mode 1, interval 5, tonnage on. Omitted dice use seed 0; supplied streams exhaust with an error. Aerospace dispatch, TAG/searchlight maintenance and generic failure are unavailable and reported in snapshots."
    )
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args(argv)
    try:

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate JSON field " + key)
                result[key] = value
            return result

        document = json.loads(
            args.input.read_text(),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError("nonfinite number " + value)
            ),
        )
        result = Session(document).run()
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OverflowError,
    ) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
