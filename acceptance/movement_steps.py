"""Movement acceptance registry; each behavior group owns its bindings."""
from acceptance.movement import (
    context, modes, controls, cargo, ice, surfaces, maneuvers, orbital, settling,
)

BINDINGS = [
    binding
    for group in (context, modes, controls, cargo, ice, surfaces, maneuvers, orbital, settling)
    for binding in group.BINDINGS
]
