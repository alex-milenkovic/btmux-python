"""Core APS bindings execute domain rules and compare their public effects."""
from core.game_loop import GameEngine

BINDINGS = []


def step(pattern):
    def register(function):
        BINDINGS.append((pattern, function))
        return function
    return register


def eq(actual, expected):
    assert actual == expected, (actual, expected)


@step(r'a fresh core simulation session with source defaults')
def fresh(world):
    world.clear()
    world['core_engine'] = GameEngine()


from . import randomness, events, startup, callbacks, skills, geometry, inventory, parts, repairs, cost, bv, integration
