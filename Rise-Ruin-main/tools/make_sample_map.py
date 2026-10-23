"""Generates a playable sample map (data/levels/castle_1.tmx) and its tileset PNG.

Plain Python, no pygame needed. It turns the old SECTION_A + SECTION_B platform lists into Tiled
layers/objects so you can open the result in Tiled and see how a map is put together. Delete this
file once you build your own maps.
"""
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TMX_PATH = os.path.join(HERE, "..", "data", "levels", "castle_1.tmx")
PNG_PATH = os.path.join(HERE, "..", "graphics", "tilesets", "castle_tiles.png")

T = 16
W = 30                      # map width in tiles
WALL = 7                    # thick castle walls, interior = columns 7..22 (16 wide, same as the old map)
SHIFT = 5                   # old interior was columns 2..17

FLOOR = "=" * 16
SECTION_A = [
    (2, 3, "======"), (2, 10, "====="), (2, 3, "====="), (1, 9, "===="), (2, 14, "==="),
    (2, 8, "====="), (2, 3, "===="), (3, 6, "====="), (1, 12, "===="), (3, 2, FLOOR),
]
SECTION_B = [
    (2, 3, "==^^==="), (2, 12, "====="), (2, 6, "====="), (2, 2, "=B=="), (5, 8, "====="),
    (2, 4, "==^^===="), (2, 13, "====", "R"), (2, 6, "======"), (3, 3, "====="),
    (1, 10, "=====", "L"), (2, 4, "===="), (3, 2, FLOOR),
]

# tile ids in the tileset (gid = id + 1 in the tmx)
WALL_T, STONE_T, BOUNCE_T, SPIKE_T, GOAL_T, PAPER_T = 1, 2, 3, 4, 5, 6


