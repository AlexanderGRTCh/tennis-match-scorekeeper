from __future__ import annotations

"""Pygame App for the Tennis Match Simulator.

Run with: `python -m gui.app`.

Controls:
  - Space/Click: next point
  - R: replay current point
  - S: toggle speed (shows current multiplier)
  - Q/Esc: quit
"""

import argparse
import sys
from typing import Optional

try:
    import pygame
except Exception as e:  # pragma: no cover - runtime dependency hint
    print("Pygame is required for GUI. Install via: pip install pygame", file=sys.stderr)
    raise

from tennis.engine import MatchConfig
from model.adapter import PointStream, PointOutcome

from . import constants as C
from .court import Court
from .sprites import PlayerSprite, BallSprite, UmpireChairSprite
from .animator import RallyAnimator
from .hud import HUD


def parse_args(argv=None):
    """Parse command line flags for the GUI app.

    This keeps values simple and safe for window size and performance.
    """
    p = argparse.ArgumentParser(description="Tennis GUI (Pygame)")
    p.add_argument("--player-a", default=None)
    p.add_argument("--player-b", default=None)
    p.add_argument("--sets", type=int, choices=[3, 5], default=None)
    p.add_argument("--bias", type=int, default=None)
    p.add_argument("--seed", type=int, default=None, help="Deterministic seed (optional)")
    p.add_argument("--no-prompt", action="store_true", help="Skip GUI prompt and use provided flags")
    p.add_argument("--width", type=int, default=C.DEFAULT_WINDOW[0])
    p.add_argument("--height", type=int, default=C.DEFAULT_WINDOW[1])
    p.add_argument("--fps", type=int, default=C.TARGET_FPS)
    return p.parse_args(argv)


