"""Small reusable UI pieces: fonts, text, bars, panels, crosshair and buttons.

TEXT SIZES
----------
Every size in the game comes from FONT_SIZES below. Change a number here and the
whole game follows. Code asks for a name ("small") instead of a number (8).

Text that must fit a box uses fit_text(): it picks the largest size that fits the
box and, if even the smallest size is too wide, cuts the text and ends it with a dot.
Text never spills outside its box.

FONT FILE
---------
The Determination pixel font is read from determination.ttf in the project root (the
folder above src/). If the file is missing the game uses pygame's default font and
prints a warning. It does not crash.
"""
import functools
import os

import pygame

import assets

_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'determination.ttf')

# One place to change text sizes (in pixels).
FONT_SIZES = {
    "title":   20,   # main title only
    "heading": 11,   # panel headers, game-over title, "GET READY"
    "body":    9,    # buttons, subtitles, labels
    "small":   8,    # HUD text, control lines, spell names
    "tiny":    7,    # hotkeys, spell-slot counts, tight rows
}
MIN_FONT = 6         # fitted text never goes below this size

CROSSHAIR_SIZE = 17
_fonts = {}
_warned_missing_font = False


def size_of(size):
    """Accept a number or a FONT_SIZES name and return a pixel size."""
    return FONT_SIZES[size] if isinstance(size, str) else int(size)


def _load_font(size):
    global _warned_missing_font
    try:
        return pygame.font.Font(_FONT_PATH, size)
    except (OSError, pygame.error) as err:
        if not _warned_missing_font:
            print(f"[ui] could not load {_FONT_PATH} ({err}); using pygame's default font.")
            _warned_missing_font = True
        return pygame.font.Font(None, size)


def font(size):
    """Cached Determination font at a size (number or FONT_SIZES name)."""
    px = size_of(size)
    if px not in _fonts:
        _fonts[px] = _load_font(px)
    return _fonts[px]


def text_width(text, size):
    return font(size).size(text)[0]


def fit_size(text, max_w, sizes=(12, 11, 10, 9)):
    """Largest size from `sizes` whose text fits in max_w pixels (kept for older code)."""
    for size in sizes:
        if text_width(text, size) <= max_w:
            return size
    return sizes[-1]


@functools.lru_cache(maxsize=2048)
def _fit_plan(text, max_w, max_h, max_size, min_size):
    """Return (size, shown_text): the largest size in [min_size, max_size] that fits
    max_w x max_h. If nothing fits, the smallest size is used and the text is cut
    (ending in '.') so that it is no wider than max_w."""
    for size in range(max_size, min_size - 1, -1):
        f = font(size)
        if f.size(text)[0] <= max_w and f.get_height() <= max_h:
            return size, text
    f = font(min_size)
    if f.size(text)[0] <= max_w:
        return min_size, text
    shown = text
    while shown and f.size(shown + ".")[0] > max_w:
        shown = shown[:-1]
    return min_size, (shown.rstrip() + ".") if shown.strip() else ""


def fit_text(surface, text, rect, color, max_size="body", min_size=MIN_FONT,
             align="center", shadow=False):
    """Draw text inside rect at the largest size that fits. Returns the size used.

    align: "center", "left" or "right" (vertically centred in rect).
    The drawing is clipped to rect, so text can never leak outside its box.
    """
    rect = pygame.Rect(rect)
    hi, lo = size_of(max_size), size_of(min_size)
    if lo > hi:
        lo = hi
    if rect.w <= 0 or rect.h <= 0 or not text:
        return lo
    size, shown = _fit_plan(text, rect.w, rect.h, hi, lo)
    if not shown:
        return size
    f = font(size)
    img = f.render(shown, True, color)
    if align == "left":
        dest = img.get_rect(midleft=(rect.left, rect.centery))
    elif align == "right":
        dest = img.get_rect(midright=(rect.right, rect.centery))
    else:
        dest = img.get_rect(center=rect.center)
    old_clip = surface.get_clip()
    surface.set_clip(rect)
    if shadow:
        surface.blit(f.render(shown, True, (0, 0, 0)), dest.move(1, 1))
    surface.blit(img, dest)
    surface.set_clip(old_clip)
    return size


