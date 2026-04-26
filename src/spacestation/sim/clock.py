"""Simulation clock and tick scheduling.

The simulation runs in fixed-size physics ticks (default 1 s of sim time)
multiplied by a user-controllable time scale. The Textual app calls
``Engine.advance(real_dt)`` every render and the engine consumes whole ticks
out of an accumulator so all physics integrates at a stable step regardless
of UI frame rate.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Clock:
    physics_dt: float = 1.0       # seconds of sim time per physics tick
    time_scale: float = 1.0       # 1 real second = N sim seconds
    sim_time_s: float = 0.0       # total elapsed sim seconds
    paused: bool = False
    _accumulator: float = 0.0

    def step(self, real_dt: float) -> int:
        """Advance the accumulator by real_dt and return the number of whole
        physics ticks owed to the engine."""
        if self.paused:
            return 0
        self._accumulator += real_dt * self.time_scale
        ticks = 0
        # Cap how many we can run in one frame so a stalled UI doesn't dump
        # an hour of ticks at once and blow the budget.
        while self._accumulator >= self.physics_dt and ticks < 1000:
            self._accumulator -= self.physics_dt
            self.sim_time_s += self.physics_dt
            ticks += 1
        return ticks

    def set_scale(self, scale: float) -> None:
        self.time_scale = max(0.0, scale)
