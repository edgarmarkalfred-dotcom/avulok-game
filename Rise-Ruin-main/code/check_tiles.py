import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pygame

img = pygame.image.load('../data/levels/stone platform.png')
print("png size:", img.get_size())
print()
print("---- bg 1st level.tsx ----")
with open('../data/levels/bg 1st level.tsx', encoding='utf-8') as f:
    print(f.read())