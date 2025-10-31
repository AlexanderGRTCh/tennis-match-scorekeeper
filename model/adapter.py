from __future__ import annotations

"""Thin adapter over `tennis.engine` to feed a GUI.

Exposes `PointStream`, an iterator that yields one structured record per
simulated point, including server/receiver, serve side, winner, a terminal
reason for animation, and current scoreboard/bias as computed by the model.

The adapter consumes the underlying `simulate_match` generator to update
internal game/set/match state and server alternation (server starts as A and
alternates each game, mirroring the engine). The GUI should not re-decide
point winners—this stream carries the winner decided by the model.
"""

from dataclasses import dataclass
from typing import Generator, Iterator, Literal, Optional, Tuple, Sequence
import random

from tennis.engine import (
    MatchConfig,
    simulate_match,
    game_score_string,
    sets_needed_to_win,
)


Side = Literal["deuce", "ad"]
PlayerKey = Literal["A", "B"]
Reason = Literal["Net", "Out", "Miss"]


@dataclass
class PointOutcome:
    """Simple record for a point so the GUI can animate it.

    This carries serve info winner a short reason and live scores.
    """

    # Who serves this point, and on which side
    server: PlayerKey
    receiver: PlayerKey
    side: Side

    # Winner for the point as decided by the model
    winner: PlayerKey
    # Terminal reason for the animation (does not affect model state)
    reason: Reason

    # Human names
    name_a: str
    name_b: str

    # Live scoreboard after applying this point
    game_text: str
    games: Tuple[int, int]
    sets: Tuple[int, int]
    best_of: int

    # Effective bias used by the model (0..100) after this point
    bias: int

    # Match finished and match winner (if applicable)
    match_over: bool = False
    match_winner_name: Optional[str] = None

    # Serve details for realism in the animator
    serve_faults: int = 0
    serve_fault_kinds: Tuple[str, ...] = ()


def _name_to_key(name: str, a: str, b: str) -> PlayerKey:
    """Map a human name to player key A or B."""
    return "A" if name == a else "B"


def PointStream(cfg: MatchConfig) -> Iterator[PointOutcome]:
    """Yield a structured outcome for each point.

    This pulls from the engine event stream and keeps track of games and sets.
    A small RNG is used only for cosmetic animation choices.
    """

    it = simulate_match(cfg)
    lookahead: Optional[Tuple[str, dict]] = None

    def get_next():
        nonlocal lookahead
        if lookahead is not None:
            # This consumes the buffered event if we looked ahead
            item = lookahead
            lookahead = None
            return item
        return next(it)

    # Internal state to align layout and scoreboard
    name_a = cfg.player_a
    name_b = cfg.player_b
    games_a = games_b = 0
    sets_a = sets_b = 0
    pts_a = pts_b = 0
    server_is_a = True  # must mirror engine default
    target_sets = sets_needed_to_win(cfg.max_sets)

    # Deterministic RNG for visualization choices
    vis_rng = random.Random() if cfg.seed is None else random.Random(cfg.seed)
    point_index = 0

    pending_match_over: Optional[str] = None

    while True:
        try:
            event, data = get_next()
        except StopIteration:
            break
        if event == "start":
            # nothing to yield yet
            continue

        if event == "point":
            # Use engine provided serve data when present
            total_pts_before = pts_a + pts_b
            side_val = data.get("serve_side")
            side: Side = side_val if side_val in ("deuce", "ad") else ("deuce" if total_pts_before % 2 == 0 else "ad")
            srv_is_a = bool(data.get("server_is_a", server_is_a))
            server: PlayerKey = "A" if srv_is_a else "B"
            receiver: PlayerKey = "B" if srv_is_a else "A"

            winner_name = data["winner"]
            winner_key = _name_to_key(winner_name, name_a, name_b)
            bias = int(data.get("bias", 50))

            # Update points locally to compute fresh game_text and games
            if winner_key == "A":
                pts_a += 1
            else:
                pts_b += 1

            # Text from engine reflects state after awarding the point
            game_text = data["game_text"]

            # Determine if this point ended the game (engine uses "Game <Name>")
            game_ended = game_text.startswith("Game ")

            # Deterministic terminal reason: bias it slightly toward Net/Out on serve
            # without affecting model. Stable per point_index.
            pr = vis_rng.random()
            serve_faults = int(data.get("serve_faults", 0))
            serve_fault_kinds: Tuple[str, ...] = tuple(data.get("serve_fault_kinds", ()))
            if serve_faults >= 2:
                # Double fault should present as the last fault kind visually
                last_kind = serve_fault_kinds[-1] if serve_fault_kinds else "Out"
                reason: Reason = "Net" if last_kind == "Net" else "Out"
            else:
                if total_pts_before == 0:
                    # On serve we slightly raise chance of Net or Out visuals
                    reason = ("Net" if pr < 0.4 else ("Out" if pr < 0.75 else "Miss"))
                else:
                    reason = ("Miss" if pr < 0.6 else ("Out" if pr < 0.85 else "Net"))

            # If game ended, advance games and reset points; also alternate server
            if game_ended:
                game_winner_key: PlayerKey = _name_to_key(game_text[5:], name_a, name_b)
                if game_winner_key == "A":
                    games_a += 1
                else:
                    games_b += 1
                # Reset points for next game
                pts_a = 0
                pts_b = 0
                # Alternate server
                server_is_a = not server_is_a

                # After a game, engine may emit 'game' and optional 'set'
                # Consume them to keep sets/games in sync for HUD
                # Peek next events if available
                while True:
                    try:
                        nxt_event, nxt_data = get_next()
                    except StopIteration:
                        break
                    if nxt_event == "game":
                        # nothing extra to maintain beyond games_a/b already set
                        continue
                    if nxt_event == "set":
                        # Update set tallies from engine authoritative data
                        final_games = tuple(nxt_data["final_games"])  # (ga, gb)
                        # Engine increments sets AFTER yielding set_winner;
                        # we can compare to our games to decide
                        set_winner_name = nxt_data["winner"]
                        if set_winner_name == name_a:
                            sets_a += 1
                        else:
                            sets_b += 1
                        # After set ends, games reset for next set
                        games_a, games_b = 0, 0
                        continue
                    if nxt_event == "match":
                        pending_match_over = nxt_data["winner"]
                        break
                    # Stop consuming if a new point begins
                    if nxt_event == "point":
                        # push it back by creating a chained iterator with this item first
                        # Simplify by storing the lookahead in a small buffer and yielding it
                        # on the next loop iteration.
                        lookahead = (nxt_event, nxt_data)
                        break
                    else:
                        # Any other event kinds are not expected
                        break

            # Emit outcome for this point
            outcome = PointOutcome(
                server=server,
                receiver=receiver,
                side=side,
                winner=winner_key,
                reason=reason,
                name_a=name_a,
                name_b=name_b,
                game_text=game_text,
                games=(games_a, games_b),
                sets=(sets_a, sets_b),
                best_of=cfg.max_sets,
                bias=bias,
                match_over=bool(pending_match_over),
                match_winner_name=pending_match_over,
                serve_faults=serve_faults,
                serve_fault_kinds=serve_fault_kinds,
            )

            point_index += 1
            yield outcome

        elif event == "match":
            # If match event arrives without a preceding point (unlikely), emit a
            # terminal dummy outcome so GUI can close politely.
            pending_match_over = event and data.get("winner")
            break


__all__ = ["PointOutcome", "PointStream"]
