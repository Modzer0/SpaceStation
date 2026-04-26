"""Ionizing radiation field, shielding, and dose accumulation.

Each compartment carries a per-volume dose-rate (Sv/s). Sources include:

  * background GCR / solar protons attenuated by hull + interior shielding
  * leaking RTG sources (point sources with their own dose-rate)
  * a damaged reactor (large rate that scales with melt-down severity)

Shielding is treated as a single "shielding factor" 0..1 multiplying the
external rate. Adding mass-rich items (water tanks, polyethylene sheets,
lead plate) lowers the factor. The body model integrates whatever rate the
player's current compartment exposes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .constants import BG_LEO_UNSHIELDED


@dataclass
class RadiationSource:
    """A localized source -- e.g., a leaky RTG or a hot reactor."""
    name: str
    dose_rate: float           # Sv/s at 1 m
    decay_per_s: float = 0.0   # set >0 if the source decays during play
    distance_m: float = 1.0    # used for inverse-square if you move closer

    def step(self, dt: float) -> None:
        if self.decay_per_s > 0:
            self.dose_rate = max(0.0, self.dose_rate * (1.0 - self.decay_per_s * dt))

    def field_at(self, distance_m: float) -> float:
        d = max(0.3, distance_m)
        return self.dose_rate * (1.0 / (d * d))


@dataclass
class CompartmentRadiation:
    """Radiation environment for one compartment."""
    background_external: float = BG_LEO_UNSHIELDED  # Sv/s outside the hull
    shielding_factor: float = 0.25                   # 0=opaque, 1=no shielding
    # Sources physically in this compartment.
    sources: List[RadiationSource] = field(default_factory=list)

    def dose_rate(self, occupant_distance_m: float = 1.5) -> float:
        rate = self.background_external * self.shielding_factor
        for s in self.sources:
            rate += s.field_at(occupant_distance_m)
        return rate

    def step(self, dt: float) -> None:
        for s in self.sources:
            s.step(dt)


def step_radiation(rooms: Dict[str, CompartmentRadiation], dt: float) -> None:
    for r in rooms.values():
        r.step(dt)
