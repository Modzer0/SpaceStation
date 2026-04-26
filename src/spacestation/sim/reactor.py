"""Reactor models -- RTG, fission (with coolant loop), fusion (with capacitor
ignition), Kilopower (passive), MSR.

These are deliberately *startup-and-failure* models, not a neutronics sim.
The fun is in the procedure: you find a reactor, you supply its prerequisites
(power for ignition, coolant pumps, control rod actuators), and it slowly
comes online -- or melts down if you ignore it.

All reactors expose ``power_w`` (current electrical output) and an
``update(self, dt)`` callable that the ``PowerBus`` calls each tick. Some
also publish radiation by attaching a ``RadiationSource`` to the host
compartment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .constants import RTG_HALF_LIFE_S, RTG_W_PER_KG
from .radiation import RadiationSource


# ====================================================================
# RTG -- decays, only thing that can go wrong is shielding cracks
# ====================================================================

@dataclass
class RTG:
    name: str
    fuel_kg: float = 4.5             # ~22 W electrical
    age_s: float = 0.0
    leak_factor: float = 0.0         # 0..1, 1 = full unshielded gamma
    online: bool = True
    # Linked source so the radiation model picks up leaks.
    source: RadiationSource = field(default=None)  # type: ignore[assignment]

    @property
    def power_w(self) -> float:
        if not self.online:
            return 0.0
        # Decay: P(t) = P0 * 0.5 ^ (t / T_half)
        decay = 0.5 ** (self.age_s / RTG_HALF_LIFE_S)
        return self.fuel_kg * RTG_W_PER_KG * decay

    def thermal_w(self) -> float:
        # Electrical conversion efficiency ~6%; rest is heat (useful!).
        return self.power_w / 0.06

    def update(self, source_obj, dt: float) -> None:
        self.age_s += dt
        source_obj.power_w = self.power_w
        # If leaking, update the radiation source
        if self.source is not None:
            self.source.dose_rate = self.leak_factor * 5e-5  # up to ~180 mSv/h on contact

    def crack_shield(self, severity: float) -> None:
        self.leak_factor = max(self.leak_factor, min(1.0, severity))


# ====================================================================
# Fission reactor with coolant loop
# ====================================================================

class FissionState(str, Enum):
    COLD = "cold"
    PRIMING = "priming"          # coolant pumps starting
    SUBCRITICAL = "subcritical"  # rods inserted, coolant running
    APPROACHING = "approaching"  # rods withdrawing
    POWERED = "powered"
    SCRAMMED = "scrammed"
    MELTDOWN = "meltdown"


@dataclass
class FissionReactor:
    name: str
    rated_w: float = 200_000.0
    state: FissionState = FissionState.COLD
    rod_position: float = 1.0           # 1.0 fully inserted, 0.0 fully out
    coolant_temp_k: float = 295.0
    coolant_pump_w_required: float = 8_000.0
    coolant_flowing: bool = False
    rod_drive_w_required: float = 500.0
    integrity: float = 1.0
    source: RadiationSource = field(default=None)  # type: ignore[assignment]

    def power_w(self) -> float:
        if self.state in (FissionState.POWERED, FissionState.APPROACHING):
            return self.rated_w * (1.0 - self.rod_position) * self.integrity
        return 0.0

    def update(self, source_obj, dt: float) -> None:
        # Update produced power
        source_obj.power_w = self.power_w()
        # Coolant temperature -- core heat warms it; pump moves heat out
        core_heat = self.power_w() * 1.5  # core thermal > electrical
        if self.coolant_flowing:
            heat_removed = self.coolant_pump_w_required * 5.0  # crude; pump moves ~40 kW thermal per 8 kW pump
            self.coolant_temp_k += (core_heat - heat_removed) * dt / 5e5
        else:
            self.coolant_temp_k += core_heat * dt / 5e5
        # Damage / meltdown gate
        if self.coolant_temp_k > 1200.0 and self.state != FissionState.MELTDOWN:
            self.state = FissionState.MELTDOWN
            self.integrity = max(0.0, self.integrity - 0.5)
        if self.state == FissionState.MELTDOWN and self.source is not None:
            self.source.dose_rate = 5e-3  # huge -- 18 Sv/h at 1 m

    def scram(self) -> None:
        self.rod_position = 1.0
        self.state = FissionState.SCRAMMED


# ====================================================================
# Kilopower -- passive cooling, Stirling engine
# ====================================================================

@dataclass
class Kilopower:
    """Reference NASA Kilopower: 1-10 kWe, U-235 fueled, heat-pipe cooled.

    The big advantage: no coolant pumps, just passive heat transport. Player
    inserts the start-up ignition load (a small heater) and progressively
    withdraws the single regulating rod.
    """
    name: str
    rated_w: float = 1_000.0
    rod_position: float = 1.0
    online: bool = False
    ignition_energy_required_j: float = 100_000.0
    ignition_progress_j: float = 0.0
    source: RadiationSource = field(default=None)  # type: ignore[assignment]

    def power_w(self) -> float:
        if not self.online:
            return 0.0
        return self.rated_w * (1.0 - self.rod_position) * 0.85

    def update(self, source_obj, dt: float) -> None:
        source_obj.power_w = self.power_w()


# ====================================================================
# Fusion reactor -- needs huge capacitor charge to ignite
# ====================================================================

@dataclass
class FusionReactor:
    name: str
    rated_w: float = 5_000_000.0
    capacitor_required_j: float = 50_000_000.0  # 50 MJ to ignite
    capacitor_charge_j: float = 0.0
    online: bool = False
    source: RadiationSource = field(default=None)  # type: ignore[assignment]

    def power_w(self) -> float:
        return self.rated_w if self.online else 0.0

    def update(self, source_obj, dt: float) -> None:
        source_obj.power_w = self.power_w()


# ====================================================================
# MSR (molten salt) -- continuous, simpler than fission
# ====================================================================

@dataclass
class MoltenSaltReactor:
    name: str
    rated_w: float = 500_000.0
    salt_temp_k: float = 295.0
    online: bool = False
    salt_target_k: float = 950.0
    drain_plug_frozen: bool = False  # passive safety: lose power -> drain
    source: RadiationSource = field(default=None)  # type: ignore[assignment]

    def power_w(self) -> float:
        if not self.online:
            return 0.0
        # Output proportional to how close salt is to operating temp
        ratio = max(0.0, min(1.0, (self.salt_temp_k - 600.0) / (self.salt_target_k - 600.0)))
        return self.rated_w * ratio

    def update(self, source_obj, dt: float) -> None:
        source_obj.power_w = self.power_w()
