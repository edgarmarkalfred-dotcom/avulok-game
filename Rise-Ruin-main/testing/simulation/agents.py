"""Deterministic bot policies for the isolated Climb simulation harness.

All movement and spell effects remain delegated to the game's Runner, Level,
Caster, and Spell methods. This module only chooses inputs and observes state.
"""
import math
import random

import pygame

from settings import (GRAVITY, JUMP_V, PROJECTILE_SPEED, RUN_SPEED,
                      LIGHTNING_WARN_TIME, SOLAR_FLARE_WARN_TIME,
                      SUPER_JUMP_MULTIPLIER)


RUNNER_CONFIGS = {
    "steady_climber": {
        "description": "Shortest reachable route; conserves Super Jump and dodges nearby threats.",
        "hazard_margin": 22, "prefer_super_rise": 58, "dodge": True,
        "shield_distance": 52,
    },
    "superjump_climber": {
        "description": "Goal-directed route; spends Super Jump to skip taller rises when ready.",
        "hazard_margin": 12, "prefer_super_rise": 34, "dodge": True,
        "shield_distance": 38,
    },
    "evasive_climber": {
        "description": "Goal-directed route with wider hazard clearance and earlier shielding.",
        "hazard_margin": 34, "prefer_super_rise": 70, "dodge": True,
        "shield_distance": 78,
    },
}

CASTER_CONFIGS = {
    "accurate_benchmark": {
        "description": "Exact current-state aim; leads the Dirty Water projectile when useful.",
        "aim_error_px": 0, "predict_delayed_aim": True, "attempt_interval_frames": 12,
    },
    "practiced_aim": {
        "description": "Small deterministic aim error and a slower decision cadence.",
        "aim_error_px": 10, "predict_delayed_aim": True, "attempt_interval_frames": 18,
    },
    "imperfect_aim": {
        "description": "Larger deterministic aim error and slower decisions.",
        "aim_error_px": 32, "predict_delayed_aim": False, "attempt_interval_frames": 24,
    },
}


def _grid_surfaces(grid):
    found = {id(s): s for cell in grid.cells.values() for s in cell}
    found.update({id(s): s for s in grid.dynamic})
    return list(found.values())


def _merge_platform_surfaces(level):
    """Merge actual solid/one-way top faces into horizontal route segments."""
    rows = {}
    for sprite in _grid_surfaces(level.solids) + _grid_surfaces(level.semis):
        rect = sprite.rect
        if rect.w < level.runner.rect.w:
            continue
        y = round(rect.top, 2)
        rows.setdefault(y, []).append((float(rect.left), float(rect.right)))
    segments = []
    for y, intervals in rows.items():
        intervals.sort()
        start, end = intervals[0] if intervals else (0, 0)
        for left, right in intervals[1:]:
            if left <= end + 1:
                end = max(end, right)
            else:
                segments.append({"left": start, "right": end, "y": y, "goal": False})
                start, end = left, right
        if intervals:
            segments.append({"left": start, "right": end, "y": y, "goal": False})
    return segments


def _flight_range(runner, rise, super_jump=False):
    """Horizontal travel allowed by the game's jump and gravity, approximately."""
    velocity = JUMP_V * (SUPER_JUMP_MULTIPLIER if super_jump else 1.0)
    discriminant = velocity * velocity - 2 * GRAVITY * max(0.0, rise)
    if discriminant < 0:
        return -1.0
    descending_time = (velocity + math.sqrt(discriminant)) / GRAVITY
    return RUN_SPEED * descending_time + runner.rect.w


def _gap(a, b):
    return max(0.0, b["left"] - a["right"], a["left"] - b["right"])


