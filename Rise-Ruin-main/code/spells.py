"""Everything the Caster can create, plus the Spell classes themselves.

Minor spells (1-5, indices 0-4): cast freely, each has its own 3 s cooldown.
Major spells (6-10, indices 5-9): max 2 active cooldowns simultaneously, 5 s each.

Every spell has an `icon` sprite (spell bar) and most have an `aim_*` preview sprite.
Object sprites: projectile, bat, lightning_warn, lightning_bolt, moss, rock, dart_shot.
See assets.py for the full list.
"""
import math
import random
from settings import *
from sprites import Sprite
import assets
import sounds


# ================================================================== world objects

class Projectile(Sprite):
    def __init__(self, pos, size, velocity, name, groups, through_walls=False):
        super().__init__(pos, assets.get(name, size), groups, Z_LAYERS['main'] + 0.4)
        self.key           = name                 # sprite name ('projectile' or 'dart_shot')
        self.velocity      = vector(velocity)
        self.age           = 0.0
        self.t             = 0.0
        self.through_walls = through_walls

    @property
    def cx(self): return self.rect.centerx
    @property
    def cy(self): return self.rect.centery

    def update(self, dt, level):
        self.t += dt
        self.rect.x += self.velocity.x * dt
        self.rect.y += self.velocity.y * dt
        self.age    += dt
        if (self.age > 6
                or not level.in_bounds(self.rect)
                or (not self.through_walls and level.hits_solid(self.rect))):
            self.kill()

    def draw(self, surface, offset):
        assets.draw_block(surface, self.key, to_screen(self.rect, offset), t=self.t)


class MovingBat(Sprite):
    """Sweeps left↔right at SPIKE_SPEED. Infinite lifespan. Sprite: 'bat'."""
    def __init__(self, y, side, bounds, groups):
        lo, hi = bounds
        if side == "left":
            x = lo
            direction = 1
        else:
            x = hi - SPIKE_SIZE
            direction = -1
        super().__init__((x, y), assets.get("bat", (SPIKE_SIZE, SPIKE_SIZE)),
                         groups, Z_LAYERS['main'] + 0.3)
        self.bounds = bounds
        self.dir    = direction
        self.life   = SPIKE_LIFETIME
        self.t      = 0.0

    def update(self, dt):
        self.t += dt
        self.rect.x += self.dir * SPIKE_SPEED * dt
        lo, hi = self.bounds
        if self.rect.left <= lo:
            self.rect.left, self.dir = lo, 1
        elif self.rect.right >= hi:
            self.rect.right, self.dir = hi, -1

    def draw(self, surface, offset):
        rect = to_screen(self.rect, offset)
        # The bat sprite sheet is left-facing by default, so rightward motion needs a horizontal flip.
        assets.draw_block(surface, "bat", rect, t=self.t, flip=(self.dir > 0))


