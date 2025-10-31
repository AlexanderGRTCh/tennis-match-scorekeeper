from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, Optional, Tuple, List, Dict
import random


PointLabel = {0: "Love", 1: "15", 2: "30", 3: "40"}

# Serve behavior tuning. These keep the model simple and readable.
# First serve is in most of the time. Second serve is safer.
FIRST_SERVE_IN_PROB = 0.65
SECOND_SERVE_IN_PROB = 0.9


@dataclass
class MatchConfig:
    player_a: str
    player_b: str
    max_sets: int  # 3 or 5
    starting_bias: int  # 0..100, where probability of B winning a point = bias%
    seed: Optional[int] = None
    # Momentum tuning (defaults follow the spec):
    point_delta: int = 1
    game_delta: int = 2
    set_delta: int = 5


@dataclass
class ScoreState:
    sets_a: int = 0
    sets_b: int = 0
    games_a: int = 0
    games_b: int = 0
    points_a: int = 0
    points_b: int = 0
    # Base bias (without server adjustment). Probability percent that B wins a point.
    bias: int = 50
    # Net momentum toward B (positive) or toward A (negative).
    momentum_net: float = 0.0
    # True if A serving this game; alternates each game.
    server_is_a: bool = True


def clamp_bias(value: int) -> int:
    """Clamp a bias value into a safe range.

    This keeps both players with some chance to win a point.
    """
    return max(10, min(90, value))


def clamp_bias_float(value: float) -> float:
    """Clamp a float bias to the same safe range.

    This is used during intermediate momentum math.
    """
    return max(10.0, min(90.0, value))


def random_digit_biased(bias: int, rng: random.Random) -> int:
    """Return zero for A win or one for B win with a given bias.

    Probability of one equals bias percent from zero to one hundred.
    """
    # Use 0..99 threshold so bias=100 means always 1, bias=0 means always 0
    threshold = bias
    roll = rng.randint(0, 99)
    return 1 if roll < threshold else 0


def game_score_string(points_a: int, points_b: int, name_a: str, name_b: str) -> str:
    """Return a friendly string for the game score within a game.

    This handles normal points and the deuce and advantage states.
    """
    if points_a >= 3 and points_b >= 3:
        if points_a == points_b:
            return "Deuce"
        elif points_a == points_b + 1:
            return f"Ad {name_a}"
        elif points_b == points_a + 1:
            return f"Ad {name_b}"
    # Normal scoring
    left = PointLabel.get(points_a, "40")
    right = PointLabel.get(points_b, "40")
    return f"{left} - {right}"


def check_game_winner(points_a: int, points_b: int) -> Optional[str]:
    """Return A or B if a game is won with a two point margin.

    This implements the standard game rule.
    """
    if (points_a >= 4 or points_b >= 4) and abs(points_a - points_b) >= 2:
        return "A" if points_a > points_b else "B"
    return None


def check_set_winner(games_a: int, games_b: int) -> Optional[str]:
    """Return A or B if a set is won by two games or at seven.

    This is a simple no tie break model where seven to five or seven to six ends a set.
    """
    if (games_a >= 6 or games_b >= 6) and abs(games_a - games_b) >= 2:
        return "A" if games_a > games_b else "B"
    # No tie-break: if 6-6, next game wins 7-6
    if games_a == 7 or games_b == 7:
        return "A" if games_a == 7 else "B"
    return None