def _route(level, start, config, super_ready):
    """Breadth-first route over surfaces reachable with actual jump envelopes."""
    nodes = _merge_platform_surfaces(level)
    for goal in level.goal_rects:
        nodes.append({"left": float(goal.left), "right": float(goal.right),
                      "y": float(goal.top), "goal": True})
    nodes.append(start)
    start_i = len(nodes) - 1
    edges = [[] for _ in nodes]
    for i, src in enumerate(nodes):
        for j, dst in enumerate(nodes):
            if i == j or dst["y"] >= src["y"] - 1:
                continue
            rise = src["y"] - dst["y"]
            gap = _gap(src, dst)
            modes = []
            if rise <= JUMP_V * JUMP_V / (2 * GRAVITY) and gap <= _flight_range(level.runner, rise):
                modes.append("normal")
            if super_ready and gap <= _flight_range(level.runner, rise, super_jump=True):
                modes.append("super")
            if not modes:
                continue
            use_super = "super" in modes and (
                "normal" not in modes or rise >= config["prefer_super_rise"]
            )
            edges[i].append((j, "super" if use_super else "normal"))

    previous = {start_i: None}
    edge_mode = {}
    queue = [start_i]
    target_i = None
    while queue:
        i = queue.pop(0)
        if nodes[i]["goal"]:
            target_i = i
            break
        # Prefer the path that gains the most height per jump; ties are stable.
        choices = sorted(edges[i], key=lambda pair: (
            -(nodes[i]["y"] - nodes[pair[0]]["y"]),
            _gap(nodes[i], nodes[pair[0]]), pair[0]))
        for j, mode in choices:
            if j not in previous:
                previous[j] = i
                edge_mode[j] = mode
                queue.append(j)
    if target_i is not None:
        path = []
        node_i = target_i
        while node_i is not None:
            path.append(node_i)
            node_i = previous[node_i]
        path.reverse()
        if len(path) > 1:
            next_i = path[1]
            return nodes[next_i], edge_mode[next_i]

    # A local best-progress fallback still requires a geometrically reachable jump.
    candidates = []
    for j, mode in edges[start_i]:
        rise = start["y"] - nodes[j]["y"]
        candidates.append((rise - _gap(start, nodes[j]) * 0.12, j, mode))
    if candidates:
        _, j, mode = max(candidates)
        return nodes[j], mode
    return None, None


def _support(level):
    r = level.runner
    candidates = [s for s in _merge_platform_surfaces(level)
                  if s["y"] >= r.rect.bottom - 2
                  and s["y"] - r.rect.bottom <= 24
                  and s["right"] >= r.rect.left
                  and s["left"] <= r.rect.right]
    if not candidates:
        # Start state can be a few frames above a floor before first landing.
        candidates = [s for s in _merge_platform_surfaces(level)
                      if s["y"] >= r.rect.bottom
                      and s["y"] - r.rect.bottom <= 64
                      and s["right"] >= r.rect.left - 8
                      and s["left"] <= r.rect.right + 8]
    if not candidates:
        return None
    return min(candidates, key=lambda s: s["y"] - r.rect.bottom)


def _hazard_at(level, x, top, margin):
    probe = pygame.FRect(x, top, level.runner.rect.w, level.runner.rect.h)
    probe.inflate_ip(margin * 2, margin)
    if any(probe.colliderect(h.hazard_rect) for h in level.hazards.query(probe)):
        return True
    if any(probe.colliderect(s.rect) for s in level.spike_sprites.sprites()):
        return True
    if any(probe.colliderect(s.rect) for s in level.rock_sprites.sprites()):
        return True
    return False


def _landing_x(level, target, preferred, margin):
    r = level.runner
    low = target["left"] + r.rect.w / 2
    high = target["right"] - r.rect.w / 2
    if target["goal"]:
        low, high = target["left"] + r.rect.w / 2, target["right"] - r.rect.w / 2
    choices = [max(low, min(high, preferred))]
    choices.extend(x for x in range(math.ceil(low), math.floor(high) + 1, 8))
    safe = [x for x in choices if not _hazard_at(level, x, target["y"] - r.rect.h, margin)]
    pool = safe or choices
    return min(pool, key=lambda x: abs(x - preferred))


def _launch_x(level, source, landing_x):
    """Choose a takeoff point the Runner can reach while still standing on source."""
    half = level.runner.rect.w / 2
    low, high = source["left"] + half, source["right"] - half
    return max(low, min(high, landing_x))


