"""The Caster: mouse only. Picks a spell, aims with the crosshair.

Cast rules
----------
Minor spells (slots 1-5, indices 0-4):
  • Unlimited casts – no per-spell cast counter.
  • Only gated by the spell's own 3 s cooldown and the global inter-cast delay.

Major spells (slots 6-10, indices 5-9):
  • Unlimited casts – no per-spell cast counter.
  • Each has its own individual cooldown (10–20 s, see SPELL_COOLDOWNS).
  • When 2 or more majors are already on cooldown, ALL spells (minor AND major)
    are blocked until at least one major cooldown expires.

Both types are also blocked while level.countdown > 0.
"""
from settings import *
from spells import ALL_SPELLS
import sounds


class Caster:
    def __init__(self):
        self.spells    = list(ALL_SPELLS)
        self.global_cd = 0.0                        # inter-cast delay
        self._spell_cd = [0.0] * len(self.spells)  # per-spell individual cooldown
        self.selected  = 0

    # ------------------------------------------------------------------ helpers
    def _is_major(self, index):
        return index >= MAJOR_SPELL_INDEX

    # ------------------------------------------------------------------ props
    @property
    def spell(self):
        return self.spells[self.selected]

    @property
    def spell_cd(self):
        return self._spell_cd[self.selected]

    @property
    def spell_cd_max(self):
        return SPELL_COOLDOWNS[self.selected]

    @property
    def majors_on_cooldown(self):
        """Count of major spells (indices 5-9) currently cooling down."""
        return sum(1 for i, cd in enumerate(self._spell_cd)
                   if cd > 0 and self._is_major(i))

    # ------------------------------------------------------------------ selection
    def select(self, index):
        self.selected = index % len(self.spells)

    # ------------------------------------------------------------------ update
    def update(self, dt):
        self.global_cd = max(0.0, self.global_cd - dt)
        for i in range(len(self._spell_cd)):
            self._spell_cd[i] = max(0.0, self._spell_cd[i] - dt)

    # ------------------------------------------------------------------ casting
    def can_cast(self, level=None):
        # Blocked during match countdown
        if level is not None and level.countdown > 0:
            return False
        # Short global inter-cast delay
        if self.global_cd > 0:
            return False
        # This spell's own cooldown must be finished
        if self._spell_cd[self.selected] > 0:
            return False
        # Major cap: when 2 majors are on cooldown, block MAJORS ONLY
        # Minors are never blocked by this rule
        if self._is_major(self.selected) and self.majors_on_cooldown >= MAX_MAJOR_ON_CD:
            return False
        return True

    def cast(self, level, screen_pos):
        """Returns True if a spell was successfully cast."""
        pos = level.to_world(screen_pos)
        if not self.can_cast(level):
            sounds.play("denied")
            return False
        if not self.spell.is_valid(level, pos):
            sounds.play("denied")
            return False
        self.spell.cast(level, pos)
        self.global_cd                = CAST_COOLDOWN
        self._spell_cd[self.selected] = SPELL_COOLDOWNS[self.selected]
        sounds.play_spell(self.selected)
        return True

    # kept for HUD compat – always returns a large number since casts are unlimited
    @property
    def casts_left(self):
        return 99
