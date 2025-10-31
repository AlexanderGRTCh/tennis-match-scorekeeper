from __future__ import annotations

"""Rally animation planner and player.

Generates deterministic 2D trajectories for a single point based on the
precomputed winner and a terminal reason. Trajectory consists of straight-line
segments with optional bounces (within court) or collisions (net/out).

Provides `preview_trajectory(outcome)` for testing to verify terminal endpoint
matches the reason semantics.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Sequence
import random
import pygame

from .court import Court
from . import constants as C


Vec2 = Tuple[float, float]


@dataclass
class Segment:
    kind: str  # 'flight', 'bounce', 'net', 'out'
    start_px: Vec2
    end_px: Vec2
    duration_s: float
    striker_is_a: Optional[bool] = None  # who hit the ball for this segment


class RallyAnimator:
    def __init__(self, court: Court, seed: int | None = 0):
        """Build a simple planner and player for a single point.

        The seed is used only to keep visuals deterministic for replays.
        """
        self.court = court
        self.base_seed = seed
        # Default: 25% slower than baseline
        self.speed_multiplier = 0.75
        # Target total duration (seconds) for a planned point at 1.0x speed
        self.target_total_s = 2.0
        self._segments: List[Segment] = []
        self._elapsed = 0.0
        self._total = 0.0

    def set_speed_multiplier(self, mul: float):
        """Set a playback speed multiplier for the animation."""
        # Allow 0.25x to 5x range
        self.speed_multiplier = max(0.25, min(5.0, mul))

    def plan(
        self,
        point_idx: int,
        server_is_a: bool,
        side: str,
        winner: str,
        reason: str,
        serve_faults: int = 0,
        serve_fault_kinds: Sequence[str] | None = None,
    ) -> List[Segment]:
        """Plan a deterministic trajectory for a single point.

        This supports first and second serves with faults. A double fault ends the point early.
        """
        rng = random.Random() if self.base_seed is None else random.Random(self.base_seed * 10007 + point_idx * 7919)
        segs: List[Segment] = []

        # Serve geometry
        serve_pos_m, _ = self.court.serve_positions(server_is_a, side)
        cx = self.court.center_x_m
        sy_top, sy_bot = self.court.service_line_y_m
        net_y = self.court.net_y_m
        target_y = sy_bot - (sy_bot - net_y) * 0.6 if server_is_a else sy_top + (net_y - sy_top) * 0.6
        target_x = cx + (1 if side == "deuce" else -1) * (C.COURT_WIDTH_M * 0.15)

        start_px = self.court.to_px(*serve_pos_m)

        # Optional explicit serve faults from the engine
        fk = list(serve_fault_kinds or [])
        if serve_faults >= 1:
            kind = (fk[0] if fk else ("Net" if rng.random() < 0.5 else "Out"))
            if kind == "Net":
                end_px = self.court.to_px(target_x, net_y)
                segs.append(Segment("net", start_px, end_px, 0.35, striker_is_a=server_is_a))
            else:
                if rng.random() < 0.5:
                    out_y = (sy_bot + 1.0) if server_is_a else (sy_top - 1.0)
                    end_px = self.court.to_px(target_x, out_y)
                else:
                    out_x_m = -1.0 if rng.random() < 0.5 else C.COURT_WIDTH_M + 1.0
                    end_px = self.court.to_px(out_x_m, target_y)
                segs.append(Segment("out", start_px, end_px, 0.45, striker_is_a=server_is_a))
            if serve_faults >= 2:
                # Second fault ends the point
                if len(fk) >= 2:
                    kind2 = fk[1]
                else:
                    kind2 = "Net" if rng.random() < 0.5 else "Out"
                # Second attempt starts again from serve position
                if kind2 == "Net":
                    end2_px = self.court.to_px(target_x, net_y)
                    segs.append(Segment("net", start_px, end2_px, 0.35, striker_is_a=server_is_a))
                else:
                    if rng.random() < 0.5:
                        out_y = (sy_bot + 1.0) if server_is_a else (sy_top - 1.0)
                        end2_px = self.court.to_px(target_x, out_y)
                    else:
                        out_x_m = -1.0 if rng.random() < 0.5 else C.COURT_WIDTH_M + 1.0
                        end2_px = self.court.to_px(out_x_m, target_y)
                    segs.append(Segment("out", start_px, end2_px, 0.45, striker_is_a=server_is_a))
                self._segments = segs
                self._elapsed = 0.0
                self._total = sum(s.duration_s for s in segs)
                return segs
            # If the first was a single fault, show a brief pause before the second serve
            segs.append(Segment("pause", end_px, end_px, 0.4, striker_is_a=server_is_a))
            # After this the code continues to plan a legal serve in

        # Normal serve in
        serve_end_px = self.court.to_px(target_x, target_y)
        segs.append(Segment("flight", start_px, serve_end_px, 0.45, striker_is_a=server_is_a))

        # Rally exchanges (6–12 including serve)
        exchanges = rng.randint(6, 12)
        last_px = serve_end_px
        current_striker_is_a = not server_is_a  # receiver hits next
        for _ in range(exchanges - 1):
            frac_x = 0.3 + 0.4 * rng.random()
            x_m = cx + (frac_x - 0.5) * C.COURT_WIDTH_M
            # Alternate halves around net using striker side
            if current_striker_is_a:
                y_m = C.COURT_LENGTH_M * (0.25 - 0.2 * rng.random())
            else:
                y_m = C.COURT_LENGTH_M * (0.75 + 0.2 * rng.random())
            next_px = self.court.to_px(x_m, y_m)
            segs.append(Segment("flight", last_px, next_px, 0.18 + 0.05 * rng.random(), striker_is_a=current_striker_is_a))
            last_px = next_px
            current_striker_is_a = not current_striker_is_a

        # Terminal event
        last_m = self.court.from_px(last_px[0], last_px[1])
        winner_is_a = (winner == "A")
        if reason == "Net":
            end_px = self.court.to_px(last_m[0], net_y)
            segs.append(Segment("net", last_px, end_px, 0.22, striker_is_a=(not winner_is_a)))
        elif reason == "Out":
            # Opponent hits out toward winner's side. Make it clearly outside.
            outside_offset = 2.5  # meters beyond boundary to ensure visibility
            if rng.random() < 0.7:
                # Long beyond winner's baseline
                end_y_m = -outside_offset if winner_is_a else C.COURT_LENGTH_M + outside_offset
                end_x_m = max(0.35 * C.COURT_WIDTH_M, min(0.65 * C.COURT_WIDTH_M, last_m[0]))
                end_px = self.court.to_px(end_x_m, end_y_m)
            else:
                # Wide past sideline near winner's half depth
                end_x_m = -outside_offset if last_m[0] < cx else C.COURT_WIDTH_M + outside_offset
                base_y = net_y * 0.6 if winner_is_a else (net_y + (C.COURT_LENGTH_M - net_y) * 0.6)
                end_px = self.court.to_px(end_x_m, base_y)
            segs.append(Segment("out", last_px, end_px, 0.32, striker_is_a=(not winner_is_a)))
        else:  # Miss
            # Winner's shot passes receiver; bounce inside loser's court, then go long out
            outside_offset = 2.5
            loser_is_a = not winner_is_a
            # In-court bounce target near loser's baseline, clearly inside
            bounce_y_m = 1.5 if loser_is_a else (C.COURT_LENGTH_M - 1.5)
            bounce_x_m = cx + (rng.random() - 0.5) * (C.COURT_WIDTH_M * 0.5)
            bounce_px = self.court.to_px(bounce_x_m, bounce_y_m)
            segs.append(Segment("flight", last_px, bounce_px, 0.22, striker_is_a=winner_is_a))
            # Then clearly out beyond loser's baseline
            end_y_m = -outside_offset if loser_is_a else C.COURT_LENGTH_M + outside_offset
            end_x_m = cx + (rng.random() - 0.5) * (C.COURT_WIDTH_M * 0.25)
            end_px = self.court.to_px(end_x_m, end_y_m)
            segs.append(Segment("out", bounce_px, end_px, 0.20, striker_is_a=winner_is_a))

        # Normalize total duration to target (2s at 1.0x)
        total = sum(s.duration_s for s in segs)
        if total > 0:
            scale = self.target_total_s / total
            for s in segs:
                s.duration_s *= scale
        self._segments = segs
        self._elapsed = 0.0
        self._total = sum(s.duration_s for s in segs)
        return segs

    def preview_trajectory(self, outcome) -> List[Segment]:
        """Return a copy of the current planned segments for inspection."""
        return list(self._segments)

    def reset_playback(self):
        """Restart playback from the beginning of the plan."""
        self._elapsed = 0.0

    def update_and_draw(self, surf: pygame.Surface, dt: float, ball_drawer, actors_update=None) -> bool:
        """Advance time and draw the current ball position.

        The ball_drawer receives the position local progress and the segment.
        """
        if not self._segments:
            return False
        scaled_dt = dt * self.speed_multiplier
        self._elapsed += scaled_dt

        t = self._elapsed
        acc = 0.0
        for idx, seg in enumerate(self._segments):
            if t <= acc + seg.duration_s or seg is self._segments[-1]:
                local_t = max(0.0, min(1.0, (t - acc) / max(0.0001, seg.duration_s)))
                x = seg.start_px[0] + (seg.end_px[0] - seg.start_px[0]) * local_t
                y = seg.start_px[1] + (seg.end_px[1] - seg.start_px[1]) * local_t
                ball_drawer((x, y), local_t, seg)
                if actors_update is not None:
                    # Also pass local progress within this segment for hit effects
                    actors_update((x, y), idx, seg, scaled_dt, local_t)
                break
            acc += seg.duration_s

        finished = self._elapsed >= self._total
        return not finished

    # Plan caching helpers (pixel-space). For simple, exact replays within a session.
    def get_segments_px(self) -> List[Segment]:
        """Return a shallow copy of planned segments in pixel space."""
        return [Segment(s.kind, s.start_px, s.end_px, s.duration_s, s.striker_is_a) for s in self._segments]

    def load_segments_px(self, segments: List[Segment]) -> None:
        """Load a list of segments for exact replays in the same session."""
        # Deep copy style set to avoid external mutation
        self._segments = [Segment(s.kind, s.start_px, s.end_px, s.duration_s, s.striker_is_a) for s in segments]
        self._elapsed = 0.0
        self._total = sum(s.duration_s for s in self._segments)
