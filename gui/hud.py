from __future__ import annotations

"""HUD for match info: players, scores, bias, and hints."""

from dataclasses import dataclass
from typing import Tuple
import pygame

from . import constants as C


@dataclass
class HUDState:
    name_a: str = "A"
    name_b: str = "B"
    best_of: int = 3
    game_text: str = "Love to Love"
    games: Tuple[int, int] = (0, 0)
    sets: Tuple[int, int] = (0, 0)
    bias: int = 50
    speed_mult: float = 0.75
    hint: str = "Space: next | R: replay | S: speed | Esc: quit"
    match_over: bool = False
    match_winner_name: str | None = None
    last_point: str = ""


class HUD:
    def __init__(self, surf: pygame.Surface):
        # This sets up fonts and a small state object for drawing
        self.surf = surf
        self.font = pygame.font.SysFont("arial", 20)
        self.font_small = pygame.font.SysFont("arial", 16)
        self.state = HUDState()

    def update(self, **kwargs):
        # This updates values that the HUD will present
        for k, v in kwargs.items():
            if hasattr(self.state, k):
                setattr(self.state, k, v)

    def draw(self):
        # This renders several text lines and a small bias bar
        pad = 10
        lines = []
        lines.append(f"{self.state.name_a} vs {self.state.name_b} | best of {self.state.best_of}")
        if self.state.match_over and self.state.match_winner_name:
            lines.append(f"Winner: {self.state.match_winner_name}")
        gt = str(self.state.game_text).replace(" - ", " to ")
        lines.append(f"Game: {gt}")
        if self.state.last_point:
            lines.append(self.state.last_point)
        lines.append(f"Set games: {self.state.name_a} {self.state.games[0]} to {self.state.games[1]} {self.state.name_b}")
        lines.append(f"Match sets: {self.state.name_a} {self.state.sets[0]} to {self.state.sets[1]} {self.state.name_b}")
        lines.append(f"Bias: {self.state.bias}")
        lines.append(f"Speed: x{self.state.speed_mult:.2f}")
        lines.append(self.state.hint)

        x = 10
        y = 10
        for i, text in enumerate(lines):
            font = self.font_small if i >= 3 else self.font
            img = font.render(text, True, C.HUD_TEXT_COLOR)
            bg = pygame.Surface((img.get_width() + pad, img.get_height() + pad), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 120))
            self.surf.blit(bg, (x - 5, y - 4))
            self.surf.blit(img, (x, y))
            y += img.get_height() + 6

        # Draw a mini bias bar showing A (left) vs B (right)
        # Interpret bias as probability percent for B (right) winning a point.
        bar_w = 220
        bar_h = 10
        bar_x = x
        bar_y = y + 4
        # Background
        pygame.draw.rect(self.surf, (30, 30, 30), pygame.Rect(bar_x, bar_y, bar_w, bar_h))
        # Split fill according to bias
        bias = max(0, min(100, int(self.state.bias)))
        left_w = int(round(bar_w * (100 - bias) / 100.0))
        right_w = bar_w - left_w
        if left_w > 0:
            pygame.draw.rect(self.surf, C.PLAYER_A_COLOR, pygame.Rect(bar_x, bar_y, left_w, bar_h))
        if right_w > 0:
            pygame.draw.rect(self.surf, C.PLAYER_B_COLOR, pygame.Rect(bar_x + left_w, bar_y, right_w, bar_h))
        # Border and center line
        pygame.draw.rect(self.surf, (220, 220, 220), pygame.Rect(bar_x, bar_y, bar_w, bar_h), 1)
        mid_x = bar_x + bar_w // 2
        pygame.draw.line(self.surf, (200, 200, 200), (mid_x, bar_y), (mid_x, bar_y + bar_h), 1)
        # End labels A | B
        la = self.font_small.render(self.state.name_a, True, C.HUD_TEXT_COLOR)
        lb = self.font_small.render(self.state.name_b, True, C.HUD_TEXT_COLOR)
        self.surf.blit(la, (bar_x, bar_y + bar_h + 2))
        self.surf.blit(lb, (bar_x + bar_w - lb.get_width(), bar_y + bar_h + 2))
