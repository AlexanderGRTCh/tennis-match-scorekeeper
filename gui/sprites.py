from __future__ import annotations

"""Simple drawable sprites for players and ball.

These are lightweight classes with explicit draw/update; no dependency on
pygame.sprite groups to keep things simple and efficient.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import pygame

from . import constants as C


Vec2 = Tuple[float, float]


@dataclass
class PlayerSprite:
    color: Tuple[int, int, int]
    radius_px: int
    pos_px: Vec2
    outline: Tuple[int, int, int] = (240, 240, 240)
    last_px: Optional[Vec2] = None

    def move_to(self, pos_px: Vec2):
        # This sets the player position immediately
        self.last_px = pos_px
        self.pos_px = pos_px

    def move_towards(self, target_px: Vec2, max_step: float):
        # This moves the player toward a target by at most a fixed step
        x, y = self.pos_px
        tx, ty = target_px
        dx = tx - x
        dy = ty - y
        dist2 = dx*dx + dy*dy
        if dist2 <= 0.0001:
            return
        import math
        dist = math.sqrt(dist2)
        if dist <= max_step:
            new_pos = (tx, ty)
        else:
            new_pos = (x + dx/dist*max_step, y + dy/dist*max_step)
        self.last_px = self.pos_px
        self.pos_px = new_pos

    def draw(self, surf: pygame.Surface):
        # Draw a simple static line-figure human scaled by radius_px
        x = int(self.pos_px[0])
        y = int(self.pos_px[1])
        r = self.radius_px
        # Head
        head_r = max(3, int(r * 0.6))
        pygame.draw.circle(surf, self.outline, (x, y), head_r + 1)
        pygame.draw.circle(surf, self.color, (x, y), head_r, 1)
        # Torso
        torso_len = max(6, int(r * 1.8))
        hip_y = y + head_r + torso_len
        pygame.draw.line(surf, self.color, (x, y + head_r), (x, hip_y), 2)
        # Arms static
        arm_len = max(6, int(r * 1.3))
        arm_y = y + head_r + max(2, int(torso_len * 0.3))
        ax = int(arm_len * 0.6)
        pygame.draw.line(surf, self.color, (x, arm_y), (x - ax, arm_y), 2)
        pygame.draw.line(surf, self.color, (x, arm_y), (x + ax, arm_y), 2)
        # Legs static
        leg_len = max(6, int(r * 1.5))
        spread = max(2, int(r * 0.5))
        lw = 2
        lx = x - spread
        rx = x + spread
        pygame.draw.line(surf, self.color, (x, hip_y), (lx, hip_y + leg_len), lw)
        pygame.draw.line(surf, self.color, (x, hip_y), (rx, hip_y + leg_len), lw)


@dataclass
class BallSprite:
    radius_px: int
    pos_px: Vec2

    def move_to(self, pos_px: Vec2):
        # This updates the ball location for the current frame
        self.pos_px = pos_px

    def draw(self, surf: pygame.Surface):
        # This draws a soft shadow then the ball itself
        x = int(self.pos_px[0])
        y = int(self.pos_px[1])
        shadow_rect = pygame.Rect(0, 0, self.radius_px * 2, int(self.radius_px * 1.2))
        shadow_rect.center = (x + 2, y + 3)
        shadow_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 80), shadow_surf.get_rect())
        surf.blit(shadow_surf, shadow_rect.topleft)
        pygame.draw.circle(surf, C.BALL_COLOR, (x, y), self.radius_px)


@dataclass
class UmpireChairSprite:
    """Simple chair umpire tower sprite drawn outside the court at the net.

    Coordinates are specified in court meters. Drawing sizes scale with court layout.
    """
    x_m: float
    y_m: float
    color: Tuple[int, int, int] = (245, 245, 245)

    def draw(self, surf: pygame.Surface, court) -> None:
        # Compute anchor in pixels using court transform
        px_per_m = court.layout.scale
        cx, cy = court.to_px(self.x_m, self.y_m)

        # Tower dimensions relative to scale
        tower_h = int(px_per_m * 2.0)
        tower_w = max(2, int(px_per_m * 0.18))
        seat_h = max(2, int(px_per_m * 0.18))
        seat_w = int(px_per_m * 0.5)
        leg_w = max(1, int(px_per_m * 0.06))
        step_gap = max(3, int(px_per_m * 0.18))

        # Base position: cx,cy is along the net line; draw tower upward (toward top of screen)
        base_y = int(cy)
        top_y = base_y - tower_h
        center_x = int(cx)

        # Legs
        leg_left = pygame.Rect(center_x - seat_w // 2, top_y, leg_w, tower_h)
        leg_right = pygame.Rect(center_x + seat_w // 2 - leg_w, top_y, leg_w, tower_h)
        pygame.draw.rect(surf, self.color, leg_left)
        pygame.draw.rect(surf, self.color, leg_right)

        # Steps (ladder rungs)
        y = top_y + step_gap
        while y < base_y - step_gap // 2:
            pygame.draw.line(surf, self.color, (leg_left.right, y), (leg_right.left, y), 2)
            y += step_gap

        # Seat platform
        seat_rect = pygame.Rect(center_x - seat_w // 2, top_y - seat_h // 2, seat_w, seat_h)
        pygame.draw.rect(surf, self.color, seat_rect)

        # Backrest
        back_h = int(seat_h * 1.6)
        back_rect = pygame.Rect(seat_rect.left, seat_rect.top - back_h, seat_w, 2)
        pygame.draw.rect(surf, self.color, back_rect)

        # Mini human: head and torso
        head_r = max(2, int(px_per_m * 0.10))
        head_x = center_x
        head_y = seat_rect.top - head_r - 2
        pygame.draw.circle(surf, self.color, (head_x, head_y), head_r, 1)
        # Torso
        torso_len = max(4, int(px_per_m * 0.35))
        pygame.draw.line(surf, self.color, (head_x, head_y + head_r), (head_x, head_y + head_r + torso_len), 2)
        # Arms
        arm_span = int(px_per_m * 0.35)
        arm_y = head_y + head_r + int(torso_len * 0.3)
        pygame.draw.line(surf, self.color, (head_x - arm_span // 2, arm_y), (head_x + arm_span // 2, arm_y), 2)
        # Legs (short since seated)
        leg_len = max(3, int(px_per_m * 0.25))
        hip_y = head_y + head_r + torso_len
        pygame.draw.line(surf, self.color, (head_x, hip_y), (head_x - arm_span // 4, hip_y + leg_len), 2)
        pygame.draw.line(surf, self.color, (head_x, hip_y), (head_x + arm_span // 4, hip_y + leg_len), 2)
