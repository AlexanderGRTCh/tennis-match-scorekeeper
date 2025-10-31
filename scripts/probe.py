from collections import Counter
import os, sys

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tennis.engine import MatchConfig, simulate_match


def run(seed: int, point_delta=1, game_delta=2, set_delta=5):
    """Run one simulated match and return per set game scores.

    This uses a fixed configuration and a changing seed.
    """
    cfg = MatchConfig(player_a='A', player_b='B', max_sets=3, starting_bias=50, seed=seed,
                      point_delta=point_delta, game_delta=game_delta, set_delta=set_delta)
    set_scores = []
    for event, data in simulate_match(cfg):
        if event == 'set':
            set_scores.append(tuple(data['final_games']))
    return tuple(set_scores)


def probe(label, **kwargs):
    """Try many seeds and print simple distribution info.

    This is a rough way to eyeball momentum settings.
    """
    c = Counter()
    blowouts = 0
    n = 200
    total_sets = 0
    for s in range(n):
        scores = run(s, **kwargs)
        total_sets += len(scores)
        for a,b in scores:
            if (a==6 and b==0) or (a==0 and b==6):
                blowouts += 1
        c[scores] += 1
    print(f"\n[{label}] matches: {n}  total sets: {total_sets}  blowout rate: {round(blowouts/total_sets,3)}")
    for k,v in c.most_common(5):
        print(v, k)


def main():
    """Run a few probes with different momentum settings."""
    # Defaults per spec
    probe('defaults pd=1 gd=2 sd=5', point_delta=1, game_delta=2, set_delta=5)
    # Lighter momentum
    probe('lighter gd=1 sd=2', point_delta=1, game_delta=1, set_delta=2)
    # Minimal momentum beyond points
    probe('points-only gd=0 sd=0', point_delta=1, game_delta=0, set_delta=0)


if __name__ == '__main__':
    main()
