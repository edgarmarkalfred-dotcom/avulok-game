"""Every tweakable number and colour lives here."""
import sys
import pygame
from pygame.math import Vector2 as vector

# ---------- screen / grid ----------
TILE_SIZE = 16
WINDOW_WIDTH, WINDOW_HEIGHT = 480, 270
HUD_H  = 28
VIEW_H = WINDOW_HEIGHT - HUD_H
FPS    = 60
ANIMATION_SPEED = 6

# ---------- draw order ----------
Z_LAYERS = {
    'bg': 0, 'clouds': 1, 'bg tiles': 2, 'path': 3, 'bg details': 4,
    'main': 5, 'water': 6, 'fg': 7,
}
LAYER_Z = {
    'terrain': Z_LAYERS['main'], 'platforms': Z_LAYERS['main'], 'bounce': Z_LAYERS['main'],
    'goal': Z_LAYERS['main'], 'spike': Z_LAYERS['bg details'],
    'spike inverted': Z_LAYERS['bg details'],
    'wallpaper': Z_LAYERS['bg tiles'], 'wallpaper1': Z_LAYERS['bg tiles'],
    'wallpaper2': Z_LAYERS['bg tiles'], 'wallpaper3': Z_LAYERS['bg tiles'],
    'background': Z_LAYERS['path'],
    'props': Z_LAYERS['bg'],
    'water': Z_LAYERS['water'], 'foreground': Z_LAYERS['fg'], 'fg': Z_LAYERS['fg'],
}

# ---------- maps ----------
LEVELS = [("The Cramped Castle", "LockinMap.tmx")]

# ---------- object sizes ----------
RUNNER_SIZE = (12, 14)
PICKUP_SIZE = (10, 10)
ORB_SIZE    = 16

# ---------- old-style moving platforms ----------
PATH_PLATFORMS = {
    "small obj": (32, 8), "med obj": (48, 8),
    "big obj": (48, 8),   "elevator": (48, 8),
}
PATH_SOLID = True
PATH_SCALE = 1.0

# ---------- runner physics ----------
GRAVITY      = 800
MAX_FALL     = 360
JUMP_V       = 320
BOUNCE_V     = 460
RUN_SPEED    = 96
BOOST_SPEED  = 136
BOOST_TIME   = 5.0
MAX_HEARTS   = 3
INVULN_TIME  = 1.5
KNOCKBACK    = (168, -168)     # used by damage AND moss knockback
STUN_TIME    = 0.3
HURT_TIME    = 0.45        # how long the 'hurt' pose lasts after losing a heart
SHIELD_TIME  = 0.8
SHIELD_COOLDOWN = 2.4
SHIELD_RADIUS   = 15
COYOTE       = 0.08
JUMP_BUFFER  = 0.12

# Super Jump (Q key) – jump strength ×1.9 for 4 seconds, 15-second cooldown
SUPER_JUMP_COOLDOWN  = 15.0
SUPER_JUMP_DURATION  = 4
SUPER_JUMP_MULTIPLIER = 1.5

# ---------- match countdown ----------
MATCH_COUNTDOWN = 3.0

# ---------- cast system ----------
CAST_COOLDOWN    = 0.6   # short global delay between any two casts

# Major spell rule: spells 6-10 (indices 5-9)
# You can only have MAX_MAJOR_ON_CD majors cooling down at once.
# Minor spells (1-5, indices 0-4) have no simultaneous cap – cast freely.
MAX_MAJOR_ON_CD   = 2
MAJOR_SPELL_INDEX = 5   # spells[5..9] are majors

MAX_SPELLS = 10

# ---------- per-spell individual cooldowns ----------
# Minor (1-5): 3 s each — unlimited casts, only gated by cooldown
# Major (6-10): individual cooldowns as specified
# When 2 majors are on cooldown, ALL spells (minor AND major) are blocked.
SPELL_COOLDOWNS = [
    3.0,    # 1  Dirty Water   – minor
    3.5,    # 2  Stun          – minor
    4.0,    # 3  Moving Bats   – minor
    3.0,    # 4  Lightning     – minor
    3.5,    # 5  Moss          – minor
    10.0,   # 6  Inversion     – major
    15.0,   # 7  Earthquake    – major
    10.0,   # 8  Solar Flare   – major (hits for 2 hearts)
    10.0,   # 9  Typhoon       – major
    20.0,   # 10 Flood         – major
]

