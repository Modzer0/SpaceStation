"""EVA suit life support.

The suit is essentially a portable, leak-resistant compartment with its own
miniature ECLSS:

  * Pressurized helmet/torso volume of ~45 L at 29.6 kPa pure O2
  * High-pressure O2 tank that bleeds into the helmet to maintain pressure
  * LiOH cartridge that scrubs CO2 (eventually saturates and must be replaced)
  * Battery driving fans, pumps, comms, wrist computer, lights
  * Sublimator / cooling water to dump body heat overboard
  * Cold-gas propellant (SAFER) for emergency translation

Two states matter most:

  * helmet_sealed: True  -- the body breathes the suit's atmosphere
  * helmet_sealed: False -- the body breathes the surrounding compartment
                            (and the suit interior leaks instantly to ambient)

When sealed, the suit interior is its own ``GasMix`` -- the body still calls
``Body.step`` against it the same way it would against a room.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .atmosphere import GasMix
from .constants import (
    LIOH_CO2_PER_MOL, LIOH_MOL_PER_KG, M_MOL,
    SUIT_BATTERY_J, SUIT_LIOH_KG, SUIT_O2_TANK_KG, SUIT_PRESSURE_O2,
    SUIT_PROPELLANT_KG, SUIT_THERMAL_W, SUIT_VOLUME, T_NORMAL_K,
)


@dataclass
class Suit:
    helmet_sealed: bool = True
    o2_tank_kg: float = SUIT_O2_TANK_KG
    lioh_kg: float = SUIT_LIOH_KG
    battery_j: float = SUIT_BATTERY_J
    propellant_kg: float = SUIT_PROPELLANT_KG
    integrity: float = 1.0                # 1.0 intact; 0.0 catastrophic breach
    cooling_w: float = SUIT_THERMAL_W
    volume_m3: float = SUIT_VOLUME

    interior: GasMix = field(default_factory=lambda: GasMix(volume=SUIT_VOLUME, temperature=T_NORMAL_K))

    # Idle electrical draw (fans, pump, wrist computer, lights, comms)
    idle_w: float = 25.0

    def __post_init__(self) -> None:
        # Charge the suit interior with pure O2 at design pressure.
        if self.helmet_sealed and self.interior.total_moles == 0:
            self.charge_interior()

    def charge_interior(self) -> None:
        from .constants import R_GAS
        n = SUIT_PRESSURE_O2 * self.volume_m3 / (R_GAS * T_NORMAL_K)
        self.interior.moles = {"O2": n}
        self.interior.temperature = T_NORMAL_K

    # ------------------------------------------------------------------
    # Per-tick update -- called by the engine before Body.step
    # ------------------------------------------------------------------
    def step(self, ambient: GasMix, dt: float) -> None:
        """Advance the suit's life support by dt seconds.

        If the helmet is sealed:
            * regulator tops the interior up to design pressure from the O2 tank
            * LiOH scrubber removes CO2 from the interior
            * battery drains by idle load
            * any breach in the suit bleeds interior to ambient

        If the helmet is open the interior simply equalizes with ambient
        (we just slam it equal each tick -- it's a tiny volume).
        """
        # Battery
        self.battery_j = max(0.0, self.battery_j - self.idle_w * dt)

        if not self.helmet_sealed:
            # Open helmet: the interior is the ambient
            self.interior.moles = {sp: n * (self.volume_m3 / max(ambient.volume, 1e-6))
                                    for sp, n in ambient.moles.items()}
            self.interior.temperature = ambient.temperature
            return

        # Pressure regulator: maintain SUIT_PRESSURE_O2 in interior using O2 tank
        from .constants import R_GAS
        target_n = SUIT_PRESSURE_O2 * self.volume_m3 / (R_GAS * self.interior.temperature)
        deficit_n = target_n - self.interior.total_moles
        if deficit_n > 0 and self.o2_tank_kg > 0:
            o2_kg_needed = deficit_n * M_MOL["O2"]
            o2_kg_used = min(self.o2_tank_kg, o2_kg_needed)
            self.o2_tank_kg -= o2_kg_used
            self.interior.add("O2", o2_kg_used / M_MOL["O2"])

        # LiOH scrubber: 2 LiOH + CO2 -> Li2CO3 + H2O
        # Scrubber rate is plenty fast for one human; cap at LiOH remaining.
        co2_have = self.interior.moles.get("CO2", 0.0)
        if co2_have > 0 and self.lioh_kg > 0:
            scrub_rate = 0.05  # mol CO2/s max -- way more than human production
            co2_to_remove = min(co2_have, scrub_rate * dt)
            lioh_mol_avail = self.lioh_kg * LIOH_MOL_PER_KG
            co2_capacity = lioh_mol_avail * LIOH_CO2_PER_MOL
            co2_to_remove = min(co2_to_remove, co2_capacity)
            if co2_to_remove > 0:
                self.interior.remove("CO2", co2_to_remove)
                # consume LiOH
                lioh_consumed_mol = co2_to_remove / LIOH_CO2_PER_MOL
                self.lioh_kg = max(0.0, self.lioh_kg - lioh_consumed_mol / LIOH_MOL_PER_KG)
                # LiOH reaction byproduct H2O is small; ignore here.

        # Humidity control (condensing heat exchanger): removes exhaled
        # water vapor before it displaces O2 in the loop. The condensate
        # would normally be routed to a wastewater bag.
        h2o_have = self.interior.moles.get("H2O", 0.0)
        if h2o_have > 0:
            condense_rate = 0.01  # mol/s; well above human respiratory output
            self.interior.remove("H2O", min(h2o_have, condense_rate * dt))

        # Suit breach: leak interior to ambient at rate proportional to (1-integrity)
        if self.integrity < 1.0 and self.interior.total_moles > 0:
            breach_area = (1.0 - self.integrity) * 1e-4  # up to 1 cm^2 at full breach
            from .atmosphere import vent_to_vacuum
            # If ambient is near-vacuum, this is real venting; otherwise tiny dP -> tiny loss
            vent_to_vacuum(self.interior, breach_area, dt)

    # ------------------------------------------------------------------
    # Player interactions
    # ------------------------------------------------------------------
    def toggle_helmet(self, ambient: GasMix) -> str:
        """Toggle the helmet seal. Returns a short human description."""
        self.helmet_sealed = not self.helmet_sealed
        if self.helmet_sealed:
            self.charge_interior()
            return "Helmet sealed. Suit interior pressurized."
        else:
            self.interior = GasMix(volume=self.volume_m3, temperature=ambient.temperature)
            return "Helmet open. Breathing ambient atmosphere."

    def replace_lioh(self, kg: float = SUIT_LIOH_KG) -> None:
        self.lioh_kg = kg

    def refill_o2(self, kg: float = SUIT_O2_TANK_KG) -> None:
        self.o2_tank_kg = kg

    def recharge_battery(self, j: float = SUIT_BATTERY_J) -> None:
        self.battery_j = j

    def damage(self, severity: float) -> None:
        self.integrity = max(0.0, self.integrity - severity)
