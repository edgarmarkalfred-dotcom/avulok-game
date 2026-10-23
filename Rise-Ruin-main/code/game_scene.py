"""The match itself: runner keyboard input, caster mouse input, HUD and game-over screen.

HUD layout (window 480 x 270, play field above, HUD band below)
  top-left     runner panel    104 px wide: hearts, shield, speed and super-jump status
  top-right    match panel     104 px wide: climb progress, caster status, major pips, cast bar
  above bar    spell tooltip   selected spell, casts left, and whether it can fire now
  bottom bar   spell bar       ten 44 x 22 slots. Each slot: hotkey and casts on top,
                               name (or cooldown / icon) below, accent line at the bottom.

Every piece of text is fitted into a fixed box with ui.fit_text, so nothing overflows.
Sizes come from ui.FONT_SIZES (edit them there).

Caster controls: click a slot, press 1-0, or use the mouse wheel to select a spell.
Click the play field to cast.

Solar Flare: select it and click the play field. The beam warns briefly, then strikes.
"""
import math

import pygame

import assets
import sounds
from settings import *
from caster import Caster
from ui import (Button, dim_rect, draw_bar, draw_crosshair, draw_panel,
                fit_text, text_width)

HUD_TOP  = VIEW_H
WHITE    = (255, 255, 255)
GOLD     = (255, 215, 0)
BAR_BG   = (16, 13, 24)
BAR_EDGE = (62, 54, 88)

# HUD panels (top corners)
PANEL_W = 104        # width of both top panels
PANEL_M = 4          # distance from the screen edge
PAD     = 6          # inner padding
ROW_H   = 10         # height of one stat row

# Spell bar: ten slots in one strip, centred in the HUD band
SLOT_W, SLOT_H, SLOT_GAP = 44, 22, 3
SLOT_Y = HUD_TOP + (HUD_H - SLOT_H) // 2

SLOT_LABELS = ["WATER", "STUN", "BATS", "BOLT", "MOSS",
               "INVERT", "QUAKE", "FLARE", "TYPHOON", "FLOOD"]
SLOT_ACCENTS = [
    (80, 130, 230),   # Dirty Water
    (255, 200, 80),   # Stun
    (200, 150, 90),   # Moving Bats
    (255, 255, 110),  # Lightning
    (80, 190, 80),    # Moss
    (190, 100, 255),  # Inversion
    (190, 140, 80),   # Earthquake
    (255, 150, 50),   # Solar Flare
    (100, 170, 255),  # Typhoon
    (50, 110, 230),   # Flood
]

# Super jump is optional. The HUD only shows it when the runner has it.
SJ_COOLDOWN = SUPER_JUMP_COOLDOWN

# Game-over and menu buttons
GAME_OVER_PANEL = pygame.Rect(110, 56, 260, 128)
GAME_OVER_TITLE = pygame.Rect(120, 66, 240, 22)
GAME_OVER_SUB   = pygame.Rect(120, 96, 240, 12)


# ------------------------------------------------------------------ small helpers
def _clamp01(v):
    return max(0.0, min(1.0, v))


def _ready_frac(cd, cd_max):
    return _clamp01(1.0 - cd / max(cd_max, 0.001))


def _dim(color, k=0.35):
    return tuple(int(v * k) for v in color)


def _accent(i):
    return SLOT_ACCENTS[i] if i < len(SLOT_ACCENTS) else WHITE


def _label(i, spell):
    return SLOT_LABELS[i] if i < len(SLOT_LABELS) else spell.name.upper()


