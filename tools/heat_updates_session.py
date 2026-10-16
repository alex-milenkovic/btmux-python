"""Heat workflow sessions over the existing movement engine and commands."""

from dataclasses import asdict
from contextlib import redirect_stdout
from io import StringIO
from core.randomness import use_source
from tools.movement import Session as MovementSession
from tools.movement_inputs import fields, number, boolean, string, array, coordinates
from tools.heat_updates_inputs import prepare, apply_unit, location
from tools.heat_updates_dice import Dice
from tools.heat_updates_observation import observe
from systems import heat, heat_control, ammo_dump, vehicle_fire, stagger, stability
from physics import heights
from entities.mech import MechStatus as S


def deadline(event):
    return event.tick if event is not None and not event.zombie else None


class Session(MovementSession):
    def __init__(self, document):
        document, base, extras, temperature, underlays = prepare(document)
        super().__init__(base)
        config = document.get("config", {})
        self.inferno_penalty = boolean(config.get('inferno_penalty', False))
        self.engine.heartbeat_enabled = boolean(config.get("heartbeat", True))
        self.engine.advanced_vehicle_fire = boolean(
            config.get("advanced_vehicle_fire", False)
        )
        self.engine.new_stagger = number(config.get("new_stagger", 1), 0, 2, True)
        self.engine.stagger_interval = number(
            config.get("stagger_interval", 5), 1, integer=True
        )
        self.engine.stagger_tonnage = boolean(config.get("stagger_tonnage", True))
        self.engine.heatcutoff_enabled = boolean(config.get("heatcutoff_enabled", True))
        clock = fields(
            document.get("clock", {}), ("wall", "event", "heartbeat", "last_dispatch")
        )
        self.engine.sim_now = number(clock.get("wall", 0), integer=True)
        self.engine.events.set_tick(number(clock.get("event", 0), integer=True))
        self.engine.global_tick = number(clock.get("heartbeat", 0), 0, integer=True)
        self.engine._last_dispatch_run = number(
            clock.get("last_dispatch", self.engine.sim_now), integer=True
        )
        self.board.temp = temperature
        if boolean(base["map"].get("special_rules", False)):
            self.board.flags |= 2
        from systems.map_conditions import alter_conditions
        alter_conditions(self.board)
        for item in underlays:
            fields(item, ("at", "terrain", "remaining"), ("at", "terrain"))
            x, y = coordinates(item["at"], self.board)
            from tools.path_cost_inputs import terrain_value
            from entities.map import FIRE, SMOKE

            visible = self.board.terrain(x, y)
            if visible not in (FIRE, SMOKE):
                raise ValueError("underlying terrain requires FIRE/SMOKE")
            real = terrain_value(string(item["terrain"]))
            if real in (FIRE, SMOKE):
                raise ValueError("underlying terrain cannot itself be an overlay")
            from physics.decorations import add_decoration
            duration = number(item.get("remaining", 120), 0, 32767, True)
            self.board.set_terrain(x, y, real)
            add_decoration(self.engine, self.board, x, y, visible, duration)
        for unit, cfg in zip(self.units.values(), extras):
            apply_unit(self, unit, cfg)
        self.dice = Dice(document.get("random", {}))
        self.source = "fixture"
        self.initial = self.snapshot()

    def snapshot(self):
        units = {name: self.unit_snapshot(u) for name, u in self.units.items()}
        return dict(
            clock=dict(
                wall=self.engine.sim_now,
                event=self.engine.tick,
                heartbeat=self.engine.global_tick,
            ),
            units=units,
            decorations=[
                dict(
                    at=list(key),
                    terrain=d["terrain"],
                    underlying=d["underlying"],
                    deadline=deadline(d["event"]),
                )
                for key, d in self.board.decorations.items()
            ],
        )

    def unit_snapshot(self, u):
        from systems.enhanced_crits import part_temp_nuke
        from entities.crittypes import is_ammo, ammo2weapon_i
        from physics.collision import mech_rterrain
        from entities.mech import MechStatus2

        nodes = [
            dict(amount=n["amount"], wall=n["occurred_at"], counted=n["counted"])
            for n in u.stagger_damage_list
        ]
        bins = [
            dict(section=loc, slot=pos + 1, rounds=c.data, weapon=ammo2weapon_i(c.type),
                 condition=int(c.firemode), temporary_failure=part_temp_nuke(c))
            for loc, s in enumerate(u.sections)
            for pos, c in enumerate(s.criticals)
            if is_ammo(c.type)
        ]
        return dict(
            heat=u.heat,
            plus_heat=u.plus_heat,
            minus_heat=u.minus_heat,
            weapon_heat=u.weap_heat,
            active_capacity=heat_control.active_capacity(u),
            disabled_capacity=u.disabled_sinks,
            cutoff=u.has_crit_status(heat_control.CritStatus.HEATCUTOFF),
            cutoff_deadline=deadline(u._cutoff_event),
            last_overheat_tick=getattr(u, "_last_overheat_tick", 0),
            pilot_hits=u.pilot_hits,
            pilot_skill_base=u.pilot_skill_base,
            max_speed=u.max_speed,
            turn_damage=u.turn_damage,
            last_fall_levels=getattr(u, 'last_fall_levels', None),
            searchlight=u.has_status2(MechStatus2.SLITE_ON),
            real_terrain=mech_rterrain(u) if u.map is not None else None,
            bins=bins,
            dumping=u.dumping,
            dump_scope=(
                asdict(u._dump_selection) if getattr(u, "_dump_selection", None) else None
            ),
            dump_deadline=deadline(getattr(u, "_dump_event", None)),
            burning_sides={
                str(loc): event.tick
                for loc, event in vehicle_fire.burning_sides(u).items()
            },
            extinguish_deadline=deadline(getattr(u, "_extinguish_event", None)),
            inferno_deadline=deadline(getattr(u, "_burn_event", None)),
            jellied=u.has_crit_status(heat_control.CritStatus.JELLIED),
            stagger=nodes,
            uncounted_damage=stagger.current_damage(u, self.engine.sim_now),
            counted_damage=stagger.current_damage(u, self.engine.sim_now, True),
            last_stagger_check=u.last_stagger_check,
            stagger_stamp=u.stagger_stamp,
            last_dropship_notice=getattr(u, "last_dropship_notice", 0),
            started=u.is_started,
            fallen=u.is_fallen,
            jumping=u.is_jumping,
            landed=u.has_status(S.LANDED),
            destroyed=u.is_destroyed,
            kill_reason=u.kill_reason or None,
            at=[u.x, u.y, u.z],
            fz=u.fz,
            speed=u.speed,
            desired_speed=u.desired_speed,
            vertical_speed=u.vertical_speed,
            facing=u.facing,
            desired_facing=u.desired_facing,
            turret_facing=getattr(u, "turret_facing", 0),
            los=bool(u.mapflag & 1),
            sections=[
                dict(front=s.armor, rear=s.rear, internal=s.internal, recycle=s.recycle)
                for s in u.sections
            ],
            weapons=[
                dict(
                    number=i,
                    recycle=w.recycle,
                    slot_recycle=u.sections[w.section].criticals[w.critical].data,
                    temporary_failure=part_temp_nuke(
                        u.sections[w.section].criticals[w.critical]
                    ),
                )
                for i, w in enumerate(u.weapons)
            ],
            unavailable=sorted(u.unavailable_updates),
        )

    def command(self, action):
        fields(action, ("op", "unit", "name", "args"), ("unit", "name", "args"))
        u = self.unit(action)
        name = string(action["name"])
        args = array(action["args"])
        if any(not isinstance(arg, str) for arg in args):
            raise ValueError("command args must be strings")
        if name in ("heatcutoff", "extinguish", "startup") and args:
            return dict(accepted=False, message="Unexpected arguments")
        if name == "heatcutoff":
            result = heat_control.heat_cutoff(self.engine, u, self.callers[u.name])
        elif name == "dump":
            result = ammo_dump.mech_dump(
                self.engine, u, " ".join(args), self.callers[u.name]
            )
        elif name == "extinguish":
            result = vehicle_fire.extinguish(self.engine, u, self.callers[u.name])
        elif name == "startup":
            result = heat.attempt_startup(u)
            return dict(accepted=result.success, message=result.message)
        elif name == "target":
            if len(args) != 1 or args[0] not in self.units:
                return dict(accepted=False, message="Unknown target")
            u.target = self.units[args[0]]._id
            return dict(accepted=True, message="Target selected.")
        elif name == "fire":
            if len(args) != 1:
                return dict(accepted=False, message="Specify one weapon number.")
            try:
                index = int(args[0])
            except ValueError:
                return dict(accepted=False, message="Illegal weapon number.")
            from systems.combat import fire_weapon_number

            shot = fire_weapon_number(self.engine, u, index)
            return dict(accepted=shot.roll > 0, message=' '.join(shot.messages),
                        hit=shot.hit, attack_roll=shot.roll)
        else:
            return super().command(action)
        return dict(accepted=result[0], message=result[1])

    def action(self, action):
        if not isinstance(action, dict) or "op" not in action:
            raise ValueError("action requires op")
        op = string(action["op"])
        if op == 'scan':
            fields(action, ('op', 'unit'), ('unit',))
            self.unit(action)
            from systems.sensors import update_los_info

            update_los_info(self.board)
            return super().action(action)
        if op == "inspect":
            fields(action, ("op", "unit"))
            if 'unit' in action:
                self.unit(action)
            return {}
        if op == "dispatch":
            fields(action, ("op", "seconds"), ("seconds",))
            for _ in range(number(action["seconds"], 0, 10000, True)):
                self.engine.dispatch()
            return {}
        if op == "heartbeat":
            fields(action, ("op", "wall_seconds"), ("wall_seconds",))
            self.engine.sim_now += number(action["wall_seconds"], 0, 10000, True)
            self.engine.heartbeat()
            return {}
        if op == "maintain":
            return self.maintain(action)
        if op == "stagger":
            return self.stagger(action)
        if op == "external_heat":
            return self.external_heat(action)
        if op == "hit":
            return self.hit(action)
        if op == "enter_hex":
            return self.enter_hex(action)
        return super().action(action)

    def maintain(self, action):
        fields(action, ("op", "unit", "kind"), ("unit", "kind"))
        u = self.unit(action)
        kind = string(action["kind"])
        if kind == "heat":
            heat.update_from_environment(u, self.engine.tick)
        elif kind == "overheat":
            heat.check_overheat(u, self.engine.tick)
        elif kind == "pilot":
            stability.update_pilot_skill_rolls(self.engine, u)
        elif kind == "height":
            heights.maintain_height(u, u.z)
        elif kind == "water_extinguish":
            from systems.missile import water_extinguish_inferno

            water_extinguish_inferno(self.engine, u)
        elif kind == "stagger_expiry":
            stagger.clear_expired(u, self.engine.sim_now)
        elif kind == "stagger_totals":
            return dict(
                uncounted=stagger.current_damage(u, self.engine.sim_now),
                counted=stagger.current_damage(u, self.engine.sim_now, True),
            )
        elif kind == "dropship_notice":
            return dict(emitted=heights.dropship_notice(u, self.engine.tick))
        else:
            raise ValueError("unknown maintenance kind " + kind)
        return dict(unavailable=sorted(u.unavailable_updates))

    def stagger(self, action):
        fields(action, ("op", "unit", "action", "level"), ("unit", "action", "level"))
        u = self.unit(action)
        kind = string(action["action"])
        level = number(action["level"], 0, integer=True)
        if kind == "CLEAR_ALL":
            stagger.clear_all(u)
        elif kind in ("MARK", "REMOVE"):
            {"MARK": stagger.mark_damage, "REMOVE": stagger.remove_damage}[kind](
                u, level
            )
        else:
            raise ValueError("unknown stagger action " + kind)
        return {}

    def external_heat(self, action):
        fields(
            action,
            ("op", "unit", "attacker", "heat", "inferno"),
            ("unit", "heat", "inferno"),
        )
        from systems.missile import heat_effect

        heat_effect(
            self.engine,
            self.units[action["attacker"]] if "attacker" in action else None,
            self.unit(action),
            number(action["heat"], 0, integer=True),
            boolean(action["inferno"]),
        )
        return {}

    def hit(self, action):
        fields(
            action,
            ("op", "target", "attacker", "section", "arc", "damage", "weapon"),
            ("target", "section", "arc", "damage", "weapon"),
        )
        from systems.combat import apply_damage_with_transfer
        from entities.weapon import get_weapon_by_index

        u = self.units[string(action["target"])]
        attacker = self.units[action["attacker"]] if "attacker" in action else u
        index = action["weapon"]
        weapon = (
            None
            if index is None
            else get_weapon_by_index(
                attacker.weapons[
                    number(index, 0, len(attacker.weapons) - 1, True)
                ].weapon_idx
            )
        )
        arc = {"FRONT": False, "REAR": True}[string(action["arc"])]
        apply_damage_with_transfer(
            u,
            location(u, action["section"]),
            number(action["damage"], 0, integer=True),
            arc,
            attacker,
            weapon=weapon,
            engine=self.engine,
        )
        return {}

    def enter_hex(self, action):
        fields(action, ("op", "unit", "at", "fallen"), ("unit", "at"))
        from physics.movement import on_hex_entered

        u = self.unit(action)
        oldx, oldy, oldz = u.x, u.y, u.z
        oldfx, oldfy = u.fx, u.fy
        x, y, z = coordinates(action["at"], self.board, True)
        u.set_hex_position(x, y)
        u.z = z
        u.fz = z * 64.5
        u.last_x, u.last_y = oldx, oldy
        if "fallen" in action:
            if boolean(action["fallen"]):
                u.set_status(S.FALLEN)
            else:
                u.clear_status(S.FALLEN)
        on_hex_entered(u, oldx, oldy, u.fx - oldfx, u.fy - oldfy, oldz)
        heights.maintain_height(u, oldz)
        return {}

    def observe(self):
        return observe(self)

    def run(self):
        results = []
        with self.observe(), use_source(self.dice):
            for action in self.actions:
                self.source = action.get("op", "invalid")
                self.messages = []
                self.rolls = []
                self.hits = []
                output = StringIO()
                with redirect_stdout(output):
                    result = self.action(action)
                if output.getvalue():
                    raise ValueError("engine diagnostic: " + output.getvalue().strip())
                results.append(
                    dict(
                        op=action["op"],
                        **result,
                        messages=list(self.messages),
                        rolls=list(self.rolls),
                        damage=list(self.hits),
                        snapshot=self.snapshot()
                    )
                )
        return dict(
            initial=self.initial,
            final=self.snapshot(),
            results=results,
            draws=self.dice.draws,
            consumed=self.dice.consumed,
        )
