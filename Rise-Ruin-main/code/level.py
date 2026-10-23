import math
import random
import pygame
import pytmx
from settings import *
from sprites import Sprite, Tile, TileLayer, MovingSprite, SpriteGrid
from groups import Allsprites
from runner import Runner
from traps import DartTrap
from pickups import Pickup
from spells import FallingRock, LightningBolt, LightningWarning, MossTile
from ui import draw_text
import assets
import sounds


class GoalSprite(Sprite):
    """The finish flag (sprite 'goal'). Animates on wall-clock time, so it keeps moving after the match."""
    def draw(self, surface, offset):
        assets.draw_block(surface, "goal", to_screen(self.rect, offset), t=assets.now())


class Level:
    ORB_SCREEN = (WINDOW_WIDTH // 2, 14)

    def __init__(self, tmx_map, name="", rng=None):
        if (tmx_map.tilewidth, tmx_map.tileheight) != (TILE_SIZE, TILE_SIZE):
            raise ValueError(
                f"Map tiles are {tmx_map.tilewidth}x{tmx_map.tileheight}, "
                f"expected {TILE_SIZE}x{TILE_SIZE}"
            )
        self.name = name
        self.rng  = rng or random.Random()
        self.width, self.height = tmx_map.width * TILE_SIZE, tmx_map.height * TILE_SIZE

        # sprite groups
        self.all_sprites        = Allsprites(self.width, self.height)
        self.projectile_sprites = pygame.sprite.Group()
        self.spike_sprites      = pygame.sprite.Group()
        self.effect_sprites     = pygame.sprite.Group()
        self.pickup_sprites     = pygame.sprite.Group()
        self.rock_sprites       = pygame.sprite.Group()
        self.moss_sprites       = pygame.sprite.Group()

        self.moving_sprites, self.traps = [], []
        self.solids, self.semis, self.hazards = SpriteGrid(), SpriteGrid(), SpriteGrid()
        self.goal_rects, self.spike_zones = [], []
        self.spike_bounds = None
        self.runner = None
        self.winner = None

        # match countdown
        self.countdown = MATCH_COUNTDOWN

        # spell state – Lightning
        self.pending_lightning = []

        # spell state – Earthquake
        self.earthquake_t  = 0.0
        self.rock_spawn_t  = 0.0
        self.shake_offset  = (0, 0)
        self.shake_t       = 0.0   # short shake timer for lightning / solar flare

        # spell state – Solar Flare (randomised zone, warn then strike)
        self.solar_flare_active  = False
        self.solar_flare_warn_t  = 0.0   # counts down during warning phase
        self.solar_flare_hit_t   = 0.0   # counts down during beam-strike phase
        self.solar_flare_beam_x  = 0.0   # world x centre of the zone
        self.solar_flare_t       = 0.0   # kept for HUD compat (mirrors warn+hit)

        # spell state – Typhoon / Rain
        self.typhoon_t  = 0.0
        self.rain_drops = []

        # spell state – Flood
        self.flood_active  = False
        self.flood_y       = 0.0
        self.flood_t       = 0.0   # countdown timer; flood drains when this hits 0
        self.flood_alarm_t = 0.0   # brief red warning pulse when flood starts

        self._load_tile_layers(tmx_map)
        self._load_objects(tmx_map)

        if self.runner is None:
            raise ValueError("The map needs a rectangle object named 'Player'")

        lefts  = [z.right for side, z in self.spike_zones if side == "left"]
        rights = [z.left  for side, z in self.spike_zones if side == "right"]
        if lefts and rights:
            self.spike_bounds = (max(lefts), min(rights))
        else:
            print("[WARNING] No SpikeZone on both sides – Moving Bats spell disabled")

        self.start_bottom = self.runner.rect.bottom
        self.goal_top     = min((g.top for g in self.goal_rects), default=0)
        self.all_sprites.snap(self.runner.rect.center)
        self.runner.jump_locked = True

    # ================================================================== loading
    def _load_tile_layers(self, tmx):
        baked = {}
        for layer in tmx.layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            key = layer.name.lower()
            z   = LAYER_Z.get(key, Z_LAYERS['bg details'])
            for x, y, surf in layer.tiles():
                pos = (x * TILE_SIZE, y * TILE_SIZE)
                if key == 'terrain':
                    self.solids.add(Tile(pos, surf, 'solid'))
                elif key == 'platforms':
                    self.semis.add(Tile(pos, surf, 'one_way'))
                elif key == 'bounce':
                    self.semis.add(Tile(pos, surf, 'bounce'))
                elif key == 'spike':
                    pass   # spike traps temporarily disabled
                    # self.hazards.add(Tile(pos, surf, 'spike'))
                elif key == 'spike inverted':
                    self.hazards.add(Tile(pos, surf, 'spike_down'))
                elif key == 'goal':
                    self.goal_rects.append(
                        pygame.FRect(pos[0], pos[1], TILE_SIZE, TILE_SIZE))
                if layer.visible and key != 'spike':   # spike images removed temporarily
                    if z not in baked:
                        baked[z] = TileLayer((self.width, self.height), z, self.all_sprites)
                    if layer.opacity < 1:
                        surf = surf.copy()
                        surf.set_alpha(round(layer.opacity * 255))
                    baked[z].image.blit(surf, pos)

    def _load_objects(self, tmx):
        for layer in tmx.layers:
            if not isinstance(layer, pytmx.TiledObjectGroup):
                continue
            for obj in layer:
                kind     = (obj.name or getattr(obj, 'type', '') or '').lower()
                pos      = (obj.x, obj.y)
                has_size = obj.width > 0 and obj.height > 0
                size     = (obj.width, obj.height)
                props    = obj.properties

                if kind == 'player':
                    self.runner = Runner(
                        pos, size if has_size else RUNNER_SIZE,
                        self.all_sprites, self)
                elif kind == 'goal':
                    size = size if has_size else (TILE_SIZE, TILE_SIZE)
                    self.goal_rects.append(pygame.FRect(pos[0], pos[1], *size))
                    if getattr(obj, 'visible', True):
                        GoalSprite(pos, assets.get('goal', size),
                                   self.all_sprites, Z_LAYERS['main'] - 0.1)
                elif kind == 'darttrap':
                    default   = 'right' if obj.x < self.width / 2 else 'left'
                    direction = 1 if str(props.get('dir', default)).lower() in ('right','r') else -1
                    trap = DartTrap(
                        pos, size if has_size else (TILE_SIZE, TILE_SIZE),
                        direction, self.rng.uniform(0, DART_INTERVAL), self.all_sprites)
                    self.solids.add(trap)
                    self.traps.append(trap)
                elif kind in ('speed', 'heart'):
                    Pickup(kind, pos, size if has_size else PICKUP_SIZE,
                           (self.all_sprites, self.pickup_sprites))
                elif kind == 'spikezone':
                    rect = pygame.FRect(pos[0], pos[1], obj.width, obj.height)
                    side = str(props.get('side') or
                               ('left' if rect.centerx < self.width / 2 else 'right')).lower()
                    self.spike_zones.append((side, rect))
                elif kind in PATH_PLATFORMS:
                    nat     = assets.natural_size(kind)
                    pw, ph  = nat if nat else PATH_PLATFORMS[kind]
                    pw, ph  = pw * PATH_SCALE, ph * PATH_SCALE
                    speed   = float(props.get('speed', 40)) * PATH_SCALE
                    if obj.width > obj.height:
                        axis, plat_pos = 'x', (obj.x, obj.y + obj.height/2 - ph/2)
                        distance = obj.width - pw
                    else:
                        axis, plat_pos = 'y', (obj.x + obj.width/2 - pw/2, obj.y)
                        distance = obj.height - ph
                    sprite = MovingSprite(
                        plat_pos, (pw, ph), axis, max(0, distance), speed,
                        PATH_SOLID, self.all_sprites, art=kind if assets.has(kind) else None)
                    self.moving_sprites.append(sprite)
                    (self.solids if PATH_SOLID else self.semis).add_moving(sprite)
                elif kind in ('movingplatform', 'movingblock'):
                    solid  = kind == 'movingblock'
                    sprite = MovingSprite(
                        pos, size if has_size else (TILE_SIZE * 3, TILE_SIZE),
                        str(props.get('axis', 'x')).lower(),
                        float(props.get('distance', 3 * TILE_SIZE)),
                        float(props.get('speed', 40)), solid, self.all_sprites)
                    self.moving_sprites.append(sprite)
                    (self.solids if solid else self.semis).add_moving(sprite)
                elif obj.name and assets.legacy_file(obj.name):
                    Sprite(pos,
                           assets.get(obj.name, size if has_size else assets.natural_size(obj.name)),
                           self.all_sprites, Z_LAYERS['bg details'])
                elif kind:
                    print(f"[WARNING] Unknown object {kind!r} – ignored")

    # ================================================================== helpers
    @property
    def orb_pos(self):
        return self.to_world(self.ORB_SCREEN)

    @property
    def progress(self):
        if self.winner == "runner": return 1.0
        total = self.start_bottom - self.goal_top
        if total <= 0: return 0.0
        return max(0.0, min(1.0, (self.start_bottom - self.runner.rect.bottom) / total))

    def to_world(self, screen_pos):
        off = self.all_sprites.draw_offset
        return screen_pos[0] - off[0], screen_pos[1] - off[1]

    def in_bounds(self, rect):
        return (rect.left >= 0 and rect.top >= 0
                and rect.right <= self.width and rect.bottom <= self.height)

    def set_winner(self, winner):
        """Declare a match winner once and play the end-of-match sound."""
        if self.winner is not None:
            return
        self.winner = winner
        if winner in ("runner", "caster"):
            sounds.play("victory")

    def hits_solid(self, rect):
        return any(rect.colliderect(s.rect) for s in self.solids.query(rect))

    def solar_flare_collision_y(self, world_x):
        """Unused in new design but kept so nothing else breaks."""
        return float(self.height)

    # ================================================================== update
    def update(self, dt, keys):
        if self.winner:
            return

        if self.countdown > 0:
            self.countdown = max(0.0, self.countdown - dt)
            if self.countdown <= 0:
                self.runner.jump_locked = False

        r = self.runner

        for s in self.moving_sprites:
            s.update(dt)
        r.update(dt, keys)
        for s in self.moving_sprites:
            if s.solid:
                s.check_crush(r)

        cam_mid_y = -self.all_sprites.offset.y + VIEW_H / 2
        for trap in self.traps:
            if abs(trap.rect.centery - cam_mid_y) < WINDOW_HEIGHT * 1.5:
                trap.update(dt, self)

        for p in list(self.projectile_sprites.sprites()):
            p.update(dt, self)
            if p.alive():
                self._projectile_vs_runner(p)

        for s in list(self.spike_sprites.sprites()):
            s.update(dt)
            if s.alive() and r.rect.colliderect(s.rect):
                if r.shield <= 0:
                    r.hit(s.rect.centerx)

        for b in list(self.effect_sprites.sprites()):
            b.update(dt)

        self._update_earthquake(dt)
        self._update_lightning(dt)
        self._update_solar_flare(dt)
        self._update_typhoon(dt)
        self._update_moss()
        self._update_flood(dt)

        self._contacts()
        self._pickups(dt)

        if not self.winner and r.hearts <= 0:
            self.set_winner("caster")
        self.all_sprites.update_camera(r.rect.center, dt)

    # ------------------------------------------------------------------ earthquake
    def _update_earthquake(self, dt):
        if self.earthquake_t <= 0:
            # No earthquake – but a lightning/flare hit may have started a short shake
            if self.shake_t > 0:
                self.shake_t = max(0.0, self.shake_t - dt)
                amp = 2
                self.shake_offset = (self.rng.randint(-amp, amp), self.rng.randint(-amp, amp))
            else:
                self.shake_offset = (0, 0)
            return
        self.earthquake_t = max(0.0, self.earthquake_t - dt)
        amp = EARTHQUAKE_SHAKE_AMP
        self.shake_offset = (self.rng.randint(-amp, amp), self.rng.randint(-amp, amp))

        self.rock_spawn_t -= dt
        if self.rock_spawn_t <= 0:
            self.rock_spawn_t = ROCK_FALL_INTERVAL
            off     = self.all_sprites.draw_offset
            cam_y   = -off[1]
            spawn_y = cam_y - ROCK_SIZE - 4
            # Spawn 1-3 rocks per interval for more chaos
            count = self.rng.randint(1, 3)
            for _ in range(count):
                spawn_x = self.rng.uniform(ROCK_SIZE, self.width - ROCK_SIZE)
                FallingRock(spawn_x, spawn_y, (self.all_sprites, self.rock_sprites))

        r = self.runner
        for rock in list(self.rock_sprites.sprites()):
            rock.update(dt, self)
            if rock.alive() and not rock.hit_done and rock.rect.colliderect(r.rect):
                rock.hit_done = True
                if r.shield <= 0:
                    r.hit(rock.cx)

    # ------------------------------------------------------------------ lightning
    def _update_lightning(self, dt):
        r = self.runner
        for entry in list(self.pending_lightning):
            entry["t"] -= dt
            if entry["t"] <= 0:
                self.pending_lightning.remove(entry)
                self.shake_t = 0.5 # short screen shake on lightning strike
                LightningBolt(entry["x"], self.height,
                              (self.all_sprites, self.effect_sprites))
                # Damage zone matches the visible warning column (LIGHTNING_WIDTH)
                bolt_rect = pygame.FRect(
                    entry["x"] - LIGHTNING_WIDTH // 2, 0,
                    LIGHTNING_WIDTH, self.height)
                if bolt_rect.colliderect(r.rect) and r.shield <= 0:
                    r.hit(entry["x"])

    # ------------------------------------------------------------------ solar flare
    def _update_solar_flare(self, dt):
        """Phase 1: warning flash  →  Phase 2: beam strike  →  done."""
        if not self.solar_flare_active:
            return

        r = self.runner

        if self.solar_flare_warn_t > 0:
            # ---- WARNING PHASE ----
            self.solar_flare_warn_t = max(0.0, self.solar_flare_warn_t - dt)
            self.solar_flare_t      = self.solar_flare_warn_t   # HUD compat
            if self.solar_flare_warn_t <= 0:
                # Transition to strike — shake the screen
                self.shake_t           = 1.0
                self.solar_flare_hit_t = SOLAR_FLARE_HIT_TIME
                # Deal damage: solar flare hits for SOLAR_FLARE_HEARTS hearts
                bw        = SOLAR_FLARE_BEAM_W
                zone_rect = pygame.FRect(
                    self.solar_flare_beam_x - bw / 2, 0, bw, self.height)
                if zone_rect.colliderect(r.rect) and r.shield <= 0:
                    for _ in range(SOLAR_FLARE_HEARTS):
                        r.hit(r.cx)
            return

        if self.solar_flare_hit_t > 0:
            # ---- BEAM STRIKE PHASE ----
            self.solar_flare_hit_t = max(0.0, self.solar_flare_hit_t - dt)
            if self.solar_flare_hit_t <= 0:
                self.solar_flare_active = False   # all done
            return

    def _runner_sheltered(self, r, beam_world_x):
        """Kept for compatibility – not used by new solar flare design."""
        return False

    # ------------------------------------------------------------------ typhoon / rain
    def _update_typhoon(self, dt):
        if self.typhoon_t <= 0:
            if self.rain_drops:
                self.rain_drops.clear()
            return
        self.typhoon_t = max(0.0, self.typhoon_t - dt)
        r = self.runner
        # Keep the slow effect alive every frame while typhoon is active
        # Use a value > 0 so runner.update() applies TYPHOON_SLOW_FACTOR
        r.slowed = max(r.slowed, dt * 2)   # always > 0 while typhoon active

        for drop in self.rain_drops:
            drop["x"] += drop["vx"] * dt
            drop["y"] += drop["vy"] * dt
            if drop["y"] > VIEW_H:
                drop["y"] = self.rng.uniform(-10, 0)
                drop["x"] = self.rng.uniform(0, WINDOW_WIDTH)
            if drop["x"] < 0:
                drop["x"] = WINDOW_WIDTH

    # ------------------------------------------------------------------ moss
    def _update_moss(self):
        r = self.runner
        for moss in list(self.moss_sprites.sprites()):
            if not moss.alive() or moss.triggered:
                continue
            if r.rect.colliderect(moss.rect):
                moss.triggered = True
                r.apply_slip()    # knockback only – NO heart damage
                moss.kill()       # disappears immediately on step

    # ------------------------------------------------------------------ flood
    def _update_flood(self, dt):
        self.flood_alarm_t = max(0.0, self.flood_alarm_t - dt)
        if not self.flood_active:
            return
        # Count down the duration timer
        self.flood_t = max(0.0, self.flood_t - dt)
        if self.flood_t <= 0:
            # Duration expired – drain the flood and reset
            self.flood_active = False
            self.flood_y      = 0.0
            return
        speed = FLOOD_RISE_SPEED_TYPHOON if self.typhoon_t > 0 else FLOOD_RISE_SPEED
        self.flood_y -= speed * dt
        self.flood_y  = max(0.0, self.flood_y)
        r = self.runner
        if r.rect.bottom >= self.flood_y:
            r.hit(r.cx)

    # ------------------------------------------------------------------ contacts
    def _projectile_vs_runner(self, p):
        r = self.runner
        if r.shield > 0 and math.hypot(p.cx - r.cx, p.cy - r.cy) <= SHIELD_RADIUS + p.rect.w / 2:
            p.kill()
        elif p.rect.colliderect(r.rect) and r.hit(p.cx):
            p.kill()

    def _contacts(self):
        r = self.runner
        for t in self.hazards.query(r.rect.inflate(2, 2)):
            if r.rect.colliderect(t.hazard_rect):
                r.hit(t.rect.centerx)
        for g in self.goal_rects:
            if r.rect.colliderect(g):
                self.set_winner("runner")

    def _pickups(self, dt):
        r = self.runner
        for pk in list(self.pickup_sprites.sprites()):
            pk.update(dt)
            if not r.rect.colliderect(pk.rect):
                continue
            if pk.kind == "speed":
                r.boost = BOOST_TIME
                sounds.play("speed_up")
            elif r.hearts < MAX_HEARTS:
                r.hearts += 1
                sounds.play("heart")
            else:
                continue
            pk.kill()

    # ================================================================== draw
    def draw(self, surface):
        surface.fill(COLORS["bg"])

        ox_orig, oy_orig = self.all_sprites.draw_offset
        sx, sy = self.shake_offset
        if sx or sy:
            self.all_sprites.draw_offset = (ox_orig + sx, oy_orig + sy)

        # Everything that lives in all_sprites (tiles, platforms, goal, moss, rocks, bats, ...)
        self.all_sprites.draw(surface)

        self.all_sprites.draw_offset = (ox_orig, oy_orig)

        self._draw_rain(surface)
        self._draw_solar_flare(surface)
        self._draw_flood_alarm(surface)
        self._draw_flood(surface)

        ox2, oy2 = self.ORB_SCREEN
        orb = pygame.Rect(ox2 - ORB_SIZE // 2, oy2 - ORB_SIZE // 2, ORB_SIZE, ORB_SIZE)
        assets.draw_block(surface, "orb", orb, t=assets.now())

    def _draw_rain(self, surface):
        if not self.rain_drops:
            return
        # Tint over the whole view (sprite 'rain_overlay', or a translucent blue fill)
        view = pygame.Rect(0, 0, WINDOW_WIDTH, VIEW_H)
        if not assets.draw(surface, "rain_overlay", view):
            overlay = pygame.Surface((WINDOW_WIDTH, VIEW_H), pygame.SRCALPHA)
            overlay.fill((30, 60, 140, 40))
            surface.blit(overlay, (0, 0))
        # Draw each drop; iterate a snapshot copy to avoid mutation issues
        for drop in list(self.rain_drops):
            x, y = int(drop["x"]), int(drop["y"])
            # Clamp to viewport so we never draw outside
            if -10 <= x <= WINDOW_WIDTH + 10 and -10 <= y <= VIEW_H + 10:
                if not assets.draw(surface, "rain_drop", pygame.Rect(x, y, 2, 6)):
                    ex = x + int(drop["vx"] * 0.05)
                    ey = y + 6
                    pygame.draw.line(surface, COLORS["rain_drop"], (x, y), (ex, ey), 1)

    def _draw_solar_flare(self, surface):
        if not self.solar_flare_active:
            return

        off   = self.all_sprites.draw_offset
        bw    = SOLAR_FLARE_BEAM_W
        bx    = int(self.solar_flare_beam_x + off[0])
        t_now = assets.now()

        if self.solar_flare_warn_t > 0:
            # Warning phase: six-frame flare pulse before impact.
            frac = 1.0 - self.solar_flare_warn_t / SOLAR_FLARE_WARN_TIME
            flicker_speed = 6 + frac * 18
            alpha = int(180 * abs(math.sin(t_now * flicker_speed)))
            alpha = max(12, alpha)

            warn_rect = pygame.Rect(bx - bw // 2, 0, bw, VIEW_H)
            warn_t = (SOLAR_FLARE_WARN_TIME - self.solar_flare_warn_t) * 12.0
            if not assets.draw(surface, "flare_warn", warn_rect, t=warn_t, alpha=alpha):
                layer = pygame.Surface((bw, VIEW_H), pygame.SRCALPHA)
                layer.fill((255, 120, 40, alpha))
                surface.blit(layer, (bx - bw // 2, 0))

            draw_text(surface, "SOLAR FLARE!", 14, (255, 220, 40),
                      (bx, VIEW_H // 2), center=True)

        elif self.solar_flare_hit_t > 0:
            # Strike phase: keep the flare animation cycling while the flare is active.
            strike_t = 1.0 - (self.solar_flare_hit_t / max(SOLAR_FLARE_HIT_TIME, 0.001))
            alpha = int(255 * (0.65 + 0.35 * (1.0 - strike_t)))
            strike_rect = pygame.Rect(bx - bw // 2, 0, bw, VIEW_H)
            impact_t = t_now * 6.0
            if not assets.draw(surface, "flare_impact", strike_rect, t=impact_t, alpha=alpha):
                layer = pygame.Surface((bw, VIEW_H), pygame.SRCALPHA)
                layer.fill((255, 245, 120, alpha))
                surface.blit(layer, (bx - bw // 2, 0))

    def _draw_flood_alarm(self, surface):
        if not self.flood_active and self.flood_alarm_t <= 0:
            return
        t = assets.now()
        pulse = 0.35 + 0.65 * abs(math.sin(t * 10.0))
        alpha = int(18 + 26 * pulse)
        overlay = pygame.Surface((WINDOW_WIDTH, VIEW_H), pygame.SRCALPHA)
        overlay.fill((180, 0, 0, alpha))
        surface.blit(overlay, (0, 0))

    def _draw_flood(self, surface):
        if not self.flood_active:
            return
        off      = self.all_sprites.draw_offset
        screen_y = int(self.flood_y + off[1])
        if screen_y >= VIEW_H:
            return
        screen_y = max(0, screen_y)
        water_h  = VIEW_H - screen_y

        # Keep the top edge cleaner and softer so the flood reads like a translucent water sheet,
        # not a compressed block when it reaches the runner.
        water_rect = pygame.Rect(0, screen_y - 10, WINDOW_WIDTH, water_h + 16)
        if assets.draw(surface, "flood", water_rect, t=assets.now(), alpha=90):
            return

        water = pygame.Surface((WINDOW_WIDTH, max(1, water_h + 16)), pygame.SRCALPHA)
        water.fill((30, 80, 180, 0))
        t = assets.now()
        for y in range(0, water_h + 16, 2):
            alpha = int(12 + (y / max(1, water_h + 16)) * 42)
            pygame.draw.line(water, (110, 185, 255, alpha), (0, y), (WINDOW_WIDTH, y))
        for wx in range(0, WINDOW_WIDTH, 5):
            wave_y = int(2.5 * math.sin(wx * 0.13 + t * 2.5))
            pygame.draw.line(water, (140, 220, 255, 45),
                             (wx, max(0, wave_y)), (wx, max(0, wave_y + 4)))
        surface.blit(water, (0, screen_y - 10))