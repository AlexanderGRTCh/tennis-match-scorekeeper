"""Model adapter package for the Tennis Match Simulator.

This package provides thin adapters over the existing `tennis.engine`
so that other front-ends (e.g., a Pygame GUI) can consume point-by-point
outcomes and current score without re-implementing the simulation rules.
"""

__all__ = ["adapter"]

