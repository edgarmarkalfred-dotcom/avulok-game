"""Power-ups lying around the castle (Tiled objects named 'Speed' and 'Heart').

Sprites: 'speed' and 'heart' (the HUD uses 'heart' and 'heart_empty' too). See assets.py.
"""
import math
import random
from settings import *
from sprites import Sprite
import assets


class Pickup(Sprite):
    def __init__(self, kind, pos, size, groups):
        super().__init__(pos, assets.get(kind, size), groups, Z_LAYERS['main'] + 0.2)
        self.kind = kind                                   # "speed" or "heart"
        self.t = random.random() * 6

    def update(self, dt):
        self.t += dt

    def draw(self, surface, offset):
        bob = round(math.sin(self.t * 4) * 1.5)
        assets.draw_block(surface, self.kind, to_screen(self.rect, offset).move(0, bob), t=self.t)