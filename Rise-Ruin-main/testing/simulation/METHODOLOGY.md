# Climb simulation methodology

## Running

Use the interpreter that launches the project:

```bash
/home/mrrobot/Climb/.venv/bin/python testing/simulation/run_simulation.py --matches 100 --seed 20261020
```

This writes `testing/simulation/baseline_results.json`. To check CLI options without
starting matches, add `--help`. The harness initializes Pygame with dummy SDL video
and audio drivers; it does not open the visible game window.

## Game fidelity

Each match loads a map listed in `settings.LEVELS`, constructs the real `Level` and
`Caster`, and steps them at a fixed `1/FPS` interval. Agent input reaches the real
`Runner.handle_event`, `Runner.update`, and `Level.update`. The Level still runs the
game's spatial collisions, projectiles, traps, pickups, spell timers/effects, goal
contact, heart loss, and winner assignment. The harness observes Runner hit and
collision methods with wrappers that immediately delegate to the original methods;
it does not replace their behavior.

The Runner agents plan jumps over the solid and one-way platform geometry loaded
from the map. Their reach estimates use the game's jump velocity, gravity, run
speed, and Super Jump multiplier. They choose real key events and let the normal
collision path resolve landings. They avoid known spike geometry, nearby projectiles
and moving bats, charging Dart Traps, warned Solar Flare zones, and a nearby rising
flood when those hazards are observable. Strategies differ in hazard clearance,
Super Jump use, and shield distance.

Caster agents call `Caster.select`, `Caster.can_cast`, and `Caster.cast`; the game's
validation, cooldowns, major-spell cap, and spell implementation remain in force.
`accurate_benchmark` uses current state and predicts projectile/delayed strike
positions; `practiced_aim` adds small seeded aim error; `imperfect_aim` adds larger
seeded error and does not predict delayed aims. Spell target coordinates are
converted between world and screen space using the game's camera offset.
Same-frame Runner/Caster inputs are ordered deterministically by the match seed and
recorded per match; Runner decisions are planned from the pre-update state, then
their queued key events are dispatched in that order.

## Metrics

- `cast_attempts` counts calls made to `Caster.cast`; `accepted_casts` counts true
  returns from that method. `accepted_casts_by_spell` records those calls by slot.
- `confirmed_spell_effects` counts an immediate observable state change in the
  game's projectile/effect groups or spell timers. It does not claim a later hit.
- `confirmed_runner_hits_all_sources` counts successful returns from the real
  `Runner.hit`, regardless of whether the source was a spell, trap, or hazard.
  Spell hit attribution and trap deaths are null because the game does not expose
  source attribution.
- Collision check/contact counts observe the Runner's actual solid, one-way, and
  map-bound methods. They do not classify every obstacle or hazard outcome.
- Caster health, Caster survival time, cooldown uptime, and trap-attributed deaths
  are null: those states are absent or not attributable in the current game.
- `timeout` is a harness cutoff, not an in-game result. There are no respawns.

## Reproducibility and scope

Every match records its seed, map file, authored starting position, fixed timestep,
timeout, strategy names/configuration, and Caster aim RNG seed. Python's global RNG
and the `Level.rng` are seeded per match. The game uses the global RNG for pickup
animation timing and Typhoon rain initialization; it uses `Level.rng` for trap
offsets, earthquake rocks/shake, and rain recycling. Because Typhoon shares the
global RNG with non-gameplay pickup animation, adding/removing pickups can change
its generated rain sequence. No other uncontrolled gameplay randomness was found.

The interactive game uses a capped wall-clock timestep, while this harness fixes
the timestep for repeatability. Only maps exposed by `settings.LEVELS` are included;
the current game exposes one map and one authored spawn. Results therefore cannot
establish balance across unavailable maps or starts. Bots are benchmark policies,
not human models. In particular, the accurate Caster is an upper-bound targeting
benchmark; compare it with the noisier strategies and goal-directed Runner agents.

`smoke_results.json` preserves the earlier five-match smoke run. It is marked as
pre-audit output: its cast counts are accepted casts and it did not measure
confirmed effects or hits. Do not combine it with reports from the revised harness.
