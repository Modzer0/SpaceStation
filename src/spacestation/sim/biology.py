"""Plants and bioreactors.

Both are "things that take inputs and produce outputs over time" with a
constraint: light/heat/water/CO2 budget for plants, nutrient/temperature
budget for bioreactors.
"""
from __future__ import annotations

from dataclasses import dataclass

from .atmosphere import GasMix
from .constants import PLANT_CO2_FIX_PER_M2_S


@dataclass
class GreenRoom:
    """A compartment dedicated to crops.

    ``area_m2`` of growing surface; ``light_w`` of PAR-equivalent illumination
    (full sun = 300 W/m2 PAR). Photosynthesis fixes CO2 -> O2 at a rate
    proportional to area * (light_w / (300*area)) capped at 1.
    """
    area_m2: float = 0.0
    light_w: float = 0.0
    crop_health: float = 1.0
    water_kg_per_m2_day: float = 1.5
    crop_yield_j_per_m2_day: float = 1.5e6      # ~360 kcal/m2/day (leafy greens)

    def step(self, atm: GasMix, dt: float) -> tuple[float, float, float]:
        """Returns ``(o2_mol_produced, co2_mol_consumed, water_mol_consumed)``."""
        if self.area_m2 <= 0 or self.crop_health <= 0:
            return 0.0, 0.0, 0.0
        light_factor = min(1.0, self.light_w / (300.0 * self.area_m2 + 1e-9))
        rate = (
            PLANT_CO2_FIX_PER_M2_S * self.area_m2 * light_factor * self.crop_health
        )
        co2_used = atm.remove("CO2", rate * dt)
        # 1:1 mol O2 produced per CO2 consumed (ideal)
        atm.add("O2", co2_used)
        # Water: ~5x the CO2 in mass terms; we ignore tank coupling here.
        return co2_used, co2_used, co2_used * 5.0


@dataclass
class Bioreactor:
    """A small heated vat running an engineered organism.

    Configurations supply the actual chemistry; this is the scaffold:
    energy in (heater + stirrer), inputs (substrate, water), outputs
    (target product, waste).
    """
    name: str = "bioreactor-1"
    volume_l: float = 5.0
    temperature_k: float = 310.0
    target_temp_k: float = 310.0
    heater_w: float = 0.0
    online: bool = False
    productivity: float = 0.0   # 0..1 culture health & throughput
    purpose: str = "idle"       # human description: "consumes CO2", "produces vitamin C", ...

    def step(self, dt: float) -> None:
        if not self.online:
            self.productivity = max(0.0, self.productivity - 0.0001 * dt)
            return
        # Heater drives temperature toward target
        delta = self.target_temp_k - self.temperature_k
        self.temperature_k += delta * 0.001 * dt + (self.heater_w / 5000.0) * dt
        # Productivity rises if conditions are good
        if abs(self.temperature_k - self.target_temp_k) < 2.0:
            self.productivity = min(1.0, self.productivity + 0.0005 * dt)
        else:
            self.productivity = max(0.0, self.productivity - 0.0005 * dt)
