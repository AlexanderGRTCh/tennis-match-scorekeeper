Tennis Match Scorekeeper with a Pygame GUI

This is a small but complete tennis match simulator and viewer. The engine decides point outcomes with a simple momentum model and the GUI renders a horizontal court with a short animated rally for each point. I focused on clean structure and repeatable visuals rather than throwing in heavy assets or physics, so it’s easy to read and tweak.

Getting Started

Install Python 3.10 or newer. Create a virtual environment if that’s your workflow. Install the only runtime dependency with:

```
pip install pygame
```

Run the GUI with:

```
python -m gui.app
```

You will see a simple prompt for player names, best of sets and a starting bias. If you prefer a non interactive launch, pass flags and skip the prompt:

```
python -m gui.app --no-prompt --player-a Alice --player-b Bob --sets 3 --bias 50 --seed 42 --width 1280 --height 720 --fps 60
```

What You See

The court is drawn to scale for singles, with a net, baselines, sidelines, service lines and the center mark. The view is horizontal so play moves left to right across the screen. The server stands on the correct deuce or ad half according to tennis rules. Serves land diagonally into the legal service box. If the first serve is a fault the GUI shows exactly what happened and that a second serve is coming. A double fault ends the point and is labeled clearly.

During rallies the ball follows straight line segments that alternate halves around the net. At the end of a point the GUI shows a brief overlay at the top center that matches the terminal reason such as OUT, NET or MISS. There is a light ball trail, a small hit marker at contact and a tiny bounce size pop so it feels a bit more alive. The HUD includes a bias bar so you can watch momentum drift during points, then move faster on games and sets. A simple chair umpire tower is rendered outside the top of the court at the net for a touch of realism.

Controls

Space or a mouse click plays the next point. R replays the last point exactly using a cached plan. S toggles animation speed and the current multiplier is shown in the HUD (starts at x0.25). Press Esc or Q to quit.

How It Works

The model that decides outcomes lives in `tennis/engine.py`. It simulates points, games and sets with a basic momentum mechanic and small server advantage. For each point it yields events that include who served, the side, the winner and the live score text. A thin adapter in `model/adapter.py` turns those events into a stream the GUI can consume and also chooses a visual terminal reason for the animation. The GUI in `gui/app.py` builds sprites, plans a rally using `gui/animator.py` and drives the frame loop.

The court coordinates are in meters. The renderer maps meters to pixels with a single consistent scale so resizing keeps the aspect intact. The animator creates a short serve plus rally with deterministic randomness so you can replay the previous point and see the exact same path again. Serve faults are handled explicitly. After a first fault there is a short pause and a large yellow banner below the court that reads SECOND SERVE. On a double fault the point ends immediately.

Momentum Bias

The engine centers around a momentum bias that nudges the next point toward the player who is doing well while staying fair and bounded.

- Base bias represents the chance (in percent) that Player B wins a point before server advantage. It starts from `starting_bias` and updates as play unfolds.
- A net momentum value drifts on each event. Points nudge it by a small step, games by a larger step, and sets by a larger step again. Defaults come from `MatchConfig` as `point_delta=1`, `game_delta=2`, `set_delta=5` and the engine applies half of each for a gentler effect.
- The new base bias is computed as `starting_bias + 0.8 * momentum_net` and clamped to a safe range so both players always have a chance: `10..90`.
- A small server advantage is applied just before sampling the next point winner (`-3` when A serves, `+3` when B serves). The result is the effective bias used to sample the next point.

You can see this live in the HUD bias bar and the numeric bias value. To reproduce scenarios deterministically, set a `--seed` and use R to replay the last point exactly.

Configuration Flags

`--player-a` and `--player-b` set the names. `--sets` chooses three or five. `--bias` is the probability percent that Player B wins a point before the server adjustment. `--seed` makes visuals and the engine deterministic which is good for debugging. `--width` and `--height` size the window and `--fps` controls the frame cap.

Code Layout

`tennis/engine.py` contains the match logic and scoring helpers. `model/adapter.py` exposes a clean point stream for the GUI. `gui/court.py` draws the court and handles the meter to pixel mapping. `gui/animator.py` plans the ball path as a series of segments including serve faults and terminal outcomes. `gui/sprites.py` contains very small drawing helpers for players, the ball and the chair umpire tower. `gui/hud.py` renders names, game score, set tallies, a bias bar and hints. `gui/app.py` ties it all together and owns the event loop.

 



