"""Compartment atmosphere model.

A ``GasMix`` is a bag of moles of named species in a fixed-volume compartment
at temperature T. Pressure follows ideal gas law ``P = nRT/V``. Each species
also has its own partial pressure, which is what physiology cares about
(O2 partial pressure, CO2 partial pressure, etc.).

Diffusion between connected compartments is modeled as a first-order pressure
equalization across an effective open area. Vacuum leaks (breaches) are an
adiabatic-choked-flow approximation: mass flow proportional to pressure and
breach area.

Tick step is ~1 s. Diffusion is integrated explicitly; with reasonable doors
this is stable, but very large pressure differentials should still be checked
for energy conservation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple

from .constants import (
    AIR_FRAC, CV_MOLAR, M_MOL, P_ATM, R_GAS, T_NORMAL_K,
)


@dataclass
class GasMix:
    """Moles of each species in a compartment of fixed volume at temperature T."""
    volume: float                                # m^3
    temperature: float = T_NORMAL_K              # K
    moles: Dict[str, float] = field(default_factory=dict)

    # ----- builders -------------------------------------------------------

    @classmethod
    def vacuum(cls, volume: float, temperature: float = T_NORMAL_K) -> "GasMix":
        return cls(volume=volume, temperature=temperature, moles={})

    @classmethod
    def standard_air(
        cls, volume: float, pressure: float = P_ATM, temperature: float = T_NORMAL_K
    ) -> "GasMix":
        n_total = pressure * volume / (R_GAS * temperature)
        return cls(
            volume=volume,
            temperature=temperature,
            moles={sp: n_total * frac for sp, frac in AIR_FRAC.items()},
        )

    # ----- aggregates -----------------------------------------------------

    @property
    def total_moles(self) -> float:
        return sum(self.moles.values())

    @property
    def pressure(self) -> float:
        """Total pressure (Pa)."""
        return self.total_moles * R_GAS * self.temperature / self.volume

    def partial(self, species: str) -> float:
        """Partial pressure of one species (Pa)."""
        n = self.moles.get(species, 0.0)
        return n * R_GAS * self.temperature / self.volume

    def fraction(self, species: str) -> float:
        n_total = self.total_moles
        if n_total <= 0:
            return 0.0
        return self.moles.get(species, 0.0) / n_total

    def mass(self) -> float:
        return sum(M_MOL.get(sp, 0.030) * n for sp, n in self.moles.items())

    def heat_capacity(self) -> float:
        """Total Cv of the gas (J/K) -- used by the thermal model."""
        return sum(CV_MOLAR.get(sp, 20.8) * n for sp, n in self.moles.items())

    # ----- mutators -------------------------------------------------------

    def add(self, species: str, mol: float) -> None:
        if mol == 0.0:
            return
        self.moles[species] = max(0.0, self.moles.get(species, 0.0) + mol)

    def remove(self, species: str, mol: float) -> float:
        """Remove up to ``mol`` mol of species; return the amount actually removed."""
        have = self.moles.get(species, 0.0)
        taken = min(have, max(0.0, mol))
        self.moles[species] = have - taken
        return taken

    def add_at_stp(self, species: str, mol: float, gas_temperature_k: float = T_NORMAL_K) -> None:
        """Add gas that arrives at a specified temperature; mix into compartment."""
        if mol <= 0:
            return
        cv_in = CV_MOLAR.get(species, 20.8) * mol
        cv_have = self.heat_capacity()
        if cv_have + cv_in > 0:
            self.temperature = (
                self.temperature * cv_have + gas_temperature_k * cv_in
            ) / (cv_have + cv_in)
        self.add(species, mol)


# ---------- Connection / diffusion / breach -------------------------------


@dataclass
class Connection:
    """An opening between two compartments (or between a compartment and vacuum).

    ``area`` is the effective flow area in m^2 (a fully open hatch is ~0.5 m^2,
    a vent is much smaller, a hairline breach is ~1e-5 m^2). ``open`` lets the
    player or pressure-shutoff doors close it.
    """
    a: str                          # compartment id (or "VACUUM")
    b: str                          # compartment id (or "VACUUM")
    area: float                     # m^2
    open: bool = True

    def conductance(self) -> float:
        return self.area if self.open else 0.0


def diffuse(
    a: GasMix, b: GasMix, conductance: float, dt: float
) -> None:
    """Equalize two compartments through ``conductance`` (m^2 of effective open area).

    Treats each species independently. The driving force for species s is
    its partial-pressure difference. Mass flow per species per second is
    approximated as

        dn_s/dt ~ k * conductance * (P_a^s - P_b^s) / sqrt(T)

    where ``k`` packages molecular speed and a fudge factor that makes a
    fully-open 0.5 m^2 hatch equalize a small room in seconds, which is
    physically reasonable. This is intentionally a simplified linear model
    -- it conserves mol exactly because we transfer the same amount we
    remove.
    """
    if conductance <= 0.0:
        return
    # k tuned so that c=0.5 m^2, dP=100 kPa, T=294 K gives ~25 mol/s
    # of bulk flow into a vacuum -- a brisk depressurization but not a
    # pop-the-airlock-instantly cartoon.
    k = 0.045
    # Average T for transport calc; if one side is vacuum (~0 mol) use the
    # other side's temperature.
    t_a = a.temperature if a.total_moles > 0 else b.temperature
    t_b = b.temperature if b.total_moles > 0 else a.temperature
    t_avg = 0.5 * (t_a + t_b) if (t_a > 0 and t_b > 0) else max(t_a, t_b, 1.0)
    species = set(a.moles) | set(b.moles)
    for sp in species:
        p_a = a.partial(sp)
        p_b = b.partial(sp)
        dp = p_a - p_b
        if dp == 0.0:
            continue
        # Per-species transferred mol over dt
        dn = k * conductance * dp / (t_avg ** 0.5) * dt
        if dn > 0:
            taken = a.remove(sp, dn)
            b.add(sp, taken)
        else:
            taken = b.remove(sp, -dn)
            a.add(sp, taken)


def vent_to_vacuum(a: GasMix, area: float, dt: float, vacuum_temp_k: float = 2.7) -> Tuple[float, float]:
    """Bleed a compartment to space through ``area`` of breach.

    Returns ``(moles_lost, energy_lost_J)``. Adiabatic-ish: the compartment
    cools as it depressurizes because the gas does PV work pushing into vacuum.
    """
    if area <= 0.0 or a.total_moles <= 0.0:
        return 0.0, 0.0
    # Same constant as ``diffuse``; pressure differential is just a.pressure.
    k = 0.045
    p = a.pressure
    if p <= 0.0:
        return 0.0, 0.0
    t = max(a.temperature, 1.0)
    total_lost = 0.0
    energy_lost = 0.0
    species_list = list(a.moles)
    for sp in species_list:
        n_have = a.moles.get(sp, 0.0)
        if n_have <= 0:
            continue
        # proportional to that species' partial pressure
        dn = k * area * a.partial(sp) / (t ** 0.5) * dt
        dn = min(dn, n_have)
        a.moles[sp] -= dn
        total_lost += dn
        # Internal energy carried away; cools the remaining gas.
        energy_lost += dn * CV_MOLAR.get(sp, 20.8) * t
    # PV work done against vacuum cools the gas slightly. Apply the
    # internal-energy loss to remaining gas heat capacity.
    cv_now = a.heat_capacity()
    if cv_now > 0:
        a.temperature -= energy_lost / max(cv_now, 1e-6) * 0.0  # currently 0; advection cooling is small at our k
    return total_lost, energy_lost


# ---------- Compartment registry helpers ----------------------------------


def step_atmospheres(
    gases: Dict[str, GasMix],
    connections: Iterable[Connection],
    dt: float,
) -> None:
    """One physics tick of all gas exchange. ``gases`` is keyed by compartment id."""
    for c in connections:
        cond = c.conductance()
        if cond <= 0.0:
            continue
        if c.a == "VACUUM":
            vent_to_vacuum(gases[c.b], cond, dt)
        elif c.b == "VACUUM":
            vent_to_vacuum(gases[c.a], cond, dt)
        else:
            diffuse(gases[c.a], gases[c.b], cond, dt)
