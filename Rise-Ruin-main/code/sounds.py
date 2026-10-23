"""
Sound system for Castle Climb.
====================================================
DROP YOUR AUDIO FILES INTO:
    Climb-main/sounds/

Supported formats: .mp3  .ogg  .wav  (anything pygame.mixer can load)

FILE NAME → WHAT IT PLAYS
--------------------------
BACKGROUND MUSIC
  bgm_menu.mp3          – loops on the main menu
  bgm_game.mp3          – loops during a match

RUNNER EVENTS
  runner_jump.wav       – normal jump
  runner_land.wav       – landing on ground / platform
  runner_hurt.wav       – loses a heart
  runner_shield.wav     – shield activated
  runner_bounce.wav     – hits a bounce pad
  runner_win.wav        – runner reaches the goal
  runner_lose.wav       – runner dies (0 hearts)
  runner_superjump.wav  – super-jump (Q) activated
  runner_stun.wav       – runner gets stunned

CASTER / SPELL EVENTS
  cast_generic.wav      – fallback for any spell with no specific sound
  spell_water.wav       – Dirty Water projectile fired
  spell_stun.wav        – Stun spell cast
  spell_bats.wav        – Moving Bats placed
  spell_lightning.wav   – Lightning warning starts
  spell_lightning_hit.wav – Lightning strikes
  spell_moss.wav        – Moss placed
  spell_inversion.wav   – Inversion cast
  spell_earthquake.wav  – Earthquake starts
  spell_flare_warn.wav  – Solar Flare warning phase
  spell_flare_hit.wav   – Solar Flare strikes
  spell_typhoon.wav     – Typhoon / rain starts
  spell_flood.wav       – Flood activated
  spell_flood_rise.wav  – Flood water rising (looping)

UI EVENTS
  ui_button_click.wav   – any button clicked
  ui_select.wav         – spell slot selected / changed
  ui_countdown.wav      – each countdown tick (3, 2, 1)
  ui_go.wav             – countdown reaches 0 (GO!)

MATCH EVENTS
  match_start.wav       – match begins (after countdown)

HOW VOLUME WORKS
  BGM_VOLUME      – background music volume  (0.0 – 1.0)
  SFX_VOLUME      – all sound effects volume (0.0 – 1.0)
  Change them at the bottom of this file or call set_volumes() at runtime.
"""

import os
import pygame

# ------------------------------------------------------------------ config
# Folder that contains all audio files (one level above code/)
_SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'sounds')

BGM_VOLUME = 0.38   # default background music volume (0.0–1.0)
MENU_BGM_VOLUME = 1
GAME_BGM_VOLUME = 0.80
SFX_VOLUME = 0.75   # sound effects     (0.0–1.0)
_SOUND_VOLUME_OVERRIDES = {
    "runner_hurt": 1.0,
    "get_damaged": 1.0,
    "ui_button_click": 0.5,
    "runner_jump": 0.5,
    "moss": 1.0,
    "denied": 0.6,
    "runner_shield": 0.8,
    "runner_superjump": 0.8,
    "spell_bats": 0.8,
    "speed_up": 0.8,
    "heart": 0.8,
    "spell_typhoon": 0.8,
    "typhoon": 0.8,
    "spell_flood": 0.8,
    "flood": 0.8,
    "alarm": 0.70,
    "spell_earthquake": 0.7,
    "earthquake": 1.0,
    "spell_flare_warn": 0.9,
    "solar_flare": 0.9,
    "spell_inversion": 0.7,
    "invert": 0.7,
}

# ------------------------------------------------------------------ internal state
_sfx    = {}          # name → pygame.Sound (or None if file not found)
_warned = set()       # names already warned about so we only print once
_ready  = False       # True after init() succeeds
_bgm_file = None      # currently playing BGM filename
_prev_overrides = {}


# ------------------------------------------------------------------ init
def init():
    """Call once after pygame.init(). Safe to call multiple times."""
    global _ready
    if _ready:
        return
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        _ready = True
    except pygame.error as e:
        print(f"[sounds] mixer init failed: {e}  – game will run without audio.")


# ------------------------------------------------------------------ helpers
_SOUND_ALIASES = {
    "runner_hurt": ("runner_hurt", "get_damaged"),
    "runner_shield": ("runner_shield", "shield"),
    "runner_superjump": ("runner_superjump", "super_jump"),
    "spell_lightning": ("spell_lightning", "lightning"),
    "spell_water": ("spell_water", "water"),
    "spell_stun": ("spell_stun", "stun"),
    "spell_bats": ("spell_bats", "bat"),
    "spell_moss": ("spell_moss", "moss"),
    "spell_inversion": ("spell_inversion", "invert"),
    "spell_earthquake": ("spell_earthquake", "earthquake"),
    "spell_flare_warn": ("spell_flare_warn", "solar_flare"),
    "spell_typhoon": ("spell_typhoon", "typhoon"),
    "spell_flood": ("spell_flood", "flood"),
    "denied": ("denied",),
    "moss": ("moss",),
    "speed_up": ("speed_up",),
    "heart": ("heart",),
}


def _candidate_names(name):
    aliases = _SOUND_ALIASES.get(name, (name,))
    seen = []
    for candidate in aliases:
        if candidate not in seen:
            seen.append(candidate)
    return tuple(seen)


def _effective_volume(name, candidate):
    value = _SOUND_VOLUME_OVERRIDES.get(candidate, _SOUND_VOLUME_OVERRIDES.get(name, SFX_VOLUME))
    return max(0.0, min(1.0, value))