# ------------------------------------------------------------------ tileset art (tiny PNG writer)
def tile_pixels(kind):
    rows = [[(0, 0, 0, 0)] * T for _ in range(T)]

    def fill(x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                rows[y][x] = c + (255,)

    if kind == "wall":
        fill(0, 0, T, T, (72, 68, 92))
        fill(0, 7, T, 8, (48, 45, 64))
        fill(0, 15, T, 16, (48, 45, 64))
        fill(7, 0, 8, 7, (48, 45, 64))
        fill(3, 8, 4, 15, (48, 45, 64))
        fill(11, 8, 12, 15, (48, 45, 64))
    elif kind == "stone":
        fill(0, 0, T, T, (140, 130, 120))
        fill(0, 0, T, 2, (175, 165, 155))
        fill(0, T - 2, T, T, (96, 88, 80))
    elif kind == "bounce":
        fill(0, 0, T, T, (70, 210, 100))
        fill(0, 0, T, 2, (120, 240, 150))
        fill(0, T - 2, T, T, (40, 130, 60))
        fill(3, 6, T - 3, 8, (40, 130, 60))
        fill(3, 10, T - 3, 12, (40, 130, 60))
    elif kind == "spike":
        for i in range(3):                                      # three red spikes on the lower part
            cx = 2 + i * 5 + 2
            for y in range(6, T):
                half = (y - 6) // 3 + 1
                fill(max(0, cx - half), y, min(T, cx + half + 1), y + 1, (230, 60, 60))
    elif kind == "goal":
        fill(0, 0, T, T, (255, 215, 0))
        fill(0, 0, T, 1, (255, 245, 150))
        fill(0, T - 1, T, T, (190, 150, 0))
    elif kind == "paper":
        fill(0, 0, T, T, (38, 34, 54))
        fill(0, 0, 8, 8, (43, 39, 61))
        fill(8, 8, T, T, (43, 39, 61))
    return rows


def write_tileset(path):
    kinds = ["wall", "stone", "bounce", "spike", "goal", "paper"]
    tiles = [tile_pixels(k) for k in kinds]
    width, height = T * len(tiles), T
    raw = b""
    for y in range(T):
        raw += b"\x00" + bytes(v for tile in tiles for px in tile[y] for v in px)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return width, height, len(kinds)


# ------------------------------------------------------------------ the map
def build():
    platforms = [dict(level=0, col=WALL, pattern="=" * (W - 2 * WALL), dart=None)]
    level = 0
    for rise, col, pattern, *dart in SECTION_A + SECTION_B:
        level += rise
        platforms.append(dict(level=level, col=col + SHIFT, pattern=pattern, dart=dart[0] if dart else None))
    rows = level + 8

    def row_of(lv):
        return rows - 2 - lv

    def grid():
        return [[0] * W for _ in range(rows)]

    wallpaper, terrain, ledges, bounce, spike = grid(), grid(), grid(), grid(), grid()
    for r in range(rows):
        for c in range(W):
            if c < WALL or c >= W - WALL or r == 0 or r >= rows - 2:
                terrain[r][c] = WALL_T
            else:
                wallpaper[r][c] = PAPER_T
    for p in platforms[1:]:
        row = row_of(p["level"])
        for i, ch in enumerate(p["pattern"]):
            c = p["col"] + i
            if ch == "B":
                bounce[row][c] = BOUNCE_T
            else:
                ledges[row][c] = STONE_T
            if ch == "^":
                spike[row - 1][c] = SPIKE_T

    objects, oid = [], [0]

    def add(name, x, y, w, h, props=None):
        oid[0] += 1
        objects.append((oid[0], name, x, y, w, h, props or {}))

    add("Player", W * T / 2 - 6, row_of(0) * T - 14, 12, 14)
    last = platforms[-1]
    goal_row = row_of(last["level"])
    add("Goal", (9 + SHIFT) * T, (goal_row - 2) * T, 2 * T, 2 * T)

    normal = [p for p in platforms[1:] if len(p["pattern"]) < 16]
    for n, p in enumerate(normal):
        row = row_of(p["level"])
        if p["dart"]:
            col, direction = (WALL - 1, "right") if p["dart"] == "L" else (W - WALL, "left")
            add("DartTrap", col * T, (row - 1) * T, T, T, {"dir": direction})
        spots = [p["col"] + i for i, ch in enumerate(p["pattern"]) if ch == "="]
        if n in (3, 8, 14, 19):
            add("Speed", spots[len(spots) // 2] * T + 3, (row - 1) * T + 6, 10, 10)
        if n == 11:
            add("Heart", spots[len(spots) // 2] * T + 3, (row - 1) * T + 6, 10, 10)

    add("SpikeZone", 0, 0, WALL * T, rows * T, {"side": "left"})
    add("SpikeZone", (W - WALL) * T, 0, WALL * T, rows * T, {"side": "right"})
    add("MovingPlatform", 17 * T, row_of(1) * T, 3 * T, T, {"axis": "x", "distance": 32, "speed": 30})
    return rows, [wallpaper, terrain, ledges, bounce, spike], objects


def prop_xml(props):
    if not props:
        return ""
    out = ["   <properties>"]
    for k, v in props.items():
        kind = ' type="int"' if isinstance(v, int) else ""
        out.append(f'    <property name="{k}"{kind} value="{v}"/>')
    out.append("   </properties>")
    return "\n" + "\n".join(out) + "\n  "


def write_tmx(path, tileset_size):
    rows, layers, objects = build()
    names = ["wallpaper", "Terrain", "Platforms", "Bounce", "Spike"]
    ts_w, ts_h, count = tileset_size
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" '
           f'width="{W}" height="{rows}" tilewidth="{T}" tileheight="{T}" infinite="0" '
           f'nextlayerid="{len(names) + 2}" nextobjectid="{len(objects) + 1}">',
           f' <tileset firstgid="1" name="castle_tiles" tilewidth="{T}" tileheight="{T}" tilecount="{count}" columns="{count}">',
           f'  <image source="../../graphics/tilesets/castle_tiles.png" width="{ts_w}" height="{ts_h}"/>',
           ' </tileset>']
    for i, (name, g) in enumerate(zip(names, layers), start=1):
        csv = ",\n".join(",".join(str(v) for v in row) for row in g)
        out += [f' <layer id="{i}" name="{name}" width="{W}" height="{rows}">',
                '  <data encoding="csv">', csv, '</data>', ' </layer>']
    out.append(f' <objectgroup id="{len(names) + 1}" name="Objects">')
    for oid, name, x, y, w, h, props in objects:
        body = prop_xml(props)
        tail = f">{body}</object>" if body else "/>"
        out.append(f'  <object id="{oid}" name="{name}" x="{x}" y="{y}" width="{w}" height="{h}"{tail}')
    out += [' </objectgroup>', '</map>']
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return rows


if __name__ == "__main__":
    size = write_tileset(PNG_PATH)
    rows = write_tmx(TMX_PATH, size)
    print(f"wrote {os.path.normpath(PNG_PATH)} and {os.path.normpath(TMX_PATH)} ({W}x{rows} tiles)")
