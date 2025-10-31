from __future__ import annotations

"""Constants for GUI rendering and animation.

All distances are in meters (court logical space) unless noted. Rendering code
scales these to pixels at runtime to preserve aspect ratio regardless of the
window size.
"""

# Court standard dimensions (ITF singles)
COURT_LENGTH_M = 23.77
COURT_WIDTH_M = 8.23
NET_Y_FROM_TOP_M = COURT_LENGTH_M / 2.0
SERVICE_LINE_FROM_NET_M = 6.40  # distance from net toward baseline
CENTER_MARK_M = 0.10

# Colors (R,G,B)
COURT_COLOR = (36, 90, 66)
LINE_COLOR = (240, 240, 240)
NET_COLOR = (200, 170, 0)  # dark yellow for the net
BALL_COLOR = (242, 214, 0)
PLAYER_A_COLOR = (66, 135, 245)  # blue for Player A
PLAYER_B_COLOR = (236, 88, 64)   # red for Player B
HUD_TEXT_COLOR = (245, 245, 245)
HUD_BG_COLOR = (0, 0, 0)

# Rendering
DEFAULT_WINDOW = (1024, 640)
TARGET_FPS = 60
PIXELS_PER_METER_BASE = 30  # used as a starting point; final scale computed per window

# Animation speeds (logical m/s, then scaled to px per frame)
BALL_SPEED_MPS = 24.0  # approximate rally speed (tuned for visual effect)
SERVE_SPEED_MPS = 30.0
PLAYER_SPEED_MPS = 10.0

# GUI speed multipliers toggled by 'S'
# Range now spans 0.25x up to 5x
SPEED_STEPS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]

# Padding around the court (in pixels) to keep some margin in window
# Increased to ensure clear blackspace outside the court for out-balls
WINDOW_PADDING_PX = 120