class GameScene:
    def __init__(self, game, roles):
        self.game, self.roles = game, roles
        self.runner_player = 1 if roles[1] == "runner" else 2
        self.caster_player = 3 - self.runner_player
        self.level  = game.new_level()
        self.caster = Caster()

        self.rematch = Button((150, 122, 180, 22), "REMATCH",   "body")
        self.menu    = Button((150, 152, 180, 22), "MAIN MENU", "body")
        self._ended_handled = False

    # ------------------------------------------------------------------ spell bar geometry
    def _slot_x0(self):
        n = len(self.caster.spells)
        total = n * SLOT_W + (n - 1) * SLOT_GAP
        return (WINDOW_WIDTH - total) // 2

    def _slot_rect(self, i):
        return pygame.Rect(self._slot_x0() + i * (SLOT_W + SLOT_GAP), SLOT_Y, SLOT_W, SLOT_H)

    def _slot_at(self, pos):
        if pos[1] < HUD_TOP:
            return None
        for i in range(len(self.caster.spells)):
            if self._slot_rect(i).collidepoint(pos):
                return i
        return None

    # ------------------------------------------------------------------ input
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.show_menu()
            return

        if self.level.winner:
            if self.rematch.clicked(event):
                sounds.play("ui_button_click")
                self.game.start_match(self.roles)
            elif self.menu.clicked(event):
                sounds.play("ui_button_click")
                self.game.show_menu()
            return

        self.level.runner.handle_event(event)

        if event.type == pygame.MOUSEWHEEL:
            self.caster.select(self.caster.selected - event.y)
            sounds.play("ui_button_click")

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            slot = self._slot_at(event.pos)
            if slot is not None:
                self.caster.select(slot)
                sounds.play("ui_button_click")
            elif event.pos[1] < HUD_TOP:
                if self.caster.cast(self.level, event.pos):
                    sounds.play("ui_button_click")

        elif event.type == pygame.KEYDOWN:
            if pygame.K_1 <= event.key <= pygame.K_9:
                num = event.key - pygame.K_1
            elif event.key == pygame.K_0:
                num = 9
            else:
                num = None
            if num is not None and num < len(self.caster.spells):
                self.caster.select(num)
                sounds.play("ui_button_click")

    # ------------------------------------------------------------------ update
    def update(self, dt):
        if not self.level.winner:
            self.caster.update(dt)
            self.level.update(dt, pygame.key.get_pressed())
        else:
            # when the match ends, stop any remaining sound effects / spell loops
            if not self._ended_handled:
                sounds.stop_all_sfx()
                self._ended_handled = True
        mouse_y = pygame.mouse.get_pos()[1]
        pygame.mouse.set_visible(bool(self.level.winner) or mouse_y >= HUD_TOP)

    # ------------------------------------------------------------------ draw
    def draw(self, surface):
        level = self.level
        level.draw(surface)

        self._draw_effect_banners(surface)

        mouse   = pygame.mouse.get_pos()
        in_view = mouse[1] < HUD_TOP

        if not level.winner and in_view:
            self.caster.spell.draw_preview(surface, level, mouse)

        self._draw_hud(surface, mouse)

        # Crosshair only for spells that use it (Inversion draws its own circle)
        if (not level.winner and in_view
                and getattr(self.caster.spell, "uses_crosshair", True)):
            can = (self.caster.can_cast(level)
                   and self.caster.spell.is_valid(level, level.to_world(mouse)))
            draw_crosshair(surface, mouse, WHITE if can else (255, 70, 70),
                           key="crosshair" if can else "crosshair_blocked")

        if level.countdown > 0:
            self._draw_countdown(surface, level.countdown)

        if level.winner:
            self._draw_game_over(surface)

    # ------------------------------------------------------------------ countdown overlay
    def _draw_countdown(self, surface, t):
        dim_rect(surface, (0, 0, WINDOW_WIDTH, VIEW_H), 120, key="countdown_bg")
        cx, cy = WINDOW_WIDTH // 2, VIEW_H // 2

        num  = math.ceil(t)
        # two sizes only, so the font cache stays small while the number pulses
        size = 30 if math.sin(t * math.pi * 2) > 0 else 28
        fit_text(surface, str(num), pygame.Rect(cx - 40, cy - 30, 80, 36), (255, 220, 60), max_size=size)
        fit_text(surface, "GET READY!", pygame.Rect(cx - 120, cy + 10, 240, 14), (220, 220, 220),
                 max_size="heading")
        fit_text(surface, "Runner: move - jump unlocks on GO", pygame.Rect(cx - 120, cy + 28, 240, 10),
                 (180, 180, 180), max_size="small")
        fit_text(surface, "Caster: aim - cast unlocks on GO", pygame.Rect(cx - 120, cy + 40, 240, 10),
                 (180, 180, 180), max_size="small")

    # ------------------------------------------------------------------ effect banners
    def _draw_effect_banners(self, surface):
        lv, runner = self.level, self.level.runner
        msgs = []

        if runner.inverted > 0:
            msgs.append(("CONTROLS INVERTED", (200, 80, 255),
                         runner.inverted / INVERSION_TIME))
        if lv.typhoon_t > 0:
            msgs.append(("TYPHOON - SLOWED", (100, 160, 255),
                         lv.typhoon_t / TYPHOON_DURATION))
        if lv.earthquake_t > 0:
            msgs.append(("EARTHQUAKE", (190, 150, 90),
                         lv.earthquake_t / EARTHQUAKE_DURATION))
        if lv.solar_flare_active:
            msgs.append(("SOLAR FLARE - TAKE COVER", (255, 210, 60),
                         lv.solar_flare_warn_t / max(SOLAR_FLARE_WARN_TIME, 0.001)))
        if lv.flood_active and lv.flood_y < lv.height:
            msgs.append(("FLOOD RISING", (60, 130, 230), 1.0))

        for idx, (text, color, fraction) in enumerate(msgs):
            fraction = _clamp01(fraction)
            w = text_width(text, "small") + 16
            x = (WINDOW_WIDTH - w) // 2
            y = 38 + idx * 13
            draw_panel(surface, (x, y, w, 12), alpha=175, radius=3, key="effect_banner")
            fit_text(surface, text, pygame.Rect(x, y, w, 10), color, max_size="small", shadow=True)
            strip_w = int((w - 8) * fraction)
            if strip_w >= 1:
                strip = pygame.Rect(x + 4, y + 10, strip_w, 2)
                if not assets.draw(surface, "banner_strip", strip, tint=color):
                    pygame.draw.rect(surface, color, strip)

    # ------------------------------------------------------------------ HUD
    def _draw_hud(self, surface, mouse):
        self._draw_runner_panel(surface)
        self._draw_match_panel(surface)
        if not self.level.winner:
            self._draw_spell_tooltip(surface)
        self._draw_spell_bar(surface, mouse)

    def _draw_runner_panel(self, surface):
        r = self.level.runner
        x, y, w = PANEL_M, PANEL_M, PANEL_W

        rows = []
        if r.shield > 0:
            rows.append(("SHIELD", _clamp01(r.shield / SHIELD_TIME), COLORS["shield"]))
        else:
            ready = _ready_frac(r.shield_cd, SHIELD_COOLDOWN)
            rows.append(("SHIELD [S]", ready, COLORS["shield"] if ready >= 1 else (90, 110, 130)))
        if r.boost > 0:
            rows.append(("SPEED", _clamp01(r.boost / BOOST_TIME), COLORS["speed"]))
        if SJ_COOLDOWN > 0 and hasattr(r, "sj_cd"):
            if getattr(r, "sj_active", 0) > 0:
                rows.append((f"SUPER {r.sj_active:.1f}s", 1.0, (255, 230, 60)))
            else:
                ready = _ready_frac(r.sj_cd, SJ_COOLDOWN)
                rows.append(("SUPER [Q]", ready,
                             (255, 255, 255) if ready >= 1 else (120, 120, 160)))

        h = 31 + len(rows) * ROW_H + 2
        draw_panel(surface, (x, y, w, h), alpha=165, border=(44, 38, 62), key="hud_panel")
        fit_text(surface, f"P{self.runner_player} RUNNER", pygame.Rect(x + PAD, y + 4, w - 2 * PAD, 9),
                 (170, 210, 255), max_size="small", align="left", shadow=True)
        for i in range(MAX_HEARTS):
            assets.draw_block(surface, "heart" if i < r.hearts else "heart_empty",
                              pygame.Rect(x + PAD + i * 13, y + 16, 11, 11))

        label_w = 46
        bar_x   = x + PAD + label_w + 2
        bar_w   = x + w - PAD - bar_x
        ry = y + 31
        for label, frac, color in rows:
            fit_text(surface, label, pygame.Rect(x + PAD, ry, label_w, 8), (200, 200, 215),
                     max_size="small", align="left")
            draw_bar(surface, (bar_x, ry + 2, bar_w, 4), frac, color)
            ry += ROW_H

    def _draw_match_panel(self, surface):
        lv, c = self.level, self.caster
        w, h = PANEL_W, 58
        x, y = WINDOW_WIDTH - w - PANEL_M, PANEL_M
        draw_panel(surface, (x, y, w, h), alpha=165, border=(44, 38, 62), key="hud_panel")
        inner_x = x + PAD
        inner_w = w - 2 * PAD

        pct = int(_clamp01(lv.progress) * 100)
        fit_text(surface, "CLIMB", pygame.Rect(inner_x, y + 4, 50, 9), (200, 200, 215),
                 max_size="small", align="left", shadow=True)
        fit_text(surface, f"{pct}%", pygame.Rect(x + w - PAD - 30, y + 4, 30, 9), WHITE,
                 max_size="small", align="right")
        draw_bar(surface, (inner_x, y + 15, inner_w, 4), lv.progress, COLORS["goal"])

        if lv.countdown > 0:
            cname, ccol = f"P{self.caster_player} CASTER  LOCKED", (230, 110, 110)
        else:
            cname, ccol = f"P{self.caster_player} CASTER", (220, 190, 255)
        fit_text(surface, cname, pygame.Rect(inner_x, y + 23, inner_w, 9), ccol,
                 max_size="small", align="left", shadow=True)

        fit_text(surface, "MAJOR", pygame.Rect(inner_x, y + 35, 30, 8), (200, 200, 215),
                 max_size="small", align="left")
        on_cd   = c.majors_on_cooldown
        pips_x  = inner_x + 32
        pip_gap = 4
        pip_w   = (x + w - PAD - pips_x - pip_gap) // max(1, MAX_MAJOR_ON_CD)
        for k in range(MAX_MAJOR_ON_CD):
            px = pips_x + k * (pip_w + pip_gap)
            pip = pygame.Rect(px, y + 36, pip_w, 6)
            filled = k < on_cd
            if not assets.draw(surface, "pip_on" if filled else "pip_off", pip):
                pygame.draw.rect(surface, (255, 140, 60) if filled else (46, 40, 64), pip, border_radius=2)

        fit_text(surface, "CAST", pygame.Rect(inner_x, y + 47, 30, 8), (200, 200, 215),
                 max_size="small", align="left")
        draw_bar(surface, (pips_x, y + 49, x + w - PAD - pips_x, 3),
                 _ready_frac(c.global_cd, CAST_COOLDOWN), COLORS["orb"])

    def _draw_spell_tooltip(self, surface):
        c, lv = self.caster, self.level
        i     = c.selected

        if lv.countdown > 0:
            status, col = "LOCKED", (230, 110, 110)
        elif c.spell_cd > 0:
            status, col = f"READY IN {c.spell_cd:.1f}s", (255, 220, 90)
        elif c.majors_on_cooldown >= MAX_MAJOR_ON_CD and c._is_major(i):
            status, col = "2 MAJORS ACTIVE", (255, 140, 60)
        elif c.global_cd > 0:
            status, col = "WAIT", (200, 200, 220)
        else:
            status, col = "READY", (120, 230, 120)

        name  = c.spell.name.upper()
        gap   = 10
        w_nm  = text_width(name, "small")
        w_st  = text_width(status, "small")
        total = w_nm + gap + w_st
        x     = (WINDOW_WIDTH - total) // 2
        y     = HUD_TOP - 15

        draw_panel(surface, (x - 6, y, total + 12, 12), alpha=185, radius=3, key="tooltip")
        fit_text(surface, name, pygame.Rect(x, y, w_nm, 12), WHITE, max_size="small", align="left")
        fit_text(surface, status, pygame.Rect(x + w_nm + gap, y, w_st, 12), col,
                 max_size="small", align="left")

    def _draw_spell_bar(self, surface, mouse):
        bar = pygame.Rect(0, HUD_TOP, WINDOW_WIDTH, HUD_H)
        if not assets.draw(surface, "hud_bar", bar):
            pygame.draw.rect(surface, BAR_BG, bar)
            pygame.draw.line(surface, BAR_EDGE, (0, HUD_TOP), (WINDOW_WIDTH - 1, HUD_TOP))

        hovered = self._slot_at(mouse)
        for i in range(len(self.caster.spells)):
            self._draw_slot(surface, i,
                            selected=(i == self.caster.selected),
                            hovered=(i == hovered))

    def _draw_slot(self, surface, i, selected, hovered):
        c      = self.caster
        spell  = c.spells[i]
        rect   = self._slot_rect(i)
        accent = _accent(i)

        rem, cd  = 99, c._spell_cd[i]   # unlimited casts
        usable   = True
        is_major = c._is_major(i)
        # Only major spells are capped by the 2-major rule. Minors are never capped.
        capped   = (is_major and cd <= 0 and c.majors_on_cooldown >= MAX_MAJOR_ON_CD)

        # Slot frame: sprite by state (slot_empty / slot_selected / slot_hover / slot)
        if not usable:
            frame_key = "slot_empty"
        elif selected:
            frame_key = "slot_selected"
        elif hovered:
            frame_key = "slot_hover"
        else:
            frame_key = "slot"
        if not assets.draw(surface, frame_key, rect):
            if not usable:
                fill = (26, 23, 36)
            elif selected:
                fill = (62, 54, 88)
            elif hovered:
                fill = (48, 42, 68)
            else:
                fill = (34, 29, 48)
            pygame.draw.rect(surface, fill, rect, border_radius=3)
            if selected:
                border = accent
            elif hovered:
                border = (120, 110, 150)
            else:
                border = (52, 46, 74)
            pygame.draw.rect(surface, border, rect, 1, border_radius=3)

        # Darkened part shows the time still to wait
        if cd > 0:
            cd_max = max(SPELL_COOLDOWNS[i] if i < len(SPELL_COOLDOWNS) else 1.0, 0.001)
            veil_w = int(rect.w * _clamp01(cd / cd_max))
            dim_rect(surface, (rect.x, rect.y, veil_w, rect.h), 150, key="cooldown_veil")

        # Accent line along the bottom, dimmed when the spell is out of casts
        strip_col  = accent if usable else _dim(accent)
        strip_rect = pygame.Rect(rect.x + 4, rect.bottom - 3, rect.w - 8, 2)
        if not assets.draw(surface, "slot_accent", strip_rect, tint=strip_col):
            pygame.draw.rect(surface, strip_col, strip_rect, border_radius=1)

        # Majors carry a gold top line
        if is_major:
            gold_rect = pygame.Rect(rect.x + 3, rect.y, rect.w - 6, 1)
            if not assets.draw(surface, "slot_major", gold_rect):
                pygame.draw.rect(surface, GOLD, gold_rect)

        # Top row: hotkey on the left only (casts are unlimited, no badge needed)
        key = "0" if i == 9 else str(i + 1)
        fit_text(surface, key, pygame.Rect(rect.x + 2, rect.y + 2, 12, 7),
                 WHITE if selected else (150, 145, 175), max_size="tiny", align="left")

        # Lower row: cooldown seconds, CAP, the spell's icon, or its name
        name_box = pygame.Rect(rect.x + 2, rect.y + 9, rect.w - 4, 9)
        if cd > 0 or capped:
            label, col = (f"{cd:.1f}", (255, 220, 90)) if cd > 0 else ("CAP", (255, 140, 60))
            fit_text(surface, label, name_box, col, max_size="small")
        else:
            icon_box = pygame.Rect(rect.centerx - 5, rect.y + 9, 10, 9)
            icon_key = getattr(spell, 'icon', None)
            drawn = bool(icon_key) and assets.draw(surface, icon_key, icon_box,
                                                   alpha=255 if usable else 110)
            if not drawn:
                label = _label(i, spell)
                col   = (225, 222, 240) if usable else (95, 90, 110)
                fit_text(surface, label, name_box, col, max_size="small")

    # ------------------------------------------------------------------ game over
    def _draw_game_over(self, surface):
        runner_won = self.level.winner == "runner"
        if not assets.draw(surface, "gameover_panel", GAME_OVER_PANEL):
            pygame.draw.rect(surface, (15, 12, 25), GAME_OVER_PANEL, border_radius=8)
            pygame.draw.rect(surface, GOLD, GAME_OVER_PANEL, 2, border_radius=8)

        banner_key = "banner_runner" if runner_won else "banner_caster"
        if not assets.draw(surface, banner_key, GAME_OVER_TITLE):
            title = "RUNNER WINS!" if runner_won else "CASTER WINS!"
            fit_text(surface, title, GAME_OVER_TITLE, GOLD, max_size="title", shadow=True)

        who  = self.runner_player if runner_won else self.caster_player
        note = "reached the top" if runner_won else "stopped the runner"
        fit_text(surface, f"Player {who} {note}", GAME_OVER_SUB, (230, 230, 240), max_size="body")
        self.rematch.draw(surface)
        self.menu.draw(surface)