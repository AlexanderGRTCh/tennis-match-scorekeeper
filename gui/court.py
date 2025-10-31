from __future__ import annotations

"""Court geometry and drawing utilities.

The Court computes scaled rectangles/lines for a singles court using standard
dimensions. The logical court is in meters; drawing methods convert to pixels
with a consistent scale preserving aspect ratio.
"""

from dataclasses import dataclass
from typing import Tuple

import pygame

from . import constants as C


Vec2 = Tuple[float, float]


@dataclass
class CourtLayout:
    origin_px: Vec2  # top-left of court rect in window pixels
    scale: float  # pixels per meter
    size_px: Vec2  # width, height in pixels for court rect


class Court:
    def __init__(self, window_size: Tuple[int, int]):
        # This sets up a court model based on the current window size
        self.window_size = window_size
        self.layout: CourtLayout = self._compute_layout(window_size)

    def resize(self, window_size: Tuple[int, int]):
        # This recalculates the layout when the window changes
        self.window_size = window_size
        self.layout = self._compute_layout(window_size)

    def _compute_layout(self, window_size: Tuple[int, int]) -> CourtLayout:
        # This computes the pixel scale and where to place the court rectangle
        w, h = window_size
        pad = C.WINDOW_PADDING_PX
        avail_w = max(100, w - 2 * pad)
        avail_h = max(100, h - 2 * pad)

        court_w_m = C.COURT_WIDTH_M
        court_h_m = C.COURT_LENGTH_M

        # Horizontal orientation maps court length to screen width, and
        # court width to screen height.
        scale_w = avail_w / court_h_m
        scale_h = avail_h / court_w_m
        scale = min(scale_w, scale_h)

        # Width (px) spans court length; height (px) spans court width
        size_px = (court_h_m * scale, court_w_m * scale)
        origin_px = ((w - size_px[0]) / 2.0, (h - size_px[1]) / 2.0)
        return CourtLayout(origin_px=origin_px, scale=scale, size_px=size_px)

    # --- Coordinate transforms ---
    def to_px(self, x_m: float, y_m: float) -> Vec2:
        # Horizontal orientation: map court length (y_m) to screen X,
        # and court width (x_m) to screen Y, achieving left↔right play.
        ox, oy = self.layout.origin_px
        s = self.layout.scale
        return (ox + y_m * s, oy + x_m * s)

    def from_px(self, x_px: float, y_px: float) -> Vec2:
        # Inverse of to_px for horizontal orientation
        ox, oy = self.layout.origin_px
        s = self.layout.scale
        return ((y_px - oy) / s, (x_px - ox) / s)

    # Convenient home positions (baseline centers) in pixels for A (left side) and B (right side)
    def home_positions_px(self) -> Tuple[Vec2, Vec2]:
        # This returns the baseline center for both players in pixels
        a_px = self.to_px(self.center_x_m, 1.0)
        b_px = self.to_px(self.center_x_m, C.COURT_LENGTH_M - 1.0)
        return a_px, b_px

    # --- Key line positions in meters ---
    @property
    def court_rect_m(self) -> Tuple[float, float, float, float]:
        return (0.0, 0.0, C.COURT_WIDTH_M, C.COURT_LENGTH_M)

    @property
    def net_y_m(self) -> float:
        return C.NET_Y_FROM_TOP_M

    @property
    def baselines_y_m(self) -> Tuple[float, float]:
        return (0.0, C.COURT_LENGTH_M)

    @property
    def service_line_y_m(self) -> Tuple[float, float]:
        cy = C.NET_Y_FROM_TOP_M
        return (cy - C.SERVICE_LINE_FROM_NET_M, cy + C.SERVICE_LINE_FROM_NET_M)

    @property
    def center_x_m(self) -> float:
        return C.COURT_WIDTH_M / 2.0

    # --- Serve and player positions ---
    def serve_positions(self, server_is_a: bool, side: str) -> Tuple[Vec2, Vec2]:
        """Return server and receiver positions for a given side (diagonally across).

        This places the server behind their baseline on the correct deuce/ad half.
        The receiver is placed behind the opposite baseline in the diagonally
        opposite half so the serve flies into the highlighted box.
        """
        cx = self.center_x_m
        net_y = self.net_y_m
        sy_top, sy_bot = self.service_line_y_m

        # Compute the center of the legal service box (in meters)
        if server_is_a:
            target_y = 0.5 * (net_y + sy_bot)
        else:
            target_y = 0.5 * (sy_top + net_y)
        if side == "deuce":
            target_x = 0.5 * (cx + C.COURT_WIDTH_M)
        else:  # ad
            target_x = 0.5 * (0.0 + cx)

        # Mirror the x position across court center to get server half
        server_x = 2 * cx - target_x

        # Y positions behind respective baselines
        y_server = -2.0 if server_is_a else (C.COURT_LENGTH_M + 2.0)
        y_receiver = (C.COURT_LENGTH_M + 1.0) if server_is_a else -1.0

        server_pos = (server_x, y_server)
        receiver_pos = (target_x, y_receiver)
        return server_pos, receiver_pos

    def service_box_rect_px(self, server_is_a: bool, side: str) -> pygame.Rect:
        """Return a pygame.Rect for the legal service box in pixels.

        This is based on who serves and whether it is deuce or ad side.
        """
        sy_top, sy_bot = self.service_line_y_m
        net_y = self.net_y_m
        cx = self.center_x_m
        if server_is_a:
            y1, y2 = net_y, sy_bot
        else:
            y1, y2 = sy_top, net_y
        if side == "deuce":
            x1, x2 = cx, C.COURT_WIDTH_M
        else:
            x1, x2 = 0.0, cx
        p1 = self.to_px(x1, y1)
        p2 = self.to_px(x2, y2)
        left = min(p1[0], p2[0])
        top = min(p1[1], p2[1])
        w = abs(p2[0] - p1[0])
        h = abs(p2[1] - p1[1])
        return pygame.Rect(left, top, w, h)

    # --- Drawing ---
    def draw(self, surf: pygame.Surface):
        # Court background
        ox, oy = self.layout.origin_px
        w_px, h_px = self.layout.size_px
        pygame.draw.rect(surf, C.COURT_COLOR, pygame.Rect(ox, oy, w_px, h_px))

        # Lines
        def line_m(p1: Vec2, p2: Vec2, width: int = 2):
            pygame.draw.line(surf, C.LINE_COLOR, self.to_px(*p1), self.to_px(*p2), width)

        # Baselines and sidelines
        line_m((0.0, 0.0), (C.COURT_WIDTH_M, 0.0), 3)
        line_m((0.0, C.COURT_LENGTH_M), (C.COURT_WIDTH_M, C.COURT_LENGTH_M), 3)
        line_m((0.0, 0.0), (0.0, C.COURT_LENGTH_M), 3)
        line_m((C.COURT_WIDTH_M, 0.0), (C.COURT_WIDTH_M, C.COURT_LENGTH_M), 3)

        # Net (dark yellow)
        pygame.draw.line(
            surf,
            C.NET_COLOR,
            self.to_px(0.0, self.net_y_m),
            self.to_px(C.COURT_WIDTH_M, self.net_y_m),
            3,
        )

        # Service lines (from net toward baselines)
        sy_top, sy_bot = self.service_line_y_m
        line_m((0.0, sy_top), (C.COURT_WIDTH_M, sy_top), 2)
        line_m((0.0, sy_bot), (C.COURT_WIDTH_M, sy_bot), 2)

        # Center service line
        line_m((self.center_x_m, sy_top), (self.center_x_m, sy_bot), 2)

        # Optional small center marks on baselines
        cm = C.CENTER_MARK_M
        line_m((self.center_x_m - cm / 2, 0.0), (self.center_x_m + cm / 2, 0.0), 2)
        line_m(
            (self.center_x_m - cm / 2, C.COURT_LENGTH_M),
            (self.center_x_m + cm / 2, C.COURT_LENGTH_M),
            2,
        )
