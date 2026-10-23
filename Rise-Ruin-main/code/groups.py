"""The draw group + camera. The camera follows the runner (clamped to the map)."""
from settings import *


class Allsprites(pygame.sprite.Group):
    def __init__(self, map_w, map_h):
        super().__init__()
        self.offset = vector()
        self.draw_offset = (0, 0)               # rounded offset used by the last draw (also used for the mouse)
        self.map_w, self.map_h = map_w, map_h

    def constrain(self):
        if self.map_w > WINDOW_WIDTH:
            self.offset.x = max(WINDOW_WIDTH - self.map_w, min(0, self.offset.x))
        else:                                                    # narrow map: centre it
            self.offset.x = (WINDOW_WIDTH - self.map_w) / 2
        if self.map_h > VIEW_H:
            self.offset.y = max(VIEW_H - self.map_h, min(0, self.offset.y))
        else:
            self.offset.y = VIEW_H - self.map_h
        self.draw_offset = (round(self.offset.x), round(self.offset.y))

    def _wanted(self, target):
        # the runner sits 60% down the view, so you see more of what is above you
        return vector(WINDOW_WIDTH / 2 - target[0], VIEW_H * 0.6 - target[1])

    def snap(self, target):
        self.offset = self._wanted(target)
        self.constrain()

    def update_camera(self, target, dt):
        self.offset += (self._wanted(target) - self.offset) * min(10 * dt, 1)
        self.constrain()

    def draw(self, surface):
        ox, oy = self.draw_offset
        view = pygame.FRect(-ox, -oy, WINDOW_WIDTH, WINDOW_HEIGHT)
        for sprite in sorted(self.sprites(), key=lambda s: s.z):
            if hasattr(sprite, 'draw'):                          # custom drawing (runner, pickups, ...)
                sprite.draw(surface, self.draw_offset)
            elif view.colliderect(sprite.rect):
                surface.blit(sprite.image, (round(sprite.rect.x + ox), round(sprite.rect.y + oy)))
