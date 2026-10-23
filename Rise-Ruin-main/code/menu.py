"""Main menu: each player picks Runner or Caster (the other player gets the opposite role).

Layout grid (window is 480 x 270):
  side margins 16 px, top margin 12 px, bottom margin 18 px
  two player panels of 216 x 116 px with a 16 px gap between them
  every label is fitted inside its own box (see ui.fit_text)

Sprites used: menu_bg, title, menu_panel, button (+ button_hover and button_selected).
"""
from settings import *
from ui import Button, draw_panel, fit_text
import assets
import sounds

ROLES    = ("runner", "caster")
CONTROLS = {
    "runner": ["A / D  -  move", "SPACE  -  jump", "Q  -  super jump", "S or SHIFT  -  shield", "Reach the top alive!"],
    "caster": ["MOUSE ONLY", "Click a spell, then click to cast", f"Up to {MAX_SPELLS} spells total",
               "Stop the runner!"],
}

MARGIN_X    = 16
GAP         = 16
PANEL_W     = (WINDOW_WIDTH - 2 * MARGIN_X - GAP) // 2          # 216
PANEL_X     = {1: MARGIN_X, 2: MARGIN_X + PANEL_W + GAP}
PANEL_Y, PANEL_H = 80, 116
PAD         = 10                                                 # inside a panel
BTN_W, BTN_H = (PANEL_W - 2 * PAD - 8) // 2, 20                  # two role buttons per panel
LINE_Y0, LINE_H = 52, 12                                         # control lines inside a panel

TITLE_RECT = pygame.Rect((WINDOW_WIDTH - 240) // 2, 12, 240, 26)
START_RECT = pygame.Rect((WINDOW_WIDTH - 140) // 2, 204, 140, 22)
QUIT_RECT  = pygame.Rect((WINDOW_WIDTH - 60) // 2, 234, 60, 18)
DIVIDER_Y  = 70


class MenuScene:
    def __init__(self, game):
        self.game = game
        pygame.mouse.set_visible(True)
        self.roles = {1: "runner", 2: "caster"}
        self.role_buttons = {}
        for player, x in PANEL_X.items():
            for i, role in enumerate(ROLES):
                rect = (x + PAD + i * (BTN_W + 8), PANEL_Y + 26, BTN_W, BTN_H)
                self.role_buttons[(player, role)] = Button(rect, role.upper(), "body")
        self.start = Button(START_RECT, "START GAME", "body")
        self.quit  = Button(QUIT_RECT, "QUIT", "small")

    def handle_event(self, event):
        for (player, role), button in self.role_buttons.items():
            if button.clicked(event):
                sounds.play("ui_button_click")
                self.roles[player] = role
                self.roles[3 - player] = "caster" if role == "runner" else "runner"
        if self.start.clicked(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
            sounds.play("ui_button_click")
            self.game.start_match(dict(self.roles))
        elif self.quit.clicked(event):
            sounds.play("ui_button_click")
            self.game.quit()

    def update(self, dt):
        pass

    def draw(self, surface):
        if not assets.draw(surface, "menu_bg", surface.get_rect()):
            surface.fill(COLORS["bg"])

        # Header
        if not assets.draw(surface, "title", TITLE_RECT):
            fit_text(surface, "CASTLE CLIMB", TITLE_RECT, (255, 215, 0), max_size="title", shadow=True)
        fit_text(surface, "Runner  vs  Caster", pygame.Rect(MARGIN_X, 40, WINDOW_WIDTH - 2 * MARGIN_X, 12),
                 (200, 200, 220), max_size="body")
        fit_text(surface, f"Map:  {LEVELS[0][0]}", pygame.Rect(MARGIN_X, 53, WINDOW_WIDTH - 2 * MARGIN_X, 11),
                 (170, 220, 170), max_size="small")
        pygame.draw.line(surface, (58, 52, 80), (MARGIN_X, DIVIDER_Y), (WINDOW_WIDTH - MARGIN_X - 1, DIVIDER_Y))

        # Player panels
        for player, x in PANEL_X.items():
            draw_panel(surface, (x, PANEL_Y, PANEL_W, PANEL_H),
                       color=(38, 34, 54), alpha=255, radius=6,
                       border=(120, 120, 160), key="menu_panel")
            fit_text(surface, f"PLAYER {player}", pygame.Rect(x + PAD, PANEL_Y + 6, PANEL_W - 2 * PAD, 14),
                     (255, 255, 255), max_size="heading")
            for role in ROLES:
                button = self.role_buttons[(player, role)]
                button.selected = self.roles[player] == role
                button.draw(surface)
            for i, line in enumerate(CONTROLS[self.roles[player]]):
                fit_text(surface, line,
                         pygame.Rect(x + PAD, PANEL_Y + LINE_Y0 + i * LINE_H, PANEL_W - 2 * PAD, LINE_H - 1),
                         (210, 210, 225), max_size="small")

        self.start.draw(surface)
        self.quit.draw(surface)