class LightningWarning(pygame.sprite.Sprite):
    """Flashing column that marks where a bolt will strike. Sprite: 'lightning_warn'."""
    def __init__(self, world_x, groups):
        super().__init__(groups)
        self.world_x = world_x
        self.t       = LIGHTNING_WARN_TIME
        self.z       = Z_LAYERS['fg']

    def update(self, dt):
        self.t -= dt
        if self.t <= 0:
            self.kill()

    def draw(self, surface, offset):
        x     = round(self.world_x + offset[0])
        alpha = max(1, int(210 * abs(math.sin(self.t * 20))))
        w     = LIGHTNING_WIDTH + 4
        column = pygame.Rect(x - w // 2, 0, w, VIEW_H)
        if assets.draw(surface, "lightning_warn", column, alpha=alpha):
            return
        surf = pygame.Surface((max(1, w), VIEW_H), pygame.SRCALPHA)
        surf.fill((255, 255, 60, alpha))
        surface.blit(surf, (x - w // 2, 0))


class LightningBolt(pygame.sprite.Sprite):
    """The strike itself, shown for about a second so all 7 frames cycle. Sprite: 'lightning_bolt'."""
    FLASH_TIME = 1.0

    def __init__(self, world_x, level_height, groups):
        super().__init__(groups)
        self.world_x = world_x
        self.z       = Z_LAYERS['fg']
        self.t       = 0.0

    def update(self, dt):
        self.t += dt
        if self.t >= self.FLASH_TIME:
            self.kill()

    def draw(self, surface, offset):
        x = round(self.world_x + offset[0])
        bolt = pygame.Rect(x - LIGHTNING_WIDTH, 0, LIGHTNING_WIDTH * 2, VIEW_H)
        if assets.draw(surface, "lightning_bolt", bolt, t=self.t):
            return
        pygame.draw.rect(surface, (255, 255, 100), bolt)
        pygame.draw.rect(surface, (255, 255, 255), (x - 2, 0, 4, VIEW_H))


class MossTile(pygame.sprite.Sprite):
    """No damage – the runner is knocked back 1 block sideways. Disappears on step. Sprite: 'moss'."""
    def __init__(self, pos, groups):
        super().__init__(groups)
        self.z         = Z_LAYERS['main'] + 0.2
        surf           = pygame.Surface((MOSS_SIZE, MOSS_SIZE // 3), pygame.SRCALPHA)
        surf.fill((60, 160, 60, 210))
        for bx in range(2, MOSS_SIZE - 2, 4):
            pygame.draw.circle(surf, (40, 130, 40), (bx, 1), 2)
        self.image     = surf                  # drawn this way when there is no moss sprite
        self.rect      = surf.get_frect(topleft=pos)
        self.old_rect  = self.rect.copy()
        self.life      = MOSS_LIFETIME
        self.triggered = False                 # set True the moment runner touches it
        self.t         = 0.0

    def update(self, dt):
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.kill()

    def draw(self, surface, offset):
        rect = to_screen(self.rect, offset)
        if not assets.draw(surface, "moss", rect, t=self.t):
            surface.blit(self.image, rect)


class FallingRock(Sprite):
    """Rock from the earthquake. Sprite: 'rock'."""
    def __init__(self, x, top_y, groups):
        super().__init__((x, top_y), assets.get("rock", (ROCK_SIZE, ROCK_SIZE)),
                         groups, Z_LAYERS['main'] + 0.35)
        self.vy       = ROCK_SPEED
        self.hit_done = False
        self.t        = 0.0

    @property
    def cx(self): return self.rect.centerx

    def update(self, dt, level):
        self.t += dt
        # Rocks only exist while the earthquake is running; they vanish when it ends.
        if level.earthquake_t <= 0:
            self.kill()
            return
        self.rect.y += self.vy * dt
        for s in level.solids.query(self.rect):
            if self.rect.colliderect(s.rect) and self.rect.bottom >= s.rect.top:
                self.kill()
                return
        if not level.in_bounds(self.rect):
            self.kill()

    def draw(self, surface, offset):
        assets.draw_block(surface, "rock", to_screen(self.rect, offset), t=self.t)


# ================================================================== spell base
class Spell:
    name           = "Spell"
    casts          = 2
    uses_crosshair = True     # False means the spell draws its own aim visual
    icon           = None     # sprite name shown on the spell bar

    def is_valid(self, level, pos): return True
    def cast(self, level, pos):     raise NotImplementedError
    def draw_preview(self, surface, level, mouse): pass


# ================================================================== spells

# ------------------------------------------------------------------ 1. Dirty Water
class DirtyWaterSpell(Spell):
    name  = "Dirty Water"
    casts = 3
    icon  = "icon_water"

    def cast(self, level, pos):
        ox, oy = level.orb_pos
        dx, dy = pos[0] - ox, pos[1] - oy
        dist   = math.hypot(dx, dy) or 1
        s      = PROJECTILE_SIZE
        Projectile(
            (ox - s / 2, oy - s / 2), (s, s),
            (dx / dist * PROJECTILE_SPEED, dy / dist * PROJECTILE_SPEED),
            "projectile", (level.all_sprites, level.projectile_sprites),
            through_walls=True,
        )

    def draw_preview(self, surface, level, mouse):
        if not assets.draw_line(surface, "aim_water", level.ORB_SCREEN, mouse, 2):
            pygame.draw.line(surface, COLORS["dirty_water"], level.ORB_SCREEN, mouse, 1)


# ------------------------------------------------------------------ 2. Stun
class StunSpell(Spell):
    """Small circle aim. If runner is inside, stun them for 1 second. Shield blocks it."""
    name  = "Stun"
    casts = 2
    icon  = "icon_stun"

    def cast(self, level, pos):
        r = level.runner
        if r.shield > 0:
            return
        if math.hypot(r.cx - pos[0], r.cy - pos[1]) <= STUN_SPELL_RADIUS:
            r.stun = max(r.stun, STUN_SPELL_DURATION)

    def draw_preview(self, surface, level, mouse):
        R    = STUN_SPELL_RADIUS
        ring = pygame.Rect(int(mouse[0] - R), int(mouse[1] - R), R * 2, R * 2)
        if not assets.draw(surface, "aim_stun", ring):
            pygame.draw.circle(surface, COLORS["stun"], mouse, R, 2)
            pygame.draw.circle(surface, COLORS["stun"], mouse, 3)


# ------------------------------------------------------------------ 3. Moving Bats
class MovingBatSpell(Spell):
    name  = "Moving Bats"
    casts = 2
    icon  = "icon_bats"

    @staticmethod
    def _side(level, pos):
        for side, zone in level.spike_zones:
            if zone.collidepoint(pos):
                return side
        return None

    def is_valid(self, level, pos):
        return level.spike_bounds is not None and self._side(level, pos) is not None

    def cast(self, level, pos):
        y = int(pos[1] // TILE_SIZE) * TILE_SIZE + (TILE_SIZE - SPIKE_SIZE) / 2
        MovingBat(y, self._side(level, pos), level.spike_bounds,
                  (level.all_sprites, level.spike_sprites))

    def draw_preview(self, surface, level, mouse):
        off = level.all_sprites.draw_offset
        for _, zone in level.spike_zones:
            zr = to_screen(zone, off)
            if not assets.draw(surface, "aim_zone", zr):
                pygame.draw.rect(surface, (255, 200, 60), zr, 1)
        world = level.to_world(mouse)
        side  = self._side(level, world)
        if side and level.spike_bounds is not None:
            row_y = int(world[1] // TILE_SIZE) * TILE_SIZE + off[1]
            hit_zone = next((z for s, z in level.spike_zones
                             if s == side and z.collidepoint(world)), None)
            if hit_zone:
                zr  = to_screen(hit_zone, off)
                row = pygame.Rect(zr.x, row_y, zr.w, TILE_SIZE)
                if not assets.draw(surface, "aim_bats", row):
                    pygame.draw.rect(surface, COLORS["moving_bat"], row, 1)


# ------------------------------------------------------------------ 4. Lightning
class LightningSpell(Spell):
    name  = "Lightning"
    casts = 2
    icon  = "icon_bolt"

    def cast(self, level, pos):
        level.pending_lightning.append({"x": pos[0], "t": LIGHTNING_WARN_TIME})
        LightningWarning(pos[0], (level.all_sprites, level.effect_sprites))

    def draw_preview(self, surface, level, mouse):
        x = mouse[0]
        w = LIGHTNING_WIDTH + 4
        column = pygame.Rect(int(x - w // 2), 0, w, VIEW_H)
        if not assets.draw(surface, "aim_lightning", column):
            surf = pygame.Surface((max(1, w), VIEW_H), pygame.SRCALPHA)
            surf.fill((255, 255, 60, 60))
            surface.blit(surf, (x - w // 2, 0))
            pygame.draw.line(surface, COLORS["lightning_warn"], (x, 0), (x, VIEW_H), 1)


# ------------------------------------------------------------------ 5. Moss  (knockback only, no damage)
class MossSpell(Spell):
    name  = "Moss"
    casts = 2
    icon  = "icon_moss"

    @staticmethod
    def _find_platform_top(level, pos):
        wx, wy = pos
        for dy in range(0, TILE_SIZE * 2, TILE_SIZE // 2):
            probe = pygame.FRect(wx - TILE_SIZE // 2, wy + dy, TILE_SIZE, 2)
            for s in level.semis.query(probe):
                if probe.colliderect(s.rect):
                    return (int(s.rect.x), int(s.rect.y))
            for s in level.solids.query(probe):
                if probe.colliderect(s.rect):
                    return (int(s.rect.x), int(s.rect.y))
        return None

    def is_valid(self, level, pos):
        return self._find_platform_top(level, pos) is not None

    def cast(self, level, pos):
        result = self._find_platform_top(level, pos)
        if result is None:
            return
        col    = int(pos[0] // TILE_SIZE)
        tx, ty = result
        MossTile((col * TILE_SIZE, ty - MOSS_SIZE // 3),
                 (level.all_sprites, level.moss_sprites))
        # Do not play a placement sound here; moss sound only plays on collision.

    def draw_preview(self, surface, level, mouse):
        off    = level.all_sprites.draw_offset
        world  = level.to_world(mouse)
        result = self._find_platform_top(level, world)
        if result:
            _, ty = result
            col   = int(world[0] // TILE_SIZE)
            mark  = pygame.Rect(col * TILE_SIZE + off[0], ty + off[1] - 4, TILE_SIZE, 4)
            if not assets.draw(surface, "aim_moss", mark):
                pygame.draw.rect(surface, COLORS["moss"], mark, 1)


# ------------------------------------------------------------------ 6. Inversion  (purple circle, 2 seconds)
class InversionSpell(Spell):
    """Purple circle replaces the crosshair. The runner is only inverted
    if their body touches the circle at the moment of casting."""
    name           = "Inversion"
    casts          = 1
    uses_crosshair = False
    icon           = "icon_invert"

    @staticmethod
    def _runner_in_circle(runner, pos):
        # Nearest point on the runner's body to the circle centre
        nx = min(max(pos[0], runner.rect.left), runner.rect.right)
        ny = min(max(pos[1], runner.rect.top), runner.rect.bottom)
        return math.hypot(nx - pos[0], ny - pos[1]) <= INVERSION_RADIUS

    def cast(self, level, pos):
        r = level.runner
        if r.shield > 0:
            return
        if self._runner_in_circle(r, pos):
            r.inverted = max(r.inverted, INVERSION_TIME)

    def draw_preview(self, surface, level, mouse):
        if mouse[1] >= VIEW_H:
            return
        R      = INVERSION_RADIUS
        inside = self._runner_in_circle(level.runner, level.to_world(mouse))
        color  = COLORS["inversion"]
        ring   = pygame.Rect(int(mouse[0] - R), int(mouse[1] - R), R * 2, R * 2)
        if assets.draw(surface, "aim_inversion", ring, alpha=110 if inside else 55):
            return
        fill = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
        pygame.draw.circle(fill, (*color, 110 if inside else 55), (R, R), R)
        surface.blit(fill, (mouse[0] - R, mouse[1] - R))
        pygame.draw.circle(surface, color, mouse, R, 2)
        pygame.draw.circle(surface, color, mouse, 2)


# ------------------------------------------------------------------ 7. Earthquake
class EarthquakeSpell(Spell):
    name  = "Earthquake"
    casts = 1
    icon  = "icon_quake"

    def cast(self, level, pos):
        level.earthquake_t = EARTHQUAKE_DURATION
        level.rock_spawn_t = 0.0

    def draw_preview(self, surface, level, mouse):
        # Earthquake preview is intentionally silent: the brown dust strip sits on top of
        # active spell visuals and was not part of the intended effect layer.
        return


# ------------------------------------------------------------------ 8. Solar Flare
class SolarFlareSpell(Spell):
    name  = "Solar Flare"
    casts = 1
    icon  = "icon_flare"

    def cast(self, level, pos):
        level.solar_flare_active = True
        level.solar_flare_warn_t = SOLAR_FLARE_WARN_TIME
        level.solar_flare_hit_t  = 0.0
        level.solar_flare_beam_x = pos[0]

    def draw_preview(self, surface, level, mouse):
        bw    = SOLAR_FLARE_BEAM_W
        t     = assets.now()
        alpha = max(1, int(80 * abs(math.sin(t * 3))))
        zone  = pygame.Rect(int(mouse[0] - bw // 2), 0, bw, VIEW_H)
        if assets.draw(surface, "aim_flare", zone, alpha=alpha):
            return
        glow = pygame.Surface((max(1, bw), VIEW_H), pygame.SRCALPHA)
        glow.fill((255, 200, 40, alpha))
        surface.blit(glow, (mouse[0] - bw // 2, 0))
        pygame.draw.line(surface, (255, 200, 40),
                         (mouse[0] - bw // 2, 0), (mouse[0] - bw // 2, VIEW_H), 1)
        pygame.draw.line(surface, (255, 200, 40),
                         (mouse[0] + bw // 2, 0), (mouse[0] + bw // 2, VIEW_H), 1)


# ------------------------------------------------------------------ 9. Typhoon  (noticeable slow, 7 s)
class TyphoonSpell(Spell):
    name  = "Typhoon"
    casts = 1
    icon  = "icon_typhoon"

    def cast(self, level, pos):
        level.typhoon_t = TYPHOON_DURATION
        for _ in range(RAIN_DROP_COUNT):
            level.rain_drops.append({
                "x":  random.uniform(0, WINDOW_WIDTH),
                "y":  random.uniform(0, VIEW_H),
                "vy": random.uniform(180, 280),
                "vx": random.uniform(-20, -8),
            })

    def draw_preview(self, surface, level, mouse):
        cx, cy = mouse[0], 4
        cloud_offsets = [
            (-128, 0), (-96, -5), (-64, 2), (-32, -4), (0, 0),
            (32, -4), (64, 2), (96, -5), (128, 0), (160, 3)
        ]

        for dx, dy in cloud_offsets:
            cloud_rect = pygame.Rect(cx + dx - 26, cy + dy - 12, 52, 28)
            if not assets.draw(surface, "aim_typhoon_cloud", cloud_rect):
                for part in [
                    (cloud_rect.x + 3, cloud_rect.y + 7, cloud_rect.w - 10, cloud_rect.h - 10),
                    (cloud_rect.x + 14, cloud_rect.y - 2, cloud_rect.w - 22, cloud_rect.h - 8),
                    (cloud_rect.x + 22, cloud_rect.y + 4, cloud_rect.w - 24, cloud_rect.h - 12),
                ]:
                    pygame.draw.ellipse(surface, COLORS["rain_drop"], part, 2)

# ------------------------------------------------------------------ 10. Flood  (6 blocks below runner)
class FloodSpell(Spell):
    """Water always starts exactly FLOOD_OFFSET_BLOCKS tiles below wherever the runner is.
    No aim line or label is drawn in the preview."""
    name  = "Flood"
    casts = 1
    icon  = "icon_flood"

    def cast(self, level, pos):
        if level.flood_active:
            return
        level.flood_active  = True
        level.flood_t       = FLOOD_DURATION
        level.flood_alarm_t = 1.2
        sounds.play("alarm")
        runner_bottom       = level.runner.rect.bottom
        level.flood_y       = runner_bottom + FLOOD_OFFSET_BLOCKS * TILE_SIZE


# ================================================================== registry
ALL_SPELLS = [
    DirtyWaterSpell(),   # 1  minor  – 3 casts, fast
    StunSpell(),         # 2  minor  – 1 s stun
    MovingBatSpell(),    # 3  minor  – fast bats
    LightningSpell(),    # 4  minor
    MossSpell(),         # 5  minor  – knockback only
    InversionSpell(),    # 6  major  – purple circle, 2 s
    EarthquakeSpell(),   # 7  major
    SolarFlareSpell(),   # 8  major  – 0.7 s warn
    TyphoonSpell(),      # 9  major  – 7 s, 0.85× slow
    FloodSpell(),        # 10 major  – spawns 6 blocks below runner
]