# ------------------------------------------------------------------ spell constants

# Spell 1 – Dirty Water 
PROJECTILE_SPEED  = 215
PROJECTILE_SIZE   = 12

# Spell 2 – Stun  (1-second stun, small radius)
STUN_SPELL_DURATION = 1.0  # stun lasts 1.0 second
STUN_SPELL_RADIUS   = 16     # aim circle radius (screen pixels)

# Spell 3 – Moving Bats 
SPIKE_SPEED    = 145
SPIKE_SIZE     = 14
SPIKE_LIFETIME = 999999.0

# Spell 4 – Lightning
LIGHTNING_WARN_TIME = 0.48
LIGHTNING_WIDTH     = 21
LIGHTNING_HEIGHT    = 300

# Spell 5 – Moss  (no damage – knockback like a hit, but no heart lost)
MOSS_LIFETIME       = 4.0
MOSS_SIZE           = TILE_SIZE

# Spell 6 – Inversion  (2.3 seconds, purple circle – runner must touch it)
INVERSION_TIME   = 2.3
INVERSION_RADIUS = 20      # circle radius in screen pixels (44 px across)

# Spell 7 – Earthquake
EARTHQUAKE_DURATION  = 5.0
EARTHQUAKE_SHAKE_AMP = 3
ROCK_FALL_INTERVAL   = 0.30
ROCK_SIZE            = 9
ROCK_SPEED           = 185

# Spell 8 – Solar Flare  (0.7 s warn, hits for 2 hearts)
SOLAR_FLARE_WARN_TIME = 0.4
SOLAR_FLARE_HIT_TIME  = 0.3
SOLAR_FLARE_BEAM_W    = 60
SOLAR_FLARE_DURATION  = 5.0   # kept for HUD compat
SOLAR_FLARE_HEARTS    = 2     # hearts lost when hit by solar flare

# Spell 9 – Typhoon  (7 s, noticeable slow)
TYPHOON_DURATION    = 8.0
TYPHOON_SLOW_FACTOR = 0.75    # runner keeps 75 % speed while slowed
RAIN_DROP_COUNT     = 80

# Spell 10 – Flood  (spawns 5 blocks below runner, lasts 10 seconds then drains)
FLOOD_OFFSET_BLOCKS      = 5
FLOOD_RISE_SPEED         = 60
FLOOD_RISE_SPEED_TYPHOON = 70
FLOOD_DURATION           = 10.0   # seconds before flood drains away

# ---------- castle traps ----------
DART_INTERVAL = 4.0
DART_CHARGE   = 0.7
DART_SPEED    = 90
DART_SIZE     = (22, 12)

# ---------- compatibility stubs (no longer used but kept to avoid NameError) ----------
BLIND_TIME   = 0.0
BLIND_RADIUS = 0

# ---------- colours ----------
COLORS = {
    "runner":          (80,  160, 255),
    "projectile":      (60,  120, 200),
    "dart_shot":       (255, 150, 40),
    "dart":            (150, 90,  50),
    "moving_spike":    (80,  60,  40),
    "heart":           (255, 90,  130),
    "heart_empty":     (70,  60,  70),
    "speed":           (255, 235, 60),
    "orb":             (160, 90,  230),
    "goal":            (255, 215, 0),
    "moving_platform": (110, 150, 190),
    "moving_block":    (170, 120, 90),
    "bg":              (24,  20,  34),
    "shield":          (120, 230, 255),
    "dirty_water":     (60,  100, 180),
    "moving_bat":      (80,  60,  40),
    "lightning":       (255, 255, 100),
    "lightning_warn":  (255, 230, 60),
    "moss":            (60,  160, 60),
    "rock":            (130, 110, 90),
    "solar_flare":     (255, 220, 60),
    "flood":           (30,  80,  180),
    "rain_drop":       (80,  140, 220),
    "stun":            (255, 200, 80),
    "inversion":       (170, 80,  230),
}


def to_screen(rect, offset):
    return pygame.Rect(
        round(rect.x + offset[0]), round(rect.y + offset[1]),
        round(rect.w), round(rect.h)
    )