"""Base sprites: Sprite, Tile, baked tile layers, moving platforms and the collision grid."""
from settings import *
import assets


class Sprite(pygame.sprite.Sprite):
    def __init__(self, pos, surf, groups=None, z=Z_LAYERS['main']):
        super().__init__()
        if groups is not None:
            self.add(groups)
        self.image = surf
        self.rect = self.image.get_frect(topleft=pos)
        self.old_rect = self.rect.copy()
        self.z = z


class Tile(Sprite):
    """One collision tile. Kept out of the draw group (the tile layers are drawn pre-baked)."""

    def __init__(self, pos, surf, kind):
        super().__init__(pos, surf)
        self.kind = kind                        # solid | one_way | bounce | spike | spike_down
        self.bounce = kind == 'bounce'
        self.hazard_rect = None
        r = self.rect
        if kind == 'spike':                     # spikes only hurt on their sharp part
            self.hazard_rect = pygame.FRect(r.x + 2, r.y + 6, r.w - 4, r.h - 6)
        elif kind == 'spike_down':
            self.hazard_rect = pygame.FRect(r.x + 2, r.y, r.w - 4, r.h - 6)


class TileLayer(pygame.sprite.Sprite):
    """All tile layers that share a z value, baked into one big surface. Only the visible part is blitted."""

    def __init__(self, size, z, groups):
        super().__init__(groups)
        self.image = pygame.Surface(size, pygame.SRCALPHA)
        self.z = z

    def draw(self, surface, offset):
        ox, oy = offset
        src = pygame.Rect(-ox, -oy, WINDOW_WIDTH, WINDOW_HEIGHT).clip(self.image.get_rect())
        if src.w > 0 and src.h > 0:
            surface.blit(self.image, (src.x + ox, src.y + oy), src)


class SpriteGrid:
    """Spatial lookup so collisions only look at the tiles near the runner, not the whole castle."""

    def __init__(self):
        self.cells = {}
        self.dynamic = []                       # moving platforms: few, so always checked

    def add(self, sprite):
        r, T = sprite.rect, TILE_SIZE
        for row in range(int(r.top // T), int((r.bottom - 0.01) // T) + 1):
            for col in range(int(r.left // T), int((r.right - 0.01) // T) + 1):
                self.cells.setdefault((col, row), []).append(sprite)

    def add_moving(self, sprite):
        self.dynamic.append(sprite)

    def query(self, rect):
        T = TILE_SIZE
        found = []
        for row in range(int(rect.top // T), int((rect.bottom - 0.01) // T) + 1):
            for col in range(int(rect.left // T), int((rect.right - 0.01) // T) + 1):
                found.extend(self.cells.get((col, row), ()))
        found.extend(self.dynamic)
        return found


class MovingSprite(Sprite):
    """A platform that slides back and forth. Its Tiled rectangle is its size AND start position.

    Tiled custom properties: axis ('x'/'y'), distance (pixels, negative = start moving the other
    way), speed (pixels/second). solid=True blocks from every side and reverses if it would crush
    the runner; solid=False is a one-way platform you can jump up through.

    `art` is the name of graphics/objects/<art>.png to draw (used by old-style path platforms).
    When it is None the default 'moving_block' / 'moving_platform' art is used.
    """
    moving = True

    def __init__(self, pos, size, axis, distance, speed, solid, groups, art=None):
        name = art or ('moving_block' if solid else 'moving_platform')
        super().__init__(pos, assets.get(name, size), groups, Z_LAYERS['main'] + 0.1)
        self.solid, self.axis, self.speed = solid, axis, speed
        self.origin = vector(pos)
        self.lo, self.hi = min(0, distance), max(0, distance)
        sign = 1 if distance >= 0 else -1
        self.direction = vector(sign, 0) if axis == 'x' else vector(0, sign)
        self.crushed = False

    def check_border(self):
        i = 0 if self.axis == 'x' else 1
        rel = (self.rect.x if i == 0 else self.rect.y) - self.origin[i]
        if self.direction[i] > 0 and rel >= self.hi:
            self.direction[i], rel = -1, self.hi
        elif self.direction[i] < 0 and rel <= self.lo:
            if not self.crushed:
                self.direction[i] = 1
            rel = self.lo
        if i == 0:
            self.rect.x = self.origin[0] + rel
        else:
            self.rect.y = self.origin[1] + rel

    def check_crush(self, runner):
        if self.rect.colliderect(runner.rect) and self.direction.y > 0:
            self.direction.y = -1
            self.crushed = True
        if self.crushed and not self.rect.colliderect(runner.rect):
            self.crushed = False

    def update(self, dt):
        self.old_rect = self.rect.copy()
        self.rect.x += self.direction.x * self.speed * dt
        self.rect.y += self.direction.y * self.speed * dt
        self.check_border()
