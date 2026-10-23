"""The Runner: A/D to move, SPACE to jump, Q to super-jump, S/SHIFT to shield.

Animation: every frame the runner picks a pose (see _pose) and plays the matching
sprite from assets.SPRITES: runner_idle, runner_run, runner_jump, runner_fall,
runner_shield, runner_stun, runner_hurt, runner_win and runner_lose.

Status effects:
  inverted    – A/D directions swapped (Inversion spell)
  slowed      – movement speed × TYPHOON_SLOW_FACTOR (Typhoon spell)
  stun        – cannot steer; velocity bleeds off (Stun spell and moss)
  hurt_t      – 'hurt' pose timer, set when a heart is lost
  jump_locked – jumping disabled during the match countdown
"""
from settings import *
import assets
import sounds


class Runner(pygame.sprite.Sprite):
    def __init__(self, pos, size, groups, level):
        super().__init__(groups)
        self.z     = Z_LAYERS['main'] + 0.5
        self.level = level
        self.rect     = pygame.FRect(pos[0], pos[1], size[0], size[1])
        self.old_rect = self.rect.copy()
        self.vx = self.vy = 0.0
        self.on_ground = self.bounced = False
        self.platform  = None
        self.facing    = 1
        self.hearts    = MAX_HEARTS

        # standard timers
        self.coyote      = 0.0
        self.jump_buffer = 0.0
        self.invuln      = 0.0
        self.stun        = 0.0
        self.blind       = 0.0   # kept for compatibility
        self.boost       = 0.0
        self.shield      = 0.0
        self.shield_cd   = 0.0
        self.hurt_t      = 0.0

        # spell-effect timers
        self.inverted = 0.0
        self.slowed   = 0.0

        # super jump (Q key)
        self.sj_active = 0.0   # seconds remaining in the boost window
        self.sj_cd     = 0.0   # cooldown before Q can be used again

        # countdown lock
        self.jump_locked = False

        # animation state: current pose name and how long it has been playing
        self.anim_state = "runner_idle"
        self.anim_t     = 0.0

    # ------------------------------------------------------------------ helpers
    @property
    def cx(self): return self.rect.centerx
    @property
    def cy(self): return self.rect.centery

    # ------------------------------------------------------------------ input
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        key = event.key

        if key == pygame.K_SPACE:
            if not self.jump_locked:
                self.jump_buffer = JUMP_BUFFER

        elif key == pygame.K_q:
            if not self.jump_locked and self.sj_cd <= 0 and self.stun <= 0:
                self.sj_active = SUPER_JUMP_DURATION
                self.sj_cd     = SUPER_JUMP_COOLDOWN
                sounds.play("runner_superjump")

        elif key in (pygame.K_s, pygame.K_LSHIFT) and self.shield_cd <= 0:
            self.shield, self.shield_cd = SHIELD_TIME, SHIELD_COOLDOWN
            sounds.play("runner_shield")

    # ------------------------------------------------------------------ update
    def update(self, dt, keys):
        self.old_rect = self.rect.copy()

        for name in ("invuln", "stun", "blind", "boost", "shield", "shield_cd",
                     "jump_buffer", "inverted", "slowed", "sj_cd", "sj_active", "hurt_t"):
            setattr(self, name, max(0.0, getattr(self, name) - dt))

        if self.stun > 0:
            self.vx *= max(0.0, 1 - 5 * dt)
        else:
            right_key = pygame.K_a if self.inverted > 0 else pygame.K_d
            left_key  = pygame.K_d if self.inverted > 0 else pygame.K_a
            direction = int(keys[right_key]) - int(keys[left_key])
            base_speed = BOOST_SPEED if self.boost > 0 else RUN_SPEED
            if self.slowed > 0:
                base_speed *= TYPHOON_SLOW_FACTOR
            self.vx = direction * base_speed
            if direction:
                self.facing = direction

        self.coyote = COYOTE if self.on_ground else max(0.0, self.coyote - dt)

        # Normal jump — multiplied by SUPER_JUMP_MULTIPLIER if super jump window is active
        if self.jump_buffer > 0 and self.coyote > 0 and self.stun <= 0 and not self.jump_locked:
            jump_v = JUMP_V * (SUPER_JUMP_MULTIPLIER if self.sj_active > 0 else 1.0)
            self.vy          = -jump_v
            self.jump_buffer = self.coyote = 0.0
            self.platform    = None
            sounds.play("runner_jump")

        if self.platform:
            self.rect.x += self.platform.rect.x - self.platform.old_rect.x
            self.rect.y += self.platform.rect.y - self.platform.old_rect.y

        self.move(dt)

        if self.bounced:
            self.coyote = 0.0

        self.tick_anim(dt)

    # ------------------------------------------------------------------ animation
    def _pose(self):
        """The sprite name that matches the runner's situation right now."""
        winner = self.level.winner
        if winner == "runner":
            return "runner_win"
        if winner == "caster":
            return "runner_lose"
        if self.hurt_t > 0:
            return "runner_hurt"
        if self.stun > 0:
            return "runner_stun"
        if self.shield > 0:
            return "runner_shield"
        if not self.on_ground:
            return "runner_jump" if self.vy < 0 else "runner_fall"
        if abs(self.vx) > 1:
            return "runner_run"
        return "runner_idle"

    def tick_anim(self, dt):
        """Advance the animation clock. Restarts the clip whenever the pose changes."""
        pose = self._pose()
        if pose != self.anim_state:
            # Fire one-shot sounds on pose transitions
            if pose == "runner_win":
                sounds.play("runner_win")
            elif pose == "runner_lose":
                sounds.play("runner_lose")
            self.anim_state, self.anim_t = pose, 0.0
        else:
            self.anim_t += dt

    # ------------------------------------------------------------------ movement + collisions
    def move(self, dt):
        self._was_on_ground = self.on_ground   # remember before resetting
        self.on_ground = self.bounced = False
        self.platform  = None

        self.rect.x += self.vx * dt
        self.collide_x()

        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        self.rect.y += self.vy * dt
        self.collide_y()
        self.collide_one_way()
        self.clamp_to_map()

    def collide_x(self):
        for s in self.level.solids.query(self.rect):
            if not self.rect.colliderect(s.rect):
                continue
            if self.rect.left <= s.rect.right and int(self.old_rect.left) >= int(s.old_rect.right):
                self.rect.left = s.rect.right
                self.vx = 0
            elif self.rect.right >= s.rect.left and int(self.old_rect.right) <= int(s.old_rect.left):
                self.rect.right = s.rect.left
                self.vx = 0

    def collide_y(self):
        for s in self.level.solids.query(self.rect):
            if not self.rect.colliderect(s.rect):
                continue
            if self.rect.top <= s.rect.bottom and int(self.old_rect.top) >= int(s.old_rect.bottom):
                self.rect.top = s.rect.bottom
                if getattr(s, 'moving', False):
                    self.rect.top -= 0.1
                self.vy = 0
            elif self.rect.bottom >= s.rect.top and int(self.old_rect.bottom) <= int(s.old_rect.top):
                self.rect.bottom = s.rect.top
                self.vy = 0
                if not self._was_on_ground:
                    sounds.play("runner_land")
                self.on_ground = True
                if getattr(s, 'moving', False):
                    self.platform = s

    def collide_one_way(self):
        if self.vy < 0:
            return
        landing = None
        for s in self.level.semis.query(self.rect):
            if self.rect.colliderect(s.rect) and self.old_rect.bottom <= s.old_rect.top + 0.01:
                if landing is None or getattr(s, 'bounce', False):
                    landing = s
        if landing:
            self.rect.bottom = landing.rect.top
            if getattr(landing, 'bounce', False):
                self.vy, self.bounced = -BOUNCE_V, True
                sounds.play("runner_bounce")
            else:
                self.vy, self.on_ground = 0, True
                if not self._was_on_ground:
                    sounds.play("runner_land")
                if getattr(landing, 'moving', False):
                    self.platform = landing

    def clamp_to_map(self):
        lv = self.level
        if self.rect.left < 0:
            self.rect.left, self.vx = 0, 0
        if self.rect.right > lv.width:
            self.rect.right, self.vx = lv.width, 0
        if self.rect.top < 0:
            self.rect.top, self.vy = 0, max(self.vy, 0)
        if self.rect.bottom > lv.height:
            self.rect.bottom, self.vy, self.on_ground = lv.height, 0, True

    # ------------------------------------------------------------------ damage / knockback
    def hit(self, from_x):
        """Takes one heart. Returns True if damage was dealt."""
        if self.invuln > 0 or self.hearts <= 0:
            return False
        self.hearts -= 1
        self.invuln, self.stun = INVULN_TIME, STUN_TIME
        self.hurt_t = HURT_TIME
        self._knock_back(from_x)
        sounds.play("runner_hurt")
        return True

    def apply_moss_knockback(self, from_x=None):
        """Moss: same knockback as a hit but NO heart lost and NO invuln."""
        self._knock_back(from_x)
        self.stun = max(self.stun, STUN_TIME)
        sounds.play("moss")

    def apply_slip(self, from_x=None):
        """Compatibility shim – moss now just knocks back."""
        self.apply_moss_knockback(from_x)

    def _knock_back(self, from_x):
        direction = (1 if self.cx >= from_x else -1) if from_x is not None else -self.facing
        self.vx, self.vy = direction * KNOCKBACK[0], KNOCKBACK[1]
        self.on_ground = False
        self.platform  = None

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, offset):
        if self.invuln > 0 and int(self.invuln * 10) % 2:
            return
        r = to_screen(self.rect, offset)

        # Body: the sprite for the current pose, standing on the hitbox's bottom edge.
        if not assets.draw(surface, self.anim_state, r, t=self.anim_t,
                           flip=self.facing < 0, feet=True):
            assets.draw_block(surface, "runner", r)
            eye_x = r.centerx + (2 if self.facing > 0 else -5)
            pygame.draw.rect(surface, (255, 255, 255), (eye_x, r.y + 3, 3, 3))

        if self.shield > 0:
            bubble = pygame.Rect(int(r.centerx - SHIELD_RADIUS), int(r.centery - SHIELD_RADIUS),
                                 int(SHIELD_RADIUS * 2), int(SHIELD_RADIUS * 2))
            if not assets.draw(surface, "shield_bubble", bubble, t=self.anim_t):
                pygame.draw.circle(surface, COLORS["shield"], r.center, SHIELD_RADIUS, 1)

        if self.stun > 0:
            popup = pygame.Rect(int(r.centerx - 9), int(r.top - 15), 18, 13)
            if not assets.draw(surface, "fx_stun_popup", popup, t=self.stun):
                pygame.draw.circle(surface, COLORS["stun"], (r.centerx, r.top - 12), 7, 2)

        if self.inverted > 0:
            tag = pygame.Rect(int(r.centerx - 8), int(r.top - 11), 15, 8)
            if not assets.draw(surface, "fx_inverted", tag):
                pygame.draw.line(surface, (200, 80, 255),
                                 (r.centerx - 5, r.top - 4), (r.centerx + 5, r.top - 4), 1)

        if self.slowed > 0:
            tag = pygame.Rect(int(r.centerx - 6), int(r.top - 15), 13, 13)
            if not assets.draw(surface, "fx_slowed", tag):
                pygame.draw.circle(surface, COLORS["rain_drop"], (r.centerx, r.top - 4), 2)

        # Super jump indicator above head
        if self.sj_active > 0:
            # Yellow shrinking bar = boost window active
            bar_w = max(1, int(10 * self.sj_active / SUPER_JUMP_DURATION))
            bar = pygame.Rect(int(r.centerx - 5), int(r.top - 5), bar_w, 2)
            if not assets.draw(surface, "fx_superjump_bar", bar):
                pygame.draw.rect(surface, (255, 230, 60), bar)