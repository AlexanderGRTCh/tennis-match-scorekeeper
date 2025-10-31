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

During rallies the ball follows straight line segments that alternate halves around the net. At the end of a point the GUI shows a brief overlay that matches the terminal reason such as OUT, NET or MISS and it marks the location. There is a light ball trail, a small hit marker at contact and a tiny bounce size pop so it feels a bit more alive. A simple chair umpire tower is rendered outside the top of the court at the net for a touch of realism.

Controls

Space or a mouse click plays the next point. R replays the last point exactly using a cached plan. S toggles animation speed and the current multiplier is shown in the HUD. Press Esc or Q to quit.

How It Works

The model that decides outcomes lives in `tennis/engine.py`. It simulates points, games and sets with a basic momentum mechanic and small server advantage. For each point it yields events that include who served, the side, the winner and the live score text. A thin adapter in `model/adapter.py` turns those events into a stream the GUI can consume and also chooses a visual terminal reason for the animation. The GUI in `gui/app.py` builds sprites, plans a rally using `gui/animator.py` and drives the frame loop.

The court coordinates are in meters. The renderer maps meters to pixels with a single consistent scale so resizing keeps the aspect intact. The animator creates a short serve plus rally with deterministic randomness so you can replay the previous point and see the exact same path again. Serve faults are handled explicitly. After a first fault there is a short pause and a banner that says NET - second serve or OUT - second serve. On a double fault the point ends immediately.

Configuration Flags

`--player-a` and `--player-b` set the names. `--sets` chooses three or five. `--bias` is the probability percent that Player B wins a point before the server adjustment. `--seed` makes visuals and the engine deterministic which is good for debugging. `--width` and `--height` size the window and `--fps` controls the frame cap.

Code Layout

`tennis/engine.py` contains the match logic and scoring helpers. `model/adapter.py` exposes a clean point stream for the GUI. `gui/court.py` draws the court and handles the meter to pixel mapping. `gui/animator.py` plans the ball path as a series of segments including serve faults and terminal outcomes. `gui/sprites.py` contains very small drawing helpers for players, the ball and the chair umpire tower. `gui/hud.py` renders names, game score, set tallies, a bias bar and hints. `gui/app.py` ties it all together and owns the event loop.

What I Would Improve Next

I would like to replace the player dots with tiny animated figures that pump their legs a little when they move. This can stay purely procedural so it does not require sprite sheets. I would also add subtle sound cues for contact, net and bounces, a simple scoreboard panel that looks closer to a broadcast graphic, and mild shading to give the court some depth without hurting performance.

Notes

This project aims for clear code and predictable behavior that you can adjust without digging through assets. If you spot something odd with fonts or symbols it’s usually a platform font fallback and can be swapped out easily.