def _load(name):
    """Return a cached Sound for `name`, or None if the file is missing."""
    if name in _sfx:
        return _sfx[name]
    if not _ready:
        _sfx[name] = None
        return None
    for candidate in _candidate_names(name):
        for ext in (".wav", ".ogg", ".mp3"):
            path = os.path.join(_SOUNDS_DIR, candidate + ext)
            if os.path.exists(path):
                try:
                    snd = pygame.mixer.Sound(path)
                    snd.set_volume(_effective_volume(name, candidate))
                    _sfx[name] = snd
                    if candidate != name:
                        _sfx[candidate] = snd
                    return snd
                except pygame.error as e:
                    print(f"[sounds] could not load {path}: {e}")
                    _sfx[name] = None
                    return None
    # file not found
    if name not in _warned:
        _warned.add(name)
        print(f"[sounds] no file for '{name}' in {_SOUNDS_DIR}  – add {name}.wav/.ogg/.mp3 to enable it")
    _sfx[name] = None
    return None


def set_volumes(bgm=None, sfx=None):
    """Change volumes at runtime. Pass 0.0–1.0."""
    global BGM_VOLUME, SFX_VOLUME
    if bgm is not None:
        BGM_VOLUME = max(0.0, min(1.0, bgm))
        pygame.mixer.music.set_volume(BGM_VOLUME)
    if sfx is not None:
        SFX_VOLUME = max(0.0, min(1.0, sfx))
        for snd in _sfx.values():
            if snd is not None:
                snd.set_volume(SFX_VOLUME)


def stop_all_sfx():
    """Stop all currently loaded sound effects except the victory cue."""
    for name, snd in _sfx.items():
        if name == "victory":
            continue
        if snd is not None:
            try:
                snd.stop()
            except Exception:
                pass


def set_sfx_volume_for(name, volume):
    """Set volume for a specific sound name (and remember override)."""
    vol = max(0.0, min(1.0, volume))
    _SOUND_VOLUME_OVERRIDES[name] = vol
    snd = _load(name)
    if snd is not None:
        try:
            snd.set_volume(vol)
        except Exception:
            pass


def clear_sfx_override(name):
    """Remove a previously set override for `name` and restore its effective volume."""
    if name in _SOUND_VOLUME_OVERRIDES:
        del _SOUND_VOLUME_OVERRIDES[name]
    snd = _sfx.get(name)
    if snd is not None:
        try:
            # recompute effective volume (fall back to global SFX_VOLUME)
            snd.set_volume(_effective_volume(name, name))
        except Exception:
            pass


def set_menu_shield_max(enable=True):
    """Internal helper: when on the main menu, make shield sound max volume.
    Call with enable=False to restore previous override (if any).
    """
    key = "runner_shield"
    if enable:
        # save previous override if any
        _prev_overrides[key] = _SOUND_VOLUME_OVERRIDES.get(key, None)
        set_sfx_volume_for(key, 1.0)
    else:
        prev = _prev_overrides.pop(key, None)
        if prev is None:
            clear_sfx_override(key)
        else:
            set_sfx_volume_for(key, prev)


def _bgm_volume_for(filename):
    """Return the music volume for a specific background track."""
    if filename == "bgm_menu":
        return MENU_BGM_VOLUME
    if filename == "bgm_game":
        return GAME_BGM_VOLUME
    return BGM_VOLUME


# ------------------------------------------------------------------ public API

def play(name, loops=0):
    """Play a sound effect by name. Silent if file not found."""
    snd = _load(name)
    if snd:
        snd.play(loops=loops)


def stop(name):
    """Stop a looping sound effect."""
    snd = _sfx.get(name)
    if snd:
        snd.stop()


def play_bgm(filename):
    """Start looping background music. `filename` is e.g. 'bgm_menu'."""
    global _bgm_file
    if not _ready:
        return
    if filename == _bgm_file:
        return   # already playing
    for ext in (".mp3", ".ogg", ".wav"):
        path = os.path.join(_SOUNDS_DIR, filename + ext)
        if os.path.exists(path):
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(_bgm_volume_for(filename))
                pygame.mixer.music.play(-1)   # loop forever
                _bgm_file = filename
                return
            except pygame.error as e:
                print(f"[sounds] could not load BGM {path}: {e}")
                return
    if filename not in _warned:
        _warned.add(filename)
        print(f"[sounds] no BGM file for '{filename}' in {_SOUNDS_DIR}")


def stop_bgm():
    global _bgm_file
    if _ready:
        pygame.mixer.music.stop()
    _bgm_file = None


# ------------------------------------------------------------------ spell sound map
# Maps spell index (0-9) to the sound name that fires when that spell is cast.
SPELL_CAST_SOUNDS = [
    "spell_water",       # 0  Dirty Water
    "spell_stun",        # 1  Stun
    "spell_bats",        # 2  Moving Bats
    "spell_lightning",   # 3  Lightning
    "spell_moss",        # 4  Moss
    "spell_inversion",   # 5  Inversion
    "spell_earthquake",  # 6  Earthquake
    "spell_flare_warn",  # 7  Solar Flare (warning phase)
    "spell_typhoon",     # 8  Typhoon
    "spell_flood",       # 9  Flood
]


def play_spell(index):
    """Play the cast sound for spell at `index` (0-based).
    Falls back to 'cast_generic' if no specific sound file exists."""
    name = SPELL_CAST_SOUNDS[index] if index < len(SPELL_CAST_SOUNDS) else "cast_generic"
    snd  = _load(name)
    if snd:
        snd.play()
    else:
        play("cast_generic")
