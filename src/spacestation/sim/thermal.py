"""Heat balance per compartment.

Each compartment has a wall heat capacity (the structure absorbs/buffers
energy) plus its gas heat capacity. Heat enters from occupants, equipment,
heaters, and reactors. It leaves via:

  * conduction through the hull to the outside (vacuum at ~3 K, sun at higher)
  * conduction to neighboring compartments through the bulkhead
  * net infrared radiation at the hull surface (Stefan-Boltzmann)

We keep the math simple but correct in sign and order-of-magnitude. The aim
is for an unheated compartment in shade to cool noticeably over an hour, and
a heated compartment with a body in it to drift toward set-point.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .atmosphere import GasMix
from .constants import SIGMA, T_NORMAL_K


@dataclass
class ThermalShell:
    """The structure surrounding a compartment's atmosphere.

    Stations are mostly aluminum; this rolls hull + furnishings into a
    single lumped-thermal-mass body.
    """
    wall_mass_kg: float = 500.0          # ~modest module
    wall_specific_heat: float = 900.0    # J / (kg K), aluminum
    wall_temp_k: float = T_NORMAL_K
    hull_area_m2: float = 30.0           # m^2 of outer hull
    bulkhead_u_w_per_k: float = 50.0     # conductance through the bulkhead per neighbor (W/K)
    hull_emissivity: float = 0.85        # painted aluminum
    insulation_u_w_per_k: float = 5.0    # conductance from inside air to wall

    # External environment seen by hull (defaults: shade-side LEO)
    external_temp_k: float = 3.0
    solar_flux_w: float = 0.0            # W absorbed (set by station orbit)

    @property
    def heat_capacity(self) -> float:
        return self.wall_mass_kg * self.wall_specific_heat


def step_thermal(
    gas: GasMix,
    shell: ThermalShell,
    occupant_heat_w: float,
    equipment_heat_w: float,
    dt: float,
) -> None:
    """Advance a compartment's thermal state by ``dt`` seconds.

    Order of operations per tick:
      1. add occupant + equipment heat to the gas
      2. exchange between gas and wall (insulation_u)
      3. exchange between wall and outside (radiative + solar)
      4. apply the temperature changes
    """
    cv_gas = gas.heat_capacity()
    cv_wall = shell.heat_capacity

    # 1) Internal sources warm the gas directly
    q_in = (occupant_heat_w + equipment_heat_w) * dt

    # 2) Insulation: wall <-> gas
    dT = gas.temperature - shell.wall_temp_k
    q_gas_to_wall = shell.insulation_u_w_per_k * dT * dt

    # 3) External: wall radiates to environment, absorbs solar
    sb = (
        shell.hull_emissivity * SIGMA * shell.hull_area_m2
        * (shell.wall_temp_k ** 4 - shell.external_temp_k ** 4)
    )  # W lost
    q_wall_to_outside = (sb - shell.solar_flux_w) * dt

    # Apply
    if cv_gas > 0:
        gas.temperature += (q_in - q_gas_to_wall) / cv_gas
    if cv_wall > 0:
        shell.wall_temp_k += (q_gas_to_wall - q_wall_to_outside) / cv_wall


def step_bulkheads(
    shells: Dict[str, ThermalShell],
    connections,
    dt: float,
) -> None:
    """Conductive heat transfer between adjacent compartments through bulkheads."""
    for c in connections:
        if c.a == "VACUUM" or c.b == "VACUUM":
            continue
        sa = shells.get(c.a)
        sb = shells.get(c.b)
        if sa is None or sb is None:
            continue
        u = min(sa.bulkhead_u_w_per_k, sb.bulkhead_u_w_per_k)
        # If door is open, conductance increases dramatically (gas swap dominates)
        if c.open:
            u *= 5.0
        dT = sa.wall_temp_k - sb.wall_temp_k
        q = u * dT * dt
        if sa.heat_capacity > 0:
            sa.wall_temp_k -= q / sa.heat_capacity
        if sb.heat_capacity > 0:
            sb.wall_temp_k += q / sb.heat_capacity
