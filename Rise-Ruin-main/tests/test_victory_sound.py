import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

import sounds
from level import Level


def test_level_set_winner_plays_victory_sound(monkeypatch):
    played = []
    monkeypatch.setattr(sounds, "play", lambda name, loops=0: played.append((name, loops)))

    level = Level.__new__(Level)
    level.winner = None

    level.set_winner("runner")
    assert level.winner == "runner"
    assert played == [("victory", 0)]

    level.set_winner("runner")
    assert played == [("victory", 0)]

    level.set_winner("caster")
    assert level.winner == "runner"
    assert played == [("victory", 0)]


def test_stop_all_sfx_keeps_victory_sound(monkeypatch):
    stopped = []
    fake_sfx = {
        "victory": type("SoundStub", (), {"stop": lambda self: stopped.append("victory")})(),
        "runner_jump": type("SoundStub", (), {"stop": lambda self: stopped.append("runner_jump")})(),
    }
    monkeypatch.setattr(sounds, "_sfx", fake_sfx)

    sounds.stop_all_sfx()

    assert stopped == ["runner_jump"]