def run(argv=None) -> int:
    """Run the pygame based tennis viewer.

    This sets up the window sprites animator and HUD then loops until exit.
    """
    args = parse_args(argv)

    def is_valid_name(s: str) -> bool:
        """Return True if a name has letters and spaces only."""
        import re
        s = (s or "").strip()
        return bool(s) and re.fullmatch(r"[A-Za-z ]+", s) is not None

    def is_valid_sets(v: Optional[int]) -> bool:
        """Return True if the best of value is three or five."""
        return v in (3, 5)

    def is_valid_bias(v: Optional[int]) -> bool:
        """Return True if the bias is within zero to one hundred."""
        return isinstance(v, int) and 0 <= v <= 100

    pygame.init()
    pygame.display.set_caption("Tennis Match Simulator - GUI")
    flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    try:
        screen = pygame.display.set_mode((args.width, args.height), flags, vsync=1)
    except TypeError:
        screen = pygame.display.set_mode((args.width, args.height), flags)
    clock = pygame.time.Clock()

    court = Court(screen.get_size())
    hud = HUD(screen)

    # Prepare sprites (positions set during animation planning)
    # Sprite radii scale with pixels-per-meter
    px_per_m = court.layout.scale
    player_radius = max(8, int(px_per_m * 0.22))
    ball_radius = max(3, int(px_per_m * 0.08))
    player_a = PlayerSprite(C.PLAYER_A_COLOR, player_radius, court.to_px(C.COURT_WIDTH_M / 2, -1))
    player_b = PlayerSprite(C.PLAYER_B_COLOR, player_radius, court.to_px(C.COURT_WIDTH_M / 2, C.COURT_LENGTH_M + 1))
    home_a_px, home_b_px = court.home_positions_px()
    ball = BallSprite(ball_radius, court.to_px(C.COURT_WIDTH_M / 2, C.NET_Y_FROM_TOP_M))
    ball_base_radius = ball_radius

    # Chair umpire just outside top of the court at the net
    umpire = UmpireChairSprite(x_m=-0.8, y_m=C.NET_Y_FROM_TOP_M)

    animator = RallyAnimator(court, seed=args.seed)
    # Default to 0.25x per request (slow motion by default)
    speed_idx = C.SPEED_STEPS.index(0.25) if 0.25 in C.SPEED_STEPS else 0
    hud.update(speed_mult=C.SPEED_STEPS[speed_idx])

    # Prompt for configuration unless flags provided and --no-prompt
    cfg: Optional[MatchConfig] = None
    stream = None
    current_outcome: Optional[PointOutcome] = None
    point_counter = 0

    def draw_prompt(fields, active_idx):
        """Draw a simple full screen prompt for match setup."""
        # Solid black background to avoid overlay with HUD/court
        screen.fill((0, 0, 0))
        title_font = pygame.font.SysFont("arial", 28)
        font = pygame.font.SysFont("arial", 22)
        y = 80
        title = title_font.render("Enter Match Setup", True, C.HUD_TEXT_COLOR)
        screen.blit(title, ((screen.get_width() - title.get_width()) // 2, y))
        y += 50
        labels = [
            ("Player A:", fields[0]),
            ("Player B:", fields[1]),
            ("Sets (3 or 5):", fields[2]),
            ("Starting Bias (0..100):", fields[3]),
        ]
        x = 80
        for i, (lab, val) in enumerate(labels):
            txt = f"{lab} {val}"
            img = font.render(txt, True, (255, 255, 255) if i == active_idx else C.HUD_TEXT_COLOR)
            screen.blit(img, (x, y))
            y += img.get_height() + 18
        hint = pygame.font.SysFont("arial", 18).render("Enter to confirm field, Tab to next, Esc to quit", True, C.HUD_TEXT_COLOR)
        screen.blit(hint, (x, y + 8))
        pygame.display.flip()

    def run_prompt():
        """Handle the interactive prompt for match configuration."""
        nonlocal cfg
        fields = [args.player_a or "", args.player_b or "", str(args.sets or 3), str(args.bias or 50)]
        active = 0
        while True:
            draw_prompt(fields, active)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        return False
                    if event.key == pygame.K_TAB:
                        active = (active + 1) % 4
                        break
                    if event.key == pygame.K_RETURN:
                        if active < 3:
                            active += 1
                        else:
                            name_a, name_b, sets_s, bias_s = fields
                            try:
                                sets_v = int(sets_s)
                                bias_v = int(bias_s)
                            except Exception:
                                break
                            if not (is_valid_name(name_a) and is_valid_name(name_b)):
                                break
                            if not is_valid_sets(sets_v) or not is_valid_bias(bias_v):
                                break
                            cfg = MatchConfig(
                                player_a=name_a.strip(),
                                player_b=name_b.strip(),
                                max_sets=sets_v,
                                starting_bias=bias_v,
                                seed=None,
                            )
                            return True
                        break
                    if event.key == pygame.K_BACKSPACE:
                        if fields[active]:
                            fields[active] = fields[active][:-1]
                        break
                    ch = event.unicode
                    if active in (0, 1):
                        if ch.isalpha() or ch == " ":
                            fields[active] += ch
                    elif active == 2:
                        if ch.isdigit() and len(fields[active]) < 1:
                            fields[active] += ch
                    else:
                        if ch.isdigit() and len(fields[active]) < 3:
                            fields[active] += ch
            pygame.time.delay(10)

    if not args.no_prompt:
        ok = run_prompt()
        if not ok:
            pygame.quit()
            return 0
    else:
        # Validate flags; fallback to defaults if invalid/empty
        raw_a = (args.player_a or "").strip()
        raw_b = (args.player_b or "").strip()
        name_a = raw_a if is_valid_name(raw_a) else "Player A"
        name_b = raw_b if is_valid_name(raw_b) else "Player B"
        sets_v = args.sets or 3
        bias_v = args.bias if args.bias is not None else 50
        cfg = MatchConfig(
            player_a=name_a,
            player_b=name_b,
            max_sets=sets_v,
            starting_bias=bias_v,
            seed=args.seed,
        )

    # Update HUD with chosen names/settings
    hud.update(name_a=cfg.player_a, name_b=cfg.player_b, best_of=cfg.max_sets)

    # Prepare model point stream now that cfg is set
    stream = PointStream(cfg)

    # Ball trail storage
    ball_trail: list[tuple[float, float]] = []

    def draw_everything():
        """Draw court, players, trail, ball, and HUD (no flip here)."""
        screen.fill((10, 18, 24))
        court.draw(screen)
        # Draw chair umpire tower (static)
        try:
            umpire.draw(screen, court)
        except Exception:
            pass
        # Subtle vignette shading around the court to add depth using a translucent overlay
        try:
            steps = 10
            max_alpha = 60
            w, h = screen.get_size()
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(steps):
                a = int(max_alpha * (i + 1) / steps)
                t = max(2, int(min(w, h) * 0.01))
                inset = i * t
                rect = pygame.Rect(inset, inset, w - inset * 2, h - inset * 2)
                pygame.draw.rect(overlay, (0, 0, 0, a), rect, width=t)
            screen.blit(overlay, (0, 0))
        except Exception:
            pass
        # Draw service box highlight during serve preparation and early flight
        if current_outcome is not None:
            try:
                rect = court.service_box_rect_px(current_server_is_a, current_outcome.side)
                shade = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                shade.fill((255, 255, 255, 30))
                screen.blit(shade, (rect.left, rect.top))
            except Exception:
                pass
        player_a.draw(screen)
        player_b.draw(screen)
        # Draw a simple fading ball trail
        if ball_trail:
            steps = len(ball_trail)
            for i, (tx, ty) in enumerate(ball_trail):
                alpha = int(160 * (i + 1) / steps)
                r = max(1, int(ball_base_radius * (i + 1) / steps))
                dot = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(dot, (255, 255, 255, alpha // 3), (r, r), r)
                screen.blit(dot, (int(tx) - r, int(ty) - r))
        ball.draw(screen)
        hud.draw()

    current_server_is_a = False
    last_outcome: Optional[PointOutcome] = None
    # Track indices and cached plans/outcomes for exact replays
    current_point_index: Optional[int] = None
    last_point_index: Optional[int] = None
    plan_cache: dict[int, list] = {}
    outcome_cache: dict[int, PointOutcome] = {}

    def plan_for_outcome(outcome: PointOutcome, plan_index: Optional[int] = None):
        """Place players and plan the rally animation for the next point."""
        # Set speed
        animator.set_speed_multiplier(C.SPEED_STEPS[speed_idx])
        # Place players near serve/return positions for this point
        nonlocal current_server_is_a
        current_server_is_a = outcome.server == "A"
        serve_pos_m, recv_pos_m = court.serve_positions(current_server_is_a, outcome.side)
        player_a.move_to(court.to_px(*serve_pos_m if current_server_is_a else recv_pos_m))
        player_b.move_to(court.to_px(*recv_pos_m if current_server_is_a else serve_pos_m))
        # Reset per-point visual effects so contact markers and trails reinitialize
        # like a fresh rally. This fixes the issue where hit markers only appeared
        # on the first point because indices were reused across points.
        nonlocal hit_markers, hit_indices_seen, ball_trail
        hit_markers = []
        hit_indices_seen.clear()
        ball_trail = []
        # Plan animation
        idx = plan_index if plan_index is not None else point_counter
        animator.plan(
            idx,
            current_server_is_a,
            outcome.side,
            outcome.winner,
            outcome.reason,
            serve_faults=getattr(outcome, "serve_faults", 0),
            serve_fault_kinds=getattr(outcome, "serve_fault_kinds", ()),
        )
        # Cache pixel-space plan and outcome for exact replay later
        try:
            plan_cache[idx] = animator.get_segments_px()
            outcome_cache[idx] = outcome
        except Exception:
            pass

    running = True
    playing_anim = False
    # Advance control: only fetch/play next point when user requests
    advance_requested = False
    # Poll-based edge detection for Space (in case KEYDOWN is missed on some systems)
    space_held = False
    # Terminal overlay (e.g., OUT / MISS / NET)
    overlay_pos = None
    overlay_text = None
    overlay_color = (255, 255, 255)
    overlay_timer = 0.0
    # First-serve fault banner (simple center-bottom banner replacing old approach)
    fault_banner_text: Optional[str] = None
    fault_banner_timer: float = 0.0

    target_aspect = (args.width / args.height) if args.height else (C.DEFAULT_WINDOW[0] / C.DEFAULT_WINDOW[1])

    # Hit markers for racket contact flashes
    hit_markers: list[tuple[tuple[float, float], tuple[int,int,int], float]] = []  # (pos, color, ttl)
    hit_indices_seen: set[int] = set()
    # Bounce effect timer (doubles ball size briefly on floor hit)
    ball_bounce_timer = 0.0

    while running:
        dt = clock.tick(args.fps) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                # Enforce constant aspect ratio
                cur_w, cur_h = screen.get_size()
                dw = abs(event.w - cur_w)
                dh = abs(event.h - cur_h)
                if dw >= dh:
                    new_w = max(320, event.w)
                    new_h = int(round(new_w / target_aspect))
                else:
                    new_h = max(240, event.h)
                    new_w = int(round(new_h * target_aspect))
                try:
                    screen = pygame.display.set_mode((new_w, new_h), flags, vsync=1)
                except TypeError:
                    screen = pygame.display.set_mode((new_w, new_h), flags)
                court.resize((new_w, new_h))
                # Recompute sprite sizes
                px_per_m = court.layout.scale
                pr = max(8, int(px_per_m * 0.22))
                br = max(3, int(px_per_m * 0.08))
                player_a.radius_px = pr
                player_b.radius_px = pr
                ball.radius_px = br
                ball_base_radius = br
                home_a_px, home_b_px = court.home_positions_px()
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    advance_requested = True
                elif event.key == pygame.K_r:
                    # Always replay the previously completed point using its original index
                    if last_point_index is not None and (last_point_index in plan_cache):
                        # Load cached plan for exact same replay
                        animator.load_segments_px(plan_cache[last_point_index])
                        current_outcome = outcome_cache.get(last_point_index, last_outcome)
                        current_point_index = last_point_index
                        animator.reset_playback()
                        playing_anim = True
                elif event.key == pygame.K_s:
                    speed_idx = (speed_idx + 1) % len(C.SPEED_STEPS)
                    mul = C.SPEED_STEPS[speed_idx]
                    animator.set_speed_multiplier(mul)
                    hud.update(speed_mult=mul)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                advance_requested = True

        # Also poll for Space edge if the window has focus
        try:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_SPACE] and not space_held:
                advance_requested = True
                space_held = True
            elif not keys[pygame.K_SPACE]:
                space_held = False
        except Exception:
            pass

        # Only advance or fetch next when the user requests it
        if advance_requested:
            advance_requested = False
            if not hud.state.match_over:
                if current_outcome is None:
                    try:
                        current_outcome = next(stream)
                        point_counter += 1
                        # Update HUD to reflect model state after this point
                        hud.update(
                            game_text=current_outcome.game_text,
                            games=current_outcome.games,
                            sets=current_outcome.sets,
                            bias=current_outcome.bias,
                            match_over=current_outcome.match_over,
                            match_winner_name=current_outcome.match_winner_name,
                        )
                        current_point_index = point_counter
                        plan_for_outcome(current_outcome, current_point_index)
                        animator.reset_playback()
                        playing_anim = True
                        # do not update last_outcome or last_point until animation completes
                    except StopIteration:
                        hud.update(match_over=True, match_winner_name=hud.state.match_winner_name)
                else:
                    # A point is prepared; start playback on request
                    if not playing_anim:
                        animator.reset_playback()
                        playing_anim = True

        # Animate if requested
        if playing_anim and current_outcome is not None:
            # Track previous segment kind to label first-serve faults accurately
            prev_seg_kind = None

            def draw_ball_at(pos_px, local_t, seg):
                """Update the ball position and add a slight arc scale.

                This makes the ball look a bit larger at the top of flight.
                """
                nonlocal overlay_text, overlay_color, overlay_timer, overlay_pos, prev_seg_kind, fault_banner_text, fault_banner_timer
                ball.move_to(pos_px)
                if seg.kind in ("flight", "out"):
                    # Simple parabola for apparent height
                    h = 4.0 * local_t * (1.0 - local_t)
                    ball.radius_px = max(ball_base_radius, int(ball_base_radius * (1.0 + 0.4 * h)))
                else:
                    ball.radius_px = ball_base_radius
                # Update trail
                ball_trail.append(pos_px)
                if len(ball_trail) > 24:
                    del ball_trail[0]
                                                # Remember segment kind for next frame (to detect pause after a fault)\n                # New simple first-serve fault banner: when a 'pause' segment follows a\n                # fault, show a large banner under the court (no per-ball overlays).\n                if getattr(seg, 'kind', None) == 'pause':\n                    if prev_seg_kind in ('net', 'out'):\n                        fault_banner_text = 'SECOND SERVE' if prev_seg_kind == 'net' else 'SECOND SERVE'\n                        fault_banner_timer = 1.2\n                prev_seg_kind = getattr(seg, 'kind', None)\n
            def move_players(ball_pos, seg_index, seg, scaled_dt, local_t):
                # Determine roles from segment attribution if available
                striker_is_a = getattr(seg, 'striker_is_a', None)
                if striker_is_a is None:
                    striker_is_a = current_server_is_a if (seg_index % 2 == 0) else (not current_server_is_a)
                receiver_is_a = not striker_is_a
                step_px = C.PLAYER_SPEED_MPS * court.layout.scale * (scaled_dt)
                # Receiver chases the live ball. For terminal OUT by loser, give up early.
                recv_step = step_px
                if seg.kind == 'out':
                    winner_is_a = (current_outcome.winner == 'A')
                    is_miss_terminal = (striker_is_a == winner_is_a)
                    is_out_by_loser = not is_miss_terminal
                    if is_out_by_loser:
                        # Slow immediately; stop after 20% of segment
                        if local_t > 0.2:
                            recv_step = 0.0
                        else:
                            recv_step *= 0.4
                if receiver_is_a:
                    player_a.move_towards(ball_pos, recv_step)
                else:
                    player_b.move_towards(ball_pos, recv_step)
                # Striker recovers toward their home baseline center
                if striker_is_a:
                    player_a.move_towards(home_a_px, step_px * 0.8)
                else:
                    player_b.move_towards(home_b_px, step_px * 0.8)

                # Add a small racket/contact hint at the start of each relevant segment
                if seg.kind in ('flight','out','net') and local_t < 0.05 and seg_index not in hit_indices_seen:
                    color = C.PLAYER_A_COLOR if striker_is_a else C.PLAYER_B_COLOR
                    hit_markers.append((seg.start_px, color, 0.40))
                    hit_indices_seen.add(seg_index)

                # Trigger bounce size effect near landing on flight/out segments
                nonlocal ball_bounce_timer
                if seg.kind in ('flight','out') and local_t > 0.98:
                    ball_bounce_timer = max(ball_bounce_timer, 0.12)

            cont = animator.update_and_draw(screen, dt, draw_ball_at, actors_update=move_players)
            if not cont:
                playing_anim = False
                # Prepare a brief terminal overlay marker
                segs = animator.preview_trajectory(None)
                if segs:
                    last = segs[-1]
                    overlay_pos = last.end_px
                    if current_outcome is not None:
                        if current_outcome.reason == "Out":
                            overlay_text = "OUT"
                            overlay_color = (236, 88, 64)
                        elif current_outcome.reason == "Net":
                            overlay_text = "NET"
                            overlay_color = (200, 170, 0)
                        else:
                            overlay_text = "MISS"
                            overlay_color = (220, 220, 220)
                        # Show DOUBLE FAULT explicitly when it happens
                        try:
                            if getattr(current_outcome, 'serve_faults', 0) >= 2:
                                overlay_text = "DOUBLE FAULT"
                                overlay_color = (236, 88, 64)
                        except Exception:
                            pass
                        overlay_timer = 1.2
                # Now that animation finished, update HUD last_point and last_outcome
                if current_outcome is not None:
                    hud.update(last_point=(f"{current_outcome.reason}: {(current_outcome.name_a if current_outcome.winner=='A' else current_outcome.name_b)} won the point"))
                    last_outcome = current_outcome
                    last_point_index = current_point_index
                current_outcome = None

        # Apply bounce size effect before drawing
        if ball_bounce_timer > 0.0:
            ball_bounce_timer = max(0.0, ball_bounce_timer - dt)
            # Temporarily enlarge ball size for this frame
            ball.radius_px = max(ball_base_radius, int(ball_base_radius * 2))
        else:
            ball.radius_px = ball_base_radius

        # Draw scene
        draw_everything()
        # Draw hit markers (decay over time)
        if hit_markers:
            next_markers = []
            for (hx, hy), c, ttl in hit_markers:
                ttl -= dt
                if ttl > 0:
                    # Simple ring only, no swing slashes
                    x0, y0 = int(hx), int(hy)
                    pygame.draw.circle(screen, c, (x0, y0), 6, 2)
                    next_markers.append(((hx, hy), c, ttl))
            hit_markers = next_markers
        # Draw terminal overlay at top center only (OUT, NET, MISS) so the
        # area near the ball stays clean.
        if overlay_timer > 0 and overlay_text:
            overlay_timer = max(0.0, overlay_timer - dt)
            label2 = pygame.font.SysFont("arial", 20, bold=True).render(overlay_text, True, (255, 255, 255))
            tx = (screen.get_width() - label2.get_width()) // 2
            ty = 8
            bg2 = pygame.Surface((label2.get_width() + 8, label2.get_height() + 4), pygame.SRCALPHA)
            bg2.fill((0, 0, 0, 140))
            pygame.draw.rect(bg2, overlay_color, bg2.get_rect(), 1)
            screen.blit(bg2, (tx - 4, ty - 2))
            screen.blit(label2, (tx, ty))
        # Draw first-serve fault banner under the court (simple big yellow text)
        if fault_banner_timer > 0 and fault_banner_text:
            fault_banner_timer = max(0.0, fault_banner_timer - dt)
            banner_font = pygame.font.SysFont("arial", 60, bold=True)
            banner_surf = banner_font.render(fault_banner_text, True, (255, 221, 0))
            ox, oy = court.layout.origin_px
            _, ch = court.layout.size_px
            bx = (screen.get_width() - banner_surf.get_width()) // 2
            by = int(oy + ch + 20)
            by = min(by, screen.get_height() - banner_surf.get_height() - 8)
            bg = pygame.Surface((banner_surf.get_width() + 20, banner_surf.get_height() + 10), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 140))
            screen.blit(bg, (bx - 10, by - 5))
            screen.blit(banner_surf, (bx, by))

        # Present the composed frame (moved flip here to ensure overlays are visible)
        pygame.display.flip()
    pygame.quit()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())



