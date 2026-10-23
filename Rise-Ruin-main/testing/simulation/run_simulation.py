"""Headless, deterministic harness that steps Climb's existing game objects."""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))
os.chdir(CODE)  # Same relative TMX path used by Game.

import pygame

if not hasattr(pygame, "FRect") or not hasattr(pygame.Surface((1, 1)), "get_frect"):
    raise SystemExit(
        "Climb simulation unavailable: this game requires pygame-ce "
        "(pygame.FRect and Surface.get_frect), but this interpreter has standard pygame. "
        "No substitute collision implementation is used by this harness."
    )

from pytmx.util_pygame import load_pygame
from settings import LEVELS, FPS
from level import Level
from caster import Caster
from agents import (CASTER_CONFIGS, RUNNER_CONFIGS, CasterAgent, RunnerAgent)

DT = 1 / FPS
TIMEOUT_SECONDS = 90


def instrument_runner(runner, metrics):
    """Observe calls/state changes while delegating every action unchanged."""
    original_hit = runner.hit

    def observed_hit(from_x):
        dealt = original_hit(from_x)
        if dealt:
            metrics["confirmed_runner_hits"] += 1
        return dealt

    runner.hit = observed_hit
    original_event = runner.handle_event

    def observed_event(event):
        shield_before, jump_before = runner.shield, runner.sj_active
        result = original_event(event)
        if runner.shield > shield_before:
            metrics["shield_activations"] += 1
        if runner.sj_active > jump_before:
            metrics["super_jump_activations"] += 1
        return result

    runner.handle_event = observed_event
    metrics["runner_collision_checks"] = {
        "solid_x": 0, "solid_y": 0, "one_way": 0, "map_bounds": 0,
    }
    metrics["runner_collision_contacts"] = {
        "solid_x": 0, "solid_y": 0, "one_way": 0, "map_bounds": 0,
    }
    for method_name, label in (("collide_x", "solid_x"), ("collide_y", "solid_y"),
                               ("collide_one_way", "one_way"), ("clamp_to_map", "map_bounds")):
        original = getattr(runner, method_name)

        def observed_collision(*args, _original=original, _label=label, **kwargs):
            rect_before = (runner.rect.x, runner.rect.y, runner.rect.w, runner.rect.h)
            metrics["runner_collision_checks"][_label] += 1
            result = _original(*args, **kwargs)
            rect_after = (runner.rect.x, runner.rect.y, runner.rect.w, runner.rect.h)
            if rect_before != rect_after:
                metrics["runner_collision_contacts"][_label] += 1
            return result

        setattr(runner, method_name, observed_collision)