def sets_needed_to_win(max_sets: int) -> int:
    """Return the number of sets needed to win the match."""
    return (max_sets // 2) + 1


def simulate_match(cfg: MatchConfig) -> Generator[Tuple[str, Dict], None, None]:
    """Simulate a match and yield simple events that describe progress.

    The generator yields start point game set and match events. The point event
    now also includes serve details so the user interface can render a proper
    first and second serve flow.
    """
    rng = random.Random(cfg.seed)

    # Effective deltas are reduced by half for a gentler momentum effect.
    point_delta_half = cfg.point_delta * 0.5
    game_delta_half = cfg.game_delta * 0.5
    set_delta_half = cfg.set_delta * 0.5

    # Initialize state with base bias
    state = ScoreState(bias=clamp_bias(cfg.starting_bias))

    def recompute_base_bias_from_momentum() -> None:
        """Recalculate the base bias after momentum changes.

        This applies a small pullback so momentum does not run away.
        """
        base = cfg.starting_bias + 0.8 * state.momentum_net
        state.bias = int(round(clamp_bias_float(base)))

    def effective_bias_for_sampling() -> int:
        """Return the effective bias after applying server advantage.

        Server gets a small advantage for realism.
        """
        server_adj = -3 if state.server_is_a else 3
        eff = state.bias + server_adj
        return clamp_bias(int(round(eff)))

    yield (
        "start",
        {"player_a": cfg.player_a, "player_b": cfg.player_b, "max_sets": cfg.max_sets},
    )

    target_sets = sets_needed_to_win(cfg.max_sets)

    while state.sets_a < target_sets and state.sets_b < target_sets:
        # Play points until game ends
        while True:
            # Compute serve side based on points already in this game
            total_pts_before = state.points_a + state.points_b
            serve_side = "deuce" if total_pts_before % 2 == 0 else "ad"

            # First and second serve model
            serve_faults = 0
            fault_kinds: List[str] = []

            def do_serve_attempt(prob_in: float) -> bool:
                """Return True if serve lands in the correct box.

                A simple random check models a fault or a clean serve.
                """
                roll = rng.random()
                return roll < prob_in

            def pick_fault_kind() -> str:
                """Return Net or Out for a serve fault type."""
                return "Net" if rng.random() < 0.5 else "Out"

            # First serve
            first_in = do_serve_attempt(FIRST_SERVE_IN_PROB)
            if not first_in:
                serve_faults = 1
                fault_kinds.append(pick_fault_kind())
                # Second serve
                second_in = do_serve_attempt(SECOND_SERVE_IN_PROB)
                if not second_in:
                    serve_faults = 2
                    fault_kinds.append(pick_fault_kind())
                    # Double fault awards point to receiver
                    if state.server_is_a:
                        state.points_b += 1
                        state.momentum_net += point_delta_half
                        recompute_base_bias_from_momentum()
                        point_winner = "B"
                        point_name = cfg.player_b
                    else:
                        state.points_a += 1
                        state.momentum_net -= point_delta_half
                        recompute_base_bias_from_momentum()
                        point_winner = "A"
                        point_name = cfg.player_a

                    # Check game state after the double fault point
                    game_winner = check_game_winner(state.points_a, state.points_b)
                    if game_winner is None:
                        game_text = game_score_string(
                            state.points_a, state.points_b, cfg.player_a, cfg.player_b
                        )
                        yield (
                            "point",
                            {
                                "winner": point_name,
                                "game_text": game_text,
                                "bias": effective_bias_for_sampling(),
                                "server_is_a": state.server_is_a,
                                "serve_side": serve_side,
                                "serve_faults": serve_faults,
                                "serve_fault_kinds": tuple(fault_kinds),
                            },
                        )
                        continue
                    else:
                        # Emit point that also closed the game
                        game_winner_name = cfg.player_a if game_winner == "A" else cfg.player_b
                        yield (
                            "point",
                            {
                                "winner": point_name,
                                "game_text": f"Game {game_winner_name}",
                                "bias": effective_bias_for_sampling(),
                                "server_is_a": state.server_is_a,
                                "serve_side": serve_side,
                                "serve_faults": serve_faults,
                                "serve_fault_kinds": tuple(fault_kinds),
                            },
                        )
                        # Update game counters then reset points for next game
                        if game_winner == "A":
                            state.games_a += 1
                        else:
                            state.games_b += 1
                        state.points_a = 0
                        state.points_b = 0
                        # Emit game event with the new set score
                        yield ("game", {"winner": game_winner_name, "set_score": (state.games_a, state.games_b)})

                        set_winner = check_set_winner(state.games_a, state.games_b)
                        if set_winner is not None:
                            if set_winner == "A":
                                state.sets_a += 1
                                set_winner_name = cfg.player_a
                                state.momentum_net -= set_delta_half
                                recompute_base_bias_from_momentum()
                                final_games = (state.games_a, state.games_b)
                            else:
                                state.sets_b += 1
                                set_winner_name = cfg.player_b
                                state.momentum_net += set_delta_half
                                recompute_base_bias_from_momentum()
                                final_games = (state.games_a, state.games_b)
                            yield ("set", {"winner": set_winner_name, "final_games": final_games})
                            state.games_a = 0
                            state.games_b = 0
                        # Alternate server for next game
                        state.server_is_a = not state.server_is_a
                        break

            # If here and serve_faults < 2 then a live point will be played
            # Bias used for rally sampling includes the server advantage
            digit = random_digit_biased(effective_bias_for_sampling(), rng)
            if digit == 0:
                state.points_a += 1
                state.momentum_net -= point_delta_half
                recompute_base_bias_from_momentum()
                point_winner = "A"
                point_name = cfg.player_a
            else:
                state.points_b += 1
                state.momentum_net += point_delta_half
                recompute_base_bias_from_momentum()
                point_winner = "B"
                point_name = cfg.player_b

            # Check game state after the rally point
            game_winner = check_game_winner(state.points_a, state.points_b)

            if game_winner is None:
                game_text = game_score_string(
                    state.points_a, state.points_b, cfg.player_a, cfg.player_b
                )
                yield (
                    "point",
                    {
                        "winner": point_name,
                        "game_text": game_text,
                        "bias": effective_bias_for_sampling(),
                        "server_is_a": state.server_is_a,
                        "serve_side": serve_side,
                        "serve_faults": serve_faults,
                        "serve_fault_kinds": tuple(fault_kinds),
                    },
                )
                continue

            # Game is won by point_winner
            if game_winner == "A":
                state.games_a += 1
                game_winner_name = cfg.player_a
                # Momentum for game: towards winner (A)
                state.momentum_net -= game_delta_half
                recompute_base_bias_from_momentum()
            else:
                state.games_b += 1
                game_winner_name = cfg.player_b
                state.momentum_net += game_delta_half
                recompute_base_bias_from_momentum()

            # Emit point line that also acknowledges game end
            yield (
                "point",
                {
                    "winner": point_name,
                    "game_text": f"Game {game_winner_name}",
                    "bias": effective_bias_for_sampling(),
                    "server_is_a": state.server_is_a,
                    "serve_side": serve_side,
                    "serve_faults": serve_faults,
                    "serve_fault_kinds": tuple(fault_kinds),
                },
            )

            # Reset points for next game
            state.points_a = 0
            state.points_b = 0

            # Emit game event and check set
            yield ("game", {"winner": game_winner_name, "set_score": (state.games_a, state.games_b)})

            set_winner = check_set_winner(state.games_a, state.games_b)
            if set_winner is not None:
                if set_winner == "A":
                    state.sets_a += 1
                    set_winner_name = cfg.player_a
                    # Momentum for set: towards winner (A)
                    state.momentum_net -= set_delta_half
                    recompute_base_bias_from_momentum()
                    final_games = (state.games_a, state.games_b)
                else:
                    state.sets_b += 1
                    set_winner_name = cfg.player_b
                    state.momentum_net += set_delta_half
                    recompute_base_bias_from_momentum()
                    final_games = (state.games_a, state.games_b)

                # Emit set event
                yield ("set", {"winner": set_winner_name, "final_games": final_games})

                # Reset game score for next set
                state.games_a = 0
                state.games_b = 0

            # Break to start next game or next set and alternate server
            state.server_is_a = not state.server_is_a
            break

        # Check if match ends after the set update
        if state.sets_a >= target_sets or state.sets_b >= target_sets:
            break

    # Match end
    match_winner_name = cfg.player_a if state.sets_a > state.sets_b else cfg.player_b
    yield ("match", {"winner": match_winner_name, "final_sets": (state.sets_a, state.sets_b)})