def _incoming_threat(level, distance):
    r = level.runner
    for shot in level.projectile_sprites.sprites():
        vx = getattr(shot, "velocity", pygame.Vector2()).x
        vy = getattr(shot, "velocity", pygame.Vector2()).y
        future = shot.rect.move(vx * 0.20, vy * 0.20)
        if abs(future.centery - r.cy) < distance and abs(future.centerx - r.cx) < distance:
            return -1 if future.centerx > r.cx else 1
    for bat in level.spike_sprites.sprites():
        if abs(bat.rect.centery - r.cy) < 24 and abs(bat.rect.centerx - r.cx) < distance:
            return -1 if bat.rect.centerx > r.cx else 1
    if level.solar_flare_active and level.solar_flare_warn_t > 0:
        if abs(level.solar_flare_beam_x - r.cx) < 48:
            return -1 if r.cx > level.width / 2 else 1
    return 0


def _trap_warning(level):
    r = level.runner
    return any(
        trap.charging
        and abs(trap.rect.centery - r.cy) <= r.rect.h + 6
        and ((trap.dir > 0 and r.cx > trap.rect.centerx)
             or (trap.dir < 0 and r.cx < trap.rect.centerx))
        for trap in level.traps
    )


class RunnerAgent:
    def __init__(self, strategy):
        if strategy not in RUNNER_CONFIGS:
            raise ValueError(f"unknown Runner strategy: {strategy}")
        self.strategy = strategy
        self.config = dict(RUNNER_CONFIGS[strategy])
        self.target = None
        self.jump_mode = None
        self._plan_frame = -999

    def act(self, level, frame):
        r = level.runner
        config = self.config
        events = []
        dodge = _incoming_threat(level, config["shield_distance"]) if config["dodge"] else 0
        trap_warning = _trap_warning(level)
        if (dodge or trap_warning) and r.shield_cd <= 0:
            queue_key(events, pygame.K_s)
        if level.flood_active and r.on_ground and r.rect.bottom >= level.flood_y - 24:
            queue_key(events, pygame.K_SPACE)

        if r.on_ground and (self.target is None or frame - self._plan_frame >= 12):
            support = _support(level)
            if support:
                ready = r.sj_cd <= 0 and r.stun <= 0 and not r.jump_locked
                self.target, self.jump_mode = _route(level, support, config, ready)
                if self.target:
                    preferred = (self.target["left"] + self.target["right"]) / 2
                    self.target_x = _landing_x(level, self.target, preferred, config["hazard_margin"])
                    self.launch_x = _launch_x(level, support, self.target_x)
                self._plan_frame = frame

        if self.target is None:
            # No reachable route found: move toward the goal's horizontal span,
            # while still relying on normal collision and gravity updates.
            goal = min(level.goal_rects, key=lambda g: abs(g.centery - r.cy)) if level.goal_rects else None
            target_x = goal.centerx if goal else level.width / 2
            jump_mode = "normal"
        else:
            target_x = self.target_x
            jump_mode = self.jump_mode or "normal"
            if r.on_ground and self.target["y"] < r.rect.bottom - 8:
                target_x = self.launch_x

        direction = 0
        if target_x - r.cx > 7:
            direction = 1
        elif target_x - r.cx < -7:
            direction = -1
        if dodge:
            direction = dodge

        keys = []
        if direction > 0:
            keys.append(pygame.K_d)
        elif direction < 0:
            keys.append(pygame.K_a)

        obstacle_ahead = False
        if direction:
            test = r.rect.move(direction * 18, 0)
            obstacle_ahead = level.hits_solid(test)
        going_up = self.target is not None and self.target["y"] < r.rect.bottom - 8
        if r.on_ground and not r.jump_locked and r.stun <= 0 and (going_up or obstacle_ahead or trap_warning):
            if jump_mode == "super" and r.sj_cd <= 0:
                queue_key(events, pygame.K_q)
            queue_key(events, pygame.K_SPACE)
        if self.target and self.target.get("goal") and r.rect.colliderect(
                pygame.FRect(self.target["left"], self.target["y"],
                             self.target["right"] - self.target["left"], 1)):
            self.target = None
        return key_state(keys), events


def key_state(held=()):
    held = set(held)

    class State:
        def __getitem__(self, key):
            return key in held
    return State()


def queue_key(events, key):
    events.append(pygame.event.Event(pygame.KEYDOWN, key=key))


