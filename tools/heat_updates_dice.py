"""Finite named dice streams and seeded fallback draws for heat workflows."""

import random
from tools.movement_inputs import fields, number, array

STREAMS = {
    "attack_rolls": (2, 12),
    "critical_rolls": (2, 12),
    "fall_pilot_rolls": (2, 12),
    "pilot_rolls": (2, 12),
    "ammo_avoidance": (2, 12),
    "shutdown_rolls": (2, 12),
    "fire_rolls": (2, 12),
    "fire_damage": (1, 6),
    "dump_candidates": (0, None),
    "heat_injury": (0, 1),
    "fall_directions": (1, 6),
    "hit_location_rolls": (2, 12),
    "motive_rolls": (2, 12),
    "interception_rolls": (2, 12),
}


class Dice:
    def __init__(self, value):
        fields(value, (*STREAMS, "seed"))
        self.random = random.Random(number(value.get("seed", 0), integer=True))
        self.queues = {
            name: [number(v, *STREAMS[name], integer=True) for v in array(values)]
            for name, values in value.items()
            if name != "seed"
        }
        self.consumed = {name: 0 for name in STREAMS}
        self.draws = []

    def __call__(self, name, low, high, fallback):
        index = self.consumed.get(name, 0)
        if name in self.queues:
            if index >= len(self.queues[name]):
                raise ValueError("deterministic dice exhausted: " + name)
            value = number(self.queues[name][index], low, high, True)
        elif STREAMS.get(name) == (2, 12):
            value = self.random.randint(1, 6) + self.random.randint(1, 6)
        else:
            value = self.random.randint(low, high)
        self.consumed[name] = index + 1
        self.draws.append(dict(name=name, value=value, range=[low, high]))
        return value