def simulate(seed, runner_strategy, caster_strategy, map_name, trial):
    import random

    random.seed(seed)  # game code's remaining module-global random calls
    file = next(f for name, f in LEVELS if name == map_name)
    tmx = load_pygame(str(ROOT / "data" / "levels" / file))
    level = Level(tmx, map_name, rng=random.Random(seed))
    caster = Caster()
    runner = level.runner
    metrics = {
        "cast_attempts": 0, "accepted_casts": 0, "spell_attempts": {},
        "accepted_casts_by_spell": {}, "confirmed_spell_effects": {},
        "confirmed_runner_hits": 0, "shield_activations": 0,
        "super_jump_activations": 0,
    }
    instrument_runner(runner, metrics)
    runner_agent = RunnerAgent(runner_strategy)
    caster_agent = CasterAgent(caster_strategy, seed)
    initial_bottom = runner.rect.bottom
    starting_position = [round(runner.rect.x, 3), round(runner.rect.y, 3)]
    input_order = "runner_first" if seed % 2 else "caster_first"
    frame = 0
    timeout_frames = int(TIMEOUT_SECONDS * FPS)
    while not level.winner and frame < timeout_frames:
        # GameScene receives events before update; then Caster.update and Level.update.
        keys, runner_events = runner_agent.act(level, frame)
        if input_order == "runner_first":
            for event in runner_events:
                runner.handle_event(event)
            caster_agent.act(level, caster, frame, metrics)
        else:
            caster_agent.act(level, caster, frame, metrics)
            for event in runner_events:
                runner.handle_event(event)
        caster.update(DT)
        level.update(DT, keys)
        frame += 1

    duration = frame * DT
    result = level.winner or "timeout"
    exercised = sorted(metrics["accepted_casts_by_spell"])
    return {
        "trial": trial,
        "seed": seed,
        "configuration": {
            "map": map_name,
            "map_file": file,
            "starting_position_world": starting_position,
            "fixed_dt_seconds": DT,
            "timeout_seconds": TIMEOUT_SECONDS,
            "same_frame_input_order": input_order,
            "runner_strategy": runner_strategy,
            "runner_agent": runner_agent.config,
            "caster_strategy": caster_strategy,
            "caster_agent": {**caster_agent.config,
                              "aim_rng_seed": seed ^ 0x5CA57E2,
                              "initial_spell_cursor": seed % 10},
        },
        "result": result,
        "duration_seconds": round(duration, 3),
        "runner_survival_seconds": round(duration, 3),
        "caster_survival_seconds": None,
        "runner_damage_received": metrics["confirmed_runner_hits"],
        "confirmed_runner_hits_all_sources": metrics["confirmed_runner_hits"],
        "caster_damage_received": None,
        "cast_attempts": metrics["cast_attempts"],
        "accepted_casts": metrics["accepted_casts"],
        "spell_attempts": metrics["spell_attempts"],
        "accepted_casts_by_spell": metrics["accepted_casts_by_spell"],
        "spells_exercised": exercised,
        "confirmed_spell_effects": metrics["confirmed_spell_effects"],
        "spell_hit_attribution": None,
        "shield_activations": metrics["shield_activations"],
        "super_jump_activations": metrics["super_jump_activations"],
        "cooldown_availability_seconds": None,
        "runner_collision_checks": metrics["runner_collision_checks"],
        "runner_collision_contacts": metrics["runner_collision_contacts"],
        "deaths": int(result == "caster"),
        "respawns": 0,
        "trap_deaths": None,
        "runner_final_hearts": runner.hearts,
        "runner_progress": round(max(0.0, min(1.0,
            (initial_bottom - runner.rect.bottom) /
            max(1, initial_bottom - level.goal_top))), 4),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--map", choices=[name for name, _ in LEVELS], default=LEVELS[0][0])
    parser.add_argument("--output", default=str(Path(__file__).with_name("baseline_results.json")))
    args = parser.parse_args()
    pygame.init()
    # Pytmx's game loader calls Surface.convert(); a dummy SDL display keeps
    # that path working without opening a visible window.
    pygame.display.set_mode((1, 1))
    try:
        matchups = [(r, c) for r in RUNNER_CONFIGS for c in CASTER_CONFIGS]
        map_name = args.map
        rows = [simulate(args.seed + i, *matchups[i % len(matchups)], map_name, i + 1)
                for i in range(args.matches)]
        wins = {"runner": 0, "caster": 0, "timeout": 0}
        for row in rows:
            wins[row["result"]] += 1
        report = {
            "kind": "simulation_run", "matches_requested": args.matches,
            "seed_base": args.seed, "timeout_seconds": TIMEOUT_SECONDS,
            "python": sys.executable, "pygame": pygame.version.ver,
            "fixed_dt_seconds": DT,
            "runner_strategies": RUNNER_CONFIGS,
            "caster_strategies": CASTER_CONFIGS,
            "strategy_matchup_schedule": matchups,
            "maps": [map_name], "outcomes": wins,
            "win_percent_of_all_matches": {
                "runner": round(100 * wins["runner"] / max(1, args.matches), 2),
                "caster": round(100 * wins["caster"] / max(1, args.matches), 2),
            },
            "matches": rows,
            "limitations": [
                "The game has no respawn; respawns are zero by construction.",
                "Caster damage received is unavailable: the game has no Caster health.",
                "Timeout is a harness cutoff, not an in-game match result.",
                "Trap-specific deaths and hit attribution are unavailable; confirmed Runner hits combine all sources.",
                "Caster survival time and spell cooldown uptime are unavailable.",
                "Spell effect counts mean an immediate, observable game-state change; later hit outcomes are not attributed to a spell.",
                "Simulation uses fixed 1/FPS steps; the interactive game uses a capped wall-clock timestep.",
                "Only maps in settings.LEVELS are offered; currently that is one map and one authored starting position.",
                "Python's global random generator and Level.rng are seeded per match. Runner decisions are deterministic; Caster aim noise has a separate recorded seed.",
            ],
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"matches": len(rows), "outcomes": wins, "output": str(output), "results": rows}, indent=2))
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
