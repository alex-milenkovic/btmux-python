"""Observe real production effects during a heat simulation workflow."""

from contextlib import ExitStack, contextmanager
from unittest.mock import patch
from systems import heat_control, ammo_dump, vehicle_fire, stagger, stability
from physics import heights


@contextmanager
def observe(session):
    from systems import combat, piloting, movement_commands
    from systems import heat, criticals
    from physics import jump
    from core.randomness import use_source

    original_damage = combat.apply_damage_with_transfer
    original_notify = movement_commands.notify
    original_roll = piloting.make_piloting_roll
    original_fall = jump.mech_falls

    def hit(*args, **kwargs):
        before = [(s.armor, s.rear, s.internal) for s in args[0].sections]
        result = original_damage(*args, **kwargs)
        session.hits.append(
            dict(
                unit=args[0].name,
                section=int(args[1]),
                requested=args[2],
                resolved=result,
                source=session.source,
                before=before,
                after=[(s.armor, s.rear, s.internal) for s in args[0].sections],
            )
        )
        return result

    def notify(unit, text, audience=2):
        session.messages.append(dict(unit=unit.name, text=text, source=session.source))
        return original_notify(unit, text, audience=audience)

    def roll(*args, **kwargs):
        result = original_roll(*args, **kwargs)
        session.rolls.append(
            dict(
                unit=args[0].name,
                modifier=args[1] if len(args) > 1 else 0,
                roll=result.roll,
                target=result.target,
                success=result.success,
                source=session.source,
            )
        )
        return result

    def scoped(function, source):
        def run(*args, **kwargs):
            previous = session.source
            session.source = source
            try:
                return function(*args, **kwargs)
            finally:
                session.source = previous

        return run

    def fall(*args, **kwargs):
        def dice(name, low, high, fallback):
            stream = 'fall_pilot_rolls' if name == 'pilot_rolls' else name
            return session.dice(stream, low, high, fallback)

        with use_source(dice):
            return original_fall(*args, **kwargs)

    with ExitStack() as stack:
        for module in (heat, criticals):
            stack.enter_context(patch.object(module, 'BTECH_INFERNO_PENALTY', session.inferno_penalty))
        stack.enter_context(patch.object(jump, 'mech_falls', side_effect=scoped(fall, 'fall')))
        stack.enter_context(
            patch.object(combat, "apply_damage_with_transfer", side_effect=hit)
        )
        # Imported aliases retain the same underlying production functions.
        for module in (
            movement_commands,
            heat_control,
            ammo_dump,
            vehicle_fire,
            heights,
            stagger,
            stability,
        ):
            if hasattr(module, "notify"):
                stack.enter_context(patch.object(module, "notify", side_effect=notify))
        for module in (piloting, stagger, stability):
            stack.enter_context(
                patch.object(module, "make_piloting_roll", side_effect=roll)
            )
        stack.enter_context(
            patch.object(
                ammo_dump,
                "blow_dumping_ammo",
                side_effect=scoped(ammo_dump.blow_dumping_ammo, "dump_ignition"),
            )
        )
        original_schedule = session.engine.events.schedule
        sources = {
            "burn_event": "burn_tick",
            "mech_dump_event": "dump_tick",
            "extinguish_event": "extinguish",
            "heat_cutoff_event": "heatcutoff",
            "_inferno_end_event": "inferno_expiry",
            "expire_smoke": "steam_expiry",
        }

        def callback_source(callback):
            label = sources.get(getattr(callback, "__name__", ""), "scheduled_event")
            return scoped(callback, label)

        for event in session.engine.events._events.values():
            event.callback = callback_source(event.callback)

        def schedule(delay, event_type, callback, data=None, data2=None):
            return original_schedule(
                delay, event_type, callback_source(callback), data, data2
            )

        stack.enter_context(
            patch.object(session.engine.events, "schedule", side_effect=schedule)
        )
        stack.enter_context(
            patch.object(
                vehicle_fire,
                "start_burn",
                side_effect=scoped(vehicle_fire.start_burn, "initial_fire"),
            )
        )
        yield
