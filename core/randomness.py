# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# MT19937 retains its separate terms in notices/MT19937.txt.
# General sources:
#   btech/mech.stat.c
#   btech/mech.utils.c
#   mt19937ar.c

"""Shared source randomness, with optional named finite input streams."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import random
import struct
import time

from core.mt19937 import MT19937

_source = ContextVar('simulation_dice', default=None)
_simulation = ContextVar('simulation_random_state', default=None)
_rolling = ContextVar('simulation_recording_roll', default=False)


def float32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


class RandomState:
    """One simulation's generator and mech.stat.c Roll histogram."""

    def __init__(self, seed=None):
        self.mt = MT19937(seed)
        self.rolls = [0] * 11
        self.total_rolls = 0
        self.critical_rolls = [0] * 11
        self.total_critical_rolls = 0
        self.hit_rolls = [0] * 11
        self.total_hit_rolls = 0

    def number(self, low, high):
        if (not isinstance(low, int) or not isinstance(high, int) or
                high < low or low < -(1 << 31) or high > 0xffffffff or high-low > 0xffffffff):
            raise ValueError('unsupported Number bounds: ordered integers within the 32-bit sampling domain required')
        bits = (high-low).bit_length()
        if not bits:
            return 0
        while True:
            value = self.mt.int32() >> (32-bits)
            if value <= high-low:
                return low + value

    def record_roll(self, value):
        if not isinstance(value, int) or not 2 <= value <= 12:
            raise ValueError('Roll input must be an integer from 2 through 12')
        self.rolls[value-2] += 1
        self.total_rolls += 1
        return value

    def roll(self):
        return self.record_roll(self.number(1, 6) + self.number(1, 6))

    def init_stat(self, epoch=None):
        self.mt.seed(int(time.time()) if epoch is None else epoch)

    def stat_rows(self):
        if not self.total_rolls:
            return []
        chances = [1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1]
        rows = []
        for i, chance in enumerate(chances):
            optimal = float32(chance * 100.0 / 36.0)
            hit = float32(sum(chances[i:]) / 36.0 * 100)
            rows.append(dict(roll=i+2, count=self.rolls[i],
                current_percent=float32(float32(self.rolls[i]) * 100.0 / self.total_rolls),
                optimal_count=int(float32(float32(optimal / 100) * float32(self.total_rolls))),
                optimal_percent=optimal, hit_percent=hit, miss_percent=100.0-hit))
        return rows

    def show_stat(self):
        rows = self.stat_rows()
        if not rows:
            return ['No rolls to show statistics for!']
        lines = ['#    Rolls %Current  Optimal Rolls %Optimal  %Hit Chance  %Miss Chance']
        for row in rows:
            lines.append('{roll:<3d} {count:6d} {current_percent:8.3f} {optimal_count:14d} '
                         '{optimal_percent:8.3f} {hit_percent:12.3f} {miss_percent:13.3f}'.format(**row))
        return lines + [f'Total rolls: {self.total_rolls}']


_standalone_critical_rolls = [0] * 11
_standalone_total_critical_rolls = 0


def record_critical_roll(value, owner=None):
    """The critical histogram is separate from the histogram of all Roll calls."""
    global _standalone_total_critical_rolls
    state = _simulation.get() or getattr(getattr(owner, '_engine', None), 'randomness', None)
    if state is None:
        _standalone_critical_rolls[value-2] += 1
        _standalone_total_critical_rolls += 1
    else:
        state.critical_rolls[value-2] += 1
        state.total_critical_rolls += 1
    if owner is not None:
        owner.critical_rolls = getattr(owner, 'critical_rolls', []) + [value]
    return value


_standalone_hit_rolls = [0] * 11
_standalone_total_hit_rolls = 0


def record_hit_roll(value, owner=None):
    """Record only the table roll, after safety and dug-in early returns."""
    global _standalone_total_hit_rolls
    state = _simulation.get() or getattr(getattr(owner, '_engine', None), 'randomness', None)
    if state is None:
        _standalone_hit_rolls[value-2] += 1
        _standalone_total_hit_rolls += 1
    else:
        state.hit_rolls[value-2] += 1
        state.total_hit_rolls += 1
    if owner is not None:
        owner.hit_rolls = getattr(owner, 'hit_rolls', []) + [value]
    return value


_standalone = RandomState()


def source_state(owner=None):
    """Resolve an explicit owner's stream, then the active or detached stream."""
    engine = getattr(owner, '_engine', None) or getattr(getattr(owner, 'map', None), '_engine', None)
    return getattr(engine, 'randomness', None) or _simulation.get() or _standalone


def number(low, high):
    return source_state().number(low, high)


def roll(name='rolls', fallback=None):
    """A source Roll, distinct from Number with the same output bounds.

    Existing injected sum streams count once; a legacy fallback calling this
    helper recursively uses two dice without a second histogram increment.
    """
    if _rolling.get():
        return number(1, 6) + number(1, 6)
    token = _rolling.set(True)
    try:
        state = _simulation.get()
        default = (lambda: number(1, 6) + number(1, 6)) if state is not None else (fallback or (lambda: number(1, 6) + number(1, 6)))
        source = _source.get()
        value = default() if source is None else source(name, 2, 12, default)
        return state.record_roll(value) if state is not None else value
    finally:
        _rolling.reset(token)


def draw(name, low, high, fallback, *, state=None):
    source = _source.get()
    state = state if state is not None else _simulation.get()
    default = (lambda: state.number(low, high)) if state is not None else fallback
    return default() if source is None else source(name, low, high, default)


@contextmanager
def use_simulation(state):
    token = _simulation.set(state)
    try:
        yield state
    finally:
        _simulation.reset(token)


def simulation_method(method):
    """Run an engine entrypoint with its own shared stream, including callbacks."""
    @wraps(method)
    def run(engine, *args, **kwargs):
        with use_simulation(engine.randomness):
            return method(engine, *args, **kwargs)
    return run


@contextmanager
def use_source(source):
    token = _source.set(source)
    try:
        yield
    finally:
        _source.reset(token)
