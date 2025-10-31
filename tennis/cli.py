from __future__ import annotations

import argparse
import sys
import re
from typing import Callable

from .engine import MatchConfig, simulate_match


def prompt_with_retries(prompt: str, validate: Callable[[str], bool], transform: Callable[[str], object] = lambda x: x, max_attempts: int = 10):
    """Ask for input with validation and a small retry budget.

    Returns the transformed value or exits on repeated invalid entries.
    """
    attempts = 0
    while attempts < max_attempts:
        try:
            raw = input(prompt).strip()
        except EOFError:
            print("Error: no input provided.")
            sys.exit(1)
        if validate(raw):
            try:
                return transform(raw)
            except Exception:
                print("Invalid input. Please try again.")
                attempts += 1
                continue
        else:
            print("Invalid input. Please try again.")
            attempts += 1
    print("Multiple invalid attempts. Exiting.")
    sys.exit(1)


def is_valid_name(s: str) -> bool:
    """Return True if a player name has only letters and spaces."""
    s = s.strip()
    return bool(s) and re.fullmatch(r"[A-Za-z ]+", s) is not None


def is_valid_sets(s: str) -> bool:
    """Return True for three or five sets."""
    if not s.isdigit():
        return False
    v = int(s)
    return v in (3, 5)


def is_valid_bias(s: str) -> bool:
    """Return True if bias is within zero to one hundred inclusive."""
    if not s.isdigit():
        return False
    v = int(s)
    return 0 <= v <= 100


def main(argv=None) -> int:
    """Run the text mode interface for the tennis simulator.

    This accepts flags or asks for values and prints each event as text.
    """
    parser = argparse.ArgumentParser(description="Tennis match scorekeeper (CLI)")
    parser.add_argument("--player-a", dest="player_a", type=str, help="Player A name", default=None)
    parser.add_argument("--player-b", dest="player_b", type=str, help="Player B name", default=None)
    parser.add_argument("--sets", dest="max_sets", type=int, choices=[3, 5], help="Max sets (3 or 5)", default=None)
    parser.add_argument("--bias", dest="starting_bias", type=int, help="Starting bias (0..100)", default=None)
    parser.add_argument("--seed", dest="seed", type=int, help="Random seed for reproducibility", default=None)
    parser.add_argument("--point-delta", dest="point_delta", type=int, default=1, help="Bias change per point toward winner (default 1)")
    parser.add_argument("--game-delta", dest="game_delta", type=int, default=2, help="Bias change per game toward winner (default 2)")
    parser.add_argument("--set-delta", dest="set_delta", type=int, default=5, help="Bias change per set toward winner (default 5)")

    args = parser.parse_args(argv)

    if args.player_a is None:
        player_a = prompt_with_retries("Player A name: ", is_valid_name, str)
    else:
        player_a = args.player_a.strip()
        if not is_valid_name(player_a):
            print("Invalid input. Please try again.")
            return 2

    if args.player_b is None:
        player_b = prompt_with_retries("Player B name: ", is_valid_name, str)
    else:
        player_b = args.player_b.strip()
        if not is_valid_name(player_b):
            print("Invalid input. Please try again.")
            return 2

    if args.max_sets is None:
        max_sets = prompt_with_retries("Number of sets (3 or 5): ", is_valid_sets, int)
    else:
        max_sets = args.max_sets
        if max_sets not in (3, 5):
            print("Invalid input. Please try again.")
            return 2

    if args.starting_bias is None:
        starting_bias = prompt_with_retries("Starting bias (0..100): ", is_valid_bias, int)
    else:
        starting_bias = args.starting_bias
        if not (0 <= starting_bias <= 100):
            print("Invalid input. Please try again.")
            return 2

    cfg = MatchConfig(
        player_a=player_a,
        player_b=player_b,
        max_sets=max_sets,
        starting_bias=starting_bias,
        seed=args.seed,
        point_delta=args.point_delta,
        game_delta=args.game_delta,
        set_delta=args.set_delta,
    )

    # Start simulation and print exact-style outputs
    for event, data in simulate_match(cfg):
        if event == "start":
            print(f"Start of play - {cfg.player_a} vs {cfg.player_b} - best out of {cfg.max_sets} sets")
        elif event == "point":
            winner = data["winner"]
            text = data["game_text"]
            if text.startswith("Game "):
                # Exactly: "Point <Name>, Game <Name>"
                print(f"Point {winner}, {text}")
            else:
                # Exactly: "Point <Name>, Game Score: <text>"
                print(f"Point {winner}, Game Score: {text}")
            print(f"Bias: {data['bias']}")
        elif event == "game":
            ga, gb = data["set_score"]
            print(f"Set Score: {cfg.player_a} vs {cfg.player_b} {ga} - {gb}")
        elif event == "set":
            winner = data["winner"]
            ga, gb = data["final_games"]
            print(f"Set won by {winner}. Games: {cfg.player_a} vs {cfg.player_b} {ga} - {gb}")
        elif event == "match":
            sa, sb = data.get("final_sets", (None, None))
            if sa is not None and sb is not None:
                print(
                    f"Winner: {data['winner']}. Final Score (sets): {cfg.player_a} vs {cfg.player_b} {sa} - {sb}"
                )
            else:
                print(f"Winner: {data['winner']}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
