import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pygame
from pytmx.util_pygame import load_pygame

pygame.init()
pygame.display.set_mode((1, 1))

folder = '../data/levels'
print("Files in", os.path.abspath(folder))
for f in sorted(os.listdir(folder)):
    print("  ", f)

for f in sorted(os.listdir(folder)):
    if not f.lower().endswith('.tmx'):
        continue
    print("\n=====", f)
    try:
        m = load_pygame(os.path.join(folder, f))
    except Exception as e:
        print("  FAILED TO LOAD:", repr(e))
        continue
    for ts in m.tilesets:
        print("  tileset:", ts.name, "| firstgid", ts.firstgid)
    for layer in m.layers:
        if hasattr(layer, "iter_data"):
            bad = {gid for _, _, gid in layer.iter_data() if gid and m.images[gid] is None}
            print("  layer", layer.name, "-> bad gids:", sorted(bad) or "none")