def _lead_point(level):
    r = level.runner
    target_x, target_y = r.cx, r.cy
    ox, oy = level.orb_pos
    vx, vy = r.vx, r.vy
    speed = PROJECTILE_SPEED
    a = vx * vx + vy * vy - speed * speed
    b = 2 * ((target_x - ox) * vx + (target_y - oy) * vy)
    c = (target_x - ox) ** 2 + (target_y - oy) ** 2
    roots = []
    if abs(a) < 1e-6:
        if abs(b) > 1e-6:
            roots.append(-c / b)
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            roots.extend(((-b - math.sqrt(disc)) / (2 * a),
                          (-b + math.sqrt(disc)) / (2 * a)))
    positive = [t for t in roots if 0 < t < 2.5]
    if positive:
        t = min(positive)
        target_x += vx * t
        target_y += vy * t
    return target_x, target_y


def _world_aim(level, spell_name, predict_delayed):
    r = level.runner
    x, y = r.cx, r.cy
    if predict_delayed and spell_name == "Dirty Water":
        x, y = _lead_point(level)
    elif predict_delayed and spell_name == "Lightning":
        x += r.vx * LIGHTNING_WARN_TIME
        y += r.vy * LIGHTNING_WARN_TIME
    elif predict_delayed and spell_name == "Solar Flare":
        x += r.vx * SOLAR_FLARE_WARN_TIME
        y += r.vy * SOLAR_FLARE_WARN_TIME
    if spell_name == "Moving Bats" and level.spike_zones:
        zone = min((z for _, z in level.spike_zones), key=lambda z: abs(z.centery - y))
        x, y = zone.centerx, r.cy
    elif spell_name == "Moss":
        # Moss validates against actual platform geometry near this aim point.
        x, y = r.cx, r.rect.bottom
    return x, y


def effect_snapshot(level):
    return {
        "Dirty Water": len(level.projectile_sprites),
        "Stun": level.runner.stun,
        "Moving Bats": len(level.spike_sprites),
        "Lightning": len(level.pending_lightning),
        "Moss": len(level.moss_sprites),
        "Inversion": level.runner.inverted,
        "Earthquake": level.earthquake_t,
        "Solar Flare": (level.solar_flare_active, level.solar_flare_warn_t,
                        level.solar_flare_beam_x),
        "Typhoon": (level.typhoon_t, len(level.rain_drops)),
        "Flood": (level.flood_active, level.flood_y, level.flood_t),
    }


def effect_confirmed(name, before, after):
    """True only when the immediate, observable game state changed for this spell."""
    return after[name] != before[name]


class CasterAgent:
    def __init__(self, strategy, seed):
        if strategy not in CASTER_CONFIGS:
            raise ValueError(f"unknown Caster strategy: {strategy}")
        self.strategy = strategy
        self.config = dict(CASTER_CONFIGS[strategy])
        self.rng = random.Random(seed ^ 0x5CA57E2)
        self.cursor = seed % 10

    def act(self, level, caster, frame, metrics):
        interval = self.config["attempt_interval_frames"]
        if frame % interval:
            return
        # Search real spell slots in a deterministic rotating order. Caster's
        # own cooldown and major-spell cap remain authoritative.
        selected = None
        for offset in range(10):
            index = (self.cursor + offset) % 10
            caster.select(index)
            if caster.can_cast(level):
                selected = index
                break
        if selected is None:
            return

        spell_name = caster.spells[selected].name
        world_x, world_y = _world_aim(level, spell_name, self.config["predict_delayed_aim"])
        error = self.config["aim_error_px"]
        if error:
            world_x += self.rng.gauss(0, error)
            world_y += self.rng.gauss(0, error)
        ox, oy = level.all_sprites.draw_offset
        screen_point = (round(world_x + ox), round(world_y + oy))
        before = effect_snapshot(level)
        metrics["cast_attempts"] += 1
        metrics["spell_attempts"][spell_name] = metrics["spell_attempts"].get(spell_name, 0) + 1
        accepted = caster.cast(level, screen_point)
        self.cursor = (selected + 1) % 10
        if accepted:
            metrics["accepted_casts"] += 1
            metrics["accepted_casts_by_spell"][spell_name] = metrics["accepted_casts_by_spell"].get(spell_name, 0) + 1
            after = effect_snapshot(level)
            if effect_confirmed(spell_name, before, after):
                metrics["confirmed_spell_effects"][spell_name] = metrics["confirmed_spell_effects"].get(spell_name, 0) + 1

