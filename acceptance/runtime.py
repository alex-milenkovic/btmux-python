"""Execute APS IR with a fresh world for every scenario example."""
from acceptance.steps import execute_step


def run_feature(ir):
    count = 0
    for scenario in ir['scenarios']:
        for index, example in enumerate(scenario['examples'] or [{}], 1):
            world = {}
            for step in ir.get('background', []) + scenario['steps']:
                try:
                    execute_step(world, step['text'], example)
                except (AssertionError, KeyError, ValueError, TypeError, IndexError) as error:
                    raise AssertionError(
                        f"{scenario['name']}/example_{index}: {step['text']}: {error}"
                    ) from error
            count += 1
    if count == 0:
        raise AssertionError('feature has no scenario executions')
    return count