def draw_text(surface, text, size, color, pos, center=True, shadow=False):
    """Plain text at a point (no fitting). `size` is a number or a FONT_SIZES name."""
    f    = font(size)
    img  = f.render(text, True, color)
    rect = img.get_rect(center=pos) if center else img.get_rect(topleft=pos)
    if shadow:
        surface.blit(f.render(text, True, (0, 0, 0)), rect.move(1, 1))
    surface.blit(img, rect)
    return rect


def draw_bar(surface, rect, fraction, color):
    """Progress bar. Sprites: bar_bg (background) and bar_fill (tinted with color)."""
    fraction = max(0.0, min(1.0, fraction))
    rect = pygame.Rect(rect)
    has_bg = assets.draw(surface, "bar_bg", rect)
    if not has_bg:
        pygame.draw.rect(surface, (20, 18, 28), rect)
    fill_w = int(rect.w * fraction)
    if fill_w > 0:
        fill = pygame.Rect(rect.x, rect.y, fill_w, rect.h)
        if not assets.draw(surface, "bar_fill", fill, tint=color):
            pygame.draw.rect(surface, color, fill)
    if not has_bg:
        pygame.draw.rect(surface, (60, 55, 80), rect, 1)


def draw_panel(surface, rect, color=(14, 11, 22), alpha=170, radius=4, border=None, key="panel"):
    """Translucent rounded box."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    if assets.draw(surface, key, rect):
        return
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, (*color, alpha), layer.get_rect(), border_radius=radius)
    surface.blit(layer, rect.topleft)
    if border is not None:
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)


def dim_rect(surface, rect, alpha=150, key=None):
    """Darkens a rectangle."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    if key and assets.draw(surface, key, rect):
        return
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    layer.fill((0, 0, 0, alpha))
    surface.blit(layer, rect.topleft)


def draw_crosshair(surface, pos, color, key="crosshair"):
    x, y = int(pos[0]), int(pos[1])
    half = CROSSHAIR_SIZE // 2
    if assets.draw(surface, key, pygame.Rect(x - half, y - half, CROSSHAIR_SIZE, CROSSHAIR_SIZE)):
        return
    pygame.draw.circle(surface, color, (x, y), 4, 1)
    pygame.draw.line(surface, color, (x - 8, y), (x - 5, y), 1)
    pygame.draw.line(surface, color, (x + 5, y), (x + 8, y), 1)
    pygame.draw.line(surface, color, (x, y - 8), (x, y - 5), 1)
    pygame.draw.line(surface, color, (x, y + 5), (x, y + 8), 1)


class Button:
    """Clickable button. The label is fitted inside the button, so it never overflows.

    size: the largest text size the label may use (number or FONT_SIZES name).
    Sprites: <key> (normal), <key>_hover and <key>_selected.
    """

    PAD_X, PAD_Y = 4, 1

    def __init__(self, rect, text, size="small", key="button"):
        self.rect     = pygame.Rect(rect)
        self.text     = text
        self.size     = size
        self.selected = False
        self.key      = key

    def clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos))

    def draw(self, surface):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        if self.selected:
            state = "_selected"
        elif hover:
            state = "_hover"
        else:
            state = ""
        if not assets.draw(surface, self.key + state, self.rect):
            color = (70, 170, 110) if self.selected else (95, 95, 140) if hover else (60, 60, 95)
            pygame.draw.rect(surface, color, self.rect, border_radius=3)
            pygame.draw.rect(surface, (230, 230, 240), self.rect, 1, border_radius=3)
        label_box = self.rect.inflate(-2 * self.PAD_X, -2 * self.PAD_Y)
        fit_text(surface, self.text, label_box, (255, 255, 255), max_size=self.size)